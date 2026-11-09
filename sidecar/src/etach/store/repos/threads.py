"""``threads`` and ``messages`` (data-model §2.7). IDs are ULIDs."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any, Literal

from etach.domain.models import Message, Thread
from etach.store.db import new_ulid, transaction
from etach.store.repos._common import from_row, insert_model

__all__ = [
    "add_message",
    "create_thread",
    "get_thread",
    "last_activity",
    "list_messages",
    "list_threads",
    "set_kind",
    "set_test_id",
    "set_title",
]

_MSG_JSON = ("body",)


def create_thread(
    conn: sqlite3.Connection,
    title: str,
    kind: Literal["filled", "blank", "pending"] = "pending",
    test_id: str | None = None,
) -> Thread:
    thread = Thread(
        id=new_ulid(), title=title, test_id=test_id, kind=kind, created_at=datetime.now(UTC)
    )
    with transaction(conn):
        insert_model(conn, "threads", thread)
    return thread


def get_thread(conn: sqlite3.Connection, thread_id: str) -> Thread | None:
    row = conn.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone()
    return None if row is None else from_row(Thread, row)


def list_threads(conn: sqlite3.Connection) -> list[Thread]:
    rows = conn.execute("SELECT * FROM threads ORDER BY created_at DESC, id DESC").fetchall()
    return [from_row(Thread, r) for r in rows]


def _update(conn: sqlite3.Connection, thread_id: str, col: str, value: object) -> None:
    with transaction(conn):
        cur = conn.execute(f"UPDATE threads SET {col} = ? WHERE id = ?", (value, thread_id))
        if cur.rowcount != 1:
            raise KeyError(f"no thread {thread_id}")


def set_test_id(conn: sqlite3.Connection, thread_id: str, test_id: str | None) -> None:
    """Keep ``threads.test_id`` equal to the current attempt's test (data-model §5.6)."""
    _update(conn, thread_id, "test_id", test_id)


def set_kind(
    conn: sqlite3.Connection, thread_id: str, kind: Literal["filled", "blank", "pending"]
) -> None:
    _update(conn, thread_id, "kind", kind)


def set_title(conn: sqlite3.Connection, thread_id: str, title: str) -> None:
    _update(conn, thread_id, "title", title)


def add_message(
    conn: sqlite3.Connection,
    thread_id: str,
    role: Literal["teacher", "app"],
    kind: Literal["text", "photo_check", "run_card", "grade_card", "notice"],
    body: dict[str, Any],
) -> Message:
    message = Message(
        id=new_ulid(),
        thread_id=thread_id,
        role=role,
        kind=kind,
        body=body,
        created_at=datetime.now(UTC),
    )
    with transaction(conn):
        insert_model(conn, "messages", message, _MSG_JSON)
    return message


def list_messages(conn: sqlite3.Connection, thread_id: str) -> list[Message]:
    rows = conn.execute(
        "SELECT * FROM messages WHERE thread_id = ? ORDER BY created_at, id", (thread_id,)
    ).fetchall()
    return [from_row(Message, r, _MSG_JSON) for r in rows]


def last_activity(conn: sqlite3.Connection) -> dict[str, str]:
    """``{thread_id: ISO time}``: the latest of the thread's creation, its messages and its
    runs' start/finish (the sidebar's "last activity")."""
    rows = conn.execute(
        "SELECT t.id, MAX(t.created_at,"
        " COALESCE((SELECT MAX(m.created_at) FROM messages m WHERE m.thread_id = t.id), ''),"
        " COALESCE((SELECT MAX(COALESCE(r.finished_at, r.started_at, ''))"
        "   FROM runs r WHERE r.thread_id = t.id), ''))"
        " FROM threads t"
    ).fetchall()
    return {r[0]: r[1] for r in rows}
