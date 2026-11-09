"""Save as Word (step 22.1.6, PRD D4 v5.0): the clean test, its key and a grade report as DOCX.

- :func:`test_document`: the print view's content in its order (the test's text form,
  data-model §2.3a, without the editing markers): the title and metadata line ("10 points ·
  0.25 each", v1.21, D7), each section heading (no points; a writing section says "[not graded]")
  and its instructions, passages, picture placeholders, numbered questions
  with their options, cues and answer openings. No key answers. Text is written as stored
  (Vietnamese NFC kept);
  the RichText markers (``**bold**``, ``<u>underline</u>``) become bold / underlined runs.
- :func:`key_document`: a separate file, each question number with its accepted answers.
- :func:`report_document`: the score, every answer's verdict, then what the report panel shows
  (summary, questions for the student, weak points, careless mistakes, explanations). Skills
  show their English names and no taxonomy code is left in the AI-written text; the explanations
  follow the printed numbers, then the wrong answer (step 22.4.6).
- :func:`save_unique`: writes into one folder, never overwriting (``name (2).docx``).

Fonts are the app's print fonts: Noto Serif for the text, Be Vietnam Pro for headings (Word falls
back to its own fonts when they are not installed).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph

from etach.domain.models import AnswerKey, Explanation, GradeReport, Question, Test
from etach.domain.skills import name_codes, skill_name
from etach.domain.test_text import _picture_line, heading_text, points_each

__all__ = [
    "HEADING_FONT",
    "TEXT_FONT",
    "VERDICT_MARK",
    "VerdictRow",
    "key_document",
    "meta_line",
    "report_document",
    "safe_file_name",
    "save_unique",
    "test_document",
]

TEXT_FONT = "Noto Serif"
HEADING_FONT = "Be Vietnam Pro"
#: The report's verdict cell; an uncertain grade is worded (the teacher's answer 2, step 22.2.7).
VERDICT_MARK = {"correct": "✓", "incorrect": "✗", "uncertain": "AI unsure grade", "ungraded": "–"}  # noqa: RUF001

_RICH = re.compile(r"(\*\*[^*]+\*\*|<u>.*?</u>)")
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _set_font(style_font: object, name: str) -> None:
    font = style_font  # docx.text.font.Font
    font.name = name  # type: ignore[attr-defined]
    rpr = font.element.get_or_add_rPr()  # type: ignore[attr-defined]
    fonts = rpr.get_or_add_rFonts()
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attr), name)


def _new_document() -> DocxDocument:
    doc = Document()
    normal = doc.styles["Normal"]
    _set_font(normal.font, TEXT_FONT)
    normal.font.size = Pt(11)
    for name in ("Title", "Heading 1", "Heading 2"):
        _set_font(doc.styles[name].font, HEADING_FONT)
    return doc


def _rich(par: Paragraph, text: str) -> Paragraph:
    """The RichText subset (data-model §2.3) as runs; line breaks stay line breaks."""
    for part in _RICH.split(text):
        if not part:
            continue
        bold = part.startswith("**") and part.endswith("**") and len(part) > 4
        underline = part.startswith("<u>") and part.endswith("</u>")
        body = part[2:-2] if bold else part[3:-4] if underline else part
        lines = body.split("\n")
        for i, line in enumerate(lines):
            run = par.add_run(line)
            run.bold = bold or None
            run.underline = underline or None
            if i < len(lines) - 1:
                run.add_break()
    return par


def meta_line(test: Test) -> str:
    """The line under the title: the parts the display name leaves out (duration, test code),
    then the points and each question's value ("10 points · 0.25 each", v1.21, D7)."""
    m = test.meta
    parts: list[str] = []
    if m.duration_minutes:
        parts.append(f"{m.duration_minutes} minutes")
    if m.test_code:
        parts.append(f"Code {m.test_code}")
    parts.append(f"{_num(test.points_possible)} points")
    each = points_each(test.content)
    if each is not None:
        parts.append(f"{_num(each)} each")
    return " · ".join(parts)


def _num(x: float | None) -> str:
    if x is None:
        return "–"  # noqa: RUF001
    return str(round(x * 100) / 100).removesuffix(".0")


def _question(doc: DocxDocument, q: Question) -> None:
    par = doc.add_paragraph()
    par.add_run(f"{q.printed_number}. ").bold = True
    if q.stem:
        _rich(par, q.stem)
    if q.cue:
        doc.add_paragraph(f"({q.cue})")
    if q.options:
        _rich(doc.add_paragraph(), "    ".join(f"{o.label}. {o.text}" for o in q.options))
    if q.answer_start:  # the printed answer line with its opening words (data-model v1.16)
        doc.add_paragraph(f"{q.answer_start} ____")


def test_document(test: Test, picture_paths: Mapping[str, str] | None = None) -> DocxDocument:
    """The clean test, as the print view shows it. No key answers."""
    doc = _new_document()
    doc.add_heading(test.meta.display_name(), level=0)
    doc.add_paragraph(meta_line(test))
    for s in test.content.sections:
        doc.add_heading(heading_text(s), level=2)  # no points (v1.21, D7)
        if s.instructions:
            doc.add_paragraph(s.instructions).runs[0].italic = True
        for g in s.groups:
            if g.stimulus:
                _rich(doc.add_paragraph(), g.stimulus)
            for p in g.pictures:
                doc.add_paragraph(_picture_line(p, picture_paths))
            for q in g.questions:
                _question(doc, q)
    return doc


def key_document(test: Test, keys: Sequence[AnswerKey]) -> DocxDocument:
    """The key: each question number with its accepted answers (a separate file)."""
    doc = _new_document()
    doc.add_heading(f"Key: {test.meta.display_name()}", level=0)
    by_id = {k.question_id: k for k in keys}
    for s in test.content.sections:
        for g in s.groups:
            for q in g.questions:
                key = by_id.get(q.id)
                answers = " / ".join(key.accepted) if key and key.accepted else "(no key)"
                par = doc.add_paragraph()
                par.add_run(f"{q.printed_number}. ").bold = True
                par.add_run(answers)
    return doc


class VerdictRow:
    """One report row: printed number, the answer as read (or corrected), the verdict."""

    def __init__(self, printed_number: int, value: str | None, verdict: str) -> None:
        self.printed_number = printed_number
        self.value = value
        self.verdict = verdict


def report_document(
    title: str,
    score_earned: float | None,
    score_possible: float | None,
    report: GradeReport,
    rows: Sequence[VerdictRow],
    explanations: Sequence[Explanation],
    numbers: Mapping[str, int],
) -> DocxDocument:
    """The grade report, as the report panel shows it."""
    doc = _new_document()
    doc.add_heading(title, level=0)
    doc.add_paragraph(
        f"Score: {_num(score_earned)}/{_num(score_possible)}"
        f" · {_num(report.uncertain_points)} unsure"
    )
    ordered = sorted(rows, key=lambda r: r.printed_number)
    table = doc.add_table(rows=0, cols=3)
    for r in ordered:
        cells = table.add_row().cells
        cells[0].text = f"{r.printed_number}."
        cells[1].text = r.value if r.value is not None else "(blank)"
        cells[2].text = VERDICT_MARK.get(r.verdict, "–")  # noqa: RUF001
    if report.summary_vi:
        doc.add_paragraph(name_codes(report.summary_vi))
    if report.teacher_questions:
        doc.add_heading("Questions for the student", level=2)
        for q in report.teacher_questions:
            means = name_codes(q.what_answers_mean_vi)
            text = name_codes(q.question_vi) + (f" — {means}" if means else "")
            doc.add_paragraph(text, style="List Number")
    if report.weak_points:
        doc.add_heading("Weak points", level=2)
        for w in report.weak_points:
            note = f" — {name_codes(w.note_vi)}" if w.note_vi else ""
            text = f"{skill_name(w.skill_tag)}: {w.wrong}/{w.seen} wrong{note}"
            doc.add_paragraph(text, style="List Bullet")
    if report.careless_notes:
        doc.add_heading("Careless mistakes", level=2)
        for n in report.careless_notes:
            doc.add_paragraph(name_codes(n), style="List Bullet")
    if explanations:
        doc.add_heading("Explanations", level=2)
        in_order = sorted(
            explanations, key=lambda e: (numbers.get(e.question_id, 0), e.wrong_answer_norm)
        )
        for e in in_order:
            text = name_codes(e.text_vi)
            doc.add_paragraph(f"{numbers.get(e.question_id, '?')}. {text}")
    return doc


def safe_file_name(name: str) -> str:
    """A Windows file name from a display name: forbidden characters → ``_``, no trailing dots or
    spaces, no reserved device names, at most 150 characters."""
    out = _FORBIDDEN.sub("_", name).strip().rstrip(". ")
    out = out[:150].rstrip(". ") or "export"
    if out.split(".")[0].upper() in _RESERVED:
        out = f"_{out}"
    return out


def save_unique(doc: DocxDocument, folder: Path, stem: str) -> Path:
    """Save as ``<folder>/<stem>.docx``; if it exists, ``<stem> (2).docx``, ``(3)`` … Never
    overwrites (exclusive create)."""
    folder.mkdir(parents=True, exist_ok=True)
    base = safe_file_name(stem)
    n = 1
    while True:
        path = folder / (f"{base}.docx" if n == 1 else f"{base} ({n}).docx")
        try:
            with path.open("xb") as fh:
                doc.save(fh)
            return path
        except FileExistsError:
            n += 1
