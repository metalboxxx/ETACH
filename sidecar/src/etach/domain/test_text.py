"""The test as text (data-model §2.3a, PRD D27): ``render(content) → text`` and
``read(text, previous) → content | errors``.

The test page in the app is one free-text page, like a Word document. On Save the sidecar reads
the text back into sections, groups and questions. Deterministic code, no model calls. Pure: no I/O.

The text looks like the printed test. Each line is one of these (data-model §2.3a has the
grammar for the teacher):

==========================  ===============================================================
``— Page 2 —``              the paper page the next questions are printed on
``# II. WORD FORM``          a section heading (v1.21, D7): ``#``, then the printed title; no
                            points (each question's value is on the line under the test title,
                            :func:`points_each`). A bracket at the end may say ``not graded`` (a
                            writing section) and ``title: <title>`` (when the title differs):
                            ``# VI. WRITING  [not graded]``. The form before v1.21, a line ending
                            in a points bracket (``II.  [2.5 points, 0.25 each]``,
                            ``[0.25 points each]``, ``[3 points: 1 / 1 / 0.5 / 0.5]``), still
                            reads as a heading; its points are ignored (10 / graded questions)
``[Passage]`` … ``[End of passage]``   a group's passage or dialogue, kept exactly as typed
``[Hình: files/ab/<id>.jpg · trang 3]``  a picture (PRD D11)
``12. stem``                a question with its printed number
``   A. text``              an option (several may share a line, two spaces apart)
``   Cue: (consume)``       the word or phrase given with the question
``   Start: My brother``    the words printed to start the answer line (a sentence question;
                            ``answer_start``, data-model v1.16)
other lines                 more text for what is above them: the section's instructions, the
                            question's stem, the option's text, the cue or the start
``\\…``                     a line that would otherwise be read as one of the forms above
==========================  ===============================================================

Blank lines are only spacing (except inside a passage). Identity (data-model §2.3a): a question
that is still there after an edit keeps its ``id`` (sequence alignment of the questions, then the
closest match); new questions get new ids. Fields the teacher does not type (ids, ``skill``,
``answer_form``, ``old_type``, ``None`` vs ``""``) come from ``previous`` when the item matches one
there; ``context`` always follows the group's passage (step 22.5.3). The text shows no form.

Round trip: ``read(render(c), c).content == c`` for every valid ``TestContent``.

Step 22.6.5 (way 2a): :func:`read_ocr_page` reads one photo page that GLM-OCR wrote in this
format into the per-page output of ``structure_text_page``; :func:`read` is unchanged.
"""

from __future__ import annotations

import difflib
import hashlib
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from etach.domain.llm_schemas import (
    PictureRegion,
    TranscribedGroup,
    TranscribedQuestion,
    TranscribedSection,
    TranscribeOut,
)
from etach.domain.models import (
    AnswerForm,
    Option,
    PictureRef,
    Question,
    QuestionGroup,
    Section,
    TestContent,
)
from etach.domain.points import TOTAL_POINTS, clean_label, equal_points
from etach.domain.renumber import clean_option_label
from etach.domain.renumber import question_id as make_question_id

__all__ = [
    "PASSAGE_END",
    "PASSAGE_START",
    "OcrPageRead",
    "ReadResult",
    "TextError",
    "format_number",
    "heading_text",
    "points_each",
    "read",
    "read_ocr_page",
    "render",
]

PASSAGE_START = "[Passage]"
PASSAGE_END = "[End of passage]"
_ESC = "\\"
_INDENT = "   "

_DASHES = "-—–"  # noqa: RUF001 (hyphen, em dash, en dash)
_PAGE = re.compile(rf"^\s*[{_DASHES}]+\s*page\s+(\d+)\s*[{_DASHES}]*\s*$", re.IGNORECASE)
_PICTURE = re.compile(r"^\s*\[(?:Hình|Hinh|Picture)\s*:\s*(\S+)\s*·\s*trang\s+(\d+)\s*\]\s*$")
_QUESTION = re.compile(r"^\s*(\d+)\.(?: (.*))?$")
_OPTION = re.compile(r"^\s*([A-HTa-ht]|\?\?\?)\.(?: (.*))?$")
_OPTION_SPLIT = re.compile(r" {2,}(?=(?:[A-HTa-ht]|\?\?\?)\.(?: |$))")
_CUE = re.compile(r"^\s*cue:(?: (.*))?$", re.IGNORECASE)
_START = re.compile(r"^\s*start:(?: (.*))?$", re.IGNORECASE)
_TAG_AT_END = re.compile(r"\[([^\[\]]*)\]\s*$")
# v1.21 (D7): a heading is "# <printed title>", with an optional bracket ("[not graded]")
_HEADING_MARK = re.compile(r"^\s*# ?(.*)$")
_POINT_WORD = r"(?:points?|pts?|điểm|diem)"
_LOOKS_LIKE_POINTS = re.compile(r"^\s*[\d.,]+\s*" + _POINT_WORD + r"\b", re.IGNORECASE)
_POINTS_HEAD = re.compile(
    r"^\s*(\d+(?:[.,]\d+)?|\d*\.\d+)\s*" + _POINT_WORD + r"(?P<each>\s+each)?\s*",
    re.IGNORECASE,
)
# v1.20.1: "0.77 each" after the total (also "0.77 points each"); read and ignored
_EACH_PART = re.compile(r"^(\d+(?:[.,]\d+)?|\d*\.\d+)\s*(?:" + _POINT_WORD + r"\s+)?each$")
_NUM = re.compile(r"^\s*(\d+(?:\.\d+)?|\.\d+)\s*$")
_BLANK = "____"


@dataclass(frozen=True)
class TextError:
    """A line the reader cannot understand (1-based ``line``; ``None`` for the whole text)."""

    line: int | None
    message: str


@dataclass
class ReadResult:
    """The content read from the text, or the errors (then ``content`` is ``None``).

    ``question_lines`` maps each question id to the line of its number (for validator messages);
    ``dropped`` lists the ids of ``previous`` questions that the text no longer has.
    """

    content: TestContent | None
    errors: list[TextError] = field(default_factory=list)
    question_lines: dict[str, int] = field(default_factory=dict)
    section_lines: dict[str, int] = field(default_factory=dict)
    dropped: list[str] = field(default_factory=list)


# --- numbers ---------------------------------------------------------------------------------


def format_number(x: float) -> str:
    """The shortest text that reads back as exactly ``x``: 2.0 → "2", 0.25 → "0.25"."""
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return repr(float(x))


def _parse_number(text: str) -> float | None:
    m = _NUM.match(text.replace(",", ".")) if text.count(",") <= 1 else None
    return float(m.group(1)) if m else None


# --- line kinds ------------------------------------------------------------------------------

LineKind = Literal[
    "escaped",
    "passage_start",
    "passage_end",
    "picture",
    "page",
    "heading",
    "question",
    "option",
    "cue",
    "start",
    "blank",
    "text",
]


def _is_heading(line: str) -> bool:
    """A ``#`` line (v1.21), or a line ending in a points bracket (the form before v1.21)."""
    if _HEADING_MARK.match(line):
        return True
    m = _TAG_AT_END.search(line)
    return bool(m and _LOOKS_LIKE_POINTS.match(m.group(1)))


def _kind(line: str) -> LineKind:
    """What a line outside a passage is (the order is the precedence)."""
    if line.startswith(_ESC):
        return "escaped"
    stripped = line.strip()
    if not stripped:
        return "blank"
    if stripped.lower() == PASSAGE_START.lower():
        return "passage_start"
    if stripped.lower() == PASSAGE_END.lower():
        return "passage_end"
    if _PICTURE.match(line):
        return "picture"
    if _PAGE.match(line):
        return "page"
    if _is_heading(line):
        return "heading"
    if _QUESTION.match(line):
        return "question"
    if _OPTION.match(line):
        return "option"
    if _CUE.match(line):
        return "cue"
    if _START.match(line):
        return "start"
    return "text"


# --- render ----------------------------------------------------------------------------------


def _field_lines(value: str) -> list[str]:
    """A text field as content lines, escaped where a line would read as something else.

    Blank lines at either end are escaped (the reader drops unescaped ones there)."""
    lines = value.split("\n")
    first = next((i for i, ln in enumerate(lines) if ln.strip()), len(lines))
    last = max((i for i, ln in enumerate(lines) if ln.strip()), default=-1)
    out: list[str] = []
    for i, ln in enumerate(lines):
        edge_blank = not ln.strip() and (i < first or i > last)
        if edge_blank or _kind(ln) not in ("text", "blank"):
            out.append(_ESC + ln)
        else:
            out.append(ln)
    return out


def _passage_lines(value: str) -> list[str]:
    out: list[str] = []
    for ln in value.split("\n"):
        if ln.startswith(_ESC) or ln.strip().lower() == PASSAGE_END.lower():
            out.append(_ESC + ln)
        else:
            out.append(ln)
    return out


def points_each(content: TestContent) -> float | None:
    """What each graded question is worth (PRD D13): 10 ÷ the graded questions, unrounded;
    ``None`` when there is no graded question. The line under the test title shows it (D7)."""
    n = sum(len(g.questions) for s in content.sections if s.graded for g in s.groups)
    return TOTAL_POINTS / n if n else None


def _heading_tag(section: Section) -> str:
    """The bracket after a heading (v1.21, D7: no points): ``not graded`` for a writing section,
    ``title: <title>`` when the title differs from the printed one; ``""`` when there is none."""
    parts: list[str] = []
    if not section.graded:
        parts.append("not graded")
    if section.title != section.printed_title:
        parts.append(f"title: {section.title}")
    return "[" + ", ".join(parts) + "]" if parts else ""


def heading_text(section: Section) -> str:
    """The heading as the print view and the Word file show it: the printed title (else the
    title), and ``[not graded]`` for a writing section. No points (v1.21, D7)."""
    title = section.printed_title or section.title
    return f"{title}  [not graded]" if not section.graded else title


def _heading_line(section: Section) -> str:
    """``# <printed title>``, then the tag when there is one (v1.21). A printed title that ends
    with a bracket of its own gets an empty ``[]`` after it, so the bracket stays in the title."""
    head = f"# {section.printed_title}" if section.printed_title else "#"
    tag = _heading_tag(section)
    if not tag and _TAG_AT_END.search(section.printed_title):
        tag = "[]"
    return f"{head}  {tag}" if tag else head


def _picture_line(ref: PictureRef, paths: Mapping[str, str] | None) -> str:
    path = (paths or {}).get(ref.file_id)
    ext = "jpg"
    if path and "." in path.rsplit("/", 1)[-1]:
        ext = path.rsplit(".", 1)[-1].lower()
    return f"[Hình: files/{ref.file_id[:2]}/{ref.file_id}.{ext} · trang {ref.page_no}]"


def _options_one_line(options: Sequence[Option]) -> str | None:
    """``   A. x    B. y`` when that reads back to exactly these options, else ``None``."""
    if len(options) < 2:
        return None
    for o in options:
        if not o.text or o.text != o.text.strip() or "\n" in o.text or "  " in o.text:
            return None
    line = _INDENT + "    ".join(f"{o.label}. {o.text}" for o in options)
    if len(line) > 72 or _kind(line) != "option":
        return None
    parsed = _split_options(line)
    if parsed != [(o.label, o.text) for o in options]:
        return None
    return line


def _head_ok(head: str, kind: LineKind) -> bool:
    if _kind(head) != kind:
        return False
    return kind != "option" or len(_split_options(head)) == 1


def _field_after(marker: str, text: str, kind: LineKind) -> list[str]:
    r"""A field written after its marker (``12.``, ``   A.``, ``   Cue:``), more lines below.

    The first line goes on the marker's line when that line still reads as ``kind``; otherwise
    the whole text goes below the bare marker. ``<marker> \`` says "the first line is empty"."""
    if text == "":
        return [marker]
    first, *rest = text.split("\n")
    head = f"{marker} {first}"
    if first.strip() and not first.startswith(_ESC) and _head_ok(head, kind):
        return [head, *(_field_lines("\n".join(rest)) if rest else [])]
    if not first:
        return [f"{marker} {_ESC}", *_field_lines("\n".join(rest))]
    return [marker, *_field_lines(text)]


def _question_lines(q: Question) -> list[str]:
    lines = _field_after(f"{q.printed_number}.", q.stem or "", "question")
    if q.options:
        # step 22.5.2: a stored label that still carries punctuation ("A.", "A..") is written as
        # its bare letter, so the line reads "A. text", not "A.." with the text below it
        options = [o.model_copy(update={"label": clean_option_label(o.label)}) for o in q.options]
        one = _options_one_line(options)
        if one is not None:
            lines.append(one)
        else:
            for o in options:
                lines += _field_after(f"{_INDENT}{o.label}.", o.text, "option")
    if q.cue is not None:
        lines += _field_after(f"{_INDENT}Cue:", q.cue, "cue")
    if q.answer_start is not None:
        lines += _field_after(f"{_INDENT}Start:", q.answer_start, "start")
    return lines


def render(content: TestContent, picture_paths: Mapping[str, str] | None = None) -> str:
    """The test as text (module docstring). ``picture_paths`` (``file_id`` → stored path) gives
    the picture placeholders their real file extension; without it they say ``.jpg``."""
    out: list[str] = []
    page = 1
    first_q = next(
        (q for s in content.sections for g in s.groups for q in g.questions),
        None,
    )
    if first_q is not None:
        page = first_q.page_no
        out += [f"— Page {page} —", ""]

    def page_to(p: int) -> None:
        nonlocal page
        if p != page:
            page = p
            out.extend([f"— Page {p} —", ""])

    for section in content.sections:
        s_first = next((q for g in section.groups for q in g.questions), None)
        if s_first is not None:
            page_to(s_first.page_no)
        out.append(_heading_line(section))
        if section.instructions:
            out += _field_lines(section.instructions)
        out.append("")
        for g_index, group in enumerate(section.groups):
            if group.questions:
                page_to(group.questions[0].page_no)
            visible = bool(group.stimulus) or bool(group.pictures)
            if g_index > 0 and not visible:
                # an invisible group boundary is kept by matching (module docstring); nothing to
                # write here
                pass
            if group.stimulus:
                out.append(PASSAGE_START)
                out += _passage_lines(group.stimulus)
                out += [PASSAGE_END, ""]
            for ref in group.pictures:
                out.append(_picture_line(ref, picture_paths))
            if group.pictures:
                out.append("")
            for q in group.questions:
                page_to(q.page_no)
                out += _question_lines(q)
                out.append("")
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + ("\n" if out else "")


# --- read: parse ----------------------------------------------------------------------------


@dataclass
class _Field:
    """A field being read: the text on its marker line (``None`` when the line has only the
    marker) and the lines below it."""

    first: str | None
    more: list[str] = field(default_factory=list)

    def text(self) -> str:
        more = _trim(self.more)
        if self.first is None:
            return "\n".join(more)
        return "\n".join([self.first, *more])


@dataclass
class _RawQ:
    line: int
    printed_number: int
    page_no: int
    stem_field: _Field
    options: list[tuple[str, _Field]] = field(default_factory=list)
    cue: _Field | None = None
    start: _Field | None = None
    target: _Field | None = None  # where continuation lines go

    def stem(self) -> str | None:
        text = self.stem_field.text()
        if self.stem_field.first is None and not text:
            return None
        return text

    def option_list(self) -> list[tuple[str, str]]:
        return [(label, f.text()) for label, f in self.options]

    def cue_text(self) -> str | None:
        return None if self.cue is None else self.cue.text()

    def start_text(self) -> str | None:
        return None if self.start is None else self.start.text()

    def signature(self) -> tuple[object, ...]:
        return (self.printed_number, self.stem() or "", tuple(self.option_list()), self.cue_text())


@dataclass
class _RawGroup:
    line: int
    stimulus: str | None = None
    pictures: list[PictureRef] = field(default_factory=list)
    questions: list[_RawQ] = field(default_factory=list)
    explicit: bool = False


@dataclass
class _RawSection:
    line: int
    printed_title: str
    title: str | None
    points: float
    per_question: list[float] | None
    each: float | None
    assumed: bool
    graded: bool
    instructions: list[str] = field(default_factory=list)
    groups: list[_RawGroup] = field(default_factory=list)


def _trim(lines: list[str]) -> list[str]:
    """Drop blank (unescaped) lines at both ends; unescape the rest. Lines are kept as
    ``(text, escaped)`` while parsing: an escaped line is stored with a leading NUL marker."""
    start, end = 0, len(lines)
    while start < end and _plain_blank(lines[start]):
        start += 1
    while end > start and _plain_blank(lines[end - 1]):
        end -= 1
    return [ln[1:] if ln.startswith("\x00") else ln for ln in lines[start:end]]


def _plain_blank(ln: str) -> bool:
    return not ln.startswith("\x00") and not ln.strip()


def _unescape(line: str) -> str:
    """An escaped line's text, marked so that trimming keeps it."""
    return "\x00" + line[1:]


def _first_text(raw: str | None) -> str | None:
    r"""The text on a question, option or cue line after its marker (``None`` when there is
    none; a leading ``\`` is dropped, so ``\`` alone is an empty first line)."""
    if raw is None or not raw.strip():
        return None
    return raw[1:] if raw.startswith(_ESC) else raw


def _split_options(line: str) -> list[tuple[str, str | None]]:
    parts = _OPTION_SPLIT.split(line.strip())
    out = []
    for part in parts:
        m = _OPTION.match(part)
        if m is None:
            return []
        out.append((m.group(1), m.group(2)))
    return out


def _tag_defaults() -> dict[str, object]:
    return {
        "points": 0.0,
        "each": False,
        "per_question": None,
        "assumed": False,
        "graded": True,
        "title": None,
    }


def _take_title(rest: str, out: dict[str, object]) -> str:
    """Move a ``title: …`` part (always last) into ``out``; return what is before it."""
    title_at = re.search(r"(?:^|[,;])\s*title\s*:", rest, re.IGNORECASE)
    if title_at is None:
        return rest
    title_text = rest[title_at.end() :]
    out["title"] = title_text[1:] if title_text.startswith(" ") else title_text
    return rest[: title_at.start()]


def _plain_tag(tag: str) -> dict[str, object] | None:
    """A ``#`` heading's bracket without points (v1.21): empty, ``not graded``, ``title: …``.
    ``None`` when the bracket says anything else: it is then part of the printed title."""
    out = _tag_defaults()
    for part in re.split(r"[,;]", _take_title(tag, out)):
        word = " ".join(part.split()).lower()
        if not word:
            continue
        if word in ("not graded", "writing"):
            out["graded"] = False
        elif word != "assumed":
            return None
    return out


def _parse_heading(line: str) -> tuple[str, dict[str, object] | None, str | None]:
    """A heading line → (printed title, the tag's parts or ``None``, an error message or
    ``None``). A ``#`` heading may have no bracket; the older form ends in a points bracket,
    whose points are read and ignored (v1.21)."""
    mark = _HEADING_MARK.match(line)
    rest = mark.group(1) if mark is not None else line
    m = _TAG_AT_END.search(rest)
    if mark is not None and (m is None or not _LOOKS_LIKE_POINTS.match(m.group(1))):
        parsed = _plain_tag(m.group(1)) if m is not None else None
        if parsed is None:
            return rest.rstrip(), _tag_defaults(), None
        assert m is not None
        return rest[: m.start()].rstrip(), parsed, None
    assert m is not None
    parsed, problem = _parse_tag(m.group(1))
    return rest[: m.start()].rstrip(), parsed, problem


def _parse_tag(tag: str) -> tuple[dict[str, object] | None, str | None]:
    """The section tag's parts (a points bracket, the form before v1.21), or an error message."""
    m = _POINTS_HEAD.match(tag)
    if m is None:
        return None, "the points must come first, for example [2 points]"
    total = _parse_number(m.group(1))
    if total is None:
        return None, f"“{m.group(1)}” is not a number"
    out = _tag_defaults()
    out.update(points=total, each=bool(m.group("each")))
    rest = _take_title(tag[m.end() :], out).strip()
    if rest.startswith(":"):
        list_part, _, rest = rest[1:].partition(",")
        values = [_parse_number(v) for v in list_part.split("/")]
        if not values or any(v is None for v in values):
            return None, "the points per question are numbers with / between them"
        out["per_question"] = [float(v) for v in values if v is not None]
        rest = "," + rest if rest else ""
    for part in re.split(r"[,;]", rest):
        word = " ".join(part.split()).lower()
        if not word:
            continue
        if word == "assumed":
            out["assumed"] = True
        elif _EACH_PART.match(word):
            pass  # v1.20.1: the per-question value written after the total; computed, so ignored
        elif word in ("not graded", "writing", "writing, not graded"):
            out["graded"] = False
        else:
            return None, f"“{part.strip()}” is not something a section heading can say"
    return out, None


def _parse(text: str) -> tuple[list[_RawSection], list[TextError]]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    sections: list[_RawSection] = []
    errors: list[TextError] = []
    page = 1
    section: _RawSection | None = None
    group: _RawGroup | None = None
    question: _RawQ | None = None
    passage: list[str] | None = None
    passage_line = 0
    where = "instructions"  # where loose text goes: instructions | question | nowhere

    def need_section(no: int, what: str) -> bool:
        if section is None:
            errors.append(
                TextError(
                    no,
                    f"{what} comes before the first section heading. Start the test with a "
                    "heading such as “# I. PRONUNCIATION”.",
                )
            )
            return False
        return True

    def new_group(no: int) -> _RawGroup:
        nonlocal group, question
        assert section is not None
        group = _RawGroup(line=no, explicit=True)
        section.groups.append(group)
        question = None
        return group

    for no, line in enumerate(lines, start=1):
        if passage is not None:
            if not line.startswith(_ESC) and line.strip().lower() == PASSAGE_END.lower():
                assert group is not None
                group.stimulus = "\n".join(passage)
                passage = None
                continue
            passage.append(line[1:] if line.startswith(_ESC) else line)
            continue
        kind = _kind(line)
        if kind == "blank":
            if question is not None:
                _append(question, line)
            elif section is not None and where == "instructions":
                section.instructions.append(line)
            continue
        if kind == "page":
            m = _PAGE.match(line)
            assert m is not None
            page = int(m.group(1))
            if question is not None:
                question = None
                where = "nowhere"
            continue
        if kind == "heading":
            printed_title, parsed, problem = _parse_heading(line)
            if parsed is None:
                errors.append(TextError(no, f"The section heading cannot be read: {problem}."))
                # read on as a section, so the lines below it give no errors of their own
                parsed = _tag_defaults()
            section = _RawSection(
                line=no,
                printed_title=printed_title,
                title=parsed["title"],  # type: ignore[arg-type]
                points=parsed["points"],  # type: ignore[arg-type]
                per_question=parsed["per_question"],  # type: ignore[arg-type]
                each=parsed["points"] if parsed["each"] else None,  # type: ignore[arg-type]
                assumed=bool(parsed["assumed"]),
                graded=bool(parsed["graded"]),
            )
            sections.append(section)
            group = question = None
            where = "instructions"
            continue
        if kind == "passage_start":
            if not need_section(no, "A passage"):
                continue
            if group is None or group.questions or group.stimulus is not None:
                new_group(no)
            passage = []
            passage_line = no
            question = None
            where = "nowhere"
            continue
        if kind == "passage_end":
            errors.append(TextError(no, f"{PASSAGE_END} has no {PASSAGE_START} above it."))
            continue
        if kind == "picture":
            if not need_section(no, "A picture"):
                continue
            m = _PICTURE.match(line)
            assert m is not None
            if group is None or group.questions:
                new_group(no)
            assert group is not None
            group.pictures.append(
                PictureRef(file_id=_picture_id(m.group(1)), page_no=int(m.group(2)))
            )
            question = None
            where = "nowhere"
            continue
        if kind == "question":
            if not need_section(no, "A question"):
                continue
            assert section is not None
            m = _QUESTION.match(line)
            assert m is not None
            if group is None:
                group = _RawGroup(line=no)
                section.groups.append(group)
            rest = m.group(2)
            question = _RawQ(
                line=no,
                printed_number=int(m.group(1)),
                page_no=page,
                stem_field=_Field(_first_text(rest)),
            )
            question.target = question.stem_field
            group.questions.append(question)
            where = "question"
            continue
        if kind == "option":
            if question is None:
                errors.append(
                    TextError(
                        no, "An option (A. …) must come under a question line such as “12. …”."
                    )
                )
                continue
            pairs = _split_options(line)
            if len(pairs) > 1:
                for label, text_ in pairs:
                    question.options.append((label, _Field(_first_text(text_))))
            else:
                m = _OPTION.match(line)
                assert m is not None
                question.options.append((m.group(1), _Field(_first_text(m.group(2)))))
            question.target = question.options[-1][1]
            continue
        if kind == "cue":
            if question is None:
                errors.append(
                    TextError(no, "“Cue:” must come under a question line such as “12. …”.")
                )
                continue
            m = _CUE.match(line)
            assert m is not None
            question.cue = _Field(_first_text(m.group(1)))
            question.target = question.cue
            continue
        if kind == "start":
            if question is None:
                errors.append(
                    TextError(no, "“Start:” must come under a question line such as “12. …”.")
                )
                continue
            m = _START.match(line)
            assert m is not None
            question.start = _Field(_first_text(m.group(1)))
            question.target = question.start
            continue
        # text or escaped
        content_line = _unescape(line) if kind == "escaped" else line
        if question is not None:
            _append(question, content_line)
        elif section is not None and where == "instructions":
            section.instructions.append(content_line)
        elif section is None:
            errors.append(
                TextError(
                    no,
                    "This text comes before the first section heading. Start the test with a "
                    "heading such as “# I. PRONUNCIATION”.",
                )
            )
        else:
            errors.append(
                TextError(
                    no,
                    "This text is not part of a question, a passage or a section heading. Start "
                    f"a question with its number (“12. …”), or put a passage between "
                    f"{PASSAGE_START} and {PASSAGE_END}.",
                )
            )
    if passage is not None:
        errors.append(TextError(passage_line, f"{PASSAGE_START} has no {PASSAGE_END} below it."))
    return sections, errors


def _append(q: _RawQ, line: str) -> None:
    (q.target or q.stem_field).more.append(line)


def _picture_id(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    if "." in name:
        name = name.rsplit(".", 1)[0]
    return name


# --- read: identity -------------------------------------------------------------------------


def _q_text(sig: tuple[object, ...]) -> str:
    _, stem, options, cue = sig
    opts = " ".join(f"{a}. {b}" for a, b in options)  # type: ignore[attr-defined]
    return f"{stem} {opts} {cue or ''}"


def _old_sig(q: Question) -> tuple[object, ...]:
    return (
        q.printed_number,
        q.stem or "",
        tuple((o.label, o.text) for o in q.options or []),
        q.cue,
    )


def _match_questions(old: list[Question], new: list[_RawQ]) -> dict[int, int]:
    """new index → old index (data-model §2.3a identity rule)."""
    old_sigs = [_old_sig(q) for q in old]
    new_sigs = [r.signature() for r in new]
    pairs: dict[int, int] = {}

    def closest(i1: int, i2: int, j1: int, j2: int) -> None:
        """Pair what is left by similarity (the same number counts a little), in order."""
        if i2 - i1 == j2 - j1:
            for k in range(i2 - i1):
                pairs[j1 + k] = i1 + k
            return
        nxt = i1
        for j in range(j1, j2):
            best, best_score = None, 0.0
            for i in range(nxt, i2):
                score = difflib.SequenceMatcher(
                    a=_q_text(old_sigs[i]), b=_q_text(new_sigs[j]), autojunk=False
                ).ratio()
                if old_sigs[i][0] == new_sigs[j][0]:
                    score += 0.1
                if score > best_score:
                    best, best_score = i, score
            if best is not None and best_score >= 0.6:
                pairs[j] = best
                nxt = best + 1

    def align(i1: int, i2: int, j1: int, j2: int, with_numbers: bool) -> None:
        """Identical questions first (with their numbers, then by text alone, so renumbered
        questions keep their ids), then the closest match."""

        def key(sig: tuple[object, ...]) -> tuple[object, ...]:
            return sig if with_numbers else sig[1:]

        sm = difflib.SequenceMatcher(
            a=[key(s) for s in old_sigs[i1:i2]], b=[key(s) for s in new_sigs[j1:j2]], autojunk=False
        )
        for tag, a1, a2, b1, b2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(a2 - a1):
                    pairs[j1 + b1 + k] = i1 + a1 + k
            elif tag == "replace" or (tag in ("insert", "delete") and with_numbers):
                if with_numbers:
                    align(i1 + a1, i1 + a2, j1 + b1, j1 + b2, with_numbers=False)
                elif tag == "replace":
                    closest(i1 + a1, i1 + a2, j1 + b1, j1 + b2)

    align(0, len(old_sigs), 0, len(new_sigs), with_numbers=True)
    return pairs


def _hash_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(p) for p in parts)
    return prefix + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]


def _infer_form(
    raw: _RawQ, stem: str | None, options: list[Option], graded: bool, stimulus: str | None
) -> AnswerForm:
    """The answer form of a question new in the text (or an old choice whose options were
    removed): writing in an ungraded section; options → choice; a ``Start:`` line → sentence; a
    blank or a cue → word; else sentence."""
    if not graded:
        return "writing"
    if options:
        return "choice"
    if raw.start_text() is not None:
        return "sentence"
    if (stem and _BLANK in stem) or (
        not stem and stimulus and f"({raw.printed_number})" in stimulus
    ):
        return "word"
    if raw.cue is not None:
        return "word"
    return "sentence"


# --- read -----------------------------------------------------------------------------------


def read(text: str, previous: TestContent | None = None) -> ReadResult:
    """The content the text describes (module docstring), or the errors with line numbers.

    ``previous`` is the stored content: matched questions, groups and sections keep their ids and
    the fields the text does not show. Nothing is validated here beyond the shape; the caller
    runs the content validators.
    """
    raw_sections, errors = _parse(text)
    if errors:
        return ReadResult(content=None, errors=errors)
    prev = previous or TestContent(sections=[])

    old_qs: list[Question] = []
    old_q_section: list[int] = []
    old_q_group: list[str] = []
    for si, s in enumerate(prev.sections):
        for g in s.groups:
            for q in g.questions:
                old_qs.append(q)
                old_q_section.append(si)
                old_q_group.append(g.id)
    invisible_groups = {
        g.id for s in prev.sections for g in s.groups if not g.stimulus and not g.pictures
    }
    old_groups = {g.id: g for s in prev.sections for g in s.groups}

    new_raw: list[_RawQ] = [q for s in raw_sections for g in s.groups for q in g.questions]
    pairs = _match_questions(old_qs, new_raw)
    match_of = {id(new_raw[j]): old_qs[i] for j, i in pairs.items()}
    old_index = {id(new_raw[j]): i for j, i in pairs.items()}

    # Split groups where matched questions came from different (invisible) previous groups.
    for rs in raw_sections:
        split: list[_RawGroup] = []
        for rg in rs.groups:
            current = rg
            current_prev: str | None = None
            kept: list[_RawQ] = []
            for rq in rg.questions:
                i = old_index.get(id(rq))
                pg = old_q_group[i] if i is not None else None
                if current_prev is None:
                    current_prev = pg
                elif pg is not None and kept and pg != current_prev and pg in invisible_groups:
                    current.questions = kept
                    split.append(current)
                    current = _RawGroup(line=rq.line)
                    current_prev = pg
                    kept = []
                kept.append(rq)
            current.questions = kept
            split.append(current)
        rs.groups = split

    # Sections: the previous section most of its questions came from, else by heading, else by
    # position.
    used_sections: set[int] = set()
    section_prev: list[int | None] = []
    claims: list[tuple[int, int, int]] = []  # (count, -index, prev index)
    for k, rs in enumerate(raw_sections):
        votes = Counter(
            old_q_section[old_index[id(q)]]
            for g in rs.groups
            for q in g.questions
            if id(q) in old_index
        )
        section_prev.append(None)
        if votes:
            prev_i, count = votes.most_common(1)[0]
            claims.append((count, -k, prev_i))
    for _count, neg_k, prev_i in sorted(claims, reverse=True):
        k = -neg_k
        if prev_i not in used_sections:
            section_prev[k] = prev_i
            used_sections.add(prev_i)
    for k, rs in enumerate(raw_sections):
        if section_prev[k] is not None:
            continue
        for i, cand_s in enumerate(prev.sections):
            if i not in used_sections and cand_s.printed_title == rs.printed_title:
                section_prev[k] = i
                used_sections.add(i)
                break
        else:
            if k < len(prev.sections) and k not in used_sections:
                section_prev[k] = k
                used_sections.add(k)

    used_ids = {q.id for q in old_qs} | {s.id for s in prev.sections} | set(old_groups)
    claimed_q: set[str] = set()
    claimed_g: set[str] = set()
    sections: list[Section] = []
    question_lines: dict[str, int] = {}
    section_lines: dict[str, int] = {}
    errors = []
    built: list[tuple[Section, list[QuestionGroup]]] = []

    for k, rs in enumerate(raw_sections):
        prev_k = section_prev[k]
        ps: Section | None = prev.sections[prev_k] if prev_k is not None else None
        if ps is not None:
            sid = ps.id
        else:
            salt = 0
            sid = _hash_id("s-", k + 1, rs.printed_title, salt)
            while sid in used_ids:
                salt += 1
                sid = _hash_id("s-", k + 1, rs.printed_title, salt)
            used_ids.add(sid)
        section_lines[sid] = rs.line
        n_questions = sum(len(g.questions) for g in rs.groups)
        # v1.19 (PRD D13 v8.0): typed points are ignored; equal_points sets them below
        if rs.per_question is not None and len(rs.per_question) != n_questions:
            per: list[float] = [0.0] * n_questions
            total = 0.0
        elif rs.each is not None:
            per = [rs.each] * n_questions
            total = rs.each * n_questions
        elif rs.per_question is not None:
            per = list(rs.per_question)
            total = rs.points
        else:
            total = rs.points
            per = [total / n_questions] * n_questions if n_questions else []
        if rs.assumed:
            # still assumed only while the points are the ones assumed before (else the teacher
            # typed them)
            assumed = ps is None or (ps.points_source == "assumed" and ps.points == total)
        else:
            assumed = False
        graded = rs.graded
        skill = ps.skill if ps is not None else ("writing" if not graded else "mixed")

        groups: list[QuestionGroup] = []
        q_counter = 0
        prev_group_ids = [g.id for g in ps.groups] if ps is not None else []
        for gi, rg in enumerate(rs.groups):
            g_votes = Counter(
                old_q_group[old_index[id(q)]] for q in rg.questions if id(q) in old_index
            )
            gid: str | None = None
            for cand, _ in g_votes.most_common():
                if cand not in claimed_g:
                    gid = cand
                    break
            if gid is None and rg.stimulus is not None and ps is not None:
                gid = next(
                    (
                        g.id
                        for g in ps.groups
                        if g.id not in claimed_g and g.stimulus == rg.stimulus
                    ),
                    None,
                )
            if gid is None and gi < len(prev_group_ids) and prev_group_ids[gi] not in claimed_g:
                cand_g = old_groups[prev_group_ids[gi]]
                if not any(id(q) in old_index for q in rg.questions) and not any(
                    old_q_group[i] == cand_g.id for i in pairs.values()
                ):
                    gid = cand_g.id
            if gid is None:
                salt = 0
                gid = _hash_id("g-", sid, gi, salt)
                while gid in used_ids:
                    salt += 1
                    gid = _hash_id("g-", sid, gi, salt)
                used_ids.add(gid)
            claimed_g.add(gid)
            prev_group = old_groups.get(gid)
            stimulus = rg.stimulus
            if stimulus is None and prev_group is not None and prev_group.stimulus == "":
                stimulus = ""
            questions: list[Question] = []
            for rq in rg.questions:
                old = match_of.get(id(rq))
                if old is not None and old.id in claimed_q:
                    old = None
                stem = rq.stem()
                if stem is None and old is not None and old.stem == "":
                    stem = ""
                opts = [Option(label=clean_label(a), text=b) for a, b in rq.option_list()]
                options: list[Option] | None = opts
                if not opts:
                    options = [] if old is not None and old.options == [] else None
                cue = rq.cue_text()
                old_type: str | None = None
                if old is not None:
                    qid = old.id
                    old_type = old.old_type
                    form: AnswerForm = old.answer_form
                    if form == "choice" and not opts and old.options:  # options removed
                        form = _infer_form(rq, stem, opts, graded, stimulus)
                else:
                    salt = 0
                    qid = make_question_id(k + 1, rq.printed_number, stem, salt)
                    while qid in used_ids:
                        salt += 1
                        qid = make_question_id(k + 1, rq.printed_number, stem, salt)
                    used_ids.add(qid)
                    form = _infer_form(rq, stem, opts, graded, stimulus)
                claimed_q.add(qid)
                question_lines[qid] = rq.line
                questions.append(
                    Question(
                        id=qid,
                        number=0,  # set below
                        printed_number=rq.printed_number,
                        page_no=rq.page_no,
                        answer_form=form,
                        stem=stem,
                        options=options,
                        cue=cue,
                        points=per[q_counter],
                        answer_start=rq.start_text(),
                        old_type=old_type,
                    )
                )
                q_counter += 1
            groups.append(
                QuestionGroup(id=gid, stimulus=stimulus, pictures=rg.pictures, questions=questions)
            )
        section = Section(
            id=sid,
            number=0,  # set below
            printed_title=rs.printed_title,
            title=rs.title if rs.title is not None else rs.printed_title,
            instructions="\n".join(_trim(rs.instructions)),
            points=total,
            points_source="assumed" if assumed else "printed",
            skill=skill,
            graded=graded,
            groups=groups,
        )
        built.append((section, groups))
    if errors:
        return ReadResult(content=None, errors=errors)

    sections = [s for s, _ in built]
    _number(sections, prev)
    content = equal_points(TestContent(sections=sections))  # also cleans the option letters
    kept_ids = {q.id for s in sections for g in s.groups for q in g.questions}
    dropped = [q.id for q in old_qs if q.id not in kept_ids]
    return ReadResult(
        content=content,
        question_lines=question_lines,
        section_lines=section_lines,
        dropped=dropped,
    )


def _number(sections: list[Section], prev: TestContent) -> None:
    """Canonical numbers (PRD D10): unchanged when the order of sections and questions is the
    same as before, else sections 1..n and questions 1..N over the graded sections, then the
    ungraded (writing) ones."""
    prev_s = [s.id for s in prev.sections]
    prev_q = [q.id for s in prev.sections for g in s.groups for q in g.questions]
    new_s = [s.id for s in sections]
    new_q = [q.id for s in sections for g in s.groups for q in g.questions]
    if prev_s == new_s and prev_q == new_q:
        old_s = {s.id: s.number for s in prev.sections}
        old_q = {q.id: q.number for s in prev.sections for g in s.groups for q in g.questions}
        for s in sections:
            s.number = old_s[s.id]
            for g in s.groups:
                for q in g.questions:
                    q.number = old_q[q.id]
        return
    for i, s in enumerate(sections, start=1):
        s.number = i
    n = 1
    for s in [s for s in sections if s.graded] + [s for s in sections if not s.graded]:
        for g in s.groups:
            for q in g.questions:
                q.number = n
                n += 1


# --- a photo page written in this format (step 22.6.5, way 2a) ------------------------------

#: a section label at the start of a heading: a Roman numeral or "Part X" (as way 2b reads it)
_LABEL_HEAD = re.compile(r"^((?:[IVX]{1,6})|(?:PART|Part)\s+[A-Z0-9]{1,4})\s*[.):\-]?\s+(\S.*)$")
_LABEL_ONLY = re.compile(r"^((?:[IVX]{1,6})|(?:PART|Part)\s+[A-Z0-9]{1,4})\s*[.):\-]?$")
#: an option label inside a line: a capital A to D and a dot, at the start or after a space
_INLINE_LABEL = re.compile(r"(?:(?<=\s)|^)([A-D])\.(?=\s|$)")
_ARROW_START = re.compile(r"^\s*(?:=>|->|→|⇒)\s*(.*)$")
_TRAILING_BLANK = re.compile(r"(?:_{2,}|\.{2,}|…+)\s*$")
_MD_HEADING = re.compile(r"^\s*#{2,}\s*")
_LISTEN = re.compile(r"\blisten", re.IGNORECASE)
_WRITE_TASK = re.compile(r"\bwrite\b", re.IGNORECASE)
_STRUCTURAL: frozenset[str] = frozenset(
    {"heading", "question", "option", "cue", "start", "passage_start", "picture"}
)
_BODY_START: frozenset[str] = frozenset({"heading", "question", "passage_start", "picture"})
_WHOLE_PAGE = PictureRegion(x0=0, y0=0, x1=1000, y1=1000)


@dataclass
class OcrPageRead:
    """One photo page read from GLM-OCR's test-text output (:func:`read_ocr_page`).

    ``out`` is always set: the page's sections, or, when the text cannot be read, the whole text
    kept as one untitled group's passage. ``problem`` says why the page needs Review (the
    reader's reason, or lines kept as text that the format did not place); ``None`` when none.
    """

    out: TranscribeOut
    problem: str | None = None


def _option_cuts(text: str) -> list[int]:
    """Where the options A., B. (C., D.) start in ``text``, in order; [] unless A and B are
    both there."""
    cuts: list[int] = []
    for m in _INLINE_LABEL.finditer(text):
        if m.group(1) == "ABCD"[len(cuts)]:
            cuts.append(m.start())
            if len(cuts) == 4:
                break
    return cuts if len(cuts) >= 2 else []


def _options_line(text: str, cuts: list[int]) -> str:
    """The options in ``text`` from ``cuts`` on one line, two spaces apart (as :func:`read`
    splits them)."""
    ends = [*cuts[1:], len(text)]
    return "  ".join(text[a:b].strip() for a, b in zip(cuts, ends, strict=True))


def _ocr_lines(text: str) -> list[str]:
    """GLM-OCR's lines with its habits undone: markdown bold and ``##`` headings, options on the
    question's line or one space apart, an arrow line under a question for ``Start:``."""
    out: list[str] = []
    in_passage = False
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.rstrip().replace("**", "")
        stripped = line.strip()
        if in_passage:
            out.append(line)
            in_passage = stripped.lower() != PASSAGE_END.lower()
            continue
        if stripped.lower() == PASSAGE_START.lower():
            in_passage = True
            out.append(line)
            continue
        line = _MD_HEADING.sub("# ", line)
        kind = _kind(line)
        if kind == "question":
            m = _QUESTION.match(line)
            assert m is not None
            rest = m.group(2) or ""
            cuts = _option_cuts(rest)
            if cuts:
                stem = rest[: cuts[0]].strip()
                out.append(f"{m.group(1)}. {stem}" if stem else f"{m.group(1)}.")
                out.append(_INDENT + _options_line(rest, cuts))
                continue
        elif kind == "option":
            cuts = _option_cuts(stripped)
            if cuts and cuts[0] == 0:
                out.append(_INDENT + _options_line(stripped, cuts))
                continue
        elif kind == "text":
            arrow = _ARROW_START.match(line)
            if arrow is not None and out and _kind(out[-1]) in ("question", "option", "text"):
                words = _TRAILING_BLANK.sub("", arrow.group(1)).strip()
                if words:
                    out.append(f"{_INDENT}Start: {words}")
                    continue
        out.append(line)
    return out


def _with_continuation(lines: list[str]) -> tuple[list[str], list[str], list[str]]:
    """``(lines, header, loose)``. Text before the first heading is the test header when a
    heading comes first; when the page starts with questions, options or a passage (the
    section goes on from the previous page), an untitled heading is put first (the merge joins
    it to the previous page's last section, like way 2b) and the text before the first
    question, with any options there (the rest of a question cut at the page's end: ``loose``,
    its number is not on this page), becomes that section's passage."""
    first = next((i for i, ln in enumerate(lines) if _kind(ln) in _STRUCTURAL), None)
    if first is None or _kind(lines[first]) == "heading":
        cut = len(lines) if first is None else first
        header = [ln.strip() for ln in lines[:cut] if ln.strip()]
        return lines[cut:], header, []
    body_at = next((i for i, ln in enumerate(lines) if _kind(ln) in _BODY_START), len(lines))
    lead = [ln for ln in lines[:body_at] if ln.strip()]
    loose = [ln.strip() for ln in lead if _kind(ln) in ("option", "cue", "start")]
    head = ["#"]
    if lead:
        head += [PASSAGE_START, *lead, PASSAGE_END]
    return head + lines[body_at:], [], loose


def _split_title(printed_title: str) -> tuple[str, str]:
    """A heading as ``(label, first instruction line)``: "II. Choose …" → ("II", "Choose …")."""
    label = _LABEL_HEAD.match(printed_title)
    if label is not None:
        return label.group(1), label.group(2)
    only = _LABEL_ONLY.match(printed_title)
    if only is not None:
        return only.group(1), ""
    return printed_title, ""


def _section_out(section: Section) -> TranscribedSection:
    title, first_line = _split_title(section.printed_title)
    instructions = "\n".join(x for x in (first_line, section.instructions) if x)
    questions = [q for g in section.groups for q in g.questions]
    numbers = [q.printed_number for q in questions]
    if _LISTEN.search(f"{section.printed_title}\n{section.instructions}"):
        return TranscribedSection(
            printed_title=title,
            instructions=instructions,
            kind="listening",
            skill="mixed",
            points_text=None,
            range_first=min(numbers) if numbers else None,
            range_last=max(numbers) if numbers else None,
            groups=[],
        )
    writing = not section.graded or (
        not questions
        and not any(g.stimulus for g in section.groups)
        and bool(_WRITE_TASK.search(instructions))
    )
    groups = [
        TranscribedGroup(
            stimulus=g.stimulus,
            pictures=[_WHOLE_PAGE] if g.pictures else [],
            questions=[
                TranscribedQuestion(
                    printed_number=q.printed_number,
                    answer_form=q.answer_form,
                    stem=q.stem,
                    options=q.options or None,
                    cue=q.cue,
                    answer_start=q.answer_start if q.answer_form == "sentence" else None,
                )
                for q in g.questions
            ],
        )
        for g in section.groups
    ]
    return TranscribedSection(
        printed_title=title,
        instructions=instructions,
        kind="writing" if writing else "questions",
        skill="writing" if writing else "mixed",
        points_text=None,
        range_first=None,
        range_last=None,
        groups=groups,
    )


def _title_block(section: Section) -> bool:
    """A ``#`` line that is the test's title, not a section: no section label, nothing under
    it but text (GLM-OCR marks the title "ĐỀ KIỂM TRA …" like a heading)."""
    return (
        bool(section.printed_title)
        and _LABEL_HEAD.match(section.printed_title) is None
        and _LABEL_ONLY.match(section.printed_title) is None
        and not section.groups
    )


def _kept(text: str) -> TranscribeOut:
    """The page's text, unread, kept as one untitled group's passage for Review."""
    group = TranscribedGroup(stimulus=text.strip() or None, pictures=[], questions=[])
    return TranscribeOut(
        header_text=None,
        sections=[
            TranscribedSection(
                printed_title="",
                instructions="",
                kind="questions",
                skill="mixed",
                points_text=None,
                range_first=None,
                range_last=None,
                groups=[group],
            )
        ],
    )


def read_ocr_page(text: str) -> OcrPageRead:
    """One photo page that GLM-OCR wrote in this format (step 22.6.5, way 2a), read by
    :func:`read` into the per-page output of ``structure_text_page`` (``TranscribeOut``).

    :func:`read` itself is unchanged. Around it: GLM-OCR's habits are undone
    (:func:`_ocr_lines`); a page that goes on from the previous one starts with an untitled
    section (:func:`_with_continuation`); ``#`` title lines before the first section are the
    test header; a heading's Roman numeral or "Part" label is the printed title and the rest of
    the heading its first instruction line; a section whose heading or instructions say "listen"
    is a listening section; one with no questions that asks to write is a writing section. A
    page :func:`read` cannot read, or text with no heading and no question, keeps its whole text
    (:func:`_kept`) and ``problem`` gives the reason. Pure: no I/O.
    """
    lines, header, loose = _with_continuation(_ocr_lines(text))
    result = read("\n".join(lines))
    if result.content is None:
        first = result.errors[0] if result.errors else None
        where = ""
        if first is not None and first.line is not None and 0 < first.line <= len(lines):
            where = f" (the line “{lines[first.line - 1].strip()}”)"
        reason = (first.message if first is not None else "the text cannot be read") + where
        if len(result.errors) > 1:
            reason += f"; {len(result.errors) - 1} more problem(s)"
        return OcrPageRead(out=_kept(text), problem=f"test-text format: {reason}")
    content = list(result.content.sections)
    if not content and text.strip():
        # no heading and no question: GLM-OCR did not write the format
        return OcrPageRead(
            out=_kept(text), problem="test-text format: no section heading or question in the text"
        )
    while len(content) > 1 and _title_block(content[0]):
        top = content.pop(0)
        header += [x for x in (top.printed_title, top.instructions) if x]
    out = TranscribeOut(
        header_text="\n".join(header) or None, sections=[_section_out(s) for s in content]
    )
    problem: str | None = None
    if loose:
        problem = (
            f"test-text format: {len(loose)} option line(s) before the first question, kept in "
            "the passage (their question's number is on the previous page)"
        )
    return OcrPageRead(out=out, problem=problem)
