"""R11.2 (etach eval on the committed synthetic fixture), R11.4 (what git tracks), the fixture
format and ``etach fixtures manifest``."""

import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from etach.cli import main
from etach.eval.fixtures import (
    Expected,
    FixtureError,
    convert_flat,
    discover,
    load_fixture,
    manifest_lines,
)
from etach.eval.harness import COLUMNS, REPO_ROOT, aggregate_row, evaluate_saved

SIDECAR = Path(__file__).resolve().parents[3]
SYNTH = SIDECAR / "tests" / "fixtures_synth"
CASSETTES = SIDECAR / "tests" / "cassettes" / "extract-synthetic"
#: the synthetic cassettes were recorded with the vision photo reader (R22.5.7.7)
VISION = ("--photo-reader", "vision")


def _rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def test_r11_2_eval_appends_one_full_row(tmp_path: Path) -> None:
    history = tmp_path / "eval-history.csv"
    shutil.copy(REPO_ROOT / "eval-history.csv", history)
    before = _rows(history)
    assert before and tuple(before[0]) == COLUMNS
    args = ["eval", "--graph", "extract", "--set", "tuning", "--fixtures", str(SYNTH)]
    args += ["--replay", str(CASSETTES), *VISION, "--history", str(history)]
    assert main(args) == 0
    after = _rows(history)
    assert len(after) == len(before) + 1
    assert tuple(after[0]) == COLUMNS
    row = dict(zip(after[0], after[-1], strict=True))
    assert set(row) == set(COLUMNS)
    assert row["graph"] == "extract" and row["set"] == "tuning" and row["mode"] == "replay"
    assert row["n_fixtures"] == "1" and row["n_failed"] == "0"
    assert row["cer"] == "0.0000"
    assert row["structure_overall"] == "1.0000"
    assert row["structure_groups"] == "1.0000" and row["structure_skill"] == "1.0000"
    assert row["stimulus_cer"] == ""  # no passage in the synthetic fixture
    assert row["answer_accuracy"] == "1.0000" and row["answer_n"] == "6"
    assert row["transcribe_page_calls"] == "3" and row["read_answers_page_calls"] == "3"
    assert row["model_vision"] and row["prompt_digest"]
    assert row["verdict_accuracy"] == "" and row["score_exact_match"] == ""
    # metrics only: nothing from the fixture's student block
    text = history.read_text(encoding="utf-8")
    assert "Học Sinh" not in text and "8X1" not in text and "s1-like" not in text
    # a second run appends a second row under the same header
    assert main(args) == 0
    assert len(_rows(history)) == len(before) + 2


def test_eval_creates_header_and_refuses_other_header(tmp_path: Path) -> None:
    history = tmp_path / "new.csv"
    args = ["eval", "--graph", "extract", "--set", "tuning", "--fixtures", str(SYNTH)]
    args += ["--replay", str(CASSETTES), *VISION, "--history", str(history)]
    assert main(args) == 0
    rows = _rows(history)
    assert tuple(rows[0]) == COLUMNS and len(rows) == 2
    # an old header with data rows is refused and left as it is
    bad = tmp_path / "bad.csv"
    bad.write_text("timestamp,cer\n2026-01-01,0.1\n", encoding="utf-8")
    assert main([*args[:-1], str(bad)]) == 2
    assert bad.read_text(encoding="utf-8") == "timestamp,cer\n2026-01-01,0.1\n"
    # an old header alone is replaced by the current one
    old = tmp_path / "old.csv"
    old.write_text("timestamp,cer\n", encoding="utf-8")
    assert main([*args[:-1], str(old)]) == 0
    rows = _rows(old)
    assert tuple(rows[0]) == COLUMNS and len(rows) == 2
    assert {"stimulus_cer", "structure_groups", "structure_skill"} <= set(COLUMNS)


def test_eval_needs_graph_and_set(capsys: pytest.CaptureFixture[str]) -> None:
    """M2: ``--graph`` / ``--set`` are checked in code (``--score-ratings`` needs neither)."""
    assert main(["eval", "--set", "tuning"]) == 2
    assert "--graph is required" in capsys.readouterr().err
    assert main(["eval", "--graph", "grade"]) == 2
    assert "--set is required" in capsys.readouterr().err
    args = ["eval", "--graph", "grade", "--set", "tuning", "--fixtures", str(SYNTH / "grade")]
    assert main([*args, "--tiles"]) == 2
    assert "--tiles is for --graph extract" in capsys.readouterr().err


def test_r22_5_7_7_photo_reader_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """``--photo-reader``: ``ocr`` by default (R22.5.7.7), ``vision`` on request; extract only."""
    args = ["eval", "--graph", "extract", "--set", "tuning", "--fixtures", str(SYNTH)]
    args += ["--replay", str(CASSETTES), "--preflight"]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["photo_reader"] == "ocr"
    assert main([*args, *VISION]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["photo_reader"] == "vision"
    grade = ["eval", "--graph", "grade", "--set", "tuning", "--fixtures", str(SYNTH / "grade")]
    assert main([*grade, *VISION]) == 2
    assert "--photo-reader is for --graph extract" in capsys.readouterr().err


def test_r22_6_5_1_photo_structure_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """``--photo-structure``: ``code`` by default (step 22.6.6 (c), D16); OCR reader and
    extract only."""
    args = ["eval", "--graph", "extract", "--set", "tuning", "--fixtures", str(SYNTH)]
    args += ["--replay", str(CASSETTES), "--preflight"]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["photo_structure"] == "code"
    assert main([*args, "--photo-structure", "qwen"]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["photo_structure"] == "qwen"
    assert main([*args, *VISION, "--photo-structure", "code"]) == 2
    assert "--photo-structure is for the OCR photo reader" in capsys.readouterr().err
    grade = ["eval", "--graph", "grade", "--set", "tuning", "--fixtures", str(SYNTH / "grade")]
    assert main([*grade, "--photo-structure", "code"]) == 2
    assert "--photo-structure is for --graph extract" in capsys.readouterr().err


def test_r22_6_5_1_code_run_mode_and_models_toml(tmp_path: Path, monkeypatch: Any) -> None:
    """``--photo-structure code`` is written into ``models.toml`` and tags the row's mode."""
    from etach.eval import harness

    written: list[str] = []
    real = harness._write_models_toml

    def spy(paths: Any, roles: Any, **kw: Any) -> None:
        real(paths, roles, **kw)
        written.append(paths.models_toml.read_text(encoding="utf-8"))

    monkeypatch.setattr(harness, "_write_models_toml", spy)
    history = tmp_path / "h.csv"
    args = ["eval", "--graph", "extract", "--set", "tuning", "--fixtures", str(SYNTH)]
    args += ["--replay", str(CASSETTES), "--history", str(history), "--photo-structure", "code"]
    main(args)
    row = dict(zip(*_rows(history)[:2], strict=True))
    assert row["mode"] == "replay+ocr+code"
    assert written and 'photo_structure = "code"' in written[0]


def test_r22_5_7_7_ocr_run_mode_and_models_toml(tmp_path: Path, monkeypatch: Any) -> None:
    """The eval writes ``photo_reader`` into each fixture's ``models.toml``; an OCR-reader row's
    mode gets ``+ocr``, and ``+code`` for the default way (step 22.6.6 (c), D16) (no OCR
    cassettes here: the run fails, the row is still written)."""
    from etach.eval import harness

    written: list[str] = []
    real = harness._write_models_toml

    def spy(paths: Any, roles: Any, **kw: Any) -> None:
        real(paths, roles, **kw)
        written.append(paths.models_toml.read_text(encoding="utf-8"))

    monkeypatch.setattr(harness, "_write_models_toml", spy)
    history = tmp_path / "h.csv"
    args = ["eval", "--graph", "extract", "--set", "tuning", "--fixtures", str(SYNTH)]
    assert (
        main([*args, "--replay", str(CASSETTES), "--history", str(history)]) == 1
    )  # a failed fixture
    row = dict(zip(*_rows(history)[:2], strict=True))
    assert row["mode"] == "replay+ocr+code"
    assert written and 'photo_reader = "ocr"' in written[0]


def test_eval_bad_role(tmp_path: Path) -> None:
    args = ["eval", "--graph", "extract", "--set", "tuning", "--fixtures", str(SYNTH)]
    assert main([*args, "--role", "vision", "--history", str(tmp_path / "h.csv")]) == 2


def test_role_override_is_recorded(tmp_path: Path) -> None:
    history = tmp_path / "h.csv"
    args = ["eval", "--graph", "extract", "--set", "tuning", "--fixtures", str(SYNTH)]
    args += ["--replay", str(CASSETTES), *VISION, "--history", str(history)]
    assert main([*args, "--role", "vision=some/other:tag"]) == 0
    row = dict(zip(*_rows(history)[:2], strict=True))
    assert row["model_vision"] == "some/other:tag"


def test_synthetic_fixture_loads() -> None:
    [fx] = discover(SYNTH, "tuning")
    assert fx.name == "s1-like" and len(fx.input.pages) == 3
    assert fx.expected.verified_by is None
    assert fx.expected.question_keys() == ["1", "2", "3", "4", "5", "6"]
    assert discover(SYNTH, "heldout") == []


def test_fixture_validation(tmp_path: Path) -> None:
    folder = tmp_path / "tuning" / "f1"
    shutil.copytree(SYNTH / "tuning" / "s1-like", folder)
    data = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
    data["answers"]["99"] = "A"
    (folder / "expected.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(FixtureError, match="99"):
        load_fixture(folder)
    del data["answers"]["99"]
    data["meta"]["occasion"] = "Finals"
    (folder / "expected.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(FixtureError, match="occasion"):
        load_fixture(folder)
    data["meta"]["occasion"] = "FinalTerm"
    (folder / "expected.json").write_text(json.dumps(data), encoding="utf-8")
    (folder / "pages" / "page-02.png").unlink()
    with pytest.raises(FixtureError, match="page-02"):
        load_fixture(folder)


def test_fixtures_manifest(tmp_path: Path) -> None:
    for set_name, name, who in (("tuning", "b", "teacher"), ("heldout", "a", None)):
        folder = tmp_path / set_name / name
        folder.mkdir(parents=True)
        (folder / "expected.json").write_text(json.dumps({"verified_by": who}), encoding="utf-8")
    assert main(["fixtures", "manifest", "--fixtures", str(tmp_path)]) == 0
    text = (tmp_path / "MANIFEST.sha256").read_bytes().decode("utf-8")
    lines = text.splitlines()
    assert lines == manifest_lines(tmp_path)
    assert [line.split("  ")[1] for line in lines] == [
        "heldout/a/expected.json",
        "tuning/b/expected.json",
    ]
    digest = hashlib.sha256((tmp_path / "tuning/b/expected.json").read_bytes()).hexdigest()
    assert lines[1] == f"{digest}  tuning/b/expected.json  verified_by: teacher"
    assert lines[0].endswith("verified_by: -")
    assert "\r" not in text


def test_r11_4_git_tracks_only_the_manifest_and_history() -> None:
    def ls(*paths: str) -> list[str]:
        out = subprocess.run(
            ["git", "ls-files", *paths], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
        return out.stdout.split()

    assert set(ls("fixtures")) <= {"fixtures/MANIFEST.sha256"}
    assert ls("eval-history.csv") == ["eval-history.csv"]


FLAT = {
    "meta": {"occasion": "FinalTerm"},
    "sections": [
        {"printed_title": "I. Listen", "kind": "listening", "points": None, "questions": []},
        {
            "printed_title": "II",
            "kind": "questions",
            "points": 2.5,
            "questions": [
                {
                    "printed_number": 1,
                    "type": "mcq",
                    "stem": "He ____ home.",
                    "options": ["go", "went"],
                    "cue": None,
                    "page_no": 1,
                },
                {"printed_number": 2, "type": "gap_fill", "stem": "x ____", "page_no": 1},
            ],
        },
    ],
    "answers": {"1": "B", "2": None},
    "student": {"name": "Học Sinh A", "class": "8X1"},
}


def test_convert_flat_to_nested(tmp_path: Path) -> None:
    new = convert_flat(FLAT)
    listening, part = new["sections"]
    assert listening["kind"] == "listening" and listening["groups"] == []
    assert part["kind"] == "questions" and part["printed_points"] == "2.5"
    assert part["skill"] is None and "points" not in part and "questions" not in part
    [group] = part["groups"]
    assert group["stimulus"] is None
    assert group["questions"] == FLAT["sections"][1]["questions"]
    assert new["answers"] == FLAT["answers"] and new["student"] == FLAT["student"]
    exp = Expected.model_validate(new)
    assert exp.question_keys() == ["1", "2"]
    assert convert_flat(new) == new  # already nested: unchanged
    # the loader names the converter for a flat file
    folder = tmp_path / "tuning" / "f1"
    shutil.copytree(SYNTH / "tuning" / "s1-like", folder)
    (folder / "expected.json").write_text(json.dumps(FLAT), encoding="utf-8")
    with pytest.raises(FixtureError, match="convert"):
        load_fixture(folder)


def test_cloze_stems_must_be_null() -> None:
    data = convert_flat(FLAT)
    group = data["sections"][1]["groups"][0]
    group["stimulus"] = "He (1) ____ home and (2) ____ to bed."
    with pytest.raises(ValueError, match="stem must be null"):
        Expected.model_validate(data)
    for q in group["questions"]:
        q["stem"] = None
    exp = Expected.model_validate(data)
    assert [q.stem for q in exp.sections[1].questions] == [None, None]
    data["sections"][1]["listening_range"] = [1, 4]
    with pytest.raises(ValueError, match="listening_range"):
        Expected.model_validate(data)


def _key_fixture(tmp_path: Path, *, key_page: bool) -> Any:
    folder = tmp_path / "tuning" / "s1-like"
    shutil.copytree(SYNTH / "tuning" / "s1-like", folder)
    data = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
    data["key"] = {"1": ["A"], "2": ["B"]}
    (folder / "expected.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    if key_page:
        inp = json.loads((folder / "input.json").read_text(encoding="utf-8"))
        inp["pages"][2]["is_key"] = True
        (folder / "input.json").write_text(json.dumps(inp), encoding="utf-8")
    return load_fixture(folder, "tuning")


def test_key_accuracy_blank_without_key_pages(tmp_path: Path) -> None:
    """M1 baseline fix: on the extract graph the key comes only from 🔑 key pages
    (llm-design §8), so a fixture with an expected key but no key page counts nothing:
    ``key_accuracy`` is blank and ``key_n`` 0 (the baseline rows had 0.0000 over 506)."""
    fx = _key_fixture(tmp_path / "a", key_page=False)
    result = evaluate_saved(fx, status="done", test=None, answers=[], keys=[])
    assert result.keys.accuracy.total == 0 and result.keys.mapping.total == 0
    row = aggregate_row(
        [result], graph="extract", set_name="tuning", mode="replay", models={}, commit="x"
    )
    assert row["key_accuracy"] == "" and row["key_n"] == "0"
    assert row["key_mapping_accuracy"] == "" and row["key_mapping_n"] == "0"


def test_key_accuracy_counts_fixtures_with_key_pages(tmp_path: Path) -> None:
    with_key = evaluate_saved(
        _key_fixture(tmp_path / "a", key_page=True), status="done", test=None, answers=[], keys=[]
    )
    without = evaluate_saved(
        _key_fixture(tmp_path / "b", key_page=False), status="done", test=None, answers=[], keys=[]
    )
    row = aggregate_row(
        [with_key, without],
        graph="extract",
        set_name="tuning",
        mode="replay",
        models={},
        commit="x",
    )
    assert row["key_accuracy"] == "0.0000" and row["key_n"] == "2"  # only the key-page fixture
    assert row["key_mapping_accuracy"] == "0.0000" and row["key_mapping_n"] == "2"
