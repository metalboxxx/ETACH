"""Step 22.4.7: one worked example in ``structure_text_page`` (typed files only).

R22.4.7.1: the example's output validates against ``TranscribeOut`` (the ``format`` schema of
the task), the prompt renders with it, and its made-up words occur nowhere in ``fixtures/`` or
the cassettes. R22.4.7.2: the longest system prompt + the longest text page + ``num_predict``
fits ``num_ctx`` by the client's own size estimate (the upper bound), and the example is under
1,500 tokens by the same estimate. R22.4.7.5: after the teacher's GPU check the photo prompt
``transcribe_page`` is back to its 0.4.0 text (commit c5caa1d), with no example and no rules.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from etach.domain.llm_schemas import TranscribeOut
from etach.llm.adapters import build_request
from etach.llm.client import MIN_CHARS_PER_TOKEN, prompt_size
from etach.llm.config import default_config
from etach.llm.tasks import EXTRACTION_TASKS, PHOTO_RULES
from etach.prompts.render import USER_MARKER, FilePromptProvider, PromptNotFound
from etach.store.documents import MAX_TEXT_PAGE_CHARS

TASK = "structure_text_page"
PHOTO_TASK = "transcribe_page"
#: sha256 of ``base/transcribe_page.md`` (LF line ends): its text before step 22.4.7
#: (commit c5caa1d) with only the step 22.5.3 answer-form part changed; step 22.4.7 left it
#: alone; step 22.5.7 added the two page-break lines and the ``{{previous_page}}`` input
PHOTO_PROMPT_SHA256 = "8794ee36689194661f7516ab17f4f6e8dcb0d4fce2cad596cd0d3cba338f39d5"
SIDECAR = Path(__file__).resolve().parents[3]
REPO = SIDECAR.parent
CASSETTES = SIDECAR / "tests" / "cassettes"
FIXTURES = REPO / "fixtures"
#: words invented for the example; none may come from a real paper
MADE_UP_WORDS = ("glimber", "glimbers", "glimbered", "Brindo", "Todd")
_PAGE_START = "Example page:\n"
_OUTPUT_START = "Its correct output:\n"
_END = "End of the example."
_TEXT_SUFFIXES = {".json", ".md", ".txt", ".csv", ".log"}


def _example() -> str:
    return FilePromptProvider().example_text("page_example")


def _page() -> str:
    text = _example()
    return text[text.index(_PAGE_START) + len(_PAGE_START) : text.index(_OUTPUT_START)].strip()


def _output() -> TranscribeOut:
    text = _example()
    raw = text[text.index(_OUTPUT_START) + len(_OUTPUT_START) : text.index(_END)]
    return TranscribeOut.model_validate_json(raw)


# --- R22.4.7.1: the example's form ------------------------------------------------------------


def test_example_output_validates_against_the_page_schema() -> None:
    spec = next(s for s in EXTRACTION_TASKS if s.task == TASK)
    assert spec.schema() is TranscribeOut
    out = _output()
    assert [s.printed_title for s in out.sections] == ["VI", "VII"]


def test_example_shows_the_checklist_cases() -> None:
    page = _page()
    vi, vii = _output().sections
    # a heading with printed points and a Vietnamese instruction line kept in the instructions
    assert vi.points_text == "(0.5 pt)" and "Thí sinh" in vi.instructions
    assert vi.skill == "vocabulary"
    # a dictionary entry as the stimulus; the two gap sentences each keep their own stem
    (entry,) = vi.groups
    assert entry.stimulus is not None and entry.stimulus.startswith("glimber (verb)")
    assert "\n• " in entry.stimulus
    assert [q.printed_number for q in entry.questions] == [33, 34]
    for q in entry.questions:
        assert q.answer_form == "word" and q.stem and q.stem not in entry.stimulus
        assert q.answer_start is None
    # "VII. Rewrite …" starts a new section with no blank line before it
    assert "\nVII. Rewrite" in page and "\n\nVII." not in page
    assert vii.skill == "rewrite" and vii.points_text == "(1.5 pts)"
    assert "Chú ý:" in vii.instructions and "Từ câu 35 đến câu 37" in vii.instructions
    (group,) = vii.groups
    assert group.stimulus is None
    rewrites = group.questions
    assert [q.printed_number for q in rewrites] == [35, 36, 37]
    assert all(q.answer_form == "sentence" and q.stem and q.answer_start for q in rewrites)
    # one with a cue word in brackets, one with "=>", one with opening words and no arrow
    assert rewrites[0].cue == "SINCE" and f"({rewrites[0].cue})" in page
    assert f"=> {rewrites[1].answer_start} " in page
    assert f"\n{rewrites[2].answer_start} …" in page


def test_example_output_copies_the_example_page() -> None:
    page = _page()
    for section in _output().sections:
        assert f"{section.printed_title}. " in page
        for line in section.instructions.split("\n"):
            assert line in page
        for group in section.groups:
            for line in (group.stimulus or "").split("\n"):
                assert line in page
            for q in group.questions:
                assert f"{q.printed_number}. {q.stem}" in page


def test_example_is_marked_as_form_only() -> None:
    assert "example of form only: do not copy its words" in _example()


def test_text_prompt_renders_with_the_example_before_the_page() -> None:
    provider = FilePromptProvider()
    assert "<!-- example: page_example -->" in provider.base_text(TASK).split(USER_MARKER)[0]
    prompt = provider.render(
        TASK, "generic", {"page_no": 1, "page_count": 2, "document": "x", "photo_rules": ""}
    )
    # the example sits in the system prompt; the page's own text or photo is in the user message
    assert _example() in prompt.system
    assert "<!-- example:" not in prompt.system
    assert "glimber" not in prompt.user_text
    assert prompt.user_text.startswith("This is page 1 of 2.")


def test_text_prompt_carries_the_three_structure_rules() -> None:
    text = " ".join(FilePromptProvider().base_text(TASK).split())
    assert "own printed sentence is its `stem`" in text
    assert "Never put it into a `stimulus`; only the numbered gaps of a passage go there." in text
    assert 'A Roman-numeral heading ("VII. Rewrite …") always starts a new section' in text
    assert '"Thí sinh …", "Chú ý: …", "Từ câu … đến câu …"' in text
    assert "An instruction line is never a section." in text
    assert '"=> It was such ……" → "It was such"' in text  # step 22.5.6


# --- R22.4.7.5: the photo prompt is back to its 0.4.0 text --------------------------------------


def test_photo_prompt_is_its_text_before_step_22_4_7() -> None:
    text = FilePromptProvider().base_text(PHOTO_TASK)
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == PHOTO_PROMPT_SHA256


def test_photo_prompt_has_no_example_and_no_structure_rules() -> None:
    provider = FilePromptProvider()
    base = provider.base_text(PHOTO_TASK)
    assert "<!-- example:" not in base
    assert "Three structure rules" not in base
    assert "Roman-numeral heading" not in base
    assert "An instruction line is never a section." not in base
    assert '"=> It was such ……"' not in base
    assert "without the dots or blank" in base
    prompt = provider.render(
        PHOTO_TASK, "generic", {"page_no": 1, "page_count": 2, "previous_page": ""}
    )
    assert "glimber" not in prompt.system and _example() not in prompt.system


# --- R22.4.7.1: made up, not taken from the teacher's papers ----------------------------------


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
        if value.lstrip().startswith(("{", "[")):
            with contextlib.suppress(ValueError):
                yield from _strings(json.loads(value))
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _texts(root: Path) -> Iterator[tuple[Path, str]]:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix.lower() == ".json":
            with contextlib.suppress(ValueError):
                raw = "\n".join([raw, *_strings(json.loads(raw))])
        yield path, unicodedata.normalize("NFC", raw).casefold()


def _probes() -> list[str]:
    """The example page's lines without their numbers, arrows and dots."""
    probes = []
    for line in _page().split("\n"):
        line = re.sub(r"^(\d+\.|=>|→|•|\d)\s*", "", line).replace("…", "").strip()
        if len(line) >= 15:
            probes.append(unicodedata.normalize("NFC", line).casefold())
    return probes


def _assert_not_in(root: Path) -> None:
    words = [re.compile(rf"\b{w.casefold()}\b") for w in MADE_UP_WORDS]
    probes = _probes()
    assert len(probes) >= 12
    seen = 0
    for path, text in _texts(root):
        seen += 1
        for word in words:
            assert not word.search(text), f"{word.pattern} occurs in {path}"
        for probe in probes:
            assert probe not in text, f"{probe!r} occurs in {path}"
    assert seen


def test_example_words_are_not_in_the_cassettes() -> None:
    _assert_not_in(CASSETTES)


def test_example_words_are_not_in_the_fixtures() -> None:
    if not FIXTURES.is_dir() or not any(FIXTURES.glob("*/*/expected.json")):
        pytest.skip("fixtures/ is gitignored and not present here")
    _assert_not_in(FIXTURES)


# --- R22.4.7.2: the budget ----------------------------------------------------------------------


def test_example_is_under_1500_tokens() -> None:
    assert -(-len(_example()) // MIN_CHARS_PER_TOKEN) < 1500


def test_longest_prompt_and_text_page_and_cap_fit_num_ctx() -> None:
    spec = next(s for s in EXTRACTION_TASKS if s.task == TASK)
    role = default_config().roles[spec.role]
    provider = FilePromptProvider()
    page = "x" * MAX_TEXT_PAGE_CHARS
    # the photo rules (step 22.6.1) make the photo call the longest one
    inputs = {"page_no": 99, "page_count": 99, "document": page, "photo_rules": PHOTO_RULES}
    prompt = provider.render(TASK, spec.profile(), inputs)
    request = build_request(
        role, prompt, TranscribeOut, think=spec.think, num_predict=spec.num_predict
    )
    num_ctx = request.body["options"]["num_ctx"]
    num_predict = request.body["options"]["num_predict"]
    assert (num_ctx, num_predict) == (16384, 8192)
    assert prompt_size(request.body).ceiling + num_predict <= num_ctx


def test_a_missing_or_unsafe_example_name_is_not_found() -> None:
    provider = FilePromptProvider()
    for name in ("no_such_example", "../base/transcribe_page"):
        with pytest.raises(PromptNotFound):
            provider.example_text(name)
