"""Grading prompts (plan step 17.2): R17.2.1-R17.2.4, the taxonomy files, packaging."""

from __future__ import annotations

import hashlib
import json
import re
from importlib import resources
from typing import Any

import pytest
from pydantic import ValidationError

from etach.domain.llm_schemas import (
    AiKeyOut,
    ExplainOut,
    JudgeOut,
    SummaryOut,
    VerifyKeyOut,
)
from etach.llm.adapters import build_request
from etach.llm.config import RoleConfig, parse_models_config
from etach.llm.tasks import (
    GRADING_TASKS,
    GRADING_THINK,
    TAG_SKILLS_SCHEMA,
    TASKS,
    parse_skill_lines,
    skill_list_text,
    taxonomy_ids,
    taxonomy_text,
)
from etach.prompts.render import FilePromptProvider, placeholders

# plan Appendix D.3, copied verbatim
D3: dict[str, list[str]] = {
    "explain": ["in Vietnamese", "keep grammar terms in English", "at most 3 sentences"],
    "judge_rewrites": ["must be grammatical", "same meaning", "no partial credit"],
    "weak_points_summary": ["3 to 5 questions for the teacher", "what each answer would mean"],
    "verify_key": ["solve independently"],
    "tag_skills": ["use only these skill IDs"],
}

GRADING = [
    "ai_key_fast",
    "verify_key",
    "tag_skills",
    "judge_rewrites",
    "explain",
    "weak_points_summary",
]

INPUTS: dict[str, dict[str, Any]] = {
    "ai_key_fast": {
        "section_id": "S2",
        "question_ids": ["Q5", "Q6"],
        "key_questions": "Q5, Q6",
        "section_text": "II. Choose the best answer.\n- Q5: She ____ to school. A. go B. goes",
    },
    "verify_key": {"question_id": "Q5", "question_text": "She ____ to school. A. go B. goes"},
    "tag_skills": {
        "section_id": "S2",
        "question_ids": ["Q5", "Q6"],
        "skill_list": skill_list_text(),
        "section_text": "II. Choose the best answer.\n- Q5: She ____ to school. A. go B. goes",
    },
    "judge_rewrites": {
        "question_text": "I started learning English 3 years ago. → I have …",
        "accepted": ["I have learnt English for 3 years."],
        "student_answer": "I have learn English for 3 years.",
    },
    "explain": {
        "question_text": "She ____ (go) to school every day.",
        "accepted": ["goes"],
        "student_answer": "go",
        "skill_tags": ["GR-PSV-A1"],
    },
    "weak_points_summary": {
        "score_text": "7.5/10",
        "weak_points": "1. GR-PPF-A2: 3 wrong of 4",
        "wrong_answers": "- Q5: go (key goes)",
    },
}


def chat_role() -> RoleConfig:
    role = parse_models_config({}).roles["reasoning"]
    assert role.adapter == "chat"
    return role


@pytest.fixture
def provider() -> FilePromptProvider:
    return FilePromptProvider()


def test_the_registry_has_every_grading_task() -> None:
    assert [spec.task for spec in GRADING_TASKS] == GRADING
    for task in GRADING:
        assert TASKS[task].role == ("grading_check" if task == "verify_key" else "reasoning")
        assert TASKS[task].profile("hk1_lop8") == "hk1_lop8"
        assert TASKS[task].profile(None) == "generic"
    assert TASKS["ai_key_fast"].schema() is AiKeyOut
    assert TASKS["verify_key"].schema() is VerifyKeyOut
    assert TASKS["tag_skills"].schema() is TAG_SKILLS_SCHEMA
    assert TASKS["judge_rewrites"].schema() is JudgeOut
    assert TASKS["explain"].schema() is ExplainOut
    assert TASKS["weak_points_summary"].schema() is SummaryOut


# --- R17.2.1 -----------------------------------------------------------------------------------


@pytest.mark.parametrize("task", GRADING)
def test_r17_2_1_renders_with_the_chat_adapter(provider: FilePromptProvider, task: str) -> None:
    spec = TASKS[task]
    prompt = provider.render(task, spec.profile("hk1_lop8"), INPUTS[task])
    schema = spec.schema()
    role = chat_role()
    req = build_request(role, prompt, schema, think=spec.think, num_predict=spec.num_predict)
    body = json.loads(json.dumps(req.body))  # JSON-serializable
    assert body["model"] == role.model
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["messages"][0]["content"] == prompt.system
    assert body["messages"][1]["content"] == prompt.user_text
    assert body["format"] == schema.model_json_schema(by_alias=True)
    assert body["think"] is spec.think
    assert body["options"]["num_predict"] == spec.num_predict
    assert "{{" not in json.dumps(body, ensure_ascii=False)
    assert prompt.user_text.strip()


@pytest.mark.parametrize("task", GRADING)
def test_every_placeholder_has_an_input(provider: FilePromptProvider, task: str) -> None:
    names = set(placeholders(provider.base_text(task)))
    assert names <= set(INPUTS[task]), f"{task}: test inputs lack {names - set(INPUTS[task])}"


# --- R17.2.2 -----------------------------------------------------------------------------------


@pytest.mark.parametrize("task", sorted(D3))
def test_r17_2_2_d3_phrases_in_each_prompt(provider: FilePromptProvider, task: str) -> None:
    prompt = provider.render(task, TASKS[task].profile(None), INPUTS[task])
    text = f"{prompt.system}\n{prompt.user_text}"
    missing = [p for p in D3[task] if p not in text]
    assert not missing, f"{task} lacks {missing}"


# M2 explain prompt (teacher's blind ratings, 2026-10-12): each rule is pinned, so dropping one
# fails here.
EXPLAIN_RULES: dict[str, list[str]] = {
    # step 22.5.4: no grade range (the teacher, 2026-10-23)
    "audience": ["a Vietnamese student who is learning English"],
    "hidden reasoning": ["`reasoning` first (never shown)"],
    "length": [
        "at most 3 sentences, plus short glosses",
        "Keep it short: about 70 words in all",
        "no wordy closing or summing-up sentence",
    ],
    "vocabulary first": [
        "Vocabulary first",
        "did not know the words, not because of grammar or logic",
        "start with the key word(s) and their Vietnamese meaning",
        "then the meaning of the sentence",
        "Grammar or logic comes after that, only if needed",
        "In a dialogue, first say what the other speaker's sentence means",
    ],
    # M2 explain prompt 2 (teacher's re-rating notes, 2026-10-12)
    "key word gloss": [
        "always gloss the word or phrase that decides the answer, even a multi-word term",
        "When you name the correct answer, give its Vietnamese meaning right after it",
    ],
    "word form": [
        "give the meaning first, then say why this word class is needed here",
        "-ed tells how a person feels",
        "the wrong form can still be grammatical but changes the meaning",
    ],
    "state the rule": [
        "state the rule or formula briefly in English terms and add what it means in Vietnamese",
    ],
    "sentence meaning": [
        "For a sentence rewrite or a sentence-building question, end with one line",
        "the Vietnamese meaning of the correct sentence",
    ],
    "no restating": [
        "do not repeat the question",
        "do not quote the whole correct sentence in English",
        "Give only the correct word or phrase",
        "A Vietnamese meaning of the sentence is not quoting",
    ],
    "on topic": ["Stay on this student's actual mistake"],
    "tone": [
        "plain and respectful",
        "Not childish",
        "no academic or clinical wording",
        "simple everyday Vietnamese words",
        "Use only real Vietnamese words",
    ],
}

# Words and phrases from the tuning papers the teacher re-rates (and from the teacher's notes);
# the prompt's examples must not favour them.
EXPLAIN_BANNED_EXAMPLES = ["reluctant", "so as to", "vertical farm", "are you coming"]


@pytest.mark.parametrize("rule", sorted(EXPLAIN_RULES))
def test_explain_prompt_keeps_the_teachers_rules(provider: FilePromptProvider, rule: str) -> None:
    text = " ".join(provider.base_text("explain").split())  # line wraps count as one space
    for phrase in EXPLAIN_RULES[rule]:
        assert phrase in text, (rule, phrase)


def test_explain_prompt_vocabulary_comes_before_grammar(provider: FilePromptProvider) -> None:
    text = provider.base_text("explain")
    assert text.index("Vocabulary first") < text.index("Grammar point")


def test_explain_prompt_examples_avoid_the_rated_papers(provider: FilePromptProvider) -> None:
    text = provider.base_text("explain").lower()
    for phrase in EXPLAIN_BANNED_EXAMPLES:
        assert phrase not in text, phrase


def test_explain_prompt_keeps_the_error_types(provider: FilePromptProvider) -> None:
    text = provider.base_text("explain")
    for value in ("gap", "careless", "spelling", "misread_question", "unknown"):
        assert f"`{value}`" in text
    assert "`text_vi`" in text


def test_verify_key_is_not_shown_a_key(provider: FilePromptProvider) -> None:
    assert "accepted" not in placeholders(provider.base_text("verify_key"))


# --- R17.2.3 -----------------------------------------------------------------------------------


def ids_in_file(name: str) -> list[str]:
    """An independent parse: the first field of every ``ID | …`` line."""
    out: list[str] = []
    for line in taxonomy_text(name).splitlines():
        head, sep, _ = line.partition("|")
        if sep and re.fullmatch(r"[A-Z][A-Z0-9-]*", head.strip()) and head == head.rstrip() + " ":
            out.append(head.strip())
    return out


def test_r17_2_3_allowed_ids_equal_the_taxonomy_ids() -> None:
    grammar = ids_in_file("grammar.txt")
    sections = ids_in_file("sections.txt")
    assert len(grammar) == 58  # "TOTAL: 58 skill IDs" in the file
    assert "TOTAL: 58 skill IDs" in taxonomy_text("grammar.txt")
    assert all(re.fullmatch(r"GR-[A-Z]{3}-(A1|A2|B1|B2)", i) for i in grammar)
    assert not set(grammar) & set(sections)
    expected = grammar + sections
    assert len(set(expected)) == len(expected)
    assert taxonomy_ids() == expected
    assert len(sections) == 26
    assert {"PRON-ED", "PRON-S", "VOC-DICT"} <= set(expected)

    schema = TAG_SKILLS_SCHEMA.model_json_schema()
    item = next(iter(schema["$defs"].values()))
    allowed = item["properties"]["tags"]["items"]["enum"]
    assert allowed == expected


def test_section_ids_follow_the_plan_families() -> None:
    sections = ids_in_file("sections.txt")
    # teacher decisions: PRON-ED, PRON-S (plan v2.7) and VOC-DICT
    assert {"PRON-VOWEL", "PRON-ED", "PRON-S", "VOC-DICT", "SIGN"} <= set(sections)
    for prefix in ("STRESS-", "VOC-", "WF-", "READ-", "REWRITE-"):
        assert any(i.startswith(prefix) for i in sections), prefix
    family = re.compile(r"PRON-(VOWEL|ED|S)|SIGN|(STRESS|VOC|WF|READ|REWRITE)-[A-Z0-9-]+")
    assert all(family.fullmatch(i) for i in sections)


def test_tag_skills_schema_rejects_unknown_ids() -> None:
    TAG_SKILLS_SCHEMA.model_validate(
        {"items": [{"question_id": "Q1", "tags": ["GR-PSV-A1"], "level": "A2"}]}
    )
    TAG_SKILLS_SCHEMA.model_validate(
        {"items": [{"question_id": "Q1", "tags": ["PRON-VOWEL"], "level": "A2"}]}
    )
    with pytest.raises(ValidationError):
        TAG_SKILLS_SCHEMA.model_validate(
            {"items": [{"question_id": "Q1", "tags": ["GR-XYZ-A1"], "level": "A2"}]}
        )


def test_the_skill_list_reaches_the_tag_skills_prompt(provider: FilePromptProvider) -> None:
    prompt = provider.render("tag_skills", "generic", INPUTS["tag_skills"])
    for skill_id in taxonomy_ids():
        assert f"{skill_id} | " in prompt.system
    assert "GR-PSV-A1 | Present Simple — Affirmative Forms | A1" in prompt.system
    for rule in ("VOC-COLLOC", "REWRITE-START and", "use SIGN", "only its GR- tag", "at least one"):
        assert rule in prompt.system, rule


def test_parse_skill_lines_ignores_crlf_and_prose() -> None:
    text = "TITLE LINE\r\nGR-ABC-A1 | Name | A1\r\nNot | a skill\r\nSIGN | Signs | x\r\n"
    assert [i for i, _ in parse_skill_lines(text.replace("\r\n", "\n"))] == ["GR-ABC-A1", "SIGN"]


def test_grammar_taxonomy_is_the_tutor_copy() -> None:
    # byte-for-byte copy of EnglishTest_Tutor's file, modulo the checkout's line endings
    raw = resources.files("etach.prompts").joinpath("taxonomy", "grammar.txt").read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    # sha256 of EnglishTest_Tutor's ENGLISH_GRAMMAR_SKILL_TAXONOMY_prompt.txt with LF line endings
    assert hashlib.sha256(lf).hexdigest() == (
        "3c115ed76f59634c12a21c2b72b9af4809547795f83fe45aa42f730e9e347ac2"
    )
    text = lf.decode("utf-8")
    assert text.startswith("=" * 80 + "\nENGLISH GRAMMAR SKILL TAXONOMY")
    assert "TOTAL: 58 skill IDs across Pre-A1 to B2." in text


# --- R17.2.4 -----------------------------------------------------------------------------------


def test_r17_2_4_thinking_off_for_every_task() -> None:
    assert not GRADING_THINK
    assert [spec.task for spec in TASKS.values() if spec.think] == []
    # judge_rewrites keeps the cap sized when it thought; verify_key is 1000 since step 22.6.3 (D6)
    assert TASKS["verify_key"].num_predict == 1000
    assert TASKS["judge_rewrites"].num_predict == 400


# --- packaging ---------------------------------------------------------------------------------


def test_grading_prompt_files_ship_in_the_package() -> None:
    root = resources.files("etach.prompts")
    for task in GRADING:
        assert root.joinpath("base", f"{task}.md").is_file()
    for name in ("grammar.txt", "sections.txt"):
        assert root.joinpath("taxonomy", name).is_file()
