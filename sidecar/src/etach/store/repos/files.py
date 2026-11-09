"""``files`` rows (data-model §2.8). The content-addressed store on disk is ``etach.store.files``
(step 3); this module only stores and reads the rows. The ID is the file's sha256."""

from __future__ import annotations

import sqlite3

from etach.domain.models import File
from etach.store.db import transaction
from etach.store.repos._common import from_row, insert_model

__all__ = ["fill_original_name", "get_file", "insert_file", "list_files"]


def insert_file(conn: sqlite3.Connection, file: File) -> File:
    """Insert the row unless one with the same ID (same content) exists; returns the stored row."""
    with transaction(conn):
        if conn.execute("SELECT 1 FROM files WHERE id = ?", (file.id,)).fetchone() is None:
            insert_model(conn, "files", file)
        stored = get_file(conn, file.id)
    assert stored is not None
    return stored


def fill_original_name(conn: sqlite3.Connection, file_id: str, original_name: str) -> bool:
    """Set ``original_name`` only when the row has none: identical bytes keep the first name
    (data-model §2.8). Returns whether the row changed."""
    with transaction(conn):
        cur = conn.execute(
            "UPDATE files SET original_name = ? WHERE id = ? AND original_name IS NULL",
            (original_name, file_id),
        )
    return cur.rowcount > 0


def get_file(conn: sqlite3.Connection, file_id: str) -> File | None:
    row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    return None if row is None else from_row(File, row)


def list_files(conn: sqlite3.Connection) -> list[File]:
    """In insertion order. The ID is a sha256, not a ULID, so ties on ``created_at`` break on
    ``rowid`` (insertion order), not on ``id``."""
    rows = conn.execute("SELECT * FROM files ORDER BY created_at, rowid")
    return [from_row(File, r) for r in rows]
