"""tests, test_pages, question_tags."""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from etach.domain import models as m
from etach.store.repos import files, tests


def _file(fid: str, f: Any) -> m.File:
    return m.File(
        id=fid,
        path=f"files/{fid}",
        kind="upload",
        derived_from=None,
        mime="image/jpeg",
        width=1,
        height=1,
        created_at=f.T0,
    )


def test_insert_get_round_trip(conn: sqlite3.Connection, f: Any) -> None:
    run = f.make_run(conn)
    meta = m.TestMetadata(
        occasion="FinalTerm",
        grade=8,
        term=1,
        test_number="1",
        variant="K",
        units=["U1"],
        extra={"note": "x", "n": 2},
    )
    t = f.make_test(conn, meta=meta, source_run_id=run.id)
    assert t.id == "T-0001"
    assert tests.get_test(conn, t.id) == t
    assert tests.find_by_source_run(conn, run.id) == t
    row = conn.execute("SELECT display_name, occasion, grade FROM tests").fetchone()
    assert tuple(row) == ("Grade 8 - Final Term 1 - Test 1", "FinalTerm", 8)
    assert f.make_test(conn).id == "T-0002"
    assert tests.get_test(conn, "T-9999") is None


def test_source_run_is_unique(conn: sqlite3.Connection, f: Any) -> None:
    run = f.make_run(conn)
    f.make_test(conn, source_run_id=run.id)
    with pytest.raises(sqlite3.IntegrityError):
        f.make_test(conn, source_run_id=run.id)


def test_update_content(conn: sqlite3.Connection, f: Any) -> None:
    t = f.make_test(conn)
    tests.update_content(conn, t.id, f.content(3), 0.75)
    got = tests.get_test(conn, t.id)
    assert got is not None and got.points_possible == 0.75
    assert len(got.content.sections[0].groups[0].questions) == 3


def test_pages_and_tags(conn: sqlite3.Connection, f: Any) -> None:
    t = f.make_test(conn)
    fid = "ab" * 32
    files.insert_file(conn, _file(fid, f))
    tests.add_test_page(conn, t.id, 2, fid)
    tests.add_test_page(conn, t.id, 1, fid)
    assert tests.list_test_pages(conn, t.id) == [(t.id, 1, fid), (t.id, 2, fid)]
    with pytest.raises(sqlite3.IntegrityError):
        tests.add_test_page(conn, t.id, 3, "missing")
    tests.set_question_tags(conn, t.id, "q-1", ["grammar", "tense", "grammar"])
    tests.set_question_tags(conn, t.id, "q-2", ["vocabulary"])
    tests.set_question_tags(conn, t.id, "q-1", ["tense"])
    assert tests.list_question_tags(conn, t.id) == {"q-1": ["tense"], "q-2": ["vocabulary"]}
