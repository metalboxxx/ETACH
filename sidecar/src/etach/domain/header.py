"""Test metadata from the printed header and the file name (llm-design §4 ``merge_and_normalize``).

Priority per field: header patterns first, then the file name. Teacher edits are applied later by
``write_test_meta``, not here. An occasion that matches nothing becomes ``Other:unknown`` plus a
pending ``unknown_occasion``. Matching is case- and accent-insensitive. Pure: no I/O.
"""

from __future__ import annotations

import re
from typing import Any

from etach.domain.normalize import collapse_spaces, fold
from etach.domain.working import PendingReview

__all__ = ["UNKNOWN_OCCASION", "metadata_from", "occasion_of"]

UNKNOWN_OCCASION = "Other:unknown"

_KI = r"k[iy]"
# Order matters: "giữa học kì" before "học kì"; "15 phút" before "45 phút".
_OCCASIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(rf"\bgiua\s+(?:hoc\s+)?{_KI}\b"), "MidTerm"),
    (re.compile(rf"\bcuoi\s+(?:hoc\s+)?{_KI}\b"), "FinalTerm"),
    (re.compile(r"\btuyen\s+sinh\s+(?:vao\s+)?lop\s*10\b"), "EntranceExam"),
    (re.compile(r"\btot\s+nghiep\s+thpt\b"), "NationalExam"),
    (re.compile(r"\bhoc\s+sinh\s+gioi\b"), "GiftedExam"),
    (re.compile(r"\b15\s*phut\b"), "FifteenMinuteTest"),
    (re.compile(r"\b(?:1\s*tiet|45\s*phut)\b"), "UnitTest"),
    (re.compile(rf"\bhoc\s+{_KI}\b"), "FinalTerm"),
)
_TERM = re.compile(rf"\b(?:hoc\s+{_KI}|{_KI}|hk)\s*(ii|i|1|2)\b")
_GRADE = re.compile(r"\b(?:lop|khoi)\s*(\d{1,2})\b|\bk(\d{1,2})\b")
_TEST_NO = re.compile(r"\bde\s*(?:so\s*)?(\d{1,3})\b")
_YEAR = re.compile(r"(?<!\d)(20\d\d)\s*[-/" + chr(0x2013) + r"]\s*(20\d\d)(?!\d)")
_VARIANT = re.compile(r"\(\s*([A-Za-z]{1,2})\s*\)\s*$")
_COPY_SUFFIX = re.compile(r"\s*\(\d+\)\s*$")
_EXT = re.compile(r"\.[A-Za-z0-9]{1,5}$")


def _key(text: str) -> str:
    """Folded, lowercased, separators as spaces."""
    return collapse_spaces(re.sub(r"[_\-.]+", " ", fold(text).lower()))


def _stem(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    return _COPY_SUFFIX.sub("", _EXT.sub("", name))


def occasion_of(text: str) -> str | None:
    key = _key(text)
    for pattern, occasion in _OCCASIONS:
        if pattern.search(key):
            return occasion
    return None


def _term(text: str) -> int | None:
    m = _TERM.search(_key(text))
    if not m:
        return None
    return 2 if m.group(1) in ("ii", "2") else 1


def _grade(text: str) -> int | None:
    # "Lop8-HKI" folds to "lop8 hki"; the grade needs the raw separators kept as spaces.
    for m in _GRADE.finditer(_key(text)):
        value = int(m.group(1) or m.group(2))
        if 1 <= value <= 12:
            return value
    return None


def _test_number(text: str) -> str | None:
    m = _TEST_NO.search(_key(text))
    return m.group(1) if m else None


def _year(text: str) -> str | None:
    m = _YEAR.search(fold(text))
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _variant(text: str) -> str | None:
    m = _VARIANT.search(collapse_spaces(text))
    return m.group(1).upper() if m else None


def metadata_from(
    header_text: str | None,
    filename: str | None,
    *,
    ref: str = "",
) -> tuple[dict[str, Any], list[PendingReview]]:
    """Return ``TestMetadata`` fields (``occasion`` always set) and the pending reviews.

    ``ref`` (the run or test id supplied by step 9) goes into the ``unknown_occasion``
    dedupe key: ``unknown_occasion:<ref>``.
    """
    sources = [s for s in (header_text or "", _stem(filename) if filename else "") if s]
    fields: dict[str, Any] = {}
    pendings: list[PendingReview] = []

    def first(fn: Any) -> Any:
        for src in sources:
            value = fn(src)
            if value is not None:
                return value
        return None

    occasion = first(occasion_of)
    if occasion is None:
        occasion = UNKNOWN_OCCASION
        pendings.append(
            PendingReview(
                kind="unknown_occasion",
                dedupe_key=f"unknown_occasion:{ref}",
                refs={},
                proposal={"occasion": UNKNOWN_OCCASION, "header_text": header_text},
            )
        )
    fields["occasion"] = occasion
    for name, fn in (
        ("term", _term),
        ("grade", _grade),
        ("test_number", _test_number),
        ("year", _year),
        ("variant", _variant),
    ):
        value = first(fn)
        if value is not None:
            fields[name] = value
    return fields, pendings
