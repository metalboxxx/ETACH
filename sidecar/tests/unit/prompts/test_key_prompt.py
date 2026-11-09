"""Step 22.5.6 R22.5.6.4: the key prompt ignores explanations on the key pages.

The national keys print an explanation under each answer. The prompt says in one line that
explanations are ignored; the output schema has room only for label-answer pairs, so a synthetic
key page with explanations maps to keys holding only the answers.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from etach.domain.keymap import map_key
from etach.domain.llm_schemas import ReadKeyOut
from etach.llm.tasks import TASKS
from etach.prompts.render import FilePromptProvider

from ..domain.test_keymap import b1_draft

#: a synthetic key page: each answer followed by its printed explanation
KEY_PAGE = [
    ("5", "B", "Giải thích: 'since' đi với mốc thời gian."),
    ("6", "C", "Giải thích: câu bị động thì hiện tại hoàn thành."),
    ("7", "A", "Giải thích: 'interested in' + V-ing."),
]


def test_r22_5_6_4_prompt_says_explanations_are_ignored() -> None:
    task = "read_key_pages"
    prompt = FilePromptProvider().render(task, TASKS[task].profile(None), {"page_count": 1})
    lines = [line for line in prompt.system.splitlines() if "explanation" in line.lower()]
    assert len(lines) == 1
    assert "ignore" in lines[0].lower()
    assert "answer next to it" in lines[0]


def test_r22_5_6_4_key_page_with_explanations_gives_only_pairs() -> None:
    reply = {"entries": [{"label": n, "answer": a} for n, a, _ in KEY_PAGE]}
    out = ReadKeyOut.model_validate(reply)
    mapped = map_key(out.entries, b1_draft(), threshold=0.7, ref="r1")
    assert [e.accepted for e in mapped.entries] == [["B"], ["C"], ["A"]]
    assert not mapped.pendings
    # an explanation has no place in the output: a reply carrying one is rejected
    with pytest.raises(ValidationError):
        ReadKeyOut.model_validate(
            {"entries": [{"label": n, "answer": a, "explanation": x} for n, a, x in KEY_PAGE]}
        )
