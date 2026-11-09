"""Step 17.1: ``key_needed`` and ``verify_needed`` (R17.1.3, plan Appendix B.7)."""

from __future__ import annotations

import pytest
from support.guards import no_io  # noqa: F401
from unit.domain.grading_support import NOW, answer, content, key, question, section

from etach.domain.keys import (
    key_failed_reviews,
    key_needed,
    questions_to_verify,
    verify_failed,
    verify_needed,
)
from etach.domain.models import Answer

pytestmark = pytest.mark.usefixtures("no_io")

T = 0.6  # margin threshold
STATUSES = ["ai_unverified", "ai_verified", "ai_uncertain", "teacher_verified", "from_key_photo"]


def _vn(
    status: str = "ai_unverified",
    margin: float | None = 0.9,
    skill: str = "grammar",
    attempt: bool = False,
    value: str | None = "A",
) -> bool:
    k = key("q-1", "A", status=status, confidence=margin)
    a = answer("q-1", value) if attempt else None
    return verify_needed(
        k, section_skill=skill, margin_threshold=T, attempt_present=attempt, answer=a
    )


# (case, status, margin, skill, attempt present, student value, expected)
B7 = [
    ("low margin", "ai_unverified", 0.3, "grammar", False, None, True),
    ("no margin", "ai_unverified", None, "grammar", False, None, True),
    ("pronunciation", "ai_unverified", 0.9, "pronunciation", False, None, True),
    ("stress", "ai_unverified", 0.9, "stress", False, None, True),
    ("answer differs", "ai_unverified", 0.9, "grammar", True, "B", True),
    ("answer blank (v2.7)", "ai_unverified", 0.9, "grammar", True, None, False),
    ("answer whitespace (v2.7)", "ai_unverified", 0.9, "grammar", True, "  ", False),
    ("answer equals key", "ai_unverified", 0.9, "grammar", True, " a ", False),
    ("confident, no attempt", "ai_unverified", 0.9, "grammar", False, None, False),
    ("margin at threshold", "ai_unverified", T, "vocabulary", False, None, False),
]


@pytest.mark.parametrize(
    ("case", "status", "margin", "skill", "attempt", "value", "expected"),
    B7,
    ids=[r[0] for r in B7],
)
def test_r17_1_3_verify_needed_b7(
    case: str,
    status: str,
    margin: float | None,
    skill: str,
    attempt: bool,
    value: str | None,
    expected: bool,
) -> None:
    assert _vn(status, margin, skill, attempt, value) is expected


@pytest.mark.parametrize("status", [s for s in STATUSES if s != "ai_unverified"])
def test_r17_1_3_false_for_other_statuses(status: str) -> None:
    # every trigger at once, still false
    assert _vn(status, 0.1, "pronunciation", True, "B") is False
    assert _vn(status, None, "stress", True, None) is False


def test_r17_1_3_override_counts() -> None:
    k = key("q-1", "A", status="ai_unverified", confidence=0.9)
    a = answer("q-1", "B", teacher_override="A")
    assert not verify_needed(
        k, section_skill="grammar", margin_threshold=T, attempt_present=True, answer=a
    )


def test_r17_1_3_blank_missing_or_empty_override_do_not_trigger() -> None:
    k = key("q-1", "A", status="ai_unverified", confidence=0.9)

    def vn(a: Answer | None) -> bool:
        return verify_needed(
            k, section_skill="grammar", margin_threshold=T, attempt_present=True, answer=a
        )

    assert vn(None) is False  # missing answer row
    assert vn(answer("q-1", None)) is False  # blank
    assert vn(answer("q-1", "B", teacher_override="")) is False  # confirmed "no answer"
    assert vn(answer("q-1", "B")) is True  # non-blank and ≠ the key
    assert vn(answer("q-1", None, teacher_override="C")) is True  # override is the answer


def test_r17_1_3_verify_gate_over_a_test() -> None:
    c = content(
        section("s-1", [question("q-1"), question("q-2", n=2)], skill="pronunciation"),
        section("s-2", [question("q-3", n=3), question("q-4", n=4)]),
        section("s-3", [question("q-5", n=5)]),
    )
    keys = [
        key("q-1", "A", "ai_unverified", 0.9),  # pronunciation → verify
        key("q-2", "A", "teacher_verified", 0.1),  # teacher-verified → never
        key("q-3", "A", "ai_unverified", 0.2),  # low margin → verify
        key("q-4", "A", "ai_verified", 0.1),  # ai_verified → never
        key("q-5", "A", "ai_unverified", 0.9),  # only with an attempt that differs
    ]
    assert questions_to_verify(c, keys, margin_threshold=T) == ["q-1", "q-3"]
    answers = [answer(f"q-{i}", "A") for i in range(1, 5)] + [answer("q-5", "C")]
    assert questions_to_verify(c, keys, margin_threshold=T, answers=answers) == [
        "q-1",
        "q-3",
        "q-5",
    ]
    # v2.7: a blank, a confirmed-blank override or a missing row for q-5 does not trigger
    base = [answer(f"q-{i}", "A") for i in range(1, 5)]
    for q5 in ([answer("q-5", None)], [answer("q-5", "C", teacher_override="")], []):
        assert questions_to_verify(c, keys, margin_threshold=T, answers=base + q5) == [
            "q-1",
            "q-3",
        ]


def test_key_needed() -> None:
    writing = question("q-w", "writing", points=1.0, n=9)
    c = content(
        section("s-1", [question("q-1"), question("q-2", n=2), question("q-3", n=3)]),
        section("s-8", [writing], "writing", graded=False),
    )
    assert key_needed(c, [key("q-1"), key("q-2"), key("q-3")]) == []  # → skip ai_key_fast
    assert key_needed(c, [key("q-2")]) == ["q-1", "q-3"]  # writing needs no key


def test_verify_failed_and_key_failed_reviews() -> None:
    k = key("q-1", "A", "ai_unverified", 0.2)
    new, item = verify_failed(k, "R-1", NOW)
    assert new.status == "ai_uncertain" and new.accepted == ["A"]
    assert (item.kind, item.dedupe_key, item.refs) == (
        "uncertain_key",
        "uncertain_key:R-1:q-1",
        {"question_id": "q-1"},
    )
    items = key_failed_reviews("R-1", ["q-2", "q-3"])
    assert [i.dedupe_key for i in items] == ["uncertain_key:R-1:q-2", "uncertain_key:R-1:q-3"]
