"""runs, steps, llm_calls."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

from etach.domain import models as m
from etach.store.repos import runs


def test_runs_steps_calls(conn: sqlite3.Connection, f: Any) -> None:
    run = f.make_run(conn)
    assert runs.get_run(conn, run.id) == run
    assert isinstance(run.input, m.ExtractInput)
    grade_input = m.GradeInput(test_id="T-0001", attempt_id=None, reason="button")
    grade = runs.create_run(conn, run.thread_id, "grade", grade_input)
    got = runs.get_run(conn, grade.id)
    assert got is not None and got.input == grade_input
    started = datetime(2026, 1, 1, tzinfo=UTC)
    runs.set_run_status(
        conn, run.id, "failed", started_at=started, finished_at=started, error="boom"
    )
    got = runs.get_run(conn, run.id)
    assert got is not None and (got.status, got.started_at, got.error) == (
        "failed",
        started,
        "boom",
    )
    assert [r.id for r in runs.list_runs(conn, status="queued")] == [grade.id]
    step = runs.insert_step(conn, run.id, "transcribe_page", "page 2", 1)
    runs.finish_step(conn, step.id, "done")
    done = runs.get_step(conn, step.id)
    assert done is not None and done.status == "done" and done.finished_at is not None
    assert runs.list_steps(conn, run.id) == [done]
    call = f.make_llm_call(conn)
    assert runs.get_llm_call(conn, call.id) == call
    assert runs.list_llm_calls(conn, call.step_id) == [call]
