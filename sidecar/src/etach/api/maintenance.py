"""The daily maintenance run (data-model §5.5, plan step 20).

:class:`MaintenanceScheduler` runs :func:`run_maintenance` once at startup and then every
:data:`INTERVAL` (24 h) while the sidecar is up. One run does, in order:

1. the file **sweep** (:func:`etach.store.files.sweep`, 24 h grace);
2. the **checkpoint purge** of finished runs
   (:func:`etach.store.repos.runs.purge_finished_checkpoints`);
3. **log retention**: ``llm_calls`` older than ``settings.json`` ``log_retention_days`` (default
   45) are deleted, except calls an explanation references
   (:func:`etach.store.repos.runs.delete_llm_calls_before`).

Each run logs one ``maintenance:`` line (logger ``etach.maintenance``). The work is blocking SQLite
and disk I/O, so it runs in the thread pool on its own connection (§7 DB-access convention) and
never blocks the event loop. A failing run is logged and the schedule goes on.

Tests inject the clock (``now``) and the wait (``sleep``); ``create_app`` starts the scheduler
unless ``ctx.extra["maintenance.enabled"]`` is ``False``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from etach.api.deps import AppContext
from etach.api.routes.settings import log_retention_days
from etach.store import db
from etach.store.files import sweep
from etach.store.repos import runs

__all__ = [
    "ENABLED_KEY",
    "INTERVAL",
    "SCHEDULER_KEY",
    "MaintenanceReport",
    "MaintenanceScheduler",
    "run_maintenance",
]

log = logging.getLogger("etach.maintenance")

INTERVAL = timedelta(hours=24)
ENABLED_KEY = "maintenance.enabled"
SCHEDULER_KEY = "maintenance.scheduler"

Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class MaintenanceReport:
    at: datetime
    files_deleted: int
    orphans_removed: int
    checkpoint_rows_purged: int
    retention_days: int
    llm_calls_deleted: int


def run_maintenance(ctx: AppContext, now: datetime | None = None) -> MaintenanceReport:
    """One maintenance run (blocking: call it from a worker thread)."""
    now = now or _utcnow()
    days = log_retention_days(ctx)
    conn = db.connect(ctx.paths.db)
    try:
        swept = sweep(conn, ctx.paths, now=now)
        purged = runs.purge_finished_checkpoints(conn)
        deleted = runs.delete_llm_calls_before(conn, now - timedelta(days=days))
    finally:
        conn.close()
    report = MaintenanceReport(
        at=now,
        files_deleted=len(swept.deleted),
        orphans_removed=len(swept.orphans_removed),
        checkpoint_rows_purged=purged,
        retention_days=days,
        llm_calls_deleted=deleted,
    )
    log.info(
        "maintenance: swept %d files (%d orphans), purged %d checkpoint rows, "
        "deleted %d llm_calls older than %d days",
        report.files_deleted,
        report.orphans_removed,
        report.checkpoint_rows_purged,
        report.llm_calls_deleted,
        report.retention_days,
    )
    return report


class MaintenanceScheduler:
    """Runs :func:`run_maintenance` at :meth:`start` and every ``interval`` after the previous
    run was due (by the injected clock)."""

    def __init__(
        self,
        ctx: AppContext,
        *,
        interval: timedelta = INTERVAL,
        now: Clock = _utcnow,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.ctx = ctx
        self.interval = interval
        self.now = now
        self.sleep = sleep
        self.reports: list[MaintenanceReport] = []
        self._task: asyncio.Task[None] | None = None
        self._first = asyncio.Event()

    async def run_once(self) -> MaintenanceReport | None:
        """One run in the thread pool; ``None`` (and a logged error) if it failed."""
        try:
            report = await asyncio.to_thread(run_maintenance, self.ctx, self.now())
        except Exception:
            log.exception("maintenance: the run failed")
            return None
        self.reports.append(report)
        return report

    async def _loop(self) -> None:
        try:
            due = self.now()
            while True:
                await self.run_once()
                self._first.set()
                due += self.interval
                wait = (due - self.now()).total_seconds()
                await self.sleep(max(wait, 0.0))
        finally:
            self._first.set()

    async def start(self) -> None:
        """Start the loop; returns once the startup run finished (so the API serves after it)."""
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="etach-maintenance")
        await self._first.wait()

    async def aclose(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
