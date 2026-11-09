"""SSE ``GET /events`` (R12.3 stream order, R12.8 recovery over SSE) and the event hub."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from etach.api import sse
from etach.api.deps import AppContext
from etach.cli import _page_inputs
from etach.store import db
from etach.store.files import FileStore
from etach.store.repos import runs, threads


def _extract_input(ctx: AppContext, s1: Any) -> tuple[str, Any]:
    conn = db.connect(ctx.paths.db)
    try:
        files = FileStore(conn, ctx.paths)
        pages, manifest = _page_inputs(argparse.Namespace(pages=[], key=[], replay=s1), files)
        from etach.domain.models import ExtractInput

        inp = ExtractInput(
            pages=pages,
            existing_test_id=manifest.existing_test_id,
            supersedes_attempt_id=manifest.supersedes_attempt_id,
        )
        thread_id = threads.create_thread(conn, "sse test").id
    finally:
        conn.close()
    return thread_id, inp


@pytest.mark.asyncio
async def test_r12_3_extract_run_streams_in_order(
    make_ctx: Callable[..., AppContext], api: Any
) -> None:
    ctx = make_ctx()
    thread_id, inp = _extract_input(ctx, api.S1)
    async with api.serving(ctx) as live, live.client() as client:  # noqa: SIM117
        async with client.stream("GET", "/events", params={"token": ctx.token}) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            reader = api.SseReader(resp)
            await reader.until_comment("connected")
            route_paths = {getattr(r, "path", "") for r in live.app.routes}
            if "/threads/{id}/runs" in route_paths or "/threads/{thread_id}/runs" in route_paths:
                r = await client.post(
                    f"/threads/{thread_id}/runs",
                    json={"kind": "extract", "input": inp.model_dump(mode="json")},
                    headers=live.auth,
                )
                assert r.status_code in (200, 201, 202), r.text
            else:  # part B's route is not there yet
                await ctx.manager.submit(thread_id, "extract", inp)
            seen: list[dict[str, Any]] = []
            while True:
                event = await reader.next_event()
                seen.append(event)
                if event["type"] in ("run.done", "run.failed", "run.interrupted"):
                    break
    types = [e["type"] for e in seen]
    assert types[0] == "run.queued"
    assert types[-1] == "run.done", seen[-1]
    started = [i for i, t in enumerate(types) if t == "run.step_started"]
    assert len(started) >= 1
    assert started[0] == 1
    assert {e["run_id"] for e in seen} == {seen[0]["run_id"]}
    assert all(e["thread_id"] == thread_id for e in seen)


@pytest.mark.asyncio
async def test_r12_8_recovery_emits_run_interrupted_over_sse(
    make_ctx: Callable[..., AppContext], api: Any
) -> None:
    ctx = make_ctx()
    thread_id, inp = _extract_input(ctx, api.S1)
    conn = db.connect(ctx.paths.db)
    try:  # the state a crash leaves: a run still `running`, another `stopping`
        crashed = runs.create_run(conn, thread_id, "extract", inp).id
        runs.set_run_status(conn, crashed, "running")
        stopping = runs.create_run(conn, thread_id, "extract", inp).id
        runs.set_run_status(conn, stopping, "stopping")
    finally:
        conn.close()
    async with api.serving(ctx) as live, live.client() as client:  # noqa: SIM117
        async with client.stream("GET", "/events", headers=live.auth) as resp:
            reader = api.SseReader(resp)
            event = await reader.next_event()
    assert event == {"type": "run.interrupted", "run_id": crashed, "thread_id": thread_id}
    conn = db.connect(ctx.paths.db)
    try:
        assert runs.get_run(conn, crashed).status == "interrupted"  # type: ignore[union-attr]
        assert runs.get_run(conn, stopping).status == "stopped"  # type: ignore[union-attr]
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_published_events_keepalive_and_disconnect(
    make_ctx: Callable[..., AppContext], api: Any
) -> None:
    ctx = make_ctx()
    ctx.extra["sse_keepalive"] = 0.2
    async with api.serving(ctx) as live, live.client() as client:
        async with client.stream("GET", "/events", params={"token": ctx.token}) as resp:
            reader = api.SseReader(resp)
            await reader.until_comment("connected")
            assert ctx.hub is not None and ctx.hub.client_count == 1
            await reader.until_comment("keep-alive")
            sse.publish(ctx.events, "review.changed", open_count=3)
            sse.publish(ctx.events, "models.pull_progress", model="m", done=1, total=2)
            assert await reader.next_event() == {"type": "review.changed", "open_count": 3}
            event = await reader.next_event()
            assert event["type"] == "models.pull_progress" and event["done"] == 1
        async with asyncio.timeout(10):
            while ctx.hub.client_count:
                await asyncio.sleep(0.05)
            # Reconnecting with Last-Event-ID gets what came after it.
        async with client.stream(
            "GET", "/events", params={"token": ctx.token}, headers={"Last-Event-ID": "1"}
        ) as resp:
            reader = api.SseReader(resp)
            event = await reader.next_event()
            assert event["type"] == "models.pull_progress"


@pytest.mark.asyncio
async def test_events_wrong_query_token_is_401(
    make_ctx: Callable[..., AppContext], api: Any
) -> None:
    ctx = make_ctx()
    async with api.serving(ctx) as live, live.client() as client:
        r = await client.get("/events", params={"token": "wrong"})
        assert r.status_code == 401
        r = await client.get("/events")
        assert r.status_code == 401
        _ = httpx  # the module is used through live.client()


def test_format_event() -> None:
    text = sse.format_event(7, {"type": "run.done", "run_id": "r", "thread_id": "t"})
    assert text == (
        'id: 7\nevent: run.done\ndata: {"type":"run.done","run_id":"r","thread_id":"t"}\n\n'
    )
