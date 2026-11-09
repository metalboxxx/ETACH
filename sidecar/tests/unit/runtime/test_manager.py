"""The run manager over the toy graph: stop/resume at every boundary and mid-call (R7.1), the
queue and the registry (R7.4), discard and purge (R7.5), keep-awake (R7.6), cancelled calls are
never reused (R7.7), dropped streams (R7.8) and the event order (R7.10)."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections import Counter
from typing import Any

import pytest
from support.toy_graph import TOY_STEPS, ToyOut, answer_tokens, toy_input

from etach.runtime import checkpoint
from etach.runtime.manager import InvalidRunState
from etach.runtime.steps import step
from etach.store.repos import runs


def steps_of(conn: sqlite3.Connection, run_id: str) -> list[Any]:
    return runs.list_steps(conn, run_id)


def calls_of(conn: sqlite3.Connection, run_id: str) -> list[Any]:
    return [c for s in steps_of(conn, run_id) for c in runs.list_llm_calls(conn, s.id)]


def domain_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Row counts of every app table except the run log (runs, steps, llm_calls, threads)."""
    skip = {"runs", "steps", "llm_calls", "threads", "schema_migrations", "checkpoints", "writes"}
    names = [
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        if r[0] not in skip and not r[0].startswith(("sqlite_", "tests_fts_"))
    ]
    return {n: conn.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for n in names}


def summary(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    steps = steps_of(conn, run_id)
    calls = calls_of(conn, run_id)
    return {
        "done_steps": sorted(
            ((s.node, s.item or "") for s in steps if s.status == "done"), key=str
        ),
        "steps_by_status": Counter(s.status for s in steps),
        "calls_by_status": Counter(c.status for c in calls),
        "checkpoint_rows": checkpoint.checkpoint_row_count(conn, run_id),
    }


async def baseline(make_toy: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    toy = await make_toy()
    run = await toy.submit()
    await toy.idle()
    assert toy.run(run.id).status == "done"
    return toy.recorder.final[run.id], summary(toy.conn, run.id), domain_counts(toy.conn)


# --- R7.1 ------------------------------------------------------------------------------------

CASES = [("boundary", i) for i in range(len(TOY_STEPS))] + [
    ("mid_call", i) for i in range(len(TOY_STEPS))
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("where", "index"), CASES, ids=[f"{w}-{i}" for w, i in CASES])
async def test_r7_1_stop_and_resume_equals_uninterrupted(
    make_toy: Any, where: str, index: int
) -> None:
    final0, sum0, domain0 = await baseline(make_toy)
    node, item = TOY_STEPS[index]
    key = f"{node}|{item}"
    fired: list[str] = []
    holder: dict[str, Any] = {}

    async def on_token(call_key: str, i: int) -> None:
        if where == "mid_call" and call_key == key and i == 2 and not fired:
            fired.append(call_key)
            holder["toy"].manager.request_stop(holder["run_id"])
            await asyncio.sleep(0)  # the cancellation lands inside the stream

    toy = await make_toy(on_token)
    holder["toy"] = toy

    def at_boundary(event: dict[str, Any]) -> None:
        if (
            where == "boundary"
            and event["type"] == "run.step_started"
            and (event["node"], event["item"]) == (node, item)
            and not fired
        ):
            fired.append(key)
            toy.manager.request_stop(event["run_id"])

    toy.events.add_listener(at_boundary)
    run = await toy.submit()
    holder["run_id"] = run.id
    await toy.idle()

    assert fired == [key]
    assert toy.run(run.id).status == "stopped"
    assert [e["type"] for e in toy.of(run.id, "run.stopped")] == ["run.stopped"]
    assert checkpoint.checkpoint_row_count(toy.conn, run.id) > 0
    open_steps = [s for s in steps_of(toy.conn, run.id) if s.status != "done"]
    assert [(s.node, s.item, s.status, s.try_no) for s in open_steps] == [
        (node, item, "incomplete", 1)
    ]

    await toy.manager.resume(run.id)
    await toy.idle()

    assert toy.run(run.id).status == "done"
    assert toy.recorder.final[run.id] == final0
    got = summary(toy.conn, run.id)
    assert got["done_steps"] == sum0["done_steps"]
    assert got["checkpoint_rows"] == sum0["checkpoint_rows"] == 0
    assert got["calls_by_status"]["complete"] == sum0["calls_by_status"]["complete"] == 6
    extra_calls = got["calls_by_status"] - sum0["calls_by_status"]
    assert extra_calls == (Counter({"cancelled": 1}) if where == "mid_call" else Counter())
    assert got["steps_by_status"] - sum0["steps_by_status"] == Counter({"incomplete": 1})
    assert domain_counts(toy.conn) == domain0
    for s in steps_of(toy.conn, run.id):
        if s.status == "done":
            assert s.try_no == (2 if (s.node, s.item) == (node, item) else 1), s


# --- R7.4 ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r7_4_one_run_at_a_time_fifo(make_toy: Any) -> None:
    toy = await make_toy()
    seen: list[tuple[str, str]] = []  # (event, status of the other run)
    ids: list[str] = []

    def watch(event: dict[str, Any]) -> None:
        if event["type"] == "run.step_started" and len(ids) == 2:
            other = ids[1] if event["run_id"] == ids[0] else ids[0]
            seen.append((event["run_id"], toy.run(other).status))

    toy.events.add_listener(watch)
    first = await toy.submit()
    second = await toy.submit()
    ids += [first.id, second.id]
    await toy.idle()

    assert toy.run(first.id).status == toy.run(second.id).status == "done"
    first_steps = [s for r, s in seen if r == first.id]
    second_steps = [s for r, s in seen if r == second.id]
    assert first_steps and set(first_steps) == {"queued"}
    assert second_steps and set(second_steps) == {"done"}
    order = [(e["run_id"], e["type"]) for e in toy.log if e["type"] in ("run.done",)]
    assert order == [(first.id, "run.done"), (second.id, "run.done")]
    done_first = toy.log.index(toy.of(first.id, "run.done")[0])
    start_second = toy.log.index(toy.of(second.id, "run.step_started")[0])
    assert done_first < start_second


@pytest.mark.asyncio
async def test_r7_4_unregistered_kind_stays_queued(make_toy: Any) -> None:
    toy = await make_toy()
    grade = await toy.submit("grade")  # no grade graph registered
    extract = await toy.submit("extract")
    await toy.idle()

    assert toy.run(grade.id).status == "queued"
    assert toy.run(grade.id).error is None
    assert toy.run(extract.id).status == "done"
    assert toy.manager.queued_run_ids() == [grade.id]
    assert [e["type"] for e in toy.of(grade.id)] == ["run.queued"]


# --- R7.5 ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r7_5_discard_purges_checkpoint_keeps_calls(make_toy: Any) -> None:
    holder: dict[str, Any] = {}

    async def on_token(call_key: str, i: int) -> None:
        if call_key == "pages|page 2" and i == 1 and "stopped" not in holder:
            holder["stopped"] = True
            holder["toy"].manager.request_stop(holder["run_id"])
            await asyncio.sleep(0)

    toy = await make_toy(on_token)
    holder["toy"] = toy
    run = await toy.submit()
    holder["run_id"] = run.id
    await toy.idle()
    assert toy.run(run.id).status == "stopped"
    calls_before = [(c.id, c.status) for c in calls_of(toy.conn, run.id)]
    assert checkpoint.checkpoint_row_count(toy.conn, run.id) > 0

    discarded = await toy.manager.discard(run.id)

    assert discarded.status == "discarded" and discarded.finished_at is not None
    assert checkpoint.checkpoint_row_count(toy.conn, run.id) == 0
    assert [(c.id, c.status) for c in calls_of(toy.conn, run.id)] == calls_before
    assert ("cancelled" in {s for _, s in calls_before}) is True
    with pytest.raises(InvalidRunState):
        await toy.manager.resume(run.id)


@pytest.mark.asyncio
async def test_r7_5_done_purges_checkpoint(make_toy: Any) -> None:
    toy = await make_toy()
    run = await toy.submit()
    await toy.idle()
    done = toy.run(run.id)
    assert done.status == "done" and done.finished_at is not None and done.started_at
    assert checkpoint.checkpoint_row_count(toy.conn, run.id) == 0
    assert len(calls_of(toy.conn, run.id)) == 6


@pytest.mark.asyncio
async def test_discard_running_run(make_toy: Any) -> None:
    holder: dict[str, Any] = {}

    async def on_token(call_key: str, i: int) -> None:
        if call_key == "combine|None" and i == 1 and "discard" not in holder:
            holder["discard"] = asyncio.ensure_future(
                holder["toy"].manager.discard(holder["run_id"])
            )
            await asyncio.sleep(0)

    toy = await make_toy(on_token)
    holder["toy"] = toy
    run = await toy.submit()
    holder["run_id"] = run.id
    await toy.idle()
    await holder["discard"]

    assert toy.run(run.id).status == "discarded"
    assert checkpoint.checkpoint_row_count(toy.conn, run.id) == 0
    assert "cancelled" in {c.status for c in calls_of(toy.conn, run.id)}
    assert {s.status for s in steps_of(toy.conn, run.id)} <= {"done", "incomplete"}
    assert toy.power.keep_awake is False
    assert toy.power.changes == [True, False]


# --- R7.6 ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r7_6_keep_awake_on_running_off_on_done(make_toy: Any) -> None:
    toy = await make_toy()
    during: list[bool] = []
    toy.events.add_listener(
        lambda e: during.append(toy.power.keep_awake) if e["type"] == "run.step_started" else None
    )
    run = await toy.submit()
    assert toy.power.keep_awake is False  # queued, not yet running
    await toy.idle()
    assert toy.run(run.id).status == "done"
    assert during == [True] * 6
    assert toy.power.keep_awake is False
    assert toy.power.changes == [True, False]


@pytest.mark.asyncio
async def test_r7_6_keep_awake_off_on_stop(make_toy: Any) -> None:
    toy = await make_toy()
    toy.events.add_listener(
        lambda e: (
            toy.manager.request_stop(e["run_id"])
            if e["type"] == "run.step_started" and e["node"] == "combine"
            else None
        )
    )
    run = await toy.submit()
    await toy.idle()
    assert toy.run(run.id).status == "stopped"
    assert toy.power.keep_awake is False
    assert toy.power.changes == [True, False]


@pytest.mark.asyncio
async def test_r7_6_keep_awake_off_on_failure(make_toy: Any) -> None:
    from langgraph.graph import END, START, StateGraph

    toy = await make_toy(register=False, start=False)

    async def boom(state: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("toy failure")

    def factory(saver: Any) -> Any:
        b: StateGraph[Any, Any, Any, Any] = StateGraph(dict)
        b.add_node("boom", step("boom", boom))
        b.add_edge(START, "boom")
        b.add_edge("boom", END)
        return b.compile(checkpointer=saver)

    toy.manager.register("extract", factory)
    await toy.manager.start()
    run = await toy.submit()
    await toy.idle()

    failed = toy.run(run.id)
    assert failed.status == "failed"
    assert failed.error == "ValueError: toy failure" and failed.finished_at is not None
    assert [s.status for s in steps_of(toy.conn, run.id)] == ["failed"]
    assert [e["type"] for e in toy.of(run.id)][-2:] == ["run.step_done", "run.failed"]
    assert toy.of(run.id, "run.failed")[0]["error"] == "ValueError: toy failure"
    assert toy.power.keep_awake is False
    assert toy.power.changes == [True, False]


# --- R7.7 ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r7_7_cancelled_valid_json_is_not_used(make_toy: Any) -> None:
    last = len(answer_tokens("combine", {"item": None})) - 1  # the trailing whitespace token
    holder: dict[str, Any] = {}

    async def on_token(call_key: str, i: int) -> None:
        if call_key == "combine|None" and i == last and "stopped" not in holder:
            holder["stopped"] = True
            holder["toy"].manager.request_stop(holder["run_id"])
            await asyncio.sleep(0)

    toy = await make_toy(on_token)
    holder["toy"] = toy
    run = await toy.submit()
    holder["run_id"] = run.id
    await toy.idle()
    assert toy.run(run.id).status == "stopped"
    [cancelled] = [c for c in calls_of(toy.conn, run.id) if c.status == "cancelled"]
    ToyOut.model_validate_json(cancelled.response_text)  # valid JSON, yet not a result
    combine_requests = toy.fake.keys.count("combine|None")
    assert combine_requests == 1

    await toy.manager.resume(run.id)
    await toy.idle()

    assert toy.run(run.id).status == "done"
    assert toy.fake.keys.count("combine|None") == combine_requests + 1
    combine_steps = [s for s in steps_of(toy.conn, run.id) if s.node == "combine"]
    assert [(s.try_no, s.status) for s in combine_steps] == [(1, "incomplete"), (2, "done")]
    [used] = [c for c in runs.list_llm_calls(toy.conn, combine_steps[1].id)]
    assert used.status == "complete" and used.id != cancelled.id
    assert json.loads(used.response_text) == json.loads(cancelled.response_text)


# --- R7.8 ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r7_8_stream_dropped_interrupts_and_resume_completes(make_toy: Any) -> None:
    toy = await make_toy(drops={"pages|page 3": 2})
    run = await toy.submit()
    await toy.idle()

    interrupted = toy.run(run.id)
    assert interrupted.status == "interrupted" and interrupted.error is None
    assert [e["type"] for e in toy.of(run.id)][-1] == "run.interrupted"
    page3 = [s for s in steps_of(toy.conn, run.id) if s.item == "page 3"]
    assert [(s.try_no, s.status) for s in page3] == [(1, "incomplete")]
    assert [c.status for c in runs.list_llm_calls(toy.conn, page3[0].id)] == ["error", "error"]
    assert toy.power.keep_awake is False

    await toy.manager.resume(run.id)
    await toy.idle()

    assert toy.run(run.id).status == "done"
    page3 = [s for s in steps_of(toy.conn, run.id) if s.item == "page 3"]
    assert [(s.try_no, s.status) for s in page3] == [(1, "incomplete"), (2, "done")]
    assert checkpoint.checkpoint_row_count(toy.conn, run.id) == 0


# --- R7.10 -----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r7_10_event_order(make_toy: Any) -> None:
    toy = await make_toy()
    sub = toy.events.subscribe()
    run = await toy.submit()
    await toy.idle()
    sub.close()
    events = [e async for e in sub]

    assert all(e["run_id"] == run.id and e["thread_id"] == toy.thread_id for e in events)
    lifecycle = [e for e in events if e["type"] != "run.progress"]
    expected = ["run.queued"]
    for _ in TOY_STEPS:
        expected += ["run.step_started", "run.step_done"]
    expected.append("run.done")
    assert [e["type"] for e in lifecycle] == expected
    pairs = lifecycle[1:-1]
    step_pairs = list(zip(pairs[::2], pairs[1::2], strict=True))
    for (node, item), (started, done) in zip(TOY_STEPS, step_pairs, strict=True):
        assert (started["node"], started["item"], started["try_no"]) == (node, item, 1)
        assert started["step_id"] == done["step_id"] and done["status"] == "done"
    # counts only: since v4.24 a model call also beats (``tokens``) from its start
    progress = [e for e in events if e["type"] == "run.progress" and "done" in e]
    assert [(p["done"], p["total"], p["item"]) for p in progress] == [
        (1, 3, "page 1"),
        (2, 3, "page 2"),
        (3, 3, "page 3"),
    ]
    # inside its step's started/done pair (token beats of the same step may sit in between)
    steps_only = [e for e in events if not (e["type"] == "run.progress" and "tokens" in e)]
    for p in progress:
        i = steps_only.index(p)
        assert steps_only[i - 1]["type"] == "run.step_started"
        assert steps_only[i + 1]["type"] == "run.step_done"
        assert steps_only[i - 1]["step_id"] == p["step_id"]
    beats = [e for e in events if e["type"] == "run.progress" and "tokens" in e]
    started_ids = {e["step_id"] for e in events if e["type"] == "run.step_started"}
    assert all(b["step_id"] in started_ids for b in beats)


# --- other transitions -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_queued_run_and_invalid_actions(make_toy: Any) -> None:
    toy = await make_toy(register=False)
    run = await toy.submit()
    await toy.idle()
    assert toy.run(run.id).status == "queued"

    stopped = await toy.manager.stop(run.id)
    assert stopped.status == "stopped"
    assert [e["type"] for e in toy.of(run.id)] == ["run.queued", "run.stopped"]
    with pytest.raises(InvalidRunState):
        await toy.manager.stop(run.id)
    await toy.manager.resume(run.id)
    assert toy.run(run.id).status == "queued"
    assert toy.manager.queued_run_ids() == [run.id]
    with pytest.raises(InvalidRunState):
        await toy.manager.resume(run.id)
    with pytest.raises(InvalidRunState):
        await toy.manager.resume("no-such-run")


@pytest.mark.asyncio
async def test_register_later_runs_waiting_run(make_toy: Any) -> None:
    from support.toy_graph import make_client, toy_factory

    toy = await make_toy(register=False)
    run = await toy.submit()
    await toy.idle()
    assert toy.run(run.id).status == "queued"
    toy.manager.register("extract", toy_factory(make_client(toy.conn, toy.fake), toy.recorder))
    await toy.idle()
    assert toy.run(run.id).status == "done"


@pytest.mark.asyncio
async def test_shutdown_marks_running_run_interrupted(make_toy: Any) -> None:
    holder: dict[str, Any] = {}
    reached = asyncio.Event()

    async def on_token(call_key: str, i: int) -> None:
        if call_key == "pages|page 1" and i == 1:
            reached.set()
            await asyncio.Event().wait()

    toy = await make_toy(on_token)
    holder["toy"] = toy
    run = await toy.submit()
    await asyncio.wait_for(reached.wait(), 30)
    await toy.manager.aclose()

    assert toy.run(run.id).status == "interrupted"
    assert [e["type"] for e in toy.of(run.id)][-1] == "run.interrupted"
    assert {c.status for c in calls_of(toy.conn, run.id)} == {"complete", "cancelled"}
    assert toy.power.keep_awake is False


@pytest.mark.asyncio
async def test_resume_without_checkpoint_starts_fresh(make_toy: Any) -> None:
    from support.toy_graph import make_client, toy_factory

    final0, _, _ = await baseline(make_toy)
    toy = await make_toy(register=False)
    run = await toy.manager.submit(toy.thread_id, "extract", toy_input())
    await toy.manager.stop(run.id)  # stopped while queued: no checkpoint yet
    assert checkpoint.checkpoint_row_count(toy.conn, run.id) == 0
    toy.manager.register("extract", toy_factory(make_client(toy.conn, toy.fake), toy.recorder))
    await toy.manager.resume(run.id)
    await toy.idle()
    assert toy.run(run.id).status == "done"
    assert toy.recorder.final[run.id] == final0
