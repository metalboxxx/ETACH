"""``schools`` (data-model v1.18): the school list the teacher edits in Settings.

Migration 0008 seeds it from the schools already on tests and students. ``tests.school`` and
``students.school`` keep the name as text, so renaming a school updates both, and remakes the
automatic Test name and search row of every test with it (a typed name is kept; ``updated_at``
and ``edited_fields`` are left alone). Names are unique ignoring case (:func:`fold`; Vietnamese
letters too). A school a (not merged) test or a student uses is not deleted. A name typed on a
test or student that is not in the list is added at the end (:func:`ensure_school`).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from etach.domain.models import TestMetadata
from etach.store.db import _write_fts_row, transaction

__all__ = [
    "School",
    "SchoolExistsError",
    "SchoolInUseError",
    "add_school",
    "clean_name",
    "delete_school",
    "ensure_school",
    "fold",
    "get_school",
    "list_schools",
    "merge_case_variants",
    "update_school",
]


@dataclass(frozen=True)
class School:
    id: int
    name: str
    position: int
    test_count: int
    student_count: int


class SchoolExistsError(Exception):
    """Add or rename refused: another school has this name (ignoring case)."""


class SchoolInUseError(Exception):
    """Delete refused: tests or students use the school."""

    def __init__(self, reason: str, test_count: int, student_count: int) -> None:
        super().__init__(reason)
        self.reason = reason
        self.test_count = test_count
        self.student_count = student_count


def clean_name(name: str | None) -> str | None:
    """Spaces collapsed; ``None`` for a blank name."""
    if name is None:
        return None
    cleaned = " ".join(name.split())
    return cleaned or None


def fold(name: str | None) -> str | None:
    """The form two school names are compared in: trimmed, spaces collapsed, case folded (also
    Vietnamese letters, which SQLite's ``NOCASE`` leaves alone)."""
    cleaned = clean_name(name)
    return None if cleaned is None else cleaned.casefold()


def _fold_fn(conn: sqlite3.Connection) -> None:
    conn.create_function("etach_school_fold", 1, fold, deterministic=True)


def _counts(conn: sqlite3.Connection, name: str) -> tuple[int, int]:
    _fold_fn(conn)
    tests = conn.execute(
        "SELECT COUNT(*) FROM tests WHERE merged_into IS NULL"
        " AND etach_school_fold(school) = etach_school_fold(?)",
        (name,),
    ).fetchone()[0]
    students = conn.execute(
        "SELECT COUNT(*) FROM students WHERE etach_school_fold(school) = etach_school_fold(?)",
        (name,),
    ).fetchone()[0]
    return int(tests), int(students)


def merge_case_variants(conn: sqlite3.Connection) -> int:
    """Keep one row per school name under Unicode case folding (data-model v1.18.1).

    Migration 0008 can only dedupe with SQLite's ``NOCASE``, which folds A-Z alone, so two old
    spellings that differ only in a Vietnamese capital ("LÊ LỢI", "Lê Lợi") both reach the table.
    The first spelling (lowest id, the seed's order) is kept and the others removed; the tests and
    students keep their text and count for the kept row, because every lookup folds the same
    way. Runs before every read of the list, so it also holds for a database seeded earlier.
    Returns the number of rows removed."""
    seen: set[str] = set()
    extra: list[int] = []
    for sid, name in conn.execute("SELECT id, name FROM schools ORDER BY id").fetchall():
        key = fold(name) or ""
        if key in seen:
            extra.append(int(sid))
        seen.add(key)
    if not extra:
        return 0
    with transaction(conn):
        conn.executemany("DELETE FROM schools WHERE id = ?", [(sid,) for sid in extra])
        ids = conn.execute("SELECT id FROM schools ORDER BY position, id").fetchall()
        for i, (sid,) in enumerate(ids):
            conn.execute("UPDATE schools SET position = ? WHERE id = ?", (i, sid))
    return len(extra)


def list_schools(conn: sqlite3.Connection) -> list[School]:
    """Every school in the teacher's order, with the tests (not merged) and students using it."""
    merge_case_variants(conn)
    rows = conn.execute("SELECT id, name, position FROM schools ORDER BY position, id").fetchall()
    return [School(sid, name, pos, *_counts(conn, name)) for sid, name, pos in rows]


def get_school(conn: sqlite3.Connection, school_id: int) -> School | None:
    row = conn.execute(
        "SELECT id, name, position FROM schools WHERE id = ?", (school_id,)
    ).fetchone()
    return None if row is None else School(row[0], row[1], row[2], *_counts(conn, row[1]))


def _find(conn: sqlite3.Connection, name: str) -> int | None:
    merge_case_variants(conn)
    _fold_fn(conn)
    row = conn.execute(
        "SELECT id FROM schools WHERE etach_school_fold(name) = etach_school_fold(?)", (name,)
    ).fetchone()
    return None if row is None else int(row[0])


def _insert(conn: sqlite3.Connection, name: str) -> int:
    pos = conn.execute("SELECT COALESCE(MAX(position) + 1, 0) FROM schools").fetchone()[0]
    cur = conn.execute("INSERT INTO schools (name, position) VALUES (?, ?)", (name, pos))
    assert cur.lastrowid is not None
    return int(cur.lastrowid)


def add_school(conn: sqlite3.Connection, name: str) -> School:
    """Add a school at the end. :class:`SchoolExistsError` when the name is taken."""
    with transaction(conn):
        if _find(conn, name) is not None:
            raise SchoolExistsError(name)
        school_id = _insert(conn, name)
    school = get_school(conn, school_id)
    assert school is not None
    return school


def ensure_school(conn: sqlite3.Connection, name: str | None) -> None:
    """Add ``name`` at the end of the list unless it is blank or already there (any case)."""
    cleaned = clean_name(name)
    if cleaned is None:
        return
    with transaction(conn):
        if _find(conn, cleaned) is None:
            _insert(conn, cleaned)


def _rename_uses(conn: sqlite3.Connection, old: str, new: str) -> None:
    """Every test and student with ``old`` (ignoring case) gets ``new``; automatic Test names and
    search rows are remade. ``edited_fields`` and ``updated_at`` stay as they are."""
    _fold_fn(conn)
    rows = conn.execute(
        "SELECT id, meta, merged_into FROM tests"
        " WHERE etach_school_fold(school) = etach_school_fold(?)",
        (old,),
    ).fetchall()
    for test_id, meta_json, merged in rows:
        meta = TestMetadata.model_validate_json(meta_json).model_copy(update={"school": new})
        conn.execute(
            "UPDATE tests SET meta = ?, school = ?, display_name = ? WHERE id = ?",
            (meta.model_dump_json(), new, meta.display_name(), test_id),
        )
        if merged is None:
            _write_fts_row(conn, test_id, meta)
    conn.execute(
        "UPDATE students SET school = ? WHERE etach_school_fold(school) = etach_school_fold(?)",
        (new, old),
    )


def update_school(
    conn: sqlite3.Connection,
    school_id: int,
    name: str | None = None,
    position: int | None = None,
) -> School:
    """Rename or move (``position`` = the new index in the list). ``KeyError`` for an unknown
    id, :class:`SchoolExistsError` when another school has the new name."""
    with transaction(conn):
        current = get_school(conn, school_id)
        if current is None:
            raise KeyError(school_id)
        if name is not None and name != current.name:
            other = _find(conn, name)
            if other is not None and other != school_id:
                raise SchoolExistsError(name)
            conn.execute("UPDATE schools SET name = ? WHERE id = ?", (name, school_id))
            _rename_uses(conn, current.name, name)
        if position is not None:
            order = [s.id for s in list_schools(conn) if s.id != school_id]
            order.insert(max(0, min(position, len(order))), school_id)
            for i, sid in enumerate(order):
                conn.execute("UPDATE schools SET position = ? WHERE id = ?", (i, sid))
    school = get_school(conn, school_id)
    assert school is not None
    return school


def _count(n: int, what: str) -> str:
    return f"{n} {what}{'s' if n != 1 else ''}"


def delete_school(conn: sqlite3.Connection, school_id: int) -> None:
    """Delete a school. ``KeyError`` when unknown; :class:`SchoolInUseError` while a (not merged)
    test or a student uses it."""
    with transaction(conn):
        current = get_school(conn, school_id)
        if current is None:
            raise KeyError(school_id)
        t, s = current.test_count, current.student_count
        if t or s:
            parts = [p for n, p in ((t, _count(t, "test")), (s, _count(s, "student"))) if n]
            verb = "use" if t + s != 1 else "uses"
            raise SchoolInUseError(f"{' and '.join(parts)} {verb} this school.", t, s)
        conn.execute("DELETE FROM schools WHERE id = ?", (school_id,))
        ids = [row.id for row in list_schools(conn)]
        for i, sid in enumerate(ids):
            conn.execute("UPDATE schools SET position = ? WHERE id = ?", (i, sid))
