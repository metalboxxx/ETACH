"""Step 22.1.3, R22.1.3.1: replayed runs publish progress that follows llm-design §2's stage
lists, starts at or above 0, never goes down and is 100 at ``run.done``, also when a stage is
skipped.

The runs go through ``etach run`` / ``etach grade --replay`` in this process (``etach.cli.main``),
so the test can record every event the run manager publishes:

- extract ``key-photo``: key pages, a test page, answers (every extract stage has work);
- extract ``s1-like``: no key pages ("Reading the key" does nothing);
- grade ``first-grade``: an attempt, with the key check;
- grade ``blank-key``: a test with no attempt, which goes from "Grading" straight to "Saving"
  ("Explaining mistakes" and "Updating student ability" are skipped).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from etach import cli
from etach.graphs.extract import EXTRACT_STAGES
from etach.graphs.grade import GRADE_STAGES
from etach.llm.cassettes import grade_scenario_extract_dir, load_grade_scenario
from etach.runtime.events import Event, EventBus
from etach.runtime.steps import Stage

from .test_extract_replay import CASSETTES, RECORDED_WITH_TILES, pinned, tiles_on

SYNTH = CASSETTES / "extract-synthetic"
GRADE = CASSETTES / "grade-synthetic"
PROGRESS_TYPES = ("run.step_started", "run.progress", "run.done")


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> list[Event]:
    log: list[Event] = []
    publish = EventBus.publish_event

    def recording(self: EventBus, type: str, **data: Any) -> Event:
        event = publish(self, type, **data)
        log.append(dict(event))
        return event

    monkeypatch.setattr(EventBus, "publish_event", recording)
    return log


def _main(capsys: pytest.CaptureFixture[str], *args: str | Path) -> dict[str, Any]:
    pinned(args)
    code = cli.main([str(a) for a in args])
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    result: dict[str, Any] = json.loads(lines[-1])
    assert code == 0 and result["status"] == "done", out
    return result


def _check(log: list[Event], run_id: str, stages: tuple[Stage, ...]) -> list[str]:
    """Checks the run's events; returns the stage labels it entered, in order."""
    mine = [e for e in log if e.get("run_id") == run_id]
    progress = [e for e in mine if e["type"] in PROGRESS_TYPES]
    assert all("percent" in e for e in progress)
    percents = [e["percent"] for e in progress]
    assert percents[0] >= 0
    assert percents == sorted(percents), percents
    assert progress[-1]["type"] == "run.done" and percents[-1] == 100
    assert all(p < 100 for p in percents[:-1])
    entered: list[str] = []
    for e in progress:
        assert e["stages"] == len(stages)
        assert e["stage_label"] == stages[e["stage"] - 1].label
        if e["type"] == "run.step_started":
            assert e["node"] in stages[e["stage"] - 1].nodes, e
            if not entered or entered[-1] != e["stage_label"]:
                entered.append(e["stage_label"])
        if e["type"] == "run.progress" and "done" in e:
            assert e["unit"] in ("page", "section", "question")
            assert 0 <= e["done"] <= e["total"]
            # v4.24: the item being worked on, 1-based ("Reading page 3 of 4")
            if not e.get("again"):
                assert 1 <= e["current"] <= e["total"], e
    return entered


def test_stage_tables_name_every_node_once() -> None:
    from etach.graphs.extract import C1_NODES
    from etach.graphs.grade import C2_NODES

    for stages, nodes in ((EXTRACT_STAGES, C1_NODES), (GRADE_STAGES, C2_NODES)):
        listed = [n for s in stages for n in s.nodes]
        assert sorted(listed) == sorted(nodes)
    assert [s.label for s in EXTRACT_STAGES] == [
        "Preparing the photos",
        "Reading the key",
        "Reading the test",
        "Reading the answers",
        "Saving",
    ]
    assert [s.label for s in GRADE_STAGES] == [
        "Getting ready",
        "Checking the key",
        "Grading",
        "Explaining mistakes",
        "Updating student ability",
        "Saving",
    ]


def test_extract_with_key_pages(
    tmp_path: Path, events: list[Event], capsys: pytest.CaptureFixture[str]
) -> None:
    out = _main(capsys, "run", "--data", tmp_path / "data", "--replay", SYNTH / "key-photo")
    entered = _check(events, out["run_id"], EXTRACT_STAGES)
    assert entered == [s.label for s in EXTRACT_STAGES]
    key_counts = [
        (e["done"], e["total"])
        for e in events
        if e["type"] == "run.progress" and e.get("node") == "read_key_pages" and "done" in e
    ]
    assert key_counts == [(0, 2), (1, 2), (1, 2), (2, 2)]
    reading = [
        (e["current"], e["total"])
        for e in events
        if e["type"] == "run.progress" and e.get("node") == "read_key_pages" and "done" in e
    ]
    assert reading == [(1, 2), (2, 2), (2, 2), (2, 2)]
    assert not any(e.get("again") for e in events)


@pytest.mark.parametrize("scenario", ["validator-retry"])
def test_a_second_pass_names_its_page_and_says_again(
    tmp_path: Path, events: list[Event], capsys: pytest.CaptureFixture[str], scenario: str
) -> None:
    """R22.2.1.5: ``retranscribe_tiles`` gives ``again: true`` with the page's own number."""
    data = tiles_on(tmp_path / "data")
    out = _main(capsys, "run", "--data", data, "--replay", SYNTH / scenario)
    _check(events, out["run_id"], EXTRACT_STAGES)
    again = [
        e
        for e in events
        if e["type"] == "run.progress" and e.get("node") == "retranscribe_tiles" and "done" in e
    ]
    assert again and all(e["again"] is True for e in again)
    pages = {e["current"] for e in again}
    assert pages == {int(str(e["label"]).split()[-1]) for e in again}, again
    assert pages == {2}  # the recording's page 2 fails validation: "Checking page 2 again"


def test_extract_without_key_pages(
    tmp_path: Path, events: list[Event], capsys: pytest.CaptureFixture[str]
) -> None:
    out = _main(capsys, "run", "--data", tmp_path / "data", "--replay", SYNTH / "s1-like")
    _check(events, out["run_id"], EXTRACT_STAGES)
    assert not any(
        e["type"] == "run.progress" and e.get("node") == "read_key_pages" for e in events
    )


def _grade(
    tmp_path: Path, events: list[Event], capsys: pytest.CaptureFixture[str], scenario: str
) -> tuple[dict[str, Any], list[str]]:
    folder = GRADE / scenario
    manifest = load_grade_scenario(folder)
    assert manifest is not None
    data = tmp_path / "data"
    extract_dir = grade_scenario_extract_dir(folder, manifest)
    if extract_dir.name in RECORDED_WITH_TILES:
        tiles_on(data)
    extracted = _main(capsys, "run", "--data", data, "--replay", extract_dir)
    _check(events, extracted["run_id"], EXTRACT_STAGES)
    target = (
        ["--attempt", extracted["attempt_id"]]
        if manifest.target == "attempt"
        else ["--test", extracted["test_id"]]
    )
    out = _main(capsys, "grade", "--data", data, *target, "--replay", folder)
    return out, _check(events, out["run_id"], GRADE_STAGES)


def test_grade_an_attempt(
    tmp_path: Path, events: list[Event], capsys: pytest.CaptureFixture[str]
) -> None:
    _, entered = _grade(tmp_path, events, capsys, "first-grade")
    assert entered == [s.label for s in GRADE_STAGES]


def test_grade_a_test_skips_stages_and_still_reaches_100(
    tmp_path: Path, events: list[Event], capsys: pytest.CaptureFixture[str]
) -> None:
    _, entered = _grade(tmp_path, events, capsys, "blank-key")
    assert entered == ["Getting ready", "Checking the key", "Grading", "Saving"]
