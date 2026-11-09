"""Extract again into the same test (PRD "Extract again", decision D8, data-model v1.21).

:func:`replace_test` saves a new reading of a thread's photos into the test the thread already
uses, so the test id stays and no "looks like" item points at the old reading. It runs inside the
extract ``save`` transaction, before the new attempt is written. In order:

1. **Match.** ``similarity.align_reading``: the new question ids → the old ones. A pair whose
   printed number and text are the same is *exact*.
2. **Keys.** Every key on an exact pair stays, with its source, status, confidence and
   explanations: one the teacher typed or verified, and an AI or key-photo key with its unsure
   state (data-model v1.21.1, D8 addition). The key rows and explanations of every other question
   go: changed and new questions are keyed again from the key photo (this run) or by the AI at
   grading.
3. **Tags.** Skill tags move with every matched question; tags of removed questions go.
4. **Answers** of every attempt on the test, superseded ones too: an answer on a matched question
   moves to the new id (two steps through a temporary id, so a swap cannot clash; an
   ``alt_question_id`` follows); an answer on a removed question is deleted. A current attempt gets
   an empty answer row for each new graded question (as a test-text save does). Changed attempts
   get ``version + 1``.
5. **Review items** (open only): on a removed question, or an ``uncertain_key`` whose key was
   dropped → ``obsolete``; on a matched question → the new id (also in ``dedupe_key``; if that
   key is taken, the item is closed instead). The old reading's test-level extract items
   (validator failures, unreadable text, the old "looks like") are closed; the new run writes its
   own.
6. **The test.** The content is saved with equal points (graded attempts are re-scored from
   their verdicts), with the new fingerprint; the read metadata is written as an AI write (a
   field the teacher set is kept); ``test_pages`` are replaced.

The caller marks ``regrade_pending`` once the thread's own attempt is superseded, so only the other
threads' graded attempts count. No grading run starts.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from etach.domain.models import Answer, TestContent
from etach.domain.similarity import align_reading
from etach.domain.working import PreparedPage, TestDraft
from etach.store.db import now_iso, transaction, write_test_meta
from etach.store.repos import attempts, keys
from etach.store.repos import points as points_repo
from etach.store.repos import tests as tests_repo

__all__ = ["READ_META_FIELDS", "ReplaceReport", "replace_test"]

#: The metadata a new reading writes (an AI write: fields in ``edited_fields`` are kept).
READ_META_FIELDS: tuple[str, ...] = (
    "occasion",
    "grade",
    "year",
    "school",
    "term",
    "test_number",
    "variant",
    "test_code",
    "region",
    "source",
    "textbook",
    "units",
    "duration_minutes",
    "exam_format",
    "omitted_sections",
)

_TMP = "\x00again:"


@dataclass
class ReplaceReport:
    matched: dict[str, str] = field(default_factory=dict)  # old question id → new question id
    exact: set[str] = field(default_factory=set)  # new ids whose number and text match
    removed: list[str] = field(default_factory=list)  # old ids not in the new reading
    keys_kept: list[str] = field(default_factory=list)  # new ids
    answers_moved: int = 0
    items_closed: int = 0


def _ids(content: TestContent) -> list[str]:
    return [q.id for s in content.sections for g in s.groups for q in g.questions]


def _move_keys(conn: sqlite3.Connection, test_id: str, report: ReplaceReport) -> None:
    exact_old = {old for old, new in report.matched.items() if new in report.exact}
    kept = [k for k in keys.list_keys(conn, test_id) if k.question_id in exact_old]
    kept_old = {k.question_id for k in kept}
    explanations = conn.execute(
        "SELECT * FROM explanations WHERE test_id = ?", (test_id,)
    ).fetchall()
    conn.execute("DELETE FROM explanations WHERE test_id = ?", (test_id,))
    conn.execute("DELETE FROM answer_keys WHERE test_id = ?", (test_id,))
    for key in kept:
        new_id = report.matched[key.question_id]
        keys.upsert_key(conn, key.model_copy(update={"question_id": new_id}))
        report.keys_kept.append(new_id)
    for row in explanations:
        if row["question_id"] not in kept_old:
            continue
        values: dict[str, Any] = dict(row)
        values["question_id"] = report.matched[row["question_id"]]
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        conn.execute(f"INSERT INTO explanations ({cols}) VALUES ({marks})", tuple(values.values()))


def _move_tags(conn: sqlite3.Connection, test_id: str, report: ReplaceReport) -> None:
    tags = tests_repo.list_question_tags(conn, test_id)
    levels = tests_repo.list_question_levels(conn, test_id)
    conn.execute("DELETE FROM question_tags WHERE test_id = ?", (test_id,))
    for old_id, values in tags.items():
        new_id = report.matched.get(old_id)
        if new_id is not None:
            tests_repo.set_question_tags(conn, test_id, new_id, values, levels.get(old_id))


def _move_answers(
    conn: sqlite3.Connection, test_id: str, new: TestContent, report: ReplaceReport
) -> None:
    moves = {old: new_id for old, new_id in report.matched.items() if old != new_id}
    fresh = [
        q
        for s in new.sections
        if s.graded
        for g in s.groups
        for q in g.questions
        if q.id not in report.matched.values() and q.answer_form != "writing"
    ]
    for att in attempts.list_attempts(conn, test_id=test_id, include_superseded=True):
        changed = False
        for old in report.removed:
            cur = conn.execute(
                "DELETE FROM answers WHERE attempt_id = ? AND question_id = ?", (att.id, old)
            )
            changed |= cur.rowcount > 0
            conn.execute(
                "UPDATE answers SET alt_question_id = NULL"
                " WHERE attempt_id = ? AND alt_question_id = ?",
                (att.id, old),
            )
        moved = _move(conn, att.id, "question_id", moves)
        _move(conn, att.id, "alt_question_id", moves)
        report.answers_moved += moved
        changed |= moved > 0
        if fresh and att.superseded_by is None:
            rows = [_empty_answer(att.id, q.id, q.printed_number) for q in fresh]
            attempts.insert_answers(conn, rows)
            changed = True
        if changed:
            attempts.bump_version(conn, att.id)


def _move(conn: sqlite3.Connection, attempt_id: str, column: str, moves: dict[str, str]) -> int:
    """Set ``column`` of the attempt's answers from each old id to its new id, through a temporary
    id, so a swap (q-1 → q-2, q-2 → q-1) cannot clash. Returns the number of answers moved."""
    sql = f"UPDATE answers SET {column} = ? WHERE attempt_id = ? AND {column} = ?"
    moved = sum(conn.execute(sql, (_TMP + old, attempt_id, old)).rowcount for old in moves)
    for old, new_id in moves.items():
        conn.execute(sql, (new_id, attempt_id, _TMP + old))
    return moved


def _empty_answer(attempt_id: str, question_id: str, printed_number: int) -> Answer:
    return Answer(
        attempt_id=attempt_id,
        question_id=question_id,
        printed_number=printed_number,
        page_no=None,
        value=None,
        value_norm=None,
        location="none",
        confidence=0.0,
        reading_unsure=False,
        alt_value=None,
        alt_question_id=None,
        points_awarded=None,
        teacher_override=None,
    )


def _move_items(conn: sqlite3.Connection, test_id: str, report: ReplaceReport) -> None:
    now = now_iso()
    kept_keys = set(report.keys_kept)
    rows = conn.execute(
        "SELECT id, kind, owner, attempt_id, question_id, dedupe_key FROM review_items"
        " WHERE status = 'open' AND (test_id = ?"
        " OR attempt_id IN (SELECT id FROM attempts WHERE test_id = ?))",
        (test_id, test_id),
    ).fetchall()
    close: list[str] = []
    for item_id, kind, owner, attempt_id, qid, dedupe_key in rows:
        if qid is None:
            if owner == "extract" and attempt_id is None:
                close.append(item_id)  # the old reading's own items
            continue
        new_id = report.matched.get(qid)
        if new_id is None or (kind == "uncertain_key" and new_id not in kept_keys):
            close.append(item_id)
            continue
        if new_id == qid:
            continue
        new_key = dedupe_key.replace(qid, new_id)
        taken = conn.execute(
            "SELECT 1 FROM review_items WHERE dedupe_key = ? AND id <> ?", (new_key, item_id)
        ).fetchone()
        if taken:
            close.append(item_id)
            continue
        conn.execute(
            "UPDATE review_items SET question_id = ?, dedupe_key = ? WHERE id = ?",
            (new_id, _TMP + item_id, item_id),
        )
        conn.execute("UPDATE review_items SET dedupe_key = ? WHERE id = ?", (new_key, item_id))
    for item_id in close:
        conn.execute(
            "UPDATE review_items SET status = 'obsolete', resolved_at = ? WHERE id = ?",
            (now, item_id),
        )
    report.items_closed = len(close)


def replace_test(
    conn: sqlite3.Connection, test_id: str, draft: TestDraft, pages: list[PreparedPage]
) -> ReplaceReport:
    """Save the new reading ``draft`` into ``test_id`` (module docstring)."""
    with transaction(conn):
        old = tests_repo.get_test(conn, test_id)
        if old is None:
            raise KeyError(f"no test {test_id}")
        pairs, exact = align_reading(draft.content, old.content)
        report = ReplaceReport(matched={o: n for n, o in pairs.items()}, exact=exact)
        report.removed = [q for q in _ids(old.content) if q not in report.matched]
        _move_keys(conn, test_id, report)
        _move_tags(conn, test_id, report)
        _move_answers(conn, test_id, draft.content, report)
        _move_items(conn, test_id, report)
        points_repo.save_content(conn, test_id, draft.content)
        tests_repo.set_fingerprint(conn, test_id, draft.fingerprint)
        meta = draft.meta.model_dump()
        write_test_meta(conn, test_id, {f: meta[f] for f in READ_META_FIELDS}, by_teacher=False)
        conn.execute("DELETE FROM test_pages WHERE test_id = ?", (test_id,))
        for page in pages:
            tests_repo.add_test_page(conn, test_id, page.page_no, page.file_id)
    return report
