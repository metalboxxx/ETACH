"""Step 12 additions to the run manager: ``run.discarded`` and :meth:`RunManager.poke` (runs
queued in the database by a Review resolution are picked up)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from support.toy_graph import toy_input

from etach.store.repos import runs


@pytest.mark.asyncio
async def test_discard_queued_run_publishes_run_discarded(make_toy: Any) -> None:
    toy = await make_toy(register=False)
    run = await toy.submit()
    discarded = await toy.manager.discard(run.id)
    assert discarded.status == "discarded"
    assert [e["type"] for e in toy.of(run.id)] == ["run.queued", "run.discarded"]
    assert toy.of(run.id, "run.discarded")[0]["thread_id"] == toy.thread_id


@pytest.mark.asyncio
async def test_discard_running_run_publishes_run_discarded(make_toy: Any) -> None:
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
    types = [e["type"] for e in toy.of(run.id)]
    assert types[-1] == "run.discarded"
    assert types.count("run.discarded") == 1
    assert "run.done" not in types


@pytest.mark.asyncio
async def test_poke_picks_up_runs_queued_in_the_database(make_toy: Any) -> None:
    toy = await make_toy()
    # What runs.enqueue_extract does after a Review resolution: only the row is written.
    row_id = runs.enqueue_extract(toy.conn, thread_id=toy.thread_id, input=toy_input())
    await toy.idle()
    assert toy.run(row_id).status == "queued"  # not seen yet
    assert toy.of(row_id) == []

    added = await toy.manager.poke()
    assert added == [row_id]
    assert await toy.manager.poke() == []  # idempotent: already queued or running
    await toy.idle()

    assert toy.run(row_id).status == "done"
    types = [e["type"] for e in toy.of(row_id)]
    assert types[0] == "run.queued" and types.count("run.queued") == 1
    assert types[-1] == "run.done"


@pytest.mark.asyncio
async def test_poke_does_not_duplicate_submitted_runs(make_toy: Any) -> None:
    toy = await make_toy(register=False)
    a = await toy.submit()
    b_id = runs.enqueue_extract(toy.conn, thread_id=toy.thread_id, input=toy_input())
    assert await toy.manager.poke() == [b_id]
    assert toy.manager.queued_run_ids() == [a.id, b_id]
    assert len(toy.of(a.id, "run.queued")) == 1
