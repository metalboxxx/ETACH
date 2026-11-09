"""Render the phase-0 live run as ``docs/initial-plan/phases-testing/phase0-live-output.txt``.

R5.2.

It reads ``_out/phase0-results.json`` (the records the live tests wrote) and
``_out/pytest-summary.json`` (each live test's outcome, written by ``conftest.py``)::

    cd sidecar
    uv run python tests/live/render_output.py \
        --out ../docs/initial-plan/phases-testing/phase0-live-output.txt

Without ``--out`` the text goes to stdout. The file is UTF-8 with ``\\n`` line ends.
``--check-cassettes tests/cassettes/phase0`` instead counts the recorded cassettes (R5.4).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

OUT_DIR = Path(__file__).resolve().parent / "_out"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(
            f"{path} is missing: run the live tests first"
            " (see docs/initial-plan/phases-testing/phase0-report.md)"
        )
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    cells = [[_fmt(c) for c in row] for row in rows]
    widths = [max([len(h)] + [len(r[i]) for r in cells]) for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))
    out = [line.rstrip(), "  ".join("-" * w for w in widths)]
    out += ["  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip() for r in cells]
    return out


def _get(record: dict[str, Any], *path: str) -> Any:
    value: Any = record
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _section(title: str, records: list[dict[str, Any]], body: list[str]) -> list[str]:
    head = [f"== {title} =="]
    if not records:
        return [*head, "(no records: the test was skipped or did not run)", ""]
    return [*head, *body, ""]


def _item1(records: list[dict[str, Any]]) -> list[str]:
    rows = []
    notes = []
    for r in records:
        if r.get("skipped"):
            notes.append(f"{r['case']}: skipped ({r['skipped']})")
            continue
        lp = r.get("logprobs") or {}
        rows.append(
            [
                r["case"],
                r.get("model"),
                r.get("request_has_format"),
                r.get("think"),
                "/".join(r.get("statuses") or []),
                r.get("valid"),
                lp.get("count"),
                lp.get("with_top_logprobs"),
                lp.get("top_logprobs_sizes"),
                r.get("logprobs_cover"),
                "; ".join(lp.get("missing") or []) or "nothing",
            ]
        )
    headers = [
        "case", "model", "format", "think", "statuses", "valid", "logprobs", "with top",
        "top sizes", "covers", "missing",
    ]  # fmt: skip
    return _table(headers, rows) + notes


def _item2(records: list[dict[str, Any]]) -> list[str]:
    rows = [
        [
            r["case"],
            "/".join(r.get("statuses") or []),
            r.get("valid"),
            r.get("parsed"),
            r.get("answers_correct"),
            _get(r, "logprobs", "count"),
            r.get("failure"),
        ]
        for r in records
    ]
    return _table(["shape", "statuses", "valid", "parsed", "correct", "logprobs", "failure"], rows)


def _item3(records: list[dict[str, Any]]) -> list[str]:
    rows = []
    for r in records:
        q1 = r.get("q1_tokens") or {}
        tokens = q1.get("tokens") or []
        rows.append(
            [
                r["case"],
                r.get("model"),
                q1.get("value"),
                [t.get("token") for t in tokens],
                q1.get("single_token"),
                tokens[0].get("choice_probs") if tokens else None,
                tokens[0].get("other_alternatives") if tokens else q1.get("note"),
            ]
        )
    return _table(
        ["case", "model", "q1", "tokens", "single", "A-D probs (1st token)", "other alts"], rows
    )


def _speed_rows(records: list[dict[str, Any]]) -> list[list[Any]]:
    rows = []
    for r in records:
        smi = _get(r, "vram", "nvidia_smi") or {}
        rows.append(
            [
                r.get("role"),
                r.get("model"),
                r.get("num_ctx"),
                _get(r, "vram", "context_length"),
                _get(r, "timing", "load_s"),
                _get(r, "timing", "prompt_tok_per_s"),
                _get(r, "timing", "eval_tok_per_s"),
                _get(r, "timing", "eval_tokens"),
                _get(r, "vram", "size_mib"),
                _get(r, "vram", "size_vram_mib"),
                _get(r, "vram", "gpu_share"),
                _get(r, "vram", "fully_on_gpu"),
                f"{smi.get('used_mib', '-')}/{smi.get('total_mib', '-')}",
                r.get("valid"),
                r.get("error"),
            ]
        )
    return rows


_SPEED_HEADERS = [
    "role", "model", "num_ctx", "ctx (ps)", "load s", "prompt tok/s", "eval tok/s", "tokens",
    "size MiB", "VRAM MiB", "GPU share", "all on GPU", "smi MiB", "valid", "error",
]  # fmt: skip


def _item5(records: list[dict[str, Any]]) -> list[str]:
    out = _table(_SPEED_HEADERS, _speed_rows(records))
    for r in records:
        out.append(f"{r.get('role')}: vs baseline {_fmt(r.get('vs_baseline'))}")
        out.append(f"{r.get('role')}: answers {_fmt(r.get('answers'))}")
        for line in r.get("server_log") or []:
            out.append(f"{r.get('role')}: server log | {line}")
    return out


def _item6(records: list[dict[str, Any]]) -> list[str]:
    rows = [
        [s.get("n"), s.get("role"), s.get("model"), s.get("load_s"), s.get("wall_s"),
         s.get("valid"), s.get("loaded_after")]
        for r in records
        for s in r.get("steps") or []
    ]  # fmt: skip
    return _table(["#", "role", "model", "load s", "wall s", "valid", "loaded after"], rows)


def render(results: dict[str, Any], summary: dict[str, Any]) -> str:
    meta = results.get("meta", {})
    records: list[dict[str, Any]] = results.get("records", [])

    def of(item: int) -> list[dict[str, Any]]:
        return [r for r in records if r.get("item") == item]

    counts = summary.get("counts", {})
    gpu = meta.get("gpu_before") or {}
    lines = [
        "Phase 0 live output - ETACH (plan step 5)",
        f"Rendered: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"Run: started {meta.get('started_at')}, finished {summary.get('finished_at')}",
        f"Command: pytest {' '.join(summary.get('args', []))}",
        f"Ollama: {meta.get('ollama_version')} ({meta.get('ollama_exe')})",
        f"Models folder: {meta.get('models_dir')}",
        f"Private server env: {_fmt(meta.get('server_env'))}",
        f"GPU: {gpu.get('name')} {gpu.get('total_mib')} MiB, driver {gpu.get('driver')},"
        f" {gpu.get('used_mib')} MiB used before the run",
        f"Other Ollama on 11434 had a model loaded: {_fmt(meta.get('other_ollama_11434_loaded'))}",
        f"Cassette recording: {_fmt(meta.get('record'))} ({meta.get('cassette_dir')})",
        f"Platform: {meta.get('platform')}, Python {meta.get('python')}",
        "",
        "== Roles ==",
        *[
            f"{name}: {r.get('model')} (adapter {r.get('adapter')},"
            f" options {_fmt(r.get('options'))})"
            f" pulled: {_fmt(r.get('present'))}"
            for name, r in (meta.get("roles") or {}).items()
        ],
        "",
        "== pytest summary ==",
        f"{counts.get('passed', 0)} passed, {counts.get('failed', 0)} failed,"
        f" {counts.get('skipped', 0)} skipped, {counts.get('error', 0)} errors"
        f" (exit status {summary.get('exitstatus')})",
        *[
            f"{t.get('outcome', '?').upper():8} {t['nodeid']} ({t.get('duration_s')} s)"
            + (f" - {t['reason']}" if t.get("reason") else "")
            for t in summary.get("tests", [])
        ],
        "",
    ]
    lines += _section(
        "Item 1 - logprobs with format, with an image, with both", of(1), _item1(of(1))
    )
    lines += _section(
        "Item 2 - NuExtract3 template alone vs template + format", of(2), _item2(of(2))
    )
    lines += _section("Item 3 - the MCQ letter is a single token", of(3), _item3(of(3)))
    lines += _section(
        "Item 4 - VRAM and speed per role model (baseline: flash attention 0, KV f16)",
        of(4),
        _table(_SPEED_HEADERS, _speed_rows(of(4))),
    )
    lines += _section("Item 5 - flash attention 1 + KV cache q8_0", of(5), _item5(of(5)))
    lines += _section("Item 6 - swap time, OLLAMA_MAX_LOADED_MODELS=1", of(6), _item6(of(6)))
    lines += [
        "== Records (JSON, as the tests wrote them) ==",
        json.dumps(records, ensure_ascii=False, indent=1),
        "",
    ]
    return "\n".join(lines)


def check_cassettes(folder: Path) -> int:
    """R5.4 by count: >= 3 cassettes with non-empty logprobs, at least one with an image input
    (the task name ends in ``_image``). Exit 0 when met, 1 otherwise."""
    files = sorted(folder.glob("*.json"))
    rows, with_lp, with_image = [], 0, 0
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        n = len(data.get("logprobs") or [])
        image = str(data.get("task", "")).endswith("_image")
        with_lp += n > 0
        with_image += n > 0 and image
        rows.append([f.name, data.get("status"), n, image])
    for line in _table(["file", "status", "logprobs", "image"], rows):
        print(line)
    ok = with_lp >= 3 and with_image >= 1
    print(
        f"{len(files)} cassettes, {with_lp} with logprobs, {with_image} of them with an image:"
        f" R5.4 count {'met' if ok else 'NOT met'}"
    )
    return 0 if ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, default=OUT_DIR / "phase0-results.json")
    parser.add_argument("--summary", type=Path, default=OUT_DIR / "pytest-summary.json")
    parser.add_argument("--out", type=Path, default=None, help="output file (default: stdout)")
    parser.add_argument(
        "--check-cassettes",
        type=Path,
        default=None,
        metavar="DIR",
        help="instead: count the cassettes in DIR against R5.4",
    )
    args = parser.parse_args(argv)
    if args.check_cassettes is not None:
        return check_cassettes(args.check_cassettes)
    text = render(_load(args.results), _load(args.summary))
    if args.out is None:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        sys.stdout.write(text)
    else:
        args.out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
