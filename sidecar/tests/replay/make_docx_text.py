"""Regenerate the SYNTHETIC picture-free DOCX scenario in ``tests/cassettes/docx-text/``
(M1 baseline fix: a DOCX without pictures is one text-only page, ``file_id = text_file_id``).

    cd sidecar
    uv run python tests/replay/make_docx_text.py

Built like ``make_synthetic.py`` (the real CLI and prompts over the schema-keyed FakeOllama).
The folder also holds the synthetic ``test.docx`` itself (two short MCQ questions, no
pictures, no student data); the replay test runs ``etach run --pages test.docx --replay`` on it.
The recorded ``input.json`` and stand-in PNG are removed: a scenario manifest can only rebuild
image pages, so replaying without the DOCX would not test the text-only page. One page: one
``transcribe_page`` and one ``read_answers_page`` call, both answered from the text.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_synthetic as base  # noqa: E402

OUT_ROOT = base.TESTS / "cassettes" / "docx-text"
DOCX_NAME = "test.docx"
MARKER = "DOCX-SYNTHETIC-7"
LINES = [
    base.HEADER,
    f"I. Choose the best answer. ({MARKER})",
    "1. Page 1 question 1: choose the word with a different sound 1",
    "A. opt a   B. opt b   C. opt c   D. opt d",
    "2. Page 1 question 2: choose the word with a different sound 2",
    "A. opt a   B. opt b   C. opt c   D. opt d",
]


def write_docx(path: Path, lines: list[str] = LINES) -> Path:
    """A picture-free Word document: one paragraph per line, no pictures. The core properties
    are fixed so that regenerating gives the same text (the bytes may still differ by zip
    timestamps)."""
    from datetime import datetime

    from docx import Document

    doc = Document()
    props = doc.core_properties
    props.author = "etach synthetic"
    props.created = props.modified = datetime(2026, 10, 8)
    for line in lines:
        doc.add_paragraph(line)
    doc.save(str(path))
    return path


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        rec = base.Recorder(work)
        docx = write_docx(work / DOCX_NAME)
        rec.run(
            work / "data",
            [str(docx)],
            {
                "TranscribeOut": [base.page_out(1, header=base.HEADER)],
                "ReadAnswersCall": [base.answers("B")],
            },
            out=OUT_ROOT,
        )
        for stray in ("input.json", "page-01.png"):
            (OUT_ROOT / stray).unlink()
        write_docx(OUT_ROOT / DOCX_NAME)
        rec.cli._TEST_TRANSPORT = None
    print(f"wrote {OUT_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
