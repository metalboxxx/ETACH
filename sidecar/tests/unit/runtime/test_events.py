"""The in-process event bus."""

from __future__ import annotations

from typing import Any

import pytest

from etach.runtime.events import RUN_EVENT_TYPES, EventBus


@pytest.mark.asyncio
async def test_subscribers_and_listeners_get_events_in_order() -> None:
    bus = EventBus()
    sub = bus.subscribe()
    heard: list[dict[str, Any]] = []
    remove = bus.add_listener(heard.append)

    first = bus.publish("run.queued", "r1", "t1")
    bus.publish("run.step_started", "r1", "t1", step_id="s1", node="n", item=None, try_no=1)
    remove()
    bus.publish("run.done", "r1", "t1")
    sub.close()

    assert first == {"type": "run.queued", "run_id": "r1", "thread_id": "t1"}
    got = [e async for e in sub]
    assert [e["type"] for e in got] == ["run.queued", "run.step_started", "run.done"]
    assert got[1]["node"] == "n" and got[1]["try_no"] == 1
    assert [e["type"] for e in heard] == ["run.queued", "run.step_started"]


@pytest.mark.asyncio
async def test_late_and_closed_subscribers() -> None:
    bus = EventBus()
    bus.publish("run.queued", "r1", "t1")
    late = bus.subscribe()
    assert late.get_nowait() is None
    bus.publish("run.done", "r1", "t1")
    assert (await late.get())["type"] == "run.done"
    late.close()
    bus.publish("run.failed", "r1", "t1", error="x")
    with pytest.raises(StopAsyncIteration):
        await late.get()


def test_event_types_match_llm_design() -> None:
    assert set(RUN_EVENT_TYPES) == {
        "run.queued",
        "run.step_started",
        "run.step_done",
        "run.progress",
        "run.done",
        "run.failed",
        "run.stopped",
        "run.interrupted",
        "run.discarded",
    }
