"""R12.2: the bearer token on every route; ``?token=`` only on ``GET /files/{id}`` and
``GET /events``; the socket is bound to 127.0.0.1.

The tests walk every route of the app, so they cover the routes parts B and C add. Two stub
routes check the mechanism itself while those routes do not exist yet.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute

from etach.api.app import HOST, bind_socket, create_app
from etach.api.auth import QUERY_TOKEN_ATTR, allow_query_token
from etach.api.deps import AppContext

QUERY_TOKEN_ROUTES = {("GET", "/files/{id}"), ("GET", "/events")}


def _normalize(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{id}", path)


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "x", path)


def _with_stubs(ctx: AppContext) -> Any:
    app = create_app(ctx)
    stub = APIRouter()

    @stub.get("/_stub/header")
    def header_only() -> dict[str, bool]:
        return {"ok": True}

    @stub.get("/_stub/query")
    @allow_query_token
    def query_ok() -> dict[str, bool]:
        return {"ok": True}

    from fastapi import Depends

    from etach.api.auth import require_token

    app.include_router(stub, dependencies=[Depends(require_token)])
    return app


def _routes(app: Any) -> list[tuple[str, str, APIRoute]]:
    out = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods):
                out.append((method, route.path, route))
    return out


@pytest.fixture
def ctx(make_ctx: Callable[..., AppContext]) -> AppContext:
    c = make_ctx()
    yield c
    c.close()


@pytest.mark.asyncio
async def test_r12_2_every_route_needs_the_token(ctx: AppContext) -> None:
    app = _with_stubs(ctx)
    routes = _routes(app)
    assert ("GET", "/events") in {(m, p) for m, p, _ in routes}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for method, path, _ in routes:
            url = _concrete(path)
            for headers, params in (
                ({}, {}),
                ({"Authorization": "Bearer wrong"}, {}),
                ({"Authorization": f"Basic {ctx.token}"}, {}),
                ({}, {"token": "wrong"}),
            ):
                r = await client.request(method, url, headers=headers, params=params)
                assert r.status_code == 401, (method, path, headers, params, r.status_code)
            # A correct query token is refused everywhere except the two routes.
            if (method, _normalize(path)) not in QUERY_TOKEN_ROUTES and not path.endswith("/query"):
                r = await client.request(method, url, params={"token": ctx.token})
                assert r.status_code == 401, (method, path)
                # ... even next to a correct bearer token.
                r = await client.request(
                    method,
                    url,
                    params={"token": ctx.token},
                    headers={"Authorization": f"Bearer {ctx.token}"},
                )
                assert r.status_code == 401, (method, path)


def test_r12_2_only_two_routes_accept_a_query_token(ctx: AppContext) -> None:
    app = create_app(ctx)
    marked = {
        (m, _normalize(p))
        for m, p, route in _routes(app)
        if getattr(route.endpoint, QUERY_TOKEN_ATTR, False)
    }
    assert marked <= QUERY_TOKEN_ROUTES
    assert ("GET", "/events") in marked
    if any(_normalize(p) == "/files/{id}" and m == "GET" for m, p, _ in _routes(app)):
        assert ("GET", "/files/{id}") in marked


@pytest.mark.asyncio
async def test_r12_2_stub_routes(ctx: AppContext) -> None:
    app = _with_stubs(ctx)
    transport = httpx.ASGITransport(app=app)
    bearer = {"Authorization": f"Bearer {ctx.token}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/_stub/header", headers=bearer)).status_code == 200
        assert (await client.get("/_stub/header", params={"token": ctx.token})).status_code == 401
        assert (await client.get("/_stub/query", params={"token": ctx.token})).status_code == 200
        assert (await client.get("/_stub/query", headers=bearer)).status_code == 200
        assert (await client.get("/_stub/query", params={"token": "nope"})).status_code == 401
        assert (await client.get("/_stub/query")).status_code == 401
        r = await client.get("/_stub/query", params={"token": "nope"}, headers=bearer)
        assert r.status_code == 401
        assert r.headers["www-authenticate"] == "Bearer"


def test_r12_2_socket_is_bound_to_localhost() -> None:
    sock = bind_socket()
    try:
        host, port = sock.getsockname()
        assert host == HOST == "127.0.0.1"
        assert port > 0
    finally:
        sock.close()
