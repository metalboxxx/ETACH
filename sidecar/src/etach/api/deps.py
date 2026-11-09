"""The sidecar's shared state (:class:`AppContext`) and the FastAPI dependencies routes use.

In a route::

    from etach.api.deps import ConnDep, CtxDep

    @router.get("/things")
    def list_things(conn: ConnDep, ctx: CtxDep) -> ...: ...

``ConnDep`` is a fresh ``sqlite3`` connection for this request (closed after the response;
``check_same_thread=False``, so a sync route running in the thread pool may use it). Write in a
``store.db.transaction(conn)``, then — if the transaction queued runs — ``await ctx.manager.poke()``
(async route) after it committed. Non-run events go through :func:`etach.api.sse.publish`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, Request

from etach.appdir import DataPaths
from etach.runtime.events import EventBus
from etach.runtime.manager import RunManager
from etach.runtime.power import Power
from etach.store import db as store_db
from etach.store.files import FileStore

if TYPE_CHECKING:
    from etach.api.sse import EventHub

__all__ = ["AppContext", "ConnDep", "CtxDep", "FilesDep", "get_conn", "get_ctx", "get_files"]


@dataclass
class AppContext:
    """Everything the routes share. Built by :func:`etach.api.app.build_context` (``etach serve``)
    or by tests. ``client`` / ``files`` are the extract graph's long-lived dependencies (their own
    DB connections); ``ollama_url`` is ``None`` when cassettes are replayed."""

    paths: DataPaths
    manager: RunManager
    token: str
    power: Power
    events: EventBus
    client: Any = None
    files: FileStore | None = None
    ollama_url: str | None = None
    replay: bool = False
    hub: EventHub | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    _closers: list[Any] = field(default_factory=list)

    def close_later(self, closer: Any) -> None:
        """Call ``closer()`` when the app shuts down (after the run manager is closed)."""
        self._closers.append(closer)

    def close(self) -> None:
        while self._closers:
            self._closers.pop()()


def get_ctx(request: Request) -> AppContext:
    ctx: AppContext | None = request.app.state.ctx
    if ctx is None:
        raise RuntimeError("the app has no context (an OpenAPI-only app)")
    return ctx


CtxDep = Annotated[AppContext, Depends(get_ctx)]


def get_conn(ctx: CtxDep) -> Iterator[sqlite3.Connection]:
    conn = store_db.connect(ctx.paths.db)
    try:
        yield conn
    finally:
        conn.close()


ConnDep = Annotated[sqlite3.Connection, Depends(get_conn)]


def get_files(conn: ConnDep, ctx: CtxDep) -> FileStore:
    """A :class:`FileStore` on this request's connection."""
    return FileStore(conn, ctx.paths)


FilesDep = Annotated[FileStore, Depends(get_files)]
