"""Regenerate the SYNTHETIC grade-eval cassettes in ``tests/cassettes/grade-eval/`` (M2).

    cd sidecar
    uv run python tests/unit/eval/make_grade_eval.py

For each synthetic fixture in ``tests/fixtures_synth/grade/tuning/`` it runs the real CLI,
``etach record --out tests/cassettes/grade-eval/<name> -- eval --graph grade --set tuning
--fixtures tests/fixtures_synth/grade --only <name> --history <temp>``, with a fake Ollama (no
model, no network) that answers by the request's schema and by the question IDs in the prompt.
So each folder holds the calls of that fixture's key run, then its verdict run, in order, exactly
like a live recording. All content is made up here.

The scripted answers (question keys of ``g1-mixed``; ``g2-blank`` gets its expected key):

- ``ai_key_fast``: the expected key, except question 2 (``B``; the truth is ``C``). It sends no
  logprobs, so every AI key has no margin and ``verify_gate`` sends all of them to
  ``verify_key``;
- ``verify_key``: agrees, except questions 2 (``C``) and 3 (``happy``) → ``ai_uncertain``;
- ``judge_rewrites``: ``incorrect`` for both rewrites (the teacher says 4 is correct);
- ``tag_skills`` / ``explain`` / ``weak_points_summary``: fixed text.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TESTS = HERE.parents[1]
SIDECAR = TESTS.parent
FIXTURES = TESTS / "fixtures_synth" / "grade"
OUT_ROOT = TESTS / "cassettes" / "grade-eval"

sys.path.insert(0, str(TESTS))

from support.fake_ollama import ChatScript, FakeOllama  # noqa: E402

QID = re.compile(r"\bq-[0-9a-f]{8}\b")
TAGS = ["GR-PSV-A1"]
SUMMARY = {
    "summary_vi": "Bài làm giả lập.",
    "teacher_questions": [
        {"question_vi": f"Câu hỏi giả lập {i}?", "what_answers_mean_vi": "Ý nghĩa giả lập."}
        for i in (1, 2, 3)
    ],
}
#: g1-mixed only: question key → the AI key / what verify_key answers / the judge's verdict
SCRIPTED = "g1-mixed"
AI_KEY = {"2": ["B"]}
VERIFY = {"2": "C", "3": "happy"}
JUDGE = {"4": "incorrect", "5": "incorrect"}


def _ids(text: str) -> list[str]:
    return list(dict.fromkeys(QID.findall(text)))


class EvalFake(FakeOllama):
    """Answers by the request's schema title, from the fixture's expected key."""

    def __init__(
        self, expected_key: dict[str, list[str]], ids: dict[str, str], scripted: bool
    ) -> None:
        super().__init__()
        self.key = expected_key
        self.qkey = {qid: k for k, qid in ids.items()}
        self.ai_key = AI_KEY if scripted else {}
        self.verify = VERIFY if scripted else {}
        self.judge = JUDGE if scripted else {}

    def _answer(self, title: str, body: dict[str, Any]) -> Any:
        text = "\n".join(str(m.get("content", "")) for m in body.get("messages") or [])
        qkeys = [self.qkey[q] for q in _ids(text) if q in self.qkey]
        if title == "AiKeyOut":
            return {
                "keys": [
                    {
                        "question_id": next(q for q, k in self.qkey.items() if k == qk),
                        "accepted": self.ai_key.get(qk, self.key[qk]),
                        "reason_vi": "Giả lập.",
                    }
                    for qk in qkeys
                ]
            }
        if title == "VerifyKeyOut":
            qk = qkeys[0]
            answer = self.verify.get(qk, self.ai_key.get(qk, self.key[qk])[0])
            return {"reasoning": "Giả lập.", "answer": answer}
        if title == "TagSkillsCall":
            ids = [q for q in _ids(text) if q in self.qkey]
            return {"items": [{"question_id": q, "tags": TAGS, "level": None} for q in ids]}
        if title == "JudgeOut":
            return {"reason": "Giả lập.", "verdict": self.judge.get(qkeys[0], "correct")}
        if title == "ExplainOut":
            return {
                "reasoning": "Giả lập.",
                "text_vi": f"Giải thích giả lập cho câu {qkeys[0]}.",
                "error_type": "gap",
            }
        if title == "SummaryOut":
            return SUMMARY
        raise AssertionError(f"unexpected schema {title}")

    def _script(self) -> ChatScript:
        body = self.requests[-1]
        fmt = body.get("format")
        title = fmt.get("title") if isinstance(fmt, dict) else None
        if title is None:
            text = json.dumps(body, ensure_ascii=False)
            title = next(t for t in ("TagSkillsCall",) if f'"{t}"' in text)
        answer = self._answer(str(title), body)
        return ChatScript(
            text=json.dumps(answer, ensure_ascii=False), with_logprobs=title != "AiKeyOut"
        )


def record(name: str, work: Path) -> Path:
    from etach import cli
    from etach.eval.fixtures import load_fixture
    from etach.eval.grade import build_test

    fx = load_fixture(FIXTURES / "tuning" / name, "tuning")
    _, ids = build_test(fx.expected)
    fake = EvalFake(dict(fx.expected.key or {}), ids, name == SCRIPTED)
    out = OUT_ROOT / name
    if out.exists():
        shutil.rmtree(out)
    argv = [
        "record", "--out", str(out), "--",
        "eval", "--graph", "grade", "--set", "tuning", "--fixtures", str(FIXTURES),
        "--only", name, "--history", str(work / f"{name}.csv"),
    ]  # fmt: skip
    cli._TEST_TRANSPORT = fake.transport
    real = sys.stdout
    sys.stdout = io.StringIO()
    try:
        code = cli.main(argv)
    finally:
        sys.stdout = real
        cli._TEST_TRANSPORT = None
    assert code == 0, f"etach {' '.join(argv)} exited {code}"
    return out


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        for d in sorted((FIXTURES / "tuning").iterdir()):
            if d.is_dir():
                print(f"wrote {record(d.name, Path(tmp))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
