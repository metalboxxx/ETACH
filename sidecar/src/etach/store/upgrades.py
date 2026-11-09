"""Content upgraders keyed by ``content_schema_version`` (data-model §5.5).

``UPGRADERS[v]`` turns the raw content JSON of version ``v`` into version ``v + 1``. Reading a
test (``etach.store.repos.tests.get_test``) applies every registered upgrader in order and writes
the result back. The current version is 1, so no upgrader is registered yet.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["CURRENT_CONTENT_VERSION", "UPGRADERS", "Upgrader", "register", "upgrade_content"]

CURRENT_CONTENT_VERSION = 1

Upgrader = Callable[[dict[str, Any]], dict[str, Any]]

UPGRADERS: dict[int, Upgrader] = {}


def register(from_version: int) -> Callable[[Upgrader], Upgrader]:
    """Decorator: register ``fn`` as the upgrader from ``from_version`` to ``from_version + 1``."""

    def decorate(fn: Upgrader) -> Upgrader:
        if from_version in UPGRADERS:
            raise ValueError(f"an upgrader from version {from_version} is already registered")
        UPGRADERS[from_version] = fn
        return fn

    return decorate


def upgrade_content(
    content: dict[str, Any], version: int, upgraders: dict[int, Upgrader] | None = None
) -> tuple[dict[str, Any], int]:
    """Apply the upgraders from ``version`` on, in order. Returns ``(content, new_version)``;
    the version is unchanged when nothing applies."""
    registry = UPGRADERS if upgraders is None else upgraders
    while version in registry:
        content = registry[version](content)
        version += 1
    return content, version
