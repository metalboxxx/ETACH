"""Step 9: the extract graph nodes up to ``resolve_answers``.

The model is a FakeOllama that answers by the task's output schema (``format`` title); the prompts
are the real ``FilePromptProvider`` files. The harness wraps ``save_extract`` to record the state
``save`` receives (the checkpoint is purged once a run is ``done``); ``save_mode = "stub"`` makes
``save`` fail before writing anything (R9.8); ``"crash_after"`` raises right after its commit
(R9.5). The ``save`` scenarios (R9.2 synthetic to R9.12) are at the end of this file.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import sqlite3
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from PIL import Image
from support.fake_ollama import ChatScript, FakeOllama

from etach.appdir import DataPaths
from etach.domain import renumber
from etach.domain import review as review_service
from etach.domain.llm_schemas import TranscribeOut
from etach.domain.models import ExtractInput, PageInput
from etach.domain.models import Test as BankTest
from etach.domain.normalize import name_search
from etach.graphs import extract as extract_mod
from etach.graphs.extract import (
    C1_EDGES,
    C1_NODES,
    ExtractDeps,
    ExtractThresholds,
    build_extract_graph,
    register_extract,
)
from etach.llm.client import OllamaClient, StreamDropped
from etach.llm.config import load_models_config, parse_models_config
from etach.prompts.render import FilePromptProvider
from etach.runtime.events import EventBus
from etach.runtime.manager import RunManager
from etach.runtime.power import FakePower
from etach.store import db
from etach.store.files import FileStore
from etach.store.repos import attempts, keys, runs, students, threads
from etach.store.repos import tests as test_repo

TIMEOUT = 60.0

# --- Appendix C.1, verbatim (plan.md) ------------------------------------------------------------

C1_TEXT = """
  - `START→prepare_pages`, `prepare_pages→read_key_pages`;
  - `read_key_pages→load_bank_test` (picked), `read_key_pages→transcribe_page` (not picked);
  - `load_bank_test→read_header`, `read_header→sanity_check`, `sanity_check→map_key`;
  - `transcribe_page→transcribe_page` (more pages), `transcribe_page→merge_and_normalize`;
  - `merge_and_normalize→retranscribe_tiles` (retranscribe), `retranscribe_tiles→merge_and_normalize`, `merge_and_normalize→compare_bank` (no retranscribe);
  - `compare_bank→map_key`, `map_key→read_answers_page`;
  - `read_answers_page→read_answers_page` (more pages), `read_answers_page→resolve_answers`;
  - `resolve_answers→save`, `save→END`.
"""  # noqa: E501


def _c1_edges() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for chunk in C1_TEXT.split("`")[1::2]:
        a, b = chunk.split("→")
        conv = {"START": "__start__", "END": "__end__"}
        out.add((conv.get(a, a), conv.get(b, b)))
    return out


# --- transcripts ---------------------------------------------------------------------------------

ROMAN = ["I", "II", "III", "IV"]


def page_out(page_no: int, *, bad: bool = False, header: str | None = None) -> dict[str, Any]:
    """Page N: section ROMAN[N-1] with MCQ questions 2N-1 and 2N (``bad`` → one option only)."""
    opts = [{"label": x, "text": f"opt {x.lower()}"} for x in "ABCD"]
    questions = [
        {
            "printed_number": n,
            "answer_form": "choice",
            "stem": f"Page {page_no} question {n}: choose the word with a different sound {n}",
            "options": opts[:1] if bad and n == 2 * page_no else opts,
            "cue": None,
        }
        for n in (2 * page_no - 1, 2 * page_no)
    ]
    return {
        "header_text": header if page_no == 1 else None,
        "sections": [
            {
                "printed_title": ROMAN[page_no - 1],
                "instructions": "Choose the best answer.",
                "kind": "questions",
                "skill": "grammar",
                "points_text": "(0.5 pts)",
                "range_first": None,
                "range_last": None,
                "groups": [{"stimulus": None, "pictures": [], "questions": questions}],
            }
        ],
    }


HEADER = "TRUONG THCS A - DE KIEM TRA HOC KI I - LOP 8 - NAM HOC 2025-2026"

TITLES = ("TranscribeOut", "ReadHeaderOut", "ReadKeyOut", "ReadAnswersCall", "RereadPiecesOut")
BAD = "not json at all"


class Routed(FakeOllama):
    """Answers each request from the queue of its schema; ``ReadAnswersCall`` entries may be a
    function of the requested question IDs. An empty queue answers invalid JSON."""

    def __init__(self) -> None:
        super().__init__()
        self.queues: dict[str, list[Any]] = {}
        self.seen: list[tuple[str, dict[str, Any]]] = []

    def _script(self) -> ChatScript:
        body = self.requests[-1]
        fmt = body.get("format")
        text = json.dumps(body, ensure_ascii=False)
        title = fmt.get("title") if isinstance(fmt, dict) else None
        if fmt is None:
            title = "PlainText"  # step 22.5.7: the ocr_page call sends no format
        elif title not in TITLES:
            title = next(t for t in TITLES if f'"{t}"' in text)
        self.seen.append((title, body))
        queue = self.queues.get(title) or []
        item = queue.pop(0) if queue else BAD
        if isinstance(item, ChatScript):
            return item  # a scripted response (e.g. a low logprob)
        if callable(item):
            item = item(_answer_ids(fmt))
        response = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        return ChatScript(tokens=list(response))


def _answer_ids(fmt: dict[str, Any]) -> list[str]:
    answers = fmt["properties"]["answers"]
    if "$ref" in answers:
        answers = fmt["$defs"][answers["$ref"].split("/")[-1]]
    return list(answers["properties"].keys())


def answers_all(value: str = "A", skip: int | None = None) -> Any:
    def build(ids: list[str]) -> dict[str, Any]:
        return {
            "student_name": "Hoc Sinh A",
            "class_name": "8A",
            "answers": {
                qid: [{"value": value, "location": "circled_option", "alt_question_id": None}]
                for i, qid in enumerate(ids)
                if i != skip
            },
        }

    return build


EMPTY_ANSWERS = {"student_name": None, "class_name": None, "answers": {}}


# --- the harness ---------------------------------------------------------------------------------


def png(color: tuple[int, int, int] = (250, 250, 250), size: tuple[int, int] = (400, 600)) -> bytes:
    buf = io.BytesIO()
    img = Image.linear_gradient("L").resize(size).convert("RGB")
    Image.blend(img, Image.new("RGB", size, color), 0.5).save(buf, format="PNG")
    return buf.getvalue()


@dataclass
class Harness:
    manager: RunManager
    fake: Routed
    files: FileStore
    conn: sqlite3.Connection
    thread_id: str
    saved_states: list[dict[str, Any]]
    save_mode: str = "real"  # "real" | "stub" (fail before writing) | "crash_after" (once)

    def photos(self, n: int, *, texts: dict[int, str] | None = None) -> list[PageInput]:
        out = []
        for i in range(1, n + 1):
            fid = self.files.put(png((200 + i, 250, 250 - i)), "png")
            tid = self.files.put_text(texts[i]) if texts and i in texts else None
            out.append(PageInput(file_id=fid, rotation=0, is_key=False, text_file_id=tid))
        return out

    async def run(
        self,
        pages: list[PageInput],
        existing: str | None = None,
        *,
        supersedes: str | None = None,
        thread_id: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Run to the end; return the run id and the state ``save`` received."""
        inp = ExtractInput(pages=pages, existing_test_id=existing, supersedes_attempt_id=supersedes)
        self.saved_states.clear()
        run = await self.manager.submit(thread_id or self.thread_id, "extract", inp)
        await asyncio.wait_for(self.manager.wait_idle(), TIMEOUT)
        assert self.saved_states, "save was never reached"
        return run.id, self.saved_states[-1]

    def steps(self, run_id: str, node: str | None = None) -> list[Any]:
        return [s for s in runs.list_steps(self.conn, run_id) if node is None or s.node == node]

    def runs_status(self, run_id: str) -> str:
        run = runs.get_run(self.conn, run_id)
        assert run is not None
        return run.status

    def count(self, table: str) -> int:
        return int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


@pytest.fixture
def data(tmp_path: Path) -> DataPaths:
    paths = DataPaths(tmp_path / "data")
    db.open_database(paths.db).close()
    return paths


@pytest.fixture
def conn(data: DataPaths) -> Iterator[sqlite3.Connection]:
    c = db.connect(data.db)
    yield c
    c.close()


_REAL_SAVE = extract_mod.save_extract


@contextlib.asynccontextmanager
async def make_harness(
    data: DataPaths,
    monkeypatch: pytest.MonkeyPatch,
    *,
    tiles: bool = False,
    keep: str = "better",
    reread: bool = False,
    ocr: bool | None = False,
) -> AsyncIterator[Harness]:
    """``tiles``: ``[extract] retranscribe_tiles`` (off by default, speed bundle 1);
    ``reread``: ``[extract] reread_pieces`` (off by default, step 22.5.7); ``ocr``:
    ``[extract] photo_reader`` ``"ocr"`` or ``"vision"`` (the scenarios here were written for
    vision), with ``photo_structure = "qwen"``; ``None``: the data folder's own
    ``models.toml`` (none: the defaults, R22.5.7.7)."""
    conn = db.connect(data.db)
    fake = Routed()
    files_conn = db.connect(data.db)
    client_conn = db.connect(data.db)
    files = FileStore(files_conn, data)
    config = (
        load_models_config(data)
        if ocr is None
        else parse_models_config(
            {
                "extract": {
                    "retranscribe_tiles": tiles,
                    "retranscribe_tiles_keep": keep,
                    "reread_pieces": reread,
                    "photo_reader": "ocr" if ocr else "vision",
                    # the OCR scenarios here were written for way 1 (the default before
                    # step 22.6.6 (c), D16)
                    "photo_structure": "qwen",
                }
            }
        )
    )
    client = OllamaClient(
        client_conn,
        config,
        FilePromptProvider(),
        base_url="http://fake-ollama",
        transport=fake.transport,
        read_image=files.read_bytes,
    )
    manager = RunManager(data.db, events=EventBus(), power=FakePower())
    register_extract(manager, ExtractDeps(client=client, files=files))
    await manager.start()
    thread_id = threads.create_thread(conn, "t").id
    harness = Harness(manager, fake, FileStore(conn, data), conn, thread_id, [])

    def recording(c: sqlite3.Connection, state: Any, **kw: Any) -> dict[str, Any]:
        harness.saved_states.append(dict(state))
        if harness.save_mode == "stub":
            raise NotImplementedError("save stubbed by the test")
        out = _REAL_SAVE(c, state, **kw)
        if harness.save_mode == "crash_after":
            harness.save_mode = "real"
            raise StreamDropped("save (crash injected after the commit)", [])
        return out

    monkeypatch.setattr(extract_mod, "save_extract", recording)
    try:
        yield harness
    finally:
        await manager.aclose()
        files_conn.close()
        client_conn.close()
        conn.close()


@pytest_asyncio.fixture
async def h(data: DataPaths, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Harness]:
    async with make_harness(data, monkeypatch) as harness:
        yield harness


@pytest_asyncio.fixture
async def ht(data: DataPaths, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Harness]:
    """The harness with ``retranscribe_tiles`` on (the tile path, tested on purpose)."""
    async with make_harness(data, monkeypatch, tiles=True) as harness:
        yield harness


def _state(state: dict[str, Any]) -> dict[str, Any]:
    """The state ``save`` received, with merge_and_normalize's pendings folded in."""
    out = dict(state)
    out["pending_reviews"] = [
        *(state.get("pending_reviews") or []),
        *(state.get("merge_pendings") or []),
    ]
    return out


def _kinds(state: dict[str, Any]) -> list[str]:
    return [p["kind"] for p in state["pending_reviews"]]


# --- R9.1 ----------------------------------------------------------------------------------------


def test_r9_1_graph_equals_appendix_c1() -> None:
    from unittest.mock import MagicMock

    graph = build_extract_graph(ExtractDeps(client=MagicMock(), files=MagicMock()))(None)
    g = graph.get_graph()
    edges = {(e.source, e.target) for e in g.edges}
    assert edges == _c1_edges()
    assert set(g.nodes) - {"__start__", "__end__"} == set(C1_NODES)
    assert set(C1_EDGES) == _c1_edges()


def test_thresholds_defaults() -> None:
    t = ExtractThresholds()
    assert (t.reading, t.key_photo, t.looks_like, t.possibly, t.sanity) == (
        0.7,
        0.7,
        0.85,
        0.5,
        0.5,
    )


# --- the new-test path ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_new_filled_path_and_r9_8(h: Harness) -> None:
    h.save_mode = "stub"
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        # 22.5.6: each page is asked only for its own questions; q4 = page 2's 2nd (index 1)
        "ReadAnswersCall": [answers_all("B"), answers_all("B", skip=1)],
    }
    run_id, snap = await h.run(h.photos(2))
    s = _state(snap)
    assert [st.item for st in h.steps(run_id, "transcribe_page")] == ["page 1", "page 2"]
    assert h.steps(run_id, "retranscribe_tiles") == []
    assert s["draft"]["meta"]["grade"] == 8
    assert len(s["answers"]) == 4
    assert all(a["attempt_id"] == "" for a in s["answers"])
    omitted = [a for a in s["answers"] if a["value"] is None]
    assert len(omitted) == 1 and omitted[0]["reading_unsure"]  # omitted → "?"
    read = [a for a in s["answers"] if a["value"] is not None]
    assert all(a["value"] == "B" and not a["reading_unsure"] for a in read)
    assert s["student_name"] == "Hoc Sinh A" and s["blank"] is False
    assert s["compare"]["best_test_id"] is None
    # prepared pages hold IDs only; the resize kept the size (≤ 1600)
    assert all(set(p) >= {"file_id", "source_file_id"} for p in s["pages"])
    # R9.8: stopped before save → no domain rows
    assert h.runs_status(run_id) == "failed"
    assert h.count("tests") == h.count("attempts") == h.count("review_items") == 0


@pytest.mark.asyncio
async def test_r9_10_text_page_sends_text_not_image(h: Harness) -> None:
    text = "TEXT LAYER: Question 1. Choose the best answer UNIQUE-MARKER-42"
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER)],
        "ReadAnswersCall": [answers_all()],
    }
    _, snap = await h.run(h.photos(1, texts={1: text}))
    _state(snap)
    transcribe = [body for title, body in h.fake.seen if title == "TranscribeOut"]
    assert len(transcribe) == 1
    body = json.dumps(transcribe[0], ensure_ascii=False)
    assert "UNIQUE-MARKER-42" in body
    assert not any(m.get("images") for m in transcribe[0]["messages"])


@pytest.mark.asyncio
async def test_text_only_page_sends_text_to_every_call(h: Harness) -> None:
    """M1 baseline fix: a picture-free DOCX is one text-only page (``file_id = text_file_id``).
    ``prepare_pages`` leaves it as it is (no image op), and ``transcribe_page`` sends its text,
    never an image (PRD §11). A run of text-only pages reads no answers (PRD D26):
    ``test_mixed_run_sends_the_text_page_to_read_answers`` covers ``read_answers_page``."""
    tid = h.files.put_text("DOCX TEXT: Question 1. Choose A, B, C or D. DOCX-MARKER-7")
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER)],
        "ReadAnswersCall": [answers_all()],
    }
    run_id, snap = await h.run([PageInput(file_id=tid, rotation=0, is_key=False, text_file_id=tid)])
    s = _state(snap)
    assert s["pages"] == [
        {
            "page_no": 1,
            "file_id": tid,
            "source_file_id": tid,
            "rotation": 0,
            "text_layer": "DOCX TEXT: Question 1. Choose A, B, C or D. DOCX-MARKER-7",
        }
    ]
    calls = [(t, b) for t, b in h.fake.seen if t in ("TranscribeOut", "ReadAnswersCall")]
    assert [t for t, _ in calls] == ["TranscribeOut"]  # D26: no answer reading
    for _, body in calls:
        assert "DOCX-MARKER-7" in json.dumps(body, ensure_ascii=False)
        assert not any(m.get("images") for m in body["messages"])
    assert h.steps(run_id, "retranscribe_tiles") == []
    assert h.runs_status(run_id) == "done"
    assert h.count("files") == 1  # no derived image was made from the text
    row = h.conn.execute("SELECT file_id FROM test_pages").fetchone()
    assert row[0] == tid


@pytest.mark.asyncio
async def test_mixed_run_sends_the_text_page_to_read_answers(h: Harness) -> None:
    """PRD D26 skips answer reading only when every test page is born-digital. A text-only page
    next to a photo is still read for answers, from its text (no image, PRD §11); the photo
    sends its image."""
    tid = h.files.put_text("DOCX TEXT: Question 1. Choose A, B, C or D. DOCX-MARKER-7")
    pages = [PageInput(file_id=tid, rotation=0, is_key=False, text_file_id=tid), *h.photos(1)]
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [answers_all(), answers_all()],
    }
    run_id, snap = await h.run(pages)
    assert snap["skip_answers"] is False
    reads = [b for t, b in h.fake.seen if t == "ReadAnswersCall"]
    assert len(reads) == 2
    assert "DOCX-MARKER-7" in json.dumps(reads[0], ensure_ascii=False)
    assert not any(m.get("images") for m in reads[0]["messages"])
    assert any(m.get("images") for m in reads[1]["messages"])
    assert h.runs_status(run_id) == "done"
    assert h.count("attempts") == 1


# --- PRD D26: typed input is a blank test ---------------------------------------------------------


def _text_pdf(pages: int) -> bytes:
    import pymupdf

    doc = pymupdf.open()
    for n in range(1, pages + 1):
        page = doc.new_page(width=595, height=842)
        body = "\n".join(
            f"{q}. Choose the word with a different sound, page {n}. A. cat B. hat C. car D. map"
            for q in (2 * n - 1, 2 * n)
        )
        page.insert_text((40, 72), f"PAGE {n} - TYPED TEST\n{body}", fontsize=9)
    data = bytes(doc.tobytes())
    doc.close()
    return data


def _assert_blank_test(h: Harness, run_id: str) -> None:
    assert h.runs_status(run_id) == "done"
    assert h.count("tests") == 1
    assert h.count("attempts") == 0
    assert h.count("answers") == 0
    kind = h.conn.execute("SELECT kind FROM threads WHERE id = ?", (h.thread_id,)).fetchone()[0]
    assert kind == "blank"


@pytest.mark.asyncio
async def test_d26_typed_pdf_reads_no_answers_and_saves_a_blank_test(h: Harness) -> None:
    from etach.store.documents import ingest

    pages = ingest(h.files, _text_pdf(2), "typed.pdf")
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [answers_all(), answers_all()],
    }
    run_id, snap = await h.run(pages)
    assert snap["skip_answers"] is True
    # D12 (step 22.5.6): the two typed pages are joined into one text piece, one call
    assert [t for t, _ in h.fake.seen] == ["TranscribeOut"]
    assert snap["absorbed_pages"] == [2]
    n = h.conn.execute(
        "SELECT COUNT(*) FROM llm_calls l JOIN steps s ON s.id = l.step_id"
        " WHERE s.run_id = ? AND s.node = 'read_answers_page'",
        (run_id,),
    ).fetchone()[0]
    assert n == 0
    assert snap["blank"] is True
    _assert_blank_test(h, run_id)


@pytest.mark.asyncio
async def test_d26_docx_with_a_picture_reads_no_answers(h: Harness) -> None:
    import docx
    from docx.shared import Inches

    from etach.store.documents import ingest

    document = docx.Document()
    document.add_paragraph("1. Choose A, B, C or D. TYPED DOCX")
    document.add_picture(io.BytesIO(png()), width=Inches(1))
    buf = io.BytesIO()
    document.save(buf)
    pages = ingest(h.files, buf.getvalue(), "typed.docx")
    assert len(pages) == 2  # a text page and a picture page
    h.fake.queues = {"TranscribeOut": [page_out(1, header=HEADER), page_out(2)]}
    run_id, snap = await h.run(pages)
    assert snap["skip_answers"] is True
    assert "ReadAnswersCall" not in [t for t, _ in h.fake.seen]
    _assert_blank_test(h, run_id)


@pytest.mark.asyncio
async def test_d26_photo_run_still_reads_answers(h: Harness) -> None:
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [answers_all(), answers_all()],
    }
    run_id, snap = await h.run(h.photos(2))
    assert snap["skip_answers"] is False
    assert [t for t, _ in h.fake.seen].count("ReadAnswersCall") == 2
    assert h.count("attempts") == 1
    assert h.runs_status(run_id) == "done"


@pytest.mark.asyncio
async def test_text_only_page_failing_validation_makes_no_tiles(h: Harness) -> None:
    """structure.md v1.1.47: a text-only page that fails validation is not cut into tiles
    (it has no image); it gets one ``validator_failed`` item at once, and the run finishes."""
    tid = h.files.put_text("DOCX TEXT: Question 1 and 2, one with a single option")
    h.fake.queues = {
        "TranscribeOut": [page_out(1, bad=True, header=HEADER)],
        "ReadAnswersCall": [answers_all()],
    }
    run_id, snap = await h.run([PageInput(file_id=tid, rotation=0, is_key=False, text_file_id=tid)])
    s = _state(snap)
    assert [t for t, _ in h.fake.seen].count("TranscribeOut") == 1  # no tile calls
    assert h.count("files") == 1  # no tile images
    assert _kinds(s).count("validator_failed") == 1
    assert h.runs_status(run_id) == "done"
    row = h.conn.execute(
        "SELECT COUNT(*) FROM review_items WHERE kind = 'validator_failed'"
    ).fetchone()
    assert row[0] == 1


@pytest.mark.asyncio
async def test_r9_9_retranscribe_then_validator_failed(ht: Harness) -> None:
    h = ht
    h.fake.queues = {
        # page 2 fails validation; both tiles still fail → validator_failed
        "TranscribeOut": [
            page_out(1, header=HEADER),
            page_out(2, bad=True),
            page_out(2, bad=True),
            page_out(2, bad=True),
        ],
        "ReadAnswersCall": [answers_all(), EMPTY_ANSWERS],
    }
    run_id, snap = await h.run(h.photos(2))
    s = _state(snap)
    tiles = h.steps(run_id, "retranscribe_tiles")
    assert [t.item for t in tiles] == ["page 2"]
    assert len(h.steps(run_id, "merge_and_normalize")) == 2
    vf = [p for p in s["pending_reviews"] if p["kind"] == "validator_failed"]
    assert len(vf) == 1 and vf[0]["refs"] == {"page_no": 2}
    assert vf[0]["proposal"]["failures"][0]["validator"] == "mcq_options"
    assert s["draft"] is not None  # kept with what was read
    derived = h.conn.execute("SELECT COUNT(*) FROM files WHERE kind='derived'").fetchone()[0]
    assert derived >= 2  # the two tiles


@pytest.mark.asyncio
async def test_tiles_off_a_failing_page_goes_straight_to_validator_failed(h: Harness) -> None:
    """Speed bundle 1, ``[extract] retranscribe_tiles = false`` (the default): no tile step,
    no tile call, no tile files; the page failing the first pass → one ``validator_failed``
    (task ``transcribe_page``), and the run saves what was read."""
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2, bad=True), page_out(2)],
        "ReadAnswersCall": [answers_all(), EMPTY_ANSWERS],
    }
    run_id, snap = await h.run(h.photos(2))
    s = _state(snap)
    assert h.steps(run_id, "retranscribe_tiles") == []
    assert len(h.steps(run_id, "merge_and_normalize")) == 1
    assert sum(1 for title, _ in h.fake.seen if title == "TranscribeOut") == 2
    vf = [p for p in s["pending_reviews"] if p["kind"] == "validator_failed"]
    assert len(vf) == 1 and vf[0]["refs"] == {"page_no": 2}
    assert vf[0]["proposal"]["task"] == "transcribe_page"
    assert vf[0]["proposal"]["failures"][0]["validator"] == "mcq_options"
    assert s["draft"] is not None
    derived = h.conn.execute("SELECT COUNT(*) FROM files WHERE kind='derived'").fetchone()[0]
    assert derived == 0  # no tiles cut (these small photos need no resize either)
    assert h.runs_status(run_id) == "done"


def _tile_out(page_no: int) -> dict[str, Any]:
    """A tile reading of page N that is no better: both questions have one option, and the
    stems say "tile" (to tell which reading the draft kept)."""
    out = page_out(page_no, bad=True)
    for q in out["sections"][0]["groups"][0]["questions"]:
        q["stem"] = q["stem"].replace("Page", "Tile")
        q["options"] = q["options"][:1]
    return out


def _stems(state: dict[str, Any]) -> list[str]:
    return [
        q["stem"]
        for s in state["draft"]["content"]["sections"]
        for g in s["groups"]
        for q in g["questions"]
    ]


@pytest.mark.asyncio
async def test_tiles_no_better_keep_the_first_pass(ht: Harness) -> None:
    """Speed bundle 1: a tile reading that does not reduce the page's validator failures (here
    it has more) is dropped; the first pass stays, and the page → validator_failed."""
    h = ht
    h.fake.queues = {
        "TranscribeOut": [
            page_out(1, header=HEADER),
            page_out(2, bad=True),
            _tile_out(2),
            _tile_out(2),
        ],
        "ReadAnswersCall": [answers_all(), EMPTY_ANSWERS],
    }
    run_id, snap = await h.run(h.photos(2))
    s = _state(snap)
    assert len(h.steps(run_id, "retranscribe_tiles")) == 1
    assert sum(1 for title, _ in h.fake.seen if title == "TranscribeOut") == 4
    stems = _stems(s)
    assert stems and not any("Tile" in stem for stem in stems)
    assert any("Page 2 question 4" in stem for stem in stems)
    vf = [p for p in s["pending_reviews"] if p["kind"] == "validator_failed"]
    assert len(vf) == 1 and vf[0]["refs"] == {"page_no": 2}
    assert len(vf[0]["proposal"]["failures"]) == 1  # the first pass's one failure


@pytest.mark.asyncio
async def test_each_tile_call_logs_its_page_and_tile(ht: Harness) -> None:
    """Speed bundle 1: the step's item names every page ("pages 2, 3"), so each tile call
    stores its own label in ``llm_calls.request.item``, and ``etach eval --keep``'s
    ``llm_calls.json`` shows it as the call's ``item``."""
    from etach.eval.harness import run_calls

    h = ht
    h.fake.queues = {
        "TranscribeOut": [
            page_out(1, header=HEADER),
            page_out(2, bad=True),
            page_out(3, bad=True),
            *[page_out(2, bad=True)] * 2,
            *[page_out(3, bad=True)] * 2,
        ],
        "ReadAnswersCall": [answers_all(), EMPTY_ANSWERS, EMPTY_ANSWERS],
    }
    run_id, _ = await h.run(h.photos(3))
    [tiles] = h.steps(run_id, "retranscribe_tiles")
    assert tiles.item == "pages 2, 3"
    rows = runs.list_llm_calls(h.conn, tiles.id)
    assert [r.request.get("item") for r in rows] == ["p2 top", "p2 bottom", "p3 top", "p3 bottom"]
    first = [
        r.request
        for s in h.steps(run_id, "transcribe_page")
        for r in runs.list_llm_calls(h.conn, s.id)
    ]
    assert first and all("item" not in r for r in first)  # no label where the step says it
    assert all("item" not in body for _title, body in h.fake.seen)  # never sent to Ollama
    calls = [c for c in run_calls(h.conn, run_id) if c["node"] == "retranscribe_tiles"]
    assert [c["item"] for c in calls] == ["p2 top", "p2 bottom", "p3 top", "p3 bottom"]
    assert {c["step_item"] for c in calls} == {"pages 2, 3"}


@pytest.mark.asyncio
async def test_tiles_keep_always_is_the_old_rule(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``retranscribe_tiles_keep = "always"``: the tile reading replaces the page even when
    worse (the rule before speed bundle 1, kept for the old recordings)."""
    async with make_harness(data, monkeypatch, tiles=True, keep="always") as h:
        h.fake.queues = {
            "TranscribeOut": [
                page_out(1, header=HEADER),
                page_out(2, bad=True),
                _tile_out(2),
                _tile_out(2),
            ],
            "ReadAnswersCall": [answers_all(), EMPTY_ANSWERS],
        }
        _run_id, snap = await h.run(h.photos(2))
        s = _state(snap)
        assert any("Tile 2 question 4" in stem for stem in _stems(s))


@pytest.mark.asyncio
async def test_tiles_skip_a_pdf_text_layer_page(ht: Harness) -> None:
    """Speed bundle 1: a page with a text layer (a PDF page with text) was transcribed from its
    exact text; tiles never replace it with an image read: no tile call, no tile file, the
    first pass stays and the page → validator_failed."""
    h = ht
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2, bad=True), page_out(2)],
        "ReadAnswersCall": [answers_all(), EMPTY_ANSWERS],
    }
    pages = h.photos(2, texts={2: "Page 2 text layer: II. Choose the best answer."})
    run_id, snap = await h.run(pages)
    s = _state(snap)
    assert len(h.steps(run_id, "retranscribe_tiles")) == 1
    assert sum(1 for title, _ in h.fake.seen if title == "TranscribeOut") == 2
    derived = h.conn.execute("SELECT COUNT(*) FROM files WHERE kind='derived'").fetchone()[0]
    assert derived == 0
    vf = [p for p in s["pending_reviews"] if p["kind"] == "validator_failed"]
    assert len(vf) == 1 and vf[0]["refs"] == {"page_no": 2}


@pytest.mark.asyncio
async def test_retranscribe_fixes_the_page(ht: Harness) -> None:
    h = ht
    h.fake.queues = {
        "TranscribeOut": [
            page_out(1, header=HEADER),
            page_out(2, bad=True),
            page_out(2),
            page_out(2),
        ],  # overlapping tiles repeat the questions
        "ReadAnswersCall": [answers_all(), EMPTY_ANSWERS],
    }
    _run_id, snap = await h.run(h.photos(2))
    s = _state(snap)
    assert "validator_failed" not in _kinds(s)
    assert len(s["answers"]) == 4  # the overlap did not duplicate questions


@pytest.mark.asyncio
async def test_call_failures_do_not_crash(h: Harness) -> None:
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), BAD, BAD],  # page 2 fails twice
        "ReadAnswersCall": [BAD, BAD, EMPTY_ANSWERS],  # page 1 answers fail twice
    }
    run_id, snap = await h.run(h.photos(2))
    s = _state(snap)
    vf = {p["dedupe_key"]: p for p in s["pending_reviews"] if p["kind"] == "validator_failed"}
    assert f"validator_failed:{run_id}:transcribe:2" in vf
    assert f"validator_failed:{run_id}:answers:1" in vf
    assert s["answers_failed"] == [1]
    assert s["blank"] is False
    assert all(a["reading_unsure"] for a in s["answers"])


@pytest.mark.asyncio
async def test_output_capped_page_is_a_failed_call_without_retry(h: Harness) -> None:
    """Speed bundle 1: a transcription cut at ``num_predict`` (8192 tokens, invalid JSON) is not
    retried; the graph treats it like any failed call (llm-design §5.1): ``validator_failed``
    for that page with the ``output_capped`` reason, and the test is saved with what was read."""
    capped = ChatScript(tokens=['{"sections": [', *(["x"] * 8191)])
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), capped, page_out(2)],
        "ReadAnswersCall": [answers_all(), EMPTY_ANSWERS],
    }
    run_id, snap = await h.run(h.photos(2))
    s = _state(snap)
    assert sum(1 for title, _ in h.fake.seen if title == "TranscribeOut") == 2  # no retry
    [page2] = h.steps(run_id, "transcribe_page")[1:]
    [row] = runs.list_llm_calls(h.conn, page2.id)
    assert row.status == "invalid" and row.tokens_out == 8192
    vf = {p["dedupe_key"]: p for p in s["pending_reviews"] if p["kind"] == "validator_failed"}
    proposal = vf[f"validator_failed:{run_id}:transcribe:2"]["proposal"]
    assert proposal["call_failure"].startswith("output_capped:")
    assert h.runs_status(run_id) == "done"


@pytest.mark.asyncio
async def test_b1_truncated_answer_prompt_fails_the_page_loudly(h: Harness) -> None:
    """B1: a read_answers prompt that does not fit ``num_ctx`` is a failed call (no retry), not
    an answer: the page's answers are unsure, one ``validator_failed``, the run finishes, and
    the ``llm_calls`` row is ``error``."""
    too_long = ChatScript(text="", error_chunk="the input length exceeds the context length")
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER)],
        "ReadAnswersCall": [too_long, answers_all()],
    }
    run_id, snap = await h.run(h.photos(1))
    s = _state(snap)
    assert h.runs_status(run_id) == "done"
    assert s["answers_failed"] == [1]
    assert f"validator_failed:{run_id}:answers:1" in {
        p["dedupe_key"] for p in s["pending_reviews"] if p["kind"] == "validator_failed"
    }
    assert s["answers"] and all(a["reading_unsure"] for a in s["answers"])
    assert all(a["value"] is None for a in s["answers"])
    [step] = h.steps(run_id, "read_answers_page")
    assert [c.status for c in runs.list_llm_calls(h.conn, step.id)] == ["error"]
    assert [t for t, _ in h.fake.seen].count("ReadAnswersCall") == 1


# --- key photos ----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_key_pages_read_and_mapped(h: Harness) -> None:
    pages = h.photos(1)
    key_fid = h.files.put(png((10, 10, 10)), "png")
    pages.append(PageInput(file_id=key_fid, rotation=90, is_key=True, text_file_id=None))
    h.fake.queues = {
        "ReadKeyOut": [{"entries": [{"label": "1", "answer": "A"}, {"label": "2", "answer": "C"}]}],
        "TranscribeOut": [page_out(1, header=HEADER)],
        "ReadAnswersCall": [answers_all()],
    }
    _run_id, snap = await h.run(pages)
    s = _state(snap)
    assert [(r[0], r[1]) for r in s["key_raw"]] == [("1", "A"), ("2", "C")]
    assert all(0.0 <= r[2] <= 1.0 for r in s["key_raw"])
    assert len(s["key"]) == 2 and len(s["pages"]) == 1 and len(s["key_pages"]) == 1
    assert set(s["key_status"]) == {e["question_id"] for e in s["key"]}


@pytest.mark.asyncio
async def test_key_page_failure_gives_no_key(h: Harness) -> None:
    pages = h.photos(1)
    key_fid = h.files.put(png((10, 10, 10)), "png")
    pages.append(PageInput(file_id=key_fid, rotation=0, is_key=True, text_file_id=None))
    h.fake.queues = {
        "ReadKeyOut": [BAD, BAD],
        "TranscribeOut": [page_out(1, header=HEADER)],
        "ReadAnswersCall": [answers_all()],
    }
    _, snap = await h.run(pages)
    s = _state(snap)
    assert s["key_raw"] is None and s["key"] == []


# --- the picked path -----------------------------------------------------------------------------


def _bank_test(h: Harness, pages: int) -> BankTest:
    transcripts = [
        renumber.page_transcript(
            p, TranscribeOut.model_validate(page_out(p, header=HEADER)), "call"
        )
        for p in range(1, pages + 1)
    ]
    merged = renumber.merge_pages(transcripts, page_files={1: "f1", 2: "f2"}, ref="bank")
    now = datetime.now(UTC)
    d = merged.draft
    return test_repo.insert_test(
        h.conn,
        BankTest(
            id=test_repo.next_test_id(h.conn),
            meta=d.meta,
            content=d.content,
            content_schema_version=1,
            fingerprint=d.fingerprint,
            points_possible=d.points_possible,
            source_run_id=None,
            merged_into=None,
            created_at=now,
            updated_at=now,
        ),
    )


@pytest.mark.asyncio
async def test_picked_match_no_transcription(h: Harness) -> None:
    bank = _bank_test(h, 2)
    stems = [q.stem for s in bank.content.sections for g in s.groups for q in g.questions]
    h.fake.queues = {
        "ReadHeaderOut": [{"header_text": HEADER, "first_stems": stems[:3]}],
        # 22.5.6: each page is asked only for its own questions
        "ReadAnswersCall": [answers_all(), answers_all()],
    }
    run_id, snap = await h.run(h.photos(2), existing=bank.id)
    s = _state(snap)
    assert h.steps(run_id, "transcribe_page") == []
    assert [st.item for st in h.steps(run_id, "read_header")] == ["page 1"]
    assert "picked_test_mismatch" not in _kinds(s)
    assert s["draft"]["fingerprint"] == bank.fingerprint
    assert len(s["answers"]) == 4
    # 22.5.6: photo count == draft page count, so each page is asked only for its own questions
    # (an answer written only on another page is not read: accepted limit); no page hints
    pages = {q.id: q.page_no for sec in bank.content.sections for g in sec.groups
             for q in g.questions}  # fmt: skip
    asked = [_answer_ids(b["format"]) for t, b in h.fake.seen if t == "ReadAnswersCall"]
    assert [{pages[i] for i in ids} for ids in asked] == [{1}, {2}]
    reqs = [json.dumps(b, ensure_ascii=False) for t, b in h.fake.seen if t == "ReadAnswersCall"]
    assert not any("printed on page" in r for r in reqs)
    assert h.count("tests") == 1  # only the bank test


@pytest.mark.asyncio
async def test_picked_mismatch(h: Harness) -> None:
    bank = _bank_test(h, 2)
    h.fake.queues = {
        "ReadHeaderOut": [
            {"header_text": "UNRELATED", "first_stems": ["Zebras jump over lazy xylophones"]}
        ],
        "ReadAnswersCall": [answers_all()],
    }
    _run_id, snap = await h.run(h.photos(1), existing=bank.id)
    s = _state(snap)
    mm = [p for p in s["pending_reviews"] if p["kind"] == "picked_test_mismatch"]
    assert len(mm) == 1 and mm[0]["refs"] == {"test_id": bank.id}
    # 1 photo, 2 draft pages → no page hints
    answers_req = next(b for t, b in h.fake.seen if t == "ReadAnswersCall")
    assert "| printed on page" not in json.dumps(answers_req, ensure_ascii=False)


@pytest.mark.asyncio
async def test_compare_bank_possible_duplicate(h: Harness) -> None:
    bank = _bank_test(h, 2)
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [answers_all(), EMPTY_ANSWERS],
    }
    _, snap = await h.run(h.photos(2))
    s = _state(snap)
    dup = [p for p in s["pending_reviews"] if p["kind"] == "possible_duplicate"]
    assert len(dup) == 1 and dup[0]["refs"] == {"test_id": bank.id}
    assert dup[0]["proposal"]["question_alignment"]


# --- save scenarios (step 9 part B) ---------------------------------------------------------------

STUDENT = "Học Sinh A"  # synthetic


def answers_named(name: str | None = STUDENT, cls: str | None = "8A") -> Any:
    def build(ids: list[str]) -> dict[str, Any]:
        out = answers_all("A")(ids)
        out["student_name"], out["class_name"] = name, cls
        return out

    return build


def _items(h: Harness, kind: str | None = None) -> list[sqlite3.Row]:
    rows = h.conn.execute("SELECT * FROM review_items ORDER BY created_at, id").fetchall()
    return [r for r in rows if kind is None or r["kind"] == kind]


def _cards(h: Harness, thread_id: str | None = None) -> list[dict[str, Any]]:
    msgs = threads.list_messages(h.conn, thread_id or h.thread_id)
    return [m.body for m in msgs if m.kind == "run_card" and m.role == "app"]


def _thread(h: Harness, thread_id: str | None = None) -> Any:
    return threads.get_thread(h.conn, thread_id or h.thread_id)


def _seed_bank(h: Harness, stems: dict[int, str]) -> BankTest:
    """A 2-page bank test built like the fake's transcripts, with some stems replaced."""
    transcripts = []
    for p in (1, 2):
        out = page_out(p, header=HEADER)
        for g in out["sections"][0]["groups"]:
            for q in g["questions"]:
                q["stem"] = stems.get(q["printed_number"], q["stem"])
        transcripts.append(renumber.page_transcript(p, TranscribeOut.model_validate(out), "call"))
    d = renumber.merge_pages(transcripts, page_files={1: "f1", 2: "f2"}, ref="bank").draft
    now = datetime.now(UTC)
    return test_repo.insert_test(
        h.conn,
        BankTest(
            id=test_repo.next_test_id(h.conn),
            meta=d.meta,
            content=d.content,
            content_schema_version=1,
            fingerprint=d.fingerprint,
            points_possible=d.points_possible,
            source_run_id=None,
            merged_into=None,
            created_at=now,
            updated_at=now,
        ),
    )


@pytest.mark.asyncio
async def test_r9_2_synthetic_s1_like_filled_run(h: Harness) -> None:
    """SYNTHETIC stand-in for R9.2 (the recorded S1 cassette comes with the teacher's recording)."""
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2), page_out(3)],
        # 22.5.6: each page is asked only for its own questions
        "ReadAnswersCall": [answers_named()] * 3,
    }
    run_id, _ = await h.run(h.photos(3))
    assert h.runs_status(run_id) == "done"
    assert h.count("tests") == 1 and h.count("attempts") == 1
    test = test_repo.find_by_source_run(h.conn, run_id)
    assert test is not None and len(test_repo.list_test_pages(h.conn, test.id)) == 3
    graded = sum(1 for s in test.content.sections for g in s.groups for q in g.questions)
    assert h.count("answers") == graded == 6
    assert h.count("attempt_pages") == 3
    att = h.conn.execute("SELECT * FROM attempts").fetchone()
    assert att["student_name_read"] == STUDENT and att["class_read"] == "8A"
    assert att["status"] == "extracted" and att["version"] == 1
    assert att["source_run_id"] == run_id and att["test_id"] == test.id
    th = _thread(h)
    assert th.kind == "filled" and th.test_id == test.id
    assert _cards(h) == [
        {
            "run_id": run_id,
            "test_id": test.id,
            "attempt_id": att["id"],
            "unsure_count": 0,
            "no_answers": False,
            "duplicate": None,
            "student_name_read": STUDENT,
        }
    ]
    # R9.12 (no match): no students → student_id NULL + 1 unknown_student with the name read
    assert att["student_id"] is None
    unknown = _items(h, "unknown_student")
    assert len(unknown) == 1 and unknown[0]["attempt_id"] == att["id"]
    assert json.loads(unknown[0]["proposal"])["student_name_read"] == STUDENT
    assert all(r["owner"] == "extract" and r["test_id"] == test.id for r in _items(h))


@pytest.mark.asyncio
async def test_r9_12_student_matched(h: Harness) -> None:
    students.create_student(h.conn, STUDENT, name_search(STUDENT), class_name="8A")
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER)],
        "ReadAnswersCall": [answers_named("hoc  sinh a")],
    }
    await h.run(h.photos(1))
    att = h.conn.execute("SELECT * FROM attempts").fetchone()
    assert att["student_id"] == "S-0001"
    assert _items(h, "unknown_student") == []


@pytest.mark.asyncio
async def test_r9_3_filled_picked_match_and_mismatch(h: Harness) -> None:
    bank = _bank_test(h, 2)
    stems = [q.stem for s in bank.content.sections for g in s.groups for q in g.questions]
    h.fake.queues = {
        "ReadHeaderOut": [{"header_text": HEADER, "first_stems": stems[:3]}],
        "ReadAnswersCall": [answers_named(), EMPTY_ANSWERS],
    }
    run_id, _ = await h.run(h.photos(2), existing=bank.id)
    assert h.steps(run_id, "transcribe_page") == []
    assert h.count("tests") == 1 and h.count("test_pages") == 0
    att = attempts.find_by_source_run(h.conn, run_id)
    assert att is not None and att.test_id == bank.id
    assert _thread(h).test_id == bank.id and _thread(h).kind == "filled"
    assert _items(h, "picked_test_mismatch") == []
    # mismatch, in a second thread
    t2 = threads.create_thread(h.conn, "t2").id
    h.fake.queues = {
        "ReadHeaderOut": [{"header_text": "UNRELATED", "first_stems": ["Zebras jump lazily"]}],
        "ReadAnswersCall": [answers_named(), EMPTY_ANSWERS],
    }
    run2, _ = await h.run(h.photos(2), existing=bank.id, thread_id=t2)
    att2 = attempts.find_by_source_run(h.conn, run2)
    assert att2 is not None and att2.test_id == bank.id
    mm = _items(h, "picked_test_mismatch")
    assert len(mm) == 1 and mm[0]["test_id"] == bank.id and mm[0]["attempt_id"] == att2.id


@pytest.mark.asyncio
async def test_r9_4_blank_new(h: Harness) -> None:
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [EMPTY_ANSWERS, EMPTY_ANSWERS],
    }
    run_id, _ = await h.run(h.photos(2))
    assert h.runs_status(run_id) == "done"
    assert h.count("tests") == 1 and h.count("attempts") == 0 and h.count("answers") == 0
    test = test_repo.find_by_source_run(h.conn, run_id)
    assert test is not None
    assert _thread(h).kind == "blank" and _thread(h).test_id == test.id
    card = _cards(h)[0]
    assert card["no_answers"] is True and card["attempt_id"] is None
    assert _items(h, "unknown_student") == []


@pytest.mark.asyncio
async def test_r9_4_blank_picked(h: Harness) -> None:
    bank = _bank_test(h, 2)
    stems = [q.stem for s in bank.content.sections for g in s.groups for q in g.questions]
    h.fake.queues = {
        "ReadHeaderOut": [{"header_text": HEADER, "first_stems": stems[:3]}],
        "ReadAnswersCall": [EMPTY_ANSWERS, EMPTY_ANSWERS],
    }
    run_id, _ = await h.run(h.photos(2), existing=bank.id)
    assert h.runs_status(run_id) == "done"
    assert h.count("tests") == 1 and h.count("attempts") == 0 and h.count("test_pages") == 0
    assert _thread(h).kind == "blank" and _thread(h).test_id == bank.id
    cards = _cards(h)
    assert len(cards) == 1 and cards[0]["no_answers"] is True and cards[0]["test_id"] == bank.id


def _all_counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            " AND name NOT LIKE 'tests_fts_%'"
        )
    ]
    return {n: int(conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]) for n in names}


async def _r9_5_run(h: Harness, *, crash: bool) -> dict[str, int]:
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [answers_named(), EMPTY_ANSWERS],
    }
    if crash:
        h.save_mode = "crash_after"
    run_id, _ = await h.run(h.photos(2))
    if crash:
        assert h.runs_status(run_id) == "interrupted"
        assert h.count("attempts") == 1  # the save transaction had committed
        await h.manager.resume(run_id)
        await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
        assert len(h.steps(run_id, "save")) == 2
    assert h.runs_status(run_id) == "done"
    return _all_counts(h.conn)


@pytest.mark.asyncio
async def test_r9_5_crash_after_save_commit_then_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    counts = []
    for name, crash in (("plain", False), ("crash", True)):
        paths = DataPaths(tmp_path / name)
        db.open_database(paths.db).close()
        async with make_harness(paths, monkeypatch) as hh:
            counts.append(await _r9_5_run(hh, crash=crash))
    plain, crashed = counts
    assert crashed["steps"] == plain["steps"] + 1  # the retried save step
    del plain["steps"], crashed["steps"]
    assert crashed == plain
    assert plain["attempts"] == 1 and plain["messages"] == 1


DUP_CASES = [
    ({1: "a"}, "looks_like", (0.85, 0.95)),  # ≈ 0.92
    (
        {1: "Totally other stem about animals", 2: "Another different stem"},
        "possibly",
        (0.55, 0.65),
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("stems", "tier", "band"), DUP_CASES)
async def test_r9_6_possible_duplicate(
    h: Harness, stems: dict[int, str], tier: str, band: tuple[float, float]
) -> None:
    bank = _seed_bank(h, stems)
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [answers_named(), EMPTY_ANSWERS],
    }
    run_id, _ = await h.run(h.photos(2))
    dup = _items(h, "possible_duplicate")
    assert len(dup) == 1
    proposal = json.loads(dup[0]["proposal"])
    assert band[0] <= proposal["similarity"] <= band[1]
    assert proposal["tier"] == tier and proposal["best_test_id"] == bank.id
    assert proposal["question_alignment"]
    new_test = test_repo.find_by_source_run(h.conn, run_id)
    assert new_test is not None and dup[0]["test_id"] == new_test.id
    assert _cards(h)[0]["duplicate"] == {"test_id": bank.id, "tier": tier}


@pytest.mark.asyncio
async def test_r9_7_key_photo_rows(h: Harness) -> None:
    pages = h.photos(1)
    for color in ((10, 10, 10), (20, 20, 20)):
        fid = h.files.put(png(color), "png")
        pages.append(PageInput(file_id=fid, rotation=0, is_key=True, text_file_id=None))
    sure = json.dumps({"entries": [{"label": "1", "answer": "A"}]})
    unsure = json.dumps({"entries": [{"label": "2", "answer": "C"}]})
    h.fake.queues = {
        "ReadKeyOut": [
            ChatScript(tokens=list(sure)),
            ChatScript(tokens=list(unsure), logprob=-3.0),
        ],
        "TranscribeOut": [page_out(1, header=HEADER)],
        "ReadAnswersCall": [answers_named()],
    }
    run_id, _ = await h.run(pages)
    test = test_repo.find_by_source_run(h.conn, run_id)
    assert test is not None
    rows = keys.list_keys(h.conn, test.id)
    assert len(rows) == 2 and all(r.source == "from_key_photo" for r in rows)
    assert {r.accepted[0]: r.status for r in rows} == {"A": "from_key_photo", "C": "ai_unverified"}


@pytest.mark.asyncio
async def test_r9_9_validator_failed_saved(ht: Harness) -> None:
    h = ht
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), *[page_out(2, bad=True)] * 3],
        "ReadAnswersCall": [answers_named(), EMPTY_ANSWERS],
    }
    run_id, _ = await h.run(h.photos(2))
    assert len(h.steps(run_id, "retranscribe_tiles")) == 1
    vf = _items(h, "validator_failed")
    assert len(vf) == 1 and vf[0]["attempt_id"] is None
    assert json.loads(vf[0]["proposal"])["task"] == "retranscribe_tiles"


@pytest.mark.asyncio
async def test_stale_first_pass_pendings_dropped(ht: Harness) -> None:
    h = ht
    """A first-pass points_assumed on the bad page is gone once the tiles read it cleanly."""
    bad = page_out(2, bad=True)
    bad["sections"][0]["points_text"] = None
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), bad, page_out(2), page_out(2)],
        "ReadAnswersCall": [answers_named(), EMPTY_ANSWERS],
    }
    run_id, state = await h.run(h.photos(2))
    assert len(h.steps(run_id, "merge_and_normalize")) == 2
    s = _state(state)
    assert "validator_failed" not in _kinds(s)
    assert "points_assumed" not in _kinds(s)
    assert _items(h, "points_assumed") == []


@pytest.mark.asyncio
async def test_r9_10_text_page_saved(h: Harness) -> None:
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER)],
        "ReadAnswersCall": [answers_named()],
    }
    run_id, _ = await h.run(h.photos(1, texts={1: "TEXT LAYER UNIQUE-MARKER-7"}))
    assert h.runs_status(run_id) == "done" and h.count("attempts") == 1


@pytest.mark.asyncio
async def test_r9_11_supersede(h: Harness) -> None:
    queues = {
        "TranscribeOut": [page_out(1, header=HEADER)],
        "ReadAnswersCall": [answers_named()],
    }
    h.fake.queues = {k: list(v) for k, v in queues.items()}
    run_a, _ = await h.run(h.photos(1))
    a = attempts.find_by_source_run(h.conn, run_a)
    assert a is not None
    h.fake.queues = {k: list(v) for k, v in queues.items()}
    run_b, _ = await h.run(h.photos(1), supersedes=a.id)
    b = attempts.find_by_source_run(h.conn, run_b)
    assert b is not None and b.id != a.id
    a2 = attempts.get_attempt(h.conn, a.id)
    assert a2 is not None and a2.superseded_by == b.id
    current = attempts.current_attempt(h.conn, h.thread_id)
    assert current is not None and current.id == b.id


# --- the file-name metadata source (data-model v1.5 File.original_name) -----------------------


@pytest.mark.asyncio
async def test_test_number_from_the_uploaded_file_name(h: Harness) -> None:
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [EMPTY_ANSWERS, EMPTY_ANSWERS],
    }
    pages = h.photos(2)
    name = "Lop8-HKI-De1 (1).jpg"
    first = h.files.put(png((10, 20, 30)), "png", original_name=name)
    pages[0] = PageInput(file_id=first, rotation=0, is_key=False, text_file_id=None)
    run_id, _ = await h.run(pages)
    assert h.runs_status(run_id) == "done"
    test = test_repo.find_by_source_run(h.conn, run_id)
    assert test is not None
    assert test.meta.test_number == "1"


@pytest.mark.asyncio
async def test_no_file_name_gives_no_test_number(h: Harness) -> None:
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [EMPTY_ANSWERS, EMPTY_ANSWERS],
    }
    run_id, _ = await h.run(h.photos(2))
    test = test_repo.find_by_source_run(h.conn, run_id)
    assert test is not None
    assert test.meta.test_number is None


# --- uncertain_answer items (step 10, PRD S7) ----------------------------------------------------


def answers_skipping(*skip: int) -> Any:
    """Every requested question read as "A", except the indices in ``skip`` (not read → the
    answer is saved with ``reading_unsure``)."""

    def build(ids: list[str]) -> dict[str, Any]:
        out = answers_named()(ids)
        out["answers"] = {q: v for i, (q, v) in enumerate(out["answers"].items()) if i not in skip}
        return out

    return build


def _unsure(h: Harness) -> list[sqlite3.Row]:
    return h.conn.execute(
        "SELECT * FROM answers WHERE reading_unsure = 1 ORDER BY question_id"
    ).fetchall()


@pytest.mark.asyncio
async def test_uncertain_answer_items_one_per_unsure_answer(h: Harness) -> None:
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        # 22.5.6: each page is asked only for its own questions; q1 and q3 not read
        "ReadAnswersCall": [answers_skipping(0), answers_skipping(0)],
    }
    run_id, _ = await h.run(h.photos(2))
    assert h.runs_status(run_id) == "done"
    unsure = _unsure(h)
    assert len(unsure) == 2
    items = _items(h, "uncertain_answer")
    assert len(items) == 2
    att = h.conn.execute("SELECT * FROM attempts").fetchone()
    for ans, item in zip(unsure, sorted(items, key=lambda r: r["question_id"]), strict=True):
        assert item["owner"] == "extract" and item["status"] == "open"
        assert item["test_id"] == att["test_id"] and item["attempt_id"] == att["id"]
        assert item["question_id"] == ans["question_id"]
        assert item["dedupe_key"] == f"uncertain_answer:{att['id']}:{ans['question_id']}"
        assert json.loads(item["proposal"]) == {
            "value": ans["value"],
            "alt_value": ans["alt_value"],
            "alt_question_id": ans["alt_question_id"],
            "confidence": ans["confidence"],
            "low_trust": bool(ans["low_trust"]),
            "page_no": ans["page_no"],
            "printed_number": ans["printed_number"],
        }


@pytest.mark.asyncio
async def test_no_uncertain_answer_items_on_a_failed_page(h: Harness) -> None:
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [BAD, BAD, answers_skipping(0)],  # page 1's read fails twice
    }
    run_id, snap = await h.run(h.photos(2))
    assert h.runs_status(run_id) == "done" and snap["answers_failed"] == [1]
    unsure = _unsure(h)
    on_failed = [a for a in unsure if a["page_no"] == 1]
    assert on_failed, "the failed page's answers are saved as unsure"
    items = _items(h, "uncertain_answer")
    assert {r["question_id"] for r in items} == {
        a["question_id"] for a in unsure if a["page_no"] != 1
    }
    assert not {r["question_id"] for r in items} & {a["question_id"] for a in on_failed}
    assert len(_items(h, "validator_failed")) == 1


@pytest.mark.asyncio
async def test_uncertain_answer_items_survive_crash_and_resume(h: Harness) -> None:
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        # 22.5.6: each page is asked only for its own questions; q1 and q3 not read
        "ReadAnswersCall": [answers_skipping(0), answers_skipping(0)],
    }
    h.save_mode = "crash_after"
    run_id, _ = await h.run(h.photos(2))
    assert h.runs_status(run_id) == "interrupted"
    assert len(_items(h, "uncertain_answer")) == 2
    await h.manager.resume(run_id)
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    assert h.runs_status(run_id) == "done" and len(h.steps(run_id, "save")) == 2
    assert len(_items(h, "uncertain_answer")) == 2  # no duplicates


@pytest.mark.asyncio
async def test_extract_then_resolve_uncertain_answer_fix(h: Harness) -> None:
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        # 22.5.6: each page is asked only for its own questions
        "ReadAnswersCall": [answers_skipping(1), answers_named()],
    }
    await h.run(h.photos(2))
    (item,) = _items(h, "uncertain_answer")
    result = review_service.resolve(h.conn, item["id"], "fix", "C")
    assert result.item.status == "fixed" and result.followup_run_ids == []  # not graded
    ans = attempts.get_answer(h.conn, item["attempt_id"], item["question_id"])
    assert ans is not None and ans.teacher_override == "C" and ans.value_norm == "c"
    att = attempts.get_attempt(h.conn, item["attempt_id"])
    assert att is not None and att.version == 2


# --- R22.3.3.3: "same series as…" (data-model v1.14, decision D3) ------------------------------


@pytest.mark.asyncio
async def test_r22_3_3_3_series_from_test_sets_five_fields_at_save(h: Harness) -> None:
    queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [answers_all("B"), EMPTY_ANSWERS],
    }
    h.fake.queues = {k: list(v) for k, v in queues.items()}
    first, _ = await h.run(h.photos(2))
    series_id = test_repo.find_by_source_run(h.conn, first).id  # type: ignore[union-attr]
    series = {"occasion": "MidTerm", "term": 2, "school": "Synthetic School",
              "source": "Synthetic Book", "year": "2024-2025"}  # fmt: skip
    db.write_test_meta(h.conn, series_id, {**series, "grade": 6, "test_number": "9"}, True)

    h.fake.queues = {k: list(v) for k, v in queues.items()}
    inp = ExtractInput(
        pages=h.photos(2),
        existing_test_id=None,
        supersedes_attempt_id=None,
        series_from_test_id=series_id,
    )
    h.saved_states.clear()
    run = await h.manager.submit(h.thread_id, "extract", inp)
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    assert h.runs_status(run.id) == "done"
    new = test_repo.find_by_source_run(h.conn, run.id)
    assert new is not None and new.id != series_id
    meta = new.meta
    assert {f: getattr(meta, f) for f in series} == series
    assert meta.grade == 8  # from the run's header, not the series test
    assert meta.test_number != "9"
    assert set(series) <= set(meta.edited_fields)
    assert "grade" not in meta.edited_fields and "test_number" not in meta.edited_fields


# --- D5 (step 22.3.6): typed pages go to structure_text_page --------------------------------------


def _tasks(h: Harness, run_id: str) -> list[tuple[str, str]]:
    rows = h.conn.execute(
        "SELECT s.node, l.role FROM llm_calls l"
        " JOIN steps s ON s.id = l.step_id WHERE s.run_id = ? ORDER BY l.created_at",
        (run_id,),
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


@pytest.mark.asyncio
async def test_d5_typed_pdf_pages_are_structured_from_text(h: Harness) -> None:
    """R22.3.6.1: typed pages call structure_text_page (reasoning role), never transcribe_page
    or retranscribe_tiles; a photo in the same run still calls transcribe_page."""
    from etach.store.documents import ingest

    pages = [*ingest(h.files, _text_pdf(1), "typed.pdf"), *h.photos(1)]
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [answers_all(), answers_all()],
    }
    run_id, snap = await h.run(pages)
    assert snap["typed_pages"] == [1]
    # the typed page's call uses the reasoning role (structure_text_page), the photo's the vision
    roles = [r for n, r in _tasks(h, run_id) if n == "transcribe_page"]
    assert roles == ["reasoning", "vision"]
    assert h.steps(run_id, "retranscribe_tiles") == []
    assert h.runs_status(run_id) == "done"


# --- step 22.5.6: typed pages and per-page answer reading ---------------------------------------


def _page_of_ten(page_no: int, *, repeat: bool = False) -> dict[str, Any]:
    """Page N: section ROMAN[N-1] with MCQ questions 10N-9 .. 10N (``repeat``: the model loops
    and gives the questions twice, then the section again)."""
    out = page_out(page_no)
    questions = [
        {
            "printed_number": n,
            "answer_form": "choice",
            "stem": f"Page {page_no} question {n}: pick the odd word out {n}",
            "options": [{"label": x, "text": f"opt {x.lower()} {n}"} for x in "ABCD"],
            "cue": None,
        }
        for n in range(10 * page_no - 9, 10 * page_no + 1)
    ]
    section = out["sections"][0]
    section["groups"][0]["questions"] = questions + (questions if repeat else [])
    if repeat:
        out["sections"].append(json.loads(json.dumps(section)))
    return out


@pytest.mark.asyncio
async def test_r22_5_6_3_each_page_is_asked_only_its_questions(h: Harness) -> None:
    h.save_mode = "stub"
    h.fake.queues = {
        "TranscribeOut": [_page_of_ten(1) | {"header_text": HEADER}]
        + [_page_of_ten(n) for n in (2, 3, 4)],
        "ReadAnswersCall": [answers_all("B") for _ in range(4)],
    }
    _, snap = await h.run(h.photos(4))
    s = _state(snap)
    asked = [_answer_ids(body["format"]) for t, body in h.fake.seen if t == "ReadAnswersCall"]
    assert len(asked) == 4 and sum(len(ids) for ids in asked) == 40  # not 4 x 40 = 160
    pages = {q["id"]: q["page_no"] for sec in s["draft"]["content"]["sections"]
             for g in sec["groups"] for q in g["questions"]}  # fmt: skip
    for page_no, ids in enumerate(asked, start=1):
        assert {pages[i] for i in ids} == {page_no}
    # resolve_answers unchanged: one answer per question, all read
    assert len(s["answers"]) == 40 and all(a["value"] == "B" for a in s["answers"])


@pytest.mark.asyncio
async def test_r22_5_6_2_a_repeating_typed_page_is_cut_and_flagged(h: Harness) -> None:
    from etach.store.documents import ingest

    pages = ingest(h.files, _text_pdf(1), "typed.pdf")
    h.fake.queues = {"TranscribeOut": [_page_of_ten(1, repeat=True) | {"header_text": HEADER}]}
    _, snap = await h.run(pages)
    s = _state(snap)
    numbers = [q["printed_number"] for sec in s["draft"]["content"]["sections"]
               for g in sec["groups"] for q in g["questions"]]  # fmt: skip
    assert numbers == list(range(1, 11))  # cut where the output started to repeat
    assert snap["repeated_pages"] == {"1": 30}  # the repeated questions and section
    flagged = [
        p for p in snap["merge_pendings"]
        if p["kind"] == "validator_failed" and "repeated output" in str(p["proposal"])
    ]  # fmt: skip
    assert len(flagged) == 1 and flagged[0]["proposal"]["task"] == "structure_text_page"


def test_r22_5_6_2_the_typed_text_prompt_has_both_answer_start_examples() -> None:
    from importlib import resources

    text = (resources.files("etach.prompts") / "base" / "structure_text_page.md").read_text(
        encoding="utf-8"
    )
    assert '"=> It was such ……" → "It was such"' in text
    assert '"The film ……" (no arrow) → "The film"' in text


# --- step 22.5.7: the targeted re-read (R22.5.7.2) ----------------------------------------------


@pytest_asyncio.fixture
async def hr(data: DataPaths, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Harness]:
    """The harness with ``[extract] reread_pieces`` on and the tiles off."""
    async with make_harness(data, monkeypatch, reread=True) as harness:
        yield harness


def _page_sections(state: dict[str, Any], page_no: int) -> list[dict[str, Any]]:
    return list(state["page_results"][str(page_no)]["sections"])


def _first_reading(page_no: int, *, bad: bool = False) -> list[dict[str, Any]]:
    """The page's sections as the first pass stores them (``renumber.page_transcript``)."""
    out = TranscribeOut.model_validate(page_out(page_no, bad=bad))
    return list(renumber.page_transcript(page_no, out, "x").sections)


def _reread_bodies(h: Harness) -> list[dict[str, Any]]:
    return [body for title, body in h.fake.seen if title == "RereadPiecesOut"]


OPTS = [{"label": x, "text": f"opt {x.lower()}"} for x in "ABCD"]


def _piece(n: int, title: str, **fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "section_title": title,
        "printed_number": n,
        "answer_form": "choice",
        "stem": f"Re-read stem {n}",
        "options": OPTS,
        "cue": None,
        "answer_start": None,
    }
    return {**base, **fields}


@pytest.mark.asyncio
async def test_reread_asks_only_the_failing_piece_and_patches_only_it(hr: Harness) -> None:
    """R22.5.7.2: page 2's question 4 has one option. One ``reread_pieces`` call on the
    ``extraction_check`` role names only question 4; the patch replaces only its options (its
    stem was read, so it stays); a piece not asked for (question 3) is ignored; every other
    piece is byte-identical; no tile call is made."""
    h = hr
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2, bad=True)],
        "RereadPiecesOut": [{"pieces": [_piece(3, "II"), _piece(4, "II")]}],
        "ReadAnswersCall": [answers_all(), EMPTY_ANSWERS],
    }
    run_id, snap = await h.run(h.photos(2))
    s = _state(snap)
    [body] = _reread_bodies(h)
    text = json.dumps(body["messages"], ensure_ascii=False)
    assert "Question 4" in text and "Question 3" not in text
    assert len(body["messages"][-1]["images"]) == 1  # the page image
    assert sum(1 for title, _ in h.fake.seen if title == "TranscribeOut") == 2  # no tiles
    [step] = h.steps(run_id, "retranscribe_tiles")
    [row] = runs.list_llm_calls(h.conn, step.id)
    assert row.role == "extraction_check" and row.request.get("item") == "p2 re-read"

    before = _first_reading(2, bad=True)
    after = _page_sections(s, 2)
    q3_before, q4_before = before[0]["groups"][0]["questions"]
    q3_after, q4_after = after[0]["groups"][0]["questions"]
    assert json.dumps(q3_after) == json.dumps(q3_before)
    assert q4_after == {**q4_before, "options": OPTS}  # only the failing field
    strip = [{**sec, "groups": None} for sec in before]
    assert json.dumps([{**sec, "groups": None} for sec in after]) == json.dumps(strip)
    assert json.dumps(_page_sections(s, 1)) == json.dumps(_first_reading(1))
    assert "validator_failed" not in _kinds(s)
    assert h.runs_status(run_id) == "done"


@pytest.mark.asyncio
async def test_reread_failed_call_leaves_the_page(hr: Harness) -> None:
    """R22.5.7.2: a failed ``reread_pieces`` call (invalid JSON twice) leaves the page as it
    was; the page then goes to ``validator_failed`` (task ``reread_pieces``)."""
    h = hr
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2, bad=True)],
        "RereadPiecesOut": [BAD, BAD],
        "ReadAnswersCall": [answers_all(), EMPTY_ANSWERS],
    }
    run_id, snap = await h.run(h.photos(2))
    s = _state(snap)
    assert _reread_bodies(h)
    assert json.dumps(_page_sections(s, 2)) == json.dumps(_first_reading(2, bad=True))
    vf = [p for p in s["pending_reviews"] if p["kind"] == "validator_failed"]
    assert len(vf) == 1 and vf[0]["refs"] == {"page_no": 2}
    assert vf[0]["proposal"]["task"] == "reread_pieces"
    assert vf[0]["proposal"]["call_failure"] is None
    assert h.runs_status(run_id) == "done"


def _gap_page() -> dict[str, Any]:
    """Page 2 printed question 6 only: questions 3, 4 and 5 are missing (numbering fails)."""
    out = page_out(2)
    q = out["sections"][0]["groups"][0]["questions"][1]
    out["sections"][0]["groups"][0]["questions"] = [{**q, "printed_number": 6}]
    return out


@pytest.mark.asyncio
async def test_reread_inserts_missing_numbers(hr: Harness) -> None:
    """A numbering failure asks for the missing numbers; they are inserted in the named
    section in order; a piece under a section title the page does not have is dropped."""
    h = hr
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), _gap_page()],
        "RereadPiecesOut": [
            {"pieces": [_piece(5, "II"), _piece(3, "II"), _piece(4, "IX")]},
        ],
        "ReadAnswersCall": [answers_all(), EMPTY_ANSWERS],
    }
    _run_id, snap = await h.run(h.photos(2))
    s = _state(snap)
    [body] = _reread_bodies(h)
    assert "Questions 3, 4, 5: missing" in json.dumps(body["messages"], ensure_ascii=False)
    numbers = [q["printed_number"] for q in _page_sections(s, 2)[0]["groups"][0]["questions"]]
    assert numbers == [3, 5, 6]  # 4 was under an unknown section: dropped


@pytest.mark.asyncio
async def test_reread_patch_with_more_failures_is_dropped(hr: Harness) -> None:
    """The patch is kept only if the page's failures do not increase: question 4 inserted
    alone before 6 (and with no blank) turns one failure into three, so the page stays."""
    h = hr
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), _gap_page()],
        "RereadPiecesOut": [
            {"pieces": [_piece(4, "II", answer_form="word", options=None)]},
        ],
        "ReadAnswersCall": [answers_all(), EMPTY_ANSWERS],
    }
    _run_id, snap = await h.run(h.photos(2))
    s = _state(snap)
    numbers = [q["printed_number"] for q in _page_sections(s, 2)[0]["groups"][0]["questions"]]
    assert numbers == [6]


@pytest.mark.asyncio
async def test_reread_off_makes_no_call(h: Harness) -> None:
    """R22.5.7.2: ``[extract] reread_pieces`` off (the default): no re-read call, no step."""
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2, bad=True)],
        "RereadPiecesOut": [{"pieces": [_piece(4, "II")]}],
        "ReadAnswersCall": [answers_all(), EMPTY_ANSWERS],
    }
    run_id, _snap = await h.run(h.photos(2))
    assert _reread_bodies(h) == []
    assert h.steps(run_id, "retranscribe_tiles") == []


# --- step 22.5.7: the GLM-OCR two-step photo reader (D13) ----------------------------------------


@pytest_asyncio.fixture
async def hocr(data: DataPaths, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Harness]:
    """The harness with ``[extract] photo_reader = "ocr"`` (and ``photo_structure = "qwen"``)."""
    async with make_harness(data, monkeypatch, ocr=True) as harness:
        yield harness


@pytest.mark.asyncio
async def test_r22_5_7_4_ocr_reader_ocr_then_structure_text_page(hocr: Harness) -> None:
    h = hocr
    h.save_mode = "stub"
    h.fake.queues = {
        "PlainText": ["OCR-PAGE-ONE text", "OCR-PAGE-TWO text"],
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [answers_all("B"), answers_all("B")],
    }
    run_id, snap = await h.run(h.photos(2))
    s = _state(snap)
    titles = [t for t, _ in h.fake.seen]
    assert titles[:4] == ["PlainText", "TranscribeOut", "PlainText", "TranscribeOut"]
    ocr = [b for t, b in h.fake.seen if t == "PlainText"]
    structured = [b for t, b in h.fake.seen if t == "TranscribeOut"]
    answers = [b for t, b in h.fake.seen if t == "ReadAnswersCall"]
    # the OCR call: the photo, GLM-OCR's prompt only, no format, no system message
    for body in ocr:
        assert body["model"] == "glm-ocr" and "format" not in body
        assert [m["role"] for m in body["messages"]] == ["user"]
        assert body["messages"][0]["content"] == "Text Recognition:"
        assert body["messages"][0]["images"]
    # then structure_text_page on that text, with no image
    for body, marker in zip(structured, ("OCR-PAGE-ONE", "OCR-PAGE-TWO"), strict=True):
        assert marker in json.dumps(body, ensure_ascii=False)
        assert not any(m.get("images") for m in body["messages"])
    # the student answers are still read from the photo by the vision model
    assert answers and all(any(m.get("images") for m in b["messages"]) for b in answers)
    assert all(b["model"] == "qwen3.5:4b" for b in answers)
    roles = [r[0] for r in h.conn.execute("SELECT role FROM llm_calls ORDER BY rowid")]
    assert roles.count("ocr") == 2
    assert [st.item for st in h.steps(run_id, "transcribe_page")] == ["page 1", "page 2"]
    assert len(s["draft"]["content"]["sections"]) == 2


@pytest.mark.asyncio
async def test_r22_5_7_4_failed_ocr_call_fails_the_page(hocr: Harness) -> None:
    h = hocr
    h.fake.queues = {"PlainText": ["", ""], "ReadAnswersCall": [answers_all()]}
    _, snap = await h.run(h.photos(1))
    s = _state(snap)
    assert "TranscribeOut" not in [t for t, _ in h.fake.seen]  # nothing to structure
    assert _kinds(s).count("validator_failed") == 1


@pytest.mark.asyncio
async def test_r22_5_7_7_vision_reader_sends_no_ocr_call(h: Harness) -> None:
    """``photo_reader = "vision"``: one ``transcribe_page`` call with the photo (today's path)."""
    h.save_mode = "stub"
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER)],
        "ReadAnswersCall": [answers_all()],
    }
    await h.run(h.photos(1))
    titles = [t for t, _ in h.fake.seen]
    assert "PlainText" not in titles
    transcribe = [b for t, b in h.fake.seen if t == "TranscribeOut"]
    assert len(transcribe) == 1 and any(m.get("images") for m in transcribe[0]["messages"])


def test_r22_5_7_7_ocr_is_the_default_reader_and_role() -> None:
    default = parse_models_config({})
    assert default.extract.photo_reader == "ocr"
    assert default.role("ocr").model == "glm-ocr" and default.role("ocr").adapter == "chat"
    assert default.extract.ocr_prompt == "Text Recognition:"
    assert default.extract.retranscribe_tiles is False  # tiles stay off (G4)
    assert default.extract.reread_pieces is False
    tagged = parse_models_config({"roles": {"ocr": {"model": "glm-ocr:q8_0"}}})
    assert tagged.role("ocr").model == "glm-ocr:q8_0"


def test_r22_5_7_7_vision_reader_drops_the_ocr_role() -> None:
    """``photo_reader = "vision"`` keeps today's roles: no ``ocr`` to list, check or download,
    unless ``models.toml`` names one."""
    vision = parse_models_config({"extract": {"photo_reader": "vision"}})
    assert vision.extract.photo_reader == "vision" and "ocr" not in vision.roles
    assert set(vision.roles) == {"vision", "reasoning", "grading_check", "extraction_check"}
    kept = parse_models_config(
        {"extract": {"photo_reader": "vision"}, "roles": {"ocr": {"model": "glm-ocr"}}}
    )
    assert kept.role("ocr").model == "glm-ocr"


@pytest_asyncio.fixture
async def hdefault(data: DataPaths, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Harness]:
    """The harness on an empty data folder: no ``models.toml``, the built-in defaults."""
    assert not data.models_toml.exists()
    async with make_harness(data, monkeypatch, ocr=None) as harness:
        yield harness


@pytest.mark.asyncio
async def test_r22_5_7_7_empty_data_folder_reads_photos_with_ocr(hdefault: Harness) -> None:
    """An empty data folder: each test photo is an ``ocr_page`` call on ``glm-ocr``, then its
    text is structured by code (``photo_structure = "code"``, the default since step 22.6.6 (c),
    D16; no structuring call); the student answers stay on the vision role."""
    h = hdefault
    h.save_mode = "stub"
    h.fake.queues = {
        "PlainText": [
            f"{HEADER}\nI. Choose the best answer. (0.5 pt)\n1. A. cat B. hat C. map D. late\n",
            "2. A. sun B. run C. fun D. bun\n",
        ],
        "ReadAnswersCall": [answers_all("B"), answers_all("B")],
    }
    run_id, _snap = await h.run(h.photos(2))
    titles = [t for t, _ in h.fake.seen]
    assert titles.count("PlainText") == 2 and "TranscribeOut" not in titles
    assert all(b["model"] == "glm-ocr" for t, b in h.fake.seen if t == "PlainText")
    answers = [b for t, b in h.fake.seen if t == "ReadAnswersCall"]
    assert answers and all(b["model"] == "qwen3.5:4b" for b in answers)
    assert all(any(m.get("images") for m in b["messages"]) for b in answers)
    rows = [tuple(r) for r in h.conn.execute("SELECT role, model FROM llm_calls ORDER BY rowid")]
    assert rows.count(("ocr", "glm-ocr")) == 2
    assert ("vision", "qwen3.5:4b") in rows  # the student answers
    assert h.steps(run_id, "retranscribe_tiles") == []  # tiles stay off
