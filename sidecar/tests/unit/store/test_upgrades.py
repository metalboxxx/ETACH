"""R2.8: content upgraders keyed by content_schema_version."""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from etach.store import upgrades
from etach.store.repos import tests


def _v1_to_v2(content: dict[str, Any]) -> dict[str, Any]:
    for section in content["sections"]:
        section["title"] = section["title"].upper()
    return content


def test_r2_8_read_upgrades_and_writes_back(
    conn: sqlite3.Connection, f: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    t = f.make_test(conn)
    assert t.content_schema_version == 1
    monkeypatch.setitem(upgrades.UPGRADERS, 1, _v1_to_v2)
    got = tests.get_test(conn, t.id)
    assert got is not None
    assert got.content_schema_version == 2
    assert got.content.sections[0].title == "CHOOSE THE BEST ANSWER"
    row = conn.execute(
        "SELECT content_schema_version, content FROM tests WHERE id = ?", (t.id,)
    ).fetchone()
    assert row[0] == 2
    assert "CHOOSE THE BEST ANSWER" in row[1]
    assert tests.get_test(conn, t.id) == got  # v2 has no upgrader: a second read is a no-op


def test_upgraders_apply_in_order() -> None:
    calls: list[int] = []

    def step(n: int) -> upgrades.Upgrader:
        def up(c: dict[str, Any]) -> dict[str, Any]:
            calls.append(n)
            return {**c, "v": n + 1}

        return up

    content, version = upgrades.upgrade_content({"v": 1}, 1, {2: step(2), 1: step(1)})
    assert (content, version, calls) == ({"v": 3}, 3, [1, 2])
    assert upgrades.upgrade_content({"v": 5}, 5, {1: step(1)}) == ({"v": 5}, 5)


def test_register_refuses_duplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(upgrades, "UPGRADERS", {})
    upgrades.register(1)(_v1_to_v2)
    with pytest.raises(ValueError):
        upgrades.register(1)(_v1_to_v2)
    assert upgrades.CURRENT_CONTENT_VERSION == 1
