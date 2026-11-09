"""Step 22.3.6 (decision D6, data-model v1.16): ``Question.answer_start``.

R22.3.6.2: content JSON, the test text (``   Start: …``), the DOCX and the key forms.
R22.3.6.3: the two page prompts ask for it on rewrite/combine only; the match key ignores prompts.
"""

from __future__ import annotations

from datetime import UTC, datetime

from etach.domain import docx_export, keys
from etach.domain import models as m
from etach.domain import test_text as tt
from etach.domain.llm_schemas import TranscribeOut
from etach.domain.points import equal_points
from etach.llm.cassettes import match_key
from etach.llm.tasks import TASKS, extraction_inputs
from etach.prompts.render import FilePromptProvider

KEY = "My brother used to stay up late playing mobile games."
FOUR = [
    "My brother used to stay up late playing mobile games.",
    "My brother used to stay up late playing mobile games",
    "used to stay up late playing mobile games.",
    "used to stay up late playing mobile games",
]


def q(start: str | None = "My brother", stem: str = "He stayed up late. (used to)") -> m.Question:
    return m.Question(
        id="q-1", number=1, printed_number=37, page_no=1, answer_form="sentence", stem=stem,
        options=None, cue=None, points=0.5, answer_start=start,
    )  # fmt: skip


def content(question: m.Question) -> m.TestContent:
    group = m.QuestionGroup(id="g-1", stimulus=None, pictures=[], questions=[question])
    section = m.Section(
        id="s-1", number=1, printed_title="VI", title="VI", instructions="Rewrite.",
        points=0.5, points_source="printed", skill="rewrite", groups=[group],
    )  # fmt: skip
    return m.TestContent(sections=[section])


# --- content JSON ------------------------------------------------------------------------------


def test_json_round_trip_and_old_content_loads() -> None:
    c = content(q())
    assert m.TestContent.model_validate(c.model_dump(mode="json")) == c
    old = c.model_dump(mode="json")
    del old["sections"][0]["groups"][0]["questions"][0]["answer_start"]
    assert m.TestContent.model_validate(old).sections[0].groups[0].questions[0].answer_start is None


# --- test text ---------------------------------------------------------------------------------


def test_text_renders_and_reads_the_start_line() -> None:
    c = content(q())
    text = tt.render(c)
    assert "   Start: My brother" in text.splitlines()
    result = tt.read(text, c)
    assert result.errors == [] and result.content == equal_points(c)


def test_text_typed_start_line_is_read_without_previous() -> None:
    text = "VI.  [0.5 points]\nRewrite.\n37. He often stayed up late.\n   start: My sister\n"
    result = tt.read(text)
    assert result.errors == []
    assert result.content is not None
    assert result.content.sections[0].groups[0].questions[0].answer_start == "My sister"


def test_text_start_without_a_question_is_an_error() -> None:
    result = tt.read("VI.  [0.5 points]\nRewrite.\nStart: My brother\n")
    assert result.content is None
    assert any("“Start:” must come under a question" in e.message for e in result.errors)


def test_text_a_stem_line_that_looks_like_start_is_escaped() -> None:
    c = content(q(start=None, stem="Rewrite the sentence.\nStart: here"))
    text = tt.render(c)
    assert "\\Start: here" in text
    result = tt.read(text, c)
    assert result.errors == [] and result.content == equal_points(c)


# --- DOCX --------------------------------------------------------------------------------------


def test_docx_prints_the_answer_line_with_its_opening() -> None:
    now = datetime(2026, 10, 18, tzinfo=UTC)
    t = m.Test(
        id="t-1", meta=m.TestMetadata(occasion="FinalTerm"), content=content(q()),
        content_schema_version=1, fingerprint="f", points_possible=0.5, source_run_id=None,
        merged_into=None, created_at=now, updated_at=now,
    )  # fmt: skip
    lines = [p.text for p in docx_export.test_document(t).paragraphs]
    assert "My brother ____" in lines


# --- key forms ---------------------------------------------------------------------------------


def test_answer_start_gives_the_four_forms_first() -> None:
    question = q()
    assert keys.given_words(question)[0] == "My brother"
    assert keys.with_forms([KEY], question) == FOUR


def test_no_answer_start_keeps_the_older_sources() -> None:
    question = q(start=None, stem="He often stayed up late.\nMy brother ……")
    assert keys.with_forms([KEY], question) == FOUR


# --- prompts and match keys (R22.3.6.3) ----------------------------------------------------------


def test_both_page_prompts_ask_for_answer_start_on_sentence_only() -> None:
    provider = FilePromptProvider()
    for task in ("transcribe_page", "structure_text_page"):
        text = provider.base_text(task)
        rule = next(line for line in text.splitlines() if line.startswith("- `answer_start`"))
        assert "`sentence`" in rule
        assert "null for every other question" in text


def test_structure_text_page_renders_with_the_document() -> None:
    spec = TASKS["structure_text_page"]
    inputs = extraction_inputs("structure_text_page", page_no=2, photo_count=3, document="TYPED")
    prompt = FilePromptProvider().render("structure_text_page", spec.profile(None), inputs)
    assert prompt.document == "TYPED"
    assert spec.role == "reasoning" and spec.schema() is TranscribeOut


def test_match_key_ignores_the_prompt_text() -> None:
    inputs = extraction_inputs("structure_text_page", page_no=1, photo_count=1, document="A")
    other = extraction_inputs("structure_text_page", page_no=1, photo_count=1, document="B")
    a = match_key("structure_text_page", "TranscribeOut", inputs)
    assert a == match_key("structure_text_page", "TranscribeOut", other)
    assert a.split(":", 1)[1] == match_key("transcribe_page", "TranscribeOut", inputs).split(":")[1]
