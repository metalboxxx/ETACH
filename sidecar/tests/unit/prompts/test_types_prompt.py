"""M1 p1, step 22.5.3: the page prompts define the answer forms and section skills.

Every form and skill named in backticks in those rules must be a value of the schema enums, so a
renamed enum value cannot leave the prompt teaching a value the schema rejects. R22.5.3.5: the
form part names the four forms, one line each, and is shorter than the old type part.
"""

from __future__ import annotations

import re
from typing import get_args

import pytest

from etach.domain.llm_schemas import SectionSkill
from etach.domain.models import AnswerForm
from etach.prompts.render import FilePromptProvider

PAGE_PROMPTS = ("transcribe_page", "structure_text_page")
#: The line count of the old "Question `type`" part of both page prompts (11 types, 14 lines).
OLD_TYPE_PART_LINES = 14


def _rules(heading: str, task: str = "transcribe_page") -> str:
    """The indented rule lines under the ``- <heading>`` bullet of a page prompt."""
    text = FilePromptProvider().base_text(task)
    start = text.index(f"- {heading}")
    lines = text[start:].splitlines()[1:]
    block = []
    for line in lines:
        if not line.startswith("  "):
            break
        block.append(line)
    return "\n".join(block)


def _named(block: str) -> set[str]:
    return set(re.findall(r"`([a-z_]+)`", block))


@pytest.mark.parametrize("task", PAGE_PROMPTS)
def test_r22_5_3_5_every_answer_form_is_defined_one_line_each(task: str) -> None:
    block = _rules("Question `answer_form`", task)
    assert _named(block) == set(get_args(AnswerForm))
    lines = block.splitlines()
    assert len(lines) == 4  # one line per form
    assert [re.match(r"  - `([a-z]+)`:", line).group(1) for line in lines] == [  # type: ignore[union-attr]
        "choice",
        "word",
        "sentence",
        "writing",
    ]
    assert len(lines) + 1 <= OLD_TYPE_PART_LINES  # the heading line plus the forms


@pytest.mark.parametrize("task", PAGE_PROMPTS)
def test_r22_5_3_1_no_old_type_in_the_page_prompts(task: str) -> None:
    text = FilePromptProvider().base_text(task)
    old_only = (
        "mcq", "true_false", "gap_fill", "verb_form", "combine`", "ordering`", "matching`",
        "short_answer", "Question `type`",
    )  # fmt: skip
    assert not [w for w in old_only if w in text]
    assert "only for `sentence` questions" in text  # answer_start is asked for sentence


def test_section_skills_use_enum_values_only() -> None:
    named = _named(_rules("Section `skill`"))
    assert named <= set(get_args(SectionSkill))
    assert {"reading", "vocabulary", "mixed"} <= named


def test_key_form_rules_are_present() -> None:
    text = FilePromptProvider().base_text("transcribe_page")
    assert "printed lettered options" in text
    assert "True/False (T/F)" in text
    assert "a dictionary entry → `vocabulary`" in text
