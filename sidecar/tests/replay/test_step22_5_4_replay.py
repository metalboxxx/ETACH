"""Step 22.5.4a replays (synthetic cassettes in ``tests/cassettes/grade-synthetic/``)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .test_grade_replay import replay_grade_scenario
from .test_grade_synthetic import GS


def _calls(data: Path, node: str) -> list[tuple[str, str]]:
    with sqlite3.connect(data / "app.db") as c:
        return c.execute(
            "SELECT l.role, l.model FROM llm_calls l JOIN steps s ON s.id = l.step_id"
            " WHERE s.node = ?",
            (node,),
        ).fetchall()


def test_r22_5_4_1_verify_key_calls_the_grading_check_model(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "models.toml").write_text(
        '[roles.grading_check]\nmodel = "checker:1b"\n', encoding="utf-8"
    )
    _, code, out = replay_grade_scenario(GS / "first-grade", data)
    assert code == 0 and out["status"] == "done", out
    verify = _calls(data, "verify_key")
    assert verify and set(verify) == {("grading_check", "checker:1b")}
    keys = _calls(data, "ai_key_fast")
    assert keys and set(keys) == {("reasoning", "qwen3.5:4b")}
