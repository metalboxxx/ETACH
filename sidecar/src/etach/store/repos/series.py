"""``series`` (data-model v1.21, decision D5): the series list the teacher edits in Settings.

Built like the school list (:mod:`etach.store.repos.schools`). Migration 0011 seeds it from the
series (``meta.source``) already on tests. Tests keep the name as text in ``meta.source``, so
renaming a series updates every test with it, and remakes the automatic Test name and search row
of each (a typed name is kept; ``updated_at`` and ``edited_fields`` are left alone). Names are
unique ignoring case (Vietnamese letters too). A series a (not merged) test uses is not deleted.
A series typed on a test that is not in the list is added at the end (:func:`ensure_series`).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from etach.domain.models import TestMetadata
from etach.store.db import _write_fts_row, transaction
from etach.store.repos.schools import clean_name, fold

__all__ = [
    "Series",
    "SeriesExistsError",
    "SeriesInUseError",
    "add_series",
    "delete_series",
    "ensure_series",
    "get_series",
    "list_series",
    "merge_case_variants",
    "newest_meta",
    "update_series",
]


@dataclass(frozen=True)
class Series:
    id: int
    name: str
    position: int
    test_count: int


class SeriesExistsError(Exception):
    """Add or rename refused: another series has this name (ignoring case)."""


class SeriesInUseError(Exception):
    """Delete refused: tests use the series."""

    def __init__(self, reason: str, test_count: int) -> None:
        super().__init__(reason)
        self.reason = reason
        self.test_count = test_count


def _fold_fn(conn: sqlite3.Connection) -> None:
    conn.create_function("etach_series_fold", 1, fold, deterministic=True)


def _count(conn: sqlite3.Connection, name: str) -> int:
    _fold_fn(conn)
    row = conn.execute(
        "SELECT COUNT(*) FROM tests WHERE merged_into IS NULL"
        " AND etach_series_fold(json_extract(meta, '$.source')) = etach_series_fold(?)",
        (name,),
    ).fetchone()
    return int(row[0])


def _renumber(conn: sqlite3.Connection, ids: list[int]) -> None:
    for i, sid in enumerate(ids):
        conn.execute("UPDATE series SET position = ? WHERE id = ?", (i, sid))


def merge_case_variants(conn: sqlite3.Connection) -> int:
    """Keep one row per series name under Unicode case folding: migration 0011 dedupes with
    SQLite's ``NOCASE`` only, so "Đề dự đoán" and "đề dự đoán" both reach the table. The first
    spelling (lowest id, the seed's order) is kept. Runs before every read of the list. Returns
    the number of rows removed."""
    seen: set[str] = set()
    extra: list[int] = []
    for sid, name in conn.execute("SELECT id, name FROM series ORDER BY id").fetchall():
        key = fold(name) or ""
        if key in seen:
            extra.append(int(sid))
        seen.add(key)
    if not extra:
        return 0
    with transaction(conn):
        conn.executemany("DELETE FROM series WHERE id = ?", [(sid,) for sid in extra])
        ids = conn.execute("SELECT id FROM series ORDER BY position, id").fetchall()
        _renumber(conn, [int(r[0]) for r in ids])
    return len(extra)


def list_series(conn: sqlite3.Connection) -> list[Series]:
    """Every series in the teacher's order, with the tests (not merged) using it."""
    merge_case_variants(conn)
    rows = conn.execute("SELECT id, name, position FROM series ORDER BY position, id").fetchall()
    return [Series(sid, name, pos, _count(conn, name)) for sid, name, pos in rows]


def get_series(conn: sqlite3.Connection, series_id: int) -> Series | None:
    row = conn.execute(
        "SELECT id, name, position FROM series WHERE id = ?", (series_id,)
    ).fetchone()
    return None if row is None else Series(row[0], row[1], row[2], _count(conn, row[1]))


def _find(conn: sqlite3.Connection, name: str) -> int | None:
    merge_case_variants(conn)
    _fold_fn(conn)
    row = conn.execute(
        "SELECT id FROM series WHERE etach_series_fold(name) = etach_series_fold(?)", (name,)
    ).fetchone()
    return None if row is None else int(row[0])


def _insert(conn: sqlite3.Connection, name: str) -> int:
    pos = conn.execute("SELECT COALESCE(MAX(position) + 1, 0) FROM series").fetchone()[0]
    cur = conn.execute("INSERT INTO series (name, position) VALUES (?, ?)", (name, pos))
    assert cur.lastrowid is not None
    return int(cur.lastrowid)


def add_series(conn: sqlite3.Connection, name: str) -> Series:
    """Add a series at the end. :class:`SeriesExistsError` when the name is taken."""
    with transaction(conn):
        if _find(conn, name) is not None:
            raise SeriesExistsError(name)
        series_id = _insert(conn, name)
    series = get_series(conn, series_id)
    assert series is not None
    return series


def ensure_series(conn: sqlite3.Connection, name: str | None) -> None:
    """Add ``name`` at the end of the list unless it is blank or already there (any case)."""
    cleaned = clean_name(name)
    if cleaned is None:
        return
    with transaction(conn):
        if _find(conn, cleaned) is None:
            _insert(conn, cleaned)


def newest_meta(
    conn: sqlite3.Connection, name: str, *, exclude: str | None = None
) -> TestMetadata | None:
    """The metadata of the newest (by ``created_at``) not merged test whose series is ``name``
    (ignoring case), leaving out the test ``exclude``; ``None`` when there is none."""
    _fold_fn(conn)
    row = conn.execute(
        "SELECT meta FROM tests WHERE merged_into IS NULL AND id IS NOT ?"
        " AND etach_series_fold(json_extract(meta, '$.source')) = etach_series_fold(?)"
        " ORDER BY created_at DESC, id DESC LIMIT 1",
        (exclude, name),
    ).fetchone()
    return None if row is None else TestMetadata.model_validate_json(row[0])


def _rename_uses(conn: sqlite3.Connection, old: str, new: str) -> None:
    """Every test with ``old`` (ignoring case) gets ``new``; automatic Test names and search rows
    are remade. ``edited_fields`` and ``updated_at`` stay as they are."""
    _fold_fn(conn)
    rows = conn.execute(
        "SELECT id, meta, merged_into FROM tests"
        " WHERE etach_series_fold(json_extract(meta, '$.source')) = etach_series_fold(?)",
        (old,),
    ).fetchall()
    for test_id, meta_json, merged in rows:
        meta = TestMetadata.model_validate_json(meta_json).model_copy(update={"source": new})
        conn.execute(
            "UPDATE tests SET meta = ?, display_name = ? WHERE id = ?",
            (meta.model_dump_json(), meta.display_name(), test_id),
        )
        if merged is None:
            _write_fts_row(conn, test_id, meta)


def update_series(
    conn: sqlite3.Connection,
    series_id: int,
    name: str | None = None,
    position: int | None = None,
) -> Series:
    """Rename or move (``position`` = the new index in the list). ``KeyError`` for an unknown
    id, :class:`SeriesExistsError` when another series has the new name."""
    with transaction(conn):
        current = get_series(conn, series_id)
        if current is None:
            raise KeyError(series_id)
        if name is not None and name != current.name:
            other = _find(conn, name)
            if other is not None and other != series_id:
                raise SeriesExistsError(name)
            conn.execute("UPDATE series SET name = ? WHERE id = ?", (name, series_id))
            _rename_uses(conn, current.name, name)
        if position is not None:
            order = [s.id for s in list_series(conn) if s.id != series_id]
            order.insert(max(0, min(position, len(order))), series_id)
            _renumber(conn, order)
    series = get_series(conn, series_id)
    assert series is not None
    return series


def delete_series(conn: sqlite3.Connection, series_id: int) -> None:
    """Delete a series. ``KeyError`` when unknown; :class:`SeriesInUseError` while a (not merged)
    test uses it."""
    with transaction(conn):
        current = get_series(conn, series_id)
        if current is None:
            raise KeyError(series_id)
        n = current.test_count
        if n:
            tests = f"{n} test{'s' if n != 1 else ''}"
            raise SeriesInUseError(f"{tests} {'use' if n != 1 else 'uses'} this series.", n)
        conn.execute("DELETE FROM series WHERE id = ?", (series_id,))
        _renumber(conn, [s.id for s in list_series(conn)])
