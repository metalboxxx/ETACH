"""Step 22.1.3: run progress (llm-design §2 "Run progress", v4.20).

- :class:`RunProgress`: equal stage shares, the ``done/total`` inside a stage, skipped stages,
  never going down, 100 at the end;
- the toy graph with a stage table: ``run.step_started`` / ``run.progress`` carry the stage
  fields, ``run.done`` carries 100, and ``percent`` never goes down;
- R22.1.3.2 (runtime half): the step's token listener publishes ``run.progress`` with
  ``tokens`` and the step's ID; a Stop mid-call still cancels it;
- R22.1.3.3 (runtime half): ``progress_of`` for a stopped run, and after a restart (a new
  manager on the same database); after Resume the first event is not lower.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from support.toy_graph import TOY_STEPS, ToyOllama, ToyPrompts, ToyRecorder, toy_factory

from etach.llm.client import OllamaClient, token_listener
from etach.llm.config import default_config
from etach.runtime.events import Event
from etach.runtime.manager import RunManager
from etach.runtime.power import FakePower
from etach.runtime.steps import RunProgress, Stage, current_step_id
from etach.store import db
from etach.store.repos import runs

TOY_STAGES = (
    Stage("Getting ready", ("prepare",)),
    Stage("Reading pages", ("pages",)),
    Stage("Finishing", ("combine", "finish")),
)
PROGRESS_TYPES = ("run.step_started", "run.progress", "run.done")


def percents(events: list[Event]) -> list[int]:
    return [e["percent"] for e in events if e["type"] in PROGRESS_TYPES and "percent" in e]


# --- RunProgress ---------------------------------------------------------------------------------


def test_equal_stage_shares_and_counts_inside_a_stage() -> None:
    p = RunProgress(TOY_STAGES)
    assert p.fields() == {}
    p.enter("prepare")
    assert p.fields() == {"stage": 1, "stages": 3, "stage_label": "Getting ready", "percent": 0}
    p.enter("pages")
    assert p.percent == 33
    p.advance(1, 3)
    assert p.percent == 44  # (1 + 1/3) / 3
    p.advance(3, 3)
    assert p.percent == 66
    p.enter("combine")
    assert (p.stage, p.percent) == (3, 66)
    p.finish()
    assert p.fields()["percent"] == 100 and p.fields()["stage_label"] == "Finishing"


def test_a_skipped_stage_counts_as_done_and_percent_never_goes_down() -> None:
    p = RunProgress(TOY_STAGES)
    p.enter("prepare")
    p.enter("finish")  # "Reading pages" skipped
    assert (p.stage, p.percent) == (3, 66)
    p.enter("pages")  # an earlier stage's node: the stage stays
    assert p.fields()["stage_label"] == "Finishing"
    p.advance(1, 2)
    high = p.percent
    p.advance(0, 2)  # a count that starts again
    assert p.percent == high == 83
    p.advance(5, 0)  # no total: ignored
    p.enter("not-a-node")
    assert p.percent == high


def test_counts_are_clamped() -> None:
    p = RunProgress(TOY_STAGES)
    p.advance(1, 2)  # before any stage: ignored
    assert p.fields() == {}
    p.enter("pages")
    p.advance(7, 3)
    assert p.percent == 66


def test_no_stages_is_an_error() -> None:
    with pytest.raises(ValueError):
        RunProgress(())


# --- the toy graph with stages -------------------------------------------------------------------


async def _toy(make_toy: Any, on_call_token: Any = None, **client_kw: Any) -> Any:
    toy = await make_toy(on_call_token, register=False, start=False)
    client = OllamaClient(
        db.connect(toy.manager.db_path),
        default_config(),
        ToyPrompts(),
        base_url="http://fake-ollama",
        transport=toy.fake.transport,
        **client_kw,
    )
    toy.manager.register("extract", toy_factory(client, toy.recorder), stages=TOY_STAGES)
    await toy.manager.start()
    return toy


@pytest.mark.asyncio
async def test_events_carry_the_stage_fields_and_reach_100(make_toy: Any) -> None:
    toy = await _toy(make_toy)
    run = await toy.submit()
    await toy.idle()
    assert toy.run(run.id).status == "done"

    started = toy.of(run.id, "run.step_started")
    assert [(e["node"], e["stage"], e["stage_label"]) for e in started] == [
        (node, stage, TOY_STAGES[stage - 1].label)
        for node, _ in TOY_STEPS
        for stage in [next(i for i, s in enumerate(TOY_STAGES, 1) if node in s.nodes)]
    ]
    assert all(e["stages"] == 3 for e in started)
    counted = [e for e in toy.of(run.id, "run.progress") if "done" in e]
    assert [(e["done"], e["total"], e["percent"]) for e in counted] == [
        (1, 3, 44),
        (2, 3, 55),
        (3, 3, 66),
    ]
    got = percents(toy.of(run.id))
    assert got[0] >= 0 and got == sorted(got)
    [done] = toy.of(run.id, "run.done")
    assert done["percent"] == 100 and done["stage"] == 3
    assert run.id not in toy.manager._progress  # forgotten once done


@pytest.mark.asyncio
async def test_a_kind_without_stages_publishes_no_stage_fields(make_toy: Any) -> None:
    toy = await make_toy()
    run = await toy.submit()
    await toy.idle()
    for e in toy.of(run.id):
        assert "percent" not in e and "stage" not in e
    assert toy.manager.progress_of(toy.run(run.id), "pages") == {}


# --- R22.1.3.2 (runtime half) ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_token_listener_publishes_tokens_with_the_step_id(make_toy: Any) -> None:
    clock = [0.0]

    def tick(key: str, i: int) -> None:
        clock[0] += 1.0  # one second per streamed token: every toy call lasts > 12 s

    toy = await _toy(make_toy, tick, clock=lambda: clock[0], heartbeat_seconds=4.0)
    run = await toy.submit()
    await toy.idle()
    assert toy.run(run.id).status == "done"

    beats = [e for e in toy.of(run.id, "run.progress") if "tokens" in e]
    steps = {s.id: s for s in runs.list_steps(toy.conn, run.id)}
    by_step: dict[str, list[int]] = {}
    for e in beats:
        assert e["step_id"] in steps and e["node"] == steps[e["step_id"]].node
        assert e["stage_label"] and "done" not in e
        by_step.setdefault(e["step_id"], []).append(e["tokens"])
    assert len(by_step) == len(TOY_STEPS)
    for tokens in by_step.values():
        assert len(tokens) >= 2 and tokens == sorted(set(tokens))
    assert percents(toy.of(run.id)) == sorted(percents(toy.of(run.id)))


@pytest.mark.asyncio
async def test_outside_a_step_there_is_no_token_listener() -> None:
    assert token_listener.get() is None


@pytest.mark.asyncio
async def test_stop_mid_call_still_cancels_with_the_heartbeat(make_toy: Any) -> None:
    clock = [0.0]
    holder: dict[str, Any] = {}

    async def tick(key: str, i: int) -> None:
        clock[0] += 1.0
        if key == "pages|page 2" and i == 6 and "stopped" not in holder:
            holder["stopped"] = True
            holder["toy"].manager.request_stop(holder["run_id"])
            await asyncio.sleep(0)

    toy = await _toy(make_toy, tick, clock=lambda: clock[0], heartbeat_seconds=4.0)
    holder["toy"] = toy
    run = await toy.submit()
    holder["run_id"] = run.id
    await toy.idle()
    assert toy.run(run.id).status == "stopped"
    open_steps = [s for s in runs.list_steps(toy.conn, run.id) if s.status != "done"]
    assert [(s.node, s.item, s.status) for s in open_steps] == [("pages", "page 2", "incomplete")]
    calls = runs.list_llm_calls(toy.conn, open_steps[0].id)
    assert [c.status for c in calls] == ["cancelled"]


# --- R22.1.3.3 (runtime half): stopped, restarted, resumed ---------------------------------------


async def _stop_at_page_3(make_toy: Any) -> tuple[Any, str, int]:
    holder: dict[str, Any] = {}

    async def on_token(key: str, i: int) -> None:
        if key == "pages|page 3" and i == 2 and "stopped" not in holder:
            holder["stopped"] = True
            holder["toy"].manager.request_stop(holder["run_id"])
            await asyncio.sleep(0)

    toy = await _toy(make_toy, on_token)
    holder["toy"] = toy
    run = await toy.submit()
    holder["run_id"] = run.id
    await toy.idle()
    assert toy.run(run.id).status == "stopped"
    shown = percents(toy.of(run.id))[-1]
    return toy, run.id, shown


@pytest.mark.asyncio
async def test_a_stopped_run_keeps_its_progress_and_resume_continues(make_toy: Any) -> None:
    toy, run_id, shown = await _stop_at_page_3(make_toy)
    assert shown == 55  # page 2 of 3 done
    latest = runs.latest_step(toy.conn, run_id)
    assert latest is not None
    assert toy.manager.progress_of(toy.run(run_id), latest.node) == {
        "stage": 2,
        "stages": 3,
        "stage_label": "Reading pages",
        "percent": shown,
    }

    before = len(toy.log)
    await toy.manager.resume(run_id)
    await toy.idle()
    after = percents([e for e in toy.log[before:] if e["run_id"] == run_id])
    assert after[0] >= shown and after == sorted(after) and after[-1] == 100
    assert toy.run(run_id).status == "done"


@pytest.mark.asyncio
async def test_after_a_restart_progress_is_seeded_from_the_latest_step(
    make_toy: Any, db_path: Any
) -> None:
    toy, run_id, shown = await _stop_at_page_3(make_toy)
    await toy.manager.aclose()

    # a new process: nothing in memory, the stage comes from the latest step
    fake = ToyOllama()
    manager = RunManager(db_path, power=FakePower())
    client_conn = db.connect(db_path)
    try:
        client = OllamaClient(
            client_conn,
            default_config(),
            ToyPrompts(),
            base_url="http://fake-ollama",
            transport=fake.transport,
        )
        manager.register("extract", toy_factory(client, ToyRecorder()), stages=TOY_STAGES)
        await manager.start()
        log: list[Event] = []
        manager.events.add_listener(log.append)
        run = toy.run(run_id)
        seeded = manager.progress_of(run, "pages")
        assert seeded == {
            "stage": 2,
            "stages": 3,
            "stage_label": "Reading pages",
            "percent": 33,  # the start of the stage: the count is not stored
        }
        assert seeded["percent"] <= shown
        await manager.resume(run_id)
        await asyncio.wait_for(manager.wait_idle(), 30)
        got = percents([e for e in log if e.get("run_id") == run_id])
        assert got[0] >= seeded["percent"] and got == sorted(got) and got[-1] == 100
    finally:
        await manager.aclose()
        client_conn.close()


@pytest.mark.asyncio
async def test_current_step_id_is_unchanged_by_the_listener(make_toy: Any) -> None:
    """The listener is set and reset around each step, like the step ID."""
    seen: list[tuple[str, bool]] = []

    toy = await _toy(make_toy)
    remove = toy.events.add_listener(
        lambda e: (
            seen.append((e["type"], token_listener.get() is not None))
            if e["type"] == "run.step_started"
            else None
        )
    )
    run = await toy.submit()
    await toy.idle()
    remove()
    assert seen and all(has for _, has in seen)
    assert token_listener.get() is None
    with pytest.raises(RuntimeError):
        current_step_id()
    assert toy.run(run.id).status == "done"
