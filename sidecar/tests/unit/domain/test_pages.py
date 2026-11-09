"""pages.plan_pages. Pure (no_io)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from support.guards import assert_pure, no_io  # noqa: F401

from etach.domain.models import ExtractInput, File, PageInput
from etach.domain.pages import MAX_SIDE, PageOp, is_text_only, plan_pages

pytestmark = pytest.mark.usefixtures("no_io")


def f(id_: str, w: int | None, h: int | None) -> File:
    return File(
        id=id_,
        path=f"files/{id_[:2]}/{id_}.jpg",
        kind="upload",
        derived_from=None,
        mime="image/jpeg",
        width=w,
        height=h,
        created_at=datetime(2026, 9, 29, tzinfo=UTC),
    )


def page_input(file_id: str, rotation: int, is_key: bool, text: str | None = None) -> PageInput:
    return PageInput.model_validate(
        {"file_id": file_id, "rotation": rotation, "is_key": is_key, "text_file_id": text}
    )


def test_plan_pages_order_keys_rotation_text() -> None:
    files = {
        "aa": f("aa", 3000, 4000),
        "bb": f("bb", 1000, 800),
        "kk": f("kk", 1200, 1600),
        "cc": f("cc", None, None),
    }
    inp = ExtractInput(
        pages=[
            page_input("bb", 90, False),
            page_input("kk", 0, True),
            page_input("aa", 0, False, "tt"),
            page_input("cc", 270, False),
        ],
        existing_test_id=None,
        supersedes_attempt_id=None,
    )
    plan = plan_pages(inp, files)
    assert [(p.page_no, p.source_file_id) for p in plan.pages] == [(1, "bb"), (2, "aa"), (3, "cc")]
    assert [(p.page_no, p.source_file_id, p.is_key) for p in plan.key_pages] == [(1, "kk", True)]
    first, second, third = plan.pages
    assert first.ops == (PageOp("rotate", 90), PageOp("resize", MAX_SIDE))
    assert first.target_size == (800, 1000)
    assert second.ops == (PageOp("resize", MAX_SIDE),)
    assert second.text_file_id == "tt" and second.target_size == (1200, 1600)
    assert third.rotation == 270 and third.target_size is None
    assert plan.key_pages[0].target_size == (1200, 1600)


def text_file(id_: str) -> File:
    return File(
        id=id_,
        path=f"files/{id_[:2]}/{id_}.txt",
        kind="text",
        derived_from="dx",
        mime="text/plain; charset=utf-8",
        width=None,
        height=None,
        created_at=datetime(2026, 9, 29, tzinfo=UTC),
    )


def test_plan_pages_text_only_page_gets_no_image_ops() -> None:
    """M1 baseline fix: a picture-free DOCX is one text-only page (``file_id = text_file_id``);
    it has no image, so no rotate/resize is planned, even when the teacher turned it."""
    files = {"tt": text_file("tt"), "aa": f("aa", 3000, 4000), "ll": text_file("ll")}
    inp = ExtractInput(
        pages=[
            page_input("tt", 0, False, "tt"),
            page_input("aa", 90, False, "ll"),  # an image page with a text layer
            page_input("tt", 90, False, "tt"),
        ],
        existing_test_id=None,
        supersedes_attempt_id=None,
    )
    plan = plan_pages(inp, files)
    text, image, turned = plan.pages
    assert text.ops == () and text.target_size is None
    assert text.source_file_id == text.text_file_id == "tt"
    assert turned.ops == () and turned.rotation == 90
    assert image.ops == (PageOp("rotate", 90), PageOp("resize", MAX_SIDE))
    assert image.text_file_id == "ll" and image.target_size == (1600, 1200)
    assert is_text_only(inp.pages[0]) and not is_text_only(inp.pages[1])
    assert not is_text_only(page_input("aa", 0, False))


def test_plan_pages_missing_file() -> None:
    inp = ExtractInput(
        pages=[page_input("zz", 0, False)], existing_test_id=None, supersedes_attempt_id=None
    )
    with pytest.raises(KeyError):
        plan_pages(inp, {})


def test_pages_is_pure() -> None:
    assert_pure("etach.domain.pages")
