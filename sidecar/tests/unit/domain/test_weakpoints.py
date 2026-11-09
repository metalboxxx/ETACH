"""Step 17.1: weak-point scores (R17.1.4), the ``value_norm`` join (R17.1.5) and careless notes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from support.guards import no_io  # noqa: F401
from unit.domain.grading_support import ATTEMPT_ID, NOW, answer, key

from etach.domain.models import Answer, ErrorType
from etach.domain.weakpoints import (
    SkillStats,
    attempt_stats,
    careless_notes,
    recency_weights,
    skill_scores,
)

HES = " He" + chr(0x2019) + "s  gone "  # the curly apostrophe of R17.1.5
pytestmark = pytest.mark.usefixtures("no_io")

OLD = datetime(2026, 3, 1, tzinfo=UTC)
OLDER = datetime(2026, 1, 1, tzinfo=UTC)


def _graded(qid: str, value: str | None, verdict: str, n: int = 5) -> Answer:
    return answer(qid, value, verdict=verdict, printed_number=n)


def _stats(attempt: str, when: datetime, tag: str, seen: int, wrong: int, **kw: int) -> SkillStats:
    return SkillStats(
        attempt_id=attempt, created_at=when, skill_tag=tag, seen=seen, wrong=wrong,
        gap_errors=kw.get("gap", 0), careless=kw.get("careless", 0),
    )  # fmt: skip


def test_r17_1_4_no_history_ranks_in_state_verdicts() -> None:
    answers = [
        _graded("q-1", "B", "incorrect"),
        _graded("q-2", "C", "incorrect"),
        _graded("q-3", "A", "correct"),
        _graded("q-4", "D", "incorrect"),
        _graded("q-5", "A", "uncertain"),  # "?" is not seen
    ]
    tags = {
        "q-1": ["tenses"],
        "q-2": ["tenses"],
        "q-3": ["tenses", "articles"],
        "q-4": ["articles"],
        "q-5": ["articles"],
    }
    current = attempt_stats(ATTEMPT_ID, NOW, answers, tags, {})
    assert sorted((s.skill_tag, s.wrong, s.seen) for s in current) == [
        ("articles", 1, 2),
        ("tenses", 2, 3),
    ]
    assert skill_scores(ATTEMPT_ID, current, ()) == {"tenses": 2.0, "articles": 1.0}


def test_r17_1_4_newer_error_outweighs_older() -> None:
    history = [
        _stats("A-old", OLD, "tenses", 1, 1),
        _stats("A-old", OLD, "articles", 1, 0),
    ]
    current = [
        _stats(ATTEMPT_ID, NOW, "articles", 1, 1),
        _stats(ATTEMPT_ID, NOW, "tenses", 1, 0),
    ]
    assert recency_weights(ATTEMPT_ID, history) == {ATTEMPT_ID: 1.0, "A-old": 0.5}
    assert skill_scores(ATTEMPT_ID, current, history) == {"articles": 1.0, "tenses": 0.5}


def test_recency_weights_rank_history_newest_first() -> None:
    history = [
        _stats("A-1", OLDER, "x", 1, 1),
        _stats("A-2", OLD, "x", 1, 1),
        _stats(ATTEMPT_ID, OLD, "x", 9, 9),  # a re-grade: the stored copy of this attempt
    ]
    assert recency_weights(ATTEMPT_ID, history) == {ATTEMPT_ID: 1.0, "A-2": 0.5, "A-1": 0.25}
    current = [_stats(ATTEMPT_ID, NOW, "x", 1, 0)]
    assert skill_scores(ATTEMPT_ID, current, history) == {"x": 0.75}  # stored copy ignored


def test_careless_and_spelling_kept_out_of_ranking() -> None:
    answers = [
        _graded("q-1", "recieve", "incorrect", n=12),
        _graded("q-2", "B", "incorrect", n=13),
        _graded("q-3", "goed", "incorrect", n=14),
    ]
    tags = {"q-1": ["spelling-skill"], "q-2": ["careless-skill"], "q-3": ["tenses"]}
    expl: dict[tuple[str, str], ErrorType] = {
        ("q-1", "recieve"): "spelling",
        ("q-2", "b"): "careless",
        ("q-3", "goed"): "gap",
    }
    current = attempt_stats(ATTEMPT_ID, NOW, answers, tags, expl)
    # careless and spelling errors score 0, so only tenses would be a weak point
    assert skill_scores(ATTEMPT_ID, current, ()) == {
        "spelling-skill": 0.0,
        "careless-skill": 0.0,
        "tenses": 1.0,
    }
    assert [(s.skill_tag, s.gap_errors) for s in current if s.skill_tag == "tenses"] == [
        ("tenses", 1)
    ]
    keys = [key("q-1", "receive"), key("q-2", "A"), key("q-3", "went")]
    assert careless_notes(answers, keys, expl) == [
        'Câu 12 (chính tả): "recieve" → "receive"',
        'Câu 13 (sơ ý): "B" → "A"',
    ]


def test_r17_1_5_value_norm_join_counts_one_gap_error() -> None:
    """The seeded case: the explanation was cached under ``"he's gone"``; the answer read
    ``" He(curly)s  gone "`` joins it on ``value_norm`` and counts 1 gap error."""
    answers = [_graded("q-1", HES, "incorrect")]
    expl: dict[tuple[str, str], ErrorType] = {("q-1", "he's gone"): "gap"}
    stats = attempt_stats(ATTEMPT_ID, NOW, answers, {"q-1": ["present-perfect"]}, expl)
    assert [(s.skill_tag, s.seen, s.wrong, s.gap_errors) for s in stats] == [
        ("present-perfect", 1, 1, 1)
    ]
    assert answers[0].value_norm == "he's gone"
