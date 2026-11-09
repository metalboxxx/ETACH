"""R22.2.4.5 + R22.2.7.2: migrations 0003 and 0005 remake stored test names once with
``display_name()``'s pattern, keep a name the teacher edited, leave ``updated_at`` alone, and
search finds the new names and the occasion codes."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from etach.domain import models as m
from etach.store import db

CASES: list[dict[str, Any]] = json.loads(
    (Path(__file__).parents[1] / "domain" / "title_line_cases.json").read_text(encoding="utf-8")
)
METAS = [c["meta"] for c in CASES if not c["meta"].get("edited_fields")] + [
    {"occasion": "UnitTest", "grade": 6, "year": "2026", "school": ""},
    {"occasion": "Other:unknown", "source": "Series B", "test_number": "3"},
    {"occasion": "Other:unknown"},
    {"occasion": "Placement", "grade": 0, "term": 2},
]


_SEARCH_ROWS = "-- search rows:"


def _sql() -> str:
    """Migrations 0003 and 0005 in order, as an existing database runs them, then 0007's search
    row part (v1.17, the occasion label): the stored name then equals today's ``display_name()``."""
    found = db.list_migrations()
    (sql7,) = [s for v, _, s in found if v == 7]
    return "\n".join([*(s for v, _, s in found if v in (3, 5)), sql7[sql7.index(_SEARCH_ROWS) :]])


def _age(conn: sqlite3.Connection, test_id: str) -> None:
    """Put the pre-v1.11 name back, as an existing database has it."""
    old = "Grade 8 · FinalTerm HK1 · Test 7"
    conn.execute("UPDATE tests SET display_name = ? WHERE id = ?", (old, test_id))
    meta_text = conn.execute(
        "SELECT meta_text FROM tests_fts WHERE test_id = ?", (test_id,)
    ).fetchone()[0]
    occasion = conn.execute("SELECT occasion FROM tests WHERE id = ?", (test_id,)).fetchone()[0]
    label = conn.execute("SELECT label FROM occasions WHERE code = ?", (occasion,)).fetchone()
    if label:  # before v1.17 the label was not there
        meta_text = meta_text.removesuffix(label[0]).strip()
    old_text = meta_text.removesuffix(occasion).strip()  # before v1.11 the code was not there
    conn.execute(
        "UPDATE tests_fts SET display_name = ?, meta_text = ? WHERE test_id = ?",
        (old, old_text, test_id),
    )


@pytest.mark.parametrize("meta", METAS, ids=[str(x) for x in METAS])
def test_migration_name_equals_display_name(
    conn: sqlite3.Connection, f: Any, meta: dict[str, Any]
) -> None:
    t = f.make_test(conn, meta=m.TestMetadata(**meta))
    _age(conn, t.id)
    before = conn.execute("SELECT updated_at FROM tests WHERE id = ?", (t.id,)).fetchone()[0]
    conn.executescript(_sql())
    row = conn.execute(
        "SELECT display_name, updated_at FROM tests WHERE id = ?", (t.id,)
    ).fetchone()
    assert row[0] == t.meta.display_name()
    assert row[1] == before
    fts = conn.execute(
        "SELECT display_name, meta_text FROM tests_fts WHERE test_id = ?", (t.id,)
    ).fetchone()
    assert fts[0] == t.meta.display_name()
    label = conn.execute(
        "SELECT label FROM occasions WHERE code = ?", (t.meta.occasion,)
    ).fetchone()
    assert fts[1] == db._meta_text(t.meta, label[0] if label else None)


def test_edited_name_is_kept_and_search_finds_new_names_and_codes(
    conn: sqlite3.Connection, f: Any
) -> None:
    a = f.make_test(
        conn, meta=m.TestMetadata(occasion="FinalTerm", grade=8, term=1, test_number="7")
    )
    b = f.make_test(conn, meta=m.TestMetadata(occasion="EntranceExam", grade=9))
    _age(conn, a.id)
    kept = b.meta.model_copy(update={"edited_fields": ["display_name"]})
    conn.execute(
        "UPDATE tests SET display_name = 'Mine', meta = ? WHERE id = ?",
        (kept.model_dump_json(), b.id),
    )
    conn.executescript(_sql())
    names = dict(conn.execute("SELECT id, display_name FROM tests").fetchall())
    assert names[a.id] == "Grade 8 - Final Term 1 - Test 7"
    assert names[b.id] == "Mine"
    assert db.search_tests(conn, "final term 1") == [a.id]
    assert db.search_tests(conn, "finalterm") == [a.id]
    assert db.search_tests(conn, "entranceexam") == [b.id]


def test_write_test_meta_remakes_the_name(conn: sqlite3.Connection, f: Any) -> None:
    t = f.make_test(conn, meta=m.TestMetadata(occasion="MidTerm", grade=7))
    db.write_test_meta(conn, t.id, {"term": 2, "school": "THCS A"}, by_teacher=True)
    row = conn.execute("SELECT display_name FROM tests WHERE id = ?", (t.id,)).fetchone()
    assert row[0] == "Grade 7 - Mid-term 2 - THCS A"
    assert db.search_tests(conn, "midterm") == [t.id]


def test_0005_remakes_automatic_names_only(conn: sqlite3.Connection, f: Any) -> None:
    """R22.2.7.2: "Unit Test" / an unknown occasion left out; a typed name kept; updated_at kept."""
    (sql5,) = [s for v, _, s in db.list_migrations() if v == 5]
    a = f.make_test(conn, meta=m.TestMetadata(occasion="UnitTest", grade=7, year="2025"))
    b = f.make_test(
        conn,
        meta=m.TestMetadata(occasion="Other:unknown", grade=8, year="2025", test_number="3"),
    )
    c = f.make_test(conn, meta=m.TestMetadata(occasion="FifteenMinuteTest", grade=6))
    db.write_test_meta(conn, c.id, {"display_name": "Mine"}, by_teacher=True)
    conn.execute("UPDATE tests SET display_name = 'Grade 7 - Unit - 2025' WHERE id = ?", (a.id,))
    conn.execute("UPDATE tests SET display_name = 'Grade 8 - unknown' WHERE id = ?", (b.id,))
    conn.execute(
        "UPDATE tests_fts SET display_name = 'Grade 7 - Unit - 2025' WHERE test_id = ?", (a.id,)
    )
    before = dict(conn.execute("SELECT id, updated_at FROM tests").fetchall())
    conn.executescript(sql5)
    names = dict(conn.execute("SELECT id, display_name FROM tests").fetchall())
    assert names[a.id] == "Grade 7 - Unit Test - 2025"
    assert names[b.id] == "Grade 8 - 2025 - Test 3"
    assert names[c.id] == "Mine"
    assert dict(conn.execute("SELECT id, updated_at FROM tests").fetchall()) == before
    assert db.search_tests(conn, "unit test") == [a.id]
    assert db.search_tests(conn, "mine") == [c.id]
