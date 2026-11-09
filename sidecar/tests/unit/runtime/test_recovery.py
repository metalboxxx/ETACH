"""Startup recovery: a process killed mid-run (R7.2) and the status rules (R7.3)."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import support.toy_graph as toy_graph
from support.toy_graph import toy_input

from etach.domain.models import LlmCall
from etach.runtime import checkpoint
from etach.runtime.recovery import recover_rows
from etach.store import db
from etach.store.repos import runs, threads

TESTS_DIR = Path(__file__).resolve().parents[2]


def _read_until(proc: subprocess.Popen[str], marker: str, timeout: float = 60.0) -> list[str]:
    lines: list[str] = []
    done = threading.Event()

    def pump() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.append(line.strip())
            if line.strip() == marker:
                done.set()
                return
        done.set()

    threading.Thread(target=pump, daemon=True).start()
    done.wait(timeout)
    return lines


@pytest.mark.asyncio
async def test_r7_2_killed_subprocess_recovers_and_resumes(
    db_path: Path, conn: sqlite3.Connection, make_toy: Any
) -> None:
    thread = threads.create_thread(conn, "crash")
    run = runs.create_run(conn, thread.id, "extract", toy_input())
    env = {**os.environ, "PYTHONPATH": str(TESTS_DIR)}
    proc = subprocess.Popen(
        [sys.executable, toy_graph.__file__, str(db_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        lines = _read_until(proc, "HANG")
        assert "HANG" in lines, (lines, proc.poll())
    finally:
        proc.kill()
        proc.wait(timeout=30)
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()

    # the killed process left the rows as they were mid-call
    assert runs.get_run(conn, run.id).status == "running"  # type: ignore[union-attr]
    open_steps = [s for s in runs.list_steps(conn, run.id) if s.status == "running"]
    assert [(s.node, s.item) for s in open_steps] == [("pages", "page 2")]
    [streaming] = [
        c for c in runs.list_llm_calls(conn, open_steps[0].id) if c.status == "streaming"
    ]
    assert checkpoint.checkpoint_row_count(conn, run.id) > 0

    toy = await make_toy()  # a restart: recovery runs in start()

    after = toy.run(run.id)
    assert after.status == "interrupted"
    assert runs.get_step(conn, open_steps[0].id).status == "incomplete"  # type: ignore[union-attr]
    assert runs.get_llm_call(conn, streaming.id).status == "incomplete"  # type: ignore[union-attr]
    assert [e["type"] for e in toy.of(run.id)] == ["run.interrupted"]

    await toy.manager.resume(run.id)
    await toy.idle()

    assert toy.run(run.id).status == "done"
    page2 = [s for s in runs.list_steps(conn, run.id) if s.item == "page 2"]
    assert [(s.try_no, s.status) for s in page2] == [(1, "incomplete"), (2, "done")]
    done_steps = [s for s in runs.list_steps(conn, run.id) if s.status == "done"]
    assert len(done_steps) == len(toy_graph.TOY_STEPS)
    assert checkpoint.checkpoint_row_count(conn, run.id) == 0
    assert toy.recorder.final[run.id]["log"] == [
        f"{node}:{item}" for node, item in toy_graph.TOY_STEPS
    ]


def _streaming_call(conn: sqlite3.Connection, step_id: str) -> LlmCall:
    return runs.insert_llm_call(
        conn,
        LlmCall(
            id=db.new_ulid(),
            step_id=step_id,
            role="reasoning",
            model="m",
            prompt_hash="h",
            request={},
            response_text='{"val',
            thinking_text="",
            logprobs=None,
            status="streaming",
            tokens_in=None,
            tokens_out=None,
            ms=None,
            created_at=datetime.now(UTC),
        ),
    )


@pytest.mark.asyncio
async def test_r7_3_recovery_rules(conn: sqlite3.Connection, make_toy: Any) -> None:
    thread = threads.create_thread(conn, "t")
    stopping = runs.create_run(conn, thread.id, "extract", toy_input(), status="stopping")
    s1 = runs.start_step(conn, stopping.id, "pages", "page 1")
    c1 = _streaming_call(conn, s1.id)
    running = runs.create_run(conn, thread.id, "extract", toy_input(), status="running")
    s2 = runs.start_step(conn, running.id, "prepare", None)
    c2 = _streaming_call(conn, s2.id)
    queued = runs.create_run(conn, thread.id, "extract", toy_input())
    failed = runs.create_run(conn, thread.id, "extract", toy_input(), status="failed")

    toy = await make_toy()
    await toy.idle()

    assert toy.run(stopping.id).status == "stopped"
    assert toy.run(running.id).status == "interrupted"
    assert toy.run(queued.id).status == "done"  # stayed queued, then ran after the restart
    assert toy.run(failed.id).status == "failed"
    for s in (s1, s2):
        assert runs.get_step(conn, s.id).status == "incomplete"  # type: ignore[union-attr]
    for c in (c1, c2):
        row = runs.get_llm_call(conn, c.id)
        assert row is not None and row.status == "incomplete" and row.response_text == '{"val'
    assert [e["type"] for e in toy.of(running.id)] == ["run.interrupted"]
    assert toy.of(stopping.id) == []  # stopping -> stopped is silent (it was stopping already)
    assert [e["type"] for e in toy.of(queued.id)][-1] == "run.done"


def test_recover_rows_is_a_no_op_when_clean(conn: sqlite3.Connection) -> None:
    thread = threads.create_thread(conn, "t")
    runs.create_run(conn, thread.id, "extract", toy_input(), status="done")
    out = recover_rows(conn)
    assert (out.interrupted, out.stopped, out.steps_incomplete, out.calls_incomplete) == (
        [],
        [],
        [],
        [],
    )
