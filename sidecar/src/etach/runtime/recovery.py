"""Startup recovery (llm-design §7, plan R7.2, R7.3).

Runs once when the sidecar starts, before the run manager takes runs from the queue:

- ``running`` → ``interrupted`` (and ``run.interrupted`` is published);
- ``stopping`` → ``stopped``;
- ``queued`` stays ``queued`` (the manager runs it);
- open (``running``) steps → ``incomplete``;
- ``streaming`` model calls → ``incomplete``.

The indicator then offers Resume / Discard for the ``interrupted`` and ``stopped`` runs.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from etach.runtime.events import EventBus
from etach.runtime.steps import Db
from etach.store.db import transaction
from etach.store.repos import runs

__all__ = ["Recovered", "recover", "recover_rows"]


@dataclass
class Recovered:
    interrupted: list[tuple[str, str]] = field(default_factory=list)  # (run_id, thread_id)
    stopped: list[str] = field(default_factory=list)
    queued: list[str] = field(default_factory=list)
    steps_incomplete: list[str] = field(default_factory=list)
    calls_incomplete: list[str] = field(default_factory=list)


def recover_rows(conn: sqlite3.Connection) -> Recovered:
    """The database part of recovery, in one transaction. Publishes nothing."""
    out = Recovered()
    with transaction(conn):
        open_runs = runs.list_runs(conn, status="running") + runs.list_runs(conn, status="stopping")
        for run in open_runs:
            for s in runs.list_steps(conn, run.id):
                for call in runs.list_llm_calls(conn, s.id):
                    if call.status == "streaming":
                        runs.set_llm_call_status(conn, call.id, "incomplete")
                        out.calls_incomplete.append(call.id)
        out.steps_incomplete = runs.close_open_steps(conn, "incomplete")
        for run in open_runs:
            if run.status == "running":
                runs.set_run_status(conn, run.id, "interrupted")
                out.interrupted.append((run.id, run.thread_id))
            else:
                runs.set_run_status(conn, run.id, "stopped")
                out.stopped.append(run.id)
        out.queued = [r.id for r in runs.list_runs(conn, status="queued")]
    return out


async def recover(db: Db, events: EventBus) -> Recovered:
    """Recover the rows, then publish ``run.interrupted`` for each interrupted run."""
    out = await db.run(recover_rows)
    for run_id, thread_id in out.interrupted:
        events.publish("run.interrupted", run_id, thread_id)
    return out
