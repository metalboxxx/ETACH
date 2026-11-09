"""Step 22.3.2 (R22.3.2.2): ``POST /threads/{id}/extract-again`` (llm-design §2 v4.29).

A new extract run on the pages of the thread's last finished extract run, without the picked
test, superseding the current attempt; 409 while a run of the thread is active or when the thread
has no finished extract run.
"""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest

from etach.api.app import create_app
from etach.api.deps import AppContext
from etach.api.routes import threads as thread_routes
from etach.domain.models import ExtractInput, PageInput
from etach.store import db
from etach.store.repos import runs


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


def _pages(*ids: str) -> list[PageInput]:
    return [PageInput(file_id=i, rotation=0, is_key=False, text_file_id=None) for i in ids]


def _done_extract(conn: sqlite3.Connection, thread_id: str, *ids: str, picked: str | None) -> str:
    run = runs.create_run(
        conn,
        thread_id,
        "extract",
        ExtractInput(pages=_pages(*ids), existing_test_id=picked, supersedes_attempt_id=None),
    )
    runs.set_run_status(conn, run.id, "done")
    conn.commit()
    return run.id


@pytest.mark.asyncio
async def test_extract_again_reuses_the_last_pages_without_the_pick_and_supersedes(
    ctx: AppContext, conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with client(ctx) as c:
        tid = (await c.post("/threads", json={"title": ""})).json()["thread_id"]
        _done_extract(conn, tid, "F-old", picked=None)
        _done_extract(conn, tid, "F-1", "F-2", picked="T-9")
        monkeypatch.setattr(
            thread_routes.attempts, "current_attempt", lambda _c, _t: SimpleNamespace(id="A-1")
        )

        async def submit(thread_id: str, kind: str, run_input: ExtractInput) -> object:
            # The manager is not started here: queue the row only (what ``submit`` writes).
            run = runs.create_run(conn, thread_id, "extract", run_input)
            conn.commit()
            return run

        monkeypatch.setattr(ctx.manager, "submit", submit)
        r = await c.post(f"/threads/{tid}/extract-again")
        assert r.status_code == 200, r.text
        body = r.json()
        assert (body["thread_id"], body["kind"]) == (tid, "extract")
        stored = runs.get_run(conn, body["id"])
        assert stored is not None and isinstance(stored.input, ExtractInput)
        assert [p.file_id for p in stored.input.pages] == ["F-1", "F-2"]
        assert stored.input.existing_test_id is None
        assert stored.input.supersedes_attempt_id == "A-1"


@pytest.mark.asyncio
async def test_extract_again_409_while_active_or_without_a_done_extract_and_404(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    async with client(ctx) as c:
        tid = (await c.post("/threads", json={"title": ""})).json()["thread_id"]
        r = await c.post(f"/threads/{tid}/extract-again")
        assert r.status_code == 409
        assert r.json()["detail"] == thread_routes.NOTHING_TO_EXTRACT
        run_id = _done_extract(conn, tid, "F-1", picked=None)
        for status in ("queued", "running", "stopping", "stopped", "interrupted"):
            other = runs.create_run(
                conn,
                tid,
                "grade",
                runs.GradeInput(test_id="T-1", attempt_id=None, reason="button"),
            )
            runs.set_run_status(conn, other.id, status)
            conn.commit()
            r = await c.post(f"/threads/{tid}/extract-again")
            assert r.status_code == 409, status
            assert "stop or discard" in r.json()["detail"]
            conn.execute("DELETE FROM runs WHERE id = ?", (other.id,))
            conn.commit()
        assert runs.get_run(conn, run_id) is not None
        assert (await c.post("/threads/nope/extract-again")).status_code == 404
