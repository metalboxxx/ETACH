"""``/threads``: conversation threads, their cards and starting runs (llm-design §2, PRD D17/D18).

- ``GET /threads`` lists :class:`ThreadSummary` rows, newest first: ``group`` is the current
  attempt's student name, :data:`UNKNOWN_STUDENT` when it has none, or :data:`BLANK_GROUP` for a
  blank-test thread.
- ``shown_title`` (data-model §5.6, v1.8) is the teacher's title, or, while the title is the
  default :data:`DEFAULT_TITLE`, made on read from the current attempt's student name and the
  test's ``display_name`` (not stored). ``PATCH /threads/{id}`` renames a thread (llm-design v4.19).
  A teacher who renames a thread to exactly :data:`DEFAULT_TITLE` keeps that title (step 22.1.5):
  it is stored with :data:`KEPT_DEFAULT` (an invisible word joiner) appended, so it no longer reads
  as the default, and every answer shows it without the marker.
- ``open_review_count`` (llm-design v4.22): the open Review items of the thread's current attempt
  plus the test-level items of its test; the sidebar marks the thread when it is above 0.
- ``POST /threads/{id}/runs`` starts a run through the run manager. D18: an extract on a thread
  that already has a ``done`` extract run or an attempt → 409 (:data:`ALREADY_RAN`). A grade run
  needs an existing, non-merged test and, when it names an attempt, a current attempt of that test.
- ``POST /threads/{id}/extract-again`` (D8, llm-design v4.41) takes ``{mode?}``: ``replace`` keeps
  the test id (``etach.store.repos.extract_again``), ``copy`` makes a new test;
  ``GET /threads/{id}`` carries ``other_thread_count`` for the choice.
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Body, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from etach.api.deps import ConnDep, CtxDep
from etach.domain.models import (
    Attempt,
    ExtractInput,
    GradeInput,
    Message,
    Run,
    Student,
    Test,
    Thread,
)
from etach.runtime.manager import InvalidRunState
from etach.store.repos import attempts, deletes, regrade, review, runs, students, tests, threads

__all__ = [
    "ALREADY_RAN",
    "BLANK_GROUP",
    "DEFAULT_TITLE",
    "KEPT_DEFAULT",
    "RUN_ACTIVE",
    "UNKNOWN_STUDENT",
    "ThreadRef",
    "router",
    "shown_title",
    "thread_refs",
]

ALREADY_RAN = "thread already ran; start a new thread"
DEFAULT_TITLE = "New thread"
KEPT_DEFAULT = "\u2060"  # WORD JOINER: "the teacher typed the default title" (module docstring)
UNKNOWN_STUDENT = "Chưa rõ"
BLANK_GROUP = "Blank tests"

router = APIRouter(tags=["threads"])


class NewThread(BaseModel):
    title: str = ""


class NewThreadResult(BaseModel):
    thread_id: str


class ThreadRename(BaseModel):
    """A new title; ``null`` goes back to the automatic title (llm-design v4.25)."""

    title: str | None


class ThreadSummary(BaseModel):
    thread: Thread
    shown_title: str
    kind: Literal["filled", "blank", "pending"]
    group: str
    student_id: str | None
    last_activity: datetime
    open_review_count: int


class ThreadDetail(BaseModel):
    thread: Thread
    shown_title: str
    attempt: Attempt | None
    test: Test | None
    test_display_name: str | None
    student: Student | None
    regrade_pending: bool = False
    """The thread's test has key changes not re-graded yet (data-model v1.20, llm-design v4.36):
    the top bar shows "Keys changed" and Re-grade."""
    other_thread_count: int = 0
    """How many other threads use the thread's test (llm-design v4.41, D8): Extract again asks
    "update the test for every thread" or "make a separate copy" when it is above 0."""


class ExtractAgainRequest(BaseModel):
    """``mode`` (D8): ``replace`` saves the new reading into the thread's test (the default when
    no other thread uses it); ``copy`` makes a new test for this thread only."""

    mode: Literal["replace", "copy"] | None = None


class ExtractRequest(BaseModel):
    kind: Literal["extract"]
    input: ExtractInput


class GradeRequest(BaseModel):
    kind: Literal["grade"]
    input: GradeInput


RunRequest = Annotated[ExtractRequest | GradeRequest, Field(discriminator="kind")]


def _thread(conn: ConnDep, thread_id: str) -> Thread:
    thread = threads.get_thread(conn, thread_id)
    if thread is None:
        raise HTTPException(404, detail=f"no thread {thread_id}")
    return thread


def _public(thread: Thread) -> Thread:
    """The thread as answered: a kept default title without its marker."""
    if thread.title.endswith(KEPT_DEFAULT):
        return thread.model_copy(update={"title": thread.title.removesuffix(KEPT_DEFAULT)})
    return thread


def shown_title(thread: Thread, student: Student | None, test: Test | None) -> str:
    """The title the sidebar shows (data-model §5.6): the teacher's title; for the default title,
    "<test display name> · <student>" (test first, step 22.2.1), or the test's name alone, or the
    default."""
    if thread.title != DEFAULT_TITLE:
        return thread.title.removesuffix(KEPT_DEFAULT)
    if test is None:
        return DEFAULT_TITLE
    name = test.meta.display_name()
    return f"{name} · {student.full_name}" if student else name


def _context(conn: ConnDep, thread: Thread) -> tuple[Attempt | None, Student | None, Test | None]:
    """The thread's current attempt, its student and the test (the attempt's, else the thread's)."""
    attempt = attempts.current_attempt(conn, thread.id)
    student = (
        students.get_student(conn, attempt.student_id) if attempt and attempt.student_id else None
    )
    test_id = attempt.test_id if attempt else thread.test_id
    test = tests.get_test(conn, test_id) if test_id else None
    return attempt, student, test


@router.post("/threads", response_model=NewThreadResult)
def create_thread(
    conn: ConnDep, body: Annotated[NewThread | None, Body()] = None
) -> NewThreadResult:
    """Create an empty (``pending``) thread."""
    thread = threads.create_thread(conn, (body.title if body else "") or DEFAULT_TITLE)
    return NewThreadResult(thread_id=thread.id)


@router.get("/threads", response_model=list[ThreadSummary])
def list_threads(conn: ConnDep) -> list[ThreadSummary]:
    """Every thread with its kind, student group and last activity (sidebar), newest first."""
    activity = threads.last_activity(conn)
    out: list[ThreadSummary] = []
    for thread in threads.list_threads(conn):
        attempt, student, test = _context(conn, thread)
        student_id = attempt.student_id if attempt else None
        if thread.kind == "blank":
            group = BLANK_GROUP
        else:
            group = student.full_name if student else UNKNOWN_STUDENT
        last = activity.get(thread.id)
        out.append(
            ThreadSummary(
                thread=_public(thread),
                shown_title=shown_title(thread, student, test),
                kind=thread.kind,
                group=group,
                student_id=student_id,
                last_activity=datetime.fromisoformat(last) if last else thread.created_at,
                open_review_count=review.count_open_for(
                    conn, attempt.id if attempt else None, test.id if test else None
                ),
            )
        )
    out.sort(key=lambda s: s.last_activity, reverse=True)
    return out


@router.get("/threads/{id}", response_model=ThreadDetail)
def get_thread(id: str, conn: ConnDep) -> ThreadDetail:
    """The thread, its current (not superseded) attempt and its test."""
    thread = _thread(conn, id)
    attempt, student, test = _context(conn, thread)
    return ThreadDetail(
        thread=_public(thread),
        shown_title=shown_title(thread, student, test),
        attempt=attempt,
        test=test,
        test_display_name=test.meta.display_name() if test else None,
        student=student,
        regrade_pending=regrade.is_pending(conn, test.id) if test else False,
        other_thread_count=_other_threads(conn, thread.id, test.id if test else None),
    )


def _other_threads(conn: ConnDep, thread_id: str, test_id: str | None) -> int:
    """The threads other than ``thread_id`` whose test is ``test_id``."""
    if test_id is None:
        return 0
    row = conn.execute(
        "SELECT COUNT(*) FROM threads WHERE test_id = ? AND id <> ?", (test_id, thread_id)
    ).fetchone()
    return int(row[0])


@router.patch("/threads/{id}", response_model=Thread)
def rename_thread(id: str, body: ThreadRename, conn: ConnDep) -> Thread:
    """Rename a thread (llm-design v4.19): a blank title → 422, an unknown thread → 404.

    ``title: null`` ("Use automatic name", v4.25) stores the default title again, so the shown
    title is made on read (data-model §5.6, v1.9.3).
    """
    if body.title is None:
        _thread(conn, id)
        threads.set_title(conn, id, DEFAULT_TITLE)
        return _public(_thread(conn, id))
    title = " ".join(body.title.split())
    if not title:
        raise HTTPException(422, detail="title must not be empty")
    _thread(conn, id)
    threads.set_title(conn, id, title + KEPT_DEFAULT if title == DEFAULT_TITLE else title)
    return _public(_thread(conn, id))


@router.get("/threads/{id}/messages", response_model=list[Message])
def list_messages(id: str, conn: ConnDep) -> list[Message]:
    """The thread's cards and messages, in order."""
    _thread(conn, id)
    return threads.list_messages(conn, id)


def _check_grade(conn: ConnDep, grade: GradeInput) -> None:
    test = tests.get_test(conn, grade.test_id)
    if test is None:
        raise HTTPException(404, detail=f"no test {grade.test_id}")
    if test.merged_into is not None:
        raise HTTPException(409, detail=f"test {test.id} was merged into {test.merged_into}")
    if grade.attempt_id is not None:
        attempt = attempts.get_attempt(conn, grade.attempt_id)
        if attempt is None:
            raise HTTPException(404, detail=f"no attempt {grade.attempt_id}")
        if attempt.test_id != grade.test_id:
            raise HTTPException(409, detail=f"attempt {attempt.id} is not on test {test.id}")
        if attempt.superseded_by is not None:
            raise HTTPException(409, detail=f"attempt {attempt.id} is superseded")


def _check_start(conn: ConnDep, id: str, body: ExtractRequest | GradeRequest) -> None:
    """The blocking checks of :func:`start_run` (run in the threadpool, never on the loop)."""
    _thread(conn, id)
    if isinstance(body, ExtractRequest):
        if runs.has_done_run(conn, id, "extract") or attempts.current_attempt(conn, id):
            raise HTTPException(409, detail=ALREADY_RAN)
        return
    _check_grade(conn, body.input)


@router.post(
    "/threads/{id}/runs",
    response_model=Run,
    responses={409: {"description": ALREADY_RAN}},
)
async def start_run(id: str, conn: ConnDep, ctx: CtxDep, body: RunRequest) -> Run:
    """Start a run on the thread: ``{kind: "extract", input}`` or ``{kind: "grade", input}``."""
    await run_in_threadpool(_check_start, conn, id, body)
    if isinstance(body, ExtractRequest):
        return await ctx.manager.submit(id, "extract", body.input)
    return await ctx.manager.submit(id, "grade", body.input)


NOTHING_TO_EXTRACT = "this thread has no finished extract run to read again"
CHOOSE_MODE = (
    "other threads use this test; choose mode replace (update it for every thread) or copy"
)
_GOING = ("queued", "running", "stopping", "stopped", "interrupted")


def _extract_again_input(
    conn: ConnDep, id: str, mode: Literal["replace", "copy"] | None = None
) -> ExtractInput:
    """The last done extract run's pages, without the picked test, superseding the current
    attempt (the same input as a ``picked_test_mismatch`` accept, step 22.3.2), and the thread's
    test as ``again_test_id`` with the ``mode`` (D8). Without a mode: ``replace`` when no other
    thread uses the test, else 409 :data:`CHOOSE_MODE`. A thread without a test reads into a
    new test, as before."""
    thread = _thread(conn, id)
    thread_runs = runs.list_runs(conn, thread_id=id)
    if any(r.status in _GOING and not is_key_run(r) for r in thread_runs):
        raise HTTPException(409, detail=RUN_ACTIVE)
    done = [r for r in thread_runs if r.kind == "extract" and r.status == "done"]
    source = done[-1].input if done else None
    if not isinstance(source, ExtractInput):
        raise HTTPException(409, detail=NOTHING_TO_EXTRACT)
    current = attempts.current_attempt(conn, id)
    test_id = thread.test_id
    if test_id is not None and mode is None:
        if _other_threads(conn, id, test_id):
            raise HTTPException(409, detail=CHOOSE_MODE)
        mode = "replace"
    return ExtractInput(
        pages=source.pages,
        existing_test_id=None,
        supersedes_attempt_id=current.id if current else None,
        series_from_test_id=source.series_from_test_id,
        series_name=source.series_name,
        again_test_id=test_id,
        again_mode=mode if test_id is not None else None,
    )


@router.post(
    "/threads/{id}/extract-again",
    response_model=Run,
    responses={409: {"description": f"{NOTHING_TO_EXTRACT}; or {CHOOSE_MODE}"}},
)
async def extract_again(
    id: str, conn: ConnDep, ctx: CtxDep, body: Annotated[ExtractAgainRequest | None, Body()] = None
) -> Run:
    """Extract again (step 22.3.2, D8): read the thread's photos again from the start, into the
    same test (``mode: replace``) or a new one for this thread (``copy``)."""
    mode = body.mode if body else None
    await run_in_threadpool(_extract_again_input, conn, id, mode)  # every 409 before a discard
    await _discard_key_runs(conn, ctx, id)
    new_input = await run_in_threadpool(_extract_again_input, conn, id, mode)
    return await ctx.manager.submit(id, "extract", new_input)


def is_key_run(run: Run) -> bool:
    """The key run an extraction's save queues (step 22.6.4, reason ``after_extract``)."""
    return (
        run.kind == "grade"
        and isinstance(run.input, GradeInput)
        and run.input.reason == "after_extract"
        and run.input.attempt_id is None
    )


def only_key_runs(conn: ConnDep, active: list[str]) -> list[str]:
    """``active`` (unfinished run ids) when every one is an ``after_extract`` key run; 409
    :data:`RUN_ACTIVE` when any other run is among them."""
    if not active:
        return []
    # read without parsing every run's input (the same test as :func:`is_key_run`)
    key_ids = {
        row[0]
        for row in conn.execute(
            f"SELECT id FROM runs WHERE id IN ({', '.join('?' * len(active))})"
            " AND kind = 'grade'"
            " AND json_extract(input, '$.reason') = 'after_extract'"
            " AND json_extract(input, '$.attempt_id') IS NULL",
            active,
        )
    }
    if any(run_id not in key_ids for run_id in active):
        raise HTTPException(409, detail=RUN_ACTIVE)
    return active


def _unfinished_key_runs(conn: ConnDep, id: str) -> list[str]:
    """The thread's unfinished runs when every one is a key run (:func:`only_key_runs`)."""
    return only_key_runs(conn, deletes.active_runs_for_thread(conn, id))


async def discard_key_runs(ctx: CtxDep, run_ids: list[str]) -> None:
    """D12, D14 (step22.6-plan): discard the key runs :func:`only_key_runs` returned. Each goes
    through the run manager's discard, so a running one is cancelled and ``run.discarded`` is
    published; one that ended in between is left as it is."""
    for run_id in run_ids:
        with contextlib.suppress(InvalidRunState):
            await ctx.manager.discard(run_id)


async def _discard_key_runs(conn: ConnDep, ctx: CtxDep, id: str) -> None:
    """D12 (step22.6-plan): Extract again and Delete thread cancel the thread's key run."""
    await discard_key_runs(ctx, await run_in_threadpool(_unfinished_key_runs, conn, id))


# --- delete (data-model §5.7, llm-design v4.26) ----------------------------------------------

RUN_ACTIVE = "a run is still going or can be resumed here; stop or discard it first"


class ThreadRef(BaseModel):
    """A thread as other lists name it: the delete preview, a student's threads."""

    id: str
    shown_title: str
    test_id: str | None
    test_display_name: str | None
    last_activity: datetime


def thread_refs(conn: ConnDep, thread_ids: list[str]) -> list[ThreadRef]:
    """The threads, newest activity first."""
    activity = threads.last_activity(conn)
    out: list[ThreadRef] = []
    for tid in thread_ids:
        thread = threads.get_thread(conn, tid)
        if thread is None:
            continue
        _attempt, student, test = _context(conn, thread)
        last = activity.get(thread.id)
        out.append(
            ThreadRef(
                id=thread.id,
                shown_title=shown_title(thread, student, test),
                test_id=test.id if test else None,
                test_display_name=test.meta.display_name() if test else None,
                last_activity=datetime.fromisoformat(last) if last else thread.created_at,
            )
        )
    out.sort(key=lambda r: r.last_activity, reverse=True)
    return out


@router.delete("/threads/{id}", status_code=204)
async def delete_thread(id: str, conn: ConnDep, ctx: CtxDep) -> None:
    """Delete the thread for good with what data-model §5.7 lists, in one transaction; 409 while
    one of its runs is going or resumable, 404 for an unknown thread."""
    # D12 (step22.6-plan): the thread's ``after_extract`` key runs are discarded first, when
    # they are its only unfinished runs (the docstring is the OpenAPI description; kept as is)
    await run_in_threadpool(_thread, conn, id)
    await _discard_key_runs(conn, ctx, id)
    await run_in_threadpool(_delete_thread, conn, id)


def _delete_thread(conn: ConnDep, id: str) -> None:
    if deletes.active_runs_for_thread(conn, id):
        raise HTTPException(409, detail=RUN_ACTIVE)
    deletes.delete_thread(conn, id)
