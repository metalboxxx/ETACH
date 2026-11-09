"""Purity guards for ``domain/`` (structure.md rule 5, plan R8.1.10).

- ``no_io``: a pytest fixture that makes ``socket.socket``, ``socket.create_connection`` and
  ``sqlite3.connect`` raise ``IOBlocked`` for the duration of a test. Use it with
  ``pytestmark = pytest.mark.usefixtures("no_io")`` after importing it into the test module
  (``from support.guards import no_io``).
- ``forbidden_imports(module_name)``: the forbidden modules that ``module_name`` imports,
  directly or through other ``etach`` modules (checked on the source with ``ast``, so nothing is
  executed). ``assert_pure(module_name)`` asserts that list is empty.
"""

from __future__ import annotations

import ast
import importlib.util
import socket
import sqlite3
from collections.abc import Iterator
from typing import Any

import pytest

__all__ = ["FORBIDDEN", "IOBlocked", "assert_pure", "forbidden_imports", "no_io"]

FORBIDDEN: tuple[str, ...] = ("etach.store", "etach.llm", "httpx", "sqlite3")


class IOBlocked(RuntimeError):
    """Raised when a pure module tries to open a socket or a database."""


def _blocked(what: str) -> Any:
    def raiser(*_args: Any, **_kwargs: Any) -> Any:
        raise IOBlocked(f"{what} is disabled in a purity test")

    return raiser


@pytest.fixture
def no_io(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(socket, "socket", _blocked("socket.socket"))
    monkeypatch.setattr(socket, "create_connection", _blocked("socket.create_connection"))
    monkeypatch.setattr(sqlite3, "connect", _blocked("sqlite3.connect"))
    yield


def _imports(module_name: str) -> list[str]:
    spec = importlib.util.find_spec(module_name)
    if spec is None or spec.origin is None or not spec.origin.endswith(".py"):
        return []
    with open(spec.origin, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), spec.origin)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
            names += [f"{node.module}.{a.name}" for a in node.names]
    return names


def _is_forbidden(name: str) -> bool:
    return any(name == f or name.startswith(f + ".") for f in FORBIDDEN)


def _exists(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):  # "pkg.module.Class" is not a module
        return False


def forbidden_imports(module_name: str) -> list[str]:
    """Forbidden imports reachable from ``module_name`` through ``etach`` modules."""
    seen: set[str] = set()
    found: list[str] = []
    todo = [module_name]
    while todo:
        mod = todo.pop()
        if mod in seen:
            continue
        seen.add(mod)
        for name in _imports(mod):
            if _is_forbidden(name):
                found.append(f"{mod} imports {name}")
            elif name.startswith("etach") and _exists(name):
                todo.append(name)
    return sorted(set(found))


def assert_pure(module_name: str) -> None:
    bad = forbidden_imports(module_name)
    assert not bad, bad
