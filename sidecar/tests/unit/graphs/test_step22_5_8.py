"""Step 22.5.8 (a)(2): a key photo whose key replaces an AI key closes that question's open
``uncertain_key`` item (``fixed``, ``{"action": "fix", "value": {"by": "key_photo"}}``) and the
photo's key is kept (R22.5.8.1). Synthetic data only, through the extract graph's save."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from unit.graphs.test_extract import (
    HEADER,
    Harness,
    _bank_test,
    answers_all,
    png,
)
from unit.graphs.test_extract import data as data
from unit.graphs.test_extract import h as h

from etach.domain.models import AnswerKey, PageInput
from etach.store.repos import keys, review


def _ai_key(test_id: str, qid: str, accepted: str, status: str = "ai_uncertain") -> AnswerKey:
    return AnswerKey(
        test_id=test_id, question_id=qid, accepted=[accepted], reason_vi=None, source="ai",
        status=status, confidence=0.4, updated_at=datetime(2026, 1, 1, tzinfo=UTC),  # type: ignore[arg-type]
    )  # fmt: skip


@pytest.mark.asyncio
async def test_r22_5_8_1_key_photo_closes_the_unsure_ai_key_item(h: Harness) -> None:
    bank = _bank_test(h, 2)
    qs = [q for s in bank.content.sections for g in s.groups for q in g.questions]
    q1, q2 = qs[0], qs[1]
    # grading made unsure AI keys on questions 1 and 2, each with an open uncertain_key item
    items = {}
    for q, letter in ((q1, "B"), (q2, "D")):
        keys.upsert_key(h.conn, _ai_key(bank.id, q.id, letter))
        items[q.id], _ = review.upsert_item(
            h.conn, kind="uncertain_key", owner="grade",
            dedupe_key=f"uncertain_key:R-GRADE:{q.id}", proposal={"accepted": [letter]},
            test_id=bank.id, question_id=q.id,
        )  # fmt: skip
    # the new run's key photo gives question 1 only
    pages = h.photos(2)
    key_fid = h.files.put(png((10, 10, 10)), "png")
    pages.append(PageInput(file_id=key_fid, rotation=0, is_key=True, text_file_id=None))
    stems = [q.stem for q in qs]
    h.fake.queues = {
        "ReadHeaderOut": [{"header_text": HEADER, "first_stems": stems[:3]}],
        "ReadKeyOut": [{"entries": [{"label": str(q1.printed_number), "answer": "C"}]}],
        "ReadAnswersCall": [answers_all(), answers_all()],
    }
    run_id, _ = await h.run(pages, existing=bank.id)
    assert h.runs_status(run_id) == "done"

    k1 = keys.get_key(h.conn, bank.id, q1.id)
    assert k1 is not None and k1.source == "from_key_photo" and k1.accepted == ["C"]
    closed = review.get_item(h.conn, items[q1.id].id)
    assert closed is not None and closed.status == "fixed" and closed.resolved_at is not None
    assert closed.resolution == {"action": "fix", "value": {"by": "key_photo"}}
    # the photo's key is kept: the item's own proposal is not applied
    assert keys.get_key(h.conn, bank.id, q1.id) == k1
    # question 2 had no photo key: its AI key and its item stay
    k2 = keys.get_key(h.conn, bank.id, q2.id)
    assert k2 is not None and k2.source == "ai" and k2.accepted == ["D"]
    still = review.get_item(h.conn, items[q2.id].id)
    assert still is not None and still.status == "open"


def test_settle_key_items_leaves_other_kinds(h: Harness) -> None:
    bank = _bank_test(h, 1)
    qid = bank.content.sections[0].groups[0].questions[0].id
    unsure, _ = review.upsert_item(
        h.conn, kind="uncertain_key", owner="grade", dedupe_key=f"uncertain_key:R:{qid}",
        proposal={}, test_id=bank.id, question_id=qid,
    )  # fmt: skip
    other, _ = review.upsert_item(
        h.conn, kind="key_unmapped", owner="extract", dedupe_key="key_unmapped:R:x",
        proposal={"label": "x", "accepted": ["A"]}, test_id=bank.id, question_id=qid,
    )  # fmt: skip
    assert review.settle_key_items(h.conn, bank.id, qid, by="key_photo") == [unsure.id]
    assert review.get_item(h.conn, other.id).status == "open"  # type: ignore[union-attr]
    row = h.conn.execute(
        "SELECT status, resolution FROM review_items WHERE id = ?", (unsure.id,)
    ).fetchone()
    assert row[0] == "fixed" and json.loads(row[1])["value"] == {"by": "key_photo"}
    assert review.settle_key_items(h.conn, bank.id, qid, by="key_photo") == []  # nothing open
