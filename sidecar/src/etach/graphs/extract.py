"""The extraction graph (llm-design §4, plan step 9, Appendix C.1).

``build_extract_graph(deps)`` returns a registry factory ``factory(checkpointer)``;
``register_extract(manager, deps)`` registers it for ``extract`` runs.

**State** (:class:`ExtractState`) holds only IDs and small JSON (never image bytes): every
pydantic value is stored as its ``model_dump(mode="json")`` and every page-keyed dict uses the page
number as a **string** key, so the checkpoint serializer only sees plain JSON.

**Dependencies** (client, file store, prompt provider, thresholds) come from
:class:`ExtractDeps`, never from state. The DB is read through the run's ``Db``
(``current_run().db``); P8: intermediate nodes write only state and ``llm_calls`` (plus derived
file rows through ``FileStore``). Domain tables are written only in ``save`` (part B).

**Call failures** (llm-design §5.1) never crash the graph: a failed transcription → a pending
``validator_failed`` for that page; a failed answers page → a failed page for
``resolve_answers``; a failed key page → no key rows from it.

**Typed input** (PRD D26): when every test page is born-digital
(``store.documents.born_digital_pages``, ``pages.skip_answer_reading``), ``prepare_pages`` sets
``skip_answers`` and ``read_answers_page`` runs once without a model call, moving the cursor past
the last page. ``resolve_answers`` then finds no answers, so the run saves a blank test. The
graph's nodes and edges (Appendix C.1) do not change.

**Typed pages** (D5, llm-design v4.32): ``prepare_pages`` keeps the born-digital test page numbers
(``typed_pages``); the ``transcribe_page`` node calls ``structure_text_page`` (reasoning role, the
page's text, the same ``TranscribeOut``) for such a page with a text layer, and
``retranscribe_tiles`` never cuts one into tiles. Other pages in the same file keep their path.
"""

from __future__ import annotations

import asyncio
import io
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Annotated, Any, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from PIL import Image, ImageOps
from pydantic import BaseModel

from etach.domain import boxes, keymap, pages, renumber, similarity
from etach.domain import keys as key_rules
from etach.domain.answer_box import strip_answer_boxes
from etach.domain.llm_schemas import (
    ReadHeaderOut,
    ReadKeyOut,
    RereadPiecesOut,
    TranscribedSection,
    TranscribeOut,
    read_answers_from_call,
)
from etach.domain.models import (
    Answer,
    AnswerKey,
    Attempt,
    AttemptPage,
    ExtractInput,
    File,
    Question,
    Test,
    local_today,
)
from etach.domain.ocr_structure import structure_ocr_page
from etach.domain.series import series_details, series_name_details
from etach.domain.students import match_student
from etach.domain.test_text import read_ocr_page
from etach.domain.validators import ValidatorFailure, failing_pages
from etach.domain.working import (
    PageAnswers,
    PageHeader,
    PageTranscript,
    PendingReview,
    PreparedPage,
    SavedIds,
    TestDraft,
)
from etach.llm.adapters import PlainText
from etach.llm.client import CallFailure, CallResult, OllamaClient
from etach.llm.confidence import field_confidences
from etach.llm.tasks import TASKS, extraction_inputs
from etach.runtime.steps import Stage, current_run, current_step_id, report_progress, step
from etach.store import db as store_db
from etach.store.documents import TextPiece, born_digital_pages, join_typed_pdf_pages, locate_pages
from etach.store.files import FileStore
from etach.store.repos import attempts as attempt_repo
from etach.store.repos import extract_again, regrade
from etach.store.repos import keys as key_repo
from etach.store.repos import review as review_repo
from etach.store.repos import runs as runs_repo
from etach.store.repos import series as series_repo
from etach.store.repos import students as student_repo
from etach.store.repos import tests as test_repo
from etach.store.repos import threads as thread_repo
from etach.store.repos.schools import clean_name
from etach.store.upgrades import CURRENT_CONTENT_VERSION

__all__ = [
    "C1_EDGES",
    "C1_NODES",
    "EXTRACT_STAGES",
    "ExtractDeps",
    "ExtractState",
    "ExtractThresholds",
    "build_extract_graph",
    "register_extract",
    "save_extract",
]

# --- Appendix C.1 ------------------------------------------------------------------------------

C1_NODES: tuple[str, ...] = (
    "prepare_pages",
    "read_key_pages",
    "load_bank_test",
    "read_header",
    "sanity_check",
    "transcribe_page",
    "merge_and_normalize",
    "retranscribe_tiles",
    "compare_bank",
    "map_key",
    "read_answers_page",
    "resolve_answers",
    "save",
)
C1_EDGES: tuple[tuple[str, str], ...] = (
    (START, "prepare_pages"),
    ("prepare_pages", "read_key_pages"),
    ("read_key_pages", "load_bank_test"),
    ("read_key_pages", "transcribe_page"),
    ("load_bank_test", "read_header"),
    ("read_header", "sanity_check"),
    ("sanity_check", "map_key"),
    ("transcribe_page", "transcribe_page"),
    ("transcribe_page", "merge_and_normalize"),
    ("merge_and_normalize", "retranscribe_tiles"),
    ("retranscribe_tiles", "merge_and_normalize"),
    ("merge_and_normalize", "compare_bank"),
    ("compare_bank", "map_key"),
    ("map_key", "read_answers_page"),
    ("read_answers_page", "read_answers_page"),
    ("read_answers_page", "resolve_answers"),
    ("resolve_answers", "save"),
    ("save", END),
)
EXTRACT_STAGES: tuple[Stage, ...] = (
    Stage("Preparing the photos", ("prepare_pages",)),
    Stage("Reading the key", ("read_key_pages",)),
    Stage(
        "Reading the test",
        (
            "load_bank_test",
            "read_header",
            "sanity_check",
            "transcribe_page",
            "retranscribe_tiles",
            "merge_and_normalize",
            "compare_bank",
            "map_key",
        ),
    ),
    Stage("Reading the answers", ("read_answers_page", "resolve_answers")),
    Stage("Saving", ("save",)),
)
"""The run progress stages, in order (llm-design §2 "Run progress", v4.20)."""

TILE_FRACTION = 0.55  # each half-page tile covers ~55% of the page height (they overlap)


@dataclass(frozen=True)
class ExtractThresholds:
    """Every extraction threshold in one place (M1 tunes them)."""

    reading: float = 0.7  # answer confidence below → reading_unsure ("?")
    key_photo: float = (
        keymap.KEY_PHOTO_THRESHOLD
    )  # key-photo entry confidence below → ai_unverified
    looks_like: float = similarity.LOOKS_LIKE  # 0.85
    possibly: float = similarity.POSSIBLY  # 0.5 → possible_duplicate
    sanity: float = 0.5  # picked test: header+stems similarity below → picked_test_mismatch


@dataclass
class ExtractDeps:
    """What the nodes need besides the state. ``files`` should have its own connection
    (it writes derived file rows)."""

    client: OllamaClient
    files: FileStore
    thresholds: ExtractThresholds = field(default_factory=ExtractThresholds)
    # step 22.6.4 (D4): the save queues the key run (a grade run without an attempt, reason
    # ``after_extract``); a tool that measures extraction alone may turn it off
    key_after_extract: bool = True


# --- state ---------------------------------------------------------------------------------------


def _merge_pendings(
    old: list[dict[str, Any]] | None, new: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Reducer: append pending reviews; a repeated ``dedupe_key`` replaces the earlier one."""
    out = list(old or [])
    index = {p["dedupe_key"]: i for i, p in enumerate(out)}
    for p in new or []:
        if p["dedupe_key"] in index:
            out[index[p["dedupe_key"]]] = p
        else:
            index[p["dedupe_key"]] = len(out)
            out.append(p)
    return out


class ExtractState(TypedDict, total=False):
    """llm-design §4; every value is plain JSON (see the module docstring)."""

    input: dict[str, Any]  # ExtractInput
    run_id: str
    thread_id: str
    pages: list[dict[str, Any]]  # PreparedPage, test pages 1..n
    key_pages: list[dict[str, Any]]  # PreparedPage, key pages 1..k
    transcribe_cursor: int  # pages transcribed so far
    answers_cursor: int  # pages read for answers so far
    skip_answers: bool  # every test page is born-digital: no answer reading (PRD D26)
    typed_pages: list[int]  # born-digital test pages, structured from their text (D5)
    # D12: a typed PDF's joined text pieces, by the page each starts on ("page_no" → TextPiece
    # as {text, page_starts: [[offset, page_no]], picture_pages}); the other joined pages
    # (absorbed) get no call; placed: "page_no" → {groups, questions} page numbers
    text_pieces: dict[str, dict[str, Any]]
    absorbed_pages: list[int]
    placed: dict[str, dict[str, list[int]]]
    repeated_pages: dict[str, int]  # "page_no" → questions dropped where the output repeated
    # step 22.6.5 (2b): "page_no" → the OCR lines the code structure could not place (kept)
    unplaced_pages: dict[str, list[str]]
    # step 22.6.5 (2a): "page_no" → why the test-text reader needs Review (its text is kept)
    format_pages: dict[str, str]
    page_results: dict[str, dict[str, Any]]  # "page_no" → PageTranscript
    transcribe_failed: dict[str, str]  # "page_no" → CallFailure reason (no transcript)
    retranscribe: list[int]  # pages that failed validation on the first pass
    retranscribed: bool  # retranscribe_tiles has run (only once)
    draft: dict[str, Any] | None  # TestDraft: new, or the picked bank test
    draft_page_count: int  # pages of the draft (picked: the bank test's pages)
    header: dict[str, Any] | None  # PageHeader (picked path)
    compare: dict[str, Any] | None  # CompareResult (new path)
    key_raw: list[tuple[str, str, float]] | None  # (printed label, answer, confidence)
    key: list[dict[str, Any]]  # KeyEntry
    key_status: dict[str, str]  # question_id → "from_key_photo" | "ai_unverified"
    answers_raw: dict[str, dict[str, Any]]  # "page_no" → PageAnswers
    answers_conf: dict[str, dict[str, dict[str, Any]]]  # "page_no" → path → {confidence, low_trust}
    answers_failed: list[int]  # answer pages whose call failed
    answers: list[dict[str, Any]]  # Answer, attempt_id="" (save fills it)
    blank: bool  # no answers at all (never True with a failed page)
    student_name: str | None
    class_name: str | None
    pending_reviews: Annotated[list[dict[str, Any]], _merge_pendings]  # PendingReview
    # merge_and_normalize's own pendings, rebuilt on every pass (a second pass after
    # retranscribe_tiles replaces the first pass's set instead of adding to it)
    merge_pendings: list[dict[str, Any]]  # PendingReview
    saved: dict[str, Any] | None  # SavedIds (save)


# --- helpers -------------------------------------------------------------------------------------


def _j(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _input(state: ExtractState) -> ExtractInput:
    return ExtractInput.model_validate(state["input"])


def _taken_on(conn: sqlite3.Connection, inp: ExtractInput) -> date:
    """The new attempt's date taken (D11a): the input's; else, on Extract again, the attempt
    it replaces keeps its date; else today."""
    if inp.taken_on is not None:
        return inp.taken_on
    if inp.supersedes_attempt_id:
        old = attempt_repo.get_attempt(conn, inp.supersedes_attempt_id)
        if old is not None:
            return old.taken_on
    return local_today()


def _pages(state: ExtractState, key: str = "pages") -> list[PreparedPage]:
    raw = cast(list[dict[str, Any]], dict(state).get(key) or [])
    return [PreparedPage.model_validate(p) for p in raw]


def _text_only_ids(state: ExtractState) -> set[str]:
    """Source file IDs of the text-only pages (a DOCX's text, ``file_id = text_file_id``): they
    have no image, so every call sends their text instead (PRD §11, data-model §2.7)."""
    return {p.file_id for p in _input(state).pages if pages.is_text_only(p)}


def _upload_name(files: FileStore, file_id: str) -> str | None:
    """The ``original_name`` of the upload a page came from: follow ``derived_from`` from the
    page's source file up to the ``upload`` row (data-model §2.8, the §2.2 file-name source)."""
    seen: set[str] = set()
    current: str | None = file_id
    while current is not None and current not in seen:
        seen.add(current)
        try:
            row = files.get(current)
        except KeyError:
            return None
        if row.kind == "upload":
            return row.original_name
        current = row.derived_from
    return None


def _draft(state: ExtractState) -> TestDraft:
    draft = state.get("draft")
    if draft is None:
        raise RuntimeError("no draft in state")
    return TestDraft.model_validate(draft)


def _placed(state: ExtractState) -> dict[int, renumber.PiecePages]:
    """D12: where each joined typed-PDF piece's groups and questions were printed."""
    return {
        int(k): renumber.PiecePages(groups=v["groups"], questions=v["questions"])
        for k, v in (state.get("placed") or {}).items()
    }


def _page_item(page_no: int) -> str:
    return f"page {page_no}"


def _failure_json(f: ValidatorFailure) -> dict[str, Any]:
    return {
        "validator": f.validator,
        "page_no": f.page_no,
        "question_id": f.question_id,
        "printed_number": f.printed_number,
        "message": f.message,
    }


def _validator_failed(
    run_id: str,
    page_no: int,
    *,
    task: str,
    failures: Sequence[ValidatorFailure] = (),
    reason: str | None = None,
) -> dict[str, Any]:
    return _j(
        PendingReview(
            kind="validator_failed",
            dedupe_key=f"validator_failed:{run_id}:transcribe:{page_no}",
            refs={"page_no": page_no},
            proposal={
                "task": task,
                "page_no": page_no,
                "failures": [_failure_json(f) for f in failures],
                "call_failure": reason,
            },
        )
    )


TRANSCRIBE = "transcribe_page"


def _previous_unit(state: ExtractState, prepared: list[PreparedPage], cursor: int) -> str | None:
    """Step 22.5.7: the last open unit of the page before (``renumber.open_unit``), when that
    page was also transcribed from its image. The pages are transcribed one after another
    (``transcribe_cursor``), so the page before is already read; no extra call."""
    if cursor == 0:
        return None
    before = prepared[cursor - 1]
    if before.text_layer or before.page_no in (state.get("typed_pages") or []):
        return None
    raw = (state.get("page_results") or {}).get(str(before.page_no))
    if raw is None:
        return None
    out = TranscribeOut.model_validate(
        {
            "header_text": raw.get("header_text"),
            "sections": [renumber.legacy_section(s) for s in raw.get("sections") or []],
        }
    )
    return renumber.open_unit(out)


def _tile_item(page_no: int, tile_no: int) -> str:
    """The log label of one tile call: ``"p2 top"`` / ``"p2 bottom"``."""
    return f"p{page_no} {'top' if tile_no == 1 else 'bottom'}"


def _merge_tiles(top: TranscribeOut, bottom: TranscribeOut) -> TranscribeOut:
    """One page transcript from two overlapping tiles: the bottom tile's first section continues
    the top tile's last one when the title matches (or is empty); questions already read in the
    overlap (same printed number in that section) are dropped."""
    sections: list[TranscribedSection] = [s.model_copy(deep=True) for s in top.sections]
    for i, sec in enumerate(bottom.sections):
        if i == 0 and sections and sec.printed_title in ("", sections[-1].printed_title):
            last = sections[-1]
            seen = {q.printed_number for g in last.groups for q in g.questions}
            groups = list(last.groups)
            for g in sec.groups:
                qs = [q for q in g.questions if q.printed_number not in seen]
                if g.questions and not qs:
                    continue
                groups.append(g.model_copy(update={"questions": qs}))
            sections[-1] = last.model_copy(update={"groups": groups})
        elif not any(s.printed_title == sec.printed_title and s.printed_title for s in sections):
            sections.append(sec)
    return TranscribeOut(header_text=top.header_text or bottom.header_text, sections=sections)


def _tile_bytes(data: bytes) -> tuple[bytes, bytes, str]:
    """Cut an image into top and bottom tiles of ``TILE_FRACTION`` of its height."""
    with Image.open(io.BytesIO(data)) as opened:
        opened.load()
        fmt = opened.format or "PNG"
        img = ImageOps.exif_transpose(opened) or opened
        w, h = img.size
        cut = max(1, round(h * TILE_FRACTION))
        out: list[bytes] = []
        for box in ((0, 0, w, cut), (0, h - cut, w, h)):
            tile = img.crop(box)
            if fmt == "JPEG" and tile.mode not in ("RGB", "L"):
                tile = tile.convert("RGB")
            buf = io.BytesIO()
            tile.save(buf, format=fmt)
            out.append(buf.getvalue())
    ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}.get(fmt, "png")
    return out[0], out[1], ext


def _bank_probe(draft: TestDraft, n: int) -> str:
    qs = sorted(
        (q for s in draft.content.sections for g in s.groups for q in g.questions),
        key=lambda q: q.number,
    )
    return " ".join(q.stem or "" for q in qs[: max(n, 1)])


def _meta_text(draft: TestDraft) -> str:
    m = draft.meta
    parts = [m.occasion, m.school, m.year, m.test_number]
    if m.grade is not None:
        parts.append(f"lop {m.grade}")
    return " ".join(p for p in parts if p)


def _candidates(conn: sqlite3.Connection, exclude: str | None = None) -> list[similarity.Candidate]:
    """The bank tests to compare with; ``exclude`` is the test an Extract again came from (D8):
    a new reading of the same photos always looks like it."""
    rows = conn.execute(
        "SELECT id FROM tests WHERE merged_into IS NULL AND id IS NOT ? ORDER BY id", (exclude,)
    ).fetchall()
    out: list[similarity.Candidate] = []
    for row in rows:
        test = test_repo.get_test(conn, row[0])
        if test is None:
            continue
        out.append(
            similarity.Candidate(
                test_id=test.id,
                grade=test.meta.grade,
                merged_into=test.merged_into,
                content=test.content,
                fingerprint=test.fingerprint,
            )
        )
    return out


# --- save (data-model §5.2) ----------------------------------------------------------------------

# Review kinds that concern the attempt (the student's photos/answers) rather than the test.
_ATTEMPT_KINDS = frozenset(
    {"uncertain_answer", "box_inline_conflict", "unknown_student", "picked_test_mismatch"}
)


def _is_attempt_pending(p: PendingReview) -> bool:
    if p.kind in _ATTEMPT_KINDS:
        return True
    return p.kind == "validator_failed" and p.proposal.get("task") == "read_answers_page"


def _upsert_uncertain_answers(
    conn: sqlite3.Connection,
    state: ExtractState,
    draft: TestDraft,
    test_id: str,
    attempt_id: str,
) -> None:
    """One ``uncertain_answer`` Review item per saved answer with ``reading_unsure`` (PRD S7),
    for a filled attempt only (the caller passes no attempt for a blank test).

    - Only answers of graded, non-writing questions (the ones ``boxes.graded_questions`` gives
      an answer row) qualify.
    - The questions of a page whose read failed (``answers_failed``, or a failed transcription)
      are skipped on purpose: every answer there is unsure, and the page-level
      ``validator_failed`` item already covers them, so they would only flood the queue.
    - Idempotent: the dedupe key ``uncertain_answer:<attempt_id>:<question_id>`` makes a
      repeated save update the same item instead of adding one (R9.5).
    """
    answerable = {q.id for q in boxes.graded_questions(draft)}
    failed_pages = {int(p) for p in state.get("answers_failed") or []} | {
        int(p) for p in (state.get("transcribe_failed") or {})
    }
    for a in state.get("answers") or []:
        if not a.get("reading_unsure") or a["question_id"] not in answerable:
            continue
        if a.get("page_no") in failed_pages:
            continue
        qid = a["question_id"]
        review_repo.upsert_item(
            conn,
            kind="uncertain_answer",
            owner="extract",
            dedupe_key=f"uncertain_answer:{attempt_id}:{qid}",
            proposal={
                "value": a.get("value"),
                "alt_value": a.get("alt_value"),
                "alt_question_id": a.get("alt_question_id"),
                "confidence": a.get("confidence"),
                "low_trust": a.get("low_trust", False),
                "page_no": a.get("page_no"),
                "printed_number": a.get("printed_number"),
            },
            test_id=test_id,
            attempt_id=attempt_id,
            question_id=qid,
        )


def _replaceable(conn: sqlite3.Connection, test_id: str) -> bool:
    """The test an Extract again replaces still exists and is not merged."""
    row = conn.execute("SELECT merged_into FROM tests WHERE id = ?", (test_id,)).fetchone()
    return row is not None and row[0] is None


def _card_exists(conn: sqlite3.Connection, thread_id: str, run_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM messages WHERE thread_id = ? AND kind = 'run_card'"
        " AND json_extract(body, '$.run_id') = ?",
        (thread_id, run_id),
    ).fetchone()
    return row is not None


def save_extract(
    conn: sqlite3.Connection, state: ExtractState, *, key_run: bool = True
) -> dict[str, Any]:
    """The extract ``save`` (data-model §5.2), in ONE transaction; returns ``SavedIds`` JSON.

    Idempotent: (0) a run already ``done`` returns at once; (1) the test and attempt are found
    by ``source_run_id`` and reused; key rows go through the guarded upsert, Review items are
    upserted by ``dedupe_key``, and the extraction card is written once per run (its body holds
    the ``run_id``). With ``key_run`` (step 22.6.4, D4) it also queues the thread's key run
    (``runs.enqueue_key_run``, at most one per extract run). The run is set ``done`` in the same
    transaction.
    """
    run_id = state["run_id"]
    thread_id = state["thread_id"]
    inp = ExtractInput.model_validate(state["input"])
    picked_id = inp.existing_test_id
    replace_id = inp.again_test_id if inp.again_mode == "replace" else None
    blank = bool(state.get("blank"))

    # (0) already saved
    run_row = conn.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
    if run_row is not None and run_row[0] == "done":
        test = test_repo.find_by_source_run(conn, run_id)
        att = attempt_repo.find_by_source_run(conn, run_id)
        test_id = test.id if test is not None else (att.test_id if att else picked_id or replace_id)
        assert test_id is not None
        return _j(SavedIds(test_id=test_id, attempt_id=att.id if att else None))

    draft = TestDraft.model_validate(state["draft"])
    now = datetime.now(UTC)
    with store_db.transaction(conn):
        # (1) reuse what an earlier try of this save already wrote
        existing_test = test_repo.find_by_source_run(conn, run_id)
        existing_att = attempt_repo.find_by_source_run(conn, run_id)
        # Extract again into the same test (D8); a test deleted or merged since → a new test
        replacing = picked_id is None and replace_id is not None and _replaceable(conn, replace_id)

        # (2) the test
        if picked_id is not None:
            test_id = picked_id
        elif replacing:
            assert replace_id is not None
            test_id = replace_id
            extract_again.replace_test(conn, test_id, draft, _pages(state))
        elif existing_test is not None:
            test_id = existing_test.id
        else:
            test_id = test_repo.next_test_id(conn)
            test_repo.insert_test(  # derives the columns + FTS row as write_test_meta does
                conn,
                Test(
                    id=test_id,
                    meta=draft.meta,
                    content=draft.content,
                    content_schema_version=CURRENT_CONTENT_VERSION,
                    fingerprint=draft.fingerprint,
                    points_possible=draft.points_possible,
                    source_run_id=run_id,
                    merged_into=None,
                    created_at=now,
                    updated_at=now,
                ),
            )
            for page in _pages(state):
                test_repo.add_test_page(conn, test_id, page.page_no, page.file_id)
        # "same series as <name>" (data-model v1.21, D5): source = the name, and grade, occasion,
        # term and year of the series' newest test, as teacher writes; school is not copied.
        # "same series as <test>" (v1.14, D3, older runs): the series test's occasion, term,
        # school, source and year. Applied on every try of a new test (idempotent).
        series_name = clean_name(inp.series_name)
        if picked_id is None and not replacing and series_name is not None:
            newest = series_repo.newest_meta(conn, series_name, exclude=test_id)
            store_db.write_test_meta(
                conn, test_id, series_name_details(series_name, newest), by_teacher=True
            )
            series_repo.ensure_series(conn, series_name)
        elif picked_id is None and not replacing and inp.series_from_test_id:
            series = test_repo.get_test(conn, inp.series_from_test_id)
            if series is not None and series.id != test_id:
                store_db.write_test_meta(
                    conn, test_id, series_details(series.meta), by_teacher=True
                )
        # the key photos are kept (data-model v1.12), for a picked test only when it has none
        if not test_repo.list_key_pages(conn, test_id):
            for page in _pages(state, "key_pages"):
                test_repo.add_key_page(conn, test_id, page.page_no, page.file_id)

        # (2) the attempt (filled only)
        pendings = [
            PendingReview.model_validate(p)
            for p in _merge_pendings(
                list(state.get("pending_reviews") or []), list(state.get("merge_pendings") or [])
            )
        ]
        attempt_id: str | None = None
        student_name = state.get("student_name")
        class_name = state.get("class_name")
        if not blank:
            if existing_att is not None:
                attempt_id = existing_att.id
                student_id = existing_att.student_id
            else:
                student_id = match_student(
                    student_name, class_name, student_repo.list_students(conn)
                )
                attempt_id = attempt_repo.next_attempt_id(conn)
                attempt_repo.insert_attempt(
                    conn,
                    Attempt(
                        id=attempt_id,
                        test_id=test_id,
                        thread_id=thread_id,
                        student_id=student_id,
                        student_name_read=student_name,
                        class_read=class_name,
                        source_run_id=run_id,
                        superseded_by=None,
                        status="extracted",
                        version=1,
                        score_earned=None,
                        score_possible=None,
                        created_at=now,
                        taken_on=_taken_on(conn, inp),
                    ),
                )
                attempt_repo.add_attempt_pages(
                    conn,
                    [
                        AttemptPage(
                            attempt_id=attempt_id,
                            page_no=p.page_no,
                            file_id=p.file_id,
                            source_file_id=p.source_file_id,
                            rotation=p.rotation,
                        )
                        for p in _pages(state)
                    ],
                )
                attempt_repo.insert_answers(
                    conn,
                    [
                        Answer.model_validate({**a, "attempt_id": attempt_id})
                        for a in state.get("answers") or []
                    ],
                )
                if inp.supersedes_attempt_id:
                    attempt_repo.set_superseded_by(conn, inp.supersedes_attempt_id, attempt_id)
            if student_id is None:
                pendings.append(
                    PendingReview(
                        kind="unknown_student",
                        dedupe_key=f"unknown_student:{run_id}",
                        refs={},
                        proposal={"student_name_read": student_name, "class_read": class_name},
                    )
                )
        if replacing:
            # D8: the other threads' graded attempts follow the new reading and wait for the
            # teacher's Re-grade (data-model v1.20); this thread's own attempt is superseded above
            regrade.mark(conn, test_id)

        # (2) key rows (guarded: never downgrade an existing key)
        key_status = dict(state.get("key_status") or {})
        saved_test = test_repo.get_test(conn, test_id)
        key_content = saved_test.content if saved_test is not None else draft.content
        for entry in state.get("key") or []:
            qid = entry["question_id"]
            write = key_repo.upsert_key(
                conn,
                AnswerKey(
                    test_id=test_id,
                    question_id=qid,
                    # sentence keys get their accepted forms (data-model v1.15)
                    accepted=key_rules.with_forms(
                        list(entry["accepted"]), key_rules.find_question(key_content, qid)
                    ),
                    reason_vi=None,
                    source="from_key_photo",
                    status=cast(Any, key_status.get(qid, "ai_unverified")),
                    confidence=entry.get("confidence"),
                    updated_at=now,
                ),
            )
            if write.outcome in ("inserted", "updated"):
                # the photo's key replaced an AI key (or a missing one): its unsure-key items close
                review_repo.settle_key_items(conn, test_id, qid, by="key_photo")

        # (2) the thread
        thread_repo.set_test_id(conn, thread_id, test_id)
        thread_repo.set_kind(conn, thread_id, "blank" if blank else "filled")

        # (3) Review items by dedupe_key
        duplicate: dict[str, Any] | None = None
        for p in pendings:
            if p.kind == "possible_duplicate":
                duplicate = {
                    "test_id": p.proposal.get("best_test_id") or p.refs.get("test_id"),
                    "tier": p.proposal.get("tier"),
                }
            dedupe_key = p.dedupe_key
            if p.kind == "unreadable_text":  # one per test page (data-model §2.8)
                dedupe_key = f"unreadable_text:{test_id}:p{p.proposal['page_no']}"
            review_repo.upsert_item(
                conn,
                kind=cast(Any, p.kind),
                owner="extract",
                dedupe_key=dedupe_key,
                proposal=p.proposal,
                # the item belongs to this run's test; a duplicate's bank test stays in
                # proposal.best_test_id
                test_id=test_id,
                attempt_id=attempt_id if _is_attempt_pending(p) else None,
                question_id=p.refs.get("question_id"),
            )
        if attempt_id is not None:
            _upsert_uncertain_answers(conn, state, draft, test_id, attempt_id)

        # (4) the extraction card
        if not _card_exists(conn, thread_id, run_id):
            answers = state.get("answers") or []
            thread_repo.add_message(
                conn,
                thread_id,
                "app",
                "run_card",
                {
                    "run_id": run_id,
                    "test_id": test_id,
                    "attempt_id": attempt_id,
                    "unsure_count": 0 if blank else sum(1 for a in answers if a["reading_unsure"]),
                    "no_answers": blank,
                    "duplicate": duplicate,
                    "student_name_read": None if blank else student_name,
                },
            )

        # (5) the key run (step 22.6.4, D4): the key is made after every extraction, by a grade
        # run without an attempt that the run manager starts after this one (FIFO)
        if key_run:
            runs_repo.enqueue_key_run(
                conn, thread_id=thread_id, test_id=test_id, after_run_id=run_id
            )

        runs_repo.set_run_status(conn, run_id, "done")
    return _j(SavedIds(test_id=test_id, attempt_id=attempt_id))


# --- the graph -----------------------------------------------------------------------------------


def build_extract_graph(deps: ExtractDeps) -> Any:
    """Return the registry factory ``factory(checkpointer) -> compiled extract graph``."""
    client = deps.client
    files = deps.files
    th = deps.thresholds

    async def call(
        task: str,
        inputs: dict[str, Any],
        schema: Any,
        *,
        images: Sequence[str] = (),
        exam_format: str | None = None,
        item: str | None = None,
    ) -> CallResult | CallFailure:
        spec = TASKS[task]
        return await client.call(
            spec.role,
            spec.task,
            inputs,
            schema,
            step_id=current_step_id(),
            images=list(images),
            think=spec.think,
            num_predict=spec.num_predict,
            profile=spec.profile(exam_format),
            item=item,
        )

    def fallback() -> Any:
        return client.config.confidence.fallback

    def tiles_on() -> bool:
        """``[extract] retranscribe_tiles`` (default off, speed bundle 1)."""
        return bool(client.config.extract.retranscribe_tiles)

    def tiles_keep() -> str:
        """``[extract] retranscribe_tiles_keep``: ``better`` (default) or ``always``."""
        return str(client.config.extract.retranscribe_tiles_keep)

    def reread_on() -> bool:
        """``[extract] reread_pieces`` (step 22.5.7, default off): the targeted re-read."""
        return bool(client.config.extract.reread_pieces)

    def ocr_on() -> bool:
        """``[extract] photo_reader = "ocr"`` (step 22.5.7, D13; the default since R22.5.7.7)."""
        return client.config.extract.photo_reader == "ocr"

    # --- nodes -------------------------------------------------------------------------------

    async def prepare_pages(state: ExtractState) -> dict[str, Any]:
        run = current_run()
        inp = _input(state)

        def work() -> tuple[
            list[PreparedPage], list[PreparedPage], bool, list[int], dict[str, Any], list[int]
        ]:
            file_rows: dict[str, File] = {p.file_id: files.get(p.file_id) for p in inp.pages}
            test_pages = [p for p in inp.pages if not p.is_key]
            born = born_digital_pages(files, test_pages)
            skip = pages.skip_answer_reading(born)
            # test pages are numbered 1..n in input order (pages.plan_pages)
            typed = [n for n, flag in enumerate(born, start=1) if flag]
            # D12: a typed PDF's pages are joined and re-cut; indexes → page numbers (+1)
            joined = join_typed_pdf_pages(files, test_pages, born)
            pieces = {
                str(i + 1): {
                    "text": piece.text,
                    "page_starts": [[off, j + 1] for off, j in piece.page_starts],
                    "picture_pages": [j + 1 for j in piece.picture_pages],
                }
                for i, piece in joined.pieces.items()
            }
            absorbed = sorted(i + 1 for i in joined.absorbed)
            plan = pages.plan_pages(inp, file_rows)

            def execute(planned: pages.PlannedPage) -> PreparedPage:
                fid = planned.source_file_id
                for op in planned.ops:
                    fid = (
                        files.rotate(fid, op.value)
                        if op.op == "rotate"
                        else files.resize(fid, op.value)
                    )
                text = files.read_text(planned.text_file_id) if planned.text_file_id else None
                return PreparedPage(
                    page_no=planned.page_no,
                    file_id=fid,
                    source_file_id=planned.source_file_id,
                    rotation=planned.rotation,
                    text_layer=text,
                )

            return (
                [execute(p) for p in plan.pages],
                [execute(p) for p in plan.key_pages],
                skip,
                typed,
                pieces,
                absorbed,
            )

        prepared, keys, skip_answers, typed_pages, pieces, absorbed = await asyncio.to_thread(work)
        return {
            "run_id": run.run_id,
            "thread_id": run.thread_id,
            "pages": [_j(p) for p in prepared],
            "key_pages": [_j(p) for p in keys],
            "transcribe_cursor": 0,
            "answers_cursor": 0,
            "skip_answers": skip_answers,
            "typed_pages": typed_pages,
            "text_pieces": pieces,
            "absorbed_pages": absorbed,
            "placed": {},
            "repeated_pages": {},
            "unplaced_pages": {},
            "format_pages": {},
            "page_results": {},
            "transcribe_failed": {},
            "retranscribe": [],
            "retranscribed": False,
            "draft": None,
            "draft_page_count": len(prepared),
            "header": None,
            "compare": None,
            "key_raw": None,
            "key": [],
            "key_status": {},
            "answers_raw": {},
            "answers_conf": {},
            "answers_failed": [],
            "answers": [],
            "blank": True,
            "student_name": None,
            "class_name": None,
            "merge_pendings": [],
            "saved": None,
        }

    async def read_key_pages(state: ExtractState) -> dict[str, Any]:
        key_pages = _pages(state, "key_pages")
        if not key_pages:
            return {"key_raw": None}
        raw: list[tuple[str, str, float]] = []
        any_ok = False
        for kp_no, kp in enumerate(key_pages, 1):
            inputs = extraction_inputs(
                "read_key_pages",
                photo_count=len(key_pages),
                document=kp.text_layer,
            )
            inputs["page_no"] = kp.page_no
            report_progress(kp_no - 1, len(key_pages), _page_item(kp.page_no), unit="page")
            result = await call(
                "read_key_pages",
                inputs,
                ReadKeyOut,
                images=[] if kp.text_layer else [kp.file_id],
            )
            report_progress(kp_no, len(key_pages), _page_item(kp.page_no), unit="page")
            if isinstance(result, CallFailure):
                continue  # llm-design §5.1: no key rows from this photo
            any_ok = True
            parsed = result.parsed
            assert isinstance(parsed, ReadKeyOut)
            conf = await field_confidences(result, ReadKeyOut, fallback=fallback())
            for i, entry in enumerate(parsed.entries):
                fc = conf.get(f"entries[{i}].answer")
                raw.append((entry.label, entry.answer, float(fc.confidence) if fc else 0.0))
        return {"key_raw": raw if any_ok else None}

    async def load_bank_test(state: ExtractState) -> dict[str, Any]:
        test_id = _input(state).existing_test_id
        assert test_id is not None
        db = current_run().db

        def load(c: sqlite3.Connection) -> tuple[Any, int]:
            test = test_repo.get_test(c, test_id)
            if test is None:
                raise LookupError(f"picked test {test_id} not found")
            return test, len(test_repo.list_test_pages(c, test_id))

        test, page_rows = await db.run(load)
        draft = TestDraft(
            meta=test.meta,
            content=test.content,
            fingerprint=test.fingerprint,
            points_possible=test.points_possible,
        )
        q_pages = [q.page_no for s in test.content.sections for g in s.groups for q in g.questions]
        count = page_rows or (max(q_pages) if q_pages else 0)
        return {"draft": _j(draft), "draft_page_count": count}

    async def read_header(state: ExtractState) -> dict[str, Any]:
        prepared = _pages(state)
        if not prepared:
            return {"header": None}
        first = prepared[0]
        inputs = extraction_inputs("read_header", page_no=1, document=first.text_layer)
        result = await call(
            "read_header",
            inputs,
            ReadHeaderOut,
            images=[] if first.text_layer else [first.file_id],
            exam_format=_draft(state).meta.exam_format,
        )
        if isinstance(result, CallFailure):
            return {"header": None}
        parsed = result.parsed
        assert isinstance(parsed, ReadHeaderOut)
        header = PageHeader(header_text=parsed.header_text, first_stems=list(parsed.first_stems))
        return {"header": _j(header)}

    async def sanity_check(state: ExtractState) -> dict[str, Any]:
        header_json = state.get("header")
        if header_json is None:
            return {}
        header = PageHeader.model_validate(header_json)
        draft = _draft(state)
        if header.first_stems:
            value = similarity.similarity(
                " ".join(header.first_stems), _bank_probe(draft, len(header.first_stems))
            )
        else:
            value = similarity.similarity(header.header_text, _meta_text(draft))
        if value >= th.sanity:
            return {}
        test_id = _input(state).existing_test_id
        pending = PendingReview(
            kind="picked_test_mismatch",
            dedupe_key=f"picked_test_mismatch:{state['run_id']}:{test_id}",
            refs={"test_id": test_id},
            proposal={
                "similarity": value,
                "header_text": header.header_text,
                "first_stems": header.first_stems,
            },
        )
        return {"pending_reviews": [_j(pending)]}

    async def transcribe_page(state: ExtractState) -> dict[str, Any]:
        prepared = _pages(state)
        cursor = state.get("transcribe_cursor", 0)
        page = prepared[cursor]
        if page.page_no in (state.get("absorbed_pages") or []):
            # D12: this typed PDF page's text went to the model in the piece before it
            return {"transcribe_cursor": cursor + 1}
        piece_json = (state.get("text_pieces") or {}).get(str(page.page_no))
        # D5 (llm-design v4.32): a born-digital page with its text goes to structure_text_page
        # (the reasoning role, text only); a scanned page or a photo is transcribed as before
        task = (
            "structure_text_page"
            if page.text_layer and page.page_no in (state.get("typed_pages") or [])
            else "transcribe_page"
        )
        document = piece_json["text"] if piece_json else page.text_layer
        report_progress(cursor, len(prepared), _page_item(page.page_no), unit="page")
        if (
            task == TRANSCRIBE
            and not page.text_layer
            and ocr_on()
            and client.config.extract.photo_structure == "ocr_format"
        ):
            return await _format_read(state, page.page_no, page.file_id, cursor)
        if task == TRANSCRIBE and not page.text_layer and ocr_on():
            # step 22.5.7 (D13): the two-step photo reader. The ocr role reads the photo as
            # plain text; structure_text_page then structures that text like a typed page's
            # (per page: the merge's page-break joins still apply; no previous-page hint)
            ocr = await call(
                "ocr_page",
                extraction_inputs(
                    "ocr_page",
                    page_no=page.page_no,
                    ocr_prompt=client.config.extract.ocr_prompt,
                ),
                PlainText,
                images=[page.file_id],
            )
            if isinstance(ocr, CallFailure):
                failed = dict(state.get("transcribe_failed") or {})
                failed[str(page.page_no)] = ocr.reason
                report_progress(cursor + 1, len(prepared), _page_item(page.page_no), unit="page")
                return {"transcribe_cursor": cursor + 1, "transcribe_failed": failed}
            assert isinstance(ocr.parsed, PlainText)
            # step 22.6.1 (D2): the answer boxes go before the text is structured
            task, document = "structure_text_page", strip_answer_boxes(ocr.parsed.text)
            photo_text = True
            if client.config.extract.photo_structure == "code":
                return _code_structured(state, page.page_no, cursor, document, ocr.llm_call_id)
        else:
            photo_text = False
        inputs = extraction_inputs(
            task,
            page_no=page.page_no,
            photo_count=len(prepared),
            document=document,
            previous_unit=_previous_unit(state, prepared, cursor) if task == TRANSCRIBE else None,
            photo=photo_text,
        )
        result = await call(
            task,
            inputs,
            TranscribeOut,
            images=[page.file_id] if task == TRANSCRIBE and not page.text_layer else [],
        )
        report_progress(cursor + 1, len(prepared), _page_item(page.page_no), unit="page")
        key = str(page.page_no)
        if isinstance(result, CallFailure):
            failed = dict(state.get("transcribe_failed") or {})
            failed[key] = result.reason
            return {"transcribe_cursor": cursor + 1, "transcribe_failed": failed}
        parsed = result.parsed
        assert isinstance(parsed, TranscribeOut)
        update: dict[str, Any] = {"transcribe_cursor": cursor + 1}
        if task == "structure_text_page":
            # step 22.5.6: a looping output is cut where it repeats and flagged for review
            parsed, dropped = renumber.cut_repetition(parsed)
            if dropped:
                update["repeated_pages"] = {**(state.get("repeated_pages") or {}), key: dropped}
        results = dict(state.get("page_results") or {})
        results[key] = _j(renumber.page_transcript(page.page_no, parsed, result.llm_call_id))
        update["page_results"] = results
        if piece_json:
            piece = TextPiece(
                piece_json["text"],
                tuple((int(off), int(no)) for off, no in piece_json["page_starts"]),
                tuple(int(no) for no in piece_json["picture_pages"]),
            )
            g_pages, q_pages = locate_pages(piece, parsed.sections)
            placed = dict(state.get("placed") or {})
            placed[key] = {"groups": g_pages, "questions": q_pages}
            update["placed"] = placed
        return update

    def _code_structured(
        state: ExtractState, page_no: int, cursor: int, text: str, ocr_call_id: str
    ) -> dict[str, Any]:
        """Step 22.6.5 (2b, ``photo_structure = "code"``): the page's OCR text structured by
        code (:mod:`etach.domain.ocr_structure`), no model call; the transcript points at the
        ``ocr_page`` call. Lines no rule placed are kept and the page is flagged at the merge."""
        structured = structure_ocr_page(text)
        key = str(page_no)
        report_progress(cursor + 1, len(_pages(state)), _page_item(page_no), unit="page")
        results = dict(state.get("page_results") or {})
        results[key] = _j(renumber.page_transcript(page_no, structured.out, ocr_call_id))
        update: dict[str, Any] = {"transcribe_cursor": cursor + 1, "page_results": results}
        if structured.unplaced:
            unplaced = dict(state.get("unplaced_pages") or {})
            unplaced[key] = structured.unplaced
            update["unplaced_pages"] = unplaced
        return update

    async def _format_read(
        state: ExtractState, page_no: int, file_id: str, cursor: int
    ) -> dict[str, Any]:
        """Step 22.6.5 (2a, ``photo_structure = "ocr_format"``): GLM-OCR writes the page in the
        app's test-text format (``ocr_format_page``), read by code
        (:func:`etach.domain.test_text.read_ocr_page`), no structuring call; the transcript points
        at the ``ocr_format_page`` call. A page the reader cannot read keeps its text and is
        flagged at the merge."""
        prepared = _pages(state)
        ocr = await call(
            "ocr_format_page",
            extraction_inputs("ocr_format_page", page_no=page_no),
            PlainText,
            images=[file_id],
        )
        report_progress(cursor + 1, len(prepared), _page_item(page_no), unit="page")
        key = str(page_no)
        if isinstance(ocr, CallFailure):
            failed = dict(state.get("transcribe_failed") or {})
            failed[key] = ocr.reason
            return {"transcribe_cursor": cursor + 1, "transcribe_failed": failed}
        assert isinstance(ocr.parsed, PlainText)
        # step 22.6.1 (D2): answer boxes out, a second barrier after the prompt's rule
        page_read = read_ocr_page(strip_answer_boxes(ocr.parsed.text))
        results = dict(state.get("page_results") or {})
        results[key] = _j(renumber.page_transcript(page_no, page_read.out, ocr.llm_call_id))
        update: dict[str, Any] = {"transcribe_cursor": cursor + 1, "page_results": results}
        if page_read.problem is not None:
            update["format_pages"] = {**(state.get("format_pages") or {}), key: page_read.problem}
        return update

    async def merge_and_normalize(state: ExtractState) -> dict[str, Any]:
        run_id = state["run_id"]
        prepared = _pages(state)
        transcripts = [
            PageTranscript.model_validate(t) for t in (state.get("page_results") or {}).values()
        ]
        first = min(prepared, key=lambda p: p.page_no, default=None)
        filename = None
        if first is not None:
            filename = await asyncio.to_thread(_upload_name, files, first.source_file_id)
        merged = renumber.merge_pages(
            transcripts,
            page_files={p.page_no: p.file_id for p in prepared},
            ref=run_id,
            placed=_placed(state),
            filename=filename,
        )
        pendings = [_j(p) for p in merged.pendings]
        typed = set(state.get("typed_pages") or [])
        text_pages = {p.page_no for p in prepared if p.text_layer}

        def first_task(page_no: int) -> str:
            """The task that read the page on the first pass (D5: a typed page is structured)."""
            typed_text = page_no in typed and page_no in text_pages
            return "structure_text_page" if typed_text else "transcribe_page"

        for failed_no, reason in (state.get("transcribe_failed") or {}).items():
            pendings.append(
                _validator_failed(
                    run_id, int(failed_no), task=first_task(int(failed_no)), reason=reason
                )
            )
        failing = failing_pages(merged.failures)
        update: dict[str, Any] = {"draft": _j(merged.draft)}
        if failing and (tiles_on() or reread_on()) and not state.get("retranscribed"):
            update["retranscribe"] = failing
        else:
            # tiles and re-read off ([extract] retranscribe_tiles = reread_pieces = false): a
            # page failing the first pass is treated like a page failing twice (llm-design §4)
            # → validator_failed
            update["retranscribe"] = []
            again_task = "retranscribe_tiles" if tiles_on() else "reread_pieces"
            for page_no in failing:
                page_failures = [f for f in merged.failures if f.page_no == page_no]
                pendings.append(
                    _validator_failed(
                        run_id,
                        page_no,
                        task=again_task
                        if state.get("retranscribed") and page_no not in typed
                        else first_task(page_no),
                        failures=page_failures,
                        reason=(state.get("transcribe_failed") or {}).get(str(page_no)),
                    )
                )
        flagged = {p["dedupe_key"] for p in pendings}
        for page_key, dropped in (state.get("repeated_pages") or {}).items():
            pending = _validator_failed(
                run_id,
                int(page_key),
                task="structure_text_page",
                reason=f"repeated output: cut where it repeated ({dropped} questions dropped)",
            )
            if pending["dedupe_key"] not in flagged:
                pendings.append(pending)
        for page_key, lines in (state.get("unplaced_pages") or {}).items():
            pending = _validator_failed(
                run_id,
                int(page_key),
                task="ocr_structure",
                reason=f"code structure: {len(lines)} line(s) not placed, kept as text",
            )
            if pending["dedupe_key"] not in {p["dedupe_key"] for p in pendings}:
                pendings.append(pending)
        for page_key, problem in (state.get("format_pages") or {}).items():
            pending = _validator_failed(
                run_id, int(page_key), task="ocr_format_page", reason=problem
            )
            same = next((p for p in pendings if p["dedupe_key"] == pending["dedupe_key"]), None)
            if same is None:
                pendings.append(pending)
            elif not same["proposal"].get("call_failure"):
                # the page also fails a validator: its item says why the reader needs Review too
                same["proposal"]["call_failure"] = problem
        update["merge_pendings"] = pendings  # replaces the previous pass's set
        return update

    async def retranscribe_tiles(state: ExtractState) -> dict[str, Any]:
        prepared = {p.page_no: p for p in _pages(state)}
        todo = list(state.get("retranscribe") or [])
        results = dict(state.get("page_results") or {})
        failed = dict(state.get("transcribe_failed") or {})
        page_files = {p.page_no: p.file_id for p in prepared.values()}

        def page_failures(candidate: dict[str, dict[str, Any]], page_no: int) -> int:
            """Validator failures on ``page_no`` when the pages are merged as ``candidate``."""
            merged = renumber.merge_pages(
                [PageTranscript.model_validate(t) for t in candidate.values()],
                page_files=page_files,
                ref=state["run_id"],
                placed=_placed(state),
            )
            return sum(1 for f in merged.failures if f.page_no == page_no)

        async def reread(page: PreparedPage) -> None:
            """Step 22.5.7, the targeted re-read: one ``reread_pieces`` call for only the page's
            failing or missing questions, patched in by code (``renumber.apply_reread``). The
            patch is kept only if the page's failures do not increase; a failed call, or a page
            with nothing to ask, keeps the page as it was."""
            key = str(page.page_no)
            if key not in results:
                return
            first = PageTranscript.model_validate(results[key])
            out = TranscribeOut.model_validate(
                {"header_text": first.header_text, "sections": first.sections}
            )
            merged = renumber.merge_pages(
                [PageTranscript.model_validate(t) for t in results.values()],
                page_files=page_files,
                ref=state["run_id"],
                placed=_placed(state),
            )
            fails = [f for f in merged.failures if f.page_no == page.page_no]
            asks = renumber.reread_asks(
                out, fails, merged.draft.content, merged.draft.meta.omitted_sections
            )
            if not asks:
                return
            inputs = extraction_inputs(
                "reread_pieces",
                page_no=page.page_no,
                photo_count=len(prepared),
                pieces=renumber.reread_text(out, asks),
            )
            result = await call(
                "reread_pieces",
                inputs,
                RereadPiecesOut,
                images=[page.file_id],
                item=f"p{page.page_no} re-read",
            )
            if isinstance(result, CallFailure):
                return
            assert isinstance(result.parsed, RereadPiecesOut)
            patched = renumber.apply_reread(out, asks, result.parsed)
            if patched is out:
                return
            candidate = _j(renumber.page_transcript(page.page_no, patched, first.llm_call_id))
            if page_failures({**results, key: candidate}, page.page_no) <= len(fails):
                results[key] = candidate

        for n, page_no in enumerate(todo, start=1):
            page = prepared[page_no]
            if page.text_layer or page_no in (state.get("typed_pages") or []):
                # a page with a text layer (a DOCX text page, or a typed PDF page) was read
                # from its exact text (D5: structure_text_page, D12: in its joined piece):
                # never replace that with an image read of tiles (text-only pages: structure.md
                # §6, v1.1.47). No call; it still fails on the next merge pass, which raises
                # validator_failed for it. A photo read by the OCR reader (step 22.5.7) has no
                # text layer, so its tiles read the photo like any photo's
                report_progress(
                    n, len(todo), _page_item(page_no), unit="page", current=page_no, again=True
                )
                continue

            report_progress(
                n - 1, len(todo), _page_item(page_no), unit="page", current=page_no, again=True
            )
            if reread_on():
                await reread(page)
            if not tiles_on():
                report_progress(
                    n, len(todo), _page_item(page_no), unit="page", current=page_no, again=True
                )
                continue

            def cut(page: PreparedPage = page) -> tuple[str, str]:
                top, bottom, ext = _tile_bytes(files.read_bytes(page.file_id))
                return (
                    files.put(top, ext, kind="derived", derived_from=page.file_id),
                    files.put(bottom, ext, kind="derived", derived_from=page.file_id),
                )

            tile_ids = await asyncio.to_thread(cut)
            outs: list[TranscribeOut] = []
            call_ids: list[str] = []
            reason: str | None = None
            for tile_no, tile_id in enumerate(tile_ids, start=1):
                inputs = extraction_inputs(
                    "transcribe_page", page_no=page_no, photo_count=len(prepared)
                )
                inputs["tile"] = tile_no
                result = await call(
                    "transcribe_page",
                    inputs,
                    TranscribeOut,
                    images=[tile_id],
                    item=_tile_item(page_no, tile_no),  # the step's item names every page
                )
                if isinstance(result, CallFailure):
                    reason = result.reason
                    break
                assert isinstance(result.parsed, TranscribeOut)
                outs.append(result.parsed)
                call_ids.append(result.llm_call_id)
            report_progress(
                n, len(todo), _page_item(page_no), unit="page", current=page_no, again=True
            )
            if reason is not None:
                failed[str(page_no)] = reason
                continue
            merged = _merge_tiles(outs[0], outs[1])
            tiled = _j(renumber.page_transcript(page_no, merged, call_ids[-1]))
            key = str(page_no)
            # keep the tile reading only if it reduces this page's validator failures;
            # otherwise the first pass stays ([extract] retranscribe_tiles_keep = "better", the
            # default; "always" is the rule before speed bundle 1)
            if (
                key not in results
                or tiles_keep() == "always"
                or page_failures({**results, key: tiled}, page_no) < page_failures(results, page_no)
            ):
                results[key] = tiled
        return {"page_results": results, "retranscribed": True, "transcribe_failed": failed}

    async def compare_bank(state: ExtractState) -> dict[str, Any]:
        draft = _draft(state)
        again = _input(state).again_test_id
        candidates = await current_run().db.run(lambda c: _candidates(c, again))
        outcome = similarity.compare(
            draft,
            candidates,
            looks_like=th.looks_like,
            possibly=th.possibly,
            ref=state["run_id"],
        )
        update: dict[str, Any] = {"compare": _j(outcome.result)}
        if outcome.pending is not None:
            update["pending_reviews"] = [_j(outcome.pending)]
        return update

    async def map_key(state: ExtractState) -> dict[str, Any]:
        key_raw = state.get("key_raw")
        if not key_raw:
            return {"key": [], "key_status": {}}
        result = keymap.map_key(
            [tuple(r) for r in key_raw], _draft(state), threshold=th.key_photo, ref=state["run_id"]
        )
        return {
            "key": [_j(e) for e in result.entries],
            "key_status": dict(result.status),
            "pending_reviews": [_j(p) for p in result.pendings],
        }

    async def read_answers_page(state: ExtractState) -> dict[str, Any]:
        prepared = _pages(state)
        if state.get("skip_answers"):
            # PRD D26: typed input holds no handwriting; no call, so the run saves a blank test
            return {"answers_cursor": len(prepared)}
        cursor = state.get("answers_cursor", 0)
        page = prepared[cursor]
        draft = _draft(state)
        questions: list[Question] = boxes.graded_questions(draft)
        page_count = state.get("draft_page_count")
        if len(prepared) == page_count:
            # step 22.5.6: each page is asked only for the questions printed on it (by page_no);
            # an answer written only on another page is not read (accepted limit). When the
            # photos do not match the test's pages (a picked test), every question is asked.
            questions = [q for q in questions if q.page_no == page.page_no]
        key = str(page.page_no)
        update: dict[str, Any] = {"answers_cursor": cursor + 1}
        if not questions:
            return update
        spec = TASKS["read_answers_page"]
        schema = spec.schema(questions)
        # a text-only page has no image: its text is the page (PRD §11); an image page with a
        # text layer still sends the image (the student's writing is only on the photo)
        text_only = page.source_file_id in _text_only_ids(state)
        inputs = extraction_inputs(
            "read_answers_page",
            page_no=page.page_no,
            photo_count=len(prepared),
            questions=questions,
            document=page.text_layer if text_only else None,
        )
        report_progress(cursor, len(prepared), _page_item(page.page_no), unit="page")
        result = await call(
            "read_answers_page",
            inputs,
            schema,
            images=[] if text_only else [page.file_id],
            exam_format=draft.meta.exam_format,
        )
        report_progress(cursor + 1, len(prepared), _page_item(page.page_no), unit="page")
        if isinstance(result, CallFailure):
            update["answers_failed"] = [*(state.get("answers_failed") or []), page.page_no]
            return update
        out = read_answers_from_call(result.parsed, questions)
        page_answers = PageAnswers(
            page_no=page.page_no,
            answers=[a.model_dump(mode="json") for a in out.answers],
            student_name=out.student_name,
            class_name=out.class_name,
        )
        conf = await field_confidences(result, schema, fallback=fallback())
        raw = dict(state.get("answers_raw") or {})
        raw[key] = _j(page_answers)
        confs = dict(state.get("answers_conf") or {})
        confs[key] = {
            path: {"confidence": float(fc.confidence), "low_trust": bool(fc.low_trust)}
            for path, fc in conf.items()
            if path.startswith("answers.")
        }
        update["answers_raw"] = raw
        update["answers_conf"] = confs
        return update

    async def resolve_answers(state: ExtractState) -> dict[str, Any]:
        draft = _draft(state)
        page_answers = [
            PageAnswers.model_validate(p) for p in (state.get("answers_raw") or {}).values()
        ]
        confidences = {
            int(page): {path: SimpleNamespace(**fc) for path, fc in paths.items()}
            for page, paths in (state.get("answers_conf") or {}).items()
        }
        result = boxes.resolve_answers(
            page_answers,
            confidences,
            draft,
            threshold=th.reading,
            failed_pages=state.get("answers_failed") or [],
            ref=state["run_id"],
            blank_share=client.config.extract.blank_share,
        )
        return {
            "answers": [_j(a) for a in result.answers],
            "blank": result.blank,
            "student_name": result.student_name,
            "class_name": result.class_name,
            "pending_reviews": [_j(p) for p in result.pendings],
        }

    async def save(state: ExtractState) -> dict[str, Any]:
        key_run = deps.key_after_extract
        saved = await current_run().db.run(lambda c: save_extract(c, state, key_run=key_run))
        return {"saved": saved}

    # --- routing -----------------------------------------------------------------------------

    def picked(state: ExtractState) -> str:
        return "load_bank_test" if _input(state).existing_test_id else "transcribe_page"

    def more_transcribe(state: ExtractState) -> str:
        if state.get("transcribe_cursor", 0) < len(state.get("pages") or []):
            return "transcribe_page"
        return "merge_and_normalize"

    def retranscribe_or_not(state: ExtractState) -> str:
        return "retranscribe_tiles" if state.get("retranscribe") else "compare_bank"

    def more_answers(state: ExtractState) -> str:
        if state.get("answers_cursor", 0) < len(state.get("pages") or []):
            return "read_answers_page"
        return "resolve_answers"

    def transcribe_item(state: ExtractState) -> str | None:
        return _page_item(state.get("transcribe_cursor", 0) + 1)

    def answers_item(state: ExtractState) -> str | None:
        return _page_item(state.get("answers_cursor", 0) + 1)

    def retranscribe_item(state: ExtractState) -> str | None:
        todo = state.get("retranscribe") or []
        if len(todo) == 1:
            return _page_item(todo[0])
        return "pages " + ", ".join(str(p) for p in todo) if todo else None

    def factory(checkpointer: Any) -> Any:
        b: Any = StateGraph(ExtractState)
        b.add_node("prepare_pages", step("prepare_pages", prepare_pages))
        b.add_node("read_key_pages", step("read_key_pages", read_key_pages))
        b.add_node("load_bank_test", step("load_bank_test", load_bank_test))
        b.add_node("read_header", step("read_header", read_header, item=lambda s: "page 1"))
        b.add_node("sanity_check", step("sanity_check", sanity_check))
        b.add_node(
            "transcribe_page", step("transcribe_page", transcribe_page, item=transcribe_item)
        )
        b.add_node("merge_and_normalize", step("merge_and_normalize", merge_and_normalize))
        b.add_node(
            "retranscribe_tiles",
            step("retranscribe_tiles", retranscribe_tiles, item=retranscribe_item),
        )
        b.add_node("compare_bank", step("compare_bank", compare_bank))
        b.add_node("map_key", step("map_key", map_key))
        b.add_node(
            "read_answers_page", step("read_answers_page", read_answers_page, item=answers_item)
        )
        b.add_node("resolve_answers", step("resolve_answers", resolve_answers))
        b.add_node("save", step("save", save))

        b.add_edge(START, "prepare_pages")
        b.add_edge("prepare_pages", "read_key_pages")
        b.add_conditional_edges("read_key_pages", picked, ["load_bank_test", "transcribe_page"])
        b.add_edge("load_bank_test", "read_header")
        b.add_edge("read_header", "sanity_check")
        b.add_edge("sanity_check", "map_key")
        b.add_conditional_edges(
            "transcribe_page", more_transcribe, ["transcribe_page", "merge_and_normalize"]
        )
        b.add_conditional_edges(
            "merge_and_normalize", retranscribe_or_not, ["retranscribe_tiles", "compare_bank"]
        )
        b.add_edge("retranscribe_tiles", "merge_and_normalize")
        b.add_edge("compare_bank", "map_key")
        b.add_edge("map_key", "read_answers_page")
        b.add_conditional_edges(
            "read_answers_page", more_answers, ["read_answers_page", "resolve_answers"]
        )
        b.add_edge("resolve_answers", "save")
        b.add_edge("save", END)
        return b.compile(checkpointer=checkpointer)

    return factory


def register_extract(manager: Any, deps: ExtractDeps) -> None:
    """Register the extract graph with a ``RunManager``."""
    manager.register("extract", build_extract_graph(deps), stages=EXTRACT_STAGES)
