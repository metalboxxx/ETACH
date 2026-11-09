"""attempts, attempt_pages, answers, grade_reports."""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from etach.domain import models as m
from etach.store.repos import attempts, files


def test_attempt_round_trip_and_updates(conn: sqlite3.Connection, f: Any) -> None:
    t = f.make_test(conn)
    a = f.make_attempt(conn, t.id, student_name_read="Học Sinh A", class_read="8X1")
    assert a.id == "A-0001"
    assert attempts.get_attempt(conn, a.id) == a
    assert attempts.find_by_source_run(conn, a.source_run_id) == a
    rerun = f.make_run(conn, a.thread_id)
    b = f.make_attempt(conn, t.id, thread_id=a.thread_id, source_run_id=rerun.id)
    attempts.set_superseded_by(conn, a.id, b.id)
    assert attempts.current_attempt(conn, a.thread_id) == b
    assert [x.id for x in attempts.list_attempts(conn, test_id=t.id)] == [b.id]
    assert len(attempts.list_attempts(conn, test_id=t.id, include_superseded=True)) == 2
    attempts.bump_version(conn, b.id)
    attempts.set_status(conn, b.id, "graded")
    got = attempts.get_attempt(conn, b.id)
    assert got is not None and (got.version, got.status) == (2, "graded")
    with pytest.raises(sqlite3.IntegrityError):
        attempts.set_student(conn, b.id, "S-9999")
    with pytest.raises(KeyError):
        attempts.set_status(conn, "A-9999", "graded")


def test_pages_answers_and_report(conn: sqlite3.Connection, f: Any) -> None:
    t = f.make_test(conn)
    a = f.make_attempt(conn, t.id)
    for fid in ("aa", "bb"):
        files.insert_file(
            conn,
            m.File(
                id=fid,
                path=f"files/{fid}",
                kind="upload",
                derived_from=None,
                mime="image/png",
                width=None,
                height=None,
                created_at=f.T0,
            ),
        )
    page = m.AttemptPage(attempt_id=a.id, page_no=1, file_id="bb", source_file_id="aa", rotation=90)
    attempts.add_attempt_pages(conn, [page])
    assert attempts.list_attempt_pages(conn, a.id) == [page]
    ans = [
        f.answer(a.id, "q-1", printed_number=5, low_trust=True),
        f.answer(a.id, "q-2", printed_number=6, value=None, value_norm=None, location="none"),
    ]
    attempts.insert_answers(conn, ans)
    assert attempts.list_answers(conn, a.id) == ans
    fixed = ans[0].model_copy(
        update={"teacher_override": "B", "value_norm": "b", "verdict": "correct"}
    )
    attempts.update_answer(conn, fixed)
    assert attempts.get_answer(conn, a.id, "q-1") == fixed
    run = f.make_run(conn)
    report = m.GradeReport(
        attempt_id=a.id,
        run_id=run.id,
        weak_points=[m.WeakPoint(skill_tag="grammar", wrong=1, seen=2, gap_errors=1, note_vi="x")],
        careless_notes=["chính tả"],
        summary_vi="Tóm tắt",
        teacher_questions=[m.TeacherQuestion(question_vi="?", what_answers_mean_vi="…")],
        uncertain_points=0.5,
        created_at=f.T0,
    )
    attempts.replace_grade_report(conn, report)
    newer = report.model_copy(update={"summary_vi": "Mới"})
    attempts.replace_grade_report(conn, newer)
    assert attempts.get_grade_report(conn, a.id) == newer
    assert conn.execute("SELECT COUNT(*) FROM grade_reports").fetchone()[0] == 1
