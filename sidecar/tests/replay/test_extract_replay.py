"""Step 9: ``etach run --replay`` over the extract cassettes (R9.2, R9.13, the synthetic scenarios).

Each test drives the real CLI in a subprocess (``python -m etach.cli``), so exit codes and stdout
are the ones the teacher and the app see. ``tests/cassettes/s1/`` is recorded live by the teacher
(``docs/initial-plan/phases-testing/step9-recording.md``); until it exists the ``s1`` tests SKIP
with that reason. The same checks run over the synthetic ``extract-synthetic/s1-like`` and always
run.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from support.reader import vision_reader

from etach.store import db

CASSETTES = Path(__file__).resolve().parents[1] / "cassettes"
SYNTH = CASSETTES / "extract-synthetic"
S1 = CASSETTES / "s1"
STUDENT = "Học Sinh A"
TIMEOUT = 180


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def pinned(args: Sequence[str | Path]) -> None:
    """The photo cassettes were recorded with the vision reader: a ``--data`` folder replays
    them with ``[extract] photo_reader = "vision"`` (R22.5.7.7)."""
    flat = [str(a) for a in args]
    if "--data" in flat:
        vision_reader(flat[flat.index("--data") + 1])


def etach(*args: str | Path) -> tuple[int, dict[str, Any] | None, str]:
    pinned(args)
    proc = subprocess.run(
        [sys.executable, "-m", "etach.cli", *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_env(),
        timeout=TIMEOUT,
        check=False,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    out = json.loads(lines[-1]) if lines else None
    return proc.returncode, out, proc.stderr


def run_ok(*args: str | Path) -> dict[str, Any]:
    code, out, err = etach("run", *args)
    assert code == 0, err
    assert out is not None and out["status"] == "done", err
    return out


#: Recordings whose cassettes include ``retranscribe_tiles`` calls: they replay with
#: ``[extract] retranscribe_tiles = true`` and ``retranscribe_tiles_keep = "always"``, the rules
#: they were recorded with (since speed bundle 1 the default is off and "better").
RECORDED_WITH_TILES = frozenset({"blank", "validator-retry", "s1"})


def tiles_on(data: Path) -> Path:
    """Tiles on, with the pre-bundle keep rule, in the data folder ``data`` (``models.toml``)."""
    data.mkdir(parents=True, exist_ok=True)
    (data / "models.toml").write_text(
        '[extract]\nretranscribe_tiles = true\nretranscribe_tiles_keep = "always"\n',
        encoding="utf-8",
    )
    return data


def conn_of(data: Path) -> sqlite3.Connection:
    return db.connect(data / "app.db")


def count(c: sqlite3.Connection, sql: str, *params: Any) -> int:
    return int(c.execute(sql, params).fetchone()[0])


def as_recorded(folder: Path, data: Path) -> Path:
    """The data folder ``data``, with tiles on when ``folder`` was recorded with them."""
    return tiles_on(data) if folder.name in RECORDED_WITH_TILES else data


def need_s1() -> Path:
    if not (S1 / "input.json").is_file():
        pytest.skip(
            "tests/cassettes/s1/ is not recorded yet: the teacher records it live with"
            " docs/initial-plan/phases-testing/step9-recording.md"
            " (then this test must pass, not skip)"
        )
    return S1


# --- R9.13 ---------------------------------------------------------------------------------


#: Step 22.6.2 (teacher, "20% as built"): the recorded S1 paper's answers were read almost all
#: empty (1 of 34 sure), so it replays as a blank test: the test, no attempt.
S1_BLANK = True


def _r9_13_run(folder: Path, data: Path, *, filled: bool = True) -> None:
    out = run_ok("--data", as_recorded(folder, data), "--replay", folder)
    assert set(out) == {"test_id", "attempt_id", "run_id", "thread_id", "status"}
    assert out["test_id"] and bool(out["attempt_id"]) is filled


def _r9_13_stop_resume(folder: Path, data: Path, *, filled: bool = True) -> None:
    vision_reader(as_recorded(folder, data))
    args = [sys.executable, "-m", "etach.cli", "run", "--data", str(data), "--replay", str(folder)]
    owner = subprocess.Popen(
        [*args, "--replay-delay-ms", "1500"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=_env(),
    )
    try:
        run_id = None
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and run_id is None:
            time.sleep(0.3)
            if (data / "app.db").is_file():
                c = conn_of(data)
                try:
                    row = c.execute(
                        "SELECT id FROM runs WHERE status = 'running'"
                        " AND EXISTS (SELECT 1 FROM steps s WHERE s.run_id = runs.id)"
                    ).fetchone()
                except sqlite3.OperationalError:
                    row = None
                finally:
                    c.close()
                run_id = row[0] if row else None
        assert run_id, "the run never started"
        code, stopped, err = etach("runs", "stop", run_id, "--data", data)
        assert code == 0, err
        assert stopped is not None and stopped["status"] == "stopped", err
        stdout, stderr = owner.communicate(timeout=TIMEOUT)
    finally:
        if owner.poll() is None:
            owner.kill()
    assert owner.returncode == 0, stderr
    owned = json.loads(stdout.strip().splitlines()[-1])
    assert owned["status"] == "stopped" and owned["run_id"] == run_id
    code, done, err = etach("runs", "resume", run_id, "--data", data, "--replay", folder)
    assert code == 0, err
    assert done is not None and done["status"] == "done", err
    assert done["test_id"] and bool(done["attempt_id"]) is filled and done["run_id"] == run_id
    # a wrong status is a clear error
    code, _, err = etach("runs", "resume", run_id, "--data", data, "--replay", folder)
    assert code != 0 and "only stopped or interrupted runs resume" in err


def test_r9_13_synthetic_run(tmp_path: Path) -> None:
    _r9_13_run(SYNTH / "s1-like", tmp_path / "data")


def test_r9_13_synthetic_stop_resume(tmp_path: Path) -> None:
    _r9_13_stop_resume(SYNTH / "s1-like", tmp_path / "data")


def test_r9_13_recorded_s1_run(tmp_path: Path) -> None:
    _r9_13_run(need_s1(), tmp_path / "data", filled=not S1_BLANK)


def test_r9_13_recorded_s1_stop_resume(tmp_path: Path) -> None:
    _r9_13_stop_resume(need_s1(), tmp_path / "data", filled=not S1_BLANK)


# --- R9.2 ----------------------------------------------------------------------------------


def _r9_2(folder: Path, data: Path, *, filled: bool = True) -> None:
    out = run_ok("--data", as_recorded(folder, data), "--replay", folder)
    pages = len(json.loads((folder / "input.json").read_text("utf-8"))["pages"])
    c = conn_of(data)
    try:
        assert count(c, "SELECT COUNT(*) FROM tests") == 1
        assert count(c, "SELECT COUNT(*) FROM attempts") == int(filled)
        content = json.loads(
            c.execute("SELECT content FROM tests WHERE id = ?", (out["test_id"],)).fetchone()[0]
        )
        questions = sum(
            len(g["questions"]) for s in content["sections"] for g in s.get("groups", [])
        )
        assert questions > 0
        assert count(c, "SELECT COUNT(*) FROM answers") == (questions if filled else 0)
        assert count(c, "SELECT COUNT(*) FROM attempt_pages") == (pages if filled else 0)
        assert pages == 3
        assert c.execute("SELECT kind FROM threads WHERE id = ?", (out["thread_id"],)).fetchone()[
            0
        ] == ("filled" if filled else "blank")
        assert (
            c.execute("SELECT status FROM runs WHERE id = ?", (out["run_id"],)).fetchone()[0]
            == "done"
        )
        assert count(c, "SELECT COUNT(*) FROM messages WHERE kind = 'run_card'") == 1
        if filled:
            name = c.execute("SELECT student_name_read FROM attempts").fetchone()[0]
            assert name == STUDENT
    finally:
        c.close()


def test_r9_2_synthetic_s1_like(tmp_path: Path) -> None:
    _r9_2(SYNTH / "s1-like", tmp_path / "data")


def test_r9_2_recorded_s1(tmp_path: Path) -> None:
    _r9_2(need_s1(), tmp_path / "data", filled=not S1_BLANK)


def test_recorded_s1_rereads_only_what_it_recorded(tmp_path: Path) -> None:
    """The S1 recording replays as recorded (tiles on, as the E2E runs it): the checks fail only
    page 3, so ``retranscribe_tiles`` re-reads page 3 alone and every recorded call is served.
    A check that newly fails another page asks for a call the recording does not have."""
    folder = need_s1()
    data = tmp_path / "data"
    out = run_ok("--data", as_recorded(folder, data), "--replay", folder)
    c = conn_of(data)
    try:
        items = [
            r[0]
            for r in c.execute(
                "SELECT item FROM steps WHERE run_id = ? AND node = 'retranscribe_tiles'",
                (out["run_id"],),
            )
        ]
        assert items == ["page 3"]
        served = count(
            c,
            "SELECT COUNT(*) FROM llm_calls l JOIN steps s ON s.id = l.step_id WHERE s.run_id = ?",
            out["run_id"],
        )
        assert served == len(list(folder.glob("[0-9][0-9][0-9]-*.json")))
    finally:
        c.close()


# --- the synthetic scenarios ---------------------------------------------------------------


def _review(c: sqlite3.Connection, kind: str) -> list[sqlite3.Row]:
    return c.execute("SELECT * FROM review_items WHERE kind = ?", (kind,)).fetchall()


@pytest.mark.parametrize(
    "scenario", ["filled-picked-match", "filled-picked-mismatch", "blank-picked"]
)
def test_picked_scenarios(tmp_path: Path, scenario: str) -> None:
    data = tmp_path / "data"
    bank = run_ok("--data", data, "--replay", SYNTH / "s1-like")
    out = run_ok("--data", data, "--replay", SYNTH / scenario, "--existing", bank["test_id"])
    assert out["test_id"] == bank["test_id"]
    c = conn_of(data)
    try:
        assert count(c, "SELECT COUNT(*) FROM tests") == 1
        steps = count(
            c,
            "SELECT COUNT(*) FROM steps WHERE run_id = ? AND node = 'transcribe_page'",
            out["run_id"],
        )
        assert steps == 0
        kind = c.execute("SELECT kind FROM threads WHERE id = ?", (out["thread_id"],)).fetchone()
        mismatch = _review(c, "picked_test_mismatch")
        if scenario == "blank-picked":
            assert out["attempt_id"] is None and kind[0] == "blank"
            assert mismatch == []
        else:
            assert out["attempt_id"] and kind[0] == "filled"
            if scenario == "filled-picked-match":
                assert mismatch == []
            else:
                assert len(mismatch) == 1 and mismatch[0]["attempt_id"] == out["attempt_id"]
    finally:
        c.close()


def test_key_photo_scenario(tmp_path: Path) -> None:
    data = tmp_path / "data"
    out = run_ok("--data", data, "--replay", SYNTH / "key-photo")
    c = conn_of(data)
    try:
        rows = c.execute(
            "SELECT source, status FROM answer_keys WHERE test_id = ?", (out["test_id"],)
        ).fetchall()
        assert sorted((r[0], r[1]) for r in rows) == [
            ("from_key_photo", "ai_unverified"),
            ("from_key_photo", "from_key_photo"),
        ]
    finally:
        c.close()


def test_validator_retry_scenario(tmp_path: Path) -> None:
    data = tiles_on(tmp_path / "data")  # the tile path, tested on purpose
    out = run_ok("--data", data, "--replay", SYNTH / "validator-retry")
    c = conn_of(data)
    try:
        statuses = [
            r[0]
            for r in c.execute(
                "SELECT l.status FROM llm_calls l JOIN steps s ON s.id = l.step_id"
                " WHERE s.run_id = ? AND s.node = 'transcribe_page'",
                (out["run_id"],),
            )
        ]
        assert "invalid" in statuses  # the validation retry replayed as invalid → valid
        tiles = count(
            c,
            "SELECT COUNT(*) FROM steps WHERE run_id = ? AND node = 'retranscribe_tiles'",
            out["run_id"],
        )
        assert tiles == 1
        assert len(_review(c, "validator_failed")) == 1
    finally:
        c.close()


def test_pdf_text_scenario(tmp_path: Path) -> None:
    data = tmp_path / "data"
    manifest = json.loads((SYNTH / "pdf-text" / "input.json").read_text("utf-8"))
    assert manifest["pages"][0]["has_text_layer"] is True
    out = run_ok("--data", data, "--replay", SYNTH / "pdf-text")
    assert out["attempt_id"]


def test_supersede_scenario(tmp_path: Path) -> None:
    data = tmp_path / "data"
    first = run_ok("--data", data, "--replay", SYNTH / "s1-like")
    out = run_ok(
        "--data",
        data,
        "--replay",
        SYNTH / "supersede",
        "--thread",
        first["thread_id"],
        "--supersedes",
        first["attempt_id"],
    )
    c = conn_of(data)
    try:
        row = c.execute(
            "SELECT superseded_by FROM attempts WHERE id = ?", (first["attempt_id"],)
        ).fetchone()
        assert row[0] == out["attempt_id"]
    finally:
        c.close()


def test_wrong_status_is_a_clear_error(tmp_path: Path) -> None:
    data = tmp_path / "data"
    out = run_ok("--data", data, "--replay", SYNTH / "s1-like")
    code, _, err = etach("runs", "stop", out["run_id"], "--data", data)
    assert code != 0 and "only a running run can be stopped" in err
    code, _, err = etach("runs", "discard", out["run_id"], "--data", data)
    assert code != 0 and "already done" in err


def test_scrub_check_passes_on_synthetic() -> None:
    code, _, err = etach("scrub", "--check", SYNTH)
    assert code == 0, err


# --- damaged cassettes (the recorded s1 failure mode) ---------------------------------------


def _copy_scenario(src: Path, dst: Path) -> Path:
    import shutil

    shutil.copytree(src, dst)
    return dst


def _edit_response(path: Path, old: str, new: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert old in data["response_text"], old
    data["response_text"] = data["response_text"].replace(old, new, 1)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_damaged_complete_cassette_is_a_clear_error(tmp_path: Path) -> None:
    """A ``complete`` cassette whose JSON was broken after recording (a number replaced by a bare
    placeholder) must not replay as a validation retry ending in "all cassettes already served"."""
    scenario = _copy_scenario(SYNTH / "s1-like", tmp_path / "scenario")
    _edit_response(
        scenario / "003-transcribe_page.json",
        '"printed_number": 5,',
        f'"printed_number": {STUDENT},',
    )
    code, _, err = etach("run", "--data", tmp_path / "data", "--replay", scenario)
    assert code != 0
    assert "changed after recording" in err and "003-transcribe_page.json" in err, err
    assert "already served" not in err, err


def test_scrub_of_a_numeric_misread_name_still_replays(tmp_path: Path) -> None:
    """The recorded-s1 chain: read_answers misreads question numbers as the student name and
    class. The scrub ignores them (not a name / class, reported on stderr) and never touches
    JSON numbers, so the scenario still replays to done."""
    scenario = _copy_scenario(SYNTH / "s1-like", tmp_path / "scenario")
    _edit_response(
        scenario / "005-read_answers_page.json",
        '"student_name": null, "class_name": null',
        '"student_name": "5", "class_name": "6"',
    )
    scrub = subprocess.run(
        [sys.executable, "-m", "etach.cli", "scrub", str(scenario)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_env(),
        timeout=TIMEOUT,
        check=False,
    )
    assert scrub.returncode == 0, scrub.stderr
    assert "ignored student_name '5': not a name" in scrub.stderr, scrub.stderr
    assert "ignored class_name '6': not a class" in scrub.stderr, scrub.stderr
    run_ok("--data", tmp_path / "data", "--replay", scenario)
