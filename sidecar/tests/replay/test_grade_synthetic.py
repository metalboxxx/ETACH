"""Step 18 (part C): the SYNTHETIC grade scenarios in ``tests/cassettes/grade-synthetic/``
(made by ``make_synthetic_grade.py``; read its docstring for what each one holds).

Each test replays the extract scenario and then the grade cassettes through the real CLI, and
counts the model calls per graph node from the run's ``llm_calls`` rows (a validation retry is
a second row of the same call).
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from .make_synthetic_grade import teacher_key
from .test_extract_replay import CASSETTES, etach, run_ok
from .test_grade_replay import replay_grade_scenario

GS = CASSETTES / "grade-synthetic"
S1L = CASSETTES / "extract-synthetic" / "s1-like"
GRADE_NODES = (
    "ai_key_fast",
    "verify_key",
    "tag_skills",
    "judge_rewrites",
    "explain",
    "weak_points",
)


def _db(data: Path) -> sqlite3.Connection:
    return sqlite3.connect(data / "app.db")


def calls(data: Path, run_id: str) -> Counter[str]:
    """``llm_calls`` rows of one run, by the graph node that made them."""
    with _db(data) as c:
        rows = c.execute(
            "SELECT s.node FROM llm_calls l JOIN steps s ON s.id = l.step_id WHERE s.run_id = ?",
            (run_id,),
        ).fetchall()
    return Counter(r[0] for r in rows)


def count(data: Path, sql: str, *args: Any) -> int:
    with _db(data) as c:
        return int(c.execute(sql, args).fetchone()[0])


def question_ids(data: Path) -> list[str]:
    with _db(data) as c:
        content = json.loads(c.execute("SELECT content FROM tests").fetchone()[0])
    return [q["id"] for s in content["sections"] for g in s["groups"] for q in g["questions"]]


def grade(data: Path, attempt_id: str, scenario: str) -> dict[str, Any]:
    code, out, err = etach(
        "grade", "--data", data, "--attempt", attempt_id, "--replay", GS / scenario
    )
    assert code == 0 and out is not None and out["status"] == "done", (out, err)
    return out


def key_row(data: Path, qid: str) -> tuple[list[str], str]:
    with _db(data) as c:
        accepted, status = c.execute(
            "SELECT accepted, status FROM answer_keys WHERE question_id = ?", (qid,)
        ).fetchone()
    return json.loads(accepted), status


def test_r18_3_key_photo_makes_no_ai_key(tmp_path: Path) -> None:
    data = tmp_path / "data"
    extracted, code, out = replay_grade_scenario(GS / "key-photo", data)
    assert code == 0 and out["status"] == "done", out
    n = calls(data, out["run_id"])
    assert n["ai_key_fast"] == 0
    assert n["weak_points"] == 1  # the run did grade the attempt
    with _db(data) as c:
        sources = {r[0] for r in c.execute("SELECT source FROM answer_keys")}
    assert sources == {"from_key_photo"}
    assert count(data, "SELECT COUNT(*) FROM grade_reports WHERE attempt_id = ?",
                 extracted["attempt_id"]) == 1  # fmt: skip


def test_r18_4_blank_test_writes_key_tags_notes_no_report(tmp_path: Path) -> None:
    data = tmp_path / "data"
    extracted, code, out = replay_grade_scenario(GS / "blank-key", data)
    assert code == 0 and out["status"] == "done", out
    assert out["attempt_id"] is None
    qids = question_ids(data)
    n = calls(data, out["run_id"])
    assert n["ai_key_fast"] == 6  # one per section with questions
    assert n["tag_skills"] == 6  # one per graded section (step 22.5.4)
    assert n["explain"] == 0 and n["weak_points"] == 0
    assert count(data, "SELECT COUNT(*) FROM answer_keys WHERE test_id = ?",
                 extracted["test_id"]) == len(qids)  # fmt: skip
    assert count(data, "SELECT COUNT(DISTINCT question_id) FROM question_tags") == len(qids)
    with _db(data) as c:
        meta = json.loads(c.execute("SELECT meta FROM tests").fetchone()[0])
    assert "test_difficulty_notice_comment_by_ai" not in meta  # step 22.5.4: the notes are gone
    assert count(data, "SELECT COUNT(*) FROM grade_reports") == 0


def test_r18_5_second_student_s2_path(tmp_path: Path) -> None:
    data = tmp_path / "data"
    first = run_ok("--data", data, "--replay", S1L)
    graded = grade(data, first["attempt_id"], "first-grade")
    n1 = calls(data, graded["run_id"])
    assert n1["ai_key_fast"] == 3 and n1["explain"] == 1  # the first student paid for them
    for qid in question_ids(data):  # the teacher verifies every key (key editor)
        accepted, _ = key_row(data, qid)
        teacher_key(data, first["test_id"], qid, accepted[0])
    assert count(data, "SELECT COUNT(*) FROM explanations") == 1  # unchanged keys keep it

    second = run_ok("--data", data, "--replay", GS / "student-b-extract",
                    "--existing", first["test_id"])  # fmt: skip
    assert second["test_id"] == first["test_id"]
    assert second["attempt_id"] != first["attempt_id"]
    out = grade(data, second["attempt_id"], "student-b-grade")
    n = calls(data, out["run_id"])
    assert n["ai_key_fast"] == 0
    assert n["verify_key"] == 0
    assert n["tag_skills"] == 0
    assert n["explain"] == 0
    assert sum(n.values()) == n["weak_points"] == 1  # only the summary
    # the second student's wrong answer reuses the cached explanation
    assert count(data, "SELECT COUNT(*) FROM explanations") == 1
    wrong = "SELECT COUNT(*) FROM answers WHERE attempt_id = ? AND verdict = 'incorrect'"
    assert count(data, wrong, second["attempt_id"]) == 1
    assert out["score_earned"] == graded["score_earned"] == 8.3333  # 5 of 6 x 10/6 (D13 v8.0)


def test_r18_6_truncated_verify_key(tmp_path: Path) -> None:
    data = tmp_path / "data"
    extracted, code, out = replay_grade_scenario(GS / "truncated-verify", data)
    assert code == 0 and out["status"] == "done", out
    n = calls(data, out["run_id"])
    assert n["verify_key"] == 2  # one call: the truncated answer, then the retry, truncated too
    with _db(data) as c:
        statuses = [r[0] for r in c.execute(
            "SELECT l.status FROM llm_calls l JOIN steps s ON s.id = l.step_id"
            " WHERE s.run_id = ? AND s.node = 'verify_key'", (out["run_id"],))]  # fmt: skip
        uncertain = c.execute(
            "SELECT question_id FROM answer_keys WHERE status = 'ai_uncertain'"
        ).fetchall()
        reviews = c.execute(
            "SELECT question_id FROM review_items WHERE kind = 'uncertain_key'"
        ).fetchall()
    assert statuses == ["invalid", "invalid"]
    q2 = question_ids(data)[1]
    assert uncertain == [(q2,)]
    assert reviews == [(q2,)]
    assert count(data, "SELECT COUNT(*) FROM grade_reports WHERE attempt_id = ?",
                 extracted["attempt_id"]) == 1  # fmt: skip


def test_r18_8_regrade_after_key_verified(tmp_path: Path) -> None:
    data = tmp_path / "data"
    ex = run_ok("--data", data, "--replay", S1L)
    before = grade(data, ex["attempt_id"], "first-grade")
    assert (before["score_earned"], before["score_possible"]) == (8.3333, 10.0)
    q1, q2 = question_ids(data)[:2]
    teacher_key(data, ex["test_id"], q1, "C")  # the student's A is now wrong

    after = grade(data, ex["attempt_id"], "regrade-after-verify")
    n = calls(data, after["run_id"])
    assert n["explain"] == 1
    assert n["ai_key_fast"] == n["verify_key"] == n["tag_skills"] == 0
    with _db(data) as c:
        (request,) = c.execute(
            "SELECT l.request FROM llm_calls l JOIN steps s ON s.id = l.step_id"
            " WHERE s.run_id = ? AND s.node = 'explain'",
            (after["run_id"],),
        ).fetchone()
        explained = {r[0] for r in c.execute("SELECT question_id FROM explanations")}
    assert q1 in request and q2 not in request  # only the re-keyed question
    assert explained == {q1, q2}
    assert (after["score_earned"], after["score_possible"]) == (6.6667, 10.0)
    assert key_row(data, q1) == (["C"], "teacher_verified")
