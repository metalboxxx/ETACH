"""R10.3: merging a duplicate test into the surviving bank test (data-model §5.4)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from etach.domain import models as m
from etach.domain.merge import merge
from etach.store import db
from etach.store.repos import attempts, keys, review, runs, tests, threads

T0 = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    c = db.open_database(tmp_path / "data" / "app.db")
    yield c
    c.close()


def _content(prefix: str, n: int = 3) -> m.TestContent:
    questions = [
        m.Question(
            id=f"{prefix}{i}",
            number=i,
            printed_number=i,
            page_no=1,
            answer_form="choice",
            stem=f"Stem {i}",
            options=[m.Option(label="A", text="one"), m.Option(label="B", text="two")],
            cue=None,
            points=0.25,
        )
        for i in range(1, n + 1)
    ]
    group = m.QuestionGroup(id="g-1", stimulus=None, pictures=[], questions=questions)
    section = m.Section(
        id="s-1",
        number=1,
        printed_title="I",
        title="Choose",
        instructions="Circle A or B.",
        points=0.25 * n,
        points_source="printed",
        skill="grammar",
        groups=[group],
    )
    return m.TestContent(sections=[section])


def _test(conn: sqlite3.Connection, prefix: str) -> str:
    t = m.Test(
        id=tests.next_test_id(conn),
        meta=m.TestMetadata(occasion="FinalTerm", grade=8, term=1, test_number="1"),
        content=_content(prefix),
        content_schema_version=1,
        fingerprint="fp",
        points_possible=0.75,
        source_run_id=None,
        merged_into=None,
        created_at=T0,
        updated_at=T0,
    )
    return tests.insert_test(conn, t).id


def _attempt(
    conn: sqlite3.Connection,
    test_id: str,
    qids: list[str],
    *,
    score: float | None = None,
    superseded_by: str | None = None,
) -> m.Attempt:
    thread = threads.create_thread(conn, "photos", kind="filled", test_id=test_id)
    run = runs.create_run(
        conn,
        thread.id,
        "extract",
        m.ExtractInput(pages=[], existing_test_id=None, supersedes_attempt_id=None),
        status="done",
    )
    att = attempts.insert_attempt(
        conn,
        m.Attempt(
            id=attempts.next_attempt_id(conn),
            test_id=test_id,
            thread_id=thread.id,
            student_id=None,
            student_name_read=None,
            class_read=None,
            source_run_id=run.id,
            superseded_by=superseded_by,
            status="graded" if score is not None else "extracted",
            version=1,
            score_earned=score,
            score_possible=None,
            created_at=T0,
        ),
    )
    attempts.insert_answers(
        conn,
        [
            m.Answer(
                attempt_id=att.id,
                question_id=q,
                printed_number=i + 1,
                page_no=1,
                value="A",
                value_norm="a",
                location="circled_option",
                confidence=0.95,
                reading_unsure=False,
                alt_value=None,
                alt_question_id=None,
                verdict="correct" if score is not None else "ungraded",
                points_awarded=0.25 if score is not None else None,
                teacher_override=None,
            )
            for i, q in enumerate(qids)
        ],
    )
    return att


def _key(test_id: str, qid: str, accepted: str, source: str = "ai") -> m.AnswerKey:
    return m.AnswerKey(
        test_id=test_id,
        question_id=qid,
        accepted=[accepted],
        reason_vi=None,
        source=source,  # type: ignore[arg-type]
        status="ai_verified",
        confidence=0.9,
        updated_at=T0,
    )


def _answers(conn: sqlite3.Connection, attempt_id: str) -> dict[str, str]:
    return {a.question_id: a.verdict for a in attempts.list_answers(conn, attempt_id)}


def _grade_runs(conn: sqlite3.Connection) -> list[m.Run]:
    return [r for r in runs.list_runs(conn, status="queued") if r.kind == "grade"]


def _dump(conn: sqlite3.Connection) -> dict[str, list[tuple[Any, ...]]]:
    names = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return {n: sorted(map(tuple, conn.execute(f"SELECT * FROM {n}")), key=repr) for n in names}


@pytest.fixture
def pair(conn: sqlite3.Connection) -> tuple[str, str]:
    """(survivor, merged): survivor questions s1..s3, merged questions m1..m3."""
    return _test(conn, "s"), _test(conn, "m")


ALIGN = {"m1": "s2", "m2": "s1"}  # m3 unaligned; a swap against the printed order


def test_answers_remapped_via_alignment_and_unaligned_kept(
    conn: sqlite3.Connection, pair: tuple[str, str]
) -> None:
    survivor, merged = pair
    att = _attempt(conn, merged, ["m1", "m2", "m3"], score=0.5)
    report = merge(conn, merged_test_id=merged, survivor_test_id=survivor, alignment=ALIGN, ref="R")
    # m1 → s2 and m2 → s1 by the alignment, not by printed number; m3 stays, ungraded
    assert _answers(conn, att.id) == {"s1": "correct", "s2": "correct", "m3": "ungraded"}
    kept = attempts.get_answer(conn, att.id, "m3")
    assert kept is not None and kept.points_awarded is None
    assert report.remapped_answers == 2
    [item] = review.list_items(conn, attempt_id=att.id)
    assert (item.kind, item.owner, item.status, item.question_id) == (
        "merge_unaligned",
        "extract",
        "open",
        "m3",
    )
    assert item.dedupe_key == f"merge_unaligned:R:{att.id}:m3"
    assert item.proposal["old_question_id"] == "m3"
    assert item.proposal["candidate_question_ids"] == ["s3"]
    assert report.unaligned_item_ids == [item.id]


def test_collision_keeps_answers_on_old_questions(
    conn: sqlite3.Connection, pair: tuple[str, str]
) -> None:
    survivor, merged = pair
    att = _attempt(conn, merged, ["m1", "m2", "m3"])
    merge(
        conn,
        merged_test_id=merged,
        survivor_test_id=survivor,
        alignment={"m1": "s1", "m2": "s1", "m3": "s3"},
        ref="R",
    )
    assert _answers(conn, att.id) == {"m1": "ungraded", "m2": "ungraded", "s3": "ungraded"}
    items = review.list_items(conn, attempt_id=att.id)
    assert sorted(i.question_id or "" for i in items) == ["m1", "m2"]
    assert all(i.kind == "merge_unaligned" and i.proposal["reason"] == "collision" for i in items)


def test_attempts_threads_meta_and_fts(conn: sqlite3.Connection, pair: tuple[str, str]) -> None:
    survivor, merged = pair
    att = _attempt(conn, merged, ["m1"])
    old = _attempt(conn, merged, ["m1"], score=0.25)
    attempts.set_superseded_by(conn, old.id, att.id)
    merge(conn, merged_test_id=merged, survivor_test_id=survivor, alignment=ALIGN, ref="R")
    for a in (att, old):
        stored = attempts.get_attempt(conn, a.id)
        thread = threads.get_thread(conn, a.thread_id)
        assert stored is not None and stored.test_id == survivor
        assert thread is not None and thread.test_id == survivor
    t = tests.get_test(conn, merged)
    assert t is not None and t.merged_into == survivor  # set, and never deleted
    fts = conn.execute("SELECT test_id FROM tests_fts").fetchall()
    assert [r[0] for r in fts] == [survivor]


def test_keys_and_tags_copied_only_where_missing(
    conn: sqlite3.Connection, pair: tuple[str, str]
) -> None:
    survivor, merged = pair
    keys.upsert_key(conn, _key(survivor, "s1", "B", "teacher_edit"))
    keys.upsert_key(conn, _key(merged, "m2", "A"))  # → s1: survivor has one, kept
    keys.upsert_key(conn, _key(merged, "m1", "A"))  # → s2: copied
    keys.upsert_key(conn, _key(merged, "m3", "A"))  # unaligned: not copied
    tests.set_question_tags(conn, survivor, "s2", ["tense"])
    tests.set_question_tags(conn, merged, "m1", ["article"])  # → s2: survivor has tags, kept
    tests.set_question_tags(conn, merged, "m2", ["plural"])  # → s1: copied
    report = merge(conn, merged_test_id=merged, survivor_test_id=survivor, alignment=ALIGN, ref="R")
    got = {k.question_id: (k.accepted, k.source) for k in keys.list_keys(conn, survivor)}
    assert got == {"s1": (["B"], "teacher_edit"), "s2": (["A"], "ai")}
    assert tests.list_question_tags(conn, survivor) == {"s1": ["plural"], "s2": ["tense"]}
    assert (report.keys_copied, report.tags_copied) == (["s2"], ["s1"])
    assert len(keys.list_keys(conn, merged)) == 3  # the merged test's rows stay


def test_merge_keeps_question_levels(conn: sqlite3.Connection, pair: tuple[str, str]) -> None:
    survivor, merged = pair
    tests.set_question_tags(conn, merged, "m2", ["GR-QNT-A2"], "B1")  # → s1
    tests.set_question_tags(conn, merged, "m1", ["VOC-TOPIC"])  # → s2: no level given
    merge(conn, merged_test_id=merged, survivor_test_id=survivor, alignment=ALIGN, ref="R")
    assert tests.list_question_levels(conn, survivor) == {"s1": "B1", "s2": None}
    assert tests.list_tag_levels(conn, survivor) == {
        "s1": {"GR-QNT-A2": "B1"},
        "s2": {"VOC-TOPIC": "A1"},
    }


def test_one_grade_run_per_moved_graded_attempt(
    conn: sqlite3.Connection, pair: tuple[str, str]
) -> None:
    survivor, merged = pair
    graded = _attempt(conn, merged, ["m1"], score=0.25)
    reviewed = _attempt(conn, merged, ["m2"], score=0.25)
    attempts.set_status(conn, reviewed.id, "reviewed")
    _attempt(conn, merged, ["m1"])  # ungraded: no run
    newer = _attempt(conn, merged, ["m1"])
    superseded = _attempt(conn, merged, ["m1"], score=0.25)
    attempts.set_superseded_by(conn, superseded.id, newer.id)  # graded but superseded: no run
    _attempt(conn, survivor, ["s1"], score=0.25)  # already on the survivor: not moved, no run
    report = merge(conn, merged_test_id=merged, survivor_test_id=survivor, alignment=ALIGN, ref="R")
    queued = _grade_runs(conn)
    assert sorted(r.id for r in queued) == sorted(report.grade_run_ids)
    by_attempt = {r.input.attempt_id: r for r in queued if isinstance(r.input, m.GradeInput)}
    assert set(by_attempt) == {graded.id, reviewed.id}
    for att in (graded, reviewed):
        run = by_attempt[att.id]
        assert run.thread_id == att.thread_id
        assert run.input == m.GradeInput(test_id=survivor, attempt_id=att.id, reason="merge")


def test_exception_mid_merge_leaves_database_unchanged(
    conn: sqlite3.Connection, pair: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    survivor, merged = pair
    _attempt(conn, merged, ["m1", "m2", "m3"], score=0.5)
    keys.upsert_key(conn, _key(merged, "m1", "A"))
    tests.set_question_tags(conn, merged, "m2", ["plural"])
    before = _dump(conn)

    def boom(*_a: Any, **_k: Any) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(runs, "enqueue_grade", boom)  # the last step, after every other write
    with pytest.raises(RuntimeError, match="boom"):
        merge(conn, merged_test_id=merged, survivor_test_id=survivor, alignment=ALIGN, ref="R")
    assert not conn.in_transaction
    assert _dump(conn) == before


@pytest.mark.parametrize("case", ["self", "already_merged", "missing"])
def test_invalid_merge_is_refused(
    conn: sqlite3.Connection, pair: tuple[str, str], case: str
) -> None:
    survivor, merged = pair
    if case == "already_merged":
        merge(conn, merged_test_id=merged, survivor_test_id=survivor, alignment={}, ref="R")
    before = _dump(conn)
    target = {"self": survivor, "already_merged": merged, "missing": "T-9999"}[case]
    with pytest.raises((ValueError, KeyError)):
        merge(conn, merged_test_id=target, survivor_test_id=survivor, alignment={}, ref="R2")
    assert _dump(conn) == before
