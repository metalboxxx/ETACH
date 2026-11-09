"""Step 22.6.6: step22.6-plan §4's open note (the round verifier, R22.6.6.1).

A test-text save that changes points or deletes questions queues a re-grade only for attempts
already graded (``domain/review.py``, ``followup_run_ids``). This test saves the test text while
an attempt's FIRST grade run is going (stopped inside ``explain``) and checks whether the
attempt ends up graded against the new test, or a re-grade is queued.

Deleting question 4 removes its answer row and bumps the attempt's version. Before R22.6.6.3
``save`` saw only the version mismatch and re-ran ``grade``, which reloads the answers but not
the test content, so the score was made from the old questions and points (this test was
``xfail``). Since R22.6.6.3 ``save`` finds the test content changed and the run loads it again.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from support.fake_ollama import ChatScript
from unit.graphs.test_grade import (
    A_ID,
    T_ID,
    TIMEOUT,
    Harness,
    explain_out,
    full_queues,
    seed,
    verify,
)
from unit.graphs.test_grade import data as data
from unit.graphs.test_grade import h as h

from etach.domain.review import save_test_text
from etach.domain.test_text import render
from etach.store.repos import attempts, runs
from etach.store.repos import tests as test_repo


def _grade_runs_for(h: Harness) -> list[str]:
    rows = h.conn.execute(
        "SELECT id FROM runs WHERE kind = 'grade' AND json_extract(input, '$.attempt_id') = ?",
        (A_ID,),
    ).fetchall()
    return [r[0] for r in rows]


@pytest.mark.asyncio
async def test_text_save_during_first_grade_run(h: Harness) -> None:
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
    assert h.steps(run_id, "explain"), "the run did not reach explain"
    stopped = await h.manager.stop(run_id)
    assert stopped.status == "stopped"
    att = attempts.get_attempt(h.conn, A_ID)
    assert att is not None and att.score_earned is None  # the first grade, not saved yet

    # the teacher deletes question 4 in the test text (its answer goes; the points change)
    test = test_repo.get_test(h.conn, T_ID)
    assert test is not None
    text = render(test.content)
    edited = text.replace("\n\n4. Question 4 ____", "")
    assert edited != text
    saved = save_test_text(h.conn, T_ID, edited, drop_confirmed=["q4"])
    assert saved.dropped_question_ids == ["q4"]
    assert saved.followup_run_ids == []  # the attempt was not graded yet: nothing queued
    new = test_repo.get_test(h.conn, T_ID)
    assert new is not None
    new_qids = {q.id for s in new.content.sections for g in s.groups for q in g.questions}
    new_total = sum(q.points for s in new.content.sections for g in s.groups for q in g.questions)
    assert "q4" not in new_qids

    await h.manager.resume(run_id)
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    assert h.status(run_id) == "done"
    assert all(runs.get_run(h.conn, r).status == "done" for r in _grade_runs_for(h))  # type: ignore[union-attr]
    att = attempts.get_attempt(h.conn, A_ID)
    assert att is not None and att.score_possible is not None
    # what should hold: the attempt is scored against the saved test (or re-graded after it)
    assert att.score_possible == pytest.approx(new_total)
