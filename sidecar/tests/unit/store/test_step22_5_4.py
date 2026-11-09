"""Step 22.5.4 (sidecar): the stored data.

R22.5.4.5 (nothing of the difficulty notes left; the first-start pass that drops them from the meta)
and R22.5.4.7 (the T/F relabel with explanation rows for both an old letter and its T/F letter).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from unit.domain.grading_support import key as g_key
from unit.store.conftest import answer, make_attempt, make_test
from unit.store.test_step22_5_3 import _tf_content

from etach.store import db
from etach.store.repos import attempts, keys, tests
from etach.store.repos.answer_form_pass import run_answer_form_pass

# --- R22.5.4.7 -----------------------------------------------------------------------------------


def test_r22_5_4_7_relabel_with_rows_a_and_f_keeps_one_f_row(tmp_path: Path) -> None:
    """q-1 is ``A. FALSE`` / ``B. TRUE`` (a → F) with explanation rows ``a`` and ``f``."""
    path = tmp_path / "data" / "app.db"
    c = db.open_database(path)
    test = make_test(c)
    attempt = make_attempt(c, test.id)
    attempts.insert_answers(c, [answer(attempt.id, "q-1", value="A", value_norm="a")])
    keys.upsert_key(c, g_key("q-1", "B").model_copy(update={"test_id": test.id}))
    for wrong, text in (("a", "Old letter."), ("f", "Already T/F.")):
        c.execute(
            "INSERT INTO explanations (test_id, question_id, wrong_answer_norm, error_type,"
            " text_vi, status, llm_call_id) VALUES (?, 'q-1', ?, 'gap', ?, 'ai', NULL)",
            (test.id, wrong, text),
        )
    c.execute("UPDATE tests SET content = ? WHERE id = ?", (json.dumps(_tf_content()), test.id))
    c.execute("INSERT INTO answer_form_pending (id) VALUES (1)")
    c.commit()
    c.close()

    c = db.open_database(path)  # the first start runs the pass and completes
    assert c.execute("SELECT COUNT(*) FROM answer_form_pending").fetchone()[0] == 0
    rows = c.execute(
        "SELECT wrong_answer_norm, text_vi FROM explanations WHERE question_id = 'q-1'"
    ).fetchall()
    assert [tuple(r) for r in rows] == [("f", "Already T/F.")]
    key = keys.get_key(c, test.id, "q-1")
    assert key is not None and key.accepted == ["T"]
    value = c.execute("SELECT value FROM answers WHERE question_id = 'q-1'").fetchone()[0]
    assert value == "F"
    after = c.execute("SELECT content FROM tests WHERE id = ?", (test.id,)).fetchone()[0]
    assert run_answer_form_pass(c) is False  # still once-only
    c.close()
    c = db.open_database(path)
    assert c.execute("SELECT content FROM tests WHERE id = ?", (test.id,)).fetchone()[0] == after
    assert c.execute("SELECT COUNT(*) FROM explanations").fetchone()[0] == 1
    c.close()


# --- R22.5.4.5 -----------------------------------------------------------------------------------

SIDECAR = Path(__file__).resolve().parents[3]
NOTES = {
    "overall": "easy",
    "cefr_estimate": "A2",
    "per_section": [{"section_id": "sec-1", "difficulty": "easy", "note": "Dễ."}],
    "trap_items": [],
    "comment_vi": "Đề dễ.",
    "generated_by_model": "qwen3.5:4b",
}


def test_r22_5_4_5_no_difficulty_notes_left() -> None:
    from etach.domain import render_schemas
    from etach.graphs.grade import C2_NODES, GRADE_STAGES
    from etach.llm.tasks import GRADING_NUM_PREDICT, TASKS

    assert "difficulty_notes" not in C2_NODES
    assert all("difficulty_notes" not in stage.nodes for stage in GRADE_STAGES)
    assert "difficulty_notes" not in TASKS and "difficulty_notes" not in GRADING_NUM_PREDICT
    assert not list((SIDECAR / "src" / "etach" / "prompts").rglob("difficulty_notes*"))
    assert not list((SIDECAR / "tests" / "cassettes").rglob("*difficulty_notes*"))
    schemas = render_schemas()
    assert not [n for n in schemas if "Difficulty" in n]
    assert not [n for n, text in schemas.items() if "test_difficulty_notice" in text]


def _snapshot(conn: sqlite3.Connection) -> dict[str, list[tuple[Any, ...]]]:
    names = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    out: dict[str, list[tuple[Any, ...]]] = {}
    for name in names:
        if name == "difficulty_notes_pending":
            continue
        rows = conn.execute(f"SELECT * FROM {name} ORDER BY 1").fetchall()
        out[name] = [tuple(r) for r in rows]
    return out


def _meta_without_notes(snap: dict[str, list[tuple[Any, ...]]], col: int) -> list[Any]:
    out = []
    for row in snap["tests"]:
        meta = json.loads(row[col])
        meta.pop("test_difficulty_notice_comment_by_ai", None)
        out.append(meta)
    return out


def test_r22_5_4_5_pass_drops_the_meta_field_once(tmp_path: Path) -> None:
    from etach.store.repos.difficulty_pass import run_difficulty_notes_pass

    path = tmp_path / "data" / "app.db"
    c = db.open_database(path)
    with_notes = make_test(c)
    without = make_test(c)
    attempt = make_attempt(c, with_notes.id)
    attempts.insert_answers(c, [answer(attempt.id, "q-1", value="A", value_norm="a")])
    keys.upsert_key(c, g_key("q-1", "A").model_copy(update={"test_id": with_notes.id}))
    meta = json.loads(
        c.execute("SELECT meta FROM tests WHERE id = ?", (with_notes.id,)).fetchone()[0]
    )
    meta["test_difficulty_notice_comment_by_ai"] = NOTES
    c.execute("UPDATE tests SET meta = ? WHERE id = ?", (json.dumps(meta), with_notes.id))
    c.execute("INSERT INTO difficulty_notes_pending (id) VALUES (1)")  # as after migration 0013
    c.commit()
    c.close()
    raw = sqlite3.connect(path)
    cols = [r[1] for r in raw.execute("PRAGMA table_info(tests)")]
    meta_col = cols.index("meta")
    before = _snapshot(raw)
    raw.close()

    c = db.open_database(path)  # the first start runs the pass
    assert not c.execute("SELECT 1 FROM difficulty_notes_pending").fetchone()
    after = _snapshot(c)
    metas = {r[0]: json.loads(r[meta_col]) for r in after["tests"]}
    assert all("test_difficulty_notice_comment_by_ai" not in m for m in metas.values())
    # every other meta field is the same, and every other column and table row-for-row
    assert _meta_without_notes(after, meta_col) == _meta_without_notes(before, meta_col)
    strip = [r[:meta_col] + r[meta_col + 1 :] for r in after["tests"]]
    assert strip == [r[:meta_col] + r[meta_col + 1 :] for r in before["tests"]]
    assert {k: v for k, v in after.items() if k != "tests"} == {
        k: v for k, v in before.items() if k != "tests"
    }
    plain = next(r for r in before["tests"] if r[0] == without.id)
    assert next(r for r in after["tests"] if r[0] == without.id) == plain  # untouched row
    got = tests.get_test(c, with_notes.id)
    assert got is not None  # the meta validates without the field
    assert run_difficulty_notes_pass(c) is False  # the row is gone: runs once
    c.close()
    c = db.open_database(path)
    assert _snapshot(c) == after
    c.close()
