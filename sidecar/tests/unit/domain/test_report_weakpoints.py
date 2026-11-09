"""Step 22.5.5: the report's weak points (R22.5.5.5; decisions D11c, D11d, D11e)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from support.guards import no_io  # noqa: F401

from etach.domain.models import GradeReport, WeakPoint
from etach.domain.weakpoints import (
    PaperSkill,
    SkillStats,
    SkillTrajectory,
    TrajectoryLabel,
    report_weak_points,
    summary_lines,
)

pytestmark = pytest.mark.usefixtures("no_io")

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _stats(tag: str, seen: int, wrong: int, careless: int = 0) -> SkillStats:
    return SkillStats(
        attempt_id="A3", created_at=T0, skill_tag=tag, seen=seen, wrong=wrong,
        gap_errors=0, careless=careless,
    )  # fmt: skip


def _paper(tag: str, level: str | None) -> PaperSkill:
    return PaperSkill(
        attempt_id="A3", taken_on=date(2026, 1, 3), created_at=T0, skill_tag=tag,
        right=0, counted=1, level=level,  # type: ignore[arg-type]
    )  # fmt: skip


def _traj(tag: str, label: TrajectoryLabel) -> SkillTrajectory:
    return SkillTrajectory(skill_tag=tag, label=label, papers=[])


def test_r22_5_5_5_labels_this_paper_only_and_exclusions() -> None:
    current = [
        _stats("GR-PST-A2", 2, 1),  # not enough evidence → this paper only
        _stats("GR-PPF-A2", 2, 2),  # slipped
        _stats("GR-QNT-A2", 2, 1),  # improved: not a weak point
        _stats("GR-ART-A1", 2, 1),  # solid: not a weak point
        _stats("GR-PSV-A1", 3, 0),  # not missed on this paper
        _stats("GR-CMP-A2", 2, 1, careless=1),  # only a careless slip
    ]
    paper = [_paper(s.skill_tag, "A2") for s in current]
    traj = {
        "GR-PPF-A2": _traj("GR-PPF-A2", "slipped"),
        "GR-QNT-A2": _traj("GR-QNT-A2", "improved"),
        "GR-ART-A1": _traj("GR-ART-A1", "solid"),
        "GR-PSV-A1": _traj("GR-PSV-A1", "consistently_weak"),
        "GR-PST-A2": _traj("GR-PST-A2", "not_enough_evidence"),
    }
    got = report_weak_points(current, paper, traj)
    assert [(w.skill_tag, w.label) for w in got] == [
        ("GR-PPF-A2", "slipped"),
        ("GR-PST-A2", "this_paper_only"),
    ]


def test_r22_5_5_5_basics_first_vocabulary_first_and_held_back() -> None:
    tags = {"GR-PPF-A2": "B1", "VOC-COLLOC": "B1", "GR-PST-A2": "A2", "READ-INFER": None}
    current = [_stats(t, 2, 1) for t in tags]
    paper = [_paper(t, lvl) for t, lvl in tags.items()]
    got = report_weak_points(current, paper, {})
    assert [(w.skill_tag, w.level, w.held_back) for w in got] == [
        ("GR-PST-A2", "A2", False),
        ("VOC-COLLOC", "B1", True),  # vocabulary first within a level
        ("GR-PPF-A2", "B1", True),
        ("READ-INFER", "B2", True),  # no level on the paper → the base level
    ]
    lines = summary_lines(got, {"GR-PST-A2": "Past Simple"}.get)  # type: ignore[arg-type]
    assert lines == "- Past Simple (this paper only): wrong 1/2, gap errors 0"
    assert summary_lines([], str) == "(none)"


def test_r22_5_5_5_old_reports_stay_readable() -> None:
    old = WeakPoint.model_validate(
        {"skill_tag": "GR-PST-A2", "wrong": 1, "seen": 2, "gap_errors": 0, "note_vi": ""}
    )
    assert (old.label, old.level, old.held_back) == (None, None, False)
    report = GradeReport(
        attempt_id="A1", run_id="R1", weak_points=[old], careless_notes=[], summary_vi="",
        teacher_questions=[], uncertain_points=0, created_at=T0,
    )  # fmt: skip
    assert GradeReport.model_validate_json(report.model_dump_json()) == report
