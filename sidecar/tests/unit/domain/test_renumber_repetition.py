"""Step 22.5.6 verifier fix (R22.5.6.1, R22.5.6.2): the repetition guard cuts only a whole
repeated block (the same section, stimulus and questions again); two sections or passages that
both number from 1 keep every question. The cases come from the verifier's probe."""

from __future__ import annotations

from etach.domain.llm_schemas import TranscribeOut
from etach.domain.renumber import cut_repetition


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


# --- the repetition guard (fix 2) -----------------------------------------------------------------


def _out(sections: list[dict[str, object]]) -> TranscribeOut:
    return TranscribeOut.model_validate({"header_text": None, "sections": sections})


def test_two_passages_numbering_from_1_are_not_a_repeat() -> None:
    out = _out([
        sec("A", [grp([q(n, None) for n in range(1, 6)],
                      "x (1) ____ (2) ____ (3) ____ (4) ____ (5) ____")],
            "Fill each gap with one word."),
        sec("B", [grp([q(n, None, cue=c) for n, c in
                       zip(range(1, 6), ["SUCCEED", "HAPPY", "CARE", "BEAUTY", "HI"], strict=True)],
                      "p (1) ____ (2) ____ (3) ____ (4) ____ (5) ____")],
            "Give the correct form of the word."),
        sec("C", [grp([q(6, "Rewrite this.")])], "Rewrite."),
    ])  # fmt: skip
    cut, dropped = cut_repetition(out)
    assert dropped == 0
    assert cut == out


def test_same_questions_under_another_stimulus_are_not_a_repeat() -> None:
    out = _out([
        sec("A", [grp([q(1, None), q(2, None)], "first passage (1) ____ (2) ____"),
                  grp([q(1, None), q(2, None)], "second passage (1) ____ (2) ____")]),
    ])  # fmt: skip
    assert cut_repetition(out) == (out, 0)


def test_a_looped_block_is_still_cut() -> None:
    block = [q(n, f"Question {n} stem", ["a", "b"]) for n in range(1, 6)]
    out = _out([sec("I", [grp(block + block)]), sec("I", [grp(block)])])
    cut, dropped = cut_repetition(out)
    assert dropped == 10
    assert len(cut.sections) == 1
    assert [x.printed_number for x in cut.sections[0].groups[0].questions] == [1, 2, 3, 4, 5]


def test_a_repeated_section_with_its_stimulus_is_cut() -> None:
    block = grp([q(n, None, cue="X") for n in (1, 2, 3)], "p (1) ____ (2) ____ (3) ____")
    out = _out([sec("A", [block]), sec("B", [grp([q(4, "Rewrite.")])]), sec("A", [block])])
    cut, dropped = cut_repetition(out)
    assert dropped == 3
    assert [s.printed_title for s in cut.sections] == ["A", "B"]
