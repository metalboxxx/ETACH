"""Step 18: grade scenarios. ``etach record --after <extract dir> -- grade …`` writes ``grade.json``
(:class:`etach.llm.cassettes.GradeScenario`), and a replay rebuilds the run from it: replay the
extract scenario it names into a fresh data folder, then ``etach grade --replay`` the target from
that replay's output. ``tests/cassettes/s1-grade/`` is recorded live by the teacher
(``docs/initial-plan/phases-testing/step18-recording.md``); until then its test skips.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from etach.graphs.grade import GradeThresholds
from etach.llm.cassettes import (
    GRADE_MANIFEST_NAME,
    MANIFEST_NAME,
    grade_scenario_extract_dir,
    load_grade_scenario,
)

from .test_extract_replay import (
    CASSETTES,
    RECORDED_WITH_TILES,
    conn_of,
    count,
    etach,
    need_s1,
    run_ok,
    tiles_on,
)

S1_GRADE = CASSETTES / "s1-grade"


def rule_before_22_6_2(data: Path) -> Path:
    """``[extract] blank_share = 0``: the recorded S1 paper (1 of 34 answers read sure) is blank
    under the 20% rule of step 22.6.2; its grade recording needs the attempt it was made on."""
    data.mkdir(parents=True, exist_ok=True)
    toml = data / "models.toml"
    text = toml.read_text(encoding="utf-8") if toml.is_file() else ""
    if "[extract]\n" in text:
        text = text.replace("[extract]\n", "[extract]\nblank_share = 0\n", 1)
    else:
        text += "\n[extract]\nblank_share = 0\n"
    toml.write_text(text, encoding="utf-8")
    return data


def replay_grade_scenario(folder: Path, data: Path) -> tuple[dict[str, Any], int, dict[str, Any]]:
    """Rebuild a recorded grade scenario: (the extract replay's output, grade exit code, its
    output)."""
    scenario = load_grade_scenario(folder)
    assert scenario is not None, f"{folder} has no {GRADE_MANIFEST_NAME}"
    extract_dir = grade_scenario_extract_dir(folder, scenario)
    if extract_dir.name in RECORDED_WITH_TILES:
        tiles_on(data)
    rule_before_22_6_2(data)
    extracted = run_ok("--data", data, "--replay", extract_dir)
    target = (
        ["--attempt", extracted["attempt_id"]]
        if scenario.target == "attempt"
        else ["--test", extracted["test_id"]]
    )
    code, out, err = etach("grade", "--data", data, *target, "--replay", folder)
    assert out is not None, err
    return extracted, code, out


def test_record_grade_writes_the_scenario(tmp_path: Path) -> None:
    """The record wrapper's argument path, without a model: the grade run itself fails on an
    empty replay folder, but ``grade.json`` is written before it starts."""
    s1 = need_s1()
    extract = tmp_path / "cassettes" / "s1"
    extract.mkdir(parents=True)
    for f in s1.iterdir():
        if f.suffix in (".json", ".png"):
            shutil.copy2(f, extract / f.name)
    assert (extract / MANIFEST_NAME).is_file()
    data = rule_before_22_6_2(tmp_path / "data")
    extracted = run_ok("--data", data, "--replay", extract)
    empty = tmp_path / "empty"
    empty.mkdir()
    out_dir = tmp_path / "cassettes" / "s1-grade"

    code, _, err = etach(
        "record", "--out", out_dir, "--", "grade", "--data", data,
        "--attempt", extracted["attempt_id"], "--replay", empty,
    )  # fmt: skip
    assert code != 0 and "--after" in err  # a grade scenario must name its extract scenario
    assert not (out_dir / GRADE_MANIFEST_NAME).exists()
    code, _, err = etach("record", "--out", out_dir, "--after", empty, "--", "grade",
                         "--data", data, "--attempt", extracted["attempt_id"])  # fmt: skip
    assert code != 0 and MANIFEST_NAME in err

    code, _, err = etach(
        "record", "--out", out_dir, "--after", extract, "--", "grade", "--data", data,
        "--attempt", extracted["attempt_id"], "--replay", empty,
    )  # fmt: skip
    assert code != 0 and "no cassettes" in err  # no model ran
    scenario = load_grade_scenario(out_dir)
    assert scenario is not None
    assert scenario.after == "../s1" and scenario.target == "attempt"
    assert scenario.recorded_attempt_id == extracted["attempt_id"]
    assert scenario.recorded_test_id == extracted["test_id"]
    assert grade_scenario_extract_dir(out_dir, scenario) == extract.resolve()


# What the teacher's recording (da97a0b) gives on replay: the score, and the keys by status.
# 22.5.6 reads each page's own questions only (accepted limit): 2 of the 3 recorded readings sat
# on another page than their question, so 1 reading is left (was 0.2941 / 9.7059 / 15-5-14).
S1_GRADE_SCORE = (0.0, 10.0)  # 0 correct, of 34 graded questions (D13 v8.0)
S1_GRADE_UNCERTAIN_POINTS = 10.0  # 34 x 10/34: all 34 uncertain (33 unsure readings, 1 key)
S1_GRADE_KEY_STATUS = {"ai_unverified": 16, "ai_verified": 2, "ai_uncertain": 16}
VERIFY_SKILLS = {"pronunciation", "stress"}  # plan B.7 "a pronunciation or stress item"


def _norm(v: str) -> str:
    """A plain comparison form (trim, collapse spaces, casefold), written here rather than
    imported, so the expected B.7 set does not reuse the code under test."""
    return " ".join(v.split()).casefold()


def _graded_questions(c: sqlite3.Connection) -> dict[str, tuple[str, float]]:
    """Graded question ID -> (its section's skill, its points)."""
    content = json.loads(c.execute("SELECT content FROM tests").fetchone()[0])
    return {
        q["id"]: (s["skill"], q["points"])
        for s in content["sections"]
        if s.get("graded", True)
        for g in s["groups"]
        for q in g["questions"]
    }


def expected_b7(c: sqlite3.Connection, margin_threshold: float) -> dict[str, list[str]]:
    """Plan B.7 over the replayed state: question ID -> the clauses that fire. Every key here
    is one ``ai_key_fast`` made in this run (``ai_unverified``); ``verify_key`` changes only
    the status, so ``accepted`` and the margin (``confidence``) are still the ones it saw."""
    questions = _graded_questions(c)
    given = {
        qid: (override if override is not None else value)
        for qid, value, override in c.execute(
            "SELECT question_id, value, teacher_override FROM answers"
        )
    }
    out: dict[str, list[str]] = {}
    for qid, accepted, margin in c.execute(
        "SELECT question_id, accepted, confidence FROM answer_keys"
    ):
        why = []
        if margin is None or margin < margin_threshold:
            why.append("margin")
        if questions[qid][0] in VERIFY_SKILLS:
            why.append("pron_stress")
        value = _norm(given.get(qid) or "")
        if value and value not in {_norm(a) for a in json.loads(accepted)}:
            why.append("answer_ne_key")  # non-blank and != the key (blank: v2.7)
        if why:
            out[qid] = why
    return out


def test_recorded_s1_grade(tmp_path: Path) -> None:
    """R18.2 on the teacher's recording of the S1 grade run."""
    if load_grade_scenario(S1_GRADE) is None:
        pytest.skip(
            "tests/cassettes/s1-grade/ is not recorded yet: the teacher records it live with"
            " docs/initial-plan/phases-testing/step18-recording.md"
        )
    data = tmp_path / "data"
    extracted, code, out = replay_grade_scenario(S1_GRADE, data)
    assert code == 0 and out["status"] == "done", out
    attempt_id = extracted["attempt_id"]
    assert out["attempt_id"] == attempt_id
    with conn_of(data) as c:
        # Every key came from ai_key_fast in this run, so each started ai_unverified.
        assert {r[0] for r in c.execute("SELECT DISTINCT source FROM answer_keys")} == {"ai"}
        statuses = dict(c.execute("SELECT question_id, status FROM answer_keys").fetchall())
        questions = _graded_questions(c)
        assert set(statuses) == set(questions)
        expected = expected_b7(c, GradeThresholds().key_margin)
        # The keys leave ai_unverified exactly for the B.7 cases, to ai_verified / ai_uncertain.
        moved = {q for q, st in statuses.items() if st != "ai_unverified"}
        assert moved == set(expected)
        assert {statuses[q] for q in moved} <= {"ai_verified", "ai_uncertain"}
        assert dict(Counter(statuses.values())) == S1_GRADE_KEY_STATUS
        # verify_key asked about exactly those questions (a retry repeats the same question).
        requests = [
            r[0]
            for r in c.execute(
                "SELECT l.request FROM llm_calls l JOIN steps s ON s.id = l.step_id"
                " WHERE s.run_id = ? AND s.node = 'verify_key'",
                (out["run_id"],),
            )
        ]
        assert {q for q in statuses for req in requests if q in req} == set(expected)
        # The score is the recorded one, and agrees with the verdicts and the question points.
        assert (out["score_earned"], out["score_possible"]) == S1_GRADE_SCORE
        verdicts = dict(
            c.execute(
                "SELECT question_id, verdict FROM answers WHERE attempt_id = ?", (attempt_id,)
            ).fetchall()
        )
        assert sum(p for _, p in questions.values()) == pytest.approx(S1_GRADE_SCORE[1])
        earned = sum(questions[q][1] for q, v in verdicts.items() if v == "correct")
        assert earned == pytest.approx(S1_GRADE_SCORE[0], abs=1e-4)
        # One grade report, with 3-5 teacher questions.
        assert count(c, "SELECT COUNT(*) FROM grade_reports") == 1
        report = c.execute(
            "SELECT teacher_questions, uncertain_points FROM grade_reports WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
        assert 3 <= len(json.loads(report[0])) <= 5
        assert report[1] == pytest.approx(S1_GRADE_UNCERTAIN_POINTS)
        # The attempt is graded with that score; the grade run is done.
        attempt = c.execute(
            "SELECT status, score_earned, score_possible FROM attempts WHERE id = ?",
            (attempt_id,),
        ).fetchone()
        assert tuple(attempt) == ("graded", *S1_GRADE_SCORE)
        run = c.execute("SELECT kind, status FROM runs WHERE id = ?", (out["run_id"],)).fetchone()
        assert tuple(run) == ("grade", "done")


def test_r18_11_grade_cassettes_signed_off() -> None:
    """R18.11: the teacher's commit "<bust> sign-off: cassettes grade" exists and touches the
    recorded set (``tests/cassettes/s1-grade/``)."""
    git = ["git", "-C", str(S1_GRADE)]
    found = subprocess.run(
        [*git, "log", "--format=%H %s", "--grep", "sign-off: cassettes grade"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.splitlines()  # fmt: skip
    subject = "\N{BUST IN SILHOUETTE} sign-off: cassettes grade"
    signed = [ln.split(" ", 1)[0] for ln in found if ln.split(" ", 1)[1].startswith(subject)]
    assert signed, found
    touched = subprocess.run(
        [*git, "show", "--name-only", "--format=", signed[0]],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.splitlines()  # fmt: skip
    assert any(p.startswith("sidecar/tests/cassettes/s1-grade/") for p in touched), touched
