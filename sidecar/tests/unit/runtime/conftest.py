"""Fixtures for the runtime tests: a migrated ``app.db``, and a started run manager with the toy
graph registered for ``extract`` (``make_toy``)."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from support.toy_graph import ToyOllama, ToyRecorder, make_client, toy_factory, toy_input

from etach.domain.models import Run
from etach.runtime.events import Event, EventBus
from etach.runtime.manager import RunManager
from etach.runtime.power import FakePower
from etach.store import db
from etach.store.repos import runs, threads

RUN_TIMEOUT = 30.0


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "data" / "app.db"
    db.open_database(path).close()
    return path


@pytest.fixture
def conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    c = db.connect(db_path)
    yield c
    c.close()


@dataclass
class Toy:
    manager: RunManager
    fake: ToyOllama
    recorder: ToyRecorder
    power: FakePower
    events: EventBus
    thread_id: str
    conn: sqlite3.Connection
    log: list[Event] = field(default_factory=list)

    async def submit(self, kind: str = "extract") -> Run:
        return await self.manager.submit(self.thread_id, kind, toy_input())  # type: ignore[arg-type]

    async def idle(self) -> None:
        await asyncio.wait_for(self.manager.wait_idle(), RUN_TIMEOUT)

    def run(self, run_id: str) -> Run:
        run = runs.get_run(self.conn, run_id)
        assert run is not None
        return run

    def of(self, run_id: str, *types: str) -> list[Event]:
        return [e for e in self.log if e["run_id"] == run_id and (not types or e["type"] in types)]


MakeToy = Callable[..., Any]


@pytest_asyncio.fixture
async def make_toy(db_path: Path, conn: sqlite3.Connection) -> AsyncIterator[MakeToy]:
    """``await make_toy(on_call_token=None, start=True)`` → a :class:`Toy`; closed at teardown."""
    made: list[tuple[RunManager, sqlite3.Connection]] = []

    async def make(
        on_call_token: Any = None,
        *,
        drops: dict[str, int] | None = None,
        start: bool = True,
        register: bool = True,
    ) -> Toy:
        fake = ToyOllama(on_call_token=on_call_token, drops=drops)
        recorder = ToyRecorder()
        power = FakePower()
        events = EventBus()
        manager = RunManager(db_path, events=events, power=power)
        client_conn = db.connect(db_path)
        if register:
            manager.register("extract", toy_factory(make_client(client_conn, fake), recorder))
        thread_id = threads.create_thread(conn, "toy").id
        toy = Toy(manager, fake, recorder, power, events, thread_id, conn)
        events.add_listener(toy.log.append)
        made.append((manager, client_conn))
        if start:
            await manager.start()
        return toy

    yield make
    for manager, client_conn in made:
        await manager.aclose()
        client_conn.close()
