"""Step 18 (part A): the grade graph with a FakeOllama that answers by the output schema title.

The test bank row, the attempt and its answers are seeded straight into the database; the
prompts are the real ``FilePromptProvider`` files. ``save_mode = "crash_after"`` raises right
after ``save``'s commit (R18.9).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sqlite3
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from pydantic import ValidationError
from support.fake_ollama import ChatScript, FakeOllama

from etach.appdir import DataPaths
from etach.domain.models import (
    Answer,
    AnswerKey,
    Attempt,
    Option,
    Question,
    QuestionGroup,
    Section,
)
from etach.domain.models import Test as BankTest
from etach.domain.models import TestContent as Content
from etach.domain.models import TestMetadata as Meta
from etach.domain.skills import skill_name
from etach.graphs import grade as grade_mod
from etach.graphs.grade import (
    C2_EDGES,
    C2_NODES,
    GradeDeps,
    answer_value_norm,
    build_grade_graph,
    register_grade,
)
from etach.llm.client import OllamaClient, StreamDropped
from etach.llm.config import default_config
from etach.llm.tasks import TAG_SKILLS_SCHEMA
from etach.prompts.render import FilePromptProvider
from etach.runtime.events import EventBus
from etach.runtime.manager import RunManager
from etach.runtime.power import FakePower
from etach.store import db
from etach.store.repos import attempts, keys, runs, threads
from etach.store.repos import tests as test_repo

TIMEOUT = 60.0
T_ID = "T-0001"
A_ID = "A-0001"

# --- Appendix C.2, verbatim (plan.md) ------------------------------------------------------------

C2_TEXT = """
  - `START→load_context`;
  - `load_context→ai_key_fast` (key needed), `load_context→verify_gate` (not needed), `ai_key_fast→verify_gate`;
  - `verify_gate→verify_key` (verify needed), `verify_gate→tag_skills`, `verify_key→tag_skills`;
  - `tag_skills→save` (no attempt), `tag_skills→grade`;
  - `grade→judge_rewrites` (rewrites pending), `grade→explain`, `judge_rewrites→explain`;
  - `explain→weak_points`, `weak_points→save`, `save→END`.
"""  # noqa: E501


def _c2_edges() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    conv = {"START": "__start__", "END": "__end__"}
    for chunk in C2_TEXT.split("`")[1::2]:
        a, b = chunk.split("→")
        out.add((conv.get(a, a), conv.get(b, b)))
    return out


def test_r18_1_graph_equals_appendix_c2() -> None:
    from unittest.mock import MagicMock

    graph = build_grade_graph(GradeDeps(client=MagicMock()))(None)
    g = graph.get_graph()
    assert {(e.source, e.target) for e in g.edges} == _c2_edges()
    assert set(g.nodes) - {"__start__", "__end__"} == set(C2_NODES)
    assert set(C2_EDGES) == _c2_edges()


def test_tag_skills_schema_caps_three_tags() -> None:
    TAG_SKILLS_SCHEMA.model_validate(
        {"items": [{"question_id": "q", "tags": ["GR-PSV-A1"] * 3, "level": "A1"}]}
    )
    with pytest.raises(ValidationError):
        TAG_SKILLS_SCHEMA.model_validate(
            {"items": [{"question_id": "q", "tags": ["GR-PSV-A1"] * 4, "level": "A1"}]}
        )
    schema = TAG_SKILLS_SCHEMA.model_json_schema()
    assert schema["$defs"]["QuestionTagsCall"]["properties"]["tags"]["maxItems"] == 3


def test_value_norm_uses_the_effective_value() -> None:
    base = _answer("q1", "A")
    assert answer_value_norm(base) == "a"
    assert answer_value_norm(base.model_copy(update={"teacher_override": ""})) == ""
    assert answer_value_norm(base.model_copy(update={"teacher_override": " He\u2019s  Gone"})) == (
        "he's gone"
    )
    assert answer_value_norm(base.model_copy(update={"value": None})) is None


# --- the fake model ------------------------------------------------------------------------------

TITLES = (
    "AiKeyOut",
    "VerifyKeyOut",
    "TagSkillsCall",
    "JudgeOut",
    "ExplainOut",
    "SummaryOut",
)
BAD = "not json at all"


class Routed(FakeOllama):
    """Answers each request from the queue of its schema title; an empty queue → invalid JSON
    (so the client fails the call after its retry). An entry may be a ``ChatScript``."""

    def __init__(self) -> None:
        super().__init__()
        self.queues: dict[str, list[Any]] = {}
        self.seen: list[str] = []

    def _script(self) -> ChatScript:
        fmt = self.requests[-1].get("format")
        title = fmt.get("title") if isinstance(fmt, dict) else None
        assert title in TITLES, title
        self.seen.append(title)
        queue = self.queues.get(title) or []
        item = queue.pop(0) if queue else BAD
        if isinstance(item, ChatScript):
            return item
        text = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        return ChatScript(tokens=list(text))

    def calls(self, title: str) -> int:
        return self.seen.count(title)


# --- the seed ------------------------------------------------------------------------------------


def _q(qid: str, n: int, qtype: Any, options: bool = True) -> Question:
    return Question(
        id=qid,
        number=n,
        printed_number=n,
        page_no=1,
        type=qtype,
        stem=f"Question {n} ____",
        options=[Option(label=x, text=f"opt {x}") for x in "ABCD"] if options else None,
        cue=None,
        points=0.5,
    )


CONTENT = Content(
    sections=[
        Section(
            id="s1",
            number=1,
            printed_title="I",
            title="Grammar",
            instructions="Choose the best answer.",
            points=1.0,
            points_source="printed",
            skill="grammar",
            groups=[
                QuestionGroup(
                    id="g1",
                    stimulus=None,
                    pictures=[],
                    questions=[_q("q1", 1, "mcq"), _q("q2", 2, "mcq")],
                )
            ],
        ),
        Section(
            id="s2",
            number=2,
            printed_title="II",
            title="Rewrite",
            instructions="Rewrite the sentence.",
            points=1.0,
            points_source="printed",
            skill="grammar",
            groups=[
                QuestionGroup(
                    id="g2",
                    stimulus=None,
                    pictures=[],
                    questions=[_q("q3", 3, "rewrite", False), _q("q4", 4, "gap_fill", False)],
                )
            ],
        ),
    ]
)


def _answer(qid: str, value: str | None, n: int = 1) -> Answer:
    return Answer(
        attempt_id=A_ID,
        question_id=qid,
        printed_number=n,
        page_no=1,
        value=value,
        value_norm=None if value is None else value.lower(),
        location="circled_option",
        confidence=0.99,
        reading_unsure=False,
        alt_value=None,
        alt_question_id=None,
        points_awarded=None,
        teacher_override=None,
    )


ANSWERS = {"q1": "A", "q2": "C", "q3": "He has lived here for years", "q4": "goes"}


def seed(conn: sqlite3.Connection, *, attempt: bool = True, student: str | None = None) -> str:
    now = datetime.now(UTC)
    test_repo.insert_test(
        conn,
        BankTest(
            id=T_ID,
            meta=Meta(occasion="UnitTest"),
            content=CONTENT,
            content_schema_version=1,
            fingerprint="fp",
            points_possible=2.0,
            source_run_id=None,
            merged_into=None,
            created_at=now,
            updated_at=now,
        ),
    )
    thread_id = threads.create_thread(conn, "t").id
    threads.set_test_id(conn, thread_id, T_ID)
    if attempt:
        attempts.insert_attempt(
            conn,
            Attempt(
                id=A_ID,
                test_id=T_ID,
                thread_id=thread_id,
                student_id=student,
                student_name_read="Hoc Sinh A",
                class_read="8A",
                source_run_id="run-extract",
                superseded_by=None,
                status="extracted",
                version=1,
                score_earned=None,
                score_possible=None,
                created_at=now - timedelta(seconds=1),
            ),
        )
        attempts.insert_answers(
            conn, [_answer(q, v, i) for i, (q, v) in enumerate(ANSWERS.items(), 1)]
        )
    return thread_id


def key_out(section: str) -> dict[str, Any]:
    if section == "s1":
        return {
            "keys": [
                {"question_id": "q1", "accepted": ["A"], "reason_vi": "r"},
                {"question_id": "q2", "accepted": ["B"], "reason_vi": "r"},
            ]
        }
    return {
        "keys": [
            {"question_id": "q3", "accepted": ["He has lived here for 5 years"], "reason_vi": "r"},
            {"question_id": "q4", "accepted": ["went"], "reason_vi": "r"},
        ]
    }


def tags_out(*qids: str) -> dict[str, Any]:
    """One section's ``tag_skills`` reply (step 22.5.4: one call per graded section)."""
    return {
        "items": [
            {
                "question_id": q,
                "tags": ["GR-PSV-A1"] if q != "q4" else ["GR-PSV-A1", "GR-PPF-A2"],
                "level": None,
            }
            for q in qids
        ]
    }


TAGS = [tags_out("q1", "q2"), tags_out("q3", "q4")]  # sections s1 and s2
SUMMARY = {
    "summary_vi": "Tóm tắt",
    "teacher_questions": [
        {"question_vi": f"Câu hỏi {i}", "what_answers_mean_vi": "ý nghĩa"} for i in range(3)
    ],
}


def explain_out(error_type: str = "gap") -> dict[str, Any]:
    return {"reasoning": "r", "text_vi": "Giải thích.", "error_type": error_type}


def verify(answer: str) -> dict[str, str]:
    return {"reasoning": "x", "answer": answer}


def full_queues() -> dict[str, list[Any]]:
    return {
        "AiKeyOut": [key_out("s1"), key_out("s2")],
        "VerifyKeyOut": [verify(" b "), verify("he has  lived here for 5 years"), verify("Went")],
        "TagSkillsCall": list(TAGS),
        "JudgeOut": [{"reason": "ok", "verdict": "correct"}] * 2,
        "ExplainOut": [explain_out(), explain_out("spelling")],
        "SummaryOut": [SUMMARY],
    }


# --- the harness ---------------------------------------------------------------------------------


@dataclass
class Harness:
    manager: RunManager
    fake: Routed
    conn: sqlite3.Connection
    thread_id: str = ""
    save_mode: str = "real"
    saves: list[dict[str, Any]] = field(default_factory=list)

    async def grade(self, attempt_id: str | None = A_ID, *, wait: bool = True) -> str:
        from etach.domain.models import GradeInput

        inp = GradeInput(test_id=T_ID, attempt_id=attempt_id, reason="button")
        run = await self.manager.submit(self.thread_id, "grade", inp)
        if wait:
            await asyncio.wait_for(self.manager.wait_idle(), TIMEOUT)
        return run.id

    def status(self, run_id: str) -> str:
        run = runs.get_run(self.conn, run_id)
        assert run is not None
        return run.status

    def steps(self, run_id: str, node: str) -> list[Any]:
        return [s for s in runs.list_steps(self.conn, run_id) if s.node == node]

    def count(self, table: str, where: str = "1") -> int:
        return int(self.conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0])

    def answer(self, qid: str) -> Answer:
        a = attempts.get_answer(self.conn, A_ID, qid)
        assert a is not None
        return a


_REAL_SAVE = grade_mod.save_grade


@contextlib.asynccontextmanager
async def make_harness(data: DataPaths, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Harness]:
    conn = db.connect(data.db)
    fake = Routed()
    client_conn = db.connect(data.db)
    client = OllamaClient(
        client_conn,
        default_config(),
        FilePromptProvider(),
        base_url="http://fake-ollama",
        transport=fake.transport,
    )
    manager = RunManager(data.db, events=EventBus(), power=FakePower())
    register_grade(manager, GradeDeps(client=client))
    await manager.start()
    h = Harness(manager, fake, conn)

    def recording(c: sqlite3.Connection, state: Any) -> dict[str, Any]:
        out = _REAL_SAVE(c, state)
        h.saves.append(out)
        if h.save_mode == "crash_after":
            h.save_mode = "real"
            raise StreamDropped("save (crash injected after the commit)", [])
        return out

    monkeypatch.setattr(grade_mod, "save_grade", recording)
    try:
        yield h
    finally:
        await manager.aclose()
        client_conn.close()
        conn.close()


@pytest.fixture
def data(tmp_path: Path) -> DataPaths:
    paths = DataPaths(tmp_path / "data")
    db.open_database(paths.db).close()
    return paths


@pytest_asyncio.fixture
async def h(data: DataPaths, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Harness]:
    async with make_harness(data, monkeypatch) as harness:
        yield harness


# --- the full path -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_grade_path(h: Harness) -> None:
    h.thread_id = seed(h.conn)
    h.fake.queues = full_queues()
    run_id = await h.grade()
    assert h.status(run_id) == "done"
    # keys: made by ai_key_fast; q2 (student C ≠ key B) and q4 (goes ≠ went) verified, and
    # the verify answers " b " / "Went" agree through value_norm
    ks = {k.question_id: k for k in keys.list_keys(h.conn, T_ID)}
    assert {q: k.status for q, k in ks.items()} == {
        "q1": "ai_unverified",
        "q2": "ai_verified",
        "q3": "ai_verified",
        "q4": "ai_verified",
    }
    assert all(k.source == "ai" for k in ks.values())
    assert h.fake.calls("AiKeyOut") == 2 and h.fake.calls("VerifyKeyOut") == 3
    # verdicts: q1 correct, q2 incorrect, q3 judged correct, q4 incorrect (near miss? no: d>2)
    verdicts = {q: h.answer(q).verdict for q in ANSWERS}
    assert verdicts == {"q1": "correct", "q2": "incorrect", "q3": "correct", "q4": "incorrect"}
    att = attempts.get_attempt(h.conn, A_ID)
    assert att is not None and att.status == "graded"
    assert (att.score_earned, att.score_possible) == (1.0, 2.0)
    report = attempts.get_grade_report(h.conn, A_ID)
    assert report is not None and report.run_id == run_id
    assert len(report.teacher_questions) == 3 and report.summary_vi == "Tóm tắt"
    # q2 wrong (gap) and q4 wrong (spelling → careless, kept out of the ranking)
    assert [w.skill_tag for w in report.weak_points] == ["GR-PSV-A1"]
    assert len(report.careless_notes) == 1 and "chính tả" in report.careless_notes[0]
    assert all(w.note_vi == "" for w in report.weak_points)
    # R22.5.5.5: one paper only → "this paper only"; the summary gets the name, not the code
    (wpt,) = report.weak_points
    assert (wpt.label, wpt.level, wpt.held_back) == ("this_paper_only", "A1", False)
    (summary,) = [r for r in h.fake.requests if "Weak points (ranked)" in str(r["messages"])]
    sent = str(summary["messages"])
    assert "Present Simple" in sent and "GR-PSV-A1" not in sent and "GR-PPF-A2" not in sent
    assert h.count("question_tags") == 5
    test = test_repo.get_test(h.conn, T_ID)
    assert test is not None
    assert h.count("explanations") == 2
    assert h.count("messages", "kind = 'grade_card'") == 1


@pytest.mark.asyncio
async def test_r22_5_5_12_first_grade_report_uses_tag_skills_levels(h: Harness) -> None:
    """The verifier's blocker: on a first grade the report's levels are the ones tag_skills
    just returned (not the base levels), equal to the stored ones the Students view reads."""
    h.thread_id = seed(h.conn)
    q = full_queues()
    q["TagSkillsCall"] = [{"items": [{**item, "level": "B2"} for item in t["items"]]} for t in TAGS]
    h.fake.queues = q
    run_id = await h.grade()
    assert h.status(run_id) == "done"
    stored = test_repo.list_tag_levels(h.conn, T_ID)
    assert stored and all(lv == "B2" for tags in stored.values() for lv in tags.values())
    report = attempts.get_grade_report(h.conn, A_ID)
    assert report is not None
    assert [(w.skill_tag, w.level) for w in report.weak_points] == [("GR-PSV-A1", "B2")]


@pytest.mark.asyncio
async def test_r22_5_5_12_summary_request_names_no_held_back_skill(h: Harness) -> None:
    """q4 (Present Simple + Present Perfect at B2) wrong as a gap: Present Perfect is held back
    behind Present Simple (A1), so neither block of the summary request names it."""
    h.thread_id = seed(h.conn)
    q = full_queues()
    q["TagSkillsCall"] = [
        tags_out("q1", "q2"),
        {"items": [{**i, "level": "B2" if i["question_id"] == "q4" else None}
                   for i in tags_out("q3", "q4")["items"]]},
    ]  # fmt: skip
    q["ExplainOut"] = [explain_out(), explain_out()]
    h.fake.queues = q
    run_id = await h.grade()
    assert h.status(run_id) == "done"
    report = attempts.get_grade_report(h.conn, A_ID)
    assert report is not None
    assert [(w.skill_tag, w.held_back) for w in report.weak_points] == [
        ("GR-PSV-A1", False),
        ("GR-PPF-A2", True),
    ]
    (summary,) = [r for r in h.fake.requests if "Weak points (ranked)" in str(r["messages"])]
    sent = str(summary["messages"])
    assert skill_name("GR-PSV-A1") in sent
    assert skill_name("GR-PPF-A2") not in sent and "GR-PPF-A2" not in sent


@pytest.mark.asyncio
async def test_verify_disagree_and_three_verifies(h: Harness) -> None:
    h.thread_id = seed(h.conn)
    q = full_queues()
    q["VerifyKeyOut"] = [{"reasoning": "x", "answer": "D"}]  # q2 disagrees; q3, q4 fail twice
    q["JudgeOut"] = []
    q["ExplainOut"] = [explain_out()]
    h.fake.queues = q
    run_id = await h.grade()
    assert h.status(run_id) == "done"
    ks = {k.question_id: k.status for k in keys.list_keys(h.conn, T_ID)}
    assert ks["q2"] == "ai_uncertain" and ks["q4"] == "ai_uncertain"
    items = h.conn.execute(
        "SELECT question_id FROM review_items WHERE kind = 'uncertain_key' ORDER BY question_id"
    ).fetchall()
    assert [r[0] for r in items] == ["q2", "q3", "q4"]


@pytest.mark.asyncio
async def test_judge_failing_twice_is_uncertain(h: Harness) -> None:
    h.thread_id = seed(h.conn)
    q = full_queues()
    q["JudgeOut"] = []  # both tries invalid → CallFailure → judged "failed"
    h.fake.queues = q
    run_id = await h.grade()
    assert h.status(run_id) == "done"
    a3 = h.answer("q3")
    assert a3.verdict == "uncertain" and a3.points_awarded is None
    report = attempts.get_grade_report(h.conn, A_ID)
    assert report is not None and report.uncertain_points == 0.5


@pytest.mark.asyncio
async def test_blank_override_is_blank_and_not_explained(h: Harness) -> None:
    h.thread_id = seed(h.conn)
    a2 = h.answer("q2").model_copy(update={"teacher_override": "", "value_norm": "c"})
    attempts.update_answer(h.conn, a2)
    q = full_queues()
    q["VerifyKeyOut"] = [verify("He has lived here for 5 years"), verify("went")]  # q3, q4
    q["ExplainOut"] = [explain_out("spelling")]
    h.fake.queues = q
    run_id = await h.grade()
    assert h.status(run_id) == "done"
    stored = h.answer("q2")
    assert stored.value_norm == "" and stored.verdict == "incorrect"
    assert stored.teacher_override == ""  # never touched
    # one explain call (q4), none for the blank q2
    assert h.fake.calls("ExplainOut") == 1
    assert h.count("explanations", "question_id = 'q2'") == 0


@pytest.mark.asyncio
async def test_r18_9_crash_between_commit_and_checkpoint(h: Harness) -> None:
    h.thread_id = seed(h.conn)
    q = full_queues()
    q["VerifyKeyOut"] = []
    h.fake.queues = q
    h.save_mode = "crash_after"
    run_id = await h.grade()
    assert h.status(run_id) == "interrupted"
    before = (
        h.count("grade_reports"),
        h.count("review_items"),
        h.count("explanations"),
        h.count("messages"),
    )
    await h.manager.resume(run_id)
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    assert h.status(run_id) == "done"
    assert len(h.steps(run_id, "save")) == 2
    # the crash leaves the run ``interrupted``, so the retried save writes again: idempotently
    after = (
        h.count("grade_reports"),
        h.count("review_items"),
        h.count("explanations"),
        h.count("messages"),
    )
    assert after == before and before[0] == 1 and before[1] >= 1


@pytest.mark.asyncio
async def test_r18_7_override_while_stopped(h: Harness) -> None:
    h.thread_id = seed(h.conn)
    q = full_queues()
    q["VerifyKeyOut"] = [verify("b"), verify("He has lived here for 5 years"), verify("went")]
    slow = ChatScript(tokens=list(json.dumps(explain_out())), delay=0.05)
    q["ExplainOut"] = [slow, explain_out(), explain_out()]
    h.fake.queues = q
    run_id = await h.grade(wait=False)
    for _ in range(400):
        if h.steps(run_id, "explain"):
            break
        await asyncio.sleep(0.02)
    stopped = await h.manager.stop(run_id)
    assert stopped.status == "stopped"
    # the teacher corrects q2's reading while the run is stopped (PUT /attempts/…/answers)
    a2 = h.answer("q2").model_copy(update={"teacher_override": "B", "value_norm": "b"})
    attempts.update_answer(h.conn, a2)
    attempts.bump_version(h.conn, A_ID)
    await h.manager.resume(run_id)
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    assert h.status(run_id) == "done"
    assert h.answer("q2").verdict == "correct"  # the override counts
    assert len(h.steps(run_id, "grade")) == 2  # the version mismatch re-ran grade
    assert [s["status"] for s in h.saves] == ["version_mismatch", "saved"]
    assert h.count("grade_reports") == 1


@pytest.mark.asyncio
async def test_r18_10_queued_grade_runs_reach_done(h: Harness) -> None:
    h.thread_id = seed(h.conn)
    h.fake.queues = full_queues()
    first = await h.grade()
    assert h.status(first) == "done"
    # a Review follow-up (data-model §5.3) only writes a queued row; the manager now runs it
    with db.transaction(h.conn):
        queued = runs.enqueue_grade(h.conn, test_id=T_ID, attempt_id=A_ID, reason="review_fix")
    h.fake.queues = {"SummaryOut": [SUMMARY], "JudgeOut": [{"reason": "ok", "verdict": "correct"}]}
    await h.manager.poke()
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    assert h.status(queued) == "done"
    # a re-grade: once-per-test nodes skipped, explanations cached
    assert h.fake.calls("AiKeyOut") == 2 and h.fake.calls("TagSkillsCall") == 2
    assert h.fake.calls("ExplainOut") == 2
    assert h.count("grade_reports") == 1


@pytest.mark.asyncio
async def test_r22_5_4_6_tag_skills_one_call_per_graded_section(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R22.5.4.6: one ``tag_skills`` call per graded section, each with only that section's
    heading, instructions, passage and questions; at most 3 tags per question; once per test."""
    sections = list(CONTENT.sections)
    group = sections[0].groups[0].model_copy(update={"stimulus": "Tom lives in Hanoi."})
    sections[0] = sections[0].model_copy(update={"groups": [group]})
    monkeypatch.setitem(globals(), "CONTENT", Content(sections=sections))
    h.thread_id = seed(h.conn)
    q = full_queues()
    q["TagSkillsCall"] = [
        {
            "items": [
                {
                    "question_id": "q1",
                    "tags": ["GR-PSV-A1", "GR-PPF-A2", "VOC-TOPIC"],
                    "level": None,
                }
            ]
        },
        tags_out("q3", "q4"),
    ]
    h.fake.queues = q
    assert h.status(await h.grade()) == "done"
    tag_requests = [
        r for r in h.fake.requests if (r.get("format") or {}).get("title") == "TagSkillsCall"
    ]
    assert len(tag_requests) == 2  # sections s1 and s2, both graded
    users = [next(m["content"] for m in r["messages"] if m["role"] == "user") for r in tag_requests]
    s1, s2 = users
    assert "I. Choose the best answer." in s1 and "Tom lives in Hanoi." in s1
    assert "q1 (no. 1" in s1 and "q2 (no. 2" in s1
    assert "Rewrite the sentence." not in s1 and "q3" not in s1 and "q4" not in s1
    assert "II. Rewrite the sentence." in s2 and "q3 (no. 3" in s2 and "q4 (no. 4" in s2
    assert "Choose the best answer." not in s2 and "Tom lives" not in s2 and "q1" not in s2
    assert all(u.startswith("One section of this test") for u in users)
    per_q = dict(
        h.conn.execute("SELECT question_id, COUNT(*) FROM question_tags GROUP BY question_id")
    )
    assert per_q == {"q1": 3, "q3": 1, "q4": 2}  # q2 left out by the model: no tag
    assert max(per_q.values()) <= 3
    # once per test: a re-grade makes no tag_skills call
    with db.transaction(h.conn):
        queued = runs.enqueue_grade(h.conn, test_id=T_ID, attempt_id=A_ID, reason="review_fix")
    h.fake.queues = {"SummaryOut": [SUMMARY], "JudgeOut": [{"reason": "ok", "verdict": "correct"}]}
    await h.manager.poke()
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    assert h.status(queued) == "done"
    assert h.fake.calls("TagSkillsCall") == 2


@pytest.mark.asyncio
async def test_blank_test_writes_keys_tags_notes_only(h: Harness) -> None:
    h.thread_id = seed(h.conn, attempt=False)
    q = full_queues()
    q["VerifyKeyOut"] = []
    h.fake.queues = q
    run_id = await h.grade(None)
    assert h.status(run_id) == "done"
    assert len(keys.list_keys(h.conn, T_ID)) == 4
    assert h.count("question_tags") == 5 and h.count("grade_reports") == 0
    assert h.fake.calls("ExplainOut") == 0 and h.fake.calls("SummaryOut") == 0
    assert not h.steps(run_id, "grade")


@pytest.mark.asyncio
async def test_teacher_key_is_never_downgraded(h: Harness) -> None:
    h.thread_id = seed(h.conn)
    now = datetime.now(UTC)
    for qid, acc in (("q1", "A"), ("q2", "C"), ("q3", "He has lived here for years")):
        keys.upsert_key(
            h.conn,
            AnswerKey(
                test_id=T_ID,
                question_id=qid,
                accepted=[acc],
                reason_vi=None,
                source="teacher_edit",
                status="teacher_verified",
                confidence=None,
                updated_at=now,
            ),
        )
    q = full_queues()
    q["AiKeyOut"] = [key_out("s2")]
    q["VerifyKeyOut"] = [verify("went")]
    h.fake.queues = q
    run_id = await h.grade()
    assert h.status(run_id) == "done"
    assert h.fake.calls("AiKeyOut") == 1  # only s2 has a question without a key
    ks = {k.question_id: k for k in keys.list_keys(h.conn, T_ID)}
    assert ks["q2"].status == "teacher_verified" and ks["q2"].accepted == ["C"]
    assert h.answer("q2").verdict == "correct"
