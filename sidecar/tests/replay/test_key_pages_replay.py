"""R22.2.5.1 (data-model v1.12, teacher's answer 10): the key photos a test was extracted with are
kept in ``test_key_pages``.

A replayed ``key-photo`` extract run stores its key pages; a sweep keeps their files;
``GET /tests/{id}`` returns them in ``key_pages``; a merge moves them to the survivor when it has
none (and leaves a survivor's own key photos alone); deleting the test removes the rows and a later
sweep the files; migration 0004 applies on an existing (version 3) database.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from support.reader import vision_reader

from etach import cli
from etach.api.routes import tests as test_routes
from etach.appdir import resolve_data_dir
from etach.domain import merge
from etach.store import db
from etach.store.files import FileStore
from etach.store.repos import deletes, tests

from .test_extract_replay import CASSETTES

SCENARIO = CASSETTES / "extract-synthetic" / "key-photo"
LATER = datetime.now(UTC) + timedelta(days=3)


def _replay(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> tuple[sqlite3.Connection, str]:
    data = tmp_path / "data"
    vision_reader(data)  # recorded with the vision reader (R22.5.7.7)
    code = cli.main(["run", "--data", str(data), "--replay", str(SCENARIO)])
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    out: dict[str, Any] = json.loads(lines[-1])
    assert code == 0 and out["status"] == "done", lines
    conn = db.open_database(data / "app.db")
    test = tests.find_by_source_run(conn, out["run_id"])
    assert test is not None
    return conn, test.id


def _copy_test(conn: sqlite3.Connection, test_id: str) -> str:
    src = tests.get_test(conn, test_id)
    new_id = tests.next_test_id(conn)
    tests.insert_test(conn, src.model_copy(update={"id": new_id, "source_run_id": None}))
    return new_id


def _file_ids(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT id FROM files")}


def test_key_photos_are_kept_moved_and_deleted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    conn, test_id = _replay(tmp_path, capsys)
    try:
        store = FileStore(conn, resolve_data_dir(tmp_path / "data").ensure())
        rows = tests.list_key_pages(conn, test_id)
        input_pages = json.loads((SCENARIO / "input.json").read_text(encoding="utf-8"))["pages"]
        assert len(rows) == sum(1 for p in input_pages if p.get("is_key")) == 2
        key_files = {r[2] for r in rows}
        assert not {r[2] for r in tests.list_test_pages(conn, test_id)} & key_files

        store.sweep(now=LATER)  # the files are no longer swept
        assert key_files <= _file_ids(conn)
        for fid in key_files:
            assert store.abspath(fid).exists()

        detail = test_routes._detail(conn, test_id)
        assert [(p.page_no, p.file_id) for p in detail.key_pages] == [(r[1], r[2]) for r in rows]

        # a survivor with its own key photo keeps it; the merged test's stay put
        own = _copy_test(conn, test_id)
        tests.add_key_page(conn, own, 9, rows[0][2])
        merge.merge(conn, merged_test_id=test_id, survivor_test_id=own, alignment={}, ref="R-x")
        assert [r[1] for r in tests.list_key_pages(conn, own)] == [9]
        assert tests.list_key_pages(conn, test_id) == rows

        # a survivor with none gets them
        survivor = _copy_test(conn, own)
        conn.execute("DELETE FROM test_key_pages WHERE test_id = ?", (own,))
        conn.execute("UPDATE test_key_pages SET test_id = ? WHERE test_id = ?", (own, test_id))
        merge.merge(conn, merged_test_id=own, survivor_test_id=survivor, alignment={}, ref="R-y")
        moved = tests.list_key_pages(conn, survivor)
        assert {r[2] for r in moved} == key_files and not tests.list_key_pages(conn, own)

        # deleting the test removes the rows, and a later sweep the files
        deletes.delete_test(conn, deletes.plan_test_delete(conn, survivor))
        deletes.delete_test(conn, deletes.plan_test_delete(conn, test_id))
        assert conn.execute("SELECT COUNT(*) FROM test_key_pages").fetchone()[0] == 0
        store.sweep(now=LATER)
        assert not key_files & _file_ids(conn)
    finally:
        conn.close()


def test_migration_0004_applies_on_an_existing_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    every = db.list_migrations()
    monkeypatch.setattr(db, "list_migrations", lambda: [m for m in every if m[0] < 4])
    old = db.open_database(tmp_path / "app.db")
    assert (
        old.execute("SELECT COUNT(*) FROM sqlite_master WHERE name = 'test_key_pages'").fetchone()[
            0
        ]
        == 0
    )
    old.close()
    monkeypatch.setattr(db, "list_migrations", lambda: every)
    new = db.open_database(tmp_path / "app.db")
    try:
        cols = [r[1] for r in new.execute("PRAGMA table_info(test_key_pages)")]
        assert cols == ["test_id", "page_no", "file_id"]
        versions = [r[0] for r in new.execute("SELECT version FROM schema_migrations")]
        assert 4 in versions and versions[-1] >= 5  # 0005: step 22.2.7, 0006: 22.3.4
    finally:
        new.close()
