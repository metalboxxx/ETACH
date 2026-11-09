"""``/schools``: the school list the teacher edits in Settings (llm-design v4.34,
data-model v1.18).

``GET`` lists them in order with the number of tests and students using each; ``POST`` adds a
school (409 if the name exists, ignoring case); ``PATCH`` renames or moves one (a rename updates
tests and students and remakes automatic Test names); ``DELETE`` removes one, 409 while a test or
student uses it. A blank name → 422, an unknown id → 404.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from etach.api.deps import ConnDep
from etach.store.repos import schools

__all__ = ["router"]

router = APIRouter(tags=["schools"])


class SchoolOut(BaseModel):
    id: int
    name: str
    position: int
    test_count: int
    student_count: int


class NewSchool(BaseModel):
    name: str


class SchoolPatch(BaseModel):
    name: str | None = None
    position: int | None = None


def _out(s: schools.School) -> SchoolOut:
    return SchoolOut(
        id=s.id,
        name=s.name,
        position=s.position,
        test_count=s.test_count,
        student_count=s.student_count,
    )


def _name(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = schools.clean_name(text)
    if cleaned is None:
        raise HTTPException(422, detail="name must not be empty")
    return cleaned


@router.get("/schools", response_model=list[SchoolOut])
def list_schools(conn: ConnDep) -> list[SchoolOut]:
    """The school list in order: id, name, number of tests and students using it."""
    return [_out(s) for s in schools.list_schools(conn)]


@router.post(
    "/schools",
    response_model=SchoolOut,
    responses={409: {"description": "a school with this name exists"}},
)
def add_school(body: NewSchool, conn: ConnDep) -> SchoolOut:
    """Add a school at the end of the list."""
    name = _name(body.name)
    assert name is not None
    try:
        return _out(schools.add_school(conn, name))
    except schools.SchoolExistsError:
        raise HTTPException(409, detail=f"{name} is already in the list.") from None


@router.patch(
    "/schools/{id}",
    response_model=SchoolOut,
    responses={409: {"description": "another school has this name"}},
)
def patch_school(id: int, body: SchoolPatch, conn: ConnDep) -> SchoolOut:
    """Rename or move (``position``); a rename updates tests and students and remakes automatic
    Test names."""
    name = _name(body.name)
    try:
        return _out(schools.update_school(conn, id, name=name, position=body.position))
    except KeyError:
        raise HTTPException(404, detail=f"no school {id}") from None
    except schools.SchoolExistsError:
        raise HTTPException(409, detail=f"{name} is already in the list.") from None


@router.delete(
    "/schools/{id}",
    status_code=204,
    responses={409: {"description": "tests or students use it"}},
)
def delete_school(id: int, conn: ConnDep) -> None:
    """Delete a school; 409 while a test or student uses it."""
    try:
        schools.delete_school(conn, id)
    except KeyError:
        raise HTTPException(404, detail=f"no school {id}") from None
    except schools.SchoolInUseError as exc:
        raise HTTPException(409, detail=exc.reason) from None
