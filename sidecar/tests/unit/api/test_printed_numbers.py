"""R22.2.4.1 (sidecar side): a test whose listening part was left out (printed 1-5 omitted,
printed 6.. on the paper, internal numbers 1..) shows the printed numbers in the test and key
DOCX. Internal numbers stay for matching (their tests are unchanged)."""

from __future__ import annotations

from unit.api.test_step22_1_6 import SYNTH, _key, _test_of, _text

from etach.domain import docx_export
from etach.domain import models as m


def _shifted(content: m.TestContent, by: int) -> m.TestContent:
    sections = []
    for s in content.sections:
        groups = []
        for g in s.groups:
            qs = [q.model_copy(update={"printed_number": q.number + by}) for q in g.questions]
            groups.append(g.model_copy(update={"questions": qs}))
        sections.append(s.model_copy(update={"groups": groups}))
    return content.model_copy(update={"sections": sections})


def test_docx_shows_printed_numbers_not_internal() -> None:
    test = _test_of(_shifted(SYNTH["edge_cases"], 5))
    qs = [q for s in test.content.sections for g in s.groups for q in g.questions]
    assert qs[0].number == 1 and qs[0].printed_number == 6
    lines = _text(docx_export.test_document(test))
    for q in qs:
        assert any(x.startswith(f"{q.printed_number}. ") for x in lines)
    assert not any(x.startswith("1. ") for x in lines)
    key_lines = _text(docx_export.key_document(test, [_key(qs[0].id, ["B"])]))
    assert key_lines[1:] == [
        f"{q.printed_number}. " + ("B" if q.id == qs[0].id else "(no key)") for q in qs
    ]
