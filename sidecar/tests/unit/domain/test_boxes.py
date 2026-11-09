"""resolve_answers over plan Appendix B.4 (R8.1.8) and the §5.1 failed-page row."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from support.guards import no_io  # noqa: F401

from etach.domain.boxes import (
    answer_path,
    clean_student,
    fits_form,
    pick_student,
    resolve_answers,
)
from etach.domain.models import OmittedSection, Option, Question, QuestionGroup, Section
from etach.domain.models import TestContent as Content
from etach.domain.models import TestMetadata as Meta
from etach.domain.working import PageAnswers
from etach.domain.working import TestDraft as Draft

pytestmark = pytest.mark.usefixtures("no_io")

T = 0.7
B1 = [
    ("II", 5, 14),
    ("III", 15, 16),
    ("IV", 17, 22),
    ("V", 23, 28),
    ("VI", 29, 34),
    ("VI", 35, 36),
    ("VIII", 37, 40),
]


@dataclass(frozen=True)
class FC:  # the shape of etach.llm.confidence.FieldConfidence that resolve_answers reads
    confidence: float
    low_trust: bool = False


def page_of(printed: int) -> int:
    return 1 if printed <= 16 else 2 if printed <= 30 else 3


#: Questions the tests read as free text; the others are choices (they are read as letters).
FREE_TEXT = {12, 15, 35, 36}


def q_type(printed: int) -> Any:
    return "word" if printed in FREE_TEXT else "choice"


def q_id(printed: int) -> str:
    return f"q{printed}"


def b1_draft(writing: bool = True) -> Draft:
    spec = [*B1, ("IX", 41, 41)] if writing else B1
    sections = []
    for s_no, (title, first, last) in enumerate(spec, 1):
        is_writing = title == "IX"
        qs = [
            Question(
                id=q_id(p),
                number=p - 4,
                printed_number=p,
                page_no=page_of(p),
                answer_form="writing" if is_writing else q_type(p),
                stem=f"stem {p}",
                options=None,
                cue=None,
                points=0.0 if is_writing else 0.25,
            )
            for p in range(first, last + 1)
        ]
        sections.append(
            Section(
                id=f"s{s_no}",
                number=s_no,
                printed_title=title,
                title=title,
                instructions="",
                points=0.25 * len(qs),
                points_source="printed",
                skill="grammar",
                graded=not is_writing,
                groups=[QuestionGroup(id=f"g{s_no}", stimulus=None, pictures=[], questions=qs)],
            )
        )
    omitted = [OmittedSection(title="I", questions=[1, 2, 3, 4], points=1.0)]
    if writing:
        omitted.append(OmittedSection(title="IX", questions=[41], points=1.0))
    return Draft(
        meta=Meta(occasion="FinalTerm", grade=8, omitted_sections=omitted),
        content=Content(sections=sections),
        fingerprint="",
        points_possible=9.0,
    )


def reading(
    printed: int, value: str | None, location: str = "written_in_blank", alt: str | None = None
) -> dict[str, Any]:
    return {
        "question_id": q_id(printed),
        "answer_form": "word",
        "value": value,
        "location": location,
        "alt_question_id": alt,
    }


def pages(
    readings: list[tuple[dict[str, Any], float]],
    name: str | None = None,
    on_page: dict[int, int] | None = None,
) -> tuple[list[PageAnswers], dict[int, dict[str, FC]]]:
    """``on_page``: reading index → the page it was read on (default: its question's page)."""
    by_page: dict[int, list[dict[str, Any]]] = {1: [], 2: [], 3: []}
    conf: dict[int, dict[str, FC]] = {1: {}, 2: {}, 3: {}}
    for i, (r, c) in enumerate(readings):
        page = (on_page or {}).get(i) or page_of(int(r["question_id"][1:]))
        index = sum(1 for x in by_page[page] if x["question_id"] == r["question_id"])
        by_page[page].append(r)
        conf[page][answer_path(r["question_id"], index)] = FC(c)
    out = [
        PageAnswers(
            page_no=p,
            answers=a,
            student_name=name if p == 2 else None,
            class_name="8A" if p == 3 else None,
        )
        for p, a in by_page.items()
    ]
    return out, conf


def b4_readings() -> list[tuple[dict[str, Any], float]]:
    rs: list[tuple[dict[str, Any], float]] = [
        (reading(p, "A", "circled_option"), 0.95) for p in range(5, 41) if p not in (10, 12, 35)
    ]
    rs += [
        (reading(10, "B", "circled_option"), 0.9),
        (reading(10, "C", "answer_box"), 0.92),
        (reading(12, "went", "written_in_blank"), 0.4),
        (reading(35, "electric fields", "written_in_blank", alt=q_id(36)), 0.95),
    ]
    return rs


def test_b4() -> None:
    pa, conf = pages(b4_readings(), name="Học Sinh A")
    out = resolve_answers(pa, conf, b1_draft(), threshold=T, ref="r1")
    by_id = {a.question_id: a for a in out.answers}
    # one answer per graded question; writing Q41 gets no row (B.1b)
    assert [a.question_id for a in out.answers] == [q_id(p) for p in range(5, 41)]
    assert q_id(41) not in by_id
    # box vs inline -> the box value + box_inline_conflict
    q10 = by_id[q_id(10)]
    assert (q10.value, q10.value_norm, q10.location, q10.alt_value) == ("C", "c", "answer_box", "B")
    assert [p.kind for p in out.pendings] == ["box_inline_conflict"]
    assert out.pendings[0].dedupe_key == f"box_inline_conflict:r1:{q_id(10)}"
    # a span near two questions -> t - 0.01, unsure, alt_question_id
    q35 = by_id[q_id(35)]
    assert q35.confidence == pytest.approx(0.69)
    assert q35.reading_unsure is True
    assert q35.alt_question_id == q_id(36)
    assert q35.value == "electric fields"
    # confidence 0.4 -> reading_unsure
    assert by_id[q_id(12)].reading_unsure is True
    assert by_id[q_id(12)].confidence == 0.4
    assert by_id[q_id(5)].reading_unsure is False
    assert out.blank is False
    assert (out.student_name, out.class_name) == ("Học Sinh A", "8A")


@pytest.mark.parametrize("alt", ["q99", "q35", "verbatim-string", "", "  ", q_id(41)])
def test_b1_invalid_alt_question_id_is_dropped(alt: str) -> None:
    """B1: ``alt_question_id`` is free text now; one that is not another readable question
    (unknown, the question itself, a template word, blank, the writing question) is dropped:
    no crash, no cap, None on the answer."""
    rs = [(reading(35, "electric fields", "written_in_blank", alt=alt), 0.95)]
    pa, conf = pages(rs)
    out = resolve_answers(pa, conf, b1_draft(), threshold=T, ref="r1")
    q35 = {a.question_id: a for a in out.answers}[q_id(35)]
    assert q35.alt_question_id is None
    assert q35.confidence == 0.95
    assert q35.reading_unsure is False
    assert q35.value == "electric fields"


def test_b1_valid_alt_question_id_is_stripped_and_kept() -> None:
    rs = [(reading(35, "electric fields", "written_in_blank", alt=f" {q_id(36)} "), 0.95)]
    pa, conf = pages(rs)
    out = resolve_answers(pa, conf, b1_draft(), threshold=T, ref="r1")
    q35 = {a.question_id: a for a in out.answers}[q_id(35)]
    assert q35.alt_question_id == q_id(36)
    assert q35.confidence == pytest.approx(T - 0.01)
    assert q35.reading_unsure is True


def test_all_answers_none_is_blank() -> None:
    pa, conf = pages([(reading(p, None, "none"), 0.9) for p in range(5, 41)])
    out = resolve_answers(pa, conf, b1_draft(), threshold=T)
    assert len(out.answers) == 36
    assert all(a.value is None and a.value_norm is None for a in out.answers)
    assert out.blank is True
    assert all(not a.reading_unsure for a in out.answers)


def test_no_readings_at_all() -> None:
    out = resolve_answers([], {}, b1_draft(), threshold=T)
    assert len(out.answers) == 36
    assert out.blank is True
    assert all(a.value is None and a.location == "none" for a in out.answers)


def test_value_norm_and_low_trust_carried() -> None:
    pa, conf = pages([(reading(15, "  Didn\u2019t   GO ", "written_in_blank"), 0.9)])
    conf[1][answer_path(q_id(15))] = FC(0.9, low_trust=True)
    out = resolve_answers(pa, conf, b1_draft(), threshold=T)
    a = next(a for a in out.answers if a.question_id == q_id(15))
    assert a.value == "  Didn\u2019t   GO "
    assert a.value_norm == "didn't go"
    assert a.low_trust is True
    assert a.page_no == 1


def test_box_and_inline_agree_no_conflict() -> None:
    pa, conf = pages(
        [(reading(10, "c", "circled_option"), 0.9), (reading(10, "C", "answer_box"), 0.8)]
    )
    out = resolve_answers(pa, conf, b1_draft(), threshold=T)
    q10 = next(a for a in out.answers if a.question_id == q_id(10))
    assert (q10.value, q10.alt_value, out.pendings) == ("C", None, [])


def test_failed_page() -> None:
    pa, conf = pages(b4_readings())
    out = resolve_answers(pa, conf, b1_draft(), threshold=T, failed_pages=[2], ref="r1")
    on_page_2 = [a for a in out.answers if page_of(a.printed_number) == 2]
    assert len(on_page_2) == 14
    assert all(a.value is None and a.reading_unsure for a in on_page_2)
    failed = [p for p in out.pendings if p.kind == "validator_failed"]
    assert len(failed) == 1
    assert failed[0].dedupe_key == "validator_failed:r1:answers:2"
    assert failed[0].proposal["page_no"] == 2
    assert len(out.answers) == 36


def test_all_pages_failed_is_not_blank() -> None:
    pa, conf = pages(b4_readings())
    out = resolve_answers(pa, conf, b1_draft(), threshold=T, failed_pages=[1, 2, 3], ref="r1")
    assert out.blank is False
    assert len(out.answers) == 36
    assert all(a.value is None and a.reading_unsure for a in out.answers)
    failed = [p for p in out.pendings if p.kind == "validator_failed"]
    assert [p.proposal["page_no"] for p in failed] == [1, 2, 3]
    assert len({p.dedupe_key for p in failed}) == 3
    assert out.pendings == failed


# --- the student's name and class ------------------------------------------------------------


def student_pages(*readings: tuple[str | None, str | None]) -> list[PageAnswers]:
    return [
        PageAnswers(page_no=i, answers=[], student_name=n, class_name=c)
        for i, (n, c) in enumerate(readings, start=1)
    ]


@pytest.mark.parametrize(
    "word", ["string", "verbatim-string", "Integer", "number", "date-time", "boolean", "None"]
)
def test_template_type_words_are_not_read(word: str) -> None:
    assert clean_student(word, word) == (None, None)
    assert pick_student(student_pages((word, word), ("Học Sinh A", "8A3"))) == (
        "Học Sinh A",
        "8A3",
    )


@pytest.mark.parametrize(
    ("name", "cls", "expected"),
    [
        ("15", "16", (None, None)),  # question numbers
        ("A", "B", (None, None)),  # one letter; an answer letter
        ("Học Sinh A", "8", ("Học Sinh A", None)),  # a class needs a letter
        ("Học Sinh A", "8TC11", ("Học Sinh A", "8TC11")),
    ],
)
def test_shape_rules(name: str, cls: str, expected: tuple[str | None, str | None]) -> None:
    assert clean_student(name, cls) == expected


def test_a_trailing_class_is_split_off_the_name() -> None:
    assert clean_student("Học Sinh A 8TC11", None) == ("Học Sinh A", "8TC11")
    assert clean_student("Học Sinh A 8TC11", "8tc11") == ("Học Sinh A", "8TC11")
    # a different class read on the page wins; the token is still dropped from the name
    assert clean_student("Học Sinh A 8TC11", "8A3") == ("Học Sinh A", "8A3")
    assert clean_student("Học Sinh A 8TC11", "verbatim-string") == ("Học Sinh A", "8TC11")
    assert clean_student("8TC11", None) == (None, None)


def test_agreement_across_pages_and_first_page_on_a_tie() -> None:
    pages = student_pages(
        ("Học Sinh B", "8A1"), ("Học Sinh A", "8A2"), ("Học Sinh A 8A2", "string")
    )
    assert pick_student(pages) == ("Học Sinh A", "8A2")
    tie = student_pages(("Học Sinh B", "8A1"), ("Học Sinh A", "8A2"))
    assert pick_student(tie) == ("Học Sinh B", "8A1")
    assert pick_student(student_pages((None, None), ("string", "15"))) == (None, None)


def test_resolve_answers_uses_the_agreed_student() -> None:
    pa, conf = pages(b4_readings(), name="Học Sinh A 8A")
    out = resolve_answers(pa, conf, b1_draft(), threshold=T, ref="r1")
    assert (out.student_name, out.class_name) == ("Học Sinh A", "8A")


# --- the step 11 hardening: disagreement, type check -------------------------------


def _by_id(out: Any) -> dict[str, Any]:
    return {a.question_id: a for a in out.answers}


def test_disagreeing_readings_are_unsure_with_the_runner_up() -> None:
    rs = [
        (reading(5, "D", "answer_box"), 0.95),  # page 1
        (reading(5, "A", "answer_box"), 0.9),  # page 2
        (reading(5, "a", "answer_box"), 0.8),  # page 3, the same value as page 2
        (reading(6, "B", "answer_box"), 0.95),
        (reading(6, "b", "answer_box"), 0.9),  # agrees after value_norm: no cap
    ]
    pa, conf = pages(rs, on_page={1: 2, 2: 3, 4: 2})
    by_id = _by_id(resolve_answers(pa, conf, b1_draft(), threshold=T))
    q5 = by_id[q_id(5)]
    assert (q5.value, q5.alt_value, q5.reading_unsure) == ("D", "A", True)
    assert q5.confidence == pytest.approx(0.69)
    q6 = by_id[q_id(6)]
    assert (q6.value, q6.alt_value, q6.reading_unsure, q6.confidence) == ("B", None, False, 0.95)
    # two inline readings on the question's own page that disagree
    pa, conf = pages(
        [(reading(7, "B", "circled_option"), 0.9), (reading(7, "C", "written_in_blank"), 0.8)]
    )
    q7 = _by_id(resolve_answers(pa, conf, b1_draft(), threshold=T))[q_id(7)]
    assert (q7.value, q7.alt_value, q7.reading_unsure) == ("B", "C", True)


def _form_q(form: Any, labels: str | None = None) -> Question:
    options = None if labels is None else [Option(label=x, text=f"opt {x}") for x in labels]
    return Question(
        id="q",
        number=1,
        printed_number=1,
        page_no=1,
        answer_form=form,
        stem="s",
        options=options,
        cue=None,
        points=0.25,
    )


@pytest.mark.parametrize(
    ("form", "labels", "value", "ok"),
    [
        ("choice", "ABCD", "B", True),
        ("choice", "ABCD", "b.", True),
        ("choice", "ABCD", "(C)", True),
        ("choice", "ABCD", "E", False),
        ("choice", "ABCD", "went", False),
        ("choice", "ABCD", "T", False),
        ("choice", None, "D", True),  # no options: A-D
        ("choice", None, "T", False),
        ("choice", "ABC", "D", False),  # only its own labels (step 22.5.3)
        ("choice", "TF", "F", True),  # True/False: the options the code adds
        ("choice", "TF", "t", True),
        ("choice", "TF", "A", False),
        ("word", None, "provision", True),
        ("word", None, "B", False),
        ("sentence", None, "D", False),
        ("word", None, "F", False),
        ("word", None, "a", True),  # the article
        ("word", None, "An", True),
        ("sentence", None, "He has lived here.", True),
        ("word", None, "???", True),  # unreadable: kept whatever the form
        ("choice", "ABCD", "???", True),
    ],
)
def test_fits_form(form: str, labels: str | None, value: str, ok: bool) -> None:
    assert fits_form(_form_q(form, labels), value) is ok


def test_wrong_type_values_are_dropped() -> None:
    rs = [
        (reading(35, "C", "answer_box"), 0.95),  # gap_fill: a bare letter is no answer
        (reading(36, "B", "answer_box"), 0.95),
        (reading(36, "electric power", "written_in_blank"), 0.9),  # the valid one is kept
        (reading(8, "went", "answer_box"), 0.95),  # mcq: not a letter
    ]
    pa, conf = pages(rs)
    out = resolve_answers(pa, conf, b1_draft(), threshold=T, ref="r1")
    by_id = _by_id(out)
    assert (by_id[q_id(35)].value, by_id[q_id(35)].reading_unsure) == (None, True)
    q36 = by_id[q_id(36)]
    assert (q36.value, q36.alt_value, q36.reading_unsure) == ("electric power", None, False)
    assert (by_id[q_id(8)].value, by_id[q_id(8)].reading_unsure) == (None, True)
    assert out.pendings == []  # the dropped box value raises no box_inline_conflict
