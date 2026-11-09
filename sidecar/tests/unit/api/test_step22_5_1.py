"""Step 22.5.1 (llm-design v4.40): ``GET /tests`` finds a test by its id, and its items carry
``created_at`` (R22.5.1.4)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from unit.api.test_routes_b import _content
from unit.api.test_step22_2_3 import client

from etach.api.deps import AppContext
from etach.domain import models as m
from etach.store import db
from etach.store.repos import tests

T0 = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)


@pytest.fixture
def ctx(make_ctx: Callable[..., AppContext]) -> Iterator[AppContext]:
    c = make_ctx()
    yield c
    c.close()


@pytest.fixture
def conn(ctx: AppContext) -> Iterator[sqlite3.Connection]:
    c = db.connect(ctx.paths.db)
    yield c
    c.close()


def _add(conn: sqlite3.Connection, meta: m.TestMetadata, day: int) -> str:
    return tests.insert_test(
        conn,
        m.Test(
            id=tests.next_test_id(conn),
            meta=meta,
            content=_content(),
            content_schema_version=1,
            fingerprint=f"fp-{day}",
            points_possible=0.5,
            source_run_id=None,
            merged_into=None,
            created_at=T0 + timedelta(days=day),
            updated_at=T0 + timedelta(days=30 - day),
        ),
    ).id


def _seed(conn: sqlite3.Connection) -> list[str]:
    """T-0001 … T-0008. T-0002's school reads "T 0008", so the name search for "T-0008" finds
    it too; T-0008 is a grade 8 test with nothing like its id in its name."""
    ids = []
    for day in range(1, 9):
        school = "T 0008 School" if day == 2 else f"School {day}"
        ids.append(_add(conn, m.TestMetadata(occasion="FinalTerm", grade=day, school=school), day))
    return ids


def test_search_by_id_any_case_with_or_without_dash(conn: sqlite3.Connection) -> None:
    ids = _seed(conn)
    assert ids[-1] == "T-0008"
    for q in ("T-0008", "t-0008", "T0008", "t0008", " T-0008 "):
        found = db.search_tests(conn, q)
        assert found[0] == "T-0008", q
        assert found.count("T-0008") == 1, q
    assert db.search_tests(conn, "T-0008") == ["T-0008", "T-0002"]
    assert db.search_tests(conn, "T-9999") == []
    # A name query returns what it did before.
    assert db.search_tests(conn, "school 5") == ["T-0005"]
    assert db.search_tests(conn, "grade 8") == ["T-0008"]


def test_search_by_id_leaves_out_merged_tests(conn: sqlite3.Connection) -> None:
    _seed(conn)
    conn.execute("UPDATE tests SET merged_into = 'T-0001' WHERE id = 'T-0008'")
    conn.commit()
    assert db.search_tests(conn, "T-0008") == ["T-0002"]


@pytest.mark.asyncio
async def test_r22_5_1_4_route(ctx: AppContext, conn: sqlite3.Connection) -> None:
    _seed(conn)
    async with client(ctx) as c:
        for q in ("T-0008", "t-0008", "T0008"):
            r = await c.get("/tests", params={"q": q})
            assert r.status_code == 200, r.text
            assert r.json()[0]["id"] == "T-0008", q
        named = (await c.get("/tests", params={"q": "school 5"})).json()
        assert [t["id"] for t in named] == ["T-0005"]
        listed = (await c.get("/tests")).json()
        assert len(listed) == 8
        created = {t["id"]: t["created_at"] for t in listed}
        assert datetime.fromisoformat(created["T-0003"]) == T0 + timedelta(days=3)
        assert all("updated_at" in t for t in listed)
