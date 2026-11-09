"""LLM output schemas: what each model task returns (llm-design §4, §5).

The model fills these, so they are small, strict (no unknown fields) and use enums wherever the
answer set is known. They carry **no confidence fields**: confidence comes from token logprobs
(D20, llm-design §6).

Two tasks also get a per-call schema, built from the call's inputs:

- ``read_answers_schema(questions)``: one optional property per question ID, with the value type
  of that question's answer form (``choice``: one of its option labels, ``A``-``D`` when it has
  none; ``word`` / ``sentence``: text); ``read_answers_from_call``
  turns the parsed result back into a ``ReadAnswersOut``.
- ``tag_skills_schema(allowed_tags)``: restricts the tags to a taxonomy (step 17.2).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from etach.domain.models import (
    AnswerForm,
    AnswerLocation,
    ErrorType,
    Option,
    Question,
    TeacherQuestion,
)

__all__ = [
    "LLM_SCHEMAS",
    "AiKeyItem",
    "AiKeyOut",
    "AnswerReading",
    "ChoiceReading",
    "ExplainOut",
    "JudgeOut",
    "KeyLabelAnswer",
    "PictureRegion",
    "QuestionLevel",
    "QuestionTags",
    "ReadAnswersOut",
    "ReadHeaderOut",
    "ReadKeyOut",
    "RereadPiece",
    "RereadPiecesOut",
    "SummaryOut",
    "TagSkillsOut",
    "TextReading",
    "TranscribeOut",
    "TranscribedGroup",
    "TranscribedQuestion",
    "TranscribedSection",
    "VerifyKeyOut",
    "choice_labels",
    "choice_value_type",
    "read_answers_from_call",
    "read_answers_schema",
    "tag_skills_schema",
]

#: A ``choice`` question without options is read as one of these letters.
ChoiceLetters = Literal["A", "B", "C", "D"]
#: The forms whose student answer is read as text (``writing`` is not read).
TextAnswerForm = Literal["word", "sentence"]
SectionKind = Literal["questions", "listening", "writing"]
SectionSkill = Literal[
    "pronunciation",
    "stress",
    "grammar",
    "vocabulary",
    "communication",
    "signs",
    "reading",
    "word_form",
    "rewrite",
    "writing",
    "mixed",
]


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- read_key_pages (vision) ---------------------------------------------------------------


class KeyLabelAnswer(_Out):
    label: str  # the printed question label, e.g. "32" (labels can repeat on sloppy keys)
    answer: str


class ReadKeyOut(_Out):
    """Key photo reading, in page order: printed label -> answer."""

    entries: list[KeyLabelAnswer]


# --- read_header (vision, picked path) -----------------------------------------------------


class ReadHeaderOut(_Out):
    """Page-1 header and the first stems, for the picked-test sanity check (= PageHeader)."""

    header_text: str
    first_stems: list[str] = Field(max_length=5)


# --- transcribe_page / retranscribe_tiles (vision) -----------------------------------------


class PictureRegion(_Out):
    """A picture on this page that is not mostly text; box on a 0-1000 grid of the page."""

    x0: int = Field(ge=0, le=1000)
    y0: int = Field(ge=0, le=1000)
    x1: int = Field(ge=0, le=1000)
    y1: int = Field(ge=0, le=1000)


class TranscribedQuestion(_Out):
    printed_number: int
    answer_form: AnswerForm  # by the printed layout (D9); ``context`` is set by code
    stem: str | None  # None for cloze items whose blank is in the group stimulus
    options: list[Option] | None
    cue: str | None
    # sentence only: the words printed to start the answer line (D6); else null
    answer_start: str | None = None
    # step 22.5.7: the rest of a question cut at the previous page's end (same printed number)
    continued: bool = False


class TranscribedGroup(_Out):
    stimulus: str | None
    pictures: list[PictureRegion]
    questions: list[TranscribedQuestion]
    continued: bool = False  # step 22.5.7: the rest of a passage cut at the previous page's end


class TranscribedSection(_Out):
    printed_title: str  # the label as printed, e.g. "VI"
    instructions: str
    kind: SectionKind  # listening: heading + printed range only; writing: the task prompt only
    skill: SectionSkill
    points_text: str | None  # printed points, e.g. "(2.5 pts)"; None if not printed
    range_first: int | None  # listening only: first printed question number
    range_last: int | None  # listening only: last printed question number
    groups: list[TranscribedGroup]
    continued: bool = False  # step 22.5.7: the previous page's last section goes on here


class TranscribeOut(_Out):
    """One page's printed text; no canonical numbers or IDs (code assigns them)."""

    header_text: str | None
    sections: list[TranscribedSection]


# --- reread_pieces (extraction_check, step 22.5.7) ---------------------------------------


class RereadPiece(_Out):
    """One broken or missing question, read again: its section's printed title and the question."""

    section_title: str
    printed_number: int
    answer_form: AnswerForm
    stem: str | None
    options: list[Option] | None
    cue: str | None
    answer_start: str | None = None


class RereadPiecesOut(_Out):
    """Only the questions asked for (the targeted re-read); code patches them into the page."""

    pieces: list[RereadPiece]


# --- read_answers_page (vision) ------------------------------------------------------------


class ChoiceReading(_Out):
    question_id: str
    answer_form: Literal["choice"]
    value: str | None  # one of the question's option labels (the per-call schema lists them)
    location: AnswerLocation
    alt_question_id: str | None  # another question this answer may belong to


class TextReading(_Out):
    question_id: str
    answer_form: TextAnswerForm
    value: str | None  # the handwriting copied exactly
    location: AnswerLocation
    alt_question_id: str | None


AnswerReading = Annotated[ChoiceReading | TextReading, Field(discriminator="answer_form")]


class ReadAnswersOut(_Out):
    """One page's answer readings. A question may have two readings (inline + answer box)."""

    student_name: str | None
    class_name: str | None
    answers: list[AnswerReading]


def choice_labels(question: Question) -> list[str]:
    """The labels a ``choice`` answer may take: its option labels (bare capitals, in order), or
    ``A``-``D`` when it has none."""
    labels = [o.label.strip(" .)(").upper() for o in question.options or []]
    labels = [label for label in dict.fromkeys(labels) if label]
    return labels or ["A", "B", "C", "D"]


def choice_value_type(question: Question) -> Any:
    """The ``value`` type of a ``choice`` reading: a Literal of :func:`choice_labels`."""
    return Literal[tuple(choice_labels(question))]


def read_answers_schema(questions: Sequence[Question]) -> type[BaseModel]:
    """The per-call schema for ``read_answers_page``.

    ``answers`` has one optional property per question ID (writing questions are not read), each a
    list of up to 2 readings (inline + answer box) whose ``value`` follows the answer form: a
    ``choice`` takes one of its option labels (``A``-``D`` when it has none; ``T``/``F`` for a
    True/False question), a ``word`` or ``sentence`` takes text.
    A question not on this page is left out. ``alt_question_id`` is a plain optional string,
    checked in code (``boxes.valid_alt_question_id``). As an enum of the other IDs it made the
    template and ``format`` grow with the square of the question count and overflow ``num_ctx``
    (bug B1); now both grow linearly.
    """
    readable = [q for q in questions if q.answer_form != "writing"]
    ids = [q.id for q in readable]
    if len(set(ids)) != len(ids):
        raise ValueError("question IDs must be unique")
    fields: dict[str, Any] = {}
    for index, question in enumerate(readable):
        value_type: Any = choice_value_type(question) if question.answer_form == "choice" else str
        reading = create_model(
            f"Reading_{index}",
            __config__=ConfigDict(extra="forbid"),
            value=(value_type | None, ...),
            location=(AnswerLocation, ...),
            alt_question_id=(str | None, ...),
        )
        fields[f"q{index}"] = (
            list[reading],  # type: ignore[valid-type]
            Field(default_factory=list, alias=question.id, max_length=2),
        )
    answers = create_model(
        "ReadAnswersByQuestion",
        __config__=ConfigDict(extra="forbid", populate_by_name=True),
        **fields,
    )
    return create_model(
        "ReadAnswersCall",
        __config__=ConfigDict(extra="forbid"),
        student_name=(str | None, ...),
        class_name=(str | None, ...),
        answers=(answers, ...),
    )


def read_answers_from_call(parsed: BaseModel, questions: Sequence[Question]) -> ReadAnswersOut:
    """Turn a result parsed with ``read_answers_schema(questions)`` into a ``ReadAnswersOut``."""
    by_id = {q.id: q for q in questions if q.answer_form != "writing"}
    raw = parsed.model_dump(by_alias=True)
    readings: list[dict[str, Any]] = []
    for question_id, items in raw["answers"].items():
        for item in items:
            readings.append(
                {"question_id": question_id, "answer_form": by_id[question_id].answer_form, **item}
            )
    return ReadAnswersOut.model_validate(
        {
            "student_name": raw["student_name"],
            "class_name": raw["class_name"],
            "answers": readings,
        }
    )


# --- ai_key_fast / verify_key (reasoning) --------------------------------------------------


class AiKeyItem(_Out):
    question_id: str
    accepted: list[str] = Field(min_length=1)  # first = canonical
    reason_vi: str


class AiKeyOut(_Out):
    """Keys for one section."""

    keys: list[AiKeyItem]


class VerifyKeyOut(_Out):
    """One question solved independently; code compares ``answer`` with the stored key."""

    reasoning: str
    answer: str


# --- tag_skills (reasoning) ---------------------------------------------


#: A question's CEFR level from ``tag_skills`` (step 22.5.5, D11d); null = not given, so each
#: tag falls back to its skill's base level (``etach.domain.levels``).
QuestionLevel = Literal["A1", "A2", "B1", "B2"] | None


class QuestionTags(_Out):
    question_id: str
    tags: list[str] = Field(min_length=1)
    level: QuestionLevel


class TagSkillsOut(_Out):
    items: list[QuestionTags]


def tag_skills_schema(allowed_tags: Sequence[str]) -> type[BaseModel]:
    """A ``TagSkillsOut`` whose tags are limited to ``allowed_tags`` (the taxonomy, step 17.2)."""
    if not allowed_tags:
        raise ValueError("allowed_tags must not be empty")
    tag_type: Any = Literal[tuple(dict.fromkeys(allowed_tags))]
    item = create_model(
        "QuestionTagsCall",
        __config__=ConfigDict(extra="forbid"),
        question_id=(str, ...),
        tags=(list[tag_type], Field(min_length=1)),
        level=(QuestionLevel, ...),
    )
    return create_model(
        "TagSkillsCall",
        __config__=ConfigDict(extra="forbid"),
        items=(list[item], ...),  # type: ignore[valid-type]
    )


# --- judge_rewrites / explain / weak_points summary (reasoning) ----------------------------


class JudgeOut(_Out):
    # step 22.5.4: ``reason`` first, so the model checks the sentence before it decides
    reason: str
    verdict: Literal["correct", "incorrect"]


class ExplainOut(_Out):
    # step 22.5.4: the model first works out why the key is right and what the student got wrong;
    # kept only with the call (llm_calls), never stored in Explanation or shown
    reasoning: str
    text_vi: str  # at most 3 sentences, plus short glosses and the correct sentence's meaning
    error_type: ErrorType


class SummaryOut(_Out):
    summary_vi: str  # 4-6 lines for the teacher
    teacher_questions: list[TeacherQuestion] = Field(min_length=3, max_length=5)


LLM_SCHEMAS: tuple[type[BaseModel], ...] = (
    ReadKeyOut,
    ReadHeaderOut,
    TranscribeOut,
    RereadPiecesOut,
    ReadAnswersOut,
    AiKeyOut,
    VerifyKeyOut,
    TagSkillsOut,
    JudgeOut,
    ExplainOut,
    SummaryOut,
)
