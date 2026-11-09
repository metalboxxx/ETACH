"""Step 22.1.1 routes (the teacher's app review, comments 7, 11, 13; llm-design v4.19,
data-model v1.8 §5.6): ``PATCH /students/{id}`` (R22.1.1.4), ``PATCH /threads/{id}``
(R22.1.1.5) and the thread's shown title (R22.1.1.6)."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager

import httpx
import pytest
from unit.api.test_routes_b import _attempt, _test

from etach.api.app import create_app
from etach.api.deps import AppContext
from etach.store import db
from etach.store.repos import attempts, students, threads


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


# --- R22.1.1.4: PATCH /students/{id} -------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_student_name_follows_name_search(ctx: AppContext) -> None:
    async with client(ctx) as c:
        created = (await c.post("/students", json={"full_name": "A", "class_name": "8A"})).json()
        sid = created["id"]

        r = await c.patch(f"/students/{sid}", json={"full_name": "  Nguyễn   Thị Ánh "})
        assert r.status_code == 200, r.text
        assert r.json()["full_name"] == "Nguyễn Thị Ánh"
        assert r.json()["name_search"] == "nguyen thi anh"
        assert r.json()["class_name"] == "8A"  # untouched

        found = (await c.get("/students", params={"q": "nguyen thi anh"})).json()
        assert [s["id"] for s in found] == [sid]

        r = await c.patch(f"/students/{sid}", json={"class_name": " 9B "})
        assert r.status_code == 200 and r.json()["class_name"] == "9B"
        assert r.json()["full_name"] == "Nguyễn Thị Ánh"


@pytest.mark.asyncio
async def test_patch_student_old_form_no_longer_found(ctx: AppContext) -> None:
    async with client(ctx) as c:
        sid = (await c.post("/students", json={"full_name": "Lê Văn Bảo"})).json()["id"]
        assert [s["id"] for s in (await c.get("/students", params={"q": "le van bao"})).json()] == [
            sid
        ]
        r = await c.patch(f"/students/{sid}", json={"full_name": "Phạm Minh Châu"})
        assert r.status_code == 200, r.text
        assert [
            s["id"] for s in (await c.get("/students", params={"q": "pham minh chau"})).json()
        ] == [sid]
        assert (await c.get("/students", params={"q": "le van bao"})).json() == []


@pytest.mark.asyncio
async def test_patch_student_blank_422_unknown_404(ctx: AppContext) -> None:
    async with client(ctx) as c:
        sid = (await c.post("/students", json={"full_name": "Lê Văn Bảo"})).json()["id"]
        assert (await c.patch(f"/students/{sid}", json={"full_name": "   "})).status_code == 422
        assert (await c.patch(f"/students/{sid}", json={"full_name": None})).status_code == 422
        assert (await c.patch("/students/S-9999", json={"full_name": "X"})).status_code == 404
        still = (await c.get("/students")).json()
        assert [s["full_name"] for s in still] == ["Lê Văn Bảo"]


def test_update_student_repo_rules(conn: sqlite3.Connection) -> None:
    s = students.create_student(conn, "A", "a")
    with pytest.raises(ValueError):
        students.update_student(conn, s.id, {"full_name": "B"})  # without its name_search
    with pytest.raises(ValueError):
        students.update_student(conn, s.id, {"notes": "x"})
    assert students.update_student(conn, "S-9999", {"class_name": "8A"}) is None
    got = students.update_student(conn, s.id, {"full_name": "Bình", "name_search": "binh"})
    assert got is not None and (got.full_name, got.name_search) == ("Bình", "binh")


# --- R22.1.1.5: PATCH /threads/{id} --------------------------------------------------------------


@pytest.mark.asyncio
async def test_rename_thread(ctx: AppContext) -> None:
    async with client(ctx) as c:
        tid = (await c.post("/threads", json={"title": ""})).json()["thread_id"]
        r = await c.patch(f"/threads/{tid}", json={"title": "  Ánh's  mid-term "})
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "Ánh's mid-term"

        listed = {t["thread"]["id"]: t for t in (await c.get("/threads")).json()}
        assert listed[tid]["thread"]["title"] == "Ánh's mid-term"
        assert listed[tid]["shown_title"] == "Ánh's mid-term"
        detail = (await c.get(f"/threads/{tid}")).json()
        assert detail["thread"]["title"] == "Ánh's mid-term"
        assert detail["shown_title"] == "Ánh's mid-term"

        assert (await c.patch(f"/threads/{tid}", json={"title": "  "})).status_code == 422
        assert (await c.patch(f"/threads/{tid}", json={})).status_code == 422
        assert (await c.patch("/threads/nope", json={"title": "x"})).status_code == 404
        assert (await c.get(f"/threads/{tid}")).json()["thread"]["title"] == "Ánh's mid-term"


# --- R22.1.1.6: the shown title ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shown_title_from_student_and_test(ctx: AppContext, conn: sqlite3.Connection) -> None:
    test_id = _test(conn)  # Grade 8 - Final Term 1 - Test 1
    att = _attempt(conn, test_id, graded=False)
    threads.set_title(conn, att.thread_id, "New thread")
    empty = threads.create_thread(conn, "New thread")
    renamed = _attempt(conn, test_id, graded=False)  # titled "photos" by the factory

    async with client(ctx) as c:

        def shown(rows: list[dict[str, object]], tid: str) -> object:
            return next(r["shown_title"] for r in rows if r["thread"]["id"] == tid)  # type: ignore[index]

        rows = (await c.get("/threads")).json()
        assert shown(rows, att.thread_id) == "Grade 8 - Final Term 1 - Test 1"  # no student yet
        assert shown(rows, empty.id) == "New thread"  # no test yet
        assert shown(rows, renamed.thread_id) == "photos"  # the teacher's title wins

        sid = (await c.post("/students", json={"full_name": "Nguyễn Văn An"})).json()["id"]
        attempts.set_student(conn, att.id, sid)
        rows = (await c.get("/threads")).json()
        assert shown(rows, att.thread_id) == "Grade 8 - Final Term 1 - Test 1 · Nguyễn Văn An"
        detail = (await c.get(f"/threads/{att.thread_id}")).json()
        assert detail["shown_title"] == "Grade 8 - Final Term 1 - Test 1 · Nguyễn Văn An"
        assert detail["thread"]["title"] == "New thread"  # made on read, not stored
        assert detail["student"]["full_name"] == "Nguyễn Văn An"
        assert detail["test_display_name"] == "Grade 8 - Final Term 1 - Test 1"

        # A student rename shows up in the title at once.
        await c.patch(f"/students/{sid}", json={"full_name": "Nguyễn Văn Ân"})
        rows = (await c.get("/threads")).json()
        assert shown(rows, att.thread_id) == "Grade 8 - Final Term 1 - Test 1 · Nguyễn Văn Ân"

        empty_detail = (await c.get(f"/threads/{empty.id}")).json()
        assert empty_detail["shown_title"] == "New thread"
        assert empty_detail["student"] is None and empty_detail["test_display_name"] is None
