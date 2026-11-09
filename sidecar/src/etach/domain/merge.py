"""Merge a duplicate test into the surviving bank test (data-model §5.4, plan R10.3).

One transaction: any exception rolls every table back.

1. The alignment (new question_id → survivor question_id, from ``compare_bank``) remaps each moved
   attempt's ``answers.question_id``. Printed numbers are never used.
2. A collision (two answers of one attempt → one survivor question) or an unaligned question
   keeps that answer on its old question as ``ungraded`` and opens a ``merge_unaligned`` Review
   item. An aligned answer whose target is taken by such a kept answer also stays (the answer
   table's key is ``(attempt_id, question_id)``), repeated until nothing collides.
3. ``attempts.test_id`` and ``threads.test_id`` move to the survivor.
4. Key rows and ``question_tags`` are copied (through the alignment) only where the survivor has
   none; keys go through the guarded upsert. The key photos (``test_key_pages``) move to the
   survivor when it has none (data-model v1.12).
5. ``tests.merged_into`` is set and the ``tests_fts`` row removed; the test is never deleted.
6. One ``merge`` grade run is queued per moved *graded* attempt (score set, not superseded).

This module is one of the two ``domain/`` services allowed to call ``store/`` (structure rule 5).
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field

from etach.domain.models import AnswerKey, TestContent
from etach.store.db import now_iso, transaction
from etach.store.repos import attempts, keys, review, runs, tests

__all__ = ["MergeReport", "merge", "survivor_question_ids"]


@dataclass
class MergeReport:
    merged_test_id: str
    survivor_test_id: str
    moved_attempt_ids: list[str] = field(default_factory=list)
    remapped_answers: int = 0
    unaligned_item_ids: list[str] = field(default_factory=list)
    keys_copied: list[str] = field(default_factory=list)  # survivor question ids
    tags_copied: list[str] = field(default_factory=list)  # survivor question ids
    grade_run_ids: list[str] = field(default_factory=list)


def survivor_question_ids(content: TestContent) -> list[str]:
    """Question ids in content order."""
    return [q.id for s in content.sections for g in s.groups for q in g.questions]


def _split(
    old_qids: list[str], alignment: Mapping[str, str], valid: set[str]
) -> tuple[dict[str, str], set[str]]:
    """``(moves, kept)``: old qid → survivor qid for the answers that move, and the old qids of
    the answers that stay (unaligned, collision, or target taken by a kept answer)."""
    kept = {q for q in old_qids if alignment.get(q) not in valid}
    while True:
        movers = [q for q in old_qids if q not in kept]
        counts = Counter(alignment[q] for q in movers)
        bad = {q for q in movers if counts[alignment[q]] > 1 or alignment[q] in kept}
        if not bad:
            return {q: alignment[q] for q in movers}, kept
        kept |= bad


def merge(
    conn: sqlite3.Connection,
    *,
    merged_test_id: str,
    survivor_test_id: str,
    alignment: Mapping[str, str],
    ref: str,
) -> MergeReport:
    """Merge ``merged_test_id`` into ``survivor_test_id``. ``ref`` (the ``possible_duplicate``
    item id) goes into the ``merge_unaligned`` proposals and dedupe keys."""
    if merged_test_id == survivor_test_id:
        raise ValueError("a test cannot be merged into itself")
    report = MergeReport(merged_test_id, survivor_test_id)
    with transaction(conn):
        merged = tests.get_test(conn, merged_test_id)
        survivor = tests.get_test(conn, survivor_test_id)
        if merged is None or survivor is None:
            raise KeyError(f"no test {merged_test_id if merged is None else survivor_test_id}")
        if merged.merged_into is not None:
            raise ValueError(f"test {merged_test_id} is already merged")
        if survivor.merged_into is not None:
            raise ValueError(f"survivor {survivor_test_id} is itself merged")
        order = survivor_question_ids(survivor.content)
        valid = set(order)

        # 1-2: remap answers, attempt by attempt
        moved = attempts.list_attempts(conn, test_id=merged_test_id, include_superseded=True)
        for att in moved:
            report.moved_attempt_ids.append(att.id)
            answers = attempts.list_answers(conn, att.id)
            moves, kept = _split([a.question_id for a in answers], alignment, valid)
            # two steps through a temporary id, so a swap (q-1 → q-2, q-2 → q-1) cannot clash
            for old in moves:
                conn.execute(
                    "UPDATE answers SET question_id = ? WHERE attempt_id = ? AND question_id = ?",
                    ("\x00merge:" + old, att.id, old),
                )
            for old, new in moves.items():
                conn.execute(
                    "UPDATE answers SET question_id = ? WHERE attempt_id = ? AND question_id = ?",
                    (new, att.id, "\x00merge:" + old),
                )
            report.remapped_answers += len(moves)
            taken = set(moves.values())
            candidates = [q for q in order if q not in taken]
            for ans in answers:
                if ans.question_id not in kept:
                    continue
                conn.execute(
                    "UPDATE answers SET verdict = 'ungraded', points_awarded = NULL,"
                    " near_miss = 0 WHERE attempt_id = ? AND question_id = ?",
                    (att.id, ans.question_id),
                )
                target = alignment.get(ans.question_id)
                item, _ = review.upsert_item(
                    conn,
                    kind="merge_unaligned",
                    owner="extract",
                    dedupe_key=f"merge_unaligned:{ref}:{att.id}:{ans.question_id}",
                    proposal={
                        "ref": ref,
                        "merged_test_id": merged_test_id,
                        "survivor_test_id": survivor_test_id,
                        "old_question_id": ans.question_id,
                        "printed_number": ans.printed_number,
                        "value": ans.value,
                        "reason": "unaligned" if target not in valid else "collision",
                        "candidate_question_ids": candidates,
                    },
                    test_id=survivor_test_id,
                    attempt_id=att.id,
                    question_id=ans.question_id,
                )
                report.unaligned_item_ids.append(item.id)

        # 3: attempts and threads point to the survivor
        conn.execute(
            "UPDATE attempts SET test_id = ? WHERE test_id = ?", (survivor_test_id, merged_test_id)
        )
        conn.execute(
            "UPDATE threads SET test_id = ? WHERE test_id = ?", (survivor_test_id, merged_test_id)
        )

        # 4: keys and tags, only where the survivor has none
        have_keys = {k.question_id for k in keys.list_keys(conn, survivor_test_id)}
        for key in keys.list_keys(conn, merged_test_id):
            target = alignment.get(key.question_id)
            if target not in valid or target in have_keys:
                continue
            assert target is not None
            copy = AnswerKey.model_validate(
                key.model_dump() | {"test_id": survivor_test_id, "question_id": target}
            )
            if keys.upsert_key(conn, copy).outcome == "inserted":
                have_keys.add(target)
                report.keys_copied.append(target)
        have_tags = tests.list_question_tags(conn, survivor_test_id)
        merged_levels = tests.list_question_levels(conn, merged_test_id)  # D11d: levels kept
        for qid, tags in tests.list_question_tags(conn, merged_test_id).items():
            target = alignment.get(qid)
            if target not in valid or have_tags.get(target):
                continue
            assert target is not None
            tests.set_question_tags(conn, survivor_test_id, target, tags, merged_levels.get(qid))
            have_tags[target] = tags
            report.tags_copied.append(target)

        if not tests.list_key_pages(conn, survivor_test_id):
            conn.execute(
                "UPDATE test_key_pages SET test_id = ? WHERE test_id = ?",
                (survivor_test_id, merged_test_id),
            )

        # 5: mark merged, out of search
        conn.execute(
            "UPDATE tests SET merged_into = ?, updated_at = ? WHERE id = ?",
            (survivor_test_id, now_iso(), merged_test_id),
        )
        conn.execute("DELETE FROM tests_fts WHERE test_id = ?", (merged_test_id,))

        # 6: follow-ups, graded attempts only (data-model §5.3)
        moved_ids = set(report.moved_attempt_ids)
        for attempt_id in attempts.graded_attempts(conn, survivor_test_id):
            if attempt_id in moved_ids:
                report.grade_run_ids.append(
                    runs.enqueue_grade(
                        conn, test_id=survivor_test_id, attempt_id=attempt_id, reason="merge"
                    )
                )
    return report
