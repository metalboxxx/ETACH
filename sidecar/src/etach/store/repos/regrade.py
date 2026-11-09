"""``regrade_pending`` (data-model v1.20, PRD v8.1 "Re-grade after checking keys").

A teacher key change no longer queues ``key_verified`` runs at once: :func:`mark` notes the test
(only when it has graded attempts), and :func:`start` (``POST /tests/{id}/regrade``) queues one
grade run per graded attempt and deletes the row. Deleting the test deletes the row
(``ON DELETE CASCADE``).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from etach.store.db import iso, transaction
from etach.store.repos import attempts, runs

__all__ = ["is_pending", "mark", "start"]


def mark(conn: sqlite3.Connection, test_id: str) -> bool:
    """Note that the test's keys changed. Returns True when the test is (now) pending; a test
    with no graded attempt gets no row (nothing to re-grade). Writes inside the caller's
    transaction when there is one."""
    if not attempts.graded_attempts(conn, test_id):
        return False
    with transaction(conn):
        conn.execute(
            "INSERT OR IGNORE INTO regrade_pending (test_id, since) VALUES (?, ?)",
            (test_id, iso(datetime.now(UTC))),
        )
    return True


def is_pending(conn: sqlite3.Connection, test_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM regrade_pending WHERE test_id = ?", (test_id,)).fetchone()
    return row is not None


def start(conn: sqlite3.Connection, test_id: str) -> list[str]:
    """Queue 1 grade run (``key_verified``) per graded attempt and clear the row. Nothing pending
    → no run. Returns the new run ids."""
    with transaction(conn):
        cur = conn.execute("DELETE FROM regrade_pending WHERE test_id = ?", (test_id,))
        if cur.rowcount == 0:
            return []
        return [
            runs.enqueue_grade(conn, test_id=test_id, attempt_id=a, reason="key_verified")
            for a in attempts.graded_attempts(conn, test_id)
        ]
