"""Step 22.5.5: the trajectory labels (R22.5.5.4; decisions D11, D11b)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from support.guards import no_io  # noqa: F401
from unit.domain.grading_support import answer

from etach.domain.weakpoints import (
    PaperSkill,
    chance_level,
    classify,
    paper_skill_results,
    trajectories,
)

pytestmark = pytest.mark.usefixtures("no_io")

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _paper(i: int, share: float, *, day: int | None = None, tag: str = "VOC-TOPIC") -> PaperSkill:
    return PaperSkill(
        attempt_id=f"A{i}", taken_on=date(2026, 1, day or i), created_at=T0,
        skill_tag=tag, right=round(share * 4), counted=4,
    )  # fmt: skip


@pytest.mark.parametrize(
    ("shares", "label"),
    [
        ([0.0, 0.25, 0.5, 0.75], "improved"),
        ([1.0, 0.75, 0.25, 0.0], "slipped"),
        ([0.25, 0.0, 1.0, 0.25], "consistently_weak"),
        ([0.75, 0.25, 0.75, 0.25, 0.5], "inconsistent"),
        ([1.0, 0.75, 1.0], "solid"),
        ([0.0, 0.0], "not_enough_evidence"),
        ([0.0], "not_enough_evidence"),
    ],
)
def test_r22_5_5_4_one_case_per_label(shares: list[float], label: str) -> None:
    assert classify(shares) == label
    rows = [_paper(i, s) for i, s in enumerate(shares, 1)]
    assert trajectories(rows)["VOC-TOPIC"].label == label


def test_r22_5_5_4_guessing_baseline_and_careless_left_out() -> None:
    answers = [
        answer("q-1", "A", verdict="correct", printed_number=1),  # choice A-D: chance 0.25
        answer("q-2", "went", verdict="correct", printed_number=2),  # word: chance 0
        answer("q-3", "recieve", verdict="incorrect", printed_number=3),  # spelling: left out
        answer("q-4", "go", verdict="incorrect", printed_number=4),  # gap: 0 of 1
        answer("q-5", "B", verdict="uncertain", printed_number=5),  # not counted
    ]
    tags = {q: ["GR-PST-A2"] for q in ("q-1", "q-2", "q-3", "q-4", "q-5")}
    forms = {"q-1": "choice", "q-2": "word", "q-3": "word", "q-4": "word", "q-5": "choice"}
    explanations = {("q-3", "recieve"): "spelling", ("q-4", "go"): "gap"}
    (row,) = paper_skill_results(
        "A1", date(2026, 1, 1), T0, answers, tags, forms, explanations,  # type: ignore[arg-type]
        {"q-1": {"GR-PST-A2": "B1"}, "q-2": {"GR-PST-A2": "A2"}}, {"q-1": 4, "q-5": 4},
    )  # fmt: skip
    assert (row.right, row.counted, row.chance) == (2, 3, 0.25)
    assert row.share == pytest.approx((2 - 0.25) / (3 - 0.25))
    assert row.level == "A2"  # the lowest effective level on the paper


def test_r22_5_5_4_papers_ordered_by_date_taken_then_created_at() -> None:
    later = datetime(2026, 5, 1, tzinfo=UTC)
    rows = [
        # uploaded late but taken first
        PaperSkill(attempt_id="A9", taken_on=date(2026, 1, 1), created_at=later,
                   skill_tag="S", right=0, counted=2),
        # same day: created_at breaks the tie
        PaperSkill(attempt_id="A2", taken_on=date(2026, 2, 1), created_at=later,
                   skill_tag="S", right=2, counted=2),
        PaperSkill(attempt_id="A1", taken_on=date(2026, 2, 1), created_at=T0,
                   skill_tag="S", right=2, counted=2),
        PaperSkill(attempt_id="A0", taken_on=date(2026, 1, 15), created_at=later,
                   skill_tag="S", right=0, counted=2),
    ]  # fmt: skip
    t = trajectories(rows)["S"]
    assert [p.attempt_id for p in t.papers] == ["A9", "A0", "A1", "A2"]
    assert t.label == "improved"


def test_r22_5_5_4_fewer_than_three_papers_and_empty_papers() -> None:
    rows = [_paper(1, 0.0), _paper(2, 0.0)]
    rows.append(PaperSkill(attempt_id="A3", taken_on=date(2026, 1, 3), created_at=T0,
                           skill_tag="VOC-TOPIC", right=0, counted=0))  # fmt: skip
    t = trajectories(rows)["VOC-TOPIC"]
    assert (t.label, len(t.papers)) == ("not_enough_evidence", 2)


# --- R22.5.5.12: the guessing baseline (D11f) ---------------------------------------------------


def _choice_paper(
    rights: list[bool], *, k: int | None = 4, forms: list[str] | None = None
) -> PaperSkill:
    qids = [f"q-{i}" for i in range(1, len(rights) + 1)]
    answers = [
        answer(q, "A", verdict="correct" if r else "incorrect", printed_number=i)
        for i, (q, r) in enumerate(zip(qids, rights, strict=True), 1)
    ]
    form_of = dict(zip(qids, forms or ["choice"] * len(qids), strict=True))
    counts = {q: k for q in qids} if k is not None else {}
    (row,) = paper_skill_results(
        "A1", date(2026, 1, 1), T0, answers, {q: ["VOC-TOPIC"] for q in qids}, form_of, {},
        None, counts,
    )  # fmt: skip
    return row


def test_r22_5_5_12_chance_levels() -> None:
    assert chance_level("choice", 4) == 0.25
    assert chance_level("choice", 2) == 0.5  # True/False
    assert chance_level("choice", 3) == pytest.approx(1 / 3)
    assert chance_level("choice", None) == 0.25  # no stored options: as A-D
    assert chance_level("word", None) == 0.0
    assert chance_level("sentence", 4) == 0.0


def test_r22_5_5_12_all_right_on_a_to_d_is_100_percent() -> None:
    assert _choice_paper([True] * 4).share == 1.0
    assert _choice_paper([True] * 3, k=None).share == 1.0  # options not stored


def test_r22_5_5_12_chance_level_is_0_percent() -> None:
    assert _choice_paper([True, False, False, False]).share == 0.0  # 1 of 4 = chance
    assert _choice_paper([False] * 4).share == 0.0  # below chance: clamped at 0
    assert _choice_paper([True, True, False, False]).share == pytest.approx(1 / 3)


def test_r22_5_5_12_true_false() -> None:
    assert _choice_paper([True, False], k=2).share == 0.0
    assert _choice_paper([True, True], k=2).share == 1.0
    assert _choice_paper([True, True, True, False], k=2).share == pytest.approx(0.5)


def test_r22_5_5_12_mixed_forms() -> None:
    # A-D right (chance 0.25), T/F wrong (0.5), word right (0), word wrong (0):
    # right 2, counted 4, chance 0.75 → (2 - 0.75) / (4 - 0.75)
    rights = {"q-1": True, "q-2": False, "q-3": True, "q-4": False}
    answers = [
        answer(q, "A", verdict="correct" if r else "incorrect", printed_number=i)
        for i, (q, r) in enumerate(rights.items(), 1)
    ]
    forms = {"q-1": "choice", "q-2": "choice", "q-3": "word", "q-4": "word"}
    (row,) = paper_skill_results(
        "A1", date(2026, 1, 1), T0, answers, {q: ["VOC-TOPIC"] for q in rights}, forms, {},
        None, {"q-1": 4, "q-2": 2},
    )  # fmt: skip
    assert (row.right, row.counted, row.chance) == (2, 4, 0.75)
    assert row.share == pytest.approx(1.25 / 3.25)
    words = _choice_paper([True, False], forms=["word", "word"])
    assert words.share == 0.5  # no chance level: the plain share


def test_r22_5_5_12_choice_only_skill_can_be_solid() -> None:
    rows = [
        _choice_paper([True] * 4).model_copy(update={"attempt_id": f"A{i}",
                                                     "taken_on": date(2026, 1, i)})
        for i in range(1, 4)
    ]  # fmt: skip
    assert trajectories(rows)["VOC-TOPIC"].label == "solid"


def test_r22_5_5_12_zero_denominator_is_not_counted() -> None:
    row = PaperSkill(attempt_id="A1", taken_on=date(2026, 1, 1), created_at=T0,
                     skill_tag="S", right=1, counted=1, chance=1.0)  # fmt: skip
    assert (row.scored, row.share) == (False, 0.0)
    assert trajectories([row]) == {}
