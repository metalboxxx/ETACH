"""threads and messages."""

from __future__ import annotations

import sqlite3
from typing import Any

from etach.store.repos import threads


def test_threads_and_messages(conn: sqlite3.Connection, f: Any) -> None:
    th = threads.create_thread(conn, "Ảnh bài kiểm tra")
    assert threads.get_thread(conn, th.id) == th and th.kind == "pending"
    t = f.make_test(conn)
    threads.set_test_id(conn, th.id, t.id)
    threads.set_kind(conn, th.id, "filled")
    threads.set_title(conn, th.id, "Grade 8")
    got = threads.get_thread(conn, th.id)
    assert got is not None and (got.test_id, got.kind, got.title) == (t.id, "filled", "Grade 8")
    m1 = threads.add_message(conn, th.id, "teacher", "text", {"text": "chấm bài"})
    m2 = threads.add_message(conn, th.id, "app", "run_card", {"run_id": "r", "n": [1, 2]})
    assert threads.list_messages(conn, th.id) == [m1, m2]
    assert [x.id for x in threads.list_threads(conn)] == [th.id]
