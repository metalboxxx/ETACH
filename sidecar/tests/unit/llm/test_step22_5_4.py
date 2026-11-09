"""Step 22.5.4a (plan-grading-quality): the model roles (R22.5.4.1) and the grading prompts and
schemas (R22.5.4.2-R22.5.4.4) that need no graph run."""

from __future__ import annotations

from pathlib import Path

from etach.llm.config import default_config, load_models_config, parse_models_config
from etach.llm.defaults import DEFAULT_ROLES
from etach.llm.tasks import TASKS

NEW_ROLES = ("grading_check", "extraction_check")


# --- R22.5.4.1: the model roles ------------------------------------------------------------------


def test_new_roles_default_to_qwen() -> None:
    config = default_config()
    for role in NEW_ROLES:
        assert DEFAULT_ROLES[role]["model"] == "qwen3.5:4b"
        assert config.role(role).model == "qwen3.5:4b"
        assert config.role(role).adapter == "chat"


def test_old_models_toml_without_new_roles_loads(tmp_path: Path) -> None:
    path = tmp_path / "models.toml"
    path.write_text(
        '[roles.vision]\nmodel = "a:1b"\n\n[roles.reasoning]\nmodel = "b:2b"\n\n'
        "[client]\nretry_capped_output = { vision = false, reasoning = true }\n",
        encoding="utf-8",
    )
    config = load_models_config(path)
    assert config.role("vision").model == "a:1b"
    assert config.role("reasoning").model == "b:2b"
    for role in NEW_ROLES:
        assert config.role(role).model == "qwen3.5:4b"
    # verify_key kept the reasoning role's retry of a capped output
    assert config.client.retries_capped("grading_check")
    assert not config.client.retries_capped("extraction_check")


def test_new_role_can_be_set() -> None:
    config = parse_models_config({"roles": {"grading_check": {"model": "other:7b"}}})
    assert config.role("grading_check").model == "other:7b"
    assert config.role("reasoning").model == "qwen3.5:4b"


def test_verify_key_uses_grading_check_and_only_the_reread_uses_extraction_check() -> None:
    """Step 22.5.7: ``reread_pieces`` is the one task on ``extraction_check``."""
    assert TASKS["verify_key"].role == "grading_check"
    others = {t: s.role for t, s in TASKS.items() if t != "verify_key"}
    assert "grading_check" not in others.values()
    assert [t for t, role in others.items() if role == "extraction_check"] == ["reread_pieces"]
    assert TASKS["ai_key_fast"].role == "reasoning"


# --- R22.5.4.2: the judge ------------------------------------------------------------------------


def test_judge_schema_lists_reason_before_verdict() -> None:
    from etach.domain.llm_schemas import JudgeOut

    schema = JudgeOut.model_json_schema()
    assert list(schema["properties"]) == ["reason", "verdict"]
    assert schema["required"] == ["reason", "verdict"]
    assert schema["properties"]["verdict"]["enum"] == ["correct", "incorrect"]  # no partial credit


# --- R22.5.4.4: explain --------------------------------------------------------------------------


def test_explain_schema_order_is_reasoning_text_error_type() -> None:
    from etach.domain.llm_schemas import ExplainOut

    schema = ExplainOut.model_json_schema()
    assert list(schema["properties"]) == ["reasoning", "text_vi", "error_type"]
    assert schema["required"] == ["reasoning", "text_vi", "error_type"]


def test_explain_prompt_names_no_grade() -> None:
    import re

    from etach.prompts.render import FilePromptProvider

    text = FilePromptProvider().base_text("explain")
    assert text.splitlines()[0] == (
        "You explain one wrong answer to a Vietnamese student who is learning English."
    )
    assert not re.search(r"\bgrade\b|\bgrades\b|lớp", text, re.IGNORECASE)


#: The explain output cap against the new shape. Measured in the teacher's app.db (2026-10-23,
#: plan-grading-quality): explain outputs were 98-151 tokens in the old shape. The prompt allows
#: at most 2 short English sentences of reasoning; a long example of that is below, counted at a
#: pessimistic 3 characters per token (English runs about 4).
LONG_REASONING = (
    "The second clause 'It looks empty' means there are no students at all, so the negative "
    "needs 'any'; the student chose 'a lot of', which does not fit an empty room."
)
OLD_SHAPE_MAX_TOKENS = 151


def test_explain_cap_fits_the_new_shape() -> None:
    reasoning_tokens = len('"reasoning": "",') // 3 + len(LONG_REASONING) // 3 + 1
    need = OLD_SHAPE_MAX_TOKENS + reasoning_tokens
    assert TASKS["explain"].num_predict == 512
    assert need < TASKS["explain"].num_predict // 2, need  # more than twice the room
