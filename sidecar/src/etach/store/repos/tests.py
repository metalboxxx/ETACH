"""``tests``, ``test_pages``, ``test_key_pages`` and ``question_tags`` (data-model §2.2-2.3).
IDs are ``T-0001``, …

Metadata changes go through ``etach.store.db.write_test_meta``; reading a test applies the
content upgraders (``etach.store.upgrades``) and writes the upgraded content back.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable

from etach.domain.levels import tag_level
from etach.domain.models import Test, TestContent, TestMetadata
from etach.store import upgrades
from etach.store.db import iso, now_iso, sync_test_meta, transaction
from etach.store.repos._common import insert_model, next_readable_id

__all__ = [
    "TestPageRow",
    "add_key_page",
    "add_test_page",
    "attempt_counts",
    "find_by_source_run",
    "get_test",
    "insert_test",
    "list_key_pages",
    "list_question_levels",
    "list_question_tags",
    "list_tag_levels",
    "list_test_pages",
    "list_unmerged_ids",
    "next_test_id",
    "set_fingerprint",
    "set_question_tags",
    "update_content",
    "with_contexts",
]

_JSON = ("meta", "content")

TestPageRow = tuple[str, int, str]
"""``(test_id, page_no, file_id)``: a ``test_pages`` row (no pydantic class in data-model §2)."""


def next_test_id(conn: sqlite3.Connection) -> str:
    return next_readable_id(conn, "tests", "T")


def with_contexts(content: TestContent) -> TestContent:
    """The content validated again, so each question's ``context`` follows its group's stimulus
    (data-model v1.22) even after an edit made with ``model_copy``."""
    return TestContent.model_validate(content.model_dump())


def insert_test(conn: sqlite3.Connection, test: Test) -> Test:
    """Insert a test. The columns, ``display_name`` and the FTS row are derived from
    ``test.meta`` exactly as ``write_test_meta`` derives them."""
    content = with_contexts(test.content)
    if content != test.content:
        test = test.model_copy(update={"content": content})
    with transaction(conn):
        insert_model(
            conn,
            "tests",
            test,
            _JSON,
            extra={"display_name": test.meta.display_name(), "occasion": test.meta.occasion},
        )
        sync_test_meta(conn, test.id, test.meta)
        conn.execute(
            "UPDATE tests SET updated_at = ? WHERE id = ?", (iso(test.updated_at), test.id)
        )
    return test


def _build(row: sqlite3.Row, content: dict[str, object], version: int) -> Test:
    return Test(
        id=row["id"],
        meta=TestMetadata.model_validate_json(row["meta"]),
        content=TestContent.model_validate(content),
        content_schema_version=version,
        fingerprint=row["fingerprint"],
        points_possible=row["points_possible"],
        source_run_id=row["source_run_id"],
        merged_into=row["merged_into"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_test(conn: sqlite3.Connection, test_id: str) -> Test | None:
    """The test, with its content upgraded to the newest registered version (written back)."""
    with transaction(conn):
        row = conn.execute("SELECT * FROM tests WHERE id = ?", (test_id,)).fetchone()
        if row is None:
            return None
        stored_version: int = row["content_schema_version"]
        content, version = upgrades.upgrade_content(json.loads(row["content"]), stored_version)
        test = _build(row, content, version)
        if version != stored_version:
            conn.execute(
                "UPDATE tests SET content = ?, content_schema_version = ?, updated_at = ?"
                " WHERE id = ?",
                (test.content.model_dump_json(), version, now_iso(), test_id),
            )
            row = conn.execute("SELECT * FROM tests WHERE id = ?", (test_id,)).fetchone()
            test = _build(row, json.loads(row["content"]), version)
    return test


def find_by_source_run(conn: sqlite3.Connection, run_id: str) -> Test | None:
    """The test an extract run created (idempotent save, data-model §5.2)."""
    row = conn.execute("SELECT id FROM tests WHERE source_run_id = ?", (run_id,)).fetchone()
    return None if row is None else get_test(conn, row[0])


def update_content(
    conn: sqlite3.Connection, test_id: str, content: TestContent, points_possible: float
) -> None:
    """Replace the content (already validated by the caller) and ``points_possible``."""
    with transaction(conn):
        cur = conn.execute(
            "UPDATE tests SET content = ?, points_possible = ?, updated_at = ? WHERE id = ?",
            (with_contexts(content).model_dump_json(), points_possible, now_iso(), test_id),
        )
        if cur.rowcount != 1:
            raise KeyError(f"no test {test_id}")


def set_fingerprint(conn: sqlite3.Connection, test_id: str, fingerprint: str) -> None:
    """Replace the fingerprint (the printed text changed in the test text, data-model §2.3a)."""
    with transaction(conn):
        conn.execute("UPDATE tests SET fingerprint = ? WHERE id = ?", (fingerprint, test_id))


# --- test_pages ------------------------------------------------------------------------------


def add_test_page(conn: sqlite3.Connection, test_id: str, page_no: int, file_id: str) -> None:
    with transaction(conn):
        conn.execute(
            "INSERT INTO test_pages (test_id, page_no, file_id) VALUES (?, ?, ?)",
            (test_id, page_no, file_id),
        )


def list_test_pages(conn: sqlite3.Connection, test_id: str) -> list[TestPageRow]:
    rows = conn.execute(
        "SELECT test_id, page_no, file_id FROM test_pages WHERE test_id = ? ORDER BY page_no",
        (test_id,),
    ).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


# --- test_key_pages (data-model v1.12) ----------------------------------------------------------


def add_key_page(conn: sqlite3.Connection, test_id: str, page_no: int, file_id: str) -> None:
    """Keep a key photo the test was extracted with (written by the extract run's save)."""
    with transaction(conn):
        conn.execute(
            "INSERT OR REPLACE INTO test_key_pages (test_id, page_no, file_id) VALUES (?, ?, ?)",
            (test_id, page_no, file_id),
        )


def list_key_pages(conn: sqlite3.Connection, test_id: str) -> list[TestPageRow]:
    rows = conn.execute(
        "SELECT test_id, page_no, file_id FROM test_key_pages WHERE test_id = ? ORDER BY page_no",
        (test_id,),
    ).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


# --- question_tags (the only place skill tags live, data-model §5.6) --------------------------


def set_question_tags(
    conn: sqlite3.Connection,
    test_id: str,
    question_id: str,
    tags: Iterable[str],
    level: str | None = None,
) -> None:
    """Replace the skill tags of one question. ``level`` is the question's level from
    ``tag_skills`` (step 22.5.5), kept on each of its tag rows; None = not given."""
    with transaction(conn):
        conn.execute(
            "DELETE FROM question_tags WHERE test_id = ? AND question_id = ?",
            (test_id, question_id),
        )
        conn.executemany(
            "INSERT INTO question_tags (test_id, question_id, tag, level) VALUES (?, ?, ?, ?)",
            [(test_id, question_id, t, level) for t in dict.fromkeys(tags)],
        )


def list_question_levels(conn: sqlite3.Connection, test_id: str) -> dict[str, str | None]:
    """``{question_id: the question's level from tag_skills, or None}`` for the tagged
    questions of one test."""
    out: dict[str, str | None] = {}
    for qid, level in conn.execute(
        "SELECT question_id, MAX(level) FROM question_tags WHERE test_id = ? GROUP BY question_id",
        (test_id,),
    ):
        out[qid] = level
    return out


def list_tag_levels(conn: sqlite3.Connection, test_id: str) -> dict[str, dict[str, str | None]]:
    """``{question_id: {tag: effective level}}``: the question's level when given, else the
    skill's base level (D11d; ``etach.domain.levels.tag_level``)."""
    out: dict[str, dict[str, str | None]] = {}
    for qid, tag, level in conn.execute(
        "SELECT question_id, tag, level FROM question_tags WHERE test_id = ?"
        " ORDER BY question_id, tag",
        (test_id,),
    ):
        out.setdefault(qid, {})[tag] = tag_level(tag, level)
    return out


def list_question_tags(conn: sqlite3.Connection, test_id: str) -> dict[str, list[str]]:
    """``{question_id: [tag, …]}`` for one test."""
    out: dict[str, list[str]] = {}
    for qid, tag in conn.execute(
        "SELECT question_id, tag FROM question_tags WHERE test_id = ? ORDER BY question_id, tag",
        (test_id,),
    ):
        out.setdefault(qid, []).append(tag)
    return out


def attempt_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """``{test_id: number of current (not superseded) attempts}``; tests without one are absent."""
    rows = conn.execute(
        "SELECT test_id, COUNT(*) FROM attempts WHERE superseded_by IS NULL GROUP BY test_id"
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def list_unmerged_ids(conn: sqlite3.Connection) -> list[str]:
    """IDs of every test that is not merged, newest change first (``GET /tests`` without ``q``)."""
    rows = conn.execute(
        "SELECT id FROM tests WHERE merged_into IS NULL ORDER BY updated_at DESC, id DESC"
    ).fetchall()
    return [r[0] for r in rows]
