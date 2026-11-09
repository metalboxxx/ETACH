"""Step 22.5.6 (sidecar) R22.5.6.5: key-photo keys and the stored-key pass.

A key read from the key photo is never ``ai_verified`` without a second model call: ``map_key``
gives it ``from_key_photo`` (``tests/unit/domain/test_keymap.py``), and ``verify_key`` still checks
only ``ai_unverified`` keys. The one-time first-start pass of migration 0015 moves the stored
key-photo keys that no check verified (``ai_verified`` with confidence ≥ 0.7) to
``from_key_photo``, once, and changes nothing else.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from unit.domain.grading_support import key as g_key
from unit.store.conftest import make_test

from etach.domain.keymap import KEY_PHOTO_THRESHOLD, map_key
from etach.store import db
from etach.store.repos import keys
from etach.store.repos.key_photo_pass import run_key_photo_pass


def _snapshot(conn: sqlite3.Connection) -> dict[str, list[tuple[Any, ...]]]:
    names = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return {
        n: sorted((tuple(r) for r in conn.execute(f"SELECT * FROM {n}")), key=repr)
        for n in names
        if n != "key_photo_pending"
    }


def test_r22_5_6_5_map_key_never_gives_ai_verified() -> None:
    from unit.domain.test_keymap import b1_draft

    out = map_key([("5", "A", 0.99), ("6", "B", 0.1)], b1_draft(), threshold=KEY_PHOTO_THRESHOLD)
    assert out.status == {"c1": "from_key_photo", "c2": "ai_unverified"}
    assert "ai_verified" not in out.status.values()


def test_r22_5_6_5_pass_moves_only_unchecked_key_photo_keys_once(tmp_path: Path) -> None:
    path = tmp_path / "data" / "app.db"
    c = db.open_database(path)
    t = make_test(c)

    def put(qid: str, source: str, status: str, conf: float | None) -> None:
        row = g_key(qid, "A", status, conf).model_copy(update={"test_id": t.id, "source": source})
        keys.upsert_key(c, row)

    put("q-1", "from_key_photo", "ai_verified", 0.95)  # map_key, no check → moves
    put("q-2", "from_key_photo", "ai_verified", 0.7)  # at the threshold → moves
    put("q-3", "from_key_photo", "ai_verified", 0.4)  # verify_key agreed → stays
    put("q-4", "from_key_photo", "ai_unverified", 0.4)  # stays
    put("q-5", "ai", "ai_verified", 0.99)  # an AI key a check verified → stays
    put("q-6", "from_key_photo", "ai_uncertain", 0.9)  # stays
    put("q-7", "teacher_edit", "teacher_verified", None)  # stays
    put("q-8", "from_key_photo", "ai_verified", None)  # no confidence: not map_key's → stays
    c.execute("INSERT INTO key_photo_pending (id) VALUES (1)")  # as after migration 0015
    c.commit()
    c.close()
    raw = sqlite3.connect(path)
    before = _snapshot(raw)
    raw.close()

    c = db.open_database(path)  # the first start runs the pass
    assert not c.execute("SELECT 1 FROM key_photo_pending").fetchone()
    after = _snapshot(c)
    status = {k.question_id: k.status for k in keys.list_keys(c, t.id)}
    assert status == {
        "q-1": "from_key_photo",
        "q-2": "from_key_photo",
        "q-3": "ai_verified",
        "q-4": "ai_unverified",
        "q-5": "ai_verified",
        "q-6": "ai_uncertain",
        "q-7": "teacher_verified",
        "q-8": "ai_verified",
    }
    # only the status of q-1 and q-2 changed: every other column, row and table is the same
    cols = [r[1] for r in c.execute("PRAGMA table_info(answer_keys)")]
    st = cols.index("status")
    qcol = cols.index("question_id")

    def strip(rows: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
        return [r[:st] + r[st + 1 :] for r in rows]

    assert strip(after["answer_keys"]) == strip(before["answer_keys"])
    moved = [
        r[qcol]
        for r, b in zip(after["answer_keys"], before["answer_keys"], strict=True)
        if r[st] != b[st]
    ]
    assert moved == ["q-1", "q-2"]
    assert {k: v for k, v in after.items() if k != "answer_keys"} == {
        k: v for k, v in before.items() if k != "answer_keys"
    }
    assert run_key_photo_pass(c) is None  # the row is gone: runs once
    c.close()
    c = db.open_database(path)
    assert _snapshot(c) == after
    c.close()


def test_r22_5_6_5_new_database_runs_the_pass_on_no_keys(tmp_path: Path) -> None:
    c = db.open_database(tmp_path / "app.db")
    assert not c.execute("SELECT 1 FROM key_photo_pending").fetchone()
    assert run_key_photo_pass(c) is None
    c.close()
