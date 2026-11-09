"""Picture placeholders (PRD D11): a picture is shown as its page image plus the page number.

Cropping is deferred, so a picture's ``file_id`` is the page image's file. Pure: no I/O.
"""

from __future__ import annotations

from etach.domain.models import PictureRef

__all__ = ["placeholder", "render_picture"]


def placeholder(file_id: str, ext: str, page_no: int) -> str:
    """``[Hình: files/<id[:2]>/<id>.<ext> · trang <n>]`` (R8.1.4)."""
    ext = ext.lstrip(".").lower()
    return f"[Hình: files/{file_id[:2]}/{file_id}.{ext} · trang {page_no}]"


def render_picture(ref: PictureRef, ext: str = "jpg") -> str:
    """The placeholder for a stored ``PictureRef``."""
    return placeholder(ref.file_id, ext, ref.page_no)
