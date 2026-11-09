# ruff: noqa: E501
"""R1.1 (class manifest), literal sets, R1.3 (display_name) and model rules."""

from __future__ import annotations

from datetime import datetime
from typing import Any, get_args

import pytest
from pydantic import BaseModel, ValidationError

from etach.domain import DATA_MODEL_CLASSES, models, working

# plan.md Appendix A, copied verbatim (one entry per line of the manifest).
# fmt: off
APPENDIX_A: dict[str, list[str]] = {
    "Student": ["id", "full_name", "name_search", "class_name", "school", "grade", "notes", "created_at"],
    "Test": ["id", "meta", "content", "content_schema_version", "fingerprint", "points_possible", "source_run_id", "merged_into", "created_at", "updated_at"],
    "TestMetadata": ["occasion", "grade", "year", "school", "created_by_ai", "term", "test_number", "variant", "test_code", "region", "source", "textbook", "units", "duration_minutes", "exam_format", "omitted_sections", "tags", "parent_test_id", "extra", "edited_fields"],
    "TestContent": ["sections"],
    "Section": ["id", "number", "printed_title", "title", "instructions", "points", "points_source", "skill", "graded", "groups"],
    "QuestionGroup": ["id", "stimulus", "pictures", "questions"],
    "Question": ["id", "number", "printed_number", "page_no", "answer_form", "context", "stem", "options", "cue", "answer_start", "points", "old_type", "old_options"],
    "PictureRef": ["file_id", "page_no"],
    "AnswerKey": ["test_id", "question_id", "accepted", "reason_vi", "source", "status", "confidence", "updated_at", "checker"],
    "Attempt": ["id", "test_id", "thread_id", "student_id", "student_name_read", "class_read", "source_run_id", "superseded_by", "status", "version", "score_earned", "score_possible", "created_at", "taken_on"],
    "AttemptPage": ["attempt_id", "page_no", "file_id", "source_file_id", "rotation"],
    "Answer": ["attempt_id", "question_id", "printed_number", "page_no", "value", "value_norm", "location", "confidence", "low_trust", "reading_unsure", "alt_value", "alt_question_id", "verdict", "near_miss", "points_awarded", "teacher_override"],
    "GradeReport": ["attempt_id", "run_id", "weak_points", "careless_notes", "summary_vi", "teacher_questions", "uncertain_points", "created_at"],
    "Explanation": ["test_id", "question_id", "wrong_answer_norm", "error_type", "text_vi", "status", "llm_call_id"],
    "Thread": ["id", "title", "test_id", "kind", "created_at"],
    "Message": ["id", "thread_id", "role", "kind", "body", "created_at"],
    "PageInput": ["file_id", "rotation", "is_key", "text_file_id"],
    "ExtractInput": ["pages", "existing_test_id", "supersedes_attempt_id", "series_from_test_id", "series_name", "again_test_id", "again_mode", "taken_on"],
    "GradeInput": ["test_id", "attempt_id", "reason"],
    "Run": ["id", "thread_id", "kind", "input", "status", "started_at", "finished_at", "error"],
    "Step": ["id", "run_id", "node", "item", "try_no", "status", "started_at", "finished_at"],
    "LlmCall": ["id", "step_id", "role", "model", "prompt_hash", "request", "response_text", "thinking_text", "logprobs", "status", "tokens_in", "tokens_out", "ms", "created_at"],
    "ReviewItem": ["id", "kind", "owner", "test_id", "attempt_id", "question_id", "dedupe_key", "proposal", "resolution", "followup_run_id", "status", "created_at", "resolved_at"],
    "File": ["id", "path", "kind", "derived_from", "mime", "width", "height", "created_at", "original_name"],
    # Helpers: OmittedSection(title, questions, points, kind)
    #          Option(label, text) · WeakPoint(skill_tag, wrong, seen, gap_errors, note_vi, label, level, held_back) · TeacherQuestion(question_vi, what_answers_mean_vi)
    "OmittedSection": ["title", "questions", "points", "kind"],
    "Option": ["label", "text"],
    "WeakPoint": ["skill_tag", "wrong", "seen", "gap_errors", "note_vi", "label", "level", "held_back"],
    "TeacherQuestion": ["question_vi", "what_answers_mean_vi"],
}

# Appendix A: "Working types: as data-model §2.9" — the fields copied from data-model §2.9.
WORKING_TYPES: dict[str, list[str]] = {
    "PreparedPage": ["page_no", "file_id", "source_file_id", "rotation", "text_layer"],
    "PageTranscript": ["page_no", "header_text", "sections", "llm_call_id"],
    "TestDraft": ["meta", "content", "fingerprint", "points_possible"],
    "PageHeader": ["header_text", "first_stems"],
    "KeyEntry": ["question_id", "accepted", "confidence"],
    "PageAnswers": ["page_no", "answers", "student_name", "class_name"],
    "CompareResult": ["best_test_id", "similarity", "question_alignment"],
    "PendingReview": ["kind", "dedupe_key", "refs", "proposal"],
    "SavedIds": ["test_id", "attempt_id"],
}

# Literal sets exactly as written in data-model §2: (class, field) -> values.
LITERAL_SETS: dict[tuple[str, str], tuple[Any, ...]] = {
    ("Section", "points_source"): ("printed", "assumed", "equal"),  # v1.19
    ("Question", "answer_form"): ("choice", "word", "sentence", "writing"),  # v1.22 (D9)
    ("Question", "context"): ("single", "paragraph"),  # v1.22: set by code; None for writing
    ("AnswerKey", "source"): ("from_key_photo", "ai", "teacher_edit"),
    ("AnswerKey", "status"): (
        "ai_unverified",
        "ai_verified",
        "ai_uncertain",
        "teacher_verified",
        "from_key_photo",
    ),
    ("Attempt", "status"): ("extracted", "graded", "reviewed"),
    ("Answer", "location"): ("circled_option", "written_in_blank", "answer_box", "margin", "none"),
    ("Answer", "verdict"): ("correct", "incorrect", "uncertain", "ungraded"),
    ("Explanation", "error_type"): ("gap", "careless", "spelling", "misread_question", "unknown"),
    ("Explanation", "status"): ("ai", "teacher_edited"),
    ("Thread", "kind"): ("filled", "blank", "pending"),
    ("Message", "role"): ("teacher", "app"),
    ("Message", "kind"): ("text", "photo_check", "run_card", "grade_card", "notice"),
    ("PageInput", "rotation"): (0, 90, 180, 270),
    ("GradeInput", "reason"): (
        "button",
        "key_verified",
        "merge",
        "review_fix",
        "points_fix",
        "after_extract",  # data-model v1.33 (step 22.6.4)
    ),
    ("Run", "kind"): ("extract", "grade"),
    ("Run", "status"): ("queued", "running", "stopping", "stopped", "interrupted", "failed", "discarded", "done"),
    ("Step", "status"): ("running", "done", "incomplete", "failed", "skipped"),
    ("LlmCall", "role"): ("vision", "reasoning", "grading_check", "extraction_check", "ocr"),
    ("LlmCall", "status"): ("streaming", "complete", "invalid", "incomplete", "cancelled", "error"),
    ("ReviewItem", "kind"): ("uncertain_answer", "box_inline_conflict", "uncertain_key", "key_unmapped", "possible_duplicate", "picked_test_mismatch", "unknown_student", "unknown_occasion", "points_assumed", "validator_failed", "merge_unaligned", "unreadable_text"),
    ("ReviewItem", "owner"): ("extract", "grade"),
    ("ReviewItem", "status"): ("open", "accepted", "fixed", "skipped", "obsolete"),
    ("File", "kind"): ("upload", "derived", "text", "export"),
}
# fmt: on


def _literal_values(annotation: Any) -> tuple[Any, ...]:
    """The values of a Literal, or of the Literal inside ``Literal[...] | None``."""
    args = get_args(annotation)
    if args and all(not isinstance(a, type) and a is not None for a in args):
        return args
    for arg in args:
        values = get_args(arg)
        if values:
            return values
    raise AssertionError(f"no Literal in {annotation!r}")


@pytest.mark.parametrize("name", list(APPENDIX_A))
def test_r1_1_data_model_fields_equal_appendix_a(name: str) -> None:
    cls: type[BaseModel] = getattr(models, name)
    assert list(cls.model_fields) == APPENDIX_A[name]


def test_r1_1_no_extra_data_model_classes() -> None:
    assert sorted(c.__name__ for c in DATA_MODEL_CLASSES) == sorted(APPENDIX_A)


@pytest.mark.parametrize("name", list(WORKING_TYPES))
def test_r1_1_working_type_fields(name: str) -> None:
    cls: type[BaseModel] = getattr(working, name)
    assert list(cls.model_fields) == WORKING_TYPES[name]


@pytest.mark.parametrize(("cls_name", "field"), list(LITERAL_SETS))
def test_literal_sets_equal_data_model(cls_name: str, field: str) -> None:
    annotation = getattr(models, cls_name).model_fields[field].annotation
    assert _literal_values(annotation) == LITERAL_SETS[(cls_name, field)]


@pytest.mark.parametrize(
    "cls", [*DATA_MODEL_CLASSES, *(getattr(working, n) for n in WORKING_TYPES)]
)
def test_every_model_forbids_extra_fields(cls: type[BaseModel]) -> None:
    assert cls.model_config.get("extra") == "forbid"


def test_r1_3_display_name_exact() -> None:
    meta = models.TestMetadata(grade=8, occasion="FinalTerm", term=1, test_number="1", variant="K")
    assert meta.display_name() == "Grade 8 - Final Term 1 - Test 1"  # v1.11, decision C


def test_display_name_full_and_en_dash_year() -> None:
    meta = models.TestMetadata(
        grade=8,
        occasion="FinalTerm",
        term=1,
        test_number="1",
        variant="K",
        school="THCS Mẫu",
        year="2025-2026",
    )
    assert (
        meta.display_name()
        == "Grade 8 - Final Term 1 - THCS Mẫu - 2025" + chr(0x2013) + "2026 - Test 1"
    )


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"occasion": "MidTerm"}, "Mid-term"),
        ({"occasion": "MidTerm", "term": 2}, "Mid-term 2"),
        ({"occasion": "UnitTest", "grade": 6, "year": "2026"}, "Grade 6 - Unit Test - 2026"),
        ({"occasion": "Other:unknown", "school": "THCS Mẫu"}, "THCS Mẫu"),
        # R22.2.7.2 (the teacher's answers 4-5)
        ({"occasion": "UnitTest", "grade": 7, "year": "2025"}, "Grade 7 - Unit Test - 2025"),
        (
            {"occasion": "FifteenMinuteTest", "grade": 6, "year": "2025"},
            "Grade 6 - 15-minute Test - 2025",
        ),
        (
            {
                "occasion": "Other:unknown",
                "grade": 8,
                "term": 1,
                "year": "2025",
                "test_number": "3",
            },
            "Grade 8 - 2025 - Test 3",
        ),
        ({"occasion": "Other:unknown"}, "Untitled test"),
    ],
)
def test_display_name_leaves_out_missing_parts(fields: dict[str, Any], expected: str) -> None:
    assert models.TestMetadata(**fields).display_name() == expected


@pytest.mark.parametrize("occasion", ["FinalTerm", "Placement", "Other:unknown", "Other:Olympic"])
def test_occasion_accepts_listed_values_and_other(occasion: str) -> None:
    assert models.TestMetadata(occasion=occasion).occasion == occasion


@pytest.mark.parametrize("occasion", ["", "Final", "finalterm", "Other:", "Other: x"])
def test_occasion_rejects_unknown_values(occasion: str) -> None:
    with pytest.raises(ValidationError):
        models.TestMetadata(occasion=occasion)


def test_only_occasion_is_required_in_metadata() -> None:
    with pytest.raises(ValidationError):
        models.TestMetadata.model_validate({})
    meta = models.TestMetadata(occasion="MidTerm")
    assert meta.units == [] and meta.created_by_ai is False


def test_datetimes_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        models.Thread(
            id="th-1", title="t", test_id=None, kind="pending", created_at=datetime(2026, 9, 28)
        )


def test_run_input_resolves_to_the_right_type() -> None:
    base = {
        "id": "r",
        "thread_id": "th",
        "status": "queued",
        "started_at": None,
        "finished_at": None,
        "error": None,
    }
    grade = models.Run.model_validate(
        {
            **base,
            "kind": "grade",
            "input": {"test_id": "T-1", "attempt_id": None, "reason": "button"},
        }
    )
    assert isinstance(grade.input, models.GradeInput)
    extract = models.Run.model_validate(
        {
            **base,
            "kind": "extract",
            "input": {"pages": [], "existing_test_id": "T-1", "supersedes_attempt_id": None},
        }
    )
    assert isinstance(extract.input, models.ExtractInput)


def test_r22_2_4_5_display_name_teacher_pattern() -> None:
    a = models.TestMetadata(
        grade=8,
        occasion="FinalTerm",
        term=1,
        school="Nguyễn Hữu Thọ",
        year="2025",
        test_number="7",
        variant="A",
        test_code="132",
    )
    assert a.display_name() == "Grade 8 - Final Term 1 - Nguyễn Hữu Thọ - 2025 - Test 7"
    b = models.TestMetadata(
        grade=9, occasion="EntranceExam", source="TuoiHocTroLuyenThi", test_number="23"
    )
    assert b.display_name() == "Grade 9 - Entrance Exam - TuoiHocTroLuyenThi - Test 23"


def test_typed_name_is_kept_only_while_in_edited_fields() -> None:
    """R22.2.7.3: a typed Test name (v1.13) wins over the automatic one."""
    typed = models.TestMetadata(
        occasion="MidTerm",
        grade=7,
        extra={"display_name": "My name"},
        edited_fields=["display_name"],
    )
    assert typed.display_name() == "My name"
    assert typed.automatic_name() == "Grade 7 - Mid-term"
    stale = typed.model_copy(update={"edited_fields": []})
    assert stale.display_name() == "Grade 7 - Mid-term"
