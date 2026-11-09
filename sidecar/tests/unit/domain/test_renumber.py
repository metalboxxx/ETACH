"""merge_pages + renumber: R8.1.1 (Appendix B.1), R8.1.2, B.1b. Pure (no_io)."""

from __future__ import annotations

from typing import Any

import pytest
from support.guards import assert_pure, no_io  # noqa: F401

from etach.domain.llm_schemas import TranscribeOut
from etach.domain.models import FORM_OF_OLD_TYPE, Option, true_false_letters
from etach.domain.models import TestContent as Content
from etach.domain.renumber import (
    choice_options,
    fingerprint_text,
    merge_pages,
    page_transcript,
    parse_points,
    question_id,
)
from etach.domain.working import PageTranscript

pytestmark = pytest.mark.usefixtures("no_io")

PAGE_FILES = {1: "a1" * 32, 2: "b2" * 32, 3: "c3" * 32}


def q(n: int, type_: str = "gap_fill") -> dict[str, Any]:
    if type_ == "mcq":
        return {
            "printed_number": n,
            "answer_form": "choice",
            "stem": f"Question {n} stem",
            "options": [{"label": x, "text": f"opt {x}"} for x in "ABCD"],
            "cue": None,
        }
    return {
        "printed_number": n,
        "answer_form": FORM_OF_OLD_TYPE.get(type_, type_),
        "stem": f"Sentence {n} with ____ here",
        "options": None,
        "cue": None,
    }


def sec(
    title: str,
    numbers: range,
    points: str | None,
    kind: str = "questions",
    type_: str = "gap_fill",
    pictures: int = 0,
) -> dict[str, Any]:
    if kind == "listening":
        return {
            "printed_title": title,
            "instructions": "Listen and choose.",
            "kind": "listening",
            "skill": "mixed",
            "points_text": points,
            "range_first": numbers.start,
            "range_last": numbers.stop - 1,
            "groups": [],
        }
    return {
        "printed_title": title,
        "instructions": f"Instructions for {title}",
        "kind": kind,
        "skill": "writing" if kind == "writing" else "grammar",
        "points_text": points,
        "range_first": None,
        "range_last": None,
        "groups": [
            {
                "stimulus": None,
                "pictures": [{"x0": 0, "y0": 0, "x1": 10, "y1": 10}] * pictures,
                "questions": [q(n, type_) for n in numbers],
            }
        ],
    }


def page(no: int, sections: list[dict[str, Any]], header: str | None = None) -> PageTranscript:
    out = TranscribeOut.model_validate({"header_text": header, "sections": sections})
    return page_transcript(no, out, f"call-{no}")


def b1_pages(writing: bool = False) -> list[PageTranscript]:
    p3 = [sec("VI", range(35, 37), "(0.5 pts)"), sec("VIII", range(37, 41), "1.0 point")]
    if writing:
        p3.append(sec("IX", range(41, 42), "(1.0 pt)", kind="writing", type_="writing"))
    return [
        page(
            1,
            [
                sec("I", range(1, 5), "(1.0 pt)", kind="listening"),
                sec("II", range(5, 15), "(2.5 pts)", type_="mcq"),
                sec("III", range(15, 17), "(0,5 điểm)"),
            ],
            header="ĐỀ CUỐI KÌ I LỚP 8 (K)",
        ),
        page(
            2,
            [
                sec("IV", range(17, 23), "1.5 points"),
                sec("V", range(23, 29), "(1.5pts)", pictures=1),
                sec("VI", range(29, 32), "(1.5 pts)"),
            ],
        ),
        # page 3 starts with the continuation of VI (no points reprinted), then the duplicate VI
        page(3, [sec("VI", range(32, 35), None), *p3]),
    ]


def test_r8_1_1_b1_renumber() -> None:
    res = merge_pages(b1_pages(), page_files=PAGE_FILES, ref="R-1", filename="Lop8-HKI-De1 (1).jpg")
    d = res.draft
    omitted = d.meta.omitted_sections
    assert [(o.title, o.questions, o.points) for o in omitted] == [("I", [1, 2, 3, 4], 1.0)]
    secs = d.content.sections
    assert [s.number for s in secs] == [1, 2, 3, 4, 5, 6, 7]
    # D2 (v1.21): a bare numeral takes the section skill as its title
    titles = ["II", "III", "IV", "V", "VI", "VI", "VIII"]
    assert [s.printed_title for s in secs] == [f"{t}. GRAMMAR" for t in titles]
    qs = [x for s in secs for g in s.groups for x in g.questions]
    assert [x.number for x in qs] == list(range(1, 37))
    assert [x.printed_number for x in qs] == list(range(5, 41))
    assert all(x.number == x.printed_number - 4 for x in qs)
    # PRD D13 v8.0: printed points are not used; every graded question is worth 10 / 36
    assert all(x.points == 10 / 36 for x in qs)
    assert [s.points for s in secs] == [round(n * 10 / 36, 6) for n in (10, 2, 6, 6, 6, 2, 4)]
    assert all(s.points_source == "equal" and s.graded for s in secs)
    assert d.points_possible == 10.0
    assert len({x.id for x in qs}) == 36
    assert all(x.id.startswith("q-") and len(x.id) == 10 for x in qs)
    # page_no comes from the page the question appeared on
    by_printed = {x.printed_number: x.page_no for x in qs}
    assert by_printed[14] == 1 and by_printed[17] == 2 and by_printed[31] == 2
    assert by_printed[32] == 3 and by_printed[40] == 3
    # section V's picture points at page 2's image
    v = secs[3]
    assert [(p.file_id, p.page_no) for g in v.groups for p in g.pictures] == [(PAGE_FILES[2], 2)]
    assert res.pendings == []
    assert res.failures == []
    assert d.meta.occasion == "FinalTerm" and d.meta.grade == 8
    assert d.fingerprint == fingerprint_text(d.content)


def test_ids_deterministic() -> None:
    a = merge_pages(b1_pages(), page_files=PAGE_FILES, ref="R-1").draft
    b = merge_pages(b1_pages(), page_files=PAGE_FILES, ref="R-1").draft
    assert a.model_dump() == b.model_dump()


def test_b1b_writing_variant() -> None:
    res = merge_pages(b1_pages(writing=True), page_files=PAGE_FILES, ref="R-1")
    d = res.draft
    secs = d.content.sections
    assert len(secs) == 8
    assert secs[7].number == 8 and not secs[7].graded and secs[7].printed_title == "IX. WRITING"
    assert [(o.title, o.questions, o.points) for o in d.meta.omitted_sections] == [
        ("I", [1, 2, 3, 4], 1.0),
        ("IX", [41], 1.0),
    ]
    assert d.points_possible == 10.0
    assert secs[7].points == 0.0  # writing counts for nothing
    wq = secs[7].groups[0].questions[0]
    assert (wq.number, wq.printed_number) == (37, 41)
    assert res.failures == []


def test_writing_numbered_after_graded_questions() -> None:
    pages = [
        page(
            1,
            [
                sec("I", range(1, 3), "(0.5 pt)"),
                sec("II", range(3, 4), None, kind="writing", type_="writing"),
                sec("III", range(4, 6), "(0.5 pt)"),
            ],
        )
    ]
    d = merge_pages(pages, page_files=PAGE_FILES).draft
    nums = [
        (x.printed_number, x.number)
        for s in d.content.sections
        for g in s.groups
        for x in g.questions
    ]
    assert nums == [(1, 1), (2, 2), (3, 5), (4, 3), (5, 4)]
    assert d.points_possible == 10.0
    assert [s.points for s in d.content.sections] == [5.0, 0.0, 5.0]


def test_no_points_assumed_item_and_equal_points() -> None:
    """v1.19: a section with no printed points gets the equal points; no points_assumed item."""
    pages = [page(1, [sec("I", range(1, 5), "(1 pt)"), sec("II", range(5, 9), None)])]
    res = merge_pages(pages, page_files=PAGE_FILES, ref="R-7")
    s1, s2 = res.draft.content.sections
    assert s1.points_source == s2.points_source == "equal"
    assert all(x.points == 1.25 for s in (s1, s2) for g in s.groups for x in g.questions)
    assert s1.points == s2.points == 5.0
    assert [p for p in res.pendings if p.kind == "points_assumed"] == []
    assert res.draft.points_possible == 10.0


def test_empty_title_continues_previous_section() -> None:
    pages = [
        page(1, [sec("I", range(1, 3), "(1 pt)")]),
        page(2, [sec("", range(3, 5), None), sec("II", range(5, 6), "(0.25 pt)")]),
    ]
    d = merge_pages(pages, page_files=PAGE_FILES).draft
    assert [s.printed_title for s in d.content.sections] == ["I. GRAMMAR", "II. GRAMMAR"]
    first = d.content.sections[0]
    assert [x.page_no for g in first.groups for x in g.questions] == [1, 1, 2, 2]
    assert all(x.points == 2.0 for g in first.groups for x in g.questions)  # 10 / 5


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("(2.5 pts)", 2.5),
        ("(2,5 điểm)", 2.5),
        ("2.5 points", 2.5),
        ("1đ", 1.0),
        ("(1.0 point)", 1.0),
        ("(1.5pts)", 1.5),
        ("(0.5 pt)", 0.5),
        ("(2 marks?)", None),
        (None, None),
        ("", None),
    ],
)
def test_parse_points(text: str | None, value: float | None) -> None:
    assert parse_points(text) == value


def test_question_id_collision_resolved() -> None:
    pages = [page(1, [sec("I", range(1, 2), "(0.5 pt)")])]
    raw = pages[0].sections[0]["groups"][0]["questions"]
    raw.append(dict(raw[0]))  # the same printed number and stem twice
    pages[0].sections[0]["groups"][0]["questions"] = raw
    d = merge_pages(pages, page_files=PAGE_FILES).draft
    ids = [x.id for g in d.content.sections[0].groups for x in g.questions]
    assert ids[0] == question_id(1, 1, raw[0]["stem"])
    assert ids[1] == question_id(1, 1, raw[0]["stem"], 1)
    assert ids[0] != ids[1]


def test_fingerprint_text_normalized() -> None:
    content = Content.model_validate(
        {
            "sections": [
                {
                    "id": "s-1",
                    "number": 1,
                    "printed_title": "I",
                    "title": "I",
                    "instructions": "  Choose   the **best** answer ",
                    "points": 0.25,
                    "points_source": "printed",
                    "skill": "grammar",
                    "groups": [
                        {
                            "id": "g-1",
                            "stimulus": None,
                            "pictures": [],
                            "questions": [
                                {
                                    "id": "q-1",
                                    "number": 1,
                                    "printed_number": 1,
                                    "page_no": 1,
                                    "answer_form": "choice",
                                    "stem": "He <u>doesn" + chr(0x2019) + "t</u> go",
                                    "options": [{"label": "A", "text": "Yes"}],
                                    "cue": None,
                                    "points": 0.25,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )
    assert fingerprint_text(content) == "choose the best answer he doesn't go yes"


def test_renumber_is_pure() -> None:
    assert_pure("etach.domain.renumber")


# --- listening safety net (llm-design §4, M1) ---------------------------------------------


def misread_listening(
    title: str, numbers: range, points: str | None, *, options_only: bool = False
) -> dict[str, Any]:
    """A section the model labelled ``listening`` although it holds question bodies."""
    out = sec(title, numbers, points, type_="mcq")
    out["kind"] = "listening"
    out["range_first"], out["range_last"] = numbers.start, numbers.stop - 1
    if options_only:
        for x in out["groups"][0]["questions"]:
            x["stem"] = None
    return out


def listening_items(res: Any) -> list[Any]:
    return [p for p in res.pendings if p.kind == "validator_failed"]


@pytest.mark.parametrize("options_only", [False, True])
def test_listening_with_questions_is_stored(options_only: bool) -> None:
    pages = [
        page(
            1,
            [
                misread_listening("I", range(1, 5), "(1.0 pt)", options_only=options_only),
                sec("II", range(5, 7), "(0.5 pts)"),
            ],
        )
    ]
    res = merge_pages(pages, page_files=PAGE_FILES, ref="R-1")
    d = res.draft
    assert d.meta.omitted_sections == []
    secs = d.content.sections
    assert [(s.printed_title, s.graded) for s in secs] == [
        ("I. GRAMMAR", True),
        ("II. GRAMMAR", True),
    ]
    qs = [x for s in secs for g in s.groups for x in g.questions]
    assert [x.printed_number for x in qs] == list(range(1, 7))
    assert [x.number for x in qs] == list(range(1, 7))
    assert d.points_possible == 10.0
    items = listening_items(res)
    assert len(items) == 1
    item = items[0]
    assert item.dedupe_key == "validator_failed:R-1:listening:1"
    assert item.refs == {"page_no": 1}
    assert item.proposal["task"] == "transcribe_page"
    assert item.proposal["reason"] == "listening_with_questions"
    assert item.proposal["page_no"] == 1
    assert item.proposal["call_failure"] is None
    assert [f["validator"] for f in item.proposal["failures"]] == ["listening_with_questions"]
    assert item.proposal["sections"] == [
        {"section_id": secs[0].id, "section_number": 1, "printed_title": "I", "questions": 4}
    ]
    assert [p.kind for p in res.pendings if p.kind != "unknown_occasion"] == ["validator_failed"]


def test_listening_heading_only_is_omitted() -> None:
    empty_questions = sec("III", range(9, 11), "(0.5 pts)", kind="listening")
    empty_questions["groups"] = [{"stimulus": None, "pictures": [], "questions": []}]
    blank_body = misread_listening("IV", range(11, 13), None)
    for x in blank_body["groups"][0]["questions"]:
        x["stem"], x["options"] = "  ", None
    pages = [
        page(
            1,
            [
                sec("I", range(1, 5), "(1.0 pt)", kind="listening"),
                sec("II", range(5, 9), "(1.0 pt)"),
                empty_questions,
                blank_body,
            ],
        )
    ]
    res = merge_pages(pages, page_files=PAGE_FILES, ref="R-1")
    omitted = res.draft.meta.omitted_sections
    assert [(o.title, o.questions, o.points) for o in omitted] == [
        ("I", [1, 2, 3, 4], 1.0),
        ("III", [9, 10], 0.5),
        ("IV", [11, 12], 0.0),
    ]
    assert [s.printed_title for s in res.draft.content.sections] == ["II. GRAMMAR"]
    assert listening_items(res) == []


def test_rescued_section_first_keeps_numbering() -> None:
    """B.1 with section I misread as listening-with-questions: it is numbered 1..4 like any
    graded section, and the rest follow in order."""
    pages = b1_pages()
    pages[0] = page(
        1,
        [
            misread_listening("I", range(1, 5), "(1.0 pt)"),
            sec("II", range(5, 15), "(2.5 pts)", type_="mcq"),
            sec("III", range(15, 17), "(0,5 điểm)"),
        ],
        header="ĐỀ CUỐI KÌ I LỚP 8 (K)",
    )
    res = merge_pages(pages, page_files=PAGE_FILES, ref="R-1")
    d = res.draft
    assert d.meta.omitted_sections == []
    secs = d.content.sections
    assert [s.number for s in secs] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert secs[0].printed_title == "I. GRAMMAR" and secs[0].graded
    qs = [x for s in secs for g in s.groups for x in g.questions]
    assert [x.number for x in qs] == list(range(1, 41))
    assert [x.printed_number for x in qs] == list(range(1, 41))
    assert d.points_possible == 10.0
    assert res.failures == []
    assert [p.dedupe_key for p in res.pendings] == ["validator_failed:R-1:listening:1"]


def test_listening_dedupe_key_stable() -> None:
    """Same key across merge passes, and across a pass that adds a section before it on the
    same page (the key is the start page, not the section index)."""

    def run(extra_first: bool) -> list[str]:
        sections = [misread_listening("III", range(5, 9), "(1.0 pt)")]
        if extra_first:
            sections.insert(0, sec("II", range(1, 5), "(1.0 pt)"))
        pages = [page(1, [sec("I", range(1, 1), None)]), page(2, sections)]
        res = merge_pages(pages, page_files=PAGE_FILES, ref="R-7")
        return [p.dedupe_key for p in listening_items(res)]

    assert run(False) == run(False) == run(True) == ["validator_failed:R-7:listening:2"]


def test_two_rescued_sections_on_one_page_share_one_item() -> None:
    pages = [
        page(
            1,
            [
                misread_listening("I", range(1, 3), "(0.5 pts)"),
                misread_listening("II", range(3, 5), "(0.5 pts)"),
            ],
        )
    ]
    res = merge_pages(pages, page_files=PAGE_FILES, ref="R-1")
    items = listening_items(res)
    assert len(items) == 1
    assert [s["printed_title"] for s in items[0].proposal["sections"]] == ["I", "II"]
    assert len(items[0].proposal["failures"]) == 2


@pytest.mark.parametrize(
    "text",
    [
        "Read the passage and decide True or False.",
        "Write True/False.",
        "TRUE / FALSE",
        "Write T or F.",
        "Write T OR F next to each statement.",
        "Write T/F.",
        "(T/F)",
        "T \u2013 F",
        "T\u2014F",
        "T - F",
        "Viết T hay F.",
        "Viết T hoặc F vào chỗ trống.",
        "Đúng (T) hay Sai (F)?",
        "Ghi Đúng/Sai.",
        "đúng hay sai",
        "Write (T) for true statements and (F) for false ones.",
    ],
)
def test_choice_options_true_false_wording(text: str) -> None:
    """Step 22.5.3 fix: the ways Vietnamese school tests print True/False give a ``choice``
    without options the two options T and F."""
    opts = choice_options("choice", None, text)
    assert opts is not None
    assert [o.label for o in opts] == ["T", "F"]


@pytest.mark.parametrize(
    "text",
    [
        "Choose the best answer A, B, C or D.",
        "Chọn đáp án đúng nhất.",
        "Tom went to the park, and his friend Fred stayed at home.",
        "T is the first letter of the word. F is the last.",
        "I can't or for sure won't go.",
        "She bought a T-shirt for Fred.",
        "Write the correct form of the word.",
        "",
    ],
)
def test_choice_options_ordinary_text_does_not_match(text: str) -> None:
    assert choice_options("choice", None, text) is None


def test_choice_options_only_for_a_choice_without_options() -> None:
    assert choice_options("word", None, "Write T or F.") is None
    assert choice_options("choice", None, None, "Write T or F.") is not None


# --- checklist (d), R22.5.3.8: True/False options the model lettered -----------------------------


def _opts(*pairs: tuple[str, str]) -> list[Option]:
    return [Option(label=label, text=text) for label, text in pairs]


@pytest.mark.parametrize(
    ("pairs", "want"),
    [
        ((("A", "True"), ("B", "False")), {"A": "T", "B": "F"}),
        ((("A", "FALSE"), ("B", "TRUE")), {"A": "F", "B": "T"}),
        ((("A", "True."), ("B", "False")), {"A": "T", "B": "F"}),
        ((("A", " true! "), ("B", "false;")), {"A": "T", "B": "F"}),
        ((("A", "Đúng"), ("B", "Sai")), {"A": "T", "B": "F"}),
        ((("A", "SAI"), ("B", "ĐÚNG")), {"A": "F", "B": "T"}),
        ((("T", "True"), ("F", "False")), {"T": "T", "F": "F"}),
    ],
)
def test_r22_5_3_8_true_false_letters(
    pairs: tuple[tuple[str, str], ...], want: dict[str, str]
) -> None:
    assert true_false_letters(list(pairs)) == want
    got = choice_options("choice", _opts(*pairs), "Choose A or B.")
    assert [(o.label, o.text) for o in got or []] == [("T", "True"), ("F", "False")]


@pytest.mark.parametrize(
    "pairs",
    [
        (("A", "yes"), ("B", "no")),
        (("A", "True"), ("B", "True")),
        (("A", "True"), ("B", "Sai")),
        (("A", "True"), ("B", "False"), ("C", "Not given")),
        (("A", "True"), ("B", "False"), ("C", "both"), ("D", "neither")),
        (("A", "It is true"), ("B", "It is false")),
    ],
)
def test_r22_5_3_8_other_options_unchanged(pairs: tuple[tuple[str, str], ...]) -> None:
    assert true_false_letters(list(pairs)) is None
    options = _opts(*pairs)
    assert choice_options("choice", options, "Write True or False.") == options


def test_r22_5_3_8_word_with_true_false_options_unchanged() -> None:
    options = _opts(("A", "True"), ("B", "False"))
    assert choice_options("word", options) == options


def test_r22_5_3_8_merge_gives_t_f_for_lettered_true_false() -> None:
    """Extraction: a page whose True/False questions the model gave as ``A. FALSE``,
    ``B. TRUE`` (G1, Test G q17-20) comes out of the merge with ``T. True``, ``F. False``."""
    s = sec("IV", range(17, 21), "(1.0 pt)", type_="mcq")
    for item in s["groups"][0]["questions"]:
        item["options"] = [{"label": "A", "text": "FALSE"}, {"label": "B", "text": "TRUE"}]
    d = merge_pages([page(1, [s])], page_files=PAGE_FILES).draft
    qs = [x for g in d.content.sections[0].groups for x in g.questions]
    assert len(qs) == 4
    for x in qs:
        assert [(o.label, o.text) for o in x.options or []] == [("T", "True"), ("F", "False")]
