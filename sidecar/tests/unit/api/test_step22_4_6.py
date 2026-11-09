"""Step 22.4.6: report wording and order (PRD v8.2, llm-design v4.37).

R22.4.6.1 every taxonomy code has a name; the report route gives each weak point its
``skill_name``. R22.4.6.2 no taxonomy code in the route's text or the Word file. R22.4.6.3
explanations written as 28, 17, 27 come out as 17, 27, 28.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import pytest
from docx import Document
from unit.api.test_routes_b import T0, _attempt, _content, _llm_call
from unit.api.test_step22_1_6 import _text

from etach.api.deps import AppContext
from etach.domain import docx_export, skills
from etach.domain import models as m
from etach.llm.tasks import taxonomy_ids
from etach.store import db
from etach.store.repos import attempts, explanations, tests

GRAMMAR = "GR-PSV-A1"
CODE = re.compile(r"\b(?:" + "|".join(map(re.escape, skills.skill_names())) + r")\b")


@pytest.fixture
def ctx(make_ctx: Callable[..., AppContext]) -> AppContext:
    return make_ctx()


def test_r22_4_6_1_every_code_has_a_name() -> None:
    names = skills.skill_names()
    assert set(taxonomy_ids()) == set(names)
    assert all(n and n != code for code, n in names.items())
    assert skills.skill_name("VOC-TOPIC") == "Vocabulary — topic words"
    assert skills.skill_name(GRAMMAR) == "Present Simple — Affirmative Forms"
    assert skills.skill_name("XYZ-NOPE") == skills.OTHER_SKILL == "Other skill"


def test_name_codes_replaces_whole_codes_only() -> None:
    text = "Yếu VOC-TOPIC, (GR-PSV-A1); VOC-TOPICS và ABC giữ nguyên."
    assert skills.name_codes(text) == (
        "Yếu Vocabulary — topic words, (Present Simple — Affirmative Forms); "
        "VOC-TOPICS và ABC giữ nguyên."
    )
    assert skills.name_codes("") == ""


def _report(attempt_id: str, run_id: str) -> m.GradeReport:
    return m.GradeReport(
        attempt_id=attempt_id,
        run_id=run_id,
        weak_points=[
            m.WeakPoint(
                skill_tag="VOC-TOPIC", wrong=3, seen=5, gap_errors=2, note_vi="Ôn VOC-TOPIC."
            ),
            m.WeakPoint(skill_tag=GRAMMAR, wrong=1, seen=4, gap_errors=1, note_vi=""),
            m.WeakPoint(skill_tag="OLD-GONE", wrong=1, seen=1, gap_errors=0, note_vi=""),
        ],
        careless_notes=["Câu 17: nhầm VOC-TOPIC."],
        summary_vi="Học sinh yếu VOC-TOPIC và GR-PSV-A1.",
        teacher_questions=[
            m.TeacherQuestion(
                question_vi="Em có biết VOC-TOPIC không?",
                what_answers_mean_vi="Nếu không, ôn GR-PSV-A1.",
            )
        ],
        uncertain_points=0.0,
        created_at=T0,
    )


def _setup(ctx: AppContext) -> str:
    """A test whose questions q-1, q-2, q-3 are printed 28, 17, 27; all three answered wrong; the
    explanations written in id order (28, 17, 27)."""
    conn = db.connect(ctx.paths.db)
    try:
        content = _content(3)
        qs = content.sections[0].groups[0].questions
        for q, n in zip(qs, (28, 17, 27), strict=True):
            q.printed_number = n
        test_id = tests.insert_test(
            conn,
            m.Test(
                id=tests.next_test_id(conn),
                meta=m.TestMetadata(occasion="FinalTerm", grade=8, term=1, test_number="1"),
                content=content,
                content_schema_version=1,
                fingerprint="fp",
                points_possible=0.75,
                source_run_id=None,
                merged_into=None,
                created_at=T0,
                updated_at=T0,
            ),
        ).id
        att = _attempt(conn, test_id, graded=True)
        (first,) = [a for a in attempts.list_answers(conn, att.id) if a.question_id == "q-2"]
        attempts.insert_answers(
            conn, [first.model_copy(update={"question_id": "q-3", "printed_number": 3})]
        )
        call = _llm_call(conn)
        for qid in ("q-1", "q-2", "q-3"):
            explanations.upsert_explanation(
                conn,
                m.Explanation(
                    test_id=test_id,
                    question_id=qid,
                    wrong_answer_norm="a",
                    error_type="gap",
                    text_vi=f"Giải thích {qid}: kỹ năng VOC-TOPIC.",
                    status="ai",
                    llm_call_id=call,
                ),
            )
        attempts.replace_grade_report(conn, _report(att.id, att.source_run_id))
        conn.commit()
        return att.id
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_r22_4_6_route_names_and_order(ctx: AppContext, api: Any) -> None:
    attempt_id = _setup(ctx)
    async with api.serving(ctx) as live, live.client() as client:
        r = await client.get(f"/attempts/{attempt_id}/report", headers=live.auth)
        assert r.status_code == 200, r.text
        body = r.json()
        x = await client.post(f"/attempts/{attempt_id}/report/export", headers=live.auth)
        assert x.status_code == 200, x.text
    # R22.4.6.1: skill_name per weak point, the code kept
    wps = body["report"]["weak_points"]
    assert [(w["skill_tag"], w["skill_name"]) for w in wps] == [
        ("VOC-TOPIC", "Vocabulary — topic words"),
        (GRAMMAR, "Present Simple — Affirmative Forms"),
        ("OLD-GONE", "Other skill"),
    ]
    assert wps[0]["note_vi"] == "Ôn Vocabulary — topic words."
    # R22.4.6.2: no code in the AI-written text
    rep = body["report"]
    texts = [
        rep["summary_vi"],
        *rep["careless_notes"],
        *(q["question_vi"] + q["what_answers_mean_vi"] for q in rep["teacher_questions"]),
        *(w["note_vi"] for w in wps),
        *(e["text_vi"] for e in body["explanations"]),
    ]
    assert not [t for t in texts if CODE.search(t)]
    assert rep["summary_vi"] == (
        "Học sinh yếu Vocabulary — topic words và Present Simple — Affirmative Forms."
    )
    # R22.4.6.3: printed order 17, 27, 28 for the explanations and the verdicts
    assert [e["question_id"] for e in body["explanations"]] == ["q-2", "q-3", "q-1"]
    assert [v["printed_number"] for v in body["verdicts"]] == [17, 27, 28]
    # the Word file: names, no code, explanations 17, 27, 28
    lines = _text(Document(x.json()["path"]))
    assert not [line for line in lines if CODE.search(line)], lines
    assert "Vocabulary — topic words: 3/5 wrong — Ôn Vocabulary — topic words." in lines
    assert "Other skill: 1/1 wrong" in lines
    expl = [line for line in lines if ". Giải thích" in line]
    assert [line.split(".")[0] for line in expl] == ["17", "27", "28"]


def test_r22_4_6_docx_orders_and_names_on_its_own() -> None:
    """``report_document`` given the stored report (codes) and explanations in 28, 17, 27 order."""
    report = _report("A-1", "r")
    exps = [
        m.Explanation(
            test_id="T",
            question_id=q,
            wrong_answer_norm=w,
            error_type="gap",
            text_vi=f"{q} VOC-TOPIC",
            status="ai",
            llm_call_id="c",
        )
        for q, w in (("q-1", "a"), ("q-2", "b"), ("q-3", "a"), ("q-2", "a"))
    ]
    numbers = {"q-1": 28, "q-2": 17, "q-3": 27}
    lines = _text(docx_export.report_document("R", 1, 2, report, [], exps, numbers))
    assert not [line for line in lines if CODE.search(line)], lines
    expl = [line for line in lines if line[:3] in {"17.", "27.", "28."}]
    assert expl == [
        "17. q-2 Vocabulary — topic words",
        "17. q-2 Vocabulary — topic words",
        "27. q-3 Vocabulary — topic words",
        "28. q-1 Vocabulary — topic words",
    ]
    assert "Present Simple — Affirmative Forms: 1/4 wrong" in lines
