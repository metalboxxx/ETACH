"""Step 22.2.3 (data-model §5.7 v1.10, llm-design v4.26): deleting a thread or a test
(R22.2.3.1), the delete preview and the student routes (R22.2.3.2).

The seed is synthetic and touches every table that references a thread, an attempt or a test, so
the before/after counts per table show exactly what a delete removes.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from etach.api.app import create_app
from etach.api.deps import AppContext
from etach.domain.skills import skill_name
from etach.store import db
from etach.store import files as file_store
from etach.store.repos import deletes

T0 = "2026-01-01T00:00:00Z"

TABLES = (
    "students",
    "tests",
    "tests_fts",
    "test_pages",
    "answer_keys",
    "question_tags",
    "attempts",
    "attempt_pages",
    "answers",
    "grade_reports",
    "explanations",
    "threads",
    "messages",
    "runs",
    "steps",
    "llm_calls",
    "review_items",
    "files",
    "checkpoints",
    "writes",
)


@pytest.fixture
def ctx(make_ctx: Callable[..., AppContext]) -> Iterator[AppContext]:
    c = make_ctx()
    yield c
    c.close()


@pytest.fixture
def conn(ctx: AppContext) -> Iterator[sqlite3.Connection]:
    c = db.connect(ctx.paths.db)
    yield c
    c.close()


@asynccontextmanager
async def client(ctx: AppContext) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(ctx))
    headers = {"Authorization": f"Bearer {ctx.token}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=headers) as c:
        yield c


def _ins(conn: sqlite3.Connection, table: str, **cols: Any) -> None:
    names = ", ".join(cols)
    marks = ", ".join("?" for _ in cols)
    values = [json.dumps(v) if isinstance(v, dict | list) else v for v in cols.values()]
    conn.execute(f"INSERT INTO {table} ({names}) VALUES ({marks})", values)


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}


def _content() -> dict[str, Any]:
    return {"sections": []}


def _test(conn: sqlite3.Connection, tid: str, **kw: Any) -> None:
    meta = {"occasion": "FinalTerm", "grade": 8, "term": 1, "test_number": tid[-1]}
    _ins(
        conn,
        "tests",
        id=tid,
        display_name=f"Test {tid}",
        occasion="FinalTerm",
        grade=8,
        term=1,
        test_number=tid[-1],
        meta=meta,
        content=_content(),
        content_schema_version=1,
        fingerprint=f"fp-{tid}",
        points_possible=1.0,
        created_at=T0,
        updated_at=T0,
        **kw,
    )
    _ins(conn, "tests_fts", test_id=tid, display_name=f"Test {tid}", meta_text="")
    _ins(
        conn,
        "files",
        id=f"F-{tid}",
        path=f"files/{tid}.png",
        kind="upload",
        mime="image/png",
        created_at=T0,
    )
    _ins(conn, "test_pages", test_id=tid, page_no=1, file_id=f"F-{tid}")
    _ins(
        conn,
        "answer_keys",
        test_id=tid,
        question_id="q1",
        accepted=["a"],
        source="teacher",
        status="confirmed",
        updated_at=T0,
    )
    _ins(conn, "question_tags", test_id=tid, question_id="q1", tag="grammar.tense")
    _ins(
        conn,
        "review_items",
        id=f"RV-{tid}",
        kind="key_unsure",
        owner="test",
        test_id=tid,
        dedupe_key=f"dk-{tid}",
        proposal={},
        status="open",
        created_at=T0,
    )


def _thread(conn: sqlite3.Connection, hid: str, test_id: str | None, kind: str = "filled") -> str:
    _ins(conn, "threads", id=hid, title="New thread", test_id=test_id, kind=kind, created_at=T0)
    _ins(conn, "messages", id=f"M-{hid}", thread_id=hid, role="system", kind="card", created_at=T0)
    rid = f"R-{hid}"
    _ins(conn, "runs", id=rid, thread_id=hid, kind="extract", input={}, status="done")
    _ins(
        conn, "steps", id=f"ST-{hid}", run_id=rid, node="n", try_no=1, status="done", started_at=T0
    )
    _ins(conn, "llm_calls", id=f"C-{hid}", step_id=f"ST-{hid}", status="complete", created_at=T0)
    for table in ("checkpoints", "writes"):
        _ins(conn, table, thread_id=rid, checkpoint_ns="", checkpoint_id=f"cp-{hid}")
    return rid


def _attempt(conn: sqlite3.Connection, aid: str, hid: str, test_id: str, sid: str | None) -> None:
    _ins(
        conn,
        "attempts",
        id=aid,
        test_id=test_id,
        thread_id=hid,
        student_id=sid,
        source_run_id=f"src-{aid}",
        status="graded",
        created_at=T0,
    )
    _ins(
        conn,
        "files",
        id=f"F-{aid}",
        path=f"files/{aid}.png",
        kind="upload",
        mime="image/png",
        created_at=T0,
    )
    _ins(
        conn,
        "attempt_pages",
        attempt_id=aid,
        page_no=1,
        file_id=f"F-{aid}",
        source_file_id=f"F-{aid}",
        rotation=0,
    )
    _ins(conn, "answers", attempt_id=aid, question_id="q1", location="written_in_blank",
         printed_number=1, confidence=1.0)  # fmt: skip
    _ins(
        conn,
        "grade_reports",
        attempt_id=aid,
        run_id=f"R-{hid}",
        weak_points=[],
        careless_notes=[],
        summary_vi="",
        teacher_questions=[],
        uncertain_points=0,
        created_at=T0,
    )
    _ins(
        conn,
        "review_items",
        id=f"RV-{aid}",
        kind="answer_unsure",
        owner="attempt",
        attempt_id=aid,
        test_id=test_id,
        dedupe_key=f"dk-{aid}",
        proposal={},
        status="open",
        created_at=T0,
    )


def seed(conn: sqlite3.Connection) -> None:
    """T1 (main), T2 (other), T3 merged into T1, T4 a child of T1. Threads: H1 on T1 (student
    S-A), H2 on T1 and T2, H3 on T2 (student S-A), H4 a blank thread of T1, H5 on T3."""
    for table in ("checkpoints", "writes"):
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {table} (thread_id TEXT NOT NULL, "
            "checkpoint_ns TEXT NOT NULL DEFAULT '', checkpoint_id TEXT NOT NULL)"
        )
    with db.transaction(conn):
        _ins(conn, "students", id="S-A", full_name="Học Sinh A", name_search="hoc sinh a",
             class_name="8A", created_at=T0)  # fmt: skip
        _ins(conn, "students", id="S-B", full_name="Học Sinh B", name_search="hoc sinh b",
             created_at=T0)  # fmt: skip
        _test(conn, "T-1")
        _test(conn, "T-2")
        _test(conn, "T-3", merged_into="T-1")
        _test(conn, "T-4", parent_test_id="T-1")
        _thread(conn, "H-1", "T-1")
        _attempt(conn, "A-1", "H-1", "T-1", "S-A")
        _thread(conn, "H-2", "T-2")
        _attempt(conn, "A-2a", "H-2", "T-1", None)
        _attempt(conn, "A-2b", "H-2", "T-2", None)
        conn.execute("UPDATE attempts SET created_at = '2026-01-02T00:00:00Z' WHERE id = 'A-2b'")
        _thread(conn, "H-3", "T-2")
        _attempt(conn, "A-3", "H-3", "T-2", "S-A")
        _thread(conn, "H-4", "T-1", kind="blank")
        _thread(conn, "H-5", "T-3")
        _attempt(conn, "A-5", "H-5", "T-3", "S-B")
        # A kept explanation (test T-2) made by a call in H-1, and a T-2 Review item whose
        # follow-up ran in H-1: both stay with their pointer cleared.
        _ins(conn, "explanations", test_id="T-2", question_id="q1", wrong_answer_norm="b",
             error_type="gap", text_vi="…", status="ai", llm_call_id="C-H-1")  # fmt: skip
        conn.execute("UPDATE review_items SET followup_run_id = 'R-H-1' WHERE id = 'RV-T-2'")


# --- R22.2.3.1: thread delete ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_thread_removes_exactly_its_rows(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    seed(conn)
    before = _counts(conn)
    other = conn.execute("SELECT * FROM attempts WHERE thread_id != 'H-1' ORDER BY id").fetchall()
    async with client(ctx) as c:
        r = await c.delete("/threads/H-1")
        assert r.status_code == 204, r.text
        assert (await c.get("/threads/H-1")).status_code == 404
        listed = [t["thread"]["id"] for t in (await c.get("/threads")).json()]
    after = _counts(conn)
    diff = {t: before[t] - after[t] for t in TABLES if before[t] != after[t]}
    assert diff == {
        "threads": 1,
        "messages": 1,
        "runs": 1,
        "steps": 1,
        "llm_calls": 1,
        "checkpoints": 1,
        "writes": 1,
        "attempts": 1,
        "attempt_pages": 1,
        "answers": 1,
        "grade_reports": 1,
        "review_items": 1,
    }
    assert "H-1" not in listed and {"H-2", "H-3", "H-4", "H-5"} <= set(listed)
    assert conn.execute("SELECT 1 FROM tests WHERE id = 'T-1'").fetchone()
    assert conn.execute("SELECT 1 FROM answer_keys WHERE test_id = 'T-1'").fetchone()
    assert conn.execute("SELECT 1 FROM students WHERE id = 'S-A'").fetchone()
    assert conn.execute("SELECT llm_call_id FROM explanations").fetchone()[0] is None
    assert (
        conn.execute("SELECT followup_run_id FROM review_items WHERE id = 'RV-T-2'").fetchone()[0]
        is None
    )
    assert conn.execute("SELECT * FROM attempts ORDER BY id").fetchall() == other
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.asyncio
async def test_delete_thread_409_while_a_run_is_active_and_404(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    seed(conn)
    async with client(ctx) as c:
        for status in ("queued", "running", "stopping", "stopped", "interrupted"):
            conn.execute("UPDATE runs SET status = ? WHERE id = 'R-H-1'", (status,))
            conn.commit()
            r = await c.delete("/threads/H-1")
            assert r.status_code == 409, status
            assert "stop or discard" in r.json()["detail"]
        assert conn.execute("SELECT 1 FROM threads WHERE id = 'H-1'").fetchone()
        assert (await c.delete("/threads/nope")).status_code == 404
        assert (await c.delete("/tests/nope")).status_code == 404
        assert (await c.get("/tests/nope/delete-preview")).status_code == 404


def test_delete_thread_is_atomic(conn: sqlite3.Connection) -> None:
    seed(conn)
    before = _counts(conn)
    conn.execute(
        "CREATE TEMP TRIGGER boom BEFORE DELETE ON threads BEGIN SELECT RAISE(ABORT, 'boom'); END"
    )
    with pytest.raises(sqlite3.DatabaseError, match="boom"):
        deletes.delete_thread(conn, "H-1")
    assert _counts(conn) == before


# --- R22.2.3.1: test delete --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_test_removes_threads_merged_tests_and_keeps_mixed_thread(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    seed(conn)
    before = _counts(conn)
    async with client(ctx) as c:
        preview = (await c.get("/tests/T-1/delete-preview")).json()
        assert sorted(t["id"] for t in preview["threads"]) == ["H-1", "H-4", "H-5"]
        assert [t["id"] for t in preview["kept_threads"]] == ["H-2"]
        assert preview["merged_test_ids"] == ["T-3"]
        assert preview["attempt_count"] == 3
        r = await c.delete("/tests/T-1")
        assert r.status_code == 204, r.text
        assert (await c.get("/tests/T-1")).status_code == 404
        listed = {t["id"] for t in (await c.get("/tests")).json()}
        threads_ = {t["thread"]["id"]: t for t in (await c.get("/threads")).json()}
    assert listed == {"T-2", "T-4"}
    assert set(threads_) == {"H-2", "H-3"}
    # The mixed thread keeps its T-2 attempt and now points at T-2.
    assert [r[0] for r in conn.execute("SELECT id FROM attempts ORDER BY id")] == ["A-2b", "A-3"]
    assert conn.execute("SELECT test_id FROM threads WHERE id = 'H-2'").fetchone()[0] == "T-2"
    assert conn.execute("SELECT parent_test_id FROM tests WHERE id = 'T-4'").fetchone()[0] is None
    after = _counts(conn)
    diff = {t: before[t] - after[t] for t in TABLES if before[t] != after[t]}
    assert diff == {
        "tests": 2,  # T-1, T-3
        "tests_fts": 2,
        "test_pages": 2,
        "answer_keys": 2,
        "question_tags": 2,
        "threads": 3,  # H-1, H-4, H-5
        "messages": 3,
        "runs": 3,
        "steps": 3,
        "llm_calls": 3,
        "checkpoints": 3,
        "writes": 3,
        "attempts": 3,  # A-1, A-5, and A-2a alone
        "attempt_pages": 3,
        "answers": 3,
        "grade_reports": 3,
        "review_items": 5,  # RV-T-1, RV-T-3, RV-A-1, RV-A-5, RV-A-2a
    }
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    # A later sweep removes the files nobody references any more.
    swept = file_store.sweep(conn, ctx.paths, now=datetime.now(UTC) + timedelta(days=1))
    gone = sorted(f.id for f in swept.deleted)
    assert gone == ["F-A-1", "F-A-2a", "F-A-5", "F-T-1", "F-T-3"]


@pytest.mark.asyncio
async def test_delete_test_409_and_atomic(ctx: AppContext, conn: sqlite3.Connection) -> None:
    seed(conn)
    async with client(ctx) as c:
        conn.execute("UPDATE runs SET status = 'stopped' WHERE id = 'R-H-5'")  # merged test's
        conn.commit()
        assert (await c.delete("/tests/T-1")).status_code == 409
        conn.execute("UPDATE runs SET status = 'done' WHERE id = 'R-H-5'")
        _ins(conn, "threads", id="H-9", title="x", kind="pending", created_at=T0)
        _ins(conn, "runs", id="R-9", thread_id="H-9", kind="grade", input={"test_id": "T-1"},
             status="running")  # fmt: skip
        conn.commit()
        assert (await c.delete("/tests/T-1")).status_code == 409
        conn.execute("UPDATE runs SET status = 'failed' WHERE id = 'R-9'")
        conn.commit()
    before = _counts(conn)
    conn.execute(
        "CREATE TEMP TRIGGER boom BEFORE DELETE ON tests BEGIN SELECT RAISE(ABORT, 'boom'); END"
    )
    with pytest.raises(sqlite3.DatabaseError, match="boom"):
        deletes.delete_test(conn, deletes.plan_test_delete(conn, "T-1"))
    assert _counts(conn) == before


# --- R22.2.3.2: students -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_students_list_counts_and_detail(ctx: AppContext, conn: sqlite3.Connection) -> None:
    seed(conn)
    async with client(ctx) as c:
        listed = {s["id"]: s for s in (await c.get("/students")).json()}
        assert listed["S-A"]["class_name"] == "8A"
        assert listed["S-A"]["thread_count"] == 2
        assert listed["S-B"]["thread_count"] == 1
        found = (await c.get("/students", params={"q": "hoc sinh a"})).json()
        assert [s["id"] for s in found] == ["S-A"] and found[0]["thread_count"] == 2
        detail = (await c.get("/students/S-A")).json()
        assert detail["student"]["full_name"] == "Học Sinh A"
        assert sorted(t["id"] for t in detail["threads"]) == ["H-1", "H-3"]
        assert all(t["shown_title"] for t in detail["threads"])
        assert (await c.get("/students/S-none")).status_code == 404
        await c.delete("/threads/H-1")
        assert [t["id"] for t in (await c.get("/students/S-A")).json()["threads"]] == ["H-3"]


@pytest.mark.asyncio
async def test_r22_5_5_student_detail_has_skills(ctx: AppContext, conn: sqlite3.Connection) -> None:
    """Step 22.5.5 (D11b): the student's skills with label, level and per-paper results."""
    seed(conn)
    with db.transaction(conn):
        for tid in ("T-1", "T-2"):
            _ins(conn, "question_tags", test_id=tid, question_id="q1", tag="VOC-TOPIC")
        conn.execute("UPDATE answers SET verdict = 'correct'")
        conn.execute("UPDATE answers SET verdict = 'incorrect' WHERE attempt_id = 'A-1'")
    async with client(ctx) as c:
        skills = (await c.get("/students/S-A")).json()["skills"]
    (s,) = [s for s in skills if s["skill_tag"] == "VOC-TOPIC"]
    assert (s["skill_tag"], s["skill_name"], s["label"], s["level"]) == (
        "VOC-TOPIC",
        skill_name("VOC-TOPIC"),
        "not_enough_evidence",
        "A1",
    )
    assert (s["weak"], s["held_back"]) == (False, False)
    assert [p["share"] for p in s["papers"]] == [0.0, 1.0]
    assert all(p["taken_on"] and p["counted"] == 1 for p in s["papers"])
