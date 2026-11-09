"""Step 22.5.2 through the extract graph (the in-process fake Ollama of the step 9 tests, synthetic
responses, no model): "same series as <name>" (R22.5.2.2, D5) and Extract again into the same
test or a copy (R22.5.2.6, D8)."""

from __future__ import annotations

import asyncio
import copy
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from unit.graphs.test_extract import (
    EMPTY_ANSWERS,
    HEADER,
    TIMEOUT,
    Harness,
    answers_all,
    make_harness,
    page_out,
)

from etach.api.routes import threads as thread_routes
from etach.appdir import DataPaths
from etach.domain.models import AnswerKey, ExtractInput
from etach.store import db
from etach.store.repos import attempts, keys, regrade, runs, series, threads
from etach.store.repos import tests as test_repo


@pytest_asyncio.fixture
async def h(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Harness]:
    paths = DataPaths(tmp_path / "data")
    db.open_database(paths.db).close()
    async with make_harness(paths, monkeypatch) as harness:
        yield harness


def _filled(h: Harness) -> dict[str, Any]:
    return {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [answers_all("B"), EMPTY_ANSWERS],
    }


async def _first(h: Harness, thread_id: str | None = None) -> str:
    """A filled 2-page extraction (questions 1-4); returns the run id."""
    h.fake.queues = _filled(h)
    run_id, _ = await h.run(h.photos(2), thread_id=thread_id)
    return run_id


async def _submit(h: Harness, thread_id: str, inp: ExtractInput, queues: dict[str, Any]) -> str:
    h.fake.queues = {k: list(v) for k, v in queues.items()}
    h.saved_states.clear()
    run = await h.manager.submit(thread_id, "extract", inp)
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    assert h.runs_status(run.id) == "done"
    return run.id


# --- R22.5.2.2: same series as <name> ------------------------------------------------------------


@pytest.mark.asyncio
async def test_r22_5_2_2_series_name_copies_from_the_newest_test(h: Harness) -> None:
    older = await _first(h)
    newer = await _first(h, threads.create_thread(h.conn, "b").id)
    older_id = test_repo.find_by_source_run(h.conn, older).id  # type: ignore[union-attr]
    newer_id = test_repo.find_by_source_run(h.conn, newer).id  # type: ignore[union-attr]
    db.write_test_meta(h.conn, older_id, {"source": "Đề dự đoán", "grade": 7, "year": "2020"}, True)
    db.write_test_meta(
        h.conn,
        newer_id,
        {
            "source": "đề dự đoán",
            "grade": 9,
            "occasion": "MidTerm",
            "term": 2,
            "year": "2024-2025",
            "school": "Synthetic School",
        },
        True,
    )
    h.conn.execute("UPDATE tests SET created_at = '2020-01-01T00:00:00Z' WHERE id = ?", (older_id,))
    h.conn.commit()

    inp = ExtractInput(
        pages=h.photos(2),
        existing_test_id=None,
        supersedes_attempt_id=None,
        series_name="  Đề dự đoán ",
    )
    run_id = await _submit(h, threads.create_thread(h.conn, "c").id, inp, _filled(h))
    new = test_repo.find_by_source_run(h.conn, run_id)
    assert new is not None and new.id not in (older_id, newer_id)
    meta = new.meta
    assert (meta.source, meta.grade, meta.occasion, meta.term, meta.year) == (
        "Đề dự đoán",
        9,
        "MidTerm",
        2,
        "2024-2025",
    )
    assert meta.school != "Synthetic School"  # the school is not copied
    assert {"source", "grade", "occasion", "term", "year"} <= set(meta.edited_fields)
    assert "school" not in meta.edited_fields
    assert [s.name for s in series.list_series(h.conn)] == ["Đề dự đoán"]

    # a series no test has yet: only the source
    inp = inp.model_copy(update={"series_name": "Bộ đề mới", "pages": h.photos(2)})
    run_id = await _submit(h, threads.create_thread(h.conn, "d").id, inp, _filled(h))
    only = test_repo.find_by_source_run(h.conn, run_id)
    assert only is not None and only.meta.source == "Bộ đề mới"
    assert set(only.meta.edited_fields) == {"source"}
    assert [s.name for s in series.list_series(h.conn)] == ["Đề dự đoán", "Bộ đề mới"]


# --- R22.5.2.6: Extract again --------------------------------------------------------------------


def _qid(h: Harness, test_id: str, printed: int) -> str:
    test = test_repo.get_test(h.conn, test_id)
    assert test is not None
    return next(
        q.id
        for s in test.content.sections
        for g in s.groups
        for q in g.questions
        if q.printed_number == printed
    )


def _key(
    test_id: str, qid: str, source: str, status: str, confidence: float | None = None
) -> AnswerKey:
    return AnswerKey.model_validate(
        {
            "test_id": test_id,
            "question_id": qid,
            "accepted": ["C"],
            "reason_vi": None,
            "source": source,
            "status": status,
            "confidence": confidence,
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )


async def _two_threads(h: Harness) -> tuple[str, str, str, str]:
    """Thread A extracts test T (questions 1-4); thread B picked T for another student and is
    graded. A teacher key on question 1, an unsure AI key on question 2, an AI key on question 3.
    Returns (T, A, B's attempt, A's attempt)."""
    run_a = await _first(h)
    test_id = test_repo.find_by_source_run(h.conn, run_a).id  # type: ignore[union-attr]
    att_a = attempts.find_by_source_run(h.conn, run_a).id  # type: ignore[union-attr]
    b = threads.create_thread(h.conn, "b").id
    stems = [q["stem"] for q in page_out(1)["sections"][0]["groups"][0]["questions"]]
    h.fake.queues = {
        "ReadHeaderOut": [{"header_text": HEADER, "first_stems": stems}],
        "ReadAnswersCall": [answers_all("C"), EMPTY_ANSWERS],
    }
    run_b, _ = await h.run(h.photos(2), existing=test_id, thread_id=b)
    att_b = attempts.find_by_source_run(h.conn, run_b).id  # type: ignore[union-attr]
    h.conn.execute(
        "UPDATE attempts SET score_earned = 5, score_possible = 10, status = 'graded' WHERE id = ?",
        (att_b,),
    )
    h.conn.commit()
    keys.upsert_key(h.conn, _key(test_id, _qid(h, test_id, 1), "teacher_edit", "teacher_verified"))
    keys.upsert_key(h.conn, _key(test_id, _qid(h, test_id, 2), "ai", "ai_uncertain", 0.4))
    keys.upsert_key(h.conn, _key(test_id, _qid(h, test_id, 3), "ai", "ai_unverified", 0.9))
    # step 22.6.4: the keys above stand in for the key runs the two saves queued (the harness
    # registers no grade graph, so they stay queued); they are over, as in the app
    for run in runs.list_runs(h.conn, status="queued"):
        assert run.kind == "grade" and run.input.reason == "after_extract"  # type: ignore[union-attr]
        runs.set_run_status(h.conn, run.id, "done")
    return test_id, h.thread_id, att_b, att_a


def _changed_page_2() -> dict[str, Any]:
    out = copy.deepcopy(page_out(2))
    q3 = out["sections"][0]["groups"][0]["questions"][0]
    q3["stem"] = "Zebras quietly gather beside the frozen northern lake today"
    return out


def _duplicates(h: Harness) -> list[Any]:
    return h.conn.execute(
        "SELECT test_id, proposal FROM review_items WHERE kind = 'possible_duplicate'"
    ).fetchall()


@pytest.mark.asyncio
async def test_r22_5_2_6_replace_keeps_the_test_id(h: Harness) -> None:
    test_id, a, att_b, att_a = await _two_threads(h)
    old_q3 = _qid(h, test_id, 3)
    ai_q2 = keys.get_key(h.conn, test_id, _qid(h, test_id, 2))
    n_tests = h.count("tests")
    with pytest.raises(Exception) as refused:  # B uses T too: a mode must be chosen
        thread_routes._extract_again_input(h.conn, a)  # type: ignore[arg-type]
    assert thread_routes.CHOOSE_MODE in str(refused.value.detail)  # type: ignore[attr-defined]
    inp = thread_routes._extract_again_input(h.conn, a, "replace")  # type: ignore[arg-type]
    queues = {
        "TranscribeOut": [page_out(1, header=HEADER), _changed_page_2()],
        "ReadAnswersCall": [answers_all("B"), EMPTY_ANSWERS],
    }
    run_id = await _submit(h, a, inp, queues)

    assert h.count("tests") == n_tests
    new_att = attempts.find_by_source_run(h.conn, run_id)
    assert new_att is not None and new_att.test_id == test_id
    assert attempts.get_attempt(h.conn, att_a).superseded_by == new_att.id  # type: ignore[union-attr]
    assert threads.get_thread(h.conn, a).test_id == test_id  # type: ignore[union-attr]
    assert _duplicates(h) == []  # no "looks like" item points at the same test
    new_q3 = _qid(h, test_id, 3)
    assert new_q3 != old_q3  # question 3 was read differently: a new question
    # keys stay on the exactly matching questions 1 (teacher) and 2 (AI, still unsure; D8
    # addition, R22.5.2.12); question 3 was read differently, so its AI key goes: keyed again
    by_q = {k.question_id: k for k in keys.list_keys(h.conn, test_id)}
    assert by_q[_qid(h, test_id, 1)].source == "teacher_edit"
    assert by_q[_qid(h, test_id, 2)] == ai_q2.model_copy(  # type: ignore[union-attr]
        update={"question_id": _qid(h, test_id, 2)}
    )
    assert by_q[_qid(h, test_id, 2)].status == "ai_uncertain"
    assert new_q3 not in by_q and set(by_q) == {_qid(h, test_id, 1), _qid(h, test_id, 2)}
    # B follows: its answers stay on the matched questions, q3's is gone, the new one is empty
    b_answers = {x.question_id: x for x in attempts.list_answers(h.conn, att_b)}
    test = test_repo.get_test(h.conn, test_id)
    assert test is not None
    ids = {q.id for s in test.content.sections for g in s.groups for q in g.questions}
    assert set(b_answers) == ids and old_q3 not in b_answers
    assert b_answers[new_q3].value is None
    assert b_answers[_qid(h, test_id, 1)].value == "C"
    assert regrade.is_pending(h.conn, test_id)  # B is graded: re-grade waits for the teacher
    # no re-grade run is queued; the only grade runs are the key runs of the three saves
    # (step 22.6.4, D4), and Extract again's is the one still queued
    grade_runs = [r for r in runs.list_runs(h.conn) if r.kind == "grade"]
    assert [r.input.reason for r in grade_runs] == ["after_extract"] * 3  # type: ignore[union-attr]
    assert [r.input.attempt_id for r in grade_runs] == [None] * 3  # type: ignore[union-attr]
    assert [r.status for r in grade_runs] == ["done", "done", "queued"]


@pytest.mark.asyncio
async def test_r22_5_2_6_copy_makes_a_new_test_for_this_thread(h: Harness) -> None:
    test_id, a, att_b, _ = await _two_threads(h)
    before_b = attempts.list_answers(h.conn, att_b)
    inp = thread_routes._extract_again_input(h.conn, a, "copy")  # type: ignore[arg-type]
    run_id = await _submit(h, a, inp, _filled(h))
    new = test_repo.find_by_source_run(h.conn, run_id)
    assert new is not None and new.id != test_id
    assert threads.get_thread(h.conn, a).test_id == new.id  # type: ignore[union-attr]
    assert _duplicates(h) == []  # the test it came from is left out of the comparison
    assert attempts.list_answers(h.conn, att_b) == before_b  # B and T are untouched
    assert keys.get_key(h.conn, test_id, _qid(h, test_id, 1)) is not None
    assert not regrade.is_pending(h.conn, test_id)
