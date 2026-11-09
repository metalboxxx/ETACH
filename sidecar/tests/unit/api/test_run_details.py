"""Step 19 (R19.3): ``GET /runs/{id}`` names each model call's task (structure §7 "Run details")."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from etach.api.deps import AppContext
from etach.domain import models as m
from etach.store import db
from etach.store.repos import runs, threads

T0 = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)


def _call(step_id: str, request: dict[str, Any]) -> m.LlmCall:
    return m.LlmCall(
        id=db.new_ulid(),
        step_id=step_id,
        role="reasoning",
        model="model-x",
        prompt_hash="h",
        request=request,
        response_text="{}",
        thinking_text="",
        logprobs=None,
        status="complete",
        tokens_in=1,
        tokens_out=1,
        ms=5,
        created_at=T0,
    )


@pytest.mark.asyncio
async def test_run_detail_reports_task_per_call(
    make_ctx: Callable[..., AppContext], api: Any
) -> None:
    ctx = make_ctx()
    conn = db.connect(ctx.paths.db)
    try:
        thread = threads.create_thread(conn, "x")
        run = runs.create_run(
            conn,
            thread.id,
            "grade",
            m.GradeInput(test_id="T-1", attempt_id=None, reason="button"),
            status="done",
        )
        # node → expected task: same name, the two renamed nodes, and a stored request.task
        nodes = {
            "explain": ("explain", {"messages": []}),
            "weak_points": ("weak_points_summary", {"messages": []}),
            "retranscribe_tiles": ("transcribe_page", {"messages": []}),
            "verify_key": ("custom_task", {"messages": [], "task": "custom_task"}),
        }
        for node, (_, request) in nodes.items():
            step = runs.insert_step(conn, run.id, node, None, 1)
            runs.insert_llm_call(conn, _call(step.id, request))
        empty = runs.insert_step(conn, run.id, "save", None, 1)
    finally:
        conn.close()
    async with api.serving(ctx) as live, live.client() as client:
        r = await client.get(f"/runs/{run.id}", headers=live.auth)
        assert r.status_code == 200, r.text
        steps = r.json()["steps"]
        got = {s["step"]["node"]: [c["task"] for c in s["calls"]] for s in steps}
        assert got == {node: [task] for node, (task, _) in nodes.items()} | {"save": []}
        assert [s["step"]["id"] for s in steps][-1] == empty.id
        assert (await client.get("/runs/nope", headers=live.auth)).status_code == 404
