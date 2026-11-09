"""Step 22.5.5a: the checker's answer on an unsure key, replayed (R22.5.5.1).

The disagreement scenario is built from the synthetic ``grade-synthetic/truncated-verify``
folder at test time: its first ``verify_key`` cassette becomes a complete answer that differs
from the AI key (``C`` where the key is ``B``) and the retry is dropped. No student data.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from .test_extract_replay import CASSETTES
from .test_grade_replay import replay_grade_scenario
from .test_grade_synthetic import question_ids

GS = CASSETTES / "grade-synthetic"
CHECKER_REASONING = "The sentence names one finished event, so the answer is C."


def _disagree_scenario(tmp: Path) -> Path:
    src = GS / "truncated-verify"
    out = tmp / "check-disagrees"
    shutil.copytree(src, out)
    manifest = json.loads((out / "grade.json").read_text(encoding="utf-8"))
    manifest["after"] = str((src / manifest["after"]).resolve())
    (out / "grade.json").write_text(json.dumps(manifest), encoding="utf-8")
    first = out / "004-verify_key.json"
    cassette = json.loads(first.read_text(encoding="utf-8"))
    cassette["status"] = "complete"
    cassette["response_text"] = json.dumps({"reasoning": CHECKER_REASONING, "answer": "C"})
    cassette["logprobs"] = None
    first.write_text(json.dumps(cassette, ensure_ascii=False), encoding="utf-8")
    (out / "005-verify_key.json").unlink()
    return out


def _checkers(data: Path) -> dict[str, dict[str, object] | None]:
    with sqlite3.connect(data / "app.db") as c:
        rows = c.execute("SELECT question_id, checker FROM answer_keys").fetchall()
    return {q: (json.loads(ch) if ch else None) for q, ch in rows}


def test_r22_5_5_1_disagreement_stores_the_checkers_answer(tmp_path: Path) -> None:
    data = tmp_path / "data"
    _, code, out = replay_grade_scenario(_disagree_scenario(tmp_path), data)
    assert code == 0 and out["status"] == "done", out
    q2 = question_ids(data)[1]
    checkers = _checkers(data)
    assert checkers[q2] == {
        "status": "disagreed",
        "answer": "C",
        "reasoning": CHECKER_REASONING,
    }
    assert all(v is None for q, v in checkers.items() if q != q2)
    with sqlite3.connect(data / "app.db") as c:
        status, accepted = c.execute(
            "SELECT status, accepted FROM answer_keys WHERE question_id = ?", (q2,)
        ).fetchone()
    assert status == "ai_uncertain" and json.loads(accepted) == ["B"]  # the first key is kept


def test_r22_5_5_1_failed_check_stores_did_not_finish(tmp_path: Path) -> None:
    data = tmp_path / "data"
    _, code, out = replay_grade_scenario(GS / "truncated-verify", data)
    assert code == 0 and out["status"] == "done", out
    q2 = question_ids(data)[1]
    checkers = _checkers(data)
    assert checkers[q2] == {"status": "did_not_finish", "answer": None, "reasoning": None}
    assert all(v is None for q, v in checkers.items() if q != q2)


def test_r22_5_5_1_agreeing_check_stores_nothing(tmp_path: Path) -> None:
    data = tmp_path / "data"
    _, code, out = replay_grade_scenario(GS / "first-grade", data)
    assert code == 0 and out["status"] == "done", out
    assert all(v is None for v in _checkers(data).values())


def _levels_scenario(tmp: Path) -> Path:
    """``first-grade`` with levels in its ``tag_skills`` replies: the first question of each
    section gets ``B1``, the others keep ``null`` (the fallback)."""
    src = GS / "first-grade"
    out = tmp / "tag-levels"
    shutil.copytree(src, out)
    manifest = json.loads((out / "grade.json").read_text(encoding="utf-8"))
    manifest["after"] = str((src / manifest["after"]).resolve())
    (out / "grade.json").write_text(json.dumps(manifest), encoding="utf-8")
    for path in out.glob("*-tag_skills-*.json"):
        cassette = json.loads(path.read_text(encoding="utf-8"))
        reply = json.loads(cassette["response_text"])
        for i, item in enumerate(reply["items"]):
            item["level"] = "B1" if i == 0 else None
        cassette["response_text"] = json.dumps(reply)
        path.write_text(json.dumps(cassette, ensure_ascii=False), encoding="utf-8")
    return out


def test_r22_5_5_3_tag_levels_are_stored_and_fall_back(tmp_path: Path) -> None:
    from etach.domain.levels import base_level
    from etach.store import db
    from etach.store.repos import tests

    data = tmp_path / "data"
    extracted, code, out = replay_grade_scenario(_levels_scenario(tmp_path), data)
    assert code == 0 and out["status"] == "done", out
    conn = db.connect(data / "app.db")
    try:
        rows = conn.execute("SELECT question_id, tag, level FROM question_tags").fetchall()
        levels = tests.list_question_levels(conn, extracted["test_id"])
        effective = tests.list_tag_levels(conn, extracted["test_id"])
    finally:
        conn.close()
    assert rows
    given = {q for q, _, lv in rows if lv == "B1"}
    missing = {q for q, _, lv in rows if lv is None}
    assert given and missing and not given & missing
    assert {lv for _, _, lv in rows} == {"B1", None}
    for qid, tag, lv in rows:
        assert levels[qid] == lv
        assert effective[qid][tag] == (lv or base_level(tag))


def test_r22_5_5_3_recorded_tags_without_levels_fall_back(tmp_path: Path) -> None:
    from etach.domain.levels import base_level
    from etach.store import db
    from etach.store.repos import tests

    data = tmp_path / "data"
    extracted, code, out = replay_grade_scenario(GS / "first-grade", data)
    assert code == 0 and out["status"] == "done", out
    conn = db.connect(data / "app.db")
    try:
        effective = tests.list_tag_levels(conn, extracted["test_id"])
        assert set(tests.list_question_levels(conn, extracted["test_id"]).values()) == {None}
    finally:
        conn.close()
    assert effective
    for tags in effective.values():
        assert all(lv == base_level(tag) and lv is not None for tag, lv in tags.items())
