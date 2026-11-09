"""The content-addressed file store, derived images and the cleanup sweep (data-model §2.8, §5.1,
§5.5).

- A file's ID is the sha256 of its bytes. It lives at ``files/<id[:2]>/<id>.<ext>`` under the data
  folder, and its ``files`` row stores that path relative to the data folder, with forward slashes.
- Identical bytes give the same ID: one file on disk and one row (the first ``put`` wins the row's
  ``kind`` and ``derived_from``).
- **Files are never modified.** Rotating or resizing makes a new ``kind="derived"`` file whose
  ``derived_from`` is the source. Every derived image first applies the EXIF orientation (what the
  photo check shows), then the requested operation; the original upload is kept byte for byte.
- Writes are atomic: a temp file in the target folder, then a rename.

The rows themselves go through :mod:`etach.store.repos.files`.
"""

from __future__ import annotations

import io
import json
import logging
import mimetypes
import os
import re
import sqlite3
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageOps

from etach.appdir import DataPaths
from etach.domain.models import File
from etach.store.db import iso, transaction
from etach.store.repos import files as file_rows

__all__ = [
    "FILES_DIR",
    "JPEG_QUALITY",
    "TEXT_MIME",
    "UNFINISHED_RUN_STATUSES",
    "FileKind",
    "FileStore",
    "SweepResult",
    "file_id_of",
    "referenced_file_ids",
    "sweep",
]

log = logging.getLogger(__name__)

FileKind = Literal["upload", "derived", "text", "export"]

FILES_DIR = "files"
TEXT_MIME = "text/plain; charset=utf-8"
JPEG_QUALITY = 95
DEFAULT_MAX_PX = 1600

# Runs whose input files must survive the sweep (data-model §2.7 statuses that are not finished).
UNFINISHED_RUN_STATUSES = ("queued", "running", "stopping", "stopped", "interrupted")

# extension -> MIME for the types the app handles; other extensions fall back to ``mimetypes``.
_MIME_BY_EXT: dict[str, str] = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": TEXT_MIME,
    "zip": "application/zip",
    "json": "application/json",
}
_EXT_ALIASES = {"jpeg": "jpg", "jpe": "jpg"}
_EXT_BY_MIME: dict[str, str] = {
    **{mime.split(";")[0]: ext for ext, mime in _MIME_BY_EXT.items()},
    "image/jpg": "jpg",
    "image/pjpeg": "jpg",
}
# Pillow format name -> (extension, MIME) for the image types the store records sizes for.
_IMAGE_FORMATS: dict[str, tuple[str, str]] = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}
_IMAGE_MIMES = {mime for _, mime in _IMAGE_FORMATS.values()}
_EXT_RE = re.compile(r"^[a-z0-9]{1,10}$")
_ID_RE = re.compile(r"^[0-9a-f]{64}$")
_EXIF_ORIENTATION = 0x0112


def file_id_of(data: bytes) -> str:
    """The content ID: the sha256 hex digest of the bytes."""
    return sha256(data).hexdigest()


def _resolve_type(ext_or_mime: str) -> tuple[str, str]:
    """``(ext, mime)`` from an extension (``".jpg"``, ``"jpeg"``) or a MIME type."""
    value = ext_or_mime.strip().lower()
    if "/" in value:
        base = value.split(";")[0].strip()
        ext = _EXT_BY_MIME.get(base)
        if ext is None:
            guessed = mimetypes.guess_extension(base)
            if guessed is None:
                raise ValueError(f"unknown MIME type {ext_or_mime!r}")
            ext = guessed.lstrip(".")
        ext = _EXT_ALIASES.get(ext, ext)
        return ext, _MIME_BY_EXT.get(ext, base)
    ext = _EXT_ALIASES.get(value.lstrip("."), value.lstrip("."))
    if not _EXT_RE.match(ext):
        raise ValueError(f"not a file extension: {ext_or_mime!r}")
    mime = _MIME_BY_EXT.get(ext) or mimetypes.guess_type(f"x.{ext}")[0]
    return ext, mime or "application/octet-stream"


def _image_size(data: bytes, mime: str) -> tuple[int, int]:
    """The stored pixel size (before any EXIF orientation); the bytes must match ``mime``."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            size = img.size
    except Exception as exc:
        raise ValueError(f"not a readable {mime} image: {exc}") from exc
    actual = _IMAGE_FORMATS.get(fmt or "")
    if actual is None or actual[1] != mime:
        raise ValueError(f"the bytes are a {fmt} image, not {mime}")
    return size


def _atomic_write(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` through a temp file in the same folder and a rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.replace(tmp, path)
        except PermissionError:
            # Windows: the target exists and is open elsewhere. It has the same content (the
            # name is the content hash), so keeping it is correct.
            if not (path.exists() and path.stat().st_size == len(data)):
                raise
    finally:
        tmp.unlink(missing_ok=True)


def _exif_orientation(img: Image.Image) -> int:
    try:
        value = img.getexif().get(_EXIF_ORIENTATION, 1)
    except Exception:
        return 1
    return value if isinstance(value, int) else 1


def _encode(img: Image.Image, fmt: str, icc_profile: bytes | None) -> bytes:
    """Encode in the source's format family: JPEG stays JPEG, PNG stays PNG, WebP stays WebP.
    EXIF is not copied (the orientation is already applied)."""
    buf = io.BytesIO()
    params: dict[str, Any] = {}
    if icc_profile:
        params["icc_profile"] = icc_profile
    if fmt == "JPEG":
        if img.mode not in ("L", "RGB", "CMYK"):
            img = img.convert("RGB")
        img.save(buf, "JPEG", quality=JPEG_QUALITY, subsampling=0, **params)
    elif fmt == "PNG":
        img.save(buf, "PNG", **params)
    elif fmt == "WEBP":
        img.save(buf, "WEBP", quality=JPEG_QUALITY, **params)
    else:  # pragma: no cover - the caller checks the format
        raise ValueError(f"cannot encode {fmt}")
    return buf.getvalue()


@dataclass(frozen=True)
class SweepResult:
    """What one sweep removed."""

    deleted: list[File] = field(default_factory=list)
    """The ``files`` rows deleted (their disk files were removed too, when present)."""
    orphans_removed: list[str] = field(default_factory=list)
    """Disk files (relative paths) that had no row, e.g. left by a crash, older than the grace."""


class FileStore:
    """The file store of one data folder, writing rows through ``conn``."""

    def __init__(self, conn: sqlite3.Connection, paths: DataPaths) -> None:
        self.conn = conn
        self.paths = paths

    # --- reading ---------------------------------------------------------------------------

    def get(self, file_id: str) -> File:
        row = file_rows.get_file(self.conn, file_id)
        if row is None:
            raise KeyError(f"no file {file_id}")
        return row

    def abspath(self, file_id: str) -> Path:
        """The absolute path of a stored file."""
        return self._abs(self.get(file_id).path)

    def read_bytes(self, file_id: str) -> bytes:
        return self.abspath(file_id).read_bytes()

    def read_text(self, file_id: str) -> str:
        return self.read_bytes(file_id).decode("utf-8")

    def _abs(self, rel_path: str) -> Path:
        return self.paths.root.joinpath(*rel_path.split("/"))

    # --- writing ---------------------------------------------------------------------------

    def put(
        self,
        data: bytes,
        ext_or_mime: str,
        kind: FileKind = "upload",
        derived_from: str | None = None,
        original_name: str | None = None,
    ) -> str:
        """Store ``data`` and return its ID. Identical bytes give the same ID, one file and one
        row; a repeat put refreshes an older row's ``created_at`` to now (the sweep's grace period
        then covers it). Images (JPEG/PNG/WebP) get ``width``/``height``; their bytes must match
        the type. ``original_name`` is the dropped file's name (uploads); a repeat put keeps the
        first name and only fills it when the row has none (data-model §2.8)."""
        if kind == "derived" and derived_from is None:
            raise ValueError("a derived file needs derived_from")
        ext, mime = _resolve_type(ext_or_mime)
        width = height = None
        if mime in _IMAGE_MIMES:
            width, height = _image_size(data, mime)
        file_id = file_id_of(data)
        files_rel = self.paths.files_dir.relative_to(self.paths.root).as_posix()
        rel = f"{files_rel}/{file_id[:2]}/{file_id}.{ext}"
        existing = file_rows.get_file(self.conn, file_id)
        if existing is not None:
            rel = existing.path  # the first put chose the extension
        target = self._abs(rel)
        if not (target.exists() and target.stat().st_size == len(data)):
            _atomic_write(target, data)
        now = datetime.now(UTC)
        with transaction(self.conn):
            # A dedup hit refreshes an older row's created_at, so the sweep's grace period
            # protects a re-uploaded photo. If a sweep removed the row meanwhile, insert it again.
            refreshed = self.conn.execute(
                "UPDATE files SET created_at = MAX(created_at, ?) WHERE id = ?",
                (iso(now), file_id),
            ).rowcount
            if refreshed and original_name is not None:
                file_rows.fill_original_name(self.conn, file_id, original_name)
            if not refreshed:
                file_rows.insert_file(
                    self.conn,
                    File(
                        id=file_id,
                        path=rel,
                        kind=kind,
                        derived_from=derived_from,
                        mime=mime,
                        width=width,
                        height=height,
                        created_at=now,
                        original_name=original_name,
                    ),
                )
        if not target.exists():  # a sweep removed it between the write and the row
            _atomic_write(target, data)
        return file_id

    def put_text(self, text: str, derived_from: str | None = None) -> str:
        """Store ``text`` as UTF-8 (``kind="text"``, ``.txt``). ``derived_from`` may name the
        document it was read from."""
        return self.put(text.encode("utf-8"), "txt", kind="text", derived_from=derived_from)

    # --- derived images --------------------------------------------------------------------

    def rotate(self, file_id: str, degrees: int) -> str:
        """The image turned ``degrees`` **clockwise** (a multiple of 90), after the EXIF
        orientation. Returns the source ID when nothing would change."""
        if degrees % 90:
            raise ValueError(f"rotation must be a multiple of 90, not {degrees}")
        turn = degrees % 360
        ops = {
            90: Image.Transpose.ROTATE_270,  # Pillow's ROTATE_* turn counter-clockwise
            180: Image.Transpose.ROTATE_180,
            270: Image.Transpose.ROTATE_90,
        }

        def op(img: Image.Image) -> Image.Image | None:
            return img.transpose(ops[turn]) if turn else None

        return self._derive(file_id, op)

    def resize(self, file_id: str, max_px: int = DEFAULT_MAX_PX) -> str:
        """The image scaled so its longer side is at most ``max_px`` (aspect ratio kept, never
        upscaled), after the EXIF orientation. Returns the source ID when nothing would change."""
        if max_px < 1:
            raise ValueError("max_px must be positive")

        def op(img: Image.Image) -> Image.Image | None:
            w, h = img.size
            longest = max(w, h)
            if longest <= max_px:
                return None
            scale = max_px / longest
            size = (max(1, round(w * scale)), max(1, round(h * scale)))
            if img.mode in ("1", "P"):  # these modes only resample with NEAREST
                img = img.convert("RGBA" if "transparency" in img.info else "RGB")
            return img.resize(size, Image.Resampling.LANCZOS)

        return self._derive(file_id, op)

    def _derive(self, file_id: str, op: Callable[[Image.Image], Image.Image | None]) -> str:
        src = self.get(file_id)
        if src.mime not in _IMAGE_MIMES:
            raise ValueError(f"file {file_id} is {src.mime}, not an image")
        with Image.open(self._abs(src.path)) as opened:
            opened.load()
            fmt = opened.format or ""
            icc = opened.info.get("icc_profile")
            needs_exif = _exif_orientation(opened) != 1
            upright = ImageOps.exif_transpose(opened) if needs_exif else opened
            assert upright is not None
            result = op(upright)
            if result is None and not needs_exif:
                return file_id
            out = upright if result is None else result
            data = _encode(out, fmt, icc if isinstance(icc, bytes) else None)
        return self.put(data, _IMAGE_FORMATS[fmt][0], kind="derived", derived_from=file_id)

    # --- cleanup ---------------------------------------------------------------------------

    def sweep(
        self, min_age: timedelta = timedelta(hours=24), now: datetime | None = None
    ) -> SweepResult:
        return sweep(self.conn, self.paths, min_age=min_age, now=now)


# --- the sweep (data-model §5.5) -------------------------------------------------------------


def _collect_file_ids(value: Any, out: set[str]) -> None:
    """Every ``file_id`` / ``text_file_id`` string anywhere in a JSON value."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("file_id", "text_file_id") and isinstance(item, str):
                out.add(item)
            else:
                _collect_file_ids(item, out)
    elif isinstance(value, list):
        for item in value:
            _collect_file_ids(item, out)


def _json_file_ids(texts: Iterable[str | None]) -> set[str]:
    found: set[str] = set()
    for text in texts:
        if text:
            _collect_file_ids(json.loads(text), found)
    return found


def referenced_file_ids(conn: sqlite3.Connection) -> set[str]:
    """IDs referenced by test pages, key pages (data-model v1.12), attempt pages (both
    columns), picture refs in any test's content, and the inputs of runs that are not finished."""
    refs: set[str] = set()
    refs.update(r[0] for r in conn.execute("SELECT file_id FROM test_pages"))
    refs.update(r[0] for r in conn.execute("SELECT file_id FROM test_key_pages"))
    for row in conn.execute("SELECT file_id, source_file_id FROM attempt_pages"):
        refs.update((row[0], row[1]))
    refs |= _json_file_ids(r[0] for r in conn.execute("SELECT content FROM tests"))
    marks = ", ".join("?" for _ in UNFINISHED_RUN_STATUSES)
    run_inputs = conn.execute(
        f"SELECT input FROM runs WHERE status IN ({marks})", UNFINISHED_RUN_STATUSES
    )
    refs |= _json_file_ids(r[0] for r in run_inputs)
    return refs


def sweep(
    conn: sqlite3.Connection,
    paths: DataPaths,
    min_age: timedelta = timedelta(hours=24),
    now: datetime | None = None,
) -> SweepResult:
    """Delete the ``files`` rows and disk files that nothing references (data-model §5.5).

    Kept: every file referenced (:func:`referenced_file_ids`), every file younger than
    ``min_age`` (photos uploaded at a photo check before Run), and every **ancestor** (the
    ``derived_from`` chain) of a kept file. A disk file that is already missing is fine. Disk
    files without a row that are older than ``min_age`` (a crash between the two writes, a
    stale temp file) are removed too.

    Photo-check uploads (step 15, orchestrator decision at step 20): an open photo-check
    message's ``body`` is deliberately **not** a reference. Photos dropped at a photo check that
    is never Run are protected only by the ``min_age`` grace (24 h); after that they are swept
    and the step 15 card shows its broken-page placeholder. Files of ``failed``/``discarded``
    runs are swept the same way.
    """
    now = now or datetime.now(UTC)
    cutoff = iso(now - min_age)
    store = FileStore(conn, paths)
    deleted: list[File] = []
    with transaction(conn):
        rows = {f.id: f for f in file_rows.list_files(conn)}
        keep = {i for i in referenced_file_ids(conn) if i in rows}
        keep |= {f.id for f in rows.values() if iso(f.created_at) > cutoff}
        stack = list(keep)
        while stack:  # close over the derived_from chain
            parent = rows[stack.pop()].derived_from
            if parent is not None and parent in rows and parent not in keep:
                keep.add(parent)
                stack.append(parent)
        doomed = [f for f in rows.values() if f.id not in keep]
        if doomed:
            # Every kept file's ancestors are kept, so no kept row points at a doomed one; the
            # doomed rows may point at each other, so check the FKs at commit, not per row.
            conn.execute("PRAGMA defer_foreign_keys = ON")
            conn.executemany("DELETE FROM files WHERE id = ?", [(f.id,) for f in doomed])
            deleted = doomed
    # Disk files go only **after** the commit: a rollback (an FK failure at commit, a crash)
    # then leaves every row with its file. A file whose delete fails stays as an orphan without
    # a row; a later sweep's orphan pass removes it.
    for f in deleted:
        try:
            store._abs(f.path).unlink(missing_ok=True)
        except OSError as exc:
            log.warning("could not delete %s: %s", f.path, exc)
    remaining = set(rows) - {f.id for f in deleted}
    orphans = _remove_orphans(paths, remaining, now - min_age)
    return SweepResult(deleted=deleted, orphans_removed=orphans)


def _remove_orphans(paths: DataPaths, known_ids: set[str], older_than: datetime) -> list[str]:
    removed: list[str] = []
    root = paths.files_dir
    if not root.is_dir():
        return removed
    limit = older_than.timestamp()
    for bucket in root.iterdir():
        if not bucket.is_dir():
            continue
        for path in bucket.iterdir():
            if not path.is_file():
                continue
            stem = path.name.split(".", 1)[0]
            is_temp = path.name.startswith(".") and path.name.endswith(".tmp")
            if not is_temp and (not _ID_RE.match(stem) or stem in known_ids):
                continue
            try:
                if path.stat().st_mtime >= limit:
                    continue
                path.unlink()
            except OSError as exc:
                log.warning("could not delete orphan %s: %s", path, exc)
                continue
            removed.append(path.relative_to(paths.root).as_posix())
    return removed
