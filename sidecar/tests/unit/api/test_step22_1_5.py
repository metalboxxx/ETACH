"""Step 22.1.5 routes (llm-design v4.22, data-model v1.9 §2.3a, §5.3): ``GET /tests/{id}``
``content_text`` and ``review``, ``PATCH /tests/{id}`` ``{content_text, drop_confirmed}``
(R22.1.5.3), ``open_review_count`` on ``GET /threads`` and ``GET /tests`` (R22.1.5.5), and a
thread renamed exactly "New thread" (R22.1.5.8)."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from unit.api.test_routes_b import _attempt, _test

from etach.api.app import create_app
from etach.api.deps import AppContext
from etach.domain import models as m
from etach.domain.test_text import render
from etach.store import db
from etach.store.repos import keys, review, tests


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


def _open(conn: sqlite3.Connection, kind: str, test_id: str, **kw: Any) -> str:
    item, _ = review.upsert_item(
        conn,
        kind=kind,  # type: ignore[arg-type]
        owner="extract",
        dedupe_key=kw.pop("dedupe_key", f"{kind}:{test_id}:{kw.get('question_id')}"),
        proposal=kw.pop("proposal", {}),
        test_id=test_id,
        **kw,
    )
    return item.id


@pytest.mark.asyncio
async def test_get_test_has_its_text_and_open_items(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    test_id = _test(conn)
    att = _attempt(conn, test_id, graded=False)
    own = _open(conn, "unknown_occasion", test_id)
    answer = _open(conn, "uncertain_answer", test_id, attempt_id=att.id, question_id="q-1")
    other = _test(conn)
    _open(conn, "unknown_occasion", other)
    done = _open(conn, "uncertain_key", test_id, question_id="q-2")
    review.resolve_item(conn, done, "accepted")
    async with client(ctx) as c:
        got = (await c.get(f"/tests/{test_id}")).json()
    stored = tests.get_test(conn, test_id)
    assert stored is not None
    assert got["content_text"] == render(stored.content)
    head = "— Page 1 —\n\n# I  [title: Choose]\n"  # v1.21 (D7): no points
    assert got["content_text"].startswith(head)
    assert sorted(i["id"] for i in got["review"]) == sorted([own, answer])


@pytest.mark.asyncio
async def test_patch_content_text_saves_it(ctx: AppContext, conn: sqlite3.Connection) -> None:
    test_id = _test(conn)
    async with client(ctx) as c:
        text = (await c.get(f"/tests/{test_id}")).json()["content_text"]
        r = await c.patch(
            f"/tests/{test_id}", json={"content_text": text.replace("Stem 2", "A better stem")}
        )
        assert r.status_code == 200, r.text
        assert "A better stem" in r.json()["content_text"]
        got = (await c.get(f"/tests/{test_id}")).json()
    q2 = got["content"]["sections"][0]["groups"][0]["questions"][1]
    assert (q2["id"], q2["stem"]) == ("q-2", "A better stem")


@pytest.mark.asyncio
async def test_patch_content_text_errors_have_lines(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    test_id = _test(conn)
    before = tests.get_test(conn, test_id)
    async with client(ctx) as c:
        text = (await c.get(f"/tests/{test_id}")).json()["content_text"]
        r = await c.patch(f"/tests/{test_id}", json={"content_text": "loose words\n" + text})
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert detail["errors"][0]["line"] == 1
        assert isinstance(detail["errors"][0]["message"], str)
        both = await c.patch(
            f"/tests/{test_id}", json={"content_text": text, "content": {"sections": []}}
        )
        assert both.status_code == 422
    assert tests.get_test(conn, test_id) == before


@pytest.mark.asyncio
async def test_r22_1_5_3_dropping_needs_confirmation(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    test_id = _test(conn)
    _attempt(conn, test_id, graded=False)
    keys.upsert_key(
        conn,
        m.AnswerKey(
            test_id=test_id,
            question_id="q-2",
            accepted=["A"],
            reason_vi=None,
            source="ai",
            status="ai_unverified",
            confidence=None,
            updated_at=tests.get_test(conn, test_id).updated_at,  # type: ignore[union-attr]
        ),
    )
    async with client(ctx) as c:
        text = (await c.get(f"/tests/{test_id}")).json()["content_text"]
        lines = text.split("\n")
        at = lines.index("2. Stem 2")
        del lines[at : at + 2]
        dropped = "\n".join(lines)
        r = await c.patch(f"/tests/{test_id}", json={"content_text": dropped})
        assert r.status_code == 422
        drops = r.json()["detail"]["drops"]
        assert [(d["question_id"], d["number"], d["has_key"], d["answers"]) for d in drops] == [
            ("q-2", 2, True, 1)
        ]
        assert "Stem 2" in (await c.get(f"/tests/{test_id}")).json()["content_text"]
        r = await c.patch(
            f"/tests/{test_id}", json={"content_text": dropped, "drop_confirmed": ["q-2"]}
        )
        assert r.status_code == 200, r.text
        assert "Stem 2" not in r.json()["content_text"]
    assert keys.get_key(conn, test_id, "q-2") is None


@pytest.mark.asyncio
async def test_r22_1_5_5_open_review_counts(ctx: AppContext, conn: sqlite3.Connection) -> None:
    test_id = _test(conn)
    att = _attempt(conn, test_id, graded=False)
    clean = _test(conn)
    _attempt(conn, clean, graded=False)
    _open(conn, "unreadable_text", test_id, dedupe_key="u:p1")
    _open(conn, "uncertain_answer", test_id, attempt_id=att.id, question_id="q-1")
    async with client(ctx) as c:
        listed = {t["thread"]["test_id"]: t for t in (await c.get("/threads")).json()}
        bank = {t["id"]: t for t in (await c.get("/tests")).json()}
    assert listed[test_id]["open_review_count"] == 2
    assert listed[clean]["open_review_count"] == 0
    assert bank[test_id]["open_review_count"] == 2
    assert bank[clean]["open_review_count"] == 0


@pytest.mark.asyncio
async def test_meta_occasion_edit_settles_unknown_occasion(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    test_id = _test(conn)
    item = _open(conn, "unknown_occasion", test_id)
    async with client(ctx) as c:
        r = await c.patch(f"/tests/{test_id}", json={"meta": {"occasion": "MidTerm"}})
        assert r.status_code == 200, r.text
        assert r.json()["review"] == []
    got = review.get_item(conn, item)
    assert got is not None and got.status == "fixed"


@pytest.mark.asyncio
async def test_r22_1_5_8_rename_to_new_thread_keeps_it(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    test_id = _test(conn)
    att = _attempt(conn, test_id, graded=False)
    async with client(ctx) as c:
        made = {t["thread"]["id"]: t for t in (await c.get("/threads")).json()}[att.thread_id]
        assert made["shown_title"] == "photos"  # the factory's title
        r = await c.patch(f"/threads/{att.thread_id}", json={"title": "New thread"})
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "New thread"
        row = {t["thread"]["id"]: t for t in (await c.get("/threads")).json()}[att.thread_id]
        assert row["shown_title"] == "New thread"
        assert row["thread"]["title"] == "New thread"
        detail = (await c.get(f"/threads/{att.thread_id}")).json()
        assert detail["shown_title"] == "New thread"
        # a fresh thread with the default title still gets its made title
        fresh = (await c.post("/threads", json={"title": ""})).json()["thread_id"]
        rows = {t["thread"]["id"]: t for t in (await c.get("/threads")).json()}
        assert rows[fresh]["shown_title"] == "New thread"
        # renaming away and back works too
        await c.patch(f"/threads/{att.thread_id}", json={"title": "Ánh"})
        await c.patch(f"/threads/{att.thread_id}", json={"title": " New   thread "})
        detail = (await c.get(f"/threads/{att.thread_id}")).json()
        assert detail["shown_title"] == "New thread"
