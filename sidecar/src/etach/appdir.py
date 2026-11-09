"""The app folder and the data folder inside it (PRD §11, data-model §5.5).

Everything the app writes lives in one app folder (default ``D:\\ETACH``); the data
folder is ``<app folder>\\data`` unless ``--data <dir>`` names another one (development uses
``etach serve --data <repo>\\.devdata``). Nothing resolves into AppData: there is no platform
default, and a path inside ``%APPDATA%`` or ``%LOCALAPPDATA%`` is refused (the system temp folder,
which tests use, is the one exception).

``ETACH_APP_DIR=<dir>`` names the app folder of a development run (plan step 14): the Tauri shell
sets it for the dev sidecar, so ``etach serve`` without ``--data`` uses the app layout
(``<dir>\\data`` and ``<dir>\\settings.json``), the same files the shell reads.

Later steps extend this module (models folder, webview folder).
"""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "APP_DIR_ENV",
    "DATA_DIR_NAME",
    "AppDirError",
    "DataPaths",
    "default_app_folder",
    "exports_dir",
    "resolve_data_dir",
    "settings_json_path",
]

DATA_DIR_NAME = "data"
EXPORTS_DIR_NAME = "exports"
APP_DIR_ENV = "ETACH_APP_DIR"


class AppDirError(RuntimeError):
    """The data folder cannot be resolved, or it would resolve into AppData."""


@dataclass(frozen=True)
class DataPaths:
    """The paths inside one data folder. ``root`` is absolute."""

    root: Path

    @property
    def db(self) -> Path:
        return self.root / "app.db"

    @property
    def files_dir(self) -> Path:
        return self.root / "files"

    @property
    def backups_dir(self) -> Path:
        return self.root / "backups"

    @property
    def models_toml(self) -> Path:
        return self.root / "models.toml"

    def ensure(self) -> DataPaths:
        """Create the data folder and its sub-folders if they are missing."""
        for folder in (self.root, self.files_dir, self.backups_dir):
            folder.mkdir(parents=True, exist_ok=True)
        return self


def default_app_folder() -> Path:
    """The app folder: ``ETACH_APP_DIR`` if set (the dev shell sets it), else, for an installed
    (frozen) sidecar, the folder holding its executable.

    A development run (not frozen) without ``ETACH_APP_DIR`` has no app folder; it must pass
    ``--data``. An app folder inside AppData is refused.
    """
    env = os.environ.get(APP_DIR_ENV)
    if env:
        folder = Path(env).resolve()
        _refuse_appdata(folder, what="the app folder")
        return folder
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    raise AppDirError("not an installed app: pass --data <dir> (development uses .devdata)")


def resolve_data_dir(data: Path | str | None = None, app_folder: Path | None = None) -> DataPaths:
    """The data folder: ``data`` if given (relative paths resolve against the current folder),
    else ``<app_folder>/data`` (``app_folder`` defaults to :func:`default_app_folder`)."""
    if data is not None:
        root = Path(data)
    else:
        root = (app_folder if app_folder is not None else default_app_folder()) / DATA_DIR_NAME
    root = root.resolve()
    _refuse_appdata(root)
    return DataPaths(root)


def _is_within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _refuse_appdata(path: Path, *, what: str = "the data folder") -> None:
    temp = Path(tempfile.gettempdir()).resolve()
    if _is_within(path, temp):
        return
    for var in ("APPDATA", "LOCALAPPDATA"):
        value = os.environ.get(var)
        if value and _is_within(path, Path(value).resolve()):
            raise AppDirError(f"{what} may not be inside %{var}% (PRD §11): {path}")


def settings_json_path(paths: DataPaths, *, explicit_data: bool | None = None) -> Path:
    r"""Where ``settings.json`` lives (PRD §11, data-model §5.5).

    - The app layout (the data folder is ``<app folder>\data`` and no ``--data`` was given):
      ``<app folder>\settings.json``.
    - ``--data <dir>`` given explicitly (development, tests, the CLI): ``<dir>\settings.json``,
      so a dev run never writes next to ``.devdata`` in the repo.

    ``explicit_data=None`` infers it: only a data folder that is ``<app folder>\data`` of
    :func:`default_app_folder` (``ETACH_APP_DIR``, or an installed sidecar's own folder) counts as
    the app layout.
    """
    if explicit_data is None:
        explicit_data = True
        if os.environ.get(APP_DIR_ENV) or getattr(sys, "frozen", False):
            app_data = (default_app_folder() / DATA_DIR_NAME).resolve()
            explicit_data = paths.root.resolve() != app_data
    if not explicit_data and paths.root.name == DATA_DIR_NAME:
        return paths.root.parent / "settings.json"
    return paths.root / "settings.json"


def exports_dir(paths: DataPaths, *, explicit_data: bool | None = None) -> Path:
    r"""Where saved DOCX files go (step 22.1.6, PRD D4 v5.0, §11): ``<app folder>\exports`` next
    to ``data\`` in the app layout; ``<dir>\exports`` when ``--data <dir>`` was given (development,
    tests, E2E), the same rule as :func:`settings_json_path`. Never AppData. Not created here."""
    folder = settings_json_path(paths, explicit_data=explicit_data).parent / EXPORTS_DIR_NAME
    folder = folder.resolve()
    _refuse_appdata(folder, what="the exports folder")
    return folder
