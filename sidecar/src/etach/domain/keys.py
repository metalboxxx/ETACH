"""Key gates of the grade graph (llm-design §5 ``key_needed?``, ``verify_gate``; plan B.7, B.8).

- ``key_needed``: the graded questions with no key row (→ ``ai_key_fast``; empty → skip it).
- ``verify_needed``: true exactly when the key is ``ai_unverified`` and (its margin is below the
  threshold, or the question is a pronunciation/stress item, or an attempt is present and the
  student gave a non-blank answer ≠ the key). False for every other status.
- ``verify_failed`` / ``key_failed_reviews``: the §5.1 failure rules for ``verify_key`` and
  ``ai_key_fast`` (the key → ``ai_uncertain``; one ``uncertain_key`` per question).

Pure: no I/O.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import datetime

from etach.domain.llm_schemas import VerifyKeyOut
from etach.domain.models import (
    Answer,
    AnswerKey,
    KeyCheck,
    Question,
    TestContent,
    true_false_letters,
)
from etach.domain.normalize import collapse_spaces, value_norm
from etach.domain.scoring import effective_value
from etach.domain.working import PendingReview

__all__ = [
    "SENTENCE_FORMS",
    "VERIFY_SKILLS",
    "find_question",
    "given_words",
    "key_failed_reviews",
    "key_needed",
    "key_with_forms",
    "questions_to_verify",
    "sentence_forms",
    "teacher_accepted",
    "true_false_key",
    "uncertain_key_review",
    "verify_failed",
    "verify_needed",
    "with_forms",
]

VERIFY_SKILLS = frozenset({"pronunciation", "stress"})


def key_needed(content: TestContent, keys: Iterable[AnswerKey]) -> list[str]:
    """The graded questions (in order) with no key row; empty = skip ``ai_key_fast``."""
    have = {k.question_id for k in keys}
    return [
        q.id
        for s in content.sections
        if s.graded
        for g in s.groups
        for q in g.questions
        if q.id not in have
    ]


def verify_needed(
    key: AnswerKey,
    *,
    section_skill: str,
    margin_threshold: float,
    attempt_present: bool,
    answer: Answer | None = None,
) -> bool:
    """Plan Appendix B.7. The margin is ``key.confidence`` (``None`` = no logprob → low).

    With an attempt, ``answer`` is the student's row for this question (the teacher's override
    applies); only a non-blank answer ≠ the key triggers it. A blank or missing answer (or an
    override of ``""``) does not (plan v2.7)."""
    if key.status != "ai_unverified":
        return False
    if key.confidence is None or key.confidence < margin_threshold:
        return True
    if section_skill in VERIFY_SKILLS:
        return True
    if attempt_present and answer is not None:
        raw = effective_value(answer)
        norm = value_norm(raw) if raw is not None else ""
        if norm:  # a blank answer says nothing about the key (plan v2.7)
            return norm not in {value_norm(a) for a in key.accepted}
    return False


def questions_to_verify(
    content: TestContent,
    keys: Iterable[AnswerKey],
    *,
    margin_threshold: float,
    answers: Iterable[Answer] | None = None,
) -> list[str]:
    """``verify_gate``: the question IDs (in order) whose key needs ``verify_key``.
    ``answers`` is ``None`` for a blank test (no attempt)."""
    key_by_q = {k.question_id: k for k in keys}
    ans_by_q: Mapping[str, Answer] = {a.question_id: a for a in answers or []}
    out: list[str] = []
    for s in content.sections:
        if not s.graded:
            continue
        for g in s.groups:
            for q in g.questions:
                key = key_by_q.get(q.id)
                if key is not None and verify_needed(
                    key,
                    section_skill=s.skill,
                    margin_threshold=margin_threshold,
                    attempt_present=answers is not None,
                    answer=ans_by_q.get(q.id),
                ):
                    out.append(q.id)
    return out


def uncertain_key_review(ref: str, question_id: str, accepted: list[str]) -> PendingReview:
    """One ``uncertain_key`` Review item (``ref`` = the run id, as in the extract dedupe keys)."""
    return PendingReview(
        kind="uncertain_key",
        dedupe_key=f"uncertain_key:{ref}:{question_id}",
        refs={"question_id": question_id},
        proposal={"accepted": list(accepted)},
    )


def checker_unsure(answer: str) -> bool:
    """``verify_key`` answered ``?``: it is not sure (step 22.6.3, D6; whitespace ignored)."""
    return "".join(answer.split()) == "?"


def verify_failed(
    key: AnswerKey, ref: str, now: datetime, checked: VerifyKeyOut | None = None
) -> tuple[AnswerKey, PendingReview]:
    """``verify_key`` disagreed, was unsure, was truncated or failed twice → ``ai_uncertain`` +
    review.

    ``checked`` is the checker's output when it disagreed (its answer and reasoning are kept on
    the key, step 22.5.5) or answered ``?`` (``unsure``, its reasoning only, step 22.6.3);
    ``None`` = the check did not finish."""
    if checked is None:
        checker = KeyCheck(status="did_not_finish")
    elif checker_unsure(checked.answer):
        checker = KeyCheck(status="unsure", reasoning=checked.reasoning)
    else:
        checker = KeyCheck(status="disagreed", answer=checked.answer, reasoning=checked.reasoning)
    new = key.model_copy(update={"status": "ai_uncertain", "updated_at": now, "checker": checker})
    return new, uncertain_key_review(ref, key.question_id, key.accepted)


def key_failed_reviews(ref: str, question_ids: Iterable[str]) -> list[PendingReview]:
    """``ai_key_fast`` failed twice for a section → no key rows; one ``uncertain_key`` per
    question (they grade ``uncertain`` by B.5 row 11)."""
    return [uncertain_key_review(ref, qid, []) for qid in question_ids]


# --- sentence keys (data-model §2.4 v1.15, plan step 22.3.4) ---------------------------------

#: The answer forms whose key gets the sentence forms (step 22.5.3: every ``sentence`` question).
SENTENCE_FORMS = frozenset({"sentence"})

# An arrow before the answer line: "He came here two years ago. -> He has ____".
_ARROW = re.compile(r"(?:->|=>|→|⇒|➝|➞)")
# The answer line's blank after the given words: "____", "......", "…", spaces.
_TRAIL = re.compile(r"[\s_.…]+$")
_WORD = re.compile(r"\S+")


def _clean_given(text: str) -> str:
    text = _ARROW.sub(" ", text)
    return collapse_spaces(_TRAIL.sub("", text))


def given_words(question: Question) -> list[str]:
    """The words the paper already prints at the start of the answer line, as candidates: the
    question's ``answer_start`` first (data-model v1.16, D6), then the text after the last arrow
    in the stem or cue, any later line of the stem, and the cue itself.
    Which one (if any) applies is decided against the key (:func:`sentence_forms`)."""
    out: list[str] = []
    if question.answer_start:
        out.append(_clean_given(question.answer_start))
    for text in (question.stem, question.cue):
        if not text:
            continue
        parts = _ARROW.split(text)
        if len(parts) > 1:
            out.append(_clean_given(parts[-1]))
    if question.stem:
        out.extend(_clean_given(line) for line in question.stem.splitlines()[1:])
    if question.cue:
        out.append(_clean_given(question.cue))
    return [g for g in dict.fromkeys(out) if g]


def _drop_given(key: str, given: str) -> str | None:
    """``key`` without its opening ``given`` words (compared as ``value_norm``, word by word),
    or None when the key does not start with them or nothing would be left."""
    words = value_norm(given).split(" ")
    spans = list(_WORD.finditer(key))
    if len(spans) <= len(words):
        return None
    if [value_norm(m.group()) for m in spans[: len(words)]] != words:
        return None
    return key[spans[len(words) - 1].end() :].strip()


def _no_stop(text: str) -> str:
    stripped = text.rstrip()
    return (
        stripped[:-1].rstrip()
        if stripped.endswith(".") and not stripped.endswith("..")
        else stripped
    )


def sentence_forms(key: str, given: Iterable[str] | str | None = None) -> list[str]:
    """The accepted forms of a sentence key (teacher's comment 10), canonical first: the full
    sentence; without its final full stop; without the opening words the paper gives; without
    both. The longest given candidate the key starts with is used. Unique; nothing else changes
    (case, other punctuation, letters). Pure and idempotent."""
    full = key.strip()
    if isinstance(given, str):
        given = [given]
    rest: str | None = None
    for g in sorted((_clean_given(s) for s in given or []), key=len, reverse=True):
        if g.strip():
            rest = _drop_given(full, g)
            if rest:
                break
    forms = [full, _no_stop(full)]
    if rest:
        forms += [rest, _no_stop(rest)]
    return [f for f in dict.fromkeys(forms) if f]


def with_forms(accepted: list[str], question: Question | None) -> list[str]:
    """``accepted`` with the sentence forms of its canonical answer added after it (for a
    ``sentence`` question; anything else is returned unchanged). Idempotent."""
    if question is None or question.answer_form not in SENTENCE_FORMS or not accepted:
        return list(accepted)
    forms = sentence_forms(accepted[0], given_words(question))
    return list(dict.fromkeys([*forms, *accepted[1:]]))


def find_question(content: TestContent, question_id: str) -> Question | None:
    return next(
        (q for s in content.sections for g in s.groups for q in g.questions if q.id == question_id),
        None,
    )


def key_with_forms(key: AnswerKey, content: TestContent) -> AnswerKey:
    """The key with :func:`with_forms` applied to its ``accepted`` (its question looked up)."""
    accepted = with_forms(key.accepted, find_question(content, key.question_id))
    return key if accepted == key.accepted else key.model_copy(update={"accepted": accepted})


def teacher_accepted(
    old: AnswerKey | None, accepted: list[str], question: Question | None
) -> list[str]:
    """A teacher's key write. While the key text (the canonical answer) is unchanged, the list is
    stored as sent, so a form the teacher removed stays removed; a new or changed key text gets
    its forms again (:func:`with_forms`)."""
    if old is not None and old.accepted and accepted and old.accepted[0] == accepted[0]:
        return list(dict.fromkeys(accepted))
    return with_forms(accepted, question)


def true_false_key(answer: str, question: Question | None) -> str:
    """A key-photo or student letter for a True/False choice relabelled by the first-start pass
    or at extraction (options ``T`` / ``F``, the ones before in ``old_options``): mapped through the
    same relabel map
    (:func:`etach.domain.models.true_false_letters`; e.g. on ``A. FALSE`` / ``B. TRUE``, ``B`` →
    ``T``). Any other answer or question is returned unchanged (step 22.5.8 (a)(3), (a)(5))."""
    if question is None or not question.old_options or not question.options:
        return answer
    if [o.label for o in question.options] != ["T", "F"]:
        return answer
    letters = true_false_letters([(o.label, o.text) for o in question.old_options])
    if letters is None:
        return answer
    by_label = {label.strip().upper(): tf for label, tf in letters.items()}
    return by_label.get(answer.strip().rstrip(".)").strip().upper(), answer)
