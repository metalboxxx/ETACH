"""Regenerate the SYNTHETIC grade cassettes in ``tests/cassettes/grade-synthetic/`` (step 18).

    cd sidecar
    uv run python tests/replay/make_synthetic_grade.py

Each grade scenario is recorded with ``etach record --out <scenario> --after <extract dir> -- grade
…`` (the real CLI, the real prompts) over a schema-routed FakeOllama, after replaying its extract
scenario into a fresh data folder, so every folder holds the cassettes and ``grade.json`` exactly
like a live recording. All content is synthetic (made up here, or the synthetic extract
scenarios); the ``blank`` extract scenario is the teacher's signed-off blank test, which holds no
student data. The scenarios (``S1L`` = ``extract-synthetic/s1-like``: six MCQs, every answer
``A``; the AI key is ``A`` except question 2 = ``B``):

- ``first-grade``: S1L graded from nothing (keys, verify of the wrong q2, tags, notes, explain q2).
- ``regrade-after-verify``: then the teacher sets q1's key to ``C`` (teacher_verified) → re-grade.
- ``student-b-extract`` (an extract scenario, ``--existing``) + ``student-b-grade``: after
  ``first-grade`` and the teacher verifying every key, a second student (name not
  read, so not student A) with the same answers is read and graded.
- ``truncated-verify``: S1L graded with q2's ``verify_key`` truncated (both tries).
- ``key-photo``: ``extract-synthetic/key-photo`` (keys from the key photos) graded.
- ``blank-key``: the ``blank`` test graded with no attempt (the key copy).

The multi-step scenarios name their extract scenario in ``grade.json`` as usual; the steps before
it (the earlier grade, the teacher's key edit) are redone by the replay tests
(``test_grade_synthetic.py``) in the same order as here.
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
CASSETTES = TESTS / "cassettes"
OUT_ROOT = CASSETTES / "grade-synthetic"
S1L = CASSETTES / "extract-synthetic" / "s1-like"
KEY_PHOTO = CASSETTES / "extract-synthetic" / "key-photo"
BLANK = CASSETTES / "blank"
#: Recordings made with ``retranscribe_tiles`` on and the tiles always kept (speed bundle 1
#: made both settings: off and "better" by default).
RECORDED_WITH_TILES = frozenset({"blank", "validator-retry"})


def tiles_on(data: Path) -> None:
    data.mkdir(parents=True, exist_ok=True)
    (data / "models.toml").write_text(
        '[extract]\nretranscribe_tiles = true\nretranscribe_tiles_keep = "always"\n',
        encoding="utf-8",
    )


sys.path.insert(0, str(TESTS))


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MS = _load("_etach_make_synthetic", HERE / "make_synthetic.py")
GX = MS.G  # the step 9 extract graph tests (page_out, _answer_ids)
from support.fake_ollama import ChatScript, FakeOllama  # noqa: E402

QID = re.compile(r"\bq-[0-9a-f]{8}\b")
BAD = "not json at all"
TRUNCATED = '{"reasoning": "The sentence talks about a finished action, so the ans'

TAGS = ["GR-PSV-A1"]
SUMMARY = {
    "summary_vi": "Bài làm tổng hợp (dữ liệu giả lập).",
    "teacher_questions": [
        {"question_vi": f"Câu hỏi giả lập {i}?", "what_answers_mean_vi": "Ý nghĩa giả lập."}
        for i in (1, 2, 3)
    ],
}
EXPLAIN = {"reasoning": "Giả lập.", "text_vi": "Giải thích giả lập.", "error_type": "gap"}


class GradeFake(FakeOllama):
    """Answers by the request's schema title. Grade items may be a function of the request body;
    extract items follow the step 9 ``Routed`` (a function of the requested question IDs). An
    empty queue answers invalid JSON."""

    def __init__(self) -> None:
        super().__init__()
        self.queues: dict[str, list[Any]] = {}
        self.seen: list[str] = []

    def _script(self) -> ChatScript:
        body = self.requests[-1]
        fmt = body.get("format")
        title = fmt.get("title") if isinstance(fmt, dict) else None
        if title is None or title not in self.queues:
            text = json.dumps(body, ensure_ascii=False)
            title = next((t for t in self.queues if f'"{t}"' in text), title)
        self.seen.append(str(title))
        queue = self.queues.get(str(title)) or []
        item = queue.pop(0) if queue else BAD
        if isinstance(item, ChatScript):
            return item
        if callable(item):
            item = item(body) if title not in GX.TITLES else item(GX._answer_ids(fmt))
        text = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        return ChatScript(tokens=list(text))


def _prompt_ids(body: dict[str, Any]) -> list[str]:
    text = "\n".join(str(m.get("content", "")) for m in body.get("messages") or [])
    return list(dict.fromkeys(QID.findall(text)))


class Keys:
    """The synthetic key: ``A`` for an MCQ (``B`` for the questions in ``b``), ``word`` else."""

    def __init__(self, data: Path, b: set[str] | None = None) -> None:
        self.db = data / "app.db"
        self.b = b or set()
        self.made: dict[str, str] = {}

    def _types(self) -> dict[str, str]:
        conn = sqlite3.connect(self.db)
        try:
            content = json.loads(conn.execute("SELECT content FROM tests").fetchone()[0])
        finally:
            conn.close()
        return {
            q["id"]: q["answer_form"]
            for s in content["sections"]
            for g in s["groups"]
            for q in g["questions"]
        }

    def ai_key(self, body: dict[str, Any]) -> dict[str, Any]:
        types = self._types()
        items = []
        for qid in _prompt_ids(body):
            answer = ("B" if qid in self.b else "A") if types.get(qid) == "choice" else "word"
            self.made[qid] = answer
            items.append({"question_id": qid, "accepted": [answer], "reason_vi": "Giả lập."})
        return {"keys": items}

    def stored(self, qid: str) -> str | None:
        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute(
                "SELECT accepted FROM answer_keys WHERE question_id = ?", (qid,)
            ).fetchone()
        finally:
            conn.close()
        return json.loads(row[0])[0] if row else None

    def verify(self, body: dict[str, Any]) -> dict[str, Any]:
        qid = _prompt_ids(body)[0]
        answer = self.made.get(qid) or self.stored(qid) or "A"
        return {"reasoning": "Giả lập.", "answer": answer}


def tags(body: dict[str, Any]) -> dict[str, Any]:
    return {"items": [{"question_id": q, "tags": TAGS, "level": None} for q in _prompt_ids(body)]}


def grade_queues(keys: Keys, *, explain: int, verify: list[Any] | None = None) -> dict[str, Any]:
    return {
        "AiKeyOut": [keys.ai_key] * 20,
        "VerifyKeyOut": verify if verify is not None else [keys.verify] * 60,
        "TagSkillsCall": [tags],
        "JudgeOut": [],
        "ExplainOut": [EXPLAIN] * explain,
        "SummaryOut": [SUMMARY],
    }


class Cli:
    def __init__(self) -> None:
        from etach import cli

        self.cli = cli
        self.fake = GradeFake()

    def __call__(self, *args: str | Path, queues: dict[str, list[Any]] | None = None) -> Any:
        self.fake.queues = {k: list(v) for k, v in (queues or {}).items()}
        self.cli._TEST_TRANSPORT = self.fake.transport if queues is not None else None
        argv = [str(a) for a in args]
        buf = io.StringIO()
        real = sys.stdout
        sys.stdout = buf
        try:
            code = self.cli.main(argv)
        finally:
            sys.stdout = real
            self.cli._TEST_TRANSPORT = None
        assert code == 0, f"etach {' '.join(argv)} exited {code}"
        return json.loads(buf.getvalue().strip().splitlines()[-1])

    def record_grade(
        self, out: Path, after: Path, data: Path, target: list[str], queues: dict[str, Any]
    ) -> Any:
        if out.exists():
            shutil.rmtree(out)
        cmd = ["record", "--out", out, "--after", after, "--", "grade", "--data", data, *target]
        return self(*cmd, queues=queues)


def teacher_key(data: Path, test_id: str, qid: str, accepted: str) -> None:
    """The teacher's key editor: ``qid``'s key set (or confirmed) as ``teacher_verified``."""
    from etach.domain.models import AnswerKey
    from etach.store import db
    from etach.store.repos import keys as key_repo

    conn = db.connect(data / "app.db")
    try:
        key_repo.upsert_key(
            conn,
            AnswerKey(
                test_id=test_id,
                question_id=qid,
                accepted=[accepted],
                reason_vi="Giáo viên.",
                source="teacher_edit",
                status="teacher_verified",
                confidence=None,
                updated_at=datetime.now(UTC),
            ),
        )
    finally:
        conn.close()


def question_ids(data: Path) -> list[str]:
    return list(Keys(data)._types())


def main() -> int:
    etach = Cli()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)

        def fresh(name: str, extract: Path) -> tuple[Path, dict[str, Any]]:
            data = work / f"data-{name}"
            if extract.name in RECORDED_WITH_TILES:  # replay as recorded (speed bundle 1)
                tiles_on(data)
            return data, etach("run", "--data", data, "--replay", extract)

        # first-grade, then regrade-after-verify (R18.8)
        data, ex = fresh("regrade", S1L)
        qids = question_ids(data)
        keys = Keys(data, b={qids[1]})
        attempt = ["--attempt", ex["attempt_id"]]
        etach.record_grade(
            OUT_ROOT / "first-grade", S1L, data, attempt, grade_queues(keys, explain=1)
        )
        teacher_key(data, ex["test_id"], qids[0], "C")
        etach.record_grade(
            OUT_ROOT / "regrade-after-verify", S1L, data, attempt, grade_queues(keys, explain=1)
        )

        # student B on the graded test (R18.5)
        data, ex = fresh("student-b", S1L)
        etach("grade", "--data", data, "--attempt", ex["attempt_id"],
            "--replay", OUT_ROOT / "first-grade")  # fmt: skip
        for qid in question_ids(data):
            stored = Keys(data).stored(qid)
            assert stored is not None
            teacher_key(data, ex["test_id"], qid, stored)
        pages = [str(MS.photo(work, f"De-synthetic ({i}).jpg", 200 + i)) for i in (1, 2)]
        header = {"header_text": MS.HEADER, "first_stems": MS.stems()[:3]}

        def answers_b(ids: list[str]) -> dict[str, Any]:
            # the name is not read: ``etach scrub`` allows only the one placeholder name, and an
            # unread name makes this attempt another (unknown) student's
            return {**MS.answers()(ids), "student_name": None, "class_name": None}

        extract_b = OUT_ROOT / "student-b-extract"
        if extract_b.exists():
            shutil.rmtree(extract_b)
        second = etach(
            "record", "--out", extract_b, "--",
            "run", "--data", data, "--pages", *pages, "--existing", ex["test_id"],
            queues={"ReadHeaderOut": [header], "ReadAnswersCall": [answers_b, MS.EMPTY]},
        )  # fmt: skip
        etach.record_grade(
            OUT_ROOT / "student-b-grade",
            extract_b,
            data,
            ["--attempt", second["attempt_id"]],
            {"SummaryOut": [SUMMARY]},
        )

        # truncated-verify (R18.6)
        data, ex = fresh("truncated", S1L)
        keys = Keys(data, b={question_ids(data)[1]})
        trunc = [ChatScript(tokens=list(TRUNCATED))] * 2
        etach.record_grade(
            OUT_ROOT / "truncated-verify",
            S1L,
            data,
            ["--attempt", ex["attempt_id"]],
            grade_queues(keys, explain=1, verify=trunc),
        )

        # key-photo (R18.3)
        data, ex = fresh("key-photo", KEY_PHOTO)
        etach.record_grade(
            OUT_ROOT / "key-photo",
            KEY_PHOTO,
            data,
            ["--attempt", ex["attempt_id"]],
            grade_queues(Keys(data), explain=5),
        )

        # blank-key (R18.4)
        data, ex = fresh("blank", BLANK)
        etach.record_grade(
            OUT_ROOT / "blank-key",
            BLANK,
            data,
            ["--test", ex["test_id"]],
            grade_queues(Keys(data), explain=0),
        )
    print(f"wrote {OUT_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
