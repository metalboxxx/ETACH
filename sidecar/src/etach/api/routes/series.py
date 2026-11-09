"""``/series``: the series list the teacher edits in Settings (llm-design v4.41, data-model
v1.21, decision D5).

Built like ``/schools``. ``GET`` lists them in order with the number of tests using each;
``POST`` adds a series (409 if the name exists, ignoring case); ``PATCH`` renames or moves one (a
rename updates the tests' ``meta.source`` and remakes automatic Test names); ``DELETE`` removes
one, 409 while a test uses it. A blank name → 422, an unknown id → 404.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from etach.api.deps import ConnDep
from etach.store.repos import schools, series

__all__ = ["router"]

router = APIRouter(tags=["series"])


class SeriesOut(BaseModel):
    id: int
    name: str
    position: int
    test_count: int


class NewSeries(BaseModel):
    name: str


class SeriesPatch(BaseModel):
    name: str | None = None
    position: int | None = None


def _out(s: series.Series) -> SeriesOut:
    return SeriesOut(id=s.id, name=s.name, position=s.position, test_count=s.test_count)


def _name(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = schools.clean_name(text)
    if cleaned is None:
        raise HTTPException(422, detail="name must not be empty")
    return cleaned


@router.get("/series", response_model=list[SeriesOut])
def list_series(conn: ConnDep) -> list[SeriesOut]:
    """The series list in order: id, name, number of tests using it."""
    return [_out(s) for s in series.list_series(conn)]


@router.post(
    "/series",
    response_model=SeriesOut,
    responses={409: {"description": "a series with this name exists"}},
)
def add_series(body: NewSeries, conn: ConnDep) -> SeriesOut:
    """Add a series at the end of the list."""
    name = _name(body.name)
    assert name is not None
    try:
        return _out(series.add_series(conn, name))
    except series.SeriesExistsError:
        raise HTTPException(409, detail=f"{name} is already in the list.") from None


@router.patch(
    "/series/{id}",
    response_model=SeriesOut,
    responses={409: {"description": "another series has this name"}},
)
def patch_series(id: int, body: SeriesPatch, conn: ConnDep) -> SeriesOut:
    """Rename or move (``position``); a rename updates the tests and remakes automatic Test
    names."""
    name = _name(body.name)
    try:
        return _out(series.update_series(conn, id, name=name, position=body.position))
    except KeyError:
        raise HTTPException(404, detail=f"no series {id}") from None
    except series.SeriesExistsError:
        raise HTTPException(409, detail=f"{name} is already in the list.") from None


@router.delete(
    "/series/{id}",
    status_code=204,
    responses={409: {"description": "tests use it"}},
)
def delete_series(id: int, conn: ConnDep) -> None:
    """Delete a series; 409 while a test uses it."""
    try:
        series.delete_series(conn, id)
    except KeyError:
        raise HTTPException(404, detail=f"no series {id}") from None
    except series.SeriesInUseError as exc:
        raise HTTPException(409, detail=exc.reason) from None
