"""R10.1, R10.2: Review resolution (data-model §5.3, plan Appendix E).

Every Appendix E row runs twice: with the attempts graded (the runs are queued as listed) and
ungraded (0 grade runs). The row labels are Appendix E's, verbatim.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_args

import pytest

from etach.domain import models as m
from etach.domain.points import equal_points
from etach.domain.review import InvalidResolution, ReviewNotOpen, resolve
from etach.store import db
from etach.store.repos import (
    attempts,
    explanations,
    keys,
    regrade,
    review,
    runs,
    students,
    tests,
    threads,
)

T0 = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
PAGES = [m.PageInput(file_id="f-page-1", rotation=0, is_key=False, text_file_id=None)]


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    c = db.open_database(tmp_path / "data" / "app.db")
    yield c
    c.close()


def _content(prefix: str, n: int = 3, points: float = 0.25) -> m.TestContent:
    questions = [
        m.Question(
            id=f"{prefix}{i}",
            number=i,
            printed_number=i,
            page_no=1,
            answer_form="choice",
            stem=f"Stem {i}",
            options=[m.Option(label="A", text="one"), m.Option(label="B", text="two")],
            cue=None,
            points=points,
        )
        for i in range(1, n + 1)
    ]
    group = m.QuestionGroup(id="g-1", stimulus=None, pictures=[], questions=questions)
    section = m.Section(
        id="s-1",
        number=1,
        printed_title="I",
        title="Choose",
        instructions="Circle A or B.",
        points=points * n,
        points_source="assumed",
        skill="grammar",
        groups=[group],
    )
    return m.TestContent(sections=[section])


def _test(conn: sqlite3.Connection, prefix: str, occasion: str) -> str:
    t = m.Test(
        id=tests.next_test_id(conn),
        meta=m.TestMetadata(occasion=occasion, grade=8),
        content=_content(prefix),
        content_schema_version=1,
        fingerprint="fp",
        points_possible=0.75,
        source_run_id=None,
        merged_into=None,
        created_at=T0,
        updated_at=T0,
    )
    return tests.insert_test(conn, t).id


def _attempt(
    conn: sqlite3.Connection, test_id: str, qids: list[str], graded: bool, name: str | None
) -> m.Attempt:
    thread = threads.create_thread(conn, "photos", kind="filled", test_id=test_id)
    run = runs.create_run(
        conn,
        thread.id,
        "extract",
        m.ExtractInput(pages=PAGES, existing_test_id=test_id, supersedes_attempt_id=None),
        status="done",
    )
    att = attempts.insert_attempt(
        conn,
        m.Attempt(
            id=attempts.next_attempt_id(conn),
            test_id=test_id,
            thread_id=thread.id,
            student_id=None,
            student_name_read=name,
            class_read="8A" if name else None,
            source_run_id=run.id,
            superseded_by=None,
            status="graded" if graded else "extracted",
            version=1,
            score_earned=0.5 if graded else None,
            score_possible=0.75 if graded else None,
            created_at=T0,
        ),
    )
    attempts.insert_answers(
        conn,
        [
            m.Answer(
                attempt_id=att.id,
                question_id=q,
                printed_number=i + 1,
                page_no=1,
                value="A",
                value_norm="a",
                location="circled_option",
                confidence=0.95,
                reading_unsure=False,
                alt_value=None,
                alt_question_id=None,
                verdict="correct" if graded else "ungraded",
                points_awarded=0.25 if graded else None,
                teacher_override=None,
            )
            for i, q in enumerate(qids)
        ],
    )
    return att


def _key(test_id: str, qid: str, accepted: str) -> m.AnswerKey:
    return m.AnswerKey(
        test_id=test_id,
        question_id=qid,
        accepted=[accepted],
        reason_vi="lý do",
        source="ai",
        status="ai_uncertain",
        confidence=0.4,
        updated_at=T0,
        checker=m.KeyCheck(status="disagreed", answer="D", reasoning="r"),
    )


@dataclass
class World:
    t: str  # the item's test (T-0001): q1..q3, points assumed, occasion Other:unknown
    t2: str  # the bank test (T-0002): p1..p3
    a1: m.Attempt  # on t
    a2: m.Attempt  # on t
    a3: m.Attempt  # on t2, with an answer left on the old question "x-old" by a merge
    s1: str  # an existing student


def _world(conn: sqlite3.Connection, graded: bool) -> World:
    t = _test(conn, "q", "Other:unknown")
    t2 = _test(conn, "p", "FinalTerm")
    a1 = _attempt(conn, t, ["q1", "q2", "q3"], graded, "  Nguyễn  Văn An ")
    a2 = _attempt(conn, t, ["q1", "q2", "q3"], graded, None)
    a3 = _attempt(conn, t2, ["p1", "x-old"], graded, None)
    keys.upsert_key(conn, _key(t, "q1", "A"))
    keys.upsert_key(conn, _key(t, "q3", "B"))
    # a cached explanation on q1 (key change → deleted; status-only change → kept)
    step = runs.insert_step(conn, a1.source_run_id, "explain", None, 1)
    call = runs.insert_llm_call(
        conn,
        m.LlmCall(
            id=db.new_ulid(),
            step_id=step.id,
            role="reasoning",
            model="model",
            prompt_hash="h",
            request={},
            response_text="",
            thinking_text="",
            logprobs=None,
            status="complete",
            tokens_in=None,
            tokens_out=None,
            ms=None,
            created_at=T0,
        ),
    )
    explanations.upsert_explanation(
        conn,
        m.Explanation(
            test_id=t,
            question_id="q1",
            wrong_answer_norm="b",
            error_type="gap",
            text_vi="giải thích",
            status="ai",
            llm_call_id=call.id,
        ),
    )
    s1 = students.create_student(conn, "Trần Bình", "tran binh", class_name="8B").id
    # sentinels keep a1 and a3 un-reviewed, so resolving the tested item changes no attempt
    # status (the `reviewed` rule is R10.4, not this table)
    for att, qid in ((a1, "q2"), (a3, "p1")):
        review.upsert_item(
            conn,
            kind="uncertain_answer",
            owner="extract",
            dedupe_key=f"sentinel:{att.id}",
            proposal={},
            test_id=att.test_id,
            attempt_id=att.id,
            question_id=qid,
        )
    return World(t, t2, a1, a2, a3, s1)


def _item(conn: sqlite3.Connection, kind: str, w: World, **kw: Any) -> str:
    item, _ = review.upsert_item(
        conn,
        kind=kind,  # type: ignore[arg-type]
        owner="extract",
        dedupe_key=f"{kind}:test",
        proposal=kw.pop("proposal", {}),
        test_id=kw.pop("test_id", w.t),
        attempt_id=kw.pop("attempt_id", None),
        question_id=kw.pop("question_id", None),
    )
    return item.id


# --- the item each kind is tested on ---------------------------------------------------------

ItemMaker = Callable[[sqlite3.Connection, World], str]

MAKERS: dict[str, ItemMaker] = {
    "uncertain_answer": lambda c, w: _item(
        c, "uncertain_answer", w, attempt_id=w.a1.id, question_id="q1"
    ),
    "box_inline_conflict": lambda c, w: _item(
        c,
        "box_inline_conflict",
        w,
        attempt_id=w.a1.id,
        question_id="q1",
        proposal={"box_value": "C", "inline_value": "D"},
    ),
    "uncertain_key": lambda c, w: _item(c, "uncertain_key", w, question_id="q1"),
    "key_unmapped": lambda c, w: _item(
        c,
        "key_unmapped",
        w,
        proposal={"position": 3, "label": "9", "answer": "C", "confidence": 0.8, "reason": "x"},
    ),
    "possible_duplicate": lambda c, w: _item(
        c,
        "possible_duplicate",
        w,
        proposal={
            "best_test_id": w.t2,
            "similarity": 0.97,
            "tier": "high",
            "question_alignment": {"q1": "p1", "q2": "p2", "q3": "p3"},
        },
    ),
    "merge_unaligned": lambda c, w: _item(
        c,
        "merge_unaligned",
        w,
        test_id=w.t2,
        attempt_id=w.a3.id,
        question_id="x-old",
        proposal={
            "ref": "r",
            "merged_test_id": w.t,
            "survivor_test_id": w.t2,
            "old_question_id": "x-old",
            "printed_number": 2,
            "value": "A",
            "reason": "unaligned",
            "candidate_question_ids": ["p2", "p3"],
        },
    ),
    "picked_test_mismatch": lambda c, w: _item(
        c,
        "picked_test_mismatch",
        w,
        attempt_id=w.a1.id,
        proposal={"similarity": 0.1, "header_text": "x", "first_stems": []},
    ),
    "unknown_student": lambda c, w: _item(
        c,
        "unknown_student",
        w,
        attempt_id=w.a1.id,
        proposal={"student_name_read": w.a1.student_name_read, "class_read": "8A"},
    ),
    "unknown_occasion": lambda c, w: _item(
        c, "unknown_occasion", w, proposal={"occasion": "Other:unknown", "header_text": "x"}
    ),
    "points_assumed": lambda c, w: _item(
        c,
        "points_assumed",
        w,
        proposal={
            "section_number": 1,
            "printed_title": "I",
            "points_per_question": 0.25,
            "questions": 3,
        },
    ),
    "validator_failed": lambda c, w: _item(
        c,
        "validator_failed",
        w,
        proposal={"task": "transcribe_page", "page_no": 1, "failures": [], "call_failure": None},
    ),
    "unreadable_text": lambda c, w: _unreadable_item(c, w),
}


# --- unreadable_text (step 21a, PRD D25) -------------------------------------------------------

INSTR = "sections[0].instructions"
STEM1 = "sections[0].groups[0].questions[0].stem"
LABEL2 = "sections[0].groups[0].questions[1].options[1].label"


def _unreadable_content() -> m.TestContent:
    """``_content("q")`` with ``???`` in the instructions, q1's stem and q2's option B label."""
    content = _content("q")
    section = content.sections[0]
    section.instructions = "Circle ??? or B."
    qs = section.groups[0].questions
    qs[0].stem = "Stem ??? 1"
    qs[1].options = [m.Option(label="A", text="one"), m.Option(label="???", text="two")]
    return content


def _unreadable_item(c: sqlite3.Connection, w: World) -> str:
    content = _unreadable_content()
    tests.update_content(c, w.t, content, 0.75)
    spans = [
        {"path": INSTR, "question_id": None, "text": "Circle ??? or B."},
        {"path": STEM1, "question_id": "q1", "text": "Stem ??? 1"},
        {"path": LABEL2, "question_id": "q2", "text": "???"},
    ]
    return _item(
        c,
        "unreadable_text",
        w,
        proposal={"page_no": 1, "file_id": "f-page-1", "spans": spans},
    )


UNREADABLE_FIX = {
    "spans": [{"path": INSTR, "text": "Circle A or B."}, {"path": STEM1, "text": "Stem 1"}]
}


def _unreadable_accept(c: sqlite3.Connection, w: World) -> None:
    t = tests.get_test(c, w.t)
    assert t is not None and t.content == _unreadable_content()  # the ??? spans stay


def _unreadable_fixed(c: sqlite3.Connection, w: World) -> None:
    t = tests.get_test(c, w.t)
    assert t is not None
    expected = _unreadable_content()
    expected.sections[0].instructions = "Circle A or B."
    expected.sections[0].groups[0].questions[0].stem = "Stem 1"
    # the listed fields hold the typed text; the others unchanged; equal points (v1.19)
    assert t.content == equal_points(expected)
    assert t.points_possible == 10.0


# --- per-row data checks ---------------------------------------------------------------------


def _answer(c: sqlite3.Connection, att: str, qid: str) -> m.Answer:
    a = attempts.get_answer(c, att, qid)
    assert a is not None
    return a


def _override(value: str, norm: str) -> Callable[[sqlite3.Connection, World], None]:
    def check(c: sqlite3.Connection, w: World) -> None:
        a = _answer(c, w.a1.id, "q1")
        assert (a.teacher_override, a.value_norm) == (value, norm)

    return check


def _key_accept(c: sqlite3.Connection, w: World) -> None:
    k = keys.get_key(c, w.t, "q1")
    assert k is not None
    assert (k.accepted, k.source, k.status) == (["A"], "ai", "teacher_verified")
    assert k.checker is None  # R22.5.5.12: Accept clears the stale checker
    assert len(explanations.list_explanations(c, w.t)) == 1


def _key_fix(c: sqlite3.Connection, w: World) -> None:
    k = keys.get_key(c, w.t, "q1")
    assert k is not None
    assert (k.accepted, k.source, k.status) == (["B", "b."], "teacher_edit", "teacher_verified")
    assert explanations.list_explanations(c, w.t) == []


def _unmapped_accept(c: sqlite3.Connection, w: World) -> None:
    assert [k.question_id for k in keys.list_keys(c, w.t)] == ["q1", "q3"]


def _unmapped_fix(c: sqlite3.Connection, w: World) -> None:
    k = keys.get_key(c, w.t, "q2")
    assert k is not None
    assert (k.accepted, k.source, k.status) == (["C"], "teacher_edit", "teacher_verified")


def _merged(c: sqlite3.Connection, w: World) -> None:
    t = tests.get_test(c, w.t)
    assert t is not None and t.merged_into == w.t2
    for att in (w.a1, w.a2):
        moved = attempts.get_attempt(c, att.id)
        assert moved is not None and moved.test_id == w.t2
        assert {a.question_id for a in attempts.list_answers(c, att.id)} == {"p1", "p2", "p3"}


def _unaligned_accept(c: sqlite3.Connection, w: World) -> None:
    a = _answer(c, w.a3.id, "x-old")
    assert a.verdict in ("ungraded", "correct")  # untouched by the resolution
    assert attempts.get_answer(c, w.a3.id, "p2") is None


def _unaligned_fix(c: sqlite3.Connection, w: World) -> None:
    assert attempts.get_answer(c, w.a3.id, "x-old") is None
    assert _answer(c, w.a3.id, "p2").value == "A"


def _mismatch(c: sqlite3.Connection, w: World) -> None:
    queued = [r for r in runs.list_runs(c, status="queued") if r.kind == "extract"]
    assert len(queued) == 1
    run = queued[0]
    assert run.thread_id == w.a1.thread_id
    assert run.input == m.ExtractInput(
        pages=PAGES, existing_test_id=None, supersedes_attempt_id=w.a1.id
    )


def _student_is(
    name: str, search: str, klass: str | None
) -> Callable[[sqlite3.Connection, World], None]:
    def check(c: sqlite3.Connection, w: World) -> None:
        att = attempts.get_attempt(c, w.a1.id)
        assert att is not None and att.student_id is not None
        s = students.get_student(c, att.student_id)
        assert s is not None
        assert (s.full_name, s.name_search, s.class_name) == (name, search, klass)

    return check


def _occasion(value: str, edited: list[str]) -> Callable[[sqlite3.Connection, World], None]:
    def check(c: sqlite3.Connection, w: World) -> None:
        t = tests.get_test(c, w.t)
        assert t is not None
        assert (t.meta.occasion, t.meta.edited_fields) == (value, edited)

    return check


def _points(
    per: float, source: str, possible: float
) -> Callable[[sqlite3.Connection, World], None]:
    def check(c: sqlite3.Connection, w: World) -> None:
        t = tests.get_test(c, w.t)
        assert t is not None
        sec = t.content.sections[0]
        assert [q.points for g in sec.groups for q in g.questions] == [per] * 3
        assert (round(sec.points, 6), sec.points_source, t.points_possible) == (
            round(per * 3, 6),
            source,
            possible,
        )

    return check


def _content_unchanged(c: sqlite3.Connection, w: World) -> None:
    t = tests.get_test(c, w.t)
    assert t is not None and t.content == _content("q")


def _content_fixed(c: sqlite3.Connection, w: World) -> None:
    t = tests.get_test(c, w.t)
    assert t is not None and t.content == equal_points(_content("q", n=2))
    assert t.points_possible == 10.0
    assert [k.question_id for k in keys.list_keys(c, w.t)] == ["q1"]  # q3's key left with q3


# --- Appendix E, verbatim labels -------------------------------------------------------------


@dataclass
class Row:
    label: str
    kind: str
    action: str
    value: Any
    runs_graded: int  # grade runs when the attempts are graded (0 when ungraded)
    reason: str | None
    version_attempt: str | None  # "a1" / "a3": that attempt's version goes +1
    check: Callable[[sqlite3.Connection, World], None]
    maker: ItemMaker | None = None  # the item to resolve; default MAKERS[kind]


ROWS = [
    Row(
        "uncertain_answer · accept | `teacher_override` = the value read; `value_norm` recomputed;"
        " version+1; graded → 1 grade run (review_fix)",
        "uncertain_answer", "accept", None, 1, "review_fix", "a1", _override("A", "a"),
    ),
    Row(
        "uncertain_answer · fix(value) | `teacher_override` = value; `value_norm` recomputed;"
        " version+1; graded → 1 grade run (review_fix)",
        "uncertain_answer", "fix", "  Went ", 1, "review_fix", "a1", _override("  Went ", "went"),
    ),
    Row(
        "box_inline_conflict · accept | `teacher_override` = the box value; version+1;"
        " graded → 1 grade run (review_fix)",
        "box_inline_conflict", "accept", None, 1, "review_fix", "a1", _override("C", "c"),
    ),
    Row(
        "box_inline_conflict · fix(value) | `teacher_override` = value; version+1;"
        " graded → 1 grade run (review_fix)",
        "box_inline_conflict", "fix", "D", 1, "review_fix", "a1", _override("D", "d"),
    ),
    Row(
        "uncertain_key · accept | key unchanged, status `teacher_verified`; explanations kept;"
        " N grade runs (key_verified), N = graded attempts on the test",
        "uncertain_key", "accept", None, 2, "key_verified", None, _key_accept,
    ),
    Row(
        "uncertain_key · fix(key) | key replaced, `teacher_edit`, `teacher_verified`; that"
        " question's explanations deleted; N grade runs (key_verified)",
        "uncertain_key", "fix", ["B", "b."], 2, "key_verified", None, _key_fix,
    ),
    Row(
        "key_unmapped · accept | the entry is discarded; no key row; no run",
        "key_unmapped", "accept", None, 0, None, None, _unmapped_accept,
    ),
    Row(
        "key_unmapped · fix(question_id) | key row for that question (`teacher_edit`,"
        " `teacher_verified`); N grade runs (key_verified)",
        "key_unmapped", "fix", "q2", 2, "key_verified", None, _unmapped_fix,
    ),
    Row(
        "possible_duplicate · accept | merge (R10.3); 1 grade run (merge) per moved graded attempt",
        "possible_duplicate", "accept", None, 2, "merge", None, _merged,
    ),
    Row(
        "merge_unaligned · accept | the answer stays `ungraded` on the old question; no run",
        "merge_unaligned", "accept", None, 0, None, None, _unaligned_accept,
    ),
    Row(
        "merge_unaligned · fix(question_id) | the answer moved to that question of the survivor;"
        " graded → 1 grade run (merge)",
        "merge_unaligned", "fix", "p2", 1, "merge", None, _unaligned_fix,
    ),
    Row(
        "picked_test_mismatch · accept | 1 queued extract run with `existing_test_id=None` and"
        " `supersedes_attempt_id` set",
        "picked_test_mismatch", "accept", None, 0, None, None, _mismatch,
    ),
    Row(
        "unknown_student · accept | a new student from `student_name_read` →"
        " `attempts.student_id`; version+1; no run. Rejected if no name was read",
        "unknown_student", "accept", None, 0, None, "a1",
        _student_is("Nguyễn Văn An", "nguyen van an", "8A"),
    ),
    Row(
        "unknown_student · fix(S or new name) | `attempts.student_id` = S (or a new student);"
        " version+1; no run",
        "unknown_student", "fix", "S-0001", 0, None, "a1",
        _student_is("Trần Bình", "tran binh", "8B"),
    ),
    Row(
        "unknown_occasion · accept | occasion stays `Other:unknown`; no run",
        "unknown_occasion", "accept", None, 0, None, None, _occasion("Other:unknown", []),
    ),
    Row(
        "unknown_occasion · fix(occasion) | `write_test_meta(by_teacher)`; `edited_fields` has"
        " occasion; no run",
        "unknown_occasion", "fix", "MidTerm", 0, None, None, _occasion("MidTerm", ["occasion"]),
    ),
    Row(
        "points_assumed · accept | points stay 0.25 each; no run",
        "points_assumed", "accept", None, 0, None, None, _points(0.25, "assumed", 0.75),
    ),
    Row(
        "points_assumed · fix(points) | v1.19: the typed points are ignored; equal points"
        " (10 / 3 each), `points_possible` 10; no run (the attempts are re-scored in place)",
        "points_assumed", "fix", {"points_per_question": 0.5}, 0, None, None,
        _points(10 / 3, "equal", 10.0),
    ),
    Row(
        "validator_failed · accept | content unchanged; no run",
        "validator_failed", "accept", None, 0, None, None, _content_unchanged,
    ),
    Row(
        "validator_failed · fix(content) | content updated and re-validated; no run unless a key"
        " changed (then as uncertain_key · fix)",
        # q3 (which has a key row) is removed, so a key changed → N grade runs (key_verified)
        "validator_failed", "fix", {"content": _content("q", n=2).model_dump(mode="json")},
        2, "key_verified", None, _content_fixed,
    ),
    Row(
        "unreadable_text · accept *(step 21a)* | content unchanged (the `???` spans stay); no run",
        "unreadable_text", "accept", None, 0, None, None, _unreadable_accept,
    ),
    Row(
        "unreadable_text · fix(spans) *(step 21a)* | each listed field set to the typed text"
        " through the content edit (`write_test_meta`, re-validated); other fields unchanged;"
        " no run. An invalid edit is rejected and nothing changes",
        "unreadable_text", "fix", UNREADABLE_FIX, 0, None, None, _unreadable_fixed,
    ),
]  # fmt: skip


def _grade_runs(conn: sqlite3.Connection) -> list[m.Run]:
    return [r for r in runs.list_runs(conn) if r.kind == "grade"]


@pytest.mark.parametrize("graded", [True, False], ids=["graded", "ungraded"])
@pytest.mark.parametrize("row", ROWS, ids=[r.label.split(" |")[0] for r in ROWS])
def test_appendix_e_row(conn: sqlite3.Connection, row: Row, graded: bool) -> None:
    """R10.1: one row per (kind, action) of Appendix E, graded and ungraded."""
    w = _world(conn, graded)
    item_id = (row.maker or MAKERS[row.kind])(conn, w)
    versions = {a.id: a.version for a in (w.a1, w.a2, w.a3)}
    assert _grade_runs(conn) == []

    result = resolve(conn, item_id, row.action, row.value)  # type: ignore[arg-type]

    item = review.get_item(conn, item_id)
    assert item == result.item
    assert item.status == ("accepted" if row.action == "accept" else "fixed")
    assert item.resolution == {"action": row.action, "value": row.value}
    assert item.resolved_at is not None

    deferred = row.reason == "key_verified"  # data-model v1.20: a key change waits for regrade
    if deferred:
        assert _grade_runs(conn) == [] and result.followup_run_ids == []
        test_id = item.test_id
        assert test_id is not None
        assert regrade.is_pending(conn, test_id) is graded  # no graded attempt → no row
    queued_now = [r.id for r in runs.list_runs(conn, status="queued")]
    assert sorted(result.followup_run_ids) == sorted(queued_now)
    if deferred:
        assert item.test_id is not None
        regrade.start(conn, item.test_id)  # POST /tests/{id}/regrade
        assert not regrade.is_pending(conn, item.test_id)
        assert regrade.start(conn, item.test_id) == []  # a second call queues none
    grade = _grade_runs(conn)
    expected = row.runs_graded if graded else 0
    assert len(grade) == expected
    for run in grade:
        assert isinstance(run.input, m.GradeInput)
        assert run.status == "queued"
        assert run.input.reason == row.reason
    queued = [r.id for r in runs.list_runs(conn, status="queued")]
    assert item.followup_run_id == (result.followup_run_ids[0] if queued_now else None)
    if row.kind == "picked_test_mismatch":
        assert len(queued) == 1  # the extract run, graded or not

    bumped = {"a1": w.a1.id, "a3": w.a3.id}.get(row.version_attempt or "")
    for att_id, before in versions.items():
        att = attempts.get_attempt(conn, att_id)
        assert att is not None
        assert att.version == before + (1 if att_id == bumped else 0)

    row.check(conn, w)


# --- confirmed blank (data-model v1.5.2: teacher_override "" = "the teacher confirmed no answer")

BLANK_ROWS = [
    Row(
        "uncertain_answer · accept (value read None) | `teacher_override` = \"\" (confirmed"
        " blank); `value_norm` = \"\"; version+1; graded → 1 grade run (review_fix)",
        "uncertain_answer", "accept", None, 1, "review_fix", "a1", _override("", ""),
        maker=lambda c, w: _item(
            c, "uncertain_answer", w, attempt_id=w.a1.id, question_id="q1",
            proposal={"value": None, "confidence": 0.0},
        ),
    ),
    Row(
        "uncertain_answer · fix(\"\") | `teacher_override` = \"\" (confirmed blank);"
        " `value_norm` = \"\"; version+1; graded → 1 grade run (review_fix)",
        "uncertain_answer", "fix", "", 1, "review_fix", "a1", _override("", ""),
    ),
    Row(
        "box_inline_conflict · accept (box value None) | `teacher_override` = \"\" (confirmed"
        " blank); version+1; graded → 1 grade run (review_fix)",
        "box_inline_conflict", "accept", None, 1, "review_fix", "a1", _override("", ""),
        maker=lambda c, w: _item(
            c, "box_inline_conflict", w, attempt_id=w.a1.id, question_id="q1",
            proposal={"box_value": None, "inline_value": "D"},
        ),
    ),
    Row(
        "box_inline_conflict · fix(\"\") | `teacher_override` = \"\" (confirmed blank);"
        " version+1; graded → 1 grade run (review_fix)",
        "box_inline_conflict", "fix", "", 1, "review_fix", "a1", _override("", ""),
    ),
]  # fmt: skip


@pytest.mark.parametrize("graded", [True, False], ids=["graded", "ungraded"])
@pytest.mark.parametrize("row", BLANK_ROWS, ids=[r.label.split(" |")[0] for r in BLANK_ROWS])
def test_confirmed_blank_row(conn: sqlite3.Connection, row: Row, graded: bool) -> None:
    """Accept of a None reading, or Fix with "", stores the confirmed blank ``""``."""
    test_appendix_e_row(conn, row, graded)


def test_every_kind_and_action_has_a_row() -> None:
    pairs = {(r.kind, r.action) for r in ROWS}
    expected = {(k, "accept") for k in MAKERS} | {
        (k, "fix") for k in MAKERS if k not in ("possible_duplicate", "picked_test_mismatch")
    }
    assert pairs == expected
    assert len(ROWS) == 22  # R21a.7: the two unreadable_text rows included


def test_skip_covers_all_12_kinds() -> None:
    """R21a.7: R10.2's Skip check runs over every ``ReviewItem.kind``."""
    kinds = set(get_args(m.ReviewItem.model_fields["kind"].annotation))
    assert set(MAKERS) == kinds
    assert len(kinds) == 12


# --- R10.2: Skip -----------------------------------------------------------------------------


def _dump(conn: sqlite3.Connection) -> dict[str, list[tuple[Any, ...]]]:
    names = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            " ORDER BY name"
        )
    ]
    return {
        n: sorted((tuple(r) for r in conn.execute(f"SELECT * FROM {n}")), key=repr) for n in names
    }


@pytest.mark.parametrize("graded", [True, False], ids=["graded", "ungraded"])
@pytest.mark.parametrize("kind", sorted(MAKERS))
def test_skip_changes_only_the_item(conn: sqlite3.Connection, kind: str, graded: bool) -> None:
    """R10.2: any · skip | status `skipped`; nothing else changes."""
    w = _world(conn, graded)
    item_id = MAKERS[kind](conn, w)
    before = _dump(conn)

    result = resolve(conn, item_id, "skip")

    after = _dump(conn)
    assert result.followup_run_ids == []
    assert {n for n in before if before[n] != after[n]} == {"review_items"}
    cols = [d[1] for d in conn.execute("PRAGMA table_info(review_items)")]
    id_col = cols.index("id")
    old = {r[id_col]: dict(zip(cols, r, strict=True)) for r in before["review_items"]}
    new = {r[id_col]: dict(zip(cols, r, strict=True)) for r in after["review_items"]}
    assert old.keys() == new.keys()
    for rid in old:
        changed = {c for c in cols if old[rid][c] != new[rid][c]}
        assert changed == ({"status", "resolution", "resolved_at"} if rid == item_id else set())
    assert new[item_id]["status"] == "skipped"
    assert new[item_id]["followup_run_id"] is None


# --- refusals --------------------------------------------------------------------------------


def test_non_open_item_is_refused(conn: sqlite3.Connection) -> None:
    w = _world(conn, graded=True)
    item_id = MAKERS["uncertain_answer"](conn, w)
    resolve(conn, item_id, "skip")
    before = _dump(conn)
    with pytest.raises(ReviewNotOpen):
        resolve(conn, item_id, "accept")
    assert _dump(conn) == before


@pytest.mark.parametrize(
    ("kind", "action", "value"),
    [
        ("possible_duplicate", "fix", "x"),
        ("picked_test_mismatch", "fix", "x"),
        ("uncertain_answer", "fix", None),
        ("uncertain_answer", "delete", None),
        ("key_unmapped", "fix", "no-such-question"),
        ("merge_unaligned", "fix", "p1"),  # taken by another answer
        ("merge_unaligned", "fix", "q1"),  # not a survivor question
        ("unknown_student", "fix", "S-0099"),
        ("unknown_occasion", "fix", "Sometime"),
        ("points_assumed", "fix", {"per": 1}),
        ("uncertain_key", "fix", []),
    ],
)
def test_invalid_resolution_changes_nothing(
    conn: sqlite3.Connection, kind: str, action: str, value: Any
) -> None:
    w = _world(conn, graded=True)
    item_id = MAKERS[kind](conn, w)
    before = _dump(conn)
    with pytest.raises(InvalidResolution):
        resolve(conn, item_id, action, value)  # type: ignore[arg-type]
    assert _dump(conn) == before


def test_invalid_content_is_refused(conn: sqlite3.Connection) -> None:
    """validator_failed · fix: content that fails the validators is not stored."""
    w = _world(conn, graded=True)
    item_id = MAKERS["validator_failed"](conn, w)
    bad = _content("q")
    bad.sections[0].groups[0].questions[1].options = [m.Option(label="B", text="x")]
    before = _dump(conn)
    with pytest.raises(InvalidResolution):
        resolve(conn, item_id, "fix", {"content": bad.model_dump(mode="json")})
    assert _dump(conn) == before


def test_content_fix_without_key_change_queues_nothing(conn: sqlite3.Connection) -> None:
    w = _world(conn, graded=True)
    item_id = MAKERS["validator_failed"](conn, w)
    fixed = _content("q")
    fixed.sections[0].groups[0].questions[0].stem = "Corrected stem"
    result = resolve(conn, item_id, "fix", {"content": fixed.model_dump(mode="json")})
    assert result.followup_run_ids == [] and _grade_runs(conn) == []
    t = tests.get_test(conn, w.t)
    assert t is not None and t.content == equal_points(fixed)


def test_unknown_student_accept_without_name_is_rejected(conn: sqlite3.Connection) -> None:
    w = _world(conn, graded=True)
    item_id = _item(
        conn,
        "unknown_student",
        w,
        attempt_id=w.a2.id,  # no name read
        proposal={"student_name_read": None, "class_read": None},
    )
    before = _dump(conn)
    with pytest.raises(InvalidResolution):
        resolve(conn, item_id, "accept")
    assert _dump(conn) == before


def test_unknown_student_fix_with_new_name(conn: sqlite3.Connection) -> None:
    w = _world(conn, graded=False)
    item_id = MAKERS["unknown_student"](conn, w)
    resolve(conn, item_id, "fix", "Lê Thị Hoa")
    _student_is("Lê Thị Hoa", "le thi hoa", "8A")(conn, w)


def test_points_fix_by_section_total(conn: sqlite3.Connection) -> None:
    w = _world(conn, graded=False)
    item_id = MAKERS["points_assumed"](conn, w)
    resolve(conn, item_id, "fix", {"section_total": 1.5})
    _points(10 / 3, "equal", 10.0)(conn, w)  # v1.19: the typed total is ignored


def test_last_open_item_marks_attempt_reviewed(conn: sqlite3.Connection) -> None:
    """Resolving the attempt's last open item → ``reviewed`` (data-model §5.3)."""
    w = _world(conn, graded=True)
    item_id = _item(conn, "uncertain_answer", w, attempt_id=w.a2.id, question_id="q1")
    resolve(conn, item_id, "accept")
    att = attempts.get_attempt(conn, w.a2.id)
    assert att is not None and att.status == "reviewed"


# --- R21a.3, R21a.4: unreadable_text Fix and Accept --------------------------------------------


@pytest.mark.parametrize("graded", [True, False], ids=["graded", "ungraded"])
def test_r21a_3_fix_replaces_the_spans(conn: sqlite3.Connection, graded: bool) -> None:
    """R21a.3: the listed fields hold the typed text and no ``???``; others unchanged; status
    ``fixed``; 0 runs queued."""
    w = _world(conn, graded)
    item_id = MAKERS["unreadable_text"](conn, w)
    fix = {
        "spans": [
            {"path": INSTR, "text": "Circle A or B."},
            {"path": STEM1, "text": "Stem 1"},
            {"path": LABEL2, "text": "B"},
        ]
    }
    result = resolve(conn, item_id, "fix", fix)
    assert result.item.status == "fixed"
    assert result.followup_run_ids == [] and runs.list_runs(conn, status="queued") == []
    t = tests.get_test(conn, w.t)
    assert t is not None
    assert t.content == equal_points(_content("q"))  # every ??? replaced; equal points
    assert "???" not in t.content.model_dump_json()


@pytest.mark.parametrize(
    "value",
    [
        {"spans": []},
        {"spans": [{"path": "sections[0].title", "text": "x"}]},  # not a span of the item
        {"spans": [{"path": STEM1, "text": None}]},
        {"spans": [{"path": STEM1}]},
        [{"path": STEM1, "text": "Stem 1"}],  # not {spans: …}
        {"spans": [{"path": LABEL2, "text": "Z"}]},  # mcq labels A, Z: fails the validators
        {"spans": [{"path": STEM1, "text": "Stem 1"}, {"path": LABEL2, "text": "Z"}]},
    ],
    ids=["empty", "unlisted-path", "text-none", "no-text", "bare-list", "invalid", "mixed"],
)
def test_r21a_3_invalid_fix_changes_nothing(conn: sqlite3.Connection, value: Any) -> None:
    w = _world(conn, graded=True)
    item_id = MAKERS["unreadable_text"](conn, w)
    before = _dump(conn)
    with pytest.raises(InvalidResolution):
        resolve(conn, item_id, "fix", value)
    assert _dump(conn) == before


def test_r21a_3_printed_title_fix_updates_its_copy(conn: sqlite3.Connection) -> None:
    w = _world(conn, graded=False)
    content = _content("q")
    content.sections[0].printed_title = "V???"
    content.sections[0].title = "V???"
    tests.update_content(conn, w.t, content, 0.75)
    path = "sections[0].printed_title"
    item_id = _item(
        conn,
        "unreadable_text",
        w,
        proposal={
            "page_no": 1,
            "file_id": "f-page-1",
            "spans": [{"path": path, "question_id": None, "text": "V???"}],
        },
    )
    resolve(conn, item_id, "fix", {"spans": [{"path": path, "text": "VI"}]})
    t = tests.get_test(conn, w.t)
    assert t is not None
    assert (t.content.sections[0].printed_title, t.content.sections[0].title) == ("VI", "VI")


@pytest.mark.parametrize("graded", [True, False], ids=["graded", "ungraded"])
def test_r21a_4_accept_keeps_the_spans(conn: sqlite3.Connection, graded: bool) -> None:
    """R21a.4: content unchanged (the ``???`` spans stay); status ``accepted``; 0 runs."""
    w = _world(conn, graded)
    item_id = MAKERS["unreadable_text"](conn, w)
    before = _dump(conn)
    result = resolve(conn, item_id, "accept")
    assert result.item.status == "accepted"
    assert result.followup_run_ids == [] and runs.list_runs(conn, status="queued") == []
    after = _dump(conn)
    assert {n for n in before if before[n] != after[n]} == {"review_items"}
    t = tests.get_test(conn, w.t)
    assert t is not None and t.content == _unreadable_content()
