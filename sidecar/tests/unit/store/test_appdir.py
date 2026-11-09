"""etach.appdir: data folder resolution (PRD §11, data-model §5.5).

(Kept under tests/unit/store/ because step 2's write scope for tests is that folder.)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from etach import appdir


def test_explicit_data_dir(tmp_path: Path) -> None:
    paths = appdir.resolve_data_dir(tmp_path / ".devdata")
    assert paths.root == (tmp_path / ".devdata").resolve()
    assert paths.db.name == "app.db" and paths.db.parent == paths.root
    assert paths.files_dir == paths.root / "files"
    assert paths.backups_dir == paths.root / "backups"
    assert paths.models_toml == paths.root / "models.toml"
    assert not paths.root.exists()  # resolving never writes
    paths.ensure()
    assert paths.files_dir.is_dir() and paths.backups_dir.is_dir()


def test_app_folder_data(tmp_path: Path) -> None:
    paths = appdir.resolve_data_dir(app_folder=tmp_path / "ETACH")
    assert paths.root == (tmp_path / "ETACH" / "data").resolve()


def test_frozen_app_folder_is_the_exe_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "etach-sidecar" / "etach-sidecar.exe"))
    assert appdir.default_app_folder() == (tmp_path / "etach-sidecar").resolve()


def test_development_run_needs_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    with pytest.raises(appdir.AppDirError, match="--data"):
        appdir.resolve_data_dir()


@pytest.mark.parametrize("var", ["APPDATA", "LOCALAPPDATA"])
def test_appdata_is_refused(monkeypatch: pytest.MonkeyPatch, var: str) -> None:
    fake = Path("Z:/etach-fake-appdata-root")
    monkeypatch.setenv(var, str(fake))
    with pytest.raises(appdir.AppDirError, match=var):
        appdir.resolve_data_dir(fake / "ETACH" / "data")
