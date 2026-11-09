"""Step 22.5.7 (R22.5.7.7): GLM-OCR is the default photo reader, so ``glm-ocr`` is a default model.

An empty data folder lists the ``ocr`` role in the settings and the model inventory, checks its
tag in the status and offers it for download; ``photo_reader = "vision"`` keeps today's roles.
Every Ollama here is a fake (:class:`support.fake_ollama.FakeOllama`, the fake pull stream).
"""

from __future__ import annotations

import asyncio
import tomllib
from collections.abc import Callable, Iterator

import pytest
from support.fake_ollama import FakeOllama
from support.reader import vision_reader
from unit.api.test_routes_c import client

from etach.api.deps import AppContext
from etach.api.routes.settings import fake_pull_transport
from etach.llm.defaults import SUGGESTED_TAGS

DEFAULT_ROLES = ("vision", "ocr", "reasoning", "grading_check", "extraction_check")


@pytest.fixture
def empty(make_ctx: Callable[..., AppContext]) -> Iterator[AppContext]:
    """An empty data folder (no ``models.toml``): the built-in defaults."""
    c = make_ctx(vision_reader=False)
    assert not c.paths.models_toml.exists()
    yield c
    c.close()


@pytest.mark.asyncio
async def test_r22_5_7_7_settings_list_the_ocr_role(empty: AppContext) -> None:
    async with client(empty) as c:
        got = (await c.get("/settings")).json()
    assert set(got["roles"]) == set(DEFAULT_ROLES)
    assert got["roles"]["ocr"]["model"] == "glm-ocr"
    assert got["roles"]["vision"]["model"] == "qwen3.5:4b"  # the student answers


@pytest.mark.asyncio
async def test_r22_5_7_7_status_checks_glm_ocr(empty: AppContext) -> None:
    empty.extra["ollama_transport"] = FakeOllama(version="0.13.1", tags=["qwen3.5:4b"]).transport
    empty.extra["other_ollama_transport"] = FakeOllama().transport
    async with client(empty) as c:
        status = (await c.get("/system/status")).json()
    assert status["ollama_status"] == "missing_model"
    assert status["missing_models"] == ["glm-ocr"]
    assert status["models_present"] == ["qwen3.5:4b"]
    # both present: ok
    empty.extra["ollama_transport"] = FakeOllama(
        version="0.13.1", tags=["qwen3.5:4b", "glm-ocr"]
    ).transport
    async with client(empty) as c:
        status = (await c.get("/system/status")).json()
    assert status["ollama_status"] == "ok" and status["missing_models"] == []


@pytest.mark.asyncio
async def test_r22_5_7_7_download_offers_glm_ocr(empty: AppContext) -> None:
    empty.extra["ollama_transport"] = fake_pull_transport()
    async with client(empty) as c:
        r = await c.post("/settings/models/pull")
        assert r.status_code == 202
        assert r.json() == {"models": ["qwen3.5:4b", "glm-ocr"]}
        await asyncio.wait_for(asyncio.gather(*empty.extra["settings.pull_tasks"]), 10)
    assert "glm-ocr" in SUGGESTED_TAGS and SUGGESTED_TAGS[0] == "qwen3.5:4b"


@pytest.mark.asyncio
async def test_r22_5_7_7_model_inventory_names_the_ocr_role(empty: AppContext) -> None:
    async with client(empty) as c:
        body = (await c.get("/models")).json()  # replay: the in-memory fake model list
    assert body["roles"]["ocr"] == "glm-ocr"
    assert "glm-ocr" in body["suggested"]
    by_name = {m["name"]: m["roles"] for m in body["models"]}
    assert by_name["glm-ocr"] == ["ocr"]


@pytest.mark.asyncio
async def test_r22_5_7_7_save_keeps_the_ocr_tag(empty: AppContext) -> None:
    """Saving every role the settings list (as the Models tab does) writes glm-ocr for ocr."""
    async with client(empty) as c:
        roles = (await c.get("/settings")).json()["roles"]
        body = {"roles": {k: {"model": v["model"]} for k, v in roles.items()}}
        r = await c.put("/settings", json=body)
        assert r.status_code == 200, r.text
    on_disk = tomllib.loads(empty.paths.models_toml.read_text(encoding="utf-8"))
    assert on_disk["roles"]["ocr"]["model"] == "glm-ocr"
    assert empty.client.config.extract.photo_reader == "ocr"


@pytest.mark.asyncio
async def test_r22_5_7_7_vision_reader_keeps_todays_roles(
    make_ctx: Callable[..., AppContext],
) -> None:
    ctx = make_ctx(vision_reader=False)
    vision_reader(ctx.paths.root)
    ctx.close()
    ctx = make_ctx(vision_reader=False)  # reads the pinned models.toml
    try:
        async with client(ctx) as c:
            roles = (await c.get("/settings")).json()["roles"]
            assert "ocr" not in roles
            r = await c.post("/settings/models/pull")
            assert r.json() == {"models": ["qwen3.5:4b"]}
            await asyncio.gather(*ctx.extra.get("settings.pull_tasks", set()))
    finally:
        ctx.close()
