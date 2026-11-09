"""R2.7: review items (dedupe, obsolete, reviewed)."""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from etach.store.repos import attempts, review


def _upsert(
    conn: sqlite3.Connection, key: str, owner: str, attempt_id: str | None, n: int = 1
) -> Any:
    return review.upsert_item(
        conn,
        kind="uncertain_answer",
        owner=owner,  # type: ignore[arg-type]
        dedupe_key=key,
        proposal={"value": n},
        attempt_id=attempt_id,
    )


def test_same_dedupe_key_twice_is_one_row(conn: sqlite3.Connection) -> None:
    first, o1 = _upsert(conn, "uncertain_answer:A:q-1", "extract", None, 1)
    second, o2 = _upsert(conn, "uncertain_answer:A:q-1", "extract", None, 2)
    assert (o1, o2) == ("inserted", "updated")
    assert second.id == first.id and second.proposal == {"value": 2}
    assert conn.execute("SELECT COUNT(*) FROM review_items").fetchone()[0] == 1


@pytest.mark.parametrize("status", ["accepted", "fixed", "skipped"])
def test_resolved_item_is_left_alone(conn: sqlite3.Connection, status: str) -> None:
    item, _ = _upsert(conn, "k", "extract", None, 1)
    review.resolve_item(conn, item.id, status, {"by": "teacher"})  # type: ignore[arg-type]
    before = review.get_item(conn, item.id)
    after, outcome = _upsert(conn, "k", "extract", None, 2)
    assert outcome == "kept" and after == before


def test_obsolete_item_is_reopened(conn: sqlite3.Connection, f: Any) -> None:
    a = f.make_attempt(conn, f.make_test(conn).id)
    item, _ = _upsert(conn, "k", "grade", a.id, 1)
    assert review.mark_obsolete(conn, "grade", a.id) == 1
    reopened, outcome = _upsert(conn, "k", "grade", a.id, 2)
    assert outcome == "reopened"
    assert (reopened.id, reopened.status, reopened.proposal) == (item.id, "open", {"value": 2})
    assert reopened.resolved_at is None and reopened.resolution is None


def test_mark_obsolete_touches_only_open_items_of_owner_and_attempt(
    conn: sqlite3.Connection, f: Any
) -> None:
    t = f.make_test(conn).id
    a, b = f.make_attempt(conn, t).id, f.make_attempt(conn, t).id
    _upsert(conn, "grade-a-open", "grade", a)
    resolved, _ = _upsert(conn, "grade-a-done", "grade", a)
    review.resolve_item(conn, resolved.id, "fixed", {})
    _upsert(conn, "extract-a", "extract", a)
    _upsert(conn, "grade-b", "grade", b)
    _upsert(conn, "grade-none", "grade", None)
    before = {i.dedupe_key: i for i in review.list_items(conn)}
    assert review.mark_obsolete(conn, "grade", a) == 1
    after = {i.dedupe_key: i for i in review.list_items(conn)}
    assert after["grade-a-open"].status == "obsolete"
    changed = {k for k in after if after[k] != before[k]}
    assert changed == {"grade-a-open"}


def test_resolving_the_last_open_item_marks_the_attempt_reviewed(
    conn: sqlite3.Connection, f: Any
) -> None:
    t = f.make_test(conn).id
    a, other = f.make_attempt(conn, t), f.make_attempt(conn, t)
    one, _ = _upsert(conn, "one", "extract", a.id)
    two, _ = _upsert(conn, "two", "grade", a.id)
    _upsert(conn, "other", "extract", other.id)
    review.resolve_item(conn, one.id, "accepted", {"ok": True})
    assert attempts.get_attempt(conn, a.id).status == "extracted"  # type: ignore[union-attr]
    done = review.resolve_item(conn, two.id, "skipped")
    assert done.status == "skipped" and done.resolved_at is not None
    assert attempts.get_attempt(conn, a.id).status == "reviewed"  # type: ignore[union-attr]
    assert attempts.get_attempt(conn, other.id).status == "extracted"  # type: ignore[union-attr]


def test_resolve_needs_an_open_item(conn: sqlite3.Connection) -> None:
    item, _ = _upsert(conn, "k", "extract", None)
    review.resolve_item(conn, item.id, "accepted")
    with pytest.raises(ValueError, match="not open"):
        review.resolve_item(conn, item.id, "fixed")
    with pytest.raises(KeyError):
        review.resolve_item(conn, "nope", "fixed")
