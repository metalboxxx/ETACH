"""The version/model check (R4.5) and the other-Ollama detector (R4.9).

No test touches port 11434 (the teacher may run Ollama there): the detector is tested against a
real HTTP server on a free local port, which is an approved deviation from R4.9's wording.
"""

from __future__ import annotations

import socket

import httpx
import pytest
from support.fake_ollama import FakeOllama, FakeOllamaServer

from etach.llm import defaults
from etach.llm.config import parse_models_config
from etach.llm.ollama_status import check, normalize_tag, other_ollama_loaded, parse_version

# two different tags (the defaults now share qwen3.5:4b, D4)
ROLES = list(
    parse_models_config({"roles": {"vision": {"model": "numind/nuextract3:Q6_K"}}}).roles.values()
)
TAGS = list(dict.fromkeys(r.model for r in ROLES))  # the four roles use two tags


@pytest.mark.asyncio
async def test_r4_5_too_old() -> None:
    fake = FakeOllama(version="0.12.10", tags=TAGS)
    status = await check("http://fake", ROLES, transport=fake.transport)
    assert status.status == "too_old" and status.version == "0.12.10"


@pytest.mark.asyncio
async def test_r4_5_ok() -> None:
    fake = FakeOllama(version="0.12.11", tags=TAGS)
    status = await check("http://fake", ROLES, transport=fake.transport)
    assert status.status == "ok" and status.version == "0.12.11" and status.missing == []


@pytest.mark.asyncio
async def test_r4_5_missing_model() -> None:
    fake = FakeOllama(version="0.13.0", tags=TAGS[:1])
    status = await check("http://fake", ROLES, transport=fake.transport)
    assert status.status == "missing_model"
    assert status.missing == TAGS[1:]


@pytest.mark.asyncio
async def test_unreachable() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    status = await check("http://fake", ROLES, transport=httpx.MockTransport(refuse))
    assert status.status == "unreachable"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("0.12.11", (0, 12, 11)), ("v0.13.2-rc1", (0, 13, 2)), ("1.0", (1, 0, 0)), ("dev", None)],
)
def test_parse_version(text: str, expected: tuple[int, int, int] | None) -> None:
    assert parse_version(text) == expected


def test_normalize_tag() -> None:
    assert normalize_tag("Vendor/Model:Q6_K") == normalize_tag("vendor/model:q6_k")
    assert normalize_tag("model") == "model:latest"
    assert normalize_tag("registry.ollama.ai/library/model:1b") == "model:1b"


def test_detector_default_is_the_standard_port() -> None:
    assert defaults.DEFAULT_OLLAMA_URL == "http://127.0.0.1:11434"
    assert other_ollama_loaded.__defaults__ == (defaults.DEFAULT_OLLAMA_URL,)


@pytest.mark.asyncio
async def test_r4_9_detector_loaded_model() -> None:
    with FakeOllamaServer(loaded=["some-model:latest"]) as server:
        assert server.port != 11434
        assert await other_ollama_loaded(server.base_url) is True


@pytest.mark.asyncio
async def test_r4_9_detector_nothing_loaded() -> None:
    with FakeOllamaServer(loaded=[]) as server:
        assert await other_ollama_loaded(server.base_url) is False


@pytest.mark.asyncio
async def test_r4_9_detector_nothing_listening() -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    assert port != 11434
    assert await other_ollama_loaded(f"http://127.0.0.1:{port}") is False


@pytest.mark.asyncio
async def test_detector_with_injected_transport() -> None:
    loaded = FakeOllama(loaded=["m:1"])
    assert await other_ollama_loaded("http://x", transport=loaded.transport) is True
    assert await other_ollama_loaded("http://x", transport=FakeOllama().transport) is False
