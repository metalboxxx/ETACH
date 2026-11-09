"""The one-time first-start pass of migration 0012 over the stored tests (data-model v1.22,
step 22.5.3, decision D9).

It runs only while ``answer_form_pending`` holds its row and removes the row in the same
transaction, so a second start changes nothing. It works on the raw content JSON (the old
``type`` no longer validates as a ``Question`` field) and, for every question of every stored
test:

- ``type`` becomes ``answer_form`` by :data:`etach.domain.models.FORM_OF_OLD_TYPE` (mcq, true_false,
  matching → choice; gap_fill, word_form, verb_form → word; rewrite, combine, ordering,
  short_answer → sentence; writing → writing);
- the old value is kept in ``old_type``, read-only and used by nothing but a revert
  (:func:`revert_question_data`), so a revert loses nothing;
- a ``true_false`` question without options gets the two options the code adds (``T. True``,
  ``F. False``);
- ``context`` is set from the group's ``stimulus`` (``paragraph`` / ``single``; none for writing);
- a ``choice`` whose two options read True and False (``A. True`` / ``B. False``, or reversed as
  ``A. FALSE`` / ``B. TRUE``; also Đúng / Sai; :func:`etach.domain.models.true_false_letters`) gets
  the options ``T. True``, ``F. False``; its stored options are kept in ``old_options``,
  read-only, for a revert (step 22.5.3 checklist (d), R22.5.3.8). In the same transaction its
  key (``answer_keys.accepted``), its student answers (``answers.value``, ``value_norm``,
  ``alt_value``, ``teacher_override``), ``explanations.wrong_answer_norm`` and the letters in the
  proposal of its **open** Review items (:data:`PROPOSAL_LETTERS`: ``uncertain_answer``
  ``value`` / ``alt_value``, ``box_inline_conflict`` ``box_value`` / ``inline_value``,
  ``uncertain_key`` ``accepted``) are relabelled: the letter whose text meant True becomes ``T``,
  the one that meant False ``F``. Resolved items are history and keep their letters. Swapped
  labels (``T. False``, ``F. True``) are safe: each row is written once from its old values, and
  the explanations go through a temporary value, so no primary key collides. A question with
  explanation rows for both an old letter and the T/F letter it maps to (rows ``a`` and ``f`` on
  ``A. FALSE`` / ``B. TRUE``) keeps one row, the one already holding the T/F letter, and the
  other is dropped (step 22.5.4, R22.5.4.7).

Apart from that relabelling, only ``tests.content`` changes: not ``updated_at``, the points, the
fingerprint, and no verdict, grade report, review item status or ``regrade_pending`` row (the
relabelled key and student answers mean the same as before); graded attempts are not marked for
re-grade.
The pass runs before the other first-start passes, which read tests through the models.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from etach.domain.models import (
    TRUE_FALSE_OPTIONS,
    TestContent,
    true_false_letters,
    upgrade_question_data,
)
from etach.domain.normalize import value_norm
from etach.store.db import transaction

__all__ = [
    "PROPOSAL_LETTERS",
    "revert_content_data",
    "revert_question_data",
    "run_answer_form_pass",
    "upgrade_content_data",
    "upgrade_content_relabels",
]


#: Question id → {stored label → ``T`` / ``F``} for the True/False choices the pass relabelled.
Relabels = dict[str, dict[str, str]]

#: Review kind → the ``proposal`` fields that hold a stored label of the question (a student
#: answer, or for ``uncertain_key`` the key), relabelled on open items by the pass.
PROPOSAL_LETTERS: dict[str, tuple[str, ...]] = {
    "uncertain_answer": ("value", "alt_value"),
    "box_inline_conflict": ("box_value", "inline_value"),
    "uncertain_key": ("accepted",),
}

#: Prefix of the temporary ``wrong_answer_norm`` while explanations are relabelled.
_TEMP = "~relabel:"


def _relabel_true_false(question: dict[str, Any], relabels: Relabels) -> dict[str, Any]:
    if question.get("answer_form") != "choice":
        return question
    options = question.get("options") or []
    letters = true_false_letters([(o.get("label", ""), o.get("text", "")) for o in options])
    added = [{"label": label, "text": text} for label, text in TRUE_FALSE_OPTIONS]
    if letters is None or options == added:
        return question
    relabels[question["id"]] = letters
    return {**question, "options": added, "old_options": options}


def upgrade_content_relabels(content: dict[str, Any]) -> tuple[dict[str, Any], Relabels]:
    """:func:`upgrade_content_data` and the True/False relabelling it made, by question id."""
    relabels: Relabels = {}
    sections = []
    for section in content.get("sections", []):
        groups = []
        for group in section.get("groups", []):
            questions = [
                _relabel_true_false(upgrade_question_data(q), relabels)
                for q in group.get("questions", [])
            ]
            groups.append({**group, "questions": questions})
        sections.append({**section, "groups": groups})
    # validating sets each question's context from its group's stimulus
    upgraded = TestContent.model_validate({**content, "sections": sections})
    return upgraded.model_dump(mode="json"), relabels


def upgrade_content_data(content: dict[str, Any]) -> dict[str, Any]:
    """Raw content JSON with every old question mapped (see the module docstring); a question
    that already has an ``answer_form`` is left as it is, apart from the True/False relabelling."""
    return upgrade_content_relabels(content)[0]


def revert_question_data(question: dict[str, Any]) -> dict[str, Any]:
    """For a revert of step 22.5.3 only: the question in the old shape, ``type`` = its
    ``old_type`` (a question made later gets the first old type of its form: choice → mcq,
    word → gap_fill, sentence → rewrite, writing → writing). The True/False options the pass
    added are removed again, and a relabelled True/False choice gets its ``old_options`` back.
    A revert of the stored key and student answers on such a question maps them back the same
    way: ``T`` → the old label whose text meant True, ``F`` → the one that meant False
    (:func:`etach.domain.models.true_false_letters` over ``old_options``, inverted)."""
    drop = ("answer_form", "context", "old_type", "old_options")
    out = {k: v for k, v in question.items() if k not in drop}
    old = question.get("old_type")
    if old is None:
        old = {"choice": "mcq", "word": "gap_fill", "sentence": "rewrite"}.get(
            question.get("answer_form", ""), "writing"
        )
    out["type"] = old
    added = [{"label": "T", "text": "True"}, {"label": "F", "text": "False"}]
    if old == "true_false" and question.get("options") == added:
        out["options"] = None
    if question.get("old_options"):
        out["options"] = question["old_options"]
    return out


def revert_content_data(content: dict[str, Any]) -> dict[str, Any]:
    """:func:`revert_question_data` over every question of a raw content JSON."""
    return {
        **content,
        "sections": [
            {
                **s,
                "groups": [
                    {**g, "questions": [revert_question_data(q) for q in g["questions"]]}
                    for g in s["groups"]
                ],
            }
            for s in content["sections"]
        ],
    }


def run_answer_form_pass(conn: sqlite3.Connection) -> bool:
    """The first-start pass (see the module docstring). Returns whether it ran."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'answer_form_pending'"
    ).fetchone()
    if not exists or not conn.execute("SELECT 1 FROM answer_form_pending").fetchone():
        return False
    with transaction(conn):
        for test_id, raw in conn.execute("SELECT id, content FROM tests ORDER BY id").fetchall():
            content = json.loads(raw)
            upgraded, relabels = upgrade_content_relabels(content)
            if upgraded != content:
                conn.execute(
                    "UPDATE tests SET content = ? WHERE id = ?",
                    (TestContent.model_validate(upgraded).model_dump_json(), test_id),
                )
            for question_id, letters in relabels.items():
                _relabel_rows(conn, test_id, question_id, letters)
        conn.execute("DELETE FROM answer_form_pending")
    return True


def _letter(value: str | None, letters: dict[str, str]) -> str | None:
    """``value`` relabelled when it is one of the old labels (any case, trimmed)."""
    if value is None:
        return None
    return letters.get(value.strip().upper(), value)


def _relabel_rows(
    conn: sqlite3.Connection, test_id: str, question_id: str, letters: dict[str, str]
) -> None:
    """The stored key, student answers and explanations of one relabelled True/False choice."""
    for (accepted,) in conn.execute(
        "SELECT accepted FROM answer_keys WHERE test_id = ? AND question_id = ?",
        (test_id, question_id),
    ).fetchall():
        new = list(dict.fromkeys(_letter(a, letters) for a in json.loads(accepted)))
        conn.execute(
            "UPDATE answer_keys SET accepted = ? WHERE test_id = ? AND question_id = ?",
            (json.dumps(new, ensure_ascii=False), test_id, question_id),
        )
    rows = conn.execute(
        "SELECT a.attempt_id, a.value, a.value_norm, a.alt_value, a.teacher_override"
        " FROM answers a JOIN attempts t ON t.id = a.attempt_id"
        " WHERE t.test_id = ? AND a.question_id = ?",
        (test_id, question_id),
    ).fetchall()
    for attempt_id, value, norm, alt, override in rows:
        new_norm = _letter(norm, letters)
        conn.execute(
            "UPDATE answers SET value = ?, value_norm = ?, alt_value = ?, teacher_override = ?"
            " WHERE attempt_id = ? AND question_id = ?",
            (
                _letter(value, letters),
                None if new_norm is None else value_norm(new_norm),
                _letter(alt, letters),
                _letter(override, letters),
                attempt_id,
                question_id,
            ),
        )
    # two rows that map to the same letter (rows ``a`` and ``f`` on ``A. FALSE`` / ``B. TRUE``):
    # one row is kept, the one already holding the new letter (else the first), the other is
    # dropped, so the relabel below cannot collide (step 22.5.4, R22.5.4.7)
    wrongs = [
        w
        for (w,) in conn.execute(
            "SELECT wrong_answer_norm FROM explanations WHERE test_id = ? AND question_id = ?"
            " ORDER BY wrong_answer_norm",
            (test_id, question_id),
        ).fetchall()
    ]
    by_target: dict[str, list[str]] = {}
    for wrong in wrongs:
        by_target.setdefault(value_norm(_letter(wrong, letters) or ""), []).append(wrong)
    for target, group in by_target.items():
        if len(group) < 2:
            continue
        keep = target if target in group else group[0]
        for wrong in group:
            if wrong != keep:
                conn.execute(
                    "DELETE FROM explanations"
                    " WHERE test_id = ? AND question_id = ? AND wrong_answer_norm = ?",
                    (test_id, question_id, wrong),
                )
                wrongs.remove(wrong)
    # through a temporary value: with swapped labels (T. False, F. True) a direct t → f would
    # collide with the f row still there (primary key test_id, question_id, wrong_answer_norm)
    for wrong in wrongs:
        conn.execute(
            "UPDATE explanations SET wrong_answer_norm = ?"
            " WHERE test_id = ? AND question_id = ? AND wrong_answer_norm = ?",
            (_TEMP + value_norm(_letter(wrong, letters) or ""), test_id, question_id, wrong),
        )
    conn.execute(
        "UPDATE explanations SET wrong_answer_norm = substr(wrong_answer_norm, ?)"
        " WHERE test_id = ? AND question_id = ? AND substr(wrong_answer_norm, 1, ?) = ?",
        (len(_TEMP) + 1, test_id, question_id, len(_TEMP), _TEMP),
    )
    _relabel_open_items(conn, test_id, question_id, letters)


def _relabel_open_items(
    conn: sqlite3.Connection, test_id: str, question_id: str, letters: dict[str, str]
) -> None:
    """The :data:`PROPOSAL_LETTERS` of the open Review items on one relabelled question, so an
    Accept (which writes the proposal) stores the new letter. Resolved items are left as
    history."""
    kinds = list(PROPOSAL_LETTERS)
    rows = conn.execute(
        "SELECT id, kind, proposal FROM review_items"
        " WHERE status = 'open' AND question_id = ?"
        f" AND kind IN ({', '.join('?' * len(kinds))})"
        " AND (test_id = ? OR attempt_id IN (SELECT id FROM attempts WHERE test_id = ?))",
        (question_id, *kinds, test_id, test_id),
    ).fetchall()
    for item_id, kind, raw in rows:
        proposal = json.loads(raw)
        new = dict(proposal)
        for name in PROPOSAL_LETTERS[kind]:
            value = proposal.get(name)
            if isinstance(value, str):
                new[name] = _letter(value, letters)
            elif isinstance(value, list):
                new[name] = list(
                    dict.fromkeys(_letter(v, letters) if isinstance(v, str) else v for v in value)
                )
        if new != proposal:
            conn.execute(
                "UPDATE review_items SET proposal = ? WHERE id = ?",
                (json.dumps(new, ensure_ascii=False), item_id),
            )
