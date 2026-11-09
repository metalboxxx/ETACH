"""M1 baseline fix: a picture-free DOCX through ``etach run --replay``.

The synthetic ``tests/cassettes/docx-text/`` scenario (made by ``make_docx_text.py``) holds its
own synthetic ``test.docx``. The DOCX becomes one text-only page (``file_id = text_file_id``):
``prepare_pages`` makes no image from it (it used to fail with "text/plain …, not an image"),
and its model call receives the page's text, not an image (PRD §11). A DOCX is born-digital
(PRD D26), so ``read_answers_page`` makes no call and the run saves a blank test; the
cassettes keep their recorded ``read_answers_page`` entries, which are simply not served.
"""

from __future__ import annotations

import json
from pathlib import Path

from .test_extract_replay import CASSETTES, conn_of, run_ok

DOCX_TEXT = CASSETTES / "docx-text"
MARKER = "DOCX-SYNTHETIC-7"  # make_docx_text.MARKER


def test_picture_free_docx_extracts_from_its_text(tmp_path: Path) -> None:
    data = tmp_path / "data"
    out = run_ok("--data", data, "--pages", DOCX_TEXT / "test.docx", "--replay", DOCX_TEXT)
    assert out["test_id"] and out["attempt_id"] is None  # D26: a blank test
    c = conn_of(data)
    try:
        kinds = sorted(r[0] for r in c.execute("SELECT kind FROM files"))
        assert kinds == ["text", "upload"]  # the DOCX and its text; no derived image
        text_id = c.execute("SELECT id FROM files WHERE kind = 'text'").fetchone()[0]
        pages = c.execute("SELECT page_no, file_id FROM test_pages").fetchall()
        assert [tuple(r) for r in pages] == [(1, text_id)]
        att = c.execute("SELECT file_id, source_file_id FROM attempt_pages").fetchall()
        assert att == []  # no attempt
        calls = c.execute(
            "SELECT s.node, l.request FROM llm_calls l JOIN steps s ON s.id = l.step_id"
            " WHERE s.run_id = ? ORDER BY l.created_at, l.id",
            (out["run_id"],),
        ).fetchall()
        assert [r[0] for r in calls] == ["transcribe_page"]  # D26: no answer reading
        for _, request in calls:
            assert MARKER in request
            messages = json.loads(request)["messages"]
            assert not any(m.get("images") for m in messages)
        steps = {
            r[0] for r in c.execute("SELECT node FROM steps WHERE run_id = ?", (out["run_id"],))
        }
        assert "retranscribe_tiles" not in steps
        assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == 0
        assert c.execute("SELECT kind FROM threads").fetchone()[0] == "blank"
    finally:
        c.close()


DOCX_LONG = CASSETTES / "docx-long"
LONG_MARKER = "DOCX-LONG-SYNTHETIC-8"  # make_docx_long.MARKER


def test_long_docx_is_split_into_text_pages_and_merges_back(tmp_path: Path) -> None:
    """M1 long-DOCX fix: a DOCX text longer than ``MAX_TEXT_PAGE_CHARS`` becomes several
    text-only pages in order (one ``transcribe_page`` each, no image); section I runs over the
    page break and merges back into one section."""
    from etach.store.documents import MAX_TEXT_PAGE_CHARS

    data = tmp_path / "data"
    out = run_ok("--data", data, "--pages", DOCX_LONG / "test.docx", "--replay", DOCX_LONG)
    assert out["test_id"] and out["attempt_id"] is None  # D26: a blank test
    c = conn_of(data)
    try:
        pages = c.execute("SELECT page_no, file_id FROM test_pages ORDER BY page_no").fetchall()
        assert [r[0] for r in pages] == [1, 2, 3]
        kinds = {r[0]: r[1] for r in c.execute("SELECT id, kind FROM files")}
        assert all(kinds[r[1]] == "text" for r in pages)
        assert sorted(kinds.values()) == ["text", "text", "text", "upload"]
        calls = c.execute(
            "SELECT s.node, l.request FROM llm_calls l JOIN steps s ON s.id = l.step_id"
            " WHERE s.run_id = ? ORDER BY l.created_at, l.id",
            (out["run_id"],),
        ).fetchall()
        assert [r[0] for r in calls] == ["transcribe_page"] * 3  # D26: no answer reading
        for _, request in calls:
            messages = json.loads(request)["messages"]
            assert not any(m.get("images") for m in messages)
        documents = [json.loads(r[1]) for r in calls[:3]]
        assert LONG_MARKER in json.dumps(documents[0])
        for doc in documents:
            # the page text is in the user message; the instructions grow with prompt tuning (M1)
            text = "".join(m["content"] for m in doc["messages"] if m["role"] == "user")
            assert len(text) < MAX_TEXT_PAGE_CHARS + 1000  # one piece, not the whole DOCX
        content = json.loads(
            c.execute("SELECT content FROM tests WHERE id = ?", (out["test_id"],)).fetchone()[0]
        )
        sections = content["sections"]
        # D2 (v1.21): a bare numeral is titled by the section skill
        assert [s["printed_title"].split(".")[0] for s in sections] == ["I", "II", "III"]
        counts = [sum(len(g["questions"]) for g in s["groups"]) for s in sections]
        assert counts == [36, 24, 8]
        numbers = [
            q["printed_number"] for s in sections for g in s["groups"] for q in g["questions"]
        ]
        assert numbers == list(range(1, 69))
        assert c.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == 0
        assert c.execute("SELECT kind FROM threads").fetchone()[0] == "blank"
    finally:
        c.close()
