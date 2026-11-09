"""R22.1.5.3, R22.1.5.4: a test-text save settles Review items (data-model §2.3a, §5.3 v1.9).

Built on the Appendix E world of ``test_review.py`` (test ``t`` with q1..q3, points assumed,
keys on q1 and q3, an explanation on q1, attempts a1 and a2 with answers). Like Appendix E, every
case with a follow-up runs twice: graded (runs queued) and ungraded (no run).
"""

from __future__ import annotations

import sqlite3

import pytest
from unit.domain.test_review import _item, _unreadable_item, _world, conn  # noqa: F401

from etach.domain.models import ReviewItem
from etach.domain.review import DropNotConfirmed, TextNotRead, resolve, save_test_text
from etach.domain.test_text import render
from etach.store.repos import attempts, explanations, keys, review, tests

GRADED = pytest.mark.parametrize("graded", [True, False], ids=["graded", "ungraded"])


def _text(c: sqlite3.Connection, test_id: str) -> str:
    test = tests.get_test(c, test_id)
    assert test is not None
    return render(test.content)


def _get(c: sqlite3.Connection, item_id: str) -> ReviewItem:
    item = review.get_item(c, item_id)
    assert item is not None
    return item


def _grade_runs(c: sqlite3.Connection) -> list[tuple[str | None, str]]:
    rows = c.execute("SELECT input FROM runs WHERE kind = 'grade'").fetchall()
    import json

    return sorted((json.loads(r[0])["attempt_id"], json.loads(r[0])["reason"]) for r in rows)


def test_unreadable_all_replaced_is_fixed(conn: sqlite3.Connection) -> None:  # noqa: F811
    w = _world(conn, graded=True)
    item_id = _unreadable_item(conn, w)
    text = _text(conn, w.t)
    assert text.count("???") == 3
    edited = text.replace("Circle ??? or B.", "Circle A or B.").replace("Stem ??? 1", "Stem 1")
    edited = edited.replace("???. two", "B. two")
    save_test_text(conn, w.t, edited)
    item = _get(conn, item_id)
    assert item.status == "fixed"
    assert item.resolution == {"action": "fix", "value": {"by": "test_text"}}
    assert item.resolved_at is not None and item.followup_run_id is None
    t = tests.get_test(conn, w.t)
    assert t is not None and "???" not in render(t.content)
    assert _grade_runs(conn) == []  # unreadable text changes no key and no points


def test_unreadable_some_left_stays_open_with_new_spans(conn: sqlite3.Connection) -> None:  # noqa: F811
    w = _world(conn, graded=True)
    item_id = _unreadable_item(conn, w)
    edited = _text(conn, w.t).replace("Stem ??? 1", "Stem 1")
    save_test_text(conn, w.t, edited)
    item = _get(conn, item_id)
    assert item.status == "open"
    paths = [s["path"] for s in item.proposal["spans"]]
    assert paths == [
        "sections[0].instructions",
        "sections[0].groups[0].questions[1].options[1].label",
    ]
    assert item.proposal["file_id"] == "f-page-1" and item.proposal["page_no"] == 1


def test_validator_failed_is_fixed_when_the_content_validates(conn: sqlite3.Connection) -> None:  # noqa: F811
    w = _world(conn, graded=True)
    item_id = _item(conn, "validator_failed", w, proposal={"task": "transcribe_page", "page_no": 1})
    answers_page = _item(
        conn,
        "uncertain_answer",
        w,
        attempt_id=w.a2.id,
        question_id="q3",
    )
    save_test_text(conn, w.t, _text(conn, w.t))
    assert _get(conn, item_id).status == "fixed"
    assert _get(conn, answers_page).status == "open"  # not a test-page kind


@GRADED
def test_typed_points_ignored_and_old_points_assumed_closed(
    conn: sqlite3.Connection,  # noqa: F811
    graded: bool,
) -> None:
    """v1.19 (PRD D13 v8.0): a text save gives equal points whatever the heading says, closes
    an item left from before as obsolete and queues no grade run; graded attempts are re-scored
    in place (out of 10)."""
    w = _world(conn, graded=graded)
    item, _ = review.upsert_item(
        conn,
        kind="points_assumed",
        owner="extract",
        dedupe_key="points_assumed:run:s-1",
        proposal={"section_number": 1, "printed_title": "I", "points_per_question": 0.25},
        test_id=w.t,
    )
    text = _text(conn, w.t)
    assert "# I  [title: Choose]\n" in text  # v1.21 (D7): no points on a heading
    save_test_text(
        conn,
        w.t,
        text.replace("# I  [title: Choose]", "I  [1.5 points, title: Choose]"),
    )
    assert _get(conn, item.id).status == "obsolete"
    assert _grade_runs(conn) == []
    t = tests.get_test(conn, w.t)
    assert t is not None and t.points_possible == 10.0
    sec = t.content.sections[0]
    assert sec.points_source == "equal" and sec.points == 10.0
    assert "# I  [title: Choose]\n" in _text(conn, w.t)
    if graded:
        for att in (w.a1, w.a2):
            a = attempts.get_attempt(conn, att.id)
            assert a is not None and a.score_possible == 10.0


@GRADED
def test_dropping_needs_confirmation_then_deletes_and_regrades(
    conn: sqlite3.Connection,  # noqa: F811
    graded: bool,
) -> None:
    w = _world(conn, graded=graded)
    key_item = _item(conn, "uncertain_key", w, question_id="q1")
    text = _text(conn, w.t)
    lines = text.split("\n")
    start = lines.index("1. Stem 1")
    del lines[start : start + 3]  # q1: its line, its options, the blank line
    renumbered = "\n".join(lines).replace("2. Stem 2", "1. Stem 2")  # numbers follow the paper
    dropped_text = renumbered.replace("3. Stem 3", "2. Stem 3")

    with pytest.raises(DropNotConfirmed) as info:
        save_test_text(conn, w.t, dropped_text)
    assert [
        (d["question_id"], d["number"], d["has_key"], d["answers"]) for d in info.value.drops
    ] == [("q1", 1, True, 2)]
    t = tests.get_test(conn, w.t)
    assert t is not None and "Stem 1" in render(t.content)  # nothing saved

    out = save_test_text(conn, w.t, dropped_text, ["q1"])
    assert out.dropped_question_ids == ["q1"]
    assert keys.get_key(conn, w.t, "q1") is None
    assert explanations.list_explanations(conn, w.t) == []
    assert attempts.get_answer(conn, w.a1.id, "q1") is None
    assert attempts.get_answer(conn, w.a2.id, "q1") is None
    assert _get(conn, key_item).status == "obsolete"
    a1 = attempts.get_attempt(conn, w.a1.id)
    assert a1 is not None and a1.version == w.a1.version + 1
    if graded:
        assert _grade_runs(conn) == [(w.a1.id, "review_fix"), (w.a2.id, "review_fix")]
    else:
        assert _grade_runs(conn) == []


def test_dropping_a_question_without_data_needs_no_confirmation(conn: sqlite3.Connection) -> None:  # noqa: F811
    w = _world(conn, graded=False)
    # q2 has answers on a1 and a2: remove them first so q2 has no data at all
    for a in (w.a1.id, w.a2.id):
        conn.execute("DELETE FROM answers WHERE attempt_id = ? AND question_id = 'q2'", (a,))
    lines = _text(conn, w.t).split("\n")
    start = lines.index("2. Stem 2")
    del lines[start : start + 3]
    out = save_test_text(conn, w.t, "\n".join(lines).replace("3. Stem 3", "2. Stem 3"))
    assert out.dropped_question_ids == ["q2"]
    assert out.followup_run_ids == []


def test_unreadable_text_saves_nothing(conn: sqlite3.Connection) -> None:  # noqa: F811
    w = _world(conn, graded=True)
    before = tests.get_test(conn, w.t)
    with pytest.raises(TextNotRead) as info:
        save_test_text(conn, w.t, "stray words\n" + _text(conn, w.t))
    assert info.value.errors[0]["line"] == 1
    assert tests.get_test(conn, w.t) == before


def test_a_new_validator_failure_is_refused_with_its_line(conn: sqlite3.Connection) -> None:  # noqa: F811
    w = _world(conn, graded=True)
    text = _text(conn, w.t)
    lines = text.split("\n")
    at = lines.index("2. Stem 2") + 1
    lines[at] = "   A. only one option"
    with pytest.raises(TextNotRead) as info:
        save_test_text(conn, w.t, "\n".join(lines))
    (err,) = info.value.errors
    assert err["line"] == at  # the question's own line (1-based: at = index + 1 - 1)
    assert "Question 2" in err["message"]


def test_review_resolution_still_works_after_a_text_save(conn: sqlite3.Connection) -> None:  # noqa: F811
    """The in-place actions keep using the Appendix E dispatch."""
    w = _world(conn, graded=False)
    item_id = _unreadable_item(conn, w)
    save_test_text(conn, w.t, _text(conn, w.t).replace("Stem ??? 1", "Stem 1"))
    result = resolve(conn, item_id, "accept")
    assert result.item.status == "accepted"
