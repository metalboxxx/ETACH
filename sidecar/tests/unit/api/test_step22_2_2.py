"""Step 22.2.2: "Use automatic name" — ``PATCH /threads/{id}`` ``{title: null}`` goes back to the
automatic title (R22.2.2.5; llm-design v4.25, data-model §5.6 v1.9.3)."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager

import httpx
import pytest
from unit.api.test_routes_b import _attempt, _test

from etach.api.app import create_app
from etach.api.deps import AppContext
from etach.api.routes.threads import DEFAULT_TITLE
from etach.store import db


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


@pytest.mark.asyncio
async def test_r22_2_2_5_title_null_goes_back_to_the_made_title(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    test_id = _test(conn)
    att = _attempt(conn, test_id, graded=False)
    async with client(ctx) as c:
        # the made title, as a thread with the default title shows it
        await c.patch(f"/threads/{att.thread_id}", json={"title": "Ánh"})
        r = await c.patch(f"/threads/{att.thread_id}", json={"title": None})
        assert r.status_code == 200, r.text
        assert r.json()["title"] == DEFAULT_TITLE
        detail = (await c.get(f"/threads/{att.thread_id}")).json()
        made = detail["shown_title"]
        assert made not in ("Ánh", DEFAULT_TITLE, "photos")
        row = {t["thread"]["id"]: t for t in (await c.get("/threads")).json()}[att.thread_id]
        assert row["shown_title"] == made
        assert row["thread"]["title"] == DEFAULT_TITLE


@pytest.mark.asyncio
async def test_title_null_clears_a_kept_default_and_404s_unknown(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    test_id = _test(conn)
    att = _attempt(conn, test_id, graded=False)
    async with client(ctx) as c:
        await c.patch(f"/threads/{att.thread_id}", json={"title": "New thread"})
        assert (await c.get(f"/threads/{att.thread_id}")).json()["shown_title"] == "New thread"
        await c.patch(f"/threads/{att.thread_id}", json={"title": None})
        assert (await c.get(f"/threads/{att.thread_id}")).json()["shown_title"] != "New thread"
        assert (await c.patch("/threads/nope", json={"title": None})).status_code == 404
        # a blank title is still refused; a missing title is not "automatic"
        assert (await c.patch(f"/threads/{att.thread_id}", json={"title": "  "})).status_code == 422
        assert (await c.patch(f"/threads/{att.thread_id}", json={})).status_code == 422
