"""Bank duplicate detection (PRD §8, llm-design §4 ``compare_bank``, plan R8.1.6).

- ``normalize_for_similarity``: ``fold`` + lowercase, numbering and punctuation removed,
  whitespace collapsed.
- ``shingles`` (5-character shingles) and ``jaccard`` (exact).
- ``compare``: the new draft against the bank candidates. Candidates of another known grade
  never count (unknown grades on either side stay eligible); merged tests are never candidates.
  Two tiers:
  ≥ ``looks_like`` → ``"looks_like"``, ≥ ``possibly`` → ``"possibly"``, below → none. A tiered
  match yields one pending ``possible_duplicate`` whose proposal carries the question alignment.
- ``align_questions``: new question_id → bank question_id, by the similarity of each question's
  normalized stem + options + cue, greedy highest-first above a minimum. Printed numbers are never
  used; ties break by canonical number. Unpaired questions are left out.
- ``align_reading`` (Extract again, D8): the same number and text first, then ``align_questions``.

Pure: no I/O.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from etach.domain.models import Question, TestContent
from etach.domain.normalize import collapse_spaces, fold
from etach.domain.working import CompareResult, PendingReview, TestDraft

__all__ = [
    "LOOKS_LIKE",
    "MIN_QUESTION_SIMILARITY",
    "POSSIBLY",
    "Candidate",
    "CompareOutcome",
    "Tier",
    "align_questions",
    "align_reading",
    "compare",
    "eligible",
    "jaccard",
    "normalize_for_similarity",
    "question_text",
    "shingles",
    "similarity",
    "tier_for",
]

LOOKS_LIKE = 0.85
POSSIBLY = 0.5
MIN_QUESTION_SIMILARITY = 0.6
QUESTION_SHINGLE = 3  # question texts are short (a pronunciation item is four words)

Tier = Literal["looks_like", "possibly"]

_MARKUP = re.compile(r"\*\*|</?u>")
# "Question 5", "Câu 5", "Bài 2" (after folding) and "Part II"-style labels
_LABELLED = re.compile(r"\b(?:question|cau|bai|part|section|exercise)\s+(?:\d+|[ivxlc]+)\b")
_NUMBERED = re.compile(r"(?:^|(?<=\s))(?:\d+|[ivxlc]+|[a-d])\s*[.):]")  # "5.", "II.", "(A)", "b)"
_BLANK_NO = re.compile(r"\(\s*\d+\s*\)")  # "(23) ______" in a cloze passage
_NON_WORD = re.compile(r"[^\w\s]|_")


def normalize_for_similarity(text: str) -> str:
    """Accent-folded, lowercase text with numbering and punctuation removed, spaces collapsed."""
    s = fold(_MARKUP.sub("", text)).lower()
    s = _LABELLED.sub(" ", s)
    s = _BLANK_NO.sub(" ", s)
    s = _NUMBERED.sub(" ", s)
    s = _NON_WORD.sub(" ", s)
    return collapse_spaces(s)


def shingles(text: str, k: int = 5) -> set[str]:
    """The set of ``k``-character shingles of ``text`` (already normalized). A text shorter than
    ``k`` is one shingle; an empty text has none."""
    if not text:
        return set()
    if len(text) <= k:
        return {text}
    return {text[i : i + k] for i in range(len(text) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    """Exact Jaccard similarity; 0.0 when either set is empty."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def similarity(a: str, b: str, k: int = 5) -> float:
    """Jaccard similarity of two raw texts after ``normalize_for_similarity``."""
    return jaccard(
        shingles(normalize_for_similarity(a), k), shingles(normalize_for_similarity(b), k)
    )


def tier_for(
    value: float, *, looks_like: float = LOOKS_LIKE, possibly: float = POSSIBLY
) -> Tier | None:
    if value >= looks_like:
        return "looks_like"
    if value >= possibly:
        return "possibly"
    return None


@dataclass(frozen=True)
class Candidate:
    """A bank test as plain data (step 9 reads it from the store)."""

    test_id: str
    grade: int | None
    merged_into: str | None
    content: TestContent
    fingerprint: str


@dataclass(frozen=True)
class CompareOutcome:
    result: CompareResult
    tier: Tier | None
    pending: PendingReview | None  # one possible_duplicate when tier is set


def _questions(content: TestContent) -> list[Question]:
    """Graded and ungraded questions alike, in canonical order."""
    out = [q for s in content.sections for g in s.groups for q in g.questions]
    return sorted(out, key=lambda q: q.number)


def question_text(q: Question) -> str:
    """The normalized text a question is aligned on: stem + options + cue (no numbers)."""
    parts = [q.stem or "", *(o.text for o in q.options or []), q.cue or ""]
    return normalize_for_similarity(" ".join(p for p in parts if p))


def align_questions(
    new: TestContent, bank: TestContent, *, minimum: float = MIN_QUESTION_SIMILARITY
) -> dict[str, str]:
    """new question_id → bank question_id (greedy, highest similarity first, one-to-one)."""
    new_qs = [(q, shingles(question_text(q), QUESTION_SHINGLE)) for q in _questions(new)]
    bank_qs = [(q, shingles(question_text(q), QUESTION_SHINGLE)) for q in _questions(bank)]
    pairs: list[tuple[float, int, int, str, str]] = []
    for nq, ns in new_qs:
        if not ns:
            continue
        for bq, bs in bank_qs:
            value = jaccard(ns, bs)
            if value >= minimum:
                pairs.append((value, nq.number, bq.number, nq.id, bq.id))
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
    used_new: set[str] = set()
    used_bank: set[str] = set()
    out: dict[str, str] = {}
    for _value, _n, _b, new_id, bank_id in pairs:
        if new_id in used_new or bank_id in used_bank:
            continue
        used_new.add(new_id)
        used_bank.add(bank_id)
        out[new_id] = bank_id
    order = {q.id: q.number for q, _ in new_qs}
    return dict(sorted(out.items(), key=lambda kv: order[kv[0]]))


def _only(content: TestContent, ids: set[str]) -> TestContent:
    """``content`` with only the questions in ``ids``."""
    return TestContent(
        sections=[
            s.model_copy(
                update={
                    "groups": [
                        g.model_copy(update={"questions": [q for q in g.questions if q.id in ids]})
                        for g in s.groups
                    ]
                }
            )
            for s in content.sections
        ]
    )


def align_reading(
    new: TestContent, old: TestContent, *, minimum: float = MIN_QUESTION_SIMILARITY
) -> tuple[dict[str, str], set[str]]:
    """Extract again into the same test (D8, data-model v1.21): new question_id → old question_id,
    and the new ids whose old question has the same printed number and the same text.

    Such exact pairs come first, in canonical order (so questions with no text to compare, a
    cloze blank in a passage, still pair by their number); the questions left pair by
    :func:`align_questions`. "The same text" is :func:`question_text`: markup, punctuation and
    numbering do not count."""
    by_key: dict[tuple[int, str], list[str]] = {}
    for q in _questions(old):
        by_key.setdefault((q.printed_number, question_text(q)), []).append(q.id)
    pairs: dict[str, str] = {}
    for q in _questions(new):
        ids = by_key.get((q.printed_number, question_text(q)))
        if ids:
            pairs[q.id] = ids.pop(0)
    exact = set(pairs)
    new_left = {q.id for q in _questions(new)} - set(pairs)
    old_left = {q.id for q in _questions(old)} - set(pairs.values())
    rest = align_questions(_only(new, new_left), _only(old, old_left), minimum=minimum)
    return pairs | rest, exact


def eligible(candidates: Iterable[Candidate], grade: int | None) -> list[Candidate]:
    """Merged tests never count; with a known grade, candidates of another known grade do not
    count either. A candidate whose grade is unknown stays eligible (unknown is not different)."""
    return [
        c
        for c in candidates
        if c.merged_into is None and (grade is None or c.grade is None or c.grade == grade)
    ]


def compare(
    new_draft: TestDraft,
    candidates: Sequence[Candidate],
    *,
    looks_like: float = LOOKS_LIKE,
    possibly: float = POSSIBLY,
    min_question_similarity: float = MIN_QUESTION_SIMILARITY,
    ref: str = "",
) -> CompareOutcome:
    """Compare ``new_draft`` with the bank (PRD §8). ``ref`` (the run id) goes into the pending
    item's dedupe key: ``possible_duplicate:<ref>:<best_test_id>``."""
    new_shingles = shingles(normalize_for_similarity(new_draft.fingerprint))
    best: Candidate | None = None
    best_value = 0.0
    for cand in eligible(candidates, new_draft.meta.grade):
        value = jaccard(new_shingles, shingles(normalize_for_similarity(cand.fingerprint)))
        if best is None or value > best_value:  # ties keep the first candidate given
            best, best_value = cand, value
    if best is None:
        return CompareOutcome(
            CompareResult(best_test_id=None, similarity=0.0, question_alignment={}), None, None
        )
    tier = tier_for(best_value, looks_like=looks_like, possibly=possibly)
    alignment = (
        align_questions(new_draft.content, best.content, minimum=min_question_similarity)
        if tier
        else {}
    )
    result = CompareResult(
        best_test_id=best.test_id, similarity=best_value, question_alignment=alignment
    )
    pending = None
    if tier:
        pending = PendingReview(
            kind="possible_duplicate",
            dedupe_key=f"possible_duplicate:{ref}:{best.test_id}",
            refs={"test_id": best.test_id},
            proposal={
                "best_test_id": best.test_id,
                "similarity": best_value,
                "tier": tier,
                "question_alignment": alignment,
            },
        )
    return CompareOutcome(result, tier, pending)
