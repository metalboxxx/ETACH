"""The one-time first-start pass of migration 0013 over the stored tests (data-model v1.23,
step 22.5.4, decision D10: drop).

It runs only while ``difficulty_notes_pending`` holds its row and removes the row in the same
transaction, so a second start changes nothing. It works on the raw meta JSON (the removed field
no longer validates as a ``TestMetadata`` field) and removes the key
``test_difficulty_notice_comment_by_ai`` from every stored test's ``meta``. Nothing else changes:
not the other meta fields, ``updated_at``, the columns, the search rows or any other table.
It runs before the other first-start passes, which read tests through the models.
"""

from __future__ import annotations

import json
import sqlite3

from etach.store.db import transaction

__all__ = ["DROPPED_META_FIELD", "run_difficulty_notes_pass"]

#: The meta key the pass removes.
DROPPED_META_FIELD = "test_difficulty_notice_comment_by_ai"


def run_difficulty_notes_pass(conn: sqlite3.Connection) -> bool:
    """The first-start pass (see the module docstring). Returns whether it ran."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'difficulty_notes_pending'"
    ).fetchone()
    if not exists or not conn.execute("SELECT 1 FROM difficulty_notes_pending").fetchone():
        return False
    with transaction(conn):
        for test_id, raw in conn.execute("SELECT id, meta FROM tests ORDER BY id").fetchall():
            meta = json.loads(raw)
            if isinstance(meta, dict) and DROPPED_META_FIELD in meta:
                del meta[DROPPED_META_FIELD]
                conn.execute(
                    "UPDATE tests SET meta = ? WHERE id = ?",
                    (json.dumps(meta, ensure_ascii=False, separators=(",", ":")), test_id),
                )
        conn.execute("DELETE FROM difficulty_notes_pending")
    return True
