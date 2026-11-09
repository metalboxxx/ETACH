"""Refinements step R3 (D6, D7): the sidecar side of Add key and delete key.

R3.1 a key added for a question with none is a teacher key; R3.3 ``DELETE
/tests/{id}/keys/{question_id}`` removes the key and its explanations and settles the question's
open ``uncertain_key`` item; R3.5 the Word file shows the changed keys. R3.4 is in
``unit/graphs/test_refinements_r3.py``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from docx import Document
from unit.api.test_routes_b import _attempt, _conn, _key, _llm_call, _test
from unit.api.test_routes_c import client

from etach.api.deps import AppContext
from etach.api.routes import tests as tests_route
from etach.domain import models as m
from etach.store.repos import explanations, keys, regrade, review, runs


@pytest.fixture
def ctx(make_ctx: Callable[..., AppContext]) -> AppContext:
    return make_ctx()


def _explanation(conn: sqlite3.Connection, test_id: str, qid: str) -> None:
    explanations.upsert_explanation(
        conn,
        m.Explanation(
            test_id=test_id,
            question_id=qid,
            wrong_answer_norm="c",
            error_type="gap",
            text_vi="Giải thích.",
            status="ai",
            llm_call_id=_llm_call(conn),
        ),
    )


def _uncertain(conn: sqlite3.Connection, test_id: str, qid: str, run: str = "R-1") -> str:
    item, _ = review.upsert_item(
        conn,
        kind="uncertain_key",
        owner="grade",
        dedupe_key=f"uncertain_key:{run}:{test_id}:{qid}",
        proposal={"accepted": []},
        test_id=test_id,
        question_id=qid,
    )
    return item.id


def _with_key(ctx: AppContext) -> str:
    conn = _conn(ctx)
    try:
        test_id = _test(conn)
        keys.upsert_key(conn, _key(test_id, "q-1", "A"))
        keys.upsert_key(conn, _key(test_id, "q-2", "B"))
    finally:
        conn.close()
    return test_id


@pytest.mark.asyncio
async def test_r3_3_delete_removes_the_key_and_its_explanations_and_starts_no_run(
    ctx: AppContext,
) -> None:
    test_id = _with_key(ctx)
    conn = _conn(ctx)
    try:
        _attempt(conn, test_id, graded=True)
        _explanation(conn, test_id, "q-1")
        _explanation(conn, test_id, "q-2")
        before = {r.id for r in runs.list_runs(conn)}
    finally:
        conn.close()
    async with client(ctx) as c:
        r = await c.delete(f"/tests/{test_id}/keys/q-1")
        assert r.status_code == 204, r.text
        assert r.content == b""
        listed = (await c.get(f"/tests/{test_id}/keys")).json()
        assert [k["question_id"] for k in listed] == ["q-2"]
        assert (await c.get(f"/tests/{test_id}")).json()["regrade_pending"] is True
    conn = _conn(ctx)
    try:
        assert explanations.get_explanation(conn, test_id, "q-1", "c") is None
        assert explanations.get_explanation(conn, test_id, "q-2", "c") is not None
        assert {r.id for r in runs.list_runs(conn)} == before
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_r3_3_a_teacher_key_can_be_deleted_too(ctx: AppContext) -> None:
    test_id = _with_key(ctx)
    async with client(ctx) as c:
        r = await c.put(f"/tests/{test_id}/keys/q-1", json={"accepted": ["C"]})
        assert r.json()["key"]["source"] == "teacher_edit"
        assert (await c.delete(f"/tests/{test_id}/keys/q-1")).status_code == 204
    conn = _conn(ctx)
    try:
        assert keys.get_key(conn, test_id, "q-1") is None
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_r3_3_no_graded_attempt_is_not_pending(ctx: AppContext) -> None:
    test_id = _with_key(ctx)
    async with client(ctx) as c:
        assert (await c.delete(f"/tests/{test_id}/keys/q-1")).status_code == 204
    conn = _conn(ctx)
    try:
        assert regrade.is_pending(conn, test_id) is False
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_r3_3_delete_settles_only_that_questions_open_unsure_items(
    ctx: AppContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_id = _with_key(ctx)
    conn = _conn(ctx)
    try:
        first = _uncertain(conn, test_id, "q-1", "R-1")
        second = _uncertain(conn, test_id, "q-1", "R-2")
        other = _uncertain(conn, test_id, "q-2")
    finally:
        conn.close()
    published: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        tests_route.sse, "publish", lambda _bus, name, **kw: published.append((name, kw))
    )
    async with client(ctx) as c:
        assert (await c.delete(f"/tests/{test_id}/keys/q-1")).status_code == 204
    conn = _conn(ctx)
    try:
        for item_id in (first, second):
            item = review.get_item(conn, item_id)
            assert item is not None and item.status == "fixed"
            assert item.resolution == {"action": "fix", "value": {"by": "key_deleted"}}
        still = review.get_item(conn, other)
        assert still is not None and still.status == "open"
    finally:
        conn.close()
    assert published == [("review.changed", {"open": 1})]


@pytest.mark.asyncio
async def test_r3_3_no_review_event_when_nothing_was_settled(
    ctx: AppContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_id = _with_key(ctx)
    published: list[str] = []
    monkeypatch.setattr(
        tests_route.sse, "publish", lambda _bus, name, **_kw: published.append(name)
    )
    async with client(ctx) as c:
        assert (await c.delete(f"/tests/{test_id}/keys/q-1")).status_code == 204
    assert published == []


@pytest.mark.asyncio
async def test_r3_3_delete_404s_and_changes_nothing(ctx: AppContext) -> None:
    test_id = _with_key(ctx)
    conn = _conn(ctx)
    try:
        _attempt(conn, test_id, graded=True)
        item = _uncertain(conn, test_id, "q-2")
    finally:
        conn.close()
    async with client(ctx) as c:
        assert (await c.delete("/tests/T-9999/keys/q-1")).status_code == 404
        assert (await c.delete(f"/tests/{test_id}/keys/q-9")).status_code == 404
        assert (await c.delete(f"/tests/{test_id}/keys/q-1")).status_code == 204
        again = await c.delete(f"/tests/{test_id}/keys/q-1")  # no key any more
        assert again.status_code == 404
    conn = _conn(ctx)
    try:
        assert keys.get_key(conn, test_id, "q-2") is not None
        still = review.get_item(conn, item)
        assert still is not None and still.status == "open"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_r3_1_a_key_added_for_a_question_with_none_is_a_teacher_key(ctx: AppContext) -> None:
    conn = _conn(ctx)
    try:
        test_id = _test(conn)
        keys.upsert_key(conn, _key(test_id, "q-1", "A"))
    finally:
        conn.close()
    async with client(ctx) as c:
        r = await c.put(f"/tests/{test_id}/keys/q-2", json={"accepted": ["B"]})
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "inserted"
    assert r.json()["key"]["source"] == "teacher_edit"
    assert r.json()["key"]["status"] == "teacher_verified"


@pytest.mark.asyncio
async def test_r3_1_a_fix_on_a_failed_key_item_is_a_teacher_key_too(ctx: AppContext) -> None:
    """``ai_key_fast`` failed: an open ``uncertain_key`` and no key row (plan §2, "Test 2"). The
    panel saves this one through the item's Fix, so the note closes with the new key."""
    conn = _conn(ctx)
    try:
        test_id = _test(conn)
        item = _uncertain(conn, test_id, "q-1")
    finally:
        conn.close()
    async with client(ctx) as c:
        r = await c.post(f"/review/{item}/resolve", json={"action": "fix", "value": ["B"]})
        assert r.status_code == 200, r.text
        listed = (await c.get(f"/tests/{test_id}/keys")).json()
    assert [(k["question_id"], k["source"], k["status"]) for k in listed] == [
        ("q-1", "teacher_edit", "teacher_verified")
    ]


@pytest.mark.asyncio
async def test_r3_1_two_open_items_skip_then_fix_closes_both_and_keeps_the_key(
    ctx: AppContext,
) -> None:
    """Each run that missed the key adds an item. ``resolve`` closes one, so the panel skips the
    extra one and sends the Fix last: the key is written once and no item stays open."""
    conn = _conn(ctx)
    try:
        test_id = _test(conn)
        first = _uncertain(conn, test_id, "q-1", "R-1")
        second = _uncertain(conn, test_id, "q-1", "R-2")
    finally:
        conn.close()
    async with client(ctx) as c:
        r = await c.post(f"/review/{first}/resolve", json={"action": "skip"})
        assert r.status_code == 200, r.text
        assert (await c.get(f"/tests/{test_id}/keys")).json() == []  # a skip writes no key
        r = await c.post(f"/review/{second}/resolve", json={"action": "fix", "value": ["B"]})
        assert r.status_code == 200, r.text
        listed = (await c.get(f"/tests/{test_id}/keys")).json()
        review_left = (await c.get(f"/tests/{test_id}")).json()["review"]
    assert [(k["accepted"], k["source"]) for k in listed] == [(["B"], "teacher_edit")]
    assert review_left == []


def _word_lines(path: Path) -> list[str]:
    return [p.text for p in Document(str(path)).paragraphs]


@pytest.mark.asyncio
async def test_r3_5_the_word_file_shows_the_changed_keys(ctx: AppContext) -> None:
    test_id = _with_key(ctx)
    async with client(ctx) as c:
        assert (await c.delete(f"/tests/{test_id}/keys/q-1")).status_code == 204
        r = await c.put(f"/tests/{test_id}/keys/q-2", json={"accepted": ["A"]})
        assert r.status_code == 200, r.text
        r = await c.post(f"/tests/{test_id}/export", json={"what": "key"})
        assert r.status_code == 200, r.text
    lines = _word_lines(Path(r.json()["path"]))
    assert "1. (no key)" in lines and "2. A" in lines
