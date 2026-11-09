"""M2: the blind rating sheet (``etach eval --graph grade --rate-explanations``) and reading it
back (``etach eval --score-ratings``), on two replayed synthetic grade runs."""

import csv
import io
import json
from pathlib import Path

import pytest

from etach.cli import main
from etach.eval.ratings import KEY_NAME, SHEET_COLUMNS, SHEET_NAME, RatingError, write_sheet

SIDECAR = Path(__file__).resolve().parents[3]
GRADE_SYNTH = SIDECAR / "tests" / "fixtures_synth" / "grade"
CASSETTES = SIDECAR / "tests" / "cassettes" / "grade-eval"
TAG_A = "synthetic/model-alpha:1b"
TAG_B = "synthetic/model-beta:2b"


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Two kept grade runs of the synthetic fixtures, one per (made-up) reasoning tag."""
    tmp = tmp_path_factory.mktemp("runs")
    out = []
    for tag, name in ((TAG_A, "run-a"), (TAG_B, "run-b")):
        keep = tmp / name
        args = [
            "eval", "--graph", "grade", "--set", "tuning", "--fixtures", str(GRADE_SYNTH),
            "--replay", str(CASSETTES), "--history", str(tmp / "h.csv"),
            "--role", f"reasoning={tag}", "--keep", str(keep),
        ]  # fmt: skip
        assert main(args) == 0
        out.append(keep)
    return out[0], out[1]


def _sheet(folder: Path) -> list[dict[str, str]]:
    text = (folder / SHEET_NAME).read_bytes().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def test_sheet_is_blind_and_complete(runs: tuple[Path, Path], tmp_path: Path) -> None:
    out = tmp_path / "rating"
    assert main(["eval", "--graph", "grade", "--rate-explanations", *map(str, runs),
                 "--out", str(out)]) == 0  # fmt: skip
    raw = (out / SHEET_NAME).read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # the BOM, so Excel reads UTF-8
    text = raw.decode("utf-8-sig")
    for tag in (TAG_A, TAG_B, "alpha", "beta", "model-"):
        assert tag not in text  # no model name in the sheet
    rows = _sheet(out)
    assert tuple(rows[0]) == SHEET_COLUMNS
    assert len(rows) == 8  # 4 explanations (g1's wrong answers) per run
    assert all(r["rating"] == "" and r["note"] == "" for r in rows)
    assert {r["fixture"] for r in rows} == {"tuning/g1-mixed"}
    assert sorted(r["question"] for r in rows) == ["2", "2", "3", "3", "4", "4", "5", "5"]
    assert any("Giải thích giả lập" in r["explanation"] for r in rows)  # Vietnamese kept
    key = json.loads((out / KEY_NAME).read_text(encoding="utf-8"))["items"]
    assert set(key) == {r["item"] for r in rows}
    assert sorted(key.values()) == [TAG_A] * 4 + [TAG_B] * 4


def test_shuffle_is_deterministic(runs: tuple[Path, Path], tmp_path: Path) -> None:
    write_sheet(list(runs), tmp_path / "a", seed=7)
    write_sheet(list(runs), tmp_path / "b", seed=7)
    write_sheet(list(runs), tmp_path / "c", seed=8)
    a = (tmp_path / "a" / SHEET_NAME).read_bytes()
    assert a == (tmp_path / "b" / SHEET_NAME).read_bytes()
    order = [(r["question"], r["explanation"]) for r in _sheet(tmp_path / "a")]
    other = [(r["question"], r["explanation"]) for r in _sheet(tmp_path / "c")]
    assert order != other and sorted(order) == sorted(other)
    # the same runs given in the other order give the same items (the key differs only by run)
    write_sheet(list(reversed(runs)), tmp_path / "d", seed=7)
    assert len(_sheet(tmp_path / "d")) == len(order)


def _fill(folder: Path, ratings: dict[str, str], *, delimiter: str = ",") -> None:
    rows = _sheet(folder)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(SHEET_COLUMNS), delimiter=delimiter)
    writer.writeheader()
    for r in rows:
        r["rating"] = ratings.get(r["item"], "")
        writer.writerow(r)
    (folder / SHEET_NAME).write_bytes(buf.getvalue().encode("utf-8-sig"))


def test_round_trip_scoring(
    runs: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "rating"
    write_sheet(list(runs), out)
    key = json.loads((out / KEY_NAME).read_text(encoding="utf-8"))["items"]
    a_items = sorted(i for i, t in key.items() if t == TAG_A)
    b_items = sorted(i for i, t in key.items() if t == TAG_B)
    ratings = dict(zip(a_items, ["5", "4", "4", "3"], strict=True))
    ratings.update(zip(b_items[:3], ["2", "1", "2.0"], strict=True))  # the 4th not rated
    _fill(out, ratings)
    assert main(["eval", "--score-ratings", str(out)]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0] == "Blind explanation ratings: 8 items, 8 in the sheet"
    assert lines[1] == (
        f"- reasoning={TAG_A}: mean 4.00, 4 rated (0 not rated);"
        " per score 1: 0, 2: 0, 3: 1, 4: 2, 5: 1"
    )
    assert lines[2] == (
        f"- reasoning={TAG_B}: mean 1.67, 3 rated (1 not rated);"
        " per score 1: 1, 2: 2, 3: 0, 4: 0, 5: 0"
    )
    text = "\n".join(lines)
    assert "Giải thích" not in text and "Synthetic" not in text  # no question or answer text
    # Excel in a ';' locale, saved in the Windows code page: the ratings still read
    _fill(out, ratings, delimiter=";")
    data = (out / SHEET_NAME).read_bytes().decode("utf-8-sig")
    (out / SHEET_NAME).write_bytes(data.encode("cp1252", errors="replace"))
    assert main(["eval", "--score-ratings", str(out)]) == 0
    assert capsys.readouterr().out.strip().splitlines()[1:] == lines[1:]


def test_bad_ratings_and_runs(
    runs: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "rating"
    write_sheet(list(runs), out)
    first = _sheet(out)[0]["item"]
    for bad in ("6", "0", "3.5", "good"):
        _fill(out, {first: bad})
        assert main(["eval", "--score-ratings", str(out)]) == 2
        assert f"rating not a whole number 1-5: {first}" in capsys.readouterr().err
    with pytest.raises(RatingError, match="at least 2"):
        write_sheet([runs[0]], tmp_path / "x")
    with pytest.raises(RatingError, match="one run per model"):
        write_sheet([runs[0], runs[0]], tmp_path / "x")
    with pytest.raises(RatingError, match="not an `etach eval --keep` folder"):
        write_sheet([runs[0], tmp_path / "nothing"], tmp_path / "x")
    assert main(["eval", "--graph", "extract", "--rate-explanations", str(runs[0])]) == 2
    assert "--rate-explanations is for --graph grade" in capsys.readouterr().err


def test_batch_folders_of_the_script_are_accepted(runs: tuple[Path, Path], tmp_path: Path) -> None:
    """The overnight script keeps a run in ``<batch>/run-1``: the batch folder works too."""
    import shutil

    batches = []
    for i, run in enumerate(runs):
        batch = tmp_path / f"batch-{i}"
        shutil.copytree(run, batch / "run-1")
        batches.append(batch)
    assert write_sheet(batches, tmp_path / "out") == 8
