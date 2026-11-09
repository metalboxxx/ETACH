"""Titles of untitled sections (PRD D13 headings, decision D2, data-model v1.21, step 22.5.2).

A section whose printed title is empty, or only a numeral ("I.", "IV", "1."), takes its title from
its section skill, in English capitals: "I." with skill ``pronunciation`` → "I. PRONUNCIATION";
``word_form`` → "WORD FORM". It is filled at extraction (the merge) and once for stored tests at the
first start (``etach.store.repos.text_pass``). The teacher can edit it like any title.

Left alone:

- a section whose skill is ``mixed`` or not a section skill (nothing to name it by);
- a section with a title of words: whoever wrote it, the model or the teacher, it is a title.
  Content edits are not recorded per field, so "the teacher typed it" is told by the text: a title
  with words is never changed, and a bare numeral is not a title.

Pure: no I/O.
"""

from __future__ import annotations

import re
from typing import get_args

from etach.domain.llm_schemas import SectionSkill
from etach.domain.models import Section, TestContent

__all__ = ["fill_titles", "is_untitled", "skill_title"]

# "I", "IV.", "1.", "(2)", "III)": a numeral and the punctuation around it, nothing else
_NUMERAL = re.compile(r"^\s*\(?\s*((?:[IVXLC]+|\d+))\s*([.):\-]?)\s*$", re.IGNORECASE)
_SKILLS = frozenset(get_args(SectionSkill)) - {"mixed"}


def is_untitled(title: str) -> bool:
    """Empty, or only a numeral."""
    return not title.strip() or _NUMERAL.match(title) is not None


def skill_title(skill: str) -> str | None:
    """``word_form`` → "WORD FORM"; ``None`` for ``mixed`` or an unknown skill."""
    return skill.replace("_", " ").upper() if skill in _SKILLS else None


def _filled(section: Section) -> Section:
    if not (is_untitled(section.printed_title) and is_untitled(section.title)):
        return section
    name = skill_title(section.skill)
    if name is None:
        return section
    m = _NUMERAL.match(section.printed_title)
    title = f"{m.group(1)}{m.group(2) or '.'} {name}" if m else name
    return section.model_copy(update={"printed_title": title, "title": title})


def fill_titles(content: TestContent) -> TestContent:
    """A copy of ``content`` where every untitled section with a specific skill has its title
    (module docstring); the other sections are unchanged."""
    sections = [_filled(s) for s in content.sections]
    if all(a is b for a, b in zip(sections, content.sections, strict=True)):
        return content
    return content.model_copy(update={"sections": sections})
