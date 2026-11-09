"""R2.10: backup via VACUUM INTO, restore into a new data folder."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from etach.store import backup, db
from etach.store.repos import attempts, keys, review, students, tests


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = [
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
    ]
    return {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}


def test_r2_10_backup_restore_same_row_counts(
    conn: sqlite3.Connection, f: Any, tmp_path: Path
) -> None:
    from datetime import UTC, datetime

    from etach.domain import models as m

    s = students.create_student(conn, "Học Sinh A", "hoc sinh a")
    t = f.make_test(conn)
    f.make_test(conn)
    tests.set_question_tags(conn, t.id, "q-1", ["grammar"])
    a = f.make_attempt(conn, t.id, s.id)
    attempts.insert_answers(conn, [f.answer(a.id, "q-1"), f.answer(a.id, "q-2")])
    keys.upsert_key(
        conn,
        m.AnswerKey(
            test_id=t.id,
            question_id="q-1",
            accepted=["A"],
            reason_vi=None,
            source="ai",
            status="ai_unverified",
            confidence=None,
            updated_at=datetime.now(UTC),
        ),
    )
    review.upsert_item(
        conn, kind="unknown_student", owner="extract", dedupe_key="k", proposal={}, attempt_id=a.id
    )
    f.make_llm_call(conn)
    before = _counts(conn)
    assert before["tests"] == 2 and before["answers"] == 2

    dest = backup.backup(conn, tmp_path / "backups" / "b1.db")
    assert dest.is_file()
    with pytest.raises(backup.BackupError):
        backup.backup(conn, dest)  # never overwrites

    paths = backup.restore(dest, tmp_path / "restored")
    assert paths.db == (tmp_path / "restored" / "app.db").resolve()
    assert paths.files_dir.is_dir()
    restored = db.open_database(paths.db)
    try:
        assert _counts(restored) == before
        assert db.search_tests(restored, "final") == db.search_tests(conn, "final")
        assert tests.get_test(restored, t.id) == tests.get_test(conn, t.id)
    finally:
        restored.close()


def test_restore_refuses_a_non_empty_folder(conn: sqlite3.Connection, tmp_path: Path) -> None:
    dest = backup.backup(conn, tmp_path / "b.db")
    target = tmp_path / "busy"
    target.mkdir()
    (target / "app.db").write_text("live data")
    with pytest.raises(backup.BackupError, match="not empty"):
        backup.restore(dest, target)
    assert (target / "app.db").read_text() == "live data"
    with pytest.raises(backup.BackupError, match="no backup"):
        backup.restore(tmp_path / "missing.db", tmp_path / "new")
