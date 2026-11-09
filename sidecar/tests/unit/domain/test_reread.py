"""Step 22.5.7: the targeted re-read's pure parts (``renumber.reread_asks``, ``reread_text``,
``apply_reread``; ``validators.missing_numbers``). R22.5.7.2's graph scenarios are in
``tests/unit/graphs/test_extract.py``."""

from __future__ import annotations

import json
from typing import Any

from etach.domain import renumber
from etach.domain.llm_schemas import RereadPiecesOut, TranscribeOut
from etach.domain.renumber import RereadAsk, apply_reread, reread_asks, reread_text

OPTS = [{"label": x, "text": f"opt {x}"} for x in "ABCD"]


def _q(n: int, **fields: Any) -> dict[str, Any]:
    base = {"printed_number": n, "answer_form": "choice", "stem": f"stem {n}", "options": OPTS}
    return {"cue": None, **base, **fields}


def _sec(title: str, *groups: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "printed_title": title,
        "instructions": "Choose.",
        "kind": "questions",
        "skill": "grammar",
        "points_text": None,
        "range_first": None,
        "range_last": None,
        "groups": [{"stimulus": None, "pictures": [], "questions": g} for g in groups],
    }


def _page(*sections: dict[str, Any]) -> TranscribeOut:
    return TranscribeOut.model_validate({"header_text": None, "sections": list(sections)})


def _pieces(*pieces: dict[str, Any]) -> RereadPiecesOut:
    full = [
        {"answer_form": "choice", "stem": None, "options": None, "cue": None, **p} for p in pieces
    ]
    return RereadPiecesOut.model_validate({"pieces": full})


def _numbers(out: TranscribeOut, s: int = 0) -> list[list[int]]:
    return [[q.printed_number for q in g.questions] for g in out.sections[s].groups]


def test_asks_from_failures_name_the_failing_pieces_and_the_missing_numbers() -> None:
    page = _page(_sec("I", [_q(1), _q(2, options=OPTS[:1])]), _sec("II", [_q(6)]))
    merged = renumber.merge_pages(
        [renumber.page_transcript(1, page, "c")], page_files={1: "f"}, ref="r"
    )
    asks = reread_asks(
        page, merged.failures, merged.draft.content, merged.draft.meta.omitted_sections
    )
    assert asks == [
        RereadAsk(2, "I", "options"),
        RereadAsk(3, None, None),
        RereadAsk(4, None, None),
        RereadAsk(5, None, None),
    ]
    text = reread_text(page, asks)
    assert 'Section titles on this page: "I", "II".' in text
    assert 'Question 2 (section "I"): its options were not read right' in text
    assert "Questions 3, 4, 5: missing from the first reading." in text
    assert "Question 1 " not in text and "Question 6" not in text


def test_patch_replaces_the_failing_field_and_fills_empty_ones_only() -> None:
    page = _page(_sec("I", [_q(1), _q(2, options=OPTS[:1], cue=None, stem="kept")]))
    got = _pieces(
        {"section_title": "I", "printed_number": 2, "stem": "new", "options": OPTS, "cue": "CUE"}
    )
    out = apply_reread(page, [RereadAsk(2, "I", "options")], got)
    q2 = out.sections[0].groups[0].questions[1]
    assert (q2.stem, len(q2.options or []), q2.cue) == ("kept", 4, "CUE")
    assert out.sections[0].groups[0].questions[0] is page.sections[0].groups[0].questions[0]


def test_patch_ignores_pieces_not_asked_for_and_unknown_sections() -> None:
    page = _page(_sec("I", [_q(1, options=OPTS[:1]), _q(2, options=OPTS[:1])]))
    got = _pieces(
        {"section_title": "I", "printed_number": 2, "options": OPTS},  # not asked
        {"section_title": "IX", "printed_number": 1, "options": OPTS},  # unknown section
    )
    out = apply_reread(page, [RereadAsk(1, "I", "options")], got)
    assert out is page
    assert json.dumps(out.model_dump()) == json.dumps(page.model_dump())


def test_missing_number_goes_after_the_nearest_lower_number() -> None:
    page = _page(_sec("I", [_q(1), _q(2)], [_q(5), _q(8)]), _sec("II"))
    asks = [RereadAsk(n, None, None) for n in (3, 6, 9)]
    got = _pieces(
        {"section_title": "I", "printed_number": 6, "options": OPTS},
        {"section_title": "I", "printed_number": 3, "options": OPTS},
        {"section_title": "II", "printed_number": 9, "options": OPTS},
    )
    out = apply_reread(page, asks, got)
    assert _numbers(out) == [[1, 2, 3], [5, 6, 8]]
    assert _numbers(out, 1) == [[9]]  # a section with no group gets one


def test_missing_number_with_no_lower_number_goes_before_the_first_higher() -> None:
    page = _page(_sec("", [_q(5), _q(6)]))
    got = _pieces({"section_title": " ", "printed_number": 4, "options": OPTS})
    out = apply_reread(page, [RereadAsk(4, None, None)], got)
    assert _numbers(out) == [[4, 5, 6]]
