"""``attempts``, ``attempt_pages``, ``answers`` and ``grade_reports`` (data-model §2.5).

Attempt IDs are ``A-0001``, ``A-0002``, …
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import date
from typing import Literal

from etach.domain.models import Answer, Attempt, AttemptPage, GradeReport, Test
from etach.domain.weakpoints import PaperSkill, SkillStats, paper_skill_results
from etach.store.db import transaction
from etach.store.repos import tests
from etach.store.repos._common import from_row, insert_model, next_readable_id, to_row

__all__ = [
    "add_attempt_pages",
    "bump_version",
    "count_answers_for_question",
    "current_attempt",
    "delete_answers_for_question",
    "find_by_source_run",
    "get_answer",
    "get_attempt",
    "get_grade_report",
    "graded_attempts",
    "insert_answers",
    "insert_attempt",
    "list_answers",
    "list_attempt_pages",
    "list_attempts",
    "move_answer",
    "next_attempt_id",
    "replace_grade_report",
    "set_answer_grade",
    "set_graded",
    "set_status",
    "set_student",
    "set_superseded_by",
    "skill_stats_by_attempt",
    "update_answer",
]

_REPORT_JSON = ("weak_points", "careless_notes", "teacher_questions")


def next_attempt_id(conn: sqlite3.Connection) -> str:
    return next_readable_id(conn, "attempts", "A")


# --- attempts --------------------------------------------------------------------------------


def insert_attempt(conn: sqlite3.Connection, attempt: Attempt) -> Attempt:
    with transaction(conn):
        insert_model(conn, "attempts", attempt)
    return attempt


def get_attempt(conn: sqlite3.Connection, attempt_id: str) -> Attempt | None:
    row = conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    return None if row is None else from_row(Attempt, row)


def find_by_source_run(conn: sqlite3.Connection, run_id: str) -> Attempt | None:
    row = conn.execute("SELECT * FROM attempts WHERE source_run_id = ?", (run_id,)).fetchone()
    return None if row is None else from_row(Attempt, row)


def list_attempts(
    conn: sqlite3.Connection,
    *,
    test_id: str | None = None,
    student_id: str | None = None,
    thread_id: str | None = None,
    include_superseded: bool = False,
) -> list[Attempt]:
    where: list[str] = []
    args: list[str] = []
    for col, value in (("test_id", test_id), ("student_id", student_id), ("thread_id", thread_id)):
        if value is not None:
            where.append(f"{col} = ?")
            args.append(value)
    if not include_superseded:
        where.append("superseded_by IS NULL")
    sql = "SELECT * FROM attempts" + (" WHERE " + " AND ".join(where) if where else "")
    return [from_row(Attempt, r) for r in conn.execute(sql + " ORDER BY id", args)]


def current_attempt(conn: sqlite3.Connection, thread_id: str) -> Attempt | None:
    """The thread's current attempt: the one that is not superseded (data-model §2.7)."""
    found = list_attempts(conn, thread_id=thread_id)
    return found[-1] if found else None


def graded_attempts(conn: sqlite3.Connection, test_id: str) -> list[str]:
    """IDs of the test's *graded* attempts: ``score_earned`` set and not superseded. ``status``
    alone cannot tell, because ``reviewed`` hides whether it was graded (data-model §5.3)."""
    rows = conn.execute(
        "SELECT id FROM attempts WHERE test_id = ? AND score_earned IS NOT NULL"
        " AND superseded_by IS NULL ORDER BY id",
        (test_id,),
    ).fetchall()
    return [r[0] for r in rows]


def _update(conn: sqlite3.Connection, attempt_id: str, sql: str, args: tuple[object, ...]) -> None:
    with transaction(conn):
        cur = conn.execute(f"UPDATE attempts SET {sql} WHERE id = ?", (*args, attempt_id))
        if cur.rowcount != 1:
            raise KeyError(f"no attempt {attempt_id}")


def set_status(
    conn: sqlite3.Connection,
    attempt_id: str,
    status: Literal["extracted", "graded", "reviewed"],
) -> None:
    _update(conn, attempt_id, "status = ?", (status,))


def bump_version(conn: sqlite3.Connection, attempt_id: str) -> None:
    """``version += 1`` (every teacher change, data-model §2.5)."""
    _update(conn, attempt_id, "version = version + 1", ())


def set_student(conn: sqlite3.Connection, attempt_id: str, student_id: str | None) -> None:
    _update(conn, attempt_id, "student_id = ?", (student_id,))


def set_taken_on(conn: sqlite3.Connection, attempt_id: str, taken_on: date) -> None:
    """The date taken (D11a, data-model v1.24)."""
    _update(conn, attempt_id, "taken_on = ?", (taken_on.isoformat(),))


def student_attempts_by_date(conn: sqlite3.Connection, student_id: str) -> list[Attempt]:
    """A student's current (not superseded) attempts in trajectory order: ``taken_on``, then
    ``created_at``, then id (D11, step 22.5.5)."""
    rows = conn.execute(
        "SELECT * FROM attempts WHERE student_id = ? AND superseded_by IS NULL"
        " ORDER BY taken_on, created_at, id",
        (student_id,),
    )
    return [from_row(Attempt, r) for r in rows]


def set_superseded_by(conn: sqlite3.Connection, attempt_id: str, newer_id: str) -> None:
    _update(conn, attempt_id, "superseded_by = ?", (newer_id,))


# --- attempt_pages ---------------------------------------------------------------------------


def add_attempt_pages(conn: sqlite3.Connection, pages: Iterable[AttemptPage]) -> None:
    with transaction(conn):
        for page in pages:
            insert_model(conn, "attempt_pages", page)


def list_attempt_pages(conn: sqlite3.Connection, attempt_id: str) -> list[AttemptPage]:
    rows = conn.execute(
        "SELECT * FROM attempt_pages WHERE attempt_id = ? ORDER BY page_no", (attempt_id,)
    ).fetchall()
    return [from_row(AttemptPage, r) for r in rows]


# --- answers ---------------------------------------------------------------------------------


def insert_answers(conn: sqlite3.Connection, answers: Iterable[Answer]) -> None:
    with transaction(conn):
        for answer in answers:
            insert_model(conn, "answers", answer)


def update_answer(conn: sqlite3.Connection, answer: Answer) -> None:
    """Replace every column of one existing answer row."""
    row = to_row(answer)
    keys = ("attempt_id", "question_id")
    sets = ", ".join(f"{c} = ?" for c in row if c not in keys)
    args = [v for c, v in row.items() if c not in keys]
    with transaction(conn):
        cur = conn.execute(
            f"UPDATE answers SET {sets} WHERE attempt_id = ? AND question_id = ?",
            (*args, answer.attempt_id, answer.question_id),
        )
        if cur.rowcount != 1:
            raise KeyError(f"no answer {answer.attempt_id}/{answer.question_id}")


def move_answer(
    conn: sqlite3.Connection, attempt_id: str, old_question_id: str, new_question_id: str
) -> None:
    """Move one answer to another question of the same attempt (Review ``merge_unaligned``
    fix). The target must be free (the key is ``(attempt_id, question_id)``)."""
    with transaction(conn):
        cur = conn.execute(
            "UPDATE answers SET question_id = ? WHERE attempt_id = ? AND question_id = ?",
            (new_question_id, attempt_id, old_question_id),
        )
        if cur.rowcount != 1:
            raise KeyError(f"no answer {attempt_id}/{old_question_id}")


def delete_answers_for_question(
    conn: sqlite3.Connection, test_id: str, question_id: str
) -> list[str]:
    """Delete the answers to one question on every attempt of the test (the question left the
    test text, data-model §2.3a). Returns the ids of the attempts that lost an answer."""
    with transaction(conn):
        rows = conn.execute(
            "SELECT a.id FROM answers x JOIN attempts a ON a.id = x.attempt_id"
            " WHERE a.test_id = ? AND x.question_id = ?",
            (test_id, question_id),
        ).fetchall()
        ids = [r[0] for r in rows]
        conn.executemany(
            "DELETE FROM answers WHERE attempt_id = ? AND question_id = ?",
            [(i, question_id) for i in ids],
        )
    return ids


def count_answers_for_question(conn: sqlite3.Connection, test_id: str, question_id: str) -> int:
    """How many attempts of the test have an answer to this question."""
    row = conn.execute(
        "SELECT COUNT(*) FROM answers x JOIN attempts a ON a.id = x.attempt_id"
        " WHERE a.test_id = ? AND x.question_id = ?",
        (test_id, question_id),
    ).fetchone()
    return int(row[0])


def get_answer(conn: sqlite3.Connection, attempt_id: str, question_id: str) -> Answer | None:
    row = conn.execute(
        "SELECT * FROM answers WHERE attempt_id = ? AND question_id = ?",
        (attempt_id, question_id),
    ).fetchone()
    return None if row is None else from_row(Answer, row)


def list_answers(conn: sqlite3.Connection, attempt_id: str) -> list[Answer]:
    rows = conn.execute(
        "SELECT * FROM answers WHERE attempt_id = ? ORDER BY printed_number, question_id",
        (attempt_id,),
    ).fetchall()
    return [from_row(Answer, r) for r in rows]


# --- grade_reports (one current report per attempt) ------------------------------------------


def replace_grade_report(conn: sqlite3.Connection, report: GradeReport) -> None:
    row = to_row(report, _REPORT_JSON)
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    with transaction(conn):
        conn.execute(
            f"INSERT OR REPLACE INTO grade_reports ({cols}) VALUES ({marks})", tuple(row.values())
        )


def get_grade_report(conn: sqlite3.Connection, attempt_id: str) -> GradeReport | None:
    row = conn.execute("SELECT * FROM grade_reports WHERE attempt_id = ?", (attempt_id,)).fetchone()
    return None if row is None else from_row(GradeReport, row, _REPORT_JSON)


# --- grading (step 18) -----------------------------------------------------------------------


def set_answer_grade(conn: sqlite3.Connection, answer: Answer) -> None:
    """Write the grading columns of one answer (``verdict``, ``near_miss``, ``points_awarded``,
    ``value_norm``). Never touches ``teacher_override`` or the reading (data-model §5.2)."""
    with transaction(conn):
        cur = conn.execute(
            "UPDATE answers SET verdict = ?, near_miss = ?, points_awarded = ?, value_norm = ?"
            " WHERE attempt_id = ? AND question_id = ?",
            (
                answer.verdict,
                int(answer.near_miss),
                answer.points_awarded,
                answer.value_norm,
                answer.attempt_id,
                answer.question_id,
            ),
        )
        if cur.rowcount != 1:
            raise KeyError(f"no answer {answer.attempt_id}/{answer.question_id}")


def set_graded(
    conn: sqlite3.Connection, attempt_id: str, score_earned: float, score_possible: float
) -> None:
    """The score snapshot and ``status = graded`` (Grade's ``save``)."""
    _update(
        conn,
        attempt_id,
        "score_earned = ?, score_possible = ?, status = 'graded'",
        (score_earned, score_possible),
    )


def skill_stats_by_attempt(
    conn: sqlite3.Connection, student_id: str, *, exclude_attempt_id: str | None = None
) -> list[SkillStats]:
    """The weak-point history: the ``student_skill_stats`` counts grouped **per attempt** as
    well, plus ``careless`` (incorrect answers explained as careless or spelling). Current
    (not superseded) attempts of ``student_id`` only; ``exclude_attempt_id`` (the attempt being
    graded) is left out."""
    rows = conn.execute(
        "SELECT a.id, a.created_at, qt.tag,"
        " SUM(ans.verdict IN ('correct','incorrect')),"
        " SUM(ans.verdict = 'incorrect'),"
        " SUM(ans.verdict = 'incorrect' AND e.error_type = 'gap'),"
        " SUM(ans.verdict = 'incorrect' AND e.error_type IN ('careless','spelling'))"
        " FROM answers ans"
        " JOIN attempts a ON a.id = ans.attempt_id AND a.superseded_by IS NULL"
        " JOIN question_tags qt ON qt.test_id = a.test_id AND qt.question_id = ans.question_id"
        " LEFT JOIN explanations e ON e.test_id = a.test_id AND e.question_id = ans.question_id"
        "  AND e.wrong_answer_norm = ans.value_norm"
        " WHERE a.student_id = ? AND a.id != ?"
        " GROUP BY a.id, qt.tag ORDER BY a.created_at, a.id, qt.tag",
        (student_id, exclude_attempt_id or ""),
    ).fetchall()
    return [
        SkillStats(
            attempt_id=r[0],
            created_at=r[1],
            skill_tag=r[2],
            seen=int(r[3] or 0),
            wrong=int(r[4] or 0),
            gap_errors=int(r[5] or 0),
            careless=int(r[6] or 0),
        )
        for r in rows
    ]


def answer_forms(test: Test) -> dict[str, str]:
    """``{question_id: answer form}`` of one test."""
    return {
        q.id: q.answer_form for s in test.content.sections for g in s.groups for q in g.questions
    }


def option_counts(test: Test) -> dict[str, int]:
    """``{question_id: number of options}`` of one test's questions that have options (D11f)."""
    return {
        q.id: len(q.options)
        for s in test.content.sections
        for g in s.groups
        for q in g.questions
        if q.options
    }


def paper_skills(conn: sqlite3.Connection, attempt: Attempt) -> list[PaperSkill]:
    """One stored paper's per-skill results for the trajectory (D11, step 22.5.5)."""

    test = tests.get_test(conn, attempt.test_id)
    if test is None:
        return []
    index = {  # the error types only (an explanation row may have lost its call pointer)
        (r[0], r[1]): r[2]
        for r in conn.execute(
            "SELECT question_id, wrong_answer_norm, error_type FROM explanations WHERE test_id = ?",
            (attempt.test_id,),
        )
    }
    return paper_skill_results(
        attempt.id,
        attempt.taken_on,
        attempt.created_at,
        list_answers(conn, attempt.id),
        tests.list_question_tags(conn, attempt.test_id),
        answer_forms(test),
        index,
        tests.list_tag_levels(conn, attempt.test_id),
        option_counts(test),
    )


def student_paper_skills(
    conn: sqlite3.Connection, student_id: str, *, exclude_attempt_id: str | None = None
) -> list[PaperSkill]:
    """Every current paper of a student (in date-taken order) as ``PaperSkill`` rows;
    ``exclude_attempt_id`` (the attempt being graded) is left out."""
    return [
        row
        for att in student_attempts_by_date(conn, student_id)
        if att.id != exclude_attempt_id
        for row in paper_skills(conn, att)
    ]
