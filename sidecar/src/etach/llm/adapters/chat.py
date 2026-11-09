"""The ``chat`` adapter (plan Appendix D.1): a system message, a user message (+ images), and
``format`` = the output schema's JSON Schema."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel

from etach.llm.adapters import (
    AdapterRequest,
    ImageInput,
    RenderedPrompt,
    assemble,
    canonical_json,
    is_plain_text,
)
from etach.llm.config import RoleConfig

__all__ = ["build", "json_schema"]


def json_schema(schema: type[BaseModel]) -> dict[str, Any]:
    return schema.model_json_schema(by_alias=True)


def build(
    role: RoleConfig,
    prompt: RenderedPrompt,
    schema: type[BaseModel],
    images: Sequence[ImageInput] = (),
    *,
    think: bool,
    num_predict: int | None = None,
) -> AdapterRequest:
    plain = is_plain_text(schema)  # step 22.5.7: plain text out (OCR), no format, no system
    fmt = None if plain else json_schema(schema)
    user_text = prompt.user_text
    if prompt.document:
        user_text = f"{user_text}\n\n{prompt.document}"

    def messages(image: Callable[[ImageInput], Any]) -> list[dict[str, Any]]:
        user: dict[str, Any] = {"role": "user", "content": user_text}
        if images:
            user["images"] = [image(i) for i in images]
        return [user] if plain else [{"role": "system", "content": prompt.system}, user]

    return assemble(
        role=role,
        build_messages=messages,
        images=images,
        think=think,
        num_predict=num_predict,
        fmt=fmt,
        schema_text="" if fmt is None else canonical_json(fmt),
    )
