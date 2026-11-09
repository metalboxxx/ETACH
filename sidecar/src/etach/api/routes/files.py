"""``/files``: upload a dropped document, read stored bytes (llm-design §2).

- ``POST /files`` takes the raw file bytes as the request body and the dropped file's name as
  ``?name=`` (python-multipart is not a dependency). It stores the document through
  :func:`etach.store.documents.ingest` and returns ``{file_id, pages}``: ``file_id`` is the stored
  upload (the content hash), ``pages`` the :class:`~etach.domain.models.PageInput` list for the
  photo check. An unsupported type → 415 with the message.
- ``GET /files/{id}`` streams the bytes with the stored ``Content-Type``; ``?thumb=1`` returns a
  thumbnail (longest side ≤ :data:`THUMB_PX`) made in memory, nothing stored. It also accepts
  ``?token=`` (``<img>`` cannot send headers).
"""

from __future__ import annotations

import io
from pathlib import PurePath
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps
from pydantic import BaseModel

from etach.api.auth import allow_query_token
from etach.api.deps import FilesDep
from etach.domain.models import PageInput
from etach.store import documents
from etach.store.files import file_id_of

__all__ = ["THUMB_PX", "UploadResult", "router"]

THUMB_PX = 256

router = APIRouter(tags=["files"])


class UploadResult(BaseModel):
    file_id: str
    pages: list[PageInput]


@router.post(
    "/files",
    response_model=UploadResult,
    responses={415: {"description": "not a JPEG, PNG, WebP, PDF or DOCX file"}},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def upload_file(
    request: Request, files: FilesDep, name: Annotated[str, Query()] = ""
) -> UploadResult:
    """Store a dropped file (image, PDF, DOCX) → its id and the pages of the photo check."""
    data = await request.body()
    base = PurePath(name.replace("\\", "/")).name
    try:
        pages = await run_in_threadpool(documents.ingest, files, data, base)
    except documents.UnsupportedDocument as exc:
        raise HTTPException(415, detail=str(exc)) from exc
    return UploadResult(file_id=file_id_of(data), pages=pages)


def _thumbnail(data: bytes) -> tuple[bytes, str]:
    with Image.open(io.BytesIO(data)) as src:
        img = ImageOps.exif_transpose(src)
        img.thumbnail((THUMB_PX, THUMB_PX))
        out = io.BytesIO()
        if img.mode in ("RGBA", "LA", "P"):
            img.save(out, "PNG")
            return out.getvalue(), "image/png"
        img.convert("RGB").save(out, "JPEG", quality=80)
        return out.getvalue(), "image/jpeg"


@router.get(
    "/files/{id}",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}, 404: {}},
)
@allow_query_token
def get_file(id: str, files: FilesDep, thumb: Annotated[bool, Query()] = False) -> Response:
    """The file bytes (``?thumb=1``: a ≤ 256 px image thumbnail)."""
    try:
        row = files.get(id)
        path = files.abspath(id)
    except KeyError as exc:
        raise HTTPException(404, detail=f"no file {id}") from exc
    if not path.exists():
        raise HTTPException(404, detail=f"file {id} is missing on disk")
    if thumb:
        if not row.mime.startswith("image/"):
            raise HTTPException(415, detail=f"file {id} ({row.mime}) has no thumbnail")
        body, mime = _thumbnail(path.read_bytes())
        return Response(body, media_type=mime)
    return FileResponse(path, media_type=row.mime)
