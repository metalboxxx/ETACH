"""The blind rating sheet for M2 (``etach eval --graph grade --rate-explanations``).

From two or more kept grade runs (``etach eval --graph grade --keep DIR``, each with another
reasoning model), :func:`write_sheet` writes into an output folder:

- ``rating-sheet.csv`` (UTF-8 with a BOM, so Excel shows Vietnamese text): one row per
  explanation, shuffled with a fixed seed. Columns: ``item``, ``fixture``, ``question``,
  ``question_text``, ``student_answer``, ``correct_answer``, ``explanation``, ``rating`` (empty;
  the teacher writes 1-5) and ``note`` (empty). No model name is in it.
- ``rating-key.json``: item → model tag (the hidden mapping), plus the seed and the runs.

:func:`score_sheet` reads the filled sheet back (``etach eval --score-ratings DIR``) and returns
plain lines per model tag: the mean rating, how many were rated, and the count of each score.
They hold no student text, so they can go into ``docs/initial-plan/phases-testing/m2-report.md``.

The output folder holds student text: it belongs under the gitignored ``fixtures/``.
"""

from __future__ import annotations

import csv
import io
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "KEY_NAME",
    "SHEET_COLUMNS",
    "SHEET_NAME",
    "RatingError",
    "collect_items",
    "score_sheet",
    "write_sheet",
]

SHEET_NAME = "rating-sheet.csv"
KEY_NAME = "rating-key.json"
SHEET_COLUMNS = (
    "item",
    "fixture",
    "question",
    "question_text",
    "student_answer",
    "correct_answer",
    "explanation",
    "rating",
    "note",
)
DEFAULT_SEED = 20261011
SCORES = (1, 2, 3, 4, 5)


class RatingError(ValueError):
    """A run folder or a filled sheet that cannot be used."""


@dataclass(frozen=True)
class _Item:
    model: str
    fixture: str
    question: str
    question_text: str
    student_answer: str
    correct_answer: str
    explanation: str


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RatingError(f"{path}: not readable ({exc})") from exc


def _run_model(run_dir: Path) -> tuple[str, list[Path]]:
    """The reasoning tag of a kept grade run and its set folders (``<set>/summary.json``)."""
    sets = sorted(p.parent for p in Path(run_dir).glob("*/summary.json"))
    runs = sorted(p for p in Path(run_dir).glob("run-*") if p.is_dir())
    if not sets and len(runs) == 1:  # a batch folder of the overnight script, with one run
        sets = sorted(p.parent for p in runs[0].glob("*/summary.json"))
    if not sets:
        raise RatingError(f"{run_dir}: no <set>/summary.json (not an `etach eval --keep` folder)")
    tags = set()
    for folder in sets:
        row = _read_json(folder / "summary.json")
        if row.get("graph") != "grade":
            raise RatingError(f"{folder}: not a grade run (graph={row.get('graph')!r})")
        tags.add(str(row.get("model_reasoning") or ""))
    if len(tags) != 1 or "" in tags:
        raise RatingError(f"{run_dir}: no single reasoning model in its summary.json")
    return tags.pop(), sets


def collect_items(run_dirs: Sequence[Path]) -> list[_Item]:
    """Every explanation of every run, in a stable order (run, set, fixture, question)."""
    if len(run_dirs) < 2:
        raise RatingError("give at least 2 kept grade runs (one per reasoning model)")
    items: list[_Item] = []
    seen: dict[str, Path] = {}
    for run_dir in run_dirs:
        model, sets = _run_model(run_dir)
        if model in seen:
            raise RatingError(f"{run_dir} and {seen[model]} both used {model}: one run per model")
        seen[model] = Path(run_dir)
        for folder in sets:
            for fx_dir in sorted(p for p in folder.iterdir() if p.is_dir()):
                path = fx_dir / "explanations.json"
                if not path.is_file():
                    continue
                for e in _read_json(path):
                    items.append(
                        _Item(
                            model=model,
                            fixture=f"{folder.name}/{fx_dir.name}",
                            question=str(e.get("question") or ""),
                            question_text=str(e.get("question_text") or ""),
                            student_answer=str(e.get("student_answer") or ""),
                            correct_answer=str(e.get("correct_answer") or ""),
                            explanation=str(e.get("explanation") or ""),
                        )
                    )
    return items


def write_sheet(run_dirs: Sequence[Path], out_dir: Path, *, seed: int = DEFAULT_SEED) -> int:
    """Write ``rating-sheet.csv`` and ``rating-key.json`` into ``out_dir``; returns the number
    of items. The same runs and seed give the same sheet."""
    items = collect_items(run_dirs)
    if not items:
        raise RatingError("the runs hold no explanations (no wrong answers were explained)")
    random.Random(seed).shuffle(items)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    width = max(3, len(str(len(items))))
    key: dict[str, str] = {}
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(SHEET_COLUMNS)
    for i, item in enumerate(items, start=1):
        name = f"E{i:0{width}d}"
        key[name] = item.model
        writer.writerow(
            [
                name,
                item.fixture,
                item.question,
                item.question_text,
                item.student_answer,
                item.correct_answer,
                item.explanation,
                "",
                "",
            ]
        )
    (out_dir / SHEET_NAME).write_bytes(buf.getvalue().encode("utf-8-sig"))
    (out_dir / KEY_NAME).write_text(
        json.dumps(
            {"seed": seed, "runs": [str(p) for p in run_dirs], "items": key},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return len(items)


def _decode(data: bytes) -> str:
    """UTF-8 (with or without a BOM); a sheet Excel saved in the Windows code page still
    gives its item and rating columns."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _delimiter(first_line: str) -> str:
    counts = {d: first_line.count(d) for d in (",", ";", "\t")}
    return max(counts, key=lambda d: counts[d])


def score_sheet(folder: Path) -> list[str]:
    """Read the filled ``rating-sheet.csv`` with ``rating-key.json``; return the summary lines.

    A rating is a whole number 1-5 (``4``, ``4.0``); empty = not rated. Anything else, an
    unknown item or a missing column raises :class:`RatingError` naming the items."""
    folder = Path(folder)
    key = _read_json(folder / KEY_NAME).get("items") or {}
    try:
        text = _decode((folder / SHEET_NAME).read_bytes())
    except OSError as exc:
        raise RatingError(f"{folder / SHEET_NAME}: not readable ({exc})") from exc
    lines = text.splitlines()
    if not lines:
        raise RatingError(f"{folder / SHEET_NAME}: empty")
    reader = csv.DictReader(io.StringIO(text), delimiter=_delimiter(lines[0]))
    fields = [f.strip().lower() for f in reader.fieldnames or []]
    if "item" not in fields or "rating" not in fields:
        raise RatingError(f"{folder / SHEET_NAME}: no 'item' and 'rating' columns")
    ratings: dict[str, list[int]] = {m: [] for m in sorted(set(key.values()))}
    unrated: dict[str, int] = dict.fromkeys(ratings, 0)
    bad: list[str] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for raw in reader:
        row = {str(k).strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        item = row.get("item", "")
        if not item:
            continue
        if item not in key or item in seen:
            unknown.append(item)
            continue
        seen.add(item)
        model = key[item]
        value = row.get("rating", "").replace(",", ".")
        if not value:
            unrated[model] += 1
            continue
        try:
            number = float(value)
        except ValueError:
            bad.append(item)
            continue
        if number != int(number) or int(number) not in SCORES:
            bad.append(item)
            continue
        ratings[model].append(int(number))
    if unknown:
        raise RatingError(f"unknown or repeated item(s) in the sheet: {', '.join(unknown)}")
    if bad:
        raise RatingError(f"rating not a whole number 1-5: {', '.join(bad)}")
    missing = sorted(set(key) - seen)
    out = [f"Blind explanation ratings: {len(key)} items, {len(seen)} in the sheet"]
    if missing:
        out.append(f"- items missing from the sheet: {len(missing)}")
    for model, values in ratings.items():
        n = len(values)
        mean = f"{sum(values) / n:.2f}" if n else "-"
        per = ", ".join(f"{s}: {values.count(s)}" for s in SCORES)
        out.append(
            f"- reasoning={model}: mean {mean}, {n} rated ({unrated[model]} not rated);"
            f" per score {per}"
        )
    return out
