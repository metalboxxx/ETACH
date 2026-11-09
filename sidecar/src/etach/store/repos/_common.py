"""Row <-> pydantic conversion and readable IDs, shared by the repository modules.

- Timestamps are stored as fixed-width ISO-8601 UTC strings (``etach.store.db.iso``).
- Booleans are stored as 0/1.
- JSON columns hold pydantic's JSON rendering of the field (``model_dump(mode="json")``).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

from etach.store.db import dumps, iso

__all__ = ["from_row", "insert_model", "next_readable_id", "to_row"]


def to_row(model: BaseModel, json_cols: Iterable[str] = ()) -> dict[str, Any]:
    """The model's fields as column values."""
    json_set = set(json_cols)
    as_json = model.model_dump(mode="json", include=json_set) if json_set else {}
    row: dict[str, Any] = {}
    for name in type(model).model_fields:
        value = getattr(model, name)
        if name in json_set:
            row[name] = None if value is None else dumps(as_json[name])
        elif isinstance(value, datetime):
            row[name] = iso(value)
        elif isinstance(value, date):
            row[name] = value.isoformat()
        elif isinstance(value, bool):
            row[name] = int(value)
        else:
            row[name] = value
    return row


def from_row[M: BaseModel](
    cls: type[M], row: sqlite3.Row | dict[str, Any], json_cols: Iterable[str] = ()
) -> M:
    """Build ``cls`` from a row; columns that are not fields of ``cls`` are ignored."""
    data = dict(row)
    for name in json_cols:
        if data.get(name) is not None:
            data[name] = json.loads(data[name])
    fields = cls.model_fields
    return cls.model_validate({k: v for k, v in data.items() if k in fields})


def insert_model(
    conn: sqlite3.Connection,
    table: str,
    model: BaseModel,
    json_cols: Sequence[str] = (),
    extra: dict[str, Any] | None = None,
) -> None:
    """``INSERT INTO table`` the model's fields (plus ``extra`` columns)."""
    row = to_row(model, json_cols)
    if extra:
        row.update(extra)
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(row.values()))


def next_readable_id(conn: sqlite3.Connection, table: str, prefix: str) -> str:
    """``<prefix>-NNNN``: the largest number in use + 1, zero-padded to 4 digits."""
    row = conn.execute(
        f"SELECT MAX(CAST(SUBSTR(id, {len(prefix) + 2}) AS INTEGER)) FROM {table}"
        " WHERE id LIKE ? || '-%'",
        (prefix,),
    ).fetchone()
    return f"{prefix}-{(row[0] or 0) + 1:04d}"
