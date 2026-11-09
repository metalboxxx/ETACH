"""Step 22.1.3, R22.1.3.3: ``GET /runs/active`` gives ``stage``, ``stages``, ``stage_label`` and
``percent`` for a running and a stopped run (the S1 replay, held at its third model call), and
after Resume the first event's ``percent`` is not lower than the stopped value. No route is added
(R12.1 is ``test_route_table.py``)."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import AsyncGenerator, Callable, Mapping
from typing import Any

import pytest

from etach.api.deps import AppContext
from etach.cli import _page_inputs
from etach.domain import models as m
from etach.graphs.extract import EXTRACT_STAGES
from etach.llm.cassettes import ReplayBackend
from etach.runtime.events import Event
from etach.store import db
from etach.store.files import FileStore

PROGRESS_TYPES = ("run.step_started", "run.progress", "run.done")


class HeldBackend:
    """The S1 replay, held before its ``hold_at``-th call (0-based) until ``release``."""

    def __init__(self, inner: ReplayBackend, hold_at: int) -> None:
        self.inner = inner
        self.hold_at = hold_at
        self.calls = 0
        self.held = asyncio.Event()
        self.release = asyncio.Event()

    async def stream(
        self, body: Mapping[str, Any], *, task: str, match_key: str
    ) -> AsyncGenerator[dict[str, Any]]:
        n = self.calls
        self.calls += 1
        if n == self.hold_at:
            self.held.set()
            await self.release.wait()
        async for chunk in self.inner.stream(body, task=task, match_key=match_key):
            yield chunk


def _extract_input(ctx: AppContext, s1: Any) -> dict[str, Any]:
    conn = db.connect(ctx.paths.db)
    try:
        files = FileStore(conn, ctx.paths)
        pages, manifest = _page_inputs(argparse.Namespace(pages=[], key=[], replay=s1), files)
    finally:
        conn.close()
    return m.ExtractInput(
        pages=pages,
        existing_test_id=manifest.existing_test_id,
        supersedes_attempt_id=manifest.supersedes_attempt_id,
    ).model_dump(mode="json")


def _row(rows: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    [row] = [r for r in rows if r["run"]["id"] == run_id]
    return row


def _check_fields(row: dict[str, Any]) -> None:
    assert row["stages"] == len(EXTRACT_STAGES)
    assert 1 <= row["stage"] <= row["stages"]
    assert row["stage_label"] == EXTRACT_STAGES[row["stage"] - 1].label
    assert 0 <= row["percent"] < 100
    assert row["current_step"]["node"] in EXTRACT_STAGES[row["stage"] - 1].nodes


@pytest.mark.asyncio
async def test_r22_1_3_3_active_runs_carry_progress(
    make_ctx: Callable[..., AppContext], api: Any
) -> None:
    backend = HeldBackend(ReplayBackend.from_dir(api.S1), hold_at=2)  # page 3's transcription
    ctx = make_ctx(backend=backend)
    log: list[Event] = []
    ctx.events.add_listener(log.append)
    inp = _extract_input(ctx, api.S1)
    async with api.serving(ctx) as live, live.client() as client:
        auth = live.auth
        thread_id = (await client.post("/threads", json={}, headers=auth)).json()["thread_id"]
        r = await client.post(
            f"/threads/{thread_id}/runs", json={"kind": "extract", "input": inp}, headers=auth
        )
        assert r.status_code == 200, r.text
        run_id = r.json()["id"]
        await asyncio.wait_for(backend.held.wait(), 60)

        # running
        row = _row((await client.get("/runs/active", headers=auth)).json(), run_id)
        assert row["run"]["status"] == "running"
        _check_fields(row)
        assert row["stage_label"] == "Reading the test"
        published = [e["percent"] for e in log if e["type"] in PROGRESS_TYPES and "percent" in e]
        assert row["percent"] == published[-1] > 0

        # stopped
        r = await client.post(f"/runs/{run_id}/stop", headers=auth)
        assert r.status_code == 200 and r.json()["status"] == "stopped", r.text
        stopped = _row((await client.get("/runs/active", headers=auth)).json(), run_id)
        assert stopped["run"]["status"] == "stopped"
        _check_fields(stopped)
        assert stopped["percent"] == row["percent"]

        # resumed: the first event is not lower, and run.done is 100
        backend.release.set()
        before = len(log)
        r = await client.post(f"/runs/{run_id}/resume", headers=auth)
        assert r.status_code == 200, r.text
        async with asyncio.timeout(60):
            while not any(e["type"] == "run.done" for e in log[before:]):
                await asyncio.sleep(0.05)
        after = [
            e["percent"]
            for e in log[before:]
            if e.get("run_id") == run_id and e["type"] in PROGRESS_TYPES and "percent" in e
        ]
        assert after[0] >= stopped["percent"]
        assert after == sorted(after) and after[-1] == 100
        rows = (await client.get("/runs/active", headers=auth)).json()
        assert all(r["run"]["id"] != run_id for r in rows)
