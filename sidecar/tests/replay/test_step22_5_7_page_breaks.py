"""Step 22.5.7: photo page breaks, the hint and the merge rule (R22.5.7.1).

SYNTHETIC 2-page photo tests through the real CLI in-process, over the schema-keyed FakeOllama of
``make_synthetic.py``, recorded with ``etach record`` into ``tmp_path`` (synthetic cassettes) and
replayed. No student data, no model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from .make_synthetic import EMPTY, HEADER, Recorder, answers, photo
from .test_extract_replay import conn_of, run_ok

OPTS = [{"label": x, "text": f"opt {x.lower()}"} for x in "ABCD"]
STEM_14 = "Mai: Would you like to come to my party on Sunday?"


def _q(n: int, stem: str | None = None, options: Any = OPTS, **extra: Any) -> dict[str, Any]:
    return {
        "printed_number": n,
        "answer_form": "choice",
        "stem": stem if stem is not None else f"Question {n}: choose the best answer {n}",
        "options": options,
        "cue": None,
        **extra,
    }


def _section(title: str, groups: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "printed_title": title,
        "instructions": "Choose the best answer." if title else "",
        "kind": "questions",
        "skill": "mixed",
        "points_text": None,
        "range_first": None,
        "range_last": None,
        "groups": groups,
        **extra,
    }


def _group(questions: list[dict[str, Any]], stimulus: str | None = None, **extra: Any) -> Any:
    return {"stimulus": stimulus, "pictures": [], "questions": questions, **extra}


def _question_pages(flag: bool) -> list[dict[str, Any]]:
    """Page 1 ends with question 14's stem; page 2 starts (under a stray section "A") with its
    options, then question 15. ``flag``: the model marks the rest ``continued``."""
    p1_questions = [_q(n) for n in range(1, 14)] + [_q(14, STEM_14, None)]
    page1 = {"header_text": HEADER, "sections": [_section("I", [_group(p1_questions)])]}
    rest = {**_q(14, None, OPTS), "stem": None}
    if flag:
        rest["continued"] = True
    second = _section("A", [_group([rest, _q(15)])], continued=flag)
    second["instructions"] = ""
    return [page1, {"header_text": None, "sections": [second]}]


PASSAGE_1 = (
    "**A Day Out**\nWe went to the zoo (1) ____ Sunday.\nIt was (2) ____ and we saw (3) ____"
)
PASSAGE_2 = "lions. Then we (4) ____ home by bus."


def _cloze(n: int) -> dict[str, Any]:
    return _q(n, None, OPTS) | {"stem": None}


def _passage_pages(flag: bool) -> list[dict[str, Any]]:
    """A cloze passage cut at the page break: page 1 has gaps 1-3 and questions 1-2; page 2 starts
    with a stray section "Question 3." holding the rest of the passage and questions 3-4."""
    page1 = {
        "header_text": HEADER,
        "sections": [_section("I", [_group([_cloze(1), _cloze(2)], PASSAGE_1)])],
    }
    group2 = _group([_cloze(3), _cloze(4)], PASSAGE_2, **({"continued": True} if flag else {}))
    second = _section("Question 3.", [group2], **({"continued": True} if flag else {}))
    return [page1, {"header_text": None, "sections": [second]}]


def _run(tmp_path: Path, transcripts: list[dict[str, Any]]) -> tuple[dict[str, Any], Recorder]:
    rec = Recorder(tmp_path)
    try:
        pages = [str(photo(tmp_path, f"De-break ({i}).jpg", 150 + i)) for i in (1, 2)]
        out = rec.run(
            tmp_path / "data",
            pages,
            {"TranscribeOut": transcripts, "ReadAnswersCall": [answers(), EMPTY]},
            out=tmp_path / "scenario",
        )
    finally:
        rec.cli._TEST_TRANSPORT = None
    assert out["status"] == "done"
    return out, rec


def _user_texts(rec: Recorder) -> list[str]:
    """The user text of each ``transcribe_page`` request, in order."""
    texts: list[str] = []
    for title, body in rec.fake.seen:
        if title == "TranscribeOut":
            user = [m for m in body["messages"] if m["role"] == "user"][-1]
            texts.append(user["content"])
    return texts


def _content(data: Path, test_id: str) -> dict[str, Any]:
    c = conn_of(data)
    try:
        row = c.execute("SELECT content FROM tests WHERE id = ?", (test_id,)).fetchone()
    finally:
        c.close()
    return dict(json.loads(row[0]))


@pytest.mark.parametrize("flag", [True, False], ids=["marked", "same-number"])
def test_r22_5_7_1_question_cut_at_the_page_break(tmp_path: Path, flag: bool) -> None:
    out, rec = _run(tmp_path, _question_pages(flag))
    first, second = _user_texts(rec)
    assert first.endswith("Transcribe its printed text.")  # page 1: nothing before it
    assert second.endswith(
        "Transcribe its printed text.\n\nThe previous page ended inside this unit:\n"
        'Section "I": Choose the best answer.\n'
        f'Question 14: stem, no options. Stem: "{STEM_14}"'
    )
    content = _content(tmp_path / "data", out["test_id"])
    assert len(content["sections"]) == 1
    qs = [q for g in content["sections"][0]["groups"] for q in g["questions"]]
    assert [q["printed_number"] for q in qs] == list(range(1, 16))
    q14 = qs[13]
    assert q14["stem"] == STEM_14
    assert [o["label"] for o in q14["options"]] == list("ABCD")
    # the recorded synthetic cassettes replay to the same test
    replayed = run_ok("--data", tmp_path / "replay-data", "--replay", tmp_path / "scenario")
    assert (
        _content(tmp_path / "replay-data", replayed["test_id"])["sections"] == content["sections"]
    )


@pytest.mark.parametrize("flag", [True, False], ids=["marked", "gap-numbers"])
def test_r22_5_7_1_passage_cut_at_the_page_break(tmp_path: Path, flag: bool) -> None:
    out, rec = _run(tmp_path, _passage_pages(flag))
    second = _user_texts(rec)[1]
    assert second.endswith(
        'Section "I": Choose the best answer.\n'
        'Passage (questions read: 1-2), last paragraph from its last blank: "(3) ____"'
    )
    content = _content(tmp_path / "data", out["test_id"])
    assert len(content["sections"]) == 1
    groups = content["sections"][0]["groups"]
    assert len(groups) == 1
    assert groups[0]["stimulus"] == f"{PASSAGE_1}\n{PASSAGE_2}"
    assert [q["printed_number"] for q in groups[0]["questions"]] == [1, 2, 3, 4]


def test_r22_5_7_1_nothing_open_sends_no_hint(tmp_path: Path) -> None:
    page1 = {
        "header_text": HEADER,
        "sections": [_section("I", [_group([_q(1), _q(2)])])],
    }
    page2 = {"header_text": None, "sections": [_section("II", [_group([_q(3), _q(4)])])]}
    out, rec = _run(tmp_path, [page1, page2])
    texts = _user_texts(rec)
    assert all(t.endswith("Transcribe its printed text.") for t in texts)
    assert len(_content(tmp_path / "data", out["test_id"])["sections"]) == 2


# --- the hint and the merge, without the CLI --------------------------------------------------


def _out(sections: list[dict[str, Any]]) -> Any:
    from etach.domain.llm_schemas import TranscribeOut

    return TranscribeOut.model_validate({"header_text": None, "sections": sections})


def test_open_unit_cases() -> None:
    from etach.domain.renumber import open_unit

    assert open_unit(_out([])) is None
    assert open_unit(_out([_section("I", [])])) == (
        'Section "I": Choose the best answer.\nNo questions read yet.'
    )
    no_stem = _out([_section("I", [_group([_q(1), {**_q(2), "stem": None}])])])
    assert (
        open_unit(no_stem) == 'Section "I": Choose the best answer.\nQuestion 2: options, no stem'
    )
    listening = _section("I", [])
    listening["kind"] = "listening"
    assert open_unit(_out([listening])) is None
    long = _out([_section("I", [_group([_q(1, "x" * 5000, None)])])])
    hint = open_unit(long)
    assert hint is not None and len(hint) < 1300  # about 300 tokens at most


def test_stemless_gap_questions_join_the_open_passage() -> None:
    from etach.domain.renumber import merge_pages, page_transcript

    page1 = _out([_section("I", [_group([_cloze(1), _cloze(2)], PASSAGE_1)])])
    page2 = _out([_section("Question 3.", [_group([_cloze(3)])])])
    merged = merge_pages(
        [page_transcript(1, page1, "c1"), page_transcript(2, page2, "c2")],
        page_files={1: "f1", 2: "f2"},
    )
    sections = merged.draft.content.sections
    assert len(sections) == 1 and len(sections[0].groups) == 1
    assert [q.printed_number for q in sections[0].groups[0].questions] == [1, 2, 3]
    assert [q.page_no for q in sections[0].groups[0].questions] == [1, 1, 2]


def _merged_sections(page1: list[dict[str, Any]], page2: list[dict[str, Any]]) -> list[Any]:
    from etach.domain.renumber import merge_pages, page_transcript

    merged = merge_pages(
        [page_transcript(1, _out(page1), "c1"), page_transcript(2, _out(page2), "c2")],
        page_files={1: "f1", 2: "f2"},
    )
    return list(merged.draft.content.sections)


def _numbers(section: Any) -> list[int]:
    return [q.printed_number for g in section.groups for q in g.questions]


@pytest.mark.parametrize(
    ("titles", "first", "last"),
    [(("I", "II"), 1, 14), (("Part A", "Part B"), 1, 1)],
    ids=["II-at-14", "part-b-restarts"],
)
def test_new_titled_section_at_the_same_number_is_kept(
    titles: tuple[str, str], first: int, last: int
) -> None:
    """A page ends with a whole question; the next page starts a new titled section at that
    number: no join, every question and both sections kept."""
    page1 = [_section(titles[0], [_group([_q(n) for n in range(first, last + 1)])])]
    page2 = [_section(titles[1], [_group([_q(last, f"New section {last}"), _q(last + 1)])])]
    sections = _merged_sections(page1, page2)
    assert [s.printed_title for s in sections] == list(titles)
    assert _numbers(sections[0]) == list(range(first, last + 1))
    assert _numbers(sections[1]) == [last, last + 1]
    assert sections[1].groups[0].questions[0].stem == f"New section {last}"


def test_two_whole_different_copies_are_both_kept() -> None:
    """Same title, same number, both copies whole and different: never drop one."""
    page1 = [_section("I", [_group([_q(13), _q(14)])])]
    page2 = [_section("I", [_group([_q(14, "Another question 14"), _q(15)])])]
    sections = _merged_sections(page1, page2)
    assert len(sections) == 1
    stems = [q.stem for g in sections[0].groups for q in g.questions]
    assert _numbers(sections[0]) == [13, 14, 14, 15]
    assert stems[1] != stems[2] and "Another question 14" in stems
