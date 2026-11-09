"""Fixtures for the store tests: a migrated database in ``tmp_path`` and small row factories."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

from etach.appdir import resolve_data_dir
from etach.domain import models as m
from etach.store import db
from etach.store.files import FileStore
from etach.store.repos import attempts, runs, tests, threads

T0 = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)


@pytest.fixture
def conn(tmp_path: Any) -> Iterator[sqlite3.Connection]:
    c = db.open_database(tmp_path / "data" / "app.db")
    yield c
    c.close()


@pytest.fixture
def store(conn: sqlite3.Connection, tmp_path: Any) -> FileStore:
    """The file store of the same data folder as ``conn``."""
    return FileStore(conn, resolve_data_dir(tmp_path / "data").ensure())


def content(n_questions: int = 2) -> m.TestContent:
    questions = [
        m.Question(
            id=f"q-{i}",
            number=i,
            printed_number=i + 4,
            page_no=1,
            answer_form="choice",
            stem=f"Stem {i}",
            options=[m.Option(label="A", text="one"), m.Option(label="B", text="two")],
            cue=None,
            points=0.25,
        )
        for i in range(1, n_questions + 1)
    ]
    group = m.QuestionGroup(id="g-1", stimulus=None, pictures=[], questions=questions)
    section = m.Section(
        id="s-1",
        number=1,
        printed_title="II",
        title="Choose the best answer",
        instructions="Circle A or B.",
        points=0.25 * n_questions,
        points_source="printed",
        skill="grammar",
        groups=[group],
    )
    return m.TestContent(sections=[section])


def make_test(
    conn: sqlite3.Connection, meta: m.TestMetadata | None = None, **fields: Any
) -> m.Test:
    values: dict[str, Any] = {
        "id": tests.next_test_id(conn),
        "meta": meta or m.TestMetadata(occasion="FinalTerm", grade=8, term=1, test_number="1"),
        "content": content(),
        "content_schema_version": 1,
        "fingerprint": "fp",
        "points_possible": 0.5,
        "source_run_id": None,
        "merged_into": None,
        "created_at": T0,
        "updated_at": T0,
    }
    values.update(fields)
    return tests.insert_test(conn, m.Test(**values))


def make_run(conn: sqlite3.Connection, thread_id: str | None = None) -> m.Run:
    if thread_id is None:
        thread_id = threads.create_thread(conn, "photos").id
    return runs.create_run(
        conn,
        thread_id,
        "extract",
        m.ExtractInput(pages=[], existing_test_id=None, supersedes_attempt_id=None),
    )


def make_attempt(
    conn: sqlite3.Connection,
    test_id: str,
    student_id: str | None = None,
    created_at: datetime = T0,
    **fields: Any,
) -> m.Attempt:
    run = make_run(conn)
    values: dict[str, Any] = {
        "id": attempts.next_attempt_id(conn),
        "test_id": test_id,
        "thread_id": run.thread_id,
        "student_id": student_id,
        "student_name_read": None,
        "class_read": None,
        "source_run_id": run.id,
        "superseded_by": None,
        "status": "extracted",
        "version": 1,
        "score_earned": None,
        "score_possible": None,
        "created_at": created_at,
    }
    values.update(fields)
    return attempts.insert_attempt(conn, m.Attempt(**values))


def make_llm_call(conn: sqlite3.Connection) -> m.LlmCall:
    run = make_run(conn)
    step = runs.insert_step(conn, run.id, "explain", None, 1)
    return runs.insert_llm_call(
        conn,
        m.LlmCall(
            id=db.new_ulid(),
            step_id=step.id,
            role="reasoning",
            model="model-x",
            prompt_hash="h",
            request={"messages": []},
            response_text="{}",
            thinking_text="",
            logprobs=None,
            status="complete",
            tokens_in=1,
            tokens_out=1,
            ms=5,
            created_at=T0,
        ),
    )


def answer(attempt_id: str, question_id: str, **fields: Any) -> m.Answer:
    values: dict[str, Any] = {
        "attempt_id": attempt_id,
        "question_id": question_id,
        "printed_number": 5,
        "page_no": 1,
        "value": "A",
        "value_norm": "a",
        "location": "circled_option",
        "confidence": 0.95,
        "reading_unsure": False,
        "alt_value": None,
        "alt_question_id": None,
        "points_awarded": None,
        "teacher_override": None,
    }
    values.update(fields)
    return m.Answer(**values)


def explanation(
    test_id: str, question_id: str, wrong: str, llm_call_id: str, error_type: str = "gap"
) -> m.Explanation:
    return m.Explanation(
        test_id=test_id,
        question_id=question_id,
        wrong_answer_norm=wrong,
        error_type=error_type,  # type: ignore[arg-type]
        text_vi="Giải thích.",
        status="ai",
        llm_call_id=llm_call_id,
    )


class Factory:
    """The helpers above, as a fixture (conftest modules are not importable in importlib mode)."""

    T0 = T0
    content = staticmethod(content)
    make_test = staticmethod(make_test)
    make_run = staticmethod(make_run)
    make_attempt = staticmethod(make_attempt)
    make_llm_call = staticmethod(make_llm_call)
    answer = staticmethod(answer)
    explanation = staticmethod(explanation)


@pytest.fixture
def f() -> type[Factory]:
    return Factory
