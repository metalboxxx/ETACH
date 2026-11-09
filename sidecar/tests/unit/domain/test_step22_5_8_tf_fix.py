"""Step 22.5.8 (a)(3): a Fix of an open ``key_unmapped`` item onto a True/False choice the
first-start pass relabelled (step 22.5.3 (d)) stores the T/F letter, through the same relabel
map (R22.5.8.1). Synthetic data only."""

from __future__ import annotations

import sqlite3

import pytest
from unit.domain.test_review import _item, _world, conn  # noqa: F401

from etach.domain import models as m
from etach.domain.keys import true_false_key
from etach.domain.review import resolve
from etach.store.repos import keys, review, tests
from etach.store.repos import points as points_repo

REVERSED = [m.Option(label="A", text="FALSE"), m.Option(label="B", text="TRUE")]
TF = [m.Option(label="T", text="True"), m.Option(label="F", text="False")]


def _relabelled(conn: sqlite3.Connection, test_id: str, qid: str) -> None:  # noqa: F811
    """``qid`` as the first-start pass leaves an ``A. FALSE`` / ``B. TRUE`` choice."""
    t = tests.get_test(conn, test_id)
    assert t is not None
    for s in t.content.sections:
        for g in s.groups:
            for i, q in enumerate(g.questions):
                if q.id == qid:
                    g.questions[i] = q.model_copy(
                        update={"answer_form": "choice", "options": TF, "old_options": REVERSED}
                    )
    points_repo.save_content(conn, test_id, t.content)


@pytest.mark.parametrize(("read", "stored"), [("B", "T"), ("A", "F"), (" b. ", "T"), ("T", "T")])
def test_r22_5_8_1_key_unmapped_fix_onto_true_false_stores_the_tf_letter(
    conn: sqlite3.Connection,  # noqa: F811
    read: str,
    stored: str,
) -> None:
    w = _world(conn, graded=True)
    _relabelled(conn, w.t, "q2")
    item_id = _item(
        conn, "key_unmapped", w,
        proposal={"position": 3, "label": "9", "answer": read, "confidence": 0.8, "reason": "x"},
    )  # fmt: skip
    resolve(conn, item_id, "fix", "q2")
    k = keys.get_key(conn, w.t, "q2")
    assert k is not None and k.accepted == [stored] and k.source == "teacher_edit"
    assert review.get_item(conn, item_id).status == "fixed"  # type: ignore[union-attr]


def test_key_unmapped_fix_onto_another_choice_keeps_the_letter(
    conn: sqlite3.Connection,  # noqa: F811
) -> None:
    w = _world(conn, graded=True)
    item_id = _item(
        conn, "key_unmapped", w,
        proposal={"position": 3, "label": "9", "answer": "B", "confidence": 0.8, "reason": "x"},
    )  # fmt: skip
    resolve(conn, item_id, "fix", "q2")
    k = keys.get_key(conn, w.t, "q2")
    assert k is not None and k.accepted == ["B"]


def _q(**kw: object) -> m.Question:
    base: dict[str, object] = {
        "id": "q", "number": 1, "printed_number": 1, "page_no": 1, "answer_form": "choice",
        "stem": "s", "options": TF, "cue": None, "points": 0.25,
    }  # fmt: skip
    return m.Question.model_validate({**base, **kw})


def test_true_false_key_uses_the_relabel_map_only() -> None:
    assert true_false_key("B", _q(old_options=REVERSED)) == "T"
    straight = [m.Option(label="A", text="True"), m.Option(label="B", text="False")]
    assert true_false_key("A", _q(old_options=straight)) == "T"
    assert true_false_key("B", _q()) == "B"  # T/F made at extraction: no relabel map
    assert true_false_key("C", _q(old_options=REVERSED)) == "C"  # not an old label
    assert true_false_key("B", None) == "B"
    abcd = [m.Option(label=x, text=x) for x in "ABCD"]
    assert true_false_key("B", _q(options=abcd, old_options=REVERSED)) == "B"  # not T/F now
