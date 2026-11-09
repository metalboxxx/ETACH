"""Unreadable text (plan step 21a, PRD D25): R21a.1, the Appendix D.2a phrases.

`retranscribe_tiles` calls the `transcribe_page` task (graphs/extract.py), so it renders the same
prompt file and carries the same rule.
"""

from __future__ import annotations

import pytest

from etach.domain.models import Option, Question
from etach.llm.tasks import TASKS, extraction_inputs
from etach.prompts.render import FilePromptProvider

# plan Appendix D.2a, copied verbatim
D2A: dict[str, list[str]] = {
    "transcribe_page": ["???", "cannot read", "never guess"],
    "read_answers_page": ["???", "cannot read", "never guess"],
}


def _questions() -> list[Question]:
    abcd = [Option(label=x, text=f"opt {x}") for x in "ABCD"]
    return [
        Question.model_validate(
            {
                "id": "Q1",
                "number": 1,
                "printed_number": 5,
                "page_no": 1,
                "answer_form": "choice",
                "stem": "Stem ____ .",
                "options": abcd,
                "cue": None,
                "points": 0.25,
            }
        )
    ]


@pytest.mark.parametrize("profile", [None, "hk1_lop8"])
@pytest.mark.parametrize("task", sorted(D2A))
def test_r21a_1_d2a_phrases_in_each_prompt(task: str, profile: str | None) -> None:
    spec = TASKS[task]
    inputs = extraction_inputs(task, page_no=1, photo_count=1, questions=_questions())
    prompt = FilePromptProvider().render(task, spec.profile(profile), inputs)
    text = f"{prompt.system}\n{prompt.user_text}"
    missing = [p for p in D2A[task] if p not in text]
    assert not missing, f"{task} lacks {missing}"
