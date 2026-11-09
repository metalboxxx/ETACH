"""match_student (R8.1.9). Synthetic names only; real student names stay out of git."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from support.guards import no_io  # noqa: F401

from etach.domain.models import Student
from etach.domain.normalize import name_search
from etach.domain.students import match_student

pytestmark = pytest.mark.usefixtures("no_io")


def student(sid: str, full_name: str, class_name: str | None = None) -> Student:
    return Student(
        id=sid,
        full_name=full_name,
        name_search=name_search(full_name),
        class_name=class_name,
        school=None,
        grade=8,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


PROFILES = [
    student("S-1", "Trần Thị Ngọc Ánh", "8A"),
    student("S-2", "Lê Văn Đức", "8B"),
    student("S-3", "Nguyễn Minh Khôi", "8A"),
    student("S-4", "Nguyễn Minh Khôi", "8C"),
]


def test_r8_1_9_unaccented_name_matches() -> None:
    assert match_student("Tran Thi Ngoc Anh", None, PROFILES) == "S-1"
    assert match_student("  TRẦN  thị ngọc ánh ", None, PROFILES) == "S-1"
    assert match_student("Le Van Duc", "8b", PROFILES) == "S-2"


def test_r8_1_9_unknown_name_none() -> None:
    assert match_student("Pham Thu Ha", None, PROFILES) is None
    assert match_student("Tran Thi Ngoc", None, PROFILES) is None  # exact, not a prefix


def test_empty_name_none() -> None:
    assert match_student(None, "8A", PROFILES) is None
    assert match_student("   ", "8A", PROFILES) is None


def test_class_breaks_a_tie() -> None:
    assert match_student("Nguyen Minh Khoi", "8C", PROFILES) == "S-4"
    assert match_student("Nguyen Minh Khoi", None, PROFILES) is None
    assert match_student("Nguyen Minh Khoi", "8D", PROFILES) is None
