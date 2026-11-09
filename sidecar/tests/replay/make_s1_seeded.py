"""Regenerate the SYNTHETIC ``tests/cassettes/s1-seeded/`` scenarios (step 19, R19.1 and R19.5).

    cd sidecar
    uv run python tests/replay/make_s1_seeded.py

An S1-like test seeded to plan Appendix **B.6**: 3 pages x 12 MCQs, each page one section printed
"(3 pts)", so 36 questions x 0.25 = 9 points. The student circles ``A`` everywhere; the AI key is
``A`` except 4 questions (key ``B``, so 4 incorrect: 2 explained as ``gap``, 2 as ``careless``,
which gives a weak point and careless notes); 2 readings carry an ``alt_question_id`` (a span
near two questions, so confidence ``t - 0.01``, ``reading_unsure`` → uncertain). That is 30
correct x 0.25 = **7.5/9**, with **0.5** uncertain points.

Every scenario is recorded through the real CLI (``etach record``, the real prompts) over the
schema-routed fake of ``make_synthetic_grade.py``, all in one data folder, in this order:

- ``extract``: the filled test (student name: the placeholder ``Học Sinh A``);
- ``grade``: ``--after extract``, the attempt graded (keys, verify of the 4 wrong keys, tags,
  notes, 4 explains, the summary with 3 teacher questions);
- ``student-b-extract`` + ``student-b-grade``: a second attempt on the same test (``--existing``,
  the name not read), graded;
- ``regrade-a`` + ``regrade-b``: after the teacher verifies the first question's key (``A``,
  unchanged), both attempts graded again (what the key editor's fan-out queues, R19.5);
- ``fix-a``: the teacher fixes attempt A's first unsure reading to ``A`` in Review (correct, so no
  new wrong answer and no explain) → A graded again: **7.75/9**, 0.25 unsure (R19.4);
- ``points-extract`` + ``points-grade`` + ``points-regrade`` (a data folder of their own): a
  one-page test of 12 MCQs with **no printed points** (0.25 each assumed, a ``points_assumed``
  item), all answered ``A`` = the key → **3/3**; the teacher sets 0.5 per question in Review →
  graded again: **6/6** (R19.7).

All content is made up here; no student data. The E2E (``app/e2e/s5-grade.spec.ts``) replays the
whole folder in a sidecar of its own and repeats these steps through the UI and the API.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
OUT_ROOT = TESTS / "cassettes" / "s1-seeded"
PER_PAGE = 12
PAGES = 3
ROMAN = ["I", "II", "III"]
WRONG = (3, 14, 22, 33)  # 0-based question positions whose key is B (the student wrote A)
CARELESS = (14, 33)  # of those, explained as careless (the other two: gap)
UNSURE = (6, 27)  # readings with an alt_question_id (the next question) → reading_unsure

sys.path.insert(0, str(TESTS))


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SG = _load("_etach_make_synthetic_grade", HERE / "make_synthetic_grade.py")
MS = SG.MS


def page_out(page_no: int) -> dict[str, Any]:
    opts = [{"label": x, "text": f"opt {x.lower()}"} for x in "ABCD"]
    first = (page_no - 1) * PER_PAGE + 1
    questions = [
        {
            "printed_number": n,
            "answer_form": "choice",
            "stem": f"Seeded page {page_no} question {n}: choose the best answer {n}",
            "options": opts,
            "cue": None,
        }
        for n in range(first, first + PER_PAGE)
    ]
    return {
        "header_text": MS.HEADER if page_no == 1 else None,
        "sections": [
            {
                "printed_title": ROMAN[page_no - 1],
                "instructions": "Choose the best answer.",
                "kind": "questions",
                "skill": "grammar",
                "points_text": "(3 pts)",
                "range_first": None,
                "range_last": None,
                "groups": [{"stimulus": None, "pictures": [], "questions": questions}],
            }
        ],
    }


def make_answers(unsure: set[str], student: str | None, klass: str | None) -> Any:
    def build(ids: list[str]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for i, qid in enumerate(ids):
            alt = ids[i + 1] if qid in unsure and i + 1 < len(ids) else None
            out[qid] = [{"value": "A", "location": "circled_option", "alt_question_id": alt}]
        return {"student_name": student, "class_name": klass, "answers": out}

    return build


def explain_for(careless: set[str]) -> Any:
    def build(body: dict[str, Any]) -> dict[str, Any]:
        ids = SG._prompt_ids(body)
        kind = "careless" if ids and ids[0] in careless else "gap"
        return {"reasoning": "Giả lập.", "text_vi": "Giải thích giả lập.", "error_type": kind}

    return build


def check_b6(data: Path, attempt_id: str) -> None:
    """B.6: 7.5/9 with 0.5 uncertain points; 30/4/2 verdicts; 3 teacher questions; a weak point
    and careless notes."""
    conn = sqlite3.connect(data / "app.db")
    try:
        earned, possible = conn.execute(
            "SELECT score_earned, score_possible FROM attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        verdicts = dict(
            conn.execute(
                "SELECT verdict, COUNT(*) FROM answers WHERE attempt_id = ? GROUP BY verdict",
                (attempt_id,),
            ).fetchall()
        )
        unsure, tq, weak, careless = conn.execute(
            "SELECT uncertain_points, teacher_questions, weak_points, careless_notes"
            " FROM grade_reports WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
    finally:
        conn.close()
    got = (earned, possible, unsure, verdicts)
    counts = (len(json.loads(tq)), len(json.loads(weak)), len(json.loads(careless)))
    print(f"{attempt_id}: earned/possible/uncertain/verdicts = {got}; tq/weak/careless = {counts}")
    assert got == (7.5, 9.0, 0.5, {"correct": 30, "incorrect": 4, "uncertain": 2}), got
    assert 3 <= counts[0] <= 5 and counts[1] >= 1 and counts[2] >= 1, counts


def score(data: Path, attempt_id: str) -> tuple[float, float, float]:
    conn = sqlite3.connect(data / "app.db")
    try:
        earned, possible = conn.execute(
            "SELECT score_earned, score_possible FROM attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        (unsure,) = conn.execute(
            "SELECT uncertain_points FROM grade_reports WHERE attempt_id = ?", (attempt_id,)
        ).fetchone()
    finally:
        conn.close()
    return (earned, possible, unsure)


def review_fix(data: Path, kind: str, where: str, args: tuple[Any, ...], value: Any) -> None:
    """The teacher's Review fix on the one open ``kind`` item matching ``where``."""
    from etach.domain import review
    from etach.store import db

    conn = db.connect(data / "app.db")
    try:
        rows = conn.execute(
            f"SELECT id FROM review_items WHERE kind = ? AND status = 'open' AND {where}",
            (kind, *args),
        ).fetchall()
        assert len(rows) == 1, rows
        review.resolve(conn, rows[0][0], "fix", value)
    finally:
        conn.close()


def record_points(etach: Any, work: Path) -> None:
    """R19.7: a test with no printed points, graded, then 0.5 per question set in Review."""
    data = work / "points-data"
    pages = [str(MS.photo(work, "De-points (1).jpg", 160))]
    out = page_out(1)
    section = out["sections"][0]
    section["points_text"] = None
    section["printed_title"] = "PART ONE"
    for q in section["groups"][0]["questions"]:
        q["stem"] = q["stem"].replace("Seeded page", "Points page")
    ex = etach(
        "record", "--out", OUT_ROOT / "points-extract", "--",
        "run", "--data", data, "--pages", *pages,
        queues={"TranscribeOut": [out],
                "ReadAnswersCall": [make_answers(set(), MS.STUDENT, MS.CLASS)]},
    )  # fmt: skip
    test_id, attempt = ex["test_id"], ex["attempt_id"]
    keys = SG.Keys(data)
    etach.record_grade(OUT_ROOT / "points-grade", OUT_ROOT / "points-extract", data,
                     ["--attempt", attempt], SG.grade_queues(keys, explain=0))  # fmt: skip
    got = score(data, attempt)
    print(f"points-grade: {got}")
    assert got == (3.0, 3.0, 0.0), got
    review_fix(data, "points_assumed", "test_id = ?", (test_id,), {"points_per_question": 0.5})
    etach.record_grade(OUT_ROOT / "points-regrade", OUT_ROOT / "points-extract", data,
                     ["--attempt", attempt], SG.grade_queues(keys, explain=0))  # fmt: skip
    got = score(data, attempt)
    print(f"points-regrade: {got}")
    assert got == (6.0, 6.0, 0.0), got


def main() -> int:
    etach = SG.Cli()
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        data = work / "data"
        pages = [str(MS.photo(work, f"De-seeded ({i}).jpg", 120 + i)) for i in range(1, 4)]
        transcribe = {"TranscribeOut": [page_out(p) for p in range(1, PAGES + 1)]}

        # 1. extract: the question IDs depend only on the content, so a dry run gives them
        dry = etach(
            "run", "--data", work / "dry", "--pages", *pages,
            queues={**transcribe, "ReadAnswersCall": [MS.EMPTY] * PAGES},
        )  # fmt: skip
        qids = SG.question_ids(work / "dry")
        assert len(qids) == PAGES * PER_PAGE, len(qids)
        del dry
        unsure = {qids[i] for i in UNSURE}
        answers_a = make_answers(unsure, MS.STUDENT, MS.CLASS)
        ex = etach(
            "record", "--out", OUT_ROOT / "extract", "--",
            "run", "--data", data, "--pages", *pages,
            queues={**transcribe, "ReadAnswersCall": [answers_a] * PAGES},
        )  # fmt: skip
        test_id, attempt_a = ex["test_id"], ex["attempt_id"]

        # 2. grade A (B.6)
        keys = SG.Keys(data, b={qids[i] for i in WRONG})
        queues = SG.grade_queues(keys, explain=0)
        queues["ExplainOut"] = [explain_for({qids[i] for i in CARELESS})] * len(WRONG)
        etach.record_grade(OUT_ROOT / "grade", OUT_ROOT / "extract", data,
                         ["--attempt", attempt_a], queues)  # fmt: skip
        check_b6(data, attempt_a)

        # 3. student B on the same test (the name not read), graded
        header = {"header_text": MS.HEADER, "first_stems": [page_out(1)["sections"][0]["groups"]
                                                             [0]["questions"][i]["stem"]
                                                             for i in range(3)]}  # fmt: skip
        second = etach(
            "record", "--out", OUT_ROOT / "student-b-extract", "--",
            "run", "--data", data, "--pages", *pages, "--existing", test_id,
            queues={"ReadHeaderOut": [header],
                    "ReadAnswersCall": [make_answers(unsure, None, None)] * PAGES},
        )  # fmt: skip
        attempt_b = second["attempt_id"]
        etach.record_grade(OUT_ROOT / "student-b-grade", OUT_ROOT / "student-b-extract", data,
                         ["--attempt", attempt_b], SG.grade_queues(keys, explain=0))  # fmt: skip
        check_b6(data, attempt_b)

        # 4. the teacher verifies q1's key (A, unchanged) → both attempts graded again
        SG.teacher_key(data, test_id, qids[0], "A")
        for name, att in (("regrade-a", attempt_a), ("regrade-b", attempt_b)):
            after = OUT_ROOT / ("extract" if name == "regrade-a" else "student-b-extract")
            etach.record_grade(OUT_ROOT / name, after, data, ["--attempt", att],
                             SG.grade_queues(keys, explain=0))  # fmt: skip
            check_b6(data, att)

        # 5. the teacher fixes A's first unsure reading (A = the key) in Review → A graded again
        review_fix(data, "uncertain_answer", "attempt_id = ? AND question_id = ?",
                   (attempt_a, qids[UNSURE[0]]), "A")  # fmt: skip
        etach.record_grade(OUT_ROOT / "fix-a", OUT_ROOT / "extract", data, ["--attempt", attempt_a],
                         SG.grade_queues(keys, explain=0))  # fmt: skip
        got = score(data, attempt_a)
        print(f"fix-a: {got}")
        assert got == (7.75, 9.0, 0.25), got

        # 6. R19.7's test (a data folder of its own)
        record_points(etach, work)
    print(json.dumps({"wrote": str(OUT_ROOT), "test_id": test_id}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
