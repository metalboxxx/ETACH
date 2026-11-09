"""models.toml loading (R4.6: changing models.toml changes the request's model field)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from support.fake_ollama import ChatScript, FakeOllama

from etach.appdir import resolve_data_dir
from etach.llm import defaults
from etach.llm.config import (
    ConfigError,
    load_models_config,
    parse_models_config,
    write_models_config,
)


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    cfg = load_models_config(resolve_data_dir(tmp_path / "data"))
    assert cfg.roles["vision"].model == defaults.DEFAULT_ROLES["vision"]["model"]
    assert cfg.roles["vision"].adapter == "chat"  # D4 (step 22.3.5): qwen3.5:4b
    assert cfg.roles["reasoning"].adapter == "chat"
    assert cfg.confidence.fallback is None


def test_partial_file_merges_over_defaults(tmp_path: Path) -> None:
    path = tmp_path / "models.toml"
    path.write_text(
        '[roles.vision]\nmodel = "vendor/other-vision:q4"\nadapter = "nuextract"\n'
        "options = { num_ctx = 8192 }\n"
        'adapter_options = { also_format = true }\n\n[confidence]\nfallback = "resample"\n',
        encoding="utf-8",
    )
    cfg = load_models_config(path)
    vision = cfg.roles["vision"]
    assert vision.model == "vendor/other-vision:q4"
    assert vision.options == {"num_ctx": 8192, "temperature": 0, "seed": 42}
    assert vision.nuextract_options().also_format is True
    assert cfg.roles["reasoning"].model == defaults.DEFAULT_ROLES["reasoning"]["model"]
    assert cfg.confidence.fallback == "resample"


@pytest.mark.parametrize(
    "data",
    [
        {"roles": {"vision": {"adapter": "llama"}}},
        {"roles": {"vision": {"adapter_options": {"nope": 1}}}},
        {"roles": {"reasoning": {"adapter_options": {"also_format": True}}}},
        {"roles": {"audio": {"model": "x", "adapter": "chat"}}},
        {"confidence": {"fallback": "guess"}},
        {"extra": {}},
    ],
)
def test_bad_config_is_rejected(data: dict[str, Any]) -> None:
    with pytest.raises(ConfigError):
        parse_models_config(data)


def test_switching_adapter_drops_the_old_adapter_options() -> None:
    cfg = parse_models_config({"roles": {"vision": {"adapter": "chat"}}})
    assert cfg.roles["vision"].adapter_options == {}


def test_retranscribe_tiles_is_off_by_default_and_can_be_turned_on(tmp_path: Path) -> None:
    """Speed bundle 1: ``[extract] retranscribe_tiles`` defaults to off (llm/defaults.py)."""
    assert defaults.DEFAULT_EXTRACT["retranscribe_tiles"] is False
    assert load_models_config(tmp_path / "missing.toml").extract.retranscribe_tiles is False
    path = tmp_path / "models.toml"
    path.write_text("[extract]\nretranscribe_tiles = true\n", encoding="utf-8")
    cfg = load_models_config(path)
    assert cfg.extract.retranscribe_tiles is True
    assert cfg.roles["vision"].model == defaults.DEFAULT_ROLES["vision"]["model"]


@pytest.mark.parametrize(
    "data",
    [
        {"extract": {"retranscribe_tiles": "maybe"}},
        {"extract": {"tiles": True}},
        {"extract": "on"},
    ],
)
def test_bad_extract_table_is_rejected(data: dict[str, Any]) -> None:
    with pytest.raises(ConfigError):
        parse_models_config(data)


def test_write_models_config_keeps_the_extract_table(tmp_path: Path) -> None:
    path = tmp_path / "models.toml"
    path.write_text("[extract]\nretranscribe_tiles = true\n", encoding="utf-8")
    cfg = write_models_config(path, {"vision": "vendor/other-vision:q4"})
    assert cfg.extract.retranscribe_tiles is True
    assert load_models_config(path).extract.retranscribe_tiles is True


def test_bad_toml_is_a_config_error(tmp_path: Path) -> None:
    path = tmp_path / "models.toml"
    path.write_text("[roles.vision\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_models_config(path)


@pytest.mark.asyncio
async def test_r4_6_models_toml_changes_the_request_model(
    tmp_path: Path,
    make_client: Any,
    conn: sqlite3.Connection,
    step_id: str,
    pair: type[BaseModel],
) -> None:
    paths = resolve_data_dir(tmp_path / "data")
    results = []
    for tag in (None, "vendor/other-vision:q4"):
        if tag is not None:
            paths.models_toml.write_text(f'[roles.vision]\nmodel = "{tag}"\n', encoding="utf-8")
        fake = FakeOllama([ChatScript(text='{"a": 1, "b": "x"}')])
        client = make_client(fake, config=load_models_config(paths))
        await client.call("vision", "demo", {}, pair, step_id=step_id)
        results.append(fake.requests[0]["model"])
    assert results == [defaults.DEFAULT_ROLES["vision"]["model"], "vendor/other-vision:q4"]


def test_retry_capped_output_is_per_role(tmp_path: Path) -> None:
    """Off for extraction (vision), on for grading (reasoning) until M2; set per role."""
    want = {
        "vision": False,
        "reasoning": True,
        "grading_check": True,
        "extraction_check": False,
        "ocr": False,
    }
    assert {"retry_capped_output": want} == defaults.DEFAULT_CLIENT
    cfg = load_models_config(tmp_path / "missing.toml")
    assert cfg.client.retry_capped_output == want
    assert cfg.client.retries_capped("vision") is False
    assert cfg.client.retries_capped("reasoning") is True
    path = tmp_path / "models.toml"
    path.write_text("[client]\nretry_capped_output = { vision = true }\n", encoding="utf-8")
    assert load_models_config(path).client.retry_capped_output == {
        **want,
        "vision": True,
    }  # merged per role over the defaults
    cfg = write_models_config(path, {"vision": "vendor/other-vision:q4"})
    assert cfg.client.retries_capped("vision") is True
    for bad in ({"retry": True}, {"retry_capped_output": True}, {"retry_capped_output": {"x": 1}}):
        with pytest.raises(ConfigError):
            parse_models_config({"client": bad})
