"""Step 22.6.3 (decision D6): the checker may be unsure (R22.6.3.1, R22.6.3.2)."""

from __future__ import annotations

import pytest
from unit.domain.grading_support import NOW, key

from etach.domain.keys import checker_unsure, verify_failed
from etach.domain.llm_schemas import VerifyKeyOut
from etach.domain.models import KeyCheck
from etach.llm.tasks import GRADING_NUM_PREDICT, TASKS
from etach.prompts.render import FilePromptProvider


@pytest.mark.parametrize("answer", ["?", " ? ", "\t?\n", "  ?"])
def test_r22_6_3_1_question_mark_is_unsure(answer: str) -> None:
    k = key("q-1", "A", "ai_unverified", 0.2)
    checked = VerifyKeyOut(reasoning="Both A and C could fit.", answer=answer)
    new, item = verify_failed(k, "R-1", NOW, checked)
    assert checker_unsure(answer)
    assert new.status == "ai_uncertain" and new.accepted == ["A"]  # the key stays
    assert new.checker == KeyCheck(status="unsure", reasoning="Both A and C could fit.")
    assert new.checker.answer is None
    assert (item.kind, item.dedupe_key, item.refs) == (
        "uncertain_key",
        "uncertain_key:R-1:q-1",
        {"question_id": "q-1"},
    )


@pytest.mark.parametrize("answer", ["C", "??", "? C", "Why?", ""])
def test_r22_6_3_1_real_disagreement_stays_disagreed(answer: str) -> None:
    k = key("q-1", "A", "ai_unverified", 0.2)
    new, item = verify_failed(k, "R-1", NOW, VerifyKeyOut(reasoning="r", answer=answer))
    assert not checker_unsure(answer)
    assert new.status == "ai_uncertain"
    assert new.checker == KeyCheck(status="disagreed", answer=answer, reasoning="r")
    assert item.kind == "uncertain_key"


def test_r22_6_3_1_cut_off_or_failed_stays_did_not_finish() -> None:
    k = key("q-1", "A", "ai_unverified", 0.2)
    new, item = verify_failed(k, "R-1", NOW, None)
    assert new.status == "ai_uncertain"
    assert new.checker == KeyCheck(status="did_not_finish")
    assert item.kind == "uncertain_key"


def test_r22_6_3_1_key_check_accepts_unsure() -> None:
    assert KeyCheck.model_validate({"status": "unsure", "reasoning": "x"}).status == "unsure"
    assert KeyCheck.model_json_schema()["properties"]["status"]["enum"] == [
        "disagreed",
        "unsure",
        "did_not_finish",
    ]


def test_r22_6_3_2_prompt_says_unsure_and_limited_in_two_short_lines() -> None:
    prompt = FilePromptProvider().base_text("verify_key")
    lines = [ln for ln in prompt.splitlines() if "`?`" in ln]
    assert 1 <= len(lines) <= 2, lines
    assert all(len(ln) <= 100 for ln in lines), lines
    text = " ".join(lines).lower()
    assert "not sure" in text
    assert "limited" in text


def test_r22_6_3_2_verify_key_cap_is_1000() -> None:
    assert GRADING_NUM_PREDICT["verify_key"] == 1000
    assert TASKS["verify_key"].num_predict == 1000
