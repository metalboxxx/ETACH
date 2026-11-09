"""R1.4 (answer-reading value types), R1.5 (the 11 schemas) and the per-call schema builders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from etach.domain import llm_schemas
from etach.domain.llm_schemas import (
    LLM_SCHEMAS,
    ReadAnswersOut,
    read_answers_from_call,
    read_answers_schema,
    tag_skills_schema,
)
from etach.domain.models import Option, Question

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schema"

ELEVEN = [
    "ReadKeyOut",
    "ReadHeaderOut",
    "TranscribeOut",
    "RereadPiecesOut",
    "ReadAnswersOut",
    "AiKeyOut",
    "VerifyKeyOut",
    "TagSkillsOut",
    "JudgeOut",
    "ExplainOut",
    "SummaryOut",
]


def _question(qid: str, form: str, printed: int, labels: str | None = None) -> Question:
    return Question(
        id=qid,
        number=printed - 4,
        printed_number=printed,
        page_no=1,
        answer_form=form,  # type: ignore[arg-type]
        stem=None,
        options=None if labels is None else [Option(label=x, text=x) for x in labels],
        cue=None,
        points=0.25,
    )


QUESTIONS = [
    _question("q-mcq", "choice", 5),  # no options: A-D
    _question("q-tf", "choice", 6, "TF"),  # True/False: the two options the code adds
    _question("q-gap", "word", 7),
    _question("q-wri", "writing", 41),
]


def _reading(form: str, value: Any) -> dict[str, Any]:
    return {
        "question_id": "q-x",
        "answer_form": form,
        "value": value,
        "location": "circled_option",
        "alt_question_id": None,
    }


def _out(*answers: dict[str, Any]) -> dict[str, Any]:
    return {"student_name": None, "class_name": None, "answers": list(answers)}


# --- R1.5 -------------------------------------------------------------------------------------


def test_r1_5_all_eleven_schemas_exist() -> None:
    assert [cls.__name__ for cls in LLM_SCHEMAS] == ELEVEN
    for name in ELEVEN:
        assert issubclass(getattr(llm_schemas, name), BaseModel)


@pytest.mark.parametrize("name", ELEVEN)
def test_r1_5_schema_file_committed(name: str) -> None:
    assert (SCHEMA_DIR / f"{name}.json").is_file()


@pytest.mark.parametrize("cls", LLM_SCHEMAS)
def test_llm_schemas_are_strict_and_have_no_confidence(cls: type[BaseModel]) -> None:
    schema = cls.model_json_schema()
    assert schema.get("additionalProperties") is False
    assert "confidence" not in str(schema).lower()


# --- R1.4 (static schema) ---------------------------------------------------------------------


@pytest.mark.parametrize("value", ["A", "D", "T", None])
def test_r1_4_choice_reading_takes_an_option_label_or_null(value: str | None) -> None:
    """Step 22.5.3: the static schema takes any label; the per-call schema lists the labels."""
    out = ReadAnswersOut.model_validate(_out(_reading("choice", value)))
    assert out.answers[0].value == value and out.answers[0].answer_form == "choice"


@pytest.mark.parametrize("form", ["mcq", "true_false", "gap_fill", "short_answer", "writing"])
def test_r22_5_3_1_reading_forms_are_the_new_ones(form: str) -> None:
    with pytest.raises(ValidationError):
        ReadAnswersOut.model_validate(_out(_reading(form, "A")))


def test_text_readings_take_free_text_and_writing_is_not_read() -> None:
    for form in ("word", "sentence"):
        out = ReadAnswersOut.model_validate(_out(_reading(form, "electric fields")))
        assert out.answers[0].value == "electric fields"
    with pytest.raises(ValidationError):
        ReadAnswersOut.model_validate(_out(_reading("writing", "My village ...")))


# --- R1.4 (per-call schema) -------------------------------------------------------------------


def _call(**answers: Any) -> dict[str, Any]:
    return {"student_name": "Học Sinh A", "class_name": "8X1", "answers": answers}


def _one(value: Any, location: str = "circled_option") -> list[dict[str, Any]]:
    return [{"value": value, "location": location, "alt_question_id": None}]


def test_per_call_schema_has_one_property_per_readable_question() -> None:
    schema = read_answers_schema(QUESTIONS).model_json_schema()
    by_question = schema["$defs"]["ReadAnswersByQuestion"]
    assert list(by_question["properties"]) == ["q-mcq", "q-tf", "q-gap"]
    assert by_question["additionalProperties"] is False


def test_r1_4_per_call_value_types() -> None:
    model = read_answers_schema(QUESTIONS)
    model.model_validate(_call(**{"q-mcq": _one("D"), "q-tf": _one("F"), "q-gap": _one("since")}))
    with pytest.raises(ValidationError):
        model.model_validate(_call(**{"q-mcq": _one("E")}))
    with pytest.raises(ValidationError):
        model.model_validate(_call(**{"q-tf": _one("Y")}))
    with pytest.raises(ValidationError):  # a True/False choice takes only T or F
        model.model_validate(_call(**{"q-tf": _one("A")}))
    with pytest.raises(ValidationError):
        model.model_validate(_call(**{"q-wri": _one("text")}))


def test_per_call_alt_question_id_is_a_plain_string() -> None:
    """B1: any string (or null) parses; ``boxes.valid_alt_question_id`` checks it in code."""
    model = read_answers_schema(QUESTIONS)
    for alt in ("q-mcq", "q-gap", "q-unknown", "verbatim-string", None):
        model.model_validate(
            _call(**{"q-gap": [{"value": "x", "location": "margin", "alt_question_id": alt}]})
        )
    reading = model.model_json_schema()["$defs"]["Reading_2"]["properties"]["alt_question_id"]
    assert reading == {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Alt Question Id"}


def _many(n: int) -> list[Question]:
    from etach.domain.renumber import question_id

    kinds = ("choice", "choice", "word", "word", "sentence")
    return [
        _question(question_id(1, i, f"stem {i}"), kinds[i % len(kinds)], i) for i in range(5, 5 + n)
    ]


def _sizes(n: int) -> tuple[int, int]:
    import json

    from etach.llm.adapters.nuextract import schema_to_template

    model = read_answers_schema(_many(n))
    template = json.dumps(schema_to_template(model), ensure_ascii=False, indent=2)
    fmt = json.dumps(model.model_json_schema(by_alias=True), ensure_ascii=False)
    return len(template), len(fmt)


def test_b1_per_call_template_and_format_grow_linearly() -> None:
    """B1: with an enum of the other IDs, 40 questions gave a ~45k-char template (quadratic).
    Now each question adds the same amount, and 40 questions stay under 14k / 28k chars."""
    t10, f10 = _sizes(10)
    t20, f20 = _sizes(20)
    t40, f40 = _sizes(40)
    assert t40 < 14_000
    assert f40 < 28_000
    per_q_t, per_q_f = (t20 - t10) / 10, (f20 - f10) / 10
    assert abs((t40 - t20) / 20 - per_q_t) <= 2
    assert abs((f40 - f20) / 20 - per_q_f) <= 2


def test_per_call_result_converts_to_read_answers_out() -> None:
    model = read_answers_schema(QUESTIONS)
    parsed = model.model_validate(
        _call(
            **{
                "q-mcq": [*_one("B"), *_one("C", "answer_box")],
                "q-gap": _one("since", "written_in_blank"),
            }
        )
    )
    out = read_answers_from_call(parsed, QUESTIONS)
    assert out.student_name == "Học Sinh A"
    assert [(a.question_id, a.answer_form, a.value, a.location) for a in out.answers] == [
        ("q-mcq", "choice", "B", "circled_option"),
        ("q-mcq", "choice", "C", "answer_box"),
        ("q-gap", "word", "since", "written_in_blank"),
    ]


def test_r22_5_3_4_choice_value_follows_its_options() -> None:
    """The reading value shape per form: a choice takes its own option labels (bare capitals)."""
    q = _question("q-3", "choice", 9, "ABC")
    q = q.model_copy(update={"options": [Option(label=x, text=x) for x in ("A.", "B.", "C.")]})
    model = read_answers_schema([q])
    model.model_validate(_call(**{"q-3": _one("C")}))
    with pytest.raises(ValidationError):
        model.model_validate(_call(**{"q-3": _one("D")}))


def test_per_call_schema_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        read_answers_schema([QUESTIONS[0], QUESTIONS[0]])


# --- tag_skills builder (step 17.2 hook) ------------------------------------------------------


def test_tag_skills_schema_limits_tags() -> None:
    model = tag_skills_schema(["G.TENSE", "V.WORD_FORM"])
    model.model_validate({"items": [{"question_id": "q-1", "tags": ["G.TENSE"], "level": None}]})
    with pytest.raises(ValidationError):
        model.model_validate({"items": [{"question_id": "q-1", "tags": ["P.ED"], "level": None}]})
    with pytest.raises(ValueError):
        tag_skills_schema([])


def test_summary_needs_three_to_five_teacher_questions() -> None:
    question = {"question_vi": "?", "what_answers_mean_vi": "."}
    for count in (3, 5):
        llm_schemas.SummaryOut(summary_vi="s", teacher_questions=[question] * count)  # type: ignore[list-item]
    for count in (2, 6):
        with pytest.raises(ValidationError):
            llm_schemas.SummaryOut.model_validate(
                {"summary_vi": "s", "teacher_questions": [question] * count}
            )
