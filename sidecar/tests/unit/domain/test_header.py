"""header.metadata_from: R8.1.3 and the occasion map. Pure (no_io)."""

from __future__ import annotations

import pytest
from support.guards import assert_pure, no_io  # noqa: F401

from etach.domain.header import metadata_from, occasion_of
from etach.domain.models import TestMetadata as Meta

pytestmark = pytest.mark.usefixtures("no_io")


def test_r8_1_3_header_and_filename() -> None:
    fields, pendings = metadata_from("ĐỀ CUỐI KÌ I LỚP 8 (K)", "Lop8-HKI-De1 (1).jpg", ref="R-1")
    assert fields["occasion"] == "FinalTerm"
    assert fields["term"] == 1
    assert fields["grade"] == 8
    assert fields["variant"] == "K"
    assert fields["test_number"] == "1"
    assert pendings == []
    Meta(**fields)


@pytest.mark.parametrize(
    ("text", "occasion"),
    [
        ("ĐỀ KIỂM TRA GIỮA KÌ II", "MidTerm"),
        ("de kiem tra giua hoc ki 1", "MidTerm"),
        ("KIỂM TRA CUỐI HỌC KỲ I", "FinalTerm"),
        ("ĐỀ KIỂM TRA HỌC KÌ II", "FinalTerm"),
        ("KỲ THI TUYỂN SINH VÀO LỚP 10 THPT", "EntranceExam"),
        ("Tuyen sinh lop 10", "EntranceExam"),
        ("KỲ THI TỐT NGHIỆP THPT 2025", "NationalExam"),
        ("ĐỀ THI HỌC SINH GIỎI CẤP HUYỆN", "GiftedExam"),
        ("Kiểm tra 15 phút", "FifteenMinuteTest"),
        ("KIỂM TRA 1 TIẾT", "UnitTest"),
        ("Kiểm tra 45 phút", "UnitTest"),
        ("Bài tập về nhà", None),
    ],
)
def test_occasion_map(text: str, occasion: str | None) -> None:
    assert occasion_of(text) == occasion


def test_unknown_occasion_pending() -> None:
    fields, pendings = metadata_from("BÀI TẬP", "scan.jpg", ref="R-9")
    assert fields["occasion"] == "Other:unknown"
    assert [(p.kind, p.dedupe_key) for p in pendings] == [
        ("unknown_occasion", "unknown_occasion:R-9")
    ]


def test_header_wins_over_filename() -> None:
    fields, _ = metadata_from("ĐỀ GIỮA KÌ II LỚP 9 - ĐỀ 2", "Lop8-HKI-De1.jpg")
    got = (fields["occasion"], fields["term"], fields["grade"], fields["test_number"])
    assert got == ("MidTerm", 2, 9, "2")


def test_filename_fallback_and_year() -> None:
    fields, _ = metadata_from(None, "K7_HK2_De3_2024-2025.png")
    assert fields["grade"] == 7 and fields["term"] == 2 and fields["test_number"] == "3"
    assert fields["year"] == "2024-2025"
    assert "variant" not in fields


def test_header_is_pure() -> None:
    assert_pure("etach.domain.header")
