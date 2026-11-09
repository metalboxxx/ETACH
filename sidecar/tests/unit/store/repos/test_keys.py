"""R2.6: guarded key upsert and explanation invalidation (data-model §2.4)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

import pytest

from etach.domain import models as m
from etach.store.repos import explanations, keys


def key(test_id: str, qid: str, accepted: list[str], source: str, status: str) -> m.AnswerKey:
    return m.AnswerKey(
        test_id=test_id,
        question_id=qid,
        accepted=accepted,
        reason_vi=None,
        source=source,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        confidence=0.9,
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def setup(conn: sqlite3.Connection, f: Any) -> tuple[str, str, str]:
    """Two tests; explanations for (T1,q-1) (two), (T1,q-2) and (T2,q-1)."""
    t1, t2 = f.make_test(conn).id, f.make_test(conn).id
    call = f.make_llm_call(conn).id
    for t, q, wrong in ((t1, "q-1", "b"), (t1, "q-1", "c"), (t1, "q-2", "b"), (t2, "q-1", "b")):
        explanations.upsert_explanation(conn, f.explanation(t, q, wrong, call))
    return t1, t2, call


def _explanations(conn: sqlite3.Connection) -> set[tuple[str, str, str]]:
    rows = conn.execute("SELECT test_id, question_id, wrong_answer_norm FROM explanations")
    return {tuple(r) for r in rows}


def test_ai_write_over_teacher_verified_is_a_no_op(
    conn: sqlite3.Connection, setup: tuple[str, str, str]
) -> None:
    t1, _, _ = setup
    teacher = key(t1, "q-1", ["A"], "ai", "teacher_verified")  # verified by the teacher
    keys.upsert_key(conn, teacher)
    before = _explanations(conn)
    result = keys.upsert_key(conn, key(t1, "q-1", ["B"], "ai", "ai_verified"))
    assert result == keys.KeyWrite("blocked", False, 0)
    assert keys.get_key(conn, t1, "q-1") == teacher
    assert _explanations(conn) == before
    edited = key(t1, "q-2", ["C"], "teacher_edit", "teacher_verified")
    keys.upsert_key(conn, edited)
    assert (
        keys.upsert_key(conn, key(t1, "q-2", ["D"], "from_key_photo", "ai_verified")).outcome
        == "blocked"
    )
    assert keys.get_key(conn, t1, "q-2") == edited


@pytest.mark.parametrize("old_status", ["ai_unverified", "ai_verified", "ai_uncertain"])
def test_key_photo_replaces_ai(
    conn: sqlite3.Connection, setup: tuple[str, str, str], old_status: str
) -> None:
    t1, _, _ = setup
    keys.upsert_key(conn, key(t1, "q-1", ["A"], "ai", old_status))
    photo = key(t1, "q-1", ["B"], "from_key_photo", "ai_verified")
    assert keys.upsert_key(conn, photo).outcome == "updated"
    assert keys.get_key(conn, t1, "q-1") == photo
    # and the AI can no longer overwrite the key photo
    assert keys.upsert_key(conn, key(t1, "q-1", ["C"], "ai", "ai_verified")).outcome == "blocked"


def test_key_change_deletes_only_that_questions_explanations(
    conn: sqlite3.Connection, setup: tuple[str, str, str]
) -> None:
    t1, t2, _ = setup
    first = keys.upsert_key(conn, key(t1, "q-1", ["A"], "ai", "ai_unverified"))
    assert (first.outcome, first.key_changed, first.explanations_deleted) == ("inserted", True, 2)
    assert _explanations(conn) == {(t1, "q-2", "b"), (t2, "q-1", "b")}


def test_status_only_change_keeps_explanations(
    conn: sqlite3.Connection, setup: tuple[str, str, str], f: Any
) -> None:
    t1, _, call = setup
    keys.upsert_key(conn, key(t1, "q-1", ["A"], "ai", "ai_unverified"))
    explanations.upsert_explanation(conn, f.explanation(t1, "q-1", "b", call))
    before = _explanations(conn)
    verified = keys.upsert_key(conn, key(t1, "q-1", ["A"], "ai", "ai_verified"))
    assert (verified.outcome, verified.key_changed) == ("updated", False)
    accepted = keys.upsert_key(conn, key(t1, "q-1", ["A"], "ai", "teacher_verified"))
    assert (accepted.outcome, accepted.key_changed) == ("updated", False)
    assert _explanations(conn) == before
    fixed = keys.upsert_key(conn, key(t1, "q-1", ["B"], "teacher_edit", "teacher_verified"))
    assert (fixed.outcome, fixed.key_changed, fixed.explanations_deleted) == ("updated", True, 1)
    assert (t1, "q-1", "b") not in _explanations(conn)


def test_identical_write_is_unchanged(
    conn: sqlite3.Connection, setup: tuple[str, str, str]
) -> None:
    t1, _, _ = setup
    keys.upsert_key(conn, key(t1, "q-1", ["A", "a."], "ai", "ai_unverified"))
    again = keys.upsert_key(conn, key(t1, "q-1", ["A", "a."], "ai", "ai_unverified"))
    assert again == keys.KeyWrite("unchanged", False, 0)
    assert [k.accepted for k in keys.list_keys(conn, t1)] == [["A", "a."]]
