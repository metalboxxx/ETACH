"""``occasions`` (data-model v1.17): the occasion list the teacher edits in Settings.

The ten built-ins are seeded by migration 0007; a teacher occasion's code is ``Custom:<id>``.
Renaming one remakes the automatic Test name and search row of every test using it (a typed
name is kept, ``updated_at`` is left alone). A built-in, or a code a test uses, is not deleted;
merged tests do not count, and lose the deleted occasion.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from etach.domain.models import CUSTOM_OCCASION_PREFIX, UNKNOWN_OCCASION_CODE, TestMetadata
from etach.store.db import _write_fts_row, load_occasion_names, new_ulid, transaction

__all__ = [
    "Occasion",
    "OccasionInUseError",
    "add_occasion",
    "delete_occasion",
    "get_occasion",
    "list_occasions",
    "update_occasion",
]


@dataclass(frozen=True)
class Occasion:
    code: str
    label: str
    short_name: str
    position: int
    builtin: bool
    test_count: int


class OccasionInUseError(Exception):
    """Delete refused: a built-in, or tests use the code (``test_count`` > 0)."""

    def __init__(self, reason: str, test_count: int) -> None:
        super().__init__(reason)
        self.reason = reason
        self.test_count = test_count


def list_occasions(conn: sqlite3.Connection) -> list[Occasion]:
    """Every occasion in the teacher's order, with the number of (not merged) tests using it."""
    counts = dict(
        conn.execute(
            "SELECT occasion, COUNT(*) FROM tests WHERE merged_into IS NULL GROUP BY occasion"
        ).fetchall()
    )
    rows = conn.execute(
        "SELECT code, label, short_name, position, builtin FROM occasions ORDER BY position, code"
    ).fetchall()
    return [
        Occasion(code, label, short, pos, bool(builtin), int(counts.get(code, 0)))
        for code, label, short, pos, builtin in rows
    ]


def get_occasion(conn: sqlite3.Connection, code: str) -> Occasion | None:
    return next((o for o in list_occasions(conn) if o.code == code), None)


def add_occasion(conn: sqlite3.Connection, label: str, short_name: str) -> Occasion:
    """Add a teacher occasion at the end of the list."""
    code = CUSTOM_OCCASION_PREFIX + new_ulid().lower()
    with transaction(conn):
        pos = conn.execute("SELECT COALESCE(MAX(position) + 1, 0) FROM occasions").fetchone()[0]
        conn.execute(
            "INSERT INTO occasions (code, label, short_name, position, builtin)"
            " VALUES (?, ?, ?, ?, 0)",
            (code, label, short_name, pos),
        )
    load_occasion_names(conn)
    occasion = get_occasion(conn, code)
    assert occasion is not None
    return occasion


def _remake_names(conn: sqlite3.Connection, code: str) -> None:
    """Remake the automatic Test name and search row of every test using ``code``."""
    rows = conn.execute(
        "SELECT id, meta, merged_into FROM tests WHERE occasion = ?", (code,)
    ).fetchall()
    for test_id, meta_json, merged in rows:
        meta = TestMetadata.model_validate_json(meta_json)
        conn.execute(
            "UPDATE tests SET display_name = ? WHERE id = ?", (meta.display_name(), test_id)
        )
        if merged is None:
            _write_fts_row(conn, test_id, meta)


def update_occasion(
    conn: sqlite3.Connection,
    code: str,
    label: str | None = None,
    short_name: str | None = None,
    position: int | None = None,
) -> Occasion:
    """Rename (label, short name) or move (``position`` = the new index in the list).
    ``KeyError`` for an unknown code."""
    renamed = label is not None or short_name is not None
    with transaction(conn):
        current = get_occasion(conn, code)
        if current is None:
            raise KeyError(code)
        if renamed:
            conn.execute(
                "UPDATE occasions SET label = ?, short_name = ? WHERE code = ?",
                (label or current.label, short_name or current.short_name, code),
            )
        if position is not None:
            order = [o.code for o in list_occasions(conn) if o.code != code]
            order.insert(max(0, min(position, len(order))), code)
            for i, c in enumerate(order):
                conn.execute("UPDATE occasions SET position = ? WHERE code = ?", (i, c))
        load_occasion_names(conn)
        if renamed:
            _remake_names(conn, code)
    occasion = get_occasion(conn, code)
    assert occasion is not None
    return occasion


def delete_occasion(conn: sqlite3.Connection, code: str) -> None:
    """Delete a teacher occasion. ``KeyError`` when unknown; :class:`OccasionInUseError` for a
    built-in or while a (not merged) test uses it."""
    with transaction(conn):
        current = get_occasion(conn, code)
        if current is None:
            raise KeyError(code)
        if current.builtin:
            raise OccasionInUseError("A built-in occasion can't be deleted.", current.test_count)
        if current.test_count:
            n = current.test_count
            raise OccasionInUseError(
                f"{n} test{'s' if n != 1 else ''} use{'' if n != 1 else 's'} this occasion.", n
            )
        _unset_merged(conn, code)
        conn.execute("DELETE FROM occasions WHERE code = ?", (code,))
        codes = [o.code for o in list_occasions(conn)]
        for i, c in enumerate(codes):
            conn.execute("UPDATE occasions SET position = ? WHERE code = ?", (i, c))
    load_occasion_names(conn)


def _unset_merged(conn: sqlite3.Connection, code: str) -> None:
    """Merged tests still using ``code`` get the unknown occasion (``Other:unknown``) and their
    automatic name remade (teacher, 2026-10-18); a typed name is kept, ``updated_at`` too."""
    rows = conn.execute(
        "SELECT id, meta FROM tests WHERE occasion = ? AND merged_into IS NOT NULL", (code,)
    ).fetchall()
    for test_id, meta_json in rows:
        meta = TestMetadata.model_validate_json(meta_json).model_copy(
            update={"occasion": UNKNOWN_OCCASION_CODE}
        )
        conn.execute(
            "UPDATE tests SET meta = ?, occasion = ?, display_name = ? WHERE id = ?",
            (meta.model_dump_json(), meta.occasion, meta.display_name(), test_id),
        )
