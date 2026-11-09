"""``GET /system/status``: Ollama, the models, the other-Ollama warning and power (llm-design §2),
plus the sidecar's own version and whether it replays cassettes (step 21: Settings, first run).

Never a 500: an Ollama that does not answer gives ``ollama_status: "unreachable"`` with nulls. In
``--replay`` mode there is no Ollama, so the status is ``unreachable`` too.

Tests inject fakes through ``ctx.extra``: ``"ollama_transport"`` (our Ollama) and
``"other_ollama_transport"`` (the default port, for the other-Ollama detector).

``system.changed`` is published by :func:`publish_status` when the status differs from the last
one this process saw (each ``GET`` compares). A periodic poll is not built yet: the frontend
polls this route (or a later step adds a background check that calls :func:`publish_status`).
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel

from etach import __version__
from etach.api.deps import AppContext, CtxDep
from etach.api.sse import publish
from etach.llm import ollama_status
from etach.llm.config import ConfigError, ModelsConfig, load_models_config
from etach.llm.defaults import DEFAULT_OLLAMA_URL
from etach.runtime.power import PowerSource

__all__ = ["SystemStatus", "current_config", "publish_status", "router", "system_status"]

router = APIRouter(tags=["system"])

_LAST = "system.last_status"


class SystemStatus(BaseModel):
    #: ``etach --version`` of this sidecar (Settings shows it; R21.2 compares the frozen one).
    sidecar_version: str
    #: ``etach serve --replay``: cassettes stand in for Ollama, so ``unreachable`` is expected and
    #: the first-run setup screen stays hidden (step 21).
    replay: bool
    ollama_version: str | None
    ollama_status: Literal["ok", "too_old", "missing_model", "unreachable"]
    models_present: list[str] | None
    missing_models: list[str] | None
    other_ollama_loaded: bool
    power_source: PowerSource
    keep_awake: bool


def current_config(ctx: AppContext) -> ModelsConfig:
    """The models config the running client uses (or ``models.toml`` without a client)."""
    config = getattr(ctx.client, "config", None)
    if isinstance(config, ModelsConfig):
        return config
    return load_models_config(ctx.paths)


async def system_status(ctx: AppContext) -> SystemStatus:
    try:
        roles = list(current_config(ctx).roles.values())
    except ConfigError:
        roles = []
    transport: Any = ctx.extra.get("ollama_transport")
    if ctx.replay and transport is None:
        status = ollama_status.OllamaStatus("unreachable")
    else:
        status = await ollama_status.check(
            ctx.ollama_url or DEFAULT_OLLAMA_URL, roles, transport=transport
        )
    other_transport: Any = ctx.extra.get("other_ollama_transport")
    own_is_default = (ctx.ollama_url or "").rstrip("/") == DEFAULT_OLLAMA_URL and not ctx.replay
    if own_is_default and other_transport is None:
        other = False  # the default port is our own Ollama
    else:
        other = await ollama_status.other_ollama_loaded(transport=other_transport)
    present: list[str] | None = None
    missing: list[str] | None = None
    if status.status in ("ok", "missing_model"):
        wanted = list(dict.fromkeys(role.model for role in roles))
        missing = list(status.missing)
        present = [tag for tag in wanted if tag not in missing]
    return SystemStatus(
        sidecar_version=__version__,
        replay=ctx.replay,
        ollama_version=status.version if status.status != "unreachable" else None,
        ollama_status=status.status,
        models_present=present,
        missing_models=missing,
        other_ollama_loaded=other,
        power_source=ctx.power.power_source(),
        keep_awake=ctx.power.keep_awake,
    )


def publish_status(ctx: AppContext, status: SystemStatus) -> bool:
    """Publish ``system.changed`` when ``status`` differs from the last one seen."""
    data = status.model_dump()
    if ctx.extra.get(_LAST) == data:
        return False
    first = _LAST not in ctx.extra
    ctx.extra[_LAST] = data
    if first:
        return False
    publish(ctx.events, "system.changed", **data)
    return True


@router.get("/system/status", response_model=SystemStatus)
async def get_system_status(ctx: CtxDep) -> SystemStatus:
    """Ollama version and status, models present / missing, other-Ollama warning, power source,
    keep-awake."""
    status = await system_status(ctx)
    publish_status(ctx, status)
    return status
