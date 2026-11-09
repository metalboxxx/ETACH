"""The ``nuextract`` adapter (plan Appendix D.1): NuExtract3's native template interface.

NuExtract3's Ollama chat template reads special message roles (checked 2026-09-28 against the
template of NuMind's NuExtract3 page on ollama.com and the Hugging Face model card):

- ``template``: the JSON extraction template (its presence switches the task to "structured");
- ``instructions``: optional extraction instructions;
- ``user``: the document, as text and/or ``images``.

The template language: leaf types ``"verbatim-string"``, ``"string"``, ``"integer"``,
``"number"``, ``"date-time"`` …; ``[<leaf>]`` for arrays; ``["a", "b"]`` for enums; a missing
value comes back as ``null`` or ``[]``.

``think`` is always ``false`` (NuMind: fast deterministic extraction). ``format`` is sent only
when the role sets ``adapter_options.also_format`` (Phase 0 compares template alone vs template +
``format``). The message layout is isolated in :func:`nuextract_messages`, since Phase 0 may
change it.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel

from etach.llm.adapters import AdapterRequest, ImageInput, RenderedPrompt, assemble, canonical_json
from etach.llm.config import RoleConfig

__all__ = ["build", "nuextract_messages", "schema_to_template"]

#: The template leaf for JSON Schema ``string``. The documents are copied, not summarized.
STRING_LEAF = "verbatim-string"
_LEAVES = {"integer": "integer", "number": "number", "string": STRING_LEAF}


def _resolve(node: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        node = {**defs[name], **{k: v for k, v in node.items() if k != "$ref"}}
    return node


def _convert(node: dict[str, Any], defs: dict[str, Any]) -> Any:
    node = _resolve(node, defs)
    if "const" in node:
        return [node["const"]]
    if "enum" in node:
        return [v for v in node["enum"] if v is not None]
    variants = node.get("anyOf") or node.get("oneOf")
    if variants:
        options = [_resolve(v, defs) for v in variants if v.get("type") != "null"]
        if len(options) == 1:
            return _convert(options[0], defs)
        converted = [_convert(v, defs) for v in options]
        if all(
            isinstance(c, list) and not any(isinstance(x, list | dict) for x in c)
            for c in converted
        ):
            # a union of enums: one enum with every value
            return list(dict.fromkeys(x for c in converted for x in c))
        if all(isinstance(c, dict) for c in converted):
            # a union of objects: one object with every property (enum values united)
            merged: dict[str, Any] = {}
            for c in converted:
                for key, value in c.items():
                    old = merged.get(key)
                    if (
                        isinstance(old, list)
                        and isinstance(value, list)
                        and old
                        and not any(isinstance(x, list | dict) for x in old + value)
                    ):
                        merged[key] = list(dict.fromkeys(old + value))
                    elif key not in merged:
                        merged[key] = value
            return merged
        return converted[0]
    kind = node.get("type")
    if kind == "object" or "properties" in node:
        return {name: _convert(sub, defs) for name, sub in node.get("properties", {}).items()}
    if kind == "array":
        return [_convert(node.get("items", {}), defs)]
    if kind == "boolean":
        return [True, False]
    if isinstance(kind, str) and kind in _LEAVES:
        return _LEAVES[kind]
    return STRING_LEAF


def schema_to_template(schema: type[BaseModel]) -> Any:
    """The NuExtract template for a pydantic output schema (field names by alias)."""
    js = schema.model_json_schema(by_alias=True)
    return _convert(js, js.get("$defs", {}))


def nuextract_messages(
    template_json: str,
    instructions: str,
    document: str,
    images: list[Any],
) -> list[dict[str, Any]]:
    """NuExtract3's message layout: ``template``, then ``instructions`` (if any), then the
    document as the ``user`` message with the page images."""
    messages: list[dict[str, Any]] = [{"role": "template", "content": template_json}]
    if instructions:
        messages.append({"role": "instructions", "content": instructions})
    user: dict[str, Any] = {"role": "user", "content": document}
    if images:
        user["images"] = images
    messages.append(user)
    return messages


def build(
    role: RoleConfig,
    prompt: RenderedPrompt,
    schema: type[BaseModel],
    images: Sequence[ImageInput] = (),
    *,
    num_predict: int | None = None,
) -> AdapterRequest:
    template_json = json.dumps(schema_to_template(schema), ensure_ascii=False, indent=2)
    instructions = "\n\n".join(part for part in (prompt.system, prompt.user_text) if part)
    fmt = schema.model_json_schema(by_alias=True) if role.nuextract_options().also_format else None

    def messages(image: Callable[[ImageInput], Any]) -> list[dict[str, Any]]:
        return nuextract_messages(
            template_json, instructions, prompt.document or "", [image(i) for i in images]
        )

    return assemble(
        role=role,
        build_messages=messages,
        images=images,
        think=False,
        num_predict=num_predict,
        fmt=fmt,
        schema_text=canonical_json({"template": template_json, "format": fmt}),
    )
