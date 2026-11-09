"""Step 12 part B routes: files, threads, runs, tests, attempts (R12.4, R12.5, R12.8 half, D18)."""

from __future__ import annotations

import argparse
import asyncio
import io
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pymupdf
import pytest
from PIL import Image

from etach.api.deps import AppContext
from etach.cli import _page_inputs
from etach.domain import models as m
from etach.store import db
from etach.store.files import FileStore
from etach.store.repos import attempts, explanations, keys, runs, tests, threads

T0 = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)


# --- small factories ----------------------------------------------------------------------------


def _content(n: int = 2) -> m.TestContent:
    questions = [
        m.Question(
            id=f"q-{i}",
            number=i,
            printed_number=i,
            page_no=1,
            answer_form="choice",
            stem=f"Stem {i}",
            options=[m.Option(label="A", text="one"), m.Option(label="B", text="two")],
            cue=None,
            points=0.25,
        )
        for i in range(1, n + 1)
    ]
    group = m.QuestionGroup(id="g-1", stimulus=None, pictures=[], questions=questions)
    section = m.Section(
        id="s-1",
        number=1,
        printed_title="I",
        title="Choose",
        instructions="Circle A or B.",
        points=0.25 * n,
        points_source="printed",
        skill="grammar",
        groups=[group],
    )
    return m.TestContent(sections=[section])


def _test(conn: sqlite3.Connection) -> str:
    return tests.insert_test(
        conn,
        m.Test(
            id=tests.next_test_id(conn),
            meta=m.TestMetadata(occasion="FinalTerm", grade=8, term=1, test_number="1"),
            content=_content(),
            content_schema_version=1,
            fingerprint="fp",
            points_possible=0.5,
            source_run_id=None,
            merged_into=None,
            created_at=T0,
            updated_at=T0,
        ),
    ).id


def _attempt(conn: sqlite3.Connection, test_id: str, graded: bool, **kw: Any) -> m.Attempt:
    thread = threads.create_thread(conn, "photos", kind="filled", test_id=test_id)
    run = runs.create_run(
        conn,
        thread.id,
        "extract",
        m.ExtractInput(pages=[], existing_test_id=None, supersedes_attempt_id=None),
        status="done",
    )
    values: dict[str, Any] = {
        "id": attempts.next_attempt_id(conn),
        "test_id": test_id,
        "thread_id": thread.id,
        "student_id": None,
        "student_name_read": "Nguyễn  Văn An",
        "class_read": "8A",
        "source_run_id": run.id,
        "superseded_by": None,
        "status": "graded" if graded else "extracted",
        "version": 1,
        "score_earned": 0.25 if graded else None,
        "score_possible": 0.5 if graded else None,
        "created_at": T0,
    }
    values.update(kw)
    att = attempts.insert_attempt(conn, m.Attempt(**values))
    attempts.insert_answers(
        conn,
        [
            m.Answer(
                attempt_id=att.id,
                question_id=q,
                printed_number=i,
                page_no=1,
                value="A",
                value_norm="a",
                location="circled_option",
                confidence=0.95,
                reading_unsure=False,
                alt_value=None,
                alt_question_id=None,
                verdict="incorrect" if graded else "ungraded",
                points_awarded=0.0 if graded else None,
                teacher_override=None,
            )
            for i, q in enumerate(("q-1", "q-2"), start=1)
        ],
    )
    return att


def _llm_call(conn: sqlite3.Connection) -> str:
    thread = threads.create_thread(conn, "x")
    run = runs.create_run(
        conn, thread.id, "grade", m.GradeInput(test_id="T-1", attempt_id=None, reason="button")
    )
    step = runs.insert_step(conn, run.id, "explain", None, 1)
    return runs.insert_llm_call(
        conn,
        m.LlmCall(
            id=db.new_ulid(),
            step_id=step.id,
            role="reasoning",
            model="model-x",
            prompt_hash="h",
            request={"messages": []},
            response_text="{}",
            thinking_text="",
            logprobs=None,
            status="complete",
            tokens_in=1,
            tokens_out=1,
            ms=5,
            created_at=T0,
        ),
    ).id


def _key(test_id: str, qid: str, accepted: str) -> m.AnswerKey:
    return m.AnswerKey(
        test_id=test_id,
        question_id=qid,
        accepted=[accepted],
        reason_vi=None,
        source="ai",
        status="ai_unverified",
        confidence=0.9,
        updated_at=T0,
    )


@pytest.fixture
def ctx(make_ctx: Callable[..., AppContext]) -> AppContext:
    return make_ctx()


def _conn(ctx: AppContext) -> sqlite3.Connection:
    return db.connect(ctx.paths.db)


def _extract_input(ctx: AppContext, s1: Any) -> m.ExtractInput:
    conn = _conn(ctx)
    try:
        files = FileStore(conn, ctx.paths)
        pages, manifest = _page_inputs(argparse.Namespace(pages=[], key=[], replay=s1), files)
    finally:
        conn.close()
    return m.ExtractInput(
        pages=pages,
        existing_test_id=manifest.existing_test_id,
        supersedes_attempt_id=manifest.supersedes_attempt_id,
    )


async def _wait_status(client: Any, auth: dict[str, str], run_id: str, status: str) -> None:
    async with asyncio.timeout(60):
        while True:
            r = await client.get(f"/runs/{run_id}", headers=auth)
            assert r.status_code == 200, r.text
            if r.json()["run"]["status"] == status:
                return
            await asyncio.sleep(0.05)


# --- files --------------------------------------------------------------------------------------


def _png(w: int, h: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(out, "PNG")
    return out.getvalue()


def _pdf(pages: int) -> bytes:
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Page {i + 1} text")
    data: bytes = doc.tobytes()
    doc.close()
    return data


@pytest.mark.asyncio
async def test_upload_png_pdf_and_thumbnail(ctx: AppContext, api: Any) -> None:
    async with api.serving(ctx) as live, live.client() as client:
        r = await client.post(
            "/files",
            params={"name": "C:\\phone\\photo.png"},
            content=_png(900, 600),
            headers=live.auth,
        )
        assert r.status_code == 200, r.text
        png = r.json()
        assert len(png["pages"]) == 1 and png["pages"][0]["file_id"] == png["file_id"]

        r = await client.get(f"/files/{png['file_id']}", headers=live.auth)
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
        assert r.content == _png(900, 600)
        r = await client.get(f"/files/{png['file_id']}", params={"thumb": 1, "token": ctx.token})
        assert r.status_code == 200
        thumb = Image.open(io.BytesIO(r.content))
        assert max(thumb.size) <= 256 and thumb.size == (256, 171)

        r = await client.post(
            "/files", params={"name": "test.pdf"}, content=_pdf(2), headers=live.auth
        )
        assert r.status_code == 200, r.text
        pdf = r.json()
        assert len(pdf["pages"]) == 2
        assert all(p["text_file_id"] for p in pdf["pages"])
        r = await client.get(f"/files/{pdf['file_id']}", headers=live.auth)
        assert r.headers["content-type"] == "application/pdf"
        r = await client.get(
            f"/files/{pdf['pages'][1]['file_id']}", params={"thumb": "1"}, headers=live.auth
        )
        assert max(Image.open(io.BytesIO(r.content)).size) <= 256

        r = await client.post(
            "/files", params={"name": "a.txt"}, content=b"hello", headers=live.auth
        )
        assert r.status_code == 415 and "a.txt" in r.json()["detail"]
        assert (await client.get("/files/nope", headers=live.auth)).status_code == 404

    conn = _conn(ctx)
    try:
        assert FileStore(conn, ctx.paths).get(png["file_id"]).original_name == "photo.png"
    finally:
        conn.close()


# --- threads + runs: R12.4, D18, R12.8 ----------------------------------------------------------


@pytest.mark.asyncio
async def test_r12_4_stop_resume_discard_and_d18(ctx: AppContext, api: Any) -> None:
    inp = _extract_input(ctx, api.S1).model_dump(mode="json")
    async with api.serving(ctx) as live, live.client() as client:
        auth = live.auth
        thread_id = (await client.post("/threads", json={}, headers=auth)).json()["thread_id"]
        r = await client.post(
            f"/threads/{thread_id}/runs", json={"kind": "extract", "input": inp}, headers=auth
        )
        assert r.status_code == 200, r.text
        run_id = r.json()["id"]

        r = await client.post(f"/runs/{run_id}/stop", headers=auth)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "stopped"
        assert (await client.post(f"/runs/{run_id}/stop", headers=auth)).status_code == 409

        r = await client.post(f"/runs/{run_id}/resume", headers=auth)
        assert r.status_code == 200, r.text
        await _wait_status(client, auth, run_id, "done")
        assert (await client.post(f"/runs/{run_id}/resume", headers=auth)).status_code == 409
        assert (await client.post(f"/runs/{run_id}/discard", headers=auth)).status_code == 409

        detail = (await client.get(f"/runs/{run_id}", headers=auth)).json()
        assert detail["steps"] and any(s["calls"] for s in detail["steps"])
        assert all(c["task"] for s in detail["steps"] for c in s["calls"])

        # D18: the thread already ran
        r = await client.post(
            f"/threads/{thread_id}/runs", json={"kind": "extract", "input": inp}, headers=auth
        )
        assert r.status_code == 409
        assert r.json()["detail"] == "thread already ran; start a new thread"

        t = (await client.get(f"/threads/{thread_id}", headers=auth)).json()
        # the recorded S1 paper replays as a blank test since step 22.6.2 (1 of 34 read sure)
        assert t["test"] is not None
        listed = (await client.get("/threads", headers=auth)).json()
        row = next(x for x in listed if x["thread"]["id"] == thread_id)
        assert row["kind"] in ("filled", "blank") and row["group"]
        r = await client.get(f"/threads/{thread_id}/messages", headers=auth)
        assert r.status_code == 200 and isinstance(r.json(), list)

        # Discard a stopped run
        other = (await client.post("/threads", json={}, headers=auth)).json()["thread_id"]
        r = await client.post(
            f"/threads/{other}/runs", json={"kind": "extract", "input": inp}, headers=auth
        )
        run2 = r.json()["id"]
        assert (await client.post(f"/runs/{run2}/stop", headers=auth)).json()["status"] == "stopped"
        r = await client.post(f"/runs/{run2}/discard", headers=auth)
        assert r.status_code == 200 and r.json()["status"] == "discarded"
        assert (await client.post("/runs/nope/stop", headers=auth)).status_code == 404
        assert (await client.get("/threads/nope", headers=auth)).status_code == 404


@pytest.mark.asyncio
async def test_d18_thread_with_an_attempt_and_grade_checks(ctx: AppContext, api: Any) -> None:
    conn = _conn(ctx)
    try:
        test_id = _test(conn)
        att = _attempt(conn, test_id, graded=False)
    finally:
        conn.close()
    empty = m.ExtractInput(pages=[], existing_test_id=None, supersedes_attempt_id=None)
    async with api.serving(ctx) as live, live.client() as client:
        r = await client.post(
            f"/threads/{att.thread_id}/runs",
            json={"kind": "extract", "input": empty.model_dump(mode="json")},
            headers=live.auth,
        )
        assert r.status_code == 409
        bad = {"test_id": test_id, "attempt_id": "A-999", "reason": "button"}
        r = await client.post(
            f"/threads/{att.thread_id}/runs",
            json={"kind": "grade", "input": bad},
            headers=live.auth,
        )
        assert r.status_code == 404
        good = {"test_id": test_id, "attempt_id": att.id, "reason": "button"}
        r = await client.post(
            f"/threads/{att.thread_id}/runs",
            json={"kind": "grade", "input": good},
            headers=live.auth,
        )
        assert r.status_code == 200 and r.json()["kind"] == "grade"
        listed = (await client.get("/threads", headers=live.auth)).json()
        row = next(x for x in listed if x["thread"]["id"] == att.thread_id)
        assert row["group"] == "Chưa rõ"


@pytest.mark.asyncio
async def test_r12_8_runs_active_after_restart(ctx: AppContext, api: Any) -> None:
    inp = _extract_input(ctx, api.S1)
    conn = _conn(ctx)
    try:  # what a crash leaves: one run `running`, one `stopped`
        thread_id = threads.create_thread(conn, "t").id
        crashed = runs.create_run(conn, thread_id, "extract", inp)
        runs.set_run_status(conn, crashed.id, "running")
        runs.insert_step(conn, crashed.id, "transcribe", "page-1", 1)
        stopped = runs.create_run(conn, thread_id, "extract", inp)
        runs.set_run_status(conn, stopped.id, "stopped")
        finished = runs.create_run(conn, thread_id, "extract", inp)
        runs.set_run_status(conn, finished.id, "done")
    finally:
        conn.close()
    async with api.serving(ctx) as live, live.client() as client:
        r = await client.get("/runs/active", headers=live.auth)
    assert r.status_code == 200
    got = {row["run"]["id"]: row for row in r.json()}
    assert got[crashed.id]["run"]["status"] == "interrupted"
    assert got[crashed.id]["current_step"]["node"] == "transcribe"
    assert got[stopped.id]["run"]["status"] == "stopped"
    assert finished.id not in got


# --- tests: R12.5, keys, merge ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r12_5_patch_meta_and_content(ctx: AppContext, api: Any) -> None:
    conn = _conn(ctx)
    try:
        test_id = _test(conn)
        _attempt(conn, test_id, graded=False)
    finally:
        conn.close()
    async with api.serving(ctx) as live, live.client() as client:
        auth = live.auth
        assert (await client.get("/tests", params={"q": "Lomonosov"}, headers=auth)).json() == []
        r = await client.patch(
            f"/tests/{test_id}", json={"meta": {"school": "Lomonosov School"}}, headers=auth
        )
        assert r.status_code == 200, r.text
        assert "school" in r.json()["meta"]["edited_fields"]
        found = (await client.get("/tests", params={"q": "lomono"}, headers=auth)).json()
        assert [t["id"] for t in found] == [test_id]
        assert found[0]["attempt_count"] == 1
        everything = (await client.get("/tests", headers=auth)).json()
        assert [t["id"] for t in everything] == [test_id]

        r = await client.patch(f"/tests/{test_id}", json={"meta": {"bogus": 1}}, headers=auth)
        assert r.status_code == 422
        content = _content(3).model_dump(mode="json")
        content["sections"][0]["groups"][0]["questions"][0]["options"] = []  # mcq without options
        r = await client.patch(f"/tests/{test_id}", json={"content": content}, headers=auth)
        assert r.status_code == 422 and r.json()["detail"]["failures"]
        r = await client.patch(
            f"/tests/{test_id}", json={"content": _content(3).model_dump(mode="json")}, headers=auth
        )
        assert r.status_code == 200, r.text
        got = (await client.get(f"/tests/{test_id}", headers=auth)).json()
        assert got["points_possible"] == 10.0  # PRD D13 v8.0: always out of 10
        assert got["meta"]["school"] == "Lomonosov School"


@pytest.mark.asyncio
async def test_get_test_picture_paths(ctx: AppContext, api: Any) -> None:
    """llm-design v4.10: ``picture_paths`` gives each picture's stored path with its real ext."""
    jpg_out = io.BytesIO()
    Image.new("RGB", (40, 30), (10, 120, 30)).save(jpg_out, "JPEG")
    conn = _conn(ctx)
    try:
        store = FileStore(conn, ctx.paths)
        png_id = store.put(_png(40, 30), "png")
        jpg_id = store.put(jpg_out.getvalue(), "jpg")
        test_id = _test(conn)
        test = tests.get_test(conn, test_id)
        assert test is not None
        content = test.content.model_copy(deep=True)
        group = content.sections[0].groups[0]
        group.pictures = [
            m.PictureRef(file_id=png_id, page_no=1),
            m.PictureRef(file_id=jpg_id, page_no=2),
            m.PictureRef(file_id=png_id, page_no=1),
        ]
        with db.transaction(conn):
            tests.update_content(conn, test_id, content, test.points_possible)
    finally:
        conn.close()
    async with api.serving(ctx) as live, live.client() as client:
        got = (await client.get(f"/tests/{test_id}", headers=live.auth)).json()
    assert got["picture_paths"] == {
        png_id: f"files/{png_id[:2]}/{png_id}.png",
        jpg_id: f"files/{jpg_id[:2]}/{jpg_id}.jpg",
    }
    assert got["content"]["sections"][0]["groups"][0]["pictures"][0]["file_id"] == png_id


@pytest.mark.asyncio
async def test_get_test_pages_and_key_pages(ctx: AppContext, api: Any) -> None:
    """R22.1.4.1 (llm-design v4.21): ``pages`` is every ``test_pages`` row by ``page_no``;
    ``key_pages`` is every ``test_key_pages`` row by ``page_no`` (v4.27); a test with no stored
    photos returns two empty lists."""
    conn = _conn(ctx)
    try:
        store = FileStore(conn, ctx.paths)
        p1 = store.put(_png(40, 30), "png")
        p2 = store.put(_png(30, 40), "png")
        with_photos = _test(conn)
        without = _test(conn)
        tests.add_test_page(conn, with_photos, 2, p2)  # inserted out of order on purpose
        tests.add_test_page(conn, with_photos, 1, p1)
        tests.add_key_page(conn, with_photos, 3, p1)
    finally:
        conn.close()
    async with api.serving(ctx) as live, live.client() as client:
        got = (await client.get(f"/tests/{with_photos}", headers=live.auth)).json()
        empty = (await client.get(f"/tests/{without}", headers=live.auth)).json()
    assert got["pages"] == [{"page_no": 1, "file_id": p1}, {"page_no": 2, "file_id": p2}]
    assert got["key_pages"] == [{"page_no": 3, "file_id": p1}]
    assert empty["pages"] == []
    assert empty["key_pages"] == []


@pytest.mark.asyncio
async def test_key_edit_deletes_explanations_and_defers_the_regrade(
    ctx: AppContext, api: Any
) -> None:
    """R22.4.5.1 (data-model v1.20, llm-design v4.36): 3 key changes on a test with 2 graded
    attempts queue no run and leave one ``regrade_pending`` row; ``POST /regrade`` queues 2 runs
    (``key_verified``) and clears it; a second call queues none."""
    conn = _conn(ctx)
    try:
        test_id = _test(conn)
        graded_atts = [_attempt(conn, test_id, graded=True) for _ in range(2)]
        graded = {a.id for a in graded_atts}
        thread_id = graded_atts[0].thread_id
        _attempt(conn, test_id, graded=False)
        keys.upsert_key(conn, _key(test_id, "q-1", "A"))
        keys.upsert_key(conn, _key(test_id, "q-2", "B"))
        call_id = _llm_call(conn)
        explanations.upsert_explanation(
            conn,
            m.Explanation(
                test_id=test_id,
                question_id="q-1",
                wrong_answer_norm="b",
                error_type="gap",
                text_vi="x",
                status="ai",
                llm_call_id=call_id,
            ),
        )
        before = {r.id for r in runs.list_runs(conn)}
    finally:
        conn.close()
    async with api.serving(ctx) as live, live.client() as client:
        auth = live.auth

        async def pending() -> bool:
            r = await client.get(f"/tests/{test_id}", headers=auth)
            return bool(r.json()["regrade_pending"])

        assert await pending() is False
        r = await client.put(f"/tests/{test_id}/keys/q-1", json={"accepted": ["B"]}, headers=auth)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["explanations_deleted"] == 1
        assert body["key"]["source"] == "teacher_edit" and body["key"]["accepted"] == ["B"]
        assert body["run_ids"] == []
        r = await client.put(f"/tests/{test_id}/keys/q-2", json={"verify": True}, headers=auth)
        assert r.json()["key"]["status"] == "teacher_verified"
        assert r.json()["explanations_deleted"] == 0 and r.json()["run_ids"] == []
        r = await client.put(f"/tests/{test_id}/keys/q-2", json={"accepted": ["C"]}, headers=auth)
        assert r.json()["outcome"] == "updated" and r.json()["run_ids"] == []
        r = await client.put(f"/tests/{test_id}/keys/q-2", json={"verify": True}, headers=auth)
        assert r.json()["outcome"] == "unchanged" and r.json()["run_ids"] == []
        r = await client.put(f"/tests/{test_id}/keys/q-9", json={"verify": True}, headers=auth)
        assert r.status_code == 404
        r = await client.put(f"/tests/{test_id}/keys/q-1", json={}, headers=auth)
        assert r.status_code == 422
        conn = _conn(ctx)
        try:
            assert [x.id for x in runs.list_runs(conn) if x.id not in before] == []
            rows = conn.execute("SELECT test_id FROM regrade_pending").fetchall()
            assert [row[0] for row in rows] == [test_id]
        finally:
            conn.close()
        assert await pending() is True
        r = await client.get(f"/threads/{thread_id}", headers=auth)
        assert r.json()["regrade_pending"] is True

        r = await client.post(f"/tests/{test_id}/regrade", headers=auth)
        assert r.status_code == 200, r.text
        run_ids = r.json()["run_ids"]
        assert len(run_ids) == 2
        again = await client.post(f"/tests/{test_id}/regrade", headers=auth)
        assert again.json() == {"run_ids": []}  # a second call queues none
        assert await pending() is False
        assert (await client.post("/tests/T-9999/regrade", headers=auth)).status_code == 404
        # The re-grade runs are handed to the manager: still queued, or already picked up
        # (running) or finished. This test has no grade cassette, so a finished run may also have
        # failed on the first LLM call (CassetteMiss), and only so.
        for run_id in run_ids:
            run = await ctx.manager.get_run(run_id)
            picked_up = run.status in ("running", "done") or (
                run.status == "failed" and (run.error or "").startswith("CassetteMiss")
            )
            assert run_id in ctx.manager.queued_run_ids() or picked_up, (run.status, run.error)
    conn = _conn(ctx)
    try:
        assert explanations.list_explanations(conn, test_id) == []
        new = [r for r in runs.list_runs(conn) if r.id not in before]
        assert sorted(r.id for r in new) == sorted(run_ids)
        assert all(isinstance(r.input, m.GradeInput) for r in new)
        assert {r.input.attempt_id for r in new} == graded  # type: ignore[union-attr]
        assert {r.input.reason for r in new} == {"key_verified"}  # type: ignore[union-attr]
        assert conn.execute("SELECT COUNT(*) FROM regrade_pending").fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_key_change_without_graded_attempts_leaves_no_regrade_row(
    ctx: AppContext, api: Any
) -> None:
    """R22.4.5.1: a test with no graded attempt gets no row; deleting a pending test removes it."""
    conn = _conn(ctx)
    try:
        test_id = _test(conn)
        _attempt(conn, test_id, graded=False)
        keys.upsert_key(conn, _key(test_id, "q-1", "A"))
        other = _test(conn)
        _attempt(conn, other, graded=True)
        keys.upsert_key(conn, _key(other, "q-1", "A"))
    finally:
        conn.close()
    async with api.serving(ctx) as live, live.client() as client:
        auth = live.auth
        r = await client.put(f"/tests/{test_id}/keys/q-1", json={"verify": True}, headers=auth)
        assert r.json()["outcome"] == "updated" and r.json()["run_ids"] == []
        r = await client.get(f"/tests/{test_id}", headers=auth)
        assert r.json()["regrade_pending"] is False
        r = await client.post(f"/tests/{test_id}/regrade", headers=auth)
        assert r.json() == {"run_ids": []}
        await client.put(f"/tests/{other}/keys/q-1", json={"verify": True}, headers=auth)
        r = await client.get(f"/tests/{other}", headers=auth)
        assert r.json()["regrade_pending"] is True
        r = await client.delete(f"/tests/{other}", headers=auth)
        assert r.status_code == 204, r.text
    conn = _conn(ctx)
    try:
        assert conn.execute("SELECT COUNT(*) FROM regrade_pending").fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_merge_route(ctx: AppContext, api: Any) -> None:
    conn = _conn(ctx)
    try:
        survivor = _test(conn)
        merged = _test(conn)
        _attempt(conn, merged, graded=False)
    finally:
        conn.close()
    async with api.serving(ctx) as live, live.client() as client:
        r = await client.post(
            f"/tests/{merged}/merge",
            json={"into": survivor, "alignment": {"q-1": "q-1", "q-2": "q-2"}},
            headers=live.auth,
        )
        assert r.status_code == 200, r.text
        assert r.json()["remapped_answers"] == 2
        listed = (await client.get("/tests", headers=live.auth)).json()
        assert [t["id"] for t in listed] == [survivor]
        r = await client.post(
            f"/tests/{merged}/merge", json={"into": survivor, "alignment": {}}, headers=live.auth
        )
        assert r.status_code == 409


# --- attempts -----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attempt_routes(ctx: AppContext, api: Any) -> None:
    conn = _conn(ctx)
    try:
        test_id = _test(conn)
        graded = _attempt(conn, test_id, graded=True)
        ungraded = _attempt(conn, test_id, graded=False)
    finally:
        conn.close()
    async with api.serving(ctx) as live, live.client() as client:
        auth = live.auth
        r = await client.get(f"/attempts/{graded.id}", headers=auth)
        assert r.status_code == 200 and len(r.json()["answers"]) == 2

        # override → version + 1, a review_fix run for the graded attempt only
        r = await client.put(
            f"/attempts/{graded.id}/answers/q-1", json={"value": " B "}, headers=auth
        )
        assert r.status_code == 200, r.text
        assert r.json()["version"] == 2 and len(r.json()["run_ids"]) == 1
        assert r.json()["answer"]["teacher_override"] == " B "
        assert r.json()["answer"]["value_norm"] == "b"
        r = await client.put(
            f"/attempts/{ungraded.id}/answers/q-1", json={"value": "  "}, headers=auth
        )
        assert r.json()["version"] == 2 and r.json()["run_ids"] == []
        assert r.json()["answer"]["teacher_override"] == ""
        r = await client.put(
            f"/attempts/{ungraded.id}/answers/q-9", json={"value": "A"}, headers=auth
        )
        assert r.status_code == 404

        # student chip
        r = await client.put(
            f"/attempts/{graded.id}/student", json={"create_from_read": True}, headers=auth
        )
        assert r.status_code == 200, r.text
        student_id = r.json()["student_id"]
        assert student_id and r.json()["version"] == 3
        r = await client.put(
            f"/attempts/{ungraded.id}/student", json={"student_id": student_id}, headers=auth
        )
        assert r.json()["student_id"] == student_id and r.json()["version"] == 3
        r = await client.put(
            f"/attempts/{ungraded.id}/student",
            json={"full_name": "Trần Thị B", "class_name": "8B"},
            headers=auth,
        )
        assert r.json()["student_id"] != student_id and r.json()["version"] == 4
        r = await client.put(f"/attempts/{ungraded.id}/student", json={}, headers=auth)
        assert r.status_code == 422
        listed = (await client.get("/threads", headers=auth)).json()
        row = next(x for x in listed if x["thread"]["id"] == graded.thread_id)
        assert row["group"] == "Nguyễn Văn An"

        # no grade report yet
        r = await client.get(f"/attempts/{graded.id}/report", headers=auth)
        assert r.status_code == 404 and r.json()["detail"] == "not graded"

    conn = _conn(ctx)
    try:
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
    finally:
        conn.close()
    async with api.serving(ctx) as live, live.client() as client:
        r = await client.get(f"/attempts/{graded.id}/report", headers=live.auth)
        assert r.status_code == 200, r.text
        assert r.json()["report"]["summary_vi"] == "Tốt."
        assert len(r.json()["verdicts"]) == 2
