"""Step 22.6.3 (decision D6): an unsure checker, replayed through the grade graph (R22.6.3.1).

Built from the synthetic ``grade-synthetic/truncated-verify`` folder at test time, as in
``test_step22_5_5_replay``: its first ``verify_key`` cassette becomes a complete ``?`` answer
(spaces around) and the retry is dropped. No student data.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from .test_extract_replay import CASSETTES
from .test_grade_replay import replay_grade_scenario
from .test_grade_synthetic import question_ids

GS = CASSETTES / "grade-synthetic"
CHECKER_REASONING = "Both B and C could fit the sentence."


def _unsure_scenario(tmp: Path) -> Path:
    src = GS / "truncated-verify"
    out = tmp / "check-unsure"
    shutil.copytree(src, out)
    manifest = json.loads((out / "grade.json").read_text(encoding="utf-8"))
    manifest["after"] = str((src / manifest["after"]).resolve())
    (out / "grade.json").write_text(json.dumps(manifest), encoding="utf-8")
    first = out / "004-verify_key.json"
    cassette = json.loads(first.read_text(encoding="utf-8"))
    cassette["status"] = "complete"
    cassette["response_text"] = json.dumps({"reasoning": CHECKER_REASONING, "answer": " ? "})
    cassette["logprobs"] = None
    first.write_text(json.dumps(cassette, ensure_ascii=False), encoding="utf-8")
    (out / "005-verify_key.json").unlink()
    return out


def test_r22_6_3_1_unsure_answer_flags_the_key(tmp_path: Path) -> None:
    data = tmp_path / "data"
    _, code, out = replay_grade_scenario(_unsure_scenario(tmp_path), data)
    assert code == 0 and out["status"] == "done", out
    q2 = question_ids(data)[1]
    with sqlite3.connect(data / "app.db") as c:
        rows = c.execute("SELECT question_id, status, accepted, checker FROM answer_keys")
        keys = {q: (s, json.loads(a), json.loads(ch) if ch else None) for q, s, a, ch in rows}
        reviews = c.execute(
            "SELECT question_id FROM review_items WHERE kind = 'uncertain_key'"
        ).fetchall()
    status, accepted, checker = keys[q2]
    assert status == "ai_uncertain" and accepted == ["B"]  # the first key is kept
    assert checker == {"status": "unsure", "answer": None, "reasoning": CHECKER_REASONING}
    assert all(ch is None for q, (_, _, ch) in keys.items() if q != q2)
    assert (q2,) in reviews
