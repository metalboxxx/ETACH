"""R8.1.10: every Step 8.1 module is pure (no store, llm, httpx or sqlite3 import), and its
functions run with sockets and the database disabled."""

from __future__ import annotations

import importlib
import socket
import sqlite3

import pytest
from support.guards import IOBlocked, assert_pure, no_io  # noqa: F401

pytestmark = pytest.mark.usefixtures("no_io")

STEP_8_1_MODULES = [
    "etach.domain.pages",
    "etach.domain.renumber",
    "etach.domain.header",
    "etach.domain.pictures",
    "etach.domain.validators",
    "etach.domain.normalize",
    "etach.domain.similarity",
    "etach.domain.keymap",
    "etach.domain.boxes",
    "etach.domain.students",
]


@pytest.mark.parametrize("module", STEP_8_1_MODULES)
def test_module_is_pure(module: str) -> None:
    assert_pure(module)
    importlib.import_module(module)  # importing does no I/O either


def test_guard_is_active() -> None:
    with pytest.raises(IOBlocked):
        socket.socket()
    with pytest.raises(IOBlocked):
        sqlite3.connect(":memory:")
