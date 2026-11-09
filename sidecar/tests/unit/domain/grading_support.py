"""Shared builders for the step 17.1 grading tests (not a test module)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from etach.domain.models import (
    FORM_OF_OLD_TYPE,
    Answer,
    AnswerKey,
    Question,
    QuestionGroup,
    Section,
)
from etach.domain.models import TestContent as Content
from etach.domain.normalize import value_norm

NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
TEST_ID = "T-0001"
ATTEMPT_ID = "A-0001"


def question(qid: str, kind: str = "choice", points: float = 0.25, n: int = 1) -> Question:
    """``kind`` is an answer form, or a type from before step 22.5.3 (then the question is that
    type mapped by the first-start pass: its form, with ``old_type`` kept)."""
    old = kind if kind in FORM_OF_OLD_TYPE else None
    return Question(
        id=qid,
        number=n,
        printed_number=n + 4,
        page_no=1,
        answer_form=FORM_OF_OLD_TYPE[old] if old else kind,  # type: ignore[arg-type]
        old_type=old,
        stem="stem",
        options=None,
        cue=None,
        points=points,
    )


def section(
    sid: str, questions: list[Question], skill: str = "grammar", graded: bool = True
) -> Section:
    return Section(
        id=sid,
        number=1,
        printed_title="II",
        title="t",
        instructions="i",
        points=sum(q.points for q in questions),
        points_source="printed",
        skill=skill,
        graded=graded,
        groups=[QuestionGroup(id=f"g-{sid}", stimulus=None, pictures=[], questions=questions)],
    )


def content(*sections: Section) -> Content:
    return Content(sections=list(sections))


def worked_example() -> Content:
    """Plan B.1: 7 graded sections, 36 MCQ questions of 0.25 (9.0 points)."""
    sizes = [10, 2, 6, 6, 6, 2, 4]
    secs: list[Section] = []
    n = 1
    for i, size in enumerate(sizes, 1):
        qs = []
        for _ in range(size):
            qs.append(question(f"q-{n}", "choice", 0.25, n))
            n += 1
        secs.append(section(f"s-{i}", qs))
    return Content(sections=secs)


def key(
    qid: str,
    accepted: list[str] | str = "A",
    status: str = "ai_verified",
    confidence: float | None = 0.99,
) -> AnswerKey:
    acc = [accepted] if isinstance(accepted, str) else accepted
    return AnswerKey(
        test_id=TEST_ID,
        question_id=qid,
        accepted=acc,
        reason_vi=None,
        source="ai",
        status=status,  # type: ignore[arg-type]
        confidence=confidence,
        updated_at=NOW,
    )


def answer(qid: str, value: str | None, **fields: Any) -> Answer:
    override = fields.get("teacher_override")
    raw = override if override is not None else value
    values: dict[str, Any] = {
        "attempt_id": ATTEMPT_ID,
        "question_id": qid,
        "printed_number": 5,
        "page_no": 1,
        "value": value,
        "value_norm": None if raw is None else value_norm(raw),
        "location": "circled_option" if value else "none",
        "confidence": 0.95,
        "reading_unsure": False,
        "alt_value": None,
        "alt_question_id": None,
        "points_awarded": None,
        "teacher_override": None,
    }
    values.update(fields)
    return Answer(**values)
