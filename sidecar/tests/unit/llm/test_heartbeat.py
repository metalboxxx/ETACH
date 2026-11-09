"""Step 22.1.3, R22.1.3.2 (client half): while a call streams, the step's token listener hears
``(step_id, tokens so far)`` at most every ``heartbeat_seconds`` (a fake clock here), never per
token; v4.24 (R22.2.1.5): the beats start with the call, also while no token has come yet; a
cancelled call stops the beats and the row is ``cancelled``."""

from __future__ import annotations

import asyncio
import sqlite3
from typing import Any

import pytest
from pydantic import BaseModel
from support.fake_ollama import ChatScript, FakeOllama

from etach.llm.client import HEARTBEAT_SECONDS, CallResult, token_listener
from etach.store.repos import runs


def _tokens(n: int) -> list[str]:
    return ['{"a": 1, "b": "', *(["x"] * (n - 2)), '"}']


async def _call(
    make_client: Any, step_id: str, pair: type[BaseModel], n: int, seconds_per_token: float
) -> tuple[Any, list[tuple[str, int]]]:
    clock = [0.0]
    beats: list[tuple[str, int]] = []

    def on_token(i: int) -> None:
        clock[0] += seconds_per_token

    fake = FakeOllama([ChatScript(tokens=_tokens(n))], on_token=on_token)
    client = make_client(fake, clock=lambda: clock[0])
    reset = token_listener.set(lambda sid, tokens: beats.append((sid, tokens)))
    try:
        result = await client.call("reasoning", "demo", {}, pair, step_id=step_id)
    finally:
        token_listener.reset(reset)
    return result, beats


def test_the_heartbeat_is_at_most_5_seconds() -> None:
    assert 0 < HEARTBEAT_SECONDS <= 5


@pytest.mark.asyncio
async def test_a_12_second_call_beats_at_least_twice(
    make_client: Any, step_id: str, pair: type[BaseModel]
) -> None:
    result, beats = await _call(make_client, step_id, pair, n=120, seconds_per_token=0.1)
    assert isinstance(result, CallResult)
    assert len(beats) >= 2
    assert len(beats) <= 12 / HEARTBEAT_SECONDS + 1  # throttled, not per token
    assert {sid for sid, _ in beats} == {step_id}
    tokens = [t for _, t in beats]
    assert tokens == sorted(set(tokens)) and tokens[-1] <= 120


@pytest.mark.asyncio
async def test_a_short_call_beats_once_at_its_start(
    make_client: Any, step_id: str, pair: type[BaseModel]
) -> None:
    """v4.24: the beats start with the call (tokens 0), so even a short call gives one."""
    result, beats = await _call(make_client, step_id, pair, n=30, seconds_per_token=0.1)
    assert isinstance(result, CallResult)
    assert beats == [(step_id, 0)]


@pytest.mark.asyncio
async def test_the_wait_for_the_first_token_beats(
    make_client: Any, step_id: str, pair: type[BaseModel]
) -> None:
    """R22.2.1.5: a first token after 12 s (fake clock and sleep) still gets >= 2 beats first."""
    clock = [0.0]
    beats: list[tuple[str, int]] = []

    async def fake_sleep(seconds: float) -> None:
        clock[0] += seconds
        await asyncio.sleep(0)

    async def on_token(i: int) -> None:
        while i == 0 and clock[0] < 12.0:
            await asyncio.sleep(0)

    fake = FakeOllama([ChatScript(tokens=_tokens(10))], on_token=on_token)
    client = make_client(fake, clock=lambda: clock[0], sleep=fake_sleep)
    reset = token_listener.set(lambda sid, tokens: beats.append((sid, tokens)))
    try:
        result = await client.call("reasoning", "demo", {}, pair, step_id=step_id)
    finally:
        token_listener.reset(reset)
    assert isinstance(result, CallResult)
    before_first_token = [b for b in beats if b[1] == 0]
    assert len(before_first_token) >= 2 + 1  # the start beat, then >= 2 during the wait
    assert {sid for sid, _ in beats} == {step_id}


@pytest.mark.asyncio
async def test_no_listener_no_beats(make_client: Any, step_id: str, pair: type[BaseModel]) -> None:
    fake = FakeOllama([ChatScript(tokens=_tokens(60))])
    client = make_client(fake, heartbeat_seconds=0.0)
    assert token_listener.get() is None
    assert isinstance(await client.call("reasoning", "demo", {}, pair, step_id=step_id), CallResult)


@pytest.mark.asyncio
async def test_cancel_mid_stream_stops_the_beats(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    clock = [0.0]
    beats: list[int] = []
    task: asyncio.Task[Any] | None = None

    async def on_token(i: int) -> None:
        clock[0] += 1.0
        if i == 50 and task is not None:
            task.cancel()
            await asyncio.sleep(0)

    fake = FakeOllama([ChatScript(tokens=_tokens(120))], on_token=on_token)
    client = make_client(fake, clock=lambda: clock[0])

    async def run() -> Any:
        token_listener.set(lambda sid, tokens: beats.append(tokens))
        return await client.call("reasoning", "demo", {}, pair, step_id=step_id)

    task = asyncio.create_task(run())
    with pytest.raises(asyncio.CancelledError):
        await task
    assert beats and max(beats) <= 50
    [row] = runs.list_llm_calls(conn, step_id)
    assert row.status == "cancelled"
