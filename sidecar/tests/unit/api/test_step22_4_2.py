"""Step 22.4.2 (data-model v1.18, llm-design v4.34, PRD v7.3): the school list (R22.4.2.2).
The seed is 22.2.3's synthetic one: T-1, T-2, T-3 (merged into T-1), T-4."""

from __future__ import annotations

import sqlite3
from importlib import resources

import pytest
from unit.api.test_step22_2_3 import client
from unit.api.test_step22_3_7 import _seed_names
from unit.api.test_step22_3_7 import conn as conn
from unit.api.test_step22_3_7 import ctx as ctx

from etach.api.deps import AppContext
from etach.domain import models as m
from etach.store import db


def _set_school(conn: sqlite3.Connection, test_id: str, school: str | None) -> None:
    """A school on a test as an AI write would store it (not added to the list)."""
    db.write_test_meta(conn, test_id, {"school": school}, by_teacher=False)


def _meta(conn: sqlite3.Connection, test_id: str) -> m.TestMetadata:
    row = conn.execute("SELECT meta FROM tests WHERE id = ?", (test_id,)).fetchone()
    return m.TestMetadata.model_validate_json(row[0])


def _student(conn: sqlite3.Connection, sid: str, school: str | None) -> None:
    conn.execute(
        "INSERT INTO students (id, full_name, name_search, school, created_at)"
        " VALUES (?, 'Học Sinh A', 'hoc sinh a', ?, '2026-01-01T00:00:00Z')",
        (sid, school),
    )
    conn.commit()


def test_migration_seeds_each_school_once(conn: sqlite3.Connection) -> None:
    _seed_names(conn)
    _set_school(conn, "T-1", " THCS Lê Lợi ")
    _set_school(conn, "T-2", "thcs lê lợi")  # a case variant (ASCII part): no second row
    _set_school(conn, "T-4", "THCS Nguyễn Du")
    _student(conn, "S-0101", "THCS Lê Lợi")
    _student(conn, "S-0102", "Trường B")
    _student(conn, "S-0103", "  ")
    conn.execute("DROP TABLE schools")
    sql = resources.files("etach.store.migrations").joinpath("0008_schools.sql").read_text("utf-8")
    conn.executescript(sql)
    rows = conn.execute("SELECT name, position FROM schools ORDER BY position").fetchall()
    assert [tuple(r) for r in rows] == [
        ("THCS Lê Lợi", 0),
        ("THCS Nguyễn Du", 1),
        ("Trường B", 2),
    ]


@pytest.mark.asyncio
async def test_add_move_and_typed_school_joins(ctx: AppContext, conn: sqlite3.Connection) -> None:
    _seed_names(conn)
    async with client(ctx) as c:
        assert (await c.get("/schools")).json() == []
        r = await c.post("/schools", json={"name": "  THCS  Lê Lợi "})
        assert r.status_code == 200, r.text
        first = r.json()
        assert first["name"] == "THCS Lê Lợi" and first["position"] == 0
        assert (await c.post("/schools", json={"name": "thcs LÊ LỢI"})).status_code == 409
        assert (await c.post("/schools", json={"name": "THCS Lê Lợi"})).status_code == 409
        assert (await c.post("/schools", json={"name": " "})).status_code == 422
        # a school typed on a test joins the list
        conn.execute("DELETE FROM review_items")  # the seed's review rows are synthetic
        conn.commit()
        r = await c.patch("/tests/T-2", json={"meta": {"school": "Trường B"}})
        assert r.status_code == 200, r.text
        # a school typed on a student joins the list
        r = await c.post("/students", json={"full_name": "Học Sinh B", "school": " Trường C "})
        assert r.status_code == 201 and r.json()["school"] == "Trường C"
        sid = r.json()["id"]
        r = await c.patch(f"/students/{sid}", json={"school": "Trường D"})
        assert r.status_code == 200 and r.json()["school"] == "Trường D"
        names = [s["name"] for s in (await c.get("/schools")).json()]
        assert names[0] == "THCS Lê Lợi"
        assert names[-3:] == ["Trường B", "Trường C", "Trường D"]
        # moved to the top
        last = (await c.get("/schools")).json()[-1]
        r = await c.patch(f"/schools/{last['id']}", json={"position": 0})
        assert r.status_code == 200 and r.json()["position"] == 0
        listed = (await c.get("/schools")).json()
        assert listed[0]["name"] == "Trường D"
        assert [s["position"] for s in listed] == list(range(len(listed)))
        assert (await c.patch("/schools/9999", json={"name": "x"})).status_code == 404


@pytest.mark.asyncio
async def test_rename_updates_tests_students_and_automatic_names(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    _seed_names(conn)
    async with client(ctx) as c:
        sid = (await c.post("/schools", json={"name": "THCS Lê Lợi"})).json()["id"]
        other = (await c.post("/schools", json={"name": "Trường B"})).json()["id"]
        for tid in ("T-1", "T-2", "T-3", "T-4"):
            _set_school(conn, tid, "THCS Lê Lợi")
        db.write_test_meta(conn, "T-4", {"display_name": "My own name"}, by_teacher=True)
        _student(conn, "S-0101", "THCS Lê Lợi")
        listed = {s["id"]: s for s in (await c.get("/schools")).json()}
        assert listed[sid]["test_count"] == 3 and listed[sid]["student_count"] == 1  # not T-3
        edited = {t: _meta(conn, t).edited_fields for t in ("T-1", "T-2", "T-3", "T-4")}
        before = dict(conn.execute("SELECT id, updated_at FROM tests").fetchall())
        assert (await c.patch(f"/schools/{sid}", json={"name": "trường b"})).status_code == 409
        r = await c.patch(f"/schools/{sid}", json={"name": "THCS Lê Quý Đôn"})
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "THCS Lê Quý Đôn" and r.json()["test_count"] == 3
        names = dict(conn.execute("SELECT id, display_name FROM tests").fetchall())
        for tid in ("T-1", "T-2", "T-3"):
            meta = _meta(conn, tid)
            assert meta.school == "THCS Lê Quý Đôn"
            assert "THCS Lê Quý Đôn" in names[tid] and names[tid] == meta.display_name()
            col = conn.execute("SELECT school FROM tests WHERE id = ?", (tid,)).fetchone()[0]
            assert col == "THCS Lê Quý Đôn"
        assert names["T-4"] == "My own name"
        assert _meta(conn, "T-4").school == "THCS Lê Quý Đôn"
        assert {t: _meta(conn, t).edited_fields for t in edited} == edited
        assert dict(conn.execute("SELECT id, updated_at FROM tests").fetchall()) == before
        school = conn.execute("SELECT school FROM students WHERE id = 'S-0101'").fetchone()[0]
        assert school == "THCS Lê Quý Đôn"
        found = {t["id"] for t in (await c.get("/tests", params={"q": "Quý Đôn"})).json()}
        assert found == {"T-1", "T-2"}  # T-3 is merged; T-4 keeps its typed name
        assert not (await c.get("/tests", params={"q": "Lê Lợi"})).json()
        assert other in {s["id"] for s in (await c.get("/schools")).json()}


@pytest.mark.asyncio
async def test_delete_refused_while_used(ctx: AppContext, conn: sqlite3.Connection) -> None:
    _seed_names(conn)
    async with client(ctx) as c:
        sid = (await c.post("/schools", json={"name": "THCS Lê Lợi"})).json()["id"]
        _set_school(conn, "T-2", "THCS Lê Lợi")
        r = await c.delete(f"/schools/{sid}")
        assert r.status_code == 409 and r.json()["detail"] == "1 test uses this school."
        _student(conn, "S-0101", "thcs lê lợi")
        _student(conn, "S-0102", "THCS Lê Lợi")
        r = await c.delete(f"/schools/{sid}")
        assert r.status_code == 409
        assert r.json()["detail"] == "1 test and 2 students use this school."
        # a merged test does not block the delete
        _set_school(conn, "T-2", None)
        _set_school(conn, "T-3", "THCS Lê Lợi")
        conn.execute("UPDATE students SET school = NULL")
        conn.commit()
        assert (await c.delete(f"/schools/{sid}")).status_code == 204
        assert (await c.get("/schools")).json() == []
        assert (await c.delete(f"/schools/{sid}")).status_code == 404


@pytest.mark.asyncio
async def test_seed_merges_vietnamese_case_variants(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    """data-model v1.18.1: "LÊ LỢI" and "Lê Lợi" seed as one school (Unicode case folding)."""
    _seed_names(conn)
    _set_school(conn, "T-1", "THCS Lê Lợi")
    _set_school(conn, "T-2", "THCS LÊ LỢI")  # NOCASE alone would keep both
    _student(conn, "S-0101", "thcs lê lợi")
    _student(conn, "S-0102", "Trường B")
    conn.execute("DROP TABLE schools")
    sql = resources.files("etach.store.migrations").joinpath("0008_schools.sql").read_text("utf-8")
    conn.executescript(sql)
    async with client(ctx) as c:
        listed = (await c.get("/schools")).json()
        assert [(s["name"], s["position"]) for s in listed] == [
            ("THCS Lê Lợi", 0),
            ("Trường B", 1),
        ]
        assert listed[0]["test_count"] == 2 and listed[0]["student_count"] == 1
        # a third spelling is not added again
        assert (await c.post("/schools", json={"name": "THCS LÊ Lợi"})).status_code == 409
    assert conn.execute("SELECT COUNT(*) FROM schools").fetchone()[0] == 2
