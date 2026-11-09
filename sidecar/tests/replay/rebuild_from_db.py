"""One-off: rebuild a recorded scenario's cassettes from the recording run's ``llm_calls`` rows.

Usage (from ``sidecar/``)::

    uv run python tests/replay/rebuild_from_db.py <app.db> <cassette dir>

For a scenario whose cassettes were damaged after recording (for example by an old ``etach scrub``),
while the recording run's database still holds the originals. The ``NNN-<task>.json`` files and
the ``llm_calls`` rows are paired in order (``created_at``, then ``id``); each pair must have the
same count, status and prompt hash, or nothing is written. Each cassette keeps its task, match
key, status and meta; only ``response_text``, ``thinking_text`` and ``logprobs`` come from the
row. It writes no images and does not touch ``input.json`` or the stand-in pages.

The rebuilt cassettes hold the unscrubbed text: run ``etach scrub`` on the folder right after.
The database is opened read-only.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from etach.llm.cassettes import iter_cassette_files


class RebuildError(RuntimeError):
    pass


def _rows(db_path: Path) -> list[dict[str, Any]]:
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT id, status, prompt_hash, response_text, thinking_text, logprobs"
                " FROM llm_calls ORDER BY created_at, id"
            )
        ]
    finally:
        conn.close()


def rebuild(db_path: Path, folder: Path) -> list[Path]:
    """Rewrite every cassette under ``folder`` from ``db_path``; returns the files written."""
    files = iter_cassette_files(folder)
    rows = _rows(db_path)
    if len(files) != len(rows):
        raise RebuildError(f"{len(files)} cassettes but {len(rows)} llm_calls rows")
    out: list[tuple[Path, dict[str, Any]]] = []
    for path, row in zip(files, rows, strict=True):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["status"] != row["status"]:
            raise RebuildError(f"{path.name}: status {data['status']} != row {row['status']}")
        if data["meta"]["prompt_hash"] != row["prompt_hash"]:
            raise RebuildError(f"{path.name}: the prompt hash differs from row {row['id']}")
        logprobs = json.loads(row["logprobs"]) if row["logprobs"] else None
        data["response_text"] = row["response_text"] or ""
        data["thinking_text"] = row["thinking_text"] or ""
        data["logprobs"] = logprobs or None
        out.append((path, data))
    for path, data in out:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [p for p, _ in out]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        written = rebuild(Path(argv[0]), Path(argv[1]))
    except RebuildError as exc:
        print(f"rebuild_from_db: {exc}", file=sys.stderr)
        return 1
    print(f"rebuilt {len(written)} cassettes; now run etach scrub on {argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
