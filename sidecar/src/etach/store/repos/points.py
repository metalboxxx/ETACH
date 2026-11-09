"""Equal points in the store (PRD D13 v8.0, data-model v1.19, step 22.4.4).

- :func:`save_content`: every content save (text save, Review fixes, a content PATCH) writes the
  content with :func:`etach.domain.points.equal_points` applied and ``points_possible`` from it,
  then re-scores the test's graded attempts from their stored verdicts (no model call), so a score
  always reads ``x/10``.
- :func:`rescore_attempt`: earned = the correct questions times their points now; ``unsure`` stays
  unsure (``points_awarded`` None, counted in ``uncertain_points``); ``score_possible`` = 10.
- :func:`run_equal_points_pass`: the one-time first-start pass of migration 0009. It runs only
  while ``equal_points_pending`` holds its row and removes the row in the same transaction, so a
  second start changes nothing: every stored test gets clean option letters and equal points, open
  ``points_assumed`` items are closed (``obsolete``), open ``validator_failed`` items of a test
  whose content now validates are closed (``fixed``), and every graded attempt is re-scored.
"""

from __future__ import annotations

import json
import sqlite3

from etach.domain import points as domain_points
from etach.domain.models import TestContent
from etach.domain.validators import validate_content
from etach.store.db import now_iso, transaction
from etach.store.repos import tests as tests_repo

__all__ = ["rescore_attempt", "rescore_test", "run_equal_points_pass", "save_content"]


def rescore_attempt(conn: sqlite3.Connection, attempt_id: str, content: TestContent) -> None:
    """Re-score one graded attempt from its stored verdicts with the content's points."""
    pts = {
        q.id: q.points for s in content.sections if s.graded for g in s.groups for q in g.questions
    }
    earned = 0.0
    unsure = 0.0
    with transaction(conn):
        rows = conn.execute(
            "SELECT question_id, verdict FROM answers WHERE attempt_id = ?", (attempt_id,)
        ).fetchall()
        for question_id, verdict in rows:
            full = pts.get(question_id)
            if full is None or verdict == "ungraded":
                continue
            awarded: float | None
            if verdict == "correct":
                awarded = full
                earned += full
            elif verdict == "incorrect":
                awarded = 0.0
            else:
                awarded = None
                unsure += full
            conn.execute(
                "UPDATE answers SET points_awarded = ? WHERE attempt_id = ? AND question_id = ?",
                (awarded, attempt_id, question_id),
            )
        possible = domain_points.points_possible(content)
        conn.execute(
            "UPDATE attempts SET score_earned = ?, score_possible = ? WHERE id = ?",
            (round(earned, 4), possible, attempt_id),
        )
        conn.execute(
            "UPDATE grade_reports SET uncertain_points = ? WHERE attempt_id = ?",
            (round(unsure, 4), attempt_id),
        )
        _rescore_cards(conn, attempt_id, round(earned, 4), possible, round(unsure, 4))


def _rescore_cards(
    conn: sqlite3.Connection, attempt_id: str, earned: float, possible: float, unsure: float
) -> None:
    """The thread's grade cards of this attempt show the new score."""
    rows = conn.execute(
        "SELECT id, body FROM messages WHERE kind = 'grade_card'"
        " AND json_extract(body, '$.attempt_id') = ?",
        (attempt_id,),
    ).fetchall()
    for msg_id, raw in rows:
        payload = json.loads(raw)
        payload.update(score_earned=earned, score_possible=possible, uncertain_points=unsure)
        conn.execute("UPDATE messages SET body = ? WHERE id = ?", (json.dumps(payload), msg_id))


def _graded_ids(conn: sqlite3.Connection, test_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT id FROM attempts WHERE test_id = ? AND score_earned IS NOT NULL", (test_id,)
    ).fetchall()
    return [r[0] for r in rows]


def rescore_test(conn: sqlite3.Connection, test_id: str, content: TestContent) -> None:
    """Re-score every graded attempt of the test (superseded ones too: they keep a score)."""
    for attempt_id in _graded_ids(conn, test_id):
        rescore_attempt(conn, attempt_id, content)


def save_content(conn: sqlite3.Connection, test_id: str, content: TestContent) -> TestContent:
    """Write the content with equal points and re-score the graded attempts. Returns the
    content as stored."""
    content = tests_repo.with_contexts(domain_points.equal_points(content))
    with transaction(conn):
        tests_repo.update_content(conn, test_id, content, domain_points.points_possible(content))
        rescore_test(conn, test_id, content)
    return content


def run_equal_points_pass(conn: sqlite3.Connection) -> bool:
    """The first-start pass (see the module docstring). Returns whether it ran."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'equal_points_pending'"
    ).fetchone()
    if not exists or not conn.execute("SELECT 1 FROM equal_points_pending").fetchone():
        return False
    with transaction(conn):
        for (test_id,) in conn.execute("SELECT id FROM tests ORDER BY id").fetchall():
            test = tests_repo.get_test(conn, test_id)
            if test is None:  # pragma: no cover - the id was just listed
                continue
            content = save_content(conn, test_id, test.content)
            if not validate_content(content, test.meta.omitted_sections):
                conn.execute(
                    "UPDATE review_items SET status = 'fixed', resolution = ?, resolved_at = ?"
                    " WHERE test_id = ? AND kind = 'validator_failed' AND status = 'open'"
                    " AND attempt_id IS NULL",
                    (json.dumps({"action": "equal_points_pass"}), now_iso(), test_id),
                )
        conn.execute(
            "UPDATE review_items SET status = 'obsolete', resolved_at = ?"
            " WHERE kind = 'points_assumed' AND status = 'open'",
            (now_iso(),),
        )
        conn.execute("DELETE FROM equal_points_pending")
    return True
