"""LangGraph's checkpointer in the app database (llm-design §7).

- ``AsyncSqliteSaver`` (``langgraph-checkpoint-sqlite``) on its own ``aiosqlite`` connection to
  the **same** ``app.db``. It creates its ``checkpoints`` and ``writes`` tables on first use.
- The connection uses WAL and the same ``busy_timeout`` as the app connections
  (:data:`etach.store.db.BUSY_TIMEOUT_MS`), so a checkpoint write and an app write wait for each
  other instead of failing with ``database is locked`` (plan R7.9).
- Graphs run with :data:`DURABILITY` = ``"sync"``: each superstep's checkpoint is committed
  before the next node starts.
- Every write of the saver (:class:`ShieldedSaver`) runs ``execute`` + ``commit`` as one unit a
  Stop cannot cut: a cancellation between the two would leave a write transaction open, holding
  the SQLite write lock, and every other writer would fail with ``database is locked``.
- The LangGraph ``thread_id`` of a run is its ``runs.id``; :func:`purge` deletes every checkpoint
  and pending write of a run (on ``done`` and ``discarded``).
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import AsyncIterator, Awaitable, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import aiosqlite
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import ChannelVersions, Checkpoint, CheckpointMetadata
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from etach.store.db import BUSY_TIMEOUT_MS

__all__ = [
    "CHECKPOINT_TABLES",
    "DURABILITY",
    "ShieldedSaver",
    "checkpoint_row_count",
    "has_checkpoint",
    "open_checkpointer",
    "purge",
    "run_config",
    "uninterruptible",
]

DURABILITY: Literal["sync"] = "sync"
CHECKPOINT_TABLES = ("checkpoints", "writes")


def run_config(run_id: str, **extra: Any) -> RunnableConfig:
    """The LangGraph config of a run: ``thread_id`` = the run ID."""
    return {"configurable": {"thread_id": run_id}, **extra}  # type: ignore[typeddict-item]


async def uninterruptible[T](work: Awaitable[T]) -> T:
    """Await ``work`` to the end even if the caller is cancelled (once or several times); the
    cancellation is then re-raised. For short database writes that must not stop half-way."""
    task = asyncio.ensure_future(work)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.done() and task.cancelled():
                raise
            cancelled = True
    result = task.result()
    if cancelled:
        raise asyncio.CancelledError
    return result


class ShieldedSaver(AsyncSqliteSaver):
    """``AsyncSqliteSaver`` whose writes (``execute`` + ``commit``) a cancellation cannot cut."""

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return await uninterruptible(super().aput(config, checkpoint, metadata, new_versions))

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        await uninterruptible(super().aput_writes(config, writes, task_id, task_path))

    async def adelete_thread(self, thread_id: str) -> None:
        await uninterruptible(super().adelete_thread(thread_id))


@asynccontextmanager
async def open_checkpointer(db_path: Path | str) -> AsyncIterator[AsyncSqliteSaver]:
    """An ``AsyncSqliteSaver`` on ``db_path`` with WAL + ``busy_timeout``, tables created.

    Must be entered on the event loop that runs the graphs; the connection is closed on exit.
    """
    conn = await aiosqlite.connect(Path(db_path), timeout=BUSY_TIMEOUT_MS / 1000)
    try:
        await conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        async with conn.execute("PRAGMA journal_mode = WAL") as cur:
            row = await cur.fetchone()
        if row is None or str(row[0]).lower() != "wal":
            raise sqlite3.OperationalError(f"checkpointer could not switch to WAL (got {row!r})")
        saver = ShieldedSaver(conn)
        await saver.setup()
        yield saver
    finally:
        await conn.close()


async def has_checkpoint(saver: AsyncSqliteSaver, run_id: str) -> bool:
    """Whether the run has a checkpoint to resume from."""
    return await saver.aget_tuple(run_config(run_id)) is not None


async def purge(saver: AsyncSqliteSaver, run_id: str) -> None:
    """Delete all checkpoints and pending writes of the run."""
    await saver.adelete_thread(run_id)


def checkpoint_row_count(conn: sqlite3.Connection, run_id: str) -> int:
    """Rows in ``checkpoints`` + ``writes`` for the run (0 when the tables do not exist yet)."""
    total = 0
    for table in CHECKPOINT_TABLES:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        if exists:
            total += conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE thread_id = ?", (run_id,)
            ).fetchone()[0]
    return total
