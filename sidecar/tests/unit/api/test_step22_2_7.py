"""Step 22.2.7: the teacher's answers. R22.2.7.1 (the report DOCX) and R22.2.7.3 (the typed Test
name, units and tags through ``PATCH /tests/{id}``)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

import pytest
from unit.api.test_routes_b import T0, _test
from unit.api.test_step22_1_6 import _text

from etach.api.deps import AppContext
from etach.domain import docx_export
from etach.domain import models as m
from etach.store import db


@pytest.fixture
def ctx(make_ctx: Callable[..., AppContext]) -> AppContext:
    return make_ctx()


def _conn(ctx: AppContext) -> sqlite3.Connection:
    return db.connect(ctx.paths.db)


def test_r22_2_7_1_report_docx_words_an_uncertain_grade() -> None:
    report = m.GradeReport(
        attempt_id="A-1",
        run_id="r",
        weak_points=[],
        careless_notes=[],
        summary_vi="",
        teacher_questions=[],
        uncertain_points=0.25,
        created_at=T0,
    )
    rows = [docx_export.VerdictRow(1, "A", "uncertain"), docx_export.VerdictRow(2, "B", "correct")]
    lines = _text(docx_export.report_document("R", 7.5, 10, report, rows, [], {}))
    assert lines[-2:] == ["1. | A | AI unsure grade", "2. | B | ✓"]
    assert not any(line.endswith("| ?") for line in lines)


@pytest.mark.asyncio
async def test_r22_2_7_3_typed_name_units_and_tags(ctx: AppContext, api: Any) -> None:
    conn = _conn(ctx)
    try:
        test_id = _test(conn)
    finally:
        conn.close()
    auto = "Grade 8 - Final Term 1 - Test 1"
    async with api.serving(ctx) as live, live.client() as client:
        auth = live.auth

        async def patch(meta: dict[str, Any]) -> dict[str, Any]:
            r = await client.patch(f"/tests/{test_id}", json={"meta": meta}, headers=auth)
            assert r.status_code == 200, r.text
            return dict(r.json())

        async def name() -> str:
            (row,) = (await client.get("/tests", headers=auth)).json()
            return str(row["display_name"])

        got = await patch({"display_name": "  My name "})
        assert await name() == "My name"
        assert got["meta"]["extra"]["display_name"] == "My name"
        assert "display_name" in got["meta"]["edited_fields"]
        # a later metadata edit keeps the typed name
        got = await patch({"grade": 9, "units": ["Unit 1", "Unit 2"], "tags": ["hard"]})
        assert await name() == "My name"
        assert got["meta"]["units"] == ["Unit 1", "Unit 2"]
        assert got["meta"]["tags"] == ["hard"]
        found = (await client.get("/tests", params={"q": "my name"}, headers=auth)).json()
        assert [t["id"] for t in found] == [test_id]
        assert found[0]["display_name"] == "My name"
        # an extraction write cannot replace it
        conn = _conn(ctx)
        try:
            db.write_test_meta(conn, test_id, {"display_name": "AI"}, by_teacher=False)
        finally:
            conn.close()
        assert await name() == "My name"
        # null goes back to the automatic name
        got = await patch({"display_name": None})
        assert await name() == auto.replace("Grade 8", "Grade 9")
        assert "display_name" not in got["meta"]["edited_fields"]
        assert "display_name" not in got["meta"]["extra"]
        assert got["meta"]["units"] == ["Unit 1", "Unit 2"]
