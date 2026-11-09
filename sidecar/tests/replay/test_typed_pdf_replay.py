"""R22.3.6.1 (decision D5): typed PDF pages through ``etach run --replay``.

The synthetic ``tests/cassettes/typed-pdf*/`` scenarios (made by ``make_typed_pdf.py``) hold their
own PDF. A born-digital page is structured from its text by ``structure_text_page`` (reasoning
role, no image), never by ``transcribe_page`` or ``retranscribe_tiles``; a scanned page in the
same file still calls ``transcribe_page`` with its image. A file of typed pages only reads no
answers (PRD D26) and saves a blank test with the cassette's structure.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from etach.store.repos import tests as test_repo

from .test_extract_replay import CASSETTES, conn_of, run_ok

TYPED = CASSETTES / "typed-pdf"
MIXED = CASSETTES / "typed-pdf-mixed"
MARKER = "TYPED-PDF-SYNTHETIC-9"  # make_typed_pdf.MARKER


def _calls(c: sqlite3.Connection, run_id: str) -> list[tuple[str, str, str, dict[str, Any]]]:
    rows = c.execute(
        "SELECT s.node, l.role, json_extract(l.request, '$.task'), l.request FROM llm_calls l"
        " JOIN steps s ON s.id = l.step_id WHERE s.run_id = ? ORDER BY l.created_at, l.id",
        (run_id,),
    ).fetchall()
    return [(r[0], r[1], r[2], json.loads(r[3])) for r in rows]


def _has_image(request: dict[str, Any]) -> bool:
    return any(m.get("images") for m in request.get("messages", []))


def test_typed_pdf_is_structured_from_its_text(tmp_path: Path) -> None:
    data = tmp_path / "data"
    out = run_ok("--data", data, "--pages", TYPED / "typed.pdf", "--replay", TYPED)
    assert out["test_id"] and out["attempt_id"] is None  # D26: a blank test
    c = conn_of(data)
    try:
        calls = _calls(c, out["run_id"])
        assert [(node, role) for node, role, _, _ in calls] == [("transcribe_page", "reasoning")]
        _, _, _, request = calls[0]
        assert MARKER in json.dumps(request, ensure_ascii=False)
        assert not _has_image(request)
        steps = {
            r[0] for r in c.execute("SELECT node FROM steps WHERE run_id = ?", (out["run_id"],))
        }
        assert "retranscribe_tiles" not in steps
        assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == 0
        test = test_repo.get_test(c, out["test_id"])
        assert test is not None
        sections = test.content.sections
        # D2 (v1.21): a bare numeral is titled by the section skill
        assert [s.printed_title.split(".")[0] for s in sections] == ["I", "II", "III"]
        mcq = sections[0].groups[0].questions[0]
        assert mcq.options is not None and len(mcq.options) == 4
        reading = sections[1].groups[0]
        assert reading.stimulus and "Lan lives in Hue" in reading.stimulus
        assert len(reading.pictures) == 1  # the D11 placeholder points at the page image
        rewrite = sections[2].groups[0].questions[0]
        assert rewrite.answer_form == "sentence" and rewrite.answer_start == "My brother"
    finally:
        c.close()


def test_mixed_pdf_routes_each_page(tmp_path: Path) -> None:
    data = tmp_path / "data"
    out = run_ok("--data", data, "--pages", MIXED / "mixed.pdf", "--replay", MIXED)
    c = conn_of(data)
    try:
        pages = [
            (node, role, _has_image(req))
            for node, role, _, req in _calls(c, out["run_id"])
            if node == "transcribe_page"
        ]
        # the typed page from its text (reasoning), the scanned page from its image (vision)
        assert pages == [
            ("transcribe_page", "reasoning", False),
            ("transcribe_page", "vision", True),
        ]
        steps = {
            r[0] for r in c.execute("SELECT node FROM steps WHERE run_id = ?", (out["run_id"],))
        }
        assert "retranscribe_tiles" not in steps
        test = test_repo.get_test(c, out["test_id"])
        assert test is not None
        titles = [s.printed_title.split(".")[0] for s in test.content.sections]
        assert titles == ["I", "II", "III", "IV"]  # D2 (v1.21): titled by skill
    finally:
        c.close()
