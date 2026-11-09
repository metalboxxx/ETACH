"""M1 listening safety net (llm-design §4), end to end through the real CLI in-process.

A SYNTHETIC 2-page filled test: page 1's section comes back as ``kind: "listening"`` but with
full question bodies (the model merged printed sections). The run must save those questions
in the test and leave one open ``validator_failed`` item for page 1. Nothing is recorded: the
schema-keyed FakeOllama of ``make_synthetic.py`` answers in-process (no model, no cassette).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .make_synthetic import EMPTY, HEADER, Recorder, answers, page_out, photo
from .test_extract_replay import conn_of


def _listening_page_1() -> dict[str, Any]:
    out = page_out(1, header=HEADER)
    section = out["sections"][0]
    section.update(kind="listening", range_first=1, range_last=2)
    return out


def test_rescued_listening_section_is_saved_with_one_item(tmp_path: Path) -> None:
    rec = Recorder(tmp_path)
    try:
        pages = [str(photo(tmp_path, f"De-listening ({i}).jpg", 150 + i)) for i in (1, 2)]
        data = tmp_path / "data"
        out = rec.run(
            data,
            pages,
            {
                "TranscribeOut": [_listening_page_1(), page_out(2)],
                "ReadAnswersCall": [answers(), EMPTY],
            },
        )
    finally:
        rec.cli._TEST_TRANSPORT = None
    assert out["status"] == "done"
    test_id = out["test_id"]
    c = conn_of(data)
    try:
        row = c.execute("SELECT content, meta FROM tests WHERE id = ?", (test_id,)).fetchone()
        content, meta = json.loads(row[0]), json.loads(row[1])
        qs = [q for s in content["sections"] for g in s["groups"] for q in g["questions"]]
        assert [q["printed_number"] for q in qs] == [1, 2, 3, 4]
        assert [q["number"] for q in qs] == [1, 2, 3, 4]
        assert content["sections"][0]["graded"] is True
        assert meta.get("omitted_sections") == []
        items = c.execute(
            "SELECT status, dedupe_key, proposal, test_id FROM review_items"
            " WHERE kind = 'validator_failed'"
        ).fetchall()
        assert len(items) == 1
        status, key, proposal, item_test = items[0]
        assert status == "open" and item_test == test_id
        assert key == f"validator_failed:{out['run_id']}:listening:1"
        p = json.loads(proposal)
        assert p["reason"] == "listening_with_questions" and p["page_no"] == 1
        assert p["sections"][0]["questions"] == 2
    finally:
        c.close()
