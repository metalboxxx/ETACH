"""Similarity: normalization, shingles, Jaccard, tiers, candidates, alignment (R8.1.6, B.2)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from support.guards import no_io  # noqa: F401

from etach.domain.models import (
    Option,
    Question,
    QuestionGroup,
    Section,
)
from etach.domain.models import TestContent as Content
from etach.domain.models import TestMetadata as Meta
from etach.domain.renumber import fingerprint_text
from etach.domain.similarity import (
    Candidate,
    align_questions,
    compare,
    jaccard,
    normalize_for_similarity,
    shingles,
    similarity,
    tier_for,
)
from etach.domain.working import TestDraft as Draft

pytestmark = pytest.mark.usefixtures("no_io")

DATA = Path(__file__).resolve().parents[2] / "data" / "similarity"
EXPECTED: dict[str, Any] = json.loads((DATA / "expected.json").read_text(encoding="utf-8"))

_Q = re.compile(r"^(\d+)\.\s*(.*)$")
_OPT = re.compile(r"^([A-D])\.\s*(.*)$")


def parse(name: str) -> Content:
    """The small text format of tests/data/similarity: ``## <title> | <instructions>``,
    ``> <stimulus>``, ``<n>. <stem> | A. .. | B. ..``. Question ids are ``q<printed number>``."""
    sections: list[dict[str, Any]] = []
    for line in (DATA / name).read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            title, instructions = (p.strip() for p in line[3:].split("|", 1))
            sections.append({"title": title, "instructions": instructions, "stim": None, "qs": []})
        elif line.startswith("> "):
            sections[-1]["stim"] = line[2:]
        elif m := _Q.match(line):
            parts = [p.strip() for p in m.group(2).split("|")]
            stem = parts[0] or None
            options = [
                Option(label=o.group(1), text=o.group(2)) for p in parts[1:] if (o := _OPT.match(p))
            ]
            sections[-1]["qs"].append((int(m.group(1)), stem, options or None))
    out: list[Section] = []
    number = 0
    for s_no, s in enumerate(sections, 1):
        questions = []
        for printed, stem, options in s["qs"]:
            number += 1
            questions.append(
                Question(
                    id=f"q{printed}",
                    number=number,
                    printed_number=printed,
                    page_no=1,
                    answer_form="choice" if options else "word",
                    stem=stem,
                    options=options,
                    cue=None,
                    points=0.25,
                )
            )
        out.append(
            Section(
                id=f"s{s_no}",
                number=s_no,
                printed_title=s["title"],
                title=s["title"],
                instructions=s["instructions"],
                points=0.25 * len(questions),
                points_source="printed",
                skill="grammar",
                groups=[
                    QuestionGroup(
                        id=f"g{s_no}", stimulus=s["stim"], pictures=[], questions=questions
                    )
                ],
            )
        )
    return Content(sections=out)


def draft(name: str, grade: int | None = 8) -> Draft:
    content = parse(name)
    return Draft(
        meta=Meta(occasion="FinalTerm", grade=grade),
        content=content,
        fingerprint=fingerprint_text(content),
        points_possible=10.0,
    )


def candidate(
    name: str, test_id: str, grade: int | None = 8, merged_into: str | None = None
) -> Candidate:
    content = parse(name)
    return Candidate(
        test_id=test_id,
        grade=grade,
        merged_into=merged_into,
        content=content,
        fingerprint=fingerprint_text(content),
    )


def test_data_files_have_40_questions() -> None:
    for name in ("base.txt", "noisy_pair.txt", "medium_pair.txt", "reordered.txt"):
        qs = [q for s in parse(name).sections for g in s.groups for q in g.questions]
        assert len(qs) == 40, name


def test_normalize_drops_numbering_punctuation_accents() -> None:
    assert normalize_for_similarity("Câu 5. Chọn  đáp án: A. cleaned, (23) ______!") == (
        "chon dap an cleaned"
    )
    assert normalize_for_similarity("II. Read the text.") == "read the text"


def test_shingles_and_jaccard_exact() -> None:
    assert shingles("abcdef") == {"abcde", "bcdef"}
    assert shingles("abc") == {"abc"}
    assert shingles("") == set()
    assert jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)
    assert jaccard(set(), {"a"}) == 0.0


def test_tiers() -> None:
    assert tier_for(0.85) == "looks_like"
    assert tier_for(0.849) == "possibly"
    assert tier_for(0.5) == "possibly"
    assert tier_for(0.499) is None
    assert tier_for(0.7, looks_like=0.9, possibly=0.6) == "possibly"


def test_identical_is_one_and_looks_like() -> None:
    out = compare(draft("base.txt"), [candidate("base.txt", "T-0001")], ref="r1")
    assert out.result.similarity == 1.0
    assert out.tier == "looks_like"
    assert out.pending is not None
    assert out.pending.kind == "possible_duplicate"
    assert out.pending.dedupe_key == "possible_duplicate:r1:T-0001"
    assert set(out.pending.proposal) == {"best_test_id", "similarity", "tier", "question_alignment"}
    assert out.result.question_alignment == {f"q{n}": f"q{n}" for n in range(1, 41)}


@pytest.mark.parametrize("case", ["noisy_pair", "medium_pair", "different"])
def test_b2_bands(case: str) -> None:
    spec = EXPECTED[case]
    out = compare(draft(spec["new"]), [candidate(spec["bank"], "T-0042")])
    lo, hi = spec["band"]
    value = out.result.similarity
    assert lo <= value <= hi if hi == 1.0 else lo <= value < hi, value
    assert out.tier == spec["tier"]
    assert (out.pending is None) == (spec["tier"] is None)
    if out.pending:
        assert out.pending.proposal["tier"] == spec["tier"]


def test_b2_reordered_alignment_equals_expected_map() -> None:
    spec = EXPECTED["reordered"]
    new, bank = parse(spec["new"]), parse(spec["bank"])
    assert align_questions(new, bank) == spec["alignment"]
    out = compare(draft(spec["new"]), [candidate(spec["bank"], "T-0042")])
    assert out.result.question_alignment == spec["alignment"]


def test_alignment_leaves_unpaired_out() -> None:
    spec = EXPECTED["medium_pair"]
    alignment = align_questions(parse(spec["new"]), parse(spec["bank"]))
    replaced = {"q3", "q4", *(f"q{n}" for n in range(17, 23)), *(f"q{n}" for n in range(29, 35))}
    assert not replaced & set(alignment)
    assert all(alignment[k] == k for k in alignment)


def test_other_grades_and_merged_tests_are_never_candidates() -> None:
    new = draft("base.txt", grade=8)
    others = [
        candidate("base.txt", "T-grade9", grade=9),
        candidate("base.txt", "T-merged", grade=8, merged_into="T-0001"),
        candidate("base.txt", "T-merged-nograde", grade=None, merged_into="T-0001"),
    ]
    out = compare(new, others)
    assert out.result.best_test_id is None
    assert out.pending is None
    out = compare(new, [*others, candidate("different.txt", "T-diff")])
    assert out.result.best_test_id == "T-diff"
    assert out.tier is None


def test_bank_test_with_unknown_grade_stays_eligible() -> None:
    new = draft("noisy_pair.txt", grade=8)
    out = compare(
        new,
        [
            candidate("base.txt", "T-grade9", grade=9),
            candidate("base.txt", "T-nograde", grade=None),
        ],
    )
    assert out.result.best_test_id == "T-nograde"
    assert out.tier == "looks_like"


def test_unknown_grade_compares_with_all_non_merged() -> None:
    new = draft("base.txt", grade=None)
    out = compare(
        new,
        [
            candidate("base.txt", "T-grade9", grade=9),
            candidate("base.txt", "T-merged", merged_into="T-0001"),
        ],
    )
    assert out.result.best_test_id == "T-grade9"
    assert out.tier == "looks_like"


def test_best_candidate_wins() -> None:
    out = compare(
        draft("noisy_pair.txt"),
        [candidate("medium_pair.txt", "T-medium"), candidate("base.txt", "T-base")],
    )
    assert out.result.best_test_id == "T-base"


def test_similarity_symmetric() -> None:
    a = (DATA / "base.txt").read_text(encoding="utf-8")
    b = (DATA / "medium_pair.txt").read_text(encoding="utf-8")
    assert similarity(a, b) == similarity(b, a)
