"""``/attempts``: an attempt, its student chip, answer corrections and the grade report
(llm-design §2, data-model §5.3).

- ``PUT /attempts/{id}/student`` takes ``{student_id}``, ``{create_from_read: true}`` (a new
  student from ``student_name_read``/``class_read``) or ``{full_name, class_name}``; then
  ``version += 1``. No run.
- ``PATCH /attempts/{id}`` takes ``{taken_on}`` (the date taken, D11a); ``version += 1``. No run.
- ``PUT /attempts/{id}/answers/{question_id}`` takes ``{value}`` → ``teacher_override`` (an empty
  or blank string = "confirmed blank", stored ``""``), ``value_norm`` recomputed, ``version += 1``;
  a graded attempt gets 1 grade run (``review_fix``).
- ``GET /attempts/{id}/report`` → 404 ``"not graded"`` while the attempt has no grade report.
  The report is worded for people (step 22.4.6): each weak point carries its ``skill_name``, any
  taxonomy code inside the AI-written text is replaced by its name, and the verdicts and
  explanations follow the paper's printed numbers (then the wrong answer).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, model_validator

from etach.api.deps import ConnDep, CtxDep
from etach.api.routes.tests import ExportResult, exports_folder
from etach.domain import docx_export
from etach.domain.models import (
    Answer,
    Attempt,
    AttemptPage,
    Explanation,
    GradeReport,
    TeacherQuestion,
    WeakPoint,
    listening_range,
)
from etach.domain.normalize import collapse_spaces, name_search, value_norm
from etach.domain.skills import name_codes, skill_name
from etach.store import db
from etach.store.repos import attempts, explanations, runs, students, tests

__all__ = ["NOT_GRADED", "router"]

NOT_GRADED = "not graded"
NOT_GRADED_EXPORT = "This attempt is not graded yet. Grade it first, then save the report."

router = APIRouter(tags=["attempts"])


class ListeningSkipped(BaseModel):
    """The printed range of the listening part left out of the test (step 22.5.6)."""

    first: int
    last: int


class AttemptDetail(BaseModel):
    attempt: Attempt
    answers: list[Answer]
    pages: list[AttemptPage]
    # step 22.5.6: the listening part left out (its printed range), None when there is none
    listening_skipped: ListeningSkipped | None = None


class StudentPut(BaseModel):
    student_id: str | None = None
    create_from_read: bool = False
    full_name: str | None = None
    class_name: str | None = None

    @model_validator(mode="after")
    def _one(self) -> StudentPut:
        chosen = [self.student_id is not None, self.create_from_read, self.full_name is not None]
        if sum(chosen) != 1:
            raise ValueError(
                'send one of {"student_id"}, {"create_from_read": true} or {"full_name"}'
            )
        if self.full_name is not None and not self.full_name.strip():
            raise ValueError("full_name must not be blank")
        return self


class AttemptPatch(BaseModel):
    taken_on: date


class AnswerPut(BaseModel):
    value: str


class AnswerPutResult(BaseModel):
    answer: Answer
    version: int
    run_ids: list[str]


class ReportVerdict(BaseModel):
    question_id: str
    printed_number: int
    value: str | None
    verdict: Literal["correct", "incorrect", "uncertain", "ungraded"]
    near_miss: bool
    points_awarded: float | None


class ReportWeakPoint(WeakPoint):
    """A stored weak point with the skill's English name (the code stays for internal use)."""

    skill_name: str


class ReportGrade(GradeReport):
    """The grade report as people read it: skill names, no taxonomy codes in the text."""

    weak_points: list[ReportWeakPoint]  # type: ignore[assignment]


class AttemptReport(BaseModel):
    attempt: Attempt
    report: ReportGrade
    verdicts: list[ReportVerdict]
    explanations: list[Explanation]


def _attempt(conn: ConnDep, attempt_id: str) -> Attempt:
    attempt = attempts.get_attempt(conn, attempt_id)
    if attempt is None:
        raise HTTPException(404, detail=f"no attempt {attempt_id}")
    return attempt


@router.get("/attempts/{id}", response_model=AttemptDetail)
def get_attempt(id: str, conn: ConnDep) -> AttemptDetail:
    """The attempt, its answers, its pages and the listening part left out."""
    attempt = _attempt(conn, id)
    test = tests.get_test(conn, attempt.test_id)
    span = None if test is None else listening_range(test.meta, test.content)
    return AttemptDetail(
        attempt=attempt,
        answers=attempts.list_answers(conn, id),
        pages=attempts.list_attempt_pages(conn, id),
        listening_skipped=None if span is None else ListeningSkipped(first=span[0], last=span[1]),
    )


@router.put("/attempts/{id}/student", response_model=Attempt)
def put_student(id: str, body: StudentPut, conn: ConnDep) -> Attempt:
    """Assign an existing student, or create one (from the name read, or typed)."""
    attempt = _attempt(conn, id)
    with db.transaction(conn):
        if body.student_id is not None:
            if students.get_student(conn, body.student_id) is None:
                raise HTTPException(404, detail=f"no student {body.student_id}")
            student_id = body.student_id
        else:
            if body.create_from_read:
                name = attempt.student_name_read
                if not name or not name.strip():
                    raise HTTPException(409, detail="no student name was read")
                class_name = attempt.class_read
            else:
                assert body.full_name is not None
                name = body.full_name
                class_name = body.class_name
            full = collapse_spaces(name)
            student_id = students.create_student(
                conn, full, name_search(full), class_name=class_name
            ).id
        attempts.set_student(conn, id, student_id)
        attempts.bump_version(conn, id)
    return _attempt(conn, id)


@router.patch("/attempts/{id}", response_model=Attempt)
def patch_attempt(id: str, body: AttemptPatch, conn: ConnDep) -> Attempt:
    """Change the date taken (D11a, the Student answers tab); ``version += 1``. No run."""
    _attempt(conn, id)
    with db.transaction(conn):
        attempts.set_taken_on(conn, id, body.taken_on)
        attempts.bump_version(conn, id)
    return _attempt(conn, id)


def _put_answer_db(conn: ConnDep, id: str, question_id: str, body: AnswerPut) -> AnswerPutResult:
    """The blocking part of :func:`put_answer` (runs in the threadpool, never on the event loop)."""
    attempt = _attempt(conn, id)
    with db.transaction(conn):
        answer = attempts.get_answer(conn, id, question_id)
        if answer is None:
            raise HTTPException(404, detail=f"no answer {id}/{question_id}")
        override = body.value if body.value.strip() else ""
        attempts.update_answer(
            conn,
            answer.model_copy(
                update={"teacher_override": override, "value_norm": value_norm(override)}
            ),
        )
        attempts.bump_version(conn, id)
        run_ids: list[str] = []
        if id in attempts.graded_attempts(conn, attempt.test_id):
            run_ids.append(
                runs.enqueue_grade(
                    conn, test_id=attempt.test_id, attempt_id=id, reason="review_fix"
                )
            )
    stored = attempts.get_answer(conn, id, question_id)
    assert stored is not None
    return AnswerPutResult(answer=stored, version=_attempt(conn, id).version, run_ids=run_ids)


@router.put("/attempts/{id}/answers/{question_id}", response_model=AnswerPutResult)
async def put_answer(
    id: str, question_id: str, body: AnswerPut, conn: ConnDep, ctx: CtxDep
) -> AnswerPutResult:
    """Correct a reading: ``teacher_override`` (``""`` = confirmed blank), version + 1, re-grade."""
    result = await run_in_threadpool(_put_answer_db, conn, id, question_id, body)
    if result.run_ids:
        await ctx.manager.poke()
    return result


@router.get(
    "/attempts/{id}/report",
    response_model=AttemptReport,
    responses={404: {"description": NOT_GRADED}},
)
def get_report(id: str, conn: ConnDep) -> AttemptReport:
    """The grade report, the verdict of every answer and the explanations of the wrong ones."""
    attempt = _attempt(conn, id)
    report = attempts.get_grade_report(conn, id)
    if report is None:
        raise HTTPException(404, detail=NOT_GRADED)
    answers = attempts.list_answers(conn, id)
    wrong = {(a.question_id, a.value_norm) for a in answers if a.verdict == "incorrect"}
    # the paper's printed number as the test has it now (a text edit may have changed it)
    test = tests.get_test(conn, attempt.test_id)
    printed = (
        {
            q.id: q.printed_number
            for s in test.content.sections
            for g in s.groups
            for q in g.questions
        }
        if test
        else {}
    )
    number = {a.question_id: printed.get(a.question_id, a.printed_number) for a in answers}
    shown = sorted(
        (
            e.model_copy(update={"text_vi": name_codes(e.text_vi)})
            for e in explanations.list_explanations(conn, attempt.test_id)
            if (e.question_id, e.wrong_answer_norm) in wrong
        ),
        key=lambda e: (number.get(e.question_id, 0), e.wrong_answer_norm),
    )
    return AttemptReport(
        attempt=attempt,
        report=_worded(report),
        verdicts=[
            ReportVerdict(
                question_id=a.question_id,
                printed_number=number[a.question_id],
                value=a.teacher_override if a.teacher_override is not None else a.value,
                verdict=a.verdict,
                near_miss=a.near_miss,
                points_awarded=a.points_awarded,
            )
            for a in sorted(answers, key=lambda a: (number[a.question_id], a.question_id))
        ],
        explanations=shown,
    )


def _worded(report: GradeReport) -> ReportGrade:
    """The report with skill names, and its AI-written text without taxonomy codes."""
    data = report.model_dump()
    data.update(
        weak_points=[
            ReportWeakPoint(
                **w.model_dump(exclude={"note_vi"}),
                note_vi=name_codes(w.note_vi),
                skill_name=skill_name(w.skill_tag),
            )
            for w in report.weak_points
        ],
        careless_notes=[name_codes(n) for n in report.careless_notes],
        summary_vi=name_codes(report.summary_vi),
        teacher_questions=[
            TeacherQuestion(
                question_vi=name_codes(q.question_vi),
                what_answers_mean_vi=name_codes(q.what_answers_mean_vi),
            )
            for q in report.teacher_questions
        ],
    )
    return ReportGrade(**data)


def _export_report_db(conn: ConnDep, folder: Path, id: str) -> ExportResult:
    attempt = _attempt(conn, id)
    if attempts.get_grade_report(conn, id) is None:
        raise HTTPException(409, detail=NOT_GRADED_EXPORT)
    full = get_report(id, conn)
    test = tests.get_test(conn, attempt.test_id)
    test_name = test.meta.display_name() if test else attempt.test_id
    student = students.get_student(conn, attempt.student_id) if attempt.student_id else None
    who = student.full_name if student else (attempt.student_name_read or "student")
    title = f"Grade report: {test_name} · {who}"
    doc = docx_export.report_document(
        title,
        attempt.score_earned,
        attempt.score_possible,
        full.report,
        [docx_export.VerdictRow(v.printed_number, v.value, v.verdict) for v in full.verdicts],
        full.explanations,
        {v.question_id: v.printed_number for v in full.verdicts},
    )
    path = docx_export.save_unique(doc, folder, f"{test_name} - Report - {who}")
    return ExportResult(path=str(path), file_name=path.name)


@router.post(
    "/attempts/{id}/report/export",
    response_model=ExportResult,
    responses={409: {"description": NOT_GRADED}},
)
async def export_report(id: str, conn: ConnDep, ctx: CtxDep) -> ExportResult:
    r"""Save the grade report as DOCX into ``<app>\exports\``; 409 while not graded."""
    return await run_in_threadpool(_export_report_db, conn, exports_folder(ctx), id)
