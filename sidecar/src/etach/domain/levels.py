"""Skill levels A1-B2 (decision D11d, step 22.5.5): weak points go basics first.

- Grammar skills (``grammar.txt``): the level is the end of the ID (``GR-QNT-A2`` → ``A2``).
- Section skills (``sections.txt``): the last column of the line, the base levels the teacher
  approved (step22.5-plan §5 D11d).
- ``tag_skills`` also gives each question a level; a tag's **effective level** is the question's
  level when given, else the skill's base level (:func:`tag_level`).

Read through the package resources like the prompts, so the frozen build finds them too.
"""

from __future__ import annotations

import re
from functools import cache
from typing import Literal, get_args

from etach.domain.skills import TAXONOMY_FILES, _text

__all__ = ["LEVELS", "Level", "base_level", "level_rank", "skill_levels", "tag_level"]

Level = Literal["A1", "A2", "B1", "B2"]
#: The levels, lowest first.
LEVELS: tuple[Level, ...] = get_args(Level)

_SKILL_LINE = re.compile(r"^([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)[ \t]+\|(.*)$", re.MULTILINE)
_GRAMMAR_ID = re.compile(r"^GR-[A-Z0-9]+-(A1|A2|B1|B2)$")
_LAST_COLUMN = re.compile(r"\|\s*(A1|A2|B1|B2)\s*$")


@cache
def skill_levels() -> dict[str, Level]:
    """Every taxonomy skill ID → its base level (the first line wins if an ID repeats)."""
    out: dict[str, Level] = {}
    for file in TAXONOMY_FILES:
        for m in _SKILL_LINE.finditer(_text(file)):
            skill_id = m.group(1)
            found = _GRAMMAR_ID.match(skill_id) or _LAST_COLUMN.search(m.group(2))
            if found is not None and skill_id not in out:
                out[skill_id] = found.group(1)  # type: ignore[assignment]
    return out


def base_level(skill_id: str) -> Level | None:
    """The skill's base level; ``None`` for an ID the taxonomy does not have."""
    return skill_levels().get(skill_id.strip())


def tag_level(skill_id: str, question_level: str | None) -> Level | None:
    """A tag's effective level: the question's level when given, else the skill's base level."""
    if question_level in LEVELS:
        return question_level
    return base_level(skill_id)


def level_rank(level: str | None) -> int:
    """0 for A1 … 3 for B2; an unknown or missing level sorts last (4)."""
    return LEVELS.index(level) if level in LEVELS else len(LEVELS)
