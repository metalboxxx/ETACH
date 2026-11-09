"""Step 22.5.4a: what the grading calls send (R22.5.4.2, R22.5.4.3), through the grade graph with
the FakeOllama of ``test_grade.py`` (answers by the output schema title) and the real prompts.

The test: section s1 (two choice questions), section s2 (q3 a ``sentence`` question whose answer
line starts with "My brother", q4 a ``word`` question). The student writes only the rest of
q3's sentence."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from unit.graphs import test_grade as tg

from etach.appdir import DataPaths
from etach.domain.models import Question
from etach.store import db

START = "My brother"


def _content() -> Any:
    content = tg.CONTENT.model_copy(deep=True)
    q3 = content.sections[1].groups[0].questions[0]
    content.sections[1].groups[0].questions[0] = Question.model_validate(
        {
            **q3.model_dump(),
            "answer_form": "sentence",
            "stem": "My brother is taller than me. (short)",
            "answer_start": START,
        }
    )
    return content


@pytest.fixture
def data(tmp_path: Path) -> DataPaths:
    paths = DataPaths(tmp_path / "data")
    db.open_database(paths.db).close()
    return paths


@pytest_asyncio.fixture
async def h(data: DataPaths, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[tg.Harness]:
    monkeypatch.setattr(tg, "CONTENT", _content())
    monkeypatch.setitem(tg.ANSWERS, "q3", "is more tall than me")
    async with tg.make_harness(data, monkeypatch) as harness:
        yield harness


def _user_messages(h: tg.Harness, title: str) -> list[str]:
    out = []
    for req in h.fake.requests:
        fmt = req.get("format")
        if isinstance(fmt, dict) and fmt.get("title") == title:
            out.append(next(m["content"] for m in req["messages"] if m["role"] == "user"))
    return out


def _queues() -> dict[str, list[Any]]:
    q = tg.full_queues()
    q["AiKeyOut"] = [
        tg.key_out("s1"),
        {
            "keys": [
                {
                    "question_id": "q3",
                    "accepted": ["My brother is taller than I am"],
                    "reason_vi": "r",
                },
                {"question_id": "q4", "accepted": ["went"], "reason_vi": "r"},
            ]
        },
    ]
    q["VerifyKeyOut"] = [
        tg.verify(" b "),
        tg.verify("My brother is taller than I am"),
        tg.verify("Went"),
    ]
    q["JudgeOut"] = [{"reason": "more tall is wrong", "verdict": "incorrect"}]
    return q


@pytest.mark.asyncio
async def test_r22_5_4_2_sentence_calls_carry_the_opening_words(h: tg.Harness) -> None:
    h.thread_id = tg.seed(h.conn)
    h.fake.queues = _queues()
    run_id = await h.grade()
    assert h.status(run_id) == "done"
    line = f"Answer line starts with: {START}"
    for title in ("AiKeyOut", "VerifyKeyOut", "JudgeOut", "ExplainOut"):
        q3 = [m for m in _user_messages(h, title) if "q3 (no. 3, sentence)" in m]
        assert q3, title
        assert all(line in m for m in q3), (title, q3)
    # choice and word questions get no such line
    assert all(line not in m for m in _user_messages(h, "AiKeyOut") if "q1 (" in m)
    assert h.answer("q3").verdict == "incorrect"
    assert json.dumps(h.fake.requests).count("Answer line starts with") >= 4


def test_judge_prompt_says_the_answer_may_continue_the_opening_words() -> None:
    from etach.prompts.render import FilePromptProvider

    text = FilePromptProvider().base_text("judge_rewrites")
    assert "may continue the words the answer line starts with" in text


# --- R22.5.4.3: ai_key_fast names only the questions without a key -------------------------------


@pytest.mark.asyncio
async def test_r22_5_4_3_ai_key_fast_names_only_the_unkeyed_questions(h: tg.Harness) -> None:
    from datetime import UTC, datetime

    from etach.domain.models import AnswerKey
    from etach.store.repos import keys

    h.thread_id = tg.seed(h.conn)
    teacher = AnswerKey(
        test_id=tg.T_ID,
        question_id="q3",
        accepted=["My brother is taller than I am"],
        reason_vi=None,
        source="teacher_edit",
        status="teacher_verified",
        confidence=None,
        updated_at=datetime.now(UTC),
    )
    keys.upsert_key(h.conn, teacher)
    h.conn.commit()
    q = _queues()  # the model answers q3 too; the code keeps only q4
    q["VerifyKeyOut"] = [tg.verify(" b "), tg.verify("Went")]
    h.fake.queues = q
    run_id = await h.grade()
    assert h.status(run_id) == "done"
    msgs = _user_messages(h, "AiKeyOut")
    assert len(msgs) == 2
    s1, s2 = msgs
    assert s1.endswith("Write the key for these questions: q1, q2")
    assert s2.endswith("Write the key for these questions: q4")
    assert "q3 (no. 3, sentence)" in s2  # the section stays as context
    stored = keys.get_key(h.conn, tg.T_ID, "q3")
    assert stored is not None
    assert (stored.source, stored.status, stored.accepted) == (
        teacher.source,
        teacher.status,
        teacher.accepted,
    )
    assert keys.get_key(h.conn, tg.T_ID, "q4") is not None


def test_ai_key_fast_prompt_drops_every_listed_question() -> None:
    from etach.prompts.render import FilePromptProvider

    text = FilePromptProvider().base_text("ai_key_fast")
    assert "every listed question" not in text
    assert "Write the key for these questions: {{key_questions}}" in text


# --- R22.5.4.4: the explain reasoning stays with the call ----------------------------------------

MARK = "HIDDEN-REASONING-MARK"


@pytest.mark.asyncio
async def test_r22_5_4_4_explain_reasoning_only_in_llm_calls(h: tg.Harness) -> None:
    h.thread_id = tg.seed(h.conn)
    q = _queues()
    q["ExplainOut"] = [
        {"reasoning": MARK, "text_vi": "Giải thích.", "error_type": "gap"} for _ in range(3)
    ]
    h.fake.queues = q
    run_id = await h.grade()
    assert h.status(run_id) == "done"
    assert h.count("explanations") >= 1
    tables = [
        r[0]
        for r in h.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    found = {}
    for table in tables:
        rows = h.conn.execute(f"SELECT * FROM {table}").fetchall()
        found[table] = sum(MARK in json.dumps(list(r), default=str) for r in rows)
    assert found.pop("llm_calls") >= 1  # kept with the call
    assert not any(found.values()), {t: n for t, n in found.items() if n}
    row = h.conn.execute("SELECT text_vi, error_type FROM explanations").fetchone()
    assert tuple(row) == ("Giải thích.", "gap")


def test_run_details_never_carry_a_call_response() -> None:
    from etach.api.routes.runs import CallSummary

    assert set(CallSummary.model_fields) == {"id", "role", "model", "task", "status"}
