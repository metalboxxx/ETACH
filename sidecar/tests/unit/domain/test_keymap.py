"""map_key over plan Appendix B.3 (R8.1.7)."""

from __future__ import annotations

import pytest
from support.guards import no_io  # noqa: F401

from etach.domain.keymap import KeyRaw, map_key
from etach.domain.llm_schemas import KeyLabelAnswer
from etach.domain.models import OmittedSection, Question, QuestionGroup, Section
from etach.domain.models import TestContent as Content
from etach.domain.models import TestMetadata as Meta
from etach.domain.working import TestDraft as Draft

pytestmark = pytest.mark.usefixtures("no_io")

# B.1: printed sections after the listening one (Q1-4), canonical = printed - 4
B1 = [
    ("II", 5, 14),
    ("III", 15, 16),
    ("IV", 17, 22),
    ("V", 23, 28),
    ("VI", 29, 34),
    ("VI", 35, 36),
    ("VIII", 37, 40),
]


def b1_draft() -> Draft:
    sections = []
    for s_no, (title, first, last) in enumerate(B1, 1):
        qs = [
            Question(
                id=f"c{p - 4}",
                number=p - 4,
                printed_number=p,
                page_no=1 + p // 15,
                answer_form="choice",
                stem=f"stem {p}",
                options=None,
                cue=None,
                points=0.25,
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
                groups=[QuestionGroup(id=f"g{s_no}", stimulus=None, pictures=[], questions=qs)],
            )
        )
    meta = Meta(
        occasion="FinalTerm",
        grade=8,
        omitted_sections=[OmittedSection(title="I", questions=[1, 2, 3, 4], points=1.0)],
    )
    return Draft(meta=meta, content=Content(sections=sections), fingerprint="", points_possible=9.0)


def test_b3_case_a() -> None:
    labels = [*range(1, 33), 32, *range(33, 42)]
    raw = [(str(n), "ABCD"[i % 4]) for i, n in enumerate(labels)]
    out = map_key(raw, b1_draft(), threshold=0.7, ref="r1")
    got = {e.question_id: e.accepted[0] for e in out.entries}
    assert len(out.entries) == 36
    assert [e.question_id for e in out.entries] == [f"c{n}" for n in range(1, 37)]
    # labels 5-32 (first "32") -> canonical 1-28; labels 33-40 -> canonical 29-36
    for i, n in enumerate(labels):
        if 5 <= n <= 32 and i < 32:
            assert got[f"c{n - 4}"] == raw[i][1]
        if 33 <= n <= 40:
            assert got[f"c{n - 4}"] == raw[i][1]
    assert [p.kind for p in out.pendings] == ["key_unmapped", "key_unmapped"]
    assert [p.proposal["label"] for p in out.pendings] == ["32", "41"]
    assert out.pendings[0].proposal["answer"] == raw[32][1]
    assert out.pendings[0].dedupe_key == "key_unmapped:r1:32"


def test_b3_case_b() -> None:
    labels = [*range(1, 33), 32, *range(34, 41)]  # 33 missing
    raw = [(str(n), f"x{i}") for i, n in enumerate(labels)]
    out = map_key(raw, b1_draft(), threshold=0.7)
    got = {e.question_id: e.accepted[0] for e in out.entries}
    assert out.pendings == []
    assert got["c29"] == "x32"  # the second "32" -> canonical 29 (printed 33)
    assert got["c28"] == "x31"  # the first "32"
    assert len(out.entries) == 36


def test_unknown_label_one_key_unmapped() -> None:
    raw = [("5", "A"), ("99", "B"), ("Q", "C")]
    out = map_key(raw, b1_draft(), threshold=0.7)
    assert [e.question_id for e in out.entries] == ["c1"]
    assert [p.proposal["reason"] for p in out.pendings] == ["no_question", "no_question"]


def test_listening_labels_skipped_silently() -> None:
    out = map_key([("1", "A"), ("4", "B")], b1_draft(), threshold=0.7)
    assert out.entries == [] and out.pendings == []


def test_status_by_confidence() -> None:
    raw = [KeyRaw("5", "A", 0.9), KeyRaw("6", "B", 0.7), KeyRaw("7", "C", 0.69), ("8", "D")]
    out = map_key(raw, b1_draft(), threshold=0.7)
    assert out.status == {
        "c1": "from_key_photo",
        "c2": "from_key_photo",
        "c3": "ai_unverified",
        "c4": "ai_unverified",
    }
    assert [e.confidence for e in out.entries] == [0.9, 0.7, 0.69, 0.0]
    three = map_key([("5", "A", 0.95)], b1_draft(), threshold=0.7)
    assert three.status == {"c1": "from_key_photo"}


def test_accepts_key_label_answer_objects() -> None:
    out = map_key([KeyLabelAnswer(label="Câu 6", answer=" B ")], b1_draft(), threshold=0.7)
    assert out.entries[0].question_id == "c2"
    assert out.entries[0].accepted == ["B"]
