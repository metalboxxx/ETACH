"""FakeOllama: an ``httpx.MockTransport`` that behaves like Ollama's HTTP API (plan step 4).

- ``POST /api/chat`` streams NDJSON chunks built from a :class:`ChatScript` (one script per
  request, in order; the last one repeats): content tokens, thinking tokens, logprobs with
  ``top_logprobs`` alternatives, a per-token delay, a connection reset after N tokens, a hang
  after N tokens (for cancellation), and the final ``done`` chunk with the counts.
- ``GET /api/version``, ``/api/tags`` and ``/api/ps`` answer from the constructor arguments.
- Each chat stream records whether the client disconnected before the stream finished
  (:attr:`FakeOllama.client_disconnected`, plan R4.3).

:class:`FakeOllamaServer` serves the same GET endpoints over real HTTP on a free local port (never
11434, where the teacher's own Ollama may run), for the other-Ollama detector (R4.9).
"""

from __future__ import annotations

import asyncio
import inspect
import json
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx

__all__ = [
    "ChatScript",
    "FakeOllama",
    "FakeOllamaServer",
    "StreamRecord",
    "logprob_entry",
    "tokenize",
]


def tokenize(text: str, size: int = 3) -> list[str]:
    """Split ``text`` into tokens of ``size`` characters (the last may be shorter)."""
    return [text[i : i + size] for i in range(0, len(text), size)]


def logprob_entry(token: str, logprob: float, alternatives: int) -> dict[str, Any]:
    data = list(token.encode("utf-8"))
    top = [{"token": token, "logprob": logprob, "bytes": data}]
    top += [
        {"token": f"<alt{k}>", "logprob": logprob - 1.0 - k, "bytes": list(f"<alt{k}>".encode())}
        for k in range(max(alternatives - 1, 0))
    ]
    return {"token": token, "logprob": logprob, "bytes": data, "top_logprobs": top}


@dataclass
class ChatScript:
    text: str | None = None  # the content, split with ``tokenize`` unless ``tokens`` is given
    tokens: list[str] | None = None
    thinking: str | None = None
    logprob: float = -0.01
    top_logprobs: int = 5
    with_logprobs: bool = True
    delay: float = 0.0  # seconds before each token
    reset_after: int | None = None  # raise a connection reset before token N (0-based)
    hang_after: int | None = None  # stop before token N and wait until the client goes away
    omit_done: bool = False  # end the stream without the final chunk
    status_code: int = 200
    error_chunk: str | None = None  # send {"error": ...} instead of the final chunk
    prompt_eval_count: int = 123
    total_duration_ns: int = 2_500_000_000

    def content_tokens(self) -> list[str]:
        if self.tokens is not None:
            return list(self.tokens)
        return tokenize(self.text or "")


@dataclass
class StreamRecord:
    script: ChatScript
    tokens_sent: int = 0
    finished: bool = False
    closed_early: bool = False


class _ChatStream(httpx.AsyncByteStream):
    def __init__(self, fake: FakeOllama, script: ChatScript, record: StreamRecord) -> None:
        self.fake = fake
        self.script = script
        self.record = record

    async def __aiter__(self) -> AsyncIterator[bytes]:
        s = self.script
        items = [("thinking", t) for t in tokenize(s.thinking or "")]
        items += [("content", t) for t in s.content_tokens()]
        for i, (kind, token) in enumerate(items):
            if self.fake.on_token is not None:
                result = self.fake.on_token(i)
                if inspect.isawaitable(result):
                    await result
            if s.hang_after is not None and i == s.hang_after:
                self.fake.hanging.set()
                await asyncio.Event().wait()
            if s.reset_after is not None and i == s.reset_after:
                raise httpx.ReadError("[WinError 10054] connection reset by peer (FakeOllama)")
            if s.delay:
                await asyncio.sleep(s.delay)
            chunk: dict[str, Any] = {
                "model": "fake",
                "created_at": "2026-01-01T00:00:00Z",
                "message": {"role": "assistant", "content": token if kind == "content" else ""},
                "done": False,
            }
            if kind == "thinking":
                chunk["message"]["thinking"] = token
            if s.with_logprobs:
                chunk["logprobs"] = [logprob_entry(token, s.logprob, s.top_logprobs)]
            self.record.tokens_sent += 1
            yield (json.dumps(chunk, ensure_ascii=False) + "\n").encode("utf-8")
        if s.error_chunk is not None:
            yield (json.dumps({"error": s.error_chunk}) + "\n").encode()
        elif not s.omit_done:
            final = {
                "model": "fake",
                "created_at": "2026-01-01T00:00:01Z",
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "done_reason": "stop",
                "total_duration": s.total_duration_ns,
                "load_duration": 1000,
                "prompt_eval_count": s.prompt_eval_count,
                "eval_count": len(items),
            }
            yield (json.dumps(final) + "\n").encode()
        self.record.finished = True

    async def aclose(self) -> None:
        if not self.record.finished:
            self.record.closed_early = True


class FakeOllama:
    def __init__(
        self,
        scripts: list[ChatScript] | None = None,
        *,
        version: str = "0.12.11",
        tags: list[str] | None = None,
        loaded: list[str] | None = None,
        on_token: Callable[[int], Awaitable[None] | None] | None = None,
    ) -> None:
        self.scripts = list(scripts or [ChatScript(text="{}")])
        self.version = version
        self.tags = list(tags or [])
        self.loaded = list(loaded or [])
        self.on_token = on_token
        self.requests: list[dict[str, Any]] = []  # /api/chat bodies, in order
        self.streams: list[StreamRecord] = []
        self.paths: list[str] = []
        self.hanging = asyncio.Event()

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    @property
    def client_disconnected(self) -> bool:
        return any(s.closed_early for s in self.streams)

    def _script(self) -> ChatScript:
        index = min(len(self.requests) - 1, len(self.scripts) - 1)
        return self.scripts[index]

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.paths.append(path)
        if request.method == "POST" and path == "/api/chat":
            self.requests.append(json.loads(request.content))
            script = self._script()
            if script.status_code != 200:
                return httpx.Response(script.status_code, json={"error": "fake failure"})
            record = StreamRecord(script)
            self.streams.append(record)
            return httpx.Response(
                200,
                headers={"content-type": "application/x-ndjson"},
                stream=_ChatStream(self, script, record),
            )
        if request.method == "GET" and path in _GET_PATHS:
            return httpx.Response(200, json=get_payload(path, self.version, self.tags, self.loaded))
        return httpx.Response(404, json={"error": f"no route {path}"})


_GET_PATHS = ("/api/version", "/api/tags", "/api/ps")


def get_payload(path: str, version: str, tags: list[str], loaded: list[str]) -> dict[str, Any]:
    if path == "/api/version":
        return {"version": version}
    if path == "/api/tags":
        return {"models": [{"name": t, "model": t, "size": 1} for t in tags]}
    return {"models": [{"name": t, "model": t, "size_vram": 1} for t in loaded]}


@dataclass
class FakeOllamaServer:
    """A real HTTP server on ``127.0.0.1:<free port>`` answering the GET endpoints."""

    version: str = "0.12.11"
    tags: list[str] = field(default_factory=list)
    loaded: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path not in _GET_PATHS:
                    self.send_error(404)
                    return
                body = json.dumps(
                    get_payload(self.path, owner.version, owner.tags, owner.loaded)
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: Any) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = int(self._server.server_address[1])
        self.base_url = f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> FakeOllamaServer:
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
