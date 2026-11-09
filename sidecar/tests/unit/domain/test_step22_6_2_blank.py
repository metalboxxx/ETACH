"""Step 22.6.2: a paper with fewer than 20% of its answers read with confidence is blank, and a
value spelled ``null`` / ``none`` / ``n/a`` is not read (R22.6.2.1-2). Made-up readings only."""

from __future__ import annotations

from typing import Any

import pytest
from support.guards import no_io  # noqa: F401
from unit.domain.test_boxes import T, b1_draft, pages, q_id, reading

from etach.domain.boxes import BLANK_SHARE, resolve_answers
from etach.llm.config import default_config, parse_models_config

pytestmark = pytest.mark.usefixtures("no_io")

#: b1_draft grades questions 5-40: 36 answers, so 20% is 7.2
CHOICES = [p for p in range(5, 41) if p not in (12, 15, 35, 36)]


def _readings(sure: int, unsure: int) -> list[tuple[dict[str, Any], float]]:
    """``sure`` letters read with confidence, then ``unsure`` letters below the threshold."""
    out = [(reading(p, "A", "circled_option"), 0.95) for p in CHOICES[:sure]]
    out += [(reading(p, "B", "circled_option"), 0.2) for p in CHOICES[sure : sure + unsure]]
    return out


def test_r22_6_2_1_share_is_the_teachers_20_percent() -> None:
    assert BLANK_SHARE == 0.2
    assert default_config().extract.blank_share == BLANK_SHARE
    assert parse_models_config({"extract": {"blank_share": 0}}).extract.blank_share == 0


def test_r22_6_2_1_share_zero_is_the_rule_before() -> None:
    """``[extract] blank_share = 0``: only a paper with nothing read is blank (recorded replays)."""
    pa, conf = pages(_readings(1, 20))
    assert resolve_answers(pa, conf, b1_draft(), threshold=T).blank is True
    assert resolve_answers(pa, conf, b1_draft(), threshold=T, blank_share=0).blank is False


def test_r22_6_2_1_made_up_unsure_letters_are_a_blank_paper() -> None:
    """Test K's shape: 2 sure, 20 unsure, the rest empty."""
    rs = _readings(2, 20)
    rs.append((reading(10, "C", "answer_box"), 0.3))  # a box/inline conflict on question 10
    pa, conf = pages(rs)
    out = resolve_answers(pa, conf, b1_draft(), threshold=T, ref="r1")
    assert out.blank is True
    assert out.pendings == []  # nothing about the answers is kept for Review


@pytest.mark.parametrize(("sure", "blank"), [(7, True), (8, False)])
def test_r22_6_2_1_the_line_is_under_20_percent(sure: int, blank: bool) -> None:
    pa, conf = pages(_readings(sure, 10))
    assert resolve_answers(pa, conf, b1_draft(), threshold=T).blank is blank


def test_r22_6_2_1_unreadable_writing_counts_as_written() -> None:
    rs = [(reading(p, "???"), 0.95) for p in CHOICES[:8]]
    pa, conf = pages(rs)
    assert resolve_answers(pa, conf, b1_draft(), threshold=T).blank is False


def test_r22_6_2_1_a_failed_page_is_never_blank() -> None:
    pa, conf = pages(_readings(1, 0))
    out = resolve_answers(pa, conf, b1_draft(), threshold=T, failed_pages=[3], ref="r1")
    assert out.blank is False
    assert [p.kind for p in out.pendings] == ["validator_failed"]


@pytest.mark.parametrize("word", ["null", "NULL", " None ", "n/a"])
def test_r22_6_2_2_a_spelled_out_null_is_not_read(word: str) -> None:
    rs = _readings(10, 0)
    rs.append((reading(12, word), 0.97))
    pa, conf = pages(rs)
    out = resolve_answers(pa, conf, b1_draft(), threshold=T)
    (q12,) = [a for a in out.answers if a.question_id == q_id(12)]
    assert q12.value is None and q12.value_norm is None
