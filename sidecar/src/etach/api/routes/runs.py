"""``/runs``: the running indicator and Stop / Resume / Discard (llm-design §2, PRD D22).

A wrong state for an action raises ``InvalidRunState`` → 409 (the app's handler).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from etach.api.deps import ConnDep, CtxDep
from etach.domain.models import LlmCall, Run, Step
from etach.store.repos import runs

__all__ = ["ACTIVE_STATUSES", "router"]

ACTIVE_STATUSES: tuple[runs.RunStatus, ...] = (
    "running",
    "stopping",
    "queued",
    "stopped",
    "interrupted",
)

router = APIRouter(tags=["runs"])


class ActiveRun(BaseModel):
    run: Run
    current_step: Step | None
    # Run progress (llm-design §2, v4.20): the latest values, so the bar is right after a
    # reload or a restart. None when the run's kind has no stages or no stage has started.
    stage: int | None = None
    stages: int | None = None
    stage_label: str | None = None
    percent: int | None = None


class CallSummary(BaseModel):
    id: str
    role: str
    model: str
    task: str | None
    status: str


class StepDetail(BaseModel):
    step: Step
    calls: list[CallSummary]


class RunDetail(BaseModel):
    run: Run
    steps: list[StepDetail]


# Each graph node makes calls of one task (structure §7 "Run details"); these two nodes are named
# differently from their task. Every other node's name is its task.
_NODE_TASKS: dict[str, str] = {
    "retranscribe_tiles": "transcribe_page",
    "weak_points": "weak_points_summary",
}


def _task(call: LlmCall, node: str) -> str:
    """The call's task: ``request.task`` when stored, else the task its step's node calls."""
    request: dict[str, Any] = call.request
    task = request.get("task")
    if isinstance(task, str):
        return task
    return _NODE_TASKS.get(node, node)


def _active(conn: ConnDep, ctx: CtxDep, run: Run) -> ActiveRun:
    step = runs.latest_step(conn, run.id)
    progress = ctx.manager.progress_of(run, step.node if step is not None else None)
    return ActiveRun(run=run, current_step=step, **progress)


@router.get("/runs/active", response_model=list[ActiveRun])
def active_runs(conn: ConnDep, ctx: CtxDep) -> list[ActiveRun]:
    """Running, queued, stopped and interrupted runs, each with its current step and its
    progress (stage, stages, stage label, percent)."""
    return [_active(conn, ctx, run) for run in runs.list_runs_by_status(conn, ACTIVE_STATUSES)]


@router.get("/runs/{id}", response_model=RunDetail)
def get_run(id: str, conn: ConnDep) -> RunDetail:
    """The run, its steps and the model calls of each step."""
    run = runs.get_run(conn, id)
    if run is None:
        raise HTTPException(404, detail=f"no run {id}")
    steps = [
        StepDetail(
            step=step,
            calls=[
                CallSummary(
                    id=c.id, role=c.role, model=c.model, task=_task(c, step.node), status=c.status
                )
                for c in runs.list_llm_calls(conn, step.id)
            ],
        )
        for step in runs.list_steps(conn, id)
    ]
    return RunDetail(run=run, steps=steps)


def _check_exists(conn: ConnDep, run_id: str) -> None:
    if runs.get_run(conn, run_id) is None:
        raise HTTPException(404, detail=f"no run {run_id}")


async def _exists(conn: ConnDep, run_id: str) -> None:
    await run_in_threadpool(_check_exists, conn, run_id)


@router.post("/runs/{id}/stop", response_model=Run)
async def stop_run(id: str, conn: ConnDep, ctx: CtxDep) -> Run:
    """Stop a running or queued run (→ ``stopped``)."""
    await _exists(conn, id)
    return await ctx.manager.stop(id)


@router.post("/runs/{id}/resume", response_model=Run)
async def resume_run(id: str, conn: ConnDep, ctx: CtxDep) -> Run:
    """Resume a stopped or interrupted run (→ ``queued``; continues from its checkpoint)."""
    await _exists(conn, id)
    return await ctx.manager.resume(id)


@router.post("/runs/{id}/discard", response_model=Run)
async def discard_run(id: str, conn: ConnDep, ctx: CtxDep) -> Run:
    """Discard a run (→ ``discarded``; its checkpoint is purged)."""
    await _exists(conn, id)
    return await ctx.manager.discard(id)
