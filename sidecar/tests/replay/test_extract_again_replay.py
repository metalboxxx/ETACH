"""R22.5.2.6 (D8, data-model v1.21) over the synthetic ``extract-synthetic/s1-like`` cassettes.

``etach run --replay`` extracts test T on thread A; a second, graded thread B uses T. Extract again
on A then replays the same cassettes in-process (the same reading of the same photos, which the
bank comparison would call "looks like" T if T were not left out):

- ``replace``: T keeps its id, no ``possible_duplicate`` item, the teacher key and an unsure AI
  key stay (every question matches exactly; R22.5.2.12), B's answers stay on the same questions
  and B waits for Re-grade (no grade run starts);
- ``copy``: A gets a new test; T and B are untouched; no item points at T.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from support.reader import vision_reader

from etach import cli
from etach.api.routes import threads as thread_routes
from etach.appdir import resolve_data_dir
from etach.domain.models import AnswerKey, Attempt
from etach.llm.cassettes import ReplayBackend
from etach.store import db
from etach.store.repos import attempts, keys, regrade, threads
from etach.store.repos import tests as test_repo

from .test_extract_replay import SYNTH

SCENARIO = SYNTH / "s1-like"
TIMEOUT = 120


def _first(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> tuple[Path, dict[str, Any]]:
    data = tmp_path / "data"
    vision_reader(data)  # recorded with the vision reader (R22.5.7.7)
    code = cli.main(["run", "--data", str(data), "--replay", str(SCENARIO)])
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    out: dict[str, Any] = json.loads(lines[-1])
    assert code == 0 and out["status"] == "done", lines
    return data, out


def _graded_thread_b(conn: sqlite3.Connection, test_id: str, from_attempt: str) -> str:
    """Thread B on T: a graded copy of A's attempt (another student's paper, synthetic)."""
    b = threads.create_thread(conn, "B")
    threads.set_test_id(conn, b.id, test_id)
    threads.set_kind(conn, b.id, "filled")
    src = attempts.get_attempt(conn, from_attempt)
    assert src is not None
    att_id = attempts.next_attempt_id(conn)
    attempts.insert_attempt(
        conn,
        Attempt.model_validate(
            src.model_dump()
            | {
                "id": att_id,
                "thread_id": b.id,
                "source_run_id": "R-B",
                "status": "graded",
                "score_earned": 5.0,
                "score_possible": 10.0,
            }
        ),
    )
    attempts.insert_answers(
        conn,
        [a.model_copy(update={"attempt_id": att_id}) for a in attempts.list_answers(conn, src.id)],
    )
    conn.commit()
    return att_id


async def _again(data: Path, conn: sqlite3.Connection, thread_id: str, mode: str) -> str:
    paths = resolve_data_dir(data).ensure()
    inp = thread_routes._extract_again_input(conn, thread_id, mode)  # type: ignore[arg-type]
    async with cli._manager(paths, ReplayBackend.from_dir(SCENARIO), None) as manager:
        run = await manager.submit(thread_id, "extract", inp)
        await asyncio.wait_for(manager.wait_idle(), TIMEOUT)
    return str(run.id)


def _world(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> tuple[Path, sqlite3.Connection, dict[str, Any], str, str]:
    data, first = _first(tmp_path, capsys)
    conn = db.open_database(data / "app.db")
    test_id = first["test_id"]
    att_b = _graded_thread_b(conn, test_id, first["attempt_id"])
    test = test_repo.get_test(conn, test_id)
    assert test is not None
    q1 = test.content.sections[0].groups[0].questions[0].id
    q2 = test.content.sections[0].groups[0].questions[1].id
    keys.upsert_key(
        conn,
        AnswerKey.model_validate(
            {
                "test_id": test_id,
                "question_id": q2,
                "accepted": ["B"],
                "reason_vi": None,
                "source": "ai",
                "status": "ai_uncertain",
                "confidence": 0.4,
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ),
    )
    keys.upsert_key(
        conn,
        AnswerKey.model_validate(
            {
                "test_id": test_id,
                "question_id": q1,
                "accepted": ["A"],
                "reason_vi": None,
                "source": "teacher_edit",
                "status": "teacher_verified",
                "confidence": None,
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ),
    )
    conn.commit()
    return data, conn, first, att_b, q1


def _duplicates(conn: sqlite3.Connection) -> list[Any]:
    return conn.execute(
        "SELECT test_id, proposal FROM review_items WHERE kind = 'possible_duplicate'"
    ).fetchall()


def test_replace_keeps_the_test_id(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data, conn, first, att_b, q1 = _world(tmp_path, capsys)
    try:
        test_id = first["test_id"]
        b_before = sorted(a.question_id for a in attempts.list_answers(conn, att_b))
        run_id = asyncio.run(_again(data, conn, first["thread_id"], "replace"))
        assert (
            conn.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()[0] == "done"
        )
        assert conn.execute("SELECT COUNT(*) FROM tests").fetchone()[0] == 1
        new_att = attempts.find_by_source_run(conn, run_id)
        assert new_att is not None and new_att.test_id == test_id
        old = attempts.get_attempt(conn, first["attempt_id"])
        assert old is not None and old.superseded_by == new_att.id
        assert _duplicates(conn) == []
        key = keys.get_key(conn, test_id, q1)
        assert key is not None and key.source == "teacher_edit"
        test = test_repo.get_test(conn, test_id)
        assert test is not None
        q2 = test.content.sections[0].groups[0].questions[1].id
        ai = keys.get_key(conn, test_id, q2)  # the AI key on the same question, still unsure
        assert ai is not None and (ai.source, ai.status, ai.confidence, ai.accepted) == (
            "ai",
            "ai_uncertain",
            0.4,
            ["B"],
        )
        assert sorted(a.question_id for a in attempts.list_answers(conn, att_b)) == b_before
        assert regrade.is_pending(conn, test_id)
        # no re-grade run starts; the only grade runs are the extractions' key runs (step 22.6.4)
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM runs WHERE kind = 'grade'"
                " AND json_extract(input, '$.reason') != 'after_extract'"
            ).fetchone()[0]
            == 0
        )
    finally:
        conn.close()


def test_copy_makes_a_new_test(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data, conn, first, att_b, q1 = _world(tmp_path, capsys)
    try:
        test_id = first["test_id"]
        b_before = attempts.list_answers(conn, att_b)
        run_id = asyncio.run(_again(data, conn, first["thread_id"], "copy"))
        new = test_repo.find_by_source_run(conn, run_id)
        assert new is not None and new.id != test_id
        thread = threads.get_thread(conn, first["thread_id"])
        assert thread is not None and thread.test_id == new.id
        assert [r for r in _duplicates(conn) if test_id in r[1]] == []
        assert attempts.list_answers(conn, att_b) == b_before
        assert keys.get_key(conn, test_id, q1) is not None
        assert not regrade.is_pending(conn, test_id)
    finally:
        conn.close()
