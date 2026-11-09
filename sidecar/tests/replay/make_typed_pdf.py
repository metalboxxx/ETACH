"""Regenerate the SYNTHETIC typed-PDF scenarios (step 22.3.6, decision D5):

- ``tests/cassettes/typed-pdf/``: ``typed.pdf``, one born-digital page (a full text layer) with
  sections, options, a passage and a rewrite with its printed opening words;
- ``tests/cassettes/typed-pdf-mixed/``: ``mixed.pdf``, the same typed page plus a scanned page
  (a full-page picture, no text layer).

    cd sidecar
    uv run python tests/replay/make_typed_pdf.py

Built like ``make_docx_text.py`` (the real CLI and prompts over the schema-keyed FakeOllama); the
model answers are synthetic until the teacher records a live run. Each folder keeps its PDF; the
replay test runs ``etach run --pages <pdf> --replay <folder>``. The recorded ``input.json`` and
stand-in PNGs are removed (a manifest can only rebuild image pages, not the text layer).
"""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_synthetic as base  # noqa: E402

OUT_TYPED = base.TESTS / "cassettes" / "typed-pdf"
OUT_MIXED = base.TESTS / "cassettes" / "typed-pdf-mixed"
MARKER = "TYPED-PDF-SYNTHETIC-9"
START = "My brother"
REWRITE_STEM = "My brother often stayed up late playing mobile games. (used to)"
TYPED_LINES = [
    base.HEADER,
    f"I. Choose the best answer. (1 pt) {MARKER}",
    "1. She ____ to school every day.  A. go  B. goes  C. going  D. gone",
    "2. They ____ football yesterday.  A. play  B. plays  C. played  D. playing",
    "II. Read the passage and answer True or False. (0.5 pts)",
    "Lan lives in Hue. She walks to school every morning with her friends.",
    "3. Lan lives in Hue.",
    "III. Rewrite the sentences. (0.5 pts)",
    "4. My brother often stayed up late playing mobile games. (used to)",
    f"-> {START} ......................................................",
]


def _q(n: int, form: str, stem: str | None, options: list[str] | None = None, **more: Any) -> Any:
    opts = (
        None
        if options is None
        else [{"label": "ABCD"[i], "text": t} for i, t in enumerate(options)]
    )
    return {
        "printed_number": n,
        "answer_form": form,
        "stem": stem,
        "options": opts,
        "cue": None,
        **more,
    }


def _section(title: str, instr: str, skill: str, pts: str, groups: list[Any]) -> Any:
    return {
        "printed_title": title, "instructions": instr, "kind": "questions", "skill": skill,
        "points_text": pts, "range_first": None, "range_last": None, "groups": groups,
    }  # fmt: skip


def typed_page_out() -> dict[str, Any]:
    """The structure of the typed page (what ``structure_text_page`` returns)."""
    return {
        "header_text": base.HEADER,
        "sections": [
            _section("I", "Choose the best answer.", "grammar", "(1 pt)", [{
                "stimulus": None, "pictures": [], "questions": [
                    _q(1, "choice", "She ____ to school every day.",
                       ["go", "goes", "going", "gone"]),
                    _q(2, "choice", "They ____ football yesterday.",
                       ["play", "plays", "played", "playing"]),
                ],
            }]),
            _section("II", "Read the passage and answer True or False.", "reading", "(0.5 pts)", [{
                "stimulus": "Lan lives in Hue. She walks to school every morning with her friends.",
                "pictures": [{"x0": 0, "y0": 0, "x1": 1000, "y1": 1000}],  # whole-page placeholder
                "questions": [_q(3, "choice", "Lan lives in Hue.")],
            }]),
            _section("III", "Rewrite the sentences.", "rewrite", "(0.5 pts)", [{
                "stimulus": None, "pictures": [], "questions": [
                    _q(4, "sentence", REWRITE_STEM,
                       answer_start=START),
                ],
            }]),
        ],
    }  # fmt: skip


def scanned_page_out() -> dict[str, Any]:
    return {
        "header_text": None,
        "sections": [
            _section("IV", "Choose the best answer.", "grammar", "(0.5 pts)", [{
                "stimulus": None, "pictures": [], "questions": [
                    _q(5, "choice", "He ____ a book now.",
                       ["read", "reads", "is reading", "readed"]),
                ],
            }]),
        ],
    }  # fmt: skip


def write_pdf(path: Path, *, scanned: bool) -> Path:
    """A typed page (real text layer) and, with ``scanned``, a page that is one full picture."""
    import pymupdf
    from PIL import Image

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((40, 72), "\n".join(TYPED_LINES), fontsize=9)
    if scanned:
        img = Image.new("RGB", (595, 842), (235, 235, 230))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        scan = doc.new_page(width=595, height=842)
        scan.insert_image(scan.rect, stream=buf.getvalue())
    doc.set_metadata({"producer": "etach synthetic", "creator": "etach synthetic"})
    path.write_bytes(doc.tobytes(garbage=3, deflate=False))
    doc.close()
    return path


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        rec = base.Recorder(work)
        for out, name, scanned, queues in (
            (OUT_TYPED, "typed.pdf", False, {"TranscribeOut": [typed_page_out()]}),
            (
                OUT_MIXED,
                "mixed.pdf",
                True,
                {
                    "TranscribeOut": [typed_page_out(), scanned_page_out()],
                    "ReadAnswersCall": [base.EMPTY, base.EMPTY],
                },
            ),
        ):
            pdf = write_pdf(work / name, scanned=scanned)
            rec.run(work / f"data-{name}", [str(pdf)], queues, out=out)
            for stray in out.glob("*"):
                if stray.suffix in (".png", ".jpg") or stray.name == "input.json":
                    stray.unlink()
            write_pdf(out / name, scanned=scanned)
        rec.cli._TEST_TRANSPORT = None
    print(f"wrote {OUT_TYPED} and {OUT_MIXED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
