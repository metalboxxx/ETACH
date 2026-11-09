"""Way (2b) of the photo path (step 22.6.5, step22.6-plan D7): code structures one page's plain
OCR text into the per-page output of ``structure_text_page`` (``TranscribeOut``), no model call.

The text comes from GLM-OCR with the answer boxes already removed (``strip_answer_boxes``). The
rules follow the printed layout and ``prompts/base/structure_text_page.md``:

- Sections: a Roman-numeral heading (``IV. Choose …``) or ``Part A`` starts a section. The rest
  of its line, and the lines after it that read as instructions, are its ``instructions``; the
  printed points (``(1.5 pts)``) go to ``points_text``. A page that starts without a heading
  starts with an untitled section (the merge joins it to the previous page's last section).
- Instruction lines between questions ("Choose the correct answer:", "Thí sinh …", "Từ câu …")
  join the current section's instructions; when the questions after one change form (e.g. the
  word-form questions end and rewrite questions start) they start a new untitled section.
- Questions: ``N.`` / ``N)`` / ``Question N.``; ``N`` without a dot only for the next number.
  A number at or below the last one is text, except the repeat below and a run from 1: a dotted
  ``1.`` and a ``2.`` with A-D options beat a lone earlier number, also across a heading. Lone:
  the page's only question so far, with no options, blank, cue, answer start or ending ``?``
  ("8. PRACTICE 3 MT2 (K)"; a one-letter bracket is no cue). Its line stays as text and is
  listed in ``unplaced``.
- A numbered line with no options followed by a question of the same number is a section
  heading read as a digit ("1. Choose …" for "I. Choose …").
- Options ``A.`` to ``D.`` on the question's line or on lines after it, one or several per line;
  the first label may lack its dot when the next has one ("A have to B. should"). Labels must go
  up (A, B, C, D); a label out of order stays in the option text and the page is flagged.
- True/False: a statement with no options in a section that says True/False, or ending in a
  lone blank (``… better. ____``), is a ``choice`` with no options (the merge adds T/F).
- A passage: the text between a section's instructions and its first question is the group
  stimulus; a cloze's ``(N) ____`` gaps stay in it and their option-only questions have a null
  stem.
- A rewrite question: the line under it that starts with an arrow (``=> Unless``) or ends in
  dots (``The man who .....``) is its ``answer_start``; the question is a ``sentence``.
- A cue in brackets at the end of a stem (``(apply)``) is the ``cue``; with no options and no
  answer start the question is a ``word``.
- Blanks (``____``, ``.....``, ``…``) are written ``____``.
- Lines it cannot place stay (as instructions or in the nearest question's stem) and are
  listed in ``unplaced``; the caller flags the page (``validator_failed``). Nothing is dropped.

Pure: no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from etach.domain.llm_schemas import (
    PictureRegion,
    SectionKind,
    SectionSkill,
    TranscribedGroup,
    TranscribedQuestion,
    TranscribedSection,
    TranscribeOut,
)
from etach.domain.models import Option
from etach.domain.normalize import name_search

__all__ = ["OcrStructure", "structure_ocr_page"]

_ROMAN = re.compile(r"^\s*([IVX]{1,6})\s*[.):\-]\s*(.*)$")
_PART = re.compile(r"^\s*((?:PART|Part)\s+[A-Z0-9]{1,4})\b\s*[.:)-]?\s*(.*)$")
_QUESTION = re.compile(r"^\s*(?:Question\s+)?(\d{1,3})\s*([.):])?\s+(\S.*)$", re.IGNORECASE)
_POINTS = re.compile(r"\(\s*\d+(?:[.,]\d+)?\s*(?:pts?|points?|đ|điểm)\.?\s*\)", re.IGNORECASE)
_BLANK = re.compile(r"_{2,}|\.{3,}|…+")
#: an option label: a capital A-D and a dot or bracket, at the start or after a space
_LABEL = re.compile(r"(?:(?<=\s)|^)([A-D])[.)]\s*")
#: GLM-OCR drops the first label's dot ("A have to B. should", Test G8)
_BARE_FIRST = re.compile(r"^\s*A\s+(?=\S)")
_ARROW = re.compile(r"^\s*(?:=>|->|→|⇒|=)\s*")
_CUE = re.compile(r"\(\s*([^()]{1,40}?)\s*\)\s*[.]?\s*$")
#: an instruction line (accents folded): an imperative or a Vietnamese note to the student
_INSTRUCTION = re.compile(
    r"^\W*(?:choose|circle|rewrite|use|read|look|listen|complete|write|decide|put|match|fill"
    r"|give|find|answer|mark|supply|change|combine|reorder|arrange|thi sinh|chu y|luu y"
    r"|tu cau|tu cau|doi voi|dối voi)\b"
)
_HEADER = re.compile(
    r"^\W*(?:truong|de |de kiem|kiem tra|thoi gian|lop|ho va ten|ho ten|name|class|time|school"
    r"|nam hoc|mon)\b"
)
_TRUE_FALSE = re.compile(r"\btrue\b.*\bfalse\b|\bT\s*/\s*F\b|đúng.*sai", re.IGNORECASE)
_LONE_BLANK_END = re.compile(r"[.!?]\s*____\s*$")
_ASKS = re.compile(r"\?[\s\"'”]*$")
_GAP = re.compile(r"\(\s*(\d{1,3})\s*\)\s*____")
_PICTURE = re.compile(r"\b(?:signs?|notices?|pictures?)\b", re.IGNORECASE)
_WHOLE_PAGE = PictureRegion(x0=0, y0=0, x1=1000, y1=1000)


@dataclass
class OcrStructure:
    """The page's structured output and the lines that no rule placed (kept, but flagged)."""

    out: TranscribeOut
    unplaced: list[str] = field(default_factory=list)


@dataclass
class _Q:
    number: int
    lines: list[str]  # the stem lines (the question's own line first)
    options: list[Option] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)  # lines after its options (unplaced)
    line: str = ""  # the printed line, number included


@dataclass
class _Sec:
    title: str
    head: list[str]  # instruction lines
    passage: list[str] = field(default_factory=list)
    questions: list[_Q] = field(default_factory=list)
    split: bool = False  # started by an instruction line between questions (no heading)


def blanks(text: str) -> str:
    """Every printed blank (underscores, dots, ellipsis) as ``____``."""
    text = _BLANK.sub(" ____ ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r" ([,.;:!?])", r"\1", text).strip()


def _heading(line: str) -> tuple[str, str] | None:
    m = _ROMAN.match(line) or _PART.match(line)
    if m is None or not m.group(2).strip():
        return None
    return m.group(1).strip(), m.group(2).strip()


def _split_options(text: str, after: str | None) -> tuple[str, list[Option], bool]:
    """``text`` split into its lead text and its options. ``after`` is the last label the
    question already has (None: none yet). Labels must follow on (A, B, …); a label out of order
    stays in the option before it (the bool says one did)."""
    want = "A" if after is None else chr(ord(after) + 1)
    if want == "A" and _BARE_FIRST.match(text) and _LABEL.search(text, 1):
        nxt = _LABEL.search(text, 1)
        assert nxt is not None
        if nxt.group(1) == "B":
            text = _BARE_FIRST.sub("A. ", text, count=1)
    marks = [m for m in _LABEL.finditer(text)]
    if not marks or marks[0].group(1) != want:
        return text, [], False
    lead = text[: marks[0].start()].strip()
    if lead and after is not None:
        return text, [], False
    kept, broken, expected = [], False, want
    for m in marks:
        if m.group(1) == expected:
            kept.append(m)
            expected = chr(ord(expected) + 1)
        else:
            broken = True  # "A. so B. and D. but D. that" (Test G8): kept in B's text
    options = []
    for i, m in enumerate(kept):
        end = kept[i + 1].start() if i + 1 < len(kept) else len(text)
        options.append(Option(label=m.group(1), text=blanks(text[m.end() : end])))
    return lead, options, broken


def _is_instruction(line: str) -> bool:
    return bool(_INSTRUCTION.match(name_search(line)))


def _continues_line(prev: str, line: str) -> bool:
    """``line`` goes on with ``prev`` (a wrapped line): ``prev`` has no closing punctuation and
    ``line`` starts in lowercase, a digit and a comma, or a bracket."""
    if re.search(r"[.!?:\"”)]\s*$", prev):
        return False
    return bool(re.match(r"^\s*(?:[a-zà-ỹ(]|\d+,)", line))


def _has_all_options(lines: list[str]) -> bool:
    after = None
    for line in lines:
        options = _split_options(line, after)[1]
        after = options[-1].label if options else after
    return after == "D"


def _run_from_1(rest: str, ahead: list[str]) -> bool:
    """The line ``1. rest`` and the lines ``ahead`` give a question 1 and a question 2, both with
    options A to D."""
    questions = [[rest]]
    for line in ahead:
        m = _QUESTION.match(line)
        if m is None:
            questions[-1].append(line)
        elif len(questions) == 1 and int(m.group(1)) == 2:
            questions.append([m.group(3)])
        else:
            break
    return len(questions) == 2 and all(_has_all_options(q) for q in questions)


def _reads_as_question(q: _Q) -> bool:
    """``q`` has a blank, an answer start, a cue (a one-letter bracket is a label: "(K)") or a
    line ending in a question mark."""
    cue = _stem_and_cue(q, None)[1]
    start = _answer_start(q)
    asks = any(_ASKS.search(line) for line in q.lines)
    blank = _BLANK.search(" ".join(q.lines))
    return asks or blank is not None or start is not None or len(cue or "") > 1


class _Reader:
    def __init__(self) -> None:
        self.header: list[str] = []
        self.sections: list[_Sec] = []
        self.unplaced: list[str] = []
        self.last: int | None = None

    @property
    def sec(self) -> _Sec:
        if not self.sections:
            self.sections.append(_Sec(title="", head=[]))
        return self.sections[-1]

    def feed(self, line: str, ahead: list[str]) -> None:
        """``ahead``: the page's lines after ``line``."""
        head = _heading(line)
        if head is not None:
            self.sections.append(_Sec(title=head[0], head=[head[1]]))
            return
        if self._question(line, ahead):
            return
        open_sec = self.sections[-1] if self.sections else None
        q = open_sec.questions[-1] if open_sec and open_sec.questions else None
        if q is not None:
            self._after_question(q, line)
        else:
            self._before_questions(line)

    def _question(self, line: str, ahead: list[str]) -> bool:
        m = _QUESTION.match(line)
        if m is None:
            return False
        n, dot, rest = int(m.group(1)), m.group(2), m.group(3)
        if n == 1 and dot is not None and _run_from_1(rest, ahead):
            self._drop_lone_number()
        repeat = self._repeat(n)
        if self.last is not None and n <= self.last and not repeat:
            return False
        if dot is None and (self.last is None or n != self.last + 1):
            return False  # "1 ★ A2 doing something" in a dictionary entry is no question
        if repeat:
            self._to_heading()
        lead, options, broken = _split_options(rest, None)
        q = _Q(number=n, lines=[lead] if lead else [], options=options, line=line.strip())
        self.sec.questions.append(q)
        if broken:
            self.unplaced.append(line)
        self.last = n
        return True

    def _drop_lone_number(self) -> None:
        """A run from 1 starts: a lone earlier number (module doc) was a stray line, so it goes
        back to text in its section and is listed as unplaced."""
        found = self._last_question()
        if found is None or sum(len(s.questions) for s in self.sections) != 1:
            return
        sec, q = self.sections[found[0]], found[1]
        if q.number > 1 and not q.options and not _reads_as_question(q):
            sec.questions.pop()
            sec.head.extend([q.line, *q.lines[1:]])
            self.unplaced.append(q.line)
            self.last = None

    def _last_question(self) -> tuple[int, _Q] | None:
        for i in range(len(self.sections) - 1, -1, -1):
            if self.sections[i].questions:
                return i, self.sections[i].questions[-1]
        return None

    def _repeat(self, n: int) -> bool:
        """``n`` repeats the last question's number, and that question has no options and only
        instruction lines may follow it: GLM-OCR read the heading "I." as "1." (Test G8)."""
        found = self._last_question()
        if found is None:
            return False
        i, q = found
        later = self.sections[i + 1 :]
        return (
            n == q.number
            and not q.options
            and not q.extra
            and all(not s.questions and not s.passage and s.split for s in later)
        )

    def _to_heading(self) -> None:
        """The repeated question becomes the heading of a new section (its lines and the
        instruction lines after it are the instructions)."""
        found = self._last_question()
        assert found is not None
        i, q = found
        self.sections[i].questions.pop()
        head = list(q.lines)
        for s in self.sections[i + 1 :]:
            head.extend(s.head)
        del self.sections[i + 1 :]
        self.sections.append(_Sec(title=str(q.number), head=head))

    def _after_question(self, q: _Q, line: str) -> None:
        after = q.options[-1].label if q.options else None
        lead, options, broken = _split_options(line, after)
        if options:
            if lead:
                q.lines.append(lead)  # "1. A. a B. b" under a question with no options yet
            q.options.extend(options)
            if broken:
                self.unplaced.append(line)
            return
        if _is_instruction(line):
            # a new instruction between questions: a candidate section (see _settle)
            self.sections.append(_Sec(title="", head=[line.strip()], split=True))
            return
        if q.options or q.extra or _answer_start(q) is not None:
            # e.g. a sign's text after its options, or a line after the answer's opening words
            q.extra.append(line.strip())
            self.unplaced.append(line)
            return
        q.lines.append(line.strip())

    def _before_questions(self, line: str) -> None:
        text = line.strip()
        if not self.sections and _HEADER.match(name_search(text)):
            self.header.append(text)  # the test header (school, test, class, time)
            return
        sec = self.sec
        if not self._last_question() and _split_options(text, None)[1]:
            # options before any question: the rest of the previous page's last question; the
            # number is not on this page, so they stay as text and the page is flagged
            self.unplaced.append(line)
        if (
            not sec.passage
            and sec.head
            and (_is_instruction(text) or _continues_line(sec.head[-1], text))
        ):
            sec.head.append(text)
            return
        if not sec.passage and not sec.head and _is_instruction(text):
            sec.head.append(text)
            return
        sec.passage.append(text)


def _same_form(prev: _Sec, sec: _Sec) -> bool:
    """``sec``'s first question has the answer form of ``prev``'s last (or ``prev`` has none)."""
    if not prev.questions:
        return True
    last, first = prev.questions[-1], sec.questions[0]
    return _form(last, prev, _answer_start(last)) == _form(first, sec, _answer_start(first))


def _settle(sections: list[_Sec]) -> list[_Sec]:
    """A section started by an instruction line between questions stays its own section only
    when its first question changes form from the question before it (word → sentence, Test
    G8's unnumbered rewrite part); otherwise it is part of the section before (a
    sub-instruction, "Choose the correct answer:")."""
    out: list[_Sec] = []
    for sec in sections:
        if not (sec.title or sec.head or sec.passage or sec.questions):
            continue  # an untitled start left empty (its only line became a heading)
        prev = out[-1] if out else None
        if sec.split and prev is not None and (not sec.questions or _same_form(prev, sec)):
            prev.head.extend(sec.head + sec.passage)
            prev.questions.extend(sec.questions)
            continue
        out.append(sec)
    return out


def _answer_start(q: _Q) -> str | None:
    """The line under a question with no options that opens its answer (``=> Unless``, ``The
    man who .....``); None otherwise."""
    if q.options or len(q.lines) < 2:
        return None
    last = q.lines[-1]
    arrow = _ARROW.match(last)
    if arrow is None and not re.search(r"(?:_{2,}|\.{2,}|…+)\s*$", last):
        return None
    words = _BLANK.sub(" ", _ARROW.sub("", last))
    words = re.sub(r"\.+\s*$", "", words).strip()
    return words or None


def _stem_and_cue(q: _Q, answer_start: str | None) -> tuple[str | None, str | None]:
    lines = q.lines[:-1] if answer_start is not None else q.lines
    stem = blanks(" ".join(lines + q.extra)) if lines or q.extra else ""
    cue = None
    m = _CUE.search(stem)
    if m and not q.options and not _POINTS.fullmatch(m.group(0).strip()):
        cue = m.group(1).strip()
        stem = stem[: m.start()].rstrip()
    return (stem or None), cue


def _form(q: _Q, sec: _Sec, answer_start: str | None) -> str:
    if q.options:
        return "choice"
    stem = blanks(" ".join(q.lines))
    if _TRUE_FALSE.search(" ".join(sec.head)) or _LONE_BLANK_END.search(stem):
        return "choice"
    if answer_start is not None or _skill_text(sec, "rewrite"):
        return "sentence"
    return "word"


def _skill_text(sec: _Sec, skill: str) -> bool:
    text = name_search(" ".join(sec.head))
    patterns = {
        "rewrite": r"\b(?:rewrite|combine|reorder|arrange|sentences? (?:beginning|starting))",
        "writing": r"\bwrite (?:a|an|about) (?:paragraph|essay|email|e-mail|letter|passage|short)",
        "listening": r"\blisten",
        "signs": r"\b(?:signs?|notices?)\b",
        "dictionary": r"\b(?:dictionary|entry)\b",
        "word_form": r"\b(?:correct|right|proper) form\b",
        "pronunciation": r"\bpronounc",
        "stress": r"\bstress",
    }
    return bool(re.search(patterns[skill], text))


def _skill(sec: _Sec, forms: list[str], cues: int) -> SectionSkill:
    if _skill_text(sec, "writing") and not sec.questions:
        return "writing"
    if _skill_text(sec, "dictionary"):
        return "vocabulary"
    if _skill_text(sec, "signs"):
        return "signs"
    if sec.passage:
        return "reading"
    if forms and all(f == "sentence" for f in forms):
        return "rewrite"
    if _skill_text(sec, "word_form") or (forms and cues == len(forms) and forms[0] == "word"):
        return "word_form"
    pron, stress = _skill_text(sec, "pronunciation"), _skill_text(sec, "stress")
    dialogue = any(len(q.lines) > 1 for q in sec.questions)
    if pron and not stress and not dialogue:
        return "pronunciation"
    if stress and not pron and not dialogue:
        return "stress"
    return "mixed"


def _passage(lines: list[str]) -> str | None:
    """The passage with wrapped lines joined; a title, a short line or a paragraph keeps its
    own line."""
    out: list[str] = []
    for line in lines:
        if out and (_continues_line(out[-1], line) or re.search(r"\(\d{1,3}\)\s*$", out[-1])):
            out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)
    text = "\n".join(blanks(line) for line in out)
    return text or None


def _section(sec: _Sec) -> TranscribedSection:
    head = "\n".join(sec.head)
    points = _POINTS.search(head)
    instructions = head
    if points is not None:
        instructions = (head[: points.start()] + head[points.end() :]).strip()
        instructions = re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]{2,}", " ", instructions))
    kind: SectionKind = "questions"
    if _skill_text(sec, "listening"):
        kind = "listening"
    elif _skill_text(sec, "writing") and not sec.questions:
        kind = "writing"
    stimulus = _passage(sec.passage)
    gaps = {int(n) for n in _GAP.findall(stimulus or "")}
    questions: list[TranscribedQuestion] = []
    cues = 0
    for q in sec.questions:
        start = _answer_start(q)
        stem, cue = _stem_and_cue(q, start)
        cues += cue is not None
        form = _form(q, sec, start)
        if q.number in gaps and q.options and not stem:
            stem = None
        questions.append(
            TranscribedQuestion(
                printed_number=q.number,
                answer_form=form,  # type: ignore[arg-type]
                stem=stem,
                options=q.options or None,
                cue=cue,
                answer_start=start if form == "sentence" else None,
            )
        )
    skill = _skill(sec, [q.answer_form for q in questions], cues)
    pictures = (
        [_WHOLE_PAGE]
        if skill == "signs" or any(q.stem and _PICTURE.search(q.stem) for q in questions)
        else []
    )
    if kind == "writing":
        instructions = "\n".join([instructions, *(sec.passage)]).strip()
        groups: list[TranscribedGroup] = []
    elif kind == "listening" or (stimulus is None and not questions):
        groups = []
    else:
        groups = [TranscribedGroup(stimulus=stimulus, pictures=pictures, questions=questions)]
    numbers = [q.number for q in sec.questions]
    return TranscribedSection(
        printed_title=sec.title,
        instructions=blanks(instructions)
        if "\n" not in instructions
        else "\n".join(blanks(x) for x in instructions.split("\n")),
        kind=kind,
        skill=skill,
        points_text=points.group(0) if points else None,
        range_first=min(numbers) if kind == "listening" and numbers else None,
        range_last=max(numbers) if kind == "listening" and numbers else None,
        groups=groups,
    )


def structure_ocr_page(text: str) -> OcrStructure:
    """One page's plain OCR text (answer boxes removed) as ``TranscribeOut`` (module doc)."""
    reader = _Reader()
    lines = [line for line in text.split("\n") if line.strip()]
    for i, line in enumerate(lines):
        reader.feed(line, lines[i + 1 :])
    sections = [_section(s) for s in _settle(reader.sections)]
    out = TranscribeOut(header_text="\n".join(reader.header) or None, sections=sections)
    return OcrStructure(out=out, unplaced=reader.unplaced)
