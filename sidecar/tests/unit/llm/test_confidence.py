"""Step 6: logprob confidence (plan R6.1-R6.4, llm-design §6)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal

import pytest
from live.phase0 import Phase0Answers
from pydantic import BaseModel, ConfigDict

from etach.domain.llm_schemas import read_answers_schema
from etach.domain.models import Question
from etach.llm.confidence import (
    FieldConfidence,
    MappingError,
    answer_confidence,
    field_confidences,
    logprob_confidences,
    parse_leaves,
    response_offset,
)

CASSETTES = Path(__file__).resolve().parents[2] / "cassettes" / "phase0"

Tok = str | bytes


def entry(tok: Tok, p: float, alts: list[tuple[Tok, float]] | None = None) -> dict[str, Any]:
    raw = tok if isinstance(tok, bytes) else tok.encode("utf-8")
    text = raw.decode("utf-8", "replace")
    tops = [(tok, p), *(alts or [])]
    return {
        "token": text,
        "logprob": math.log(p),
        "bytes": list(raw),
        "top_logprobs": [
            {
                "token": (t if isinstance(t, str) else t.decode("utf-8", "replace")),
                "logprob": math.log(q),
                "bytes": list(t if isinstance(t, bytes) else t.encode("utf-8")),
            }
            for t, q in tops
        ],
    }


def sure(*tokens: Tok) -> list[dict[str, Any]]:
    """Tokens with probability 1 (JSON punctuation around the tested values)."""
    return [entry(t, 1.0) for t in tokens]


def response_of(logprobs: list[dict[str, Any]], skip: int = 0) -> str:
    return b"".join(bytes(e["bytes"]) for e in logprobs[skip:]).decode("utf-8")


class Mcq(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q1: Literal["A", "B", "C", "D"] | None


class Text(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q2: str | None


class Mixed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q1: Literal["A", "B", "C", "D"] | None
    q2: str | None
    location: Literal["circled_option", "written_in_blank"]
    n: int
    ok: bool
    confidence: float | None = None


# --- R6.1: the phase-0 cassettes -----------------------------------------------------------------


def _cassettes() -> list[Path]:
    return sorted(CASSETTES.glob("*.json"))


def _raw(response: bytes, leaf_start: int, leaf_end: int) -> bytes:
    return response[leaf_start:leaf_end]


def _decoded(raw: bytes, value: Any) -> Any:
    text = raw.decode("utf-8")
    return json.loads(f'"{text}"') if isinstance(value, str) else json.loads(text)


def test_r6_1_enough_phase0_cassettes() -> None:
    files = _cassettes()
    assert len(files) >= 3, f"R6.1 needs >= 3 cassettes in {CASSETTES}, found {len(files)}"
    names = [f.name for f in files]
    assert any(n.endswith("_think.json") for n in names), "no thinking cassette"
    assert any(n.endswith("_image.json") for n in names), "no image cassette"


@pytest.mark.parametrize("path", _cassettes(), ids=lambda p: p.name[:3])
def test_r6_1_every_leaf_of_a_phase0_cassette(path: Path) -> None:
    cassette = json.loads(path.read_text(encoding="utf-8"))
    text: str = cassette["response_text"]
    logprobs: list[dict[str, Any]] = cassette["logprobs"]
    assert logprobs, "phase-0 cassettes all have logprobs"
    result = logprob_confidences(text, logprobs, Phase0Answers)

    leaves = parse_leaves(text)
    assert {leaf.path for leaf in leaves} == {"student_name", "class_name", "q1", "q2"}
    assert set(result) == {leaf.path for leaf in leaves}
    response = text.encode("utf-8")
    offset = response_offset(logprobs, text)
    if path.name.endswith("_think.json"):
        assert offset > len(cassette["thinking_text"].encode("utf-8"))  # thinking + </think>
    starts = [0]
    for e in logprobs:
        starts.append(starts[-1] + len(bytes(e["bytes"])))
    for leaf in leaves:
        fc = result[leaf.path]
        assert 0.0 <= fc.confidence <= 1.0
        assert fc.low_trust is False
        assert fc.value == leaf.value == json.loads(text)[leaf.path]
        # the span maps back to the exact value text ...
        assert fc.byte_span == (leaf.start, leaf.end)
        raw = _raw(response, leaf.start, leaf.end)
        assert _decoded(raw, leaf.value) == leaf.value
        # ... and the covering tokens hold exactly that text at that place
        assert fc.token_span is not None
        first, last = fc.token_span
        covered = b"".join(bytes(logprobs[i]["bytes"]) for i in range(first, last))
        at = leaf.start + offset - starts[first]
        assert covered[at : at + len(raw)] == raw
        assert starts[first] <= leaf.start + offset and starts[last] >= leaf.end + offset
        assert fc.seq_prob is not None and 0.0 <= fc.seq_prob <= 1.0
    assert result["q1"].kind == "enum" and result["q1"].value == "B"
    assert result["q1"].confidence > 0.99  # Phase 0 item 3: B at 0.999+
    assert result["q2"].kind == "text" and result["q2"].value == "plays"


# --- R6.2 / R6.3: exact synthetic examples --------------------------------------------------------


def test_r6_2_enum_margin_restricted_and_renormalized() -> None:
    value = entry("D", 0.62, [("B", 0.31), ("A", 0.01), ("C", 0.01), ("(", 0.05)])
    logprobs = [*sure('{"', "q", "1", '":', ' "'), value, *sure('"}')]
    fc = logprob_confidences(response_of(logprobs), logprobs, Mcq)["q1"]
    assert fc.kind == "enum" and fc.value == "D" and fc.low_trust is False
    assert fc.confidence == pytest.approx((0.62 - 0.31) / 0.95, abs=1e-9)
    assert fc.confidence == pytest.approx(0.326, abs=0.001)


def test_r6_3_free_text_minimum_token_probability() -> None:
    logprobs = [
        *sure('{"', "q", "2", '":', ' "'),
        entry("pl", 0.9),
        entry("ay", 0.4),
        entry("s", 0.8),
        *sure('"}'),
    ]
    fc = logprob_confidences(response_of(logprobs), logprobs, Text)["q2"]
    assert fc.kind == "text" and fc.value == "plays"
    assert fc.confidence == pytest.approx(0.4)
    assert fc.seq_prob == pytest.approx(0.9 * 0.4 * 0.8)
    assert fc.token_span == (5, 8)


# --- R6.4: fallbacks ------------------------------------------------------------------------------

REPORTED = (
    '{"q1": "B", "q2": "plays", "location": "circled_option", "n": 3, "ok": true,'
    ' "confidence": 0.7}'
)
LEAVES = {"q1", "q2", "location", "n", "ok", "confidence"}


@pytest.mark.parametrize(
    ("fallback", "second", "expected"),
    [
        ("resample", REPORTED, 1.0),
        (
            "resample",
            REPORTED.replace('"B"', '"C"')
            .replace("plays", "play")
            .replace("3", "4")
            .replace("true", "false")
            .replace("circled_option", "written_in_blank")
            .replace("0.7", "0.2"),
            0.0,
        ),
        ("self_report", None, 0.7),
        ("none", None, 0.0),
        (None, None, 0.0),
    ],
    ids=["resample-agree", "resample-disagree", "self_report", "none", "not-set-means-none"],
)
@pytest.mark.parametrize("logprobs", [None, []], ids=["missing", "empty"])
@pytest.mark.asyncio
async def test_r6_4_fallback_without_logprobs(
    fallback: Any, second: str | None, expected: float, logprobs: Any
) -> None:
    calls: list[int] = []

    async def resample() -> str:
        calls.append(1)
        assert second is not None
        return second

    result = await field_confidences(
        (REPORTED, logprobs), Mixed, fallback=fallback, resample=resample
    )
    assert set(result) == LEAVES
    for fc in result.values():
        assert fc.low_trust is True
        assert fc.confidence == expected
        assert fc.token_span is None and fc.seq_prob is None
    assert len(calls) == (1 if fallback == "resample" else 0)
    assert result["q1"].value == "B" and result["q1"].kind == "enum"


@pytest.mark.asyncio
async def test_resample_partial_agreement_and_parsed_sample() -> None:
    async def resample() -> dict[str, Any]:
        return {**json.loads(REPORTED), "q1": "C"}

    result = await field_confidences(
        (REPORTED, None), Mixed, fallback="resample", resample=resample
    )
    assert result["q1"].confidence == 0.0
    assert result["q2"].confidence == 1.0


@pytest.mark.asyncio
async def test_resample_needs_the_callable() -> None:
    with pytest.raises(ValueError, match="resample"):
        await field_confidences((REPORTED, None), Mixed, fallback="resample")


@pytest.mark.asyncio
async def test_self_report_without_a_confidence_field_is_zero() -> None:
    result = await field_confidences(('{"q2": "plays"}', None), Text, fallback="self_report")
    assert result["q2"].confidence == 0.0 and result["q2"].low_trust is True


@pytest.mark.asyncio
async def test_logprob_result_is_not_low_trust_even_with_a_fallback_set() -> None:
    logprobs = [*sure('{"', "q", "2", '":', ' "'), entry("plays", 0.5), *sure('"}')]
    result = await field_confidences((response_of(logprobs), logprobs), Text, fallback="none")
    assert result["q2"].low_trust is False and result["q2"].confidence == pytest.approx(0.5)


# --- edge cases -----------------------------------------------------------------------------------


def test_escaped_string_span_is_the_escaped_form() -> None:
    logprobs = [
        *sure('{"', "q", "2", '":', ' "'),
        entry("say", 0.9),
        entry(' \\"', 0.7),
        entry('hi\\"', 0.6),
        entry(" caf", 0.95),
        entry("\\u00", 0.5),
        entry("e9", 0.8),
        *sure('"}'),
    ]
    text = response_of(logprobs)
    assert '\\"' in text and "\\u00e9" in text
    fc = logprob_confidences(text, logprobs, Text)["q2"]
    assert fc.value == 'say "hi" café'
    assert fc.byte_span is not None
    raw = text.encode()[fc.byte_span[0] : fc.byte_span[1]]
    assert raw == b'say \\"hi\\" caf\\u00e9'
    assert fc.confidence == pytest.approx(0.5)
    assert fc.token_span == (5, 11)


def test_vietnamese_multibyte_split_across_tokens() -> None:
    word = "Học Sinh".encode()  # "ọ" is 3 bytes: E1 BB 8D
    cut = word.index(b"\xbb")
    logprobs = [
        *sure('{"', "q", "2", '":', ' "'),
        entry(word[:cut], 0.9),  # "H" + half of "ọ"
        entry(word[cut:], 0.3),  # the rest of "ọ" + "c Sinh"
        *sure('"}'),
    ]
    text = response_of(logprobs)
    fc = logprob_confidences(text, logprobs, Text)["q2"]
    assert fc.value == "Học Sinh"
    assert fc.token_span == (5, 7)
    assert fc.confidence == pytest.approx(0.3)


def test_value_starting_mid_token() -> None:
    # the opening quote and the letter share a token; so do the text and the closing quote
    letter = entry(' "B', 0.8, [(' "A', 0.1), (' "b', 0.05), (" null", 0.05)])
    logprobs = [
        *sure('{"', "q1", '":'),
        letter,
        *sure('", "', "q", "2", '":'),
        entry(' "pl', 0.6),
        entry('ays"}', 0.9),
    ]
    text = response_of(logprobs)
    result = logprob_confidences(text, logprobs, Mixed.model_json_schema())
    assert result["q1"].kind == "enum" and result["q1"].value == "B"
    assert result["q1"].confidence == pytest.approx((0.8 - 0.1) / 0.9)  # "b" and null dropped
    assert result["q2"].value == "plays"
    assert result["q2"].confidence == pytest.approx(0.6)


def test_lowercase_letter_is_not_a_choice_and_missing_choices_count_zero() -> None:
    value = entry("B", 0.5, [("b", 0.45), ("A", 0.05)])
    logprobs = [*sure('{"', "q", "1", '":', ' "'), value, *sure('"}')]
    fc = logprob_confidences(response_of(logprobs), logprobs, Mcq)["q1"]
    assert fc.confidence == pytest.approx((0.5 - 0.05) / 0.55)


def test_enum_null_is_the_null_token_probability() -> None:
    logprobs = [*sure('{"', "q", "1", '":'), entry(" null", 0.7, [(' "', 0.3)]), *sure("}")]
    fc = logprob_confidences(response_of(logprobs), logprobs, Mcq)["q1"]
    assert fc.kind == "null" and fc.value is None
    assert fc.confidence == pytest.approx(0.7)


def test_thinking_prefix_is_skipped_by_the_suffix_rule() -> None:
    thinking = [entry("The", 0.2), entry(" answer </think> is", 0.1), entry("\n</think>", 0.99)]
    body = [*sure("\n\n", '{"', "q", "1", '":', ' "'), entry("C", 0.9, [("A", 0.1)]), *sure('"}')]
    logprobs = thinking + body
    text = response_of(body)
    fc = logprob_confidences(text, logprobs, Mcq)["q1"]
    assert fc.token_span == (9, 10)
    assert fc.confidence == pytest.approx(0.8)


def test_missing_bytes_fall_back_to_the_token_text() -> None:
    logprobs = [*sure('{"', "q", "2", '":', ' "'), entry("plays", 0.5), *sure('"}')]
    for e in logprobs:
        del e["bytes"]
    fc = logprob_confidences(response_of_text(logprobs), logprobs, Text)["q2"]
    assert fc.confidence == pytest.approx(0.5)


def response_of_text(logprobs: list[dict[str, Any]]) -> str:
    return "".join(e["token"] for e in logprobs)


@pytest.mark.asyncio
async def test_suffix_mismatch_falls_back() -> None:
    logprobs = [*sure('{"', "q", "2", '":', ' "'), entry("plays", 0.9), *sure('"}')]
    with pytest.raises(MappingError):
        logprob_confidences('{"q2": "played"}', logprobs, Text)
    result = await field_confidences(('{"q2": "played"}', logprobs), Text)
    assert result["q2"] == FieldConfidence(
        value="played",
        confidence=0.0,
        kind="text",
        token_span=None,
        seq_prob=None,
        low_trust=True,
        byte_span=(8, 14),
    )


def test_numbers_bools_and_multitoken_enums_use_min_probability() -> None:
    logprobs = [
        *sure('{"', "q1", '":', ' "'),
        entry("A", 0.9, [("B", 0.1)]),
        *sure('", "', "q2", '":', " "),
        entry("null", 0.8),
        *sure(', "', "location", '":', ' "'),
        entry("circ", 0.7),
        entry("led", 0.95),
        entry("_option", 0.6),
        *sure('", "', "n", '":', " "),
        entry("1", 0.9),
        entry("2", 0.75),
        *sure(', "', "ok", '":', " "),
        entry("true", 0.65),
        *sure("}"),
    ]
    result = logprob_confidences(response_of(logprobs), logprobs, Mixed)
    assert result["q1"].confidence == pytest.approx(0.8)
    assert result["q2"].kind == "null" and result["q2"].confidence == pytest.approx(0.8)
    assert result["location"].kind == "enum_multitoken"
    assert result["location"].confidence == pytest.approx(0.6)
    assert result["n"].kind == "number" and result["n"].value == 12
    assert result["n"].confidence == pytest.approx(0.75)
    assert result["ok"].kind == "bool" and result["ok"].confidence == pytest.approx(0.65)


def test_empty_string_uses_the_closing_quote_token() -> None:
    logprobs = [*sure('{"', "q", "2", '":'), entry(' ""', 0.4), *sure("}")]
    fc = logprob_confidences(response_of(logprobs), logprobs, Text)["q2"]
    assert fc.value == "" and fc.token_span == (4, 5)
    assert fc.confidence == pytest.approx(0.4)


def test_parse_leaves_paths_and_invalid_json() -> None:
    leaves = parse_leaves('{"a": [1, {"b": "x"}], "c": {}, "d": [], "e": -1.5e2}')
    assert [(leaf.path, leaf.value) for leaf in leaves] == [
        ("a[0]", 1),
        ("a[1].b", "x"),
        ("e", -150.0),
    ]
    with pytest.raises(MappingError):
        parse_leaves('{"a": 1} x')


# --- answer_confidence over a read_answers_schema call --------------------------------------------


def _question(qid: str, qtype: str, printed: int) -> Question:
    return Question(
        id=qid,
        number=printed,
        printed_number=printed,
        page_no=1,
        type=qtype,  # type: ignore[arg-type]
        stem=None,
        options=None,
        cue=None,
        points=0.25,
    )


def test_answer_confidence_on_a_read_answers_call() -> None:
    schema = read_answers_schema(
        [_question("q-7f3a", "mcq", 1), _question("q-9b2c", "gap_fill", 2)]
    ).model_json_schema(by_alias=True)
    logprobs = [
        *sure('{"', "student_name", '":', " null", ', "', "class_name", '":', " null", ', "'),
        *sure("answers", '":', ' {"', "q-7f3a", '":', ' [{"', "value", '":', ' "'),
        entry("A", 0.7, [("D", 0.2), ("a", 0.1)]),
        *sure('", "', "location", '":', ' "', "circled_option", '", "'),
        *sure("alt_question_id", '":', " null", '}], "', "q-9b2c", '":', ' [{"', "value", '":'),
        *sure(' "'),
        entry("went", 0.55),
        *sure('", "', "location", '":', ' "', "written_in_blank", '", "'),
        *sure("alt_question_id", '":', ' "', "q-7f3a", '"}]}}'),
    ]
    confidences = logprob_confidences(response_of(logprobs), logprobs, schema)
    mcq = answer_confidence(confidences, "q-7f3a")
    assert mcq.kind == "enum" and mcq.confidence == pytest.approx(0.5 / 0.9)
    gap = answer_confidence(confidences, "q-9b2c", 0)
    assert gap.kind == "text" and gap.confidence == pytest.approx(0.55)
    # B1: alt_question_id is a plain string now (checked in code), so a text leaf
    assert confidences["answers.q-9b2c[0].alt_question_id"].kind == "text"
    assert confidences["answers.q-7f3a[0].location"].value == "circled_option"
    with pytest.raises(KeyError):
        answer_confidence(confidences, "q-7f3a", 1)
