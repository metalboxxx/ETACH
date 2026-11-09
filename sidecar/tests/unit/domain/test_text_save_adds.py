"""R22.2.4.2, R22.2.4.3: printed numbers may skip; a text save adds answer rows and ``???`` items
(data-model §2.3a, §5.3 v1.11). Built on the Appendix E world of ``test_review.py``."""

from __future__ import annotations

import json
import sqlite3

import pytest
from unit.domain.test_review import _unreadable_item, _world, conn  # noqa: F401

from etach.domain.review import save_test_text
from etach.domain.test_text import render
from etach.store.repos import attempts, review, tests

GRADED = pytest.mark.parametrize("graded", [True, False], ids=["graded", "ungraded"])


def _text(c: sqlite3.Connection, test_id: str) -> str:
    test = tests.get_test(c, test_id)
    assert test is not None
    return render(test.content)


def _grade_runs(c: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = c.execute("SELECT input FROM runs WHERE kind = 'grade'").fetchall()
    return sorted((json.loads(r[0])["attempt_id"], json.loads(r[0])["reason"]) for r in rows)


def _printed(c: sqlite3.Connection, test_id: str) -> list[int]:
    t = tests.get_test(c, test_id)
    assert t is not None
    return [q.printed_number for s in t.content.sections for g in s.groups for q in g.questions]


def test_gaps_in_printed_numbers_save_and_are_kept(conn: sqlite3.Connection) -> None:  # noqa: F811
    w = _world(conn, graded=False)
    text = _text(conn, w.t).replace("1. Stem 1", "6. Stem 1").replace("2. Stem 2", "7. Stem 2")
    save_test_text(conn, w.t, text.replace("3. Stem 3", "9. Stem 3"))
    assert _printed(conn, w.t) == [6, 7, 9]


def test_numbers_that_go_back_are_still_refused(conn: sqlite3.Connection) -> None:  # noqa: F811
    from etach.domain.review import TextNotRead

    w = _world(conn, graded=False)
    with pytest.raises(TextNotRead):
        save_test_text(conn, w.t, _text(conn, w.t).replace("3. Stem 3", "1. Stem 3"))


@GRADED
def test_a_new_question_gets_answer_rows_and_a_regrade(
    conn: sqlite3.Connection,  # noqa: F811
    graded: bool,
) -> None:
    w = _world(conn, graded=graded)
    added = "\n\n4. Stem 4\n   A. one    B. two\n"
    text = _text(conn, w.t).rstrip("\n") + added
    out = save_test_text(conn, w.t, text)
    t = tests.get_test(conn, w.t)
    assert t is not None
    new = [q for s in t.content.sections for g in s.groups for q in g.questions][-1]
    assert new.printed_number == 4
    for a in (w.a1, w.a2):
        row = attempts.get_answer(conn, a.id, new.id)
        assert row is not None
        assert row.value is None and row.location == "none" and row.verdict == "ungraded"
        assert row.printed_number == 4 and not row.reading_unsure
        after = attempts.get_attempt(conn, a.id)
        assert after is not None and after.version == a.version + 1
    if graded:
        assert _grade_runs(conn) == [(w.a1.id, "review_fix"), (w.a2.id, "review_fix")]
        assert len(out.followup_run_ids) == 2
    else:
        assert _grade_runs(conn) == []


def test_a_typed_unreadable_creates_the_page_item(conn: sqlite3.Connection) -> None:  # noqa: F811
    w = _world(conn, graded=False)
    save_test_text(conn, w.t, _text(conn, w.t).replace("2. Stem 2", "2. Stem ??? 2"))
    found = [i for i in review.list_open_for_test(conn, w.t) if i.kind == "unreadable_text"]
    (item,) = found
    assert item.dedupe_key == f"unreadable_text:{w.t}:p1"
    assert item.proposal["page_no"] == 1
    assert [s["text"] for s in item.proposal["spans"]] == ["Stem ??? 2"]


def test_a_typed_unreadable_updates_an_open_item(conn: sqlite3.Connection) -> None:  # noqa: F811
    w = _world(conn, graded=False)
    item_id = _unreadable_item(conn, w)
    text = _text(conn, w.t).replace("3. Stem 3", "3. Stem ??? 3")
    save_test_text(conn, w.t, text)
    item = review.get_item(conn, item_id)
    assert item is not None and item.status == "open"
    assert "Stem ??? 3" in [s["text"] for s in item.proposal["spans"]]
    found = [i for i in review.list_open_for_test(conn, w.t) if i.kind == "unreadable_text"]
    assert len(found) == 1
