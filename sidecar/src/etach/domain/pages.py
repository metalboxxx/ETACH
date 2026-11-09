"""Page planning for ``prepare_pages`` (llm-design §4): order, rotation, key pages, text layers.

``plan_pages`` only returns the plan; step 9 executes the file operations. Rotation is in
degrees **clockwise** (structure.md §7); every image page is then resized to at most 1600 px.
A **text-only page** (a DOCX's text: ``file_id = text_file_id``, data-model §2.7) has no image,
so it gets no file operation; its text goes to the model as text (PRD §11).
A run whose test pages are all born-digital skips answer reading (PRD D26,
:func:`skip_answer_reading`).
Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from etach.domain.models import ExtractInput, File, PageInput

__all__ = [
    "MAX_SIDE",
    "PageOp",
    "PagePlan",
    "PlannedPage",
    "is_text_only",
    "plan_pages",
    "skip_answer_reading",
]

MAX_SIDE = 1600


@dataclass(frozen=True)
class PageOp:
    """One file operation: ``rotate`` (``value`` = degrees clockwise) or ``resize`` (max side)."""

    op: Literal["rotate", "resize"]
    value: int


@dataclass(frozen=True)
class PlannedPage:
    page_no: int  # test pages 1..n; key pages 1..k in their own list
    source_file_id: str
    rotation: int
    is_key: bool
    text_file_id: str | None
    ops: tuple[PageOp, ...]
    target_size: tuple[int, int] | None  # (width, height) after the ops, if the size is known


@dataclass(frozen=True)
class PagePlan:
    pages: list[PlannedPage] = field(default_factory=list)
    key_pages: list[PlannedPage] = field(default_factory=list)


def is_text_only(page: PageInput) -> bool:
    """A text-only page (data-model §2.7 ``PageInput``): its ``file_id`` is its text file."""
    return page.text_file_id is not None and page.file_id == page.text_file_id


def _target_size(file: File, rotation: int) -> tuple[int, int] | None:
    if file.width is None or file.height is None:
        return None
    w, h = (file.height, file.width) if rotation in (90, 270) else (file.width, file.height)
    longest = max(w, h)
    if longest <= MAX_SIDE:
        return (w, h)
    scale = MAX_SIDE / longest
    return (max(1, round(w * scale)), max(1, round(h * scale)))


def plan_pages(input: ExtractInput, files: Mapping[str, File]) -> PagePlan:
    """Plan the pages in the teacher's order; 🔑 pages go to ``key_pages``. A text-only page
    gets no ops and no ``target_size`` (it has no image to turn or resize).

    Raises ``KeyError`` if a page's file is not in ``files``.
    """
    plan = PagePlan()
    for page in input.pages:
        file = files[page.file_id]
        text_only = is_text_only(page)
        ops: list[PageOp] = []
        if not text_only:
            if page.rotation % 360:
                ops.append(PageOp("rotate", page.rotation % 360))
            ops.append(PageOp("resize", MAX_SIDE))
        target = plan.key_pages if page.is_key else plan.pages
        target.append(
            PlannedPage(
                page_no=len(target) + 1,
                source_file_id=page.file_id,
                rotation=page.rotation,
                is_key=page.is_key,
                text_file_id=page.text_file_id,
                ops=tuple(ops),
                target_size=None if text_only else _target_size(file, page.rotation),
            )
        )
    return plan


def skip_answer_reading(test_pages_born_digital: Sequence[bool]) -> bool:
    """PRD D26: answer reading is skipped only when **every** test page is born-digital (a typed
    page holds no handwriting; ``store.documents.born_digital_pages`` decides per page). A mixed
    run (e.g. photos plus a typed PDF) still reads answers on every page; no test page → read."""
    return bool(test_pages_born_digital) and all(test_pages_born_digital)
