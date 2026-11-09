"""``answer_keys`` with the guarded upsert (data-model §2.4).

Precedence: ``teacher_edit`` source or ``teacher_verified`` status (3) > ``from_key_photo`` (2)
> ``ai`` (1). A write never replaces a row of higher precedence; an equal or higher one replaces
it (so verification can move ``ai_unverified`` to ``ai_verified``).

A key *change* is a change of ``accepted`` (the canonical answer and its variants). It deletes
that question's explanations, and nothing else. A status-only change (for example Review
"uncertain_key · accept" → ``teacher_verified``) keeps them (plan Appendix E).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal

from etach.domain import keys as key_rules
from etach.domain.models import AnswerKey, TestContent
from etach.store.db import dumps, transaction
from etach.store.repos import explanations
from etach.store.repos._common import from_row, to_row

__all__ = [
    "KeyWrite",
    "delete_key",
    "get_key",
    "list_keys",
    "precedence",
    "upgrade_key_forms",
    "upsert_key",
]

_JSON = ("accepted", "checker")


def precedence(key: AnswerKey) -> int:
    if key.source == "teacher_edit" or key.status == "teacher_verified":
        return 3
    if key.source == "from_key_photo":
        return 2
    return 1


@dataclass(frozen=True)
class KeyWrite:
    """What ``upsert_key`` did."""

    outcome: Literal["inserted", "updated", "unchanged", "blocked"]
    key_changed: bool  # ``accepted`` differs from before (or the row is new)
    explanations_deleted: int


def get_key(conn: sqlite3.Connection, test_id: str, question_id: str) -> AnswerKey | None:
    row = conn.execute(
        "SELECT * FROM answer_keys WHERE test_id = ? AND question_id = ?", (test_id, question_id)
    ).fetchone()
    return None if row is None else from_row(AnswerKey, row, _JSON)


def upgrade_key_forms(conn: sqlite3.Connection, test_id: str) -> int:
    """The one-time upgrade of migration 0006 (data-model v1.15): a test listed in
    ``key_forms_pending`` gets the sentence forms added to its existing keys, then leaves the
    list. ``updated_at`` and explanations are kept (the key text is unchanged). Returns the rows
    changed; a test not listed is left alone, so a form the teacher later removes stays removed."""
    if not conn.execute("SELECT 1 FROM key_forms_pending WHERE test_id = ?", (test_id,)).fetchone():
        return 0
    changed = 0
    with transaction(conn):
        row = conn.execute("SELECT content FROM tests WHERE id = ?", (test_id,)).fetchone()
        if row is not None:
            content = TestContent.model_validate_json(row[0])
            rows = conn.execute("SELECT * FROM answer_keys WHERE test_id = ?", (test_id,))
            for key in [from_row(AnswerKey, r, _JSON) for r in rows.fetchall()]:
                new = key_rules.key_with_forms(key, content)
                if new.accepted != key.accepted:
                    conn.execute(
                        "UPDATE answer_keys SET accepted = ? WHERE test_id = ? AND question_id = ?",
                        (dumps(new.accepted), test_id, key.question_id),
                    )
                    changed += 1
        conn.execute("DELETE FROM key_forms_pending WHERE test_id = ?", (test_id,))
    return changed


def list_keys(conn: sqlite3.Connection, test_id: str) -> list[AnswerKey]:
    upgrade_key_forms(conn, test_id)
    rows = conn.execute(
        "SELECT * FROM answer_keys WHERE test_id = ? ORDER BY question_id", (test_id,)
    ).fetchall()
    return [from_row(AnswerKey, r, _JSON) for r in rows]


def _same(a: AnswerKey, b: AnswerKey) -> bool:
    return a.model_dump(exclude={"updated_at"}) == b.model_dump(exclude={"updated_at"})


def upsert_key(conn: sqlite3.Connection, key: AnswerKey) -> KeyWrite:
    """Guarded upsert of one key row; see the module docstring for the rules."""
    row = to_row(key, _JSON)
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    with transaction(conn):
        old = get_key(conn, key.test_id, key.question_id)
        if old is not None:
            if precedence(key) < precedence(old):
                return KeyWrite("blocked", False, 0)
            if _same(key, old):
                return KeyWrite("unchanged", False, 0)
        conn.execute(
            f"INSERT OR REPLACE INTO answer_keys ({cols}) VALUES ({marks})", tuple(row.values())
        )
        changed = old is None or old.accepted != key.accepted
        deleted = (
            explanations.delete_for_question(conn, key.test_id, key.question_id) if changed else 0
        )
    return KeyWrite("inserted" if old is None else "updated", changed, deleted)


def delete_key(conn: sqlite3.Connection, test_id: str, question_id: str) -> bool:
    """Remove one key row and that question's explanations (the question left the content, e.g.
    a ``validator_failed`` content fix, or the teacher deleted the key, refinements D7). Any row
    goes, a teacher's too: with no row, the next ``ai_key_fast`` may write the question's key.
    Returns whether a row was removed."""
    with transaction(conn):
        cur = conn.execute(
            "DELETE FROM answer_keys WHERE test_id = ? AND question_id = ?", (test_id, question_id)
        )
        if cur.rowcount:
            explanations.delete_for_question(conn, test_id, question_id)
    return cur.rowcount == 1
