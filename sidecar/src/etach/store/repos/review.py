"""``review_items`` (data-model §2.8, §5.2-5.3). IDs are ULIDs.

- :func:`upsert_item` dedupes on ``dedupe_key``: an ``open`` item gets the new proposal, an
  ``obsolete`` one is reopened with it, and a resolved one (``accepted``/``fixed``/``skipped``)
  is left alone.
- :func:`mark_obsolete` closes the open items one graph (``owner``) made for one attempt; a
  re-run calls it before upserting its new items, which reopens the ones still relevant.
- :func:`resolve_item` records the teacher's decision; when it resolves the attempt's last open
  item, the attempt becomes ``reviewed``.
- An item inserted, or an ``obsolete`` one reopened, on a ``reviewed`` attempt sends the attempt
  back to ``graded`` (``score_earned`` set) or ``extracted`` (data-model §5.3, plan R10.4).

What a resolution *does* to the other tables is the step 10 service (``domain/review.py``).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any, Literal

from etach.domain.models import ReviewItem
from etach.store.db import dumps, new_ulid, now_iso, transaction
from etach.store.repos import attempts
from etach.store.repos._common import from_row, insert_model

__all__ = [
    "ReviewKind",
    "UpsertOutcome",
    "count_open",
    "count_open_for",
    "count_open_for_attempt",
    "get_by_dedupe_key",
    "get_item",
    "list_items",
    "list_open_for_test",
    "mark_obsolete",
    "open_counts_by_test",
    "resolve_item",
    "set_obsolete",
    "set_proposal",
    "settle_key_items",
    "upsert_item",
]

_JSON = ("proposal", "resolution")

ReviewKind = Literal[
    "uncertain_answer",
    "box_inline_conflict",
    "uncertain_key",
    "key_unmapped",
    "possible_duplicate",
    "picked_test_mismatch",
    "unknown_student",
    "unknown_occasion",
    "points_assumed",
    "validator_failed",
    "merge_unaligned",
    "unreadable_text",
]
UpsertOutcome = Literal["inserted", "updated", "reopened", "kept"]


def get_item(conn: sqlite3.Connection, item_id: str) -> ReviewItem | None:
    row = conn.execute("SELECT * FROM review_items WHERE id = ?", (item_id,)).fetchone()
    return None if row is None else from_row(ReviewItem, row, _JSON)


def get_by_dedupe_key(conn: sqlite3.Connection, dedupe_key: str) -> ReviewItem | None:
    row = conn.execute("SELECT * FROM review_items WHERE dedupe_key = ?", (dedupe_key,)).fetchone()
    return None if row is None else from_row(ReviewItem, row, _JSON)


def list_items(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    attempt_id: str | None = None,
    test_id: str | None = None,
) -> list[ReviewItem]:
    where: list[str] = []
    args: list[str] = []
    for col, value in (("status", status), ("attempt_id", attempt_id), ("test_id", test_id)):
        if value is not None:
            where.append(f"{col} = ?")
            args.append(value)
    sql = "SELECT * FROM review_items" + (" WHERE " + " AND ".join(where) if where else "")
    rows = conn.execute(sql + " ORDER BY created_at, id", args).fetchall()
    return [from_row(ReviewItem, r, _JSON) for r in rows]


def upsert_item(
    conn: sqlite3.Connection,
    *,
    kind: ReviewKind,
    owner: Literal["extract", "grade"],
    dedupe_key: str,
    proposal: dict[str, Any],
    test_id: str | None = None,
    attempt_id: str | None = None,
    question_id: str | None = None,
) -> tuple[ReviewItem, UpsertOutcome]:
    """Insert a new open item, or apply the dedupe rules to the existing one."""
    with transaction(conn):
        old = get_by_dedupe_key(conn, dedupe_key)
        if old is None:
            item = ReviewItem(
                id=new_ulid(),
                kind=kind,
                owner=owner,
                test_id=test_id,
                attempt_id=attempt_id,
                question_id=question_id,
                dedupe_key=dedupe_key,
                proposal=proposal,
                resolution=None,
                followup_run_id=None,
                status="open",
                created_at=datetime.now(UTC),
                resolved_at=None,
            )
            insert_model(conn, "review_items", item, _JSON)
            _unreview(conn, attempt_id)
            return item, "inserted"
        outcome: UpsertOutcome
        if old.status == "open":
            conn.execute(
                "UPDATE review_items SET proposal = ? WHERE id = ?", (dumps(proposal), old.id)
            )
            outcome = "updated"
        elif old.status == "obsolete":
            conn.execute(
                "UPDATE review_items SET status = 'open', proposal = ?, resolution = NULL,"
                " followup_run_id = NULL, resolved_at = NULL WHERE id = ?",
                (dumps(proposal), old.id),
            )
            _unreview(conn, old.attempt_id)
            outcome = "reopened"
        else:
            outcome = "kept"
        stored = get_item(conn, old.id)
    assert stored is not None
    return stored, outcome


def _unreview(conn: sqlite3.Connection, attempt_id: str | None) -> None:
    """A new open item on a ``reviewed`` attempt: back to ``graded`` if it has a score, else
    ``extracted``. Any other status is left alone."""
    if attempt_id is None:
        return
    row = conn.execute(
        "SELECT status, score_earned FROM attempts WHERE id = ?", (attempt_id,)
    ).fetchone()
    if row is None or row[0] != "reviewed":
        return
    attempts.set_status(conn, attempt_id, "graded" if row[1] is not None else "extracted")


def mark_obsolete(
    conn: sqlite3.Connection, owner: Literal["extract", "grade"], attempt_id: str
) -> int:
    """Set the open items of ``owner`` for ``attempt_id`` to ``obsolete``. Returns the count."""
    with transaction(conn):
        cur = conn.execute(
            "UPDATE review_items SET status = 'obsolete'"
            " WHERE owner = ? AND attempt_id = ? AND status = 'open'",
            (owner, attempt_id),
        )
    return cur.rowcount


def count_open_for_attempt(conn: sqlite3.Connection, attempt_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM review_items WHERE attempt_id = ? AND status = 'open'",
        (attempt_id,),
    ).fetchone()
    return int(row[0])


def resolve_item(
    conn: sqlite3.Connection,
    item_id: str,
    status: Literal["accepted", "fixed", "skipped"],
    resolution: dict[str, Any] | None = None,
    followup_run_id: str | None = None,
) -> ReviewItem:
    """Record the teacher's decision on an open item (``resolved_at`` = now). If that was the
    attempt's last open item, the attempt becomes ``reviewed`` (data-model §5.3)."""
    with transaction(conn):
        item = get_item(conn, item_id)
        if item is None:
            raise KeyError(f"no review item {item_id}")
        if item.status != "open":
            raise ValueError(f"review item {item_id} is {item.status}, not open")
        conn.execute(
            "UPDATE review_items SET status = ?, resolution = ?, followup_run_id = ?,"
            " resolved_at = ? WHERE id = ?",
            (
                status,
                None if resolution is None else dumps(resolution),
                followup_run_id,
                now_iso(),
                item_id,
            ),
        )
        if item.attempt_id is not None and count_open_for_attempt(conn, item.attempt_id) == 0:
            attempts.set_status(conn, item.attempt_id, "reviewed")
        resolved = get_item(conn, item_id)
    assert resolved is not None
    return resolved


def settle_key_items(
    conn: sqlite3.Connection, test_id: str, question_id: str, by: Literal["key_photo"]
) -> list[str]:
    """A key photo's key replaced the question's AI key (or gave the key ``ai_key_fast`` could
    not): its open ``uncertain_key`` items are ``fixed`` with ``{"action": "fix", "value":
    {"by": by}}``, as a test-text save settles items (data-model §5.3). The photo's key stays.
    Returns the closed item ids."""
    rows = conn.execute(
        "SELECT id FROM review_items WHERE status = 'open' AND kind = 'uncertain_key'"
        " AND test_id = ? AND question_id = ? ORDER BY created_at, id",
        (test_id, question_id),
    ).fetchall()
    for (item_id,) in rows:
        resolve_item(conn, item_id, "fixed", {"action": "fix", "value": {"by": by}})
    return [r[0] for r in rows]


def count_open(conn: sqlite3.Connection) -> int:
    """The number of ``open`` items (the "Review · N" badge)."""
    row = conn.execute("SELECT COUNT(*) FROM review_items WHERE status = 'open'").fetchone()
    return int(row[0])


# --- review in place (step 22.1.5, PRD D27) --------------------------------------------------

# An open item belongs to a test when it is a test-level item of that test (no attempt), or an
# item of a current (not superseded) attempt on that test.
_OPEN_BY_TEST = (
    "SELECT r.id AS id, COALESCE(a.test_id, r.test_id) AS test_id"
    " FROM review_items r LEFT JOIN attempts a ON a.id = r.attempt_id"
    " WHERE r.status = 'open' AND (r.attempt_id IS NULL OR a.superseded_by IS NULL)"
)


def list_open_for_test(conn: sqlite3.Connection, test_id: str) -> list[ReviewItem]:
    """The open items of one test: its own and those of its current attempts, oldest first."""
    rows = conn.execute(
        "SELECT r.* FROM review_items r WHERE r.id IN"
        f" (SELECT id FROM ({_OPEN_BY_TEST}) WHERE test_id = ?) ORDER BY r.created_at, r.id",
        (test_id,),
    ).fetchall()
    return [from_row(ReviewItem, r, _JSON) for r in rows]


def open_counts_by_test(conn: sqlite3.Connection) -> dict[str, int]:
    """``{test_id: open items}`` (``GET /tests`` ``open_review_count``); tests with none absent."""
    rows = conn.execute(
        f"SELECT test_id, COUNT(*) FROM ({_OPEN_BY_TEST}) WHERE test_id IS NOT NULL"
        " GROUP BY test_id"
    ).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def count_open_for(conn: sqlite3.Connection, attempt_id: str | None, test_id: str | None) -> int:
    """A thread's open items (``GET /threads`` ``open_review_count``): those of its current
    attempt, plus the test-level items (no attempt) of its test."""
    row = conn.execute(
        "SELECT COUNT(*) FROM review_items WHERE status = 'open' AND"
        " ((? IS NOT NULL AND attempt_id = ?) OR (? IS NOT NULL AND attempt_id IS NULL"
        " AND test_id = ?))",
        (attempt_id, attempt_id, test_id, test_id),
    ).fetchone()
    return int(row[0])


def set_proposal(conn: sqlite3.Connection, item_id: str, proposal: dict[str, Any]) -> None:
    """Replace an item's proposal (an ``unreadable_text`` item whose spans changed)."""
    with transaction(conn):
        conn.execute(
            "UPDATE review_items SET proposal = ? WHERE id = ?", (dumps(proposal), item_id)
        )


def set_obsolete(conn: sqlite3.Connection, item_id: str) -> None:
    """Close one open item as ``obsolete`` (its question left the test). When that was its
    attempt's last open item, the attempt becomes ``reviewed`` (data-model §5.3)."""
    with transaction(conn):
        item = get_item(conn, item_id)
        if item is None or item.status != "open":
            return
        conn.execute("UPDATE review_items SET status = 'obsolete' WHERE id = ?", (item_id,))
        if item.attempt_id is not None and count_open_for_attempt(conn, item.attempt_id) == 0:
            attempts.set_status(conn, item.attempt_id, "reviewed")
