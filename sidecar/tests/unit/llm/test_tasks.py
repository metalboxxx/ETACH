"""The extraction task registry and the inputs helper (plan step 8.2)."""

from __future__ import annotations

import pytest

from etach.domain.llm_schemas import ReadHeaderOut, ReadKeyOut, TranscribeOut
from etach.domain.models import Option, Question
from etach.llm.cassettes import MATCH_INPUT_KEYS
from etach.llm.tasks import (
    EXTRACTION_NUM_PREDICT,
    EXTRACTION_TASKS,
    TASKS,
    extraction_inputs,
    question_list_text,
)


def q(i: int, form: str, page: int, options: list[Option] | None = None) -> Question:
    return Question.model_validate(
        {
            "id": f"Q{i}",
            "number": i,
            "printed_number": 30 + i,
            "page_no": page,
            "answer_form": form,
            "stem": None,
            "options": options,
            "cue": None,
            "points": 0.25,
        }
    )


QS = [
    q(1, "choice", 1, [Option(label="A", text="go"), Option(label="B", text="goes")]),
    q(2, "word", 2),
    q(3, "writing", 2),
]


def test_registry_entries() -> None:
    extraction = {
        "read_key_pages",
        "read_header",
        "transcribe_page",
        "structure_text_page",
        "read_answers_page",
        "reread_pieces",
        "ocr_page",
        "ocr_format_page",
    }
    assert {spec.task for spec in EXTRACTION_TASKS} == extraction
    assert extraction <= set(TASKS)
    assert TASKS["read_key_pages"].schema() is ReadKeyOut
    assert TASKS["read_header"].schema() is ReadHeaderOut
    assert TASKS["transcribe_page"].schema() is TranscribeOut
    assert TASKS["read_answers_page"].schema(QS).__name__ == "ReadAnswersCall"
    for spec in EXTRACTION_TASKS:
        # D5; step 22.5.7: the targeted re-read is on extraction_check
        roles = {
            "structure_text_page": "reasoning",
            "reread_pieces": "extraction_check",
            "ocr_page": "ocr",
            "ocr_format_page": "ocr",
        }
        want = roles.get(spec.task, "vision")
        assert (spec.role, spec.think) == (want, False)


def test_profile_policy() -> None:
    assert TASKS["transcribe_page"].profile("hk1") == "generic"
    for task in ("read_key_pages", "read_header", "read_answers_page"):
        assert TASKS[task].profile("hk1") == "hk1"
        assert TASKS[task].profile(None) == "generic"
        assert TASKS[task].profile("") == "generic"


def test_page_hints_only_when_photo_count_equals_page_count() -> None:
    same = extraction_inputs(
        "read_answers_page", page_no=1, photo_count=2, questions=QS, draft_page_count=2
    )
    assert "printed on page 2" in same["question_list"]
    for draft in (3, None):
        other = extraction_inputs(
            "read_answers_page", page_no=1, photo_count=2, questions=QS, draft_page_count=draft
        )
        assert "printed on page" not in other["question_list"]


def test_question_list_lines() -> None:
    text = question_list_text(QS, page_hints=False)
    assert text.splitlines() == [
        "- Q1: no. 31 | choice | options A. go; B. goes",
        "- Q2: no. 32 | word",
    ]


def test_inputs_use_the_match_key_names() -> None:
    inputs = extraction_inputs(
        "read_answers_page", page_no=2, photo_count=2, questions=QS, section_id="S1"
    )
    assert inputs["page_no"] == 2
    assert inputs["question_ids"] == ["Q1", "Q2"]
    assert inputs["section_id"] == "S1"
    assert set(MATCH_INPUT_KEYS) <= set(inputs)
    assert extraction_inputs("transcribe_page", page_no=3, photo_count=4) == {
        "page_no": 3,
        "page_count": 4,
        "previous_page": "",
    }
    assert extraction_inputs("read_header") == {"page_no": 1}
    assert extraction_inputs("read_key_pages", photo_count=2) == {"page_count": 2}


def test_inputs_errors() -> None:
    with pytest.raises(KeyError):
        extraction_inputs("explain")
    with pytest.raises(ValueError, match="questions"):
        extraction_inputs("read_answers_page", page_no=1, photo_count=1)
    with pytest.raises(ValueError, match="page_no"):
        extraction_inputs("transcribe_page", photo_count=1)


def test_num_predict_caps_reach_the_request_body() -> None:
    from etach.llm.adapters import build_request
    from etach.llm.config import parse_models_config
    from etach.prompts.render import FilePromptProvider

    assert EXTRACTION_NUM_PREDICT == {
        "read_header": 512,
        "read_key_pages": 1024,
        "read_answers_page": 2048,
        "transcribe_page": 8192,
        "structure_text_page": 8192,
        "reread_pieces": 2048,
        "ocr_page": 4096,
        "ocr_format_page": 4096,
    }
    roles = parse_models_config({}).roles
    provider = FilePromptProvider()
    for spec in EXTRACTION_TASKS:
        assert isinstance(spec.num_predict, int)
        assert spec.num_predict > 0
        assert spec.num_predict == EXTRACTION_NUM_PREDICT[spec.task]
        inputs = extraction_inputs(
            spec.task,
            page_no=1,
            photo_count=2,
            questions=QS,
            draft_page_count=2,
            pieces="- Question 1",
            ocr_prompt="Text Recognition:",
        )
        prompt = provider.render(spec.task, spec.profile(None), inputs)
        for role in roles.values():  # nuextract (vision) and chat (reasoning)
            req = build_request(
                role, prompt, spec.schema(QS), think=spec.think, num_predict=spec.num_predict
            )
            assert req.body["options"]["num_predict"] == spec.num_predict
            assert req.stored["options"]["num_predict"] == spec.num_predict


def test_a_full_text_page_and_the_transcribe_cap_fit_num_ctx() -> None:
    """M1 long-DOCX fix: a text-only page of ``MAX_TEXT_PAGE_CHARS`` (the split limit) plus the
    ``transcribe_page`` output cap fit ``num_ctx``, by the client's own upper bound."""
    from etach.llm.adapters import build_request
    from etach.llm.client import prompt_size
    from etach.llm.config import parse_models_config
    from etach.prompts.render import FilePromptProvider
    from etach.store.documents import MAX_TEXT_PAGE_CHARS

    spec = TASKS["transcribe_page"]
    assert spec.num_predict == 8192
    role = parse_models_config({}).roles[spec.role]
    num_ctx = role.options["num_ctx"]
    assert num_ctx == 16384
    # the upper bound counts characters (MIN_CHARS_PER_TOKEN each), so any 6 000 characters do
    document = ("Câu 1. Chọn đáp án đúng nhất. A. go  B. goes  C. went  D. gone\n" * 200)[
        :MAX_TEXT_PAGE_CHARS
    ]
    inputs = extraction_inputs("transcribe_page", page_no=2, photo_count=3, document=document)
    prompt = FilePromptProvider().render("transcribe_page", spec.profile(None), inputs)
    req = build_request(role, prompt, spec.schema(), think=spec.think, num_predict=spec.num_predict)
    size = prompt_size(req.body)
    assert not any(m.get("images") for m in req.body["messages"])
    assert size.ceiling + spec.num_predict <= num_ctx, (size, spec.num_predict, num_ctx)
