"""Step 22.6.6, R22.6.6.3 (step22.6-plan D15): a test-text save during an attempt's FIRST grade
run (queued, running, stopped and resumed) ends with that attempt graded against the saved
test. The grade ``save`` finds the test content changed since ``load_context``, writes nothing
and loads it again; the work done for unchanged questions (keys, tags, explanations) is reused.
Synthetic data only."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from support.fake_ollama import ChatScript
from unit.graphs.test_grade import (
    A_ID,
    SUMMARY,
    T_ID,
    TIMEOUT,
    Harness,
    explain_out,
    full_queues,
    key_out,
    seed,
    verify,
)
from unit.graphs.test_grade import data as data
from unit.graphs.test_grade import h as h

from etach.domain.review import save_test_text
from etach.domain.test_text import render
from etach.store.repos import attempts, explanations, keys, review
from etach.store.repos import tests as test_repo


def _queues(slow_explain: bool) -> dict[str, list[Any]]:
    q = full_queues()
    first: Any = explain_out()
    if slow_explain:
        first = ChatScript(tokens=list(json.dumps(explain_out())), delay=0.05)
    q["ExplainOut"] = [first, explain_out(), explain_out(), explain_out()]
    q["SummaryOut"] = [SUMMARY, SUMMARY]
    return q


def _total(h: Harness) -> tuple[float, set[str]]:
    test = test_repo.get_test(h.conn, T_ID)
    assert test is not None
    qs = [q for s in test.content.sections for g in s.groups for q in g.questions]
    return sum(q.points for q in qs), {q.id for q in qs}


def _text(h: Harness) -> str:
    test = test_repo.get_test(h.conn, T_ID)
    assert test is not None
    return render(test.content)


def _delete_q4(h: Harness) -> None:
    text = _text(h)
    edited = text.replace("\n\n4. Question 4 ____", "")
    assert edited != text
    saved = save_test_text(h.conn, T_ID, edited, drop_confirmed=["q4"])
    assert saved.dropped_question_ids == ["q4"]
    assert saved.followup_run_ids == []  # not graded yet: the run itself picks the change up


async def _until_explain(h: Harness, run_id: str) -> None:
    for _ in range(400):
        if h.steps(run_id, "explain"):
            return
        await asyncio.sleep(0.02)
    raise AssertionError("the run did not reach explain")


def _assert_graded_against_saved(h: Harness, run_id: str) -> None:
    assert h.status(run_id) == "done"
    total, qids = _total(h)
    att = attempts.get_attempt(h.conn, A_ID)
    assert att is not None and att.status == "graded"
    assert att.score_possible == pytest.approx(total)
    assert {a.question_id for a in attempts.list_answers(h.conn, A_ID)} <= qids
    assert all(a.verdict is not None for a in attempts.list_answers(h.conn, A_ID))


@pytest.mark.asyncio
async def test_r22_6_6_3_running_first_grade_deleted_question(h: Harness) -> None:
    """Running (not stopped): the save finds the test changed and grades against the saved
    test; q4's key, explanation and Review items are not written."""
    h.thread_id = seed(h.conn)
    h.fake.queues = _queues(slow_explain=True)
    run_id = await h.grade(wait=False)
    await _until_explain(h, run_id)
    _delete_q4(h)
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    _assert_graded_against_saved(h, run_id)
    assert any(s["status"] == "test_changed" for s in h.saves)
    assert len(h.steps(run_id, "load_context")) == 2
    assert keys.get_key(h.conn, T_ID, "q4") is None
    assert not [e for e in explanations.list_explanations(h.conn, T_ID) if e.question_id == "q4"]
    assert not [i for i in review.list_open_for_test(h.conn, T_ID) if i.question_id == "q4"]
    assert keys.get_key(h.conn, T_ID, "q1") is not None  # the unchanged questions' keys saved
    # reused: no key, check or tag call again for the unchanged questions
    assert h.fake.calls("AiKeyOut") == 2
    assert h.fake.calls("VerifyKeyOut") == 3
    assert h.fake.calls("TagSkillsCall") == 2


@pytest.mark.asyncio
async def test_r22_6_6_3_stopped_first_grade_points_change(h: Harness) -> None:
    """Stopped, then resumed: a text save that changes only the points (the seed's 0.5 each
    becomes the equal 2.5 each; no question deleted) gives the new points possible."""
    h.thread_id = seed(h.conn)
    h.fake.queues = _queues(slow_explain=True)
    run_id = await h.grade(wait=False)
    await _until_explain(h, run_id)
    stopped = await h.manager.stop(run_id)
    assert stopped.status == "stopped"
    before, _ = _total(h)
    saved = save_test_text(h.conn, T_ID, _text(h))
    assert saved.followup_run_ids == []
    after, qids = _total(h)
    assert after != before and qids == {"q1", "q2", "q3", "q4"}
    await h.manager.resume(run_id)
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    _assert_graded_against_saved(h, run_id)
    att = attempts.get_attempt(h.conn, A_ID)
    assert att is not None and att.score_possible == pytest.approx(after)
    # the explanations made before the reload are reused (two before it, none after)
    assert h.fake.calls("ExplainOut") <= 4
    assert h.fake.calls("AiKeyOut") == 2


@pytest.mark.asyncio
async def test_r22_6_6_3_queued_first_grade(h: Harness) -> None:
    """Queued behind another run: it loads the saved test when it starts."""
    h.thread_id = seed(h.conn)
    q = _queues(slow_explain=False)
    # the run ahead: the test's key run (no attempt), slow in its first key call
    slow_key = ChatScript(tokens=list(json.dumps(key_out("s1"))), delay=0.05)
    q["AiKeyOut"] = [slow_key, key_out("s2")]
    q["VerifyKeyOut"] = [verify("b"), verify("He has lived here for 5 years"), verify("went")]
    h.fake.queues = q
    ahead = await h.grade(attempt_id=None, wait=False)
    run_id = await h.grade(wait=False)
    for _ in range(400):
        if h.steps(ahead, "ai_key_fast"):
            break
        await asyncio.sleep(0.02)
    assert h.status(run_id) == "queued"
    _delete_q4(h)
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    _assert_graded_against_saved(h, run_id)
    assert keys.get_key(h.conn, T_ID, "q4") is None  # the key run saw the change too
