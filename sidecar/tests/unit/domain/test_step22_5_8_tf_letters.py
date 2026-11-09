"""Step 22.5.8 (a)(5): a True/False choice printed as ``A. FALSE`` / ``B. TRUE`` and relabelled
T/F at extraction keeps its options as read in ``old_options``, so a key-photo letter and a
student's letter are stored as T/F (R22.5.8.1). Synthetic data only."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from support.guards import no_io  # noqa: F401

from etach.domain.boxes import resolve_answers
from etach.domain.keymap import map_key
from etach.domain.models import Option, Question, QuestionGroup, Section
from etach.domain.models import TestContent as Content
from etach.domain.models import TestMetadata as Meta
from etach.domain.renumber import choice_options, relabelled_from
from etach.domain.working import PageAnswers
from etach.domain.working import TestDraft as Draft

pytestmark = pytest.mark.usefixtures("no_io")

REVERSED = [Option(label="A", text="FALSE"), Option(label="B", text="TRUE")]
TF = [Option(label="T", text="True"), Option(label="F", text="False")]
ABCD = [Option(label=x, text=f"opt {x}") for x in "ABCD"]


@dataclass(frozen=True)
class FC:  # the shape of etach.llm.confidence.FieldConfidence that resolve_answers reads
    confidence: float
    low_trust: bool = False


def _q(qid: str, n: int, options: list[Option], old: list[Option] | None) -> Question:
    return Question(
        id=qid,
        number=n,
        printed_number=n,
        page_no=1,
        answer_form="choice",
        stem=f"stem {n}",
        options=options,
        cue=None,
        points=0.25,
        old_options=old,
    )


def _draft() -> Draft:
    qs = [_q("q1", 1, TF, REVERSED), _q("q2", 2, ABCD, None)]
    section = Section(
        id="s1",
        number=1,
        printed_title="I",
        title="I",
        instructions="",
        points=0.5,
        points_source="printed",
        skill="reading",
        groups=[QuestionGroup(id="g1", stimulus=None, pictures=[], questions=qs)],
    )
    return Draft(
        meta=Meta(occasion="FinalTerm", grade=8),
        content=Content(sections=[section]),
        fingerprint="",
        points_possible=0.5,
    )


def test_relabelled_at_extraction_keeps_the_options_as_read() -> None:
    options = choice_options("choice", REVERSED, "", "stem")
    assert [o.label for o in options or []] == ["T", "F"]
    assert relabelled_from(REVERSED, options) == REVERSED
    # nothing relabelled: no old options
    assert relabelled_from(ABCD, choice_options("choice", ABCD, "", "s")) is None
    assert relabelled_from(TF, choice_options("choice", TF, "", "s")) is None
    assert relabelled_from(None, choice_options("choice", None, "True or False?", "s")) is None


def test_key_photo_letter_on_a_relabelled_true_false_is_stored_as_tf() -> None:
    out = map_key([("1", "B"), ("2", "B")], _draft(), threshold=0.7, ref="r1")
    got = {e.question_id: e.accepted for e in out.entries}
    assert got == {"q1": ["T"], "q2": ["B"]}


@pytest.mark.parametrize(("read", "stored"), [("B", "T"), ("a", "F"), ("T", "T")])
def test_student_letter_on_a_relabelled_true_false_is_read_as_tf(read: str, stored: str) -> None:
    pa = [
        PageAnswers(
            page_no=1,
            student_name=None,
            class_name=None,
            answers=[
                {"question_id": "q1", "value": read, "location": "circled_option"},
                {"question_id": "q2", "value": "B", "location": "circled_option"},
            ],
        )
    ]
    conf = {1: {"answers.q1[0].value": FC(0.9), "answers.q2[0].value": FC(0.9)}}
    by_id = {a.question_id: a for a in resolve_answers(pa, conf, _draft(), threshold=0.7).answers}
    assert by_id["q1"].value == stored
    assert by_id["q2"].value == "B"
