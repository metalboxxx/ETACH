"""Step 22.5.2 (data-model v1.21, llm-design v4.41, decisions D5, D7, D8): the series list
(R22.5.2.1), ``points_each`` (R22.5.2.3), the Extract again ``mode`` and the other-threads count
(R22.5.2.6). The seed is 22.2.3's synthetic one: T-1, T-2, T-3 (merged into T-1), T-4; threads
H-1, H-2 on T-1 / T-2, H-3 on T-2, H-4 a blank thread of T-1, H-5 on T-3."""

from __future__ import annotations

import sqlite3
from importlib import resources
from typing import Any

import pytest
from unit.api.test_step22_2_3 import client
from unit.api.test_step22_3_7 import _seed_names
from unit.api.test_step22_3_7 import conn as conn
from unit.api.test_step22_3_7 import ctx as ctx

from etach.api.deps import AppContext
from etach.api.routes import threads as thread_routes
from etach.domain import models as m
from etach.domain.models import ExtractInput, PageInput
from etach.store import db
from etach.store.repos import runs, threads


def _set_source(conn: sqlite3.Connection, test_id: str, source: str | None) -> None:
    """A series on a test as an AI write would store it (not added to the list)."""
    db.write_test_meta(conn, test_id, {"source": source}, by_teacher=False)


def _meta(conn: sqlite3.Connection, test_id: str) -> m.TestMetadata:
    row = conn.execute("SELECT meta FROM tests WHERE id = ?", (test_id,)).fetchone()
    return m.TestMetadata.model_validate_json(row[0])


# --- R22.5.2.1: the series list ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_seeds_each_series_once(ctx: AppContext, conn: sqlite3.Connection) -> None:
    _seed_names(conn)
    _set_source(conn, "T-1", " Đề dự đoán tuyển sinh vào 10 ")
    _set_source(conn, "T-2", "đề dự đoán tuyển sinh vào 10")  # a case variant (Vietnamese Đ)
    _set_source(conn, "T-4", "  ")
    conn.execute("UPDATE tests SET created_at = '2025-01-01T00:00:00Z' WHERE id = 'T-1'")
    conn.execute("DROP TABLE series")
    conn.execute("DROP TABLE test_text_pending")
    sql = resources.files("etach.store.migrations").joinpath("0011_series.sql").read_text("utf-8")
    conn.executescript(sql)
    async with client(ctx) as c:
        listed = (await c.get("/series")).json()
    assert [(s["name"], s["position"], s["test_count"]) for s in listed] == [
        ("Đề dự đoán tuyển sinh vào 10", 0, 2)  # T-1 is the oldest: its spelling is kept
    ]


@pytest.mark.asyncio
async def test_series_routes_add_rename_move_delete(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    _seed_names(conn)
    async with client(ctx) as c:
        assert (await c.get("/series")).json() == []
        r = await c.post("/series", json={"name": "  Đề  dự đoán "})
        assert r.status_code == 200, r.text
        first = r.json()
        assert first == {"id": first["id"], "name": "Đề dự đoán", "position": 0, "test_count": 0}
        assert (await c.post("/series", json={"name": "đề DỰ ĐOÁN"})).status_code == 409
        assert (await c.post("/series", json={"name": " "})).status_code == 422
        second = (await c.post("/series", json={"name": "Global Success"})).json()
        # a series typed on a test joins the list
        conn.execute("DELETE FROM review_items")  # the seed's review rows are synthetic
        conn.commit()
        r = await c.patch("/tests/T-2", json={"meta": {"source": "Bộ đề Hà Nội"}})
        assert r.status_code == 200, r.text
        names = [s["name"] for s in (await c.get("/series")).json()]
        assert names == ["Đề dự đoán", "Global Success", "Bộ đề Hà Nội"]
        # moved to the top
        r = await c.patch(f"/series/{second['id']}", json={"position": 0})
        assert r.status_code == 200 and r.json()["position"] == 0
        listed = (await c.get("/series")).json()
        assert [s["name"] for s in listed] == ["Global Success", "Đề dự đoán", "Bộ đề Hà Nội"]
        assert (await c.patch("/series/9999", json={"name": "x"})).status_code == 404
        assert (await c.delete("/series/9999")).status_code == 404

        # a rename updates the tests that use it and their automatic names
        for tid in ("T-1", "T-3", "T-4"):
            _set_source(conn, tid, "đề dự đoán")
        db.write_test_meta(conn, "T-4", {"display_name": "My own name"}, by_teacher=True)
        edited = {t: _meta(conn, t).edited_fields for t in ("T-1", "T-3", "T-4")}
        before = dict(conn.execute("SELECT id, updated_at FROM tests").fetchall())
        assert next(s for s in listed if s["id"] == first["id"])["test_count"] == 0
        listed = (await c.get("/series")).json()
        assert next(s for s in listed if s["id"] == first["id"])["test_count"] == 2  # not T-3
        r = await c.patch(f"/series/{first['id']}", json={"name": "global success"})
        assert r.status_code == 409
        r = await c.patch(f"/series/{first['id']}", json={"name": "Đề thi thử"})
        assert r.status_code == 200 and r.json()["name"] == "Đề thi thử"
        names = dict(conn.execute("SELECT id, display_name FROM tests").fetchall())
        for tid in ("T-1", "T-3", "T-4"):
            assert _meta(conn, tid).source == "Đề thi thử"
        meta1 = _meta(conn, "T-1")
        assert names["T-1"] == meta1.display_name()
        assert (meta1.school is not None) or "Đề thi thử" in names["T-1"]
        assert names["T-4"] == "My own name"
        assert {t: _meta(conn, t).edited_fields for t in edited} == edited
        assert dict(conn.execute("SELECT id, updated_at FROM tests").fetchall()) == before

        # delete is refused while a (not merged) test uses it
        r = await c.delete(f"/series/{first['id']}")
        assert r.status_code == 409 and r.json()["detail"] == "2 tests use this series."
        _set_source(conn, "T-1", None)
        r = await c.delete(f"/series/{first['id']}")
        assert r.status_code == 409 and r.json()["detail"] == "1 test uses this series."
        _set_source(conn, "T-4", None)  # T-3 is merged: it does not block the delete
        assert (await c.delete(f"/series/{first['id']}")).status_code == 204
        listed = (await c.get("/series")).json()
        assert [s["position"] for s in listed] == list(range(len(listed)))
        assert first["id"] not in {s["id"] for s in listed}


# --- R22.5.2.3: points_each ----------------------------------------------------------------------


def _questions(n: int) -> list[dict[str, Any]]:
    return [
        {
            "id": f"q-{i}",
            "number": i,
            "printed_number": i,
            "page_no": 1,
            "answer_form": "word",
            "stem": f"Stem {i} ____",
            "options": None,
            "cue": None,
            "points": 0.0,
        }
        for i in range(1, n + 1)
    ]


@pytest.mark.parametrize(("n", "each"), [(40, 0.25), (50, 0.2), (45, 10 / 45)])
@pytest.mark.asyncio
async def test_get_test_carries_points_each(
    ctx: AppContext, conn: sqlite3.Connection, n: int, each: float
) -> None:
    _seed_names(conn)
    section = {
        "id": "s-1",
        "number": 1,
        "printed_title": "I",
        "title": "I",
        "instructions": "",
        "points": 0.0,
        "points_source": "equal",
        "skill": "grammar",
        "groups": [{"id": "g-1", "stimulus": None, "pictures": [], "questions": _questions(n)}],
    }
    writing = section | {
        "id": "s-2",
        "number": 2,
        "printed_title": "II",
        "title": "II",
        "graded": False,
        "skill": "writing",
        "groups": [{"id": "g-2", "stimulus": None, "pictures": [], "questions": []}],
    }
    conn.execute("DELETE FROM review_items")
    conn.commit()
    async with client(ctx) as c:
        r = await c.patch("/tests/T-2", json={"content": {"sections": [section, writing]}})
        assert r.status_code == 200, r.text
        got = (await c.get("/tests/T-2")).json()
    assert got["points_each"] == pytest.approx(each)
    assert "points" not in got["content_text"]
    assert "# II  [not graded]" in got["content_text"]


# --- R22.5.2.6: the extract-again mode and the other threads ------------------------------------


def _pages(*ids: str) -> list[PageInput]:
    return [PageInput(file_id=i, rotation=0, is_key=False, text_file_id=None) for i in ids]


def _done_extract(conn: sqlite3.Connection, thread_id: str, **kw: Any) -> None:
    inp = ExtractInput(pages=_pages("F-1"), existing_test_id=None, supersedes_attempt_id=None, **kw)
    run = runs.create_run(conn, thread_id, "extract", inp)
    runs.set_run_status(conn, run.id, "done")
    conn.commit()


@pytest.mark.asyncio
async def test_other_thread_count_and_extract_again_mode(
    ctx: AppContext, conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_names(conn)
    placeholder = ExtractInput(
        pages=_pages("F-0"), existing_test_id=None, supersedes_attempt_id=None
    )
    conn.execute(
        "UPDATE runs SET input = ?, status = 'discarded' WHERE input = '{}'",
        (placeholder.model_dump_json(),),
    )
    conn.commit()
    async with client(ctx) as c:
        # T-1: H-1 and H-4 (blank); H-2's thread test is T-2 (its old attempt was on T-1)
        assert (await c.get("/threads/H-1")).json()["other_thread_count"] == 1
        assert (await c.get("/threads/H-3")).json()["other_thread_count"] == 1  # H-2
        alone = threads.create_thread(conn, "x").id
        assert (await c.get(f"/threads/{alone}")).json()["other_thread_count"] == 0

        async def submit(thread_id: str, kind: str, run_input: ExtractInput) -> object:
            run = runs.create_run(conn, thread_id, "extract", run_input)
            conn.commit()
            return run

        monkeypatch.setattr(ctx.manager, "submit", submit)
        _done_extract(conn, "H-1", series_name="Đề dự đoán")
        # another thread uses T-1: no mode → 409 asking for one
        r = await c.post("/threads/H-1/extract-again")
        assert r.status_code == 409 and r.json()["detail"] == thread_routes.CHOOSE_MODE
        for mode in ("replace", "copy"):
            r = await c.post("/threads/H-1/extract-again", json={"mode": mode})
            assert r.status_code == 200, r.text
            stored = runs.get_run(conn, r.json()["id"])
            assert stored is not None and isinstance(stored.input, ExtractInput)
            assert (stored.input.again_test_id, stored.input.again_mode) == ("T-1", mode)
            assert stored.input.existing_test_id is None
            assert stored.input.series_name == "Đề dự đoán"
            conn.execute("DELETE FROM runs WHERE id = ?", (stored.id,))
            conn.commit()
        assert (await c.post("/threads/H-1/extract-again", json={"mode": "x"})).status_code == 422
        # no other thread uses T-4: replace by default
        conn.execute("UPDATE threads SET test_id = 'T-4' WHERE id = ?", (alone,))
        conn.commit()
        assert (await c.get(f"/threads/{alone}")).json()["other_thread_count"] == 0
        _done_extract(conn, alone)
        r = await c.post(f"/threads/{alone}/extract-again")
        assert r.status_code == 200, r.text
        stored = runs.get_run(conn, r.json()["id"])
        assert stored is not None and isinstance(stored.input, ExtractInput)
        assert (stored.input.again_test_id, stored.input.again_mode) == ("T-4", "replace")
