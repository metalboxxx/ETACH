"""M1 tooling: ``etach eval --keep DIR`` (per-fixture outputs and mismatches) and ``--preflight``,
on the committed synthetic fixture and its replay cassettes."""

import csv
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from etach.cli import main
from etach.eval.harness import COLUMNS

SIDECAR = Path(__file__).resolve().parents[3]
SYNTH = SIDECAR / "tests" / "fixtures_synth"
CASSETTES = SIDECAR / "tests" / "cassettes" / "extract-synthetic"


def _args(fixtures: Path, history: Path, *extra: str) -> list[str]:
    return [
        "eval",
        "--graph",
        "extract",
        "--set",
        "tuning",
        "--fixtures",
        str(fixtures),
        "--replay",
        str(CASSETTES),
        "--history",
        str(history),
        "--photo-reader",
        "vision",  # the cassettes were recorded with the vision reader (R22.5.7.7)
        *extra,
    ]


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _last_row(history: Path) -> dict[str, str]:
    with history.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    return dict(zip(rows[0], rows[-1], strict=True))


def test_keep_writes_per_fixture_outputs(tmp_path: Path) -> None:
    history = tmp_path / "h.csv"
    keep = tmp_path / "keep"
    assert main(_args(SYNTH, history, "--keep", str(keep))) == 0
    folder = keep / "tuning" / "s1-like"
    assert sorted(p.name for p in folder.iterdir()) == [
        "answers.json",
        "keys.json",
        "llm_calls.json",
        "metrics.json",
        "pages.json",
        "test.json",
    ]
    # the set summary holds exactly the CSV row
    row = _last_row(history)
    summary = _load(keep / "tuning" / "summary.json")
    assert list(summary) == list(COLUMNS)
    assert summary == row
    # the saved test, as JSON
    test = _load(folder / "test.json")
    # D2 (v1.21): a bare numeral is titled by the section skill
    titles = [s["printed_title"].split(".")[0] for s in test["content"]["sections"]]
    assert titles == ["I", "II", "III"]
    # the answers read, keyed by question, with confidence and the ? flag
    answers = _load(folder / "answers.json")
    assert [a["question"] for a in answers] == ["1", "2", "3", "4", "5", "6"]
    assert all("confidence" in a and "reading_unsure" in a for a in answers)
    assert [a["value"] for a in answers] == ["A"] * 6
    assert _load(folder / "keys.json") == []
    # the fixture's own metrics: the same names and format as the CSV (one fixture = the row)
    metrics = _load(folder / "metrics.json")
    assert metrics["fixture"] == "tuning/s1-like" and metrics["status"] == "done"
    for name, value in metrics["metrics"].items():
        assert value == row[name], name
    assert {"cer", "stimulus_cer", "structure_overall", "answer_accuracy", "calibration"} <= set(
        metrics["metrics"]
    )
    assert metrics["counts"]["answers"]["accuracy"] == {"hits": 6, "total": 6}
    assert metrics["counts"]["structure"]["question_match"] == {"hits": 6, "total": 6}
    # nothing wrong on the synthetic replay
    mm = metrics["mismatches"]
    assert mm["structure"] == [] and mm["answers"] == [] and mm["keys"] == []
    assert mm["extra_questions"] == [] and mm["flagged_correct"] == []
    assert mm["sections"]["expected"] == [["I", 2], ["II", 2], ["III", 2]]
    # D2 (v1.21): the app titles a bare numeral by its section skill
    assert mm["sections"]["got"] == [[f"{n}. GRAMMAR", 2] for n in ("I", "II", "III")]
    # per-node usage, as in the CSV's node columns
    usage = metrics["usage"]
    assert usage["transcribe_page"]["calls"] == int(row["transcribe_page_calls"]) == 3
    assert usage["read_answers_page"]["calls"] == 3
    assert all(set(u) == {"tokens_in", "tokens_out", "calls", "ms"} for u in usage.values())


def test_b4_keep_writes_the_runs_llm_calls_and_page_results(tmp_path: Path) -> None:
    """B4: the run's data folder is deleted, so ``--keep`` saves its model calls and the
    per-page results before merge."""
    history = tmp_path / "h.csv"
    keep = tmp_path / "keep"
    assert main(_args(SYNTH, history, "--keep", str(keep))) == 0
    folder = keep / "tuning" / "s1-like"
    calls = _load(folder / "llm_calls.json")
    metrics = _load(folder / "metrics.json")
    # one entry per call, matching the per-node usage
    by_node: dict[str, int] = {}
    for c in calls:
        by_node[c["node"]] = by_node.get(c["node"], 0) + 1
    assert by_node == {node: u["calls"] for node, u in metrics["usage"].items() if u["calls"]}
    assert by_node["transcribe_page"] == 3 and by_node["read_answers_page"] == 3
    first = calls[0]
    assert {
        "node",
        "item",  # the call's own label when it has one (a tile: "p2 top"), else the step's
        "step_item",
        "try_no",
        "step_status",
        "call_id",
        "status",
        "role",
        "model",
        "prompt_hash",
        "tokens_in",
        "tokens_out",
        "ms",
        "created_at",
        "logprob_count",
        "request",
        "response_text",
        "thinking_text",
    } == set(first)
    assert all(c["status"] == "complete" and c["response_text"] for c in calls)
    assert all(c["request"]["truncate"] is False for c in calls)  # B1
    assert all("logprobs" not in c for c in calls)
    assert metrics["call_status"] == {node: {"complete": n} for node, n in by_node.items()}
    # the per-page results: each complete page call, parsed
    pages = _load(folder / "pages.json")
    assert [(p["node"], p["call_id"]) for p in pages] == [
        (c["node"], c["call_id"])
        for c in calls
        if c["node"] in ("transcribe_page", "retranscribe_tiles", "read_answers_page")
    ]
    transcribed = [p for p in pages if p["node"] == "transcribe_page"]
    assert all(isinstance(p["result"], dict) and "sections" in p["result"] for p in transcribed)
    assert [p["item"] for p in transcribed] == [c["item"] for c in calls[:3]]


def test_keep_lists_the_questions_that_fail(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    folder = root / "tuning" / "s1-like"
    shutil.copytree(SYNTH / "tuning" / "s1-like", folder)
    data = _load(folder / "expected.json")
    data["answers"]["2"] = "B"  # the student "wrote" B; the replay reads A
    q3 = data["sections"][1]["groups"][0]["questions"][0]
    assert q3["printed_number"] == 3
    q3["type"] = "gap_fill"
    q3["stem"] = q3["stem"] + " ____"
    data["key"] = {"1": ["A"]}  # no key photo, so nothing is saved for it
    (folder / "expected.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    history = tmp_path / "h.csv"
    keep = tmp_path / "keep"
    assert main(_args(root, history, "--keep", str(keep))) == 0
    metrics = _load(keep / "tuning" / "s1-like" / "metrics.json")
    mm = metrics["mismatches"]
    assert mm["answers"] == [
        {
            "question": "2",
            "expected": "B",
            "got": "A",
            "read": True,
            "reading_unsure": False,
            "confidence": mm["answers"][0]["confidence"],
        }
    ]
    [s3] = mm["structure"]
    assert s3["question"] == "3"
    assert s3["problems"] == ["types", "blanks"]
    assert 0 < s3["text_cer"] < 1
    assert s3["expected"]["answer_form"] == "word" and s3["got"]["answer_form"] == "choice"
    assert mm["keys"] == [{"question": "1", "expected": ["A"], "got": None, "from_key_photo": None}]
    assert metrics["metrics"]["answer_accuracy"] == _last_row(history)["answer_accuracy"]
    assert metrics["counts"]["answers"]["accuracy"] == {"hits": 5, "total": 6}


def test_without_keep_nothing_extra(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    history = tmp_path / "h.csv"
    assert main(_args(SYNTH, history)) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["h.csv"]
    assert " -> " not in capsys.readouterr().err


def test_preflight_runs_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    history = tmp_path / "h.csv"
    keep = tmp_path / "keep"
    assert main(_args(SYNTH, history, "--keep", str(keep), "--preflight")) == 0
    assert not history.exists() and not keep.exists()
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["preflight"] == "ok" and line["mode"] == "replay"
    assert line["n_fixtures"] == 1 and line["model_vision"]
    # a missing fixture set still fails the preflight
    assert main(_args(tmp_path / "none", history, "--preflight")) == 2


def test_vram_mb_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    history = tmp_path / "h.csv"
    vram = tmp_path / "peak.txt"
    vram.write_text("5321\n", encoding="utf-8")
    assert main(_args(SYNTH, history, "--vram-mb", "100", "--vram-mb-file", str(vram))) == 0
    assert _last_row(history)["vram_peak_mb"] == "5321"
    # an empty or missing file falls back to --vram-mb, with a warning
    vram.write_text("", encoding="utf-8")
    assert main(_args(SYNTH, history, "--vram-mb", "100", "--vram-mb-file", str(vram))) == 0
    assert _last_row(history)["vram_peak_mb"] == "100"
    assert "--vram-mb-file" in capsys.readouterr().err
    missing = tmp_path / "none.txt"
    assert main(_args(SYNTH, history, "--vram-mb-file", str(missing))) == 0
    assert _last_row(history)["vram_peak_mb"] == ""


@pytest.mark.parametrize("tiles", [False, True])
def test_tiles_flag_turns_retranscribe_tiles_on_for_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tiles: bool
) -> None:
    """Speed bundle 1: ``--tiles`` writes ``[extract] retranscribe_tiles = true`` into each
    fixture's data folder (the graph reads it), and the row's mode says so; without it the
    run uses the default (off)."""
    from etach.llm import config as config_mod

    seen: list[bool] = []
    real = config_mod.load_models_config

    def spy(source: Any) -> Any:
        cfg = real(source)
        seen.append(cfg.extract.retranscribe_tiles)
        return cfg

    monkeypatch.setattr(config_mod, "load_models_config", spy)
    history = tmp_path / "h.csv"
    extra = ["--tiles"] if tiles else []
    assert main(_args(SYNTH, history, *extra)) == 0
    assert seen and set(seen) == {tiles}
    assert _last_row(history)["mode"] == ("replay+tiles" if tiles else "replay")


def _two_fixtures(tmp_path: Path) -> tuple[Path, Path]:
    """A tuning set with two copies of the synthetic fixture, ``s1-a`` and ``s1-b``, and a
    replay folder with their cassettes."""
    fixtures = tmp_path / "fixtures"
    replay = tmp_path / "replay"
    for name in ("s1-a", "s1-b"):
        shutil.copytree(SYNTH / "tuning" / "s1-like", fixtures / "tuning" / name)
        shutil.copytree(CASSETTES / "s1-like", replay / name)
    return fixtures, replay


@pytest.mark.parametrize("only", [["--only", "s1-b"], ["--only", "s1-b,s1-a"]])
def test_only_runs_the_named_fixtures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], only: list[str]
) -> None:
    """Speed bundle 1: ``--only NAME`` (repeatable or comma-separated) picks fixtures by name."""
    fixtures, replay = _two_fixtures(tmp_path)
    history = tmp_path / "h.csv"
    keep = tmp_path / "keep"
    args = [
        "eval", "--graph", "extract", "--set", "tuning", "--fixtures", str(fixtures),
        "--replay", str(replay), "--history", str(history), "--keep", str(keep),
        "--photo-reader", "vision", *only,
    ]  # fmt: skip
    assert main(args) == 0
    names = sorted(p.name for p in (keep / "tuning").iterdir() if p.is_dir())
    want = ["s1-b"] if only[-1] == "s1-b" else ["s1-a", "s1-b"]
    assert names == want
    assert _last_row(history)["n_fixtures"] == str(len(want))
    # repeated flags work too, and an unknown name is an error that runs nothing
    capsys.readouterr()
    rows_before = history.read_text(encoding="utf-8").count("\n")
    bad = [*args[: -len(only)], "--only", "s1-a", "--only", "nope"]
    assert main(bad) == 2
    assert "--only: no fixture nope" in capsys.readouterr().err
    assert history.read_text(encoding="utf-8").count("\n") == rows_before


def test_only_twice_and_preflight(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fixtures, replay = _two_fixtures(tmp_path)
    args = [
        "eval", "--graph", "extract", "--set", "tuning", "--fixtures", str(fixtures),
        "--replay", str(replay), "--preflight", "--only", "s1-a", "--only", "s1-b",
    ]  # fmt: skip
    assert main(args) == 0
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["n_fixtures"] == 2
    assert main([*args[:-4], "--only", "s1-a"]) == 0
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["n_fixtures"] == 1
