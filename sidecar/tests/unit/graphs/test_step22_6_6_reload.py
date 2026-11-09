"""Step 22.6.6 (re-check holes 1-3 of R22.6.6.3): what a grade run's reload after a test-text
save keeps. A stale ``uncertain_key`` item of a changed question is not written (the reloaded
pass's own items are), a teacher key written while the run was stopped wins over the run's
unsaved AI key, and a changed question gets its skill tags. Synthetic data only."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from unit.graphs.test_grade import (
    A_ID,
    SUMMARY,
    T_ID,
    TAGS,
    TIMEOUT,
    Harness,
    explain_out,
    key_out,
    seed,
    tags_out,
    verify,
)
from unit.graphs.test_grade import data as data
from unit.graphs.test_grade import h as h
from unit.graphs.test_step22_6_6 import _text, _until_explain

from etach.domain.models import AnswerKey
from etach.domain.review import save_test_text
from etach.graphs.grade import RESET_PENDINGS, _merge_pendings
from etach.store.repos import attempts, keys, review
from etach.store.repos import tests as test_repo


def _queues() -> dict[str, list[Any]]:
    return {
        # s1, s2, then s1 again after the reload (only q2 is needed: its text changed)
        "AiKeyOut": [key_out("s1"), key_out("s2"), key_out("s1")],
        # q2 and q3 disagree, q4 agrees; after the reload the new q2 key agrees
        "VerifyKeyOut": [verify("C"), verify("He lived here"), verify("Went"), verify("B")],
        "TagSkillsCall": [*TAGS, tags_out("q2")],
        "JudgeOut": [{"reason": "ok", "verdict": "correct"}] * 4,
        "ExplainOut": [explain_out()] * 6,
        "SummaryOut": [SUMMARY, SUMMARY],
    }


def test_reset_pendings_reducer() -> None:
    old = [{"dedupe_key": "a"}, {"dedupe_key": "b"}]
    assert _merge_pendings(old, [{"dedupe_key": "c"}]) == [*old, {"dedupe_key": "c"}]
    assert _merge_pendings(old, [RESET_PENDINGS, {"dedupe_key": "b", "x": 1}]) == [
        {"dedupe_key": "b", "x": 1}
    ]
    assert _merge_pendings(old, [RESET_PENDINGS]) == []


@pytest.mark.asyncio
async def test_reload_drops_stale_items_keeps_teacher_key_and_tags_changed_question(
    h: Harness,
) -> None:
    h.thread_id = seed(h.conn)
    h.fake.queues = _queues()
    run_id = await h.grade(wait=False)
    await _until_explain(h, run_id)
    stopped = await h.manager.stop(run_id)
    assert stopped.status == "stopped"
    # while stopped: the teacher edits q2's stem and sets q1's key (q1's text is unchanged)
    text = _text(h)
    edited = text.replace("Question 2 ____", "Question two ____")
    assert edited != text
    save_test_text(h.conn, T_ID, edited)
    keys.upsert_key(
        h.conn,
        AnswerKey(
            test_id=T_ID,
            question_id="q1",
            accepted=["B"],
            reason_vi=None,
            source="teacher_edit",
            status="teacher_verified",
            confidence=None,
            updated_at=datetime.now(UTC),
        ),
    )
    await h.manager.resume(run_id)
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    assert h.status(run_id) == "done"
    assert any(s["status"] == "test_changed" for s in h.saves)

    # hole 1: no stale uncertain_key for q2 (its new key is verified); q3's own item is kept
    items = [i for i in review.list_open_for_test(h.conn, T_ID) if i.kind == "uncertain_key"]
    assert {i.question_id for i in items} == {"q3"}
    q2 = keys.get_key(h.conn, T_ID, "q2")
    assert q2 is not None and q2.status == "ai_verified"

    # hole 2: the teacher's q1 key is the one graded with (the student wrote A)
    q1 = keys.get_key(h.conn, T_ID, "q1")
    assert q1 is not None and q1.accepted == ["B"] and q1.status == "teacher_verified"
    verdicts = {a.question_id: a.verdict for a in attempts.list_answers(h.conn, A_ID)}
    assert verdicts["q1"] == "incorrect"

    # hole 3: the changed q2 is tagged again (one more call, for s1's q2 only)
    tags = test_repo.list_question_tags(h.conn, T_ID)
    assert set(tags) == {"q1", "q2", "q3", "q4"}
    assert h.fake.calls("TagSkillsCall") == 3
