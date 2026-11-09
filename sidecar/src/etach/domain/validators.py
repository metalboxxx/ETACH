"""Validators for a merged test (llm-design §4 ``merge_and_normalize``).

Each validator returns failures that carry the page number. Step 9 puts the failing pages in
``state.retranscribe`` (``failing_pages``) and turns a page that fails twice into a pending
``validator_failed``. Pure: no I/O.

Unreadable text (PRD D25): ``???`` stands for words the model could not read. It is valid text,
not a failure: a ``word`` question whose text has ``???`` passes (the blank may be what is
unreadable), and a choice option label ``???`` stands for the label printed at its position.

By answer form (step 22.5.3): the blank check applies to a ``word`` question with no cue and no
options (what a ``gap_fill`` was); a ``word`` question with a cue (a former ``word_form`` or
``verb_form``) or with printed options is not blank-checked, as those types were not. The option
check applies to ``choice`` questions. The validator names (``gap_fill_blank``, ``mcq_options``)
are kept as they were, because stored review items carry them.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from etach.domain.models import (
    TRUE_FALSE_OPTIONS,
    OmittedSection,
    Question,
    QuestionGroup,
    TestContent,
)
from etach.domain.points import clean_label

__all__ = [
    "BLANK",
    "UNREADABLE",
    "ValidatorFailure",
    "failing_pages",
    "has_unreadable",
    "missing_numbers",
    "validate_choice",
    "validate_content",
    "validate_numbering",
    "validate_word_blank",
]

BLANK = "____"
UNREADABLE = "???"
_LABELS = "ABCD"
_TRUE_FALSE_LABELS = [label for label, _ in TRUE_FALSE_OPTIONS]


def has_unreadable(text: str | None) -> bool:
    """Whether a text holds an unreadable span ``???`` (PRD D25)."""
    return text is not None and UNREADABLE in text


@dataclass(frozen=True)
class ValidatorFailure:
    validator: str  # "gap_fill_blank" | "mcq_options" | "numbering"
    page_no: int
    question_id: str | None
    printed_number: int | None
    message: str


def validate_word_blank(question: Question, group: QuestionGroup) -> list[ValidatorFailure]:
    """A ``word`` question with no cue and no options has ``____`` in its stem (or, with no stem,
    in the stimulus). A cue or options mean the student writes the word without a printed blank."""
    if question.answer_form != "word" or question.cue or question.options:
        return []
    text = question.stem if question.stem is not None else (group.stimulus or "")
    if BLANK in text or has_unreadable(text) or has_unreadable(question.stem):
        return []
    return [
        ValidatorFailure(
            "gap_fill_blank",
            question.page_no,
            question.id,
            question.printed_number,
            f"word question {question.printed_number} has no {BLANK}",
        )
    ]


def validate_choice(question: Question) -> list[ValidatorFailure]:
    """A ``choice`` has 2 to 4 options labelled A, B, (C, (D)) in order, or the True/False pair
    (``T``, ``F``) the code adds."""
    if question.answer_form != "choice":
        return []
    labels = [clean_label(o.label) for o in question.options or []]
    if labels == _TRUE_FALSE_LABELS:
        return []
    if 2 <= len(labels) <= 4 and all(
        label == _LABELS[i] or has_unreadable(label) for i, label in enumerate(labels)
    ):
        return []
    return [
        ValidatorFailure(
            "mcq_options",
            question.page_no,
            question.id,
            question.printed_number,
            f"choice question {question.printed_number} has options {labels!r}",
        )
    ]


def validate_numbering(
    questions: Sequence[Question], omitted: Iterable[OmittedSection]
) -> list[ValidatorFailure]:
    """Printed numbers run 1, 2, 3, … in order; a gap is allowed only over omitted numbers."""
    allowed = {n for o in omitted for n in o.questions}
    failures: list[ValidatorFailure] = []
    prev = 0
    for q in questions:
        n = q.printed_number
        gap = set(range(prev + 1, n))
        if n <= prev or not gap <= allowed:
            failures.append(
                ValidatorFailure(
                    "numbering",
                    q.page_no,
                    q.id,
                    n,
                    f"printed number {n} follows {prev}",
                )
            )
        prev = max(prev, n)
    return failures


def validate_content(
    content: TestContent, omitted: Iterable[OmittedSection]
) -> list[ValidatorFailure]:
    """Run every validator over the draft content, in document order."""
    failures: list[ValidatorFailure] = []
    ordered: list[Question] = []
    for section in content.sections:
        for group in section.groups:
            for q in group.questions:
                failures += validate_word_blank(q, group)
                failures += validate_choice(q)
                ordered.append(q)
    return failures + validate_numbering(ordered, list(omitted))


def failing_pages(failures: Iterable[ValidatorFailure]) -> list[int]:
    """The sorted, distinct page numbers with at least one failure."""
    return sorted({f.page_no for f in failures})


def missing_numbers(
    content: TestContent, omitted: Iterable[OmittedSection], question_id: str
) -> list[int]:
    """The printed numbers missing just before question ``question_id`` (its ``numbering``
    failure; step 22.5.7, what the targeted re-read asks for): the gap after the highest number
    before it, without the omitted numbers and the numbers read elsewhere in the test."""
    allowed = {n for o in omitted for n in o.questions}
    ordered = [q for s in content.sections for g in s.groups for q in g.questions]
    seen = {q.printed_number for q in ordered}
    prev = 0
    for q in ordered:
        if q.id == question_id:
            gap = range(prev + 1, q.printed_number)
            return [n for n in gap if n not in allowed and n not in seen]
        prev = max(prev, q.printed_number)
    return []
