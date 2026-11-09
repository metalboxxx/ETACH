"""Working types: data-model §2.9. They live in graph state only and are never stored."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from etach.domain.models import TestContent, TestMetadata

__all__ = [
    "CompareResult",
    "KeyEntry",
    "PageAnswers",
    "PageHeader",
    "PageTranscript",
    "PendingReview",
    "PreparedPage",
    "SavedIds",
    "TestDraft",
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreparedPage(_Model):
    page_no: int
    file_id: str
    source_file_id: str
    rotation: int
    text_layer: str | None


class PageTranscript(_Model):
    page_no: int
    header_text: str | None
    sections: list[dict[str, Any]]
    llm_call_id: str


class TestDraft(_Model):
    meta: TestMetadata
    content: TestContent
    fingerprint: str
    points_possible: float


class PageHeader(_Model):
    header_text: str
    first_stems: list[str]


class KeyEntry(_Model):
    question_id: str
    accepted: list[str]
    confidence: float


class PageAnswers(_Model):
    page_no: int
    answers: list[dict[str, Any]]
    student_name: str | None
    class_name: str | None


class CompareResult(_Model):
    best_test_id: str | None
    similarity: float
    question_alignment: dict[str, str]  # new question_id -> bank question_id


class PendingReview(_Model):
    kind: str
    dedupe_key: str
    refs: dict[str, Any]
    proposal: dict[str, Any]


class SavedIds(_Model):
    test_id: str
    attempt_id: str | None
