"""Step 22.5.5a: the sidecar API (R22.5.5.1 the Key read carries the checker's answer)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from unit.api.test_routes_b import _conn, _key, _test
from unit.api.test_routes_c import client

from etach.api.deps import AppContext
from etach.domain import models as m
from etach.store.repos import keys


@pytest.fixture
def ctx(make_ctx: Callable[..., AppContext]) -> AppContext:
    return make_ctx()


@pytest.mark.asyncio
async def test_r22_5_5_1_key_read_carries_the_checker(ctx: AppContext) -> None:
    conn = _conn(ctx)
    try:
        test_id = _test(conn)
        unsure = m.KeyCheck(status="disagreed", answer="B", reasoning="Past simple: B.")
        keys.upsert_key(
            conn,
            _key(test_id, "q-1", "A").model_copy(
                update={"status": "ai_uncertain", "checker": unsure}
            ),
        )
        keys.upsert_key(
            conn,
            _key(test_id, "q-2", "B").model_copy(
                update={"status": "ai_uncertain", "checker": m.KeyCheck(status="did_not_finish")}
            ),
        )
    finally:
        conn.close()
    async with client(ctx) as c:
        r = await c.get(f"/tests/{test_id}/keys")
    assert r.status_code == 200, r.text
    got = {k["question_id"]: k["checker"] for k in r.json()}
    assert got["q-1"] == {"status": "disagreed", "answer": "B", "reasoning": "Past simple: B."}
    assert got["q-2"] == {"status": "did_not_finish", "answer": None, "reasoning": None}


@pytest.mark.asyncio
async def test_r22_5_5_2_patch_sets_the_date_taken(ctx: AppContext) -> None:
    from unit.api.test_routes_b import _attempt

    conn = _conn(ctx)
    try:
        test_id = _test(conn)
        att = _attempt(conn, test_id, graded=True)
    finally:
        conn.close()
    async with client(ctx) as c:
        before = (await c.get(f"/attempts/{att.id}")).json()["attempt"]
        r = await c.patch(f"/attempts/{att.id}", json={"taken_on": "2026-10-01"})
        assert r.status_code == 200, r.text
        assert r.json()["taken_on"] == "2026-10-01"
        assert r.json()["version"] == before["version"] + 1
        after = (await c.get(f"/attempts/{att.id}")).json()["attempt"]
        assert after["taken_on"] == "2026-10-01"
        assert (await c.patch(f"/attempts/{att.id}", json={"taken_on": "x"})).status_code == 422
        assert (
            await c.patch("/attempts/A-9999", json={"taken_on": "2026-10-01"})
        ).status_code == 404
        active = (await c.get("/runs/active")).json()
    assert active == [] or all(r.get("attempt_id") != att.id for r in active)  # no run


@pytest.mark.asyncio
async def test_r22_5_5_12_verify_clears_a_stale_checker(ctx: AppContext) -> None:
    conn = _conn(ctx)
    try:
        test_id = _test(conn)
        keys.upsert_key(
            conn,
            _key(test_id, "q-1", "A").model_copy(
                update={
                    "status": "ai_uncertain",
                    "checker": m.KeyCheck(status="disagreed", answer="B", reasoning="r"),
                }
            ),
        )
    finally:
        conn.close()
    async with client(ctx) as c:
        r = await c.put(f"/tests/{test_id}/keys/q-1", json={"verify": True})
        assert r.status_code == 200, r.text
        assert (r.json()["key"]["status"], r.json()["key"]["checker"]) == (
            "teacher_verified",
            None,
        )
        (key,) = [
            k for k in (await c.get(f"/tests/{test_id}/keys")).json() if k["question_id"] == "q-1"
        ]
    assert key["checker"] is None and key["accepted"] == ["A"]


@pytest.mark.asyncio
async def test_r22_5_5_12_explanation_with_null_llm_call_id_loads(ctx: AppContext) -> None:
    """A thread delete sets ``explanations.llm_call_id`` NULL; the explanations of the test (and
    another paper's report) still load."""
    from unit.api.test_routes_b import _attempt

    from etach.store.repos import explanations

    conn = _conn(ctx)
    try:
        test_id = _test(conn)
        att = _attempt(conn, test_id, graded=True)
        conn.execute(
            "INSERT INTO explanations (test_id, question_id, wrong_answer_norm, error_type,"
            " text_vi, status, llm_call_id)"
            " VALUES (?, 'q-1', 'b', 'gap', 'giải thích', 'ai', NULL)",
            (test_id,),
        )
        conn.commit()
        (e,) = explanations.list_explanations(conn, test_id)
        assert e.llm_call_id is None
    finally:
        conn.close()
    async with client(ctx) as c:
        r = await c.get(f"/attempts/{att.id}")
    assert r.status_code == 200, r.text
