"""Step 22.5.5a: the store (R22.5.5.2 the date taken; migration 0014)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from unit.store.conftest import make_attempt, make_run, make_test

from etach.domain import models as m
from etach.graphs.extract import _taken_on
from etach.store import db
from etach.store.repos import attempts, students
from etach.store.repos._common import to_row


def test_r22_5_5_2_migration_gives_stored_attempts_their_created_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    every = db.list_migrations()
    cut = [m[0] for m in every].index(14)  # the migrations before 0014
    assert every[cut][:2] == (14, "0014_checker_taken_on_levels.sql")
    monkeypatch.setattr(db, "list_migrations", lambda: every[:cut])
    path = tmp_path / "app.db"
    c = db.open_database(path)
    test = make_test(c)
    created = datetime(2026, 3, 4, 2, 30, tzinfo=UTC)
    run = make_run(c)
    row = to_row(
        m.Attempt(
            id="A-0001", test_id=test.id, thread_id=run.thread_id, student_id=None,
            student_name_read=None, class_read=None, source_run_id=run.id, superseded_by=None,
            status="extracted", version=1, score_earned=None, score_possible=None,
            created_at=created,
        )
    )  # fmt: skip
    del row["taken_on"]  # the table before 0014
    c.execute(
        f"INSERT INTO attempts ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
        tuple(row.values()),
    )
    c.commit()
    c.close()
    monkeypatch.setattr(db, "list_migrations", lambda: every)
    c = db.open_database(path)
    try:
        (raw,) = c.execute("SELECT taken_on FROM attempts WHERE id = ?", ("A-0001",)).fetchone()
        assert raw == created.astimezone().date().isoformat()
        got = attempts.get_attempt(c, "A-0001")
        assert got is not None and got.taken_on == created.astimezone().date()
    finally:
        c.close()


def test_r22_5_5_2_new_attempts_default_to_today(conn: sqlite3.Connection) -> None:
    test = make_test(conn)
    a = make_attempt(conn, test.id)
    got = attempts.get_attempt(conn, a.id)
    assert got is not None and got.taken_on == m.local_today()


def test_r22_5_5_2_set_taken_on_and_trajectory_order(conn: sqlite3.Connection) -> None:
    test = make_test(conn)
    sid = students.create_student(conn, "Học Sinh A", "hoc sinh a").id
    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = datetime(2026, 1, 2, tzinfo=UTC)
    late = make_attempt(conn, test.id, sid, created_at=t1, taken_on=date(2026, 5, 1))
    early_b = make_attempt(conn, test.id, sid, created_at=t2, taken_on=date(2026, 2, 1))
    early_a = make_attempt(conn, test.id, sid, created_at=t1, taken_on=date(2026, 2, 1))
    old = make_attempt(conn, test.id, sid, taken_on=date(2026, 1, 1))
    make_attempt(conn, test.id, None, taken_on=date(2025, 1, 1))  # another student's paper
    attempts.set_superseded_by(conn, old.id, late.id)  # superseded: left out
    order = [a.id for a in attempts.student_attempts_by_date(conn, sid)]
    assert order == [early_a.id, early_b.id, late.id]  # same date: created_at decides

    attempts.set_taken_on(conn, late.id, date(2026, 1, 15))
    order = [a.id for a in attempts.student_attempts_by_date(conn, sid)]
    assert order == [late.id, early_a.id, early_b.id]
    got = attempts.get_attempt(conn, late.id)
    assert got is not None and got.taken_on == date(2026, 1, 15)


def test_r22_5_5_2_extract_input_sets_the_date(conn: sqlite3.Connection) -> None:
    test = make_test(conn)
    old = make_attempt(conn, test.id, taken_on=date(2026, 4, 2))

    def inp(**kw: object) -> m.ExtractInput:
        return m.ExtractInput(pages=[], existing_test_id=None, supersedes_attempt_id=None, **kw)

    assert _taken_on(conn, inp(taken_on=date(2026, 9, 9))) == date(2026, 9, 9)
    assert _taken_on(conn, inp()) == m.local_today()
    # Extract again keeps the replaced attempt's date unless one is sent
    again = m.ExtractInput(pages=[], existing_test_id=None, supersedes_attempt_id=old.id)
    assert _taken_on(conn, again) == date(2026, 4, 2)
    sent = again.model_copy(update={"taken_on": date(2026, 4, 3)})
    assert _taken_on(conn, sent) == date(2026, 4, 3)
    assert m.ExtractInput.model_validate(
        {
            "pages": [],
            "existing_test_id": None,
            "supersedes_attempt_id": None,
            "taken_on": "2026-10-20",
        }
    ).taken_on == date(2026, 10, 20)


def test_r22_5_5_2_a_row_without_a_date_reads_as_its_created_date(
    conn: sqlite3.Connection,
) -> None:
    test = make_test(conn)
    created = datetime(2026, 6, 30, 20, 0, tzinfo=UTC)
    a = make_attempt(conn, test.id, created_at=created)
    conn.execute("UPDATE attempts SET taken_on = NULL WHERE id = ?", (a.id,))
    got = attempts.get_attempt(conn, a.id)
    assert got is not None and got.taken_on == created.astimezone().date()


def test_r22_5_5_3_question_levels_round_trip(conn: sqlite3.Connection) -> None:
    from etach.store.repos import tests

    test = make_test(conn)
    tests.set_question_tags(conn, test.id, "q-1", ["GR-PSV-A1", "VOC-TOPIC"], "B1")
    tests.set_question_tags(conn, test.id, "q-2", ["READ-INFER"])
    assert tests.list_question_levels(conn, test.id) == {"q-1": "B1", "q-2": None}
    assert tests.list_tag_levels(conn, test.id) == {
        "q-1": {"GR-PSV-A1": "B1", "VOC-TOPIC": "B1"},
        "q-2": {"READ-INFER": "B2"},
    }
    assert tests.list_question_tags(conn, test.id) == {
        "q-1": ["GR-PSV-A1", "VOC-TOPIC"],
        "q-2": ["READ-INFER"],
    }
