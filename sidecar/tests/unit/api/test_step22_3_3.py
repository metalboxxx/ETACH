"""Step 22.3.3 (data-model §5.7 v1.14, llm-design v4.30, decisions D1, D3): deleting a student
(R22.3.3.1) and copying series details (R22.3.3.2). The seed is 22.2.3's synthetic one, plus a
thread shared by two students."""

from __future__ import annotations

import sqlite3

import pytest
from unit.api.test_step22_2_3 import TABLES, _attempt, _counts, _thread, client, seed
from unit.api.test_step22_2_3 import conn as conn
from unit.api.test_step22_2_3 import ctx as ctx

from etach.api.deps import AppContext
from etach.domain.models import TestMetadata as Meta
from etach.store import db
from etach.store.repos import deletes


def seed_shared(conn: sqlite3.Connection) -> None:
    """22.2.3's seed + H-6 on T-2 with one paper of S-A (A-6a) and one of S-B (A-6b)."""
    seed(conn)
    with db.transaction(conn):
        _thread(conn, "H-6", "T-2")
        _attempt(conn, "A-6a", "H-6", "T-2", "S-A")
        _attempt(conn, "A-6b", "H-6", "T-2", "S-B")
        conn.execute("UPDATE attempts SET created_at = '2026-01-03T00:00:00Z' WHERE id = 'A-6a'")


# --- R22.3.3.1: delete a student ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_student_removes_exactly_their_threads(
    ctx: AppContext,
    conn: sqlite3.Connection,
) -> None:
    seed_shared(conn)
    before = _counts(conn)
    kept_attempts = conn.execute(
        "SELECT * FROM attempts WHERE id NOT IN ('A-1', 'A-3', 'A-6a') ORDER BY id"
    ).fetchall()
    async with client(ctx) as c:
        preview = (await c.get("/students/S-A/delete-preview")).json()
        assert preview["full_name"] == "Học Sinh A"
        assert sorted(t["id"] for t in preview["threads"]) == ["H-1", "H-3"]
        assert [t["id"] for t in preview["kept_threads"]] == ["H-6"]
        assert preview["attempt_count"] == 3
        r = await c.delete("/students/S-A")
        assert r.status_code == 204, r.text
        assert (await c.get("/students/S-A")).status_code == 404
        listed = {t["thread"]["id"] for t in (await c.get("/threads")).json()}
        tests_ = {t["id"] for t in (await c.get("/tests")).json()}
        students_ = {s["id"] for s in (await c.get("/students")).json()}
    assert listed == {"H-2", "H-4", "H-5", "H-6"}
    assert tests_ == {"T-1", "T-2", "T-4"}
    assert students_ == {"S-B"}
    assert conn.execute("SELECT * FROM attempts ORDER BY id").fetchall() == kept_attempts
    assert conn.execute("SELECT test_id FROM threads WHERE id = 'H-6'").fetchone()[0] == "T-2"
    after = _counts(conn)
    diff = {t: before[t] - after[t] for t in TABLES if before[t] != after[t]}
    assert diff == {
        "students": 1,
        "threads": 2,  # H-1, H-3
        "messages": 2,
        "runs": 2,
        "steps": 2,
        "llm_calls": 2,
        "checkpoints": 2,
        "writes": 2,
        "attempts": 3,  # A-1, A-3, and A-6a alone
        "attempt_pages": 3,
        "answers": 3,
        "grade_reports": 3,
        "review_items": 3,
    }
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.asyncio
async def test_delete_student_409_404_and_atomic(
    ctx: AppContext,
    conn: sqlite3.Connection,
) -> None:
    seed_shared(conn)
    async with client(ctx) as c:
        for status in ("queued", "running", "stopping", "stopped", "interrupted"):
            conn.execute("UPDATE runs SET status = ? WHERE id = 'R-H-6'", (status,))
            conn.commit()
            r = await c.delete("/students/S-A")
            assert r.status_code == 409, status
            assert "stop or discard" in r.json()["detail"]
        conn.execute("UPDATE runs SET status = 'done' WHERE id = 'R-H-6'")
        conn.commit()
        assert conn.execute("SELECT 1 FROM students WHERE id = 'S-A'").fetchone()
        assert (await c.delete("/students/nope")).status_code == 404
        assert (await c.get("/students/nope/delete-preview")).status_code == 404
    before = _counts(conn)
    conn.execute(
        "CREATE TEMP TRIGGER boom BEFORE DELETE ON students BEGIN SELECT RAISE(ABORT, 'boom'); END"
    )
    with pytest.raises(sqlite3.DatabaseError, match="boom"):
        deletes.delete_student(conn, deletes.plan_student_delete(conn, "S-A"))
    assert _counts(conn) == before


@pytest.mark.asyncio
async def test_delete_student_without_threads(
    ctx: AppContext,
    conn: sqlite3.Connection,
) -> None:
    seed(conn)
    conn.execute("UPDATE attempts SET student_id = NULL WHERE student_id = 'S-B'")
    conn.commit()
    async with client(ctx) as c:
        preview = (await c.get("/students/S-B/delete-preview")).json()
        assert preview["threads"] == [] and preview["attempt_count"] == 0
        assert (await c.delete("/students/S-B")).status_code == 204
    assert conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 1


# --- R22.3.3.2: copy series details ------------------------------------------------------------

SERIES = {
    "occasion": "MidTerm",
    "term": 2,
    "school": "Synthetic School",
    "source": "Synthetic Book",
    "year": "2024-2025",
}


def _meta(conn: sqlite3.Connection, tid: str) -> Meta:
    return Meta.model_validate_json(
        conn.execute("SELECT meta FROM tests WHERE id = ?", (tid,)).fetchone()[0]
    )


@pytest.mark.asyncio
async def test_copy_details_copies_five_fields_only(
    ctx: AppContext,
    conn: sqlite3.Connection,
) -> None:
    seed(conn)
    conn.execute("DELETE FROM review_items")  # the seed's items are only row-count stand-ins
    conn.commit()
    db.write_test_meta(conn, "T-2", {**SERIES, "grade": 6, "test_number": "9"}, by_teacher=True)
    async with client(ctx) as c:
        r = await c.post("/tests/T-1/copy-details", json={"from_test_id": "T-2"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert (
            await c.post("/tests/T-1/copy-details", json={"from_test_id": "T-1"})
        ).status_code == 422
        assert (
            await c.post("/tests/T-1/copy-details", json={"from_test_id": "nope"})
        ).status_code == 404
        assert (
            await c.post("/tests/nope/copy-details", json={"from_test_id": "T-2"})
        ).status_code == 404
    meta = _meta(conn, "T-1")
    assert {f: getattr(meta, f) for f in SERIES} == SERIES
    assert meta.grade == 8 and meta.test_number == "1"
    assert set(SERIES) <= set(meta.edited_fields)
    assert "grade" not in meta.edited_fields and "test_number" not in meta.edited_fields
    # the automatic name follows, in the column and in the response
    name = conn.execute("SELECT display_name FROM tests WHERE id = 'T-1'").fetchone()[0]
    assert name == meta.display_name() and "Synthetic School" in name
    assert body["meta"]["school"] == "Synthetic School"
    # a later extraction (not a teacher write) does not overwrite them
    db.write_test_meta(conn, "T-1", {"school": "AI School", "year": "1999", "grade": 7}, False)
    meta = _meta(conn, "T-1")
    assert meta.school == "Synthetic School" and meta.year == "2024-2025" and meta.grade == 7


@pytest.mark.asyncio
async def test_copy_details_blank_source_field_keeps_target(
    ctx: AppContext,
    conn: sqlite3.Connection,
) -> None:
    seed(conn)
    conn.execute("DELETE FROM review_items")
    conn.commit()
    db.write_test_meta(conn, "T-1", {"school": "Target School", "year": "2023"}, by_teacher=True)
    db.write_test_meta(
        conn, "T-2", {"occasion": "MidTerm", "school": None, "year": "2024-2025"}, by_teacher=True
    )
    async with client(ctx) as c:
        r = await c.post("/tests/T-1/copy-details", json={"from_test_id": "T-2"})
        assert r.status_code == 200, r.text
    meta = _meta(conn, "T-1")
    assert meta.school == "Target School"  # blank in the source: the target's value stays
    assert meta.year == "2024-2025" and meta.occasion == "MidTerm"
