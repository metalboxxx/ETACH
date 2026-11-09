"""Refinements R3.4 (D7): after a key is deleted, the grade graph's key step writes a new AI key
for that question and leaves the other keys alone."""

from __future__ import annotations

import pytest
from unit.graphs.test_grade import T_ID, Harness, full_queues, seed
from unit.graphs.test_grade import data as data
from unit.graphs.test_grade import h as h

from etach.api.routes.tests import KeyPut, _delete_key_db, _put_key_db
from etach.store.repos import keys


@pytest.mark.asyncio
@pytest.mark.parametrize("teacher", [False, True], ids=["ai_key", "teacher_key"])
async def test_r3_4_the_next_grade_writes_a_new_ai_key(h: Harness, teacher: bool) -> None:
    h.thread_id = seed(h.conn)
    h.fake.queues = full_queues()
    first = await h.grade()
    assert h.status(first) == "done"
    if teacher:
        _put_key_db(h.conn, T_ID, "q1", KeyPut(accepted=["B"]))
    others = {k.question_id: k for k in keys.list_keys(h.conn, T_ID) if k.question_id != "q1"}

    _delete_key_db(h.conn, T_ID, "q1")
    assert keys.get_key(h.conn, T_ID, "q1") is None

    calls = h.fake.calls("AiKeyOut")
    q = full_queues()
    q["AiKeyOut"] = [{"keys": [{"question_id": "q1", "accepted": ["C"], "reason_vi": "r"}]}]
    q["VerifyKeyOut"] = [{"reasoning": "x", "answer": "C"}]
    h.fake.queues = q
    second = await h.grade()

    assert h.status(second) == "done"
    assert h.fake.calls("AiKeyOut") == calls + 1  # one section, for that question only
    new = keys.get_key(h.conn, T_ID, "q1")
    assert new is not None and new.accepted == ["C"] and new.source == "ai"
    assert new.status != "teacher_verified"
    after = {k.question_id: k for k in keys.list_keys(h.conn, T_ID) if k.question_id != "q1"}
    assert after == others
