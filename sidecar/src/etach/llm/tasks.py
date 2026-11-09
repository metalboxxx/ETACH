"""Per-task call settings (llm-design §3.2, §4, §8; plan step 8.2; step 17.2 adds grading).

``TASKS[task]`` is a :class:`TaskSpec`: the role, the output schema (fixed, or built per call),
the profile policy, ``think`` and ``num_predict``. A graph node calls::

    spec = TASKS["read_answers_page"]
    inputs = extraction_inputs("read_answers_page", page_no=2, photo_count=3,
                               questions=questions, draft_page_count=3)
    await client.call(spec.role, spec.task, inputs, spec.schema(questions),
                      profile=spec.profile(exam_format), think=spec.think,
                      num_predict=spec.num_predict, step_id=..., images=[...])

``extraction_inputs`` uses the cassette match-key names (``page_no``, ``question_ids``,
``section_id``; :data:`etach.llm.cassettes.MATCH_INPUT_KEYS`) for those inputs.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib import resources
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from etach.domain.llm_schemas import (
    AiKeyOut,
    ExplainOut,
    JudgeOut,
    QuestionLevel,
    ReadHeaderOut,
    ReadKeyOut,
    RereadPiecesOut,
    SummaryOut,
    TranscribeOut,
    VerifyKeyOut,
    read_answers_schema,
    tag_skills_schema,
)
from etach.domain.models import Question
from etach.llm.adapters import PlainText
from etach.llm.config import Role

__all__ = [
    "EXTRACTION_NUM_PREDICT",
    "EXTRACTION_TASKS",
    "GENERIC_PROFILE",
    "GRADING_NUM_PREDICT",
    "GRADING_ROLES",
    "GRADING_TASKS",
    "GRADING_THINK",
    "MAX_TAGS_PER_QUESTION",
    "PHOTO_RULES",
    "TAG_SKILLS_SCHEMA",
    "TASKS",
    "TAXONOMY_FILES",
    "ProfilePolicy",
    "SchemaBuilder",
    "TaskSpec",
    "extraction_inputs",
    "parse_skill_lines",
    "question_list_text",
    "skill_list_text",
    "taxonomy_ids",
    "taxonomy_skills",
    "taxonomy_text",
]

GENERIC_PROFILE = "generic"

ProfilePolicy = Literal["generic", "exam_format"]
SchemaBuilder = Callable[[Sequence[Question]], type[BaseModel]]


@dataclass(frozen=True)
class TaskSpec:
    task: str
    role: Role
    #: a fixed output schema, or a builder called with the question list (per-call schema)
    schema_or_builder: type[BaseModel] | SchemaBuilder
    #: ``generic`` always, or the test's ``exam_format`` falling back to generic
    profile_policy: ProfilePolicy
    think: bool
    #: the output-token cap; ``None`` = the model's default
    num_predict: int | None = None

    @property
    def per_call_schema(self) -> bool:
        return not isinstance(self.schema_or_builder, type)

    def schema(self, questions: Sequence[Question] | None = None) -> type[BaseModel]:
        if isinstance(self.schema_or_builder, type):
            return self.schema_or_builder
        if questions is None:
            raise ValueError(f"{self.task}: the schema is built per call; pass the questions")
        return self.schema_or_builder(questions)

    def profile(self, exam_format: str | None = None) -> str:
        """The profile name to render with (the provider falls back to generic if no file)."""
        if self.profile_policy == "generic" or not exam_format:
            return GENERIC_PROFILE
        return exam_format


#: The ``photo_rules`` input of a photo page's ``structure_text_page`` call (step 22.6.1): put
#: after the last rule line of ``base/structure_text_page.md``; the renderer replaces the marker
#: with ``examples/photo_rules.md`` after the placeholders are filled.
PHOTO_RULES = "\n<!-- example: photo_rules -->"

#: Output-token caps (``num_predict``) that stop repetition loops. A call that hits its cap ends
#: truncated (invalid JSON): the client retries once, then fails into llm-design §5.1.
#: M1 tunes these values. ``transcribe_page`` (also used by ``retranscribe_tiles``) is 8192: a
#: text-only page of up to ``MAX_TEXT_PAGE_CHARS`` plus this cap still fits ``num_ctx`` 16384
#: (M1 ``baseline2``: 4096 cut a long DOCX page off mid-JSON).
EXTRACTION_NUM_PREDICT: dict[str, int] = {
    "read_header": 512,
    "read_key_pages": 1024,
    "read_answers_page": 2048,
    "transcribe_page": 8192,
    "structure_text_page": 8192,
    "reread_pieces": 2048,
    "ocr_page": 4096,
    "ocr_format_page": 4096,
}

EXTRACTION_TASKS: tuple[TaskSpec, ...] = (
    TaskSpec(
        "read_key_pages",
        "vision",
        ReadKeyOut,
        "exam_format",
        think=False,
        num_predict=EXTRACTION_NUM_PREDICT["read_key_pages"],
    ),
    TaskSpec(
        "read_header",
        "vision",
        ReadHeaderOut,
        "exam_format",
        think=False,
        num_predict=EXTRACTION_NUM_PREDICT["read_header"],
    ),
    # the format is not known until the header is read (llm-design §4)
    TaskSpec(
        "transcribe_page",
        "vision",
        TranscribeOut,
        "generic",
        think=False,
        num_predict=EXTRACTION_NUM_PREDICT["transcribe_page"],
    ),
    # a born-digital page's exact text, structured by the reasoning role (D5, llm-design v4.32);
    # the same output schema as transcribe_page
    TaskSpec(
        "structure_text_page",
        "reasoning",
        TranscribeOut,
        "generic",
        think=False,
        num_predict=EXTRACTION_NUM_PREDICT["structure_text_page"],
    ),
    TaskSpec(
        "read_answers_page",
        "vision",
        read_answers_schema,
        "exam_format",
        think=False,
        num_predict=EXTRACTION_NUM_PREDICT["read_answers_page"],
    ),
    # step 22.5.7: the targeted re-read of a failing page's broken or missing questions
    TaskSpec(
        "reread_pieces",
        "extraction_check",
        RereadPiecesOut,
        "generic",
        think=False,
        num_predict=EXTRACTION_NUM_PREDICT["reread_pieces"],
    ),
    # step 22.5.7 (D13): a photo page as plain text ([extract] photo_reader = "ocr"); the text
    # then goes to structure_text_page
    TaskSpec(
        "ocr_page",
        "ocr",
        PlainText,
        "generic",
        think=False,
        num_predict=EXTRACTION_NUM_PREDICT["ocr_page"],
    ),
    # step 22.6.5 (D7, way 2a; [extract] photo_structure = "ocr_format"): a photo page written
    # by GLM-OCR in the app's test-text format, read by code (test_text.read_ocr_page)
    TaskSpec(
        "ocr_format_page",
        "ocr",
        PlainText,
        "generic",
        think=False,
        num_predict=EXTRACTION_NUM_PREDICT["ocr_format_page"],
    ),
)

# --- grading (step 17.2; llm-design §5) ------------------------------------------------------

#: ``prompts/taxonomy/<file>``: the grammar taxonomy (copied byte-for-byte from EnglishTest_Tutor)
#: and the section skills. A skill line is ``ID | name | …``; the IDs are what ``tag_skills`` may
#: return (R17.2.3).
TAXONOMY_FILES: tuple[str, ...] = ("grammar.txt", "sections.txt")
_SKILL_LINE = re.compile(r"^([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)[ \t]+\|(.*)$", re.MULTILINE)


def taxonomy_text(name: str) -> str:
    """One taxonomy file from the packaged ``etach/prompts/taxonomy`` folder (CRLF → LF)."""
    entry = resources.files("etach.prompts").joinpath("taxonomy").joinpath(name)
    return entry.read_text(encoding="utf-8").replace("\r\n", "\n")


def parse_skill_lines(text: str) -> list[tuple[str, str]]:
    """``(id, rest of the line)`` for every ``ID | …`` line, in file order."""
    return [(m.group(1), m.group(2).strip()) for m in _SKILL_LINE.finditer(text)]


def taxonomy_skills() -> list[tuple[str, str]]:
    """Every skill of the two taxonomy files, grammar first: ``(id, "name | …")``."""
    return [skill for name in TAXONOMY_FILES for skill in parse_skill_lines(taxonomy_text(name))]


def taxonomy_ids() -> list[str]:
    """The allowed ``tag_skills`` IDs: exactly the IDs parsed from the two files (R17.2.3)."""
    return list(dict.fromkeys(skill_id for skill_id, _ in taxonomy_skills()))


def skill_list_text() -> str:
    """The ``{{skill_list}}`` input of ``tag_skills``: one ``ID | name | …`` line per skill."""
    return "\n".join(f"{skill_id} | {rest}" for skill_id, rest in taxonomy_skills())


#: At most this many skill tags per question (the prompt asks for 1-3; step 18 caps the schema).
MAX_TAGS_PER_QUESTION = 3


def _capped_tag_skills_schema(allowed_tags: Sequence[str]) -> type[BaseModel]:
    """``tag_skills_schema(allowed_tags)`` with each question's tags capped at
    :data:`MAX_TAGS_PER_QUESTION` (same class names, so cassette match keys are unchanged)."""
    tag_skills_schema(allowed_tags)  # validates ``allowed_tags`` the same way
    tag_type: Any = Literal[tuple(dict.fromkeys(allowed_tags))]
    item = create_model(
        "QuestionTagsCall",
        __config__=ConfigDict(extra="forbid"),
        question_id=(str, ...),
        tags=(list[tag_type], Field(min_length=1, max_length=MAX_TAGS_PER_QUESTION)),
        level=(QuestionLevel, ...),
    )
    return create_model(
        "TagSkillsCall",
        __config__=ConfigDict(extra="forbid"),
        items=(list[item], ...),  # type: ignore[valid-type]
    )


#: ``tag_skills``'s output schema: ``TagSkillsOut`` with the tags limited to ``taxonomy_ids()``
#: and at most 3 per question.
TAG_SKILLS_SCHEMA: type[BaseModel] = _capped_tag_skills_schema(taxonomy_ids())

#: Output-token caps of the grading tasks (llm-design §3.1, §5). M1 tunes these values; the
#: ``judge_rewrites`` cap was sized when that task thought. ``verify_key`` is 1000 (step 22.6.3,
#: D6; was 1500): its prompt says to answer ``?`` rather than run out.
GRADING_NUM_PREDICT: dict[str, int] = {
    "ai_key_fast": 1024,
    "verify_key": 1000,
    "tag_skills": 2048,
    "judge_rewrites": 400,
    "explain": 512,
    "weak_points_summary": 1024,
}

#: Grading tasks that think: none (R17.2.4; thinking off for every task since llm-design v4.17).
GRADING_THINK: frozenset[str] = frozenset()

_GRADING_SCHEMAS: dict[str, type[BaseModel]] = {
    "ai_key_fast": AiKeyOut,
    "verify_key": VerifyKeyOut,
    "tag_skills": TAG_SKILLS_SCHEMA,
    "judge_rewrites": JudgeOut,
    "explain": ExplainOut,
    "weak_points_summary": SummaryOut,
}

#: The grading calls use the reasoning role, except ``verify_key``, which uses ``grading_check``
#: (step 22.5.4), all with the ``chat`` adapter and the test's ``exam_format``
#: profile, falling back to generic (llm-design §8). Prompt placeholders (step 18 fills them):
#:
#: - ``ai_key_fast``: ``section_id``, ``section_text``, ``key_questions`` (the IDs needing a key,
#:   comma-separated; also send ``question_ids``);
#: - ``verify_key``: ``question_id``, ``question_text`` (no key: it solves independently);
#: - ``tag_skills`` (one call per graded section): ``section_id``, ``question_ids``,
#:   ``skill_list`` (= :func:`skill_list_text`), ``section_text`` (heading, instructions,
#:   passage and questions);
#: - ``judge_rewrites``: ``question_text``, ``accepted``, ``student_answer``;
#: - ``explain``: ``question_text``, ``accepted``, ``student_answer``, ``skill_tags``;
#: - ``weak_points_summary``: ``score_text``, ``weak_points``, ``wrong_answers``.
#: The grading tasks whose role is not ``reasoning``.
GRADING_ROLES: dict[str, Role] = {"verify_key": "grading_check"}

GRADING_TASKS: tuple[TaskSpec, ...] = tuple(
    TaskSpec(
        task,
        GRADING_ROLES.get(task, "reasoning"),
        schema,
        "exam_format",
        think=task in GRADING_THINK,
        num_predict=GRADING_NUM_PREDICT[task],
    )
    for task, schema in _GRADING_SCHEMAS.items()
)

TASKS: dict[str, TaskSpec] = {spec.task: spec for spec in (*EXTRACTION_TASKS, *GRADING_TASKS)}


# --- inputs ----------------------------------------------------------------------------------


def _readable(questions: Sequence[Question]) -> list[Question]:
    """The questions that are read (writing is not read, PRD D12; same as the schema)."""
    return [q for q in questions if q.answer_form != "writing"]


def question_list_text(questions: Sequence[Question], *, page_hints: bool) -> str:
    """One line per readable question: ID, printed number, answer form, options, page hint."""
    lines: list[str] = []
    for q in _readable(questions):
        parts = [f"- {q.id}: no. {q.printed_number}", q.answer_form]
        if q.options:
            parts.append("options " + "; ".join(f"{o.label}. {o.text}" for o in q.options))
        if page_hints:
            parts.append(f"printed on page {q.page_no}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def extraction_inputs(
    task: str,
    *,
    page_no: int | None = None,
    photo_count: int | None = None,
    questions: Sequence[Question] | None = None,
    draft_page_count: int | None = None,
    section_id: str | None = None,
    document: str | None = None,
    previous_unit: str | None = None,
    pieces: str | None = None,
    ocr_prompt: str | None = None,
    photo: bool = False,
) -> dict[str, Any]:
    """The ``inputs`` dict for an extraction call.

    - ``page_no``: this photo's position (1-based); ``photo_count``: photos in this call's set
      (the key photos for ``read_key_pages``);
    - ``read_answers_page`` needs ``questions`` (the full list) and sends ``question_ids``;
      page hints are added only when ``photo_count == draft_page_count`` (llm-design §4);
    - ``document``: the page's text layer (PDF/DOCX), sent as the document;
    - ``transcribe_page`` always sends ``previous_page``: empty, or (step 22.5.7) the last open
      unit of the page before, as already read (``renumber.open_unit``), with a lead-in line;
    - ``reread_pieces`` (step 22.5.7) needs ``pieces``: the questions to read again, as text
      (``renumber.reread_text``);
    - ``ocr_page`` (step 22.5.7) needs ``ocr_prompt`` (``[extract] ocr_prompt``).
    - ``ocr_format_page`` (step 22.6.5, way 2a) needs ``page_no`` only: its prompt file is the
      whole user message (the test-text format and one example).
    - ``structure_text_page`` always sends ``photo_rules``: empty for a typed page (so its prompt
      renders as before), or, with ``photo=True`` (GLM-OCR's text of a photo, step 22.6.1), the
      line that the renderer replaces with ``examples/photo_rules.md``.
    """
    if task not in EXTRACTION_NUM_PREDICT:
        raise KeyError(f"unknown extraction task {task!r}")
    inputs: dict[str, Any] = {}

    def need(name: str, value: Any) -> Any:
        if value is None:
            raise ValueError(f"{task}: {name} is required")
        return value

    if task == "read_key_pages":
        inputs["page_count"] = need("photo_count", photo_count)
    elif task == "read_header":
        inputs["page_no"] = page_no if page_no is not None else 1
    elif task in ("transcribe_page", "structure_text_page"):
        inputs["page_no"] = need("page_no", page_no)
        inputs["page_count"] = need("photo_count", photo_count)
        if task == "transcribe_page":
            inputs["previous_page"] = (
                f"\n\nThe previous page ended inside this unit:\n{previous_unit}"
                if previous_unit
                else ""
            )
        else:
            inputs["photo_rules"] = PHOTO_RULES if photo else ""
    elif task == "reread_pieces":
        inputs["page_no"] = need("page_no", page_no)
        inputs["page_count"] = need("photo_count", photo_count)
        inputs["pieces"] = need("pieces", pieces)
    elif task == "ocr_page":
        inputs["page_no"] = need("page_no", page_no)
        inputs["ocr_prompt"] = need("ocr_prompt", ocr_prompt)
    elif task == "ocr_format_page":
        inputs["page_no"] = need("page_no", page_no)
    elif task == "read_answers_page":
        qs = need("questions", questions)
        inputs["page_no"] = need("page_no", page_no)
        inputs["page_count"] = need("photo_count", photo_count)
        inputs["question_ids"] = [q.id for q in _readable(qs)]
        hints = draft_page_count is not None and photo_count == draft_page_count
        inputs["question_list"] = question_list_text(qs, page_hints=hints)
    if section_id is not None:
        inputs["section_id"] = section_id
    if document is not None:
        inputs["document"] = document
    return inputs
