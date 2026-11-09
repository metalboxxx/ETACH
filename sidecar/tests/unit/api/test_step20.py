"""Step 20 part A: settings, backup/restore, clear logs, the maintenance scheduler, portability
(R20.1, R20.2, R20.3, R20.6, R20.7, R20.8)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
import sqlite3
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import BaseModel
from support.fake_ollama import ChatScript, FakeOllama
from support.reader import vision_reader

from etach.api.app import build_context, create_app
from etach.api.deps import AppContext
from etach.api.maintenance import ENABLED_KEY, MaintenanceScheduler, run_maintenance
from etach.api.routes.settings import FAKE_PULL_ENV
from etach.appdir import DataPaths
from etach.domain import models as m
from etach.llm.adapters import RenderedPrompt
from etach.llm.cassettes import ReplayBackend
from etach.llm.config import load_models_config
from etach.runtime.power import FakePower
from etach.store import db
from etach.store.files import FileStore
from etach.store.repos import runs, threads

SIDECAR = Path(__file__).resolve().parents[3]
S1 = SIDECAR / "tests" / "cassettes" / "s1"


@asynccontextmanager
async def client(ctx: AppContext) -> AsyncIterator[httpx.AsyncClient]:
    """The ASGI app without its lifespan (no run manager, no scheduler)."""
    transport = httpx.ASGITransport(app=create_app(ctx))
    headers = {"Authorization": f"Bearer {ctx.token}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=headers) as c:
        yield c


def _insert_calls(conn: sqlite3.Connection, now: datetime, ages: Mapping[str, float]) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    for call_id, days in ages.items():
        conn.execute(
            "INSERT INTO llm_calls (id, step_id, status, created_at)"
            " VALUES (?, 'st', 'complete', ?)",
            (call_id, db.iso(now - timedelta(days=days))),
        )
    conn.commit()


def _reference(conn: sqlite3.Connection, call_id: str) -> None:
    conn.execute(
        "INSERT INTO explanations VALUES (?, 'q1', 'a', 'grammar', 'x', 'ai', ?)",
        (f"T-{call_id}", call_id),
    )
    conn.commit()


def _call_ids(paths: DataPaths) -> set[str]:
    conn = db.connect(paths.db)
    try:
        return {r[0] for r in conn.execute("SELECT id FROM llm_calls")}
    finally:
        conn.close()


# --- R20.1 --------------------------------------------------------------------------------------


class Pair(BaseModel):
    a: int
    b: str


class StubPrompts:
    def render(self, task: str, profile: str, inputs: Mapping[str, Any]) -> RenderedPrompt:
        return RenderedPrompt.of("system", f"user {task}")


@pytest.mark.asyncio
async def test_r20_1_put_settings_writes_models_toml_and_next_call_uses_new_tag(
    make_ctx: Callable[..., AppContext], paths: DataPaths
) -> None:
    fake = FakeOllama([ChatScript(text='{"a": 1, "b": "x"}')])
    ctx = make_ctx(backend=None, base_url="http://fake-ollama", transport=fake.transport)
    ctx.client.prompts = StubPrompts()
    conn = db.connect(paths.db)
    try:
        thread = threads.create_thread(conn, "t")
        run = runs.create_run(
            conn,
            thread.id,
            "extract",
            m.ExtractInput(pages=[], existing_test_id=None, supersedes_attempt_id=None),
        )
        step_id = runs.insert_step(conn, run.id, "transcribe_page", "page 1", 1).id
    finally:
        conn.close()
    old = ctx.client.config.role("reasoning").model
    await ctx.client.call("reasoning", "t", {}, Pair, step_id=step_id)
    assert fake.requests[-1]["model"] == old

    async with client(ctx) as c:
        r = await c.put("/settings", json={"roles": {"reasoning": {"model": "qwen3:8b-new"}}})
        assert r.status_code == 200, r.text
        assert r.json()["roles"]["reasoning"]["model"] == "qwen3:8b-new"
        got = (await c.get("/settings")).json()
    assert got["data_folder"] == str(paths.root) and got["log_retention_days"] == 45
    assert load_models_config(paths).role("reasoning").model == "qwen3:8b-new"  # models.toml
    await ctx.client.call("reasoning", "t", {}, Pair, step_id=step_id)
    assert fake.requests[-1]["model"] == "qwen3:8b-new"
    ctx.close()


# --- R20.2 / R20.7 helpers ----------------------------------------------------------------------


def _table_counts(db_path: Path) -> dict[str, int]:
    conn = db.connect(db_path)
    try:
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                " AND name != 'schema_migrations'"
            )
        ]
        return {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}
    finally:
        conn.close()


def _file_hashes(files_dir: Path) -> dict[str, str]:
    return {
        p.relative_to(files_dir).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files_dir.rglob("*")
        if p.is_file()
    }


async def _seed_s1(c: httpx.AsyncClient) -> str:
    """Upload S1's stand-in pages, extract them (cassette replay) and wait for ``done``."""
    manifest = json.loads((S1 / "input.json").read_text(encoding="utf-8"))
    pages: list[Any] = []
    for p in manifest["pages"]:
        r = await c.post(
            "/files", params={"name": p["stand_in"]}, content=(S1 / p["stand_in"]).read_bytes()
        )
        assert r.status_code in (200, 201), r.text
        pages += r.json()["pages"]
    thread_id = (await c.post("/threads", json={"title": ""})).json()["thread_id"]
    body = {
        "kind": "extract",
        "input": {"pages": pages, "existing_test_id": None, "supersedes_attempt_id": None},
    }
    run = await c.post(f"/threads/{thread_id}/runs", json=body)
    assert run.status_code in (200, 201, 202), run.text
    run_id = run.json()["id"]
    async with asyncio.timeout(120):
        while True:
            status = (await c.get(f"/runs/{run_id}")).json()["run"]["status"]
            if status == "done":
                break
            assert status in ("queued", "running"), status
            await asyncio.sleep(0.2)
        # step 22.6.4: the extraction's key run follows (it fails here: the S1 replay has no
        # grade cassettes); wait until it has ended, so the thread no longer changes
        while any(a["run"]["thread_id"] == thread_id for a in (await c.get("/runs/active")).json()):
            await asyncio.sleep(0.2)
    return thread_id


# --- R20.2 --------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r20_2_backup_restore_same_rows_and_files(
    make_ctx: Callable[..., AppContext], paths: DataPaths, tmp_path: Path, api: Any
) -> None:
    ctx = make_ctx()
    async with api.serving(ctx) as live, live.client(headers=live.auth) as c:
        await _seed_s1(c)
        await c.post("/students", json={"full_name": "An"})
        r = await c.post("/maintenance/backup")
        assert r.status_code == 200, r.text
        backup = Path(r.json()["path"])
        assert backup.parent == paths.backups_dir and backup.suffix == ".zip"
        target = tmp_path / "restored"
        r = await c.post(
            "/maintenance/restore", json={"backup_path": str(backup), "new_folder": str(target)}
        )
        assert r.status_code == 200, r.text
    restored = DataPaths(Path(r.json()["data_folder"]))
    before, after = _table_counts(paths.db), _table_counts(restored.db)
    assert before["files"] > 0 and before["tests"] == 1
    assert after == before
    assert _file_hashes(restored.files_dir) == _file_hashes(paths.files_dir)
    assert _file_hashes(restored.files_dir)


# --- R20.3 --------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r20_3_clear_logs_7_days(
    make_ctx: Callable[..., AppContext], paths: DataPaths
) -> None:
    ctx = make_ctx()
    conn = db.connect(paths.db)
    _insert_calls(conn, datetime.now(UTC), {"old": 8, "old-ref": 30, "edge": 6.9, "new": 1})
    _reference(conn, "old-ref")
    conn.close()
    async with client(ctx) as c:
        r = await c.post("/maintenance/clear-logs", json={"older_than_days": 7})
        assert r.json() == {"deleted": 1}
    assert _call_ids(paths) == {"old-ref", "edge", "new"}
    ctx.close()


# --- R20.6 / R20.8 ------------------------------------------------------------------------------


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.t = start
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self.t

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += timedelta(seconds=seconds)
        await asyncio.sleep(0)


async def _until(cond: Callable[[], bool]) -> None:
    async with asyncio.timeout(10):
        while not cond():
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_r20_6_startup_run_logs_a_line(
    make_ctx: Callable[..., AppContext], api: Any, caplog: pytest.LogCaptureFixture
) -> None:
    ctx = make_ctx(maintenance=True)
    caplog.set_level(logging.INFO, logger="etach.maintenance")
    async with api.serving(ctx):
        lines = [r.getMessage() for r in caplog.records if r.name == "etach.maintenance"]
        assert len(lines) == 1 and lines[0].startswith("maintenance: swept 0 files")
        assert len(ctx.extra["maintenance.scheduler"].reports) == 1


@pytest.mark.asyncio
async def test_r20_6_sweep_and_purge_every_24h_fake_clock(
    make_ctx: Callable[..., AppContext], paths: DataPaths
) -> None:
    ctx = make_ctx()
    t0 = datetime.now(UTC) + timedelta(minutes=1)
    conn = db.connect(paths.db)
    try:
        file_id = FileStore(conn, paths).put(b"never referenced", "txt", kind="text")
        abs_path = FileStore(conn, paths).abspath(file_id)
        # checkpoint rows of a done run and a running one (the LangGraph tables, minimal)
        conn.execute("CREATE TABLE checkpoints (thread_id TEXT)")
        conn.execute("CREATE TABLE writes (thread_id TEXT)")
        thread = threads.create_thread(conn, "t")
        empty = m.ExtractInput(pages=[], existing_test_id=None, supersedes_attempt_id=None)
        done = runs.create_run(conn, thread.id, "extract", empty)
        live = runs.create_run(conn, thread.id, "extract", empty)
        conn.execute("UPDATE runs SET status = 'done' WHERE id = ?", (done.id,))
        conn.execute("UPDATE runs SET status = 'running' WHERE id = ?", (live.id,))
        for table in ("checkpoints", "writes"):
            conn.executemany(
                f"INSERT INTO {table} VALUES (?)", [(done.id,), (done.id,), (live.id,)]
            )
        conn.commit()
    finally:
        conn.close()

    clock = FakeClock(t0)
    sched = MaintenanceScheduler(ctx, now=clock.now, sleep=clock.sleep)
    await sched.start()
    assert len(sched.reports) == 1  # the startup run, before start() returns
    first = sched.reports[0]
    assert first.at == t0 and first.files_deleted == 0 and abs_path.exists()  # 24 h grace
    assert first.checkpoint_rows_purged == 4
    await _until(lambda: len(sched.reports) >= 3)
    await sched.aclose()
    assert [r.at for r in sched.reports[:3]] == [
        t0,
        t0 + timedelta(hours=24),
        t0 + timedelta(hours=48),
    ]
    assert clock.sleeps[:2] == [86400.0, 86400.0]
    second = sched.reports[1]
    assert second.files_deleted == 1 and not abs_path.exists()
    assert second.checkpoint_rows_purged == 0
    check = db.connect(paths.db)
    try:
        assert check.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 1
        assert check.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0
    finally:
        check.close()
    ctx.close()


@pytest.mark.asyncio
async def test_r20_8_retention_default_45_days_at_startup(
    make_ctx: Callable[..., AppContext], paths: DataPaths, api: Any
) -> None:
    conn = db.connect(paths.db)
    _insert_calls(conn, datetime.now(UTC), {"old": 46, "old-ref": 90, "young": 44, "today": 0})
    _reference(conn, "old-ref")
    conn.close()
    ctx = make_ctx(maintenance=True)
    async with api.serving(ctx):
        assert ctx.extra["maintenance.scheduler"].reports[0].llm_calls_deleted == 1
    assert _call_ids(paths) == {"old-ref", "young", "today"}


@pytest.mark.asyncio
async def test_r20_8_retention_fake_clock_and_setting(
    make_ctx: Callable[..., AppContext], paths: DataPaths
) -> None:
    ctx = make_ctx()
    t0 = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
    conn = db.connect(paths.db)
    _insert_calls(conn, t0, {"a": 44.5, "b": 45.5, "ref": 100, "c": 20})
    _reference(conn, "ref")
    conn.close()
    clock = FakeClock(t0)
    sched = MaintenanceScheduler(ctx, now=clock.now, sleep=clock.sleep)
    await sched.start()
    assert sched.reports[0].retention_days == 45
    assert _call_ids(paths) == {"a", "ref", "c"}
    await _until(lambda: len(sched.reports) >= 2)  # a day later "a" is 45.5 days old
    await sched.aclose()
    assert _call_ids(paths) == {"ref", "c"}
    # a shorter retention from settings.json applies to the next run
    async with client(ctx) as c:
        assert (await c.put("/settings", json={"log_retention_days": 7})).status_code == 200
    report = run_maintenance(ctx, t0)
    assert report.retention_days == 7 and _call_ids(paths) == {"ref"}
    ctx.close()


# --- R20.5 sidecar side: the fake pull hook ------------------------------------------------------


@pytest.mark.asyncio
async def test_fake_pull_env_hook_streams_progress(
    make_ctx: Callable[..., AppContext], monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = make_ctx()
    events: list[dict[str, Any]] = []
    ctx.events.add_listener(events.append)
    async with client(ctx) as c:
        r = await c.post("/settings/models/pull")
        await asyncio.wait_for(asyncio.gather(*set(ctx.extra["settings.pull_tasks"])), 10)
    models = r.json()["models"]
    progress = [e for e in events if e["type"] == "models.pull_progress"]
    # --replay without the hook never reaches for a real Ollama
    assert [p["status"] for p in progress] == ["error: no Ollama in replay mode"] * len(models)

    monkeypatch.setenv(FAKE_PULL_ENV, "0")
    events.clear()
    async with client(ctx) as c:
        await c.post("/settings/models/pull")
        await asyncio.wait_for(asyncio.gather(*set(ctx.extra["settings.pull_tasks"])), 10)
    progress = [e for e in events if e["type"] == "models.pull_progress"]
    assert len(progress) == 4 * len(models)
    for model in models:
        mine = [p for p in progress if p["model"] == model]
        assert [p["completed"] for p in mine] == [None, 40, 100, None]
        assert mine[-1]["status"] == "success"
    ctx.close()


# --- R20.7 --------------------------------------------------------------------------------------


def _all_text_values(db_path: Path) -> list[str]:
    conn = db.connect(db_path)
    try:
        out: list[str] = []
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for t in tables:
            for row in conn.execute(f'SELECT * FROM "{t}"'):
                out += [
                    v if isinstance(v, str) else v.decode("latin-1")
                    for v in row
                    if isinstance(v, str | bytes)
                ]
        return out
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_r20_7_copy_the_app_folder_and_start_from_there(tmp_path: Path, api: Any) -> None:
    def ctx_for(app_folder: Path) -> AppContext:
        p = DataPaths((app_folder / "data").resolve()).ensure()
        db.open_database(p.db).close()
        vision_reader(p.root)  # the s1 cassettes were recorded with the vision reader
        c = build_context(p, backend=ReplayBackend.from_dir(S1), power=FakePower())
        c.extra[ENABLED_KEY] = False
        return c

    first = tmp_path / "ETACH"
    ctx1 = ctx_for(first)
    async with api.serving(ctx1) as live, live.client(headers=live.auth) as c:
        await _seed_s1(c)
        before = {
            "threads": (await c.get("/threads")).json(),
            "tests": (await c.get("/tests")).json(),
        }
        test_id = before["tests"][0]["id"]
        before["test"] = (await c.get(f"/tests/{test_id}")).json()
        rows = db.connect(first / "data" / "app.db")
        try:
            file_ids = [r[0] for r in rows.execute("SELECT id FROM files ORDER BY id")]
        finally:
            rows.close()
        assert file_ids
        before["files"] = [(await c.get(f"/files/{f}")).content for f in file_ids]

    # no absolute path anywhere in the database
    values = _all_text_values(first / "data" / "app.db")
    roots = {str(tmp_path), str(tmp_path).replace("\\", "/"), str(first), first.as_posix()}
    assert not [v for v in values if any(r.lower() in v.lower() for r in roots)]
    assert not [v for v in values if len(v) > 2 and v[1:3] in (":\\", ":/") and v[0].isalpha()]

    moved = tmp_path / "Moved" / "ETACH"
    shutil.copytree(first, moved)
    shutil.rmtree(first)  # the old location is gone: nothing may still point at it
    ctx2 = ctx_for(moved)
    async with api.serving(ctx2) as live, live.client(headers=live.auth) as c:
        after = {
            "threads": (await c.get("/threads")).json(),
            "tests": (await c.get("/tests")).json(),
        }
        after["test"] = (await c.get(f"/tests/{test_id}")).json()
        after["files"] = [(await c.get(f"/files/{f}")).content for f in file_ids]
    assert after == before
    assert all(after["files"])
