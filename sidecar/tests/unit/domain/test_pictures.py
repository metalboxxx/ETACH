"""pictures: R8.1.4. Pure (no_io)."""

from __future__ import annotations

import hashlib

import pytest
from support.guards import assert_pure, no_io  # noqa: F401

from etach.domain.models import PictureRef
from etach.domain.pictures import placeholder, render_picture

pytestmark = pytest.mark.usefixtures("no_io")


def test_r8_1_4_placeholder() -> None:
    h = hashlib.sha256(b"page image").hexdigest()
    assert placeholder(h, "jpg", 3) == f"[Hình: files/{h[:2]}/{h}.jpg · trang 3]"
    assert render_picture(PictureRef(file_id=h, page_no=3)) == (
        f"[Hình: files/{h[:2]}/{h}.jpg · trang 3]"
    )
    assert placeholder(h, ".PNG", 1).endswith(f"{h}.png · trang 1]")


def test_pictures_is_pure() -> None:
    assert_pure("etach.domain.pictures")
