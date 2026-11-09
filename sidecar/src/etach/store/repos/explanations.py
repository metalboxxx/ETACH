"""``explanations``, the explanation cache (data-model §2.6)."""

from __future__ import annotations

import sqlite3

from etach.domain.models import Explanation
from etach.store.db import transaction
from etach.store.repos._common import from_row, to_row

__all__ = [
    "delete_for_question",
    "get_explanation",
    "list_explanations",
    "upsert_explanation",
]


def upsert_explanation(conn: sqlite3.Connection, explanation: Explanation) -> None:
    """Insert or replace the cached explanation for (test, question, wrong answer)."""
    row = to_row(explanation)
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    with transaction(conn):
        conn.execute(
            f"INSERT OR REPLACE INTO explanations ({cols}) VALUES ({marks})", tuple(row.values())
        )


def get_explanation(
    conn: sqlite3.Connection, test_id: str, question_id: str, wrong_answer_norm: str
) -> Explanation | None:
    row = conn.execute(
        "SELECT * FROM explanations WHERE test_id = ? AND question_id = ?"
        " AND wrong_answer_norm = ?",
        (test_id, question_id, wrong_answer_norm),
    ).fetchone()
    return None if row is None else from_row(Explanation, row)


def list_explanations(conn: sqlite3.Connection, test_id: str) -> list[Explanation]:
    rows = conn.execute(
        "SELECT * FROM explanations WHERE test_id = ? ORDER BY question_id, wrong_answer_norm",
        (test_id,),
    ).fetchall()
    return [from_row(Explanation, r) for r in rows]


def delete_for_question(conn: sqlite3.Connection, test_id: str, question_id: str) -> int:
    """Delete one question's explanations (its key changed, data-model §2.4). Returns the count."""
    with transaction(conn):
        cur = conn.execute(
            "DELETE FROM explanations WHERE test_id = ? AND question_id = ?",
            (test_id, question_id),
        )
    return cur.rowcount
