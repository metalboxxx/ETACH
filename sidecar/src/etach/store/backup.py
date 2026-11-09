"""Backup and restore (data-model §5.5).

A backup is ``VACUUM INTO`` (a consistent copy of the open database) plus the ``files/`` folder
(and ``models.toml`` when present), zipped into one file, normally under ``data\\backups\\``. It
is not encrypted in this version. Inside the zip every name is relative to the data folder
(``app.db``, ``models.toml``, ``files/ab/<id>.jpg``), so a restore can go anywhere.

``backup`` still writes a bare database file when the destination does not end in ``.zip``, and
``restore`` accepts both.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from etach.appdir import DataPaths, resolve_data_dir
from etach.store.db import apply_migrations, connect

__all__ = ["DB_NAME", "BackupError", "backup", "restore"]

DB_NAME = "app.db"
_MODELS_TOML = "models.toml"


class BackupError(RuntimeError):
    pass


def _vacuum_into(conn: sqlite3.Connection, dest: Path) -> None:
    if conn.in_transaction:
        raise BackupError("backup must not run inside a transaction")
    conn.execute("VACUUM INTO ?", (str(dest),))


def backup(conn: sqlite3.Connection, dest_path: Path | str, paths: DataPaths | None = None) -> Path:
    """Write a backup to ``dest_path`` (which must not exist).

    ``*.zip``: the database plus ``paths.files_dir`` (and ``models.toml``) of ``paths`` (needed
    then); otherwise the database alone."""
    dest = Path(dest_path).resolve()
    if dest.exists():
        raise BackupError(f"backup destination already exists: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.suffix.lower() != ".zip":
        _vacuum_into(conn, dest)
        return dest
    if paths is None:
        raise BackupError("a zip backup needs the data folder")
    tmp = Path(tempfile.mkdtemp(dir=dest.parent, prefix=".backup-"))
    partial = dest.with_name(dest.name + ".part")
    try:
        db_copy = tmp / DB_NAME
        _vacuum_into(conn, db_copy)
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_copy, DB_NAME)
            if paths.models_toml.is_file():
                zf.write(paths.models_toml, _MODELS_TOML)
            if paths.files_dir.is_dir():
                for file in sorted(paths.files_dir.rglob("*")):
                    if not file.is_file() or file.name.endswith(".tmp"):
                        continue
                    zf.write(file, file.relative_to(paths.root).as_posix())
        partial.replace(dest)
    finally:
        partial.unlink(missing_ok=True)
        shutil.rmtree(tmp, ignore_errors=True)
    return dest


def _against(path: Path | str, base: Path | None) -> Path:
    """``path`` made absolute against ``base`` when it is relative and ``base`` is given."""
    p = Path(path)
    if base is not None and not p.is_absolute():
        return Path(base) / p
    return p


def _safe_member(name: str, files_prefix: str) -> bool:
    """Only ``app.db``, ``models.toml`` and plain paths under ``files/`` are restored."""
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or "\\" in name or ":" in name:
        return False
    return name in (DB_NAME, _MODELS_TOML) or (
        name.startswith(files_prefix + "/") and not name.endswith("/")
    )


def restore(
    backup_path: Path | str, new_folder: Path | str, *, base: Path | None = None
) -> DataPaths:
    """Restore a backup (a zip, or a bare database file) into a new data folder. The folder must
    not exist or must be empty; the live data folder is never touched. The restored database is
    integrity-checked and migrated to the current schema.

    ``base``: the folder a relative ``backup_path`` or ``new_folder`` resolves against (the app
    folder, CLAUDE.md "resolve every path relative to that folder"); never the process's working
    folder. Without it a relative path resolves against the working folder (CLI use)."""
    source = _against(backup_path, base)
    if not source.is_file():
        raise BackupError(f"no backup file at {source}")
    paths = resolve_data_dir(_against(new_folder, base))
    if paths.root.exists() and any(paths.root.iterdir()):
        raise BackupError(f"restore target is not empty: {paths.root}")
    paths.ensure()
    if zipfile.is_zipfile(source):
        files_prefix = paths.files_dir.relative_to(paths.root).as_posix()
        with zipfile.ZipFile(source) as zf:
            names = zf.namelist()
            if DB_NAME not in names:
                raise BackupError(f"the backup has no {DB_NAME}")
            for name in names:
                if not _safe_member(name, files_prefix):
                    raise BackupError(f"unexpected entry in the backup: {name!r}")
            for name in names:
                target = paths.root.joinpath(*name.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, target.open("wb") as out:
                    shutil.copyfileobj(src, out)
    else:
        shutil.copyfile(source, paths.db)
    conn = connect(paths.db)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise BackupError(f"restored database failed the integrity check: {result}")
        apply_migrations(conn)
    finally:
        conn.close()
    return paths
