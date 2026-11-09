"""``/maintenance``: backup, restore, clear old model-call logs (llm-design §2, data-model §5.5).

A backup is ``<data>/backups/<timestamp>.zip``: the database (``VACUUM INTO``) plus ``files/``
and ``models.toml`` (:mod:`etach.store.backup`). Restore goes into a new, empty folder. The daily
scheduler is :mod:`etach.api.maintenance`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from etach.api.deps import ConnDep, CtxDep
from etach.api.routes.settings import settings_path
from etach.appdir import AppDirError
from etach.store import backup as store_backup
from etach.store.repos import runs

__all__ = ["router"]

router = APIRouter(tags=["maintenance"])


class BackupDone(BaseModel):
    path: str


class RestoreRequest(BaseModel):
    backup_path: str
    new_folder: str


class RestoreDone(BaseModel):
    data_folder: str


class ClearLogs(BaseModel):
    older_than_days: int = Field(ge=0)


class LogsCleared(BaseModel):
    deleted: int


@router.post("/maintenance/backup", response_model=BackupDone)
def backup(conn: ConnDep, ctx: CtxDep) -> BackupDone:
    """``<data>/backups/<timestamp>.zip``: the database plus ``files/`` (data-model §5.5)."""
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    dest = ctx.paths.backups_dir / f"{stamp}.zip"
    try:
        path = store_backup.backup(conn, dest, ctx.paths)
    except store_backup.BackupError as exc:
        raise HTTPException(409, detail=str(exc)) from None
    return BackupDone(path=str(path))


@router.post("/maintenance/restore", response_model=RestoreDone)
def restore(body: RestoreRequest, ctx: CtxDep) -> RestoreDone:
    """Restore a backup into a new (empty) data folder; the live folder is not touched. A relative
    ``backup_path`` or ``new_folder`` resolves against the app folder (the folder holding
    ``settings.json``: ``<app>`` in the app layout, the data folder itself with ``--data``), never
    the sidecar's working folder."""
    base = settings_path(ctx).parent
    try:
        paths = store_backup.restore(body.backup_path, body.new_folder, base=base)
    except (store_backup.BackupError, AppDirError) as exc:
        raise HTTPException(409, detail=str(exc)) from None
    return RestoreDone(data_folder=str(paths.root))


@router.post("/maintenance/clear-logs", response_model=LogsCleared)
def clear_logs(body: ClearLogs, conn: ConnDep) -> LogsCleared:
    """Delete ``llm_calls`` older than ``older_than_days`` that no explanation references."""
    cutoff = datetime.now(UTC) - timedelta(days=body.older_than_days)
    return LogsCleared(deleted=runs.delete_llm_calls_before(conn, cutoff))
