"""``/settings``: model tags, the data folder, log retention, and model downloads (llm-design §2,
PRD §10.2, §11).

- The model roles live in ``<data>/models.toml`` (llm-design §3.1); ``log_retention_days`` in
  ``settings.json`` (default 45; the file may be absent): in the app folder for the installed
  layout (PRD §11), in the data folder when ``--data`` was given (dev, tests, CLI); see
  :func:`etach.appdir.settings_json_path`. ``ctx.extra["settings_path"]`` carries the resolved
  path (a caller that knows whether ``--data`` was explicit may set it).
- ``PUT /settings`` writes both, then **swaps the running client's config**
  (``ctx.client.config``), so the next model call uses the new tag without a restart. A run in
  the middle of a call keeps the tag it started that call with.
- ``POST /settings/models/pull`` streams Ollama ``/api/pull`` for each configured model in a
  background task and publishes ``models.pull_progress`` ``{model, status, completed, total}``;
  the last event of a model has ``status`` ``"success"`` or ``"error: …"``. Tests inject a fake
  Ollama through ``ctx.extra["ollama_transport"]``.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from etach.api.deps import AppContext, CtxDep
from etach.api.routes.system import current_config
from etach.api.sse import publish
from etach.appdir import settings_json_path
from etach.llm.config import ConfigError, write_models_config
from etach.llm.defaults import DEFAULT_OLLAMA_URL

__all__ = [
    "DEFAULT_LOG_RETENTION_DAYS",
    "FAKE_PULL_ENV",
    "SETTINGS_PATH",
    "fake_pull_transport",
    "log_retention_days",
    "read_app_settings",
    "router",
    "settings_path",
]

router = APIRouter(tags=["settings"])

DEFAULT_LOG_RETENTION_DAYS = 45
_PULLS = "settings.pull_tasks"
SETTINGS_PATH = "settings_path"


def settings_path(ctx: AppContext) -> Path:
    """The resolved ``settings.json`` path, carried by ``ctx.extra["settings_path"]`` (resolved
    once with :func:`etach.appdir.settings_json_path` when nothing set it)."""
    path = ctx.extra.get(SETTINGS_PATH)
    if not isinstance(path, Path):
        path = settings_json_path(ctx.paths)
        ctx.extra[SETTINGS_PATH] = path
    return path


def read_app_settings(ctx: AppContext) -> dict[str, Any]:
    path = settings_path(ctx)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def log_retention_days(ctx: AppContext) -> int:
    """``settings.json`` ``log_retention_days`` (a positive int), else 45 (data-model §5.5)."""
    value = read_app_settings(ctx).get("log_retention_days", DEFAULT_LOG_RETENTION_DAYS)
    return value if isinstance(value, int) and value > 0 else DEFAULT_LOG_RETENTION_DAYS


class RoleSettings(BaseModel):
    model: str
    options: dict[str, Any]


class Settings(BaseModel):
    roles: dict[str, RoleSettings]
    data_folder: str
    log_retention_days: int


class RoleUpdate(BaseModel):
    model: str = Field(min_length=1)
    options: dict[str, Any] | None = None


class SettingsUpdate(BaseModel):
    roles: dict[str, RoleUpdate] | None = None
    log_retention_days: int | None = Field(default=None, ge=1)


class PullStarted(BaseModel):
    models: list[str]


def _settings(ctx: AppContext) -> Settings:
    config = current_config(ctx)
    return Settings(
        roles={
            name: RoleSettings(model=role.model, options=dict(role.options))
            for name, role in config.roles.items()
        },
        data_folder=str(ctx.paths.root),
        log_retention_days=log_retention_days(ctx),
    )


@router.get("/settings", response_model=Settings)
def get_settings(ctx: CtxDep) -> Settings:
    """Model tag per role, the data folder, log retention."""
    return _settings(ctx)


@router.put("/settings", response_model=Settings)
def put_settings(body: SettingsUpdate, ctx: CtxDep) -> Settings:
    """Update the role model tags / options (``models.toml``) and ``log_retention_days``
    (``settings.json``)."""
    if body.roles:
        models = {name: r.model for name, r in body.roles.items()}
        if any(not tag.strip() for tag in models.values()):
            raise HTTPException(422, detail="model tags must be non-empty")
        options = {name: r.options for name, r in body.roles.items() if r.options}
        try:
            config = write_models_config(ctx.paths, models, options)
        except ConfigError as exc:
            raise HTTPException(422, detail=str(exc)) from None
        if ctx.client is not None and hasattr(ctx.client, "config"):
            ctx.client.config = config
    if body.log_retention_days is not None:
        data = read_app_settings(ctx)
        data["log_retention_days"] = body.log_retention_days
        path = settings_path(ctx)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
    return _settings(ctx)


FAKE_PULL_ENV = "ETACH_FAKE_OLLAMA_PULL"
"""Test hook (plan R20.5 E2E): when set to a number of milliseconds (``"0"`` allowed), the pull
talks to :func:`fake_pull_transport` instead of an Ollama, waiting that long between lines."""


def fake_pull_transport(delay_ms: int = 0) -> httpx.AsyncBaseTransport:
    """A fake Ollama ``/api/pull`` stream: ``pulling manifest``, two ``downloading`` lines (40 %,
    100 % of 100 bytes), ``success``. Anything else is a 404."""

    async def lines() -> Any:
        for msg in (
            {"status": "pulling manifest"},
            {"status": "downloading", "digest": "sha256:fake", "total": 100, "completed": 40},
            {"status": "downloading", "digest": "sha256:fake", "total": 100, "completed": 100},
            {"status": "success"},
        ):
            if delay_ms:
                await asyncio.sleep(delay_ms / 1000)
            yield (json.dumps(msg) + "\n").encode()

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/pull":
            return httpx.Response(200, content=lines())
        return httpx.Response(404, json={"error": f"no route {request.url.path}"})

    return httpx.MockTransport(handle)


def _pull_transport(ctx: AppContext) -> Any:
    transport: Any = ctx.extra.get("ollama_transport")
    if transport is None:
        fake = os.environ.get(FAKE_PULL_ENV, "").strip()
        if fake:
            transport = fake_pull_transport(int(fake) if fake.isdigit() else 0)
    return transport


async def _pull(ctx: AppContext, models: list[str]) -> None:
    transport = _pull_transport(ctx)
    if transport is None and ctx.replay:
        # --replay has no Ollama; never reach for a real one on the default port.
        for model in models:
            publish(
                ctx.events,
                "models.pull_progress",
                model=model,
                status="error: no Ollama in replay mode",
                completed=None,
                total=None,
            )
        return
    base = (ctx.ollama_url or DEFAULT_OLLAMA_URL).rstrip("/")
    timeout = httpx.Timeout(10.0, read=None)
    async with httpx.AsyncClient(base_url=base, transport=transport, timeout=timeout) as http:
        for model in models:
            try:
                async with http.stream(
                    "POST", "/api/pull", json={"model": model, "stream": True}
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        msg = json.loads(line)
                        if "error" in msg:
                            raise RuntimeError(str(msg["error"]))
                        publish(
                            ctx.events,
                            "models.pull_progress",
                            model=model,
                            status=str(msg.get("status", "")),
                            completed=msg.get("completed"),
                            total=msg.get("total"),
                        )
            except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                publish(
                    ctx.events,
                    "models.pull_progress",
                    model=model,
                    status=f"error: {exc}",
                    completed=None,
                    total=None,
                )


@router.post("/settings/models/pull", response_model=PullStarted, status_code=202)
async def pull_models(ctx: CtxDep) -> PullStarted:
    """Download the configured models (``ollama pull``); progress goes out as
    ``models.pull_progress`` over SSE."""
    models = list(dict.fromkeys(role.model for role in current_config(ctx).roles.values()))
    tasks: set[asyncio.Task[None]] = ctx.extra.setdefault(_PULLS, set())
    task = asyncio.create_task(_pull(ctx, models))
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return PullStarted(models=models)
