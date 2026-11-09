"""Step 22.6.2: a paper whose answers are all read unsure (Test K's made-up readings) is blank,
so the run saves the test alone, as for a paper with nothing read: no attempt, no answers, no
answer Review items, the thread "blank" (R22.6.2.3, step22.6-plan D5). Synthetic data only."""

from __future__ import annotations

from typing import Any

import pytest
from unit.graphs.test_extract import HEADER, Harness, _cards, _thread, answers_all, page_out
from unit.graphs.test_extract import data as data
from unit.graphs.test_extract import h as h

from etach.domain import boxes
from etach.store.repos import tests as test_repo


@pytest.mark.asyncio
async def test_r22_6_2_3_unsure_readings_make_a_test_only_thread(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the fake model's letters always come out sure, so a threshold above 1 makes them unsure
    resolve = boxes.resolve_answers

    def unsure_resolve(*args: Any, **kwargs: Any) -> boxes.ResolveResult:
        return resolve(*args, **{**kwargs, "threshold": 1.01})

    monkeypatch.setattr(boxes, "resolve_answers", unsure_resolve)
    h.fake.queues = {
        "TranscribeOut": [page_out(1, header=HEADER), page_out(2)],
        "ReadAnswersCall": [answers_all("A"), answers_all("B")],
    }
    run_id, _ = await h.run(h.photos(2))
    assert h.saved_states[-1]["answers"]  # the readings were made, then judged blank
    assert h.runs_status(run_id) == "done"
    assert h.count("tests") == 1 and h.count("attempts") == 0 and h.count("answers") == 0
    kinds = [r[0] for r in h.conn.execute("SELECT kind FROM review_items")]
    assert "uncertain_answer" not in kinds and "box_inline_conflict" not in kinds
    test = test_repo.find_by_source_run(h.conn, run_id)
    assert test is not None
    assert _thread(h).kind == "blank" and _thread(h).test_id == test.id
    card = _cards(h)[0]
    assert card["no_answers"] is True and card["attempt_id"] is None
