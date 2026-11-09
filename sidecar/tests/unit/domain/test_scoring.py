"""Step 17.1: ``grade()`` over plan Appendix B.5 (R17.1.1), no partial credit and the B.6 seeded
score (R17.1.2), and the explanation cache key (R17.1.5)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from support.guards import assert_pure, no_io  # noqa: F401
from unit.domain.grading_support import (
    answer,
    content,
    key,
    question,
    section,
    worked_example,
)

from etach.domain.models import Answer, AnswerKey, Question
from etach.domain.normalize import value_norm
from etach.domain.scoring import (
    edit_distance,
    explanation_key,
    grade,
    grade_answer,
)

HES = " He" + chr(0x2019) + "s  gone "  # the curly apostrophe of R17.1.5
pytestmark = pytest.mark.usefixtures("no_io")

Case = tuple[Question, Answer, AnswerKey | None, str | None]

# plan Appendix B.5, verbatim: (#, Situation, Verdict)
B5 = [
    (1, "Reading unsure, no override", "uncertain"),
    (2, "Reading unsure, override present", "graded normally (confidence 1.0)"),
    (3, "Key `ai_uncertain`", "uncertain"),
    (4, "`choice` value = key", "correct"),
    (5, "`choice` value ≠ key", "incorrect"),
    (6, "`word` or `sentence` normalized value ∈ accepted", "correct"),
    (7, "`word`: edit distance 1–2 from accepted, confident reading", "incorrect + `near_miss`"),  # noqa: RUF001
    (8, "`word`: edit distance 1–2, unsure reading", "uncertain"),  # noqa: RUF001
    (9, "`sentence`, no normalized match", "judge result (correct/incorrect)"),
    (10, "Value None (blank)", "incorrect"),
    (11, "No key row for the question (key making failed)", "uncertain"),
    (
        12,
        "Retired in step 22.5.3: ordering is a `sentence` (row 9), matching a `choice` (rows 4–5)",  # noqa: RUF001
        "–",  # noqa: RUF001
    ),
    (13, "Retired in step 22.5.3: combine is a `sentence` (row 9)", "–"),  # noqa: RUF001
    (14, "`judge_rewrites` failed twice", "uncertain"),
    (15, "Page reading failed (value None, `reading_unsure`)", "uncertain"),
    (
        16,
        "Question in a writing section (`graded=False`), or a `writing` question",
        "no answer row, not graded",
    ),
]

# by answer form (step 22.5.3); the former types are those forms with ``old_type`` kept
Q_MCQ = question("q-1", "choice")
Q_TF = question("q-1", "true_false")
Q_GAP = question("q-1", "word")
Q_RW = question("q-1", "sentence")
Q_CB = question("q-1", "combine")
Q_ORD = question("q-1", "ordering")
Q_MAT = question("q-1", "matching")
REWRITE_KEY = "She said that she was tired."


def _verdict(q: Question, a: Answer, k: AnswerKey | None, judged: str | None = None) -> str:
    v = grade_answer(q, a, k, judged)  # type: ignore[arg-type]
    return v.verdict + (" + near_miss" if v.near_miss else "")


def row_1() -> None:
    a = answer("q-1", "A", reading_unsure=True, confidence=0.4)
    assert _verdict(Q_MCQ, a, key("q-1", "A")) == "uncertain"
    assert _verdict(Q_GAP, answer("q-1", "went", reading_unsure=True), key("q-1", "went")) == (
        "uncertain"
    )


def row_2() -> None:
    right = answer("q-1", "C", reading_unsure=True, confidence=0.3, teacher_override="A")
    wrong = answer("q-1", "A", reading_unsure=True, confidence=0.3, teacher_override="B")
    assert _verdict(Q_MCQ, right, key("q-1", "A")) == "correct"
    assert _verdict(Q_MCQ, wrong, key("q-1", "A")) == "incorrect"
    # graded as a confident reading: a near miss is incorrect + near_miss, not uncertain
    near = answer("q-1", "x", reading_unsure=True, confidence=0.1, teacher_override="wnet")
    assert _verdict(Q_GAP, near, key("q-1", "went")) == "incorrect + near_miss"
    # "" = the teacher confirmed "no answer" → graded as blank
    blank = answer("q-1", "A", reading_unsure=True, teacher_override="")
    assert _verdict(Q_MCQ, blank, key("q-1", "A")) == "incorrect"


def row_3() -> None:
    k = key("q-1", "A", status="ai_uncertain")
    assert _verdict(Q_MCQ, answer("q-1", "A"), k) == "uncertain"
    assert _verdict(Q_MCQ, answer("q-1", "A", teacher_override="A"), k) == "uncertain"


def row_4() -> None:
    assert _verdict(Q_MCQ, answer("q-1", "A"), key("q-1", "A")) == "correct"
    assert _verdict(Q_MCQ, answer("q-1", " a "), key("q-1", "A")) == "correct"
    assert _verdict(Q_TF, answer("q-1", "T"), key("q-1", "T")) == "correct"


def row_5() -> None:
    assert _verdict(Q_MCQ, answer("q-1", "B"), key("q-1", "A")) == "incorrect"
    assert _verdict(Q_TF, answer("q-1", "F"), key("q-1", "T")) == "incorrect"
    # MCQ has no near miss: a different letter is just incorrect
    assert not grade_answer(Q_MCQ, answer("q-1", "B"), key("q-1", "A")).near_miss


def row_6() -> None:
    k = key("q-1", ["has gone", "has left"])
    assert _verdict(Q_GAP, answer("q-1", "  Has   GONE "), k) == "correct"
    assert _verdict(Q_GAP, answer("q-1", "has left"), k) == "correct"
    k2 = key("q-1", "he's gone")
    assert _verdict(Q_GAP, answer("q-1", HES), k2) == "correct"
    assert _verdict(Q_GAP, answer("q-1", "information"), key("q-1", "inform")) == "incorrect"


def row_7() -> None:
    k = key("q-1", "beautiful")
    assert _verdict(Q_GAP, answer("q-1", "beautifull"), k) == "incorrect + near_miss"  # 1
    assert _verdict(Q_GAP, answer("q-1", "beatiful"), k) == "incorrect + near_miss"  # 1
    assert _verdict(Q_GAP, answer("q-1", "beutifull"), k) == "incorrect + near_miss"  # 2
    assert _verdict(Q_GAP, answer("q-1", "butifl"), k) == "incorrect"  # 3: not a near miss
    a = answer("q-1", "beautifull")
    result = grade(content(section("s-1", [Q_GAP])), [a], [k])
    assert result.answers[0].points_awarded == 0.0  # near misses still score 0 (D24)


def row_8() -> None:
    k = key("q-1", "beautiful")
    a = answer("q-1", "beautifull", reading_unsure=True, confidence=0.5)
    assert _verdict(Q_GAP, a, k) == "uncertain"


def row_9() -> None:
    k = key("q-1", REWRITE_KEY)
    a = answer("q-1", "She said she was tired.")
    first = grade(content(section("s-1", [Q_RW])), [a], [k])
    assert first.to_judge == ["q-1"]
    for judged in ("correct", "incorrect"):
        assert _verdict(Q_RW, a, k, judged) == judged
    # a normalized match needs no judge
    exact = answer("q-1", "she said that she was  tired.")
    assert _verdict(Q_RW, exact, k) == "correct"
    assert grade(content(section("s-1", [Q_RW])), [exact], [k]).to_judge == []


def row_10() -> None:
    assert _verdict(Q_MCQ, answer("q-1", None), key("q-1", "A")) == "incorrect"
    assert _verdict(Q_GAP, answer("q-1", None), key("q-1", "went")) == "incorrect"
    assert _verdict(Q_RW, answer("q-1", None), key("q-1", REWRITE_KEY)) == "incorrect"
    assert _verdict(Q_GAP, answer("q-1", "   "), key("q-1", "went")) == "incorrect"


def row_11() -> None:
    assert _verdict(Q_MCQ, answer("q-1", "A"), None) == "uncertain"
    r = grade(content(section("s-1", [Q_MCQ])), [answer("q-1", "A")], [])
    assert r.answers[0].points_awarded is None
    assert r.uncertain_points == 0.25


def row_12() -> None:
    """Retired: a former ordering question is a sentence (exact, else the judge, row 9); a former
    matching question is a choice (exact, rows 4-5). No verdict carries rule 12."""
    k = key("q-1", "C-A-B-D")
    assert _verdict(Q_ORD, answer("q-1", " c-a-b-d "), k) == "correct"
    wrong = grade_answer(Q_ORD, answer("q-1", "C-A-D-B"), k)
    assert (wrong.verdict, wrong.needs_judge, wrong.rule) == ("uncertain", True, 9)
    assert _verdict(Q_ORD, answer("q-1", "C-A-D-B"), k, "incorrect") == "incorrect"
    assert grade_answer(Q_MAT, answer("q-1", "c"), key("q-1", "C")).rule == 4
    assert grade_answer(Q_MAT, answer("q-1", "B"), key("q-1", "C")).rule == 5
    assert not grade_answer(Q_MAT, answer("q-1", "D"), key("q-1", "C")).near_miss


def row_13() -> None:
    """Retired: a former combine question follows row 9 (one judge rule for every sentence)."""
    k = key("q-1", "Although it rained, we went out.")
    a = answer("q-1", "Despite the rain, we went out.")
    first = grade(content(section("s-1", [Q_CB])), [a], [k])
    assert first.to_judge == ["q-1"]
    assert first.answers[0].verdict == "uncertain"
    for judged in ("correct", "incorrect"):
        v = grade_answer(Q_CB, a, k, judged)  # type: ignore[arg-type]
        assert (v.verdict, v.rule) == (judged, 9)


def row_14() -> None:
    k = key("q-1", REWRITE_KEY)
    a = answer("q-1", "She told she tired.")
    assert _verdict(Q_RW, a, k, "failed") == "uncertain"
    r = grade(content(section("s-1", [Q_RW])), [a], [k], judged={"q-1": "failed"})
    assert r.to_judge == []
    assert r.answers[0].points_awarded is None


def row_15() -> None:
    a = answer("q-1", None, reading_unsure=True, confidence=0.0)
    assert _verdict(Q_MCQ, a, key("q-1", "A")) == "uncertain"
    assert grade_answer(Q_MCQ, a, key("q-1", "A")).rule == 15


def row_16() -> None:
    writing = question("q-w", "writing", points=1.0, n=37)
    c = content(section("s-1", [Q_MCQ]), section("s-8", [writing], "writing", graded=False))
    stray = answer("q-w", "My favourite ...")
    r = grade(c, [answer("q-1", "A"), stray], [key("q-1", "A"), key("q-w", "x")])
    assert [a.question_id for a in r.answers] == ["q-1"]
    assert r.score_possible == 0.25
    # a writing question in a graded section is not graded either (step 22.5.3)
    inside = question("q-w", "writing", points=0.25, n=2)
    r = grade(content(section("s-1", [Q_MCQ, inside])), [answer("q-1", "A"), stray], [])
    assert [a.question_id for a in r.answers] == ["q-1"] and r.to_judge == []


CHECKS: dict[int, Callable[[], None]] = {
    1: row_1,
    2: row_2,
    3: row_3,
    4: row_4,
    5: row_5,
    6: row_6,
    7: row_7,
    8: row_8,
    9: row_9,
    10: row_10,
    11: row_11,
    12: row_12,
    13: row_13,
    14: row_14,
    15: row_15,
    16: row_16,
}


@pytest.mark.parametrize(("no", "situation", "verdict"), B5, ids=[f"B5-{r[0]}" for r in B5])
def test_r17_1_1_b5_row(no: int, situation: str, verdict: str) -> None:
    assert situation and verdict
    CHECKS[no]()


def test_r17_1_1_table_is_complete() -> None:
    assert [r[0] for r in B5] == list(range(1, 17)) == sorted(CHECKS)


def _seeded() -> tuple[list[Answer], list[AnswerKey]]:
    """B.6: the worked example with 30 correct, 4 incorrect, 2 uncertain."""
    answers: list[Answer] = []
    keys: list[AnswerKey] = []
    for n in range(1, 37):
        qid = f"q-{n}"
        keys.append(key(qid, "A"))
        if n <= 30:
            answers.append(answer(qid, "A"))
        elif n <= 34:
            answers.append(answer(qid, "B"))
        else:
            answers.append(answer(qid, "A", reading_unsure=True, confidence=0.3))
    return answers, keys


def test_r17_1_2_seeded_score() -> None:
    answers, keys = _seeded()
    r = grade(worked_example(), answers, keys)
    verdicts = [a.verdict for a in r.answers]
    assert verdicts.count("correct") == 30
    assert verdicts.count("incorrect") == 4
    assert verdicts.count("uncertain") == 2
    assert (r.score_earned, r.score_possible) == (7.5, 9.0)
    assert r.uncertain_points == 0.5


def test_r17_1_2_no_partial_credit() -> None:
    answers, keys = _seeded()
    answers.append(answer("q-x", "zzz"))  # not a question of the test: dropped
    r = grade(worked_example(), answers, keys)
    by_q = {q.id: q for s in worked_example().sections for g in s.groups for q in g.questions}
    for a in r.answers:
        full = by_q[a.question_id].points
        assert a.points_awarded in (0.0, full) or (
            a.points_awarded is None and a.verdict == "uncertain"
        )
        assert (a.points_awarded is None) == (a.verdict == "uncertain")


def test_points_follow_question_points() -> None:
    q = question("q-1", "rewrite", points=0.5)
    k = key("q-1", REWRITE_KEY)
    a = answer("q-1", "She said she was tired.")
    c = content(section("s-1", [q]))
    assert grade(c, [a], [k], {"q-1": "correct"}).answers[0].points_awarded == 0.5
    assert grade(c, [a], [k], {"q-1": "incorrect"}).answers[0].points_awarded == 0.0


def test_r17_1_5_cache_key_normalization() -> None:
    assert value_norm(HES) == value_norm("he's gone") == "he's gone"
    assert explanation_key("T-1", "q-1", HES) == explanation_key("T-1", "q-1", "he's gone")
    assert explanation_key("T-1", "q-1", chr(0x201C) + "Gone" + chr(0x201D)) == (
        "T-1",
        "q-1",
        '"gone"',
    )
    # the key equals the stored Answer.value_norm the weak-point view joins on
    a = answer("q-1", HES)
    assert explanation_key("T-1", "q-1", a.value or "")[2] == a.value_norm


def test_edit_distance() -> None:
    assert edit_distance("", "") == 0
    assert edit_distance("abc", "abc") == 0
    assert edit_distance("kitten", "sitting") == 3
    assert edit_distance("went", "wnet") == 2
    assert edit_distance("", "ab") == 2


@pytest.mark.parametrize(
    "module", ["etach.domain.scoring", "etach.domain.keys", "etach.domain.weakpoints"]
)
def test_module_is_pure(module: str) -> None:
    assert_pure(module)
