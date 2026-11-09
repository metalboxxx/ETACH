"""Eval fixtures: the folder format and its loaders (plan step 11, llm-design §8).

The format
==========

``fixtures/<set>/<name>/`` with ``<set>`` = ``tuning`` or ``heldout``. The folder is gitignored
(student names and handwriting); only ``fixtures/MANIFEST.sha256`` is committed. Folders whose
name starts with ``_`` or ``.`` are skipped.

``pages/``
    The photos, PDF or DOCX files of the paper (and of the answer key, if any).

``input.json`` — the photo-check choices (:class:`FixtureInput`)::

    {"pages": [{"file": "p1.jpg", "rotation": 0, "is_key": false},
               {"file": "p2.jpg", "rotation": 90, "is_key": false},
               {"file": "key.jpg", "rotation": 0, "is_key": true}],
     "existing_test_id": null}

    ``file`` is a name inside ``pages/``, in page order; ``rotation`` is 0, 90, 180 or 270
    (clockwise); a PDF or DOCX file gives all its pages, each with the same choices.

``expected.json`` — the truth, typed from the paper (:class:`Expected`). It mirrors the app's
``TestMetadata`` and ``TestContent`` → ``Section`` → ``QuestionGroup`` → ``Question`` (data-model
§2.2-2.3), keeping only what is printed on the paper::

    {"meta": {"occasion": "FinalTerm", "grade": 8, "term": 1, "test_number": "1",
              "variant": null, "school": "…", "year": "2025-2026"},
     "sections": [
       {"printed_title": "I", "instructions": "Listen to the conversation.", "printed_points": null,
        "skill": null, "kind": "listening", "listening_range": [1, 4], "groups": []},
       {"printed_title": "IV", "instructions": "Choose the word … in the following passage.",
        "printed_points": "(1.5pts)", "skill": "reading", "kind": "questions",
        "groups": [
          {"stimulus": "In Cambodia … and (17) ____ minutes later …",
           "pictures": [],
           "questions": [
             {"printed_number": 17, "type": "mcq", "stem": null,
              "options": ["much", "more", "less", "a few"], "cue": null, "page_no": 2}]}]}],
     "answers": {"17": "D", "2": null, "7#2": "went"},
     "key": {"17": ["D"]},
     "student": {"name": "…", "class": "…"},
     "verified_by": "teacher", "verified_on": "2026-10-01"}

- ``meta``: ``occasion`` (as in the app: MidTerm, FinalTerm, …) is required; the others may be
  null.
- ``sections[]`` in paper order, with the field names of ``Section`` / ``TranscribedSection``:
  ``printed_title`` is the label as printed (``"IV"``), ``instructions`` the printed task line.
  ``kind`` has the meaning of ``TranscribedSection.kind``: ``questions``, ``listening`` (the app
  stores no listening section: give its printed ``listening_range`` ``[first, last]``; its
  questions are not compared and may be left out) or ``writing``. ``skill`` is one of the app's
  section skills (pronunciation, stress, grammar, vocabulary, communication, signs, reading,
  word_form, rewrite, writing, mixed); null = not filled in (not compared).
- Names that differ from the app: ``printed_points`` is ``TranscribedSection.points_text`` (the
  points text as printed, e.g. ``"(2.5pts)"``, or null), and ``listening_range`` is its
  ``range_first`` / ``range_last``. A picture is ``{"page_no", "note"}`` (the app stores a file
  id; the note says what the picture shows, for the teacher).
- Left out, because the app computes them: ids, canonical numbers, ``title``, ``points``,
  ``points_source``, ``graded`` (it follows from ``kind``), fingerprints, ``points_possible``.
- ``groups[]``: a ``stimulus`` (passage, letter, dialogue, dictionary entry; null when the
  questions stand alone), ``pictures`` (optional) and ``questions``. **Cloze:** the blanks are
  written ``(17) ____`` inside ``stimulus`` and those questions have ``stem: null``.
- ``questions[]``: ``type`` is one of the question types the app used before step 22.5.3 (mcq,
  true_false, gap_fill, word_form, verb_form, rewrite, combine, ordering, matching, short_answer,
  writing). The fixtures keep it; the loader maps it to the app's answer form
  (:attr:`ExpectedQuestion.answer_form`, the table ``FORM_OF_OLD_TYPE``), and a ``true_false``
  question without options gets the two options the app adds (``T. True``, ``F. False``). ``stem``,
  ``stimulus``, the ``options`` texts (without the ``A.`` label, in order) and ``cue`` use the
  app's rich text: ``**bold**``, ``<u>underline</u>``, and a blank written as ``____``.
- The old flat format (sections → questions, with ``points``) is turned into this one by
  :func:`convert_flat` (``python -m etach.eval.fixtures convert <expected.json>``): each
  section's questions become one group with ``stimulus: null``; ``points`` becomes
  ``printed_points`` text; ``skill`` and ``instructions`` are left for the teacher.
- **Question keys.** ``answers`` and ``key`` are keyed by the question key: the printed number as
  text (``"7"``); when a number is printed twice in the test (two parts both start at 1), the
  second one is ``"7#2"``, the third ``"7#3"``, counting over the non-listening sections in order.
- ``answers``: every question the student could answer → the value read from the paper
  (``"B"``, ``"T"``, ``"went"``), or ``null`` if it was left blank. Compared after ``value_norm``.
- ``key`` (optional): question key → the accepted answers, only for questions whose correct
  answer is known (from a key photo, or the teacher's own key).
- ``verdicts`` (optional, **teacher-written**, M2): question key → ``"correct"`` or
  ``"incorrect"``, the teacher's verdict on the student's answer. The grade eval derives the
  true verdicts from ``key`` + ``answers`` with the app's scoring rules; an entry here
  overrides that. It is needed for free-text answers (rewrite, combine) that do not equal an
  accepted answer: the app sends them to ``judge_rewrites``, and the rules alone give no
  verdict. ``etach eval --graph grade --keep DIR`` lists them in
  ``DIR/<set>/<name>/needs-verdict.json``.
- ``student``: ``{"name", "class"}``. **Local only**, never copied into a committed file.
- ``verified_by`` / ``verified_on``: **teacher-only**. The code never writes them; the teacher
  fills them after checking the file, then runs ``etach fixtures manifest``.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from etach.domain.llm_schemas import SectionKind, SectionSkill
from etach.domain.models import FORM_OF_OLD_TYPE, OCCASIONS, TRUE_FALSE_OPTIONS, AnswerForm
from etach.eval.metrics import SimpleGroup, SimpleQuestion, SimpleSection, question_keys

__all__ = [
    "SETS",
    "Expected",
    "ExpectedGroup",
    "ExpectedMeta",
    "ExpectedPicture",
    "ExpectedQuestion",
    "ExpectedSection",
    "ExpectedStudent",
    "Fixture",
    "FixtureError",
    "FixtureInput",
    "FixturePage",
    "convert_flat",
    "discover",
    "is_flat",
    "load_fixture",
    "manifest_lines",
    "write_manifest",
]

SETS: tuple[str, ...] = ("tuning", "heldout")


class FixtureError(ValueError):
    """A fixture folder or file that does not follow the format."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FixturePage(_Strict):
    file: str = Field(min_length=1)
    rotation: Literal[0, 90, 180, 270] = 0
    is_key: bool = False


class FixtureInput(_Strict):
    pages: list[FixturePage] = Field(min_length=1)
    existing_test_id: str | None = None


class ExpectedMeta(_Strict):
    occasion: str
    grade: int | None = None
    term: int | None = None
    test_number: str | None = None
    variant: str | None = None
    school: str | None = None
    year: str | None = None

    @model_validator(mode="after")
    def _check_occasion(self) -> ExpectedMeta:
        if self.occasion not in OCCASIONS and not self.occasion.startswith("Other:"):
            raise ValueError(f"occasion must be one of {', '.join(OCCASIONS)} or 'Other:<text>'")
        return self


#: The question types a fixture's ``type`` may hold (the app's 11 types before step 22.5.3).
OldQuestionType = Literal[
    "mcq",
    "true_false",
    "gap_fill",
    "word_form",
    "verb_form",
    "rewrite",
    "combine",
    "ordering",
    "matching",
    "short_answer",
    "writing",
]


class ExpectedQuestion(_Strict):
    printed_number: int
    type: OldQuestionType
    stem: str | None = None
    options: list[str] | None = None
    cue: str | None = None
    page_no: int | None = None

    @property
    def answer_form(self) -> AnswerForm:
        """The expected answer form (step 22.5.3): the fixture's type by ``FORM_OF_OLD_TYPE``."""
        return FORM_OF_OLD_TYPE[self.type]

    def labelled_options(self) -> list[tuple[str, str]] | None:
        """The options as the app stores them, ``(label, text)``: ``A``, ``B``, … in order; a
        ``true_false`` question without options gets the app's ``T. True`` / ``F. False``."""
        if self.type == "true_false" and not self.options:
            return list(TRUE_FALSE_OPTIONS)
        if self.options is None:
            return None
        return [(chr(ord("A") + i), text) for i, text in enumerate(self.options)]


class ExpectedPicture(_Strict):
    page_no: int
    note: str | None = None


_CLOZE_BLANK = re.compile(r"\((\d+)\)\s*_{2,}")


class ExpectedGroup(_Strict):
    stimulus: str | None = None
    pictures: list[ExpectedPicture] = []
    questions: list[ExpectedQuestion] = []

    @model_validator(mode="after")
    def _check_cloze(self) -> ExpectedGroup:
        blanks = {int(n) for n in _CLOZE_BLANK.findall(self.stimulus or "")}
        bad = [q.printed_number for q in self.questions if q.printed_number in blanks and q.stem]
        if bad:
            raise ValueError(
                f"questions {', '.join(map(str, bad))} have their blank in the stimulus "
                "(cloze): their stem must be null"
            )
        return self


class ExpectedSection(_Strict):
    printed_title: str
    instructions: str | None = None
    printed_points: str | None = None
    skill: SectionSkill | None = None
    kind: SectionKind = "questions"
    listening_range: tuple[int, int] | None = None
    groups: list[ExpectedGroup] = []

    @property
    def questions(self) -> list[ExpectedQuestion]:
        return [q for g in self.groups for q in g.questions]

    @model_validator(mode="after")
    def _check_kind(self) -> ExpectedSection:
        if self.listening_range is not None:
            if self.kind != "listening":
                raise ValueError("listening_range is only for a listening section")
            first, last = self.listening_range
            if first > last:
                raise ValueError("listening_range: first is after last")
        return self


class ExpectedStudent(_Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str | None = None
    class_name: str | None = Field(default=None, alias="class")


class Expected(_Strict):
    meta: ExpectedMeta
    sections: list[ExpectedSection] = Field(min_length=1)
    answers: dict[str, str | None]
    key: dict[str, list[str]] | None = None
    verdicts: dict[str, Literal["correct", "incorrect"]] | None = None
    student: ExpectedStudent | None = None
    verified_by: str | None = None
    verified_on: date | None = None

    def stored_sections(self) -> list[SimpleSection]:
        """The sections the app stores (not listening), in the metrics' shape."""
        return [
            SimpleSection(
                printed_title=s.printed_title,
                skill=s.skill,
                groups=[
                    SimpleGroup(
                        stimulus=g.stimulus,
                        questions=[
                            SimpleQuestion(
                                printed_number=q.printed_number,
                                answer_form=q.answer_form,
                                stem=q.stem,
                                options=None
                                if (labelled := q.labelled_options()) is None
                                else [text for _, text in labelled],
                                cue=q.cue,
                                page_no=q.page_no,
                            )
                            for q in g.questions
                        ],
                    )
                    for g in s.groups
                ],
                graded=s.kind != "writing",
            )
            for s in self.sections
            if s.kind != "listening"
        ]

    def question_keys(self) -> list[str]:
        return question_keys(q.printed_number for s in self.stored_sections() for q in s.questions)

    @model_validator(mode="after")
    def _check_keys(self) -> Expected:
        known = set(self.question_keys())
        for name, mapping in (
            ("answers", self.answers),
            ("key", self.key or {}),
            ("verdicts", self.verdicts or {}),
        ):
            unknown = sorted(set(mapping) - known)
            if unknown:
                raise ValueError(
                    f"{name}: no (non-listening) question with key {', '.join(unknown)}"
                )
        return self


@dataclass(frozen=True)
class Fixture:
    set: str
    name: str
    folder: Path
    input: FixtureInput
    expected: Expected

    @property
    def pages_dir(self) -> Path:
        return self.folder / "pages"

    @property
    def has_key_photo(self) -> bool:
        return any(p.is_key for p in self.input.pages)


def _load_json[M: BaseModel](path: Path, model: type[M]) -> M:
    if not path.is_file():
        raise FixtureError(f"{path}: missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FixtureError(f"{path}: not readable JSON ({exc})") from exc
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise FixtureError(f"{path}: {exc}") from exc


def is_flat(data: Any) -> bool:
    """True for the old flat ``expected.json`` (sections with ``questions``, no ``groups``)."""
    sections = data.get("sections") if isinstance(data, dict) else None
    return isinstance(sections, list) and any(
        isinstance(s, dict) and "questions" in s and "groups" not in s for s in sections
    )


def _points_text(points: Any) -> str | None:
    if points is None:
        return None
    return f"{points:g}" if isinstance(points, int | float) else str(points)


_FLAT_FIELDS = {"printed_title", "instructions", "points", "skill", "kind", "questions"}


def convert_flat(data: dict[str, Any]) -> dict[str, Any]:
    """The old flat format -> the nested one. Every value is kept: ``kind`` stays ``kind``,
    ``points`` becomes ``printed_points`` (as text), and each section's ``questions`` become one
    group with ``stimulus: null``. ``skill`` / ``instructions`` are left null for the teacher.
    A file already nested is returned unchanged (a copy)."""
    out: dict[str, Any] = json.loads(json.dumps(data))
    if not is_flat(out):
        return out
    sections = []
    for old in out["sections"]:
        if "groups" in old:
            sections.append(old)
            continue
        new: dict[str, Any] = {
            "printed_title": old.get("printed_title", ""),
            "instructions": old.get("instructions"),
            "printed_points": _points_text(old.get("points")),
            "skill": old.get("skill"),
            "kind": old.get("kind", "questions"),
        }
        questions = old.get("questions") or []
        new["groups"] = (
            [{"stimulus": None, "pictures": [], "questions": questions}] if questions else []
        )
        for name in sorted(set(old) - _FLAT_FIELDS):  # kept, so validation reports them
            new[name] = old[name]
        sections.append(new)
    out["sections"] = sections
    return out


def load_fixture(folder: Path, set_name: str | None = None) -> Fixture:
    """Load and validate ``input.json`` + ``expected.json``; every page file must exist."""
    folder = Path(folder)
    inp = _load_json(folder / "input.json", FixtureInput)
    try:
        flat = is_flat(json.loads((folder / "expected.json").read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        flat = False
    if flat:
        raise FixtureError(
            f"{folder / 'expected.json'}: the old flat format (sections -> questions); convert "
            "it with `python -m etach.eval.fixtures convert <expected.json>`"
        )
    expected = _load_json(folder / "expected.json", Expected)
    for page in inp.pages:
        if not (folder / "pages" / page.file).is_file():
            raise FixtureError(f"{folder}: pages/{page.file} is missing")
    return Fixture(
        set=set_name or folder.parent.name,
        name=folder.name,
        folder=folder,
        input=inp,
        expected=expected,
    )


def discover(root: Path, set_name: str) -> list[Fixture]:
    """The fixtures of one set under ``root`` (``root/<set>/<name>/``), sorted by name."""
    if set_name not in SETS:
        raise FixtureError(f"unknown set {set_name!r} (one of {', '.join(SETS)})")
    base = Path(root) / set_name
    if not base.is_dir():
        return []
    return [
        load_fixture(d, set_name)
        for d in sorted(base.iterdir())
        if d.is_dir() and not d.name.startswith(("_", "."))
    ]


# --- MANIFEST.sha256 -------------------------------------------------------------------------

MANIFEST_NAME = "MANIFEST.sha256"


def manifest_lines(root: Path) -> list[str]:
    """``<sha256 of expected.json>  <set>/<name>/expected.json  verified_by: <value or ->``,
    sorted by path. ``verified_by`` is read as the teacher wrote it; nothing is validated here
    beyond JSON, so an unsigned or half-written fixture still gets a line."""
    import hashlib

    lines = []
    for set_name in SETS:
        base = Path(root) / set_name
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            path = d / "expected.json"
            if d.name.startswith(("_", ".")) or not path.is_file():
                continue
            data = path.read_bytes()
            try:
                who = json.loads(data.decode("utf-8")).get("verified_by")
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                who = None
            digest = hashlib.sha256(data).hexdigest()
            lines.append(f"{digest}  {set_name}/{d.name}/expected.json  verified_by: {who or '-'}")
    return sorted(lines, key=lambda line: line.split("  ")[1])


def write_manifest(root: Path) -> Path:
    """Write ``<root>/MANIFEST.sha256`` (LF line ends). The teacher commits it."""
    out = Path(root) / MANIFEST_NAME
    lines = manifest_lines(root)
    out.write_bytes(("".join(line + "\n" for line in lines)).encode("utf-8"))
    return out


def _main(argv: list[str]) -> int:
    """``python -m etach.eval.fixtures convert PATH``: rewrite a flat expected.json in place."""
    if len(argv) != 2 or argv[0] != "convert":
        print("usage: python -m etach.eval.fixtures convert <expected.json>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    new = convert_flat(json.loads(path.read_text(encoding="utf-8")))
    try:
        Expected.model_validate(new)
    except ValidationError as exc:
        print(f"{path}: converted, but not valid yet:\n{exc}", file=sys.stderr)
    path.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
