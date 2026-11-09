"""R10.4: a new or reopened open item on a ``reviewed`` attempt sends it back to ``graded``
(score set) or ``extracted``; on any other status nothing changes."""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from etach.store.repos import attempts, review


def _upsert(conn: sqlite3.Connection, key: str, attempt_id: str) -> Any:
    return review.upsert_item(
        conn,
        kind="uncertain_answer",
        owner="grade",
        dedupe_key=key,
        proposal={"value": 1},
        attempt_id=attempt_id,
    )


@pytest.mark.parametrize(("score", "expected"), [(7.5, "graded"), (None, "extracted")])
def test_new_item_on_reviewed_attempt(
    conn: sqlite3.Connection, f: Any, score: float | None, expected: str
) -> None:
    a = f.make_attempt(conn, f.make_test(conn).id, status="reviewed", score_earned=score)
    _, outcome = _upsert(conn, "k", a.id)
    assert outcome == "inserted"
    stored = attempts.get_attempt(conn, a.id)
    assert stored is not None and stored.status == expected


@pytest.mark.parametrize(("score", "expected"), [(7.5, "graded"), (None, "extracted")])
def test_reopened_item_on_reviewed_attempt(
    conn: sqlite3.Connection, f: Any, score: float | None, expected: str
) -> None:
    a = f.make_attempt(conn, f.make_test(conn).id, status="extracted", score_earned=score)
    _upsert(conn, "k", a.id)
    review.mark_obsolete(conn, "grade", a.id)
    attempts.set_status(conn, a.id, "reviewed")
    _, outcome = _upsert(conn, "k", a.id)
    assert outcome == "reopened"
    stored = attempts.get_attempt(conn, a.id)
    assert stored is not None and stored.status == expected


@pytest.mark.parametrize("status", ["extracted", "graded"])
def test_item_on_non_reviewed_attempt_keeps_status(
    conn: sqlite3.Connection, f: Any, status: str
) -> None:
    a = f.make_attempt(conn, f.make_test(conn).id, status=status, score_earned=5.0)
    _upsert(conn, "k", a.id)
    stored = attempts.get_attempt(conn, a.id)
    assert stored is not None and stored.status == status


def test_updated_or_kept_item_does_not_change_status(conn: sqlite3.Connection, f: Any) -> None:
    a = f.make_attempt(conn, f.make_test(conn).id, score_earned=5.0)
    item, _ = _upsert(conn, "k", a.id)
    review.resolve_item(conn, item.id, "accepted")  # → reviewed
    _, outcome = _upsert(conn, "k", a.id)
    assert outcome == "kept"
    stored = attempts.get_attempt(conn, a.id)
    assert stored is not None and stored.status == "reviewed"
