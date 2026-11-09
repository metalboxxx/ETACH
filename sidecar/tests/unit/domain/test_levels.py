"""Step 22.5.5a: skill levels (R22.5.5.3, decision D11d)."""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from etach.domain.levels import LEVELS, base_level, level_rank, skill_levels, tag_level
from etach.domain.llm_schemas import TagSkillsOut
from etach.llm.tasks import TAG_SKILLS_SCHEMA, skill_list_text, taxonomy_ids, taxonomy_text

#: step22.5-plan §5 D11d, the base levels the teacher approved (copied, not computed).
D11D = {
    "A1": "VOC-TOPIC",
    "A2": "VOC-COMM PRON-VOWEL PRON-ED PRON-S STRESS-2SYL WF-NOUN WF-ADJ READ-DETAIL READ-REF"
    " SIGN REWRITE-ORDER",
    "B1": "VOC-COLLOC VOC-SYN-ANT VOC-DICT STRESS-3SYL WF-VERB WF-ADV WF-NEG READ-WORD READ-MAIN"
    " READ-CLOZE REWRITE-START REWRITE-CUE REWRITE-COMBINE",
    "B2": "READ-INFER",
}


def _ids(file: str) -> list[str]:
    return [
        m.group(1) for m in re.finditer(r"^([A-Z][A-Z0-9-]*) \|", taxonomy_text(file), re.MULTILINE)
    ]


def test_r22_5_5_3_every_skill_has_a_level() -> None:
    grammar, sections = _ids("grammar.txt"), _ids("sections.txt")
    assert len(grammar) == 58 and len(sections) == 26
    levels = skill_levels()
    assert set(levels) == set(taxonomy_ids()) == set(grammar) | set(sections)
    assert set(levels.values()) <= set(LEVELS)
    for skill in grammar:  # the grammar level is the end of the ID
        assert levels[skill] == skill[-2:]
    expected = {s: lv for lv, ids in D11D.items() for s in ids.split()}
    assert len(expected) == 26
    assert {s: levels[s] for s in sections} == expected


def test_r22_5_5_3_the_prompt_grows_by_the_level_column_only() -> None:
    lines = skill_list_text().splitlines()
    section_lines = [line for line in lines if not line.startswith("GR-")]
    assert len(section_lines) == 26
    for line in section_lines:
        skill = line.split(" |", 1)[0]
        assert line.endswith(f" | {base_level(skill)}")
        assert line.count(" | ") == 3  # ID | name | what is tested | level


def test_r22_5_5_3_effective_level_falls_back_to_the_base_level() -> None:
    assert tag_level("GR-PSV-A1", "B1") == "B1"  # the question's level wins
    assert tag_level("GR-PSV-A1", None) == "A1"
    assert tag_level("READ-INFER", None) == "B2"
    assert tag_level("VOC-TOPIC", "C1") == "A1"  # not a level → the base level
    assert tag_level("NO-SUCH", None) is None
    assert [level_rank(x) for x in ("A1", "A2", "B1", "B2", None)] == [0, 1, 2, 3, 4]


def test_r22_5_5_3_tag_skills_output_carries_a_level_per_question() -> None:
    ok = {"items": [{"question_id": "q", "tags": ["GR-PSV-A1"], "level": "A2"}]}
    TAG_SKILLS_SCHEMA.model_validate(ok)
    TagSkillsOut.model_validate(ok)
    none = {"items": [{"question_id": "q", "tags": ["GR-PSV-A1"], "level": None}]}
    assert TAG_SKILLS_SCHEMA.model_validate(none).model_dump()["items"][0]["level"] is None
    for bad in ("C1", "a2"):
        with pytest.raises(ValidationError):
            TAG_SKILLS_SCHEMA.model_validate(
                {"items": [{"question_id": "q", "tags": ["GR-PSV-A1"], "level": bad}]}
            )
    with pytest.raises(ValidationError):  # the field is required (null when not known)
        TAG_SKILLS_SCHEMA.model_validate({"items": [{"question_id": "q", "tags": ["GR-PSV-A1"]}]})
    item = TAG_SKILLS_SCHEMA.model_json_schema()["$defs"]["QuestionTagsCall"]
    assert "level" in item["required"]
