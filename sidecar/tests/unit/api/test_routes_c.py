"""Step 12 part C routes: students, review (R12.6), system (R12.7), settings, maintenance."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import tomllib
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from support.fake_ollama import FakeOllama
from unit.domain import test_review as appendix_e

from etach import __version__
from etach.api.app import create_app
from etach.api.deps import AppContext
from etach.appdir import DataPaths, settings_json_path
from etach.domain import models as m
from etach.llm.config import parse_models_config
from etach.runtime.power import FakePower
from etach.store import db
from etach.store.repos import attempts, regrade, review, runs

# --- harness: the ASGI app without its lifespan (the run manager is not started, so the
# --- follow-up runs stay ``queued`` as in R10.1); poke() and the events are recorded.


class Recorder:
    def __init__(self, ctx: AppContext) -> None:
        self.events: list[dict[str, Any]] = []
        self.pokes = 0
        ctx.events.add_listener(self.events.append)

        async def poke() -> list[str]:
            self.pokes += 1
            return []

        ctx.manager.poke = poke  # type: ignore[method-assign]

    def of(self, type: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["type"] == type]


@pytest.fixture
def ctx(make_ctx: Callable[..., AppContext]) -> Iterator[AppContext]:
    c = make_ctx()
    yield c
    c.close()


@asynccontextmanager
async def client(ctx: AppContext) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(ctx))
    headers = {"Authorization": f"Bearer {ctx.token}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=headers) as c:
        yield c


@pytest.fixture
def conn(ctx: AppContext) -> Iterator[sqlite3.Connection]:
    c = db.connect(ctx.paths.db)
    yield c
    c.close()


# --- students -----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_students_create_and_search(ctx: AppContext) -> None:
    async with client(ctx) as c:
        r = await c.post("/students", json={"full_name": "  Nguyễn  Văn An ", "class_name": "6A"})
        assert r.status_code == 201
        an = r.json()
        assert an["full_name"] == "Nguyễn Văn An"
        assert an["name_search"] == "nguyen van an"
        await c.post("/students", json={"full_name": "Trần Thị Bình", "grade": 7})
        await c.post("/students", json={"full_name": "Văn Nguyên"})
        prefix = (await c.get("/students", params={"q": "NGUYEN"})).json()
        assert [s["full_name"] for s in prefix] == ["Nguyễn Văn An", "Văn Nguyên"]  # prefix first
        assert [
            s["full_name"] for s in (await c.get("/students", params={"q": "binh"})).json()
        ] == ["Trần Thị Bình"]
        assert len((await c.get("/students")).json()) == 3
        assert (await c.get("/students", params={"q": "%"})).json() == []
        assert (await c.post("/students", json={"full_name": "  "})).status_code == 422


# --- review: R12.6 ------------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("graded", [True, False], ids=["graded", "ungraded"])
@pytest.mark.parametrize(
    "row", appendix_e.ROWS, ids=[r.label.split(" |")[0] for r in appendix_e.ROWS]
)
async def test_r12_6_appendix_e_row_over_http(
    ctx: AppContext, conn: sqlite3.Connection, row: Any, graded: bool
) -> None:
    """R12.6: each Appendix E row through ``POST /review/{id}/resolve`` gives R10.1's
    post-conditions and emits ``review.changed``."""
    rec = Recorder(ctx)
    w = appendix_e._world(conn, graded)
    item_id = (row.maker or appendix_e.MAKERS[row.kind])(conn, w)
    versions = {a.id: a.version for a in (w.a1, w.a2, w.a3)}

    async with client(ctx) as c:
        r = await c.post(
            f"/review/{item_id}/resolve", json={"action": row.action, "value": row.value}
        )
    assert r.status_code == 200, r.text
    body = r.json()

    item = review.get_item(conn, item_id)
    assert item is not None
    assert body["item"]["id"] == item_id and body["item"]["status"] == item.status
    assert item.status == ("accepted" if row.action == "accept" else "fixed")
    assert item.resolution == {"action": row.action, "value": row.value}
    assert item.resolved_at is not None

    queued = [q.id for q in runs.list_runs(conn, status="queued")]
    assert sorted(body["followup_run_ids"]) == sorted(queued)
    assert item.followup_run_id == (body["followup_run_ids"][0] if queued else None)
    assert rec.pokes == (1 if queued else 0)
    if row.reason == "key_verified":  # data-model v1.20: deferred to POST /tests/{id}/regrade
        assert queued == []
        assert item.test_id is not None
        assert regrade.is_pending(conn, item.test_id) is graded
        async with client(ctx) as c:
            r = await c.post(f"/tests/{item.test_id}/regrade")
        assert r.status_code == 200, r.text
        assert len(r.json()["run_ids"]) == (row.runs_graded if graded else 0)
        assert not regrade.is_pending(conn, item.test_id)
    grade = appendix_e._grade_runs(conn)
    assert len(grade) == (row.runs_graded if graded else 0)
    for run in grade:
        assert isinstance(run.input, m.GradeInput)
        assert run.input.reason == row.reason

    bumped = {"a1": w.a1.id, "a3": w.a3.id}.get(row.version_attempt or "")
    for att_id, before in versions.items():
        att = attempts.get_attempt(conn, att_id)
        assert att is not None
        assert att.version == before + (1 if att_id == bumped else 0)
    row.check(conn, w)

    changed = rec.of("review.changed")
    assert changed == [{"type": "review.changed", "open": review.count_open(conn)}]


@pytest.mark.asyncio
async def test_review_queue_count_and_errors(ctx: AppContext, conn: sqlite3.Connection) -> None:
    rec = Recorder(ctx)
    w = appendix_e._world(conn, False)
    base = review.count_open(conn)  # the world's own items
    first = appendix_e.MAKERS["uncertain_answer"](conn, w)
    second = appendix_e.MAKERS["unknown_occasion"](conn, w)
    async with client(ctx) as c:
        assert (await c.get("/review/count")).json() == {"open": base + 2}
        queue = (await c.get("/review", params={"status": "open"})).json()
        assert [i["id"] for i in queue][-2:] == [first, second]  # oldest first
        assert [i["created_at"] for i in queue] == sorted(i["created_at"] for i in queue)
        assert {"kind", "proposal", "created_at", "attempt_id", "test_id"} <= set(queue[0])

        r = await c.post(f"/review/{first}/resolve", json={"action": "skip"})
        assert r.status_code == 200
        assert rec.of("review.changed")[-1]["open"] == base + 1
        assert (await c.get("/review/count")).json() == {"open": base + 1}
        assert (
            await c.post(f"/review/{first}/resolve", json={"action": "skip"})
        ).status_code == 409
        assert (
            await c.post(f"/review/{second}/resolve", json={"action": "fix", "value": None})
        ).status_code == 422
        assert (await c.post("/review/nope/resolve", json={"action": "skip"})).status_code == 404
        assert (await c.post(f"/review/{second}/resolve", json={"action": "x"})).status_code == 422
        assert [i["id"] for i in (await c.get("/review", params={"status": "skipped"})).json()] == [
            first
        ]
    assert len(rec.of("review.changed")) == 1


# --- system: R12.7 ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r12_7_system_status_from_fakes(ctx: AppContext) -> None:
    # two different tags (the defaults now share qwen3.5:4b, D4)
    ctx.client.config = parse_models_config(
        {"roles": {"vision": {"model": "numind/nuextract3:Q6_K"}}}
    )
    roles = ctx.client.config.roles
    vision, reasoning = roles["vision"].model, roles["reasoning"].model
    ctx.extra["ollama_transport"] = FakeOllama(version="0.13.1", tags=[vision]).transport
    ctx.extra["other_ollama_transport"] = FakeOllama(loaded=["llama3:8b"]).transport
    assert isinstance(ctx.power, FakePower)
    ctx.power.source = "battery"
    ctx.power.set_keep_awake(True)
    async with client(ctx) as c:
        r = await c.get("/system/status")
    assert r.status_code == 200
    assert r.json() == {
        "sidecar_version": __version__,  # step 21 (R21.2)
        "replay": ctx.replay,  # step 21 (the first-run screen)
        "ollama_version": "0.13.1",
        "ollama_status": "missing_model",
        "models_present": [vision],
        "missing_models": [reasoning, roles["ocr"].model],  # glm-ocr is a default (R22.5.7.7)
        "other_ollama_loaded": True,
        "power_source": "battery",
        "keep_awake": True,
    }


@pytest.mark.asyncio
async def test_system_status_unreachable_is_not_500(ctx: AppContext) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    rec = Recorder(ctx)
    ctx.extra["ollama_transport"] = httpx.MockTransport(refuse)
    ctx.extra["other_ollama_transport"] = httpx.MockTransport(refuse)
    async with client(ctx) as c:
        r = await c.get("/system/status")
        assert r.status_code == 200
        assert r.json() == {
            "sidecar_version": __version__,  # step 21
            "replay": ctx.replay,  # step 21
            "ollama_version": None,
            "ollama_status": "unreachable",
            "models_present": None,
            "missing_models": None,
            "other_ollama_loaded": False,
            "power_source": "ac",
            "keep_awake": False,
        }
        assert rec.of("system.changed") == []  # the first status is the baseline
        tags = [r.model for r in ctx.client.config.roles.values()]
        ctx.extra["ollama_transport"] = FakeOllama(tags=tags).transport
        assert (await c.get("/system/status")).json()["ollama_status"] == "ok"
        await c.get("/system/status")
    changed = rec.of("system.changed")
    assert len(changed) == 1 and changed[0]["ollama_status"] == "ok"


@pytest.mark.asyncio
async def test_system_status_in_replay_without_ollama(ctx: AppContext) -> None:
    async with client(ctx) as c:
        r = await c.get("/system/status")
    assert r.status_code == 200
    assert r.json()["ollama_status"] == "unreachable"


# --- settings -----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_settings_read_and_write(ctx: AppContext) -> None:
    settings_json = ctx.paths.root / "settings.json"  # --data given explicitly
    assert not settings_json.exists()
    async with client(ctx) as c:
        got = (await c.get("/settings")).json()
        assert got["data_folder"] == str(ctx.paths.root)
        assert got["log_retention_days"] == 45
        assert set(got["roles"]) == {"vision", "reasoning", "grading_check", "extraction_check"}

        r = await c.put(
            "/settings",
            json={
                "roles": {"reasoning": {"model": "qwen3:8b", "options": {"num_ctx": 8192}}},
                "log_retention_days": 30,
            },
        )
        assert r.status_code == 200, r.text
        new = r.json()
        assert new["roles"]["reasoning"]["model"] == "qwen3:8b"
        assert new["roles"]["reasoning"]["options"]["num_ctx"] == 8192
        assert new["roles"]["vision"] == got["roles"]["vision"]
        assert new["log_retention_days"] == 30
        # the running client uses the new tag on its next call (R20.1 checks the call itself)
        assert ctx.client.config.role("reasoning").model == "qwen3:8b"
        on_disk = tomllib.loads(ctx.paths.models_toml.read_text(encoding="utf-8"))
        assert on_disk["roles"]["reasoning"]["model"] == "qwen3:8b"
        assert json.loads(settings_json.read_text(encoding="utf-8")) == {"log_retention_days": 30}
        assert (await c.get("/settings")).json() == new

        bad = {"roles": {"vision": {"model": ""}}}
        assert (await c.put("/settings", json=bad)).status_code == 422
        blank = {"roles": {"vision": {"model": "   "}}}
        assert (await c.put("/settings", json=blank)).status_code == 422
        unknown = {"roles": {"painter": {"model": "x"}}}
        assert (await c.put("/settings", json=unknown)).status_code == 422
        assert (await c.put("/settings", json={"log_retention_days": 0})).status_code == 422
        assert (await c.get("/settings")).json() == new
    assert ctx.extra["settings_path"] == settings_json
    assert not (ctx.paths.root.parent / "settings.json").exists()


def test_settings_json_path_layouts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The app layout keeps settings.json in the app folder; an explicit --data keeps it in the
    data folder (never next to a dev data folder in the repo)."""
    app = tmp_path / "ETACH"
    layout = DataPaths((app / "data").resolve())
    assert settings_json_path(layout, explicit_data=False) == layout.root.parent / "settings.json"
    assert settings_json_path(layout, explicit_data=True) == layout.root / "settings.json"
    dev = DataPaths((tmp_path / ".devdata").resolve())
    assert settings_json_path(dev, explicit_data=False) == dev.root / "settings.json"
    # inferred: a development (not frozen) run always counts as explicit --data
    assert settings_json_path(layout) == layout.root / "settings.json"
    # inferred: a frozen sidecar with its own <app>/data is the app layout
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(app / "etach-sidecar.exe"))
    assert settings_json_path(layout) == app.resolve() / "settings.json"
    assert settings_json_path(dev) == dev.root / "settings.json"


@pytest.mark.asyncio
async def test_settings_use_the_path_ctx_carries(ctx: AppContext, tmp_path: Path) -> None:
    app_layout = tmp_path / "app-settings.json"
    ctx.extra["settings_path"] = app_layout
    async with client(ctx) as c:
        assert (await c.put("/settings", json={"log_retention_days": 7})).status_code == 200
        assert (await c.get("/settings")).json()["log_retention_days"] == 7
    assert json.loads(app_layout.read_text(encoding="utf-8")) == {"log_retention_days": 7}
    assert not (ctx.paths.root / "settings.json").exists()


@pytest.mark.asyncio
async def test_models_pull_streams_progress(ctx: AppContext) -> None:
    fake = FakeOllama()
    pulled: list[str] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/pull":
            model = json.loads(request.content)["model"]
            pulled.append(model)
            lines = [
                {"status": "pulling manifest"},
                {"status": "downloading", "digest": "sha256:1", "total": 100, "completed": 40},
                {"status": "downloading", "digest": "sha256:1", "total": 100, "completed": 100},
                {"status": "success"},
            ]
            body = "".join(json.dumps(x) + "\n" for x in lines).encode()
            return httpx.Response(200, content=body)
        return await fake._handle(request)

    ctx.extra["ollama_transport"] = httpx.MockTransport(handle)
    rec = Recorder(ctx)
    models = list(dict.fromkeys(r.model for r in ctx.client.config.roles.values()))
    async with client(ctx) as c:
        r = await c.post("/settings/models/pull")
        assert r.status_code == 202
        assert r.json() == {"models": models}
        tasks = set(ctx.extra["settings.pull_tasks"])
        await asyncio.wait_for(asyncio.gather(*tasks), 10)
    assert pulled == models
    progress = rec.of("models.pull_progress")
    assert len(progress) == 4 * len(models)
    assert progress[1] == {
        "type": "models.pull_progress",
        "model": models[0],
        "status": "downloading",
        "completed": 40,
        "total": 100,
    }
    assert [p["status"] for p in progress if p["model"] == models[-1]][-1] == "success"


# --- maintenance --------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backup_and_restore(ctx: AppContext, tmp_path: Path) -> None:
    async with client(ctx) as c:
        await c.post("/students", json={"full_name": "An"})
        r = await c.post("/maintenance/backup")
        assert r.status_code == 200
        path = Path(r.json()["path"])
        assert path.parent == ctx.paths.backups_dir and path.suffix == ".zip" and path.is_file()

        target = tmp_path / "restored"
        r = await c.post(
            "/maintenance/restore", json={"backup_path": str(path), "new_folder": str(target)}
        )
        assert r.status_code == 200, r.text
        assert Path(r.json()["data_folder"]) == target.resolve()
        restored = db.connect(target / "app.db")
        try:
            assert restored.execute("SELECT full_name FROM students").fetchall()[0][0] == "An"
        finally:
            restored.close()
        again = await c.post(
            "/maintenance/restore", json={"backup_path": str(path), "new_folder": str(target)}
        )
        assert again.status_code == 409  # not empty


@pytest.mark.asyncio
async def test_clear_logs_keeps_referenced_and_recent(
    ctx: AppContext, conn: sqlite3.Connection
) -> None:
    now = datetime.now(UTC)
    conn.execute("PRAGMA foreign_keys = OFF")
    for call_id, age in (("old", 60), ("old-ref", 60), ("new", 1)):
        conn.execute(
            "INSERT INTO llm_calls (id, step_id, status, created_at)"
            " VALUES (?, 'st', 'complete', ?)",
            (call_id, db.iso(now - timedelta(days=age))),
        )
    conn.execute(
        "INSERT INTO explanations VALUES ('T-0001', 'q1', 'a', 'grammar', 'x', 'ai', 'old-ref')"
    )
    conn.commit()
    async with client(ctx) as c:
        r = await c.post("/maintenance/clear-logs", json={"older_than_days": 45})
        assert r.json() == {"deleted": 1}
        left = {row[0] for row in conn.execute("SELECT id FROM llm_calls")}
        assert left == {"old-ref", "new"}
        assert (await c.post("/maintenance/clear-logs", json={"older_than_days": 0})).json() == {
            "deleted": 1
        }
        bad = await c.post("/maintenance/clear-logs", json={"older_than_days": -1})
        assert bad.status_code == 422
