"""The toy graph for the run-runtime tests (plan step 7).

``prepare`` → ``pages`` (a self-loop over 3 items, "page 1" … "page 3") → ``combine`` →
``finish``. Every execution of a node makes exactly one ``client.call`` through FakeOllama
(:class:`ToyOllama`) and writes only to graph state and ``llm_calls`` (P8). ``finish`` records the
final state in :attr:`ToyRecorder.final` (the checkpoint is purged once the run is done).

:class:`ToyOllama` answers every call with a JSON object derived from the call's task and inputs,
so the final state is deterministic however often a node is restarted. Its ``on_call_token``
hook sees ``(call key, token index)`` before each streamed token (call key =
``"<node>|<item>"``); the tests use it to Stop in the middle of a call. Every answer ends with a
whitespace token, so a Stop just before that token leaves a ``cancelled`` row whose partial text
is already valid JSON (plan R7.7).

Run as a script (``python toy_graph.py <app.db>``, with ``sidecar/tests`` on ``PYTHONPATH``) it
starts a run manager on the database with a ToyOllama that hangs in the middle of the ``page 2``
call and prints ``HANG`` (plan R7.2: the test kills the process there).
"""

from __future__ import annotations

import asyncio
import inspect
import json
import operator
import sqlite3
import sys
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict

from etach.domain.models import ExtractInput
from etach.llm.adapters import RenderedPrompt
from etach.llm.client import CallFailure, OllamaClient
from etach.llm.config import default_config
from etach.runtime.manager import GraphFactory
from etach.runtime.steps import current_run, current_step_id, report_progress, step
from support.fake_ollama import ChatScript, FakeOllama, tokenize

__all__ = [
    "PAGES",
    "TOY_STEPS",
    "ToyOllama",
    "ToyOut",
    "ToyPrompts",
    "ToyRecorder",
    "ToyState",
    "make_client",
    "toy_factory",
    "toy_input",
]

PAGES = 3
TOY_STEPS: list[tuple[str, str | None]] = [
    ("prepare", None),
    *[("pages", f"page {p}") for p in range(1, PAGES + 1)],
    ("combine", None),
    ("finish", None),
]
"""Every node execution of an uninterrupted toy run, in order: 6 steps, 6 model calls."""

_MARK = "toy::"


class ToyOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str
    n: int


class ToyPrompts:
    """Puts the task and inputs in the system prompt (``toy::<json>``) for ToyOllama to read."""

    def render(self, task: str, profile: str, inputs: Mapping[str, Any]) -> RenderedPrompt:
        payload = json.dumps({"task": task, "inputs": dict(inputs)}, sort_keys=True)
        return RenderedPrompt.of(_MARK + payload, f"Answer the {task} call.")


def call_key(task: str, inputs: Mapping[str, Any]) -> str:
    return f"{task}|{inputs.get('item')}"


def answer(task: str, inputs: Mapping[str, Any]) -> dict[str, Any]:
    item = inputs.get("item")
    return {"value": f"{task}:{item}", "n": len(task) * 10 + len(str(item))}


def answer_tokens(task: str, inputs: Mapping[str, Any]) -> list[str]:
    return [*tokenize(json.dumps(answer(task, inputs))), " "]


TokenHook = Callable[[str, int], Awaitable[None] | None]


class ToyOllama(FakeOllama):
    """FakeOllama whose answer depends on the request (see the module docstring)."""

    def __init__(
        self, on_call_token: TokenHook | None = None, drops: Mapping[str, int] | None = None
    ) -> None:
        super().__init__(on_token=self._token)
        self.on_call_token = on_call_token
        self.drops = dict(drops or {})  # call key -> how many more requests reset mid-stream
        self.keys: list[str] = []  # the call key of every /api/chat request, in order

    def _decode(self, body: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        system = body["messages"][0]["content"]
        assert system.startswith(_MARK), system
        payload = json.loads(system[len(_MARK) :])
        return payload["task"], payload["inputs"]

    def _script(self) -> ChatScript:
        task, inputs = self._decode(self.requests[-1])
        key = call_key(task, inputs)
        self.keys.append(key)
        if self.drops.get(key, 0) > 0:
            self.drops[key] -= 1
            return ChatScript(tokens=answer_tokens(task, inputs), reset_after=2)
        return ChatScript(tokens=answer_tokens(task, inputs))

    async def _token(self, index: int) -> None:
        if self.on_call_token is None:
            return
        result = self.on_call_token(self.keys[-1], index)
        if inspect.isawaitable(result):
            await result


def make_client(conn: sqlite3.Connection, fake: FakeOllama) -> OllamaClient:
    return OllamaClient(
        conn,
        default_config(),
        ToyPrompts(),
        base_url="http://fake-ollama",
        transport=fake.transport,
    )


class ToyState(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    total: Annotated[int, operator.add]
    page: int
    summary: str


@dataclass
class ToyRecorder:
    final: dict[str, dict[str, Any]] = field(default_factory=dict)  # run_id -> final state


def toy_input() -> ExtractInput:
    return ExtractInput(pages=[], existing_test_id=None, supersedes_attempt_id=None)


def toy_factory(client: OllamaClient, recorder: ToyRecorder | None = None) -> GraphFactory:
    """A registry factory for the toy graph (``manager.register("extract", toy_factory(...))``)."""
    rec = recorder if recorder is not None else ToyRecorder()

    async def ask(task: str, **inputs: Any) -> ToyOut:
        result = await client.call("reasoning", task, inputs, ToyOut, step_id=current_step_id())
        if isinstance(result, CallFailure):
            raise RuntimeError(f"toy call failed: {result.reason}")
        assert isinstance(result.parsed, ToyOut)
        return result.parsed

    async def prepare(state: ToyState) -> dict[str, Any]:
        out = await ask("prepare", item=None)
        return {"log": [out.value], "total": out.n, "page": 0}

    async def pages(state: ToyState) -> dict[str, Any]:
        page = state["page"] + 1
        out = await ask("pages", item=f"page {page}")
        report_progress(page, PAGES, f"page {page}")
        return {"log": [out.value], "total": out.n, "page": page}

    async def combine(state: ToyState) -> dict[str, Any]:
        out = await ask("combine", item=None, seen=len(state["log"]))
        return {"log": [out.value], "total": out.n}

    async def finish(state: ToyState) -> dict[str, Any]:
        out = await ask("finish", item=None)
        update = {"log": [out.value], "total": out.n, "summary": " / ".join(state["log"])}
        final = dict(state)
        final["log"] = [*state["log"], out.value]
        final["total"] = state["total"] + out.n
        final["summary"] = update["summary"]
        rec.final[current_run().run_id] = final
        return update

    def page_item(state: ToyState) -> str:
        return f"page {state['page'] + 1}"

    def more_pages(state: ToyState) -> str:
        return "pages" if state["page"] < PAGES else "combine"

    def factory(checkpointer: Any) -> Any:
        builder = StateGraph(ToyState)
        builder.add_node("prepare", step("prepare", prepare))
        builder.add_node("pages", step("pages", pages, item=page_item))
        builder.add_node("combine", step("combine", combine))
        builder.add_node("finish", step("finish", finish))
        builder.add_edge(START, "prepare")
        builder.add_edge("prepare", "pages")
        builder.add_conditional_edges("pages", more_pages, ["pages", "combine"])
        builder.add_edge("combine", "finish")
        builder.add_edge("finish", END)
        return builder.compile(checkpointer=checkpointer)

    return factory


# --- the crash subprocess (plan R7.2) --------------------------------------------------------


async def _crash_main(db_path: Path) -> None:
    from etach.runtime.manager import RunManager
    from etach.runtime.power import FakePower
    from etach.store import db

    async def hang(key: str, index: int) -> None:
        if key == "pages|page 2" and index == 2:
            print("HANG", flush=True)
            await asyncio.Event().wait()

    fake = ToyOllama(on_call_token=hang)
    manager = RunManager(db_path, power=FakePower())
    manager.register("extract", toy_factory(make_client(db.connect(db_path), fake)))
    await manager.start()
    print("STARTED", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(_crash_main(Path(sys.argv[1])))
