"""The checkpointer in app.db: setup, pragmas, purge, and 1,000 checkpoint writes interleaved
with app writes without ``database is locked`` (R7.9)."""

from __future__ import annotations

import asyncio
import operator
import sqlite3
import threading
import time
from pathlib import Path
from typing import Annotated, Any, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph

from etach.runtime import checkpoint
from etach.store import db
from etach.store.repos import threads


@pytest.mark.asyncio
async def test_tables_live_in_app_db_with_wal_and_busy_timeout(db_path: Path) -> None:
    async with checkpoint.open_checkpointer(db_path) as saver:
        async with saver.conn.execute("PRAGMA busy_timeout") as cur:
            assert (await cur.fetchone())[0] == db.BUSY_TIMEOUT_MS  # type: ignore[index]
        async with saver.conn.execute("PRAGMA journal_mode") as cur:
            assert (await cur.fetchone())[0] == "wal"  # type: ignore[index]
    conn = db.connect(db_path)
    try:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"checkpoints", "writes", "runs", "steps", "llm_calls"} <= names
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == db.BUSY_TIMEOUT_MS
    finally:
        conn.close()


class Tick(TypedDict):
    n: int
    seen: Annotated[list[int], operator.add]


def _tick_graph(saver: Any, on_tick: Any, limit: int) -> Any:
    async def tick(state: Tick) -> dict[str, Any]:
        await on_tick(state["n"])
        return {"n": state["n"] + 1, "seen": [state["n"]]}

    b: StateGraph[Any, Any, Any, Any] = StateGraph(Tick)
    b.add_node("tick", tick)
    b.add_edge(START, "tick")
    b.add_conditional_edges("tick", lambda s: "tick" if s["n"] < limit else END, ["tick", END])
    return b.compile(checkpointer=saver)


@pytest.mark.asyncio
async def test_r7_9_checkpoint_writes_interleaved_with_app_writes(db_path: Path) -> None:
    locked: list[str] = []
    app_writes = 0
    stop = threading.Event()

    def app_writer() -> None:
        nonlocal app_writes
        c = db.connect(db_path)
        try:
            while not stop.is_set():
                try:
                    threads.create_thread(c, "background")
                    time.sleep(0.001)  # an app write about every millisecond
                    app_writes += 1
                except sqlite3.OperationalError as exc:
                    locked.append(str(exc))
        finally:
            c.close()

    node_conn = db.connect(db_path)
    writer = threading.Thread(target=app_writer)
    writes = {"aput": 0, "aput_writes": 0}
    async with checkpoint.open_checkpointer(db_path) as saver:
        for name in writes:
            original = getattr(saver, name)

            def counted(*args: Any, _orig: Any = original, _name: str = name, **kw: Any) -> Any:
                writes[_name] += 1
                return _orig(*args, **kw)

            setattr(saver, name, counted)

        async def on_tick(n: int) -> None:  # an app write inside every node, too
            try:
                await asyncio.to_thread(threads.create_thread, node_conn, f"tick {n}")
            except sqlite3.OperationalError as exc:
                locked.append(str(exc))

        graph = _tick_graph(saver, on_tick, limit=500)
        writer.start()
        try:
            out = await graph.ainvoke(
                {"n": 0, "seen": []},
                checkpoint.run_config("r79", recursion_limit=2000),
                durability=checkpoint.DURABILITY,
            )
        finally:
            stop.set()
            await asyncio.to_thread(writer.join)
        node_conn.close()
        total = writes["aput"] + writes["aput_writes"]
        reader = db.connect(db_path)
        rows = checkpoint.checkpoint_row_count(reader, "r79")
        reader.close()
        await checkpoint.purge(saver, "r79")

    assert out["n"] == 500 and out["seen"] == list(range(500))
    assert total >= 1000, writes
    assert rows >= 1000
    assert app_writes > 0
    assert locked == []


@pytest.mark.asyncio
async def test_purge_and_has_checkpoint(db_path: Path) -> None:
    async def nothing(n: int) -> None:
        return None

    async with checkpoint.open_checkpointer(db_path) as saver:
        graph = _tick_graph(saver, nothing, limit=3)
        assert not await checkpoint.has_checkpoint(saver, "a")
        await graph.ainvoke({"n": 0, "seen": []}, checkpoint.run_config("a"), durability="sync")
        await graph.ainvoke({"n": 0, "seen": []}, checkpoint.run_config("b"), durability="sync")
        assert await checkpoint.has_checkpoint(saver, "a")
        await checkpoint.purge(saver, "a")
        assert not await checkpoint.has_checkpoint(saver, "a")
        assert await checkpoint.has_checkpoint(saver, "b")
    conn = db.connect(db_path)
    try:
        assert checkpoint.checkpoint_row_count(conn, "a") == 0
        assert checkpoint.checkpoint_row_count(conn, "b") > 0
    finally:
        conn.close()


def test_row_count_without_tables(conn: sqlite3.Connection) -> None:
    assert checkpoint.checkpoint_row_count(conn, "x") == 0
