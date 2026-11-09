"""Step 17.1: plan Appendix B.8, the failure rules of llm-design §5.1 (R17.1.6), held verbatim.

Each row checks the domain side after two failures of that call: the verdicts, the Review items
and that grading still completes (no exception, so the run can end ``done``, not ``failed``).
The run-status write itself is the grade graph's ``save`` (step 18, R18.6)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from support.guards import no_io  # noqa: F401
from unit.domain.grading_support import (
    ATTEMPT_ID,
    NOW,
    answer,
    content,
    key,
    question,
    section,
)

from etach.domain.keys import key_failed_reviews, key_needed, verify_failed
from etach.domain.models import ErrorType
from etach.domain.scoring import grade
from etach.domain.weakpoints import attempt_stats, careless_notes, skill_scores

pytestmark = pytest.mark.usefixtures("no_io")

# llm-design §5.1, verbatim: (Call, Result)
B8 = [
    (
        "`read_answers_page` (a page)",
        "Every graded question on that page: value None, `reading_unsure = true` (→ `?`), "
        "plus one `validator_failed` item for the page",
    ),
    (
        "`transcribe_page` / `retranscribe_tiles`",
        "`validator_failed` for that page; the test is saved with what was read",
    ),
    ("`read_key_pages`", "No key rows from the photo; Grade makes the key"),
    (
        "`ai_key_fast` (a section)",
        "No key rows for those questions → they grade `uncertain` (no key row) + `uncertain_key`",
    ),
    ("`verify_key`", "Key → `ai_uncertain` (+ `uncertain_key`)"),
    ("`judge_rewrites`", "That answer `uncertain`"),
    ("`explain`", 'No explanation; the report shows "no explanation" for that question'),
    (
        "`tag_skills` / `weak_points_summary`",
        "Skipped; tags or notes are missing; the report shows ranked skills without the narrative",
    ),
]

C = content(
    section("s-1", [question("q-1", n=1), question("q-2", n=2)]),  # page 1
    section("s-2", [question("q-3", "rewrite", n=3)]),
)
KEYS = [key("q-1", "A"), key("q-2", "B"), key("q-3", "She said that she was tired.")]


def read_answers_page() -> None:
    # the extract graph (step 8.1 boxes) wrote the failed page's answers this way
    failed = [answer(q, None, reading_unsure=True, confidence=0.0) for q in ("q-1", "q-2")]
    r = grade(C, [*failed, answer("q-3", "She said that she was tired.")], KEYS)
    assert [a.verdict for a in r.answers] == ["uncertain", "uncertain", "correct"]
    assert (r.score_earned, r.uncertain_points) == (0.25, 0.5)


def transcribe_page() -> None:
    # the test was saved with what was read (only section s-1): grading uses that content
    partial = content(section("s-1", [question("q-1", n=1), question("q-2", n=2)]))
    r = grade(partial, [answer("q-1", "A"), answer("q-2", "C")], KEYS)
    assert [a.verdict for a in r.answers] == ["correct", "incorrect"]
    assert r.score_possible == 0.5


def read_key_pages() -> None:
    assert key_needed(C, []) == ["q-1", "q-2", "q-3"]  # → ai_key_fast makes them


def ai_key_fast() -> None:
    missing = key_needed(C, KEYS[2:])
    assert missing == ["q-1", "q-2"]
    reviews = key_failed_reviews("R-1", missing)
    assert [(i.kind, i.refs["question_id"]) for i in reviews] == [
        ("uncertain_key", "q-1"),
        ("uncertain_key", "q-2"),
    ]
    r = grade(C, [answer("q-1", "A"), answer("q-2", "B")], KEYS[2:])
    assert [a.verdict for a in r.answers] == ["uncertain", "uncertain"]
    assert r.uncertain_points == 0.5


def verify_key() -> None:
    k, item = verify_failed(key("q-1", "A", "ai_unverified", 0.2), "R-1", NOW)
    assert k.status == "ai_uncertain"
    assert item.kind == "uncertain_key"
    r = grade(C, [answer("q-1", "A")], [k])
    assert r.answers[0].verdict == "uncertain"


def judge_rewrites() -> None:
    a = answer("q-3", "She told me tired.")
    r = grade(C, [a], KEYS, judged={"q-3": "failed"})
    assert r.answers[0].verdict == "uncertain"
    assert r.answers[0].points_awarded is None
    assert r.to_judge == []


def explain() -> None:
    answers = [answer("q-1", "C", verdict="incorrect")]
    stats = attempt_stats(ATTEMPT_ID, NOW, answers, {"q-1": ["tenses"]}, {})  # no explanation
    assert [(s.wrong, s.gap_errors, s.careless) for s in stats] == [(1, 0, 0)]
    assert skill_scores(ATTEMPT_ID, stats, ()) == {"tenses": 1.0}
    assert careless_notes(answers, KEYS, {}) == []


def tag_skills() -> None:
    answers = [answer("q-1", "C", verdict="incorrect")]
    expl: dict[tuple[str, str], ErrorType] = {("q-1", "c"): "careless"}
    stats = attempt_stats(ATTEMPT_ID, NOW, answers, {}, expl)  # no tags
    assert stats == []
    assert careless_notes(answers, KEYS, expl) == ['Câu 5 (sơ ý): "C" → "A"']


CHECKS: list[Callable[[], None]] = [
    read_answers_page,
    transcribe_page,
    read_key_pages,
    ai_key_fast,
    verify_key,
    judge_rewrites,
    explain,
    tag_skills,
]


@pytest.mark.parametrize(
    ("index", "call", "result"),
    [(i, *row) for i, row in enumerate(B8)],
    ids=[c.__name__ for c in CHECKS],
)
def test_r17_1_6_b8_row(index: int, call: str, result: str) -> None:
    assert call and result
    CHECKS[index]()  # completes without raising: the run can still end `done`
