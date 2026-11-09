"""Adapters: turn a rendered prompt + an output schema into an Ollama ``/api/chat`` body.

Each adapter returns two versions of the body: ``body`` (sent; images as base64) and ``stored``
(written to ``llm_calls.request``; images as ``{"file_id": ...}`` only). Both set ``stream``,
``logprobs``, ``top_logprobs = 5`` and the role's ``options`` (plan Appendix D.1).

The prompt text comes from a :class:`PromptProvider` (step 8.2 renders ``prompts/``); the
adapters only place it.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol

from pydantic import BaseModel, Field

from etach.llm.config import RoleConfig

__all__ = [
    "TOP_LOGPROBS",
    "AdapterRequest",
    "ImageInput",
    "PlainText",
    "PromptProvider",
    "RenderedPrompt",
    "build_request",
    "canonical_json",
    "sha256_hex",
]

TOP_LOGPROBS = 5


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RenderedPrompt:
    """A rendered prompt. ``document`` is page text sent as the document (text pages, PRD §11);
    ``hash`` covers the prompt text only (the client adds the schema to the stored hash)."""

    system: str
    user_text: str
    hash: str
    document: str | None = None

    @classmethod
    def of(cls, system: str, user_text: str, document: str | None = None) -> RenderedPrompt:
        digest = sha256_hex(canonical_json([system, user_text, document]))
        return cls(system=system, user_text=user_text, hash=digest, document=document)

    def with_note(self, note: str) -> RenderedPrompt:
        """The same prompt with ``note`` appended to the user text (the validation retry)."""
        return RenderedPrompt.of(self.system, f"{self.user_text}\n\n{note}", self.document)


class PromptProvider(Protocol):
    """Renders ``prompts/base/<task>.md`` + ``prompts/profiles/<profile>.md`` (step 8.2)."""

    def render(self, task: str, profile: str, inputs: Mapping[str, Any]) -> RenderedPrompt: ...


class PlainText(BaseModel):
    """The "schema" of a plain-text call (step 22.5.7, ``ocr_page``): no ``format`` and no
    system message are sent, and the client wraps the whole answer as ``text`` (an empty answer
    is invalid). Not an LLM JSON schema: it is never exported."""

    PLAIN_TEXT: ClassVar[bool] = True
    text: str = Field(min_length=1)


def is_plain_text(schema: type[BaseModel]) -> bool:
    return bool(getattr(schema, "PLAIN_TEXT", False))


@dataclass(frozen=True)
class ImageInput:
    file_id: str
    data: bytes


@dataclass(frozen=True)
class AdapterRequest:
    body: dict[str, Any]  # sent to Ollama
    stored: dict[str, Any]  # written to llm_calls.request
    schema_text: str  # canonical JSON of what the model is given as the schema (hash input)


def _common(
    model: str,
    messages: list[dict[str, Any]],
    role: RoleConfig,
    think: bool,
    num_predict: int | None,
) -> dict[str, Any]:
    options = dict(role.options)
    if num_predict is not None:
        options["num_predict"] = num_predict
    return {
        "model": model,
        "messages": messages,
        "stream": True,
        "think": think,
        "logprobs": True,
        "top_logprobs": TOP_LOGPROBS,
        "options": options,
    }


BuildMessages = Callable[[Callable[[ImageInput], Any]], list[dict[str, Any]]]


def assemble(
    *,
    role: RoleConfig,
    build_messages: BuildMessages,
    images: Sequence[ImageInput],
    think: bool,
    num_predict: int | None,
    fmt: dict[str, Any] | None,
    schema_text: str,
) -> AdapterRequest:
    """Build the sent and the stored body from one message builder."""

    def encode(image: ImageInput) -> str:
        return base64.b64encode(image.data).decode("ascii")

    def ref(image: ImageInput) -> dict[str, str]:
        return {"file_id": image.file_id}

    body = _common(role.model, build_messages(encode), role, think, num_predict)
    stored = _common(role.model, build_messages(ref), role, think, num_predict)
    if fmt is not None:
        body["format"] = fmt
        stored["format"] = fmt
    return AdapterRequest(body=body, stored=stored, schema_text=schema_text)


def build_request(
    role: RoleConfig,
    prompt: RenderedPrompt,
    schema: type[BaseModel],
    images: Sequence[ImageInput] = (),
    *,
    think: bool | None = None,
    num_predict: int | None = None,
) -> AdapterRequest:
    """Dispatch to the role's adapter."""
    if role.adapter == "nuextract":
        from etach.llm.adapters import nuextract

        return nuextract.build(role, prompt, schema, images, num_predict=num_predict)
    from etach.llm.adapters import chat

    return chat.build(
        role,
        prompt,
        schema,
        images,
        think=role.think if think is None else think,
        num_predict=num_predict,
    )
