"""The model-agnostic Ollama client (llm-design §3.2, plan step 4).

``OllamaClient.call(role, task, inputs, schema, *, step_id, …)``:

1. renders the prompt through a :class:`PromptProvider` and builds the ``/api/chat`` body with
   the role's adapter;
2. inserts an ``llm_calls`` row as ``streaming`` and streams the answer, updating
   ``response_text`` / ``thinking_text`` / ``logprobs`` every ~50 tokens or 1 s;
3. at the end of the stream records ``tokens_in`` / ``tokens_out`` / ``ms`` and validates with
   pydantic: valid → ``complete`` and a :class:`CallResult`; invalid → ``invalid`` and one retry
   (a new row) with the validation error appended; invalid twice → a :class:`CallFailure`.
   The client never writes Review items (P8);
4. a dropped stream (connection reset, read error, no final chunk) → the row is ``error`` and
   the call is retried once as a new row; a second drop raises :class:`StreamDropped` (the
   runtime turns it into ``interrupted``). Drop and validation retries are separate budgets;
5. cancellation → the row is ``cancelled`` with the partial text kept, the HTTP stream is
   closed, and ``CancelledError`` propagates.

6. a prompt that does not fit ``num_ctx`` (bug B1: Ollama silently dropped the template and
   instructions and kept only the image) fails loudly instead of being answered from a part of
   the prompt. Every body carries ``truncate: false`` (Ollama 0.40 ``ChatRequest.Truncate``:
   don't drop chat messages to fit the context), and the client checks the size itself
   (:func:`prompt_size`, a lower and an upper bound on the prompt's tokens): before the call,
   a lower bound above ``num_ctx``; after it, a prompt that may not fit (upper bound above
   ``num_ctx``) of which Ollama's ``prompt_eval_count`` read fewer tokens than the text alone
   has; and an Ollama error that says the input is longer than the context. Each gives a
   :class:`CallFailure` whose reason starts with ``prompt_truncated:``, with no retry (the
   same prompt would fail again), the row ``error`` and a logged warning; the graph treats it
   like any failed call (llm-design §5.1, e.g. a ``validator_failed`` page).

7. an invalid output that stopped because it hit ``num_predict`` (Ollama ``done_reason:
   "length"``, or ``tokens_out`` ≥ the request's ``num_predict``) is not retried (speed bundle 1):
   at temperature 0 the retry repeats the same truncation. The row is ``invalid`` and the call
   returns a :class:`CallFailure` at once, its reason starting with ``output_capped:``; the
   graph treats it like any failed call (llm-design §5.1). Other invalid outputs keep their
   one retry. This is per role: ``models.toml`` ``[client] retry_capped_output = { vision =
   false, reasoning = true }`` (the default: grading keeps the retry until M2).

8. while a call streams, the step's :data:`token_listener` (set by the runtime's step wrapper) is
   called with ``(step_id, tokens so far)`` at most every :data:`HEARTBEAT_SECONDS`, so the
   running indicator shows that a long call is still writing (llm-design §2 "Run progress",
   v4.20). Nothing is published per token.

Confidence is not computed here (step 6): the result carries the raw logprobs.

DB writes run in ``asyncio.to_thread`` under one lock per client (structure.md §7), except the
final write of a cancelled call, which runs synchronously so a second cancellation cannot skip it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping, Sequence
from contextlib import aclosing
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ValidationError

from etach.domain.models import LlmCall
from etach.llm import cassettes
from etach.llm.adapters import (
    AdapterRequest,
    ImageInput,
    PromptProvider,
    RenderedPrompt,
    build_request,
    is_plain_text,
    sha256_hex,
)
from etach.llm.config import ModelsConfig, Role
from etach.store.db import new_ulid, transaction
from etach.store.repos import runs

__all__ = [
    "CallFailure",
    "CallResult",
    "ChatBackend",
    "HttpBackend",
    "OllamaClient",
    "OllamaError",
    "PromptProvider",
    "PromptSize",
    "RenderedPrompt",
    "StreamDropped",
    "TokenListener",
    "prompt_hash",
    "prompt_size",
    "token_listener",
]

#: The most characters one token of our prompts covers. English averages ~4, Vietnamese and
#: JSON keys fewer; 8 also covers the whitespace runs of an indented template. So
#: ``chars / 8`` is a lower bound: a whole prompt never counts fewer tokens.
MAX_CHARS_PER_TOKEN = 8
#: The fewest characters per token, for the upper bound (Vietnamese diacritics run near 2).
MIN_CHARS_PER_TOKEN = 2
#: Tokens of one page image: at least (Ollama's own truncation heuristic uses 768) and at most
#: (NuExtract3 pages measured ~1900 in the M1 baseline).
MIN_IMAGE_TOKENS = 256
MAX_IMAGE_TOKENS = 4096
TRUNCATED = "prompt_truncated"
CAPPED = "output_capped"
#: Ollama error texts that mean "the prompt is longer than the context" (0.40.1 sources).
_CONTEXT_ERRORS = ("context length", "context size", "exceeds the available context")

log = logging.getLogger(__name__)

FLUSH_TOKENS = 50
FLUSH_SECONDS = 1.0
#: The most seconds between two token heartbeats (llm-design §2: at least every 5 s). v4.24:
#: the beats start with the call, so the wait for the first token beats too (tokens 0).
HEARTBEAT_SECONDS = 4.0

TokenListener = Callable[[str, int], None]
"""``listener(step_id, tokens)``: output tokens of the streaming call so far."""
token_listener: ContextVar[TokenListener | None] = ContextVar("etach_token_listener", default=None)
"""Set by the runtime for each step (``etach.runtime.steps.step``); ``None`` outside a run."""
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=600.0, write=60.0, pool=10.0)


class OllamaError(RuntimeError):
    """Ollama answered with an HTTP error or an ``{"error": …}`` chunk (not a dropped stream)."""


class StreamDropped(RuntimeError):
    """The stream dropped twice for one call (llm-design §7 "Sleep")."""

    def __init__(self, task: str, llm_call_ids: Sequence[str]) -> None:
        super().__init__(f"{task}: the Ollama stream dropped twice ({', '.join(llm_call_ids)})")
        self.task = task
        self.llm_call_ids = list(llm_call_ids)


@dataclass(frozen=True)
class CallResult:
    parsed: BaseModel
    raw_text: str
    logprobs: list[Any] | None
    llm_call_id: str
    thinking_text: str = ""


@dataclass(frozen=True)
class CallFailure:
    """The output failed validation twice; it goes into graph state (``save`` decides)."""

    task: str
    reason: str
    llm_call_ids: list[str] = field(default_factory=list)


class ChatBackend(Protocol):
    """Where the chunks come from: Ollama over HTTP, or cassettes (``ReplayBackend``)."""

    def stream(
        self, body: Mapping[str, Any], *, task: str, match_key: str
    ) -> AsyncGenerator[dict[str, Any]]: ...


class HttpBackend:
    """Streams ``POST /api/chat`` as NDJSON chunks."""

    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.timeout = timeout

    async def stream(
        self, body: Mapping[str, Any], *, task: str, match_key: str
    ) -> AsyncGenerator[dict[str, Any]]:
        async with (
            httpx.AsyncClient(
                base_url=self.base_url, transport=self.transport, timeout=self.timeout
            ) as http,
            http.stream("POST", "/api/chat", json=dict(body)) as response,
        ):
            if response.status_code != 200:
                detail = (await response.aread()).decode("utf-8", "replace")[:500]
                raise OllamaError(f"/api/chat returned {response.status_code}: {detail}")
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if "error" in chunk:
                    raise OllamaError(f"Ollama: {chunk['error']}")
                yield chunk


@dataclass(frozen=True)
class PromptSize:
    """Bounds on a prompt's tokens, from its message characters and image count."""

    text_floor: int  # the text alone has at least this many tokens
    floor: int  # text + images, at least
    ceiling: int  # text + images, at most


def prompt_size(body: Mapping[str, Any]) -> PromptSize:
    """:class:`PromptSize` of a ``/api/chat`` body (see the ``*_CHARS_PER_TOKEN`` and
    ``*_IMAGE_TOKENS`` constants)."""
    chars = images = 0
    for message in body.get("messages") or []:
        content = message.get("content")
        if isinstance(content, str):
            chars += len(content)
        images += len(message.get("images") or [])
    text_floor = chars // MAX_CHARS_PER_TOKEN
    return PromptSize(
        text_floor=text_floor,
        floor=text_floor + MIN_IMAGE_TOKENS * images,
        ceiling=-(-chars // MIN_CHARS_PER_TOKEN) + MAX_IMAGE_TOKENS * images,
    )


def _num_ctx(body: Mapping[str, Any]) -> int | None:
    value = (body.get("options") or {}).get("num_ctx")
    return value if isinstance(value, int) and value > 0 else None


def _num_predict(body: Mapping[str, Any]) -> int | None:
    value = (body.get("options") or {}).get("num_predict")
    return value if isinstance(value, int) and value > 0 else None


def _capped(stream: _Stream, num_predict: int | None) -> bool:
    """The output stopped at the ``num_predict`` cap (``done_reason`` ``length``, or as many
    output tokens as the cap)."""
    if stream.done_reason == "length":
        return True
    return num_predict is not None and (stream.tokens_out or 0) >= num_predict


def _context_error(exc: OllamaError) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _CONTEXT_ERRORS)


def prompt_hash(prompt: RenderedPrompt, request: AdapterRequest) -> str:
    """sha256 over the rendered prompt text + the schema/template JSON the model is given."""
    return sha256_hex(f"{prompt.hash}\n{request.schema_text}")


@dataclass
class _Stream:
    text: list[str] = field(default_factory=list)
    thinking: list[str] = field(default_factory=list)
    logprobs: list[Any] = field(default_factory=list)
    tokens_in: int | None = None
    tokens_out: int | None = None
    ms: int | None = None
    done_reason: str | None = None

    @property
    def response_text(self) -> str:
        return "".join(self.text)

    @property
    def thinking_text(self) -> str:
        return "".join(self.thinking)

    @property
    def logprobs_or_none(self) -> list[Any] | None:
        return self.logprobs or None


class _Dropped(Exception):
    def __init__(self, cause: BaseException, stream: _Stream) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.stream = stream


class OllamaClient:
    def __init__(
        self,
        conn: sqlite3.Connection,
        config: ModelsConfig,
        prompts: PromptProvider,
        *,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        backend: ChatBackend | None = None,
        read_image: Callable[[str], bytes] | None = None,
        recorder: cassettes.CassetteRecorder | None = None,
        flush_tokens: int = FLUSH_TOKENS,
        flush_seconds: float = FLUSH_SECONDS,
        heartbeat_seconds: float = HEARTBEAT_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if backend is None:
            if base_url is None:
                raise ValueError("pass base_url (Ollama) or a backend (replay)")
            backend = HttpBackend(base_url, transport=transport)
        self.conn = conn
        self.config = config
        self.prompts = prompts
        self.backend = backend
        self.read_image = read_image
        self.recorder = recorder
        self.flush_tokens = flush_tokens
        self.flush_seconds = flush_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.clock = clock
        self.sleep = sleep
        self._db_lock = threading.Lock()

    # --- DB helpers (all llm_calls writes of the client) -------------------------------------

    def _locked[T](self, fn: Callable[[], T]) -> T:
        with self._db_lock:
            return fn()

    async def _db[T](self, fn: Callable[[], T]) -> T:
        return await asyncio.to_thread(self._locked, fn)

    def _flush(self, call_id: str, s: _Stream) -> None:
        runs.update_llm_call_stream(
            self.conn,
            call_id,
            response_text=s.response_text,
            thinking_text=s.thinking_text,
            logprobs=s.logprobs_or_none,
        )

    def _close(self, call_id: str, status: runs.LlmCallStatus, s: _Stream, ms: int | None) -> None:
        """The last write of a row: the text so far, the counts, then the final status."""
        with transaction(self.conn):
            self._flush(call_id, s)
            runs.set_llm_call_counts(
                self.conn, call_id, tokens_in=s.tokens_in, tokens_out=s.tokens_out, ms=ms
            )
            runs.set_llm_call_status(self.conn, call_id, status)

    # --- the call --------------------------------------------------------------------------

    async def call(
        self,
        role: Role,
        task: str,
        inputs: Mapping[str, Any],
        schema: type[BaseModel],
        *,
        step_id: str,
        images: Sequence[str] = (),
        think: bool | None = None,
        num_predict: int | None = None,
        profile: str = "generic",
        item: str | None = None,
    ) -> CallResult | CallFailure:
        """``item``: what this call reads when its step's item does not say (e.g. ``"p2 top"``,
        one tile of page 2); stored as ``request.item`` in the ``llm_calls`` row (not sent)."""
        role_cfg = self.config.role(role)
        prompt = self.prompts.render(task, profile, inputs)
        image_inputs = [ImageInput(fid, await self._image(fid)) for fid in images]
        key = cassettes.match_key(task, schema.__name__, inputs)
        recorder = self.recorder or cassettes.active_recorder()
        call_ids: list[str] = []
        drops = invalids = 0
        while True:
            request = build_request(
                role_cfg, prompt, schema, image_inputs, think=think, num_predict=num_predict
            )
            # never let Ollama drop messages to fit num_ctx (B1); the client checks instead
            request.body["truncate"] = False
            request.stored["truncate"] = False
            if item is not None:
                request.stored["item"] = item  # a label for the log, never sent to Ollama
            p_hash = prompt_hash(prompt, request)
            call_id = await self._insert_row(step_id, role, role_cfg.model, p_hash, request)
            call_ids.append(call_id)
            size = prompt_size(request.body)
            num_ctx = _num_ctx(request.body)
            if num_ctx is not None and size.floor > num_ctx:
                await self._finish(call_id, "error", _Stream())
                return _truncated(
                    task,
                    call_ids,
                    f"the prompt needs at least {size.floor} tokens"
                    f" ({len(image_inputs)} image(s)), more than num_ctx {num_ctx}",
                )

            def record(status: cassettes.CassetteStatus, s: _Stream, p_hash: str = p_hash) -> None:
                if recorder is None:
                    return
                recorder.record(
                    cassettes.new_cassette(
                        task=task,
                        key=key,
                        response_text=s.response_text,
                        thinking_text=s.thinking_text,
                        logprobs=s.logprobs_or_none,
                        status=status,
                        model=role_cfg.model,
                        prompt_hash=p_hash,
                        schema_name=schema.__name__,
                    )
                )

            try:
                stream = await self._stream(call_id, request, task, key, step_id)
            except _Dropped as dropped:
                await asyncio.to_thread(record, "error", dropped.stream)
                drops += 1
                if drops > 1:
                    raise StreamDropped(task, call_ids) from dropped.cause
                continue
            except OllamaError as exc:  # the row is already "error"
                if not _context_error(exc):
                    raise
                return _truncated(task, call_ids, f"Ollama refused the prompt ({exc})")

            if (
                num_ctx is not None
                and size.ceiling > num_ctx
                and stream.tokens_in  # 0/None: unknown (cassette replay)
                and stream.tokens_in < size.text_floor
            ):
                # the prompt may not fit, and Ollama read fewer tokens than the text alone
                # has: part of it was dropped, so this is not an answer to this prompt
                await self._finish(call_id, "error", stream)
                return _truncated(
                    task,
                    call_ids,
                    f"Ollama read {stream.tokens_in} prompt tokens, but the text alone has at"
                    f" least {size.text_floor} (num_ctx {num_ctx})",
                )

            try:
                if is_plain_text(schema):  # step 22.5.7: an OCR call answers in plain text
                    parsed = schema.model_validate({"text": stream.response_text.strip()})
                else:
                    parsed = schema.model_validate_json(stream.response_text)
            except ValidationError as exc:
                await self._finish(call_id, "invalid", stream)
                await asyncio.to_thread(record, "invalid", stream)
                invalids += 1
                cap = _num_predict(request.body)
                if not self.config.client.retries_capped(role) and _capped(stream, cap):
                    # the output was cut at num_predict: a retry at temperature 0 repeats it
                    return _capped_failure(task, call_ids, stream, cap, exc)
                if invalids > 1:
                    return CallFailure(task=task, reason=_short(exc), llm_call_ids=call_ids)
                prompt = prompt.with_note(_retry_note(exc))
                continue

            await self._finish(call_id, "complete", stream)
            await asyncio.to_thread(record, "complete", stream)
            return CallResult(
                parsed=parsed,
                raw_text=stream.response_text,
                logprobs=stream.logprobs_or_none,
                llm_call_id=call_id,
                thinking_text=stream.thinking_text,
            )

    async def _image(self, file_id: str) -> bytes:
        if self.read_image is None:
            raise ValueError("images were passed but the client has no read_image")
        return await asyncio.to_thread(self.read_image, file_id)

    async def _insert_row(
        self, step_id: str, role: Role, model: str, p_hash: str, request: AdapterRequest
    ) -> str:
        row = LlmCall(
            id=new_ulid(),
            step_id=step_id,
            role=role,
            model=model,
            prompt_hash=p_hash,
            request=request.stored,
            response_text="",
            thinking_text="",
            logprobs=None,
            status="streaming",
            tokens_in=None,
            tokens_out=None,
            ms=None,
            created_at=datetime.now(UTC),
        )
        await self._db(lambda: runs.insert_llm_call(self.conn, row))
        return row.id

    async def _finish(self, call_id: str, status: runs.LlmCallStatus, s: _Stream) -> None:
        await self._db(lambda: self._close(call_id, status, s, s.ms))

    async def _stream(
        self, call_id: str, request: AdapterRequest, task: str, key: str, step_id: str
    ) -> _Stream:
        s = _Stream()
        started = self.clock()
        last_flush = last_beat = started
        since_flush = tokens = 0
        done = False
        listener = token_listener.get()

        async def flush() -> None:
            await self._db(lambda: self._flush(call_id, s))

        def elapsed() -> int:
            return int((self.clock() - started) * 1000)

        def beat(now: float) -> None:
            nonlocal last_beat
            last_beat = now
            if listener is not None:
                listener(step_id, tokens)

        async def beat_while_quiet() -> None:
            # llm-design §2 v4.24: the live sign beats from the start of the call, also while
            # the model has not sent a chunk yet (a long prompt, a cold model)
            while True:
                await self.sleep(self.heartbeat_seconds)
                now = self.clock()
                if now - last_beat >= self.heartbeat_seconds:
                    beat(now)

        beater: asyncio.Task[None] | None = None
        if listener is not None:
            beat(started)
            beater = asyncio.create_task(beat_while_quiet())

        try:
            async with aclosing(self.backend.stream(request.body, task=task, match_key=key)) as it:
                async for chunk in it:
                    message = chunk.get("message") or {}
                    if message.get("content"):
                        s.text.append(message["content"])
                    if message.get("thinking"):
                        s.thinking.append(message["thinking"])
                    chunk_logprobs = chunk.get("logprobs") or []
                    s.logprobs.extend(chunk_logprobs)
                    since_flush += max(len(chunk_logprobs), 1)
                    tokens += max(len(chunk_logprobs), 1)
                    if chunk.get("done"):
                        done = True
                        s.tokens_in = chunk.get("prompt_eval_count")
                        s.tokens_out = chunk.get("eval_count")
                        s.done_reason = chunk.get("done_reason")
                        total = chunk.get("total_duration")
                        s.ms = int(total) // 1_000_000 if total else elapsed()
                        break
                    now = self.clock()
                    if since_flush >= self.flush_tokens or now - last_flush >= self.flush_seconds:
                        await flush()
                        since_flush = 0
                        last_flush = now
                    if listener is not None and now - last_beat >= self.heartbeat_seconds:
                        beat(now)
            if not done:
                raise httpx.RemoteProtocolError("the stream ended without a final chunk")
        except asyncio.CancelledError:
            # synchronous on purpose: a second cancellation must not skip this write
            self._locked(lambda: self._close(call_id, "cancelled", s, elapsed()))
            raise
        except httpx.TransportError as exc:
            await self._db(lambda: self._close(call_id, "error", s, elapsed()))
            raise _Dropped(exc, s) from exc
        except BaseException:
            self._locked(lambda: self._close(call_id, "error", s, elapsed()))
            raise
        finally:
            if beater is not None:
                beater.cancel()
        return s


def _truncated(task: str, call_ids: Sequence[str], detail: str) -> CallFailure:
    reason = f"{TRUNCATED}: {detail}"
    log.warning("%s: %s (llm_calls %s)", task, reason, ", ".join(call_ids))
    return CallFailure(task=task, reason=reason, llm_call_ids=list(call_ids))


def _capped_failure(
    task: str,
    call_ids: Sequence[str],
    stream: _Stream,
    num_predict: int | None,
    exc: ValidationError,
) -> CallFailure:
    reason = (
        f"{CAPPED}: the output stopped at num_predict {num_predict}"
        f" ({stream.tokens_out} tokens, done_reason {stream.done_reason!r}) and is not valid;"
        f" not retried. {_short(exc, 500)}"
    )
    log.warning("%s: %s (llm_calls %s)", task, reason, ", ".join(call_ids))
    return CallFailure(task=task, reason=reason, llm_call_ids=list(call_ids))


def _short(exc: ValidationError, limit: int = 2000) -> str:
    text = str(exc)
    return text if len(text) <= limit else text[:limit] + " …"


def _retry_note(exc: ValidationError) -> str:
    return (
        "Your previous answer did not match the required JSON schema:\n"
        f"{_short(exc)}\n"
        "Answer again with JSON only, matching the schema exactly."
    )
