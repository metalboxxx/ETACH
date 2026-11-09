"""``/review``: the Review queue and the resolution dispatch (llm-design §2, data-model §5.3).

``POST /review/{id}/resolve`` calls :func:`etach.domain.review.resolve` (its own transaction);
after the commit it pokes the run manager when follow-up runs were queued and publishes
``review.changed`` with ``{open: N}``. ``ReviewNotOpen`` → 409, ``InvalidResolution`` → 422,
an unknown item → 404.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from etach.api.deps import ConnDep, CtxDep
from etach.api.sse import publish
from etach.domain.models import ReviewItem
from etach.domain.review import InvalidResolution, ReviewNotOpen, resolve
from etach.store.repos import review

__all__ = ["router"]

router = APIRouter(tags=["review"])

ReviewStatus = Literal["open", "accepted", "fixed", "skipped", "obsolete"]


class ReviewCount(BaseModel):
    open: int


class Resolution(BaseModel):
    action: Literal["accept", "fix", "skip"]
    value: Any = None


class Resolved(BaseModel):
    item: ReviewItem
    followup_run_ids: list[str]


@router.get("/review", response_model=list[ReviewItem])
def list_review(conn: ConnDep, status: ReviewStatus | None = "open") -> list[ReviewItem]:
    """The queue (``status=open`` by default), oldest first: kind, refs, proposal, created_at."""
    return review.list_items(conn, status=status)


@router.get("/review/count", response_model=ReviewCount)
def review_count(conn: ConnDep) -> ReviewCount:
    """Review · N."""
    return ReviewCount(open=review.count_open(conn))


def _resolve_db(conn: ConnDep, id: str, body: Resolution) -> tuple[Resolved, int]:
    """The blocking part of :func:`resolve_item` (runs in the threadpool): the resolution and
    the open count after it."""
    if review.get_item(conn, id) is None:
        raise HTTPException(404, detail=f"no review item {id}")
    try:
        result = resolve(conn, id, body.action, body.value)
    except ReviewNotOpen as exc:
        raise HTTPException(409, detail=str(exc)) from None
    except InvalidResolution as exc:
        raise HTTPException(422, detail=str(exc)) from None
    resolved = Resolved(item=result.item, followup_run_ids=result.followup_run_ids)
    return resolved, review.count_open(conn)


@router.post("/review/{id}/resolve", response_model=Resolved)
async def resolve_item(id: str, body: Resolution, conn: ConnDep, ctx: CtxDep) -> Resolved:
    """Resolve one open item: ``{action: accept | fix | skip, value}``."""
    resolved, open_count = await run_in_threadpool(_resolve_db, conn, id, body)
    if resolved.followup_run_ids:
        await ctx.manager.poke()
    publish(ctx.events, "review.changed", open=open_count)
    return resolved
