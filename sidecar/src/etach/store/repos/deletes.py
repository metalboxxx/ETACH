"""Deleting a thread, a test or a student for good (data-model §5.7, v1.10; teacher's decisions
B1, B2; a student: v1.14, decision D1).

Each delete is one transaction. ``files`` rows and files on disk are left to the sweep
(data-model §5.5). Foreign keys are on (``etach.store.db.connect``), so every row that points at a
deleted row is removed first or, where it belongs to something that stays, has its pointer
cleared:

- ``attempts.superseded_by`` of a kept attempt → ``NULL``;
- ``review_items.followup_run_id`` of a kept item (a test-level item whose follow-up ran in the
  deleted thread) → ``NULL``;
- ``explanations.llm_call_id`` of a kept explanation → ``NULL``: ``llm_calls.step_id`` is
  ``NOT NULL REFERENCES steps`` and ``steps.run_id`` → ``runs.thread_id`` → ``threads``, so a
  deleted thread's calls cannot outlive its runs; the explanation text stays;
- ``tests.parent_test_id`` of a kept test → ``NULL``.

``llm_calls`` of runs in a deleted thread go with the runs (see above); every other call is kept
until its retention ends.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from etach.store.db import transaction
from etach.store.repos.runs import FINISHED_RUN_STATUSES

CHECKPOINT_TABLES = ("checkpoints", "writes")  # LangGraph SqliteSaver (etach.runtime.checkpoint)

__all__ = [
    "StudentDeletePlan",
    "TestDeletePlan",
    "active_runs_for_student",
    "active_runs_for_test",
    "active_runs_for_thread",
    "count_attempts",
    "count_student_attempts",
    "delete_student",
    "delete_test",
    "delete_thread",
    "plan_student_delete",
    "plan_test_delete",
]


def _marks(values: Sequence[object]) -> str:
    return ", ".join("?" for _ in values)


def _ids(conn: sqlite3.Connection, sql: str, params: Sequence[object]) -> list[str]:
    return [r[0] for r in conn.execute(sql, tuple(params)).fetchall()]


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?", (name,)
    ).fetchone()
    return row is not None


def _active(conn: sqlite3.Connection, where: str, params: Sequence[object]) -> list[str]:
    fin = FINISHED_RUN_STATUSES
    return _ids(
        conn,
        f"SELECT id FROM runs WHERE status NOT IN ({_marks(fin)}) AND ({where}) ORDER BY id",
        (*fin, *params),
    )


def active_runs_for_thread(conn: sqlite3.Connection, thread_id: str) -> list[str]:
    """The thread's runs that are queued, running, stopping or stopped/interrupted (resumable)."""
    return _active(conn, "thread_id = ?", (thread_id,))


# --- attempts --------------------------------------------------------------------------------


def _delete_attempts(conn: sqlite3.Connection, attempt_ids: list[str]) -> None:
    if not attempt_ids:
        return
    m = _marks(attempt_ids)
    conn.execute(
        f"UPDATE attempts SET superseded_by = NULL WHERE superseded_by IN ({m})", attempt_ids
    )
    for table in ("review_items", "answers", "attempt_pages", "grade_reports"):
        conn.execute(f"DELETE FROM {table} WHERE attempt_id IN ({m})", attempt_ids)
    conn.execute(f"DELETE FROM attempts WHERE id IN ({m})", attempt_ids)


# --- threads ---------------------------------------------------------------------------------


def _delete_threads(conn: sqlite3.Connection, thread_ids: list[str]) -> None:
    if not thread_ids:
        return
    m = _marks(thread_ids)
    _delete_attempts(
        conn, _ids(conn, f"SELECT id FROM attempts WHERE thread_id IN ({m})", thread_ids)
    )
    run_ids = _ids(conn, f"SELECT id FROM runs WHERE thread_id IN ({m})", thread_ids)
    if run_ids:
        rm = _marks(run_ids)
        conn.execute(
            f"UPDATE review_items SET followup_run_id = NULL WHERE followup_run_id IN ({rm})",
            run_ids,
        )
        conn.execute(f"DELETE FROM grade_reports WHERE run_id IN ({rm})", run_ids)
        calls = (
            "SELECT c.id FROM llm_calls c JOIN steps s ON s.id = c.step_id "
            f"WHERE s.run_id IN ({rm})"
        )
        conn.execute(
            f"UPDATE explanations SET llm_call_id = NULL WHERE llm_call_id IN ({calls})", run_ids
        )
        conn.execute(
            f"DELETE FROM llm_calls WHERE step_id IN (SELECT id FROM steps WHERE run_id IN ({rm}))",
            run_ids,
        )
        conn.execute(f"DELETE FROM steps WHERE run_id IN ({rm})", run_ids)
        for table in CHECKPOINT_TABLES:
            if _table_exists(conn, table):
                conn.execute(f"DELETE FROM {table} WHERE thread_id IN ({rm})", run_ids)
        conn.execute(f"DELETE FROM runs WHERE id IN ({rm})", run_ids)
    conn.execute(f"DELETE FROM messages WHERE thread_id IN ({m})", thread_ids)
    conn.execute(f"DELETE FROM threads WHERE id IN ({m})", thread_ids)


def delete_thread(conn: sqlite3.Connection, thread_id: str) -> None:
    """Delete the thread and everything data-model §5.7 lists, in one transaction. The caller
    checks that it exists and has no active run."""
    with transaction(conn):
        _delete_threads(conn, [thread_id])


# --- tests -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class TestDeletePlan:
    """What ``DELETE /tests/{id}`` removes: the test and the tests merged into it, the threads
    that go whole, and the attempts deleted alone inside threads that stay."""

    __test__ = False  # not a pytest class

    test_ids: list[str]
    thread_ids: list[str]
    kept_thread_ids: list[str]
    lone_attempt_ids: list[str]


def _merged_closure(conn: sqlite3.Connection, test_id: str) -> list[str]:
    found = [test_id]
    frontier = [test_id]
    while frontier:
        nxt = _ids(
            conn, f"SELECT id FROM tests WHERE merged_into IN ({_marks(frontier)})", frontier
        )
        nxt = [t for t in nxt if t not in found]
        found.extend(nxt)
        frontier = nxt
    return found


def plan_test_delete(conn: sqlite3.Connection, test_id: str) -> TestDeletePlan:
    test_ids = _merged_closure(conn, test_id)
    m = _marks(test_ids)
    touched = _ids(
        conn,
        f"SELECT DISTINCT thread_id FROM attempts WHERE test_id IN ({m}) "
        f"UNION SELECT id FROM threads WHERE test_id IN ({m})",
        (*test_ids, *test_ids),
    )
    whole: list[str] = []
    kept: list[str] = []
    for tid in sorted(touched):
        other = conn.execute(
            f"SELECT 1 FROM attempts WHERE thread_id = ? AND test_id NOT IN ({m}) LIMIT 1",
            (tid, *test_ids),
        ).fetchone()
        (kept if other else whole).append(tid)
    lone: list[str] = []
    if kept:
        km = _marks(kept)
        lone = _ids(
            conn,
            f"SELECT id FROM attempts WHERE thread_id IN ({km}) AND test_id IN ({m}) ORDER BY id",
            (*kept, *test_ids),
        )
    return TestDeletePlan(test_ids, whole, kept, lone)


def active_runs_for_test(conn: sqlite3.Connection, plan: TestDeletePlan) -> list[str]:
    """Active runs in the threads the delete touches, or whose input names one of the tests."""
    threads_ = [*plan.thread_ids, *plan.kept_thread_ids]
    clauses: list[str] = []
    params: list[object] = []
    if threads_:
        clauses.append(f"thread_id IN ({_marks(threads_)})")
        params.extend(threads_)
    for t in plan.test_ids:
        clauses.append("instr(input, ?) > 0")
        params.append(f'"{t}"')
    return _active(conn, " OR ".join(clauses), params)


def _retarget_kept_threads(conn: sqlite3.Connection, thread_ids: Iterable[str]) -> None:
    for tid in thread_ids:
        row = conn.execute(
            "SELECT test_id FROM attempts WHERE thread_id = ? AND superseded_by IS NULL "
            "ORDER BY created_at DESC, id DESC LIMIT 1",
            (tid,),
        ).fetchone()
        conn.execute("UPDATE threads SET test_id = ? WHERE id = ?", (row[0] if row else None, tid))


def delete_test(conn: sqlite3.Connection, plan: TestDeletePlan) -> None:
    """Delete what ``plan`` names (data-model §5.7), in one transaction."""
    with transaction(conn):
        _delete_threads(conn, plan.thread_ids)
        _delete_attempts(conn, plan.lone_attempt_ids)
        _retarget_kept_threads(conn, plan.kept_thread_ids)
        ids = plan.test_ids
        m = _marks(ids)
        # Attempts in other threads on these tests cannot exist after the plan; stay safe.
        _delete_attempts(conn, _ids(conn, f"SELECT id FROM attempts WHERE test_id IN ({m})", ids))
        conn.execute(f"UPDATE threads SET test_id = NULL WHERE test_id IN ({m})", ids)
        for table in (
            "review_items",
            "explanations",
            "question_tags",
            "answer_keys",
            "test_pages",
            "test_key_pages",
        ):
            conn.execute(f"DELETE FROM {table} WHERE test_id IN ({m})", ids)
        if _table_exists(conn, "tests_fts"):
            conn.execute(f"DELETE FROM tests_fts WHERE test_id IN ({m})", ids)
        conn.execute(
            f"UPDATE tests SET parent_test_id = NULL WHERE parent_test_id IN ({m}) "
            f"AND id NOT IN ({m})",
            (*ids, *ids),
        )
        conn.execute(f"UPDATE tests SET merged_into = NULL WHERE id IN ({m})", ids)
        conn.execute(f"UPDATE tests SET parent_test_id = NULL WHERE id IN ({m})", ids)
        conn.execute(f"DELETE FROM tests WHERE id IN ({m})", ids)


def count_attempts(conn: sqlite3.Connection, plan: TestDeletePlan) -> int:
    """How many attempts ``delete_test(plan)`` removes."""
    m = _marks(plan.test_ids)
    clauses = [f"test_id IN ({m})"]
    params: list[object] = [*plan.test_ids]
    if plan.thread_ids:
        clauses.append(f"thread_id IN ({_marks(plan.thread_ids)})")
        params.extend(plan.thread_ids)
    sql = f"SELECT COUNT(*) FROM attempts WHERE {' OR '.join(clauses)}"
    return int(conn.execute(sql, params).fetchone()[0])


# --- students (data-model §5.7 v1.14, decision D1) ------------------------------------------


@dataclass(frozen=True)
class StudentDeletePlan:
    """What ``DELETE /students/{id}`` removes: the threads that go whole (every attempt in them
    is this student's or has no student), and this student's attempts inside threads that stay
    because another student has an attempt there."""

    student_id: str
    thread_ids: list[str]
    kept_thread_ids: list[str]
    lone_attempt_ids: list[str]


def plan_student_delete(conn: sqlite3.Connection, student_id: str) -> StudentDeletePlan:
    touched = _ids(
        conn,
        "SELECT DISTINCT thread_id FROM attempts WHERE student_id = ? ORDER BY thread_id",
        (student_id,),
    )
    whole: list[str] = []
    kept: list[str] = []
    for tid in touched:
        other = conn.execute(
            "SELECT 1 FROM attempts WHERE thread_id = ? AND student_id IS NOT NULL "
            "AND student_id != ? LIMIT 1",
            (tid, student_id),
        ).fetchone()
        (kept if other else whole).append(tid)
    lone: list[str] = []
    if kept:
        lone = _ids(
            conn,
            f"SELECT id FROM attempts WHERE thread_id IN ({_marks(kept)}) AND student_id = ? "
            "ORDER BY id",
            (*kept, student_id),
        )
    return StudentDeletePlan(student_id, whole, kept, lone)


def active_runs_for_student(conn: sqlite3.Connection, plan: StudentDeletePlan) -> list[str]:
    """Active runs in the threads the delete touches."""
    threads_ = [*plan.thread_ids, *plan.kept_thread_ids]
    if not threads_:
        return []
    return _active(conn, f"thread_id IN ({_marks(threads_)})", threads_)


def count_student_attempts(conn: sqlite3.Connection, plan: StudentDeletePlan) -> int:
    """How many attempts ``delete_student(plan)`` removes."""
    params: list[object] = [plan.student_id]
    sql = "SELECT COUNT(*) FROM attempts WHERE student_id = ?"
    if plan.thread_ids:
        sql += f" OR thread_id IN ({_marks(plan.thread_ids)})"
        params.extend(plan.thread_ids)
    return int(conn.execute(sql, params).fetchone()[0])


def delete_student(conn: sqlite3.Connection, plan: StudentDeletePlan) -> None:
    """Delete what ``plan`` names and then the student (data-model §5.7), in one transaction."""
    with transaction(conn):
        _delete_threads(conn, plan.thread_ids)
        _delete_attempts(conn, plan.lone_attempt_ids)
        _retarget_kept_threads(conn, plan.kept_thread_ids)
        # Attempts outside the plan cannot exist; stay safe so the foreign key holds.
        _delete_attempts(
            conn, _ids(conn, "SELECT id FROM attempts WHERE student_id = ?", (plan.student_id,))
        )
        conn.execute("DELETE FROM students WHERE id = ?", (plan.student_id,))
