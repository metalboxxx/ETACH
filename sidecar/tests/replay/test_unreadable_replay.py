"""Step 21a (PRD D25): the synthetic ``tests/cassettes/unreadable/`` scenario (made by
``make_unreadable.py``; its docstring says what each page holds). R21a.2 and R21a.5."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from etach.domain import models as m
from etach.domain.models import Answer, AnswerKey
from etach.domain.scoring import grade, grade_answer
from etach.graphs.extract import ExtractThresholds

from .test_extract_replay import CASSETTES, conn_of, etach, run_ok

UNREADABLE = CASSETTES / "unreadable"
THRESHOLD = ExtractThresholds().reading


def _items(c: sqlite3.Connection) -> list[sqlite3.Row]:
    c.row_factory = sqlite3.Row
    return c.execute(
        "SELECT * FROM review_items WHERE kind = 'unreadable_text' ORDER BY dedupe_key"
    ).fetchall()


def _count(c: sqlite3.Connection, kind: str) -> int:
    return int(c.execute("SELECT COUNT(*) FROM review_items WHERE kind = ?", (kind,)).fetchone()[0])


def _content(c: sqlite3.Connection, test_id: str) -> m.TestContent:
    row = c.execute("SELECT content FROM tests WHERE id = ?", (test_id,)).fetchone()
    return m.TestContent.model_validate_json(row[0])


def _get(content: m.TestContent, path: str) -> Any:
    node: Any = content.model_dump()
    for part in path.replace("]", "").replace("[", ".").split("."):
        node = node[int(part)] if part.isdigit() else node[part]
    return node


# --- R21a.2 ----------------------------------------------------------------------------------


def test_r21a_2_one_item_per_page_with_unreadable_text(tmp_path: Path) -> None:
    data = tmp_path / "data"
    out = run_ok("--data", data, "--replay", UNREADABLE / "filled")
    test_id = out["test_id"]
    c = conn_of(data)
    try:
        items = _items(c)
        assert len(items) == 2
        rows = c.execute("SELECT page_no, file_id FROM test_pages WHERE test_id = ?", (test_id,))
        pages = {r[0]: r[1] for r in rows}
        assert sorted(pages) == [1, 2, 3]
        content = _content(c, test_id)
        by_page = {}
        for item in items:
            proposal = json.loads(item["proposal"])
            by_page[proposal["page_no"]] = proposal
            assert item["status"] == "open" and item["owner"] == "extract"
            assert item["test_id"] == test_id
            assert item["attempt_id"] is None and item["question_id"] is None
            assert item["dedupe_key"] == f"unreadable_text:{test_id}:p{proposal['page_no']}"
            assert proposal["file_id"] == pages[proposal["page_no"]]
            for span in proposal["spans"]:
                assert "???" in span["text"]
                assert _get(content, span["path"]) == span["text"]
        assert sorted(by_page) == [1, 3]  # none for page 2
        p1 = by_page[1]["spans"]
        assert [s["path"] for s in p1] == [
            "sections[0].instructions",
            "sections[0].groups[0].questions[0].stem",
        ]
        q1 = content.sections[0].groups[0].questions[0]
        assert [s["question_id"] for s in p1] == [None, q1.id]
        p3 = by_page[3]["spans"]
        q6 = content.sections[2].groups[0].questions[1]
        assert p3 == [
            {
                "path": "sections[2].groups[0].questions[1].stem",
                "question_id": q6.id,
                "text": q6.stem,
            }
        ]
        # ??? is valid text: no page went to retranscribe_tiles or validator_failed
        tiles = c.execute(
            "SELECT COUNT(*) FROM steps WHERE run_id = ? AND node = 'retranscribe_tiles'",
            (out["run_id"],),
        ).fetchone()[0]
        assert tiles == 0
        assert _count(c, "validator_failed") == 0
    finally:
        c.close()


def test_r21a_2_picked_test_run_makes_no_item(tmp_path: Path) -> None:
    data = tmp_path / "data"
    bank = run_ok("--data", data, "--replay", UNREADABLE / "filled")
    c = conn_of(data)
    try:
        before = {r["id"] for r in _items(c)}
    finally:
        c.close()
    out = run_ok("--data", data, "--replay", UNREADABLE / "picked", "--existing", bank["test_id"])
    assert out["test_id"] == bank["test_id"] and out["attempt_id"]
    c = conn_of(data)
    try:
        steps = c.execute(
            "SELECT COUNT(*) FROM steps WHERE run_id = ? AND node = 'transcribe_page'",
            (out["run_id"],),
        ).fetchone()[0]
        assert steps == 0
        # the picked run (no transcription) adds 0 unreadable_text items
        assert {r["id"] for r in _items(c)} == before
        assert _count(c, "picked_test_mismatch") == 0
    finally:
        c.close()


def test_scrub_check_passes_on_unreadable() -> None:
    code, _, err = etach("scrub", "--check", UNREADABLE)
    assert code == 0, err


# --- R21a.5 ----------------------------------------------------------------------------------


def test_r21a_5_unreadable_answer_is_unsure_and_graded_uncertain(tmp_path: Path) -> None:
    data = tmp_path / "data"
    out = run_ok("--data", data, "--replay", UNREADABLE / "filled")
    c = conn_of(data)
    try:
        content = _content(c, out["test_id"])
        q4 = content.sections[1].groups[0].questions[1]
        assert q4.answer_form == "word" and q4.printed_number == 4
        rows = c.execute("SELECT * FROM answers WHERE attempt_id = ?", (out["attempt_id"],))
        cols = [d[0] for d in rows.description]
        answers = [Answer.model_validate(dict(zip(cols, r, strict=True))) for r in rows]
        uncertain = c.execute(
            "SELECT question_id FROM review_items WHERE kind = 'uncertain_answer'"
        ).fetchall()
    finally:
        c.close()
    by_q = {a.question_id: a for a in answers}
    a4 = by_q[q4.id]
    assert a4.value == "???"  # kept as read
    assert a4.reading_unsure is True
    assert a4.confidence <= THRESHOLD - 0.01 + 1e-9
    assert [r[0] for r in uncertain] == [q4.id]  # the only "?" of the attempt
    assert all(not a.reading_unsure for q, a in by_q.items() if q != q4.id)

    # after Grade (the grade node's scoring): verdict uncertain, B.5 row 1
    now = datetime.now(UTC)
    keys = [
        AnswerKey(
            test_id=out["test_id"],
            question_id=q.id,
            accepted=["beautifully" if q.id == q4.id else "A"],
            reason_vi=None,
            source="teacher_edit",
            status="teacher_verified",
            confidence=None,
            updated_at=now,
        )
        for s in content.sections
        for g in s.groups
        for q in g.questions
    ]
    verdict = grade_answer(q4, a4, keys[3])
    assert (verdict.verdict, verdict.rule) == ("uncertain", 1)
    result = grade(content, answers, keys)
    graded = {a.question_id: a for a in result.answers}
    assert graded[q4.id].verdict == "uncertain" and graded[q4.id].points_awarded is None
    assert result.uncertain_points == round(q4.points, 4)
