"""Page readings → exactly one answer per graded question (llm-design §4 ``resolve_answers``,
§5.1, plan Appendix B.4, R8.1.8).

- One ``Answer`` per graded question; writing sections (``graded=False``) and ``writing``
  questions get no row (B.1b). No reading → value None.
- ``value_norm`` from ``normalize.value_norm``.
- The answer box wins: a box reading and an inline reading that disagree → the box value,
  ``alt_value`` = the inline value, and a pending ``box_inline_conflict``.
- A reading with ``alt_question_id`` (a span near two questions) → confidence capped at
  ``threshold - 0.01``, so it is always unsure. The model writes the ID as free text (bug B1:
  an enum of the other IDs made the per-call template grow with the square of the question
  count), so it is checked here (:func:`valid_alt_question_id`): a value that is not the ID of
  another readable question of the test (blank, a template word, the question's own ID, an
  unknown ID) is dropped (None) and caps nothing.
- Confidence below ``threshold`` → ``reading_unsure``. The confidence (and ``low_trust``) come
  from the step 6 per-field confidence of the reading's ``value`` leaf.
- **Form check** (found by the step 11 baseline; by answer form since step 22.5.3): a value that
  does not fit the question's answer form is dropped as a reading: a ``choice`` takes only one of
  its option labels (``A``-``D`` when it has none, ``T``/``F`` for True/False; case-insensitive,
  a trailing ``.`` or brackets ignored); a ``word`` or ``sentence`` drops a single bare capital
  ``A``-``D``/``T``/``F`` (a lowercase ``a`` may be the article).
  When every filled reading was dropped this way, the answer is None and ``reading_unsure``.
- **Disagreement:** when two accepted box readings, or two accepted inline readings, disagree
  after ``value_norm``, the most confident one is kept, its confidence is capped at
  ``threshold - 0.01`` (so it is unsure), and ``alt_value`` is the most confident other value
  (box vs inline keeps the box-wins rule above, and its ``alt_value``).
- **Unreadable** (PRD D25): a value containing ``???`` fits every question type, is kept as
  read, and its confidence is capped at ``threshold - 0.01`` (so ``reading_unsure``, ``?``).
- A failed page (§5.1): every graded question printed on it → value None, ``reading_unsure``,
  and one pending ``validator_failed`` for the page.
- No non-null value anywhere and no failed page → ``blank``. **Step 22.6.2 (step22.6-plan D5):**
  also blank when fewer than ``blank_share`` (default :data:`BLANK_SHARE`; ``[extract]
  blank_share``) of the answers have a value read with
  confidence (not ``reading_unsure``; an unreadable ``???`` counts, it shows writing): a paper
  with no student marks still gets made-up, mostly
  unsure readings (Test K: 2 of 40 sure). A blank paper keeps no answers and no Review items; the
  run saves the test alone, as for a paper with nothing read.
- A value spelled ``null``, ``none`` or ``n/a`` (:data:`NOT_READ_WORDS`) is not read (G8).
- **Student name and class** (:func:`pick_student`): a value that is a NuExtract template type
  word (``string``, ``verbatim-string``, ``integer`` …, :data:`NOT_READ_WORDS`) or fails the
  shape rules (a name: 2+ letters, no digits; a class: a letter and a digit, 2+ characters;
  the same rules as ``etach scrub``) counts as not read. A name ending in a class-shaped token
  (``… 8TC11``) is split: the name is the rest, and the token is the class when the page read
  no class or the same one. Across pages the most common valid value wins; on a tie, the
  lowest page.

The returned answers carry ``attempt_id=""``; ``save`` (step 9) sets the real id.

Pure: no I/O. The confidences are duck-typed (``.confidence``, ``.low_trust``), so this module
does not import ``etach.llm``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from etach.domain.keys import true_false_key
from etach.domain.llm_schemas import choice_labels
from etach.domain.models import Answer, Question
from etach.domain.normalize import value_norm
from etach.domain.validators import has_unreadable
from etach.domain.working import PageAnswers, PendingReview, TestDraft

__all__ = [
    "BLANK_SHARE",
    "BOX",
    "NOT_READ_WORDS",
    "ResolveResult",
    "answer_path",
    "clean_student",
    "fits_form",
    "graded_questions",
    "looks_like_class",
    "looks_like_name",
    "not_read_word",
    "pick_student",
    "resolve_answers",
    "valid_alt_question_id",
]

BOX = "answer_box"
_BARE_LETTERS = frozenset("ABCDTF")
CAP_BELOW_THRESHOLD = 0.01
#: a paper with fewer answers than this share read with confidence is blank (the teacher,
#: 2026-10-30: "Under 20%")
BLANK_SHARE = 0.2

#: Words a model writes when it read nothing: NuExtract template leaf types echoed back as the
#: value, and "none"/"null" spelled out. Compared case-insensitively.
NOT_READ_WORDS = frozenset(
    {
        "string", "verbatim-string", "integer", "number", "date-time", "date", "time",
        "boolean", "none", "null", "n/a",
    }
)  # fmt: skip


def not_read_word(value: str) -> bool:
    return value.strip().casefold() in NOT_READ_WORDS


def looks_like_name(value: str) -> bool:
    """At least 2 letters and no digits."""
    return sum(ch.isalpha() for ch in value) >= 2 and not any(ch.isdigit() for ch in value)


def looks_like_class(value: str) -> bool:
    """At least one letter and one digit, 2+ characters (``8A3``, ``7B4``, ``8TC11``)."""
    v = value.strip()
    return len(v) >= 2 and any(ch.isalpha() for ch in v) and any(ch.isdigit() for ch in v)


def clean_student(name: str | None, class_name: str | None) -> tuple[str | None, str | None]:
    """One page's (name, class) with unread values as ``None`` and a trailing class split off
    the name (module doc)."""
    cls = " ".join(class_name.split()) if class_name else None
    if cls is not None and (not_read_word(cls) or not looks_like_class(cls)):
        cls = None
    nm = " ".join(name.split()) if name else None
    if nm is not None and not_read_word(nm):
        nm = None
    if nm is not None:
        head, _, last = nm.rpartition(" ")
        if head and looks_like_class(last) and looks_like_name(head):
            if cls is None or cls.casefold() == last.casefold():
                cls = last
            nm = head
    if nm is not None and not looks_like_name(nm):
        nm = None
    return nm, cls


def _vote(values: Sequence[str | None]) -> str | None:
    """The most common value (``values`` in page order); a tie → the first seen."""
    found = [v for v in values if v is not None]
    if not found:
        return None
    counts = Counter(found)
    return max(dict.fromkeys(found), key=lambda v: counts[v])


def pick_student(pages: Sequence[PageAnswers]) -> tuple[str | None, str | None]:
    """The student's (name, class) by agreement across the pages (module doc)."""
    cleaned = [clean_student(p.student_name, p.class_name) for p in pages]
    return _vote([n for n, _ in cleaned]), _vote([c for _, c in cleaned])


@dataclass
class ResolveResult:
    answers: list[Answer] = field(default_factory=list)
    pendings: list[PendingReview] = field(default_factory=list)
    blank: bool = True
    student_name: str | None = None
    class_name: str | None = None


@dataclass(frozen=True)
class _Reading:
    page_no: int
    value: str | None
    location: str
    alt_question_id: str | None
    confidence: float
    low_trust: bool


def answer_path(question_id: str, index: int = 0) -> str:
    """The path of a reading's value in a ``read_answers_schema`` response (the same format as
    ``etach.llm.confidence.answer_path``)."""
    return f"answers.{question_id}[{index}].value"


def graded_questions(draft: TestDraft) -> list[Question]:
    """The questions that get an answer row, in canonical order."""
    out = [
        q
        for s in draft.content.sections
        if s.graded
        for g in s.groups
        for q in g.questions
        if q.answer_form != "writing"
    ]
    return sorted(out, key=lambda q: q.number)


def valid_alt_question_id(value: Any, question_id: str, known_ids: Iterable[str]) -> str | None:
    """``value`` (stripped) when it is the ID of another known question, else None."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v or v == question_id or v not in set(known_ids):
        return None
    return v


def _readable_ids(draft: TestDraft) -> frozenset[str]:
    """The IDs a ``read_answers_page`` call lists (every question but ``writing``)."""
    return frozenset(
        q.id
        for s in draft.content.sections
        for g in s.groups
        for q in g.questions
        if q.answer_form != "writing"
    )


def _readings(
    page_answers: Iterable[PageAnswers],
    confidences: Mapping[int, Mapping[str, Any]],
    failed: set[int],
    known_ids: frozenset[str],
) -> dict[str, list[_Reading]]:
    out: dict[str, list[_Reading]] = {}
    for page in page_answers:
        if page.page_no in failed:
            continue
        page_conf = confidences.get(page.page_no, {})
        seen: dict[str, int] = {}
        for raw in page.answers:
            qid = str(raw["question_id"])
            index = seen.get(qid, 0)
            seen[qid] = index + 1
            fc = page_conf.get(answer_path(qid, index))
            value = raw.get("value")
            out.setdefault(qid, []).append(
                _Reading(
                    page_no=page.page_no,
                    value=None if value is None or not_read_word(str(value)) else str(value),
                    location=str(raw.get("location") or "none"),
                    alt_question_id=valid_alt_question_id(
                        raw.get("alt_question_id"), qid, known_ids
                    ),
                    confidence=float(fc.confidence) if fc is not None else 0.0,
                    low_trust=bool(fc.low_trust) if fc is not None else True,
                )
            )
    return out


def _best(readings: Sequence[_Reading]) -> _Reading | None:
    return max(readings, key=lambda r: r.confidence) if readings else None


def fits_form(question: Question, value: str) -> bool:
    """Whether a filled reading's value can be an answer to this question's answer form."""
    v = value.strip()
    if has_unreadable(v):  # unreadable handwriting is kept as read, whatever the form (D25)
        return True
    if question.answer_form == "choice":
        return v.strip(".()").strip().upper() in choice_labels(question)
    return v.strip(".()").strip() not in _BARE_LETTERS


def _disagree(readings: Sequence[_Reading]) -> bool:
    return len({value_norm(r.value or "") for r in readings}) > 1


def _runner_up(readings: Sequence[_Reading], chosen: _Reading) -> str | None:
    norm = value_norm(chosen.value or "")
    other = _best([r for r in readings if value_norm(r.value or "") != norm])
    return None if other is None else other.value


def resolve_answers(
    page_answers: Sequence[PageAnswers],
    confidences: Mapping[int, Mapping[str, Any]],
    draft: TestDraft,
    *,
    threshold: float,
    failed_pages: Iterable[int] = (),
    ref: str = "",
    blank_share: float = BLANK_SHARE,
) -> ResolveResult:
    """Resolve the ``read_answers_page`` readings into answers.

    ``confidences`` maps a page number to that call's per-field confidences (path → an object
    with ``confidence`` and ``low_trust``, e.g. ``FieldConfidence``). A reading without one counts
    confidence 0.0, ``low_trust=True``. ``ref`` (the run id) goes into the dedupe keys:
    ``box_inline_conflict:<ref>:<question_id>`` and ``validator_failed:<ref>:answers:<page_no>``.
    """
    failed = set(failed_pages)
    pages = sorted(page_answers, key=lambda p: p.page_no)
    by_question = _readings(pages, confidences, failed, _readable_ids(draft))
    result = ResolveResult()
    result.student_name, result.class_name = pick_student(pages)

    for page_no in sorted(failed):
        result.pendings.append(
            PendingReview(
                kind="validator_failed",
                dedupe_key=f"validator_failed:{ref}:answers:{page_no}",
                refs={"page_no": page_no},
                proposal={"task": "read_answers_page", "page_no": page_no},
            )
        )

    for q in graded_questions(draft):
        if q.page_no in failed:
            result.answers.append(_answer(q, None, q.page_no, "none", 0.0, False, True))
            continue
        # a student's printed letter on a relabelled True/False choice (B on "A. FALSE / B. TRUE")
        # is read as its T/F (step 22.5.8 (a)(5))
        readings = [
            r if not r.value else replace(r, value=true_false_key(r.value, q))
            for r in by_question.get(q.id, [])
        ]
        filled_all = [r for r in readings if r.value is not None and r.value.strip()]
        filled = [r for r in filled_all if fits_form(q, r.value or "")]
        if filled_all and not filled:  # every value was the wrong kind for this question
            result.answers.append(_answer(q, None, q.page_no, "none", 0.0, False, True))
            continue
        boxes_ = [r for r in filled if r.location == BOX]
        inlines = [r for r in filled if r.location != BOX]
        box = _best(boxes_)
        inline = _best(inlines)
        chosen = box or inline
        alt_value: str | None = None
        split = _disagree(boxes_) if box else _disagree(inlines)
        if box and inline and value_norm(box.value or "") != value_norm(inline.value or ""):
            alt_value = inline.value
            result.pendings.append(
                PendingReview(
                    kind="box_inline_conflict",
                    dedupe_key=f"box_inline_conflict:{ref}:{q.id}",
                    refs={"question_id": q.id},
                    proposal={"box_value": box.value, "inline_value": inline.value},
                )
            )
        if chosen is None:  # blank or not read: the most confident empty reading, if any
            empty = _best(readings)
            if empty is None:
                result.answers.append(_answer(q, None, q.page_no, "none", 0.0, False, True))
                continue
            chosen = empty
        confidence = chosen.confidence
        alt_qid = chosen.alt_question_id
        if alt_qid or split or has_unreadable(chosen.value):
            confidence = min(confidence, threshold - CAP_BELOW_THRESHOLD)
        if split and alt_value is None:
            alt_value = _runner_up(boxes_ if box else inlines, chosen)
        answer = _answer(
            q,
            chosen.value if chosen.value is not None and chosen.value.strip() else None,
            chosen.page_no,
            chosen.location,
            confidence,
            chosen.low_trust,
            confidence < threshold,
        )
        result.answers.append(
            answer.model_copy(update={"alt_value": alt_value, "alt_question_id": alt_qid})
        )

    # a failed page is unread, not blank: the attempt must still be saved (every answer "?")
    # unreadable handwriting (``???``, D25) is always unsure but shows the student wrote
    sure = sum(
        1
        for a in result.answers
        if a.value is not None and (not a.reading_unsure or has_unreadable(a.value))
    )
    result.blank = not failed and (
        all(a.value is None for a in result.answers) or sure < blank_share * len(result.answers)
    )
    if result.blank:
        result.pendings = []  # no answers are kept, so nothing about them to review
    return result


def _answer(
    q: Question,
    value: str | None,
    page_no: int | None,
    location: str,
    confidence: float,
    low_trust: bool,
    unsure: bool,
) -> Answer:
    return Answer(
        attempt_id="",
        question_id=q.id,
        printed_number=q.printed_number,
        page_no=page_no,
        value=value,
        value_norm=None if value is None else value_norm(value),
        location=location,  # type: ignore[arg-type]
        confidence=max(0.0, min(1.0, confidence)),
        low_trust=low_trust,
        reading_unsure=unsure,
        alt_value=None,
        alt_question_id=None,
        points_awarded=None,
        teacher_override=None,
    )
