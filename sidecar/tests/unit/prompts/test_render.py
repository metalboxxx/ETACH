"""Extraction prompts (plan step 8.2): R8.2.1-R8.2.3, placeholders, profiles, packaging."""

from __future__ import annotations

import json
import shutil
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from etach.domain.models import Option, Question
from etach.llm.adapters import build_request
from etach.llm.cassettes import match_key
from etach.llm.config import RoleConfig, parse_models_config
from etach.llm.tasks import TASKS, extraction_inputs
from etach.prompts.render import FilePromptProvider, PromptInputError, fill

# plan Appendix D.2, copied verbatim
D2: dict[str, list[str]] = {
    "transcribe_page": [
        "printed text only",
        "write every blank as ____",
        "<u>",
        "**",
        "listening: return only the heading and question range",
        "writing: return only the task prompt",
        "transcribe pictures that are mostly text",
    ],
    "read_answers_page": [
        "copy handwriting exactly, including mistakes",
        "answer box",
        "circled",
        "null if no answer",
        "student name",
    ],
    "read_key_pages": ["question number", "answer"],
    "read_header": ["header", "first questions"],
}

EXTRACTION = ["read_key_pages", "read_header", "transcribe_page", "read_answers_page"]


def questions() -> list[Question]:
    def q(i: int, qtype: str, page: int, options: list[Option] | None = None) -> Question:
        return Question.model_validate(
            {
                "id": f"Q{i}",
                "number": i,
                "printed_number": i + 4,
                "page_no": page,
                "type": qtype,
                "stem": f"Stem {i} ____ .",
                "options": options,
                "cue": None,
                "points": 0.25,
            }
        )

    abcd = [Option(label=x, text=f"opt {x}") for x in "ABCD"]
    return [
        q(1, "mcq", 1, abcd),
        q(2, "true_false", 1),
        q(3, "word_form", 2),
        q(4, "writing", 2),
    ]


def inputs_for(task: str) -> dict[str, Any]:
    return extraction_inputs(
        task, page_no=1, photo_count=2, questions=questions(), draft_page_count=2
    )


def role(adapter: str) -> RoleConfig:
    # the NuExtract role as an older models.toml names it (the default vision is chat, D4)
    cfg = parse_models_config({"roles": {"vision": {"model": "numind/nuextract3:Q6_K"}}})
    base = cfg.roles["vision" if adapter == "nuextract" else "reasoning"]
    assert base.adapter == adapter
    return base


@pytest.fixture
def provider() -> FilePromptProvider:
    return FilePromptProvider()


# --- R8.2.1 ------------------------------------------------------------------------------------


@pytest.mark.parametrize("adapter", ["nuextract", "chat"])
@pytest.mark.parametrize("task", EXTRACTION)
def test_r8_2_1_renders_with_both_adapters(
    provider: FilePromptProvider, task: str, adapter: str
) -> None:
    spec = TASKS[task]
    prompt = provider.render(task, spec.profile("hk1_lop8"), inputs_for(task))
    schema = spec.schema(questions())
    r = role(adapter)
    req = build_request(r, prompt, schema, think=spec.think, num_predict=spec.num_predict)
    body = json.loads(json.dumps(req.body))  # JSON-serializable
    assert body["model"] == r.model
    assert body["think"] is False
    assert "{{" not in json.dumps(body, ensure_ascii=False)
    roles = [m["role"] for m in body["messages"]]
    if adapter == "nuextract":
        assert roles == ["template", "instructions", "user"]
        json.loads(body["messages"][0]["content"])  # the template is JSON
        assert prompt.system in body["messages"][1]["content"]
        assert prompt.user_text in body["messages"][1]["content"]
    else:
        assert roles == ["system", "user"]
        assert body["messages"][0]["content"] == prompt.system
        assert body["messages"][1]["content"] == prompt.user_text
        assert body["format"] == schema.model_json_schema(by_alias=True)


def test_read_answers_uses_the_per_call_schema() -> None:
    spec = TASKS["read_answers_page"]
    assert spec.per_call_schema
    schema = spec.schema(questions())
    answers = schema.model_json_schema(by_alias=True)["$defs"]["ReadAnswersByQuestion"]
    assert set(answers["properties"]) == {"Q1", "Q2", "Q3"}  # writing is not read
    with pytest.raises(ValueError):
        spec.schema()


def test_all_extraction_tasks_are_vision_without_thinking() -> None:
    for task in EXTRACTION:
        spec = TASKS[task]
        assert spec.role == "vision"
        assert spec.think is False


# --- R8.2.2 ------------------------------------------------------------------------------------


@pytest.mark.parametrize("task", EXTRACTION)
def test_r8_2_2_d2_phrases_in_each_prompt(provider: FilePromptProvider, task: str) -> None:
    prompt = provider.render(task, TASKS[task].profile(None), inputs_for(task))
    text = f"{prompt.system}\n{prompt.user_text}"
    missing = [p for p in D2[task] if p not in text]
    assert not missing, f"{task} lacks {missing}"


# --- R8.2.3 ------------------------------------------------------------------------------------


def copy_prompts(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    with resources.as_file(resources.files("etach.prompts")) as src:
        shutil.copytree(src, root, ignore=shutil.ignore_patterns("*.py", "__pycache__"))
    return root


@pytest.mark.parametrize("task", EXTRACTION)
def test_r8_2_3_hash_stable_and_changes_with_the_file(tmp_path: Path, task: str) -> None:
    root = copy_prompts(tmp_path)
    provider = FilePromptProvider(root)
    first = provider.render(task, "generic", inputs_for(task))
    again = FilePromptProvider(root).render(task, "generic", inputs_for(task))
    assert first.hash == again.hash
    assert first == again
    assert first.hash == FilePromptProvider().render(task, "generic", inputs_for(task)).hash

    base = root / "base" / f"{task}.md"
    base.write_text(base.read_text(encoding="utf-8") + "\n- One more rule.\n", encoding="utf-8")
    assert provider.render(task, "generic", inputs_for(task)).hash != first.hash


def test_hash_changes_with_the_profile_file_and_inputs(tmp_path: Path) -> None:
    root = copy_prompts(tmp_path)
    provider = FilePromptProvider(root)
    task = "read_header"
    first = provider.render(task, "generic", {"page_no": 1})
    assert provider.render(task, "generic", {"page_no": 2}).hash != first.hash
    profile = root / "profiles" / "generic.md"
    profile.write_text(profile.read_text(encoding="utf-8") + "\nMore.\n", encoding="utf-8")
    assert provider.render(task, "generic", {"page_no": 1}).hash != first.hash


def test_hash_ignores_crlf_line_endings(tmp_path: Path) -> None:
    root = copy_prompts(tmp_path)
    task = "read_answers_page"
    first = FilePromptProvider(root).render(task, "generic", inputs_for(task))
    for path in [root / "base" / f"{task}.md", root / "profiles" / "generic.md"]:
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert FilePromptProvider(root).render(task, "generic", inputs_for(task)) == first


def test_hash_includes_the_task_name(tmp_path: Path) -> None:
    root = copy_prompts(tmp_path)
    shutil.copy(root / "base" / "read_header.md", root / "base" / "read_header_copy.md")
    provider = FilePromptProvider(root)
    a = provider.render("read_header", "generic", {"page_no": 1})
    b = provider.render("read_header_copy", "generic", {"page_no": 1})
    assert (a.system, a.user_text) == (b.system, b.user_text)
    assert a.hash != b.hash


# --- placeholders, profiles, document ------------------------------------------------------


def test_missing_placeholder_input_raises(provider: FilePromptProvider) -> None:
    with pytest.raises(PromptInputError, match="question_list"):
        provider.render("read_answers_page", "generic", {"page_no": 1, "page_count": 2})


def test_fill_is_one_pass_and_formats_values() -> None:
    assert fill("{{a}} {{ b }}", {"a": "{{b}}", "b": [1, "x"]}) == '{{b}} [1,"x"]'


def test_transcribe_ignores_the_exam_format_profile(tmp_path: Path) -> None:
    root = copy_prompts(tmp_path)
    (root / "profiles" / "hk1_lop8.md").write_text("SPECIAL PROFILE TEXT", encoding="utf-8")
    provider = FilePromptProvider(root)
    spec = TASKS["transcribe_page"]
    assert spec.profile("hk1_lop8") == "generic"
    prompt = provider.render(spec.task, spec.profile("hk1_lop8"), inputs_for(spec.task))
    assert "SPECIAL PROFILE TEXT" not in prompt.system
    # the other tasks do use it
    other = TASKS["read_answers_page"]
    assert other.profile("hk1_lop8") == "hk1_lop8"
    prompt = provider.render(other.task, other.profile("hk1_lop8"), inputs_for(other.task))
    assert "SPECIAL PROFILE TEXT" in prompt.system


@pytest.mark.parametrize("profile", ["no_such_format", "", "../base/read_header", "Lớp 8"])
def test_missing_or_unsafe_profile_falls_back_to_generic(
    provider: FilePromptProvider, profile: str
) -> None:
    generic = provider.render("read_header", "generic", {"page_no": 1})
    assert provider.render("read_header", profile, {"page_no": 1}) == generic
    assert provider.resolve_profile(profile) == "generic"


def test_document_input_becomes_the_document(provider: FilePromptProvider) -> None:
    inputs = extraction_inputs("transcribe_page", page_no=1, photo_count=1, document="I. Choose")
    prompt = provider.render("transcribe_page", "generic", inputs)
    assert prompt.document == "I. Choose"
    assert "I. Choose" not in prompt.system + prompt.user_text
    body = build_request(role("nuextract"), prompt, TASKS["transcribe_page"].schema()).body
    assert body["messages"][-1]["content"] == "I. Choose"


def test_unknown_task_raises(provider: FilePromptProvider) -> None:
    with pytest.raises(FileNotFoundError):
        provider.render("no_such_task", "generic", {})


def test_prompt_files_ship_in_the_package() -> None:
    root = resources.files("etach.prompts")
    for task in EXTRACTION:
        assert root.joinpath("base", f"{task}.md").is_file()
    assert root.joinpath("profiles", "generic.md").is_file()


def test_match_key_uses_the_inputs_helper_names() -> None:
    a = extraction_inputs("read_answers_page", page_no=1, photo_count=2, questions=questions())
    b = extraction_inputs("read_answers_page", page_no=2, photo_count=2, questions=questions())
    assert a["question_ids"] == ["Q1", "Q2", "Q3"]
    assert match_key("read_answers_page", "S", a) != match_key("read_answers_page", "S", b)
