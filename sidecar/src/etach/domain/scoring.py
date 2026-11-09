"""Grading verdicts, score and ``uncertain_points`` (llm-design §5 ``grade``; plan Appendix B.5).

No partial credit (PRD D24): ``points_awarded`` is the question's full points (correct), ``0.0``
(incorrect) or ``None`` (``?``, uncertain). The score is ``earned / possible`` over the graded
questions (writing sections, ``graded=False``, and ``writing`` questions have no answer rows and are
left out, D13).

By answer form (step 22.5.3, D9): ``choice`` exact match; ``word`` exact match, a 1-2 letter
difference is a spelling near miss; ``sentence`` exact match after normalising, else the AI judge
(one judge rule for every sentence); ``writing`` not graded.

Two passes, because ``judge_rewrites`` is a model call between them:

1. ``grade(content, answers, keys)`` → ``sentence`` answers with no normalized match are listed in
   ``GradeResult.to_judge`` (verdict ``uncertain`` for now);
2. ``grade(content, answers, keys, judged={qid: "correct" | "incorrect" | "failed"})`` → the
   final verdicts. ``"failed"`` (the judge failed twice, llm-design §5.1) stays ``uncertain``.

``explanation_key`` is the explanation-cache key (data-model §2.6): ``(test_id, question_id,
value_norm(wrong answer))``, the same ``value_norm`` the weak-point view joins on.

Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict

from etach.domain.models import Answer, AnswerForm, AnswerKey, Question, TestContent
from etach.domain.normalize import value_norm

__all__ = [
    "EXACT_FORMS",
    "JUDGE_FORMS",
    "NEAR_MISS_FORMS",
    "NOT_GRADED_FORMS",
    "GradeResult",
    "JudgeResult",
    "Verdict",
    "Verdicted",
    "edit_distance",
    "effective_value",
    "explanation_key",
    "grade",
    "grade_answer",
    "graded_questions",
]

Verdict = Literal["correct", "incorrect", "uncertain"]
JudgeResult = Literal["correct", "incorrect", "failed"]

EXACT_FORMS: frozenset[AnswerForm] = frozenset({"choice"})
NEAR_MISS_FORMS: frozenset[AnswerForm] = frozenset({"word"})
JUDGE_FORMS: frozenset[AnswerForm] = frozenset({"sentence"})
NOT_GRADED_FORMS: frozenset[AnswerForm] = frozenset({"writing"})
NEAR_MISS_MAX = 2  # edit distance 1-2 from an accepted answer (B.5 rows 7-8)


class Verdicted(BaseModel):
    """One question's grading outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: Verdict
    near_miss: bool = False
    needs_judge: bool = False  # a sentence with no normalized match, not judged yet
    rule: int  # the Appendix B.5 row that decided it


class GradeResult(BaseModel):
    """``answers``: the input rows (graded questions only) with ``verdict``, ``near_miss`` and
    ``points_awarded`` set. ``to_judge``: question IDs for ``judge_rewrites``."""

    model_config = ConfigDict(extra="forbid")

    answers: list[Answer]
    to_judge: list[str]
    score_earned: float
    score_possible: float
    uncertain_points: float


def effective_value(answer: Answer) -> str | None:
    """The value graded: the teacher's override when set (``""`` = confirmed blank), else the
    value read."""
    return answer.teacher_override if answer.teacher_override is not None else answer.value


def explanation_key(test_id: str, question_id: str, wrong_answer: str) -> tuple[str, str, str]:
    """The explanation-cache key: ``(test_id, question_id, value_norm(wrong_answer))``.

    ``wrong_answer_norm`` equals ``Answer.value_norm``, so ``" He(curly)s  gone "``
    and ``"he's gone"`` share one cache row, and the ``student_skill_stats`` join finds it."""
    return (test_id, question_id, value_norm(wrong_answer))


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance (insert, delete, substitute; cost 1 each)."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def graded_questions(content: TestContent) -> list[Question]:
    """The questions of the graded sections, in order (B.5 row 16: writing is not graded)."""
    return [q for s in content.sections if s.graded for g in s.groups for q in g.questions]


def grade_answer(
    question: Question,
    answer: Answer,
    key: AnswerKey | None,
    judged: JudgeResult | None = None,
) -> Verdicted:
    """The verdict for one answer (plan Appendix B.5, rows 1-15).

    Order: no key (11) → key ``ai_uncertain`` (3) → reading unsure without override (1, 15;
    this also covers row 8, a near miss read unsurely) → blank (10) → by answer form: choice
    (4, 5), normalized match (6), sentence → judge (9, 14), near miss for a word (7), else
    incorrect. An override counts as a sure reading (2). ``rule`` 6 is also used for a word
    answer that is wrong and not a near miss. Rows 12 and 13 are retired (step 22.5.3): ordering
    is a sentence and matching a choice; combine follows row 9. A ``writing`` question is not
    graded (row 16; :func:`grade` drops its answer)."""
    if key is None:
        return Verdicted(verdict="uncertain", rule=11)
    if key.status == "ai_uncertain":
        return Verdicted(verdict="uncertain", rule=3)
    overridden = answer.teacher_override is not None
    if answer.reading_unsure and not overridden:  # row 15 = a failed page: value None + unsure
        return Verdicted(verdict="uncertain", rule=15 if answer.value is None else 1)
    raw = effective_value(answer)
    norm = value_norm(raw) if raw is not None else ""
    if not norm:
        return Verdicted(verdict="incorrect", rule=10)
    accepted = {value_norm(a) for a in key.accepted}
    if question.answer_form in EXACT_FORMS:
        return (
            Verdicted(verdict="correct", rule=4)
            if norm in accepted
            else Verdicted(verdict="incorrect", rule=5)
        )
    if norm in accepted:
        return Verdicted(verdict="correct", rule=6)
    if question.answer_form in JUDGE_FORMS:
        if judged is None:
            return Verdicted(verdict="uncertain", needs_judge=True, rule=9)
        if judged == "failed":
            return Verdicted(verdict="uncertain", rule=14)
        return Verdicted(verdict=judged, rule=9)
    if question.answer_form in NOT_GRADED_FORMS:  # pragma: no cover - grade() drops these
        return Verdicted(verdict="uncertain", rule=16)
    distance = min((edit_distance(norm, a) for a in accepted), default=NEAR_MISS_MAX + 1)
    if 1 <= distance <= NEAR_MISS_MAX:  # row 8 (unsure reading) was already caught by row 1
        return Verdicted(verdict="incorrect", near_miss=True, rule=7)
    return Verdicted(verdict="incorrect", rule=6)


def _points(verdict: Verdict, full: float) -> float | None:
    if verdict == "correct":
        return full
    if verdict == "incorrect":
        return 0.0
    return None


def grade(
    content: TestContent,
    answers: Iterable[Answer],
    keys: Iterable[AnswerKey],
    judged: Mapping[str, JudgeResult] | None = None,
) -> GradeResult:
    """Grade every answer of a graded question; compute the score and ``uncertain_points``.

    Answers for questions outside the graded sections, and for ``writing`` questions, are
    dropped (B.5 row 16; extraction writes no row for them). A graded
    question with no answer row is not invented here (extraction writes one row per graded
    question); ``score_possible`` still counts its points."""
    questions = graded_questions(content)
    by_id = {q.id: q for q in questions}
    key_by_q = {k.question_id: k for k in keys}
    judged = judged or {}
    out: list[Answer] = []
    to_judge: list[str] = []
    earned = 0.0
    unsure_points = 0.0
    for ans in answers:
        q = by_id.get(ans.question_id)
        if q is None or q.answer_form in NOT_GRADED_FORMS:
            continue
        v = grade_answer(q, ans, key_by_q.get(q.id), judged.get(q.id))
        if v.needs_judge:
            to_judge.append(q.id)
        pts = _points(v.verdict, q.points)
        if pts is None:
            unsure_points += q.points
        else:
            earned += pts
        out.append(
            ans.model_copy(
                update={"verdict": v.verdict, "near_miss": v.near_miss, "points_awarded": pts}
            )
        )
    return GradeResult(
        answers=out,
        to_judge=to_judge,
        score_earned=round(earned, 4),
        score_possible=round(sum(q.points for q in questions), 4),
        uncertain_points=round(unsure_points, 4),
    )
