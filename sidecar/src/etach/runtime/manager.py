"""The run manager: a FIFO queue, one run at a time, statuses and the graph registry
(llm-design §2 "Only one run executes at a time", §7; data-model §2.7; plan step 7).

Statuses::

    queued → running → done | failed
    running → stopping → stopped            Stop (the graph task is cancelled)
    running → interrupted                   StreamDropped (or the sidecar shutting down)
    stopped | interrupted → queued          Resume (continues from the last checkpoint)
    queued | stopped | interrupted | failed | running → discarded     Discard

**Events.** ``run.discarded`` is published when a run is discarded (llm-design §2, v4.8).

**Runs queued in the database.** A Review resolution (data-model §5.3) only writes a ``queued``
row (``runs.enqueue_grade`` / ``enqueue_extract``). After committing, the caller awaits
:meth:`RunManager.poke`, which loads such rows into the FIFO (and publishes ``run.queued``). A
graph's ``save`` may queue rows too (step 22.6.4: an extraction queues its key run, a grade run
with reason ``after_extract``); the manager pokes itself after every ``done`` run, so they follow.

**Queue order.** FIFO by the moment a run entered ``queued`` (``submit`` or ``resume``) in this
process; runs found ``queued`` at startup come first, in creation order (``runs.id`` is a
monotonic ULID). Among them the manager takes the first *runnable* run: one whose kind has a
registered graph. A run of an unregistered kind stays ``queued`` without error and does not block
the runs behind it (grade runs can be queued before the grade graph exists).

**Registry.** ``register(kind, factory)``: ``factory(checkpointer)`` returns the compiled graph
(``builder.compile(checkpointer=checkpointer)``); it is called once per kind, on first use.
``initial(run)`` gives the input of a run's first ``ainvoke`` (default
``{"input": run.input as JSON}``). A run that already has a checkpoint is continued with
``ainvoke(None, {"configurable": {"thread_id": run_id}})``.

**Progress.** ``register(..., stages=...)`` gives a kind its stage table (llm-design §2 "Run
progress"). Each run of that kind gets a :class:`~etach.runtime.steps.RunProgress`, kept in memory
while the run is active (also while it is stopped, so a Resume continues from the value shown)
and seeded from the run's latest step when the run starts or resumes in a new process. ``run.done``
carries ``percent`` 100. :meth:`progress_of` gives the latest fields for ``GET /runs/active``.

**After the graph task ends** the manager closes whatever the task left open (``running`` steps,
``streaming`` calls), sets the final status, purges the checkpoint on ``done``/``discarded``,
clears keep-awake and publishes the run event. A graph's ``save`` may already have set the run
``done`` in its own transaction (data-model §5.2); the manager then only fills ``finished_at``.

Every public method must be awaited (or, for :meth:`request_stop`, called) on the event loop that
ran :meth:`start`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sqlite3
from collections.abc import Callable, Coroutine
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from etach.domain.models import ExtractInput, GradeInput, Run
from etach.llm.client import StreamDropped
from etach.runtime import checkpoint
from etach.runtime.events import EventBus
from etach.runtime.power import Power, default_power
from etach.runtime.recovery import Recovered, recover
from etach.runtime.steps import Db, RunContext, RunProgress, Stage, _run_ctx
from etach.store import db as store_db
from etach.store.repos import runs

__all__ = [
    "DEFAULT_RECURSION_LIMIT",
    "GraphFactory",
    "InitialState",
    "InvalidRunState",
    "RunKind",
    "RunManager",
]

RunKind = Literal["extract", "grade"]
GraphFactory = Callable[[AsyncSqliteSaver], Any]
"""``factory(checkpointer) -> compiled graph`` (anything with LangGraph's ``ainvoke``)."""
InitialState = Callable[[Run], Any]

DEFAULT_RECURSION_LIMIT = 1000
"""LangGraph's default (25 supersteps) is too low for a many-page test: every page is a step."""

_StopReason = Literal["stop", "discard", "shutdown"]
_FINAL_BY_REASON: dict[_StopReason, runs.RunStatus] = {
    "stop": "stopped",
    "discard": "discarded",
    "shutdown": "interrupted",
}


class InvalidRunState(RuntimeError):
    """The action is not allowed in the run's current status (or the run does not exist)."""


_log = logging.getLogger(__name__)


def _default_initial(run: Run) -> Any:
    return {"input": run.input.model_dump(mode="json")}


@dataclass
class _Registration:
    factory: GraphFactory
    initial: InitialState
    stages: tuple[Stage, ...] = ()
    graph: Any = None


@dataclass
class _Active:
    run_id: str
    run: Run | None = None  # read by ``_run_one`` once the run is taken
    task: asyncio.Task[Any] | None = None
    stop_reason: _StopReason | None = None
    finished: asyncio.Event = field(default_factory=asyncio.Event)


def _now() -> datetime:
    return datetime.now(UTC)


def _stream_dropped(exc: BaseException) -> bool:
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        if isinstance(cur, StreamDropped):
            return True
        seen.add(id(cur))
        cur = cur.__cause__ or cur.__context__
    return False


class RunManager:
    def __init__(
        self,
        db_path: Path | str,
        *,
        events: EventBus | None = None,
        power: Power | None = None,
        recursion_limit: int = DEFAULT_RECURSION_LIMIT,
    ) -> None:
        self.db_path = Path(db_path)
        self.events = events or EventBus()
        self._owns_power = power is None
        self.power: Power = power if power is not None else default_power()
        self.recursion_limit = recursion_limit
        self._registry: dict[str, _Registration] = {}
        self._queue: list[tuple[str, str]] = []  # (run_id, kind) in FIFO order
        self._active: _Active | None = None  # set as soon as the run leaves the queue
        self._background: set[asyncio.Task[Any]] = set()  # status writes of ``request_stop``
        self._resuming: set[str] = set()
        self._progress: dict[str, RunProgress] = {}  # active runs of kinds with stages
        self._db: Db | None = None
        self._saver: AsyncSqliteSaver | None = None
        self._stack = AsyncExitStack()
        self._scheduler: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()
        self._idle = asyncio.Event()
        self._closing = False

    # --- lifecycle -------------------------------------------------------------------------

    async def start(self, *, run_recovery: bool = True) -> Recovered | None:
        """Open the database and the checkpointer, run startup recovery, load the queued runs
        and start taking runs from the queue."""
        if self._scheduler is not None:
            raise RuntimeError("the run manager is already started")
        conn = await asyncio.to_thread(store_db.connect, self.db_path)
        self._stack.callback(conn.close)
        self._db = Db(conn)
        self._saver = await self._stack.enter_async_context(
            checkpoint.open_checkpointer(self.db_path)
        )
        recovered = await recover(self._db, self.events) if run_recovery else None
        queued = await self._db.run(lambda c: runs.list_runs(c, status="queued"))
        self._queue = [(r.id, r.kind) for r in queued]
        self._scheduler = asyncio.create_task(self._schedule(), name="etach-run-scheduler")
        self._wake.set()
        return recovered

    async def aclose(self) -> None:
        """Stop taking runs; a running run is cancelled and marked ``interrupted``."""
        self._closing = True
        active = self._active
        if active is not None:
            if active.stop_reason is None:
                active.stop_reason = "shutdown"
            if active.task is not None:
                active.task.cancel()
            await active.finished.wait()
        if self._background:
            await asyncio.gather(*self._background, return_exceptions=True)
        if self._scheduler is not None:
            self._scheduler.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scheduler
            self._scheduler = None
        await self._stack.aclose()
        if self._owns_power:
            self.power.close()

    # --- registry --------------------------------------------------------------------------

    def register(
        self,
        kind: RunKind,
        factory: GraphFactory,
        *,
        initial: InitialState | None = None,
        stages: tuple[Stage, ...] = (),
    ) -> None:
        self._registry[kind] = _Registration(factory, initial or _default_initial, tuple(stages))
        self._wake.set()
        self._idle.clear()

    def registered(self, kind: str) -> bool:
        return kind in self._registry

    # --- queries ---------------------------------------------------------------------------

    @property
    def db(self) -> Db:
        if self._db is None:
            raise RuntimeError("the run manager is not started")
        return self._db

    @property
    def checkpointer(self) -> AsyncSqliteSaver:
        if self._saver is None:
            raise RuntimeError("the run manager is not started")
        return self._saver

    @property
    def running_run_id(self) -> str | None:
        return self._active.run_id if self._active is not None else None

    def queued_run_ids(self) -> list[str]:
        """The queue in FIFO order (runnable or not)."""
        return [run_id for run_id, _ in self._queue]

    async def get_run(self, run_id: str) -> Run:
        run = await self.db.run(lambda c: runs.get_run(c, run_id))
        if run is None:
            raise InvalidRunState(f"no run {run_id}")
        return run

    def progress_of(self, run: Run, latest_node: str | None) -> dict[str, Any]:
        """``stage``, ``stages``, ``stage_label`` and ``percent`` of an active run: the values
        last published in this process, else (a run left by an earlier process) the start of
        the stage of its latest step. Empty when the kind has no stages or nothing started."""
        kept = self._progress.get(run.id)
        if kept is not None:
            return kept.fields()
        return self._seeded(run.kind, latest_node).fields() if self._has_stages(run.kind) else {}

    def _has_stages(self, kind: str) -> bool:
        reg = self._registry.get(kind)
        return reg is not None and bool(reg.stages)

    def _seeded(self, kind: str, latest_node: str | None) -> RunProgress:
        progress = RunProgress(self._registry[kind].stages)
        if latest_node is not None:
            progress.enter(latest_node)
        return progress

    async def _progress_for(self, run: Run) -> RunProgress | None:
        """The run's progress, kept from earlier in this process or seeded from its latest
        step (a run resumed after a restart continues from the value it showed)."""
        if not self._has_stages(run.kind):
            return None
        kept = self._progress.get(run.id)
        if kept is None:
            latest = await self.db.run(lambda c: runs.latest_step(c, run.id))
            kept = self._seeded(run.kind, latest.node if latest is not None else None)
            self._progress[run.id] = kept
        return kept

    async def wait_idle(self) -> None:
        """Wait until nothing is running and no queued run is runnable."""
        await self._idle.wait()

    # --- actions ---------------------------------------------------------------------------

    async def submit(
        self, thread_id: str, kind: RunKind, run_input: ExtractInput | GradeInput
    ) -> Run:
        """Create a ``queued`` run and publish ``run.queued``."""
        run = await self.db.run(lambda c: runs.create_run(c, thread_id, kind, run_input))
        self._enqueue(run)
        return run

    def request_stop(self, run_id: str) -> None:
        """Stop without waiting (safe to call from an event listener inside the run).

        A running run → ``stopping``, and its graph task is cancelled; the manager sets
        ``stopped`` when the task has ended. A queued run → ``stopped``. The cancellation is
        immediate; the status write runs in the background (see :meth:`_begin_stop`).
        """
        write = self._begin_stop(run_id)
        task = asyncio.get_running_loop().create_task(write, name=f"etach-stop-{run_id}")
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def stop(self, run_id: str) -> Run:
        """Stop and wait until the run is ``stopped``."""
        active = self._active
        await self._begin_stop(run_id)
        if active is not None and active.run_id == run_id:
            await active.finished.wait()
        return await self.get_run(run_id)

    def _begin_stop(self, run_id: str) -> Coroutine[Any, Any, None]:
        """The in-memory part of a stop, done at once (cancel the task, or leave the queue);
        returns the status write, to be awaited.

        No database write happens on the event loop: a blocking write there can deadlock
        against the checkpointer's aiosqlite connection, whose open write transaction needs
        the loop to commit (``database is locked`` after ``busy_timeout``).
        """
        active = self._active
        if active is not None and active.run_id == run_id:
            if active.stop_reason is None:
                active.stop_reason = "stop"
            if active.task is not None:
                active.task.cancel()
            return self._mark_stopping(run_id)
        if self._dequeue(run_id):
            return self._mark_queued_stopped(run_id)
        raise InvalidRunState(f"run {run_id} is neither running nor queued")

    async def _mark_stopping(self, run_id: str) -> None:
        def write(c: sqlite3.Connection) -> None:
            with store_db.transaction(c):  # never over the final status ``_finish`` wrote
                run = runs.get_run(c, run_id)
                if run is not None and run.status == "running":
                    runs.set_run_status(c, run_id, "stopping")

        await self.db.run(write)

    async def _mark_queued_stopped(self, run_id: str) -> None:
        await self.db.run(lambda c: runs.set_run_status(c, run_id, "stopped"))
        run = await self.get_run(run_id)
        self.events.publish("run.stopped", run.id, run.thread_id)

    async def resume(self, run_id: str) -> Run:
        """``stopped``/``interrupted`` → ``queued``; the run continues from its checkpoint."""
        run = await self.get_run(run_id)
        if run.status not in ("stopped", "interrupted") or run_id in self._resuming:
            raise InvalidRunState(
                f"run {run_id} is {run.status}; only stopped or interrupted runs resume"
            )
        self._resuming.add(run_id)  # claimed before the await: a second resume is refused
        try:
            await self.db.run(lambda c: runs.set_run_status(c, run_id, "queued"))
        finally:
            self._resuming.discard(run_id)
        self._enqueue(run)
        return await self.get_run(run_id)

    async def poke(self) -> list[str]:
        """Load runs that are ``queued`` in the database but not in the FIFO (rows written by
        ``runs.enqueue_grade`` / ``enqueue_extract`` after a Review resolution) and publish
        ``run.queued`` for each. Returns their ids, in creation order. Call it after the
        transaction that wrote the rows has committed."""
        queued = await self.db.run(lambda c: runs.list_runs(c, status="queued"))
        added: list[str] = []
        for run in queued:
            if self._enqueue(run):
                added.append(run.id)
        return added

    async def discard(self, run_id: str) -> Run:
        """→ ``discarded``: the checkpoint is purged, the ``llm_calls`` rows are kept. A running
        run is cancelled first."""
        active = self._active
        if active is not None and active.run_id == run_id:
            active.stop_reason = "discard"
            if active.task is not None:
                active.task.cancel()
            await active.finished.wait()
            run = await self.get_run(run_id)
            if run.status == "done":
                raise InvalidRunState(f"run {run_id} is already done")
            return run
        run = await self.get_run(run_id)
        if run.status in ("done", "discarded"):
            raise InvalidRunState(f"run {run_id} is already {run.status}")
        self._dequeue(run_id)
        self._progress.pop(run_id, None)
        await self.db.run(lambda c: runs.set_run_status(c, run_id, "discarded", finished_at=_now()))
        await checkpoint.purge(self.checkpointer, run_id)
        self.events.publish("run.discarded", run.id, run.thread_id)
        return await self.get_run(run_id)

    # --- the queue -------------------------------------------------------------------------

    def _enqueue(self, run: Run) -> bool:
        """Append to the FIFO and publish ``run.queued``; ``False`` (and nothing published) when
        the run is already queued, being taken or running (a :meth:`poke` racing a
        :meth:`submit` or :meth:`resume`)."""
        active = self._active
        if any(queued_id == run.id for queued_id, _ in self._queue) or (
            active is not None and active.run_id == run.id
        ):
            return False
        self._queue.append((run.id, run.kind))
        self.events.publish("run.queued", run.id, run.thread_id)
        self._idle.clear()
        self._wake.set()
        return True

    def _dequeue(self, run_id: str) -> bool:
        for i, (queued_id, _) in enumerate(self._queue):
            if queued_id == run_id:
                del self._queue[i]
                return True
        return False

    def _pop_runnable(self) -> tuple[str, str] | None:
        for i, (_, kind) in enumerate(self._queue):
            if kind in self._registry:
                return self._queue.pop(i)
        return None

    async def _schedule(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            while not self._closing:
                entry = self._pop_runnable()
                if entry is None:
                    break
                # Active from the moment it leaves the queue, so a Stop or Discard in between
                # always finds it (no await between the pop and this line).
                active = _Active(entry[0])
                self._active = active
                try:
                    await self._run_one(active, entry[1])
                except Exception:  # keep serving the queue; the run's row shows its last status
                    _log.exception("run %s: the run manager failed to handle it", entry[0])
                finally:
                    self._active = None
                    active.finished.set()
            if not self._wake.is_set():
                self._idle.set()

    # --- one run ---------------------------------------------------------------------------

    async def _run_one(self, active: _Active, kind: str) -> None:
        db = self.db
        run_id = active.run_id
        run = await db.run(lambda c: runs.get_run(c, run_id))
        if run is None or run.status != "queued":
            return
        active.run = run
        try:
            await db.run(
                lambda c: runs.set_run_status(
                    c, run_id, "running", started_at=_now() if run.started_at is None else None
                )
            )
            self.power.set_keep_awake(True)
            progress = await self._progress_for(run)
            ctx = RunContext(run.id, run.thread_id, run.kind, run.input, db, self.events, progress)
            active.task = asyncio.create_task(
                self._invoke(self._registry[kind], run, ctx), name=f"etach-run-{run_id}"
            )
            if active.stop_reason is not None:
                active.task.cancel()
            await asyncio.wait([active.task])
            await self._finish(active)
        finally:
            if self.power.keep_awake:
                self.power.set_keep_awake(False)

    async def _invoke(self, reg: _Registration, run: Run, ctx: RunContext) -> Any:
        _run_ctx.set(ctx)
        if reg.graph is None:
            reg.graph = reg.factory(self.checkpointer)
        config = checkpoint.run_config(run.id, recursion_limit=self.recursion_limit)
        resuming = await checkpoint.has_checkpoint(self.checkpointer, run.id)
        graph_input = None if resuming else reg.initial(run)
        try:
            return await reg.graph.ainvoke(graph_input, config, durability=checkpoint.DURABILITY)
        except asyncio.CancelledError as exc:
            # LangGraph hands over its exit task so the caller can let the checkpointer finish
            # before the connection is used again.
            pending = [a for a in exc.args if isinstance(a, asyncio.Future)]
            if pending:
                await asyncio.wait(pending)
            raise

    async def _release_checkpointer(self) -> None:
        """Roll back a write transaction the cancelled graph left open on the checkpointer's
        connection. ``AsyncSqliteSaver`` does ``execute`` then ``await commit()``; a Stop landing
        between the two leaves the SQLite write lock held, and every other writer then fails
        with ``database is locked`` after ``busy_timeout``. The rolled-back write is one the
        graph never saw complete, so Resume simply redoes it.

        A safety net: :class:`checkpoint.ShieldedSaver` already makes each write one
        uncancellable unit; this catches a transaction left open by an error instead."""
        saver = self.checkpointer
        async with saver.lock:
            if saver.conn.in_transaction:
                await saver.conn.rollback()

    async def _finish(self, active: _Active) -> None:
        task = active.task
        assert task is not None
        run = active.run
        assert run is not None
        error: str | None = None
        final: runs.RunStatus
        if task.cancelled():
            reason = active.stop_reason or "shutdown"
            final = _FINAL_BY_REASON[reason]
            step_status: runs.StepStatus = "incomplete"
            call_status: runs.LlmCallStatus = "cancelled"
        elif (exc := task.exception()) is not None:
            step_status, call_status = "incomplete", "incomplete"
            if _stream_dropped(exc):
                final = "interrupted"
            else:
                final, step_status, call_status = "failed", "failed", "error"
                error = f"{type(exc).__name__}: {exc}"
        else:
            final, step_status, call_status = "done", "incomplete", "incomplete"
        if active.stop_reason == "discard" and final != "done":
            final = "discarded"
        await self._release_checkpointer()

        def close_rows(c: sqlite3.Connection) -> runs.RunStatus:
            nonlocal_final = final
            with store_db.transaction(c):
                current = runs.get_run(c, run.id)
                if (
                    active.stop_reason in ("stop", "discard")
                    and current is not None
                    and current.status == "done"
                ):
                    # The graph's ``save`` committed before the Stop/Discard landed: the run's
                    # results are saved, so it stays ``done`` (that Discard is refused). A crash
                    # after the commit still ends ``interrupted`` and Resume redoes the save (R9.5).
                    nonlocal_final = "done"
                for s in runs.list_steps(c, run.id):
                    for call in runs.list_llm_calls(c, s.id):
                        if call.status == "streaming":
                            runs.set_llm_call_status(c, call.id, call_status)
                runs.close_open_steps(c, step_status, run.id)
                finished = _now() if nonlocal_final in ("done", "failed", "discarded") else None
                runs.set_run_status(c, run.id, nonlocal_final, finished_at=finished, error=error)
            return nonlocal_final

        final = await self.db.run(close_rows)
        self.power.set_keep_awake(False)
        if final in ("done", "discarded"):
            await checkpoint.purge(self.checkpointer, run.id)
        progress = self._progress.get(run.id)
        if final in ("done", "failed", "discarded"):
            self._progress.pop(run.id, None)
        if final == "done":
            done_fields: dict[str, Any] = {}
            if progress is not None:
                progress.finish()
                done_fields = progress.fields()
            self.events.publish("run.done", run.id, run.thread_id, **done_fields)
            # rows the run's save queued (step 22.6.4: an extraction's key run) join the FIFO
            await self.poke()
        elif final == "stopped":
            self.events.publish("run.stopped", run.id, run.thread_id)
        elif final == "interrupted":
            self.events.publish("run.interrupted", run.id, run.thread_id)
        elif final == "failed":
            self.events.publish("run.failed", run.id, run.thread_id, error=error)
        elif final == "discarded":
            self.events.publish("run.discarded", run.id, run.thread_id)
