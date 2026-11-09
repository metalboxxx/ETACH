"""``/occasions``: the occasion list the teacher edits in Settings (llm-design v4.33,
data-model v1.17).

``GET`` lists them in order with the number of tests using each; ``POST`` adds a teacher
occasion; ``PATCH`` renames or moves one (a rename remakes automatic Test names); ``DELETE``
removes a teacher occasion, 409 for a built-in or while a test uses it. A blank label or short
name → 422, an unknown code → 404.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from etach.api.deps import ConnDep
from etach.store.repos import occasions

__all__ = ["router"]

router = APIRouter(tags=["occasions"])


class OccasionOut(BaseModel):
    code: str
    label: str
    short_name: str
    position: int
    builtin: bool
    test_count: int


class NewOccasion(BaseModel):
    label: str
    short_name: str


class OccasionPatch(BaseModel):
    label: str | None = None
    short_name: str | None = None
    position: int | None = None


def _out(o: occasions.Occasion) -> OccasionOut:
    return OccasionOut(
        code=o.code,
        label=o.label,
        short_name=o.short_name,
        position=o.position,
        builtin=o.builtin,
        test_count=o.test_count,
    )


def _clean(text: str | None, field: str) -> str | None:
    if text is None:
        return None
    cleaned = " ".join(text.split())
    if not cleaned:
        raise HTTPException(422, detail=f"{field} must not be empty")
    return cleaned


@router.get("/occasions", response_model=list[OccasionOut])
def list_occasions(conn: ConnDep) -> list[OccasionOut]:
    """The occasion list in order: code, label, short name, built-in, test count."""
    return [_out(o) for o in occasions.list_occasions(conn)]


@router.post("/occasions", response_model=OccasionOut)
def add_occasion(body: NewOccasion, conn: ConnDep) -> OccasionOut:
    """Add a teacher occasion at the end of the list."""
    label = _clean(body.label, "label")
    short = _clean(body.short_name, "short_name")
    assert label is not None and short is not None
    return _out(occasions.add_occasion(conn, label, short))


@router.patch("/occasions/{code}", response_model=OccasionOut)
def patch_occasion(code: str, body: OccasionPatch, conn: ConnDep) -> OccasionOut:
    """Rename (label, short name) or move (``position``); a rename remakes automatic Test names."""
    try:
        return _out(
            occasions.update_occasion(
                conn,
                code,
                label=_clean(body.label, "label"),
                short_name=_clean(body.short_name, "short_name"),
                position=body.position,
            )
        )
    except KeyError:
        raise HTTPException(404, detail=f"no occasion {code}") from None


@router.delete(
    "/occasions/{code}",
    status_code=204,
    responses={409: {"description": "a built-in, or tests use it"}},
)
def delete_occasion(code: str, conn: ConnDep) -> None:
    """Delete a teacher occasion; 409 while a test uses it or for a built-in."""
    try:
        occasions.delete_occasion(conn, code)
    except KeyError:
        raise HTTPException(404, detail=f"no occasion {code}") from None
    except occasions.OccasionInUseError as exc:
        raise HTTPException(409, detail=exc.reason) from None
