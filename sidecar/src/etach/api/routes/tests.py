"""``/tests``: the test bank, its metadata, content, keys and merges (llm-design §2).

- ``GET /tests?q=`` is the FTS prefix search over display names and metadata (merged tests are
  never listed); without ``q`` every non-merged test, newest change first. Each row has its
  number of current attempts.
- ``PATCH /tests/{id}`` takes ``{meta: {field: value}}`` (through ``write_test_meta`` as a teacher
  write: the fields go into ``edited_fields``) and/or ``{content: TestContent}`` (re-validated with
  ``domain.validators``; a failure → 422 with the failures). Both in one transaction.
  ``{content_text, drop_confirmed?}`` saves the test page (data-model §2.3a, §5.3 v1.9;
  ``domain.review.save_test_text``): 422 ``{message, errors: [{line, message}]}`` when the text
  cannot be read or adds a content-check failure, 422 ``{message, drops: [{question_id, number,
  printed_number, has_key, answers}]}`` when it drops questions with a key or answers that are
  not in ``drop_confirmed``; nothing is saved then. A save settles the test's Review items and
  publishes ``review.changed``. The answer is the same as ``GET /tests/{id}``.
- ``GET /tests/{id}`` adds ``content_text`` (the test as text) and ``review`` (its open items:
  the test's own and those of its current attempts) to the test (llm-design v4.22).
- ``GET /tests`` rows carry ``open_review_count`` (the sidebar marks; v4.22).
- ``PUT /tests/{id}/keys/{question_id}`` takes ``{accepted: [...]}`` (a teacher edit; a changed
  ``accepted`` deletes that question's explanations) or ``{verify: true}``. A key that changed
  queues no run since v4.36 (``run_ids`` is empty): a test with graded attempts goes to
  ``regrade_pending`` (data-model v1.20).
- ``DELETE /tests/{id}/keys/{question_id}`` removes the key and its explanations and settles the
  question's open ``uncertain_key`` items; like a key change it notes ``regrade_pending`` and
  starts no run (refinements D7). The next Grade may write a new AI key.
- ``POST /tests/{id}/regrade`` queues 1 grade run (``key_verified``) per graded attempt of a
  pending test and clears ``regrade_pending``; nothing pending → no run (v4.36).
- ``GET /tests/{id}`` carries ``regrade_pending`` (v4.36).
- ``POST /tests/{id}/merge`` takes ``{into, alignment}``: the test ``id`` is merged into ``into``.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ValidationError, model_validator

from etach.api import sse
from etach.api.deps import ConnDep, CtxDep
from etach.api.routes.threads import (
    RUN_ACTIVE,
    ThreadRef,
    discard_key_runs,
    only_key_runs,
    thread_refs,
)
from etach.appdir import exports_dir
from etach.domain import docx_export, test_text
from etach.domain import keys as key_rules
from etach.domain import merge as merge_mod
from etach.domain.models import AnswerKey, ReviewItem, Test, TestContent, TestMetadata
from etach.domain.review import DropNotConfirmed, TextNotRead, save_test_text
from etach.domain.series import series_details
from etach.domain.validators import validate_content
from etach.store import db
from etach.store.repos import deletes, files, keys, regrade, review, schools, series, tests
from etach.store.repos import points as points_repo

__all__ = ["router"]

router = APIRouter(tags=["tests"])


class TestSummary(BaseModel):
    id: str
    display_name: str
    meta: TestMetadata
    points_possible: float
    attempt_count: int
    open_review_count: int
    created_at: datetime
    """When the test came into the bank: the Tests tab's "Newest added" order (llm-design v4.40)."""
    updated_at: datetime


class TestPageRef(BaseModel):
    """One original page photo of a test (llm-design v4.21): its page number and stored file."""

    page_no: int
    file_id: str


class TestWithPaths(Test):
    """``GET /tests/{id}``: the test plus each picture's stored path (llm-design v4.10) and the
    original page photos (v4.21).

    ``picture_paths`` maps a ``PictureRef.file_id`` to its ``files`` row path
    (``files/<id[:2]>/<id>.<ext>``), so the D11 placeholder names the real extension.
    A picture whose file row is missing is left out.

    ``pages`` is every ``test_pages`` row by ``page_no``: the prepared page the test was
    extracted from (already turned by the photo check's rotation and resized; a text-only page's
    ``file_id`` is its text file). ``key_pages`` is every ``test_key_pages`` row by ``page_no``:
    the key photos the test was extracted with (data-model v1.12; llm-design v4.27). Tests
    extracted before v1.12 have none."""

    picture_paths: dict[str, str]
    pages: list[TestPageRef]
    key_pages: list[TestPageRef]
    content_text: str
    review: list[ReviewItem]
    regrade_pending: bool = False
    """Key changes not re-graded yet (data-model v1.20; llm-design v4.36)."""
    points_each: float | None = None
    """What each graded question is worth: 10 ÷ the graded questions, unrounded; ``None`` with no
    graded question (data-model v1.21, D7). The line under the test title shows it."""


class TestPatch(BaseModel):
    meta: dict[str, Any] | None = None
    content: dict[str, Any] | None = None
    content_text: str | None = None
    drop_confirmed: list[str] | None = None

    @model_validator(mode="after")
    def _one_content(self) -> TestPatch:
        if self.content is not None and self.content_text is not None:
            raise ValueError("send either content or content_text, not both")
        return self


class KeyPut(BaseModel):
    accepted: list[str] | None = None
    reason_vi: str | None = None
    verify: bool = False

    @model_validator(mode="after")
    def _one(self) -> KeyPut:
        if (self.accepted is None) == (not self.verify):
            raise ValueError('send either {"accepted": [...]} or {"verify": true}')
        if self.accepted is not None and (
            not self.accepted or not all(a.strip() for a in self.accepted)
        ):
            raise ValueError("accepted must be a non-empty list of non-empty strings")
        return self


class KeyPutResult(BaseModel):
    key: AnswerKey
    outcome: str
    explanations_deleted: int
    run_ids: list[str]


class MergeRequest(BaseModel):
    into: str
    alignment: dict[str, str]


class MergeResult(BaseModel):
    merged_test_id: str
    survivor_test_id: str
    moved_attempt_ids: list[str]
    remapped_answers: int
    unaligned_item_ids: list[str]
    keys_copied: list[str]
    tags_copied: list[str]
    grade_run_ids: list[str]


def _test(conn: ConnDep, test_id: str) -> Test:
    test = tests.get_test(conn, test_id)
    if test is None:
        raise HTTPException(404, detail=f"no test {test_id}")
    return test


def _summary(test: Test, counts: dict[str, int], open_counts: dict[str, int]) -> TestSummary:
    return TestSummary(
        id=test.id,
        display_name=test.meta.display_name(),
        meta=test.meta,
        points_possible=test.points_possible,
        attempt_count=counts.get(test.id, 0),
        open_review_count=open_counts.get(test.id, 0),
        created_at=test.created_at,
        updated_at=test.updated_at,
    )


@router.get("/tests", response_model=list[TestSummary])
def list_tests(conn: ConnDep, q: str | None = None) -> list[TestSummary]:
    """``?q=``: prefix search (best match first); without it, every non-merged test."""
    ids = db.search_tests(conn, q) if q and q.strip() else tests.list_unmerged_ids(conn)
    counts = tests.attempt_counts(conn)
    open_counts = review.open_counts_by_test(conn)
    found = (tests.get_test(conn, i) for i in ids)
    return [
        _summary(t, counts, open_counts) for t in found if t is not None and t.merged_into is None
    ]


def _picture_paths(conn: ConnDep, content: TestContent) -> dict[str, str]:
    paths: dict[str, str] = {}
    for section in content.sections:
        for group in section.groups:
            for ref in group.pictures:
                if ref.file_id not in paths:
                    row = files.get_file(conn, ref.file_id)
                    if row is not None:
                        paths[ref.file_id] = row.path
    return paths


def _detail(conn: ConnDep, id: str) -> TestWithPaths:
    test = _test(conn, id)
    pages = [
        TestPageRef(page_no=page_no, file_id=file_id)
        for _, page_no, file_id in tests.list_test_pages(conn, test.id)
    ]
    paths = _picture_paths(conn, test.content)
    return TestWithPaths(
        **dict(test),
        picture_paths=paths,
        pages=pages,
        key_pages=[
            TestPageRef(page_no=page_no, file_id=file_id)
            for _, page_no, file_id in tests.list_key_pages(conn, test.id)
        ],
        content_text=test_text.render(test.content, paths),
        review=review.list_open_for_test(conn, test.id),
        regrade_pending=regrade.is_pending(conn, test.id),
        points_each=test_text.points_each(test.content),
    )


@router.get("/tests/{id}", response_model=TestWithPaths)
def get_test(id: str, conn: ConnDep) -> TestWithPaths:
    """The test's metadata and content, plus ``picture_paths`` for the D11 placeholders, the
    original page photos (``pages``) and key photos (``key_pages``), the
    test as text (``content_text``) and its open Review items (``review``)."""
    return _detail(conn, id)


def _patch_db(conn: ConnDep, id: str, body: TestPatch) -> tuple[TestWithPaths, list[str], bool]:
    """The blocking part of :func:`patch_test` (runs in the threadpool): the test after the
    edit, the follow-up runs a text save queued, and whether Review items changed."""
    test = _test(conn, id)
    if body.content_text is not None:
        if body.meta:
            raise HTTPException(422, detail="send the metadata and the test text separately")
        try:
            saved = save_test_text(conn, id, body.content_text, body.drop_confirmed or [])
        except TextNotRead as exc:
            raise HTTPException(
                422, detail={"message": "The test text could not be read.", "errors": exc.errors}
            ) from None
        except DropNotConfirmed as exc:
            raise HTTPException(
                422,
                detail={
                    "message": "These questions have answers or a key. Confirm to delete them.",
                    "drops": exc.drops,
                },
            ) from None
        changed = bool(saved.settled_item_ids or saved.obsolete_item_ids)
        return _detail(conn, id), saved.followup_run_ids, changed
    _patch_fields(conn, test, body)
    changed = False
    if body.meta and "occasion" in body.meta:
        # editing the occasion chip is the Fix of an open unknown_occasion (data-model §5.3)
        for item in review.list_open_for_test(conn, id):
            if item.kind == "unknown_occasion" and item.test_id == id:
                review.resolve_item(
                    conn, item.id, "fixed", {"action": "fix", "value": body.meta["occasion"]}
                )
                changed = True
    return _detail(conn, id), [], changed


@router.patch("/tests/{id}", response_model=TestWithPaths)
async def patch_test(id: str, body: TestPatch, conn: ConnDep, ctx: CtxDep) -> TestWithPaths:
    """Edit metadata (teacher write) and/or content (re-validated), or save the test text."""
    detail, run_ids, changed = await run_in_threadpool(_patch_db, conn, id, body)
    if run_ids:
        await ctx.manager.poke()
    if changed:
        sse.publish(ctx.events, "review.changed", open=review.count_open(conn))
    return detail


def _patch_fields(conn: ConnDep, test: Test, body: TestPatch) -> None:
    """``{meta}`` and/or ``{content}`` in one transaction."""
    id = test.id
    with db.transaction(conn):
        meta = test.meta
        if body.meta:
            try:
                meta = db.write_test_meta(conn, id, body.meta, by_teacher=True)
                if "school" in body.meta:
                    schools.ensure_school(conn, meta.school)  # v1.18: a typed school joins the list
                if "source" in body.meta:
                    series.ensure_series(conn, meta.source)  # v1.21: a typed series joins the list
            except ValidationError as exc:
                raise HTTPException(422, detail=exc.errors(include_url=False)) from exc
            except ValueError as exc:
                raise HTTPException(422, detail=str(exc)) from exc
        if body.content is not None:
            try:
                content = TestContent.model_validate(body.content)
            except ValidationError as exc:
                raise HTTPException(422, detail=exc.errors(include_url=False)) from exc
            failures = validate_content(content, meta.omitted_sections)
            if failures:
                raise HTTPException(
                    422,
                    detail={
                        "message": "the content does not pass the validators",
                        "failures": [dataclasses.asdict(f) for f in failures],
                    },
                )
            content = points_repo.save_content(conn, id, content)


@router.get("/tests/{id}/keys", response_model=list[AnswerKey])
def list_keys(id: str, conn: ConnDep) -> list[AnswerKey]:
    """The test's key rows."""
    _test(conn, id)
    return keys.list_keys(conn, id)


def _put_key_db(conn: ConnDep, id: str, question_id: str, body: KeyPut) -> KeyPutResult:
    """The blocking part of :func:`put_key`; it runs in the threadpool, never on the event loop
    (a blocking ``BEGIN IMMEDIATE`` there deadlocks with the checkpointer's commit)."""
    test = _test(conn, id)
    if question_id not in merge_mod.survivor_question_ids(test.content):
        raise HTTPException(404, detail=f"no question {question_id} in test {id}")
    now = datetime.now(UTC)
    with db.transaction(conn):
        old = keys.get_key(conn, id, question_id)
        if body.accepted is not None:
            new = AnswerKey(
                test_id=id,
                question_id=question_id,
                accepted=key_rules.teacher_accepted(
                    old, list(body.accepted), key_rules.find_question(test.content, question_id)
                ),
                reason_vi=body.reason_vi
                if body.reason_vi is not None
                else (old.reason_vi if old else None),
                source="teacher_edit",
                status="teacher_verified",
                confidence=None,
                updated_at=now,
            )
        else:
            if old is None:
                raise HTTPException(404, detail=f"no key row for {question_id}")
            new = old.model_copy(
                update={"status": "teacher_verified", "checker": None, "updated_at": now}
            )  # a verified key has no unsure check (step 22.5.5)
        write = keys.upsert_key(conn, new)
        run_ids: list[str] = []  # v4.36: always empty; the re-grade waits for POST /regrade
        if write.outcome in ("inserted", "updated"):
            regrade.mark(conn, id)
    stored = keys.get_key(conn, id, question_id)
    assert stored is not None
    return KeyPutResult(
        key=stored,
        outcome=write.outcome,
        explanations_deleted=write.explanations_deleted,
        run_ids=run_ids,
    )


@router.put("/tests/{id}/keys/{question_id}", response_model=KeyPutResult)
async def put_key(
    id: str, question_id: str, body: KeyPut, conn: ConnDep, ctx: CtxDep
) -> KeyPutResult:
    """Edit (``teacher_edit``) or verify (``teacher_verified``) a key. A change on a test with
    graded attempts adds it to ``regrade_pending``; no run starts (v4.36)."""
    result = await run_in_threadpool(_put_key_db, conn, id, question_id, body)
    if result.run_ids:
        await ctx.manager.poke()
    return result


def _delete_key_db(conn: ConnDep, id: str, question_id: str) -> int | None:
    """The blocking part of :func:`delete_key`; it runs in the threadpool, never on the event
    loop, as :func:`_put_key_db`. Returns the open Review count when an item was settled."""
    test = _test(conn, id)
    if question_id not in merge_mod.survivor_question_ids(test.content):
        raise HTTPException(404, detail=f"no question {question_id} in test {id}")
    with db.transaction(conn):
        if not keys.delete_key(conn, id, question_id):
            raise HTTPException(404, detail=f"no key row for {question_id}")
        unsure = [
            item
            for item in review.list_open_for_test(conn, id)
            if item.kind == "uncertain_key" and item.question_id == question_id
        ]
        for item in unsure:  # as a key photo settles them (data-model §5.3); no run is queued
            review.resolve_item(
                conn, item.id, "fixed", {"action": "fix", "value": {"by": "key_deleted"}}
            )
        regrade.mark(conn, id)
    return review.count_open(conn) if unsure else None


@router.delete("/tests/{id}/keys/{question_id}", status_code=204)
async def delete_key(id: str, question_id: str, conn: ConnDep, ctx: CtxDep) -> None:
    """Delete a key and its explanations (D7); the question's open ``uncertain_key`` items are
    ``fixed``. A test with graded attempts goes to ``regrade_pending``; no run starts. 404 for an
    unknown test or question, or a question with no key."""
    open_count = await run_in_threadpool(_delete_key_db, conn, id, question_id)
    if open_count is not None:
        sse.publish(ctx.events, "review.changed", open=open_count)


class RegradeResult(BaseModel):
    run_ids: list[str]


def _regrade_db(conn: ConnDep, id: str) -> RegradeResult:
    """The blocking part of :func:`regrade_test` (runs in the threadpool)."""
    _test(conn, id)
    return RegradeResult(run_ids=regrade.start(conn, id))


@router.post("/tests/{id}/regrade", response_model=RegradeResult)
async def regrade_test(id: str, conn: ConnDep, ctx: CtxDep) -> RegradeResult:
    """Queue 1 grade run (``key_verified``) per graded attempt of the test and clear
    ``regrade_pending``; the run ids (empty when nothing is pending or nothing is graded)."""
    result = await run_in_threadpool(_regrade_db, conn, id)
    if result.run_ids:
        await ctx.manager.poke()
    return result


def _merge_db(conn: ConnDep, id: str, body: MergeRequest) -> merge_mod.MergeReport:
    """The blocking part of :func:`merge_test` (runs in the threadpool)."""
    _test(conn, id)
    _test(conn, body.into)
    try:
        return merge_mod.merge(
            conn,
            merged_test_id=id,
            survivor_test_id=body.into,
            alignment=body.alignment,
            ref=f"api:{id}:{body.into}",
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@router.post("/tests/{id}/merge", response_model=MergeResult)
async def merge_test(id: str, body: MergeRequest, conn: ConnDep, ctx: CtxDep) -> MergeResult:
    """Merge test ``id`` into ``into`` (answers remapped by ``alignment``)."""
    report = await run_in_threadpool(_merge_db, conn, id, body)
    if report.grade_run_ids:
        await ctx.manager.poke()
    if report.unaligned_item_ids:
        sse.publish(ctx.events, "review.changed")
    return MergeResult(**dataclasses.asdict(report))


# --- Save as Word (step 22.1.6, llm-design v4.23) -------------------------------------------


class ExportRequest(BaseModel):
    what: Literal["test", "key"]


class ExportResult(BaseModel):
    path: str
    file_name: str


def exports_folder(ctx: CtxDep) -> Path:
    r"""``<app>\exports`` (next to ``settings.json`` and ``data\``; PRD §11)."""
    return exports_dir(ctx.paths)


def _export_db(conn: ConnDep, folder: Path, id: str, what: str) -> ExportResult:
    test = _test(conn, id)
    if what == "key":
        doc = docx_export.key_document(test, keys.list_keys(conn, id))
        stem = f"{test.meta.display_name()} - Key"
    else:
        doc = docx_export.test_document(test, _picture_paths(conn, test.content))
        stem = f"{test.meta.display_name()} - Test"
    path = docx_export.save_unique(doc, folder, stem)
    return ExportResult(path=str(path), file_name=path.name)


@router.post("/tests/{id}/export", response_model=ExportResult)
async def export_test(id: str, body: ExportRequest, conn: ConnDep, ctx: CtxDep) -> ExportResult:
    r"""Save the clean test or its key as DOCX into ``<app>\exports\`` (never overwrites)."""
    return await run_in_threadpool(_export_db, conn, exports_folder(ctx), id, body.what)


# --- delete (data-model §5.7, llm-design v4.26) ----------------------------------------------


class TestDeletePreview(BaseModel):
    """What ``DELETE /tests/{id}`` removes: ``threads`` go whole; ``kept_threads`` lose only
    their attempts on this test; ``merged_test_ids`` are the tests merged into it;
    ``attempt_count`` is the attempts (papers) that go, current or superseded."""

    __test__ = False  # not a pytest class

    test_id: str
    display_name: str
    threads: list[ThreadRef]
    kept_threads: list[ThreadRef]
    merged_test_ids: list[str]
    attempt_count: int


@router.get("/tests/{id}/delete-preview", response_model=TestDeletePreview)
def delete_preview(id: str, conn: ConnDep) -> TestDeletePreview:
    """Exactly the threads ``DELETE /tests/{id}`` would remove (for the confirm dialog)."""
    test = _test(conn, id)
    plan = deletes.plan_test_delete(conn, id)
    return TestDeletePreview(
        test_id=test.id,
        display_name=test.meta.display_name(),
        threads=thread_refs(conn, plan.thread_ids),
        kept_threads=thread_refs(conn, plan.kept_thread_ids),
        merged_test_ids=[t for t in plan.test_ids if t != id],
        attempt_count=deletes.count_attempts(conn, plan),
    )


@router.delete("/tests/{id}", status_code=204)
async def delete_test(id: str, conn: ConnDep, ctx: CtxDep) -> None:
    """Delete the test for good with what data-model §5.7 lists, in one transaction; 409 while a
    run on it (or in a thread that goes) is going or resumable, 404 for an unknown test."""
    # D14 (step22.6-plan): the ``after_extract`` key runs are discarded first, when they are the
    # only unfinished runs the delete touches (the docstring is the OpenAPI description; kept)
    await discard_key_runs(ctx, await run_in_threadpool(_test_key_runs, conn, id))
    await run_in_threadpool(_delete_test, conn, id)


def _test_key_runs(conn: ConnDep, id: str) -> list[str]:
    _test(conn, id)
    return only_key_runs(
        conn, deletes.active_runs_for_test(conn, deletes.plan_test_delete(conn, id))
    )


def _delete_test(conn: ConnDep, id: str) -> None:
    plan = deletes.plan_test_delete(conn, id)
    if deletes.active_runs_for_test(conn, plan):
        raise HTTPException(409, detail=RUN_ACTIVE)
    deletes.delete_test(conn, plan)


# --- copy series details (data-model v1.14, llm-design v4.30, decision D3) -------------------


class CopyDetailsRequest(BaseModel):
    from_test_id: str


def _copy_details_db(conn: ConnDep, id: str, from_test_id: str) -> TestWithPaths:
    _test(conn, id)
    if from_test_id == id:
        raise HTTPException(422, detail="pick another test to copy the details from")
    source = _test(conn, from_test_id)
    meta = db.write_test_meta(conn, id, series_details(source.meta), by_teacher=True)
    schools.ensure_school(conn, meta.school)
    series.ensure_series(conn, meta.source)
    return _detail(conn, id)


@router.post("/tests/{id}/copy-details", response_model=TestWithPaths)
async def copy_details(id: str, body: CopyDetailsRequest, conn: ConnDep) -> TestWithPaths:
    """Copy occasion, term, school, source and year from ``from_test_id`` as a teacher write (in
    ``edited_fields``; the automatic name follows); never grade or test number. 404 for an
    unknown test, 422 for the same test."""
    return await run_in_threadpool(_copy_details_db, conn, id, body.from_test_id)
