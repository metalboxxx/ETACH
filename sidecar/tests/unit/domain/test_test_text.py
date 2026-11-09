"""R22.1.5.1, R22.1.5.2: the test as text (data-model §2.3a, PRD D27).

R22.1.5.1: ``read(render(c), c) == c`` for every ``TestContent`` in the replay outputs (each
cassette scenario's transcriptions through ``merge_pages``, as the extract run builds them), the
test-suite builders and hand-made edge cases (passages, cloze, pictures, ``???``, writing
sections, assumed points, escapes).
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest
from unit.domain.grading_support import worked_example

from etach.domain import models as m
from etach.domain.points import equal_points
from etach.domain.renumber import merge_pages
from etach.domain.test_text import read, render
from etach.domain.working import PageTranscript

CASSETTES = Path(__file__).resolve().parents[2] / "cassettes"


def _replay_contents() -> dict[str, m.TestContent]:
    """Each cassette scenario's ``transcribe_page`` outputs merged into one test."""
    by_scenario: dict[str, list[dict[str, object]]] = defaultdict(list)
    for path in sorted(CASSETTES.rglob("*transcribe_page*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        try:
            out = json.loads(data["response_text"])
        except (KeyError, ValueError):
            continue
        if isinstance(out, dict) and "sections" in out:
            by_scenario[str(path.parent.relative_to(CASSETTES))].append(out)
    contents: dict[str, m.TestContent] = {}
    for name, outs in by_scenario.items():
        pages = [
            PageTranscript(
                page_no=i,
                header_text=o.get("header_text"),  # type: ignore[arg-type]
                sections=o["sections"],  # type: ignore[arg-type]
                llm_call_id="call",
            )
            for i, o in enumerate(outs, start=1)
        ]
        files = {i: f"{i:02d}" * 32 for i in range(1, len(pages) + 1)}
        contents[f"replay:{name}"] = merge_pages(pages, page_files=files).draft.content
    return contents


def _q(qid: str, n: int, **kw: object) -> m.Question:
    base: dict[str, object] = {
        "id": qid,
        "number": n,
        "printed_number": n,
        "page_no": 1,
        "answer_form": "choice",
        "stem": f"Stem {n}",
        "options": [m.Option(label="A", text="one"), m.Option(label="B", text="two")],
        "cue": None,
        "points": 0.25,
    }
    base.update(kw)
    return m.Question.model_validate(base)


def _section(sid: str, groups: list[m.QuestionGroup], **kw: object) -> m.Section:
    base: dict[str, object] = {
        "id": sid,
        "number": 1,
        "printed_title": "I.",
        "title": "I.",
        "instructions": "Choose the best answer.",
        "points": 0.25 * sum(len(g.questions) for g in groups),
        "points_source": "printed",
        "skill": "grammar",
        "graded": True,
        "groups": groups,
    }
    base.update(kw)
    return m.Section.model_validate(base)


def edge_cases() -> m.TestContent:
    """Text that looks like structure, empty and None fields, uneven points, writing, titles."""
    pic = m.PictureRef(file_id="ab" * 32, page_no=2)
    s1 = _section(
        "s-a",
        [
            m.QuestionGroup(
                id="g-a1",
                stimulus="Line one\n\n12. looks like a question\n[End of passage]\n\\back",
                pictures=[pic],
                questions=[
                    _q("q-1", 1, stem="A. starts like an option\nCue: not a cue"),
                    _q("q-2", 2, stem="", options=[], answer_form="word"),
                    _q("q-3", 3, stem=None, options=None, answer_form="word", page_no=2),
                    _q(
                        "q-4",
                        4,
                        stem="Ends like a heading [2 points]",
                        options=[
                            m.Option(label="A", text="has  two spaces"),
                            m.Option(label="B", text="multi\nline"),
                            m.Option(label="C", text=""),
                            m.Option(label="???", text="unread ???"),
                        ],
                        page_no=2,
                    ),
                ],
            ),
            m.QuestionGroup(id="g-a2", stimulus=None, pictures=[], questions=[_q("q-5", 5)]),
            m.QuestionGroup(id="g-a3", stimulus="", pictures=[], questions=[_q("q-6", 6)]),
        ],
        instructions="\nFirst line blank.\n\nInternal blank above.\n",
        printed_title="PART A. READING",
        title="Reading",
    )
    uneven = [
        _q("q-7", 7, points=1.0, cue="(consume)", answer_form="word", options=None),
        _q("q-8", 8, points=0.5, cue="\nsecond line", answer_form="word", options=None),
        _q("q-9", 9, points=0.5, cue="", answer_form="word", options=None),
    ]
    s2 = _section(
        "s-b",
        [m.QuestionGroup(id="g-b1", stimulus=None, pictures=[], questions=uneven)],
        points=2.0,
        printed_title="",
        title="",
        instructions="",
        skill="word_form",
    )
    each = [_q(f"q-e{i}", 9 + i, points=0.1, printed_number=9 + i) for i in range(1, 4)]
    s3 = _section(
        "s-c",
        [m.QuestionGroup(id="g-c1", stimulus=None, pictures=[], questions=each)],
        points=0.1 * 3,
        points_source="assumed",
        printed_title="III",
        title="III",
    )
    writing = _section(
        "s-w",
        [
            m.QuestionGroup(
                id="g-w1",
                stimulus=None,
                pictures=[],
                questions=[
                    _q(
                        "q-w",
                        13,
                        stem="Write a paragraph (80-100 words).\n- point one\n12. not a number",
                        options=None,
                        answer_form="writing",
                        page_no=3,
                    )
                ],
            )
        ],
        printed_title="IV.",
        title="IV.",
        graded=False,
        skill="writing",
        points=1.0,
        number=4,
    )
    empty = _section("s-e", [], printed_title="V.", title="V.", points=0.0, number=5)
    return m.TestContent(sections=[s1, s2, s3, writing, empty])


def _builder_contents() -> dict[str, m.TestContent]:
    unreadable = m.TestContent(
        sections=[
            _section(
                "s-1",
                [
                    m.QuestionGroup(
                        id="g-1",
                        stimulus="A passage with ??? in it and (17)______ a cloze blank.",
                        pictures=[],
                        questions=[
                            _q("q1", 1, stem="Stem ??? 1"),
                            _q(
                                "q2",
                                2,
                                options=[
                                    m.Option(label="A", text="one"),
                                    m.Option(label="???", text="two"),
                                ],
                            ),
                        ],
                    )
                ],
                instructions="Circle ??? or B.",
            )
        ]
    )
    return {
        "builder:worked_example": worked_example(),
        "builder:unreadable": unreadable,
        "builder:empty": m.TestContent(sections=[]),
        "edge_cases": edge_cases(),
    }


ALL = {**_replay_contents(), **_builder_contents()}


def test_enough_contents() -> None:
    """At least 10 different tests, with passages, pictures, ``???``, writing and assumed."""
    assert len(ALL) >= 10
    every = list(ALL.values())
    assert any(g.stimulus for c in every for s in c.sections for g in s.groups)
    assert any(g.pictures for c in every for s in c.sections for g in s.groups)
    assert any("???" in render(c) for c in every)
    assert any(not s.graded for c in every for s in c.sections)
    assert any(s.points_source == "assumed" for c in every for s in c.sections)


@pytest.mark.parametrize("name", sorted(ALL))
def test_r22_1_5_1_round_trip(name: str) -> None:
    content = ALL[name]
    text = render(content)
    result = read(text, content)
    assert result.errors == []
    assert result.content == equal_points(content)  # v1.19: the points are the equal ones
    assert result.dropped == []


def test_render_with_picture_paths_round_trips() -> None:
    content = edge_cases()
    text = render(content, {"ab" * 32: f"files/ab/{'ab' * 32}.png"})
    assert f"[Hình: files/ab/{'ab' * 32}.png · trang 2]" in text
    assert read(text, content).content == equal_points(content)


def test_render_looks_like_the_paper() -> None:
    text = render(_builder_contents()["builder:unreadable"])
    assert text.splitlines()[:6] == [
        "— Page 1 —",
        "",
        "# I.",  # v1.21 (D7): no points on a heading
        "Circle ??? or B.",
        "",
        "[Passage]",
    ]
    assert "1. Stem ??? 1\n   A. one    B. two\n" in text
    assert "2. Stem 2\n   A. one    ???. two\n" in text


# --- R22.1.5.2: identity and errors -----------------------------------------------------------


def _ids(content: m.TestContent) -> list[str]:
    return [q.id for s in content.sections for g in s.groups for q in g.questions]


def _replay(name: str) -> m.TestContent:
    return ALL[f"replay:{name}"]


def test_editing_a_stem_an_option_and_a_passage_keeps_every_id() -> None:
    content = _replay("s1")
    text = render(content)
    edited = (
        text.replace("Which word has a different stress", "Which word has another stress")
        .replace("A. bracelet", "A. braceletes")
        .replace("In the Southeast Asian country", "In the South-East Asian country")
    )
    assert edited != text
    result = read(edited, content)
    assert result.content is not None, result.errors
    assert _ids(result.content) == _ids(content)
    assert result.dropped == []
    assert [g.id for s in result.content.sections for g in s.groups] == [
        g.id for s in content.sections for g in s.groups
    ]


def test_inserting_a_question_keeps_the_others_and_adds_a_new_id() -> None:
    content = _replay("s1")
    lines = render(content).split("\n")
    at = next(i for i, line in enumerate(lines) if line.startswith("6. "))
    lines[at:at] = ["6. A new question with a ____ blank.", ""]
    result = read("\n".join(lines), content)
    assert result.content is not None, result.errors
    old, new = _ids(content), _ids(result.content)
    assert set(old) <= set(new)
    added = [q for q in new if q not in old]
    assert len(added) == 1
    assert new.index(added[0]) == 1  # between the old first and second questions
    q = next(
        q for s in result.content.sections for g in s.groups for q in g.questions if q.id in added
    )
    assert q.answer_form == "word" and q.printed_number == 6
    # canonical numbers follow the new order
    numbers = [
        q.number for s in result.content.sections if s.graded for g in s.groups for q in g.questions
    ]
    assert numbers == list(range(1, len(numbers) + 1))


def test_deleting_a_question_reports_it_dropped() -> None:
    content = _replay("s1")
    lines = render(content).split("\n")
    at = next(i for i, line in enumerate(lines) if line.startswith("6. "))
    del lines[at : at + 3]
    result = read("\n".join(lines), content)
    assert result.content is not None
    six = next(
        q.id
        for s in content.sections
        for g in s.groups
        for q in g.questions
        if q.printed_number == 6
    )
    assert result.dropped == [six]


def test_typed_heading_points_are_ignored() -> None:
    """v1.19 (PRD D13 v8.0): the heading's points are computed; a typed value is ignored and
    an old ``assumed`` still reads back. v1.21 (D7): the text is written with no points, and the
    older heading form with points still reads as the same test."""
    content = _builder_contents()["edge_cases"]
    text = render(content)
    assert "# III\n" in text and "points" not in text.replace("[2 points]", "")
    expected = read(text, content).content
    assert expected is not None
    old = text.replace("# III\n", "III  [0.1 points each]\n")
    assert read(old, content).content == expected
    assert (
        read(old.replace("[0.1 points each]", "[0.1 points each, assumed]"), content).content
        == expected
    )
    result = read(old.replace("[0.1 points each]", "[0.6 points: 1 / 2]"), content)
    assert result.errors == [] and result.content == expected
    section = result.content.sections[2]
    assert section.points_source == "equal"
    n = sum(len(g.questions) for s in expected.sections if s.graded for g in s.groups)
    assert [q.points for g in section.groups for q in g.questions] == [10 / n] * 3
    assert "assumed" not in render(expected)


def test_unreadable_lines_give_line_numbered_errors() -> None:
    content = _replay("s1")
    text = "Some words first\n" + render(content) + "\n[Passage]\nnever closed\n"
    result = read(text, content)
    assert result.content is None
    lines = {e.line for e in result.errors}
    assert 1 in lines
    assert len(text.split("\n")) - 2 in lines  # the [Passage] line
    first = next(ln for ln in render(content).split("\n") if ln.startswith("# II."))
    # a points bracket (the form before v1.21) that says something unknown is an error
    bad_tag = render(content).replace(first, "II.  [2 points, maybe]", 1)
    errs = read(bad_tag, content).errors
    assert len(errs) == 1 and "maybe" in errs[0].message
    assert bad_tag.split("\n")[errs[0].line - 1].startswith("II.")  # type: ignore[operator]


def test_option_outside_a_question_is_an_error() -> None:
    result = read("I.  [1 point]\nChoose.\n\n   A. alone\n", None)
    assert result.content is None
    assert result.errors[0].line == 4


def test_a_new_test_from_text_alone() -> None:
    text = (
        "I.  [1 point]\nChoose the best answer.\n\n1. She ____ to school.\n   A. go    B. goes\n\n"
        "2. They ____ happy.\n   A. is    B. are\n\n— Page 2 —\n\nII.  [1 point, not graded]\n"
        "3. Write about your school.\n"
    )
    result = read(text, None)
    assert result.content is not None, result.errors
    s1, s2 = result.content.sections
    assert [q.answer_form for g in s1.groups for q in g.questions] == ["choice", "choice"]
    assert [q.points for g in s1.groups for q in g.questions] == [5.0, 5.0]  # 10 / 2
    assert not s2.graded and s2.skill == "writing"
    q3 = s2.groups[0].questions[0]
    assert q3.answer_form == "writing" and q3.page_no == 2 and q3.number == 3
    assert len(set(_ids(result.content))) == 3
