"""M2: ``etach eval --graph grade`` (the grade metrics, the verdict truth, the teacher's
``verdicts`` field, the CSV header extension) on synthetic data only.

The replay test runs the committed synthetic fixtures in ``tests/fixtures_synth/grade/`` against
the synthetic cassettes in ``tests/cassettes/grade-eval/`` (made by ``make_grade_eval.py``; its
docstring lists the scripted answers the numbers below follow from)."""

import csv
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from etach.cli import main
from etach.domain.models import AnswerKey
from etach.eval import grade as grade_eval
from etach.eval.fixtures import Expected, FixtureError, load_fixture
from etach.eval.harness import (
    COLUMNS,
    GRADE_COLUMNS,
    NUMBER_COLUMNS,
    REPO_ROOT,
    HistoryHeaderMismatch,
    aggregate_row,
    append_history,
    pad_history,
)
from etach.eval.metrics import (
    Ratio,
    SavedKey,
    grade_key_counts,
    score_match,
    verdict_counts,
)

SIDECAR = Path(__file__).resolve().parents[3]
GRADE_SYNTH = SIDECAR / "tests" / "fixtures_synth" / "grade"
G1 = GRADE_SYNTH / "tuning" / "g1-mixed"
CASSETTES = SIDECAR / "tests" / "cassettes" / "grade-eval"


def _rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def _expected(**changes: Any) -> Expected:
    data = json.loads((G1 / "expected.json").read_text(encoding="utf-8"))
    data.update(changes)
    return Expected.model_validate(data)


# --- metrics ---------------------------------------------------------------------------------


def test_grade_key_counts_fast_verified_uncertain() -> None:
    expected = {"1": ["A"], "2": ["C"], "3": ["happiness"], "4": ["x", "y"], "5": ["B"]}
    saved = {
        "1": SavedKey(["a"], "ai_verified"),  # same after value_norm
        "2": SavedKey(["B"], "ai_uncertain"),  # wrong and uncertain
        "3": SavedKey(["happiness"], "ai_uncertain"),  # right but uncertain
        "4": SavedKey(["x"], "ai_unverified"),  # one of two accepted: not the same set
        # "5": no key row (ai_key_fast failed)
    }
    c = grade_key_counts(expected, saved)
    assert (c.fast.hits, c.fast.total) == (2, 5)  # 1, 3
    assert (c.verified.hits, c.verified.total) == (1, 5)  # 1 only: 3 is uncertain
    assert c.uncertain == 2
    assert grade_key_counts(None, saved).fast.total == 0


def test_verdict_counts_by_hand() -> None:
    truth = {"1": "correct", "2": "incorrect", "3": "incorrect", "4": "correct", "5": None}
    graph = {"1": "correct", "2": "incorrect", "3": "uncertain", "4": "incorrect"}
    c = verdict_counts(truth, graph, answered=["1", "2", "3", "4", "5"], judged=["4", "5"])
    assert (c.verdict.hits, c.verdict.total) == (2, 4)  # 3 is "?" = a miss; 5 has no truth
    assert (c.judge.hits, c.judge.total) == (0, 1)
    assert c.uncertain == 1 and c.no_truth == 1
    # a question with no verdict row at all counts as ungraded (a miss)
    c = verdict_counts({"9": "correct"}, {}, answered=["9"])
    assert (c.verdict.hits, c.verdict.total, c.uncertain) == (0, 1, 1)


def test_score_match() -> None:
    assert score_match(None, 3.0, graph_unsure=False) == Ratio(0, 0)  # no truth: not counted
    assert score_match(3.0, 3.0, graph_unsure=False) == Ratio(1, 1)
    assert score_match(3.0, 3.0, graph_unsure=True) == Ratio(0, 1)  # a "?" left: no match
    assert score_match(3.0, 2.5, graph_unsure=False) == Ratio(0, 1)
    assert score_match(3.0, None, graph_unsure=False) == Ratio(0, 1)


# --- the truth -------------------------------------------------------------------------------


def _truth(expected: Expected) -> tuple[dict[str, Any], grade_eval.Truth]:
    draft, ids = grade_eval.build_test(expected)
    answers = grade_eval.seed_answers(expected, draft.content, ids, "A-0001")
    keys = grade_eval.teacher_keys(expected, ids, "T-0001", datetime.now(UTC))
    overrides = {ids[k]: v for k, v in (expected.verdicts or {}).items()}
    truth = grade_eval.verdict_truth(draft.content, answers, keys, overrides)
    by_key = {qkey: truth.verdicts[qid] for qkey, qid in ids.items()}
    return {"ids": ids, "by_key": by_key, "draft": draft}, truth


def test_verdict_truth_from_rules_and_teacher() -> None:
    info, truth = _truth(_expected())
    ids = info["ids"]
    # rules: MCQ exact (1 right, 2 wrong); a near miss is incorrect (3); the rewrites go to the
    # judge and take the teacher's verdicts (4 correct, 5 incorrect)
    assert info["by_key"] == {
        "1": "correct",
        "2": "incorrect",
        "3": "incorrect",
        "4": "correct",
        "5": "incorrect",
    }
    assert truth.to_judge == [ids["4"], ids["5"]]
    assert truth.source[ids["1"]] == "rules" and truth.source[ids["4"]] == "teacher"
    # points (D13 v8.0): 10 / 5 graded questions → 1 and 4 are worth 2 each
    assert truth.total == 4.0
    assert info["draft"].points_possible == 10.0


def test_verdict_truth_without_teacher_verdicts() -> None:
    info, truth = _truth(_expected(verdicts=None))
    assert info["by_key"]["4"] is None and info["by_key"]["5"] is None  # judge answers
    assert truth.total is None  # incomplete: no exact-score truth
    # the teacher may also override a rule verdict
    info, truth = _truth(_expected(verdicts={"2": "correct"}))
    assert info["by_key"]["2"] == "correct" and info["by_key"]["4"] is None


def test_verdict_truth_no_key_is_unknown() -> None:
    info, truth = _truth(_expected(key={"1": ["A"]}, verdicts=None))
    assert info["by_key"]["1"] == "correct"
    assert all(info["by_key"][k] is None for k in ("2", "3", "4", "5"))
    assert truth.to_judge == []  # no key: rule 11 (uncertain), never judged


def test_build_test_matches_the_expected_question_keys() -> None:
    fx = load_fixture(GRADE_SYNTH / "tuning" / "g2-blank")
    draft, ids = grade_eval.build_test(fx.expected)
    assert list(ids) == ["3", "4"]  # the listening section is not stored
    sections = draft.content.sections
    assert [s.printed_title for s in sections] == ["II. GRAMMAR"]  # D2 (v1.21): titled by skill
    assert grade_eval.has_answers(fx.expected) is False
    # a section with no skill in expected.json is stored as "mixed"
    draft, _ = grade_eval.build_test(_expected())
    assert [s.skill for s in draft.content.sections] == ["grammar", "word_form", "mixed"]


# --- the teacher's verdicts field ------------------------------------------------------------


def test_expected_verdicts_field(tmp_path: Path) -> None:
    assert _expected().verdicts == {"4": "correct", "5": "incorrect"}
    data = json.loads((G1 / "expected.json").read_text(encoding="utf-8"))
    data.pop("verdicts")
    assert Expected.model_validate(data).verdicts is None  # optional, absent by default
    with pytest.raises(ValueError, match=r"verdicts: no .*question with key 99"):
        _expected(verdicts={"99": "correct"})
    with pytest.raises(ValueError):
        _expected(verdicts={"4": "partly"})
    folder = tmp_path / "tuning" / "bad"
    shutil.copytree(G1, folder)
    data["verdicts"] = {"6": "correct"}
    (folder / "expected.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(FixtureError, match="verdicts"):
        load_fixture(folder)


# --- the CSV header --------------------------------------------------------------------------


def test_committed_history_has_the_new_header() -> None:
    rows = _rows(REPO_ROOT / "eval-history.csv")
    assert tuple(rows[0]) == COLUMNS
    tail = GRADE_COLUMNS + NUMBER_COLUMNS
    assert COLUMNS[-len(tail) :] == tail  # appended at the end, in that order
    assert all(len(r) == len(COLUMNS) for r in rows)
    assert all(r[2] in ("extract", "grade") for r in rows[1:])
    # extract rows (all the rows written before M2) are padded: no grade value
    extract_rows = [r for r in rows[1:] if r[2] == "extract"]
    assert extract_rows
    g0, g1 = COLUMNS.index(GRADE_COLUMNS[0]), COLUMNS.index(GRADE_COLUMNS[-1]) + 1
    assert not any(any(r[g0:g1]) for r in extract_rows)


def test_pad_history_keeps_every_value(tmp_path: Path) -> None:
    new = GRADE_COLUMNS + NUMBER_COLUMNS
    old_header = COLUMNS[: -len(new)]
    path = tmp_path / "h.csv"
    lines = [",".join(old_header)]
    for i in range(2):
        cells = [f"v{i}_{j}" for j in range(len(old_header))]
        cells[10] = f'"a,b;{i}"'  # a quoted cell stays byte for byte
        lines.append(",".join(cells))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    before = path.read_text(encoding="utf-8").splitlines()
    assert pad_history(path) == 2
    after = path.read_text(encoding="utf-8").splitlines()
    assert after[0] == ",".join(COLUMNS)
    pad = "," * len(new)
    assert after[1:] == [line + pad for line in before[1:]]
    rows = _rows(path)
    assert rows[1][10] == "a,b;0" and all(len(r) == len(COLUMNS) for r in rows)
    assert pad_history(path) == 0  # already current
    # append_history pads an older header by itself, then appends
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    append_history(path, dict.fromkeys(COLUMNS, "x"))
    rows = _rows(path)
    assert len(rows) == 4 and rows[1][: len(old_header)] == next(csv.reader([lines[1]]))
    # a header that is not an older prefix is still refused
    other = tmp_path / "other.csv"
    other.write_text("timestamp,cer\n2026-01-01,0.1\n", encoding="utf-8")
    with pytest.raises(HistoryHeaderMismatch):
        append_history(other, {})
    assert other.read_text(encoding="utf-8") == "timestamp,cer\n2026-01-01,0.1\n"


def test_extract_rows_leave_the_grade_columns_empty() -> None:
    row = aggregate_row([], graph="extract", set_name="tuning", mode="x", models={}, commit="c")
    assert tuple(row) == COLUMNS
    assert all(row[c] == "" for c in GRADE_COLUMNS)


# --- the replay run --------------------------------------------------------------------------


def _grade_args(history: Path, *extra: str) -> list[str]:
    return [
        "eval", "--graph", "grade", "--set", "tuning", "--fixtures", str(GRADE_SYNTH),
        "--replay", str(CASSETTES), "--history", str(history), *extra,
    ]  # fmt: skip


def test_m2_grade_eval_replay_appends_one_full_row(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    history = tmp_path / "eval-history.csv"
    shutil.copy(REPO_ROOT / "eval-history.csv", history)
    before = _rows(history)
    keep = tmp_path / "keep"
    assert main(_grade_args(history, "--keep", str(keep))) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    after = _rows(history)
    assert len(after) == len(before) + 1
    assert after[: len(before)] == before  # the old rows are untouched
    row = dict(zip(after[0], after[-1], strict=True))
    assert set(row) == set(COLUMNS)
    assert (row["graph"], row["set"], row["mode"]) == ("grade", "tuning", "replay")
    assert row["n_fixtures"] == "2" and row["n_failed"] == "0"
    assert row["model_reasoning"] and row["model_vision"] == ""
    # keys (key run, 7 expected keys): fast misses only g1's 2; verified also loses g1's 3
    # (right but left ai_uncertain): 6/7 and 5/7
    assert row["key_accuracy_fast"] == "0.8571" and row["key_accuracy"] == "0.7143"
    assert row["key_n"] == "7" and row["key_uncertain_n"] == "2"
    # verdicts (g1's verdict run with the true key): 1 ✓, 2 ✗, 3 ✗ (near miss), 4 judged ✗
    # (the teacher says ✓), 5 judged ✗ (the teacher agrees): 4/5; the judge 1/2
    assert row["verdict_accuracy"] == "0.8000" and row["verdict_n"] == "5"
    assert row["judge_accuracy"] == "0.5000" and row["judge_n"] == "2"
    assert row["verdict_uncertain_n"] == "0" and row["verdict_no_truth_n"] == "0"
    # truth 1.0 (questions 1 and 4), graph 0.5: no exact match, over 1 answered fixture
    assert row["score_exact_match"] == "0.0000" and row["score_n"] == "1"
    # usage = the key runs: g1 (3 sections) + g2 (1) key calls; 5 + 2 verify calls
    assert row["ai_key_fast_calls"] == "4" and row["verify_key_calls"] == "7"
    assert row["judge_rewrites_calls"] == "2" and row["explain_calls"] == "2"
    assert row["weak_points_calls"] == "1" and row["tag_skills_calls"] == "4"
    assert row["total_calls"] == "20"  # 4 + 7 + 4 tag (one per graded section) + 2 + 2 + 1 summary
    assert "weak_points_summary=" in row["prompt_hashes"]
    # the extract-only columns stay empty
    for c in ("cer", "structure_overall", "answer_accuracy", "calibration", "key_mapping_n"):
        assert row[c] == "", c
    assert row["transcribe_page_calls"] == ""
    assert out["needs_verdict"] == 0 and out["verdict_accuracy"] == "0.8000"
    # metrics only: no fixture name, no student block, no answer text
    added = ",".join(after[-1])
    for text in ("Học Sinh", "8X1", "g1-mixed", "happyness", "so cold"):
        assert text not in added

    # --keep
    g1 = keep / "tuning" / "g1-mixed"
    grade = json.loads((g1 / "grade.json").read_text(encoding="utf-8"))
    verdicts = {v["question"]: v for v in grade["verdicts"]}
    assert verdicts["4"]["truth"] == "correct" and verdicts["4"]["truth_from"] == "teacher"
    assert verdicts["4"]["graph"] == "incorrect" and verdicts["4"]["judged"] is True
    assert verdicts["3"]["near_miss"] is True
    keys = {k["question"]: k for k in grade["keys"]}
    assert keys["3"]["status"] == "ai_uncertain" and keys["3"]["fast_ok"] is True
    assert keys["3"]["verified_ok"] is False
    assert grade["score"] == {
        "truth_total": 4.0,
        "graph_earned": 2.0,
        "graph_possible": 10.0,
        "graph_left_unsure": False,
        "match": False,
    }
    needs = json.loads((g1 / "needs-verdict.json").read_text(encoding="utf-8"))
    assert [n["question"] for n in needs["items"]] == ["4", "5"]
    assert needs["missing"] == 0 and needs["template"] == {}
    expl = json.loads((g1 / "explanations.json").read_text(encoding="utf-8"))
    assert [e["question"] for e in expl] == ["2", "3", "4", "5"]
    assert expl[0]["correct_answer"] == "C" and expl[0]["student_answer"] == "B"
    assert "Synthetic question two" in expl[0]["question_text"]
    calls = json.loads((g1 / "llm_calls.json").read_text(encoding="utf-8"))
    assert len(calls["key_run"]) == 16 and len(calls["verdict_run"]) == 10  # 3 tag calls each
    metrics = json.loads((g1 / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["metrics"]["verdict_accuracy"] == "0.8000"
    g2 = keep / "tuning" / "g2-blank"
    assert json.loads((g2 / "explanations.json").read_text(encoding="utf-8")) == []
    summary = json.loads((keep / "tuning" / "summary.json").read_text(encoding="utf-8"))
    assert summary["graph"] == "grade" and summary["key_accuracy"] == "0.7143"


def test_needs_verdict_listed_when_the_teacher_has_not_judged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "fixtures"
    folder = root / "tuning" / "g1-mixed"
    shutil.copytree(G1, folder)
    data = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
    data.pop("verdicts")
    (folder / "expected.json").write_text(json.dumps(data), encoding="utf-8")
    history = tmp_path / "h.csv"
    keep = tmp_path / "keep"
    args = _grade_args(history, "--keep", str(keep))
    args[args.index(str(GRADE_SYNTH))] = str(root)
    assert main(args) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out.strip().splitlines()[-1])["needs_verdict"] == 2
    assert "2 answer(s) need the teacher's verdict" in captured.err
    assert "so cold" not in captured.out + captured.err  # counts only, no answer text
    row = dict(zip(*_rows(history)[:2], strict=True))
    assert row["verdict_n"] == "3" and row["verdict_no_truth_n"] == "2"
    assert row["judge_n"] == "0" and row["judge_accuracy"] == ""
    assert row["score_n"] == "0" and row["score_exact_match"] == ""
    needs = json.loads((keep / "tuning" / "g1-mixed" / "needs-verdict.json").read_text("utf-8"))
    assert needs["missing"] == 2 and needs["template"] == {"4": "", "5": ""}


def test_grade_preflight_checks_the_fixtures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([*_grade_args(tmp_path / "h.csv"), "--preflight"]) == 0
    pre = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert pre["preflight"] == "ok" and pre["n_fixtures"] == 2
    assert not (tmp_path / "h.csv").exists()


def test_teacher_keys_are_teacher_verified() -> None:
    exp = _expected()
    _, ids = grade_eval.build_test(exp)
    keys = grade_eval.teacher_keys(exp, ids, "T-0001", datetime.now(UTC))
    assert all(isinstance(k, AnswerKey) for k in keys)
    assert {(k.source, k.status) for k in keys} == {("teacher_edit", "teacher_verified")}


def test_list_verdicts_runs_no_model(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--list-verdicts --keep DIR``: the needs-verdict.json files before any run (no Ollama,
    no cassettes); stdout has counts only."""
    root = tmp_path / "fixtures"
    shutil.copytree(GRADE_SYNTH / "tuning", root / "tuning")
    path = root / "tuning" / "g1-mixed" / "expected.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["verdicts"] = {"4": "correct"}
    path.write_text(json.dumps(data), encoding="utf-8")
    keep = tmp_path / "keep"
    args = ["eval", "--graph", "grade", "--set", "tuning", "--fixtures", str(root)]
    assert main([*args, "--list-verdicts"]) == 2
    assert "--list-verdicts needs --keep" in capsys.readouterr().err
    assert main([*args, "--list-verdicts", "--keep", str(keep)]) == 0
    out = capsys.readouterr().out
    assert json.loads(out.strip().splitlines()[-1])["needs_verdict"] == 1
    assert "so cold" not in out
    needs = json.loads((keep / "tuning" / "g1-mixed" / "needs-verdict.json").read_text("utf-8"))
    assert [n["question"] for n in needs["items"]] == ["4", "5"]
    assert needs["items"][0]["teacher_verdict"] == "correct"
    assert needs["template"] == {"5": ""} and needs["missing"] == 1
    blank = json.loads((keep / "tuning" / "g2-blank" / "needs-verdict.json").read_text("utf-8"))
    assert blank["items"] == [] and blank["missing"] == 0
    extract = ["eval", "--graph", "extract", "--set", "tuning", "--fixtures", str(root)]
    assert main([*extract, "--list-verdicts"]) == 2
    assert "--list-verdicts is for --graph grade" in capsys.readouterr().err
