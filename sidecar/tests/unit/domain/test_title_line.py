"""R22.2.2.6: the on-screen and printed test show the DOCX's title and details line. The app's
``lib/testTitle.ts`` is checked against the same cases (``title_line_cases.json``).

R22.5.2.12: a case with ``graded_questions`` gets that many graded questions, so its details line
ends with each question's value (``points_each``, D7); the app reads ``points_each`` from the
case, as it reads it from ``GET /tests/{id}``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from etach.domain import docx_export
from etach.domain import models as m
from etach.domain.test_text import points_each

CASES: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent / "title_line_cases.json").read_text(encoding="utf-8")
)


def _content(graded_questions: int) -> m.TestContent:
    if not graded_questions:
        return m.TestContent(sections=[])
    qs = [
        m.Question.model_construct(id=f"q{n}", number=n, printed_number=n)
        for n in range(1, graded_questions + 1)
    ]
    group = m.QuestionGroup.model_construct(id="g1", stimulus=None, pictures=[], questions=qs)
    section = m.Section.model_construct(id="s1", graded=True, groups=[group])
    return m.TestContent.model_construct(sections=[section])


def _test(case: dict[str, Any]) -> m.Test:
    return m.Test.model_construct(
        meta=m.TestMetadata(**case["meta"]),
        content=_content(case.get("graded_questions", 0)),
        points_possible=case["points_possible"],
    )


@pytest.mark.parametrize("case", CASES, ids=[c["title"] for c in CASES])
def test_title_and_details_line(case: dict[str, Any]) -> None:
    test = _test(case)
    assert test.meta.display_name() == case["title"]
    assert docx_export.meta_line(test) == case["details"]
    assert points_each(test.content) == case.get("points_each")


def test_a_case_shows_each_question_value() -> None:
    """R22.5.2.12: the shared cases hold at least one ``points_each`` case (40 → 0.25)."""
    assert any(c.get("points_each") == 0.25 and c["details"].endswith("0.25 each") for c in CASES)


def test_the_docx_writes_them_first() -> None:
    case = CASES[0]
    doc = docx_export.test_document(_test(case))
    texts = [p.text for p in doc.paragraphs[:2]]
    assert texts == [case["title"], case["details"]]
