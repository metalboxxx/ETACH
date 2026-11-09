"""``students`` (data-model §2.1). IDs are ``S-0001``, ``S-0002``, …"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from etach.domain.models import Student
from etach.store.db import transaction
from etach.store.repos._common import from_row, insert_model, next_readable_id

__all__ = [
    "create_student",
    "find_by_name_search",
    "get_student",
    "list_students",
    "search_students",
    "thread_counts",
    "thread_ids",
    "update_student",
]


def create_student(
    conn: sqlite3.Connection,
    full_name: str,
    name_search: str,
    class_name: str | None = None,
    school: str | None = None,
    grade: int | None = None,
    notes: str = "",
) -> Student:
    """Insert a new student with the next ``S-`` ID.

    ``name_search`` (lowercase, accents removed) is computed by the caller with the domain
    normalization (``domain/normalize.py``, step 8.1).
    """
    with transaction(conn):
        student = Student(
            id=next_readable_id(conn, "students", "S"),
            full_name=full_name,
            name_search=name_search,
            class_name=class_name,
            school=school,
            grade=grade,
            notes=notes,
            created_at=datetime.now(UTC),
        )
        insert_model(conn, "students", student)
    return student


def get_student(conn: sqlite3.Connection, student_id: str) -> Student | None:
    row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    return None if row is None else from_row(Student, row)


def find_by_name_search(conn: sqlite3.Connection, name_search: str) -> list[Student]:
    """Students whose ``name_search`` equals the given (already normalized) value."""
    rows = conn.execute(
        "SELECT * FROM students WHERE name_search = ? ORDER BY id", (name_search,)
    ).fetchall()
    return [from_row(Student, r) for r in rows]


def list_students(conn: sqlite3.Connection) -> list[Student]:
    return [from_row(Student, r) for r in conn.execute("SELECT * FROM students ORDER BY id")]


def search_students(conn: sqlite3.Connection, name_search: str, limit: int = 50) -> list[Student]:
    """Students whose ``name_search`` starts with, then contains, the (already normalized) query;
    prefix matches first, then by ID. An empty query lists all students."""
    if not name_search:
        return list_students(conn)[:limit]
    escaped = name_search.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    rows = conn.execute(
        "SELECT * FROM students WHERE name_search LIKE ? ESCAPE '!' "
        "ORDER BY CASE WHEN name_search LIKE ? ESCAPE '!' THEN 0 ELSE 1 END, id LIMIT ?",
        (f"%{escaped}%", f"{escaped}%", limit),
    ).fetchall()
    return [from_row(Student, r) for r in rows]


def update_student(
    conn: sqlite3.Connection, student_id: str, changes: dict[str, str | None]
) -> Student | None:
    """Change ``full_name``, ``class_name`` and/or ``school`` (v1.18); ``None`` when there is
    no such student.

    A new ``full_name`` must come with its ``name_search`` (data-model §5.6: recomputed on every
    name write), computed by the caller with the domain normalization.
    """
    allowed = {"full_name", "name_search", "class_name", "school"}
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"cannot change {sorted(unknown)}")
    if ("full_name" in changes) != ("name_search" in changes):
        raise ValueError("full_name and name_search change together")
    with transaction(conn):
        if get_student(conn, student_id) is None:
            return None
        for col, value in changes.items():
            conn.execute(f"UPDATE students SET {col} = ? WHERE id = ?", (value, student_id))
        return get_student(conn, student_id)


_CURRENT = "superseded_by IS NULL AND student_id IS NOT NULL"


def thread_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """``{student_id: threads whose current attempt is the student's}`` (llm-design v4.26)."""
    rows = conn.execute(
        f"SELECT student_id, COUNT(DISTINCT thread_id) FROM attempts WHERE {_CURRENT} "
        "GROUP BY student_id"
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def thread_ids(conn: sqlite3.Connection, student_id: str) -> list[str]:
    """The threads whose current attempt is the student's."""
    rows = conn.execute(
        f"SELECT DISTINCT thread_id FROM attempts WHERE {_CURRENT} AND student_id = ? "
        "ORDER BY thread_id",
        (student_id,),
    ).fetchall()
    return [r[0] for r in rows]
