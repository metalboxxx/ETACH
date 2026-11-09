"""students: create with readable IDs, find by name_search."""

from __future__ import annotations

import sqlite3

from etach.store.repos import students


def test_create_and_find(conn: sqlite3.Connection) -> None:
    a = students.create_student(conn, "Học Sinh A", "hoc sinh a", class_name="8X1", grade=8)
    b = students.create_student(conn, "Học Sinh B", "hoc sinh b")
    c = students.create_student(conn, "Học Sinh A", "hoc sinh a", school="THCS X")
    assert [s.id for s in (a, b, c)] == ["S-0001", "S-0002", "S-0003"]
    assert students.get_student(conn, a.id) == a
    assert students.find_by_name_search(conn, "hoc sinh a") == [a, c]
    assert students.find_by_name_search(conn, "hoc sinh") == []
    assert students.list_students(conn) == [a, b, c]
    assert students.get_student(conn, "S-9999") is None


def test_next_id_is_max_plus_one(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO students (id, full_name, name_search, created_at)"
        " VALUES ('S-0041', 'x', 'x', 't')"
    )
    assert students.create_student(conn, "Y", "y").id == "S-0042"
