"""Step 22.5.6 verifier fix (D12, R22.5.6.1): a passage question gets the page its text starts
on (its in-passage marker, else its passage), and a numbered list in a passage does not capture
the questions after it. The cases come from the verifier's probes; every text is synthetic."""

from __future__ import annotations

import random

import pytest

from etach.domain.llm_schemas import TranscribeOut
from etach.store.documents import TextPiece, locate_pages


def q(
    n: int, stem: str | None, options: list[str] | None = None, cue: str | None = None
) -> dict[str, object]:
    return {
        "printed_number": n,
        "answer_form": "choice" if options else "word",
        "stem": stem,
        "options": None
        if options is None
        else [{"label": "ABCD"[i], "text": t} for i, t in enumerate(options)],
        "cue": cue,
    }


def sec(title: str, groups: list[dict[str, object]], ins: str = "Do it.") -> dict[str, object]:
    return {
        "printed_title": title, "instructions": ins, "kind": "questions", "skill": "grammar",
        "points_text": None, "range_first": None, "range_last": None, "groups": groups,
    }  # fmt: skip


def grp(
    questions: list[dict[str, object]], stimulus: str | None = None, pictures: bool = False
) -> dict[str, object]:
    boxes = [{"x0": 0, "y0": 0, "x1": 5, "y1": 5}] if pictures else []
    return {"stimulus": stimulus, "pictures": boxes, "questions": questions}


def piece(pages: list[list[str]], pictures: tuple[int, ...] = ()) -> TextPiece:
    texts = ["\n".join(p) for p in pages]
    starts = []
    offset = 0
    for i, t in enumerate(texts):
        starts.append((offset, i))
        offset += len(t) + 1
    return TextPiece("\n".join(texts), tuple(starts), pictures)


def locate(
    pages: list[list[str]], sections: list[dict[str, object]], pictures: tuple[int, ...] = ()
) -> tuple[list[int], list[int]]:
    out = TranscribeOut.model_validate({"header_text": None, "sections": sections})
    return locate_pages(piece(pages, pictures), out.sections)


# --- locating questions (fix 1) -------------------------------------------------------------------


def test_open_cloze_on_page_2_after_a_section_ending_on_page_1() -> None:
    groups, questions = locate(
        [
            ["I. Choose.", "15. a ____ b", "16. c ____ d"],
            ["II. Fill the gaps.", "My town is (17) ____ and the people are (18) ____ friendly.",
             "There are (19) ____ parks."],
        ],
        [
            sec("I", [grp([q(15, "a ____ b"), q(16, "c ____ d")])]),
            sec("II", [grp(
                [q(17, None, ["big", "small"]), q(18, None, ["very", "much"]),
                 q(19, None, ["many", "much"])],
                "My town is (17) ____ and the people are (18) ____ friendly. There are (19) ____"
                " parks.",
            )]),
        ],
    )  # fmt: skip
    assert questions == [0, 0, 1, 1, 1]
    assert groups == [0, 1]


@pytest.mark.parametrize(
    "marker",
    ["(17)", "17.", "17 ____", "__(17)__", "[17]"],
)
def test_word_form_passage_question_is_found_by_its_marker(marker: str) -> None:
    passage_1 = "Tom is a very kind boy and everyone likes him a lot."
    passage_2 = f"His {marker} (SUCCEED) made his parents proud."
    groups, questions = locate(
        [
            ["I. Choose.", "16. c ____ d", "II. Give the correct form of the word.", passage_1],
            [passage_2],
        ],
        [
            sec("I", [grp([q(16, "c ____ d")])]),
            sec("II", [grp([q(17, None, cue="SUCCEED")], f"{passage_1} {passage_2}")]),
        ],
    )
    assert questions == [0, 1]  # question 17's blank is printed on page 2
    assert groups == [0, 0]  # the passage starts on page 1


def test_stemless_question_without_a_marker_falls_back_to_its_passage() -> None:
    groups, questions = locate(
        [
            ["I. Choose.", "16. c ____ d"],
            ["II. Fill the gaps.", "My town is ____ and nice."],
        ],
        [
            sec("I", [grp([q(16, "c ____ d")])]),
            sec("II", [grp([q(17, None, ["big", "small"])], "My town is ____ and nice.")]),
        ],
    )
    assert questions == [0, 1]  # never question 16's place on page 1
    assert groups == [0, 1]


def test_a_numbered_list_in_the_passage_does_not_capture_the_questions() -> None:
    groups, questions = locate(
        [
            ["Read the passage.", "1. Wake up early.", "2. Eat breakfast."],
            ["Questions:", "1. What first?", "2. What next?"],
        ],
        [sec("R", [grp([q(1, "What first?"), q(2, "What next?")],
                       "1. Wake up early. 2. Eat breakfast.")])],
    )  # fmt: skip
    assert questions == [1, 1]
    assert groups == [0]


@pytest.mark.parametrize(
    ("pages", "sections", "want_groups", "want_questions"),
    [
        pytest.param(
            [["I. Choose.", "1. a ____ b", "2. c ____ d"],
             ["II. Write.", "1. Rewrite x", "2. Rewrite y"]],
            [sec("I", [grp([q(1, "a ____ b"), q(2, "c ____ d")])]),
             sec("II", [grp([q(1, "Rewrite x"), q(2, "Rewrite y")])])],
            [0, 1], [0, 0, 1, 1], id="two sections from 1",
        ),
        pytest.param(
            [["Read the passage.", "In 1990 the town was small.",
              "2. The second point of the list.", "It grew."],
             ["1. When was the town small?", "2. Did it grow?"]],
            [sec("R", [grp([q(1, "When was the town small?"), q(2, "Did it grow?")],
                           "In 1990 the town was small. 2. The second point of the list. It"
                           " grew.")])],
            [0], [1, 1], id="numbers in the passage",
        ),
        pytest.param(
            [["Read the passage.", "Tom lives in Hanoi with his family and"],
             ["his dog. He likes it.", "1. Where does Tom live?"]],
            [sec("R", [grp([q(1, "Where does Tom live?")],
                           "Tom lives in Hanoi with his family and his dog. He likes it.")])],
            [0], [1], id="page starts mid passage",
        ),
        pytest.param(
            [["Read the passage.", "WELCOME TO THE CITY of lights"], ["more text.", "1. Where?"]],
            [sec("R", [grp([q(1, "Where?")], "**WELCOME TO THE CITY** of lights more text.")])],
            [0], [1], id="bold stimulus",
        ),
        pytest.param(
            [["Câu 13. He ____ a. A. x B. y"], ["Câu 14. She ____ b.", "A. go B. goes"]],
            [sec("I", [grp([q(13, "He ____ a."), q(14, "She ____ b.")])])],
            [0], [0, 1], id="Câu",
        ),
        pytest.param(
            [["1. How long? A. 2 hours B. 3 hours", "2. How far?"],
             ["3 kilometres away is", "3. Next?"]],
            [sec("I", [grp([q(1, "How long?", ["2 hours", "3 hours"]), q(2, "How far?"),
                            q(3, "Next?")])])],
            [0], [0, 0, 1], id="digits in options",
        ),
    ],
)  # fmt: skip
def test_other_probe_layouts_keep_their_pages(
    pages: list[list[str]],
    sections: list[dict[str, object]],
    want_groups: list[int],
    want_questions: list[int],
) -> None:
    groups, questions = locate(pages, sections)
    assert questions == want_questions
    assert groups == want_groups


def test_picture_group_spanning_two_pages_goes_to_the_picture_page() -> None:
    groups, questions = locate(
        [["II. Look at pictures.", "1. What is it?"], ["2. What is that?"]],
        [sec("II", [grp([q(1, "What is it?"), q(2, "What is that?")], pictures=True)])],
        pictures=(1,),
    )
    assert questions == [0, 1]
    assert groups == [1]


def test_cloze_spanning_a_page_break() -> None:
    groups, questions = locate(
        [["II. Fill the gaps.", "My town is (17) ____ and nice."],
         ["There are (18) ____ parks."]],
        [sec("II", [grp([q(17, None, ["big", "small"]), q(18, None, ["many", "much"])],
                        "My town is (17) ____ and nice. There are (18) ____ parks.")])],
    )  # fmt: skip
    assert questions == [0, 1]
    assert groups == [0]


# --- normalised matching (re-check fix) -----------------------------------------------------------


@pytest.mark.parametrize(
    ("pdf_marker", "model_marker"),
    [
        ("({n})____", "({n})____"),
        ("__({n})__", "__({n})__"),
        ("{n}.____", "{n}.____"),
        ("……({n})……", "……({n})……"),
        ("__({n})__", "({n}) ____"),
        ("{n}.____", "____"),
        ("……({n})……", "({n}) ..."),
    ],
)
def test_passage_end_is_found_with_markers_glued_to_their_blanks(
    pdf_marker: str, model_marker: str
) -> None:
    def text(marker: str) -> list[str]:
        m = [marker.format(n=n) for n in (1, 2, 3)]
        return [
            f"My town is {m[0]} big and quiet. The people",
            f"are {m[1]} friendly and the food is {m[2]} good.",
        ]

    stimulus = " ".join(text(model_marker))
    pdf = text(pdf_marker)
    passage = sec("I", [grp([q(1, None), q(2, None), q(3, None)], stimulus)])
    groups, questions = locate([["I. Read and fill.", pdf[0]], [pdf[1]]], [passage])
    assert questions == [0, 1, 1]
    assert groups == [0]

    later = sec(
        "II",
        [grp([q(1, "He go home."), q(2, "She like it."), q(3, "They is here.")])],
    )
    groups, questions = locate(
        [
            ["I. Read and fill.", pdf[0]],
            [pdf[1]],
            ["II. Correct the mistakes.", "1. He go home.", "2. She like it.", "3. They is here."],
        ],
        [passage, later],
    )
    assert questions == [0, 1, 1, 2, 2, 2]
    assert groups == [0, 2]


def test_stemless_question_with_a_missing_marker_stays_in_its_passage() -> None:
    # minor (a): question 2's marker is not printed; a later section's "2." must not take it
    groups, questions = locate(
        [
            ["I. Fill the gaps.",
             "My town is (1) ____ and the people are ____ friendly. There are (3) ____ parks."],
            ["II. Correct.", "1. He go home.", "2. She like it.", "3. They is here."],
        ],
        [
            sec("I", [grp([q(1, None), q(2, None), q(3, None)],
                          "My town is (1) ____ and the people are ____ friendly. There are (3)"
                          " ____ parks.")]),
            sec("II", [grp([q(1, "He go home."), q(2, "She like it."), q(3, "They is here.")])]),
        ],
    )  # fmt: skip
    assert questions == [0, 0, 0, 1, 1, 1]
    assert groups == [0, 1]


@pytest.mark.parametrize(
    ("pdf_name", "model_name"),
    [
        ("Mary\N{RIGHT SINGLE QUOTATION MARK}s", "Mary's"),
        ("Mary's", "Mary\N{RIGHT SINGLE QUOTATION MARK}s"),
        ("\N{LEFT DOUBLE QUOTATION MARK}Mary\N{RIGHT DOUBLE QUOTATION MARK}", '"Mary"'),
    ],
)
def test_stimulus_is_found_across_curly_and_straight_quotes(pdf_name: str, model_name: str) -> None:
    # minor (b)
    def body(name: str) -> str:
        return f"{name} house is (17) ____ big. It has (18) ____ rooms \N{EN DASH} all small."

    model_body = body(model_name).replace("\N{EN DASH}", "-")
    groups, questions = locate(
        [["I. Choose.", "16. c ____ d"], ["II. Fill.", body(pdf_name)]],
        [
            sec("I", [grp([q(16, "c ____ d")])]),
            sec("II", [grp([q(17, None), q(18, None)], model_body)]),
        ],
    )
    assert questions == [0, 1, 1]
    assert groups == [0, 1]


def test_a_number_ending_a_sentence_is_not_a_marker() -> None:
    # minor (c): "aged 17." is not question 17's marker
    groups, questions = locate(
        [
            ["I. Choose.", "16. c ____ d", "II. Fill the gaps.", "Tom was aged 17. He lived in"],
            ["a (17) ____ town."],
        ],
        [
            sec("I", [grp([q(16, "c ____ d")])]),
            sec("II", [grp([q(17, None)], "Tom was aged 17. He lived in a (17) ____ town.")]),
        ],
    )
    assert questions == [0, 1]
    assert groups == [0, 0]


def test_nfd_passage_text_is_found() -> None:
    import unicodedata

    body = "Bé Lan ở Hà Nội và (1) ____ rất vui."
    groups, questions = locate(
        [["I. Choose.", "16. c ____ d"], ["II. Điền.", unicodedata.normalize("NFD", body)]],
        [
            sec("I", [grp([q(16, "c ____ d")])]),
            sec("II", [grp([q(1, None)], unicodedata.normalize("NFC", body))]),
        ],
    )
    assert questions == [0, 1]
    assert groups == [0, 1]


# --- global alignment (second re-check rework) ----------------------------------------------------


@pytest.mark.parametrize(
    "key_rows",
    [["1. B   2. A   3. C", "4. D   5. A"], ["1-B  2-A  3-C  4-D  5-A"], ["1. B", "2. A", "3. C"]],
)
def test_two_questions_per_line_and_an_answer_key_table(key_rows: list[str]) -> None:
    # major: a number printed mid-line must not jump to the key table's row for it
    groups, questions = locate(
        [
            ["I. Choose.", "1. He ____ home.     2. She ____ tall.",
             "3. They ____ here.     4. We ____ late."],
            ["5. It ____ cold today."],
            ["ĐÁP ÁN", *key_rows],
        ],
        [sec("I", [grp([q(1, "He ____ home."), q(2, "She ____ tall."), q(3, "They ____ here."),
                        q(4, "We ____ late."), q(5, "It ____ cold today.")])])],
    )  # fmt: skip
    assert questions == [0, 0, 0, 0, 1]
    assert groups == [0]


def test_two_questions_per_line_then_a_section_numbering_from_1() -> None:
    # major: question 2 printed mid-line is not the next section's "2."
    groups, questions = locate(
        [
            ["I. Choose.", "1. He ____ home.     2. She ____ tall."],
            ["II. Write.", "1. Rewrite x now.", "2. Rewrite y now."],
        ],
        [
            sec("I", [grp([q(1, "He ____ home."), q(2, "She ____ tall.")])]),
            sec("II", [grp([q(1, "Rewrite x now."), q(2, "Rewrite y now.")])]),
        ],
    )
    assert questions == [0, 0, 1, 1]
    assert groups == [0, 1]


def test_a_passage_whose_closing_phrase_also_comes_earlier() -> None:
    # minor (a)
    page_1 = "We go to the park on Sunday. It is (1) ____ fun and (2) ____ nice."
    page_2 = "Then (3) ____ we go to the park on Sunday."
    groups, questions = locate(
        [["I. Fill the gaps.", page_1], [page_2]],
        [sec("I", [grp([q(1, None), q(2, None), q(3, None)], f"{page_1} {page_2}")])],
    )
    assert questions == [0, 0, 1]
    assert groups == [0]


def test_a_passage_ending_in_a_bare_blank() -> None:
    # minor (b): "... we love it (3) ____" with no full stop; gap 3 is on the next page
    groups, questions = locate(
        [
            ["I. Fill the gaps.", "My town is (1) ____ big."],
            ["The people are (2) ____ and we love it"],
            ["(3) ____", "II. Correct.", "4. He go home."],
        ],
        [
            sec("I", [grp([q(1, None), q(2, None), q(3, None)],
                          "My town is (1) ____ big. The people are (2) ____ and we love it (3)"
                          " ____")]),
            sec("II", [grp([q(4, "He go home.")])]),
        ],
    )  # fmt: skip
    assert questions == [0, 1, 2, 2]
    assert groups == [0, 2]


def test_a_number_before_a_bracket_is_not_the_marker() -> None:
    # minor (c): "Tom turned 17. (He was happy.)" is not question 17's marker
    groups, questions = locate(
        [
            ["I. Choose.", "16. c ____ d", "II. Fill the gaps.",
             "Tom turned 17. (He was happy.) He lived in"],
            ["a (17) ____ town."],
        ],
        [
            sec("I", [grp([q(16, "c ____ d")])]),
            sec("II", [grp([q(17, None)],
                           "Tom turned 17. (He was happy.) He lived in a (17) ____ town.")]),
        ],
    )  # fmt: skip
    assert questions == [0, 1]
    assert groups == [0, 0]


def test_a_group_start_is_not_an_earlier_stem_with_the_same_words() -> None:
    # minor (d): "Bà ba bán bánh mì" and "Ba bà bán bánh mì" fold the same
    passage = "Ba bà bán bánh mì ở chợ mỗi sáng. Họ (1) ____ rất vui."
    groups, questions = locate(
        [["I. Choose.", "1. Bà ba bán bánh mì ở chợ."], ["II. Fill the gap.", passage]],
        [
            sec("I", [grp([q(1, "Bà ba bán bánh mì ở chợ.")])]),
            sec("II", [grp([q(1, None)], passage)]),
        ],
    )
    assert questions == [0, 1]
    assert groups == [0, 1]


def test_a_stimulus_copied_with_an_added_comma_is_found() -> None:
    # minor (e)
    groups, questions = locate(
        [["I. Choose.", "16. c ____ d"], ["II. Fill.", "My town is big and ____ nice."]],
        [
            sec("I", [grp([q(16, "c ____ d")])]),
            sec("II", [grp([q(17, None)], "My town, is big and ____ nice.")]),
        ],
    )
    assert questions == [0, 1]
    assert groups == [0, 1]


def test_a_cau_marker_in_brackets() -> None:
    # minor (f): "(Câu 17)"
    groups, questions = locate(
        [
            ["I. Choose.", "16. c ____ d", "II. Fill.", "Tom lives in a big house. It is"],
            ["(Câu 17) very old."],
        ],
        [
            sec("I", [grp([q(16, "c ____ d")])]),
            sec("II", [grp([q(17, None)], "Tom lives in a big house. It is (Câu 17) very old.")]),
        ],
    )
    assert questions == [0, 1]
    assert groups == [0, 0]


# --- property: synthetic multi-page tests ---------------------------------------------------------

_VOCAB = [
    "apple", "river", "garden", "window", "teacher", "yellow", "market", "quiet", "sunday",
    "bridge", "pencil", "forest", "doctor", "summer", "orange", "basket", "island", "kitten",
    "mirror", "bottle", "letter", "castle", "dragon", "engine", "flower", "jacket", "ladder",
    "meadow", "needle", "pillow", "rocket", "saddle", "tunnel", "violin", "wagon", "zebra",
    "anchor", "button", "candle", "dinner", "eagle", "feather", "guitar", "hammer", "jungle",
    "kettle", "lemon", "monkey", "noodle", "ocean", "parrot", "rabbit", "salmon", "tomato",
    "uncle", "velvet", "walnut", "cotton", "puzzle",
]  # fmt: skip
_MARKERS = ["({n}) ____", "__({n})__", "{n}.____", "……({n})……", "[{n}] ____", "(Câu {n}) ____"]


def _words(rng: random.Random, k: int) -> str:
    return " ".join(rng.choice(_VOCAB) for _ in range(k))


def _synthetic_test(
    rng: random.Random,
) -> tuple[list[list[str]], list[dict[str, object]], list[int], list[int]]:
    """A random typed test cut into pages: (pages, the model's sections, true group pages, true
    question pages). Sections of choice rows (some two per line), cloze passages with markers in
    every form and reading passages with questions after them; numbering goes on or starts again
    at 1; sometimes an answer-key table at the end."""
    lines: list[str] = []
    group_line: list[int] = []
    question_line: list[int] = []
    sections: list[dict[str, object]] = []
    numbers: list[int] = []
    n = 1
    for s in range(rng.randint(2, 5)):
        if s and rng.random() < 0.35:
            n = 1
        kind = rng.choice(["choice", "cloze", "reading"])
        lines.append(f"{'IVXLC'[s % 5]}. {_words(rng, 4).capitalize()}.")
        count = rng.randint(2, 6)
        qs: list[dict[str, object]] = []
        stimulus: str | None = None
        if kind == "choice":
            group_line.append(len(lines))
            k = 0
            while k < count:
                per_line = 2 if count - k >= 2 and rng.random() < 0.4 else 1
                row = []
                for _ in range(per_line):
                    stem = f"{_words(rng, 2).capitalize()} ____ {_words(rng, rng.randint(2, 5))}."
                    options = [_words(rng, 1) for _ in range(4)]
                    qs.append(q(n, stem, options))
                    question_line.append(len(lines))
                    opts = " ".join(f"{'ABCD'[i]}. {o}" for i, o in enumerate(options))
                    row.append(f"{n}. {stem} {opts}" if per_line == 2 else f"{n}. {stem}")
                    if per_line == 1 and rng.random() < 0.5:
                        row.append(opts)
                    numbers.append(n)
                    n += 1
                    k += 1
                if per_line == 2:
                    lines.append("     ".join(row))
                else:
                    lines.extend(row)
        elif kind == "cloze":
            group_line.append(len(lines))
            form = rng.choice(_MARKERS)
            model_form = rng.choice([form, "({n}) ____"])
            pdf_parts: list[str] = []
            model_parts: list[str] = []
            for _ in range(count):
                head, tail = _words(rng, rng.randint(2, 6)), _words(rng, rng.randint(1, 4))
                pdf_parts.append(f"{head.capitalize()} {form.format(n=n)} {tail}.")
                model_parts.append(f"{head.capitalize()} {model_form.format(n=n)} {tail}.")
                question_line.append(len(lines))
                lines.append(pdf_parts[-1])
                qs.append(q(n, None, [_words(rng, 1) for _ in range(4)] if rng.random() < 0.5
                            else None))  # fmt: skip
                numbers.append(n)
                n += 1
            stimulus = " ".join(model_parts)
        else:
            group_line.append(len(lines))
            body = [
                f"{_words(rng, rng.randint(5, 9)).capitalize()}." for _ in range(rng.randint(2, 4))
            ]
            lines.extend(body)
            stimulus = " ".join(body)
            for _ in range(count):
                stem = f"{_words(rng, rng.randint(3, 6)).capitalize()}?"
                qs.append(q(n, stem))
                question_line.append(len(lines))
                lines.append(f"{n}. {stem}")
                numbers.append(n)
                n += 1
        sections.append(sec(f"S{s}", [grp(qs, stimulus)]))
    if rng.random() < 0.5:
        lines.append("ĐÁP ÁN")
        row = [f"{m}. {rng.choice('ABCD')}" for m in numbers]
        for i in range(0, len(row), 5):
            lines.append("   ".join(row[i : i + 5]))
    cuts = sorted(rng.sample(range(1, len(lines)), rng.randint(1, min(4, len(lines) - 1))))
    page_of = [sum(1 for c in cuts if c <= i) for i in range(len(lines))]
    pages = [lines[a:b] for a, b in zip([0, *cuts], [*cuts, len(lines)], strict=True)]
    return (
        pages,
        sections,
        [page_of[i] for i in group_line],
        [page_of[i] for i in question_line],
    )


@pytest.mark.parametrize("seed", range(300))
def test_every_question_gets_its_true_page_on_synthetic_tests(seed: int) -> None:
    pages, sections, want_groups, want_questions = _synthetic_test(random.Random(seed))
    groups, questions = locate(pages, sections)
    assert questions == want_questions
    assert groups == want_groups
