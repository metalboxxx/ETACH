"""In-process event bus for run events (llm-design §2 ``/events``; step 12's SSE subscribes).

Every event is a small JSON-ready dict with ``type``, ``run_id`` and ``thread_id`` (the
conversation thread, ``runs.thread_id``), plus the step details where they apply:

- ``run.queued``: a run entered the queue (new, or after Resume);
- ``run.step_started`` / ``run.step_done``: ``step_id``, ``node``, ``item``, ``try_no``
  (``step_done`` adds ``status``: ``done`` | ``failed`` | ``incomplete``);
- ``run.progress``: ``step_id``, ``node``, ``item``, ``done``, ``total``, ``label``, ``unit``
  (what is counted: ``"page"``, ``"question"``…); or, while a model call streams (at most
  every few seconds), ``step_id``, ``node``, ``item`` and ``tokens`` (output tokens so far);
- ``run.step_started`` and ``run.progress`` add ``stage`` (1-based), ``stages``, ``stage_label``
  and ``percent`` (0 to 100) when the graph registered its stages (llm-design §2 "Run progress");
- ``run.done`` (with ``percent`` 100 and the stage fields, as above), ``run.stopped``,
  ``run.interrupted``, ``run.discarded``; ``run.failed`` adds ``error``.

Non-run events (``review.changed``, ``system.changed``, ``models.pull_progress``) carry no
``run_id``/``thread_id``; they go through :meth:`EventBus.publish_event`.

:meth:`EventBus.publish` is synchronous and must be called on the event loop thread. Async
consumers :meth:`~EventBus.subscribe` (an unbounded queue each); synchronous listeners
(:meth:`~EventBus.add_listener`) are called inline, in publish order.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any, Literal

__all__ = ["RUN_EVENT_TYPES", "Event", "EventBus", "RunEventType", "Subscription"]

RunEventType = Literal[
    "run.queued",
    "run.step_started",
    "run.step_done",
    "run.progress",
    "run.done",
    "run.failed",
    "run.stopped",
    "run.interrupted",
    "run.discarded",
]
RUN_EVENT_TYPES: tuple[RunEventType, ...] = (
    "run.queued",
    "run.step_started",
    "run.step_done",
    "run.progress",
    "run.done",
    "run.failed",
    "run.stopped",
    "run.interrupted",
    "run.discarded",
)

Event = dict[str, Any]
Listener = Callable[[Event], None]


class Subscription:
    """An async iterator over the events published after it was created."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._queue: asyncio.Queue[Event | None] = asyncio.Queue()
        self.closed = False

    def _put(self, event: Event) -> None:
        if not self.closed:
            self._queue.put_nowait(event)

    async def get(self) -> Event:
        """The next event; raises ``StopAsyncIteration`` once the subscription is closed."""
        item = await self._queue.get()
        if item is None:
            raise StopAsyncIteration
        return item

    def get_nowait(self) -> Event | None:
        """The next queued event, or ``None`` when none is waiting."""
        try:
            item = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None
        return item

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self._bus._subscriptions.discard(self)
            self._queue.put_nowait(None)

    def __aiter__(self) -> AsyncIterator[Event]:
        return self

    async def __anext__(self) -> Event:
        return await self.get()


class EventBus:
    def __init__(self) -> None:
        self._subscriptions: set[Subscription] = set()
        self._listeners: list[Listener] = []

    def subscribe(self) -> Subscription:
        sub = Subscription(self)
        self._subscriptions.add(sub)
        return sub

    def add_listener(self, listener: Listener) -> Callable[[], None]:
        """Call ``listener(event)`` inline for every event; returns a function that removes it."""
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    def publish(self, type: RunEventType, run_id: str, thread_id: str, **details: Any) -> Event:
        """Publish a run event."""
        return self.publish_event(type, run_id=run_id, thread_id=thread_id, **details)

    def publish_event(self, type: str, **data: Any) -> Event:
        """Publish any event (run or non-run) with its JSON-ready fields."""
        event: Event = {"type": type, **data}
        for sub in list(self._subscriptions):
            sub._put(dict(event))
        for listener in list(self._listeners):
            listener(dict(event))
        return event
