"""The FastAPI app factory (llm-design §2, PRD §11, plan step 12).

``create_app(ctx)`` builds the app: every module in :mod:`etach.api.routes` that exposes a
``router`` is included (sorted by module name), plus ``GET /events`` (:mod:`etach.api.sse`); the
auth dependency (:func:`etach.api.auth.require_token`) is applied to all of them. The lifespan
starts the run manager (startup recovery runs there) and then the daily maintenance scheduler
(:mod:`etach.api.maintenance`; its startup run finishes before the app serves), and closes both on
shutdown.

``create_app(None)`` gives an app without state, only for ``etach openapi export``.

``build_context`` wires the runtime the way ``etach run`` does: the models config, an
``OllamaClient`` (live, or a cassette replay backend) and a ``FileStore`` on their own
connections, a ``RunManager`` with the extract graph registered.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from etach import __version__
from etach.api import routes as routes_pkg
from etach.api import sse
from etach.api.auth import new_token, require_token
from etach.api.deps import AppContext
from etach.api.maintenance import ENABLED_KEY, SCHEDULER_KEY, MaintenanceScheduler
from etach.appdir import DataPaths
from etach.runtime.events import EventBus
from etach.runtime.manager import InvalidRunState, RunManager
from etach.runtime.power import Power, default_power

__all__ = [
    "HOST",
    "bind_socket",
    "build_context",
    "create_app",
    "openapi_text",
    "route_routers",
    "write_openapi",
]

HOST = "127.0.0.1"

# The only browser origins allowed to call the sidecar (llm-design §2): the Tauri webview and
# loopback pages (`vite dev` / `vite preview`, the E2E tests). Starlette full-matches the regex.
CORS_ORIGIN_REGEX = (
    r"tauri://localhost|https?://tauri\.localhost|http://(127\.0\.0\.1|localhost):\d{1,5}"
)
CORS_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
CORS_HEADERS = ("Authorization", "Content-Type", "Last-Event-ID")


def route_routers() -> list[tuple[str, APIRouter]]:
    """``(module name, router)`` for every module in :mod:`etach.api.routes` with a ``router``."""
    out: list[tuple[str, APIRouter]] = []
    for info in sorted(pkgutil.iter_modules(routes_pkg.__path__), key=lambda m: m.name):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{routes_pkg.__name__}.{info.name}")
        router = getattr(module, "router", None)
        if isinstance(router, APIRouter):
            out.append((info.name, router))
    return out


def create_app(ctx: AppContext | None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if ctx is None:
            yield
            return
        if ctx.hub is None:
            ctx.hub = sse.EventHub(ctx.events)
        scheduler: MaintenanceScheduler | None = None
        try:
            await ctx.manager.start()
            if ctx.extra.get(ENABLED_KEY, True):
                scheduler = ctx.extra.get(SCHEDULER_KEY) or MaintenanceScheduler(ctx)
                ctx.extra[SCHEDULER_KEY] = scheduler
                await scheduler.start()
            ctx.hub.mark_started()
            yield
        finally:
            if scheduler is not None:
                await scheduler.aclose()
            await ctx.manager.aclose()
            ctx.hub.detach()
            ctx.close()

    app = FastAPI(
        title="ETACH sidecar",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.ctx = ctx
    app.state.token = ctx.token if ctx is not None else ""
    # CORS for the app's own origins only (llm-design §2). The middleware answers a preflight
    # itself, before any route or the auth dependency, so OPTIONS never needs the token.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=CORS_ORIGIN_REGEX,
        allow_methods=list(CORS_METHODS),
        allow_headers=list(CORS_HEADERS),
        allow_credentials=False,
    )
    auth = [Depends(require_token)]
    for _, router in route_routers():
        app.include_router(router, dependencies=auth)
    app.include_router(sse.router, dependencies=auth)

    @app.exception_handler(InvalidRunState)
    async def _invalid_run_state(request: Request, exc: InvalidRunState) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=409)

    return app


def openapi_text() -> str:
    """The OpenAPI document, deterministic: sorted keys, 2-space indent, ``\\n`` at the end."""
    schema = create_app(None).openapi()
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def bind_socket(host: str = HOST, port: int = 0) -> socket.socket:
    """A listening-ready TCP socket on ``127.0.0.1`` and a free port (``port=0``)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, port))
    sock.set_inheritable(True)
    return sock


def build_context(
    paths: DataPaths,
    *,
    backend: Any = None,
    base_url: str | None = None,
    transport: Any = None,
    token: str | None = None,
    power: Power | None = None,
    events: EventBus | None = None,
) -> AppContext:
    """Open the runtime for ``etach serve`` (the database must already be migrated)."""
    from etach.graphs.extract import ExtractDeps, register_extract
    from etach.graphs.grade import GradeDeps, register_grade
    from etach.llm.client import OllamaClient
    from etach.llm.config import load_models_config
    from etach.prompts.render import FilePromptProvider
    from etach.store import db
    from etach.store.files import FileStore

    events = events or EventBus()
    power = power if power is not None else default_power()
    config = load_models_config(paths)
    files_conn = db.connect(paths.db)
    client_conn = db.connect(paths.db)
    files = FileStore(files_conn, paths)
    client = OllamaClient(
        client_conn,
        config,
        FilePromptProvider(),
        base_url=base_url if backend is None else None,
        transport=transport if backend is None else None,
        backend=backend,
        read_image=files.read_bytes,
    )
    manager = RunManager(paths.db, events=events, power=power)
    register_extract(manager, ExtractDeps(client=client, files=files))
    register_grade(manager, GradeDeps(client=client))
    ctx = AppContext(
        paths=paths,
        manager=manager,
        token=token or new_token(),
        power=power,
        events=events,
        client=client,
        files=files,
        ollama_url=None if backend is not None else base_url,
        replay=backend is not None,
    )
    ctx.close_later(power.close)
    ctx.close_later(client_conn.close)
    ctx.close_later(files_conn.close)
    return ctx


def write_openapi(path: Path) -> bool:
    """Write the OpenAPI document; ``False`` when the file already holds it (CRLF ignored)."""
    data = openapi_text().encode("utf-8")
    if path.exists() and path.read_bytes().replace(b"\r\n", b"\n") == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True
