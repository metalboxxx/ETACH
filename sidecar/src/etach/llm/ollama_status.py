"""Ollama checks: the version and model check at startup, and the other-Ollama detector.

- :func:`check` → ``ok | too_old | missing_model | unreachable`` (llm-design §3.2: Ollama ≥
  0.12.11 and every role's model pulled; otherwise Settings shows **Download models**).
- :func:`other_ollama_loaded`: whether a separately started Ollama on the default port has a
  model loaded (PRD R7: it would compete for the GPU).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

import httpx

from etach.llm.config import RoleConfig
from etach.llm.defaults import DEFAULT_OLLAMA_URL, MIN_OLLAMA_VERSION

__all__ = [
    "OllamaStatus",
    "check",
    "normalize_tag",
    "other_ollama_loaded",
    "parse_version",
]

StatusKind = Literal["ok", "too_old", "missing_model", "unreachable"]

_TIMEOUT = httpx.Timeout(5.0)


@dataclass(frozen=True)
class OllamaStatus:
    status: StatusKind
    version: str | None = None
    missing: list[str] = field(default_factory=list)


def parse_version(text: str) -> tuple[int, int, int] | None:
    """``"0.12.11"`` (or ``"v0.12.11-rc1"``) → ``(0, 12, 11)``; ``None`` if unreadable."""
    match = re.match(r"^v?(\d+)\.(\d+)(?:\.(\d+))?", text.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)


def normalize_tag(tag: str) -> str:
    """Compare model tags the way Ollama resolves them: case-insensitive, ``:latest`` implied,
    the default registry and ``library/`` namespace dropped."""
    name = tag.strip().lower()
    for prefix in ("registry.ollama.ai/", "library/"):
        if name.startswith(prefix):
            name = name[len(prefix) :]
    if ":" not in name.rsplit("/", 1)[-1]:
        name += ":latest"
    return name


def _client(base_url: str, transport: httpx.AsyncBaseTransport | None) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url.rstrip("/"), transport=transport, timeout=_TIMEOUT)


async def check(
    base_url: str,
    roles: Iterable[RoleConfig],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> OllamaStatus:
    """The startup check: version first, then the role models (``/api/tags``)."""
    try:
        async with _client(base_url, transport) as http:
            version_resp = await http.get("/api/version")
            version_resp.raise_for_status()
            version = str(version_resp.json().get("version", ""))
            parsed = parse_version(version)
            if parsed is None or parsed < MIN_OLLAMA_VERSION:
                return OllamaStatus("too_old", version=version)
            tags_resp = await http.get("/api/tags")
            tags_resp.raise_for_status()
            models = tags_resp.json().get("models") or []
    except (httpx.HTTPError, ValueError):
        return OllamaStatus("unreachable")
    present = {
        normalize_tag(str(m.get(key))) for m in models for key in ("name", "model") if m.get(key)
    }
    wanted = list(dict.fromkeys(role.model for role in roles))
    missing = [tag for tag in wanted if normalize_tag(tag) not in present]
    if missing:
        return OllamaStatus("missing_model", version=version, missing=missing)
    return OllamaStatus("ok", version=version)


async def other_ollama_loaded(
    base_url: str = DEFAULT_OLLAMA_URL,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    timeout: float = 2.0,
) -> bool:
    """``True`` when an Ollama at ``base_url`` lists a loaded model in ``/api/ps``; ``False``
    when it lists none, or nothing answers."""
    try:
        async with httpx.AsyncClient(
            base_url=base_url.rstrip("/"), transport=transport, timeout=timeout
        ) as http:
            response = await http.get("/api/ps")
            response.raise_for_status()
            return bool(response.json().get("models"))
    except (httpx.HTTPError, ValueError):
        return False
