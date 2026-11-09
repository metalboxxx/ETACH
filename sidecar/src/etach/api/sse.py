"""``GET /events``: the :class:`~etach.runtime.events.EventBus` as a ``text/event-stream``
(llm-design §2).

Each event is sent as ``id: <n>``, ``event: <type>``, ``data: <json>``; a ``: keep-alive``
comment goes out every :data:`KEEPALIVE_SECONDS`. The stream starts with a ``: connected``
comment once the subscription exists (a client may act after it and miss nothing).

:class:`EventHub` numbers every bus event and keeps the last :data:`BUFFER_SIZE`:

- a reconnecting ``EventSource`` sends ``Last-Event-ID`` (or ``?last_event_id=``) and gets the
  buffered events after it;
- a fresh connection (no id) first gets the events published during startup (recovery's
  ``run.interrupted``, R12.8), then the live ones.

Run events come from the run manager. Other events (``review.changed``, ``system.changed``,
``models.pull_progress``) are published with :func:`publish`. A client disconnect closes the
subscription.
"""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from etach.api.auth import allow_query_token
from etach.api.deps import CtxDep
from etach.runtime.events import Event, EventBus

__all__ = [
    "BUFFER_SIZE",
    "EVENT_TYPES",
    "KEEPALIVE_SECONDS",
    "EventHub",
    "format_event",
    "publish",
    "router",
]

KEEPALIVE_SECONDS = 15.0
BUFFER_SIZE = 1000

EVENT_TYPES: tuple[str, ...] = (
    "run.queued",
    "run.step_started",
    "run.step_done",
    "run.progress",
    "run.done",
    "run.failed",
    "run.stopped",
    "run.interrupted",
    "run.discarded",
    "review.changed",
    "system.changed",
    "models.pull_progress",
)


def publish(bus: EventBus, type: str, **data: Any) -> Event:
    """Publish a non-run event (``review.changed``, ``system.changed``, ``models.pull_progress``)
    with its JSON-ready fields. Call it on the event loop thread (an async route, or
    ``loop.call_soon_threadsafe`` from a worker thread)."""
    return bus.publish_event(type, **data)


Item = tuple[int, Event]


class EventHub:
    """Numbers the bus events, buffers them and fans them out to SSE clients."""

    def __init__(self, bus: EventBus, buffer_size: int = BUFFER_SIZE) -> None:
        self._seq = 0
        self._buffer: deque[Item] = deque(maxlen=buffer_size)
        self._clients: set[asyncio.Queue[Item]] = set()
        self.startup_seq: int | None = None
        self._remove = bus.add_listener(self._on_event)

    def _on_event(self, event: Event) -> None:
        self._seq += 1
        item = (self._seq, event)
        self._buffer.append(item)
        for q in list(self._clients):
            q.put_nowait(item)

    def mark_started(self) -> None:
        """Startup (recovery) is over: what was published so far is the startup backlog."""
        self.startup_seq = self._seq

    def open(self, last_id: int | None) -> tuple[asyncio.Queue[Item], list[Item]]:
        """A new client queue, plus the backlog to send first."""
        q: asyncio.Queue[Item] = asyncio.Queue()
        self._clients.add(q)
        if last_id is not None:
            backlog = [it for it in self._buffer if it[0] > last_id]
        else:
            upto = self.startup_seq if self.startup_seq is not None else self._seq
            backlog = [it for it in self._buffer if it[0] <= upto]
        return q, backlog

    def close(self, q: asyncio.Queue[Item]) -> None:
        self._clients.discard(q)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def detach(self) -> None:
        self._remove()


def format_event(seq: int, event: Event) -> str:
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"), default=str)
    return f"id: {seq}\nevent: {event.get('type', 'message')}\ndata: {data}\n\n"


def _last_id(request: Request) -> int | None:
    raw = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def _stream(
    hub: EventHub, request: Request, last_id: int | None, keepalive: float
) -> AsyncIterator[str]:
    q, backlog = hub.open(last_id)
    try:
        yield ": connected\n\n"
        for seq, event in backlog:
            yield format_event(seq, event)
        while True:
            try:
                seq, event = await asyncio.wait_for(q.get(), keepalive)
            except TimeoutError:
                if await request.is_disconnected():
                    return
                yield ": keep-alive\n\n"
                continue
            yield format_event(seq, event)
    finally:
        hub.close(q)


router = APIRouter()


@router.get("/events", response_class=StreamingResponse, tags=["events"])
@allow_query_token
async def events(request: Request, ctx: CtxDep) -> StreamingResponse:
    """SSE: run events, ``review.changed``, ``system.changed``, ``models.pull_progress``."""
    hub = ctx.hub
    if hub is None:  # a context built without the app's lifespan
        hub = ctx.hub = EventHub(ctx.events)
    keepalive = float(ctx.extra.get("sse_keepalive", KEEPALIVE_SECONDS))
    return StreamingResponse(
        _stream(hub, request, _last_id(request), keepalive),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
