"""``/models``: the model manager (step 22.3.5, llm-design §2 v4.31, PRD D7 / §10).

- ``GET /models``: the models installed in the app's own Ollama, with size and the roles that
  use each, plus the role tags and the suggested tags (``etach.llm.defaults.SUGGESTED_TAGS``).
- ``POST /models/pull`` ``{name}``: the response itself is the progress stream
  (``text/event-stream``, one ``models.pull_progress`` event per Ollama line; the last has
  ``status`` ``"success"`` or ``"error"`` with a plain ``message``). **Cancel = close the
  request**: the stream to Ollama closes with it and Ollama stops the download. Each event is
  also published on ``GET /events``. 503 when Ollama does not answer; 409 while the same tag is
  already downloading.
- ``DELETE /models/{name}``: 409 while a role uses the model or a run is going; 404 when it is
  not installed; 503 when Ollama does not answer.

Only the app's own Ollama (``ctx.ollama_url``) is called, never another one. Tests inject a fake
through ``ctx.extra["ollama_transport"]``; ``etach serve --replay`` (no Ollama) uses an in-memory
:class:`etach.llm.ollama_models.FakeModelStore` holding the role tags and the suggested tags.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from etach.api.deps import AppContext, ConnDep, CtxDep
from etach.api.routes.system import current_config
from etach.api.sse import publish
from etach.llm import ollama_models
from etach.llm.defaults import DEFAULT_OLLAMA_URL, SUGGESTED_TAGS
from etach.llm.ollama_status import normalize_tag
from etach.store.repos import runs
from etach.store.repos.runs import RunStatus

__all__ = ["router"]

router = APIRouter(tags=["models"])

_FAKE = "models.fake_store"
_PULLING = "models.pulling"
_RUN_GOING: tuple[RunStatus, ...] = ("queued", "running", "stopping")

OLLAMA_DOWN = "Ollama is not running. Restart the app; if it keeps happening, reinstall it."
ROLE_USES = "This model is used by the {roles} role. Pick another model for it first."
RUN_GOING = "A run is going. Delete the model when it has finished."
PULLING = "This model is already downloading."


class InstalledModel(BaseModel):
    name: str
    size: int
    modified_at: str | None
    #: The roles (``vision``, ``reasoning``) whose model tag is this model.
    roles: list[str]


class ModelInventory(BaseModel):
    models: list[InstalledModel]
    #: Role → configured tag (installed or not).
    roles: dict[str, str]
    #: Tags offered for download, the current defaults first.
    suggested: list[str]


class PullRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


def _transport(ctx: AppContext) -> Any:
    transport = ctx.extra.get("ollama_transport")
    if transport is None and ctx.replay:
        store = ctx.extra.get(_FAKE)
        if store is None:
            tags = [r.model for r in current_config(ctx).roles.values()]
            store = ollama_models.FakeModelStore([*tags, *SUGGESTED_TAGS], delay=0.3, steps=6)
            ctx.extra[_FAKE] = store
        transport = store.transport
    return transport


def _base(ctx: AppContext) -> str:
    return ctx.ollama_url or DEFAULT_OLLAMA_URL


def _roles_using(ctx: AppContext, name: str) -> list[str]:
    tag = normalize_tag(name)
    return [
        role for role, cfg in current_config(ctx).roles.items() if normalize_tag(cfg.model) == tag
    ]


@router.get("/models", response_model=ModelInventory, responses={503: {"description": OLLAMA_DOWN}})
async def get_models(ctx: CtxDep) -> ModelInventory:
    """Installed Ollama models: ``name``, ``size``, ``modified_at``, and the roles using each."""
    try:
        installed = await ollama_models.list_models(_base(ctx), transport=_transport(ctx))
    except ollama_models.OllamaUnavailable:
        raise HTTPException(503, detail=OLLAMA_DOWN) from None
    return ModelInventory(
        models=[
            InstalledModel(
                name=m.name, size=m.size, modified_at=m.modified_at, roles=_roles_using(ctx, m.name)
            )
            for m in installed
        ],
        roles={role: cfg.model for role, cfg in current_config(ctx).roles.items()},
        suggested=list(SUGGESTED_TAGS),
    )


def _event(ctx: AppContext, name: str, **data: Any) -> bytes:
    payload = {"model": name, "completed": None, "total": None, "message": None, **data}
    publish(ctx.events, "models.pull_progress", **payload)
    return f"event: models.pull_progress\ndata: {json.dumps(payload)}\n\n".encode()


async def _pull_events(ctx: AppContext, name: str) -> AsyncIterator[bytes]:
    try:
        async for msg in ollama_models.pull_model(_base(ctx), name, transport=_transport(ctx)):
            yield _event(ctx, name, **msg)
    except ollama_models.OllamaUnavailable:
        yield _event(ctx, name, status="error", message=OLLAMA_DOWN)
    except ollama_models.PullFailed as exc:
        message = ollama_models.plain_pull_error(str(exc))
        yield _event(ctx, name, status="error", message=message)


class _PullResponse(StreamingResponse):
    """The pull's event stream; ``on_end`` runs however the request ends (done, error, the app
    closing it, or a disconnect before the first event), so the tag is never left marked as
    downloading."""

    def __init__(self, content: AsyncIterator[bytes], on_end: Callable[[], None]) -> None:
        super().__init__(
            content, media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )
        self._on_end = on_end

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._on_end()
            aclose = getattr(self.body_iterator, "aclose", None)
            if aclose is not None:
                await aclose()  # a generator that never started is closed too


@router.post(
    "/models/pull",
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "Progress events"},
        409: {"description": PULLING},
        422: {"description": "Not a model tag"},
        503: {"description": OLLAMA_DOWN},
    },
)
async def pull_model(body: PullRequest, ctx: CtxDep) -> StreamingResponse:
    """``{name}``: pull one model; progress events over SSE (this response); closing the request
    cancels the download."""
    name = body.name.strip()
    if not ollama_models.valid_tag(name):
        raise HTTPException(422, detail="Not a model tag. A tag looks like name:size.")
    try:  # answer 503 now, while the status code can still change
        await ollama_models.list_models(_base(ctx), transport=_transport(ctx))
    except ollama_models.OllamaUnavailable:
        raise HTTPException(503, detail=OLLAMA_DOWN) from None
    pulling: set[str] = ctx.extra.setdefault(_PULLING, set())
    if normalize_tag(name) in pulling:
        raise HTTPException(409, detail=PULLING)
    tag = normalize_tag(name)
    pulling.add(tag)
    return _PullResponse(_pull_events(ctx, name), lambda: pulling.discard(tag))


@router.delete(
    "/models/{name:path}",
    status_code=204,
    responses={
        404: {"description": "Not installed"},
        409: {"description": "Used by a role, or a run is going"},
        503: {"description": OLLAMA_DOWN},
    },
)
async def delete_model(name: str, ctx: CtxDep, conn: ConnDep) -> None:
    """Delete an installed model; 409 while a role uses it or a run is active."""
    roles = _roles_using(ctx, name)
    if roles:
        raise HTTPException(409, detail=ROLE_USES.format(roles=" and ".join(roles)))
    if runs.list_runs_by_status(conn, _RUN_GOING):
        raise HTTPException(409, detail=RUN_GOING)
    try:
        await ollama_models.delete_model(_base(ctx), name, transport=_transport(ctx))
    except ollama_models.ModelNotFound:
        raise HTTPException(404, detail=f"{name} is not installed.") from None
    except ollama_models.OllamaUnavailable:
        raise HTTPException(503, detail=OLLAMA_DOWN) from None
