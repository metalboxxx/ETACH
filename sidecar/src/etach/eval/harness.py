"""``etach eval``: run a graph over a fixture set and append one row to ``eval-history.csv``.

For each fixture of the set, the extract graph runs into a fresh temporary data folder (live, or
replaying cassettes), the saved test, answers and keys are read back and compared with
``expected.json`` (:mod:`etach.eval.metrics`), and the counts are added up over the fixtures. The
row holds metrics, model tags and prompt hashes only: never student data (no names, no answers,
no fixture names).

``--replay DIR``: the cassettes of fixture ``<set>/<name>`` are looked for in
``DIR/<set>/<name>``, then ``DIR/<name>``, then ``DIR`` itself.

``--tiles`` turns ``[extract] retranscribe_tiles`` on for the run (off by default since speed
bundle 1) and adds ``+tiles`` to the row's ``mode``.

``--photo-reader vision|ocr`` sets ``[extract] photo_reader`` for the run (default ``ocr`` since
R22.5.7.7); a run with the OCR reader adds ``+ocr`` to the row's ``mode``.

``--photo-structure qwen|code|ocr_format`` sets ``[extract] photo_structure`` for the run
(step 22.6.5, OCR reader only; default ``code`` since step 22.6.6, D16); ``code`` or
``ocr_format`` is added to the row's ``mode`` after ``+ocr`` (``replay+ocr+code``).

``--keep DIR`` (M1 tuning) also writes, as each fixture finishes, ``DIR/<set>/<name>/``:
``test.json`` (the saved test), ``answers.json`` (the answers read, with ``confidence`` and
``reading_unsure``), ``keys.json``, ``metrics.json`` (that fixture's own metrics under the
CSV's column names, the raw counts, the per-question mismatches, the per-node usage and
``call_status``, the call statuses per node),
``llm_calls.json`` (every model call of the run, in order: node, page item (a tile call: its own
``"p2 top"``; ``step_item`` keeps the step's), statuses, tokens,
timing, the stored request and the raw response; no logprobs) and ``pages.json`` (the parsed
per-page results of the page tasks before merge: each complete ``transcribe_page``,
``retranscribe_tiles``, ``read_answers_page`` and ``read_key_pages`` call). The last two exist
because the run's data folder is deleted afterwards (B4). At the end it writes
``DIR/<set>/summary.json``, the CSV row. These files hold student text, so ``DIR`` goes under
the gitignored ``fixtures/`` (``fixtures/_runs/``).
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from etach.eval.fixtures import Fixture
from etach.eval.metrics import (
    AnswerCounts,
    CalibrationCounts,
    KeyCounts,
    NodeUsage,
    NumberCounts,
    Ratio,
    ReadAnswer,
    ReadKey,
    SimpleGroup,
    SimpleQuestion,
    SimpleSection,
    StructureCounts,
    answer_counts,
    calibration_counts,
    key_counts,
    number_counts,
    question_keys,
    structure_counts,
)
from etach.graphs.extract import C1_NODES
from etach.graphs.grade import C2_NODES

__all__ = [
    "COLUMNS",
    "GRADE_COLUMNS",
    "GRADE_NODES",
    "NUMBER_COLUMNS",
    "FixtureResult",
    "Saved",
    "aggregate_row",
    "append_history",
    "default_history_path",
    "evaluate_saved",
    "fixture_metrics",
    "form_report",
    "mismatches",
    "pad_history",
    "page_results",
    "run_calls",
    "run_extract_fixture",
    "write_kept_fixture",
    "write_summary",
]

REPO_ROOT = Path(__file__).resolve().parents[4]
HISTORY_NAME = "eval-history.csv"
META_FIELDS = ("occasion", "grade", "term", "test_number", "variant", "school", "year")
NODE_FIELDS = ("tokens_in", "tokens_out", "calls", "ms")

#: The grade nodes that have no column of their own yet (``save`` shares the extract one).
#: ``difficulty_notes`` left the graph in step 22.5.4; its columns stay in the header, empty in
#: newer rows, so the committed history keeps its shape.
_RETIRED_AFTER = {"tag_skills": "difficulty_notes"}
GRADE_NODES: tuple[str, ...] = tuple(
    name
    for n in C2_NODES
    if n not in C1_NODES
    for name in (n, *([_RETIRED_AFTER[n]] if n in _RETIRED_AFTER else []))
)

#: The columns the grade eval added (M2), appended at the end of the header; they stay empty in
#: extract rows. See :mod:`etach.eval.grade` for their meaning.
GRADE_COLUMNS: tuple[str, ...] = (
    "key_accuracy_fast",
    "key_uncertain_n",
    "verdict_n",
    "verdict_uncertain_n",
    "verdict_no_truth_n",
    "judge_accuracy",
    "judge_n",
    "score_n",
    *(f"{node}_{f}" for node in GRADE_NODES for f in NODE_FIELDS),
)

#: Answer-number errors (step 22.5.7, :class:`~etach.eval.metrics.NumberCounts`), appended after
#: the grade columns: error rates over the questions aligned by content; empty in grade rows.
NUMBER_COLUMNS: tuple[str, ...] = ("number_renumbering_errors", "number_reading_errors")

#: The CSV header, in order. A new column is a new header: ``append_history`` rewrites the
#: header of a file that has no data rows yet, pads the rows of a file whose header is an
#: older prefix of this one (new columns are only ever appended), and refuses any other header.
COLUMNS: tuple[str, ...] = (
    "timestamp",
    "commit",
    "graph",
    "set",
    "mode",
    "n_fixtures",
    "n_failed",
    "model_vision",
    "model_reasoning",
    "prompt_digest",
    "prompt_hashes",
    "cer",
    "stimulus_cer",
    "structure_overall",
    *(f"structure_{d}" for d in StructureCounts.DIMENSIONS),
    "meta_accuracy",
    "answer_accuracy",
    "answer_n",
    "calibration",
    "calibration_lo",
    "calibration_hi",
    "calibration_wrong_n",
    "flagged_correct_rate",
    "key_accuracy",
    "key_n",
    "key_mapping_accuracy",
    "key_mapping_n",
    "verdict_accuracy",
    "score_exact_match",
    "vram_peak_mb",
    "wall_s",
    "total_tokens_in",
    "total_tokens_out",
    "total_calls",
    "total_node_ms",
    *(f"{node}_{f}" for node in C1_NODES for f in NODE_FIELDS),
    *GRADE_COLUMNS,
    *NUMBER_COLUMNS,
)


# --- one fixture -----------------------------------------------------------------------------


@dataclass
class Saved:
    """What one run saved (written out by ``--keep``)."""

    test: Any | None = None
    answers: list[Any] = field(default_factory=list)
    keys: list[Any] = field(default_factory=list)


@dataclass
class FixtureResult:
    status: str
    structure: StructureCounts = field(default_factory=StructureCounts)
    numbers: NumberCounts = field(default_factory=NumberCounts)
    meta: Ratio = field(default_factory=Ratio)
    answers: AnswerCounts = field(default_factory=AnswerCounts)
    calibration: CalibrationCounts = field(default_factory=CalibrationCounts)
    keys: KeyCounts = field(default_factory=KeyCounts)
    usage: dict[str, NodeUsage] = field(default_factory=dict)
    tasks: set[str] = field(default_factory=set)
    wall_s: float = 0.0
    saved: Saved | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)  # ``--keep`` only (B4)


def _simple_sections(test: Any) -> list[SimpleSection]:
    return [
        SimpleSection(
            printed_title=s.printed_title,
            skill=s.skill,
            groups=[
                SimpleGroup(
                    stimulus=g.stimulus,
                    questions=[
                        SimpleQuestion(
                            printed_number=q.printed_number,
                            answer_form=q.answer_form,
                            stem=q.stem,
                            options=None if q.options is None else [o.text for o in q.options],
                            cue=q.cue,
                            page_no=q.page_no,
                            number=q.number,
                        )
                        for q in g.questions
                    ],
                )
                for g in s.groups
            ],
            graded=s.graded,
        )
        for s in test.content.sections
    ]


def _question_ids(test: Any) -> dict[str, str]:
    """question_id → question key, in the test's stored order."""
    qs = [q for s in test.content.sections for g in s.groups for q in g.questions]
    return dict(zip((q.id for q in qs), question_keys(q.printed_number for q in qs), strict=True))


def _expected_key(fx: Fixture) -> Mapping[str, Sequence[str]] | None:
    """The key entries the extract graph is measured on: on this graph the key comes only from
    🔑 key pages (llm-design §8 "key accuracy, key mapping accuracy (🔑 photos)"), so a fixture
    with no key page counts nothing and ``key_accuracy`` stays blank, like ``key_mapping``."""
    return fx.expected.key if fx.has_key_photo else None


def evaluate_saved(
    fx: Fixture,
    *,
    status: str,
    test: Any | None,
    answers: list[Any],
    keys: list[Any],
) -> FixtureResult:
    """Compare what one run saved with the fixture's ``expected.json`` (no usage)."""
    exp = fx.expected
    out = FixtureResult(status=status)
    actual_sections = [] if test is None else _simple_sections(test)
    ids = {} if test is None else _question_ids(test)
    out.structure = structure_counts(exp.stored_sections(), actual_sections)
    out.numbers = number_counts(exp.stored_sections(), actual_sections)
    meta_exp = exp.meta.model_dump()
    for name in META_FIELDS:
        want = meta_exp.get(name)
        if want is None:
            continue
        got = None if test is None else getattr(test.meta, name, None)
        out.meta.count(str(want).strip().lower() == str(got).strip().lower())
    read = _read_answers(ids, answers)
    out.answers = answer_counts(exp.answers, read)
    out.calibration = calibration_counts(exp.answers, read)
    out.keys = key_counts(_expected_key(fx), _read_keys(ids, keys), has_key_photo=fx.has_key_photo)
    out.saved = Saved(test=test, answers=list(answers), keys=list(keys))
    return out


def _read_answers(ids: Mapping[str, str], answers: list[Any]) -> dict[str, ReadAnswer]:
    return {
        ids[a.question_id]: ReadAnswer(a.value, a.reading_unsure)
        for a in answers
        if a.question_id in ids
    }


def _read_keys(ids: Mapping[str, str], keys: list[Any]) -> dict[str, ReadKey]:
    return {
        ids[k.question_id]: ReadKey(list(k.accepted), k.source == "from_key_photo")
        for k in keys
        if k.question_id in ids
    }


# --- --keep: the per-fixture outputs -----------------------------------------------------------

#: The structure dimensions checked per matched question (the rest are per section or count).
_QUESTION_DIMS = ("types", "option_count", "option_text", "blanks", "underline", "bold")


def _question_dict(q: SimpleQuestion) -> dict[str, Any]:
    return {
        "printed_number": q.printed_number,
        "answer_form": q.answer_form,
        "stem": q.stem,
        "options": q.options,
        "cue": q.cue,
        "page_no": q.page_no,
    }


def _keyed_questions(sections: list[SimpleSection]) -> dict[str, SimpleQuestion]:
    qs = [q for s in sections for q in s.questions]
    return dict(zip(question_keys(q.printed_number for q in qs), qs, strict=True))


def mismatches(fx: Fixture, saved: Saved) -> dict[str, Any]:
    """Which questions a run got wrong, expected vs got (the details behind the metrics).

    - ``sections``: the expected and the read section titles with their question counts;
    - ``structure``: per expected question, ``missing`` or the failed dimensions (``types``,
      ``option_count``, ``option_text``, ``blanks``, ``underline``, ``bold``) and its text CER,
      listed when anything differs; ``extra_questions``: read keys that are not expected;
    - ``answers``: wrong readings (expected, got, ``reading_unsure``, ``confidence``);
      ``flagged_correct``: right readings flagged ``?``;
    - ``keys``: key entries whose accepted set differs."""
    exp = fx.expected
    test = saved.test
    exp_sections = exp.stored_sections()
    act_sections = [] if test is None else _simple_sections(test)
    exp_q = _keyed_questions(exp_sections)
    act_q = _keyed_questions(act_sections)
    structure: list[dict[str, Any]] = []
    for key, e in exp_q.items():
        a = act_q.get(key)
        if a is None:
            structure.append(
                {
                    "question": key,
                    "problems": ["missing"],
                    "text_cer": 1.0,
                    "expected": _question_dict(e),
                    "got": None,
                }
            )
            continue
        c = structure_counts([SimpleSection.flat("", [e])], [SimpleSection.flat("", [a])])
        problems = [d for d in _QUESTION_DIMS if getattr(c, d).hits < getattr(c, d).total]
        if problems or c.text.edits:
            structure.append(
                {
                    "question": key,
                    "problems": problems,
                    "text_cer": None if c.text.value is None else round(c.text.value, 4),
                    "expected": _question_dict(e),
                    "got": _question_dict(a),
                }
            )
    ids = {} if test is None else _question_ids(test)
    by_key = {ids[a.question_id]: a for a in saved.answers if a.question_id in ids}
    read = _read_answers(ids, saved.answers)
    wrong: list[dict[str, Any]] = []
    flagged_correct: list[str] = []
    for key, want in exp.answers.items():
        got = read.get(key)
        ok = answer_counts({key: want}, {} if got is None else {key: got}).accuracy.hits == 1
        if ok:
            if got is not None and got.reading_unsure:
                flagged_correct.append(key)
            continue
        answer = by_key.get(key)
        wrong.append(
            {
                "question": key,
                "expected": want,
                "got": None if got is None else got.value,
                "read": answer is not None,
                "reading_unsure": bool(got is not None and got.reading_unsure),
                "confidence": None if answer is None else answer.confidence,
            }
        )
    key_wrong: list[dict[str, Any]] = []
    read_keys = _read_keys(ids, saved.keys)
    for key, accepted in (exp.key or {}).items():
        got_key = read_keys.get(key)
        single = {} if got_key is None else {key: got_key}
        counted = key_counts({key: accepted}, single, has_key_photo=fx.has_key_photo)
        if counted.accuracy.hits < counted.accuracy.total:
            key_wrong.append(
                {
                    "question": key,
                    "expected": list(accepted),
                    "got": None if got_key is None else got_key.accepted,
                    "from_key_photo": None if got_key is None else got_key.from_key_photo,
                }
            )
    return {
        "sections": {
            "expected": [[s.printed_title, len(s.questions)] for s in exp_sections],
            "got": [[s.printed_title, len(s.questions)] for s in act_sections],
        },
        "structure": structure,
        "extra_questions": [k for k in act_q if k not in exp_q],
        "answers": wrong,
        "flagged_correct": flagged_correct,
        "keys": key_wrong,
    }


#: The metric columns of a fixture's own ``metrics.json`` (no identity, VRAM or per-node columns).
_FIXTURE_METRIC_COLUMNS = tuple(
    c
    for c in COLUMNS[COLUMNS.index("cer") : COLUMNS.index("total_node_ms") + 1]
    if c not in ("verdict_accuracy", "score_exact_match", "vram_peak_mb")
)


def fixture_metrics(fx: Fixture, result: FixtureResult) -> dict[str, str]:
    """One fixture's metrics, computed and formatted exactly as the CSV row is."""
    row = aggregate_row([result], graph="extract", set_name=fx.set, mode="", models={}, commit="")
    return {c: row[c] for c in _FIXTURE_METRIC_COLUMNS}


def _dump(obj: Any) -> Any:
    return obj.model_dump(mode="json") if hasattr(obj, "model_dump") else obj


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


#: The page tasks whose complete responses ``pages.json`` holds (the results before merge).
#: ``structure_text_page`` (D5) runs in the ``transcribe_page`` node; it is listed for a call
#: matched by its task name.
PAGE_TASKS = (
    "transcribe_page",
    "structure_text_page",
    "retranscribe_tiles",
    "read_answers_page",
    "read_key_pages",
)


def run_calls(conn: Any, run_id: str) -> list[dict[str, Any]]:
    """Every ``llm_calls`` row of a run with its step, in step and call order (B4)."""
    from etach.store.repos import runs

    out: list[dict[str, Any]] = []
    for step in runs.list_steps(conn, run_id):
        for call in runs.list_llm_calls(conn, step.id):
            out.append(
                {
                    "node": step.node,
                    # the call's own label when it has one (a tile: "p2 top"), else the step's
                    "item": (call.request or {}).get("item") or step.item,
                    "step_item": step.item,
                    "try_no": step.try_no,
                    "step_status": step.status,
                    "call_id": call.id,
                    "status": call.status,
                    "role": call.role,
                    "model": call.model,
                    "prompt_hash": call.prompt_hash,
                    "tokens_in": call.tokens_in,
                    "tokens_out": call.tokens_out,
                    "ms": call.ms,
                    "created_at": call.created_at.isoformat(),
                    "logprob_count": len(call.logprobs or []),
                    "request": call.request,
                    "response_text": call.response_text,
                    "thinking_text": call.thinking_text,
                }
            )
    return out


def page_results(calls: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The parsed response of each complete page-task call (``result`` None if not JSON)."""
    out: list[dict[str, Any]] = []
    for c in calls:
        if c["node"] not in PAGE_TASKS or c["status"] != "complete":
            continue
        try:
            parsed = json.loads(c["response_text"])
        except ValueError:
            parsed = None
        out.append(
            {"node": c["node"], "item": c["item"], "call_id": c["call_id"], "result": parsed}
        )
    return out


def _call_status(calls: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    """node → call status → count."""
    out: dict[str, dict[str, int]] = {}
    for c in calls:
        by_status = out.setdefault(c["node"], {})
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    return out


def write_kept_fixture(folder: Path, fx: Fixture, result: FixtureResult) -> None:
    """Write ``test.json``, ``answers.json``, ``keys.json``, ``metrics.json``,
    ``llm_calls.json`` and ``pages.json`` into ``folder``."""
    folder.mkdir(parents=True, exist_ok=True)
    saved = result.saved or Saved()
    ids = {} if saved.test is None else _question_ids(saved.test)
    _write_json(folder / "test.json", None if saved.test is None else _dump(saved.test))
    _write_json(
        folder / "answers.json",
        [{"question": ids.get(a.question_id), **_dump(a)} for a in saved.answers],
    )
    _write_json(
        folder / "keys.json",
        [{"question": ids.get(k.question_id), **_dump(k)} for k in saved.keys],
    )
    _write_json(
        folder / "metrics.json",
        {
            "fixture": f"{fx.set}/{fx.name}",
            "status": result.status,
            "wall_s": round(result.wall_s, 1),
            "metrics": fixture_metrics(fx, result),
            "counts": {
                "structure": asdict(result.structure),
                "meta": asdict(result.meta),
                "answers": asdict(result.answers),
                "calibration": asdict(result.calibration),
                "keys": asdict(result.keys),
            },
            "mismatches": mismatches(fx, saved),
            "usage": {node: asdict(u) for node, u in result.usage.items()},
            # e.g. "error" counts the prompt_truncated failures (B1); details in llm_calls.json
            "call_status": _call_status(result.calls),
        },
    )
    _write_json(folder / "llm_calls.json", result.calls)
    _write_json(folder / "pages.json", page_results(result.calls))


def write_summary(folder: Path, row: Mapping[str, str]) -> Path:
    """``folder/summary.json``: the set's CSV row, the same values."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "summary.json"
    _write_json(path, {c: row.get(c, "") for c in COLUMNS})
    return path


def _usage(conn: Any, run_id: str) -> tuple[dict[str, NodeUsage], set[str]]:
    from etach.store.repos import runs

    usage: dict[str, NodeUsage] = {}
    tasks: set[str] = set()
    for step in runs.list_steps(conn, run_id):
        u = NodeUsage()
        if step.finished_at is not None:
            u.ms = int((step.finished_at - step.started_at).total_seconds() * 1000)
        for call in runs.list_llm_calls(conn, step.id):
            u.calls += 1
            u.tokens_in += call.tokens_in or 0
            u.tokens_out += call.tokens_out or 0
            tasks.add(step.node)
        usage[step.node] = usage.get(step.node, NodeUsage()).add(u)
    return usage, tasks


def _write_models_toml(
    paths: Any,
    roles: Mapping[str, str],
    *,
    tiles: bool = False,
    photo_reader: str | None = None,
    photo_structure: str | None = None,
) -> None:
    """The run's ``models.toml``: the ``--role`` tags, ``[extract] retranscribe_tiles``
    with ``--tiles`` (off by default, speed bundle 1) and ``photo_reader`` with
    ``--photo-reader`` (R22.5.7.7)."""
    lines = []
    for role, tag in sorted(roles.items()):
        lines += [f"[roles.{role}]", f"model = {json.dumps(tag)}", ""]
    extract = ["retranscribe_tiles = true"] if tiles else []
    if photo_reader is not None:
        extract.append(f"photo_reader = {json.dumps(photo_reader)}")
    if photo_structure is not None:
        extract.append(f"photo_structure = {json.dumps(photo_structure)}")
    if extract:
        lines += ["[extract]", *extract, ""]
    if lines:
        paths.models_toml.write_text("\n".join(lines), encoding="utf-8")


async def run_extract_fixture(
    fx: Fixture,
    data_dir: Path,
    *,
    backend: Any | None,
    base_url: str | None,
    roles: Mapping[str, str],
    keep_calls: bool = False,
    tiles: bool = False,
    photo_reader: str | None = None,
    photo_structure: str | None = None,
) -> FixtureResult:
    """Run the extract graph on one fixture into ``data_dir`` (fresh) and compare; with
    ``keep_calls``, also read the run's model calls into ``result.calls`` (B4); ``tiles``
    turns ``retranscribe_tiles`` on for this run; ``photo_reader`` sets
    ``[extract] photo_reader``."""
    from etach.cli import _manager, _open_data, _wait_owned
    from etach.domain.models import ExtractInput
    from etach.store import db, documents
    from etach.store.files import FileStore
    from etach.store.repos import attempts, keys, runs, threads
    from etach.store.repos import tests as test_repo

    started = time.monotonic()
    paths = _open_data(data_dir)
    _write_models_toml(
        paths, roles, tiles=tiles, photo_reader=photo_reader, photo_structure=photo_structure
    )
    conn = db.connect(paths.db)
    try:
        files = FileStore(conn, paths)
        pages = []
        for page in fx.input.pages:
            path = fx.pages_dir / page.file
            for p in documents.ingest(files, path.read_bytes(), path.name):
                pages.append(
                    p.model_copy(update={"rotation": page.rotation, "is_key": page.is_key})
                )
        if fx.input.existing_test_id:
            print(
                f"etach eval: {fx.set}/{fx.name}: existing_test_id is ignored (fresh data folder)",
                file=sys.stderr,
            )
        inp = ExtractInput(pages=pages, existing_test_id=None, supersedes_attempt_id=None)
        thread_id = threads.create_thread(conn, "etach eval").id
        async with _manager(paths, backend, base_url) as manager:
            run = await manager.submit(thread_id, "extract", inp)
            await _wait_owned(manager, run.id)
        final = runs.get_run(conn, run.id)
        status = final.status if final is not None else "missing"
        if final is not None and final.error:
            print(f"etach eval: {fx.set}/{fx.name}: {final.error}", file=sys.stderr)
        test = test_repo.find_by_source_run(conn, run.id)
        attempt = attempts.find_by_source_run(conn, run.id)
        result = evaluate_saved(
            fx,
            status=status,
            test=test,
            answers=[] if attempt is None else attempts.list_answers(conn, attempt.id),
            keys=[] if test is None else keys.list_keys(conn, test.id),
        )
        result.usage, result.tasks = _usage(conn, run.id)
        if keep_calls:
            result.calls = run_calls(conn, run.id)
    finally:
        conn.close()
    result.wall_s = time.monotonic() - started
    return result


# --- the row ---------------------------------------------------------------------------------


def _fmt(value: float | int | None, digits: int = 4) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}f}"


def prompt_hashes(tasks: set[str]) -> str:
    """``task=<sha256[:12]>`` of each used task's base prompt + the generic profile, sorted."""
    from etach.prompts.render import FilePromptProvider, PromptNotFound

    provider = FilePromptProvider()
    parts = []
    for task in sorted(tasks):
        try:
            text = provider.base_text(task) + "\n\x00\n" + provider.profile_text(None)
        except PromptNotFound:
            continue
        parts.append(f"{task}={hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}")
    return ";".join(parts)


def git_commit(cwd: Path = REPO_ROOT) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError:
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def aggregate_row(
    results: list[FixtureResult],
    *,
    graph: str,
    set_name: str,
    mode: str,
    models: Mapping[str, str],
    vram_mb: float | None = None,
    commit: str | None = None,
    now: datetime | None = None,
) -> dict[str, str]:
    structure = StructureCounts()
    numbers = NumberCounts()
    meta = Ratio()
    answers = AnswerCounts()
    calibration = CalibrationCounts()
    keys = KeyCounts()
    usage: dict[str, NodeUsage] = {}
    tasks: set[str] = set()
    wall = 0.0
    for r in results:
        structure = structure.add(r.structure)
        numbers = numbers.add(r.numbers)
        meta = meta.add(r.meta)
        answers = answers.add(r.answers)
        calibration = calibration.add(r.calibration)
        keys = keys.add(r.keys)
        for node, u in r.usage.items():
            usage[node] = usage.get(node, NodeUsage()).add(u)
        tasks |= r.tasks
        wall += r.wall_s
    hashes = prompt_hashes(tasks)
    interval = calibration.interval
    row: dict[str, str] = {
        "timestamp": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "commit": git_commit() if commit is None else commit,
        "graph": graph,
        "set": set_name,
        "mode": mode,
        "n_fixtures": str(len(results)),
        "n_failed": str(sum(1 for r in results if r.status != "done")),
        "model_vision": models.get("vision", ""),
        "model_reasoning": models.get("reasoning", ""),
        "prompt_digest": hashlib.sha256(hashes.encode()).hexdigest()[:12] if hashes else "",
        "prompt_hashes": hashes,
        "cer": _fmt(structure.text.value),
        "stimulus_cer": _fmt(structure.stimulus.value),
        "structure_overall": _fmt(structure.overall),
        **{f"structure_{k}": _fmt(v) for k, v in structure.ratios().items()},
        "meta_accuracy": _fmt(meta.value),
        "answer_accuracy": _fmt(answers.accuracy.value),
        "answer_n": str(answers.accuracy.total),
        "calibration": _fmt(calibration.wrong_flagged.value),
        "calibration_lo": _fmt(None if interval is None else interval[0]),
        "calibration_hi": _fmt(None if interval is None else interval[1]),
        "calibration_wrong_n": str(calibration.wrong_flagged.total),
        "flagged_correct_rate": _fmt(calibration.correct_flagged.value),
        "key_accuracy": _fmt(keys.accuracy.value),
        "key_n": str(keys.accuracy.total),
        "key_mapping_accuracy": _fmt(keys.mapping.value),
        "key_mapping_n": str(keys.mapping.total),
        "verdict_accuracy": "",  # the grade graph (step 18)
        "score_exact_match": "",  # the grade graph (step 18)
        "vram_peak_mb": _fmt(vram_mb, 0),
        "wall_s": _fmt(wall, 1),
        "total_tokens_in": str(sum(u.tokens_in for u in usage.values())),
        "total_tokens_out": str(sum(u.tokens_out for u in usage.values())),
        "total_calls": str(sum(u.calls for u in usage.values())),
        "total_node_ms": str(sum(u.ms for u in usage.values())),
    }
    for node in C1_NODES:
        u = usage.get(node, NodeUsage())
        for f in NODE_FIELDS:
            row[f"{node}_{f}"] = str(getattr(u, f))
    row.update(dict.fromkeys(GRADE_COLUMNS, ""))  # the grade graph's columns (M2)
    row["number_renumbering_errors"] = _fmt(numbers.renumbering.value)
    row["number_reading_errors"] = _fmt(numbers.reading.value)
    assert tuple(row) == COLUMNS, "the row and COLUMNS disagree"
    return row


def default_history_path() -> Path:
    return REPO_ROOT / HISTORY_NAME


class HistoryHeaderMismatch(RuntimeError):
    pass


def pad_history(path: Path) -> int:
    """Bring a history file whose header is an older **prefix** of :data:`COLUMNS` up to date:
    the header becomes the current one and every data row gains empty cells at the end. No
    existing cell changes (each line is extended as text). Returns the number of rows padded;
    0 when the header is already current. Raises :class:`HistoryHeaderMismatch` for any other
    header, or a row whose cell count is not the old header's."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines:
        return 0
    with path.open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.reader(f) if r]
    header = tuple(rows[0])
    if header == COLUMNS:
        return 0
    if len(header) >= len(COLUMNS) or COLUMNS[: len(header)] != header:
        raise HistoryHeaderMismatch(f"{path}: its header is not an older form of the current one")
    if len(rows) != len(lines) or any(len(r) != len(header) for r in rows):
        raise HistoryHeaderMismatch(f"{path}: a row does not have the header's cells")
    extra = "," * (len(COLUMNS) - len(header))
    out = [",".join(COLUMNS)] + [line + extra for line in lines[1:]]
    path.write_bytes(("\n".join(out) + "\n").encode("utf-8"))
    return len(out) - 1


def append_history(path: Path, row: Mapping[str, str]) -> None:
    """Append one row; write the header first if the file is missing or empty.

    A file whose header is not the current :data:`COLUMNS` gets the new header when it holds
    no data rows yet; with data rows, an older prefix of the header is padded
    (:func:`pad_history`) and any other header is refused (its old rows would not line up)."""
    path = Path(path)
    header: list[str] | None = None
    if path.is_file() and path.stat().st_size > 0:
        with path.open(encoding="utf-8", newline="") as f:
            rows = [r for r in csv.reader(f) if r]
        header = rows[0] if rows else None
        if header is not None and tuple(header) != COLUMNS:
            if len(rows) > 1:
                try:
                    pad_history(path)
                except HistoryHeaderMismatch as exc:
                    raise HistoryHeaderMismatch(
                        f"{path}: its header is not the current columns and it already has "
                        f"{len(rows) - 1} data row(s); move the file aside to start a new one"
                        f" ({exc})"
                    ) from exc
            else:
                path.write_text("", encoding="utf-8")
                header = None
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        if header is None:
            writer.writerow(COLUMNS)
        writer.writerow([row.get(c, "") for c in COLUMNS])


# --- the whole set -------------------------------------------------------------------------


def replay_dir_for(root: Path, fx: Fixture) -> Path:
    for candidate in (root / fx.set / fx.name, root / fx.name):
        if candidate.is_dir():
            return candidate
    return root


async def run_extract_set(
    fixtures: list[Fixture],
    *,
    backend_for: Callable[[Fixture], Any | None],
    base_url: str | None,
    roles: Mapping[str, str],
    keep: Path | None = None,
    tiles: bool = False,
    photo_reader: str | None = None,
    photo_structure: str | None = None,
) -> list[FixtureResult]:
    """Run every fixture; with ``keep``, write each one's outputs as soon as it finishes."""
    results = []
    with tempfile.TemporaryDirectory(prefix="etach-eval-") as tmp:
        for i, fx in enumerate(fixtures, start=1):
            print(f"etach eval: [{i}/{len(fixtures)}] {fx.set}/{fx.name}", file=sys.stderr)
            result = await run_extract_fixture(
                fx,
                Path(tmp) / f"f{i:03d}",
                backend=backend_for(fx),
                base_url=base_url,
                roles=roles,
                keep_calls=keep is not None,
                tiles=tiles,
                photo_reader=photo_reader,
                photo_structure=photo_structure,
            )
            results.append(result)
            if keep is not None:
                folder = keep / fx.set / fx.name
                write_kept_fixture(folder, fx, result)
                m = fixture_metrics(fx, result)
                print(
                    f"etach eval: [{i}/{len(fixtures)}] {fx.name}: {result.status},"
                    f" cer {m['cer'] or '-'}, structure {m['structure_overall'] or '-'},"
                    f" answers {m['answer_accuracy'] or '-'}, {result.wall_s:.0f} s -> {folder}",
                    file=sys.stderr,
                    flush=True,
                )
    print(form_report(results), file=sys.stderr, flush=True)
    return results


def form_report(results: Sequence[FixtureResult]) -> str:
    """The answer-form line of a run (step 22.5.3): the form accuracy over the matched questions
    and the confusion of forms, ``expected→read: count``, e.g.
    ``etach eval: forms 0.9500 (19/20); choice→choice 12, word→sentence 1, …``."""
    total = StructureCounts()
    for r in results:
        total = total.add(r.structure)
    ratio = total.types
    pairs = ", ".join(f"{pair} {n}" for pair, n in total.form_confusion.items())
    accuracy = _fmt(ratio.value) or "-"
    return f"etach eval: forms {accuracy} ({ratio.hits}/{ratio.total}); {pairs or '-'}"


def model_tags(roles: Mapping[str, str]) -> dict[str, str]:
    """The tags a run uses: the default config with the ``--role`` overrides."""
    from etach.llm.config import default_config

    config = default_config()
    tags: dict[str, str] = {str(name): rc.model for name, rc in config.roles.items()}
    tags.update(roles)
    return tags
