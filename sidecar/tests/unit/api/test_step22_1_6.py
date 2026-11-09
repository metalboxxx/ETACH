"""Step 22.1.6: save as DOCX (PRD D4 v5.0, llm-design v4.23). R22.1.6.1 to R22.1.6.3, R22.1.6.5."""

from __future__ import annotations

import io
import os
import sqlite3
import unicodedata
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from docx import Document
from docx.oxml.ns import qn
from unit.api.test_routes_b import T0, _attempt, _test
from unit.domain.test_test_text import ALL

from etach.api.app import create_app
from etach.api.deps import AppContext
from etach.domain import docx_export
from etach.domain import models as m
from etach.domain.test_text import _picture_line, heading_text
from etach.store import db
from etach.store.repos import attempts, keys

# --- helpers ------------------------------------------------------------------------------------


def _test_of(content: m.TestContent, **meta: object) -> m.Test:
    return m.Test(
        id="T-1",
        meta=m.TestMetadata(occasion="Other:Giữa kì", grade=8, term=1, **meta),  # type: ignore[arg-type]
        content=content,
        content_schema_version=1,
        fingerprint="fp",
        points_possible=sum(s.points for s in content.sections),
        source_run_id=None,
        merged_into=None,
        created_at=T0,
        updated_at=T0,
    )


def _text(doc: object) -> list[str]:
    buf = io.BytesIO()
    doc.save(buf)  # type: ignore[attr-defined]
    buf.seek(0)
    back = Document(buf)
    lines = [p.text for p in back.paragraphs]
    for t in back.tables:
        for row in t.rows:
            lines.append(" | ".join(c.text for c in row.cells))
    return lines


def _plain(rich: str) -> str:
    return rich.replace("**", "").replace("<u>", "").replace("</u>", "")


def _expected(test: m.Test, paths: dict[str, str] | None = None) -> list[str]:
    """The print view's order (CleanTest), as plain text."""
    out = [test.meta.display_name(), docx_export.meta_line(test)]
    for s in test.content.sections:
        out.append(heading_text(s))  # no points (v1.21, D7)
        if s.instructions:
            out.append(s.instructions)
        for g in s.groups:
            if g.stimulus:
                out.append(_plain(g.stimulus))
            out.extend(_picture_line(p, paths) for p in g.pictures)
            for q in g.questions:
                out.append(f"{q.printed_number}. " + _plain(q.stem or ""))
                if q.cue:
                    out.append(f"({q.cue})")
                if q.options:
                    out.append(_plain("    ".join(f"{o.label}. {o.text}" for o in q.options)))
    return out


SYNTH = {k: v for k, v in ALL.items() if v.sections}


# --- R22.1.6.1: the test DOCX ---------------------------------------------------------------------


def test_enough_synthetic_tests() -> None:
    every = list(SYNTH.values())
    assert len(every) >= 5
    assert any(g.stimulus for c in every for s in c.sections for g in s.groups)
    assert any(g.pictures for c in every for s in c.sections for g in s.groups)
    assert any(s.skill == "writing" for c in every for s in c.sections)
    assert any("____" in (g.stimulus or "") for c in every for s in c.sections for g in s.groups)


@pytest.mark.parametrize("name", sorted(SYNTH))
def test_r22_1_6_1_test_docx_has_the_print_text_in_order(name: str) -> None:
    test = _test_of(SYNTH[name], duration_minutes=45)
    lines = _text(docx_export.test_document(test))
    assert lines == _expected(test)  # same characters as stored: NFC text stays NFC


def test_r22_1_6_1_vietnamese_unchanged_and_no_key() -> None:
    content = SYNTH[sorted(SYNTH)[0]]
    vi = unicodedata.normalize("NFC", "Đọc đoạn văn và chọn đáp án đúng nhất.")
    sec = content.sections[0].model_copy(update={"instructions": vi})
    test = _test_of(m.TestContent(sections=[sec, *content.sections[1:]]))
    lines = _text(docx_export.test_document(test))
    assert vi in lines
    assert "Giữa kì 1" in lines[0]
    assert not any("Answer key" in x or "accepted" in x.lower() for x in lines)


# --- R22.1.6.2: key and report ------------------------------------------------------------------


def _key(qid: str, accepted: list[str]) -> m.AnswerKey:
    return m.AnswerKey(
        test_id="T-1",
        question_id=qid,
        accepted=accepted,
        reason_vi=None,
        source="ai",
        status="ai_verified",
        confidence=0.9,
        updated_at=T0,
    )


def test_r22_1_6_2_key_lists_each_number_with_its_answers() -> None:
    test = _test_of(SYNTH["edge_cases"])
    qs = [q for s in test.content.sections for g in s.groups for q in g.questions]
    ks = [_key(qs[0].id, ["B"]), _key(qs[1].id, ["has been", "'s been"])]
    lines = _text(docx_export.key_document(test, ks))
    assert lines[0].startswith("Key: ")
    assert not any("Answer key" in x or "correct answer" in x.lower() for x in lines)
    assert lines[1:] == [
        f"{q.printed_number}. "
        + {qs[0].id: "B", qs[1].id: "has been / 's been"}.get(q.id, "(no key)")
        for q in qs
    ]


def test_r22_1_6_2_report_has_what_the_panel_shows() -> None:
    report = m.GradeReport(
        attempt_id="A-1",
        run_id="r",
        # "tense" is not a taxonomy code: the report shows "Other skill" (step 22.4.6)
        weak_points=[m.WeakPoint(skill_tag="tense", wrong=2, seen=3, gap_errors=0, note_vi="Thì")],
        careless_notes=["Quên dấu chấm."],
        summary_vi="Tốt.",
        teacher_questions=[m.TeacherQuestion(question_vi="Em hiểu chưa?", what_answers_mean_vi="")],
        uncertain_points=0.25,
        created_at=T0,
    )
    expl = m.Explanation(
        test_id="T-1",
        question_id="q-2",
        wrong_answer_norm="a",
        error_type="gap",
        text_vi="Cần dùng thì hiện tại.",
        status="ai",
        llm_call_id="c",
    )
    rows = [docx_export.VerdictRow(2, "A", "incorrect"), docx_export.VerdictRow(1, None, "correct")]
    lines = _text(docx_export.report_document("R", 7.5, 10, report, rows, [expl], {"q-2": 2}))
    assert lines[:2] == ["R", "Score: 7.5/10 · 0.25 unsure"]
    for want in ["Tốt.", "Em hiểu chưa?", "Other skill: 2/3 wrong — Thì", "Quên dấu chấm."]:
        assert want in lines
    assert "2. Cần dùng thì hiện tại." in lines
    assert lines[-2:] == ["1. | (blank) | ✓", "2. | A | ✗"]


# --- R22.1.6.5: valid DOCX, print fonts -----------------------------------------------------------


def test_r22_1_6_5_fonts_are_the_print_fonts(tmp_path: Path) -> None:
    test = _test_of(SYNTH["edge_cases"])
    path = docx_export.save_unique(docx_export.test_document(test), tmp_path, "x")
    back = Document(str(path))
    normal = back.styles["Normal"].font
    assert normal.name == "Noto Serif"
    assert back.styles["Title"].font.name == "Be Vietnam Pro"
    assert back.styles["Heading 2"].font.name == "Be Vietnam Pro"
    rfonts = back.styles["Normal"].element.rPr.rFonts
    assert rfonts.get(qn("w:cs")) == "Noto Serif"


# --- R22.1.6.3: routes, folder, names -------------------------------------------------------------


def test_safe_file_name() -> None:
    assert docx_export.safe_file_name('Grade 8 · A/B: "x"?*<>|') == "Grade 8 · A_B_ _x______"
    assert docx_export.safe_file_name("CON") == "_CON"
    assert docx_export.safe_file_name("name. ") == "name"


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


@asynccontextmanager
async def client(ctx: AppContext) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(ctx))
    headers = {"Authorization": f"Bearer {ctx.token}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=headers) as c:
        yield c


def _tree(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


@pytest.mark.asyncio
async def test_r22_1_6_3_exports_land_in_exports_only(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    root = ctx.paths.root.parent
    test_id = _test(conn)
    keys.upsert_key(conn, _key("q-1", ["A"]).model_copy(update={"test_id": test_id}))
    conn.commit()
    before = _tree(root)
    exports = (ctx.paths.root / "exports").resolve()
    async with client(ctx) as c:
        r1 = await c.post(f"/tests/{test_id}/export", json={"what": "test"})
        r2 = await c.post(f"/tests/{test_id}/export", json={"what": "test"})
        r3 = await c.post(f"/tests/{test_id}/export", json={"what": "key"})
        bad = await c.post(f"/tests/{test_id}/export", json={"what": "pdf"})
        missing = await c.post("/tests/T-999/export", json={"what": "test"})
    assert r1.status_code == 200, r1.text
    name = "Grade 8 - Final Term 1 - Test 1 - Test"
    assert r1.json() == {"path": str(exports / f"{name}.docx"), "file_name": f"{name}.docx"}
    assert r2.json()["file_name"] == f"{name} (2).docx"
    assert r3.json()["file_name"] == "Grade 8 - Final Term 1 - Test 1 - Key.docx"
    assert bad.status_code == 422 and missing.status_code == 404
    new = _tree(root) - before
    new_files = {n for n in new if not n.startswith(os.path.join("data", "app.db"))}
    assert new_files == {
        os.path.join("data", "exports", n)
        for n in (f"{name}.docx", f"{name} (2).docx", "Grade 8 - Final Term 1 - Test 1 - Key.docx")
    }
    for n in new_files:
        Document(str(root / n))  # R22.1.6.5: python-docx reopens it


@pytest.mark.asyncio
async def test_r22_1_6_2_report_export_409_then_saved(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    test_id = _test(conn)
    graded = _attempt(conn, test_id, graded=True)
    conn.commit()
    async with client(ctx) as c:
        r = await c.post(f"/attempts/{graded.id}/report/export")
        assert r.status_code == 409, r.text
        assert "not graded" in r.json()["detail"]
        assert (await c.post("/attempts/A-999/report/export")).status_code == 404
    attempts.replace_grade_report(
        conn,
        m.GradeReport(
            attempt_id=graded.id,
            run_id=graded.source_run_id,
            weak_points=[],
            careless_notes=[],
            summary_vi="Tốt.",
            teacher_questions=[],
            uncertain_points=0.0,
            created_at=T0,
        ),
    )
    conn.commit()
    async with client(ctx) as c:
        r = await c.post(f"/attempts/{graded.id}/report/export")
    assert r.status_code == 200, r.text
    path = Path(r.json()["path"])
    assert path.parent == (ctx.paths.root / "exports").resolve()
    assert r.json()["file_name"].endswith(".docx") and " - Report - " in r.json()["file_name"]
    lines = _text(Document(str(path)))
    assert "Score: 0.25/0.5 · 0 unsure" in lines and "Tốt." in lines
