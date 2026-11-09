"""Fixtures for the API tests: a migrated data folder, an :class:`AppContext` replaying the ``s1``
cassettes, and a real uvicorn server on 127.0.0.1 in the test's event loop (SSE needs a real
socket: httpx's ASGI transport buffers the whole response)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from support.reader import vision_reader

from etach.api.app import bind_socket, build_context, create_app
from etach.api.deps import AppContext
from etach.appdir import DataPaths
from etach.llm.cassettes import ReplayBackend
from etach.runtime.power import FakePower
from etach.store import db

SIDECAR = Path(__file__).resolve().parents[3]
S1 = SIDECAR / "tests" / "cassettes" / "s1"
TIMEOUT = 60.0


@pytest.fixture
def paths(tmp_path: Path) -> DataPaths:
    p = DataPaths((tmp_path / "data").resolve()).ensure()
    db.open_database(p.db).close()
    return p


@pytest.fixture
def make_ctx(paths: DataPaths) -> Callable[..., AppContext]:
    def make(**kw: Any) -> AppContext:
        if kw.pop("vision_reader", True):
            # the s1 cassettes were recorded with the vision photo reader (R22.5.7.7);
            # ``vision_reader=False`` keeps the data folder empty (the defaults)
            vision_reader(paths.root)
        kw.setdefault("backend", ReplayBackend.from_dir(S1))
        kw.setdefault("power", FakePower())
        maintenance = kw.pop("maintenance", False)
        ctx = build_context(paths, **kw)
        # The daily maintenance run is off unless a test asks for it (it would delete the old
        # rows some tests insert before serving); the step 20 tests turn it on.
        ctx.extra["maintenance.enabled"] = maintenance
        return ctx

    return make


@dataclass
class Live:
    base: str
    server: uvicorn.Server
    ctx: AppContext
    app: FastAPI

    def client(self, **kw: Any) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base, timeout=TIMEOUT, **kw)

    @property
    def auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.ctx.token}"}


@asynccontextmanager
async def serving(ctx: AppContext, app: FastAPI | None = None) -> AsyncIterator[Live]:
    app = app or create_app(ctx)
    sock = bind_socket()
    port = sock.getsockname()[1]
    config = uvicorn.Config(
        app, log_level="warning", access_log=False, lifespan="on", timeout_graceful_shutdown=2
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(TIMEOUT):
            while not server.started:
                if task.done():
                    task.result()
                await asyncio.sleep(0.02)
        yield Live(f"http://127.0.0.1:{port}", server, ctx, app)
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, TIMEOUT)
        sock.close()


class SseReader:
    """Reads ``event:``/``data:`` frames from a streamed ``GET /events`` response."""

    def __init__(self, response: httpx.Response) -> None:
        self.lines = response.aiter_lines()
        self.comments: list[str] = []

    async def until_comment(self, text: str) -> None:
        async with asyncio.timeout(TIMEOUT):
            async for line in self.lines:
                if line.startswith(":") and text in line:
                    return
        raise AssertionError(f"no comment {text!r}")

    async def next_event(self) -> dict[str, Any]:
        event_type: str | None = None
        async with asyncio.timeout(TIMEOUT):
            async for line in self.lines:
                if line.startswith(":"):
                    self.comments.append(line)
                elif line.startswith("event: "):
                    event_type = line[len("event: ") :]
                elif line.startswith("data: "):
                    data = json.loads(line[len("data: ") :])
                    assert data["type"] == event_type
                    return dict(data)
        raise AssertionError("the stream ended")


class ApiHelpers:
    """The helpers above, for test modules (``--import-mode=importlib`` cannot import conftest)."""

    S1 = S1
    SseReader = SseReader

    @staticmethod
    def serving(ctx: AppContext, app: FastAPI | None = None) -> Any:
        return serving(ctx, app)


@pytest.fixture
def api() -> ApiHelpers:
    return ApiHelpers()
