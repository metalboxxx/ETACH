"""``runs``, ``steps`` and ``llm_calls`` (data-model §2.7). IDs are ULIDs.

The run machinery (step 7) and the Ollama client (step 4) build on these; they only store rows.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, Literal

from etach.domain.models import ExtractInput, GradeInput, LlmCall, Run, Step
from etach.store.db import dumps, iso, new_ulid, transaction
from etach.store.repos._common import from_row, insert_model

__all__ = [
    "FINISHED_RUN_STATUSES",
    "LlmCallStatus",
    "RunStatus",
    "StepStatus",
    "close_open_steps",
    "create_run",
    "delete_llm_calls_before",
    "enqueue_extract",
    "enqueue_grade",
    "enqueue_key_run",
    "finish_step",
    "get_llm_call",
    "get_run",
    "get_step",
    "has_done_run",
    "insert_llm_call",
    "insert_step",
    "latest_step",
    "list_llm_calls",
    "list_runs",
    "list_runs_by_status",
    "list_steps",
    "purge_finished_checkpoints",
    "set_llm_call_counts",
    "set_llm_call_status",
    "set_run_status",
    "start_step",
    "update_llm_call_stream",
]

RunStatus = Literal[
    "queued", "running", "stopping", "stopped", "interrupted", "failed", "discarded", "done"
]
StepStatus = Literal["running", "done", "incomplete", "failed", "skipped"]
LlmCallStatus = Literal["streaming", "complete", "invalid", "incomplete", "cancelled", "error"]

_RUN_JSON = ("input",)
_CALL_JSON = ("request", "logprobs")


# --- runs ------------------------------------------------------------------------------------


def create_run(
    conn: sqlite3.Connection,
    thread_id: str,
    kind: Literal["extract", "grade"],
    run_input: ExtractInput | GradeInput,
    status: RunStatus = "queued",
) -> Run:
    run = Run(
        id=new_ulid(),
        thread_id=thread_id,
        kind=kind,
        input=run_input,
        status=status,
        started_at=None,
        finished_at=None,
        error=None,
    )
    with transaction(conn):
        insert_model(conn, "runs", run, _RUN_JSON)
    return run


def enqueue_grade(
    conn: sqlite3.Connection,
    *,
    test_id: str,
    attempt_id: str,
    reason: Literal["button", "key_verified", "merge", "review_fix", "points_fix"],
) -> str:
    """Queue a grade run on the attempt's thread (a Review follow-up, data-model §5.3). It only
    writes the row, inside the caller's transaction; the ``RunManager`` picks it up later."""
    row = conn.execute("SELECT thread_id FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    if row is None:
        raise KeyError(f"no attempt {attempt_id}")
    grade_input = GradeInput(test_id=test_id, attempt_id=attempt_id, reason=reason)
    return create_run(conn, row[0], "grade", grade_input).id


def enqueue_key_run(
    conn: sqlite3.Connection, *, thread_id: str, test_id: str, after_run_id: str
) -> str:
    """Queue the key run an extraction's save makes (step 22.6.4, D4): a grade run on the thread
    with ``attempt_id`` None and reason ``after_extract`` (the AI key for the questions without
    one, its check and the skill tags; no grading). Idempotent: when the thread already has an
    ``after_extract`` run created after ``after_run_id`` (the extract run), its id is returned and
    nothing is written. It only writes the row, inside the caller's transaction."""
    row = conn.execute(
        "SELECT id FROM runs WHERE thread_id = ? AND kind = 'grade' AND id > ?"
        " AND json_extract(input, '$.reason') = 'after_extract' ORDER BY id LIMIT 1",
        (thread_id, after_run_id),
    ).fetchone()
    if row is not None:
        return str(row[0])
    grade_input = GradeInput(test_id=test_id, attempt_id=None, reason="after_extract")
    return create_run(conn, thread_id, "grade", grade_input).id


def enqueue_extract(conn: sqlite3.Connection, *, thread_id: str, input: ExtractInput) -> str:
    """Queue an extract run on ``thread_id`` (e.g. ``picked_test_mismatch`` accept). It only
    writes the row, inside the caller's transaction."""
    return create_run(conn, thread_id, "extract", input).id


def get_run(conn: sqlite3.Connection, run_id: str) -> Run | None:
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return None if row is None else from_row(Run, row, _RUN_JSON)


def list_runs(
    conn: sqlite3.Connection, *, thread_id: str | None = None, status: RunStatus | None = None
) -> list[Run]:
    where: list[str] = []
    args: list[str] = []
    if thread_id is not None:
        where.append("thread_id = ?")
        args.append(thread_id)
    if status is not None:
        where.append("status = ?")
        args.append(status)
    sql = "SELECT * FROM runs" + (" WHERE " + " AND ".join(where) if where else "")
    return [from_row(Run, r, _RUN_JSON) for r in conn.execute(sql + " ORDER BY id", args)]


def set_run_status(
    conn: sqlite3.Connection,
    run_id: str,
    status: RunStatus,
    *,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    error: str | None = None,
) -> None:
    """Set the status; the timestamps and error are written only when given."""
    sets = ["status = ?"]
    args: list[object] = [status]
    if started_at is not None:
        sets.append("started_at = ?")
        args.append(iso(started_at))
    if finished_at is not None:
        sets.append("finished_at = ?")
        args.append(iso(finished_at))
    if error is not None:
        sets.append("error = ?")
        args.append(error)
    with transaction(conn):
        cur = conn.execute(f"UPDATE runs SET {', '.join(sets)} WHERE id = ?", (*args, run_id))
        if cur.rowcount != 1:
            raise KeyError(f"no run {run_id}")


# --- steps -----------------------------------------------------------------------------------


def insert_step(
    conn: sqlite3.Connection, run_id: str, node: str, item: str | None, try_no: int
) -> Step:
    step = Step(
        id=new_ulid(),
        run_id=run_id,
        node=node,
        item=item,
        try_no=try_no,
        status="running",
        started_at=datetime.now(UTC),
        finished_at=None,
    )
    with transaction(conn):
        insert_model(conn, "steps", step)
    return step


def finish_step(conn: sqlite3.Connection, step_id: str, status: StepStatus) -> None:
    with transaction(conn):
        cur = conn.execute(
            "UPDATE steps SET status = ?, finished_at = ? WHERE id = ?",
            (status, iso(datetime.now(UTC)), step_id),
        )
        if cur.rowcount != 1:
            raise KeyError(f"no step {step_id}")


def start_step(conn: sqlite3.Connection, run_id: str, node: str, item: str | None) -> Step:
    """Insert a ``running`` step whose ``try_no`` is the number of earlier rows for the same
    ``(run, node, item)`` + 1 (a node restarted after Stop gets a new row, llm-design §7)."""
    with transaction(conn):
        (tries,) = conn.execute(
            "SELECT COUNT(*) FROM steps WHERE run_id = ? AND node = ? AND item IS ?",
            (run_id, node, item),
        ).fetchone()
        return insert_step(conn, run_id, node, item, int(tries) + 1)


def close_open_steps(
    conn: sqlite3.Connection, status: StepStatus, run_id: str | None = None
) -> list[str]:
    """Set every ``running`` step (of ``run_id``, or of all runs) to ``status``; returns their
    IDs. Used when a run's task ends and by startup recovery."""
    where = "status = 'running'" + (" AND run_id = ?" if run_id is not None else "")
    args: tuple[str, ...] = (run_id,) if run_id is not None else ()
    with transaction(conn):
        ids = [r[0] for r in conn.execute(f"SELECT id FROM steps WHERE {where}", args)]
        conn.executemany(
            "UPDATE steps SET status = ?, finished_at = ? WHERE id = ?",
            [(status, iso(datetime.now(UTC)), i) for i in ids],
        )
    return ids


def get_step(conn: sqlite3.Connection, step_id: str) -> Step | None:
    row = conn.execute("SELECT * FROM steps WHERE id = ?", (step_id,)).fetchone()
    return None if row is None else from_row(Step, row)


def list_steps(conn: sqlite3.Connection, run_id: str) -> list[Step]:
    rows = conn.execute(
        "SELECT * FROM steps WHERE run_id = ? ORDER BY started_at, id", (run_id,)
    ).fetchall()
    return [from_row(Step, r) for r in rows]


# --- llm_calls -------------------------------------------------------------------------------


def insert_llm_call(conn: sqlite3.Connection, call: LlmCall) -> LlmCall:
    """Insert a call row built by the caller (its ``id`` from ``etach.store.db.new_ulid``)."""
    with transaction(conn):
        insert_model(conn, "llm_calls", call, _CALL_JSON)
    return call


def get_llm_call(conn: sqlite3.Connection, call_id: str) -> LlmCall | None:
    row = conn.execute("SELECT * FROM llm_calls WHERE id = ?", (call_id,)).fetchone()
    return None if row is None else from_row(LlmCall, row, _CALL_JSON)


def list_llm_calls(conn: sqlite3.Connection, step_id: str) -> list[LlmCall]:
    rows = conn.execute(
        "SELECT * FROM llm_calls WHERE step_id = ? ORDER BY created_at, id", (step_id,)
    ).fetchall()
    return [from_row(LlmCall, r, _CALL_JSON) for r in rows]


def update_llm_call_stream(
    conn: sqlite3.Connection,
    call_id: str,
    *,
    response_text: str,
    thinking_text: str,
    logprobs: list[Any] | None,
) -> bool:
    """Write the streamed text so far; only while the row is still ``streaming`` (a late flush
    after the final status is a no-op). Returns whether the row was updated."""
    with transaction(conn):
        cur = conn.execute(
            "UPDATE llm_calls SET response_text = ?, thinking_text = ?, logprobs = ?"
            " WHERE id = ? AND status = 'streaming'",
            (response_text, thinking_text, None if logprobs is None else dumps(logprobs), call_id),
        )
    return cur.rowcount == 1


def set_llm_call_status(conn: sqlite3.Connection, call_id: str, status: LlmCallStatus) -> None:
    with transaction(conn):
        cur = conn.execute("UPDATE llm_calls SET status = ? WHERE id = ?", (status, call_id))
        if cur.rowcount != 1:
            raise KeyError(f"no llm_call {call_id}")


def set_llm_call_counts(
    conn: sqlite3.Connection,
    call_id: str,
    *,
    tokens_in: int | None,
    tokens_out: int | None,
    ms: int | None,
) -> None:
    """The final counts: prompt and output tokens, and the duration in milliseconds."""
    with transaction(conn):
        cur = conn.execute(
            "UPDATE llm_calls SET tokens_in = ?, tokens_out = ?, ms = ? WHERE id = ?",
            (tokens_in, tokens_out, ms, call_id),
        )
        if cur.rowcount != 1:
            raise KeyError(f"no llm_call {call_id}")


def list_runs_by_status(conn: sqlite3.Connection, statuses: Iterable[RunStatus]) -> list[Run]:
    """Runs in any of ``statuses``, oldest first (``GET /runs/active``)."""
    wanted = list(statuses)
    if not wanted:
        return []
    marks = ", ".join("?" for _ in wanted)
    rows = conn.execute(f"SELECT * FROM runs WHERE status IN ({marks}) ORDER BY id", wanted)
    return [from_row(Run, r, _RUN_JSON) for r in rows]


def latest_step(conn: sqlite3.Connection, run_id: str) -> Step | None:
    """The run's most recently started step (the running indicator's "current step")."""
    row = conn.execute(
        "SELECT * FROM steps WHERE run_id = ? ORDER BY started_at DESC, rowid DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    return None if row is None else from_row(Step, row)


def has_done_run(
    conn: sqlite3.Connection, thread_id: str, kind: Literal["extract", "grade"]
) -> bool:
    """Whether the thread has a ``done`` run of ``kind`` (D18: one extract per thread)."""
    row = conn.execute(
        "SELECT 1 FROM runs WHERE thread_id = ? AND kind = ? AND status = 'done' LIMIT 1",
        (thread_id, kind),
    ).fetchone()
    return row is not None


def delete_llm_calls_before(conn: sqlite3.Connection, cutoff: datetime) -> int:
    """Delete the ``llm_calls`` created before ``cutoff`` that no ``explanations.llm_call_id``
    references (data-model §5.5); returns how many were deleted."""
    # The date filter runs in SQL: ``julianday`` parses the stored ISO-8601 text (``Z`` or an
    # offset, any number of fractional digits), so no row is loaded into Python.
    if cutoff.tzinfo is None:
        raise ValueError("cutoff must be timezone-aware")
    with transaction(conn):
        cur = conn.execute(
            "DELETE FROM llm_calls WHERE julianday(created_at) < julianday(?) AND NOT EXISTS "
            "(SELECT 1 FROM explanations e WHERE e.llm_call_id = llm_calls.id)",
            (iso(cutoff),),
        )
    return cur.rowcount


FINISHED_RUN_STATUSES = ("done", "failed", "discarded")


def purge_finished_checkpoints(conn: sqlite3.Connection) -> int:
    """Delete the LangGraph checkpoints and pending writes (tables ``checkpoints`` /
    ``writes``, keyed by ``thread_id`` = the run ID) of every run that is ``done``, ``failed``
    or ``discarded`` (data-model §5.5); returns the rows deleted. A finished run cannot resume,
    so its checkpoint is dead weight (the run manager purges ``done``/``discarded`` itself; this
    catches ``failed`` and anything a crash left behind). Missing tables are fine."""
    marks = ", ".join("?" for _ in FINISHED_RUN_STATUSES)
    total = 0
    with transaction(conn):
        for table in ("checkpoints", "writes"):
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
            ).fetchone()
            if not exists:
                continue
            total += conn.execute(
                f"DELETE FROM {table} WHERE thread_id IN "
                f"(SELECT id FROM runs WHERE status IN ({marks}))",
                FINISHED_RUN_STATUSES,
            ).rowcount
    return total
