"""explanations cache."""

from __future__ import annotations

import sqlite3
from typing import Any

from etach.store.repos import explanations


def test_explanations(conn: sqlite3.Connection, f: Any) -> None:
    t = f.make_test(conn)
    call = f.make_llm_call(conn).id
    e = f.explanation(t.id, "q-1", "b", call)
    explanations.upsert_explanation(conn, e)
    edited = e.model_copy(update={"text_vi": "Sửa", "status": "teacher_edited"})
    explanations.upsert_explanation(conn, edited)
    assert explanations.get_explanation(conn, t.id, "q-1", "b") == edited
    assert explanations.list_explanations(conn, t.id) == [edited]
    assert explanations.delete_for_question(conn, t.id, "q-1") == 1
    assert explanations.list_explanations(conn, t.id) == []
