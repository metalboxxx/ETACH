"""The grade graph (llm-design §5, plan step 18, Appendix C.2).

``build_grade_graph(deps)`` returns a registry factory ``factory(checkpointer)``;
``register_grade(manager, deps)`` registers it for ``grade`` runs.

**State** (:class:`GradeState`) is plain JSON, as in the extract graph: pydantic values are
stored as ``model_dump(mode="json")``. P8: the nodes before ``save`` write only state and
``llm_calls``; domain tables are written only in ``save``, in one transaction.

**Keys** live in ``keys`` (question_id → AnswerKey, the current view) and every row the graph
made or changed is also listed in ``key_writes`` (``save`` upserts them through the guarded
upsert, so a teacher's key is never downgraded).

**Version check** (data-model §5.2, R18.7): ``load_context`` stores ``attempts.version``.
``save`` compares it inside its transaction; on a mismatch it writes nothing and sends the run
back to ``grade`` (``Command(goto="grade")`` with ``reload``), which reloads the answers. The
``grade → … → weak_points → save`` path then runs again; keys, tags and the
explanations already made are reused, so only new wrong answers cost a model call. This
loop-back is not a graph edge (Appendix C.2 is the static graph).

**Test check** (R22.6.6.3, step22.6-plan D15): ``save`` also compares the test content with
the one ``load_context`` loaded. When it changed (a test-text or points save while the run was
running, stopped or interrupted), it writes nothing and sends the run back to ``load_context``
(``Command(goto="load_context")``), which loads the test, keys and answers again; the keys,
skill tags and explanations this run made for questions whose text is unchanged are kept, the
ones for deleted or changed questions are dropped, and ``save`` skips Review items for a
question the test no longer has. So an attempt's first grade ends against the saved test.

**Call failures** (llm-design §5.1) never crash the graph: ``ai_key_fast`` → no key rows +
``uncertain_key``; ``verify_key`` → ``ai_uncertain`` + ``uncertain_key``; ``judge_rewrites`` →
``judged="failed"`` (uncertain); ``explain`` → no explanation; ``tag_skills`` /
``weak_points_summary`` → skipped.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Annotated, Any, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import BaseModel

from etach.domain import keys as key_rules
from etach.domain import scoring
from etach.domain import weakpoints as wp
from etach.domain.levels import tag_level
from etach.domain.llm_schemas import (
    AiKeyOut,
    ExplainOut,
    JudgeOut,
    SummaryOut,
    VerifyKeyOut,
)
from etach.domain.models import (
    Answer,
    AnswerKey,
    Explanation,
    GradeInput,
    GradeReport,
    Question,
    Section,
    TestContent,
)
from etach.domain.normalize import value_norm
from etach.domain.skills import skill_name
from etach.domain.working import PendingReview
from etach.llm.client import CallFailure, CallResult, OllamaClient
from etach.llm.confidence import field_confidences
from etach.llm.tasks import TASKS, skill_list_text
from etach.runtime.steps import Stage, current_run, current_step_id, report_progress, step
from etach.store import db as store_db
from etach.store.repos import attempts as attempt_repo
from etach.store.repos import explanations as expl_repo
from etach.store.repos import keys as key_repo
from etach.store.repos import review as review_repo
from etach.store.repos import runs as runs_repo
from etach.store.repos import tests as test_repo
from etach.store.repos import threads as thread_repo

__all__ = [
    "C2_EDGES",
    "C2_NODES",
    "GRADE_STAGES",
    "GradeDeps",
    "GradeState",
    "GradeThresholds",
    "answer_value_norm",
    "build_grade_graph",
    "register_grade",
    "save_grade",
]

# --- Appendix C.2 ------------------------------------------------------------------------------

C2_NODES: tuple[str, ...] = (
    "load_context",
    "ai_key_fast",
    "verify_gate",
    "verify_key",
    "tag_skills",
    "grade",
    "judge_rewrites",
    "explain",
    "weak_points",
    "save",
)
C2_EDGES: tuple[tuple[str, str], ...] = (
    (START, "load_context"),
    ("load_context", "ai_key_fast"),
    ("load_context", "verify_gate"),
    ("ai_key_fast", "verify_gate"),
    ("verify_gate", "verify_key"),
    ("verify_gate", "tag_skills"),
    ("verify_key", "tag_skills"),
    ("tag_skills", "save"),
    ("tag_skills", "grade"),
    ("grade", "judge_rewrites"),
    ("grade", "explain"),
    ("judge_rewrites", "explain"),
    ("explain", "weak_points"),
    ("weak_points", "save"),
    ("save", END),
)
GRADE_STAGES: tuple[Stage, ...] = (
    Stage("Getting ready", ("load_context",)),
    Stage("Checking the key", ("ai_key_fast", "verify_gate", "verify_key")),
    Stage("Grading", ("tag_skills", "grade", "judge_rewrites")),
    Stage("Explaining mistakes", ("explain",)),
    Stage("Updating student ability", ("weak_points",)),
    Stage("Saving", ("save",)),
)
"""The run progress stages, in order (llm-design §2 "Run progress", v4.20)."""


@dataclass(frozen=True)
class GradeThresholds:
    """Every grading threshold in one place (M1 tunes them)."""

    key_margin: float = 0.7  # an AI key's logprob margin below → verify_key (B.7 "low margin")


@dataclass
class GradeDeps:
    client: OllamaClient
    thresholds: GradeThresholds = field(default_factory=GradeThresholds)


# --- state ---------------------------------------------------------------------------------------


#: The first entry of a ``pending_reviews`` update that replaces the list instead of appending.
RESET_PENDINGS: dict[str, Any] = {"dedupe_key": "", "reset": True}


def _merge_pendings(
    old: list[dict[str, Any]] | None, new: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Reducer: append pending reviews; a repeated ``dedupe_key`` replaces the earlier one. An
    update that starts with :data:`RESET_PENDINGS` first drops every earlier one (the reload
    after the test changed, R22.6.6.3)."""
    out = list(old or [])
    if new and new[0].get("reset"):
        out, new = [], new[1:]
    index = {p["dedupe_key"]: i for i, p in enumerate(out)}
    for p in new or []:
        if p["dedupe_key"] in index:
            out[index[p["dedupe_key"]]] = p
        else:
            index[p["dedupe_key"]] = len(out)
            out.append(p)
    return out


class GradeState(TypedDict, total=False):
    input: dict[str, Any]  # GradeInput
    run_id: str
    thread_id: str
    content: dict[str, Any]  # TestContent
    exam_format: str | None
    keys: dict[str, dict[str, Any]]  # question_id → AnswerKey (current view)
    key_writes: list[str]  # question IDs whose key row save must upsert
    to_verify: list[str]
    tags: dict[str, list[str]]  # question_id → skill tags
    tags_new: bool  # tag_skills produced the tags (save writes question_tags)
    tag_levels: dict[str, str | None]  # question_id → its level from tag_skills (step 22.5.5)
    attempt_id: str | None
    student_id: str | None
    attempt_created_at: str | None
    version: int | None
    answers: list[dict[str, Any]]  # Answer (value_norm from the effective value)
    reload: bool  # save found a version mismatch: grade reloads the answers
    grade_passes: int  # how many times grade ran (R18.7)
    graded: dict[str, Any] | None  # GradeResult
    judged: dict[str, str]  # question_id → correct | incorrect | failed
    explanations: list[dict[str, Any]]  # Explanation, made by this run
    report: dict[str, Any] | None  # GradeReport
    pending_reviews: Annotated[list[dict[str, Any]], _merge_pendings]  # PendingReview
    saved: dict[str, Any] | None


# --- helpers -------------------------------------------------------------------------------------


def _j(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _input(state: GradeState) -> GradeInput:
    return GradeInput.model_validate(state["input"])


def _content(state: GradeState) -> TestContent:
    return TestContent.model_validate(state["content"])


def _keys(state: GradeState) -> dict[str, AnswerKey]:
    return {q: AnswerKey.model_validate(k) for q, k in (state.get("keys") or {}).items()}


def _answers(state: GradeState) -> list[Answer]:
    return [Answer.model_validate(a) for a in state.get("answers") or []]


def answer_value_norm(answer: Answer) -> str | None:
    """``value_norm`` of the **effective** value (data-model §2.5): the override when it is not
    None (so an override of ``""`` is a blank, ``""``), else the value read (None stays None)."""
    raw = scoring.effective_value(answer)
    return None if raw is None else value_norm(raw)


def _with_norm(answers: Sequence[Answer]) -> list[Answer]:
    return [a.model_copy(update={"value_norm": answer_value_norm(a)}) for a in answers]


def _questions(content: TestContent) -> dict[str, tuple[Section, Question]]:
    return {q.id: (s, q) for s in content.sections for g in s.groups for q in g.questions}


def _question_text(content: TestContent, question_id: str) -> str:
    """The section instructions, the group stimulus and the question (stem + options)."""
    for s in content.sections:
        for g in s.groups:
            for q in g.questions:
                if q.id == question_id:
                    parts = [f"Section {s.printed_title}: {s.instructions}"]
                    if g.stimulus:
                        parts.append(g.stimulus)
                    parts.append(_one_question(q))
                    return "\n".join(parts)
    raise KeyError(question_id)


def _one_question(q: Question) -> str:
    line = f"{q.id} (no. {q.printed_number}, {q.answer_form}): {q.stem or ''}".rstrip()
    if q.cue:
        line += f" [{q.cue}]"
    if q.options:
        line += "\n" + "\n".join(f"  {o.label}. {o.text}" for o in q.options)
    if q.answer_form == "sentence" and q.answer_start:
        # the words printed on the answer line (step 22.5.4): the student may write only the rest
        line += f"\n  Answer line starts with: {q.answer_start}"
    return line


def _section_text(s: Section) -> str:
    parts = [f"{s.printed_title}. {s.instructions}"]
    for g in s.groups:
        if g.stimulus:
            parts.append(g.stimulus)
        parts.extend(_one_question(q) for q in g.questions)
    return "\n".join(parts)


def _accepted_text(key: AnswerKey | None) -> str:
    return " | ".join(key.accepted) if key else "(no key)"


def _same_questions(old: TestContent, new: TestContent) -> set[str]:
    """The questions in both contents whose text, as the models see it, is the same."""
    both = set(_questions(old)) & set(_questions(new))
    return {q for q in both if _question_text(old, q) == _question_text(new, q)}


def _carry_over(state: GradeState, out: dict[str, Any]) -> None:
    """A reload after the test changed (R22.6.6.3): ``out`` is the fresh context; the work this
    run already did for questions whose text is unchanged (its keys, explanations and skill
    tags) is kept, so only changed and new questions cost a model call. Work for a question that
    is gone or changed is dropped, and so is the run's key for a question the store now has a
    stronger key for (a teacher key written while the run was stopped wins, as in the guarded
    upsert). The run's pending Review items are kept only for the keys it keeps; the reloaded
    pass makes its own for the others."""
    same = _same_questions(_content(state), TestContent.model_validate(out["content"]))
    old_keys = state.get("keys") or {}
    stored = out["keys"]
    kept: dict[str, dict[str, Any]] = {}
    for q in dict.fromkeys(state.get("key_writes") or []):
        if q not in same or q not in old_keys:
            continue
        mine = AnswerKey.model_validate(old_keys[q])
        theirs = stored.get(q)
        if theirs is not None and key_repo.precedence(mine) < key_repo.precedence(
            AnswerKey.model_validate(theirs)
        ):
            continue
        kept[q] = old_keys[q]
    out["keys"] = {**stored, **kept}
    out["key_writes"] = list(kept)
    pendings = [
        p
        for p in state.get("pending_reviews") or []
        if (p.get("refs") or {}).get("question_id") in kept
    ]
    out["pending_reviews"] = [RESET_PENDINGS, *pendings]
    out["explanations"] = [e for e in state.get("explanations") or [] if e["question_id"] in same]
    if state.get("tags_new") and not out["tags"]:
        tags = {q: t for q, t in (state.get("tags") or {}).items() if q in same}
        levels = {q: v for q, v in (state.get("tag_levels") or {}).items() if q in tags}
        out.update(tags=tags, tag_levels=levels, tags_new=bool(tags))
    out["grade_passes"] = int(state.get("grade_passes") or 0)


def untagged(content: TestContent, tags: dict[str, list[str]]) -> set[str]:
    """The graded questions without skill tags (a reload's ``tag_skills`` tags only these)."""
    return {
        q.id
        for s in content.sections
        if s.graded
        for g in s.groups
        for q in g.questions
        if not tags.get(q.id)
    }


def _load_answers(c: sqlite3.Connection, attempt_id: str) -> tuple[list[Answer], int]:
    att = attempt_repo.get_attempt(c, attempt_id)
    if att is None:
        raise KeyError(f"no attempt {attempt_id}")
    return _with_norm(attempt_repo.list_answers(c, attempt_id)), att.version


@dataclass(frozen=True)
class _PaperContext:
    """What the ``weak_points`` node reads besides the explanations (step 22.5.5)."""

    history: list[wp.PaperSkill]
    taken_on: date | None
    forms: dict[str, str]
    option_counts: dict[str, int]
    levels: dict[str, dict[str, str | None]]


def _explanation_index(
    conn: sqlite3.Connection, test_id: str, made: Sequence[Explanation]
) -> dict[tuple[str, str], Explanation]:
    out = {
        (e.question_id, e.wrong_answer_norm): e for e in expl_repo.list_explanations(conn, test_id)
    }
    for e in made:
        out.setdefault((e.question_id, e.wrong_answer_norm), e)
    return out


def _card_exists(conn: sqlite3.Connection, thread_id: str, run_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM messages WHERE thread_id = ? AND kind = 'grade_card'"
        " AND json_extract(body, '$.run_id') = ?",
        (thread_id, run_id),
    ).fetchone()
    return row is not None


# --- save ----------------------------------------------------------------------------------------


def save_grade(conn: sqlite3.Connection, state: GradeState) -> dict[str, Any]:
    """The grade ``save`` (llm-design §5, data-model §5.2), in ONE transaction.

    Returns ``{"status": "saved" | "already_done" | "test_changed" | "version_mismatch",
    ...}``. Idempotent:
    (0) a run already ``done`` returns at once (a crash between the commit and the checkpoint,
    R18.9); key rows go through the guarded upsert; Review items are upserted by ``dedupe_key``
    after this graph's older open items for the attempt are marked ``obsolete``; the report is
    replaced; the grade card is written once per run.
    """
    run_id = state["run_id"]
    thread_id = state["thread_id"]
    inp = GradeInput.model_validate(state["input"])
    test_id = inp.test_id
    attempt_id = state.get("attempt_id")

    run_row = conn.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
    if run_row is not None and run_row[0] == "done":
        return {"status": "already_done", "test_id": test_id, "attempt_id": attempt_id}

    now = datetime.now(UTC)
    with store_db.transaction(conn):
        # R22.6.6.3: the test changed since load_context (a test-text or points save while this
        # run was queued behind, running, stopped or interrupted): write nothing, reload it all
        test = test_repo.get_test(conn, test_id)
        if test is None:
            raise KeyError(f"no test {test_id}")
        if test.content != _content(state):
            return {"status": "test_changed", "test_id": test_id, "attempt_id": attempt_id}
        if attempt_id is not None:
            att = attempt_repo.get_attempt(conn, attempt_id)
            if att is None:
                raise KeyError(f"no attempt {attempt_id}")
            if att.version != state.get("version"):
                return {
                    "status": "version_mismatch",
                    "test_id": test_id,
                    "attempt_id": attempt_id,
                    "expected": state.get("version"),
                    "found": att.version,
                }

        # keys (guarded: never downgrade a teacher key; a changed key drops its explanations)
        keys = _keys(state)
        for qid in dict.fromkeys(state.get("key_writes") or []):
            key = keys.get(qid)
            if key is not None:
                key_repo.upsert_key(conn, key.model_copy(update={"updated_at": now}))

        # tags (once per test; after a reload, only the questions this run tagged: the ones in
        # ``tag_levels``, R22.6.6.3)
        if state.get("tags_new"):
            levels = state.get("tag_levels") or {}
            for qid, tags in (state.get("tags") or {}).items():
                if levels and qid not in levels:
                    continue
                test_repo.set_question_tags(conn, test_id, qid, tags, levels.get(qid))

        # Review items: this graph's older open items for the attempt → obsolete, then upsert
        if attempt_id is not None:
            review_repo.mark_obsolete(conn, "grade", attempt_id)
        present = set(_questions(test.content))
        for raw in state.get("pending_reviews") or []:
            p = PendingReview.model_validate(raw)
            ref_qid = p.refs.get("question_id")
            if ref_qid is not None and ref_qid not in present:
                continue  # made before a reload, for a question the test no longer has
            review_repo.upsert_item(
                conn,
                kind=cast(Any, p.kind),
                owner="grade",
                dedupe_key=p.dedupe_key,
                proposal=p.proposal,
                test_id=test_id,
                attempt_id=None if p.kind == "uncertain_key" else attempt_id,
                question_id=p.refs.get("question_id"),
            )

        graded = state.get("graded")
        if attempt_id is not None and graded is not None:
            result = scoring.GradeResult.model_validate(graded)
            for ans in result.answers:
                attempt_repo.set_answer_grade(conn, ans)
            for raw in state.get("explanations") or []:
                e = Explanation.model_validate(raw)
                if expl_repo.get_explanation(conn, e.test_id, e.question_id, e.wrong_answer_norm):
                    continue  # a teacher-edited (or earlier) explanation is kept
                key = key_repo.get_key(conn, e.test_id, e.question_id)
                stale = keys.get(e.question_id)
                if key is None or stale is None or key.accepted != stale.accepted:
                    continue  # the key changed since the explanation was made
                expl_repo.upsert_explanation(conn, e)
            report = state.get("report")
            if report is not None:
                attempt_repo.replace_grade_report(conn, GradeReport.model_validate(report))
            attempt_repo.set_graded(conn, attempt_id, result.score_earned, result.score_possible)
            if not _card_exists(conn, thread_id, run_id):
                thread_repo.add_message(
                    conn,
                    thread_id,
                    "app",
                    "grade_card",
                    {
                        "run_id": run_id,
                        "test_id": test_id,
                        "attempt_id": attempt_id,
                        "score_earned": result.score_earned,
                        "score_possible": result.score_possible,
                        "uncertain_points": result.uncertain_points,
                    },
                )
        runs_repo.set_run_status(conn, run_id, "done")
    return {"status": "saved", "test_id": test_id, "attempt_id": attempt_id}


# --- the graph -----------------------------------------------------------------------------------


def build_grade_graph(deps: GradeDeps) -> Any:
    """Return the registry factory ``factory(checkpointer) -> compiled grade graph``."""
    client = deps.client
    th = deps.thresholds

    async def call(
        task: str, inputs: dict[str, Any], state: GradeState
    ) -> CallResult | CallFailure:
        spec = TASKS[task]
        return await client.call(
            spec.role,
            spec.task,
            inputs,
            spec.schema(),
            step_id=current_step_id(),
            think=spec.think,
            num_predict=spec.num_predict,
            profile=spec.profile(state.get("exam_format")),
        )

    # --- nodes -------------------------------------------------------------------------------

    async def load_context(state: GradeState) -> dict[str, Any]:
        run = current_run()
        inp = _input(state)

        def load(c: sqlite3.Connection) -> dict[str, Any]:
            test = test_repo.get_test(c, inp.test_id)
            if test is None:
                raise KeyError(f"no test {inp.test_id}")
            keys = {k.question_id: _j(k) for k in key_repo.list_keys(c, inp.test_id)}
            out: dict[str, Any] = {
                "run_id": run.run_id,
                "thread_id": run.thread_id,
                "content": _j(test.content),
                "exam_format": test.meta.exam_format,
                "keys": keys,
                "key_writes": [],
                "tags": test_repo.list_question_tags(c, inp.test_id),
                "tags_new": False,
                "attempt_id": inp.attempt_id,
                "student_id": None,
                "attempt_created_at": None,
                "version": None,
                "answers": [],
                "reload": False,
                "grade_passes": 0,
                "graded": None,
                "judged": {},
                "explanations": [],
                "report": None,
                "pending_reviews": [],
            }
            if inp.attempt_id is not None:
                att = attempt_repo.get_attempt(c, inp.attempt_id)
                if att is None:
                    raise KeyError(f"no attempt {inp.attempt_id}")
                answers, version = _load_answers(c, inp.attempt_id)
                out.update(
                    student_id=att.student_id,
                    attempt_created_at=att.created_at.isoformat(),
                    version=version,
                    answers=[_j(a) for a in answers],
                )
            if state.get("content") is not None:  # save found the test changed
                _carry_over(state, out)
            return out

        return await run.db.run(load)

    async def ai_key_fast(state: GradeState) -> dict[str, Any]:
        content = _content(state)
        keys = _keys(state)
        needed = set(key_rules.key_needed(content, keys.values()))
        new_keys = dict(state.get("keys") or {})
        writes = list(state.get("key_writes") or [])
        pendings: list[PendingReview] = []
        sections = [
            s
            for s in content.sections
            if s.graded and any(q.id in needed for g in s.groups for q in g.questions)
        ]
        now = datetime.now(UTC)
        for i, s in enumerate(sections, 1):
            qids = [q.id for g in s.groups for q in g.questions if q.id in needed]
            result = await call(
                "ai_key_fast",
                {
                    "section_id": s.id,
                    "section_text": _section_text(s),  # the whole section, as context
                    "question_ids": qids,
                    # the prompt names only the questions without a key (step 22.5.4)
                    "key_questions": ", ".join(qids),
                },
                state,
            )
            report_progress(i, len(sections), s.id, unit="section")
            got: set[str] = set()
            if isinstance(result, CallResult):
                parsed = result.parsed
                assert isinstance(parsed, AiKeyOut)
                conf = await field_confidences(
                    result, AiKeyOut, fallback=client.config.confidence.fallback
                )
                for j, item in enumerate(parsed.keys):
                    if item.question_id not in qids or item.question_id in got:
                        continue
                    fc = conf.get(f"keys[{j}].accepted[0]")
                    key = AnswerKey(
                        test_id=_input(state).test_id,
                        question_id=item.question_id,
                        accepted=key_rules.with_forms(
                            list(item.accepted), key_rules.find_question(content, item.question_id)
                        ),
                        reason_vi=item.reason_vi,
                        source="ai",
                        status="ai_unverified",
                        confidence=float(fc.confidence) if fc and not fc.low_trust else None,
                        updated_at=now,
                    )
                    new_keys[item.question_id] = _j(key)
                    writes.append(item.question_id)
                    got.add(item.question_id)
            missing = [q for q in qids if q not in got]
            pendings.extend(key_rules.key_failed_reviews(state["run_id"], missing))
        return {
            "keys": new_keys,
            "key_writes": writes,
            "pending_reviews": [_j(p) for p in pendings],
        }

    async def verify_gate(state: GradeState) -> dict[str, Any]:
        answers = _answers(state) if state.get("attempt_id") else None
        todo = key_rules.questions_to_verify(
            _content(state),
            _keys(state).values(),
            margin_threshold=th.key_margin,
            answers=answers,
        )
        return {"to_verify": todo}

    async def verify_key(state: GradeState) -> dict[str, Any]:
        content = _content(state)
        keys = _keys(state)
        new_keys = dict(state.get("keys") or {})
        writes = list(state.get("key_writes") or [])
        pendings: list[PendingReview] = []
        todo = list(state.get("to_verify") or [])
        now = datetime.now(UTC)
        for i, qid in enumerate(todo, 1):
            key = keys[qid]
            result = await call(
                "verify_key",
                {"question_id": qid, "question_text": _question_text(content, qid)},
                state,
            )
            report_progress(i, len(todo), qid, unit="question")
            agree = False
            checked: VerifyKeyOut | None = None
            if isinstance(result, CallResult):
                parsed = result.parsed
                assert isinstance(parsed, VerifyKeyOut)
                checked = parsed
                agree = not key_rules.checker_unsure(parsed.answer) and value_norm(
                    parsed.answer
                ) in {value_norm(a) for a in key.accepted}
            if agree:
                new = key.model_copy(
                    update={"status": "ai_verified", "updated_at": now, "checker": None}
                )
            else:  # disagreed, unsure (`?`), truncated or failed twice (llm-design §5.1)
                new, review = key_rules.verify_failed(key, state["run_id"], now, checked)
                pendings.append(review)
            new_keys[qid] = _j(new)
            writes.append(qid)
        return {
            "keys": new_keys,
            "key_writes": writes,
            "pending_reviews": [_j(p) for p in pendings],
        }

    async def tag_skills(state: GradeState) -> dict[str, Any]:
        content = _content(state)
        have = state.get("tags") or {}
        reloaded = (state.get("saved") or {}).get("status") == "test_changed"
        todo = untagged(content, have) if reloaded else None
        if have and not todo:
            return {}  # once per test: question_tags exist
        # a reload after the test changed (R22.6.6.3) tags only the questions without tags
        sections = [
            s
            for s in content.sections
            if s.graded and any(todo is None or q.id in todo for g in s.groups for q in g.questions)
        ]
        tags: dict[str, list[str]] = {}
        levels: dict[str, str | None] = {}
        # one call per graded section, with its heading, instructions, passage and questions
        # (step 22.5.4); a failed call skips that section's tags (llm-design §5.1)
        for i, s in enumerate(sections, 1):
            qids = [q.id for g in s.groups for q in g.questions if todo is None or q.id in todo]
            result = await call(
                "tag_skills",
                {
                    "section_id": s.id,
                    "question_ids": qids,
                    "skill_list": skill_list_text(),
                    "section_text": _section_text(s),
                },
                state,
            )
            report_progress(i, len(sections), s.id, unit="section")
            if isinstance(result, CallFailure):
                continue
            known = set(qids)
            for item in result.parsed.model_dump()["items"]:
                if item["question_id"] in known:
                    tags[item["question_id"]] = list(dict.fromkeys(item["tags"]))[:3]
                    levels[item["question_id"]] = item.get("level")
        if have:  # the reload: the earlier tags stay; save writes only the new ones
            if not tags:
                return {}
            return {
                "tags": {**have, **tags},
                "tag_levels": {**(state.get("tag_levels") or {}), **levels},
                "tags_new": True,
            }
        return {"tags": tags, "tag_levels": levels, "tags_new": bool(tags)}

    async def grade(state: GradeState) -> dict[str, Any]:
        out: dict[str, Any] = {"grade_passes": int(state.get("grade_passes") or 0) + 1}
        answers = _answers(state)
        if state.get("reload"):
            attempt_id = state.get("attempt_id")
            assert attempt_id is not None
            answers, version = await current_run().db.run(lambda c: _load_answers(c, attempt_id))
            out.update(answers=[_j(a) for a in answers], version=version, reload=False)
        answers = _with_norm(answers)
        result = scoring.grade(_content(state), answers, _keys(state).values())
        out.update(graded=_j(result), judged={})
        return out

    async def judge_rewrites(state: GradeState) -> dict[str, Any]:
        content = _content(state)
        keys = _keys(state)
        answers = {a.question_id: a for a in _answers(state)}
        graded = scoring.GradeResult.model_validate(state["graded"])
        judged: dict[str, scoring.JudgeResult] = {}
        for i, qid in enumerate(graded.to_judge, 1):
            ans = answers[qid]
            result = await call(
                "judge_rewrites",
                {
                    "question_text": _question_text(content, qid),
                    "accepted": _accepted_text(keys.get(qid)),
                    "student_answer": scoring.effective_value(ans) or "",
                },
                state,
            )
            report_progress(i, len(graded.to_judge), qid, unit="question")
            if isinstance(result, CallFailure):
                judged[qid] = "failed"  # B.5 row 14
            else:
                parsed = result.parsed
                assert isinstance(parsed, JudgeOut)
                judged[qid] = parsed.verdict
        final = scoring.grade(
            content, _with_norm(list(answers.values())), keys.values(), judged=judged
        )
        return {"graded": _j(final), "judged": dict(judged)}

    async def explain(state: GradeState) -> dict[str, Any]:
        content = _content(state)
        keys = _keys(state)
        test_id = _input(state).test_id
        graded = scoring.GradeResult.model_validate(state["graded"])
        made = [Explanation.model_validate(e) for e in state.get("explanations") or []]
        index = await current_run().db.run(lambda c: _explanation_index(c, test_id, made))
        tags = state.get("tags") or {}
        todo = [
            a
            for a in graded.answers
            if a.verdict == "incorrect" and a.value_norm  # blanks are not explained
        ]
        new: list[Explanation] = []
        for i, ans in enumerate(todo, 1):
            norm = cast(str, ans.value_norm)
            if (ans.question_id, norm) in index:
                continue  # cache hit
            result = await call(
                "explain",
                {
                    "question_text": _question_text(content, ans.question_id),
                    "accepted": _accepted_text(keys.get(ans.question_id)),
                    "student_answer": scoring.effective_value(ans) or "",
                    "skill_tags": ", ".join(tags.get(ans.question_id, [])) or "(none)",
                },
                state,
            )
            report_progress(i, len(todo), ans.question_id, unit="question")
            if isinstance(result, CallFailure):
                continue  # llm-design §5.1: no explanation
            parsed = result.parsed
            assert isinstance(parsed, ExplainOut)
            e = Explanation(
                test_id=test_id,
                question_id=ans.question_id,
                wrong_answer_norm=norm,
                error_type=parsed.error_type,
                text_vi=parsed.text_vi,
                status="ai",
                llm_call_id=result.llm_call_id,
            )
            new.append(e)
            index[(e.question_id, e.wrong_answer_norm)] = e
        return {"explanations": [_j(e) for e in [*made, *new]]}

    async def weak_points(state: GradeState) -> dict[str, Any]:
        test_id = _input(state).test_id
        attempt_id = cast(str, state.get("attempt_id"))
        graded = scoring.GradeResult.model_validate(state["graded"])
        made = [Explanation.model_validate(e) for e in state.get("explanations") or []]
        student_id = state.get("student_id")

        def load(c: sqlite3.Connection) -> tuple[dict[tuple[str, str], Any], _PaperContext]:
            idx = {k: e.error_type for k, e in _explanation_index(c, test_id, made).items()}
            history = (
                attempt_repo.student_paper_skills(c, student_id, exclude_attempt_id=attempt_id)
                if student_id
                else []
            )
            att = attempt_repo.get_attempt(c, attempt_id)
            test = test_repo.get_test(c, test_id)
            return idx, _PaperContext(
                history=history,
                taken_on=att.taken_on if att else None,
                forms=attempt_repo.answer_forms(test) if test else {},
                option_counts=attempt_repo.option_counts(test) if test else {},
                levels=test_repo.list_tag_levels(c, test_id),
            )

        index, ctx = await current_run().db.run(load)
        created = datetime.fromisoformat(cast(str, state.get("attempt_created_at")))
        tags = state.get("tags") or {}
        levels = ctx.levels
        if state.get("tags_new"):
            # a first grade: tag_skills just gave the levels and ``save`` stores them only after
            # this node, so the state's levels win over the stored ones (step 22.5.5 verifier)
            fresh = state.get("tag_levels") or {}
            levels = {
                **ctx.levels,
                **{
                    q: {t: tag_level(t, fresh.get(q)) for t in ts}
                    for q, ts in tags.items()
                    if not fresh or q in fresh
                },
            }
        current = wp.attempt_stats(attempt_id, created, graded.answers, tags, index)
        # D11, D11c-e: weak points from the student's trajectory, basics first
        paper = wp.paper_skill_results(
            attempt_id,
            ctx.taken_on or created.astimezone().date(),
            created,
            graded.answers,
            tags,
            ctx.forms,
            index,
            levels,
            ctx.option_counts,
        )
        trajectory = wp.trajectories([*ctx.history, *paper])
        ranked = wp.report_weak_points(current, paper, trajectory)
        keys = _keys(state)
        notes = wp.careless_notes(graded.answers, keys.values(), index)

        # D11e: the summary request names no held-back skill, in either block
        held_back = {w.skill_tag for w in ranked if w.held_back}
        wrong_lines = []
        for a in graded.answers:
            if a.verdict != "incorrect":
                continue
            q_tags = tags.get(a.question_id, [])
            shown = [t for t in q_tags if t not in held_back]
            if q_tags and not shown:
                continue  # only held-back skills: left out
            key = keys.get(a.question_id)
            etype = index.get((a.question_id, a.value_norm or ""))
            wrong_lines.append(
                f"- no. {a.printed_number}: {scoring.effective_value(a) or '(blank)'}"
                f" → {key.accepted[0] if key and key.accepted else '?'}"
                f" [{', '.join(skill_name(t) for t in shown)}]" + (f" ({etype})" if etype else "")
            )
        result = await call(
            "weak_points_summary",
            {
                "score_text": (
                    f"{graded.score_earned:g}/{graded.score_possible:g},"
                    f" {graded.uncertain_points:g} unsure"
                ),
                "weak_points": wp.summary_lines(ranked, skill_name),  # D11e: names, no held back
                "wrong_answers": "\n".join(wrong_lines) or "(none)",
            },
            state,
        )
        summary_vi = ""
        questions: list[Any] = []
        if isinstance(result, CallResult):  # §5.1: a failure → ranked skills, no narrative
            parsed = result.parsed
            assert isinstance(parsed, SummaryOut)
            summary_vi = parsed.summary_vi
            questions = list(parsed.teacher_questions)
        report = GradeReport(
            attempt_id=attempt_id,
            run_id=state["run_id"],
            weak_points=ranked,  # note_vi stays "": no documented source (step 18 report)
            careless_notes=notes,
            summary_vi=summary_vi,
            teacher_questions=questions,
            uncertain_points=graded.uncertain_points,
            created_at=datetime.now(UTC),
        )
        return {"report": _j(report)}

    async def save(state: GradeState) -> Any:
        saved = await current_run().db.run(lambda c: save_grade(c, state))
        if saved["status"] == "version_mismatch":
            # data-model §5.2: reload and redo grade → weak_points (not a C.2 edge)
            return Command(goto="grade", update={"saved": saved, "reload": True})
        if saved["status"] == "test_changed":
            # R22.6.6.3: load the saved test (and the answers) and redo from there
            return Command(goto="load_context", update={"saved": saved})
        return {"saved": saved}

    # --- routing -----------------------------------------------------------------------------

    def key_needed_route(state: GradeState) -> str:
        if key_rules.key_needed(_content(state), _keys(state).values()):
            return "ai_key_fast"
        return "verify_gate"

    def verify_route(state: GradeState) -> str:
        return "verify_key" if state.get("to_verify") else "tag_skills"

    def attempt_route(state: GradeState) -> str:
        return "grade" if state.get("attempt_id") else "save"

    def judge_route(state: GradeState) -> str:
        graded = state.get("graded") or {}
        return "judge_rewrites" if graded.get("to_judge") else "explain"

    def factory(checkpointer: Any) -> Any:
        b: Any = StateGraph(GradeState)
        b.add_node("load_context", step("load_context", load_context))
        b.add_node("ai_key_fast", step("ai_key_fast", ai_key_fast))
        b.add_node("verify_gate", step("verify_gate", verify_gate))
        b.add_node("verify_key", step("verify_key", verify_key))
        b.add_node("tag_skills", step("tag_skills", tag_skills))
        b.add_node("grade", step("grade", grade))
        b.add_node("judge_rewrites", step("judge_rewrites", judge_rewrites))
        b.add_node("explain", step("explain", explain))
        b.add_node("weak_points", step("weak_points", weak_points))
        b.add_node("save", step("save", save))

        b.add_edge(START, "load_context")
        b.add_conditional_edges("load_context", key_needed_route, ["ai_key_fast", "verify_gate"])
        b.add_edge("ai_key_fast", "verify_gate")
        b.add_conditional_edges("verify_gate", verify_route, ["verify_key", "tag_skills"])
        b.add_edge("verify_key", "tag_skills")
        b.add_conditional_edges("tag_skills", attempt_route, ["grade", "save"])
        b.add_conditional_edges("grade", judge_route, ["judge_rewrites", "explain"])
        b.add_edge("judge_rewrites", "explain")
        b.add_edge("explain", "weak_points")
        b.add_edge("weak_points", "save")
        b.add_edge("save", END)
        return b.compile(checkpointer=checkpointer)

    return factory


def register_grade(manager: Any, deps: GradeDeps) -> None:
    """Register the grade graph with a ``RunManager``."""
    manager.register("grade", build_grade_graph(deps), stages=GRADE_STAGES)
