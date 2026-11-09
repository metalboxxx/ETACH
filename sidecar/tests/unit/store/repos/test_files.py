"""files rows."""

from __future__ import annotations

import sqlite3
from typing import Any

from etach.domain import models as m
from etach.store.repos import files


def test_files(conn: sqlite3.Connection, f: Any) -> None:
    up = m.File(
        id="a1",
        path="files/a1/a1.jpg",
        kind="upload",
        derived_from=None,
        mime="image/jpeg",
        width=10,
        height=20,
        created_at=f.T0,
    )
    der = up.model_copy(
        update={"id": "b2", "path": "files/b2/b2.jpg", "kind": "derived", "derived_from": "a1"}
    )
    assert files.insert_file(conn, up) == up
    assert files.insert_file(conn, der) == der
    assert files.insert_file(conn, up.model_copy(update={"width": 99})) == up  # same content id
    assert files.list_files(conn) == [up, der]
    assert files.get_file(conn, "zz") is None
