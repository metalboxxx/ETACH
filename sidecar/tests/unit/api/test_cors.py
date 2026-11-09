"""CORS (llm-design §2): only the Tauri webview and loopback pages may call the sidecar from a
browser; a preflight needs no token, every real request still does."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from etach.api.deps import AppContext

ALLOWED = [
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "http://127.0.0.1:4173",
    "http://localhost:5173",
]
FOREIGN = [
    "https://evil.example",
    "http://127.0.0.1:4173.evil.example",
    "http://localhost.evil.example:80",
    "https://127.0.0.1:4173",
    "http://192.168.1.5:4173",
    "null",
]


@pytest.mark.parametrize("origin", ALLOWED)
@pytest.mark.asyncio
async def test_allowed_origin_gets_the_header(
    origin: str, make_ctx: Callable[..., AppContext], api: Any
) -> None:
    async with api.serving(make_ctx()) as live, live.client() as c:
        r = await c.get("/review/count", headers={**live.auth, "Origin": origin})
        assert r.status_code == 200
        assert r.headers["access-control-allow-origin"] == origin
        assert "access-control-allow-credentials" not in r.headers


@pytest.mark.parametrize("origin", FOREIGN)
@pytest.mark.asyncio
async def test_foreign_origin_gets_no_header(
    origin: str, make_ctx: Callable[..., AppContext], api: Any
) -> None:
    async with api.serving(make_ctx()) as live, live.client() as c:
        r = await c.get("/review/count", headers={**live.auth, "Origin": origin})
        assert "access-control-allow-origin" not in r.headers
        pre = await c.options(
            "/review/count",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert pre.status_code != 200
        assert "access-control-allow-origin" not in pre.headers


@pytest.mark.asyncio
async def test_preflight_needs_no_token(make_ctx: Callable[..., AppContext], api: Any) -> None:
    async with api.serving(make_ctx()) as live, live.client() as c:
        pre = await c.options(
            "/threads",
            headers={
                "Origin": "http://127.0.0.1:4173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization, content-type",
            },
        )
        assert pre.status_code == 200
        assert pre.headers["access-control-allow-origin"] == "http://127.0.0.1:4173"
        methods = {m.strip() for m in pre.headers["access-control-allow-methods"].split(",")}
        assert {"GET", "POST", "PUT", "PATCH", "DELETE"} <= methods
        headers = pre.headers["access-control-allow-headers"].lower()
        for h in ("authorization", "content-type", "last-event-id"):
            assert h in headers


@pytest.mark.asyncio
async def test_cross_origin_request_still_needs_the_token(
    make_ctx: Callable[..., AppContext], api: Any
) -> None:
    async with api.serving(make_ctx()) as live, live.client() as c:
        r = await c.get("/review/count", headers={"Origin": "http://127.0.0.1:4173"})
        assert r.status_code == 401
