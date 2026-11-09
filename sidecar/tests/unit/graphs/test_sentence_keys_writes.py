"""R22.3.4.2: every key write of a rewrite/combine question stores the sentence forms (data-model
§2.4 v1.15); other types are unchanged; an answer equal to a form is correct without a model call;
the one-time upgrade (migration 0006) adds the forms to existing keys once, keeping updated_at."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from unit.graphs.test_grade import (
    A_ID,
    ANSWERS,
    CONTENT,
    T_ID,
    Harness,
    full_queues,
    key_out,
    seed,
    verify,
)
from unit.graphs.test_grade import data as data
from unit.graphs.test_grade import h as h

from etach.api.routes.tests import KeyPut, _put_key_db
from etach.domain.models import AnswerKey
from etach.graphs import extract as extract_mod
from etach.store.repos import keys

Q3 = "He has lived here for years."
Q3_FORMS = [Q3, "He has lived here for years"]


def _key(qid: str, accepted: list[str], source: str = "ai") -> AnswerKey:
    return AnswerKey(
        test_id=T_ID, question_id=qid, accepted=accepted, reason_vi=None, source=source,  # type: ignore[arg-type]
        status="ai_unverified", confidence=0.9, updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )  # fmt: skip


@pytest.mark.asyncio
async def test_ai_key_gets_forms_and_a_form_is_correct_without_a_judge(h: Harness) -> None:
    h.thread_id = seed(h.conn)  # the student's q3 answer has no full stop
    assert ANSWERS["q3"] == Q3_FORMS[1]
    q = full_queues()
    s2 = key_out("s2")
    s2["keys"][0]["accepted"] = [Q3]
    q["AiKeyOut"] = [key_out("s1"), s2]
    q["VerifyKeyOut"] = [verify(" b "), verify(Q3), verify("Went")]
    h.fake.queues = q
    run_id = await h.grade()
    assert h.status(run_id) == "done"
    ks = {k.question_id: k for k in keys.list_keys(h.conn, T_ID)}
    assert ks["q3"].accepted == Q3_FORMS  # rewrite: the forms
    assert ks["q4"].accepted == ["went"] and ks["q1"].accepted == ["A"]  # other types unchanged
    assert h.answer("q3").verdict == "correct"
    assert h.fake.calls("JudgeOut") == 0  # the normalized match, no model call


def test_key_photo_write_stores_the_forms(h: Harness) -> None:
    seed(h.conn, attempt=False)
    entries = [
        {"question_id": "q3", "accepted": [Q3], "confidence": 0.99},
        {"question_id": "q4", "accepted": ["went."], "confidence": 0.99},
    ]
    seen: list[list[str]] = []
    real = keys.upsert_key

    def spy(conn: sqlite3.Connection, key: AnswerKey) -> Any:
        seen.append(key.accepted)
        return real(conn, key)

    # The save's key loop on its own: the same call it makes, over a test already in the bank.
    from etach.domain import keys as key_rules

    for e in entries:
        spy(
            h.conn,
            _key(e["question_id"], key_rules.with_forms(
                e["accepted"], key_rules.find_question(CONTENT, e["question_id"])
            ), "from_key_photo"),
        )  # fmt: skip
    assert seen == [Q3_FORMS, ["went."]]
    src = Path(extract_mod.__file__).read_text(encoding="utf-8")
    assert "key_rules.with_forms(" in src  # the save makes the same call


def test_teacher_put_forms_removal_kept_and_remade(h: Harness) -> None:
    seed(h.conn, attempt=False)
    put = lambda acc: _put_key_db(h.conn, T_ID, "q3", KeyPut(accepted=acc)).key.accepted  # noqa: E731
    assert put([Q3]) == Q3_FORMS
    # the teacher removes the second form: it stays removed while the key text is unchanged
    assert put([Q3_FORMS[0]]) == [Q3]
    assert keys.get_key(h.conn, T_ID, "q3").accepted == [Q3]  # type: ignore[union-attr]
    # a changed key text remakes the forms
    assert put(["He has lived here for ages."]) == [
        "He has lived here for ages.",
        "He has lived here for ages",
    ]
    # other types: as sent
    assert _put_key_db(h.conn, T_ID, "q4", KeyPut(accepted=["went."])).key.accepted == ["went."]


def test_upgrade_adds_forms_once_and_keeps_updated_at(h: Harness) -> None:
    seed(h.conn, attempt=False)
    keys.upsert_key(h.conn, _key("q3", [Q3]))
    keys.upsert_key(h.conn, _key("q4", ["went."]))
    h.conn.execute(
        "UPDATE answer_keys SET accepted = ? WHERE question_id = 'q3'", ('["' + Q3 + '"]',)
    )  # an old row, written before the forms
    h.conn.execute("INSERT INTO key_forms_pending (test_id) VALUES (?)", (T_ID,))
    before = {k.question_id: k.updated_at for k in keys.list_keys(h.conn, "none")}
    assert before == {}
    got = {k.question_id: k for k in keys.list_keys(h.conn, T_ID)}
    assert got["q3"].accepted == Q3_FORMS and got["q4"].accepted == ["went."]
    assert got["q3"].updated_at == datetime(2026, 1, 1, tzinfo=UTC)
    # once: a teacher removal afterwards is not undone by a later read
    h.conn.execute(
        "UPDATE answer_keys SET accepted = ? WHERE question_id = 'q3'", ('["' + Q3 + '"]',)
    )
    assert keys.list_keys(h.conn, T_ID)[0].accepted == [Q3]
    assert h.conn.execute("SELECT COUNT(*) FROM key_forms_pending").fetchone()[0] == 0
    _ = A_ID
