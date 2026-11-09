"""Step 21: a relative restore path resolves against the app folder, never the sidecar's working
folder (structure §7, the step 20 verifier's note); ``/system/status`` carries the sidecar's
version and the replay flag (R21.2, the first-run screen)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from etach import __version__
from etach.api.deps import AppContext
from etach.appdir import APP_DIR_ENV, DataPaths


async def _backup(c: Any) -> Path:
    r = await c.post("/maintenance/backup")
    assert r.status_code == 200, r.text
    return Path(r.json()["path"])


@pytest.mark.asyncio
async def test_relative_restore_resolves_against_the_app_folder(
    make_ctx: Callable[..., AppContext],
    paths: DataPaths,
    tmp_path: Path,
    api: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The app layout: ETACH_APP_DIR=<tmp>, data folder <tmp>/data (the shell's and the frozen
    # sidecar's layout). The working folder is somewhere else entirely.
    app_folder = paths.root.parent
    monkeypatch.setenv(APP_DIR_ENV, str(app_folder))
    elsewhere = tmp_path / "cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    ctx = make_ctx()
    async with api.serving(ctx) as live, live.client(headers=live.auth) as c:
        backup = await _backup(c)
        relative_backup = backup.relative_to(app_folder).as_posix()  # data/backups/<stamp>.zip
        r = await c.post(
            "/maintenance/restore",
            json={"backup_path": relative_backup, "new_folder": "restored"},
        )
        assert r.status_code == 200, r.text
    restored = Path(r.json()["data_folder"])
    assert restored == (app_folder / "restored").resolve()
    assert DataPaths(restored).db.is_file()
    assert not (elsewhere / "restored").exists()


@pytest.mark.asyncio
async def test_relative_restore_with_explicit_data_resolves_against_the_data_folder(
    make_ctx: Callable[..., AppContext],
    paths: DataPaths,
    tmp_path: Path,
    api: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `--data <dir>` (development): no app folder, so the data folder is the base.
    monkeypatch.delenv(APP_DIR_ENV, raising=False)
    elsewhere = tmp_path / "cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    ctx = make_ctx()
    async with api.serving(ctx) as live, live.client(headers=live.auth) as c:
        backup = await _backup(c)
        r = await c.post(
            "/maintenance/restore",
            json={"backup_path": str(backup), "new_folder": "restored"},
        )
        assert r.status_code == 200, r.text
    assert Path(r.json()["data_folder"]) == (paths.root / "restored").resolve()
    assert not (elsewhere / "restored").exists()


@pytest.mark.asyncio
async def test_absolute_restore_path_is_unchanged(
    make_ctx: Callable[..., AppContext], tmp_path: Path, api: Any
) -> None:
    ctx = make_ctx()
    target = tmp_path / "abs-target"
    async with api.serving(ctx) as live, live.client(headers=live.auth) as c:
        backup = await _backup(c)
        r = await c.post(
            "/maintenance/restore", json={"backup_path": str(backup), "new_folder": str(target)}
        )
        assert r.status_code == 200, r.text
    assert Path(r.json()["data_folder"]) == target.resolve()


@pytest.mark.asyncio
async def test_system_status_carries_the_sidecar_version_and_replay(
    make_ctx: Callable[..., AppContext], api: Any
) -> None:
    ctx = make_ctx()
    async with api.serving(ctx) as live, live.client(headers=live.auth) as c:
        r = await c.get("/system/status")
        assert r.status_code == 200, r.text
    body = r.json()
    assert body["sidecar_version"] == __version__
    assert body["replay"] is True  # make_ctx replays the S1 cassettes
