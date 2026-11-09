"""Fixtures for the llm tests: a migrated database with one step, a stub prompt provider, and a
client factory wired to FakeOllama."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict
from support.fake_ollama import FakeOllama

from etach.domain import models as m
from etach.llm.adapters import RenderedPrompt
from etach.llm.client import OllamaClient
from etach.llm.config import ModelsConfig, default_config
from etach.store import db
from etach.store.repos import runs, threads


class StubPrompts:
    """Renders ``<task> for <inputs>``; records every render."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def render(self, task: str, profile: str, inputs: Mapping[str, Any]) -> RenderedPrompt:
        self.calls.append((task, profile, dict(inputs)))
        return RenderedPrompt.of(f"system for {task} ({profile})", f"{task} for {dict(inputs)}")


class Pair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a: int
    b: str


@pytest.fixture
def pair() -> type[Pair]:
    """A small output schema ``{"a": int, "b": str}``."""
    return Pair


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "data" / "app.db"


@pytest.fixture
def conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    c = db.open_database(db_path)
    yield c
    c.close()


@pytest.fixture
def step_id(conn: sqlite3.Connection) -> str:
    thread = threads.create_thread(conn, "photos")
    run = runs.create_run(
        conn,
        thread.id,
        "extract",
        m.ExtractInput(pages=[], existing_test_id=None, supersedes_attempt_id=None),
    )
    return runs.insert_step(conn, run.id, "transcribe_page", "page 1", 1).id


@pytest.fixture
def prompts() -> StubPrompts:
    return StubPrompts()


@pytest.fixture
def config() -> ModelsConfig:
    return default_config()


MakeClient = Callable[..., OllamaClient]


@pytest.fixture
def make_client(conn: sqlite3.Connection, config: ModelsConfig, prompts: StubPrompts) -> MakeClient:
    def make(fake: FakeOllama | None = None, **kwargs: Any) -> OllamaClient:
        if fake is not None:
            kwargs.setdefault("base_url", "http://fake-ollama")
            kwargs.setdefault("transport", fake.transport)
        kwargs.setdefault("config", config)
        kwargs.setdefault("prompts", prompts)
        return OllamaClient(conn, **kwargs)

    return make
