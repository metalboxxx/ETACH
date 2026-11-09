"""Domain classes: data-model §2.1-2.8 (field names per plan Appendix A).

These are the source of truth for the stored data. Every class forbids unknown fields, so a
``Run.input`` union resolves without ambiguity and JSON read back from the database is strict.
Datetimes must carry a timezone.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

__all__ = [
    "FORM_OF_OLD_TYPE",
    "OCCASIONS",
    "TRUE_FALSE_OPTIONS",
    "Answer",
    "AnswerForm",
    "AnswerKey",
    "AnswerLocation",
    "Attempt",
    "AttemptPage",
    "ErrorType",
    "Explanation",
    "ExtractInput",
    "File",
    "GradeInput",
    "GradeReport",
    "KeyCheck",
    "LlmCall",
    "Message",
    "OmittedSection",
    "Option",
    "PageInput",
    "PictureRef",
    "Question",
    "QuestionContext",
    "QuestionGroup",
    "ReviewItem",
    "RichText",
    "Run",
    "Section",
    "Step",
    "Student",
    "TeacherQuestion",
    "Test",
    "TestContent",
    "TestMetadata",
    "Thread",
    "WeakPoint",
    "WeakPointLabel",
    "listening_range",
    "local_today",
    "true_false_letters",
]

RichText = str
"""Markdown subset: **bold**, <u>underline</u>, line breaks."""

OCCASIONS: tuple[str, ...] = (
    "MidTerm",
    "FinalTerm",
    "NationalExam",
    "EntranceExam",
    "GiftedExam",
    "UnitTest",
    "FifteenMinuteTest",
    "GrammarPractice",
    "TopicPractice",
    "Placement",
)
#: What an unmatched header occasion becomes (``domain.header.UNKNOWN_OCCASION``).
UNKNOWN_OCCASION_CODE = "Other:unknown"
_OTHER_OCCASION = re.compile(r"^Other:\S.*$")
#: A teacher occasion's code (data-model v1.17): "Custom:<id>", a row of the ``occasions`` table.
CUSTOM_OCCASION_PREFIX = "Custom:"
_CUSTOM_OCCASION = re.compile(r"^Custom:[0-9a-z]+$")
EN_DASH = chr(0x2013)

#: The shape of the student's answer (data-model v1.22, step 22.5.3, D9), chosen by the model from
#: the printed layout: ``choice`` a letter or True/False; ``word`` one word or a short phrase in a
#: blank; ``sentence`` a whole sentence; ``writing`` a paragraph or essay (not graded).
AnswerForm = Literal["choice", "word", "sentence", "writing"]
#: Whether the question relies on its group's shared text, set by code (never by the model):
#: ``paragraph`` when the group has a ``stimulus``, else ``single``; ``None`` for ``writing``.
QuestionContext = Literal["single", "paragraph"]

#: The 11 question types before step 22.5.3 → the answer form (the first-start pass, D9). The old
#: value stays on each stored question as ``old_type``, which only a revert reads.
FORM_OF_OLD_TYPE: dict[str, AnswerForm] = {
    "mcq": "choice",
    "true_false": "choice",
    "matching": "choice",
    "gap_fill": "word",
    "word_form": "word",
    "verb_form": "word",
    "rewrite": "sentence",
    "combine": "sentence",
    "ordering": "sentence",
    "short_answer": "sentence",
    "writing": "writing",
}
#: The two options code adds to a True/False ``choice`` (label, text).
TRUE_FALSE_OPTIONS: tuple[tuple[str, str], ...] = (("T", "True"), ("F", "False"))

#: The option texts that mean True / False, after NFC, trim, case-fold and trailing punctuation.
_TRUE_FALSE_WORDS = ({"true": "T", "false": "F"}, {"đúng": "T", "sai": "F"})
_TRAILING = " .,;:!?"


def true_false_letters(options: Sequence[tuple[str, str]] | None) -> dict[str, str] | None:
    """For a choice's options as (label, text): when there are exactly two and their texts are
    True and False in either order (also Đúng and Sai; NFC, trimmed, any case, trailing
    punctuation ignored), the map from each label to ``T`` (the one that meant True) or ``F``.
    Anything else gives None (step 22.5.3 checklist (d), R22.5.3.8)."""
    if not options or len(options) != 2:
        return None
    words = {
        label: unicodedata.normalize("NFC", text or "").strip().rstrip(_TRAILING).casefold()
        for label, text in options
    }
    if len(words) != 2:
        return None
    for pair in _TRUE_FALSE_WORDS:
        if set(words.values()) == set(pair):
            return {label: pair[word] for label, word in words.items()}
    return None


def context_of(answer_form: str, stimulus: str | None) -> QuestionContext | None:
    """A question's ``context`` from its form and its group's ``stimulus`` (code, not the model)."""
    if answer_form == "writing":
        return None
    return "paragraph" if stimulus is not None and stimulus.strip() else "single"


def upgrade_question_data(data: dict[str, Any]) -> dict[str, Any]:
    """A question stored before step 22.5.3 (``type``, no ``answer_form``) in the new shape: the
    form by :data:`FORM_OF_OLD_TYPE`, ``old_type`` = the old value, and a ``true_false`` question
    without options gets the two True/False options. Anything else is returned unchanged."""
    if "type" not in data or "answer_form" in data:
        return data
    out = dict(data)
    old = out.pop("type")
    out["answer_form"] = FORM_OF_OLD_TYPE.get(str(old), "sentence")
    out.setdefault("old_type", old)
    if old == "true_false" and not out.get("options"):
        out["options"] = [{"label": label, "text": text} for label, text in TRUE_FALSE_OPTIONS]
    return out


AnswerLocation = Literal["circled_option", "written_in_blank", "answer_box", "margin", "none"]
ErrorType = Literal["gap", "careless", "spelling", "misread_question", "unknown"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- helpers -------------------------------------------------------------------------------


class OmittedSection(_Model):
    """A section left out of points_possible: listening (not stored) or writing (graded=False)."""

    title: str
    questions: list[int]  # the printed question numbers, e.g. [1, 2, 3, 4]
    points: float
    # v1.25 (step 22.5.6): which part was left out; None = stored before (see listening_range)
    kind: Literal["listening", "writing"] | None = None


def listening_range(meta: TestMetadata, content: TestContent) -> tuple[int, int] | None:
    """The printed range (first, last) of the listening part left out, or None (data-model
    v1.25). A section stored before step 22.5.6 has no ``kind``: it is listening when none of its
    printed numbers is a stored question (a writing section is stored, ``graded=False``)."""
    stored = {q.printed_number for s in content.sections for g in s.groups for q in g.questions}
    nums = [
        n
        for o in meta.omitted_sections
        if o.kind == "listening"
        or (o.kind is None and o.questions and not stored.intersection(o.questions))
        for n in o.questions
    ]
    return (min(nums), max(nums)) if nums else None


class Option(_Model):
    label: str  # "A"
    text: RichText


#: A weak point's trajectory label (D11), or ``this_paper_only`` while the skill has fewer than 3
#: papers (D11c). Improved and solid skills are not weak points.
WeakPointLabel = Literal["slipped", "consistently_weak", "inconsistent", "this_paper_only"]


class WeakPoint(_Model):
    skill_tag: str
    wrong: int
    seen: int
    gap_errors: int
    note_vi: str
    # v1.24 (step 22.5.5, D11c-e); reports saved before read as None / None / False
    label: WeakPointLabel | None = None
    level: Literal["A1", "A2", "B1", "B2"] | None = None
    held_back: bool = False  # above the lowest weak level: "later, after the basics"


class TeacherQuestion(_Model):
    question_vi: str
    what_answers_mean_vi: str


# --- 2.1 Student ---------------------------------------------------------------------------


class Student(_Model):
    id: str
    full_name: str
    name_search: str
    class_name: str | None
    school: str | None
    grade: int | None
    notes: str = ""
    created_at: AwareDatetime


# --- 2.2 Test ------------------------------------------------------------------------------


class TestMetadata(_Model):
    # the fields the teacher asked for (only `occasion` is required)
    occasion: str
    grade: int | None = None
    year: str | None = None
    school: str | None = None
    created_by_ai: bool = False
    # extras
    term: int | None = None
    test_number: str | None = None
    variant: str | None = None
    test_code: str | None = None
    region: str | None = None
    source: str | None = None
    textbook: str | None = None
    units: list[str] = []
    duration_minutes: int | None = None
    exam_format: str | None = None
    omitted_sections: list[OmittedSection] = []
    tags: list[str] = []
    parent_test_id: str | None = None
    extra: dict[str, str | int | float | bool] = {}
    edited_fields: list[str] = []

    @field_validator("occasion")
    @classmethod
    def _check_occasion(cls, value: str) -> str:
        if value in OCCASIONS or _OTHER_OCCASION.match(value) or _CUSTOM_OCCASION.match(value):
            return value
        raise ValueError(
            f"occasion must be one of {', '.join(OCCASIONS)}, 'Other:<text>' or 'Custom:<id>'"
        )

    def display_name(self) -> str:
        """The Test name. A name the teacher typed (data-model v1.13: ``display_name`` in
        ``edited_fields``, the text in ``extra["display_name"]``) is kept as typed. Otherwise the
        automatic name (decision C, data-model v1.11): grade - occasion + term - school (else
        source) - year - test number, in English, joined by " - "; empty parts and an unknown
        occasion are left out. E.g. "Grade 8 - Final Term 1 - Nguyễn Hữu Thọ - 2025 - Test 7"."""
        typed = self.extra.get(TYPED_NAME_KEY)
        if TYPED_NAME_KEY in self.edited_fields and isinstance(typed, str) and typed.strip():
            return typed
        return self.automatic_name()

    def automatic_name(self) -> str:
        """The automatic Test name, ignoring a typed one (see :meth:`display_name`)."""
        parts: list[str] = []
        if self.grade is not None:
            parts.append(f"Grade {self.grade}")
        occasion = occasion_short_name(self.occasion)
        if occasion:
            parts.append(occasion if self.term is None else f"{occasion} {self.term}")
        if self.school or self.source:
            parts.append(self.school or self.source or "")
        if self.year:
            parts.append(self.year.replace("-", EN_DASH))
        if self.test_number:
            parts.append(f"Test {self.test_number}")
        return " - ".join(parts) or UNTITLED_TEST


#: The automatic name when every part is empty (an unknown occasion and nothing else).
UNTITLED_TEST = "Untitled test"

#: The ``edited_fields`` entry and ``extra`` key of a Test name the teacher typed (v1.13).
TYPED_NAME_KEY = "display_name"

#: The occasion in the Test name (decision C; "Unit Test" / "15-minute Test", v1.13). v1.17: the
#: ``occasions`` table is the source; the store loads its short names here
#: (:func:`set_occasion_short_names`) when the database opens and after every occasion write.
#: These built-in values are only the defaults before a database is open (the migration's seed).
OCCASION_SHORT_NAMES: dict[str, str] = {
    "MidTerm": "Mid-term",
    "FinalTerm": "Final Term",
    "NationalExam": "National Exam",
    "EntranceExam": "Entrance Exam",
    "GiftedExam": "Gifted Exam",
    "UnitTest": "Unit Test",
    "FifteenMinuteTest": "15-minute Test",
    "GrammarPractice": "Grammar Practice",
    "TopicPractice": "Topic Practice",
    "Placement": "Placement",
}


def set_occasion_short_names(names: dict[str, str]) -> None:
    """Replace the short names :func:`occasion_short_name` uses (from the ``occasions`` table)."""
    OCCASION_SHORT_NAMES.clear()
    OCCASION_SHORT_NAMES.update(names)


def occasion_short_name(occasion: str) -> str:
    """``FinalTerm`` → "Final Term"; ``Other:<text>`` → the text; the unknown occasion
    (``Other:unknown``) → "" (left out of the name, v1.13)."""
    if occasion == UNKNOWN_OCCASION_CODE:
        return ""
    if occasion.startswith("Other:"):
        return occasion.removeprefix("Other:").strip() or "Other"
    return OCCASION_SHORT_NAMES.get(occasion, occasion)


class Test(_Model):
    id: str
    meta: TestMetadata
    content: TestContent
    content_schema_version: int
    fingerprint: str
    points_possible: float
    source_run_id: str | None
    merged_into: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


# --- 2.3 Test content ----------------------------------------------------------------------


class PictureRef(_Model):
    file_id: str
    page_no: int


class Question(_Model):
    id: str
    number: int
    printed_number: int
    page_no: int
    answer_form: AnswerForm  # v1.22 (D9): replaces the 11-value ``type``
    # v1.22: set by code from the group's stimulus (QuestionGroup); None for writing
    context: QuestionContext | None = None
    stem: RichText | None
    options: list[Option] | None
    cue: str | None
    # v1.16 (D6): a sentence question: the words the paper prints to start the answer line
    answer_start: str | None = None
    points: float
    # v1.22: read-only; the question's type before step 22.5.3 (mcq, gap_fill, …), kept by the
    # first-start pass so a revert loses nothing. Nothing else reads it; None for later questions.
    old_type: str | None = None
    # v1.22.2: read-only; a True/False choice's options as stored before the first-start pass,
    # or as read before an extraction, relabelled them T/F (e.g. "A. FALSE", "B. TRUE"): a revert
    # restores them, and a key-photo or student letter is mapped through them. None otherwise.
    old_options: list[Option] | None = None

    @model_validator(mode="before")
    @classmethod
    def _legacy_type(cls, data: Any) -> Any:
        # a question written before step 22.5.3 (a run paused across the upgrade)
        return upgrade_question_data(data) if isinstance(data, dict) else data


class QuestionGroup(_Model):
    id: str
    stimulus: RichText | None
    pictures: list[PictureRef]
    questions: list[Question]

    @model_validator(mode="after")
    def _set_context(self) -> QuestionGroup:
        """Each question's ``context`` follows this group's stimulus, whatever was given."""
        if any(q.context != context_of(q.answer_form, self.stimulus) for q in self.questions):
            self.questions = [
                q.model_copy(update={"context": context_of(q.answer_form, self.stimulus)})
                for q in self.questions
            ]
        return self


class Section(_Model):
    id: str
    number: int
    printed_title: str
    title: str
    instructions: str
    points: float
    points_source: Literal["printed", "assumed", "equal"]  # v1.19: always "equal"
    skill: str  # pronunciation | stress | grammar | vocabulary | communication | signs
    #             | reading | word_form | rewrite | writing | mixed
    graded: bool = True
    groups: list[QuestionGroup]


class TestContent(_Model):
    sections: list[Section]


# --- 2.4 Answer key ------------------------------------------------------------------------


class KeyCheck(_Model):
    """What ``verify_key`` said when it did not confirm the key (data-model v1.24, step 22.5.5).

    ``disagreed``: the checker's own ``answer`` and its ``reasoning``. ``unsure``: the checker
    answered ``?`` (step 22.6.3, D6), so only its ``reasoning`` is kept. ``did_not_finish``: the
    check was cut off or failed twice, so there is no answer (both ``None``)."""

    status: Literal["disagreed", "unsure", "did_not_finish"]
    answer: str | None = None
    reasoning: str | None = None


class AnswerKey(_Model):
    test_id: str
    question_id: str
    accepted: list[str]
    reason_vi: str | None
    source: Literal["from_key_photo", "ai", "teacher_edit"]
    # v1.25 (step 22.5.6): ``from_key_photo`` = read from the key photo, no second call;
    # ``ai_verified`` = a second call (``verify_key``) agreed
    status: Literal[
        "ai_unverified", "ai_verified", "ai_uncertain", "teacher_verified", "from_key_photo"
    ]
    confidence: float | None
    updated_at: AwareDatetime
    # step 22.5.5: kept while the key is ``ai_uncertain`` from ``verify_key``; None otherwise
    checker: KeyCheck | None = None


# --- 2.5 Attempt, AttemptPage, Answer, GradeReport -----------------------------------------


def local_today() -> date:
    """Today on the teacher's computer (the default date taken, step 22.5.5)."""
    return datetime.now().astimezone().date()


class Attempt(_Model):
    id: str
    test_id: str
    thread_id: str
    student_id: str | None
    student_name_read: str | None
    class_read: str | None
    source_run_id: str
    superseded_by: str | None
    status: Literal["extracted", "graded", "reviewed"]
    version: int
    score_earned: float | None
    score_possible: float | None
    created_at: AwareDatetime
    # v1.24 (D11a): the day the student did the paper; the trajectory orders by it, then
    # created_at. Default today; migration 0014 gave stored attempts the date of created_at.
    taken_on: date = Field(default_factory=local_today)

    @model_validator(mode="before")
    @classmethod
    def _taken_on_from_created(cls, data: Any) -> Any:
        """A row with no date taken (NULL) reads as the local date of ``created_at``."""
        if isinstance(data, dict) and data.get("taken_on") is None and "taken_on" in data:
            created = data.get("created_at")
            if isinstance(created, str):
                created = datetime.fromisoformat(created)
            if isinstance(created, datetime):
                data = {**data, "taken_on": created.astimezone().date()}
        return data


class AttemptPage(_Model):
    attempt_id: str
    page_no: int
    file_id: str
    source_file_id: str
    rotation: int


class Answer(_Model):
    attempt_id: str
    question_id: str
    printed_number: int
    page_no: int | None
    value: str | None
    value_norm: str | None
    location: AnswerLocation
    confidence: float
    low_trust: bool = False
    reading_unsure: bool
    alt_value: str | None
    alt_question_id: str | None
    verdict: Literal["correct", "incorrect", "uncertain", "ungraded"] = "ungraded"
    near_miss: bool = False
    points_awarded: float | None
    teacher_override: str | None


class GradeReport(_Model):
    attempt_id: str
    run_id: str
    weak_points: list[WeakPoint]
    careless_notes: list[str]
    summary_vi: str
    teacher_questions: list[TeacherQuestion]
    uncertain_points: float
    created_at: AwareDatetime


# --- 2.6 Explanation cache -----------------------------------------------------------------


class Explanation(_Model):
    test_id: str
    question_id: str
    wrong_answer_norm: str
    error_type: ErrorType
    text_vi: str
    status: Literal["ai", "teacher_edited"]
    llm_call_id: str | None  # NULL once a thread delete removes the call (data-model v1.24.1)


# --- 2.7 Thread, Message, run inputs, Run, Step, LlmCall -----------------------------------


class Thread(_Model):
    id: str
    title: str
    test_id: str | None
    kind: Literal["filled", "blank", "pending"]
    created_at: AwareDatetime


class Message(_Model):
    id: str
    thread_id: str
    role: Literal["teacher", "app"]
    kind: Literal["text", "photo_check", "run_card", "grade_card", "notice"]
    body: dict[str, Any]
    created_at: AwareDatetime


class PageInput(_Model):
    file_id: str
    rotation: Literal[0, 90, 180, 270]
    is_key: bool
    text_file_id: str | None


class ExtractInput(_Model):
    pages: list[PageInput]
    existing_test_id: str | None
    supersedes_attempt_id: str | None
    series_from_test_id: str | None = None  # v1.14 (D3): "same series as…"; applied at save
    # v1.21 (D5): "same series as…" picks a series name: source = the name, and grade, occasion,
    # term and year from the newest test of that series; applied at save
    series_name: str | None = None
    # v1.21 (D8): Extract again: the test the photos were read for before (compare_bank leaves it
    # out); "replace" saves the new reading into that test, "copy" makes a new test
    again_test_id: str | None = None
    again_mode: Literal["replace", "copy"] | None = None
    # v1.24 (D11a): the date the student's paper was taken (photo check card); None = today
    taken_on: date | None = None


class GradeInput(_Model):
    test_id: str
    attempt_id: str | None
    # v1.33 (step 22.6.4, D4): ``after_extract``, the key run an extraction's save queues
    # (``attempt_id`` None: the key, its check and the skill tags; no grading)
    reason: Literal["button", "key_verified", "merge", "review_fix", "points_fix", "after_extract"]


class Run(_Model):
    id: str
    thread_id: str
    kind: Literal["extract", "grade"]
    input: ExtractInput | GradeInput
    status: Literal[
        "queued", "running", "stopping", "stopped", "interrupted", "failed", "discarded", "done"
    ]
    started_at: AwareDatetime | None
    finished_at: AwareDatetime | None
    error: str | None


class Step(_Model):
    id: str
    run_id: str
    node: str
    item: str | None
    try_no: int
    status: Literal["running", "done", "incomplete", "failed", "skipped"]
    started_at: AwareDatetime
    finished_at: AwareDatetime | None


class LlmCall(_Model):
    id: str
    step_id: str
    role: Literal["vision", "reasoning", "grading_check", "extraction_check", "ocr"]
    model: str
    prompt_hash: str
    request: dict[str, Any]
    response_text: str
    thinking_text: str
    logprobs: list[Any] | None
    status: Literal["streaming", "complete", "invalid", "incomplete", "cancelled", "error"]
    tokens_in: int | None
    tokens_out: int | None
    ms: int | None
    created_at: AwareDatetime


# --- 2.8 Review item, File -----------------------------------------------------------------


class ReviewItem(_Model):
    id: str
    kind: Literal[
        "uncertain_answer",
        "box_inline_conflict",
        "uncertain_key",
        "key_unmapped",
        "possible_duplicate",
        "picked_test_mismatch",
        "unknown_student",
        "unknown_occasion",
        "points_assumed",
        "validator_failed",
        "merge_unaligned",
        "unreadable_text",
    ]
    owner: Literal["extract", "grade"]
    test_id: str | None
    attempt_id: str | None
    question_id: str | None
    dedupe_key: str
    proposal: dict[str, Any]
    resolution: dict[str, Any] | None
    followup_run_id: str | None
    status: Literal["open", "accepted", "fixed", "skipped", "obsolete"]
    created_at: AwareDatetime
    resolved_at: AwareDatetime | None


class File(_Model):
    id: str
    path: str
    kind: Literal["upload", "derived", "text", "export"]
    derived_from: str | None
    mime: str
    width: int | None
    height: int | None
    created_at: AwareDatetime
    original_name: str | None = None


# Test is declared before TestContent; resolve the forward reference.
Test.model_rebuild()
