"""Series details (data-model v1.14.1, decision D3; v1.21, decision D5).

"Copy details from…" copies :data:`SERIES_FIELDS`, always as a teacher write
(``write_test_meta(by_teacher=True)``), so they go into ``edited_fields`` and an extraction never
overwrites them. Only fields with a value in the source are copied; a blank one leaves the target's
value. ``grade`` and ``test_number`` are never copied.

"Same series as…" (v1.21, D5) picks a series name: the new test's ``source`` is that name, and
:data:`SERIES_NAME_FIELDS` (grade, occasion, term, year) come from the newest test of that series,
also as teacher writes and only when they have a value (the unknown occasion counts as none). The
school is not copied.
"""

from __future__ import annotations

from typing import Any

from etach.domain.models import UNKNOWN_OCCASION_CODE, TestMetadata

__all__ = ["SERIES_FIELDS", "SERIES_NAME_FIELDS", "series_details", "series_name_details"]

SERIES_FIELDS: tuple[str, ...] = ("occasion", "term", "school", "source", "year")
SERIES_NAME_FIELDS: tuple[str, ...] = ("grade", "occasion", "term", "year")


def _filled(meta: TestMetadata, fields: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in fields:
        value = getattr(meta, f)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        out[f] = value
    return out


def series_details(meta: TestMetadata) -> dict[str, Any]:
    """The series fields of ``meta`` that have a value (``None`` and blank text are left out)."""
    return _filled(meta, SERIES_FIELDS)


def series_name_details(name: str, newest: TestMetadata | None) -> dict[str, Any]:
    """What "same series as <name>" writes (D5): ``source`` = ``name``, plus grade, occasion,
    term and year of ``newest`` (the newest test of the series) that have a value."""
    out: dict[str, Any] = {}
    if newest is not None:
        out = _filled(newest, SERIES_NAME_FIELDS)
        if out.get("occasion") == UNKNOWN_OCCASION_CODE:
            del out["occasion"]
    out["source"] = name
    return out
