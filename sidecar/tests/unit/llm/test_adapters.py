"""Adapters: request bodies against plan Appendix D.1 (R4.6)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel

from etach.domain.llm_schemas import ReadAnswersOut, read_answers_schema
from etach.domain.models import Option, Question
from etach.llm.adapters import ImageInput, RenderedPrompt, build_request
from etach.llm.adapters.nuextract import nuextract_messages, schema_to_template
from etach.llm.config import RoleConfig, parse_models_config

PROMPT = RenderedPrompt.of("You read exam pages.", "Copy the printed text only.")
IMAGES = [ImageInput("F1", b"img-bytes")]


def role(adapter: str, **extra: Any) -> RoleConfig:
    # the NuExtract role as an older models.toml names it (the default vision is chat, D4)
    cfg = parse_models_config({"roles": {"vision": {"model": "numind/nuextract3:Q6_K"}}})
    base = cfg.roles["vision" if adapter == "nuextract" else "reasoning"]
    return base.model_copy(update=extra)


def assert_common(body: dict[str, Any], r: RoleConfig) -> None:
    assert body["model"] == r.model
    assert body["stream"] is True
    assert body["logprobs"] is True
    assert body["top_logprobs"] == 5
    assert body["options"] == r.options


def test_d1_nuextract_template_instructions_and_think_false(pair: type[BaseModel]) -> None:
    r = role("nuextract", adapter_options={"also_format": False})  # template alone
    req = build_request(r, PROMPT, pair, IMAGES, think=True)
    body = req.body
    assert_common(body, r)
    assert body["think"] is False  # always, even when a call asks for thinking
    assert "format" not in body
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["template", "instructions", "user"]
    template = json.loads(body["messages"][0]["content"])
    assert template == {"a": "integer", "b": "verbatim-string"}
    assert body["messages"][1]["content"] == "You read exam pages.\n\nCopy the printed text only."
    assert body["messages"][2]["images"] == ["aW1nLWJ5dGVz"]
    assert req.stored["messages"][2]["images"] == [{"file_id": "F1"}]


def test_nuextract_also_format_adds_format(pair: type[BaseModel]) -> None:
    r = role("nuextract", adapter_options={"also_format": True})
    body = build_request(r, PROMPT, pair).body
    assert body["format"] == pair.model_json_schema()
    assert body["messages"][0]["role"] == "template"


def test_nuextract_document_text_goes_in_the_user_message(pair: type[BaseModel]) -> None:
    prompt = RenderedPrompt.of("", "Extract.", document="I. Choose the best answer ...")
    body = build_request(role("nuextract"), prompt, pair).body
    assert body["messages"][-1] == {"role": "user", "content": "I. Choose the best answer ..."}
    assert body["messages"][1] == {"role": "instructions", "content": "Extract."}


def test_nuextract_messages_layout_is_isolated() -> None:
    msgs = nuextract_messages('{"x": "string"}', "", "doc", [])
    assert msgs == [
        {"role": "template", "content": '{"x": "string"}'},
        {"role": "user", "content": "doc"},
    ]


def test_d1_chat_system_user_and_format(pair: type[BaseModel]) -> None:
    r = role("chat")
    req = build_request(r, PROMPT, pair, IMAGES)
    body = req.body
    assert_common(body, r)
    assert body["think"] is False  # the role default
    assert body["format"] == pair.model_json_schema()
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["messages"][0]["content"] == "You read exam pages."
    assert body["messages"][1]["content"] == "Copy the printed text only."
    assert body["messages"][1]["images"] == ["aW1nLWJ5dGVz"]
    assert build_request(r, PROMPT, pair, think=True).body["think"] is True


def test_num_predict_goes_into_options(pair: type[BaseModel]) -> None:
    body = build_request(role("chat"), PROMPT, pair, think=True, num_predict=1500).body
    assert body["options"]["num_predict"] == 1500
    assert "num_predict" not in role("chat").options


def test_template_for_discriminated_union_merges_variants() -> None:
    template = schema_to_template(ReadAnswersOut)
    reading = template["answers"][0]
    assert template["student_name"] == "verbatim-string"
    assert set(reading["answer_form"]) == {"choice", "word", "sentence"}
    assert reading["location"] == [
        "circled_option",
        "written_in_blank",
        "answer_box",
        "margin",
        "none",
    ]


def test_template_for_per_call_schema_uses_question_ids() -> None:
    questions = [
        Question(
            id="q-1",
            number=1,
            printed_number=5,
            page_no=1,
            answer_form="choice",
            stem="s",
            options=[Option(label=x, text=x.lower()) for x in "ABCD"],
            cue=None,
            points=0.25,
        ),
        Question(
            id="q-2",
            number=2,
            printed_number=6,
            page_no=1,
            answer_form="choice",
            stem="t",
            options=[Option(label="T", text="True"), Option(label="F", text="False")],
            cue=None,
            points=0.25,
        ),
    ]
    template = schema_to_template(read_answers_schema(questions))
    assert set(template["answers"]) == {"q-1", "q-2"}
    assert template["answers"]["q-1"][0]["value"] == ["A", "B", "C", "D"]
    assert template["answers"]["q-2"][0]["value"] == ["T", "F"]
    # B1: a plain string (checked in code), not an enum of the other IDs
    assert template["answers"]["q-1"][0]["alt_question_id"] == "verbatim-string"


@pytest.mark.parametrize("adapter", ["nuextract", "chat"])
def test_stored_request_has_no_base64(adapter: str, pair: type[BaseModel]) -> None:
    req = build_request(role(adapter), PROMPT, pair, IMAGES)
    assert "aW1nLWJ5dGVz" not in json.dumps(req.stored)
    assert "aW1nLWJ5dGVz" in json.dumps(req.body)
