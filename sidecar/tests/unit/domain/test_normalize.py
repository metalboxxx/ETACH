"""normalize: value_norm, fold, name_search. Pure (no_io)."""

from __future__ import annotations

import pytest
from support.guards import assert_pure, no_io  # noqa: F401

from etach.domain.normalize import fold, name_search, value_norm

pytestmark = pytest.mark.usefixtures("no_io")


def test_value_norm() -> None:
    curly = "  He  DOESN" + chr(0x2019) + "T\tgo " + chr(0x201C) + "home" + chr(0x201D) + " "
    assert value_norm(curly) == 'he doesn\'t go "home"'
    assert value_norm("Trần") == "trần"  # accents kept


def test_fold() -> None:
    assert fold("Trần Thị Ngọc Ánh") == "Tran Thi Ngoc Anh"
    assert fold("Đề đường") == "De duong"


def test_name_search() -> None:
    assert name_search("  Trần   Thị Ngọc ÁNH ") == "tran thi ngoc anh"
    assert name_search("Tran Thi Ngoc Anh") == name_search("Trần Thị Ngọc Ánh")


def test_normalize_is_pure() -> None:
    assert_pure("etach.domain.normalize")
