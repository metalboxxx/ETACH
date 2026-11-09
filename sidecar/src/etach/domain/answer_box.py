"""Answer boxes out of a photo page's OCR text (step 22.6.1, step22.6-plan D2).

A Vietnamese test prints an answer box under a section: a heading "Phần trả lời" (often with an
instruction after it) and rows of numbered blanks (``1. ____ 2. ____``, ``35. ...``). They are
not questions, but the structuring model made sections and extra questions of them (Test G8).
:func:`strip_answer_boxes` removes them before ``structure_text_page`` sees the text; the
prompt's photo rules say the same, as the second barrier.

- The heading "Phần trả lời" is matched without accents (``normalize.name_search``), so
  GLM-OCR's misreads "Phàn trả lối" and "Phàn trà lòi" match; "ANSWER" / "ANSWERS" in capitals,
  or "Answer:", count as a heading only when nothing but numbers, with or without blanks,
  follows on its line (so "Answer the questions", "Answer: 1. He goes to school" and
  "ANSWERS 5 points" stay). The whole heading line goes, with any blanks on it.
- The lines right after it that hold only numbers, with or without blanks (``1. ____``,
  ``35. ...``, ``29. 30. 31.``), go too; empty lines between them are allowed. The first other
  line ends the box and stays.
- Without a heading, a line of two or more numbered blanks and nothing else is a box row and
  goes (Test K); a single ``29. ____`` stays, so a real question is never removed.
"""

from __future__ import annotations

import re

from etach.domain.normalize import name_search

__all__ = ["strip_answer_boxes"]

_HEADING = re.compile(r"^\W*phan tra loi\b")
_BLANK = r"(?:_{2,}|\.{3,}|…+)"
#: "ANSWER" / "ANSWERS" / "Answer:" with nothing after it on its line but numbers, each with or
#: without a blank (R22.6.6.4: "Answer: 1. He goes to school" and "ANSWERS 5 points" stay)
_EN_HEADING = re.compile(
    rf"^\W*(?:ANSWERS?\b|Answers?:)\s*:?\s*(?:\d{{1,3}}\s*[.)]?\s*{_BLANK}?\s*)*$"
)
#: after a heading: one or more ``N.`` (``)`` for ``.`` too), each with or without a blank
_BOX_ROW = re.compile(rf"^\s*(?:\d{{1,3}}\s*[.)]\s*{_BLANK}?\s*)+$")
#: with no heading: two or more ``N. ____`` / ``N. ...`` / ``N. …``, nothing else
_HEADLESS_ROW = re.compile(rf"^\s*(?:\d{{1,3}}\s*[.)]\s*{_BLANK}\s*){{2,}}$")


def strip_answer_boxes(text: str) -> str:
    """``text`` without its answer boxes; text without one comes back unchanged."""
    lines = text.split("\n")
    kept: list[str] = []
    empties: list[str] = []  # empty lines inside a box: dropped only when more blanks follow
    in_box = False
    for line in lines:
        if _HEADING.match(name_search(line)) or _EN_HEADING.match(line):
            in_box, empties = True, []
            continue
        if in_box and not line.strip():
            empties.append(line)
            continue
        if (in_box and _BOX_ROW.match(line)) or _HEADLESS_ROW.match(line):
            in_box, empties = True, []
            continue
        in_box = False
        kept.extend(empties)
        empties = []
        kept.append(line)
    kept.extend(empties)
    if len(kept) == len(lines):
        return text
    return "\n".join(kept)
