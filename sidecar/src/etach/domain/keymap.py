"""Key photo → key rows by question_id (llm-design §4 ``map_key``, plan Appendix B.3, R8.1.7).

``key_raw`` is the ordered list of (label, answer) entries read from the key photo, optionally
with a confidence per entry. Rules (B.3):

- a label maps to the question with that printed number;
- labels of omitted sections (listening, writing: ``meta.omitted_sections``) are skipped silently;
- a **duplicate label** maps by position to the next question (canonical order) only if that
  question's own label is absent from the key; otherwise it is ``key_unmapped``;
- a label with no matching question is ``key_unmapped``.

Status (data-model §2.4, v1.25): confidence ≥ ``threshold`` → ``from_key_photo`` (read from the key
photo, no second call; never ``ai_verified``), below → ``ai_unverified`` (``verify_key`` checks it).
An entry given without a confidence counts 0.0 (every value flagged for the teacher, as the
``none`` confidence fallback).

Pure: no I/O.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from etach.domain.keys import true_false_key
from etach.domain.models import Question
from etach.domain.working import KeyEntry, PendingReview, TestDraft

__all__ = ["KEY_PHOTO_THRESHOLD", "KeyMapResult", "KeyRaw", "KeyStatus", "map_key"]

KeyStatus = Literal["from_key_photo", "ai_unverified"]

KEY_PHOTO_THRESHOLD = 0.7
"""Key-photo entry confidence below → ``ai_unverified`` (unchanged since step 9A)."""

_DIGITS = re.compile(r"\d+")


@dataclass(frozen=True)
class KeyRaw:
    """One key-photo entry with its confidence (from the step 6 confidence of its ``answer``)."""

    label: str
    answer: str
    confidence: float = 0.0


@dataclass
class KeyMapResult:
    entries: list[KeyEntry] = field(default_factory=list)
    status: dict[str, KeyStatus] = field(default_factory=dict)  # question_id → key status
    pendings: list[PendingReview] = field(default_factory=list)


def _entry(raw: Any) -> KeyRaw:
    if isinstance(raw, KeyRaw):
        return raw
    if isinstance(raw, tuple | list):
        if len(raw) == 2:
            return KeyRaw(str(raw[0]), str(raw[1]))
        return KeyRaw(str(raw[0]), str(raw[1]), float(raw[2]))
    # any object with label/answer (+ confidence), e.g. llm_schemas.KeyLabelAnswer
    return KeyRaw(str(raw.label), str(raw.answer), float(getattr(raw, "confidence", 0.0) or 0.0))


def _label_number(label: str) -> int | None:
    match = _DIGITS.search(label)
    return int(match.group()) if match else None


def map_key(
    key_raw: Sequence[Any],
    draft: TestDraft,
    *,
    threshold: float,
    ref: str = "",
) -> KeyMapResult:
    """Map ``key_raw`` onto ``draft``'s questions. ``ref`` (the run id) goes into each
    ``key_unmapped`` dedupe key: ``key_unmapped:<ref>:<entry index>``."""
    entries = [_entry(r) for r in key_raw]
    omitted = {n for o in draft.meta.omitted_sections for n in o.questions}
    questions: list[Question] = sorted(
        (q for s in draft.content.sections for g in s.groups for q in g.questions),
        key=lambda q: q.number,
    )
    by_printed: dict[int, int] = {}  # printed number → index in ``questions``
    for i, q in enumerate(questions):
        by_printed.setdefault(q.printed_number, i)
    labels_present = {n for e in entries if (n := _label_number(e.label)) is not None}

    result = KeyMapResult()
    mapped: set[int] = set()  # indices of questions already given a key row
    last_for_label: dict[int, int] = {}  # label → index of the question its last entry mapped to

    def unmapped(index: int, entry: KeyRaw, reason: str) -> None:
        result.pendings.append(
            PendingReview(
                kind="key_unmapped",
                dedupe_key=f"key_unmapped:{ref}:{index}",
                refs={},
                proposal={
                    "position": index,
                    "label": entry.label,
                    "answer": entry.answer,
                    "confidence": entry.confidence,
                    "reason": reason,
                },
            )
        )

    for index, entry in enumerate(entries):
        number = _label_number(entry.label)
        if number is not None and number in omitted:
            continue  # listening / writing: skipped silently
        target: int | None
        if number is None or number not in by_printed:
            unmapped(index, entry, "no_question")
            continue
        if number in last_for_label:  # a duplicate label: by position, to the next question
            nxt = last_for_label[number] + 1
            if (
                nxt < len(questions)
                and questions[nxt].printed_number not in labels_present
                and nxt not in mapped
            ):
                target = nxt
            else:
                unmapped(index, entry, "duplicate_label")
                continue
        else:
            target = by_printed[number]
            if target in mapped:
                unmapped(index, entry, "question_already_mapped")
                continue
        mapped.add(target)
        last_for_label[number] = target
        question = questions[target]
        result.entries.append(
            KeyEntry(
                question_id=question.id,
                accepted=[true_false_key(entry.answer.strip(), question)],
                confidence=entry.confidence,
            )
        )
        result.status[question.id] = (
            "from_key_photo" if entry.confidence >= threshold else "ai_unverified"
        )
    return result
