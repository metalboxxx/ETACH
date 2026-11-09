"""The step wrapper and the run/step repository functions it uses."""

from __future__ import annotations

import asyncio
import sqlite3
from typing import Any

import pytest
from support.toy_graph import toy_input

from etach.llm.client import StreamDropped
from etach.runtime.events import EventBus
from etach.runtime.steps import (
    Db,
    RunContext,
    _run_ctx,
    current_run,
    current_step_id,
    report_progress,
    step,
)
from etach.store.repos import runs, threads


def test_start_step_counts_tries_per_node_and_item(conn: sqlite3.Connection) -> None:
    thread = threads.create_thread(conn, "t")
    run = runs.create_run(conn, thread.id, "extract", toy_input())
    other = runs.create_run(conn, thread.id, "extract", toy_input())
    tries = [
        runs.start_step(conn, run.id, "pages", "page 1").try_no,
        runs.start_step(conn, run.id, "pages", "page 1").try_no,
        runs.start_step(conn, run.id, "pages", "page 2").try_no,
        runs.start_step(conn, run.id, "prepare", None).try_no,
        runs.start_step(conn, run.id, "prepare", None).try_no,
        runs.start_step(conn, other.id, "pages", "page 1").try_no,
    ]
    assert tries == [1, 2, 1, 1, 2, 1]


def test_close_open_steps(conn: sqlite3.Connection) -> None:
    thread = threads.create_thread(conn, "t")
    a = runs.create_run(conn, thread.id, "extract", toy_input())
    b = runs.create_run(conn, thread.id, "extract", toy_input())
    done = runs.start_step(conn, a.id, "prepare", None)
    runs.finish_step(conn, done.id, "done")
    open_a = runs.start_step(conn, a.id, "pages", "page 1")
    open_b = runs.start_step(conn, b.id, "pages", "page 1")

    assert runs.close_open_steps(conn, "failed", a.id) == [open_a.id]
    assert runs.get_step(conn, done.id).status == "done"  # type: ignore[union-attr]
    closed = runs.get_step(conn, open_a.id)
    assert closed is not None and closed.status == "failed" and closed.finished_at is not None
    assert runs.get_step(conn, open_b.id).status == "running"  # type: ignore[union-attr]
    assert runs.close_open_steps(conn, "incomplete") == [open_b.id]


def test_outside_a_run() -> None:
    with pytest.raises(RuntimeError):
        current_run()
    with pytest.raises(RuntimeError):
        current_step_id()


@pytest.fixture
def ctx(conn: sqlite3.Connection) -> RunContext:
    thread = threads.create_thread(conn, "t")
    run = runs.create_run(conn, thread.id, "extract", toy_input(), status="running")
    return RunContext(run.id, thread.id, "extract", run.input, Db(conn), EventBus())


async def _in_run(ctx: RunContext, coro: Any) -> Any:
    async def inner() -> Any:
        _run_ctx.set(ctx)
        return await coro

    return await asyncio.create_task(inner())


@pytest.mark.asyncio
async def test_wrapper_statuses_events_and_step_id(ctx: RunContext) -> None:
    seen: list[str] = []
    events: list[dict[str, Any]] = []
    ctx.events.add_listener(events.append)

    async def node(state: dict[str, Any]) -> dict[str, Any]:
        seen.append(current_step_id())
        report_progress(1, 2, "half")
        return {"x": state["x"] + 1}

    wrapped = step("node", node, item=lambda s: f"page {s['x']}")
    assert wrapped.__name__ == "node"
    assert await _in_run(ctx, wrapped({"x": 1})) == {"x": 2}
    assert await _in_run(ctx, wrapped({"x": 1})) == {"x": 2}

    rows = runs.list_steps(ctx.db.conn, ctx.run_id)
    assert [(r.node, r.item, r.try_no, r.status) for r in rows] == [
        ("node", "page 1", 1, "done"),
        ("node", "page 1", 2, "done"),
    ]
    assert seen == [r.id for r in rows]
    assert [e["type"] for e in events] == [
        "run.step_started",
        "run.progress",
        "run.step_done",
    ] * 2
    assert events[1]["step_id"] == rows[0].id and events[1]["label"] == "half"
    assert events[2]["status"] == "done" and events[2]["try_no"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ValueError("bad"), "failed"),
        (StreamDropped("t", ["c1", "c2"]), "incomplete"),
        (asyncio.CancelledError(), "incomplete"),
    ],
)
async def test_wrapper_marks_failure_kinds(
    ctx: RunContext, error: BaseException, status: str
) -> None:
    events: list[dict[str, Any]] = []
    ctx.events.add_listener(events.append)

    async def node(state: dict[str, Any]) -> dict[str, Any]:
        raise error

    with pytest.raises(type(error)):
        await _in_run(ctx, step("n", node)({}))
    [row] = runs.list_steps(ctx.db.conn, ctx.run_id)
    assert row.status == status and row.item is None
    assert events[-1]["type"] == "run.step_done" and events[-1]["status"] == status


@pytest.mark.asyncio
async def test_stop_at_boundary_skips_node_work(ctx: RunContext) -> None:
    ran: list[bool] = []

    async def node(state: dict[str, Any]) -> dict[str, Any]:
        ran.append(True)
        return {}

    task: asyncio.Task[Any] | None = None

    def cancel_on_start(event: dict[str, Any]) -> None:
        if event["type"] == "run.step_started" and task is not None:
            task.cancel()

    ctx.events.add_listener(cancel_on_start)

    async def inner() -> Any:
        _run_ctx.set(ctx)
        return await step("n", node)({})

    task = asyncio.create_task(inner())
    with pytest.raises(asyncio.CancelledError):
        await task
    assert ran == []
    [row] = runs.list_steps(ctx.db.conn, ctx.run_id)
    assert row.status == "incomplete"
