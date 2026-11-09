"""``merge_and_normalize`` (llm-design §4): merge page transcripts into a ``TestDraft``.

- Continuation: a page's first section is merged into the previous page's last section when its
  ``printed_title`` is empty, or equals that title and prints no new (or the same) points text.
  Page breaks (step 22.5.7): it is also merged when the model marked it ``continued``, when
  its first question has the printed number of the previous page's last question (a question
  cut at the page's end), or when its first group goes on with the previous page's open passage
  (below). At the join, that question's copy fills the first copy's missing stem,
  options, cue or answer start (the first copy wins where both have text) and is dropped; a
  first group marked ``continued`` (or whose cloze gaps go on from the previous passage's last
  gap, or whose stem-less questions are that open passage's gaps) is joined into the previous
  page's last group: its stimulus is appended on a new line and its questions follow. A group
  with pictures is never joined (its picture boxes belong to its own page).
  :func:`open_unit` gives the next page's ``transcribe_page`` call the unit the page ended in.
- Listening →``meta.omitted_sections`` only (not stored). Safety net (llm-design §4): a
  listening section whose groups hold a question with a stem or options was misread (e.g. the
  model merged printed sections into one "listening" section) → it is stored and graded like a
  ``questions`` section, and its start page gets one pending ``validator_failed``
  (``reason="listening_with_questions"``, key ``validator_failed:<ref>:listening:<page_no>``).
  Writing → a section with
  ``graded=False`` **and** an ``omitted_sections`` entry (Appendix B.1b). Neither counts in
  ``points_possible``.
- Canonical numbers: sections 1..n over the stored sections; questions 1..N over the graded
  sections in order, then the writing questions. ``printed_title``/``printed_number`` are kept.
- Points (PRD D13 v8.0): every graded question is worth 10 / N (``etach.domain.points``),
  ``points_source="equal"``; no ``points_assumed`` item is made. Option labels are stored as
  the bare capital letter (:func:`clean_option_label`, step 22.5.2: also "A..", a fullwidth
  letter, a look-alike Cyrillic capital).
- Titles (D2, v1.21): an untitled section (empty, or only a numeral) takes its title from its
  section skill (``etach.domain.section_titles``), after the ids are made.
- Validators run on the draft; the failures are returned alongside it (``MergeResult``).
- Unreadable text (PRD D25, data-model §2.8): each page whose merged text holds ``???`` → one
  pending ``unreadable_text`` with ``{page_no, file_id, spans: [{path, question_id, text}]}``,
  one span per content field with ``???``. A section's own text belongs to the page where the
  section starts, a group's to its page, a question's to ``page_no``. ``title`` is not listed
  when it equals ``printed_title`` (it is a copy; the Fix of ``printed_title`` updates it).

Pure: no I/O.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from etach.domain.header import metadata_from
from etach.domain.llm_schemas import (
    RereadPiece,
    RereadPiecesOut,
    TranscribedGroup,
    TranscribedQuestion,
    TranscribedSection,
    TranscribeOut,
)
from etach.domain.models import (
    FORM_OF_OLD_TYPE,
    TRUE_FALSE_OPTIONS,
    OmittedSection,
    Option,
    PictureRef,
    Question,
    QuestionGroup,
    Section,
    TestContent,
    TestMetadata,
    true_false_letters,
)
from etach.domain.normalize import fold, value_norm
from etach.domain.points import clean_label, equal_points, points_possible
from etach.domain.section_titles import fill_titles
from etach.domain.validators import (
    ValidatorFailure,
    has_unreadable,
    missing_numbers,
    validate_content,
)
from etach.domain.working import PageTranscript, PendingReview, TestDraft

__all__ = [
    "ASSUMED_POINTS",
    "MergeResult",
    "PiecePages",
    "RereadAsk",
    "apply_reread",
    "choice_options",
    "clean_option_label",
    "clean_option_labels",
    "cut_repetition",
    "fingerprint_text",
    "legacy_section",
    "merge_pages",
    "open_unit",
    "page_transcript",
    "parse_points",
    "question_id",
    "reread_asks",
    "reread_text",
    "unreadable_pendings",
    "unreadable_spans",
]

ASSUMED_POINTS = 0.25

_POINTS = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:pts?|points?|diem|d)\b")
_BARE = re.compile(r"^\(?\s*(\d+(?:[.,]\d+)?)\s*\)?$")
_MARKUP = re.compile(r"\*\*|</?u>")


@dataclass
class MergeResult:
    draft: TestDraft
    pendings: list[PendingReview] = field(default_factory=list)
    failures: list[ValidatorFailure] = field(default_factory=list)


@dataclass(frozen=True)
class PiecePages:
    """Where a joined typed-PDF piece's content was printed (D12): the page of each group and of
    each question of its transcript, flat in document order (``documents.locate_pages``)."""

    groups: Sequence[int]
    questions: Sequence[int]


@dataclass
class _Sec:
    """A transcribed section gathered across pages (each group remembers its page)."""

    src: TranscribedSection
    groups: list[tuple[int, TranscribedGroup]] = field(default_factory=list)
    page_no: int = 0  # the page where the section starts
    # per group, the page of each question (D12: a joined typed-PDF piece); else the group's page
    q_pages: list[list[int]] = field(default_factory=list)


def _block_sig(head: tuple[str, str], stimulus: str | None, q: TranscribedQuestion) -> str:
    """A question's place in a repeated block: its section head, its group's stimulus, and its
    number, stem, options and cue."""
    return json.dumps(
        [
            head,
            value_norm(stimulus or ""),
            q.printed_number,
            q.stem,
            [o.text for o in q.options or []],
            q.cue,
        ],
        ensure_ascii=False,
    )


def cut_repetition(out: TranscribeOut) -> tuple[TranscribeOut, int]:
    """Stop a page's structure where the model's output starts repeating (step 22.5.6).

    A long typed page can make a small model loop: the same block comes back again until the
    output cap. A repeat is only a whole block repeated: questions with the same section (title
    and instructions), the same group stimulus and the same number, stem, options and cue as
    earlier ones, two in a row (or the last question of the output); questions under another
    section heading or another stimulus are never a repeat, so two passages that both number
    from 1 keep every question. The output is cut before the first repeated question, and
    before a section that repeats an earlier one with no question of its own. Returns the cut
    output and how many questions were dropped (0: the output is unchanged).
    """
    heads = [
        (value_norm(s.printed_title or ""), value_norm(s.instructions or "")) for s in out.sections
    ]
    sigs = [
        _block_sig(head, g.stimulus, q)
        for sec, head in zip(out.sections, heads, strict=True)
        for g in sec.groups
        for q in g.questions
    ]
    total = len(sigs)
    cut = total
    seen: set[str] = set()
    for i, sig in enumerate(sigs):
        if sig in seen and (i + 1 == total or sigs[i + 1] in seen or sigs[i + 1] == sig):
            cut = i
            break
        seen.add(sig)
    sections: list[TranscribedSection] = []
    seen_heads: set[tuple[str, str]] = set()
    at = 0
    for sec, head in zip(out.sections, heads, strict=True):
        groups: list[TranscribedGroup] = []
        stop = False
        for group in sec.groups:
            n = len(group.questions)
            if at + n > cut:
                questions = group.questions[: cut - at]
                if questions:
                    groups.append(group.model_copy(update={"questions": questions}))
                stop = True
                break
            groups.append(group)
            at += n
        repeated_head = head in seen_heads and not any(g.questions for g in groups)
        seen_heads.add(head)
        if not repeated_head and (groups or not stop):
            sections.append(sec.model_copy(update={"groups": groups}))
        if stop or repeated_head:
            break
    dropped = total - cut
    if dropped == 0 and len(sections) == len(out.sections):
        return out, 0
    return out.model_copy(update={"sections": sections}), max(dropped, 1)


def page_transcript(page_no: int, out: TranscribeOut, llm_call_id: str) -> PageTranscript:
    """Wrap one ``transcribe_page`` output as the graph-state ``PageTranscript``."""
    return PageTranscript(
        page_no=page_no,
        header_text=out.header_text,
        sections=[s.model_dump() for s in out.sections],
        llm_call_id=llm_call_id,
    )


def parse_points(text: str | None) -> float | None:
    """``(2.5 pts)``, ``(2,5 điểm)``, ``2.5 points``, ``1đ``, ``(1.0 point)`` → the number."""
    if not text:
        return None
    key = fold(text).lower().strip()
    m = _POINTS.search(key) or _BARE.match(key)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


# the marks printed around an option letter: ASCII, the middle dot, the ideographic full stop and
# comma, the ellipsis; and spaces
_LABEL_MARKS = ".)(:][-,; ·。、…"
# Cyrillic A, B, C, E, H and Greek A, B, E, H: capitals that look like Latin option letters
_LOOKALIKE = str.maketrans(
    {0x0410: "A", 0x0412: "B", 0x0421: "C", 0x0415: "E", 0x041D: "H"}
    | {0x0391: "A", 0x0392: "B", 0x0395: "E", 0x0397: "H"}
)


def clean_option_label(label: str) -> str:
    """A printed option letter as its bare capital (step 22.5.2, the "A.." text). Wider than
    ``points.clean_label``: the label is NFKC-normalized (a fullwidth A and full stop read as
    "A."), invisible
    characters are dropped, every mark around the letter goes ("A..", "A,", "(A)", "A…"), and a
    Cyrillic or Greek look-alike capital is read as the Latin one. Anything that is not one letter
    then goes to ``points.clean_label`` (so ``???`` stays)."""
    text = "".join(
        ch for ch in unicodedata.normalize("NFKC", label) if unicodedata.category(ch) != "Cf"
    )
    core = text.strip().strip(_LABEL_MARKS).translate(_LOOKALIKE)
    if len(core) == 1 and core.isascii() and core.isalpha():
        return core.upper()
    return clean_label(label)


def clean_option_labels(options: list[Option] | None) -> list[Option] | None:
    """The options with :func:`clean_option_label` applied (``None`` stays ``None``)."""
    if options is None:
        return None
    return [
        o
        if o.label == clean_option_label(o.label)
        else o.model_copy(update={"label": clean_option_label(o.label)})
        for o in options
    ]


#: Words that say a question is answered True/False, as Vietnamese school tests print them:
#: "True … False" (incl. "True/False"), "Đúng/Sai", "Đúng hay Sai", "(T) … (F)" (incl.
#: "Đúng (T) … Sai (F)"), and the capitals T and F joined by "/", a dash, "or", "hay" or "hoặc"
#: ("T/F", "T - F" or with an en or em dash, "Write T or F", "T hay F"). The bare letters must be
#: capitals and stand next to each other, so a "T" and an "F" apart in ordinary text do not count.
_TRUE_FALSE_TEXT = re.compile(
    r"(?i:\btrue\b.*\bfalse\b"
    r"|\bđúng\s*(?:/|[-\u2013\u2014]|hay|hoặc)\s*sai\b"
    r"|\(\s*T\s*\).*\(\s*F\s*\))"
    r"|\bT\s*(?:/|[-\u2013\u2014]|(?i:or|hay|hoặc))\s*F\b",
    re.DOTALL,
)


def choice_options(
    answer_form: str, options: list[Option] | None, *texts: str | None
) -> list[Option] | None:
    """A True/False question's options (step 22.5.3, D9): a ``choice`` the model gave without
    options gets the two options ``T. True`` and ``F. False`` when its section instructions or
    stem say True/False (``texts``); a ``choice`` the model gave two options that read True and
    False (e.g. ``A. FALSE``, ``B. TRUE``; :func:`etach.domain.models.true_false_letters`) gets the
    same two options, in that order (checklist (d), R22.5.3.8). Anything else is returned
    unchanged, so a choice whose options were lost (e.g. at a page break) still fails the option
    check."""
    if answer_form != "choice":
        return options
    if options:
        if true_false_letters([(o.label, o.text) for o in options]) is None:
            return options
    elif not any(t and _TRUE_FALSE_TEXT.search(t) for t in texts):
        return options
    return [Option(label=label, text=text) for label, text in TRUE_FALSE_OPTIONS]


def relabelled_from(read: list[Option] | None, options: list[Option] | None) -> list[Option] | None:
    """The options as read when :func:`choice_options` relabelled a True/False choice's own
    options (e.g. ``A. FALSE`` / ``B. TRUE``) to ``T`` / ``F``, so a key-photo letter or a
    student's letter can be mapped through them (step 22.5.8 (a)(5)); None otherwise."""
    if not read or not options or options is read:
        return None
    if [o.label for o in read] == [o.label for o in options]:
        return None
    return read if true_false_letters([(o.label, o.text) for o in read]) is not None else None


def _legacy_section(raw: object) -> object:
    """A page transcript saved before step 22.5.3 (a run paused across the upgrade): each
    question's ``type`` becomes its ``answer_form``."""
    if not isinstance(raw, dict):
        return raw
    groups = []
    for g in raw.get("groups") or []:
        if isinstance(g, dict) and isinstance(g.get("questions"), list):
            questions = []
            for q in g["questions"]:
                if isinstance(q, dict) and "type" in q and "answer_form" not in q:
                    old = q["type"]
                    q = {k: v for k, v in q.items() if k != "type"}
                    q["answer_form"] = FORM_OF_OLD_TYPE.get(str(old), "sentence")
                questions.append(q)
            g = {**g, "questions": questions}
        groups.append(g)
    return {**raw, "groups": groups}


legacy_section = _legacy_section  # the graph reads saved page transcripts too (step 22.5.7)


def question_id(section_index: int, printed_number: int, stem: str | None, salt: int = 0) -> str:
    """``q-`` + 8 hex of sha1(section index, printed number, stem[, salt])."""
    raw = f"{section_index}|{printed_number}|{stem or ''}"
    if salt:
        raw += f"|{salt}"
    return "q-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]


def _short_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(p) for p in parts)
    return prefix + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]


def fingerprint_text(content: TestContent) -> str:
    """The normalized printed text of a test (instructions, stimuli, stems, cues, options).

    Markup (``**``, ``<u>``) is dropped and the result goes through ``value_norm``. Part B's
    similarity consumes this string.
    """
    parts: list[str] = []
    for section in content.sections:
        parts.append(section.instructions)
        for group in section.groups:
            if group.stimulus:
                parts.append(group.stimulus)
            for q in group.questions:
                for text in (q.stem, q.cue):
                    if text:
                        parts.append(text)
                for opt in q.options or []:
                    parts.append(opt.text)
    return value_norm(_MARKUP.sub("", " ".join(p for p in parts if p)))


def _continues(prev: _Sec, nxt: TranscribedSection) -> bool:
    if nxt.kind != prev.src.kind:
        return False
    title = value_norm(nxt.printed_title)
    if not title:
        return True
    if title != value_norm(prev.src.printed_title):
        return False
    # Same label: a continuation unless it prints its own, different points (B.1's second "VI").
    return nxt.points_text is None or parse_points(nxt.points_text) == parse_points(
        prev.src.points_text
    )


# --- page breaks (step 22.5.7) -------------------------------------------------------------

_GAP = re.compile(r"\((\d+)\)\s*_{2,}")  # a cloze gap as transcribed: "(17) ____"
HINT_INSTRUCTIONS_CHARS = 200
HINT_STEM_CHARS = 300
HINT_PASSAGE_CHARS = 600  # with the head and the stem, the hint stays near 300 tokens


def _clip(text: str, n: int, *, tail: bool = False) -> str:
    text = text.strip() if tail else " ".join(text.split())
    if len(text) <= n:
        return text
    return "…" + text[-n:] if tail else text[:n] + "…"


def _gaps(stimulus: str | None) -> list[int]:
    return [int(m) for m in _GAP.findall(stimulus or "")]


def _lacks(q: TranscribedQuestion, group: TranscribedGroup) -> list[str]:
    """What a question cut at a page's end lacks: its options (a choice), its stem (no passage)."""
    out: list[str] = []
    if not (q.stem and q.stem.strip()) and not group.stimulus:
        out.append("no stem")
    if q.answer_form == "choice" and not q.options:
        out.append("no options")
    return out


def _passage_open(group: TranscribedGroup) -> bool:
    """A passage whose questions go on past the page: none read yet, or gaps after the last."""
    if not group.stimulus:
        return False
    if not group.questions:
        return True
    gaps = _gaps(group.stimulus)
    return bool(gaps) and max(gaps) > max(q.printed_number for q in group.questions)


def open_unit(out: TranscribeOut) -> str | None:
    """The last open unit of a page as already read, as text for the next page's call (step
    22.5.7), or ``None`` when nothing is open. Open: a ``questions`` section whose heading has
    no question yet, a last question with no options (a choice) or no stem, or a passage whose
    questions go on. The text names the section (title, instructions), the question and what it
    lacks ("Question 14: stem, no options"), or the passage's last paragraph from its last
    blank; at most about 300 tokens."""
    if not out.sections or out.sections[-1].kind != "questions":
        return None
    sec = out.sections[-1]
    head = f'Section "{sec.printed_title}"'
    if sec.instructions.strip():
        head += f": {_clip(sec.instructions, HINT_INSTRUCTIONS_CHARS)}"
    group = sec.groups[-1] if sec.groups else None
    if group is None or (not group.questions and not group.stimulus):
        return f"{head}\nNo questions read yet."
    if _passage_open(group):
        paragraph = (group.stimulus or "").strip().split("\n")[-1]
        gaps = list(_GAP.finditer(paragraph))
        if gaps:
            paragraph = paragraph[gaps[-1].start() :]
        read = sorted(q.printed_number for q in group.questions)
        so_far = f"questions read: {read[0]}-{read[-1]}" if read else "no questions read yet"
        text = _clip(paragraph, HINT_PASSAGE_CHARS, tail=True)
        return f'{head}\nPassage ({so_far}), last paragraph from its last blank: "{text}"'
    q = group.questions[-1] if group.questions else None
    lacks = _lacks(q, group) if q is not None else []
    if q is None or not lacks:
        return None
    has_stem = bool(q.stem and q.stem.strip())
    has = "stem" if has_stem else "options" if q.options else "number only"
    line = f"Question {q.printed_number}: {has}, {', '.join(lacks)}"
    if has_stem and q.stem:
        line += f'. Stem: "{_clip(q.stem, HINT_STEM_CHARS)}"'
    return f"{head}\n{line}"


def _filled(first: TranscribedQuestion, rest: TranscribedQuestion) -> TranscribedQuestion:
    """A question cut at a page break: the first copy, with its empty fields from the rest."""
    update: dict[str, object] = {"continued": False}
    if not (first.stem and first.stem.strip()) and rest.stem and rest.stem.strip():
        update["stem"] = rest.stem
    if not first.options and rest.options:
        update["options"] = rest.options
        update["answer_form"] = rest.answer_form
    if not first.cue and rest.cue:
        update["cue"] = rest.cue
    if not first.answer_start and rest.answer_start:
        update["answer_start"] = rest.answer_start
    return first.model_copy(update=update)


def _last_question(prev: _Sec) -> tuple[TranscribedQuestion, TranscribedGroup] | None:
    """The previous page's last question and its group."""
    for _, g in reversed(prev.groups):
        if g.questions:
            return g.questions[-1], g
    return None


def _whole(q: TranscribedQuestion, group: TranscribedGroup) -> bool:
    """A question with its own stem that lacks nothing (options for a choice)."""
    return bool(q.stem and q.stem.strip()) and not _lacks(q, group)


def _keeps_both(
    last: tuple[TranscribedQuestion, TranscribedGroup],
    first: tuple[TranscribedQuestion, TranscribedGroup],
) -> bool:
    """Both copies of a printed number are whole and differ: two questions, never drop one."""
    (a, a_group), (b, b_group) = last, first
    return (
        _whole(a, a_group)
        and _whole(b, b_group)
        and (value_norm(a.stem or ""), a.options) != (value_norm(b.stem or ""), b.options)
    )


def _splits_question(prev: _Sec, nxt: TranscribedSection) -> bool:
    """``nxt`` starts with the rest of the previous page's last question: the same printed
    number, and the last question lacks something or ``nxt`` has no title of its own (empty or
    the previous section's). A new titled section restarting at that number ("II" at 14, Part B
    at 1) after a whole question is no cut, nor are two whole, different copies."""
    last = _last_question(prev)
    g0 = nxt.groups[0] if nxt.groups else None
    if last is None or g0 is None or not g0.questions:
        return False
    first = g0.questions[0]
    if first.printed_number != last[0].printed_number or _keeps_both(last, (first, g0)):
        return False
    title = value_norm(nxt.printed_title or "")
    return bool(_lacks(*last)) or not title or title == value_norm(prev.src.printed_title or "")


def _joins_passage(prev: TranscribedGroup, nxt: TranscribedGroup) -> bool:
    """``nxt`` (a page's first group) goes on with ``prev``'s passage (module doc)."""
    if not prev.stimulus or nxt.pictures:
        return False
    if nxt.continued:
        return True
    before, after = _gaps(prev.stimulus), _gaps(nxt.stimulus)
    if nxt.stimulus:
        return bool(before and after) and min(after) == max(before) + 1
    numbers = [q.printed_number for q in nxt.questions]
    return (
        bool(numbers)
        and _passage_open(prev)
        and all(not (q.stem and q.stem.strip()) for q in nxt.questions)
        and set(numbers) <= set(before)
    )


def _join(prev: _Sec, groups: list[tuple[int, TranscribedGroup]], q_pages: list[list[int]]) -> None:
    """Join a page's first section (its ``groups`` and ``q_pages``) into ``prev`` (module doc)."""
    groups, q_pages = list(groups), [list(p) for p in q_pages]
    last = _last_question(prev)
    if groups and groups[0][1].questions and last is not None:
        g_page, g0 = groups[0]
        first = g0.questions[0]
        if first.printed_number == last[0].printed_number and not _keeps_both(last, (first, g0)):
            for k in range(len(prev.groups) - 1, -1, -1):
                p_page, pg = prev.groups[k]
                if pg.questions:
                    merged = _filled(pg.questions[-1], g0.questions[0])
                    questions = [*pg.questions[:-1], merged]
                    prev.groups[k] = (p_page, pg.model_copy(update={"questions": questions}))
                    break
            g0 = g0.model_copy(update={"questions": g0.questions[1:]})
            groups[0] = (g_page, g0)
            q_pages[0] = q_pages[0][1:]
            if not g0.questions and not g0.stimulus and not g0.pictures:
                groups, q_pages = groups[1:], q_pages[1:]
    if groups and prev.groups and _joins_passage(prev.groups[-1][1], groups[0][1]):
        p_page, pg = prev.groups[-1]
        g0 = groups[0][1]
        stimulus = f"{pg.stimulus}\n{g0.stimulus}" if g0.stimulus else pg.stimulus
        update = {"stimulus": stimulus, "questions": [*pg.questions, *g0.questions]}
        prev.groups[-1] = (p_page, pg.model_copy(update=update))
        prev.q_pages[-1] = [*prev.q_pages[-1], *q_pages[0]]
        groups, q_pages = groups[1:], q_pages[1:]
    prev.groups.extend(groups)
    prev.q_pages.extend(q_pages)


def _page_break_join(prev: _Sec, nxt: TranscribedSection) -> bool:
    """A page's first section goes on with the previous page's last one (module doc)."""
    if _continues(prev, nxt):
        return True
    if prev.src.kind == "listening" or nxt.kind == "listening":
        return False
    if nxt.continued or _splits_question(prev, nxt):
        return True
    last = prev.groups[-1][1] if prev.groups else None
    return (
        last is not None
        and bool(nxt.groups)
        and _passage_open(last)
        and _joins_passage(last, nxt.groups[0])
    )


def _gather(
    pages: Sequence[PageTranscript], placed: Mapping[int, PiecePages] | None = None
) -> list[_Sec]:
    out: list[_Sec] = []
    for page in sorted(pages, key=lambda p: p.page_no):
        where = (placed or {}).get(page.page_no)
        g_flat = iter(where.groups) if where else None
        q_flat = iter(where.questions) if where else None
        for i, raw in enumerate(page.sections):
            sec = TranscribedSection.model_validate(_legacy_section(raw))
            groups: list[tuple[int, TranscribedGroup]] = []
            q_pages: list[list[int]] = []
            for g in sec.groups:
                g_page = next(g_flat, page.page_no) if g_flat else page.page_no
                groups.append((g_page, g))
                q_pages.append([next(q_flat, g_page) if q_flat else g_page for _ in g.questions])
            if i == 0 and out and _page_break_join(out[-1], sec):
                _join(out[-1], groups, q_pages)
                continue
            start = groups[0][0] if groups else page.page_no
            out.append(_Sec(sec, groups, start, q_pages))
    return out


def _printed_numbers(sec: _Sec) -> list[int]:
    nums = [q.printed_number for _, g in sec.groups for q in g.questions]
    if not nums and sec.src.range_first is not None:
        last = sec.src.range_last if sec.src.range_last is not None else sec.src.range_first
        nums = list(range(sec.src.range_first, last + 1))
    return nums


def _has_question_content(sec: _Sec) -> bool:
    """A question with a non-empty stem or at least one option (the listening safety net)."""
    return any(
        bool(q.stem and q.stem.strip()) or bool(q.options)
        for _, g in sec.groups
        for q in g.questions
    )


def _listening_pendings(rescued: Sequence[tuple[int, _Sec, str]], ref: str) -> list[PendingReview]:
    """One pending ``validator_failed`` per start page of the rescued listening sections.

    ``rescued`` holds (stored section index, section, section id). The dedupe key is
    ``validator_failed:<ref>:listening:<page_no>``: the page stays stable across merge passes
    (section indexes shift when a retranscription splits or joins sections), and one item per
    page stays unique when two rescued sections start on the same page. The proposal has the
    shape of the ``transcribe_page`` item (``task``, ``page_no``, ``failures``,
    ``call_failure``) plus ``reason`` and ``sections``; Accept keeps the stored content, Fix
    takes the edited content (review.py)."""
    by_page: dict[int, list[tuple[int, _Sec, str]]] = {}
    for item in rescued:
        by_page.setdefault(item[1].page_no, []).append(item)
    out: list[PendingReview] = []
    for page_no, items in sorted(by_page.items()):
        failures = [
            {
                "validator": "listening_with_questions",
                "page_no": page_no,
                "question_id": None,
                "printed_number": None,
                "message": (
                    f"Section {s_idx + 1} ({sec.src.printed_title or 'untitled'}) was read as "
                    f"listening but holds {_question_count(sec)} questions; it was kept as a "
                    "graded section. Check how it splits into the printed sections."
                ),
            }
            for s_idx, sec, _ in items
        ]
        out.append(
            PendingReview(
                kind="validator_failed",
                dedupe_key=f"validator_failed:{ref}:listening:{page_no}",
                refs={"page_no": page_no},
                proposal={
                    "task": "transcribe_page",
                    "page_no": page_no,
                    "failures": failures,
                    "call_failure": None,
                    "reason": "listening_with_questions",
                    "sections": [
                        {
                            "section_id": section_id,
                            "section_number": s_idx + 1,
                            "printed_title": sec.src.printed_title,
                            "questions": _question_count(sec),
                        }
                        for s_idx, sec, section_id in items
                    ],
                },
            )
        )
    return out


def _question_count(sec: _Sec) -> int:
    return sum(len(g.questions) for _, g in sec.groups)


def unreadable_spans(
    content: TestContent,
    *,
    section_pages: Mapping[int, int] | None = None,
    group_pages: Mapping[tuple[int, int], int] | None = None,
) -> dict[int, list[dict[str, str | None]]]:
    """page_no → the content fields with ``???`` on that page, in document order (module doc).

    ``section_pages`` maps a section index to the page where it starts, ``group_pages`` a
    (section index, group index) to the group's page. Without them a group's page is its first
    question's page, and a section's page is its first group's page (else 1).
    """
    by_page: dict[int, list[dict[str, str | None]]] = {}

    def add(page_no: int, path: str, qid: str | None, text: str | None) -> None:
        if has_unreadable(text):
            by_page.setdefault(page_no, []).append({"path": path, "question_id": qid, "text": text})

    for si, section in enumerate(content.sections):
        g_pages: list[int] = []
        for gi, group in enumerate(section.groups):
            first_q = group.questions[0].page_no if group.questions else None
            fallback = first_q if first_q is not None else (g_pages[-1] if g_pages else 1)
            g_pages.append((group_pages or {}).get((si, gi), fallback))
        s_page = (section_pages or {}).get(si, g_pages[0] if g_pages else 1)
        base = f"sections[{si}]"
        add(s_page, f"{base}.printed_title", None, section.printed_title)
        if section.title != section.printed_title:
            add(s_page, f"{base}.title", None, section.title)
        add(s_page, f"{base}.instructions", None, section.instructions)
        for gi, group in enumerate(section.groups):
            g_base = f"{base}.groups[{gi}]"
            add(g_pages[gi], f"{g_base}.stimulus", None, group.stimulus)
            for qi, q in enumerate(group.questions):
                q_base = f"{g_base}.questions[{qi}]"
                q_page = q.page_no if q.page_no is not None else g_pages[gi]
                add(q_page, f"{q_base}.stem", q.id, q.stem)
                add(q_page, f"{q_base}.cue", q.id, q.cue)
                for oi, opt in enumerate(q.options or []):
                    add(q_page, f"{q_base}.options[{oi}].label", q.id, opt.label)
                    add(q_page, f"{q_base}.options[{oi}].text", q.id, opt.text)
    return dict(sorted(by_page.items()))


def unreadable_pendings(
    content: TestContent,
    *,
    page_files: Mapping[int, str],
    ref: str = "",
    section_pages: Mapping[int, int] | None = None,
    group_pages: Mapping[tuple[int, int], int] | None = None,
) -> list[PendingReview]:
    """One pending ``unreadable_text`` per page with ``???`` (data-model §2.8).

    The dedupe key is ``unreadable_text:<ref>:p<page_no>``; the extract ``save`` rewrites it
    with the test id."""
    spans = unreadable_spans(content, section_pages=section_pages, group_pages=group_pages)
    return [
        PendingReview(
            kind="unreadable_text",
            dedupe_key=f"unreadable_text:{ref}:p{page_no}",
            refs={"page_no": page_no},
            proposal={"page_no": page_no, "file_id": page_files.get(page_no), "spans": items},
        )
        for page_no, items in spans.items()
    ]


def merge_pages(
    pages: Sequence[PageTranscript],
    *,
    page_files: Mapping[int, str],
    ref: str = "",
    filename: str | None = None,
    meta: TestMetadata | None = None,
    placed: Mapping[int, PiecePages] | None = None,
) -> MergeResult:
    """Merge the page transcripts into a draft with pending reviews and validator failures.

    - ``page_files``: page_no → the page image's file id (pictures point at it, PRD D11).
    - ``ref``: the run or test id for dedupe keys (supplied by step 9).
    - ``filename``: the first page's original file name, for ``metadata_from``.
    - ``meta``: base metadata to use instead of the header/file-name one (its
      ``omitted_sections`` are replaced).
    - ``placed``: transcript page_no → :class:`PiecePages` for a joined typed-PDF piece (D12):
      each question gets the page its text starts on, each group its own page (its pictures).
    """
    ordered = sorted(pages, key=lambda p: p.page_no)
    pendings: list[PendingReview] = []
    if meta is None:
        header_text = next((p.header_text for p in ordered if p.header_text), None)
        fields, meta_pendings = metadata_from(header_text, filename, ref=ref)
        pendings.extend(meta_pendings)
        meta = TestMetadata(**fields)

    omitted: list[OmittedSection] = []
    stored: list[tuple[_Sec, bool]] = []  # (section, graded)
    rescued_idx: set[int] = set()  # stored indexes of listening sections kept by the safety net
    for sec in _gather(ordered, placed):
        kind = sec.src.kind
        if kind == "listening" and _has_question_content(sec):
            # misread as listening (e.g. printed sections merged): keep it as a questions section
            rescued_idx.add(len(stored))
            stored.append((sec, True))
            continue
        if kind == "listening":
            omitted.append(
                OmittedSection(
                    title=sec.src.printed_title,
                    questions=_printed_numbers(sec),
                    points=parse_points(sec.src.points_text) or 0.0,
                    kind="listening",
                )
            )
            continue
        if kind == "writing":
            nums = _printed_numbers(sec)
            printed = parse_points(sec.src.points_text)
            omitted.append(
                OmittedSection(
                    title=sec.src.printed_title,
                    questions=nums,
                    points=printed if printed is not None else ASSUMED_POINTS * len(nums),
                    kind="writing",
                )
            )
        stored.append((sec, kind != "writing"))

    # Canonical question numbers: graded sections first (in order), then writing.
    order = [i for i, (_, g) in enumerate(stored) if g] + [
        i for i, (_, g) in enumerate(stored) if not g
    ]
    next_no = 1
    first_no: dict[int, int] = {}
    for i in order:
        first_no[i] = next_no
        next_no += _question_count(stored[i][0])

    sections: list[Section] = []
    section_pages: dict[int, int] = {}
    group_pages: dict[tuple[int, int], int] = {}
    used_ids: set[str] = set()
    rescued: list[tuple[int, _Sec, str]] = []
    for s_idx, (sec, graded) in enumerate(stored):
        n_questions = _question_count(sec)
        printed = parse_points(sec.src.points_text)
        source: Literal["printed", "assumed"]
        if printed is not None:
            source = "printed"
            total = printed
            per_q = printed / n_questions if n_questions else 0.0
        else:
            source = "assumed"
            per_q = ASSUMED_POINTS
            total = ASSUMED_POINTS * n_questions
        section_id = _short_id("s-", s_idx + 1, sec.src.printed_title, sec.src.instructions)
        if s_idx in rescued_idx:
            rescued.append((s_idx, sec, section_id))
        number = first_no[s_idx]
        groups: list[QuestionGroup] = []
        section_pages[s_idx] = sec.page_no
        for g_idx, (page_no, tg) in enumerate(sec.groups):
            group_pages[(s_idx, g_idx)] = page_no
            questions: list[Question] = []
            for q_idx, tq in enumerate(tg.questions):
                salt = 0
                qid = question_id(s_idx + 1, tq.printed_number, tq.stem)
                while qid in used_ids:
                    salt += 1
                    qid = question_id(s_idx + 1, tq.printed_number, tq.stem, salt)
                used_ids.add(qid)
                read_options = clean_option_labels(tq.options)
                options = choice_options(
                    tq.answer_form, read_options, sec.src.instructions, tq.stem
                )
                questions.append(
                    Question(
                        id=qid,
                        number=number,
                        printed_number=tq.printed_number,
                        page_no=sec.q_pages[g_idx][q_idx],
                        answer_form=tq.answer_form,
                        stem=tq.stem,
                        options=options,
                        cue=tq.cue,
                        answer_start=tq.answer_start,
                        points=per_q,
                        old_options=relabelled_from(read_options, options),
                    )
                )
                number += 1
            pictures: list[PictureRef] = []
            if tg.pictures and page_no in page_files:
                pictures.append(PictureRef(file_id=page_files[page_no], page_no=page_no))
            groups.append(
                QuestionGroup(
                    id=_short_id("g-", section_id, g_idx),
                    stimulus=tg.stimulus,
                    pictures=pictures,
                    questions=questions,
                )
            )
        sections.append(
            Section(
                id=section_id,
                number=s_idx + 1,
                printed_title=sec.src.printed_title,
                title=sec.src.printed_title,
                instructions=sec.src.instructions,
                points=total,
                points_source=source,
                skill=sec.src.skill,
                graded=graded,
                groups=groups,
            )
        )
    # PRD D13 v8.0: every graded question is worth 10 / N; no points_assumed items (v1.19)
    content = equal_points(fill_titles(TestContent(sections=sections)))
    pendings.extend(_listening_pendings(rescued, ref))
    pendings.extend(
        unreadable_pendings(
            content,
            page_files=page_files,
            ref=ref,
            section_pages=section_pages,
            group_pages=group_pages,
        )
    )
    meta = meta.model_copy(update={"omitted_sections": omitted})
    draft = TestDraft(
        meta=meta,
        content=content,
        fingerprint=fingerprint_text(content),
        points_possible=points_possible(content),
    )
    return MergeResult(draft=draft, pendings=pendings, failures=validate_content(content, omitted))


# --- the targeted re-read (step 22.5.7) -----------------------------------------------------

#: At most this many missing printed numbers are asked for in one re-read call.
MAX_REREAD_MISSING = 20
#: The field a failing check names: the re-read replaces it (other fields are only filled).
_FAILING_FIELD: dict[str, Literal["options", "stem"]] = {
    "mcq_options": "options",
    "gap_fill_blank": "stem",
}
_PROBLEM = {"options": "its options were not read right", "stem": "its blank ____ is missing"}


@dataclass(frozen=True)
class RereadAsk:
    """One question the targeted re-read asks for: a broken question, by its section's printed
    title on the page and its printed number, with the field that failed; or a missing printed
    number (``section_title`` and ``field`` are ``None``)."""

    printed_number: int
    section_title: str | None
    field: Literal["options", "stem"] | None


def _locate(sections: Sequence[TranscribedSection], n: int) -> tuple[int, int, int] | None:
    """The first (section, group, question) index of printed number ``n``, if read."""
    for si, sec in enumerate(sections):
        for gi, group in enumerate(sec.groups):
            for qi, q in enumerate(group.questions):
                if q.printed_number == n:
                    return si, gi, qi
    return None


def reread_asks(
    out: TranscribeOut,
    failures: Sequence[ValidatorFailure],
    content: TestContent,
    omitted: Sequence[OmittedSection],
) -> list[RereadAsk]:
    """What to read again on one page, from that page's validator failures (in the merged
    ``content``): a failing ``choice`` or blank question by its printed number (located on the
    page as read), and for a ``numbering`` failure the missing numbers before it (at most
    :data:`MAX_REREAD_MISSING`). A numbering failure with no gap (a number repeated or out of
    order) asks nothing."""
    asks: dict[int, RereadAsk] = {}
    missing = 0
    for f in failures:
        field_name = _FAILING_FIELD.get(f.validator)
        if field_name is not None and f.printed_number is not None:
            where = _locate(out.sections, f.printed_number)
            if where is not None and f.printed_number not in asks:
                title = out.sections[where[0]].printed_title
                asks[f.printed_number] = RereadAsk(f.printed_number, title, field_name)
        elif f.validator == "numbering" and f.question_id is not None:
            for n in missing_numbers(content, omitted, f.question_id):
                if n in asks or missing >= MAX_REREAD_MISSING:
                    continue
                if _locate(out.sections, n) is None:
                    asks[n] = RereadAsk(n, None, None)
                    missing += 1
    return sorted(asks.values(), key=lambda a: a.printed_number)


def reread_text(out: TranscribeOut, asks: Sequence[RereadAsk]) -> str:
    """The ``{{pieces}}`` input of ``reread_pieces``: the page's section titles, each broken
    question with what failed and its first reading, and the missing numbers."""
    titles = ", ".join(f'"{s.printed_title}"' for s in out.sections)
    lines = [f"Section titles on this page: {titles}.", "Read again only these questions:"]
    gone: list[str] = []
    for ask in asks:
        where = _locate(out.sections, ask.printed_number)
        if ask.field is None or where is None:
            gone.append(str(ask.printed_number))
            continue
        si, gi, qi = where
        q = out.sections[si].groups[gi].questions[qi]
        first = json.dumps(q.model_dump(include={"stem", "options", "cue"}), ensure_ascii=False)
        lines.append(
            f'- Question {ask.printed_number} (section "{ask.section_title}"): '
            f"{_PROBLEM[ask.field]}. First reading: {first}"
        )
    if gone:
        lines.append(f"- Questions {', '.join(gone)}: missing from the first reading.")
    return "\n".join(lines)


def _has(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _patched(
    q: TranscribedQuestion, piece: RereadPiece, failing: Literal["options", "stem"]
) -> TranscribedQuestion:
    """``q`` with its failing field replaced and its empty fields filled from ``piece``."""
    update: dict[str, object] = {}
    for name in ("stem", "options", "cue", "answer_start"):
        new = getattr(piece, name)
        if _has(new) and (name == failing or not _has(getattr(q, name))):
            update[name] = new
    return q.model_copy(update=update) if update else q


def _inserted(sec: TranscribedSection, q: TranscribedQuestion) -> TranscribedSection:
    """``sec`` with ``q`` after the nearest lower printed number (else before the first higher
    one, else at the end of its last group; a section with no group gets one)."""
    n = q.printed_number
    lower: tuple[int, int, int] | None = None  # (number, group, index to insert at)
    higher: tuple[int, int] | None = None
    for gi, group in enumerate(sec.groups):
        for qi, x in enumerate(group.questions):
            if x.printed_number < n and (lower is None or x.printed_number > lower[0]):
                lower = (x.printed_number, gi, qi + 1)
            if x.printed_number > n and higher is None:
                higher = (gi, qi)
    if not sec.groups:
        group = TranscribedGroup(stimulus=None, pictures=[], questions=[q])
        return sec.model_copy(update={"groups": [group]})
    if lower is not None:
        gi, at = lower[1], lower[2]
    elif higher is not None:
        gi, at = higher
    else:
        gi, at = len(sec.groups) - 1, len(sec.groups[-1].questions)
    groups = list(sec.groups)
    qs = list(groups[gi].questions)
    qs.insert(at, q)
    groups[gi] = groups[gi].model_copy(update={"questions": qs})
    return sec.model_copy(update={"groups": groups})


def apply_reread(
    out: TranscribeOut, asks: Sequence[RereadAsk], got: RereadPiecesOut
) -> TranscribeOut:
    """Patch the re-read pieces into the page (step 22.5.7). A piece not asked for, or under a
    section title the page does not have, is dropped; a broken question gets its failing field
    replaced and its empty fields filled; a missing number is inserted into the named section
    after the nearest lower number. The first piece per number wins; every other section, group
    and question is kept as the same object (so it dumps byte-identical)."""
    by_no = {a.printed_number: a for a in asks}
    sections = list(out.sections)
    done: set[int] = set()
    for piece in got.pieces:
        n = piece.printed_number
        ask = by_no.get(n)
        if ask is None or n in done:
            continue
        title = piece.section_title.strip()
        si = next((i for i, s in enumerate(sections) if s.printed_title.strip() == title), None)
        if si is None:
            continue
        sec = sections[si]
        if ask.field is None:
            if _locate(sections, n) is not None:
                continue
            q = TranscribedQuestion(
                printed_number=n,
                answer_form=piece.answer_form,
                stem=piece.stem,
                options=piece.options,
                cue=piece.cue,
                answer_start=piece.answer_start,
            )
            sections[si] = _inserted(sec, q)
        else:
            where = _locate([sec], n)
            if where is None:
                continue
            _, gi, qi = where
            old = sec.groups[gi].questions[qi]
            new = _patched(old, piece, ask.field)
            if new is old:
                continue
            groups = list(sec.groups)
            qs = list(groups[gi].questions)
            qs[qi] = new
            groups[gi] = groups[gi].model_copy(update={"questions": qs})
            sections[si] = sec.model_copy(update={"groups": groups})
        done.add(n)
    return out.model_copy(update={"sections": sections}) if done else out
