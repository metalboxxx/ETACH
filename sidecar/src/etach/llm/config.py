"""``<data>/models.toml``: the model roles (llm-design §3.1), the confidence fallback
and the extraction switches.

```toml
[roles.vision]
model   = "<tag>"
adapter = "nuextract"
options = { num_ctx = 16384, temperature = 0, seed = 42 }
think   = false
adapter_options = { also_format = true }

[confidence]
fallback = "none"          # resample | self_report | none (step 6 uses it)

[extract]
retranscribe_tiles = false # re-read a failing page as half-page tiles (default off)
retranscribe_tiles_keep = "better"  # better | always: when the tile reading replaces the page
reread_pieces = false     # re-read only a failing page's broken questions (default off)
photo_reader = "ocr"      # ocr (GLM-OCR, then photo_structure) | vision (one vision call)
photo_structure = "code"  # ocr reader only: code (layout rules) | qwen | ocr_format
blank_share = 0.2         # blank paper: fewer answers than this share read with confidence

[client]
retry_capped_output = { vision = false, reasoning = true, grading_check = true }  # capped output
```

A missing file gives :mod:`etach.llm.defaults`. A file that sets only some keys is merged over the
defaults key by key (``options`` and ``adapter_options`` are merged per option), so
``[roles.vision] model = "x"`` changes only the model.
"""

from __future__ import annotations

import copy
import json
import re
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from etach.appdir import DataPaths
from etach.llm.defaults import (
    DEFAULT_CLIENT,
    DEFAULT_EXTRACT,
    DEFAULT_ROLES,
    adapter_for_tag,
)

__all__ = [
    "AdapterName",
    "ChatOptions",
    "ClientConfig",
    "ConfidenceConfig",
    "ConfigError",
    "ExtractConfig",
    "ModelsConfig",
    "NuExtractOptions",
    "Role",
    "RoleConfig",
    "default_config",
    "load_models_config",
    "parse_models_config",
    "write_models_config",
]

#: ``grading_check`` checks keys (``verify_key``); ``extraction_check`` will check extractions
#: (step 22.5.4; no task uses it yet). Both default to the same tag as the others.
#: ``ocr`` (step 22.5.7, D13): the OCR model of the two-step photo reader, a default role since
#: R22.5.7.7; absent when ``[extract] photo_reader = "vision"`` and ``models.toml`` names no
#: ``[roles.ocr]``.
Role = Literal["vision", "reasoning", "grading_check", "extraction_check", "ocr"]
AdapterName = Literal["nuextract", "chat"]


class ConfigError(ValueError):
    """``models.toml`` cannot be read or does not match the expected shape."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NuExtractOptions(_Strict):
    #: Also send Ollama's ``format`` (the JSON Schema) next to the template (Phase 0 compares).
    also_format: bool = False


class ChatOptions(_Strict):
    pass


_ADAPTER_OPTIONS: dict[str, type[_Strict]] = {"nuextract": NuExtractOptions, "chat": ChatOptions}


class RoleConfig(_Strict):
    model: str = Field(min_length=1)
    adapter: AdapterName
    options: dict[str, Any] = Field(default_factory=dict)
    think: bool = False
    adapter_options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_adapter_options(self) -> RoleConfig:
        _ADAPTER_OPTIONS[self.adapter].model_validate(self.adapter_options)
        return self

    def nuextract_options(self) -> NuExtractOptions:
        return NuExtractOptions.model_validate(
            self.adapter_options if self.adapter == "nuextract" else {}
        )


class ConfidenceConfig(_Strict):
    #: llm-design §6 fallbacks. ``None`` = not configured; step 6 decides what that means.
    fallback: Literal["resample", "self_report", "none"] | None = None


class ExtractConfig(_Strict):
    #: Re-read a page that fails validation as two half-page tiles (llm-design §4). Off: such a
    #: page goes straight to ``validator_failed`` (speed bundle 1; the default is in defaults.py).
    retranscribe_tiles: bool = bool(DEFAULT_EXTRACT["retranscribe_tiles"])
    #: ``better``: keep the tile reading only if it reduces the page's validator failures;
    #: ``always``: the tiles always replace the first pass (the rule before speed bundle 1).
    retranscribe_tiles_keep: Literal["better", "always"] = DEFAULT_EXTRACT[
        "retranscribe_tiles_keep"
    ]
    #: Step 22.5.7: re-read only the failing or missing questions of a page that fails a check
    #: (one ``reread_pieces`` call on ``extraction_check``), patched in by code; before the tiles.
    reread_pieces: bool = bool(DEFAULT_EXTRACT["reread_pieces"])
    #: Step 22.5.7 (D13): how a photo page is read. ``ocr`` (the default since G4, R22.5.7.7):
    #: an ``ocr_page`` call (the ``ocr`` role, plain text), then that text structured as
    #: ``photo_structure`` says. ``vision``: one ``transcribe_page`` call on the vision role (the
    #: path before 0.6.0). The student answers stay on vision.
    photo_reader: Literal["vision", "ocr"] = DEFAULT_EXTRACT["photo_reader"]
    #: Step 22.6.5 (D7): how a photo page's OCR text becomes sections and questions, on the
    #: OCR reader only. ``code`` (2b, the default since step 22.6.6 (c), step22.6-plan D16):
    #: :mod:`etach.domain.ocr_structure`, no model call. ``qwen`` (way 1, the default before):
    #: ``structure_text_page``. ``ocr_format`` (2a): one
    #: ``ocr_format_page`` call (GLM-OCR writes the page in the app's test-text format) read by
    #: :func:`etach.domain.test_text.read_ocr_page`, no structuring call.
    photo_structure: Literal["qwen", "code", "ocr_format"] = DEFAULT_EXTRACT["photo_structure"]
    #: the ``ocr_page`` prompt (the whole user message next to the photo)
    ocr_prompt: str = Field(default=DEFAULT_EXTRACT["ocr_prompt"], min_length=1)
    #: Step 22.6.2: a paper with fewer than this share of its answers read with confidence is
    #: blank; 0 is the rule before 22.6.2 (only a paper with nothing read)
    blank_share: float = Field(default=DEFAULT_EXTRACT["blank_share"], ge=0, le=1)


class ClientConfig(_Strict):
    #: Per role: retry an invalid output that stopped at ``num_predict`` like any invalid output.
    #: Off: it fails at once as ``output_capped`` (speed bundle 1; defaults in defaults.py).
    retry_capped_output: dict[Role, bool] = Field(
        default_factory=lambda: dict(DEFAULT_CLIENT["retry_capped_output"])
    )

    def retries_capped(self, role: str) -> bool:
        """Whether a ``role`` call retries an invalid output cut at ``num_predict``."""
        return bool(self.retry_capped_output.get(role, False))  # type: ignore[call-overload]


class ModelsConfig(_Strict):
    roles: dict[Role, RoleConfig]
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)
    extract: ExtractConfig = Field(default_factory=ExtractConfig)
    client: ClientConfig = Field(default_factory=ClientConfig)

    def role(self, name: str) -> RoleConfig:
        try:
            return self.roles[name]  # type: ignore[index]
        except KeyError:
            raise ConfigError(f"no role {name!r} in models.toml") from None


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def parse_models_config(data: dict[str, Any]) -> ModelsConfig:
    """Validate a parsed ``models.toml`` merged over the defaults."""
    unknown = set(data) - {"roles", "confidence", "extract", "client"}
    if unknown:
        raise ConfigError(f"unknown tables in models.toml: {sorted(unknown)}")
    roles_in = data.get("roles", {})
    if not isinstance(roles_in, dict):
        raise ConfigError("[roles] must be a table")
    roles: dict[str, Any] = {}
    extract_raw = data.get("extract", {})
    names = set(DEFAULT_ROLES) | set(roles_in)
    if (
        isinstance(extract_raw, dict)
        and extract_raw.get("photo_reader") == "vision"
        and "ocr" not in roles_in
    ):
        # R22.5.7.7: the vision reader does not use the ocr role, so it is not listed, checked
        # or downloaded (the path before 0.6.0); a [roles.ocr] table keeps it.
        names.discard("ocr")
    for name in sorted(names):
        role_in = roles_in.get(name, {})
        if not isinstance(role_in, dict):
            raise ConfigError(f"[roles.{name}] must be a table")
        base = DEFAULT_ROLES.get(name, {})
        if "adapter" not in role_in and isinstance(role_in.get("model"), str):
            # the model is named but not the adapter: the adapter follows the tag (step 22.3.5)
            inferred = adapter_for_tag(role_in["model"])
            if inferred["adapter"] != base.get("adapter"):
                base = {k: v for k, v in base.items() if k != "adapter_options"} | inferred
        elif "adapter" in role_in and role_in["adapter"] != base.get("adapter"):
            # another adapter: its options do not carry over
            base = {k: v for k, v in base.items() if k != "adapter_options"}
        roles[name] = _merge(base, role_in)
    extract_in = data.get("extract", {})
    if not isinstance(extract_in, dict):
        raise ConfigError("[extract] must be a table")
    client_in = data.get("client", {})
    if not isinstance(client_in, dict):
        raise ConfigError("[client] must be a table")
    try:
        return ModelsConfig.model_validate(
            {
                "roles": roles,
                "confidence": data.get("confidence", {}),
                "extract": {**DEFAULT_EXTRACT, **extract_in},
                "client": _merge(DEFAULT_CLIENT, client_in),
            }
        )
    except ValidationError as exc:
        raise ConfigError(f"models.toml: {exc}") from exc


def default_config() -> ModelsConfig:
    return parse_models_config({})


def load_models_config(source: DataPaths | Path) -> ModelsConfig:
    """Read ``models.toml`` from the data folder (or an explicit file path)."""
    path = source.models_toml if isinstance(source, DataPaths) else source
    if not path.exists():
        return default_config()
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    return parse_models_config(data)


# --- writing (PUT /settings) -------------------------------------------------------------------


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)  # a JSON string is a TOML basic string
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    if isinstance(value, dict):
        inner = ", ".join(f"{_toml_key(k)} = {_toml_value(v)}" for k, v in value.items())
        return "{ " + inner + " }" if inner else "{}"
    raise ConfigError(f"cannot write {type(value).__name__} to models.toml")


def _toml_key(key: str) -> str:
    return key if _BARE_KEY.match(key) else json.dumps(key, ensure_ascii=False)


_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def _dump_toml(data: dict[str, Any]) -> str:
    """``[roles.<name>]``, ``[confidence]``, ``[extract]`` and ``[client]`` tables with scalar /
    inline-table values."""
    lines: list[str] = []

    def table(name: str, body: dict[str, Any]) -> None:
        lines.append(f"[{name}]")
        lines.extend(f"{_toml_key(k)} = {_toml_value(v)}" for k, v in body.items())
        lines.append("")

    for role, body in data.get("roles", {}).items():
        table(f"roles.{_toml_key(role)}", body)
    if data.get("confidence"):
        table("confidence", data["confidence"])
    if data.get("extract"):
        table("extract", data["extract"])
    if data.get("client"):
        table("client", data["client"])
    return "\n".join(lines)


def write_models_config(
    source: DataPaths | Path,
    models: dict[str, str],
    options: dict[str, dict[str, Any]] | None = None,
) -> ModelsConfig:
    """Set the model tag (and, if given, merge ``options``) of the named roles in
    ``models.toml``, keeping everything else the file sets; returns the new merged config.

    The result is validated before the file is replaced (written to a temp file, then renamed).
    """
    path = source.models_toml if isinstance(source, DataPaths) else source
    data: dict[str, Any] = {}
    if path.exists():
        try:
            with path.open("rb") as fh:
                data = tomllib.load(fh)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{path}: {exc}") from exc
    roles: dict[str, Any] = dict(data.get("roles") or {})
    for role, tag in models.items():
        if not isinstance(tag, str) or not tag.strip():
            raise ConfigError(f"the model tag of role {role!r} must be a non-empty string")
        current = dict(roles.get(role, {}))
        if current.get("model") != tag.strip():
            # a new model: its adapter follows the tag again (parse_models_config)
            for key in ("adapter", "adapter_options"):
                current.pop(key, None)
        roles[role] = {**current, "model": tag.strip()}
    for role, opts in (options or {}).items():
        roles[role] = {
            **roles.get(role, {}),
            "options": {**roles.get(role, {}).get("options", {}), **opts},
        }
    data["roles"] = roles
    config = parse_models_config(data)
    text = _dump_toml(data)
    if tomllib.loads(text) != data:
        raise ConfigError("models.toml would not round-trip")  # pragma: no cover
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".toml.tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)
    return config
