"""Step 21a (PRD D25): ``???`` in the extraction logic (validators, ``merge_and_normalize``'s
per-page ``unreadable_text`` pendings, ``resolve_answers``). The replay checks are in
``tests/replay/test_unreadable_replay.py``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from etach.domain.boxes import answer_path, fits_form, resolve_answers
from etach.domain.models import Option, Question, QuestionGroup
from etach.domain.renumber import merge_pages
from etach.domain.validators import validate_choice, validate_word_blank
from etach.domain.working import PageAnswers, PageTranscript

T = 0.7


def _q(qtype: str, stem: str | None, labels: str = "ABCD") -> Question:
    return Question(
        id="q-1",
        number=1,
        printed_number=1,
        page_no=1,
        answer_form=qtype,  # type: ignore[arg-type]
        stem=stem,
        options=[Option(label=x, text=x.lower()) for x in labels] if qtype == "choice" else None,
        cue=None,
        points=0.25,
    )


GROUP = QuestionGroup(id="g", stimulus=None, pictures=[], questions=[])


def test_validators_accept_unreadable_text() -> None:
    assert validate_word_blank(_q("word", "She ??? to school."), GROUP) == []
    assert validate_word_blank(_q("word", "She went to school."), GROUP) != []
    mcq = _q("choice", "x")
    mcq.options = [Option(label=x, text="t") for x in ("A", "???", "C", "D")]
    assert validate_choice(mcq) == []
    mcq.options = [Option(label=x, text="t") for x in ("A", "Z", "C", "D")]
    assert validate_choice(mcq) != []


def _page(page_no: int, *, stem: str, instructions: str = "Choose.") -> PageTranscript:
    opts = [{"label": x, "text": x.lower()} for x in "ABCD"]
    return PageTranscript(
        page_no=page_no,
        header_text=None,
        llm_call_id=f"c{page_no}",
        sections=[
            {
                "printed_title": ["I", "II", "III"][page_no - 1],
                "instructions": instructions,
                "kind": "questions",
                "skill": "grammar",
                "points_text": None,
                "range_first": None,
                "range_last": None,
                "groups": [
                    {
                        "stimulus": None,
                        "pictures": [],
                        "questions": [
                            {
                                "printed_number": page_no,
                                "answer_form": "choice",
                                "stem": stem,
                                "options": opts,
                                "cue": None,
                            }
                        ],
                    }
                ],
            }
        ],
    )


FILES = {1: "f1", 2: "f2", 3: "f3"}


def test_one_pending_per_page_with_unreadable_text() -> None:
    pages = [
        _page(1, stem="Stem ??? one", instructions="Choose ??? answer."),
        _page(2, stem="Stem two"),
        _page(3, stem="??? three"),
    ]
    out = merge_pages(pages, page_files=FILES, ref="r1")
    assert out.failures == []  # ??? is valid text
    items = [p for p in out.pendings if p.kind == "unreadable_text"]
    assert [p.proposal["page_no"] for p in items] == [1, 3]
    assert [p.dedupe_key for p in items] == ["unreadable_text:r1:p1", "unreadable_text:r1:p3"]
    p1 = items[0].proposal
    assert p1["file_id"] == "f1"
    qid = out.draft.content.sections[0].groups[0].questions[0].id
    stem = "sections[0].groups[0].questions[0].stem"
    assert p1["spans"] == [
        {"path": "sections[0].instructions", "question_id": None, "text": "Choose ??? answer."},
        {"path": stem, "question_id": qid, "text": "Stem ??? one"},
    ]
    assert items[1].proposal["file_id"] == "f3"
    assert [s["path"] for s in items[1].proposal["spans"]] == [
        "sections[2].groups[0].questions[0].stem"
    ]


def test_pendings_are_recomputed_on_every_pass() -> None:
    """A page that ``retranscribe_tiles`` read fully gets none (the next merge pass)."""
    first = merge_pages([_page(1, stem="Stem ??? one")], page_files=FILES, ref="r1")
    assert [p.kind for p in first.pendings if p.kind == "unreadable_text"] == ["unreadable_text"]
    again = merge_pages([_page(1, stem="Stem one")], page_files=FILES, ref="r1")
    assert [p for p in again.pendings if p.kind == "unreadable_text"] == []


@dataclass
class FC:
    confidence: float
    low_trust: bool = False


@pytest.mark.parametrize(
    ("qtype", "value"),
    [("choice", "???"), ("word", "beauti???"), ("sentence", "He ??? here."), ("word", "???")],
)
def test_unreadable_answer_is_kept_and_unsure(qtype: str, value: str) -> None:
    from etach.domain.models import Section, TestContent, TestMetadata
    from etach.domain.working import TestDraft

    q = _q(qtype, "Stem ____")
    section = Section(
        id="s",
        number=1,
        printed_title="I",
        title="I",
        instructions="x",
        points=0.25,
        points_source="printed",
        skill="grammar",
        groups=[QuestionGroup(id="g", stimulus=None, pictures=[], questions=[q])],
    )
    draft = TestDraft(
        meta=TestMetadata(occasion="Other:unknown"),
        content=TestContent(sections=[section]),
        fingerprint="",
        points_possible=0.25,
    )
    reading: dict[str, Any] = {
        "question_id": q.id,
        "type": qtype,
        "value": value,
        "location": "written_in_blank",
        "alt_question_id": None,
    }
    page = PageAnswers(page_no=1, answers=[reading], student_name=None, class_name=None)
    assert fits_form(q, value)
    out = resolve_answers([page], {1: {answer_path(q.id): FC(0.99)}}, draft, threshold=T)
    (a,) = out.answers
    assert a.value == value  # kept as read
    assert a.reading_unsure is True
    assert a.confidence == pytest.approx(T - 0.01)
    assert out.blank is False
