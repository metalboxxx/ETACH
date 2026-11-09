# ruff: noqa: E501
"""etach.store.db: schema (R2.1), migrations (R2.2), pragmas (R2.3), write_test_meta (R2.4, R2.5),
search, transactions, and the weak-point view (R2.9)."""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from etach.domain import models as m
from etach.store import db
from etach.store.repos import attempts, explanations, tests

# --- R2.1: expected schema, written by hand from the data-model.md v1.2 §3 text ---------------
# (column, declared type, NOT NULL, default as SQLite reports it, position in the primary key)
# fmt: off
EXPECTED_COLUMNS: dict[str, list[tuple[str, str, int, str | None, int]]] = {
    "students": [
        ("id", "TEXT", 0, None, 1), ("full_name", "TEXT", 1, None, 0), ("name_search", "TEXT", 1, None, 0),
        ("class_name", "TEXT", 0, None, 0), ("school", "TEXT", 0, None, 0), ("grade", "INTEGER", 0, None, 0),
        ("notes", "TEXT", 0, "''", 0), ("created_at", "TEXT", 1, None, 0),
    ],
    "tests": [
        ("id", "TEXT", 0, None, 1), ("display_name", "TEXT", 1, None, 0),
        ("occasion", "TEXT", 1, None, 0), ("grade", "INTEGER", 0, None, 0), ("year", "TEXT", 0, None, 0),
        ("school", "TEXT", 0, None, 0), ("term", "INTEGER", 0, None, 0), ("test_number", "TEXT", 0, None, 0),
        ("created_by_ai", "INTEGER", 1, "0", 0), ("parent_test_id", "TEXT", 0, None, 0),
        ("meta", "JSON", 1, None, 0), ("content", "JSON", 1, None, 0), ("content_schema_version", "INTEGER", 1, None, 0),
        ("fingerprint", "TEXT", 1, None, 0), ("points_possible", "REAL", 1, None, 0),
        ("source_run_id", "TEXT", 0, None, 0), ("merged_into", "TEXT", 0, None, 0),
        ("created_at", "TEXT", 1, None, 0), ("updated_at", "TEXT", 1, None, 0),
    ],
    "test_pages": [
        ("test_id", "TEXT", 1, None, 1), ("page_no", "INTEGER", 1, None, 2), ("file_id", "TEXT", 1, None, 0),
    ],
    "test_key_pages": [  # migration 0004 (data-model v1.12)
        ("test_id", "TEXT", 1, None, 1), ("page_no", "INTEGER", 1, None, 2), ("file_id", "TEXT", 1, None, 0),
    ],
    "key_forms_pending": [("test_id", "TEXT", 0, None, 1)],
    "regrade_pending": [("test_id", "TEXT", 0, None, 1), ("since", "TEXT", 1, None, 0)],  # 0010 (step 22.4.5): tests whose keys changed since the last re-grade
    "equal_points_pending": [("id", "INTEGER", 0, None, 1)],  # 0009 (step 22.4.4): one row until the first-start pass  # 0006 (step 22.3.4): tests whose keys get the forms once
    "series": [  # 0011 (step 22.5.2): the series list the teacher edits
        ("id", "INTEGER", 0, None, 1), ("name", "TEXT", 1, None, 0), ("position", "INTEGER", 1, None, 0),
    ],
    "test_text_pending": [("id", "INTEGER", 0, None, 1)],  # 0011: one row until the first-start pass
    "answer_form_pending": [("id", "INTEGER", 0, None, 1)],  # 0012 (step 22.5.3): one row until the first-start pass
    "key_photo_pending": [("id", "INTEGER", 0, None, 1)],  # 0015 (step 22.5.6): one row until the first-start pass
    "difficulty_notes_pending": [("id", "INTEGER", 0, None, 1)],  # 0013 (step 22.5.4): one row until the first-start pass
    "schools": [  # 0008 (step 22.4.2): the school list the teacher edits
        ("id", "INTEGER", 0, None, 1), ("name", "TEXT", 1, None, 0), ("position", "INTEGER", 1, None, 0),
    ],
    "occasions": [  # 0007 (step 22.3.7): the occasion list the teacher edits
        ("code", "TEXT", 0, None, 1), ("label", "TEXT", 1, None, 0), ("short_name", "TEXT", 1, None, 0),
        ("position", "INTEGER", 1, None, 0), ("builtin", "INTEGER", 1, None, 0),
    ],
    "answer_keys": [
        ("test_id", "TEXT", 1, None, 1), ("question_id", "TEXT", 1, None, 2),
        ("accepted", "JSON", 1, None, 0), ("reason_vi", "TEXT", 0, None, 0), ("source", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0), ("confidence", "REAL", 0, None, 0), ("updated_at", "TEXT", 1, None, 0),
        ("checker", "JSON", 0, None, 0),  # 0014 (step 22.5.5): the checker's answer on an unsure key
    ],
    "question_tags": [
        ("test_id", "TEXT", 1, None, 1), ("question_id", "TEXT", 1, None, 2), ("tag", "TEXT", 1, None, 3),
        ("level", "TEXT", 0, None, 0),  # 0014 (step 22.5.5): the question's level from tag_skills
    ],
    "attempts": [
        ("id", "TEXT", 0, None, 1), ("test_id", "TEXT", 1, None, 0),
        ("thread_id", "TEXT", 1, None, 0), ("student_id", "TEXT", 0, None, 0),
        ("student_name_read", "TEXT", 0, None, 0), ("class_read", "TEXT", 0, None, 0), ("source_run_id", "TEXT", 1, None, 0),
        ("superseded_by", "TEXT", 0, None, 0), ("status", "TEXT", 1, None, 0), ("version", "INTEGER", 1, "1", 0),
        ("score_earned", "REAL", 0, None, 0), ("score_possible", "REAL", 0, None, 0), ("created_at", "TEXT", 1, None, 0),
        ("taken_on", "TEXT", 0, None, 0),  # 0014 (step 22.5.5): the date taken
    ],
    "attempt_pages": [
        ("attempt_id", "TEXT", 1, None, 1), ("page_no", "INTEGER", 1, None, 2),
        ("file_id", "TEXT", 1, None, 0), ("source_file_id", "TEXT", 1, None, 0),
        ("rotation", "INTEGER", 1, None, 0),
    ],
    "answers": [
        ("attempt_id", "TEXT", 1, None, 1), ("question_id", "TEXT", 1, None, 2),
        ("printed_number", "INTEGER", 0, None, 0), ("page_no", "INTEGER", 0, None, 0), ("value", "TEXT", 0, None, 0),
        ("value_norm", "TEXT", 0, None, 0), ("location", "TEXT", 1, None, 0),
        ("confidence", "REAL", 1, None, 0), ("low_trust", "INTEGER", 1, "0", 0), ("reading_unsure", "INTEGER", 1, "0", 0),
        ("alt_value", "TEXT", 0, None, 0), ("alt_question_id", "TEXT", 0, None, 0), ("verdict", "TEXT", 1, "'ungraded'", 0),
        ("near_miss", "INTEGER", 1, "0", 0), ("points_awarded", "REAL", 0, None, 0), ("teacher_override", "TEXT", 0, None, 0),
    ],
    "grade_reports": [
        ("attempt_id", "TEXT", 0, None, 1),
        ("run_id", "TEXT", 1, None, 0), ("weak_points", "JSON", 1, None, 0), ("careless_notes", "JSON", 1, None, 0),
        ("summary_vi", "TEXT", 1, None, 0), ("teacher_questions", "JSON", 1, None, 0), ("uncertain_points", "REAL", 1, None, 0),
        ("created_at", "TEXT", 1, None, 0),
    ],
    "explanations": [
        ("test_id", "TEXT", 1, None, 1), ("question_id", "TEXT", 1, None, 2),
        ("wrong_answer_norm", "TEXT", 1, None, 3), ("error_type", "TEXT", 1, None, 0), ("text_vi", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0), ("llm_call_id", "TEXT", 0, None, 0),
    ],
    "threads": [
        ("id", "TEXT", 0, None, 1), ("title", "TEXT", 0, None, 0), ("test_id", "TEXT", 0, None, 0),
        ("kind", "TEXT", 1, "'pending'", 0), ("created_at", "TEXT", 1, None, 0),
    ],
    "messages": [
        ("id", "TEXT", 0, None, 1), ("thread_id", "TEXT", 1, None, 0),
        ("role", "TEXT", 1, None, 0), ("kind", "TEXT", 1, None, 0), ("body", "JSON", 0, None, 0), ("created_at", "TEXT", 1, None, 0),
    ],
    "runs": [
        ("id", "TEXT", 0, None, 1), ("thread_id", "TEXT", 1, None, 0),
        ("kind", "TEXT", 1, None, 0), ("input", "JSON", 1, None, 0), ("status", "TEXT", 1, None, 0),
        ("started_at", "TEXT", 0, None, 0), ("finished_at", "TEXT", 0, None, 0), ("error", "TEXT", 0, None, 0),
    ],
    "steps": [
        ("id", "TEXT", 0, None, 1), ("run_id", "TEXT", 1, None, 0), ("node", "TEXT", 1, None, 0),
        ("item", "TEXT", 0, None, 0), ("try_no", "INTEGER", 1, None, 0), ("status", "TEXT", 1, None, 0),
        ("started_at", "TEXT", 1, None, 0), ("finished_at", "TEXT", 0, None, 0),
    ],
    "llm_calls": [
        ("id", "TEXT", 0, None, 1), ("step_id", "TEXT", 1, None, 0), ("role", "TEXT", 0, None, 0), ("model", "TEXT", 0, None, 0),
        ("prompt_hash", "TEXT", 0, None, 0), ("request", "JSON", 0, None, 0), ("response_text", "TEXT", 0, None, 0),
        ("thinking_text", "TEXT", 0, None, 0), ("logprobs", "JSON", 0, None, 0), ("status", "TEXT", 1, None, 0),
        ("tokens_in", "INTEGER", 0, None, 0), ("tokens_out", "INTEGER", 0, None, 0), ("ms", "INTEGER", 0, None, 0),
        ("created_at", "TEXT", 1, None, 0),
    ],
    "review_items": [
        ("id", "TEXT", 0, None, 1), ("kind", "TEXT", 1, None, 0), ("owner", "TEXT", 1, None, 0),
        ("test_id", "TEXT", 0, None, 0), ("attempt_id", "TEXT", 0, None, 0), ("question_id", "TEXT", 0, None, 0),
        ("dedupe_key", "TEXT", 1, None, 0), ("proposal", "JSON", 1, None, 0), ("resolution", "JSON", 0, None, 0),
        ("followup_run_id", "TEXT", 0, None, 0), ("status", "TEXT", 1, None, 0),
        ("created_at", "TEXT", 1, None, 0), ("resolved_at", "TEXT", 0, None, 0),
    ],
    "files": [
        ("id", "TEXT", 0, None, 1), ("path", "TEXT", 1, None, 0), ("kind", "TEXT", 1, None, 0),
        ("derived_from", "TEXT", 0, None, 0), ("mime", "TEXT", 0, None, 0), ("width", "INTEGER", 0, None, 0),
        ("height", "INTEGER", 0, None, 0), ("created_at", "TEXT", 1, None, 0),
        ("original_name", "TEXT", 0, None, 0),  # migration 0002 (data-model v1.5)
    ],
    "schema_migrations": [("version", "INTEGER", 0, None, 1), ("applied_at", "TEXT", 1, None, 0)],
}

# (from column, referenced table, referenced column)
EXPECTED_FKS: dict[str, set[tuple[str, str, str]]] = {
    "students": set(),
    "tests": {("parent_test_id", "tests", "id"), ("merged_into", "tests", "id")},
    "test_pages": {("test_id", "tests", "id"), ("file_id", "files", "id")},
    "test_key_pages": {("test_id", "tests", "id"), ("file_id", "files", "id")},
    "answer_keys": {("test_id", "tests", "id")},
    "question_tags": {("test_id", "tests", "id")},
    "attempts": {("test_id", "tests", "id"), ("thread_id", "threads", "id"),
                 ("student_id", "students", "id"), ("superseded_by", "attempts", "id")},
    "attempt_pages": {("attempt_id", "attempts", "id"), ("file_id", "files", "id"), ("source_file_id", "files", "id")},
    "answers": {("attempt_id", "attempts", "id")},
    "grade_reports": {("attempt_id", "attempts", "id"), ("run_id", "runs", "id")},
    "explanations": {("test_id", "tests", "id"), ("llm_call_id", "llm_calls", "id")},
    "threads": {("test_id", "tests", "id")},
    "regrade_pending": {("test_id", "tests", "id")},
    "messages": {("thread_id", "threads", "id")},
    "runs": {("thread_id", "threads", "id")},
    "steps": {("run_id", "runs", "id")},
    "llm_calls": {("step_id", "steps", "id")},
    "review_items": {("test_id", "tests", "id"), ("attempt_id", "attempts", "id"), ("followup_run_id", "runs", "id")},
    "files": {("derived_from", "files", "id")},
    "schema_migrations": set(),
}

# UNIQUE constraints other than primary keys
EXPECTED_UNIQUE: dict[str, set[tuple[str, ...]]] = {
    "tests": {("source_run_id",)},
    "attempts": {("source_run_id",)},
    "review_items": {("dedupe_key",)},
    "schools": {("name",)},  # 0008: unique ignoring case
    "series": {("name",)},  # 0011: unique ignoring case
}

# named indexes: (table, columns, partial)
EXPECTED_INDEXES: dict[str, tuple[str, tuple[str, ...], bool]] = {
    "students_name": ("students", ("name_search",), False),
    "tests_grade": ("tests", ("grade",), True),
    "question_tags_tag": ("question_tags", ("tag",), False),
    "attempts_test": ("attempts", ("test_id",), False),
    "attempts_student": ("attempts", ("student_id",), False),
    "attempts_thread": ("attempts", ("thread_id",), False),
    "messages_thread": ("messages", ("thread_id", "created_at"), False),
    "runs_status": ("runs", ("status",), False),
    "steps_run": ("steps", ("run_id", "started_at"), False),
    "llm_calls_step": ("llm_calls", ("step_id",), False),
    "review_open": ("review_items", ("status", "created_at"), False),
    "review_attempt": ("review_items", ("attempt_id",), False),
}

FTS_TABLE = "tests_fts"
FTS_COLUMNS = ["test_id", "display_name", "meta_text"]
FTS_SHADOW = {f"{FTS_TABLE}_{s}" for s in ("data", "idx", "content", "docsize", "config")}
VIEW_COLUMNS = ["student_id", "skill_tag", "seen", "wrong", "gap_errors", "last_seen"]
# fmt: on


def _master(conn: sqlite3.Connection, kind: str) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = ?", (kind,))
    return {r[0] for r in rows}


def test_r2_1_tables_are_exactly_the_documented_ones(conn: sqlite3.Connection) -> None:
    assert _master(conn, "table") == set(EXPECTED_COLUMNS) | {FTS_TABLE} | FTS_SHADOW
    assert _master(conn, "view") == {"student_skill_stats"}
    assert _master(conn, "trigger") == set()


@pytest.mark.parametrize("table", sorted(EXPECTED_COLUMNS))
def test_r2_1_columns_and_primary_keys(conn: sqlite3.Connection, table: str) -> None:
    info = conn.execute(f"PRAGMA table_info({table})").fetchall()
    actual = [(r["name"], r["type"], r["notnull"], r["dflt_value"], r["pk"]) for r in info]
    assert actual == EXPECTED_COLUMNS[table]


@pytest.mark.parametrize("table", sorted(EXPECTED_FKS))
def test_r2_1_foreign_keys(conn: sqlite3.Connection, table: str) -> None:
    rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    assert {(r["from"], r["table"], r["to"]) for r in rows} == EXPECTED_FKS[table]


@pytest.mark.parametrize("table", sorted(EXPECTED_COLUMNS))
def test_r2_1_unique_constraints(conn: sqlite3.Connection, table: str) -> None:
    uniques: set[tuple[str, ...]] = set()
    for idx in conn.execute(f"PRAGMA index_list({table})").fetchall():
        if idx["origin"] == "u":
            cols = conn.execute(f"PRAGMA index_info({idx['name']})").fetchall()
            uniques.add(tuple(c["name"] for c in cols))
    assert uniques == EXPECTED_UNIQUE.get(table, set())


def test_r2_1_indexes(conn: sqlite3.Connection) -> None:
    named = {n for n in _master(conn, "index") if not n.startswith("sqlite_autoindex_")}
    assert named == set(EXPECTED_INDEXES)
    for name, (table, cols, partial) in EXPECTED_INDEXES.items():
        info = conn.execute(f"PRAGMA index_info({name})").fetchall()
        assert tuple(r["name"] for r in info) == cols, name
        listed = {r["name"]: r for r in conn.execute(f"PRAGMA index_list({table})")}
        assert bool(listed[name]["partial"]) is partial, name


def test_r2_1_fts_table_and_view(conn: sqlite3.Connection) -> None:
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = ?", (FTS_TABLE,)).fetchone()[0]
    assert "fts5" in sql and "remove_diacritics 2" in sql and "test_id UNINDEXED" in sql
    assert [r["name"] for r in conn.execute(f"PRAGMA table_info({FTS_TABLE})")] == FTS_COLUMNS
    view = conn.execute("SELECT * FROM student_skill_stats")
    assert [d[0] for d in view.description] == VIEW_COLUMNS


# --- R2.2 ------------------------------------------------------------------------------------


def test_r2_2_migrations_twice_is_a_no_op(conn: sqlite3.Connection, tmp_path: Any) -> None:
    assert db.apply_migrations(conn) == []
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    assert [r[0] for r in rows] == list(range(1, 16))
    again = db.open_database(tmp_path / "data" / "app.db")  # a second startup
    assert again.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 15
    again.close()


def test_migration_files_ship_with_the_package() -> None:
    found = db.list_migrations()
    assert found[0][:2] == (1, "0001_init.sql")
    assert "CREATE TABLE schema_migrations" in found[0][2]


def test_failed_migration_rolls_back(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    good = db.list_migrations()
    bad_version = good[-1][0] + 1
    bad_name = f"{bad_version:04d}_bad.sql"
    bad_sql = "CREATE TABLE extra_x (a); SELECT * FROM no_such_table;"
    bad = [*good, (bad_version, bad_name, bad_sql)]
    monkeypatch.setattr(db, "list_migrations", lambda: bad)
    c = db.connect(tmp_path / "app.db")
    with pytest.raises(db.MigrationError, match=bad_name.removesuffix(".sql")):
        db.apply_migrations(c)
    applied = [r[0] for r in c.execute("SELECT version FROM schema_migrations")]
    assert applied == [v for v, _, _ in good]
    assert "extra_x" not in _master(c, "table")
    c.close()


def test_missing_fts5_stops_startup(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_fts(c: sqlite3.Connection) -> None:
        raise db.Fts5UnavailableError("no fts5")

    monkeypatch.setattr(db, "check_fts5", no_fts)
    with pytest.raises(db.Fts5UnavailableError):
        db.open_database(tmp_path / "app.db")


# --- R2.3 ------------------------------------------------------------------------------------


def test_r2_3_pragmas_on_every_connection(conn: sqlite3.Connection, tmp_path: Any) -> None:
    other = db.connect(tmp_path / "data" / "app.db")
    for c in (conn, other):
        assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    other.close()


def test_r2_3_answer_for_missing_attempt_is_rejected(conn: sqlite3.Connection, f: Any) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        attempts.insert_answers(conn, [f.answer("A-9999", "q-1")])


# --- transactions ----------------------------------------------------------------------------


def test_transaction_commits_and_rolls_back(conn: sqlite3.Connection) -> None:
    with db.transaction(conn):
        conn.execute("INSERT INTO threads (id, title, created_at) VALUES ('t1', 'x', 'now')")
    with pytest.raises(RuntimeError), db.transaction(conn):
        conn.execute("INSERT INTO threads (id, title, created_at) VALUES ('t2', 'x', 'now')")
        raise RuntimeError
    ids = [r[0] for r in conn.execute("SELECT id FROM threads")]
    assert ids == ["t1"]
    assert not conn.in_transaction


def test_nested_transaction_is_a_savepoint(conn: sqlite3.Connection) -> None:
    with db.transaction(conn):
        conn.execute("INSERT INTO threads (id, title, created_at) VALUES ('outer', 'x', 'now')")
        with pytest.raises(RuntimeError), db.transaction(conn):
            conn.execute("INSERT INTO threads (id, title, created_at) VALUES ('inner', 'x', 'now')")
            raise RuntimeError
    assert [r[0] for r in conn.execute("SELECT id FROM threads")] == ["outer"]


# --- R2.4 / R2.5: write_test_meta ------------------------------------------------------------


def _snapshot(conn: sqlite3.Connection, test_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT meta, display_name, occasion, grade, year, school, term, test_number,"
        " created_by_ai, parent_test_id FROM tests WHERE id = ?",
        (test_id,),
    ).fetchone()
    fts = conn.execute(
        "SELECT display_name, meta_text FROM tests_fts WHERE test_id = ?", (test_id,)
    ).fetchall()
    return {"row": tuple(row), "fts": [tuple(r) for r in fts]}


def test_r2_4_updates_all_four_parts(conn: sqlite3.Connection, f: Any) -> None:
    t = f.make_test(conn, meta=m.TestMetadata(occasion="MidTerm", grade=7))
    assert db.search_tests(conn, "final") == []
    meta = db.write_test_meta(
        conn,
        t.id,
        {"occasion": "FinalTerm", "grade": 8, "term": 1, "school": "THCS Lê Lợi"},
        by_teacher=False,
    )
    row = conn.execute("SELECT * FROM tests WHERE id = ?", (t.id,)).fetchone()
    assert m.TestMetadata.model_validate_json(row["meta"]) == meta
    assert (row["occasion"], row["grade"], row["term"], row["school"]) == (
        "FinalTerm",
        8,
        1,
        "THCS Lê Lợi",
    )
    assert row["display_name"] == "Grade 8 - Final Term 1 - THCS Lê Lợi" == meta.display_name()
    fts = conn.execute("SELECT display_name FROM tests_fts WHERE test_id = ?", (t.id,)).fetchall()
    assert [r[0] for r in fts] == [row["display_name"]]
    assert db.search_tests(conn, "final") == [t.id]  # prefix: "final" finds "FinalTerm"
    assert db.search_tests(conn, "grade 8 final") == [t.id]
    assert db.search_tests(conn, "le loi") == [t.id]  # accents removed
    assert db.search_tests(conn, "midterm") == []


def test_r2_4_exception_before_commit_changes_nothing(
    conn: sqlite3.Connection, f: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    t = f.make_test(conn, meta=m.TestMetadata(occasion="MidTerm", grade=7))
    before = _snapshot(conn, t.id)
    real = db._write_fts_row

    def write_then_fail(c: sqlite3.Connection, test_id: str, meta: m.TestMetadata) -> None:
        real(c, test_id, meta)  # meta, columns, display_name and the FTS row are all written…
        assert _snapshot(c, test_id) != before
        raise RuntimeError("injected before commit")  # …and then the commit never happens

    monkeypatch.setattr(db, "_write_fts_row", write_then_fail)
    with pytest.raises(RuntimeError, match="injected"):
        db.write_test_meta(conn, t.id, {"occasion": "FinalTerm", "grade": 8}, by_teacher=True)
    assert not conn.in_transaction
    assert _snapshot(conn, t.id) == before
    monkeypatch.undo()
    assert db.search_tests(conn, "final") == []
    assert db.search_tests(conn, "mid-term") == [t.id]


def test_r2_5_teacher_write_records_and_protects_fields(conn: sqlite3.Connection, f: Any) -> None:
    t = f.make_test(conn, meta=m.TestMetadata(occasion="Other:unknown", grade=7))
    meta = db.write_test_meta(conn, t.id, {"occasion": "GiftedExam"}, by_teacher=True)
    assert meta.edited_fields == ["occasion"]
    meta = db.write_test_meta(conn, t.id, {"occasion": "MidTerm", "grade": 9}, by_teacher=False)
    assert meta.occasion == "GiftedExam"  # protected
    assert meta.grade == 9  # not edited by the teacher, so extraction may change it
    assert meta.edited_fields == ["occasion"]
    meta = db.write_test_meta(conn, t.id, {"grade": 6, "occasion": "Placement"}, by_teacher=True)
    assert meta.edited_fields == ["occasion", "grade"]
    assert (meta.occasion, meta.grade) == ("Placement", 6)
    stored = tests.get_test(conn, t.id)
    assert stored is not None and stored.meta == meta


def test_write_test_meta_rejects_bad_input(conn: sqlite3.Connection, f: Any) -> None:
    t = f.make_test(conn)
    with pytest.raises(ValueError, match="unknown"):
        db.write_test_meta(conn, t.id, {"colour": "red"}, by_teacher=True)
    with pytest.raises(ValueError, match="edited_fields"):
        db.write_test_meta(conn, t.id, {"edited_fields": []}, by_teacher=True)
    with pytest.raises(KeyError):
        db.write_test_meta(conn, "T-9999", {"grade": 1}, by_teacher=True)


def test_merged_test_leaves_search(conn: sqlite3.Connection, f: Any) -> None:
    survivor = f.make_test(conn)
    merged = f.make_test(conn)
    conn.execute("UPDATE tests SET merged_into = ? WHERE id = ?", (survivor.id, merged.id))
    db.write_test_meta(conn, merged.id, {"grade": 8}, by_teacher=False)
    assert db.search_tests(conn, "final") == [survivor.id]


# --- search helper ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("grade 8 final", '"grade"* "8"* "final"*'),
        ("  Final  ", '"Final"*'),
        ('a"b', '"a""b"*'),
        ("final OR NOT x", '"final"* "OR"* "NOT"* "x"*'),
        ("· - *", ""),
        ("", ""),
    ],
)
def test_fts_prefix_query(text: str, query: str) -> None:
    assert db.fts_prefix_query(text) == query


@pytest.mark.parametrize("text", ['"', "final*", "grade AND", "(", "NEAR(a b)", "test_id:1", "^x"])
def test_search_escapes_operators(conn: sqlite3.Connection, f: Any, text: str) -> None:
    f.make_test(conn)
    assert isinstance(db.search_tests(conn, text), list)  # never a syntax error


def test_search_needs_every_token(conn: sqlite3.Connection, f: Any) -> None:
    t8 = f.make_test(conn)
    f.make_test(conn, meta=m.TestMetadata(occasion="FinalTerm", grade=9, textbook="Global Success"))
    assert db.search_tests(conn, "grade 8 fin") == [t8.id]
    assert len(db.search_tests(conn, "fin")) == 2
    assert len(db.search_tests(conn, "global")) == 1  # meta_text is searched too


# --- ids and timestamps ----------------------------------------------------------------------


def test_ulid_shape() -> None:
    ids = {db.new_ulid() for _ in range(200)}
    assert len(ids) == 200
    assert all(len(i) == 26 and i.isalnum() and i.isupper() for i in ids)


def test_iso_is_fixed_width_utc() -> None:
    from datetime import datetime, timedelta, timezone

    local = datetime(2026, 1, 1, 15, 0, tzinfo=timezone(timedelta(hours=7)))
    assert db.iso(local) == "2026-01-01T08:00:00.000000Z"
    with pytest.raises(ValueError):
        db.iso(datetime(2026, 1, 1))


# --- R2.9: the weak-point view ---------------------------------------------------------------
# Seed table, written by hand. Test T with tags: q-1 grammar · q-2 grammar+vocabulary ·
# q-3 vocabulary · q-4 reading. Explanations: (q-1,"a") gap · (q-2,"b") careless · (q-3,"c") gap.
#
# attempt | student | superseded | created    | q-1                | q-2                 | q-3                | q-4
# A1      | S1      | no         | 2026-01-10 | incorrect "a"      | correct "ok"        | uncertain "c"      | incorrect "x"
# A2      | S1      | by A3      | 2026-01-20 | incorrect "a"      | incorrect "b"       | incorrect "c"      | incorrect "x"
# A3      | S1      | no         | 2026-02-01 | correct "ok"       | incorrect "b"       | incorrect "c"      | ungraded None
# A4      | NULL    | no         | 2026-02-05 | incorrect "a"      | incorrect "b"       | incorrect "c"      | incorrect "x"
# A5      | S2      | no         | 2026-03-01 | correct "ok"       | ungraded None       | -                  | -
SEED: list[tuple[str, str | None, str | None, str, dict[str, tuple[str, str | None]]]] = [
    (
        "A1",
        "S1",
        None,
        "2026-01-10",
        {
            "q-1": ("incorrect", "a"),
            "q-2": ("correct", "ok"),
            "q-3": ("uncertain", "c"),
            "q-4": ("incorrect", "x"),
        },
    ),
    (
        "A2",
        "S1",
        "A3",
        "2026-01-20",
        {
            "q-1": ("incorrect", "a"),
            "q-2": ("incorrect", "b"),
            "q-3": ("incorrect", "c"),
            "q-4": ("incorrect", "x"),
        },
    ),
    (
        "A3",
        "S1",
        None,
        "2026-02-01",
        {
            "q-1": ("correct", "ok"),
            "q-2": ("incorrect", "b"),
            "q-3": ("incorrect", "c"),
            "q-4": ("ungraded", None),
        },
    ),
    (
        "A4",
        None,
        None,
        "2026-02-05",
        {
            "q-1": ("incorrect", "a"),
            "q-2": ("incorrect", "b"),
            "q-3": ("incorrect", "c"),
            "q-4": ("incorrect", "x"),
        },
    ),
    ("A5", "S2", None, "2026-03-01", {"q-1": ("correct", "ok"), "q-2": ("ungraded", None)}),
]
# Expected, worked out by hand from the table above:
# (student, skill, seen, wrong, gap_errors, last_seen date).
# S1 reading: A1 q-4 is incorrect with no explanation (1 AND NULL = NULL, skipped by SUM) and
# A3 q-4 is ungraded (0), so gap_errors = 0.
EXPECTED_STATS = {
    ("S1", "grammar", 4, 2, 1, "2026-02-01"),
    ("S1", "vocabulary", 3, 2, 1, "2026-02-01"),
    ("S1", "reading", 1, 1, 0, "2026-02-01"),
    ("S2", "grammar", 1, 0, 0, "2026-03-01"),
    ("S2", "vocabulary", 0, 0, 0, "2026-03-01"),
}


def test_r2_9_student_skill_stats(conn: sqlite3.Connection, f: Any) -> None:
    from datetime import UTC, datetime

    from etach.store.repos import students

    t = f.make_test(conn, content=f.content(4))
    s1 = students.create_student(conn, "Học Sinh A", "hoc sinh a")
    s2 = students.create_student(conn, "Học Sinh B", "hoc sinh b")
    sid = {"S1": s1.id, "S2": s2.id, None: None}
    for qid, tags in {
        "q-1": ["grammar"],
        "q-2": ["grammar", "vocabulary"],
        "q-3": ["vocabulary"],
        "q-4": ["reading"],
    }.items():
        tests.set_question_tags(conn, t.id, qid, tags)
    call = f.make_llm_call(conn)
    for qid, wrong, kind in (("q-1", "a", "gap"), ("q-2", "b", "careless"), ("q-3", "c", "gap")):
        explanations.upsert_explanation(conn, f.explanation(t.id, qid, wrong, call.id, kind))
    ids: dict[str, str] = {}
    for name, student, _sup, day, answers in SEED:
        created = datetime.fromisoformat(day).replace(tzinfo=UTC)
        a = f.make_attempt(conn, t.id, sid[student], created_at=created)
        ids[name] = a.id
        attempts.insert_answers(
            conn,
            [f.answer(a.id, q, verdict=v, value=n, value_norm=n) for q, (v, n) in answers.items()],
        )
    for name, _student, sup, *_ in SEED:
        if sup:
            attempts.set_superseded_by(conn, ids[name], ids[sup])
    rows = conn.execute("SELECT * FROM student_skill_stats").fetchall()
    back = {v: k for k, v in sid.items()}
    actual = {
        (
            back[r["student_id"]],
            r["skill_tag"],
            r["seen"],
            r["wrong"],
            r["gap_errors"],
            r["last_seen"][:10],
        )
        for r in rows
    }
    assert actual == EXPECTED_STATS
