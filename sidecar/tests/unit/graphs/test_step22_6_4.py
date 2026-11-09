"""Step 22.6.4 (step22.6-plan D4): the key after every extraction.

The extract and grade graphs run on one real ``RunManager`` with in-process fake models (the
extract fake of ``test_extract``; a key fake here that keys every question it is asked for with
"A"). An extraction's save queues a grade run without an attempt, reason ``after_extract``, and
the manager starts it after the extract run (R22.6.4.1); it never grades, keeps key-photo and
teacher keys, and a later Grade keys only what is still missing (R22.6.4.2). R22.6.4.3 checks
the model and the generated files; R22.6.4.5 the docs.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from fastapi import HTTPException
from support.fake_ollama import ChatScript, FakeOllama
from unit.graphs.test_extract import (
    EMPTY_ANSWERS,
    HEADER,
    TIMEOUT,
    Harness,
    _bank_test,
    _text_pdf,
    answers_all,
    make_harness,
    page_out,
    png,
)

from etach.api.routes import students as student_routes
from etach.api.routes import tests as test_routes
from etach.api.routes import threads as thread_routes
from etach.appdir import DataPaths
from etach.domain.models import AnswerKey, ExtractInput, GradeInput, PageInput, Run
from etach.graphs.grade import GradeDeps, register_grade
from etach.llm.client import OllamaClient
from etach.llm.config import default_config
from etach.prompts.render import FilePromptProvider
from etach.store import db
from etach.store.repos import attempts, keys, runs, students, threads
from etach.store.repos import tests as test_repo

REPO = Path(__file__).resolve().parents[4]
REASONS = ["button", "key_verified", "merge", "review_fix", "points_fix", "after_extract"]


class KeyFake(FakeOllama):
    """The grade graph's model: ``ai_key_fast`` keys every question it is asked for with "A",
    ``verify_key`` agrees with "A", every other task gets invalid JSON (the graph skips it).
    ``fail`` answers HTTP 500, so the run fails."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: list[str] = []
        self.keyed: list[str] = []
        self.fail = False
        self.hang = False  # every call hangs until the client goes away (a running key run)

    def _script(self) -> ChatScript:
        body = self.requests[-1]
        title = body["format"]["title"]
        self.seen.append(title)
        if self.fail:
            return ChatScript(status_code=500)
        if self.hang:
            return ChatScript(tokens=list("{}"), hang_after=0)
        if title == "AiKeyOut":
            user = body["messages"][-1]["content"]
            asked = re.search(r"Write the key for these questions: (.+)", user)
            assert asked is not None
            qids = [q.strip() for q in asked.group(1).split(",")]
            self.keyed.extend(qids)
            out: Any = {
                "keys": [{"question_id": q, "accepted": ["A"], "reason_vi": "r"} for q in qids]
            }
        elif title == "VerifyKeyOut":
            out = {"reasoning": "x", "answer": "A"}
        else:
            out = "not json at all"
        text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
        return ChatScript(tokens=list(text))

    def calls(self, title: str) -> int:
        return self.seen.count(title)


@contextlib.asynccontextmanager
async def both_graphs(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch, *, grade: bool = True
) -> AsyncIterator[tuple[Harness, KeyFake, Any]]:
    """The extract harness with the grade graph registered on the same manager (``grade``
    False: registered later by the test, through the returned function)."""
    async with make_harness(data, monkeypatch) as h:
        fake = KeyFake()
        client_conn = db.connect(data.db)
        client = OllamaClient(
            client_conn,
            default_config(),
            FilePromptProvider(),
            base_url="http://fake-ollama",
            transport=fake.transport,
        )

        def register() -> None:
            register_grade(h.manager, GradeDeps(client=client))

        if grade:
            register()
        try:
            yield h, fake, register
        finally:
            await h.manager.aclose()
            client_conn.close()


@pytest.fixture
def data(tmp_path: Path) -> DataPaths:
    paths = DataPaths(tmp_path / "data")
    db.open_database(paths.db).close()
    return paths


@pytest_asyncio.fixture
async def hk(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[Harness, KeyFake]]:
    async with both_graphs(data, monkeypatch) as (h, fake, _):
        yield h, fake


def _filled() -> dict[str, Any]:
    return {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [answers_all("B"), answers_all("B")],
    }


def key_runs(h: Harness, thread_id: str | None = None) -> list[Run]:
    tid = thread_id or h.thread_id
    return [
        r
        for r in runs.list_runs(h.conn, thread_id=tid)
        if r.kind == "grade" and isinstance(r.input, GradeInput)
        if r.input.reason == "after_extract"
    ]


def _test_id(h: Harness, run_id: str) -> str:
    thread = threads.get_thread(
        h.conn,
        runs.get_run(h.conn, run_id).thread_id,  # type: ignore[union-attr]
    )
    assert thread is not None and thread.test_id is not None
    return thread.test_id


def _qids(h: Harness, test_id: str) -> list[str]:
    test = test_repo.get_test(h.conn, test_id)
    assert test is not None
    return [q.id for s in test.content.sections for g in s.groups for q in g.questions]


def _assert_one_key_run_after(h: Harness, run_id: str, thread_id: str | None = None) -> Run:
    """Exactly one ``after_extract`` run created after the extract run ``run_id``, on its
    thread, for its test, without an attempt, started after the extract run ended, done."""
    extract = runs.get_run(h.conn, run_id)
    assert extract is not None and extract.status == "done"
    after = [r for r in key_runs(h, thread_id) if r.id > run_id]
    assert len(after) == 1, after
    (run,) = after
    assert isinstance(run.input, GradeInput)
    assert run.input.attempt_id is None
    assert run.input.test_id == _test_id(h, run_id)
    assert run.status == "done"
    assert extract.finished_at is not None and run.started_at is not None
    assert run.started_at >= extract.finished_at
    return run


# --- R22.6.4.1: every save queues one key run --------------------------------------------------


@pytest.mark.asyncio
async def test_r22_6_4_1_a_new_photo_test_queues_one_key_run_after_the_extract_run(
    hk: tuple[Harness, KeyFake],
) -> None:
    h, fake = hk
    h.fake.queues = _filled()
    run_id, _ = await h.run(h.photos(2))
    run = _assert_one_key_run_after(h, run_id)
    test_id = _test_id(h, run_id)
    # the key run made the AI key for every question (the "Make the key" run)
    assert sorted(fake.keyed) == sorted(_qids(h, test_id))
    ks = keys.list_keys(h.conn, test_id)
    assert len(ks) == 4 and all(k.source == "ai" and k.accepted == ["A"] for k in ks)
    assert [s.node for s in runs.list_steps(h.conn, run.id)][:2] == ["load_context", "ai_key_fast"]
    # FIFO: the extract run is done before the key run's first step
    assert [r.kind for r in runs.list_runs(h.conn)] == ["extract", "grade"]


@pytest.mark.asyncio
async def test_r22_6_4_1_the_row_is_written_by_the_save_transaction(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A save that fails before its commit queues nothing (R9.8's stub); the key run is in the
    same commit as the test (a save that crashes after its commit already left it queued)."""
    async with both_graphs(data, monkeypatch, grade=False) as (h, _fake, _register):
        h.fake.queues = _filled()
        h.save_mode = "stub"
        run = await h.manager.submit(
            h.thread_id,
            "extract",
            ExtractInput(pages=h.photos(2), existing_test_id=None, supersedes_attempt_id=None),
        )
        await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
        assert h.runs_status(run.id) == "failed"
        assert key_runs(h) == [] and h.count("tests") == 0

        h.fake.queues = _filled()
        h.save_mode = "crash_after"
        thread_b = threads.create_thread(h.conn, "b").id
        run_b, _ = await h.run(h.photos(2), thread_id=thread_b)
        assert h.runs_status(run_b) == "interrupted"
        (queued,) = key_runs(h, thread_b)
        assert queued.status == "queued" and queued.id > run_b
        assert test_repo.find_by_source_run(h.conn, run_b) is not None


@pytest.mark.asyncio
async def test_r22_6_4_1_a_retried_save_queues_no_second_key_run(
    hk: tuple[Harness, KeyFake],
) -> None:
    h, fake = hk
    h.fake.queues = _filled()
    h.save_mode = "crash_after"
    run_id, _ = await h.run(h.photos(2))
    # the save committed, then the run was cut: the key run waits until the extract run is done
    assert h.runs_status(run_id) == "interrupted"
    assert [r.status for r in key_runs(h)] == ["queued"]
    assert fake.seen == []
    await h.manager.resume(run_id)
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    assert len(h.steps(run_id, "save")) == 2  # the save ran again
    _assert_one_key_run_after(h, run_id)
    assert len(key_runs(h)) == 1


def test_r22_6_4_1_enqueue_key_run_is_idempotent(data: DataPaths) -> None:
    conn = db.connect(data.db)
    try:
        thread_id = threads.create_thread(conn, "t").id
        extract = runs.create_run(
            conn,
            thread_id,
            "extract",
            ExtractInput(pages=[], existing_test_id=None, supersedes_attempt_id=None),
        )
        first = runs.enqueue_key_run(
            conn, thread_id=thread_id, test_id="T-0001", after_run_id=extract.id
        )
        again = runs.enqueue_key_run(
            conn, thread_id=thread_id, test_id="T-0001", after_run_id=extract.id
        )
        assert again == first
        run = runs.get_run(conn, first)
        assert run is not None and run.kind == "grade" and run.status == "queued"
        assert run.input == GradeInput(test_id="T-0001", attempt_id=None, reason="after_extract")
        # a later extract run on the thread (Extract again) gets its own
        later = runs.create_run(
            conn,
            thread_id,
            "extract",
            ExtractInput(pages=[], existing_test_id=None, supersedes_attempt_id=None),
        )
        second = runs.enqueue_key_run(
            conn, thread_id=thread_id, test_id="T-0001", after_run_id=later.id
        )
        assert second != first
        assert len(runs.list_runs(conn, thread_id=thread_id)) == 4
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_r22_6_4_1_every_kind_of_extraction_queues_one(
    hk: tuple[Harness, KeyFake],
) -> None:
    h, _fake = hk
    # a blank photo test (no answers read)
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [EMPTY_ANSWERS, EMPTY_ANSWERS],
    }
    blank_run, _ = await h.run(h.photos(2))
    assert threads.get_thread(h.conn, h.thread_id).kind == "blank"  # type: ignore[union-attr]
    _assert_one_key_run_after(h, blank_run)

    # a picked existing test (a filled paper of another student)
    bank = _bank_test(h, 2)
    stems = [q.stem for s in bank.content.sections for g in s.groups for q in g.questions]
    picked_thread = threads.create_thread(h.conn, "picked").id
    h.fake.queues = {
        "ReadHeaderOut": [{"header_text": HEADER, "first_stems": stems[:3]}],
        "ReadAnswersCall": [answers_all("B"), answers_all("B")],
    }
    picked_run, _ = await h.run(h.photos(2), bank.id, thread_id=picked_thread)
    run = _assert_one_key_run_after(h, picked_run, picked_thread)
    assert run.input.test_id == bank.id  # type: ignore[union-attr]

    # typed input (a typed PDF: a test without answers)
    from etach.store.documents import ingest

    typed_thread = threads.create_thread(h.conn, "typed").id
    h.fake.queues = {"TranscribeOut": [page_out(1, header=HEADER), page_out(2)]}
    typed_run, _ = await h.run(ingest(h.files, _text_pdf(2), "typed.pdf"), thread_id=typed_thread)
    _assert_one_key_run_after(h, typed_run, typed_thread)

    # Extract again into the same test (replace), on the filled thread
    filled_thread = threads.create_thread(h.conn, "filled").id
    h.fake.queues = _filled()
    first, _ = await h.run(h.photos(2), thread_id=filled_thread)
    _assert_one_key_run_after(h, first, filled_thread)
    test_id = _test_id(h, first)
    inp = thread_routes._extract_again_input(h.conn, filled_thread, "replace")  # type: ignore[arg-type]
    h.fake.queues = _filled()
    again = await h.manager.submit(filled_thread, "extract", inp)
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    run = _assert_one_key_run_after(h, again.id, filled_thread)
    assert run.input.test_id == test_id  # type: ignore[union-attr]
    assert len(key_runs(h, filled_thread)) == 2


# --- R22.6.4.2: never grades; keeps keys; Grade after it ----------------------------------------


@pytest.mark.asyncio
async def test_r22_6_4_2_the_key_run_never_grades_the_attempt(
    hk: tuple[Harness, KeyFake],
) -> None:
    h, fake = hk
    h.fake.queues = _filled()
    run_id, _ = await h.run(h.photos(2))
    _assert_one_key_run_after(h, run_id)
    att = attempts.find_by_source_run(h.conn, run_id)
    assert att is not None
    got = attempts.get_attempt(h.conn, att.id)
    assert got is not None and got.status == "extracted" and got.score_earned is None
    answers = attempts.list_answers(h.conn, att.id)
    assert answers and all(a.verdict == "ungraded" and a.points_awarded is None for a in answers)
    assert attempts.get_grade_report(h.conn, att.id) is None
    cards = [m for m in threads.list_messages(h.conn, h.thread_id) if m.kind == "grade_card"]
    assert cards == []
    for title in ("JudgeOut", "ExplainOut", "SummaryOut"):
        assert fake.calls(title) == 0


@pytest.mark.asyncio
async def test_r22_6_4_2_key_photo_and_teacher_keys_stay(hk: tuple[Harness, KeyFake]) -> None:
    h, fake = hk
    # a key photo with the keys of questions 1 and 2: the key run keys only 3 and 4
    pages = h.photos(2)
    key_fid = h.files.put(png((10, 10, 10)), "png")
    pages.append(PageInput(file_id=key_fid, rotation=0, is_key=True, text_file_id=None))
    h.fake.queues = {
        "ReadKeyOut": [{"entries": [{"label": "1", "answer": "C"}, {"label": "2", "answer": "D"}]}],
        **_filled(),
    }
    run_id, _ = await h.run(pages)
    _assert_one_key_run_after(h, run_id)
    test_id = _test_id(h, run_id)
    q1, q2, q3, q4 = _qids(h, test_id)
    by_q = {k.question_id: k for k in keys.list_keys(h.conn, test_id)}
    assert {q: (by_q[q].source, by_q[q].accepted) for q in (q1, q2)} == {
        q1: ("from_key_photo", ["C"]),
        q2: ("from_key_photo", ["D"]),
    }
    assert sorted(fake.keyed) == sorted([q3, q4])
    assert by_q[q3].source == by_q[q4].source == "ai"

    # a teacher key on a picked test stays; the key run keys only the questions without one
    bank = _bank_test(h, 2)
    b1, *rest = _qids(h, bank.id)
    teacher = AnswerKey(
        test_id=bank.id,
        question_id=b1,
        accepted=["B"],
        reason_vi=None,
        source="teacher_edit",
        status="teacher_verified",
        confidence=None,
        updated_at=datetime.now(UTC),
    )
    keys.upsert_key(h.conn, teacher)
    fake.keyed.clear()
    stems = [q.stem for s in bank.content.sections for g in s.groups for q in g.questions]
    thread_b = threads.create_thread(h.conn, "b").id
    h.fake.queues = {
        "ReadHeaderOut": [{"header_text": HEADER, "first_stems": stems[:3]}],
        "ReadAnswersCall": [answers_all("B"), answers_all("B")],
    }
    picked_run, _ = await h.run(h.photos(2), bank.id, thread_id=thread_b)
    _assert_one_key_run_after(h, picked_run, thread_b)
    assert sorted(fake.keyed) == sorted(rest)
    assert keys.get_key(h.conn, bank.id, b1) == teacher


async def _grade(h: Harness, attempt_id: str, test_id: str) -> str:
    inp = GradeInput(test_id=test_id, attempt_id=attempt_id, reason="button")
    run = await h.manager.submit(h.thread_id, "grade", inp)
    await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
    return run.id


@pytest.mark.asyncio
async def test_r22_6_4_2_a_later_grade_uses_the_keys_and_makes_only_missing_ones(
    hk: tuple[Harness, KeyFake],
) -> None:
    h, fake = hk
    h.fake.queues = _filled()
    run_id, _ = await h.run(h.photos(2))
    _assert_one_key_run_after(h, run_id)
    test_id = _test_id(h, run_id)
    att = attempts.find_by_source_run(h.conn, run_id)
    assert att is not None
    made = {k.question_id: (k.source, k.accepted) for k in keys.list_keys(h.conn, test_id)}
    assert fake.calls("AiKeyOut") == 2  # one call per section

    # Grade with every key there: no new key
    fake.keyed.clear()
    grade_run = await _grade(h, att.id, test_id)
    assert h.runs_status(grade_run) == "done"
    assert fake.keyed == [] and fake.calls("AiKeyOut") == 2
    assert {k.question_id: (k.source, k.accepted) for k in keys.list_keys(h.conn, test_id)} == made
    graded = attempts.get_attempt(h.conn, att.id)
    assert graded is not None and graded.status == "graded"

    # one key gone: the next Grade makes only that one
    q4 = _qids(h, test_id)[3]
    h.conn.execute("DELETE FROM answer_keys WHERE test_id = ? AND question_id = ?", (test_id, q4))
    h.conn.commit()
    regrade = await _grade(h, att.id, test_id)
    assert h.runs_status(regrade) == "done"
    assert fake.keyed == [q4]
    assert {k.question_id: (k.source, k.accepted) for k in keys.list_keys(h.conn, test_id)} == made


@pytest.mark.asyncio
async def test_r22_6_4_2_grade_works_when_the_key_run_failed(
    hk: tuple[Harness, KeyFake],
) -> None:
    h, fake = hk
    fake.fail = True
    h.fake.queues = _filled()
    run_id, _ = await h.run(h.photos(2))
    (failed,) = key_runs(h)
    assert failed.status == "failed"
    test_id = _test_id(h, run_id)
    assert keys.list_keys(h.conn, test_id) == []
    fake.fail = False
    att = attempts.find_by_source_run(h.conn, run_id)
    assert att is not None
    grade_run = await _grade(h, att.id, test_id)
    assert h.runs_status(grade_run) == "done"
    assert sorted(fake.keyed) == sorted(_qids(h, test_id))
    graded = attempts.get_attempt(h.conn, att.id)
    assert graded is not None and graded.status == "graded"


@pytest.mark.asyncio
async def test_r22_6_4_2_grade_works_when_the_key_run_was_stopped_or_discarded(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    # no grade graph yet: the key run waits in the queue, where the teacher stops it
    async with both_graphs(data, monkeypatch, grade=False) as (h, fake, register):
        h.fake.queues = _filled()
        run_id, _ = await h.run(h.photos(2))
        (queued,) = key_runs(h)
        assert queued.status == "queued"
        stopped = await h.manager.stop(queued.id)
        assert stopped.status == "stopped"
        register()
        test_id = _test_id(h, run_id)
        att = attempts.find_by_source_run(h.conn, run_id)
        assert att is not None
        grade_run = await _grade(h, att.id, test_id)
        assert h.runs_status(grade_run) == "done"
        assert sorted(fake.keyed) == sorted(_qids(h, test_id))
        assert key_runs(h)[0].status == "stopped"  # Grade did not resume it
        discarded = await h.manager.discard(queued.id)
        assert discarded.status == "discarded"
        assert len(keys.list_keys(h.conn, test_id)) == 4


# --- R22.6.4.6: Extract again and Delete thread cancel the key run (D12) ------------------------


async def _key_run_in(
    h: Harness, fake: KeyFake, register: Any, state: str
) -> tuple[str, Run, list[tuple[str, str]]]:
    """An extracted thread whose key run is ``queued``, ``running`` (its model call hangs) or
    ``stopped``; returns the extract run id, the key run and the events seen from now on."""
    h.fake.queues = _filled()
    if state == "running":
        fake.hang = True
        register()
        extract = await h.manager.submit(
            h.thread_id,
            "extract",
            ExtractInput(pages=h.photos(2), existing_test_id=None, supersedes_attempt_id=None),
        )
        await asyncio.wait_for(fake.hanging.wait(), TIMEOUT)
        run_id = extract.id
    else:
        run_id, _ = await h.run(h.photos(2))
    (key_run,) = key_runs(h)
    if state == "stopped":
        await h.manager.stop(key_run.id)
    key_run = runs.get_run(h.conn, key_run.id)  # type: ignore[assignment]
    assert key_run is not None and key_run.status == state
    seen: list[tuple[str, str]] = []
    h.manager.events.add_listener(lambda e: seen.append((e["type"], e.get("run_id", ""))))
    return run_id, key_run, seen


def _ctx(h: Harness) -> Any:
    return SimpleNamespace(manager=h.manager)


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["queued", "running", "stopped"])
async def test_r22_6_4_6_extract_again_discards_the_key_run_and_goes_ahead(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    async with both_graphs(data, monkeypatch, grade=False) as (h, fake, register):
        run_id, key_run, seen = await _key_run_in(h, fake, register, state)
        fake.hang = False
        h.fake.queues = _filled()
        again = await thread_routes.extract_again(h.thread_id, h.conn, _ctx(h), None)
        assert again.kind == "extract" and again.id != run_id
        assert h.runs_status(key_run.id) == "discarded"
        assert ("run.discarded", key_run.id) in seen
        if state != "running":
            register()
        await asyncio.wait_for(h.manager.wait_idle(), TIMEOUT)
        assert h.runs_status(again.id) == "done"
        _assert_one_key_run_after(h, again.id)  # the new extraction queues its own


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["queued", "running", "stopped"])
async def test_r22_6_4_6_delete_thread_discards_the_key_run_and_deletes(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    async with both_graphs(data, monkeypatch, grade=False) as (h, fake, register):
        _run_id, key_run, seen = await _key_run_in(h, fake, register, state)
        await thread_routes.delete_thread(h.thread_id, h.conn, _ctx(h))
        assert ("run.discarded", key_run.id) in seen
        assert threads.get_thread(h.conn, h.thread_id) is None
        assert runs.list_runs(h.conn, thread_id=h.thread_id) == []


async def _other_run(h: Harness, other: str, extract_id: str) -> str:
    """Another unfinished run on the thread beside its queued key run: a normal grade (queued)
    or an extract (stopped)."""
    if other == "grade":
        att = attempts.find_by_source_run(h.conn, extract_id)
        assert att is not None
        inp = GradeInput(test_id=_test_id(h, extract_id), attempt_id=att.id, reason="button")
        return runs.create_run(h.conn, h.thread_id, "grade", inp).id
    inp_x = ExtractInput(pages=h.photos(1), existing_test_id=None, supersedes_attempt_id=None)
    return runs.create_run(h.conn, h.thread_id, "extract", inp_x, status="stopped").id


@pytest.mark.asyncio
@pytest.mark.parametrize("other", ["grade", "extract"])
async def test_r22_6_4_6_another_unfinished_run_still_gives_409(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch, other: str
) -> None:
    async with both_graphs(data, monkeypatch, grade=False) as (h, fake, register):
        run_id, key_run, seen = await _key_run_in(h, fake, register, "queued")
        other_id = await _other_run(h, other, run_id)
        for call in (
            thread_routes.extract_again(h.thread_id, h.conn, _ctx(h), None),
            thread_routes.delete_thread(h.thread_id, h.conn, _ctx(h)),
        ):
            with pytest.raises(HTTPException) as exc:
                await call
            assert exc.value.status_code == 409
            assert exc.value.detail == thread_routes.RUN_ACTIVE
        assert h.runs_status(key_run.id) == "queued"  # nothing was discarded
        assert h.runs_status(other_id) in ("queued", "stopped")
        assert not [e for e in seen if e[0] == "run.discarded"]
        assert threads.get_thread(h.conn, h.thread_id) is not None


@pytest.mark.asyncio
async def test_r22_6_4_6_a_409_for_the_mode_choice_discards_nothing(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with both_graphs(data, monkeypatch, grade=False) as (h, fake, register):
        run_id, key_run, _ = await _key_run_in(h, fake, register, "queued")
        other = threads.create_thread(h.conn, "other").id
        threads.set_test_id(h.conn, other, _test_id(h, run_id))
        with pytest.raises(HTTPException) as exc:
            await thread_routes.extract_again(h.thread_id, h.conn, _ctx(h), None)
        assert exc.value.detail == thread_routes.CHOOSE_MODE
        assert h.runs_status(key_run.id) == "queued"


def _extract_deps(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    import etach.graphs.extract as extract_graph

    seen: list[Any] = []
    real = extract_graph.register_extract
    monkeypatch.setattr(
        extract_graph, "register_extract", lambda m, deps: (seen.append(deps), real(m, deps))
    )
    return seen


@pytest.mark.asyncio
async def test_r22_6_4_6_etach_run_and_eval_queue_no_key_run(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    from etach import cli

    seen = _extract_deps(monkeypatch)
    async with cli._manager(data, None, "http://fake-ollama"):
        pass
    assert [d.key_after_extract for d in seen] == [False]


def test_r22_6_4_6_etach_serve_keeps_the_key_run(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    from etach.api.app import build_context

    seen = _extract_deps(monkeypatch)
    ctx = build_context(data, base_url="http://fake-ollama")
    try:
        assert [d.key_after_extract for d in seen] == [True]
    finally:
        ctx.close()


# --- R22.6.4.7: deleting a test or a student cancels the key run (D14) -------------------------


def _delete_call(h: Harness, what: str, extract_id: str) -> Any:
    """``DELETE /tests/{id}`` for the extracted test, or ``DELETE /students/{id}`` for a student
    the thread's attempt is set to (so the thread goes whole with the student)."""
    if what == "test":
        return test_routes.delete_test(_test_id(h, extract_id), h.conn, _ctx(h))
    att = attempts.find_by_source_run(h.conn, extract_id)
    assert att is not None
    student = students.get_student(h.conn, att.student_id) if att.student_id else None
    if student is None:
        student = students.create_student(h.conn, "Nguyễn Văn A", "nguyen van a")
        attempts.set_student(h.conn, att.id, student.id)
    return student_routes.delete_student(student.id, h.conn, _ctx(h))


@pytest.mark.asyncio
@pytest.mark.parametrize("what", ["test", "student"])
@pytest.mark.parametrize("state", ["queued", "running"])
async def test_r22_6_4_7_delete_discards_the_key_run_and_deletes(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch, state: str, what: str
) -> None:
    async with both_graphs(data, monkeypatch, grade=False) as (h, fake, register):
        run_id, key_run, seen = await _key_run_in(h, fake, register, state)
        test_id = _test_id(h, run_id)
        await _delete_call(h, what, run_id)
        assert ("run.discarded", key_run.id) in seen
        if what == "test":
            assert test_repo.get_test(h.conn, test_id) is None
        else:
            assert threads.get_thread(h.conn, h.thread_id) is None
            assert runs.list_runs(h.conn, thread_id=h.thread_id) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("what", ["test", "student"])
async def test_r22_6_4_7_another_unfinished_run_still_gives_409(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch, what: str
) -> None:
    async with both_graphs(data, monkeypatch, grade=False) as (h, fake, register):
        run_id, key_run, seen = await _key_run_in(h, fake, register, "queued")
        test_id = _test_id(h, run_id)
        other_id = await _other_run(h, "grade", run_id)
        with pytest.raises(HTTPException) as exc:
            await _delete_call(h, what, run_id)
        assert exc.value.status_code == 409
        assert exc.value.detail == thread_routes.RUN_ACTIVE
        assert h.runs_status(key_run.id) == "queued"  # nothing was discarded
        assert h.runs_status(other_id) == "queued"
        assert not [e for e in seen if e[0] == "run.discarded"]
        assert test_repo.get_test(h.conn, test_id) is not None
        assert threads.get_thread(h.conn, h.thread_id) is not None


# --- R22.6.4.3: the model and the generated files ------------------------------------------------


def _reason_enum(schema: dict[str, Any]) -> list[str]:
    return list(schema["properties"]["reason"]["enum"])


def test_r22_6_4_3_grade_input_reason_gains_after_extract() -> None:
    assert _reason_enum(GradeInput.model_json_schema()) == REASONS
    exported = json.loads((REPO / "sidecar" / "schema" / "GradeInput.json").read_text("utf-8"))
    assert _reason_enum(exported) == REASONS
    openapi = json.loads((REPO / "sidecar" / "schema" / "openapi.json").read_text("utf-8"))
    assert _reason_enum(openapi["components"]["schemas"]["GradeInput"]) == REASONS
    gen = "\n".join(p.read_text("utf-8") for p in (REPO / "app" / "src" / "gen").rglob("*.ts"))
    assert '"after_extract"' in gen


# --- R22.6.4.5: the docs -------------------------------------------------------------------------


def _version(doc: str) -> tuple[int, ...]:
    text = (REPO / "docs" / doc).read_text("utf-8")
    found = re.search(r"\| \*\*v(\d+)\.(\d+)(?:\.(\d+))?\*\* \|", text)
    assert found is not None, doc
    return tuple(int(x) for x in found.groups(default="0"))


def test_r22_6_4_5_the_docs_say_the_key_is_made_after_every_extraction() -> None:
    prd = (REPO / "docs" / "PRD.md").read_text("utf-8")
    # the initial plan's changelog rows moved to this record on 2026-11-09
    record = (REPO / "docs" / "initial-plan" / "changelogs.md").read_text("utf-8")
    assert _version("PRD.md") >= (9, 0, 0)  # a decision changed: a major bump
    # the v9.0 changelog row of step 22.6.4 (a later patch may sit above it)
    rows = [line for line in (prd + record).splitlines() if re.match(r"\| (\*\*)?v\d", line)]
    assert any("22.6.4" in row and "D4" in row for row in rows)
    for doc in ("data-model.md", "llm-design.md"):
        text = (REPO / "docs" / doc).read_text("utf-8")
        assert "after_extract" in text, doc
        # a changelog row of step 22.6.4 (a later step may bump the doc again, e.g. 22.6.5)
        rows = [line for line in (text + record).splitlines() if re.match(r"\| (\*\*)?v\d", line)]
        assert any("22.6.4" in row for row in rows), doc
    d2 = next(line for line in prd.splitlines() if line.startswith("| D2 |"))
    d16 = next(line for line in prd.splitlines() if line.startswith("| D16 |"))
    assert "Made after every extraction" in d2 and "Rev. v9.0" in d2
    assert "key run" in d16 and "rev. v9.0" in d16
    # The finished initial plan (moved to docs/initial-plan/) keeps its last "Based on" line; later
    # plans pin their own, so only the link to each doc is checked here.
    plan = (REPO / "docs" / "initial-plan" / "plan.md").read_text("utf-8")
    based_on = next(line for line in plan.splitlines() if line.startswith("| Based on |"))
    for doc in ("PRD.md", "data-model.md", "llm-design.md"):
        assert f"[`{doc}`](../{doc}) v" in based_on, doc
