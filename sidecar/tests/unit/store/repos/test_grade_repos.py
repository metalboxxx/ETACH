"""Step 18: the repo functions added for the grade graph's ``save`` and weak points."""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from typing import Any

from etach.store.repos import attempts, explanations, students, tests


def test_skill_stats_by_attempt_counts_careless_per_attempt(
    conn: sqlite3.Connection, f: Any
) -> None:
    t = f.make_test(conn, content=f.content(4))
    s = students.create_student(conn, "Hoc Sinh A", "8A")
    old = f.make_attempt(conn, t.id, s.id, created_at=f.T0)
    new = f.make_attempt(conn, t.id, s.id, created_at=f.T0 + timedelta(days=1))
    gone = f.make_attempt(conn, t.id, s.id, superseded_by=new.id)
    other = f.make_attempt(conn, t.id, None)
    for qid in ("q-1", "q-2", "q-3", "q-4"):
        tests.set_question_tags(conn, t.id, qid, ["GR-X"])
    call = f.make_llm_call(conn).id
    explanations.upsert_explanation(conn, f.explanation(t.id, "q-2", "b", call, "gap"))
    explanations.upsert_explanation(conn, f.explanation(t.id, "q-3", "b", call, "spelling"))
    explanations.upsert_explanation(conn, f.explanation(t.id, "q-4", "b", call, "careless"))
    for att in (old, new, gone, other):
        attempts.insert_answers(
            conn,
            [
                f.answer(att.id, "q-1", verdict="correct"),
                f.answer(att.id, "q-2", value="B", value_norm="b", verdict="incorrect"),
                f.answer(att.id, "q-3", value="B", value_norm="b", verdict="incorrect"),
                f.answer(att.id, "q-4", value="B", value_norm="b", verdict="uncertain"),
            ],
        )
    rows = attempts.skill_stats_by_attempt(conn, s.id)
    assert [(r.attempt_id, r.seen, r.wrong, r.gap_errors, r.careless) for r in rows] == [
        (old.id, 3, 2, 1, 1),
        (new.id, 3, 2, 1, 1),
    ]
    assert [
        r.attempt_id for r in attempts.skill_stats_by_attempt(conn, s.id, exclude_attempt_id=new.id)
    ] == [old.id]


def test_set_answer_grade_keeps_the_override(conn: sqlite3.Connection, f: Any) -> None:
    t = f.make_test(conn)
    att = f.make_attempt(conn, t.id)
    attempts.insert_answers(conn, [f.answer(att.id, "q-1", teacher_override="")])
    graded = f.answer(
        att.id, "q-1", teacher_override="X", verdict="incorrect", points_awarded=0.0, value_norm=""
    )
    attempts.set_answer_grade(conn, graded)
    stored = attempts.get_answer(conn, att.id, "q-1")
    assert stored is not None
    assert (stored.verdict, stored.points_awarded, stored.value_norm) == ("incorrect", 0.0, "")
    assert stored.teacher_override == ""
    attempts.set_graded(conn, att.id, 0.25, 0.5)
    a = attempts.get_attempt(conn, att.id)
    assert a is not None and (a.status, a.score_earned, a.score_possible) == ("graded", 0.25, 0.5)
