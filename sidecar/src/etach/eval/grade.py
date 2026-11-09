"""``etach eval --graph grade`` (M2): the grade graph measured on the fixtures' typed truth.

Extraction is **not** part of this eval: each fixture's ``expected.json`` becomes a bank test
(:func:`build_test`: the expected sections go through the app's own ``merge_pages``, so ids,
points and graded flags are what the app would store), seeded into a fresh data folder, and
the grade graph runs on it with the chosen reasoning model. Per fixture:

1. **The key run** (always): the test with **no key**, plus an attempt holding the expected
   answers when any answer is filled (as a teacher's first Grade press would be). The model
   makes the key, so this run gives the key metrics and the per-node usage of the row.
2. **The verdict run** (only when the fixture has filled answers and an expected key): a fresh
   folder with the same test, the expected key saved as the teacher's key
   (``teacher_verified``), and the same attempt. The graph grades with the true key, so key
   mistakes do not reach the verdict metrics. Its explanations feed the blind rating sheet.

**Truth** (:func:`verdict_truth`): the app's scoring rules (``domain.scoring.grade``) applied
to the expected key + the expected answers; a teacher entry in ``expected.json``
``verdicts`` overrides it. A free-text answer that matches no accepted answer gets no verdict
from the rules (the app would send it to ``judge_rewrites``): it has a truth only once the
teacher writes one. ``--keep`` lists those answers in ``needs-verdict.json``.

**The row** (``graph=grade``; the extract-only columns stay empty):

- ``key_accuracy_fast`` / ``key_accuracy``, ``key_n``, ``key_uncertain_n``: the key run's keys
  against the expected key (:class:`~etach.eval.metrics.GradeKeyCounts`);
- ``verdict_accuracy``, ``verdict_n``, ``verdict_uncertain_n``, ``verdict_no_truth_n``,
  ``judge_accuracy``, ``judge_n``, ``score_exact_match``, ``score_n``: the verdict run against
  the truth (:class:`~etach.eval.metrics.VerdictCounts`);
- tokens, calls and time per node and in total: the **key run** only (the cost of one real
  Grade press on the paper); ``wall_s`` is the time of both runs.

``--keep DIR`` writes ``DIR/<set>/<name>/``: ``grade.json`` (per question: the expected and
the made key, the expected answer, the graph's verdict, the truth and where it came from),
``explanations.json`` (the verdict run's explanations with the question, the student's answer
and the correct answer), ``needs-verdict.json`` (the answers that need the teacher's verdict,
with a template to paste into ``expected.json``), ``metrics.json`` and ``llm_calls.json`` (both
runs), and ``DIR/<set>/summary.json``. These files hold student text: ``DIR`` goes under the
gitignored ``fixtures/``.
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from etach.domain import scoring
from etach.domain.llm_schemas import TranscribedSection
from etach.domain.models import (
    Answer,
    AnswerKey,
    Attempt,
    Explanation,
    Question,
    Test,
    TestContent,
    TestMetadata,
)
from etach.domain.normalize import value_norm
from etach.domain.renumber import merge_pages
from etach.domain.working import PageTranscript, TestDraft
from etach.eval.fixtures import Expected, Fixture, FixtureError
from etach.eval.harness import (
    COLUMNS,
    GRADE_NODES,
    NODE_FIELDS,
    _fmt,
    _usage,
    _write_json,
    _write_models_toml,
    git_commit,
    prompt_hashes,
    run_calls,
)
from etach.eval.metrics import (
    GradeKeyCounts,
    NodeUsage,
    SavedKey,
    VerdictCounts,
    grade_key_counts,
    question_keys,
    score_match,
    verdict_counts,
)

__all__ = [
    "GradeFixtureResult",
    "Truth",
    "aggregate_grade_row",
    "build_test",
    "check_fixture",
    "grade_fixture_metrics",
    "needs_verdict_count",
    "needs_verdict_items",
    "question_text",
    "run_grade_fixture",
    "run_grade_set",
    "seed_answers",
    "teacher_keys",
    "verdict_truth",
    "write_kept_grade_fixture",
    "write_needs_verdict",
]

#: A section with no ``skill`` in ``expected.json`` (not filled in) is stored as ``mixed``;
#: the skill matters to grading only through ``verify_gate`` (pronunciation / stress).
DEFAULT_SKILL = "mixed"
#: The node whose prompt is another task's (``weak_points`` calls ``weak_points_summary``).
_NODE_TASK = {"weak_points": "weak_points_summary"}
_EXACT_LOCATION = frozenset({"choice"})


# --- the test, from expected.json --------------------------------------------------------------


def _transcribed(expected: Expected) -> list[dict[str, Any]]:
    """The expected sections in the transcription's shape (a listening section: its heading
    and printed range only, as ``transcribe_page`` returns it)."""
    out = []
    for s in expected.sections:
        listening = s.kind == "listening"
        first, last = s.listening_range if s.listening_range is not None else (None, None)
        groups = []
        if not listening:
            for g in s.groups:
                groups.append(
                    {
                        "stimulus": g.stimulus,
                        "pictures": [],  # grading reads no picture
                        "questions": [
                            {
                                "printed_number": q.printed_number,
                                "answer_form": q.answer_form,
                                "stem": q.stem,
                                "options": None
                                if (labelled := q.labelled_options()) is None
                                else [{"label": label, "text": text} for label, text in labelled],
                                "cue": q.cue,
                            }
                            for q in g.questions
                        ],
                    }
                )
        section = TranscribedSection.model_validate(
            {
                "printed_title": s.printed_title,
                "instructions": s.instructions or "",
                "kind": s.kind,
                "skill": s.skill or DEFAULT_SKILL,
                "points_text": s.printed_points,
                "range_first": first,
                "range_last": last,
                "groups": groups,
            }
        )
        out.append(section.model_dump())
    return out


def build_test(expected: Expected) -> tuple[TestDraft, dict[str, str]]:
    """The bank test the app would store for ``expected`` (via ``merge_pages``, one page) and
    question key → question id. Raises :class:`FixtureError` when the stored questions do not
    match the expected question keys."""
    m = expected.meta
    meta = TestMetadata(
        occasion=m.occasion,
        grade=m.grade,
        term=m.term,
        test_number=m.test_number,
        variant=m.variant,
        school=m.school,
        year=m.year,
    )
    page = PageTranscript(
        page_no=1, header_text=None, sections=_transcribed(expected), llm_call_id="eval"
    )
    draft = merge_pages([page], page_files={1: "eval"}, ref="eval", meta=meta).draft
    qs = [q for s in draft.content.sections for g in s.groups for q in g.questions]
    ids = dict(zip(question_keys(q.printed_number for q in qs), (q.id for q in qs), strict=True))
    if list(ids) != expected.question_keys():
        raise FixtureError("the stored test's questions do not match expected.json")
    return draft, ids


def _graded(content: TestContent) -> list[Question]:
    return scoring.graded_questions(content)


def seed_answers(
    expected: Expected, content: TestContent, ids: Mapping[str, str], attempt_id: str
) -> list[Answer]:
    """One sure reading per graded question (as extraction writes one row each): the expected
    answer, or a blank when the question has none."""
    keys = {qid: qkey for qkey, qid in ids.items()}
    out = []
    for q in _graded(content):
        value = expected.answers.get(keys[q.id])
        location = "none" if value is None else "written_in_blank"
        if value is not None and q.answer_form in _EXACT_LOCATION:
            location = "circled_option"
        out.append(
            Answer(
                attempt_id=attempt_id,
                question_id=q.id,
                printed_number=q.printed_number,
                page_no=q.page_no,
                value=value,
                value_norm=None if value is None else value_norm(value),
                location=location,  # type: ignore[arg-type]
                confidence=1.0,
                reading_unsure=False,
                alt_value=None,
                alt_question_id=None,
                points_awarded=None,
                teacher_override=None,
            )
        )
    return out


def teacher_keys(
    expected: Expected, ids: Mapping[str, str], test_id: str, now: datetime
) -> list[AnswerKey]:
    """The expected key as the teacher's verified key rows."""
    return [
        AnswerKey(
            test_id=test_id,
            question_id=ids[qkey],
            accepted=list(accepted),
            reason_vi=None,
            source="teacher_edit",
            status="teacher_verified",
            confidence=None,
            updated_at=now,
        )
        for qkey, accepted in (expected.key or {}).items()
    ]


def has_answers(expected: Expected) -> bool:
    return any(_answered(v) for v in expected.answers.values())


def _answered(value: str | None) -> bool:
    return value is not None and bool(value_norm(value))


# --- the truth ---------------------------------------------------------------------------------


@dataclass
class Truth:
    """``verdicts``: question id → the true verdict, None when unknown; ``source``: question id →
    ``rules`` or ``teacher``; ``to_judge``: the question ids the app sends to the judge (with the
    true key); ``total``: the true score, None unless every graded answer has a truth."""

    verdicts: dict[str, str | None]
    source: dict[str, str]
    to_judge: list[str]
    total: float | None


def verdict_truth(
    content: TestContent,
    answers: Sequence[Answer],
    keys: Sequence[AnswerKey],
    overrides: Mapping[str, str] | None = None,
) -> Truth:
    """The true verdicts: the app's scoring rules on the true key and the true answers
    (``domain.scoring.grade``, so the same normalization, MCQ/T-F, ordering and near-miss
    rules), then ``overrides`` (question id → ``correct`` / ``incorrect``, the teacher's)."""
    result = scoring.grade(content, answers, keys)
    verdicts: dict[str, str | None] = {}
    source: dict[str, str] = {}
    for a in result.answers:
        sure = a.verdict in ("correct", "incorrect")
        verdicts[a.question_id] = a.verdict if sure else None
        if sure:
            source[a.question_id] = "rules"
    for qid, verdict in (overrides or {}).items():
        if qid in verdicts:
            verdicts[qid] = verdict
            source[qid] = "teacher"
    points = {q.id: q.points for q in _graded(content)}
    total: float | None = None
    if all(v is not None for v in verdicts.values()):
        total = round(sum(points[q] for q, v in verdicts.items() if v == "correct"), 4)
    return Truth(verdicts, source, list(result.to_judge), total)


# --- the question text (the rating sheet, needs-verdict.json) ----------------------------------


def question_text(content: TestContent, question_id: str) -> str:
    """The section's instructions, the group's passage and the question with its options."""
    for s in content.sections:
        for g in s.groups:
            for q in g.questions:
                if q.id != question_id:
                    continue
                parts = [f"{s.printed_title}. {s.instructions}".strip()]
                if g.stimulus:
                    parts.append(g.stimulus)
                line = f"{q.printed_number}. {q.stem or ''}".rstrip()
                if q.cue:
                    line += f" ({q.cue})"
                parts.append(line)
                parts.extend(f"{o.label}. {o.text}" for o in q.options or [])
                return "\n".join(parts)
    raise KeyError(question_id)


# --- one run of the graph ----------------------------------------------------------------------


@dataclass
class _Run:
    status: str
    content: TestContent
    ids: dict[str, str]  # question key → question id
    keys: list[AnswerKey]
    answers: list[Answer]  # graded, as saved
    attempt: Attempt | None
    explanations: list[Explanation]
    usage: dict[str, NodeUsage]
    tasks: set[str]
    calls: list[dict[str, Any]]
    wall_s: float


async def _grade_run(
    fx: Fixture,
    data_dir: Path,
    *,
    with_key: bool,
    with_attempt: bool,
    backend: Any | None,
    base_url: str | None,
    roles: Mapping[str, str],
    keep_calls: bool,
) -> _Run:
    from etach.cli import _manager, _open_data, _wait_owned
    from etach.domain.models import GradeInput
    from etach.store import db
    from etach.store.repos import attempts, keys, runs, threads
    from etach.store.repos import explanations as expl_repo
    from etach.store.repos import tests as test_repo
    from etach.store.upgrades import CURRENT_CONTENT_VERSION

    started = time.monotonic()
    draft, ids = build_test(fx.expected)
    paths = _open_data(data_dir)
    _write_models_toml(paths, roles)
    conn = db.connect(paths.db)
    try:
        now = datetime.now(UTC)
        thread = threads.create_thread(
            conn, "etach eval", kind="filled" if with_attempt else "blank"
        )
        attempt_id: str | None = None
        with db.transaction(conn):
            test_id = test_repo.next_test_id(conn)
            test_repo.insert_test(
                conn,
                Test(
                    id=test_id,
                    meta=draft.meta,
                    content=draft.content,
                    content_schema_version=CURRENT_CONTENT_VERSION,
                    fingerprint=draft.fingerprint,
                    points_possible=draft.points_possible,
                    source_run_id=None,
                    merged_into=None,
                    created_at=now,
                    updated_at=now,
                ),
            )
            threads.set_test_id(conn, thread.id, test_id)
            if with_key:
                for key in teacher_keys(fx.expected, ids, test_id, now):
                    keys.upsert_key(conn, key)
            if with_attempt:
                attempt_id = attempts.next_attempt_id(conn)
                attempts.insert_attempt(
                    conn,
                    Attempt(
                        id=attempt_id,
                        test_id=test_id,
                        thread_id=thread.id,
                        student_id=None,
                        student_name_read=None,
                        class_read=None,
                        source_run_id=f"eval-{attempt_id}",
                        superseded_by=None,
                        status="extracted",
                        version=1,
                        score_earned=None,
                        score_possible=None,
                        created_at=now,
                    ),
                )
                attempts.insert_answers(
                    conn, seed_answers(fx.expected, draft.content, ids, attempt_id)
                )
        inp = GradeInput(test_id=test_id, attempt_id=attempt_id, reason="button")
        async with _manager(paths, backend, base_url) as manager:
            run = await manager.submit(thread.id, "grade", inp)
            await _wait_owned(manager, run.id)
        final = runs.get_run(conn, run.id)
        status = final.status if final is not None else "missing"
        if final is not None and final.error:
            print(f"etach eval: {fx.set}/{fx.name}: {final.error}", file=sys.stderr)
        graded = {q.id for q in _graded(draft.content)}
        usage, tasks = _usage(conn, run.id)
        return _Run(
            status=status,
            content=draft.content,
            ids=ids,
            keys=keys.list_keys(conn, test_id),
            answers=[]
            if attempt_id is None
            else [a for a in attempts.list_answers(conn, attempt_id) if a.question_id in graded],
            attempt=None if attempt_id is None else attempts.get_attempt(conn, attempt_id),
            explanations=expl_repo.list_explanations(conn, test_id),
            usage=usage,
            tasks={_NODE_TASK.get(t, t) for t in tasks},
            calls=run_calls(conn, run.id) if keep_calls else [],
            wall_s=time.monotonic() - started,
        )
    finally:
        conn.close()


# --- one fixture -------------------------------------------------------------------------------


@dataclass
class GradeFixtureResult:
    status: str
    key_status: str = ""
    verdict_status: str = ""  # "" when there was no verdict run
    keys: GradeKeyCounts = field(default_factory=GradeKeyCounts)
    verdicts: VerdictCounts = field(default_factory=VerdictCounts)
    usage: dict[str, NodeUsage] = field(default_factory=dict)  # the key run's
    verdict_usage: dict[str, NodeUsage] = field(default_factory=dict)
    tasks: set[str] = field(default_factory=set)
    wall_s: float = 0.0
    # the details --keep writes (student text)
    key_rows: list[dict[str, Any]] = field(default_factory=list)
    verdict_rows: list[dict[str, Any]] = field(default_factory=list)
    explanations: list[dict[str, Any]] = field(default_factory=list)
    needs_verdict: list[dict[str, Any]] = field(default_factory=list)
    score: dict[str, Any] = field(default_factory=dict)
    calls: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def _ids_to_keys(ids: Mapping[str, str]) -> dict[str, str]:
    return {qid: qkey for qkey, qid in ids.items()}


def evaluate_key_run(fx: Fixture, run: _Run) -> tuple[GradeKeyCounts, list[dict[str, Any]]]:
    qkeys = _ids_to_keys(run.ids)
    saved = {
        qkeys[k.question_id]: SavedKey(list(k.accepted), k.status)
        for k in run.keys
        if k.question_id in qkeys
    }
    expected = fx.expected.key or {}
    counts = grade_key_counts(expected, saved)
    rows = []
    for qkey in run.ids:
        got = saved.get(qkey)
        want = expected.get(qkey)
        single = grade_key_counts({qkey: want}, saved) if want is not None else None
        rows.append(
            {
                "question": qkey,
                "expected": want,
                "made": None if got is None else got.accepted,
                "status": None if got is None else got.status,
                "fast_ok": None if single is None else single.fast.hits == 1,
                "verified_ok": None if single is None else single.verified.hits == 1,
            }
        )
    return counts, rows


def evaluate_verdict_run(
    fx: Fixture, run: _Run
) -> tuple[VerdictCounts, list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    """The verdict run against the truth: the counts, one row per graded question, the score,
    and the answers that need the teacher's verdict."""
    exp = fx.expected
    qkeys = _ids_to_keys(run.ids)
    now = datetime.now(UTC)
    test_id = run.attempt.test_id if run.attempt is not None else ""
    true_answers = seed_answers(exp, run.content, run.ids, "truth")
    true_keys = teacher_keys(exp, run.ids, test_id, now)
    overrides = {run.ids[k]: v for k, v in (exp.verdicts or {}).items()}
    truth = verdict_truth(run.content, true_answers, true_keys, overrides)
    graph = {qkeys[a.question_id]: a.verdict for a in run.answers}
    truth_by_key = {qkeys[q]: v for q, v in truth.verdicts.items()}
    judged = [qkeys[q] for q in truth.to_judge]
    answered = [qkeys[a.question_id] for a in true_answers if _answered(a.value)]
    counts = verdict_counts(truth_by_key, graph, answered=answered, judged=judged)
    unsure = any(a.verdict not in ("correct", "incorrect") for a in run.answers) or not run.answers
    earned = None if run.attempt is None else run.attempt.score_earned
    counts.score = score_match(truth.total, earned, graph_unsure=unsure)
    score = {
        "truth_total": truth.total,
        "graph_earned": earned,
        "graph_possible": None if run.attempt is None else run.attempt.score_possible,
        "graph_left_unsure": unsure,
        "match": None if truth.total is None else counts.score.hits == 1,
    }
    rows = []
    needs = []
    by_qid = {a.question_id: a for a in run.answers}
    for a in true_answers:
        qkey = qkeys[a.question_id]
        got = by_qid.get(a.question_id)
        rows.append(
            {
                "question": qkey,
                "answer": a.value,
                "accepted": (exp.key or {}).get(qkey),
                "graph": None if got is None else got.verdict,
                "truth": truth.verdicts.get(a.question_id),
                "truth_from": truth.source.get(a.question_id),
                "judged": a.question_id in truth.to_judge,
                "near_miss": None if got is None else got.near_miss,
            }
        )
        if a.question_id in truth.to_judge:
            needs.append(
                {
                    "question": qkey,
                    "question_text": question_text(run.content, a.question_id),
                    "student_answer": a.value,
                    "accepted": (exp.key or {}).get(qkey),
                    "teacher_verdict": (exp.verdicts or {}).get(qkey),
                    "graph_verdict": None if got is None else got.verdict,
                }
            )
    return counts, rows, score, needs


def explanation_rows(fx: Fixture, run: _Run) -> list[dict[str, Any]]:
    """The verdict run's explanations, in question order, with what a rater needs."""
    qkeys = _ids_to_keys(run.ids)
    answers = {a.question_id: a for a in run.answers}
    order = {qid: i for i, qid in enumerate(run.ids.values())}
    out = []
    for e in sorted(run.explanations, key=lambda e: order.get(e.question_id, 0)):
        qkey = qkeys.get(e.question_id)
        if qkey is None:
            continue
        a = answers.get(e.question_id)
        out.append(
            {
                "question": qkey,
                "question_text": question_text(run.content, e.question_id),
                "student_answer": None if a is None else scoring.effective_value(a),
                "correct_answer": " | ".join((fx.expected.key or {}).get(qkey, [])),
                "error_type": e.error_type,
                "explanation": e.text_vi,
            }
        )
    return out


async def run_grade_fixture(
    fx: Fixture,
    data_dir: Path,
    *,
    backend: Any | None,
    base_url: str | None,
    roles: Mapping[str, str],
    keep_calls: bool = False,
) -> GradeFixtureResult:
    """The key run, then (filled answers + an expected key) the verdict run, each into its own
    fresh folder under ``data_dir``. One replay ``backend`` serves both, in that order."""
    answered = has_answers(fx.expected)
    key_run = await _grade_run(
        fx,
        data_dir / "key",
        with_key=False,
        with_attempt=answered,
        backend=backend,
        base_url=base_url,
        roles=roles,
        keep_calls=keep_calls,
    )
    result = GradeFixtureResult(status=key_run.status, key_status=key_run.status)
    result.keys, result.key_rows = evaluate_key_run(fx, key_run)
    result.usage, result.tasks = key_run.usage, set(key_run.tasks)
    result.wall_s = key_run.wall_s
    result.calls["key_run"] = key_run.calls
    if answered and fx.expected.key:
        run = await _grade_run(
            fx,
            data_dir / "verdict",
            with_key=True,
            with_attempt=True,
            backend=backend,
            base_url=base_url,
            roles=roles,
            keep_calls=keep_calls,
        )
        result.verdict_status = run.status
        if run.status != "done":
            result.status = run.status
        result.verdicts, result.verdict_rows, result.score, result.needs_verdict = (
            evaluate_verdict_run(fx, run)
        )
        result.explanations = explanation_rows(fx, run)
        result.verdict_usage = run.usage
        result.tasks |= run.tasks
        result.wall_s += run.wall_s
        result.calls["verdict_run"] = run.calls
    return result


# --- the row -----------------------------------------------------------------------------------


def aggregate_grade_row(
    results: Sequence[GradeFixtureResult],
    *,
    set_name: str,
    mode: str,
    models: Mapping[str, str],
    vram_mb: float | None = None,
    commit: str | None = None,
    now: datetime | None = None,
) -> dict[str, str]:
    """The ``graph=grade`` row: every column present; the extract-only ones empty."""
    keys = GradeKeyCounts()
    verdicts = VerdictCounts()
    usage: dict[str, NodeUsage] = {}
    tasks: set[str] = set()
    wall = 0.0
    for r in results:
        keys = keys.add(r.keys)
        verdicts = verdicts.add(r.verdicts)
        for node, u in r.usage.items():
            usage[node] = usage.get(node, NodeUsage()).add(u)
        tasks |= r.tasks
        wall += r.wall_s
    hashes = prompt_hashes(tasks)
    row = dict.fromkeys(COLUMNS, "")
    row.update(
        {
            "timestamp": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
            "commit": git_commit() if commit is None else commit,
            "graph": "grade",
            "set": set_name,
            "mode": mode,
            "n_fixtures": str(len(results)),
            "n_failed": str(sum(1 for r in results if r.status != "done")),
            "model_reasoning": models.get("reasoning", ""),
            "prompt_digest": hashlib.sha256(hashes.encode()).hexdigest()[:12] if hashes else "",
            "prompt_hashes": hashes,
            "key_accuracy": _fmt(keys.verified.value),
            "key_n": str(keys.verified.total),
            "key_accuracy_fast": _fmt(keys.fast.value),
            "key_uncertain_n": str(keys.uncertain),
            "verdict_accuracy": _fmt(verdicts.verdict.value),
            "verdict_n": str(verdicts.verdict.total),
            "verdict_uncertain_n": str(verdicts.uncertain),
            "verdict_no_truth_n": str(verdicts.no_truth),
            "judge_accuracy": _fmt(verdicts.judge.value),
            "judge_n": str(verdicts.judge.total),
            "score_exact_match": _fmt(verdicts.score.value),
            "score_n": str(verdicts.score.total),
            "vram_peak_mb": _fmt(vram_mb, 0),
            "wall_s": _fmt(wall, 1),
            "total_tokens_in": str(sum(u.tokens_in for u in usage.values())),
            "total_tokens_out": str(sum(u.tokens_out for u in usage.values())),
            "total_calls": str(sum(u.calls for u in usage.values())),
            "total_node_ms": str(sum(u.ms for u in usage.values())),
        }
    )
    for node in (*GRADE_NODES, "save"):
        u = usage.get(node, NodeUsage())
        for f in NODE_FIELDS:
            row[f"{node}_{f}"] = str(getattr(u, f))
    assert tuple(row) == COLUMNS, "the row and COLUMNS disagree"
    return row


#: The metric columns of a grade fixture's own ``metrics.json``.
GRADE_FIXTURE_COLUMNS = (
    "key_accuracy_fast",
    "key_accuracy",
    "key_n",
    "key_uncertain_n",
    "verdict_accuracy",
    "verdict_n",
    "verdict_uncertain_n",
    "verdict_no_truth_n",
    "judge_accuracy",
    "judge_n",
    "score_exact_match",
    "score_n",
    "total_tokens_in",
    "total_tokens_out",
    "total_calls",
    "total_node_ms",
)


def grade_fixture_metrics(fx: Fixture, result: GradeFixtureResult) -> dict[str, str]:
    row = aggregate_grade_row([result], set_name=fx.set, mode="", models={}, commit="")
    return {c: row[c] for c in GRADE_FIXTURE_COLUMNS}


def needs_verdict_items(fx: Fixture) -> list[dict[str, Any]]:
    """Without any model: the answers the app sends to ``judge_rewrites`` when it grades with
    the true key (free text that equals no accepted answer). Only these need the teacher's
    verdict; it does not depend on the model, so the teacher can fill them before any run."""
    exp = fx.expected
    if not has_answers(exp) or not exp.key:
        return []
    draft, ids = build_test(exp)
    answers = {a.question_id: a for a in seed_answers(exp, draft.content, ids, "truth")}
    keys = teacher_keys(exp, ids, "", datetime.now(UTC))
    truth = verdict_truth(draft.content, list(answers.values()), keys)
    qkeys = _ids_to_keys(ids)
    return [
        {
            "question": qkeys[qid],
            "question_text": question_text(draft.content, qid),
            "student_answer": answers[qid].value,
            "accepted": exp.key.get(qkeys[qid]),
            "teacher_verdict": (exp.verdicts or {}).get(qkeys[qid]),
            "graph_verdict": None,
        }
        for qid in truth.to_judge
    ]


def write_needs_verdict(folder: Path, fx: Fixture, items: Sequence[Mapping[str, Any]]) -> Path:
    """``folder/needs-verdict.json``: the items, how many still lack the teacher's verdict, and
    a template (question → "") to fill and paste into ``expected.json`` as ``verdicts``."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "needs-verdict.json"
    missing = [n["question"] for n in items if n["teacher_verdict"] is None]
    _write_json(
        path,
        {
            "fixture": f"{fx.set}/{fx.name}",
            "how": 'Add a "verdicts" object to expected.json: question -> "correct" or'
            ' "incorrect" (the template lists the questions without your verdict).',
            "missing": len(missing),
            "items": list(items),
            "template": dict.fromkeys(missing, ""),
        },
    )
    return path


def write_kept_grade_fixture(folder: Path, fx: Fixture, result: GradeFixtureResult) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    _write_json(
        folder / "grade.json",
        {
            "fixture": f"{fx.set}/{fx.name}",
            "keys": result.key_rows,
            "verdicts": result.verdict_rows,
            "score": result.score,
        },
    )
    _write_json(folder / "explanations.json", result.explanations)
    write_needs_verdict(folder, fx, result.needs_verdict)
    _write_json(
        folder / "metrics.json",
        {
            "fixture": f"{fx.set}/{fx.name}",
            "status": result.status,
            "key_run": result.key_status,
            "verdict_run": result.verdict_status or None,
            "wall_s": round(result.wall_s, 1),
            "metrics": grade_fixture_metrics(fx, result),
            "counts": {"keys": asdict(result.keys), "verdicts": asdict(result.verdicts)},
            "usage": {node: asdict(u) for node, u in result.usage.items()},
            "verdict_run_usage": {node: asdict(u) for node, u in result.verdict_usage.items()},
        },
    )
    _write_json(folder / "llm_calls.json", result.calls)


# --- the whole set -----------------------------------------------------------------------------


async def run_grade_set(
    fixtures: list[Fixture],
    *,
    backend_for: Callable[[Fixture], Any | None],
    base_url: str | None,
    roles: Mapping[str, str],
    keep: Path | None = None,
) -> list[GradeFixtureResult]:
    results = []
    with tempfile.TemporaryDirectory(prefix="etach-eval-grade-") as tmp:
        for i, fx in enumerate(fixtures, start=1):
            print(f"etach eval: [{i}/{len(fixtures)}] {fx.set}/{fx.name}", file=sys.stderr)
            result = await run_grade_fixture(
                fx,
                Path(tmp) / f"f{i:03d}",
                backend=backend_for(fx),
                base_url=base_url,
                roles=roles,
                keep_calls=keep is not None,
            )
            results.append(result)
            m = grade_fixture_metrics(fx, result)
            where = ""
            if keep is not None:
                folder = keep / fx.set / fx.name
                write_kept_grade_fixture(folder, fx, result)
                where = f" -> {folder}"
            missing = sum(1 for n in result.needs_verdict if n["teacher_verdict"] is None)
            print(
                f"etach eval: [{i}/{len(fixtures)}] {fx.name}: {result.status},"
                f" key fast {m['key_accuracy_fast'] or '-'}, key {m['key_accuracy'] or '-'},"
                f" verdicts {m['verdict_accuracy'] or '-'}, {missing} answer(s) need a"
                f" verdict, {result.wall_s:.0f} s{where}",
                file=sys.stderr,
                flush=True,
            )
    return results


def needs_verdict_count(results: Sequence[GradeFixtureResult]) -> int:
    return sum(1 for r in results for n in r.needs_verdict if n["teacher_verdict"] is None)


def check_fixture(fx: Fixture) -> None:
    """Build the fixture's test (the preflight): raises :class:`FixtureError` if it fails."""
    build_test(fx.expected)
