"""Weak-point scores and careless notes (llm-design §5 ``weak_points``; data-model §4).

The history comes per attempt (``SkillStats`` rows, the ``student_skill_stats`` view grouped by
attempt as well); the current attempt's stats come from its in-state verdicts via
``attempt_stats``, which counts exactly as the view does: ``seen`` = correct + incorrect,
``wrong`` = incorrect, ``gap_errors`` = incorrect whose explanation (joined on
``(question_id, value_norm)``) is ``gap``. Careless and spelling errors are counted apart
(``careless``) and kept out of the ranking; they become ``careless_notes``.

Recency: attempts are ranked newest first, the current attempt is rank 0, and an attempt of rank
``r`` weighs ``w = 0.5**r``. A skill's score is ``Σ w·(wrong - careless)``. The report's weak
points come from the trajectory (``report_weak_points``, step 22.5.5).

Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from etach.domain.levels import LEVELS, Level, base_level, level_rank
from etach.domain.models import Answer, AnswerKey, ErrorType, WeakPoint
from etach.domain.normalize import value_norm
from etach.domain.scoring import effective_value

__all__ = [
    "CARELESS_TYPES",
    "CHOICE_NO_OPTIONS_CHANCE",
    "CONSISTENTLY_WEAK_FRACTION",
    "INCONSISTENT_HIGH",
    "INCONSISTENT_LOW",
    "RECENT_PAPERS",
    "THIS_PAPER_ONLY",
    "TRAJECTORY_MIN_PAPERS",
    "WEAK_LABELS",
    "WEAK_SHARE",
    "PaperSkill",
    "SkillStats",
    "SkillTrajectory",
    "TrajectoryLabel",
    "attempt_stats",
    "careless_notes",
    "chance_level",
    "classify",
    "paper_skill_results",
    "recency_weights",
    "report_weak_points",
    "skill_scores",
    "summary_lines",
    "trajectories",
]

CARELESS_TYPES: frozenset[ErrorType] = frozenset({"careless", "spelling"})
_LABEL_VI = {"careless": "sơ ý", "spelling": "chính tả"}

# (question_id, wrong_answer_norm) → error_type: the explanations of this test
ExplanationIndex = Mapping[tuple[str, str], ErrorType]


class SkillStats(BaseModel):
    """One attempt's counts for one skill tag."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_id: str
    created_at: datetime
    skill_tag: str
    seen: int
    wrong: int
    gap_errors: int
    careless: int = 0  # incorrect with error_type careless/spelling (part of ``wrong``)


def _error_type(answer: Answer, explanations: ExplanationIndex) -> ErrorType | None:
    raw = effective_value(answer)
    return explanations.get((answer.question_id, value_norm(raw if raw is not None else "")))


def attempt_stats(
    attempt_id: str,
    created_at: datetime,
    answers: Iterable[Answer],
    tags: Mapping[str, Sequence[str]],
    explanations: ExplanationIndex,
) -> list[SkillStats]:
    """Per-skill counts for one attempt from its verdicts (``tags``: question_id → skill tags).
    ``uncertain``/``ungraded`` answers are not seen, as in the view."""
    acc: dict[str, list[int]] = {}
    for ans in answers:
        if ans.verdict not in ("correct", "incorrect"):
            continue
        wrong = ans.verdict == "incorrect"
        etype = _error_type(ans, explanations) if wrong else None
        for tag in tags.get(ans.question_id, ()):
            row = acc.setdefault(tag, [0, 0, 0, 0])
            row[0] += 1
            row[1] += wrong
            row[2] += etype == "gap"
            row[3] += etype in CARELESS_TYPES
    return [
        SkillStats(
            attempt_id=attempt_id,
            created_at=created_at,
            skill_tag=tag,
            seen=s,
            wrong=w,
            gap_errors=g,
            careless=c,
        )
        for tag, (s, w, g, c) in sorted(acc.items())
    ]


def recency_weights(current_attempt_id: str, history: Iterable[SkillStats]) -> dict[str, float]:
    """attempt_id → ``0.5**rank``: the current attempt is rank 0, then history newest first."""
    seen: dict[str, datetime] = {}
    for row in history:
        if row.attempt_id != current_attempt_id:
            seen[row.attempt_id] = row.created_at
    order = sorted(seen, key=lambda a: (seen[a], a), reverse=True)
    weights = {current_attempt_id: 1.0}
    for rank, attempt_id in enumerate(order, 1):
        weights[attempt_id] = 0.5**rank
    return weights


def _combined(
    current_attempt_id: str, current: Iterable[SkillStats], history: Iterable[SkillStats]
) -> tuple[list[SkillStats], dict[str, float]]:
    hist = [r for r in history if r.attempt_id != current_attempt_id]  # a re-grade: in-state wins
    rows = [*hist, *(r for r in current if r.attempt_id == current_attempt_id)]
    return rows, recency_weights(current_attempt_id, hist)


def skill_scores(
    current_attempt_id: str, current: Iterable[SkillStats], history: Iterable[SkillStats]
) -> dict[str, float]:
    """skill_tag → ``Σ w·(wrong - careless)`` over the current attempt and the history."""
    rows, weights = _combined(current_attempt_id, current, history)
    scores: dict[str, float] = {}
    for r in rows:
        scores[r.skill_tag] = scores.get(r.skill_tag, 0.0) + weights[r.attempt_id] * (
            r.wrong - r.careless
        )
    return scores


def careless_notes(
    answers: Iterable[Answer],
    keys: Iterable[AnswerKey],
    explanations: ExplanationIndex,
) -> list[str]:
    """One line per incorrect answer explained as careless or spelling (this attempt only), in
    answer order, e.g. ``Câu 12 (chính tả): "recieve" → "receive"``."""
    key_by_q = {k.question_id: k for k in keys}
    notes: list[str] = []
    for ans in answers:
        if ans.verdict != "incorrect":
            continue
        etype = _error_type(ans, explanations)
        if etype not in CARELESS_TYPES:
            continue
        key = key_by_q.get(ans.question_id)
        expected = key.accepted[0] if key and key.accepted else "?"
        notes.append(
            f'Câu {ans.printed_number} ({_LABEL_VI[etype]}): "{effective_value(ans) or ""}" '
            f'→ "{expected}"'
        )
    return notes


# --- The trajectory (D11, D11b, step 22.5.5) ----------------------------------------------------
#
# Per student and skill, the papers in date-taken order (``taken_on``, then ``created_at``, then
# the attempt id). Per paper the **share right** over a guessing baseline (D11f): each counted
# question has a chance level (a ``choice`` with k options: 1/k; any other form: 0), and the share
# is ``max(0, right - sum(chance)) / (counted - sum(chance))``, so all right = 100 % and
# chance-level = 0 %. Careless and spelling mistakes are left out (neither right nor counted). Each
# paper weighs the same: "earlier" and "overall" are means of the per-paper shares (D11: papers,
# not questions).

#: A skill needs answers on at least this many papers for a label.
TRAJECTORY_MIN_PAPERS = 3
#: "Recent" is the last this many papers.
RECENT_PAPERS = 2
#: A share below this is weak on that paper.
WEAK_SHARE = 0.5
#: Consistently weak: weak on at least this fraction of the papers.
CONSISTENTLY_WEAK_FRACTION = 2 / 3
#: Inconsistent: the overall share within these bounds (inclusive).
INCONSISTENT_LOW = 0.35
INCONSISTENT_HIGH = 0.65
#: The chance level of a ``choice`` whose options are not stored (as A-D).
CHOICE_NO_OPTIONS_CHANCE = 0.25

TrajectoryLabel = Literal[
    "improved", "slipped", "consistently_weak", "inconsistent", "solid", "not_enough_evidence"
]
#: The labels that make a skill a weak point (improved and solid do not).
WEAK_LABELS: frozenset[str] = frozenset({"slipped", "consistently_weak", "inconsistent"})
#: A weak point on a skill without enough evidence (D11c).
THIS_PAPER_ONLY = "this_paper_only"


class PaperSkill(BaseModel):
    """One paper's result for one skill: ``right`` out of ``counted`` answers, whose chance levels
    add up to ``chance`` (D11f)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_id: str
    taken_on: date
    created_at: datetime
    skill_tag: str
    right: int
    counted: int
    chance: float = 0.0  # the sum of the counted questions' chance levels
    level: Level | None = None  # the lowest effective level of the skill's questions on it

    @property
    def scored(self) -> bool:
        """Whether the share is defined (``counted - chance`` > 0); otherwise not counted."""
        return self.counted - self.chance > 1e-9

    @property
    def share(self) -> float:
        """``max(0, right - chance) / (counted - chance)``; 0 when not ``scored``."""
        if not self.scored:
            return 0.0
        return max(0.0, self.right - self.chance) / (self.counted - self.chance)


class SkillTrajectory(BaseModel):
    """A skill's papers in date-taken order and its label."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    skill_tag: str
    label: TrajectoryLabel
    papers: list[PaperSkill]


def chance_level(form: str | None, option_count: int | None) -> float:
    """A question's chance level (D11f): a ``choice`` with k options 1/k (A-D 0.25, T/F 0.5; no
    stored options: ``CHOICE_NO_OPTIONS_CHANCE``); any other form 0."""
    if form != "choice":
        return 0.0
    if option_count is None or option_count < 2:
        return CHOICE_NO_OPTIONS_CHANCE
    return 1.0 / option_count


def paper_skill_results(
    attempt_id: str,
    taken_on: date,
    created_at: datetime,
    answers: Iterable[Answer],
    tags: Mapping[str, Sequence[str]],
    forms: Mapping[str, str],
    explanations: ExplanationIndex,
    tag_levels: Mapping[str, Mapping[str, str | None]] | None = None,
    option_counts: Mapping[str, int] | None = None,
) -> list[PaperSkill]:
    """One paper's ``PaperSkill`` rows (``tags``: question_id → skill tags; ``forms``:
    question_id → answer form; ``tag_levels``: question_id → {tag: effective level};
    ``option_counts``: question_id → number of options of a ``choice``).
    ``uncertain``/``ungraded`` answers and careless/spelling mistakes are not counted."""
    acc: dict[str, list[float]] = {}  # tag → [right, counted, sum of chance levels]
    lvl: dict[str, Level | None] = {}
    for ans in answers:
        if ans.verdict not in ("correct", "incorrect"):
            continue
        right = ans.verdict == "correct"
        if not right and _error_type(ans, explanations) in CARELESS_TYPES:
            continue
        chance = chance_level(
            forms.get(ans.question_id), (option_counts or {}).get(ans.question_id)
        )
        for tag in tags.get(ans.question_id, ()):
            row = acc.setdefault(tag, [0.0, 0.0, 0.0])
            row[0] += right
            row[1] += 1
            row[2] += chance
            level = (tag_levels or {}).get(ans.question_id, {}).get(tag) or base_level(tag)
            if tag not in lvl or level_rank(level) < level_rank(lvl[tag]):
                lvl[tag] = level if level in LEVELS else None
    return [
        PaperSkill(
            attempt_id=attempt_id,
            taken_on=taken_on,
            created_at=created_at,
            skill_tag=tag,
            right=int(r),
            counted=int(n),
            chance=ch,
            level=lvl.get(tag),
        )
        for tag, (r, n, ch) in sorted(acc.items())
    ]


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def classify(shares: Sequence[float]) -> TrajectoryLabel:
    """The label for one skill's per-paper shares in date-taken order (the first that applies)."""
    if len(shares) < TRAJECTORY_MIN_PAPERS:
        return "not_enough_evidence"
    earlier, recent = shares[:-RECENT_PAPERS], shares[-RECENT_PAPERS:]
    if _mean(earlier) < WEAK_SHARE and all(s >= WEAK_SHARE for s in recent):
        return "improved"
    if _mean(earlier) >= WEAK_SHARE and all(s < WEAK_SHARE for s in recent):
        return "slipped"
    if sum(s < WEAK_SHARE for s in shares) >= CONSISTENTLY_WEAK_FRACTION * len(shares):
        return "consistently_weak"
    if INCONSISTENT_LOW <= _mean(shares) <= INCONSISTENT_HIGH:
        return "inconsistent"
    return "solid"


def trajectories(rows: Iterable[PaperSkill]) -> dict[str, SkillTrajectory]:
    """skill_tag → its trajectory. Papers without a defined share (no counted answers, or
    ``counted - chance`` = 0) are left out; a paper's rows
    are ordered by ``taken_on``, then ``created_at``, then the attempt id."""
    by_skill: dict[str, list[PaperSkill]] = {}
    for r in rows:
        if r.scored:
            by_skill.setdefault(r.skill_tag, []).append(r)
    out: dict[str, SkillTrajectory] = {}
    for tag in sorted(by_skill):
        papers = sorted(by_skill[tag], key=lambda p: (p.taken_on, p.created_at, p.attempt_id))
        out[tag] = SkillTrajectory(
            skill_tag=tag, label=classify([p.share for p in papers]), papers=papers
        )
    return out


def _vocabulary_first(tag: str) -> int:
    return 0 if tag.startswith("VOC-") else 1


def report_weak_points(
    current: Iterable[SkillStats],
    paper: Iterable[PaperSkill],
    trajectory: Mapping[str, SkillTrajectory],
) -> list[WeakPoint]:
    """The report's weak points (D11c, D11e): each skill missed on this paper (wrong, careless and
    spelling left out) with its trajectory label, or ``this_paper_only`` without enough evidence;
    improved and solid skills are left out. Counts are this paper's. Ordered basics first (the
    level, then vocabulary, then the label's order, then the tag); when any weak point is at a
    level L, those above L are ``held_back``. ``trajectory`` includes this paper."""
    levels = {p.skill_tag: p.level for p in paper}
    order = {"slipped": 0, "consistently_weak": 1, "inconsistent": 2, THIS_PAPER_ONLY: 3}
    out: list[WeakPoint] = []
    for r in current:
        missed = r.wrong - r.careless
        if missed <= 0:
            continue
        t = trajectory.get(r.skill_tag)
        label: str = t.label if t is not None else "not_enough_evidence"
        if label == "not_enough_evidence":
            label = THIS_PAPER_ONLY
        elif label not in WEAK_LABELS:
            continue  # improved / solid
        out.append(
            WeakPoint(
                skill_tag=r.skill_tag,
                wrong=missed,
                seen=r.seen - r.careless,
                gap_errors=r.gap_errors,
                note_vi="",
                label=label,  # type: ignore[arg-type]
                level=levels.get(r.skill_tag) or base_level(r.skill_tag),
            )
        )
    out.sort(
        key=lambda w: (
            level_rank(w.level),
            _vocabulary_first(w.skill_tag),
            order[w.label or THIS_PAPER_ONLY],
            w.skill_tag,
        )
    )
    if not out:
        return out
    lowest = level_rank(out[0].level)
    return [w.model_copy(update={"held_back": level_rank(w.level) > lowest}) for w in out]


def summary_lines(weak_points: Iterable[WeakPoint], name: Callable[[str], str]) -> str:
    """The ``weak_points`` input of ``weak_points_summary``: skill names (``name``: code → the
    taxonomy name), not codes, and only the weak points not held back (D11e)."""
    return (
        "\n".join(
            f"- {name(w.skill_tag)} ({(w.label or THIS_PAPER_ONLY).replace('_', ' ')}):"
            f" wrong {w.wrong}/{w.seen}, gap errors {w.gap_errors}"
            for w in weak_points
            if not w.held_back
        )
        or "(none)"
    )
