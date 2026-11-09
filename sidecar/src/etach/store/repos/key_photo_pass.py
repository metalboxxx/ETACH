"""The one-time first-start pass of migration 0015 over the stored keys (data-model v1.25,
step 22.5.6).

Before step 22.5.6 ``map_key`` stored a key read from the key photo as ``ai_verified`` when its
confidence was at least :data:`etach.domain.keymap.KEY_PHOTO_THRESHOLD` (0.7, unchanged since step
9A), with no second model call. ``verify_key`` checks only ``ai_unverified`` keys, and a key-photo
key is ``ai_unverified`` only below that threshold, so a key-photo key that a check verified
always has a confidence below it. Such a key is recognised by: ``source = 'from_key_photo'``,
``status = 'ai_verified'`` and ``confidence >= 0.7``. Exactly those rows get the status
``from_key_photo``; their confidence, ``accepted``, ``updated_at`` and explanations are kept, and
nothing else changes (no other row, column or table).

It runs only while ``key_photo_pending`` holds its row and removes the row in the same
transaction, so a second start changes nothing.
"""

from __future__ import annotations

import sqlite3

from etach.domain.keymap import KEY_PHOTO_THRESHOLD
from etach.store.db import transaction

__all__ = ["run_key_photo_pass"]


def run_key_photo_pass(conn: sqlite3.Connection) -> int | None:
    """The first-start pass (see the module docstring). Returns the keys moved, or ``None``
    when it did not run."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'key_photo_pending'"
    ).fetchone()
    if not exists or not conn.execute("SELECT 1 FROM key_photo_pending").fetchone():
        return None
    with transaction(conn):
        cur = conn.execute(
            "UPDATE answer_keys SET status = 'from_key_photo' WHERE source = 'from_key_photo'"
            " AND status = 'ai_verified' AND confidence IS NOT NULL AND confidence >= ?",
            (KEY_PHOTO_THRESHOLD,),
        )
        moved = cur.rowcount
        conn.execute("DELETE FROM key_photo_pending")
    return moved
