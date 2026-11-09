"""The step wrapper: one ``steps`` row per node execution (data-model §2.7, llm-design §7).

A graph factory wraps each node with :func:`step`::

    builder.add_node("transcribe_page", step("transcribe_page", transcribe, item=page_item))

For every execution the wrapper

1. inserts a ``running`` step with ``try_no`` = earlier rows of the same ``(run, node, item)``
   + 1, and publishes ``run.step_started``;
2. exposes the step's ID through :func:`current_step_id` (a ``ContextVar``), which the node passes
   to ``client.call(step_id=...)`` so its ``llm_calls`` rows link to the step;
3. runs the node **from scratch** (a restarted node never reads the ``cancelled``/``incomplete``
   calls of an earlier try; only the checkpointed state carries results, P8);
4. sets the step to ``done``, ``failed``, or ``incomplete`` (cancelled by Stop, or the stream
   dropped: the node will run again on Resume), and publishes ``run.step_done``.

A Stop requested while ``run.step_started`` is being published takes effect before the node's
work begins (an explicit cancellation point), so no model call is started.

The node sees the run through :func:`current_run` (run ID, thread ID, kind, input).

**Run progress** (llm-design §2 "Run progress", v4.20). A graph registers its ordered
:class:`Stage` table with the run manager; each run then gets a :class:`RunProgress`
(``RunContext.progress``). ``run.step_started`` and ``run.progress`` carry its fields: ``stage``
(1-based), ``stages``, ``stage_label`` and ``percent``. While a model call streams, the client
calls the step's token listener (:data:`etach.llm.client.token_listener`), which publishes
``run.progress`` with ``tokens``.
"""

from __future__ import annotations

import asyncio
import math
import sqlite3
import threading
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from etach.domain.models import ExtractInput, GradeInput
from etach.llm.client import StreamDropped, token_listener
from etach.runtime.checkpoint import uninterruptible
from etach.runtime.events import EventBus
from etach.store.repos import runs

__all__ = [
    "Db",
    "NodeFn",
    "RunContext",
    "RunProgress",
    "Stage",
    "current_run",
    "current_step_id",
    "report_progress",
    "step",
]


class Db:
    """One ``sqlite3`` connection used by one thread at a time (structure.md §7): async callers
    go through :meth:`run` (``asyncio.to_thread``); :meth:`run_sync` blocks its thread, so
    it is never called on the event loop (a blocking write there can deadlock with the
    checkpointer's connection); see :func:`etach.runtime.checkpoint.uninterruptible`."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._lock = threading.Lock()

    def run_sync[T](self, fn: Callable[[sqlite3.Connection], T]) -> T:
        with self._lock:
            return fn(self.conn)

    async def run[T](self, fn: Callable[[sqlite3.Connection], T]) -> T:
        return await asyncio.to_thread(self.run_sync, fn)


@dataclass(frozen=True)
class Stage:
    """One stage of a graph: a plain-words name for a group of nodes (llm-design §2)."""

    label: str
    nodes: tuple[str, ...]


class RunProgress:
    """The progress of one run through its graph's ordered stages.

    ``percent`` gives each stage an equal share and, inside the current stage, the
    ``done/total`` of its latest :func:`report_progress`. Entering a later stage counts every
    stage before it as done (a skipped stage too). ``percent`` never goes down: a node that
    restarts, or a later node whose count starts again at 1, keeps the value already shown.
    A node that is in no stage (or an earlier one) leaves the stage as it is.
    """

    def __init__(self, stages: Sequence[Stage]) -> None:
        if not stages:
            raise ValueError("a run's progress needs at least one stage")
        self.stages = tuple(stages)
        self._index = {node: i for i, s in enumerate(self.stages, 1) for node in s.nodes}
        self.stage = 0  # 0: no node of a stage has started yet
        self.fraction = 0.0
        self.percent = 0

    def stage_of(self, node: str) -> int | None:
        return self._index.get(node)

    def enter(self, node: str) -> None:
        """A step of ``node`` starts."""
        stage = self._index.get(node)
        if stage is not None and stage > self.stage:
            self.stage = stage
            self.fraction = 0.0
            self._update()

    def advance(self, done: int, total: int) -> None:
        """The current stage reports ``done`` of ``total``."""
        if self.stage == 0 or total <= 0:
            return
        self.fraction = min(1.0, max(0.0, done / total))
        self._update()

    def finish(self) -> None:
        """The run is done: the last stage, 100%."""
        self.stage = len(self.stages)
        self.fraction = 1.0
        self.percent = 100

    def _update(self) -> None:
        share = ((self.stage - 1) + self.fraction) / len(self.stages)
        self.percent = max(self.percent, min(100, math.floor(share * 100)))

    def fields(self) -> dict[str, Any]:
        """``stage``, ``stages``, ``stage_label``, ``percent``; empty before the first stage."""
        if self.stage == 0:
            return {}
        return {
            "stage": self.stage,
            "stages": len(self.stages),
            "stage_label": self.stages[self.stage - 1].label,
            "percent": self.percent,
        }


@dataclass(frozen=True)
class RunContext:
    """What a node may know about the run it executes in."""

    run_id: str
    thread_id: str
    kind: str
    input: ExtractInput | GradeInput
    db: Db
    events: EventBus
    progress: RunProgress | None = None  # None: the graph registered no stages


@dataclass(frozen=True)
class _StepInfo:
    step_id: str
    node: str
    item: str | None
    try_no: int


_run_ctx: ContextVar[RunContext | None] = ContextVar("etach_run", default=None)
_step_ctx: ContextVar[_StepInfo | None] = ContextVar("etach_step", default=None)


def current_run() -> RunContext:
    ctx = _run_ctx.get()
    if ctx is None:
        raise RuntimeError("not inside a run (the run manager sets the run context)")
    return ctx


def current_step_id() -> str:
    """The ``steps.id`` of the node execution in progress; pass it to ``client.call``."""
    info = _step_ctx.get()
    if info is None:
        raise RuntimeError("not inside a step (wrap the node with etach.runtime.steps.step)")
    return info.step_id


def _progress_fields(ctx: RunContext) -> dict[str, Any]:
    return ctx.progress.fields() if ctx.progress is not None else {}


def report_progress(
    done: int,
    total: int,
    label: str | None = None,
    *,
    unit: str | None = None,
    current: int | None = None,
    again: bool = False,
) -> None:
    """Publish ``run.progress`` for the current step (e.g. page 2 of 3).

    ``unit`` names what is counted, in plain words (``"page"``, ``"question"``), so the
    running indicator can say "page 2 of 3" without showing a node name.

    llm-design §2 v4.24: ``current`` is the item being worked on, 1-based ("Reading page 3 of
    4"); by default ``done + 1`` while items remain, else ``total``. ``again`` marks a second
    pass over an item (``retranscribe_tiles``: "Checking page 2 again"), with ``current`` that
    item's own number.
    """
    if current is None:
        current = min(done + 1, total) if total else None
    ctx = current_run()
    info = _step_ctx.get()
    if ctx.progress is not None:
        ctx.progress.advance(done, total)
    ctx.events.publish(
        "run.progress",
        ctx.run_id,
        ctx.thread_id,
        step_id=info.step_id if info else None,
        node=info.node if info else None,
        item=info.item if info else None,
        done=done,
        total=total,
        label=label,
        unit=unit,
        current=current,
        again=again,
        **_progress_fields(ctx),
    )


def _publish_tokens(ctx: RunContext, info: _StepInfo) -> Callable[[str, int], None]:
    """The token listener of one step: ``run.progress`` with ``tokens`` (no count), so the
    indicator shows that the model is still writing."""

    def listener(step_id: str, tokens: int) -> None:
        ctx.events.publish(
            "run.progress",
            ctx.run_id,
            ctx.thread_id,
            step_id=step_id,
            node=info.node,
            item=info.item,
            tokens=tokens,
            **_progress_fields(ctx),
        )

    return listener


State = Mapping[str, Any]
NodeFn = Callable[[Any], Awaitable[Any]]


def step(
    node: str,
    fn: NodeFn,
    *,
    item: Callable[[Any], str | None] | None = None,
) -> NodeFn:
    """Wrap the async node ``fn(state) -> update`` (see the module docstring).

    ``item`` computes the step's item from the state (e.g. ``lambda s: f"page {s['page']}"``).
    """

    async def wrapped(state: Any) -> Any:
        ctx = current_run()
        step_item = item(state) if item is not None else None
        row = await ctx.db.run(lambda c: runs.start_step(c, ctx.run_id, node, step_item))
        info = _StepInfo(row.id, node, step_item, row.try_no)
        details = {"step_id": row.id, "node": node, "item": step_item, "try_no": row.try_no}
        token = _step_ctx.set(info)
        listener_token = token_listener.set(_publish_tokens(ctx, info))
        if ctx.progress is not None:
            ctx.progress.enter(node)
        try:
            ctx.events.publish(
                "run.step_started",
                ctx.run_id,
                ctx.thread_id,
                **details,
                **_progress_fields(ctx),
            )
            status: runs.StepStatus = "failed"
            try:
                await asyncio.sleep(0)  # a Stop requested at the boundary lands here
                result = await fn(state)
                status = "done"
                return result
            except (asyncio.CancelledError, StreamDropped):
                status = "incomplete"
                raise
            finally:
                # in a worker thread (a blocking write on the event loop can deadlock with the
                # checkpointer's connection), awaited so a second cancellation cannot skip it
                await uninterruptible(ctx.db.run(lambda c: runs.finish_step(c, row.id, status)))
                ctx.events.publish(
                    "run.step_done", ctx.run_id, ctx.thread_id, **details, status=status
                )
        finally:
            token_listener.reset(listener_token)
            _step_ctx.reset(token)

    wrapped.__name__ = node
    wrapped.__qualname__ = node
    return wrapped
