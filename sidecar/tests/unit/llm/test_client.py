"""client.call: streaming, incremental writes, validation retry, cancellation, dropped streams
(plan R4.1-R4.4)."""

from __future__ import annotations

import asyncio
import base64
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from support.fake_ollama import ChatScript, FakeOllama

from etach.domain import models as m
from etach.llm.client import CallFailure, CallResult, OllamaError, StreamDropped
from etach.llm.config import parse_models_config
from etach.store import db
from etach.store.repos import runs, threads

VALID = '{"a": 1, "b": "x"}'


def rows(conn: sqlite3.Connection, step_id: str) -> list[Any]:
    return runs.list_llm_calls(conn, step_id)


def statuses(conn: sqlite3.Connection, step_id: str) -> list[str]:
    return [r.status for r in rows(conn, step_id)]


# --- R4.1 ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r4_1_streams_200_tokens_with_incremental_writes(
    make_client: Any, conn: sqlite3.Connection, db_path: Path, step_id: str, pair: type[BaseModel]
) -> None:
    tokens = ['{"a": 1, "b": "', *(["x"] * 198), '"}']
    assert len(tokens) == 200
    reader = db.connect(db_path)
    seen: list[tuple[int, str]] = []

    def on_token(i: int) -> None:
        if i in (60, 120, 180):
            row = reader.execute("SELECT response_text, status FROM llm_calls").fetchone()
            seen.append((len(row[0]), row[1]))

    fake = FakeOllama([ChatScript(tokens=tokens)], on_token=on_token)
    client = make_client(fake, flush_seconds=3600.0)
    result = await client.call("reasoning", "demo", {"page_no": 1}, pair, step_id=step_id)
    reader.close()

    assert isinstance(result, CallResult)
    assert result.parsed == pair(a=1, b="x" * 198)
    lengths = [n for n, _ in seen]
    assert len(lengths) == 3
    assert 0 < lengths[0] < lengths[1] < lengths[2]
    assert {status for _, status in seen} == {"streaming"}

    [row] = rows(conn, step_id)
    assert row.status == "complete"
    assert row.prompt_hash and len(row.prompt_hash) == 64
    assert row.response_text == "".join(tokens)
    assert row.tokens_in == 123 and row.tokens_out == 200 and row.ms == 2500
    assert row.logprobs is not None and len(row.logprobs) == 200
    assert row.logprobs[0]["top_logprobs"] and len(row.logprobs[0]["top_logprobs"]) == 5
    assert result.logprobs == row.logprobs and result.llm_call_id == row.id


@pytest.mark.asyncio
async def test_time_based_flush(
    make_client: Any, db_path: Path, step_id: str, pair: type[BaseModel]
) -> None:
    reader = db.connect(db_path)
    seen: list[int] = []

    def on_token(i: int) -> None:
        if i == 5:
            seen.append(len(reader.execute("SELECT response_text FROM llm_calls").fetchone()[0]))

    fake = FakeOllama([ChatScript(text=VALID)], on_token=on_token)
    client = make_client(fake, flush_tokens=10_000, flush_seconds=0.0)
    await client.call("reasoning", "demo", {}, pair, step_id=step_id)
    reader.close()
    assert seen and seen[0] > 0


@pytest.mark.asyncio
async def test_thinking_is_stored_and_request_carries_logprobs(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    fake = FakeOllama([ChatScript(text=VALID, thinking="Let me think about it.")])
    result = await make_client(fake).call(
        "reasoning", "demo", {}, pair, step_id=step_id, think=True, num_predict=400
    )
    assert isinstance(result, CallResult)
    assert result.thinking_text == "Let me think about it."
    [row] = rows(conn, step_id)
    assert row.thinking_text == "Let me think about it."
    body = fake.requests[0]
    assert body["stream"] is True and body["logprobs"] is True and body["top_logprobs"] == 5
    assert body["think"] is True
    assert body["options"]["num_predict"] == 400
    assert row.request["options"]["num_predict"] == 400


# --- R4.2 ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r4_2_invalid_then_valid(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    fake = FakeOllama([ChatScript(text='{"a": "not a number"'), ChatScript(text=VALID)])
    result = await make_client(fake).call("reasoning", "demo", {}, pair, step_id=step_id)
    assert isinstance(result, CallResult)
    assert result.parsed == pair(a=1, b="x")
    assert statuses(conn, step_id) == ["invalid", "complete"]
    first, second = rows(conn, step_id)
    assert result.llm_call_id == second.id
    assert first.response_text == '{"a": "not a number"'
    # the retry carries the validation error; the hash changes with the prompt
    retry_user = fake.requests[1]["messages"][-1]["content"]
    assert "did not match the required JSON schema" in retry_user
    assert "did not match" not in fake.requests[0]["messages"][-1]["content"]
    assert first.prompt_hash != second.prompt_hash


@pytest.mark.asyncio
async def test_r4_2_invalid_twice_returns_failure_without_review_items(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    fake = FakeOllama([ChatScript(text="nope"), ChatScript(text='{"a": 1}')])
    result = await make_client(fake).call("reasoning", "demo", {}, pair, step_id=step_id)
    assert isinstance(result, CallFailure)
    assert result.task == "demo"
    assert result.reason
    assert result.llm_call_ids == [r.id for r in rows(conn, step_id)]
    assert statuses(conn, step_id) == ["invalid", "invalid"]
    assert conn.execute("SELECT COUNT(*) FROM review_items").fetchone()[0] == 0


# --- R4.3 ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r4_3_cancel_mid_stream(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    fake = FakeOllama([ChatScript(text='{"a": 1, "b": "' + "y" * 300 + '"}', hang_after=30)])
    client = make_client(fake, flush_tokens=10)
    task = asyncio.create_task(client.call("reasoning", "demo", {}, pair, step_id=step_id))
    await asyncio.wait_for(fake.hanging.wait(), timeout=10)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    [row] = rows(conn, step_id)
    assert row.status == "cancelled"
    assert row.response_text  # the partial text is kept
    assert len(row.response_text) == 30 * 3
    assert row.logprobs is not None and len(row.logprobs) == 30
    assert fake.client_disconnected
    assert len(fake.requests) == 1  # no retry after a cancel


# --- R4.4 ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r4_4_reset_once_then_success(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    fake = FakeOllama([ChatScript(text=VALID, reset_after=3), ChatScript(text=VALID)])
    result = await make_client(fake).call("reasoning", "demo", {}, pair, step_id=step_id)
    assert isinstance(result, CallResult)
    assert statuses(conn, step_id) == ["error", "complete"]
    assert rows(conn, step_id)[0].response_text == VALID[:9]  # partial text kept on the error row
    assert fake.requests[0] == fake.requests[1]  # a drop retries the same request


@pytest.mark.asyncio
async def test_r4_4_reset_twice_raises_stream_dropped(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    fake = FakeOllama([ChatScript(text=VALID, reset_after=2)])
    with pytest.raises(StreamDropped) as info:
        await make_client(fake).call("reasoning", "demo", {}, pair, step_id=step_id)
    assert statuses(conn, step_id) == ["error", "error"]
    assert info.value.llm_call_ids == [r.id for r in rows(conn, step_id)]


@pytest.mark.asyncio
async def test_stream_without_final_chunk_counts_as_a_drop(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    fake = FakeOllama([ChatScript(text=VALID, omit_done=True), ChatScript(text=VALID)])
    result = await make_client(fake).call("reasoning", "demo", {}, pair, step_id=step_id)
    assert isinstance(result, CallResult)
    assert statuses(conn, step_id) == ["error", "complete"]


@pytest.mark.asyncio
async def test_drop_and_validation_retries_are_separate_budgets(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    fake = FakeOllama(
        [
            ChatScript(text="bad json"),
            ChatScript(text=VALID, reset_after=2),
            ChatScript(text=VALID),
        ]
    )
    result = await make_client(fake).call("reasoning", "demo", {}, pair, step_id=step_id)
    assert isinstance(result, CallResult)
    assert statuses(conn, step_id) == ["invalid", "error", "complete"]
    # the drop retry repeats the prompt that carries the validation note
    assert fake.requests[1] == fake.requests[2]


@pytest.mark.asyncio
async def test_http_error_marks_row_error_and_raises(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    fake = FakeOllama([ChatScript(text=VALID, status_code=500)])
    with pytest.raises(OllamaError):
        await make_client(fake).call("reasoning", "demo", {}, pair, step_id=step_id)
    assert statuses(conn, step_id) == ["error"]


@pytest.mark.asyncio
async def test_error_chunk_raises(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    fake = FakeOllama([ChatScript(text=VALID, error_chunk="out of memory")])
    with pytest.raises(OllamaError, match="out of memory"):
        await make_client(fake).call("reasoning", "demo", {}, pair, step_id=step_id)
    assert statuses(conn, step_id) == ["error"]


# --- images and the stored request -------------------------------------------------------------


@pytest.mark.asyncio
async def test_images_sent_as_base64_but_stored_as_file_ids(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    data = {"F1": b"\x89PNG one", "F2": b"\x89PNG two"}
    fake = FakeOllama([ChatScript(text=VALID)])
    client = make_client(fake, read_image=data.__getitem__)
    await client.call("vision", "demo", {}, pair, step_id=step_id, images=["F1", "F2"])
    sent = fake.requests[0]["messages"][-1]["images"]
    assert [base64.b64decode(s) for s in sent] == [data["F1"], data["F2"]]
    [row] = rows(conn, step_id)
    assert row.request["messages"][-1]["images"] == [{"file_id": "F1"}, {"file_id": "F2"}]
    stored = json.dumps(row.request)
    assert base64.b64encode(data["F1"]).decode() not in stored
    assert row.role == "vision"


@pytest.mark.asyncio
async def test_images_without_reader_is_an_error(
    make_client: Any, step_id: str, pair: type[BaseModel]
) -> None:
    with pytest.raises(ValueError, match="read_image"):
        await make_client(FakeOllama()).call(
            "vision", "demo", {}, pair, step_id=step_id, images=["F1"]
        )


@pytest.mark.asyncio
async def test_prompt_hash_depends_on_prompt_and_schema(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    class Other(BaseModel):
        a: int
        b: str
        c: int = 0

    fake = FakeOllama([ChatScript(text=VALID)])
    client = make_client(fake)
    await client.call("reasoning", "demo", {"page_no": 1}, pair, step_id=step_id)
    await client.call("reasoning", "demo", {"page_no": 1}, pair, step_id=step_id)
    await client.call("reasoning", "demo", {"page_no": 2}, pair, step_id=step_id)
    await client.call("reasoning", "demo", {"page_no": 1}, Other, step_id=step_id)
    hashes = [r.prompt_hash for r in rows(conn, step_id)]
    assert hashes[0] == hashes[1]
    assert len({hashes[0], hashes[2], hashes[3]}) == 3


def test_repo_stream_update_is_a_no_op_after_the_final_status(conn: sqlite3.Connection) -> None:
    """The llm_calls update functions the client uses (store/repos/runs.py)."""
    thread_step = runs.insert_step(
        conn,
        runs.create_run(
            conn,
            threads.create_thread(conn, "t").id,
            "extract",
            m.ExtractInput(pages=[], existing_test_id=None, supersedes_attempt_id=None),
        ).id,
        "node",
        None,
        1,
    )
    call = runs.insert_llm_call(
        conn,
        m.LlmCall(
            id=db.new_ulid(),
            step_id=thread_step.id,
            role="reasoning",
            model="m",
            prompt_hash="h",
            request={},
            response_text="",
            thinking_text="",
            logprobs=None,
            status="streaming",
            tokens_in=None,
            tokens_out=None,
            ms=None,
            created_at=datetime.now(UTC),
        ),
    )
    lp = [{"token": "a", "logprob": -0.1}]
    assert runs.update_llm_call_stream(
        conn, call.id, response_text="ab", thinking_text="t", logprobs=lp
    )
    runs.set_llm_call_counts(conn, call.id, tokens_in=3, tokens_out=2, ms=10)
    runs.set_llm_call_status(conn, call.id, "complete")
    assert not runs.update_llm_call_stream(
        conn, call.id, response_text="stale", thinking_text="", logprobs=None
    )
    row = runs.get_llm_call(conn, call.id)
    assert row is not None
    assert (row.status, row.response_text, row.thinking_text, row.logprobs) == (
        "complete",
        "ab",
        "t",
        lp,
    )
    assert (row.tokens_in, row.tokens_out, row.ms) == (3, 2, 10)
    with pytest.raises(KeyError):
        runs.set_llm_call_status(conn, "missing", "error")
    with pytest.raises(KeyError):
        runs.set_llm_call_counts(conn, "missing", tokens_in=None, tokens_out=None, ms=None)


# --- B1: a prompt that does not fit num_ctx fails loudly ---------------------------------------

#: A prompt of ~40k characters: at least 5000 text tokens, possibly more than num_ctx 16384.
BIG = {"blob": "word " * 8000}


def _with_num_ctx(config: Any, num_ctx: int) -> Any:
    role = config.roles["reasoning"]
    roles = {**config.roles, "reasoning": role.model_copy(update={"options": {"num_ctx": num_ctx}})}
    return config.model_copy(update={"roles": roles})


def test_prompt_size_bounds() -> None:
    from etach.llm.client import prompt_size

    body = {
        "messages": [
            {"role": "system", "content": "x" * 800},
            {"role": "user", "content": "y" * 800, "images": ["a", "b"]},
        ]
    }
    size = prompt_size(body)
    assert size.text_floor == 200
    assert size.floor == 200 + 2 * 256
    assert size.ceiling == 800 + 2 * 4096


@pytest.mark.asyncio
async def test_b1_body_asks_ollama_not_to_truncate(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    fake = FakeOllama([ChatScript(text=VALID)])
    await make_client(fake).call("reasoning", "demo", {}, pair, step_id=step_id)
    assert fake.requests[0]["truncate"] is False
    [row] = rows(conn, step_id)
    assert row.request["truncate"] is False


@pytest.mark.asyncio
async def test_b1_low_prompt_eval_count_is_a_truncation_failure(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    """The M1 baseline: Ollama kept only the image (~1929 tokens) of a 16k+ prompt."""
    fake = FakeOllama([ChatScript(text=VALID, prompt_eval_count=1929)])
    result = await make_client(fake).call("reasoning", "demo", BIG, pair, step_id=step_id)
    assert isinstance(result, CallFailure)
    assert result.reason.startswith("prompt_truncated:")
    assert "1929" in result.reason
    assert len(fake.requests) == 1  # no retry: the same prompt would be cut again
    [row] = rows(conn, step_id)
    assert result.llm_call_ids == [row.id]
    assert row.status == "error"
    assert row.tokens_in == 1929
    assert row.response_text == VALID  # kept for debugging, never read as a result


@pytest.mark.asyncio
async def test_b1_full_prompt_eval_count_passes(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    fake = FakeOllama([ChatScript(text=VALID, prompt_eval_count=12_000)])
    result = await make_client(fake).call("reasoning", "demo", BIG, pair, step_id=step_id)
    assert isinstance(result, CallResult)
    assert statuses(conn, step_id) == ["complete"]


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 123])
async def test_b1_small_prompt_or_unknown_count_is_not_checked(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel], count: int
) -> None:
    """A prompt that surely fits is never flagged, and 0 (cassette replay) means unknown."""
    big = BIG if count == 0 else {}
    fake = FakeOllama([ChatScript(text=VALID, prompt_eval_count=count)])
    result = await make_client(fake).call("reasoning", "demo", big, pair, step_id=step_id)
    assert isinstance(result, CallResult)


@pytest.mark.asyncio
async def test_b1_prompt_over_num_ctx_fails_before_the_call(
    make_client: Any, conn: sqlite3.Connection, config: Any, step_id: str, pair: type[BaseModel]
) -> None:
    fake = FakeOllama([ChatScript(text=VALID)])
    client = make_client(fake, config=_with_num_ctx(config, 2048))
    result = await client.call("reasoning", "demo", BIG, pair, step_id=step_id)
    assert isinstance(result, CallFailure)
    assert result.reason.startswith("prompt_truncated:")
    assert "num_ctx 2048" in result.reason
    assert fake.requests == []  # Ollama was never asked
    [row] = rows(conn, step_id)
    assert row.status == "error" and row.request["truncate"] is False


@pytest.mark.asyncio
async def test_b1_ollama_context_error_is_a_truncation_failure(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    fake = FakeOllama(
        [ChatScript(text=VALID, error_chunk="the input length exceeds the context length")]
    )
    result = await make_client(fake).call("reasoning", "demo", {}, pair, step_id=step_id)
    assert isinstance(result, CallFailure)
    assert result.reason.startswith("prompt_truncated:")
    assert statuses(conn, step_id) == ["error"]


# --- speed bundle 1: no invalid-retry on an output cut at num_predict ------------------------


class ScriptedBackend:
    """A ``ChatBackend`` that answers each call with one content chunk and a final chunk with
    the given ``done_reason`` and ``eval_count`` (a fake Ollama response)."""

    def __init__(self, answers: list[tuple[str, str, int]]) -> None:
        self.answers = list(answers)  # (content, done_reason, eval_count)
        self.bodies: list[dict[str, Any]] = []

    async def stream(self, body: Any, *, task: str, match_key: str) -> Any:
        self.bodies.append(dict(body))
        content, done_reason, eval_count = self.answers.pop(0)
        yield {"message": {"role": "assistant", "content": content}, "done": False}
        yield {
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "done_reason": done_reason,
            "prompt_eval_count": 10,
            "eval_count": eval_count,
            "total_duration": 1_000_000,
        }


CUT = '{"a": 1, "b": "a very long answer that never'
#: the reasoning role retries a capped output by default (grading, until M2): these tests turn
#: it off to test the no-retry rule on the same small fake
NO_RETRY = parse_models_config({"client": {"retry_capped_output": {"reasoning": False}}})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("done_reason", "eval_count"),
    [("length", 1500), ("length", 37), ("stop", 1500), ("stop", 1600)],
)
async def test_capped_invalid_output_is_not_retried(
    make_client: Any,
    conn: sqlite3.Connection,
    step_id: str,
    pair: type[BaseModel],
    done_reason: str,
    eval_count: int,
) -> None:
    """``done_reason: "length"``, or ``tokens_out`` ≥ ``num_predict`` (1500): one call, the row
    ``invalid``, a failure whose reason starts with ``output_capped:``."""
    backend = ScriptedBackend([(CUT, done_reason, eval_count), (VALID, "stop", 5)])
    client = make_client(backend=backend, config=NO_RETRY)
    result = await client.call("reasoning", "demo", {}, pair, step_id=step_id, num_predict=1500)
    assert isinstance(result, CallFailure)
    assert result.reason.startswith("output_capped:")
    assert "1500" in result.reason
    assert len(backend.bodies) == 1  # no retry
    [row] = rows(conn, step_id)
    assert result.llm_call_ids == [row.id]
    assert row.status == "invalid" and row.tokens_out == eval_count
    assert row.response_text == CUT


@pytest.mark.asyncio
async def test_uncapped_invalid_output_keeps_its_retry(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    backend = ScriptedBackend([('{"a": "x"}', "stop", 8), (VALID, "stop", 5)])
    client = make_client(backend=backend, config=NO_RETRY)
    result = await client.call("reasoning", "demo", {}, pair, step_id=step_id, num_predict=1500)
    assert isinstance(result, CallResult)
    assert len(backend.bodies) == 2
    assert statuses(conn, step_id) == ["invalid", "complete"]


@pytest.mark.asyncio
async def test_capped_retry_ends_the_call_with_output_capped(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    """An uncapped invalid output is retried; a capped retry fails as ``output_capped``."""
    backend = ScriptedBackend([('{"a": "x"}', "stop", 8), (CUT, "length", 1500)])
    result = await make_client(backend=backend, config=NO_RETRY).call(
        "reasoning", "demo", {}, pair, step_id=step_id, num_predict=1500
    )
    assert isinstance(result, CallFailure)
    assert result.reason.startswith("output_capped:")
    assert statuses(conn, step_id) == ["invalid", "invalid"]


@pytest.mark.asyncio
async def test_capped_but_valid_output_is_a_result(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    """Only an invalid output is a failure: a valid one that used every token is kept."""
    backend = ScriptedBackend([(VALID, "length", 1500)])
    result = await make_client(backend=backend, config=NO_RETRY).call(
        "reasoning", "demo", {}, pair, step_id=step_id, num_predict=1500
    )
    assert isinstance(result, CallResult)
    assert statuses(conn, step_id) == ["complete"]


@pytest.mark.asyncio
async def test_without_num_predict_only_done_reason_counts(
    make_client: Any, conn: sqlite3.Connection, step_id: str, pair: type[BaseModel]
) -> None:
    backend = ScriptedBackend([('{"a": "x"}', "stop", 99_999), (VALID, "stop", 5)])
    result = await make_client(backend=backend, config=NO_RETRY).call(
        "reasoning", "demo", {}, pair, step_id=step_id
    )
    assert isinstance(result, CallResult)
    assert len(backend.bodies) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(("role", "retries"), [("reasoning", True), ("vision", False)])
async def test_capped_retry_default_is_per_role(
    make_client: Any,
    conn: sqlite3.Connection,
    step_id: str,
    pair: type[BaseModel],
    role: str,
    retries: bool,
) -> None:
    """The defaults: grading (reasoning) keeps the retry of a capped output until M2 reworks
    ``verify_key``; extraction (vision) fails it at once as ``output_capped``."""
    backend = ScriptedBackend([(CUT, "length", 1500), (VALID, "stop", 5)])
    result = await make_client(backend=backend).call(
        role, "demo", {}, pair, step_id=step_id, num_predict=1500
    )
    if retries:
        assert isinstance(result, CallResult)
        assert statuses(conn, step_id) == ["invalid", "complete"]
    else:
        assert isinstance(result, CallFailure) and result.reason.startswith("output_capped:")
        assert statuses(conn, step_id) == ["invalid"]
