"""Cassettes: match key, recorder, replay (R4.7) and ``etach record``."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from support.fake_ollama import ChatScript, FakeOllama

from etach.cli import main
from etach.domain.llm_schemas import ReadAnswersOut, ReadHeaderOut
from etach.llm.adapters import RenderedPrompt
from etach.llm.cassettes import (
    Cassette,
    CassetteMiss,
    CassetteRecorder,
    ReplayBackend,
    active_recorder,
    load_cassettes,
    match_key,
    recording,
)
from etach.llm.client import CallResult, StreamDropped
from etach.llm.config import parse_models_config
from etach.store.repos import runs

SYNTHETIC = Path(__file__).resolve().parents[2] / "cassettes" / "_synthetic"
VALID = '{"a": 7, "b": "seven"}'


class OtherPrompts:
    def render(self, task: str, profile: str, inputs: Mapping[str, Any]) -> RenderedPrompt:
        return RenderedPrompt.of("a tuned system prompt", f"tuned {task}")


def test_match_key_uses_task_schema_and_selected_inputs() -> None:
    base = match_key("t", "S", {"page_no": 1, "question_ids": ["q-1", "q-2"]})
    assert base.startswith("t:")
    assert base == match_key("t", "S", {"question_ids": ("q-1", "q-2"), "page_no": 1})
    assert base == match_key("t", "S", {"page_no": 1, "question_ids": ["q-1", "q-2"], "x": 5})
    assert base != match_key("t", "S", {"page_no": 2, "question_ids": ["q-1", "q-2"]})
    assert base != match_key("t", "S2", {"page_no": 1, "question_ids": ["q-1", "q-2"]})
    assert base != match_key("u", "S", {"page_no": 1, "question_ids": ["q-1", "q-2"]})
    assert match_key("t", "S", {"section_id": "s-1"}) != match_key("t", "S", {})


@pytest.mark.asyncio
async def test_recorder_writes_one_file_per_finished_call(
    tmp_path: Path, make_client: Any, step_id: str, pair: type[BaseModel]
) -> None:
    out = tmp_path / "scenario"
    fake = FakeOllama(
        [ChatScript(text=VALID, reset_after=2), ChatScript(text="bad"), ChatScript(text=VALID)]
    )
    client = make_client(fake, recorder=CassetteRecorder(out))
    await client.call("vision", "read_key_pages", {"page_no": 3}, pair, step_id=step_id)
    files = sorted(p.name for p in out.iterdir())
    assert files == [
        "001-read_key_pages.json",
        "002-read_key_pages.json",
        "003-read_key_pages.json",
    ]
    cassettes = load_cassettes(out)
    assert [c.status for c in cassettes] == ["error", "invalid", "complete"]
    last = json.loads((out / files[-1]).read_text(encoding="utf-8"))
    assert set(last) == {
        "task",
        "match_key",
        "response_text",
        "thinking_text",
        "logprobs",
        "status",
        "meta",
    }
    assert set(last["meta"]) == {"model", "prompt_hash", "recorded_at", "schema"}
    assert last["meta"]["schema"] == "Pair"
    assert last["match_key"] == match_key("read_key_pages", "Pair", {"page_no": 3})
    assert last["response_text"] == VALID and len(last["logprobs"]) > 0
    # numbering continues after the files already there
    CassetteRecorder(out).record(cassettes[0])
    assert (out / "004-read_key_pages.json").exists()


@pytest.mark.asyncio
async def test_recorder_never_stores_images(
    tmp_path: Path, make_client: Any, step_id: str, pair: type[BaseModel]
) -> None:
    out = tmp_path / "scenario"
    client = make_client(
        FakeOllama([ChatScript(text=VALID)]),
        recorder=CassetteRecorder(out),
        read_image=lambda fid: b"secret-image-bytes",
    )
    await client.call("vision", "read_key_pages", {}, pair, step_id=step_id, images=["F1"])
    text = next(out.iterdir()).read_text(encoding="utf-8")
    assert "F1" not in text and "c2VjcmV0" not in text


@pytest.mark.asyncio
async def test_r4_7_replay_ignores_prompt_hash_and_model(
    tmp_path: Path,
    make_client: Any,
    conn: sqlite3.Connection,
    step_id: str,
    pair: type[BaseModel],
) -> None:
    out = tmp_path / "rec"
    fake = FakeOllama([ChatScript(text=VALID)])
    recorded = await make_client(fake, recorder=CassetteRecorder(out)).call(
        "vision", "read_key_pages", {"page_no": 1}, pair, step_id=step_id
    )
    assert isinstance(recorded, CallResult)
    [cassette] = load_cassettes(out)
    recorded_row = runs.get_llm_call(conn, recorded.llm_call_id)
    assert recorded_row is not None
    assert cassette.meta.prompt_hash == recorded_row.prompt_hash
    assert cassette.meta.model == recorded_row.model

    other_config = parse_models_config({"roles": {"vision": {"model": "vendor/different:tag"}}})
    replay = make_client(
        backend=ReplayBackend.from_dir(out), config=other_config, prompts=OtherPrompts()
    )
    result = await replay.call("vision", "read_key_pages", {"page_no": 1}, pair, step_id=step_id)
    assert isinstance(result, CallResult)
    assert result.parsed == pair(a=7, b="seven")
    row = runs.get_llm_call(conn, result.llm_call_id)
    assert row is not None and row.status == "complete"
    assert row.model == "vendor/different:tag" != cassette.meta.model
    assert row.prompt_hash != cassette.meta.prompt_hash
    assert row.logprobs == cassette.logprobs

    with pytest.raises(CassetteMiss):
        await replay.call("vision", "read_key_pages", {"page_no": 2}, pair, step_id=step_id)
    with pytest.raises(CassetteMiss):  # the one cassette for page 1 was served already
        await replay.call("vision", "read_key_pages", {"page_no": 1}, pair, step_id=step_id)


@pytest.mark.asyncio
async def test_replay_serves_same_key_in_recorded_order(
    make_client: Any, conn: sqlite3.Connection, step_id: str
) -> None:
    client = make_client(backend=ReplayBackend.from_dir(SYNTHETIC / "read_answers_retry"))
    result = await client.call(
        "vision", "read_answers_page", {"page_no": 2}, ReadAnswersOut, step_id=step_id
    )
    assert isinstance(result, CallResult)
    assert isinstance(result.parsed, ReadAnswersOut)
    assert result.parsed.answers[0].value == "B"
    assert [r.status for r in runs.list_llm_calls(conn, step_id)] == ["invalid", "complete"]


@pytest.mark.asyncio
async def test_replayed_error_cassette_is_a_dropped_stream(
    make_client: Any, conn: sqlite3.Connection, step_id: str
) -> None:
    backend = ReplayBackend.from_dir(SYNTHETIC / "drop_then_ok")
    client = make_client(backend=backend)
    result = await client.call(
        "vision", "read_header", {"page_no": 1}, ReadHeaderOut, step_id=step_id
    )
    assert isinstance(result, CallResult)
    assert [r.status for r in runs.list_llm_calls(conn, step_id)] == ["error", "complete"]

    two_drops = ReplayBackend([backend.served[0], backend.served[0]])
    with pytest.raises(StreamDropped):
        await make_client(backend=two_drops).call(
            "vision", "read_header", {"page_no": 1}, ReadHeaderOut, step_id=step_id
        )


def test_synthetic_cassettes_load() -> None:
    cassettes = load_cassettes(SYNTHETIC)
    assert len(cassettes) >= 4
    assert all(isinstance(c, Cassette) for c in cassettes)
    pages = {"read_answers_page": 2, "read_header": 1}
    for c in cassettes:
        assert c.match_key == match_key(c.task, c.meta.schema_ or "", {"page_no": pages[c.task]})


def test_recording_context_sets_the_active_recorder(tmp_path: Path) -> None:
    assert active_recorder() is None
    with recording(tmp_path) as rec:
        assert active_recorder() is rec
    assert active_recorder() is None


def test_etach_record_runs_a_subcommand_with_recording_on(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_client: Any,
    step_id: str,
    pair: type[BaseModel],
) -> None:
    """The CLI plumbing: ``etach record --out <dir> -- schema export …`` with the subcommand
    replaced by one that makes a model call through a client with no explicit recorder."""
    import etach.domain

    seen: dict[str, Any] = {}

    def fake_export(out: Path) -> list[Path]:
        seen["out"] = out
        seen["recorder"] = active_recorder()
        client = make_client(FakeOllama([ChatScript(text=VALID)]))
        asyncio.run(client.call("reasoning", "explain", {}, pair, step_id=step_id))
        return []

    monkeypatch.setattr(etach.domain, "export_schemas", fake_export)
    out = tmp_path / "cassettes" / "scenario"
    code = main(["record", "--out", str(out), "--", "schema", "export", "--out", str(tmp_path)])
    assert code == 0
    assert seen["out"] == tmp_path
    assert seen["recorder"] is not None
    assert [p.name for p in out.iterdir()] == ["001-explain.json"]
    assert active_recorder() is None


def test_etach_record_needs_a_subcommand(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["record", "--out", str(tmp_path)])
