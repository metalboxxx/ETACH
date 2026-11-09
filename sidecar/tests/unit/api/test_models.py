"""Step 22.3.5: the model manager routes (R22.3.5.1) and the default tags (R22.3.5.2).

Every Ollama here is :class:`etach.llm.ollama_models.FakeModelStore` or a refusing transport; no
test pulls, deletes or runs a real model.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from starlette.requests import ClientDisconnect
from unit.api.conftest import serving

from etach.api.app import create_app
from etach.api.deps import AppContext
from etach.api.routes import models as models_route
from etach.llm import ollama_models
from etach.llm.config import default_config, load_models_config, write_models_config
from etach.llm.defaults import SUGGESTED_TAGS
from etach.llm.tasks import extraction_inputs
from etach.prompts.render import FilePromptProvider

UNUSED = "smollm2:135m"


@pytest.fixture
def ctx(make_ctx: Callable[..., AppContext]) -> Iterator[AppContext]:
    c = make_ctx()
    yield c
    c.close()


def _roles(ctx: AppContext) -> dict[str, str]:
    return {name: r.model for name, r in ctx.client.config.roles.items()}


@pytest.fixture
def store(ctx: AppContext) -> ollama_models.FakeModelStore:
    s = ollama_models.FakeModelStore([*_roles(ctx).values(), UNUSED], size=1000)
    ctx.extra["ollama_transport"] = s.transport
    return s


@asynccontextmanager
async def client(ctx: AppContext) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(ctx))
    headers = {"Authorization": f"Bearer {ctx.token}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=headers) as c:
        yield c


def _events(body: str) -> list[dict[str, Any]]:
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def _refuse(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("refused", request=request)


# --- R22.3.5.1 ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_models_with_size_and_roles(
    ctx: AppContext, store: ollama_models.FakeModelStore
) -> None:
    roles = _roles(ctx)
    async with client(ctx) as c:
        r = await c.get("/models")
    assert r.status_code == 200
    body = r.json()
    by_name = {m["name"]: m for m in body["models"]}
    assert by_name[UNUSED]["roles"] == [] and by_name[UNUSED]["size"] == 1000
    for role, tag in roles.items():
        assert role in by_name[tag]["roles"]
    assert body["roles"] == roles
    assert body["suggested"] == list(SUGGESTED_TAGS)
    assert body["suggested"][0] == default_config().roles["vision"].model  # defaults first


@pytest.mark.asyncio
async def test_pull_streams_progress_and_ends_success(
    ctx: AppContext, store: ollama_models.FakeModelStore
) -> None:
    published: list[dict[str, Any]] = []
    ctx.events.add_listener(published.append)
    async with client(ctx) as c:
        r = await c.post("/models/pull", json={"name": "tinyllama:1.1b"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = _events(r.text)
        listed = [m["name"] for m in (await c.get("/models")).json()["models"]]
    assert events[0]["status"] == "pulling manifest"
    downloading = [e for e in events if e["status"] == "downloading"]
    assert [e["completed"] for e in downloading] == [250, 500, 750, 1000]
    assert events[-1]["status"] == "success" and events[-1]["model"] == "tinyllama:1.1b"
    assert "tinyllama:1.1b" in listed
    assert [e for e in published if e["type"] == "models.pull_progress"][-1]["status"] == "success"


@pytest.mark.asyncio
async def test_pull_error_in_plain_words(
    ctx: AppContext, store: ollama_models.FakeModelStore
) -> None:
    async with client(ctx) as c:
        store.fail_with = "pull model manifest: file does not exist"
        events = _events((await c.post("/models/pull", json={"name": "nope:1b"})).text)
        assert events[-1]["status"] == "error"
        assert events[-1]["message"] == "No model with this name. Check the spelling of the tag."
        store.fail_with = 'Get "https://registry.ollama.ai/v2/": dial tcp: lookup failed'
        events = _events((await c.post("/models/pull", json={"name": "nope:1b"})).text)
        assert events[-1]["message"].startswith("No internet connection")
        store.fail_with = "write /models/blobs/x: There is not enough space on the disk; no space"
        events = _events((await c.post("/models/pull", json={"name": "nope:1b"})).text)
        assert events[-1]["message"].startswith("Not enough disk space")
        assert (await c.post("/models/pull", json={"name": "bad tag!"})).status_code == 422
        assert (await c.post("/models/pull", json={"name": ""})).status_code == 422
    assert "nope:1b" not in store.models


@pytest.mark.asyncio
async def test_cancel_stops_the_pull_and_leaves_nothing_listed(
    make_ctx: Callable[..., AppContext],
) -> None:
    """Cancel = the app closes the request: over real HTTP, the sidecar closes the stream to
    Ollama, and the half-pulled model is not listed."""
    ctx = make_ctx()
    store = ollama_models.FakeModelStore([UNUSED], size=1000, delay=0.2, steps=50)
    ctx.extra["ollama_transport"] = store.transport
    try:
        async with serving(ctx) as live, live.client(headers=live.auth) as c:
            async with c.stream("POST", "/models/pull", json={"name": "big:70b"}) as r:
                assert r.status_code == 200
                seen = 0
                async for line in r.aiter_lines():
                    if line.startswith("data: ") and '"downloading"' in line:
                        seen += 1
                        if seen == 2:
                            break  # Cancel
            async with asyncio.timeout(10):
                while store.disconnected == 0:
                    await asyncio.sleep(0.05)
            names = [m["name"] for m in (await c.get("/models")).json()["models"]]
            assert "big:70b" not in names
            # the tag is free again: a new pull may start
            async with c.stream("POST", "/models/pull", json={"name": "big:70b"}) as r2:
                assert r2.status_code == 200
    finally:
        ctx.close()


@pytest.mark.asyncio
async def test_downloading_mark_clears_on_a_disconnect_before_the_first_event(
    ctx: AppContext, store: ollama_models.FakeModelStore
) -> None:
    """The app goes away before the stream starts: the tag is free again, Ollama never saw a
    pull."""
    resp = await models_route.pull_model(models_route.PullRequest(name="tinyllama:1.1b"), ctx)
    assert "tinyllama:1.1b" in ctx.extra["models.pulling"]

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        raise OSError("client went away")

    scope = {"type": "http", "asgi": {"spec_version": "2.4"}}
    with pytest.raises((OSError, ClientDisconnect)):
        await resp(scope, receive, send)
    assert ctx.extra["models.pulling"] == set()
    assert store.pulls == []
    async with client(ctx) as c:  # a new pull of the tag starts
        events = _events((await c.post("/models/pull", json={"name": "tinyllama:1.1b"})).text)
    assert events[-1]["status"] == "success"
    assert ctx.extra["models.pulling"] == set()


@pytest.mark.asyncio
async def test_pull_of_a_tag_already_downloading_is_409(
    ctx: AppContext, store: ollama_models.FakeModelStore
) -> None:
    ctx.extra.setdefault("models.pulling", set()).add("tinyllama:1.1b")
    async with client(ctx) as c:
        r = await c.post("/models/pull", json={"name": "TinyLlama:1.1b"})
    assert r.status_code == 409 and r.json()["detail"] == models_route.PULLING


@pytest.mark.asyncio
async def test_delete_unused_used_and_during_a_run(
    ctx: AppContext, store: ollama_models.FakeModelStore
) -> None:
    vision = _roles(ctx)["vision"]
    async with client(ctx) as c:
        r = await c.delete(f"/models/{vision}")
        assert r.status_code == 409
        assert "vision" in r.json()["detail"] and vision in store.models
        real = models_route.runs.list_runs_by_status
        models_route.runs.list_runs_by_status = lambda conn, st: [object()]  # type: ignore[assignment,return-value]
        try:
            r = await c.delete(f"/models/{UNUSED}")
        finally:
            models_route.runs.list_runs_by_status = real  # type: ignore[assignment]
        assert r.status_code == 409 and r.json()["detail"] == models_route.RUN_GOING
        assert (await c.delete(f"/models/{UNUSED}")).status_code == 204
        assert UNUSED not in store.models
        assert (await c.delete(f"/models/{UNUSED}")).status_code == 404
        store.models["org/name:tag"] = 1
        assert (await c.delete("/models/org/name:tag")).status_code == 204  # a tag with "/"


@pytest.mark.asyncio
async def test_ollama_not_running_is_a_readable_503(ctx: AppContext) -> None:
    ctx.extra["ollama_transport"] = httpx.MockTransport(_refuse)
    async with client(ctx) as c:
        for r in (
            await c.get("/models"),
            await c.post("/models/pull", json={"name": "qwen3.5:4b"}),
            await c.delete(f"/models/{UNUSED}"),
        ):
            assert r.status_code == 503
            assert r.json()["detail"] == models_route.OLLAMA_DOWN


@pytest.mark.asyncio
async def test_replay_uses_the_fake_model_list(make_ctx: Callable[..., AppContext]) -> None:
    ctx = make_ctx()
    ctx.replay = True
    try:
        async with client(ctx) as c:
            names = [m["name"] for m in (await c.get("/models")).json()["models"]]
    finally:
        ctx.close()
    assert set(SUGGESTED_TAGS) <= set(names)


# --- R22.3.5.2 ---------------------------------------------------------------------------------


def test_fresh_settings_give_qwen35_4b_for_both_roles(tmp_path: Path) -> None:
    config = load_models_config(tmp_path / "models.toml")  # no file: the defaults
    assert config.roles["vision"].model == "qwen3.5:4b"
    assert config.roles["reasoning"].model == "qwen3.5:4b"
    assert config.roles["vision"].adapter == "chat"


def test_existing_nuextract_models_toml_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "models.toml"
    text = '[roles.vision]\nmodel = "numind/nuextract3:Q6_K"\n'
    path.write_text(text, encoding="utf-8")
    config = load_models_config(path)
    assert path.read_text(encoding="utf-8") == text  # not rewritten
    vision = config.roles["vision"]
    assert vision.model == "numind/nuextract3:Q6_K"
    assert vision.adapter == "nuextract"  # the adapter follows the tag
    assert vision.nuextract_options().also_format is True
    # the teacher picks qwen3.5:4b in Settings: the adapter follows the new tag
    new = write_models_config(path, {"vision": "qwen3.5:4b"})
    assert new.roles["vision"].adapter == "chat" and new.roles["vision"].adapter_options == {}


def test_vision_prompt_profile_for_qwen35_4b() -> None:
    """llm-design §8: profiles are per exam format, not per model tag. Transcription always uses
    the ``generic`` profile, so qwen3.5:4b in the vision role reads with ``generic`` through the
    ``chat`` adapter (the same prompt files the reasoning role uses)."""
    vision = default_config().roles["vision"]
    assert (vision.model, vision.adapter) == ("qwen3.5:4b", "chat")
    provider = FilePromptProvider()
    assert provider.resolve_profile("generic") == "generic"
    assert provider.resolve_profile(None) == "generic"
    rendered = provider.render(
        "transcribe_page", "generic", extraction_inputs("transcribe_page", page_no=1, photo_count=1)
    )
    assert rendered.system  # base/transcribe_page.md + profiles/generic.md
