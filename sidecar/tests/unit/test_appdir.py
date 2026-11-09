"""``ETACH_APP_DIR`` (plan step 14): the dev shell names the app folder, so the sidecar and the
shell share ``<app>\\data`` and ``<app>\\settings.json`` (PRD §11, data-model §5.5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from etach import appdir


@pytest.fixture(autouse=True)
def _not_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delenv(appdir.APP_DIR_ENV, raising=False)


def test_env_names_the_app_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = tmp_path / "EtachApp"
    monkeypatch.setenv(appdir.APP_DIR_ENV, str(app))
    assert appdir.default_app_folder() == app.resolve()
    paths = appdir.resolve_data_dir()
    assert paths.root == (app / "data").resolve()
    # the app layout: settings.json sits in the app folder, next to data\
    assert appdir.settings_json_path(paths) == app.resolve() / "settings.json"


def test_env_with_explicit_other_data_keeps_settings_in_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(appdir.APP_DIR_ENV, str(tmp_path / "EtachApp"))
    dev = appdir.resolve_data_dir(tmp_path / ".devdata")
    assert dev.root == (tmp_path / ".devdata").resolve()
    assert appdir.settings_json_path(dev) == dev.root / "settings.json"


def test_frozen_ignored_when_env_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "exe" / "etach-sidecar.exe"))
    monkeypatch.setenv(appdir.APP_DIR_ENV, str(tmp_path / "EtachApp"))
    assert appdir.default_app_folder() == (tmp_path / "EtachApp").resolve()


@pytest.mark.parametrize("var", ["APPDATA", "LOCALAPPDATA"])
def test_env_in_appdata_is_refused(monkeypatch: pytest.MonkeyPatch, var: str) -> None:
    fake = Path("Z:/etach-fake-appdata-root")
    monkeypatch.setenv(var, str(fake))
    monkeypatch.setenv(appdir.APP_DIR_ENV, str(fake / "ETACH"))
    with pytest.raises(appdir.AppDirError, match=f"app folder.*{var}"):
        appdir.default_app_folder()
    with pytest.raises(appdir.AppDirError, match=var):
        appdir.resolve_data_dir()


def test_no_env_is_unchanged(tmp_path: Path) -> None:
    with pytest.raises(appdir.AppDirError, match="--data"):
        appdir.default_app_folder()
    with pytest.raises(appdir.AppDirError, match="--data"):
        appdir.resolve_data_dir()
    explicit = appdir.resolve_data_dir(tmp_path / "data")
    # a development run with --data keeps settings.json in the data folder
    assert appdir.settings_json_path(explicit) == explicit.root / "settings.json"


def test_empty_env_counts_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(appdir.APP_DIR_ENV, "")
    with pytest.raises(appdir.AppDirError, match="--data"):
        appdir.default_app_folder()


def test_exports_dir_follows_the_settings_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r"""Step 22.1.6: ``<app>\exports`` next to ``data\``; ``<dir>\exports`` with ``--data``."""
    app = tmp_path / "EtachApp"
    monkeypatch.setenv(appdir.APP_DIR_ENV, str(app))
    assert appdir.exports_dir(appdir.resolve_data_dir()) == app.resolve() / "exports"
    dev = appdir.resolve_data_dir(tmp_path / ".devdata")
    assert appdir.exports_dir(dev) == dev.root / "exports"


def test_exports_dir_in_appdata_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Path("Z:/etach-fake-appdata-root")
    monkeypatch.setenv("APPDATA", str(fake))
    monkeypatch.delenv(appdir.APP_DIR_ENV, raising=False)
    paths = appdir.DataPaths((fake / "data").resolve())
    with pytest.raises(appdir.AppDirError, match="exports folder"):
        appdir.exports_dir(paths, explicit_data=True)
