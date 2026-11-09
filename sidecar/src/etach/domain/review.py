"""Review resolution (data-model §5.3, plan Appendix E, R10.1-R10.2).

:func:`resolve` applies the teacher's decision on one ``open`` item, in ONE transaction:

- it writes the per-kind database changes of Appendix E;
- it queues the follow-up runs (grade runs only for *graded* attempts: ``score_earned`` set and
  not superseded, data-model §5.3); they stay ``queued`` until the grade graph exists;
- it records ``resolution = {action, value}``, ``resolved_at``, the status (``accepted`` /
  ``fixed`` / ``skipped``) and ``followup_run_id`` (the first queued run).

Skip changes nothing but the item itself (R10.2). A non-open item raises :class:`ReviewNotOpen`;
an action the kind does not have, or a bad value, raises :class:`InvalidResolution`. Both leave
the database unchanged.

Fix values per kind:

- ``uncertain_answer`` / ``box_inline_conflict``: the typed answer (``str``); ``""`` = the
  teacher confirmed no answer (data-model v1.5.2).
- ``uncertain_key``: the key: a ``str`` or a list of accepted variants.
- ``key_unmapped``: the ``question_id`` of the test to attach the entry to.
- ``merge_unaligned``: a free ``question_id`` of the survivor.
- ``unknown_student``: an existing student ID (``S-…``) or a new full name (``str``), or
  ``{"student_id": …}`` / ``{"full_name": …, "class_name": …}``.
- ``unknown_occasion``: the occasion (``str``, validated by ``TestMetadata``).
- ``points_assumed``: ``{"points_per_question": x}`` or ``{"section_total": y}``.
- ``validator_failed``: ``{"content": <TestContent>, "keys": {question_id: [accepted…]}}``
  (``keys`` optional), or the ``TestContent`` JSON itself.
- ``unreadable_text``: ``{"spans": [{"path": …, "text": …}]}``, the new full text of each listed
  field (data-model §2.8); a path must be one of the item's ``proposal.spans``.

Test-text save (data-model §2.3a, §5.3 v1.9, PRD D27): :func:`save_test_text` reads the test
page's text back (``domain/test_text.py``), checks it, saves it and settles the test's open items
in ONE transaction: an ``unreadable_text`` item with no ``???`` left on its page → ``fixed`` (else
its spans are updated); test-level ``validator_failed`` → ``fixed`` once the content validates;
``points_assumed`` → ``obsolete`` (the points are the equal ones; ``save_content`` re-scores the
graded attempts, so a points change queues no run); items of dropped questions → ``obsolete``.
Dropping a question that has a key row or answers needs the teacher's confirmation; its key,
answers, tags and explanations are then deleted and every graded attempt gets one grade run
(``review_fix``). An attempt whose first grade run is not finished gets none: that run's
``save`` finds the test changed and grades against the saved test (R22.6.6.3).

This module is one of the two ``domain/`` services allowed to call ``store/`` (structure rule 5).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import ValidationError

from etach.domain import keys as key_rules
from etach.domain import test_text, validators
from etach.domain.merge import merge, survivor_question_ids
from etach.domain.models import (
    Answer,
    AnswerKey,
    ExtractInput,
    OmittedSection,
    ReviewItem,
    Section,
    Test,
    TestContent,
)
from etach.domain.normalize import collapse_spaces, name_search, value_norm
from etach.domain.renumber import fingerprint_text, unreadable_spans
from etach.store.db import transaction, write_test_meta
from etach.store.repos import attempts, explanations, keys, regrade, review, runs, students, tests
from etach.store.repos import points as points_repo

__all__ = [
    "Action",
    "DropNotConfirmed",
    "InvalidResolution",
    "ResolveResult",
    "ReviewNotOpen",
    "TextNotRead",
    "TextSaveResult",
    "failure_text",
    "resolve",
    "save_test_text",
]

Action = Literal["accept", "fix", "skip"]

_NO_FIX = {"possible_duplicate", "picked_test_mismatch"}
_STUDENT_ID = re.compile(r"^S-\d+$")


class ReviewNotOpen(ValueError):
    """The item is not ``open`` (already resolved, or obsolete)."""


class InvalidResolution(ValueError):
    """The action does not exist for the kind, or the value is invalid."""


@dataclass
class ResolveResult:
    item: ReviewItem
    followup_run_ids: list[str] = field(default_factory=list)


def resolve(
    conn: sqlite3.Connection, item_id: str, action: Action, value: Any = None
) -> ResolveResult:
    """Resolve one open Review item; see the module docstring."""
    if action not in ("accept", "fix", "skip"):
        raise InvalidResolution(f"unknown action {action!r}")
    with transaction(conn):
        item = review.get_item(conn, item_id)
        if item is None:
            raise KeyError(f"no review item {item_id}")
        if item.status != "open":
            raise ReviewNotOpen(f"review item {item_id} is {item.status}, not open")
        if action == "fix" and item.kind in _NO_FIX:
            raise InvalidResolution(f"{item.kind} has no fix")
        if action == "fix" and value is None:
            raise InvalidResolution("fix needs a value")
        run_ids: list[str] = []
        if action != "skip":
            run_ids = _HANDLERS[item.kind](conn, item, action, value)
        status: Literal["accepted", "fixed", "skipped"] = (
            "skipped" if action == "skip" else "accepted" if action == "accept" else "fixed"
        )
        resolved = review.resolve_item(
            conn,
            item_id,
            status,
            {"action": action, "value": value},
            run_ids[0] if run_ids else None,
        )
    return ResolveResult(resolved, run_ids)


# --- helpers ---------------------------------------------------------------------------------


def _need(value: Any, what: str) -> Any:
    if value is None:
        raise InvalidResolution(f"the item has no {what}")
    return value


def _test(conn: sqlite3.Connection, test_id: str | None) -> Test:
    test = tests.get_test(conn, _need(test_id, "test"))
    if test is None:
        raise InvalidResolution(f"no test {test_id}")
    return test


def _graded(conn: sqlite3.Connection, test_id: str, attempt_id: str) -> bool:
    return attempt_id in attempts.graded_attempts(conn, test_id)


def _grade_attempt(
    conn: sqlite3.Connection,
    attempt_id: str,
    reason: Literal["key_verified", "merge", "review_fix", "points_fix"],
) -> list[str]:
    """1 grade run if the attempt is graded, else none."""
    att = attempts.get_attempt(conn, attempt_id)
    assert att is not None
    if not _graded(conn, att.test_id, attempt_id):
        return []
    return [runs.enqueue_grade(conn, test_id=att.test_id, attempt_id=attempt_id, reason=reason)]


def _grade_test(
    conn: sqlite3.Connection, test_id: str, reason: Literal["key_verified", "points_fix"]
) -> list[str]:
    """1 grade run per graded attempt on the test. A key change (``key_verified``) queues none
    since data-model v1.20: the test goes to ``regrade_pending`` (only when it has graded
    attempts) and ``POST /tests/{id}/regrade`` starts the runs."""
    if reason == "key_verified":
        regrade.mark(conn, test_id)
        return []
    return [
        runs.enqueue_grade(conn, test_id=test_id, attempt_id=a, reason=reason)
        for a in attempts.graded_attempts(conn, test_id)
    ]


def _text(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidResolution(f"{what} must be a non-empty string")
    return value


def _now() -> datetime:
    return datetime.now(UTC)


# --- per kind --------------------------------------------------------------------------------


def _answer_override(
    conn: sqlite3.Connection, item: ReviewItem, action: Action, value: Any
) -> list[str]:
    """``uncertain_answer`` / ``box_inline_conflict``: ``teacher_override``, ``value_norm``,
    ``version += 1``; graded → 1 grade run (``review_fix``).

    ``teacher_override = ""`` means "the teacher confirmed no answer" (data-model v1.5.2): an
    Accept whose read (or box) value is None, and a Fix with an empty or blank string, store
    ``""`` (``value_norm`` ``""``)."""
    attempt_id = _need(item.attempt_id, "attempt")
    qid = _need(item.question_id, "question")
    answer = attempts.get_answer(conn, attempt_id, qid)
    if answer is None:
        raise InvalidResolution(f"no answer {attempt_id}/{qid}")
    override: str | None
    if action == "fix":
        if not isinstance(value, str):
            raise InvalidResolution('the answer must be a string ("" = confirmed blank)')
        override = value
    elif item.kind == "box_inline_conflict":
        override = item.proposal.get("box_value")
    else:
        override = item.proposal.get("value", answer.value)
    if override is None or not override.strip():
        override = ""  # confirmed blank
    attempts.update_answer(
        conn,
        answer.model_copy(
            update={"teacher_override": override, "value_norm": value_norm(override)}
        ),
    )
    attempts.bump_version(conn, attempt_id)
    return _grade_attempt(conn, attempt_id, "review_fix")


def _accepted(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(v, str) and v.strip() for v in value)
    ):
        raise InvalidResolution("a key is a non-empty string or list of strings")
    return list(value)


def _teacher_key(test_id: str, qid: str, accepted: list[str], reason_vi: str | None) -> AnswerKey:
    return AnswerKey(
        test_id=test_id,
        question_id=qid,
        accepted=accepted,
        reason_vi=reason_vi,
        source="teacher_edit",
        status="teacher_verified",
        confidence=None,
        updated_at=_now(),
    )


def _uncertain_key(
    conn: sqlite3.Connection, item: ReviewItem, action: Action, value: Any
) -> list[str]:
    """Accept: status → ``teacher_verified`` (explanations kept). Fix: key replaced
    (``teacher_edit``; explanations deleted by the upsert). The test goes to ``regrade_pending``
    (v1.20) instead of N grade runs (``key_verified``)."""
    test_id = _need(item.test_id, "test")
    qid = _need(item.question_id, "question")
    old = keys.get_key(conn, test_id, qid)
    if action == "accept":
        if old is None:
            raise InvalidResolution(f"no key row for {qid}")
        new = old.model_copy(
            update={"status": "teacher_verified", "checker": None, "updated_at": _now()}
        )  # a verified key has no unsure check (step 22.5.5)
    else:
        test = _test(conn, test_id)
        accepted = key_rules.teacher_accepted(
            old, _accepted(value), key_rules.find_question(test.content, qid)
        )
        new = _teacher_key(test_id, qid, accepted, old.reason_vi if old else None)
    keys.upsert_key(conn, new)
    return _grade_test(conn, test_id, "key_verified")


def _key_unmapped(
    conn: sqlite3.Connection, item: ReviewItem, action: Action, value: Any
) -> list[str]:
    """Accept: the entry is discarded. Fix: a key row on the chosen question; N grade runs. On a
    True/False choice the first-start pass relabelled, the photo's letter goes through the same
    relabel map (``B`` on ``A. FALSE`` / ``B. TRUE`` → ``T``; step 22.5.8 (a)(3))."""
    if action == "accept":
        return []
    test = _test(conn, item.test_id)
    qid = _text(value, "question_id")
    if qid not in survivor_question_ids(test.content):
        raise InvalidResolution(f"{qid} is not a question of {test.id}")
    question = key_rules.find_question(test.content, qid)
    answer = _text(item.proposal.get("answer"), "the unmapped entry's answer")
    answer = key_rules.true_false_key(answer, question)
    old = keys.get_key(conn, test.id, qid)
    accepted = key_rules.teacher_accepted(old, [answer], question)
    keys.upsert_key(conn, _teacher_key(test.id, qid, accepted, None))
    return _grade_test(conn, test.id, "key_verified")


def _possible_duplicate(
    conn: sqlite3.Connection, item: ReviewItem, action: Action, value: Any
) -> list[str]:
    """Accept: merge this test into ``proposal.best_test_id`` (data-model §5.4)."""
    survivor = _need(item.proposal.get("best_test_id"), "best_test_id")
    alignment = item.proposal.get("question_alignment") or {}
    try:
        report = merge(
            conn,
            merged_test_id=_need(item.test_id, "test"),
            survivor_test_id=survivor,
            alignment=alignment,
            ref=item.id,
        )
    except (KeyError, ValueError) as exc:
        raise InvalidResolution(str(exc)) from exc
    return report.grade_run_ids


def _merge_unaligned(
    conn: sqlite3.Connection, item: ReviewItem, action: Action, value: Any
) -> list[str]:
    """Accept: the answer stays ``ungraded``. Fix: move it to a free survivor question;
    graded → 1 grade run (``merge``)."""
    if action == "accept":
        return []
    attempt_id = _need(item.attempt_id, "attempt")
    old_qid = _need(item.proposal.get("old_question_id", item.question_id), "old question")
    survivor = _test(conn, item.proposal.get("survivor_test_id", item.test_id))
    target = _text(value, "question_id")
    if target not in survivor_question_ids(survivor.content):
        raise InvalidResolution(f"{target} is not a question of {survivor.id}")
    if attempts.get_answer(conn, attempt_id, target) is not None:
        raise InvalidResolution(f"{target} already has an answer on {attempt_id}")
    if attempts.get_answer(conn, attempt_id, old_qid) is None:
        raise InvalidResolution(f"no answer {attempt_id}/{old_qid}")
    attempts.move_answer(conn, attempt_id, old_qid, target)
    return _grade_attempt(conn, attempt_id, "merge")


def _picked_test_mismatch(
    conn: sqlite3.Connection, item: ReviewItem, action: Action, value: Any
) -> list[str]:
    """Accept: a queued extract run of the same pages without the pick, superseding the
    attempt (``superseded_by`` is set by that run's save)."""
    att = attempts.get_attempt(conn, _need(item.attempt_id, "attempt"))
    if att is None:
        raise InvalidResolution(f"no attempt {item.attempt_id}")
    source = runs.get_run(conn, att.source_run_id)
    if source is None or not isinstance(source.input, ExtractInput):
        raise InvalidResolution(f"no extract run {att.source_run_id}")
    new_input = ExtractInput(
        pages=source.input.pages, existing_test_id=None, supersedes_attempt_id=att.id
    )
    return [runs.enqueue_extract(conn, thread_id=att.thread_id, input=new_input)]


def _unknown_student(
    conn: sqlite3.Connection, item: ReviewItem, action: Action, value: Any
) -> list[str]:
    """Accept: a new student from the name read. Fix: a chosen or new student.
    ``version += 1``; no run."""
    att = attempts.get_attempt(conn, _need(item.attempt_id, "attempt"))
    if att is None:
        raise InvalidResolution(f"no attempt {item.attempt_id}")
    class_name = att.class_read or item.proposal.get("class_read")
    if action == "accept":
        name = att.student_name_read or item.proposal.get("student_name_read")
        if not name or not str(name).strip():
            raise InvalidResolution("no student name was read")
        student_id = _new_student(conn, name, class_name)
    else:
        student_id = None
        full_name: Any = None
        if isinstance(value, dict):
            student_id = value.get("student_id")
            full_name = value.get("full_name")
            class_name = value.get("class_name", class_name)
        elif isinstance(value, str) and _STUDENT_ID.match(value.strip()):
            student_id = value.strip()
        else:
            full_name = value
        if student_id is not None:
            if students.get_student(conn, student_id) is None:
                raise InvalidResolution(f"no student {student_id}")
        else:
            student_id = _new_student(conn, _text(full_name, "the student name"), class_name)
    attempts.set_student(conn, att.id, student_id)
    attempts.bump_version(conn, att.id)
    return []


def _new_student(conn: sqlite3.Connection, name: str, class_name: str | None) -> str:
    full = collapse_spaces(name)
    return students.create_student(conn, full, name_search(full), class_name=class_name).id


def _unknown_occasion(
    conn: sqlite3.Connection, item: ReviewItem, action: Action, value: Any
) -> list[str]:
    """Accept: ``Other:unknown`` stays. Fix: ``write_test_meta(by_teacher=True)``."""
    if action == "accept":
        return []
    test = _test(conn, item.test_id)
    try:
        write_test_meta(conn, test.id, {"occasion": _text(value, "occasion")}, by_teacher=True)
    except ValidationError as exc:
        raise InvalidResolution(f"invalid occasion {value!r}") from exc
    return []


def _points_assumed(
    conn: sqlite3.Connection, item: ReviewItem, action: Action, value: Any
) -> list[str]:
    """Only an item made before v1.19 (they are closed at first start). Accept: nothing.
    Fix: the value is checked, then the content is saved with equal points and the graded
    attempts re-scored (no grade run; PRD D13 v8.0)."""
    if action == "accept":
        return []
    test = _test(conn, item.test_id)
    content = test.content.model_copy(deep=True)
    section_id = item.proposal.get("section_id")
    number = item.proposal.get("section_number")
    matches = [
        s for s in content.sections if (s.id == section_id if section_id else s.number == number)
    ]
    if len(matches) != 1:
        raise InvalidResolution("the item's section is not in the test")
    section = matches[0]
    questions = [q for g in section.groups for q in g.questions]
    if not isinstance(value, dict) or len(value) != 1:
        raise InvalidResolution("points: {points_per_question: x} or {section_total: y}")
    ((mode, amount),) = value.items()
    if isinstance(amount, bool) or not isinstance(amount, int | float) or amount < 0:
        raise InvalidResolution("points must be a number ≥ 0")
    if mode == "points_per_question":
        per = float(amount)
    elif mode == "section_total":
        if not questions:
            raise InvalidResolution("the section has no questions")
        per = float(amount) / len(questions)
    else:
        raise InvalidResolution("points: {points_per_question: x} or {section_total: y}")
    del per  # v1.19 (PRD D13 v8.0): the typed points are ignored; the equal rule decides them
    # save_content re-scores the graded attempts from their verdicts: no grade run is needed
    points_repo.save_content(conn, test.id, content)
    return []


def _validator_failed(
    conn: sqlite3.Connection, item: ReviewItem, action: Action, value: Any
) -> list[str]:
    """Accept: content unchanged. Fix: the edited content, re-validated; if a key row changed
    (a question removed, or new keys given) → as ``uncertain_key`` fix (N grade runs)."""
    if action == "accept":
        return []
    test = _test(conn, item.test_id)
    if not isinstance(value, dict):
        raise InvalidResolution("content must be a TestContent object")
    if "content" in value:
        raw_content, raw_keys = value["content"], value.get("keys") or {}
    else:
        raw_content, raw_keys = value, {}
    try:
        content = TestContent.model_validate(raw_content)
    except ValidationError as exc:
        raise InvalidResolution(f"invalid content: {exc.error_count()} errors") from exc
    failures = validators.validate_content(content, test.meta.omitted_sections)
    if failures:
        raise InvalidResolution(
            "content fails validation: "
            + "; ".join(f"{f.validator}: {f.message}" for f in failures)
        )
    if not isinstance(raw_keys, dict):
        raise InvalidResolution("keys must map question_id → accepted")
    qids = set(survivor_question_ids(content))
    unknown = set(raw_keys) - qids
    if unknown:
        raise InvalidResolution(f"keys for unknown questions: {sorted(unknown)}")
    content = points_repo.save_content(conn, test.id, content)
    key_changed = False
    for key in keys.list_keys(conn, test.id):
        if key.question_id not in qids:
            key_changed |= keys.delete_key(conn, test.id, key.question_id)
    for qid, accepted in raw_keys.items():
        old = keys.get_key(conn, test.id, qid)
        sent = key_rules.teacher_accepted(
            old, _accepted(accepted), key_rules.find_question(content, qid)
        )
        write = keys.upsert_key(
            conn, _teacher_key(test.id, qid, sent, old.reason_vi if old else None)
        )
        key_changed |= write.key_changed
    return _grade_test(conn, test.id, "key_verified") if key_changed else []


_PATH_PART = re.compile(r"^([a-z_]+)(?:\[(\d+)\])?$")


def _path_parts(path: str) -> list[str | int]:
    parts: list[str | int] = []
    for raw in path.split("."):
        m = _PATH_PART.match(raw)
        if m is None:
            raise InvalidResolution(f"bad path {path!r}")
        parts.append(m.group(1))
        if m.group(2) is not None:
            parts.append(int(m.group(2)))
    return parts


def _set_path(data: dict[str, Any], path: str, text: str) -> None:
    """Set the text field at ``path`` in the content JSON."""
    *head, last = _path_parts(path)
    node: Any = data
    try:
        for part in head:
            node = node[part]
        old = node[last]
    except (KeyError, IndexError, TypeError) as exc:
        raise InvalidResolution(f"{path} is not in the test content") from exc
    if old is not None and not isinstance(old, str):
        raise InvalidResolution(f"{path} is not a text field")
    node[last] = text


def _failure_keys(failures: list[validators.ValidatorFailure]) -> set[tuple[str, str | None, str]]:
    return {(f.validator, f.question_id, f.message) for f in failures}


def _unreadable_text(
    conn: sqlite3.Connection, item: ReviewItem, action: Action, value: Any
) -> list[str]:
    """Accept: content unchanged (the ``???`` spans stay). Fix ``{spans: [{path, text}]}``: each
    listed field gets the typed text through the content edit (re-validated: the content model and
    the validators; an edit that adds a validator failure is rejected). Other fields unchanged;
    a section's ``title`` follows its ``printed_title`` when it was a copy of it. No run."""
    if action == "accept":
        return []
    test = _test(conn, item.test_id)
    spans = value.get("spans") if isinstance(value, dict) else None
    if not isinstance(spans, list) or not spans:
        raise InvalidResolution("fix needs {spans: [{path, text}, …]}")
    listed = {s.get("path") for s in item.proposal.get("spans") or [] if isinstance(s, dict)}
    data = test.content.model_dump(mode="json")
    for span in spans:
        if not isinstance(span, dict) or not isinstance(span.get("text"), str):
            raise InvalidResolution("each span is {path, text} with text a string")
        path = span.get("path")
        if not isinstance(path, str) or path not in listed:
            raise InvalidResolution(f"{path!r} is not a span of this item")
        _set_path(data, path, span["text"])
        parts = _path_parts(path)
        if parts[0] == "sections" and parts[2:] == ["printed_title"]:
            section = test.content.sections[int(parts[1])]
            if section.title == section.printed_title:  # title is a copy of the printed one
                data["sections"][parts[1]]["title"] = span["text"]
    try:
        content = TestContent.model_validate(data)
    except ValidationError as exc:
        raise InvalidResolution(f"invalid content: {exc.error_count()} errors") from exc
    omitted = test.meta.omitted_sections
    before = _failure_keys(validators.validate_content(test.content, omitted))
    added = [
        f
        for f in validators.validate_content(content, omitted)
        if (f.validator, f.question_id, f.message) not in before
    ]
    if added:
        raise InvalidResolution(
            "content fails validation: " + "; ".join(f"{f.validator}: {f.message}" for f in added)
        )
    content = points_repo.save_content(conn, test.id, content)
    return []


_HANDLERS = {
    "uncertain_answer": _answer_override,
    "box_inline_conflict": _answer_override,
    "uncertain_key": _uncertain_key,
    "key_unmapped": _key_unmapped,
    "possible_duplicate": _possible_duplicate,
    "merge_unaligned": _merge_unaligned,
    "picked_test_mismatch": _picked_test_mismatch,
    "unknown_student": _unknown_student,
    "unknown_occasion": _unknown_occasion,
    "points_assumed": _points_assumed,
    "validator_failed": _validator_failed,
    "unreadable_text": _unreadable_text,
}


# --- the test page: a text save settles items (data-model §5.3 v1.9) -----------------------


class TextNotRead(ValueError):
    """The text cannot be read, or reading it adds a content-check failure. ``errors`` is a list
    of ``{line, message}`` (``line`` 1-based, or ``None``)."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("the test text could not be read")
        self.errors = errors


class DropNotConfirmed(ValueError):
    """The text drops questions that have a key row or answers, and they are not confirmed.
    ``drops`` is a list of ``{question_id, number, printed_number, has_key, answers}``."""

    def __init__(self, drops: list[dict[str, Any]]) -> None:
        super().__init__("dropping these questions needs the teacher's confirmation")
        self.drops = drops


@dataclass
class TextSaveResult:
    settled_item_ids: list[str] = field(default_factory=list)
    obsolete_item_ids: list[str] = field(default_factory=list)
    dropped_question_ids: list[str] = field(default_factory=list)
    followup_run_ids: list[str] = field(default_factory=list)


def failure_text(f: validators.ValidatorFailure) -> str:
    """A content-check failure in words for the teacher."""
    n = f.printed_number
    if f.validator == "gap_fill_blank":
        return (
            f"Question {n} has no blank. Type ____ where the answer goes, in the question or in "
            "the passage above it."
        )
    if f.validator == "mcq_options":
        return f"Question {n} needs 2 to 4 options, labelled A, B, C, D in that order."
    if f.validator == "numbering":
        return (
            f"Question {n} is out of order ({f.message}). Number the questions 1, 2, 3, … "
            "as on the paper."
        )
    return f.message


def save_test_text(
    conn: sqlite3.Connection,
    test_id: str,
    text: str,
    drop_confirmed: list[str] | tuple[str, ...] = (),
) -> TextSaveResult:
    """Save the test page's text (module docstring). Raises :class:`TextNotRead` or
    :class:`DropNotConfirmed` with nothing written; ``KeyError`` for an unknown test."""
    with transaction(conn):
        test = tests.get_test(conn, test_id)
        if test is None:
            raise KeyError(f"no test {test_id}")
        result = test_text.read(text, test.content)
        if result.content is None:
            raise TextNotRead([{"line": e.line, "message": e.message} for e in result.errors])
        content = result.content
        omitted = test.meta.omitted_sections
        before = _failure_keys(_text_failures(test.content, omitted))
        added = [
            f
            for f in _text_failures(content, omitted)
            if (f.validator, f.question_id, f.message) not in before
        ]
        if added:
            raise TextNotRead(
                [
                    {
                        "line": result.question_lines.get(f.question_id or ""),
                        "message": failure_text(f),
                    }
                    for f in added
                ]
            )
        old_q = {q.id: q for s in test.content.sections for g in s.groups for q in g.questions}
        confirmed = set(drop_confirmed)
        needs: list[dict[str, Any]] = []
        for qid in result.dropped:
            has_key = keys.get_key(conn, test_id, qid) is not None
            answers = attempts.count_answers_for_question(conn, test_id, qid)
            if has_key or answers:
                q = old_q[qid]
                needs.append(
                    {
                        "question_id": qid,
                        "number": q.number,
                        "printed_number": q.printed_number,
                        "has_key": has_key,
                        "answers": answers,
                    }
                )
        unconfirmed = [d for d in needs if d["question_id"] not in confirmed]
        if unconfirmed:
            raise DropNotConfirmed(unconfirmed)

        graded = attempts.graded_attempts(conn, test_id)
        content = points_repo.save_content(conn, test_id, content)
        added_rows = _add_answer_rows(conn, test_id, test.content, content)
        tests.set_fingerprint(conn, test_id, fingerprint_text(content))
        data_deleted = False
        for qid in result.dropped:
            data_deleted |= keys.delete_key(conn, test_id, qid)
            explanations.delete_for_question(conn, test_id, qid)
            for attempt_id in attempts.delete_answers_for_question(conn, test_id, qid):
                attempts.bump_version(conn, attempt_id)
                data_deleted = True
            tests.set_question_tags(conn, test_id, qid, [])
        out = _settle(conn, test, content, set(result.dropped), data_deleted or added_rows, graded)
        out.dropped_question_ids = list(result.dropped)
    return out


def _text_failures(
    content: TestContent, omitted: list[OmittedSection]
) -> list[validators.ValidatorFailure]:
    """The content checks of a text save. Printed numbers may skip (PRD D10 v6.0, answer 12):
    every number up to the highest counts as allowed to be missing, so only a number that does
    not follow the one before is a failure."""
    nums = [q.printed_number for s in content.sections for g in s.groups for q in g.questions]
    gaps = OmittedSection(title="", questions=list(range(1, max(nums, default=0) + 1)), points=0)
    return validators.validate_content(content, [*omitted, gaps])


def _add_answer_rows(
    conn: sqlite3.Connection, test_id: str, old: TestContent, new: TestContent
) -> bool:
    """A question new in the text gets an empty, unread answer row in every attempt of the test
    (data-model §5.3 v1.11). True when a row was added."""
    old_ids = {q.id for s in old.sections for g in s.groups for q in g.questions}
    fresh = [
        q
        for s in new.sections
        if s.graded
        for g in s.groups
        for q in g.questions
        if q.id not in old_ids and q.answer_form != "writing"
    ]
    if not fresh:
        return False
    added = False
    for att in attempts.list_attempts(conn, test_id=test_id):
        attempts.insert_answers(
            conn,
            [
                Answer(
                    attempt_id=att.id,
                    question_id=q.id,
                    printed_number=q.printed_number,
                    page_no=None,
                    value=None,
                    value_norm=None,
                    location="none",
                    confidence=0.0,
                    reading_unsure=False,
                    alt_value=None,
                    alt_question_id=None,
                    points_awarded=None,
                    teacher_override=None,
                )
                for q in fresh
            ],
        )
        attempts.bump_version(conn, att.id)
        added = True
    return added


def _section_of(item: ReviewItem, content: TestContent) -> Section | None:
    """The section a ``points_assumed`` item is about: by the id in its proposal or dedupe key,
    else by its number."""
    section_id = item.proposal.get("section_id") or item.dedupe_key.rsplit(":", 1)[-1]
    for s in content.sections:
        if s.id == section_id:
            return s
    number = item.proposal.get("section_number")
    return next((s for s in content.sections if s.number == number), None)


def _settle(
    conn: sqlite3.Connection,
    test: Test,
    content: TestContent,
    dropped: set[str],
    data_deleted: bool,
    graded: list[str],
) -> TextSaveResult:
    out = TextSaveResult()
    spans = unreadable_spans(content)
    validates = not _text_failures(content, test.meta.omitted_sections)
    open_pages: set[int] = set()
    fixed: list[tuple[ReviewItem, bool]] = []  # (item, its points changed)
    # no points_changed: save_content re-scores the graded attempts on a points change, so a
    # text save queues a run only when data was deleted or added (R22.6.6.3)
    for item in review.list_open_for_test(conn, test.id):
        if item.question_id is not None and item.question_id in dropped:
            review.set_obsolete(conn, item.id)
            out.obsolete_item_ids.append(item.id)
            continue
        if item.kind == "unreadable_text" and item.test_id == test.id:
            page_no = item.proposal.get("page_no")
            if isinstance(page_no, int) and page_no in spans:
                open_pages.add(page_no)
                review.set_proposal(conn, item.id, {**item.proposal, "spans": spans[page_no]})
            else:
                fixed.append((item, False))
        elif item.kind == "validator_failed" and item.attempt_id is None and validates:
            fixed.append((item, False))
        elif item.kind == "points_assumed":
            # v1.19 (PRD D13 v8.0): the points are the equal ones and the attempts were
            # re-scored by save_content, so an item left from before is closed, with no run
            review.set_obsolete(conn, item.id)
            out.obsolete_item_ids.append(item.id)
    # a typed ??? on a page with no open item creates (or reopens) that page's item (v1.11)
    page_files = {p[1]: p[2] for p in tests.list_test_pages(conn, test.id)}
    for page_no, page_spans in spans.items():
        if page_no not in open_pages:
            review.upsert_item(
                conn,
                kind="unreadable_text",
                owner="extract",
                dedupe_key=f"unreadable_text:{test.id}:p{page_no}",
                proposal={
                    "page_no": page_no,
                    "file_id": page_files.get(page_no),
                    "spans": page_spans,
                },
                test_id=test.id,
            )
    if data_deleted:
        # graded attempts only: an attempt whose first grade run is unfinished is graded
        # against the saved test by that run (grade ``save``'s test check, R22.6.6.3)
        out.followup_run_ids = [
            runs.enqueue_grade(conn, test_id=test.id, attempt_id=a, reason="review_fix")
            for a in graded
        ]
    for item, with_run in fixed:
        followup = out.followup_run_ids[0] if with_run and out.followup_run_ids else None
        review.resolve_item(
            conn, item.id, "fixed", {"action": "fix", "value": {"by": "test_text"}}, followup
        )
        out.settled_item_ids.append(item.id)
    return out
