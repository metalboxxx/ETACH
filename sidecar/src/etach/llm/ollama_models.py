"""The model inventory on the app's own Ollama (step 22.3.5, llm-design §2 v4.31).

Ollama's own API, on the app's Ollama only (``ctx.ollama_url``: ``OLLAMA_MODELS`` =
``<app>\\data\\models``): ``GET /api/tags`` (installed models), ``POST /api/pull`` (a streamed
download; closing the stream stops it) and ``DELETE /api/delete``. The same small httpx calls
as :mod:`etach.llm.ollama_status`, with the same ``transport`` hook for tests.

:class:`FakeModelStore` is an in-memory Ollama for these three endpoints, used by the tests and
by ``etach serve --replay`` (the E2E's model manager), so no test pulls or deletes a real model.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Any

import httpx

__all__ = [
    "FakeModelStore",
    "InstalledModel",
    "ModelNotFound",
    "OllamaUnavailable",
    "PullFailed",
    "delete_model",
    "list_models",
    "plain_pull_error",
    "pull_model",
    "valid_tag",
]

_TIMEOUT = httpx.Timeout(10.0)
_TAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")


class OllamaUnavailable(RuntimeError):
    """The app's Ollama does not answer."""


class ModelNotFound(RuntimeError):
    """Ollama has no model with that name."""


class PullFailed(RuntimeError):
    """Ollama reported an error during a pull (the raw Ollama message)."""


@dataclass(frozen=True)
class InstalledModel:
    name: str
    size: int
    modified_at: str | None


def valid_tag(tag: str) -> bool:
    """A tag Ollama could accept: letters, digits and ``. _ : / -``, at most 200 characters."""
    return bool(_TAG.match(tag)) and ".." not in tag


def _client(base_url: str, transport: httpx.AsyncBaseTransport | None, **kw: Any) -> Any:
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/"), transport=transport, timeout=kw.get("timeout", _TIMEOUT)
    )


async def list_models(
    base_url: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> list[InstalledModel]:
    """``GET /api/tags``, sorted by name."""
    try:
        async with _client(base_url, transport) as http:
            resp = await http.get("/api/tags")
            resp.raise_for_status()
            items = resp.json().get("models") or []
    except (httpx.HTTPError, ValueError) as exc:
        raise OllamaUnavailable(str(exc)) from exc
    out = [
        InstalledModel(
            name=str(m.get("name") or m.get("model")),
            size=int(m.get("size") or 0),
            modified_at=str(m["modified_at"]) if m.get("modified_at") else None,
        )
        for m in items
        if m.get("name") or m.get("model")
    ]
    return sorted(out, key=lambda m: m.name.lower())


async def pull_model(
    base_url: str, name: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> AsyncIterator[dict[str, Any]]:
    """``POST /api/pull`` as progress dicts ``{status, completed, total}``; the last one has
    ``status == "success"``. An Ollama error line raises :class:`PullFailed`; no answer raises
    :class:`OllamaUnavailable`. Closing the generator (Cancel) closes the stream, which stops
    Ollama's download; Ollama writes the model's manifest only at ``success``, so a cancelled
    pull is never listed (its partial blobs are pruned by Ollama at its next start)."""
    timeout = httpx.Timeout(10.0, read=None)
    try:
        async with (
            _client(base_url, transport, timeout=timeout) as http,
            http.stream("POST", "/api/pull", json={"model": name, "stream": True}) as resp,
        ):
            if resp.status_code >= 400:
                body = (await resp.aread()).decode("utf-8", "replace")
                try:
                    message = str(json.loads(body).get("error", body))
                except ValueError:
                    message = body
                raise PullFailed(message or f"HTTP {resp.status_code}")
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                msg = json.loads(line)
                if "error" in msg:
                    raise PullFailed(str(msg["error"]))
                yield {
                    "status": str(msg.get("status", "")),
                    "completed": msg.get("completed"),
                    "total": msg.get("total"),
                }
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        raise OllamaUnavailable(str(exc)) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise PullFailed(str(exc)) from exc


async def delete_model(
    base_url: str, name: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> None:
    """``DELETE /api/delete``; 404 → :class:`ModelNotFound`."""
    try:
        async with _client(base_url, transport) as http:
            resp = await http.request("DELETE", "/api/delete", json={"model": name})
    except httpx.HTTPError as exc:
        raise OllamaUnavailable(str(exc)) from exc
    if resp.status_code == 404:
        raise ModelNotFound(name)
    if resp.status_code >= 400:
        raise OllamaUnavailable(f"HTTP {resp.status_code}: {resp.text[:200]}")


def plain_pull_error(raw: str) -> str:
    """Ollama's pull error in plain words for the teacher (comment 17)."""
    text = raw.lower()
    if "no space" in text or "disk full" in text or "not enough space" in text:
        return "Not enough disk space for this model. Free some space and try again."
    if "file does not exist" in text or "manifest unknown" in text or "not found" in text:
        return "No model with this name. Check the spelling of the tag."
    if any(
        k in text
        for k in ("dial tcp", "lookup", "no such host", "timeout", "connection", "network")
    ):
        return "No internet connection. Connect to the internet and try again."
    return f"The download failed: {raw}"


class FakeModelStore:
    """An in-memory Ollama for ``/api/version``, ``/api/tags``, ``/api/pull`` and
    ``/api/delete``. A pull streams ``pulling manifest``, ``downloading`` 0 → 100 % in
    ``steps`` lines (``delay`` seconds apart) and ``success``; the model is listed only after
    ``success``. ``fail_with`` makes the next pulls end with that Ollama error line.
    :attr:`disconnected` counts pulls whose reader went away before the end."""

    def __init__(
        self,
        models: Iterable[str] = (),
        *,
        size: int = 3_400_000_000,
        delay: float = 0.0,
        steps: int = 4,
    ) -> None:
        self.models: dict[str, int] = {name: size for name in dict.fromkeys(models)}
        self.size = size
        self.delay = delay
        self.steps = max(steps, 1)
        self.fail_with: str | None = None
        self.disconnected = 0
        self.pulls: list[str] = []

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _lines(self, name: str) -> Any:
        store = self

        class Stream(httpx.AsyncByteStream):
            def __init__(self) -> None:
                self.done = False

            async def __aiter__(self) -> AsyncIterator[bytes]:
                yield b'{"status":"pulling manifest"}\n'
                if store.fail_with:
                    self.done = True
                    yield (json.dumps({"error": store.fail_with}) + "\n").encode()
                    return
                for k in range(1, store.steps + 1):
                    if store.delay:
                        await asyncio.sleep(store.delay)
                    done = store.size * k // store.steps
                    msg = {"status": "downloading", "total": store.size, "completed": done}
                    yield (json.dumps(msg) + "\n").encode()
                store.models[name] = store.size
                self.done = True
                yield b'{"status":"success"}\n'

            async def aclose(self) -> None:
                if not self.done:
                    store.disconnected += 1

        return Stream()

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/api/version":
            return httpx.Response(200, json={"version": "0.13.1"})
        if request.method == "GET" and path == "/api/tags":
            models = [
                {"name": n, "model": n, "size": s, "modified_at": "2026-10-17T09:00:00Z"}
                for n, s in self.models.items()
            ]
            return httpx.Response(200, json={"models": models})
        if request.method == "POST" and path == "/api/pull":
            name = str(json.loads(request.content).get("model", ""))
            self.pulls.append(name)
            return httpx.Response(200, stream=self._lines(name))
        if request.method == "DELETE" and path == "/api/delete":
            name = str(json.loads(request.content).get("model", ""))
            if self.models.pop(name, None) is None:
                return httpx.Response(404, json={"error": f"model '{name}' not found"})
            return httpx.Response(200)
        return httpx.Response(404, json={"error": f"no route {path}"})
