"""``/students``: the student search and the "new student" form (llm-design §2).

``GET /students?q=`` matches the query's ``name_search`` form (accents folded, lowercase) as a
prefix or anywhere in the name; prefix matches come first.

``PATCH /students/{id}`` edits the name, class or school (llm-design v4.19; school v4.34);
``name_search`` follows the new name (data-model §5.6). A blank name → 422, an unknown
student → 404.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from etach.api.deps import ConnDep, CtxDep
from etach.api.routes.threads import (
    RUN_ACTIVE,
    ThreadRef,
    discard_key_runs,
    only_key_runs,
    thread_refs,
)
from etach.domain import weakpoints as wp
from etach.domain.levels import Level, base_level, level_rank
from etach.domain.models import Student
from etach.domain.normalize import name_search
from etach.domain.skills import skill_name
from etach.store.repos import attempts, deletes, schools, students

__all__ = ["router"]

router = APIRouter(tags=["students"])


class NewStudent(BaseModel):
    full_name: str
    class_name: str | None = None
    school: str | None = None
    grade: int | None = None


class StudentPatch(BaseModel):
    full_name: str | None = None
    class_name: str | None = None
    school: str | None = None


def _clean_name(full_name: str) -> str:
    name = " ".join(full_name.split())
    if not name:
        raise HTTPException(422, detail="full_name must not be empty")
    return name


class StudentSummary(Student):
    """A student with the number of threads whose current attempt is theirs (v4.26)."""

    thread_count: int


class SkillPaper(BaseModel):
    """One paper's result for a skill (D11b): the date taken and the share right."""

    attempt_id: str
    taken_on: date
    share: float  # over the guessing baseline (D11f); careless/spelling left out
    counted: int


class StudentSkill(BaseModel):
    """A skill on the Students tab (D11b, D11e; v4.45)."""

    skill_tag: str
    skill_name: str
    label: wp.TrajectoryLabel
    level: Level | None
    weak: bool  # slipped, consistently weak or inconsistent
    held_back: bool  # weak, above the lowest weak level: "later, after the basics"
    papers: list[SkillPaper]  # date-taken order


class StudentDetail(BaseModel):
    student: Student
    threads: list[ThreadRef]
    skills: list[StudentSkill] = []


def student_skills(trajectory: dict[str, wp.SkillTrajectory]) -> list[StudentSkill]:
    """Every skill with its label and level, basics first (the level, then vocabulary, then the
    tag); weak skills above the lowest weak level are held back (D11e). A skill's level is the
    lowest effective level on its papers, else its base level."""
    rows: list[StudentSkill] = []
    for tag, t in trajectory.items():
        levels = [p.level for p in t.papers if p.level is not None]
        rows.append(
            StudentSkill(
                skill_tag=tag,
                skill_name=skill_name(tag),
                label=t.label,
                level=min(levels, key=level_rank) if levels else base_level(tag),
                weak=t.label in wp.WEAK_LABELS,
                held_back=False,
                papers=[
                    SkillPaper(
                        attempt_id=p.attempt_id,
                        taken_on=p.taken_on,
                        share=round(p.share, 4),
                        counted=p.counted,
                    )
                    for p in t.papers
                ],
            )
        )
    rows.sort(
        key=lambda r: (level_rank(r.level), 0 if r.skill_tag.startswith("VOC-") else 1, r.skill_tag)
    )
    weak_ranks = [level_rank(r.level) for r in rows if r.weak]
    if weak_ranks:
        lowest = min(weak_ranks)
        for r in rows:
            r.held_back = r.weak and level_rank(r.level) > lowest
    return rows


@router.get("/students", response_model=list[StudentSummary])
def search_students(conn: ConnDep, q: str = "") -> list[StudentSummary]:
    """Search students by name (prefix or contains); no ``q`` lists them all. Each has
    ``class_name`` and ``thread_count`` (llm-design v4.26)."""
    counts = students.thread_counts(conn)
    return [
        StudentSummary(**dict(s), thread_count=counts.get(s.id, 0))
        for s in students.search_students(conn, name_search(q))
    ]


@router.get("/students/{id}", response_model=StudentDetail)
def get_student(id: str, conn: ConnDep) -> StudentDetail:
    """The student and their threads, newest activity first (llm-design v4.26), and their skills
    with the trajectory label, level and per-paper results (D11b, v4.45)."""
    student = students.get_student(conn, id)
    if student is None:
        raise HTTPException(404, detail=f"no student {id}")
    return StudentDetail(
        student=student,
        threads=thread_refs(conn, students.thread_ids(conn, id)),
        skills=student_skills(wp.trajectories(attempts.student_paper_skills(conn, id))),
    )


@router.post("/students", response_model=Student, status_code=201)
def create_student(body: NewStudent, conn: ConnDep) -> Student:
    """Create a student."""
    full_name = _clean_name(body.full_name)
    school = schools.clean_name(body.school)
    schools.ensure_school(conn, school)  # v1.18: a typed school joins the list
    return students.create_student(
        conn,
        full_name,
        name_search(full_name),
        class_name=body.class_name,
        school=school,
        grade=body.grade,
    )


@router.patch("/students/{id}", response_model=Student)
def patch_student(id: str, body: StudentPatch, conn: ConnDep) -> Student:
    """Edit a student's name and/or class; ``name_search`` is recomputed from the new name."""
    changes: dict[str, str | None] = {}
    if "full_name" in body.model_fields_set:
        if body.full_name is None:
            raise HTTPException(422, detail="full_name must not be empty")
        full_name = _clean_name(body.full_name)
        changes["full_name"] = full_name
        changes["name_search"] = name_search(full_name)
    if "class_name" in body.model_fields_set:
        class_name = " ".join((body.class_name or "").split())
        changes["class_name"] = class_name or None
    if "school" in body.model_fields_set:
        changes["school"] = schools.clean_name(body.school)
    student = students.update_student(conn, id, changes)
    if student is None:
        raise HTTPException(404, detail=f"no student {id}")
    if "school" in changes:
        schools.ensure_school(conn, student.school)  # v1.18: a typed school joins the list
    return student


# --- delete (data-model §5.7 v1.14, llm-design v4.30, decision D1) ---------------------------


class StudentDeletePreview(BaseModel):
    """What ``DELETE /students/{id}`` removes: ``threads`` go whole; ``kept_threads`` are shared
    with another student and lose only this student's attempts; ``attempt_count`` is the
    attempts (papers) that go, current or superseded."""

    student_id: str
    full_name: str
    threads: list[ThreadRef]
    kept_threads: list[ThreadRef]
    attempt_count: int


def _student(conn: ConnDep, id: str) -> Student:
    student = students.get_student(conn, id)
    if student is None:
        raise HTTPException(404, detail=f"no student {id}")
    return student


@router.get("/students/{id}/delete-preview", response_model=StudentDeletePreview)
def student_delete_preview(id: str, conn: ConnDep) -> StudentDeletePreview:
    """Exactly the threads ``DELETE /students/{id}`` would remove (for the confirm dialog)."""
    student = _student(conn, id)
    plan = deletes.plan_student_delete(conn, id)
    return StudentDeletePreview(
        student_id=student.id,
        full_name=student.full_name,
        threads=thread_refs(conn, plan.thread_ids),
        kept_threads=thread_refs(conn, plan.kept_thread_ids),
        attempt_count=deletes.count_student_attempts(conn, plan),
    )


@router.delete("/students/{id}", status_code=204)
async def delete_student(id: str, conn: ConnDep, ctx: CtxDep) -> None:
    """Delete the student for good with their threads (data-model §5.7), in one transaction;
    409 while a run in one of those threads is going or resumable, 404 for an unknown student."""
    # D14 (step22.6-plan): the ``after_extract`` key runs are discarded first, when they are the
    # only unfinished runs in those threads (the docstring is the OpenAPI description; kept)
    await discard_key_runs(ctx, await run_in_threadpool(_student_key_runs, conn, id))
    await run_in_threadpool(_delete_student, conn, id)


def _student_key_runs(conn: ConnDep, id: str) -> list[str]:
    _student(conn, id)
    plan = deletes.plan_student_delete(conn, id)
    return only_key_runs(conn, deletes.active_runs_for_student(conn, plan))


def _delete_student(conn: ConnDep, id: str) -> None:
    plan = deletes.plan_student_delete(conn, id)
    if deletes.active_runs_for_student(conn, plan):
        raise HTTPException(409, detail=RUN_ACTIVE)
    deletes.delete_student(conn, plan)
