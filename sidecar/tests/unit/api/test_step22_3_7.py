"""Step 22.3.7 (data-model v1.17, llm-design v4.33, PRD v7.2): the editable occasion list
(R22.3.7.1). The seed is 22.2.3's synthetic one: T-1, T-2, T-3 (merged into T-1), T-4, all
"FinalTerm"."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest
from unit.api.test_step22_2_3 import client, seed
from unit.api.test_step22_2_3 import conn as conn
from unit.api.test_step22_2_3 import ctx as ctx

from etach.api.deps import AppContext
from etach.domain import models as m
from etach.store import db

BUILTINS = [
    ("MidTerm", "Mid-term test", "Mid-term"),
    ("FinalTerm", "Final-term test", "Final Term"),
    ("NationalExam", "National exam", "National Exam"),
    ("EntranceExam", "Entrance exam", "Entrance Exam"),
    ("GiftedExam", "Gifted students' exam", "Gifted Exam"),
    ("UnitTest", "Unit test", "Unit Test"),
    ("FifteenMinuteTest", "15-minute test", "15-minute Test"),
    ("GrammarPractice", "Grammar practice", "Grammar Practice"),
    ("TopicPractice", "Topic practice", "Topic Practice"),
    ("Placement", "Placement test", "Placement"),
]


@pytest.fixture(autouse=True)
def _keep_short_names() -> Iterator[None]:
    """The short names are process-wide; give the next test the built-in ones back."""
    saved = dict(m.OCCASION_SHORT_NAMES)
    yield
    m.set_occasion_short_names(saved)


def _seed_names(conn: sqlite3.Connection) -> None:
    """The seed with real stored names (as ``write_test_meta`` makes them)."""
    seed(conn)
    for tid in ("T-1", "T-2", "T-3", "T-4"):
        meta = m.TestMetadata.model_validate_json(
            conn.execute("SELECT meta FROM tests WHERE id = ?", (tid,)).fetchone()[0]
        )
        db.sync_test_meta(conn, tid, meta)


def test_seed_equals_the_domain_defaults(tmp_path: object) -> None:
    c = db.open_database(f"{tmp_path}/app.db")
    rows = [
        tuple(r)
        for r in c.execute("SELECT code, label, short_name, position, builtin FROM occasions")
    ]
    c.close()
    assert sorted(rows, key=lambda r: r[3]) == [
        (code, label, short, i, 1) for i, (code, label, short) in enumerate(BUILTINS)
    ]
    assert {code: short for code, _, short in BUILTINS} == m.OCCASION_SHORT_NAMES
    assert [code for code, _, _ in BUILTINS] == list(m.OCCASIONS)


@pytest.mark.asyncio
async def test_teacher_occasion_in_the_test_name(ctx: AppContext, conn: sqlite3.Connection) -> None:
    _seed_names(conn)
    async with client(ctx) as c:
        listed = (await c.get("/occasions")).json()
        assert [(o["code"], o["label"], o["short_name"]) for o in listed] == BUILTINS
        assert next(o for o in listed if o["code"] == "FinalTerm")["test_count"] == 3  # not T-3
        r = await c.post("/occasions", json={"label": " Weekly  quiz ", "short_name": "Quiz"})
        assert r.status_code == 200, r.text
        new = r.json()
        assert new["code"].startswith("Custom:") and new["label"] == "Weekly quiz"
        assert new["position"] == 10 and not new["builtin"]
        assert (
            await c.post("/occasions", json={"label": " ", "short_name": "x"})
        ).status_code == 422
        # the seed's review rows are synthetic, so the chip write goes through write_test_meta
        db.write_test_meta(conn, "T-1", {"occasion": new["code"]}, by_teacher=True)
        name = conn.execute("SELECT display_name FROM tests WHERE id = 'T-1'").fetchone()[0]
        assert name == "Grade 8 - Quiz 1 - Test 1"
        found = {t["id"] for t in (await c.get("/tests", params={"q": "weekly"})).json()}
        assert found == {"T-1"}
        # moved to the top
        r = await c.patch(f"/occasions/{new['code']}", json={"position": 0})
        assert r.status_code == 200
        assert (await c.get("/occasions")).json()[0]["code"] == new["code"]
        assert (await c.patch("/occasions/Custom:nope", json={"label": "x"})).status_code == 404


@pytest.mark.asyncio
async def test_rename_remakes_automatic_names_only(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    _seed_names(conn)
    async with client(ctx) as c:
        db.write_test_meta(conn, "T-4", {"display_name": "My own name"}, by_teacher=True)
        before = dict(conn.execute("SELECT id, updated_at FROM tests").fetchall())
        r = await c.patch("/occasions/FinalTerm", json={"short_name": "End of Term"})
        assert r.status_code == 200, r.text
        assert r.json()["label"] == "Final-term test"
        names = dict(conn.execute("SELECT id, display_name FROM tests").fetchall())
        assert names["T-2"] == "Grade 8 - End of Term 1 - Test 2"
        assert names["T-4"] == "My own name"
        assert dict(conn.execute("SELECT id, updated_at FROM tests").fetchall()) == before
        found = {t["id"] for t in (await c.get("/tests", params={"q": "End of Term"})).json()}
        assert found == {"T-1", "T-2"}


@pytest.mark.asyncio
async def test_delete_refused_while_used_or_built_in(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    _seed_names(conn)
    async with client(ctx) as c:
        r = await c.delete("/occasions/FinalTerm")
        assert r.status_code == 409 and "built-in" in r.json()["detail"]
        code = (await c.post("/occasions", json={"label": "Quiz", "short_name": "Quiz"})).json()[
            "code"
        ]
        db.write_test_meta(conn, "T-2", {"occasion": code}, by_teacher=True)
        r = await c.delete(f"/occasions/{code}")
        assert r.status_code == 409 and r.json()["detail"] == "1 test uses this occasion."
        # a merged test does not block the delete
        conn.execute("UPDATE tests SET occasion = 'FinalTerm' WHERE id = 'T-2'")
        conn.execute("UPDATE tests SET occasion = ? WHERE id = 'T-3'", (code,))
        conn.commit()
        assert (await c.delete(f"/occasions/{code}")).status_code == 204
        assert code not in {o["code"] for o in (await c.get("/occasions")).json()}
        merged = conn.execute(
            "SELECT occasion, meta, display_name FROM tests WHERE id = 'T-3'"
        ).fetchone()
        assert merged[0] == "Other:unknown"
        assert m.TestMetadata.model_validate_json(merged[1]).occasion == "Other:unknown"
        assert merged[2] == "Grade 8 - Test 3"
        assert (await c.delete(f"/occasions/{code}")).status_code == 404
