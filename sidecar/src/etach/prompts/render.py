"""Prompt files → :class:`RenderedPrompt` (llm-design §3.2 step 1, §8; plan step 8.2).

``FilePromptProvider.render(task, profile, inputs)``:

- loads ``base/<task>.md`` and ``profiles/<profile>.md``; a missing, empty or unsafe profile
  name falls back to ``profiles/generic.md``;
- a base file is split at the line ``<!-- user -->``: the text above is the system prompt, the
  text below the user text. The profile is appended to the system prompt;
- ``{{name}}`` placeholders are filled from ``inputs`` in one pass (no Jinja). A placeholder with
  no input raises :class:`PromptInputError`; inputs that no placeholder uses are allowed (the
  match-key inputs ``page_no`` / ``question_ids`` / ``section_id`` often are). Strings go in as
  they are; other values as compact JSON;
- the input ``document`` (the text layer of a PDF/DOCX page, PRD §11) is not a placeholder: it
  becomes :attr:`RenderedPrompt.document`, which the adapters send as the document;
- a line ``<!-- example: <name> -->`` in a base file is replaced by ``examples/<name>.md`` (step
  22.4.7: one worked example, used by ``structure_text_page`` only; ``transcribe_page`` keeps the
  0.4.0 text, after the teacher's GPU check). It is put in after the placeholders are filled, so the
  example's JSON is never read as a placeholder;
- the hash is sha256 over the task name + the exact rendered text (+ the document), so it is
  stable for identical inputs and changes when a prompt file changes.

The ``.md`` files ship inside the ``etach.prompts`` package and are read with
:mod:`importlib.resources`, like ``etach.store`` migrations.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

from etach.llm.adapters import RenderedPrompt, canonical_json, sha256_hex

__all__ = [
    "DOCUMENT_INPUT",
    "GENERIC_PROFILE",
    "USER_MARKER",
    "FilePromptProvider",
    "PromptInputError",
    "PromptNotFound",
    "fill",
    "placeholders",
    "prompt_hash",
]

GENERIC_PROFILE = "generic"
USER_MARKER = "<!-- user -->"
EXAMPLES_FOLDER = "examples"
DOCUMENT_INPUT = "document"

_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
_EXAMPLE = re.compile(r"^<!-- example: ([A-Za-z0-9_-]+) -->$", re.MULTILINE)


class PromptInputError(KeyError):
    """A ``{{name}}`` placeholder has no value in the inputs."""


class PromptNotFound(FileNotFoundError):
    """``base/<task>.md`` (or ``profiles/generic.md``) does not exist."""


def placeholders(text: str) -> list[str]:
    """The placeholder names in ``text``, in order of first use."""
    return list(dict.fromkeys(m.group(1) for m in _PLACEHOLDER.finditer(text)))


def _value_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def fill(text: str, inputs: Mapping[str, Any], *, where: str = "prompt") -> str:
    """Replace every ``{{name}}`` in one pass; a missing input raises ``PromptInputError``."""
    missing = [name for name in placeholders(text) if name not in inputs]
    if missing:
        raise PromptInputError(f"{where}: no input for placeholder(s) {', '.join(missing)}")
    return _PLACEHOLDER.sub(lambda m: _value_text(inputs[m.group(1)]), text)


def prompt_hash(task: str, system: str, user_text: str, document: str | None) -> str:
    """sha256 over the task name and the exact rendered text."""
    return sha256_hex(canonical_json([task, system, user_text, document]))


def _default_root() -> Traversable:
    return resources.files("etach.prompts")


class FilePromptProvider:
    """A :class:`etach.llm.adapters.PromptProvider` over ``base/`` and ``profiles/``.

    ``root`` defaults to the packaged ``etach/prompts`` folder; tests pass a copy.
    """

    def __init__(self, root: Path | Traversable | None = None) -> None:
        self.root: Path | Traversable = _default_root() if root is None else root

    # --- files ---------------------------------------------------------------------------

    def _read(self, folder: str, name: str) -> str | None:
        entry = self.root.joinpath(folder).joinpath(f"{name}.md")
        if not entry.is_file():
            return None
        # a checkout may turn LF into CRLF; the hash must not depend on it
        return entry.read_text(encoding="utf-8").replace("\r\n", "\n")

    def base_text(self, task: str) -> str:
        if not _SAFE_NAME.match(task):
            raise PromptNotFound(f"invalid task name {task!r}")
        text = self._read("base", task)
        if text is None:
            raise PromptNotFound(f"no prompt file base/{task}.md")
        return text

    def example_text(self, name: str) -> str:
        """``examples/<name>.md``, the text an ``<!-- example: <name> -->`` line stands for."""
        text = self._read(EXAMPLES_FOLDER, name) if _SAFE_NAME.match(name) else None
        if text is None:
            raise PromptNotFound(f"no prompt file {EXAMPLES_FOLDER}/{name}.md")
        return text.strip()

    def _with_examples(self, text: str) -> str:
        return _EXAMPLE.sub(lambda m: self.example_text(m.group(1)), text)

    def resolve_profile(self, profile: str | None) -> str:
        """The profile actually used: ``profile`` if its file exists, else ``generic``."""
        if profile and _SAFE_NAME.match(profile) and self._read("profiles", profile) is not None:
            return profile
        return GENERIC_PROFILE

    def profile_text(self, profile: str | None) -> str:
        name = self.resolve_profile(profile)
        text = self._read("profiles", name)
        if text is None:
            raise PromptNotFound(f"no prompt file profiles/{name}.md")
        return text

    # --- render --------------------------------------------------------------------------

    def render(self, task: str, profile: str, inputs: Mapping[str, Any]) -> RenderedPrompt:
        base = self.base_text(task)
        system_part, marker, user_part = base.partition(USER_MARKER)
        if not marker:
            raise PromptNotFound(f"base/{task}.md has no {USER_MARKER} line")
        values = {k: v for k, v in inputs.items() if k != DOCUMENT_INPUT}
        system_raw = f"{system_part.strip()}\n\n{self.profile_text(profile).strip()}"
        system = self._with_examples(fill(system_raw, values, where=f"{task} (system)"))
        user_text = self._with_examples(fill(user_part.strip(), values, where=f"{task} (user)"))
        document = inputs.get(DOCUMENT_INPUT)
        if document is not None and not isinstance(document, str):
            raise TypeError("the 'document' input must be a string")
        return RenderedPrompt(
            system=system,
            user_text=user_text,
            hash=prompt_hash(task, system, user_text, document),
            document=document,
        )
