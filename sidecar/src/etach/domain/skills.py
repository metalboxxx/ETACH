"""Skill names for the report (step 22.4.6, PRD v8.2 "Report wording and order").

The taxonomy codes (``VOC-TOPIC``, ``GR-PSV-A1`` …) are internal. The report, on screen and in the
Word file, shows each skill's English name from the taxonomy files
(``etach/prompts/taxonomy/*.txt``, lines ``CODE | Name | …``), read through the package resources
like the prompts, so the frozen build finds them too.

- :func:`skill_names`: every code → its name.
- :func:`skill_name`: one code's name; an unknown code is :data:`OTHER_SKILL`.
- :func:`name_codes`: a text with every known code in it replaced by its name (AI-written text).
"""

from __future__ import annotations

import re
from functools import cache
from importlib import resources

__all__ = ["OTHER_SKILL", "TAXONOMY_FILES", "name_codes", "skill_name", "skill_names"]

#: The name shown for a code the taxonomy files do not have.
OTHER_SKILL = "Other skill"
#: The same files as ``etach.llm.tasks.TAXONOMY_FILES`` (grammar first).
TAXONOMY_FILES: tuple[str, ...] = ("grammar.txt", "sections.txt")

_SKILL_LINE = re.compile(r"^([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)[ \t]+\|([^|\n]*)", re.MULTILINE)


def _text(name: str) -> str:
    entry = resources.files("etach.prompts").joinpath("taxonomy").joinpath(name)
    return entry.read_text(encoding="utf-8").replace("\r\n", "\n")


@cache
def skill_names() -> dict[str, str]:
    """Every taxonomy code → its English name (the first one wins if a code repeats)."""
    names: dict[str, str] = {}
    for file in TAXONOMY_FILES:
        for m in _SKILL_LINE.finditer(_text(file)):
            name = m.group(2).strip()
            if name:
                names.setdefault(m.group(1), name)
    return names


def skill_name(code: str) -> str:
    """The skill's name; :data:`OTHER_SKILL` for a code the taxonomy does not have."""
    return skill_names().get(code.strip(), OTHER_SKILL)


@cache
def _code_pattern() -> re.Pattern[str]:
    codes = sorted(skill_names(), key=len, reverse=True)  # longest first: GR-PSV-A2 before GR-PSV
    alternatives = "|".join(map(re.escape, codes))
    return re.compile(r"(?<![A-Za-z0-9-])(" + alternatives + r")(?![A-Za-z0-9-])")


def name_codes(text: str) -> str:
    """``text`` with every taxonomy code in it replaced by the skill's name."""
    if not text:
        return text
    names = skill_names()
    return _code_pattern().sub(lambda m: names[m.group(1)], text)
