"""Equal points (PRD D13 v8.0, data-model v1.19) and option letters (step 22.4.4).

- The score is always out of :data:`TOTAL_POINTS` (10). Every question of a graded section is
  worth ``10 / N`` (N = the graded questions of the test; 0.25 with 40, 0.2 with 50); a graded
  section's points are the sum of its questions'; a writing section (``graded=False``) and its
  questions count for nothing; a section with no questions adds nothing. ``points_source`` is
  ``"equal"``. :func:`equal_points` runs on every content save, so ``points_possible`` and the
  grade's ``score_possible`` are always equal: 10, or 0 with no graded question.
- :func:`clean_label`: an option label such as ``"A."``, ``"B)"`` or ``" c "`` is stored as the
  bare capital letter (the extraction merge, the test-text read-back and ``validate_choice``).

Pure: no I/O.
"""

from __future__ import annotations

import re

from etach.domain.models import Option, TestContent

__all__ = ["TOTAL_POINTS", "clean_label", "clean_options", "equal_points", "points_possible"]

TOTAL_POINTS = 10.0

_LABEL = re.compile(r"^[\s(\[]*([A-Za-z])\s*[.):\]\-]?\s*$")


def clean_label(label: str) -> str:
    """``"A."``, ``"(b)"``, ``"C)"``, ``" d "`` → ``"A"``…``"D"``; anything else is only
    stripped (``???`` stays as it is, so the validator still sees it)."""
    m = _LABEL.match(label)
    return m.group(1).upper() if m else label.strip()


def clean_options(options: list[Option] | None) -> list[Option] | None:
    """The options with :func:`clean_label` applied (``None`` stays ``None``)."""
    if options is None:
        return None
    return [
        o
        if o.label == clean_label(o.label)
        else o.model_copy(update={"label": clean_label(o.label)})
        for o in options
    ]


def _graded_count(content: TestContent) -> int:
    return sum(len(g.questions) for s in content.sections if s.graded for g in s.groups)


def points_possible(content: TestContent) -> float:
    """10 when the test has a graded question, else 0."""
    return TOTAL_POINTS if _graded_count(content) else 0.0


def equal_points(content: TestContent) -> TestContent:
    """A copy of ``content`` with the equal points set on every section and question (and the
    option letters cleaned)."""
    n = _graded_count(content)
    per = TOTAL_POINTS / n if n else 0.0
    sections = []
    for s in content.sections:
        groups = []
        total = 0.0
        for g in s.groups:
            questions = []
            for q in g.questions:
                pts = per if s.graded else 0.0
                total += pts
                questions.append(
                    q.model_copy(update={"points": pts, "options": clean_options(q.options)})
                )
            groups.append(g.model_copy(update={"questions": questions}))
        sections.append(
            s.model_copy(
                update={"points": round(total, 6), "points_source": "equal", "groups": groups}
            )
        )
    return content.model_copy(update={"sections": sections})
