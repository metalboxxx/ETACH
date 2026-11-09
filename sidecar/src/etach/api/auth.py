"""The sidecar's auth rule (llm-design §2, PRD §11, plan R12.2).

Every route needs ``Authorization: Bearer <token>``. Only the routes marked with
:func:`allow_query_token` (``GET /files/{id}`` and ``GET /events``: ``<img>`` and ``EventSource``
cannot send headers) also accept ``?token=<token>``. Every other route rejects a query token,
even the right one. A missing or wrong token → 401. Tokens are compared in constant time.

:func:`require_token` is applied to every router by :func:`etach.api.app.create_app`; route
modules do not add it themselves.
"""

from __future__ import annotations

import hmac
import secrets
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request, status

__all__ = ["QUERY_TOKEN_ATTR", "allow_query_token", "new_token", "require_token", "token_ok"]

QUERY_TOKEN_ATTR = "__etach_query_token__"


def new_token() -> str:
    return secrets.token_urlsafe(32)


def allow_query_token[F: Callable[..., Any]](endpoint: F) -> F:
    """Mark an endpoint as also accepting ``?token=``. Put it *below* the router decorator::

    @router.get("/events")
    @allow_query_token
    async def events(...): ...
    """
    setattr(endpoint, QUERY_TOKEN_ATTR, True)
    return endpoint


def token_ok(given: str | None, expected: str) -> bool:
    if given is None:
        return False
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def require_token(request: Request) -> None:
    """The FastAPI dependency that enforces the rule above."""
    expected: str = request.app.state.token
    endpoint = request.scope.get("endpoint")
    query_allowed = bool(getattr(endpoint, QUERY_TOKEN_ATTR, False))

    header = request.headers.get("authorization")
    bearer: str | None = None
    if header is not None:
        scheme, _, value = header.partition(" ")
        if scheme.lower() != "bearer" or not token_ok(value.strip(), expected):
            raise _unauthorized("wrong token")
        bearer = value
    query = request.query_params.get("token")
    if query is not None:
        if not query_allowed:
            raise _unauthorized("this route does not accept a query token")
        if not token_ok(query, expected):
            raise _unauthorized("wrong token")
    if bearer is None and query is None:
        raise _unauthorized("missing token")
