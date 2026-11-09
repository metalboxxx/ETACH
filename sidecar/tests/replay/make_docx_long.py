"""Regenerate the SYNTHETIC long picture-free DOCX scenario in ``tests/cassettes/docx-long/``
(M1 long-DOCX fix: a text longer than ``MAX_TEXT_PAGE_CHARS`` is split into several text-only
pages at ingest).

    cd sidecar
    uv run python tests/replay/make_docx_long.py

Built like ``make_docx_text.py`` (the real CLI and prompts over the schema-keyed FakeOllama).
The folder holds the synthetic ``test.docx`` (a header, sections I, II and III with 36, 24 and 8
MCQs; no pictures, no student data). Section I is longer than one page, so the split breaks it
at a question start and page 2 continues it (empty ``printed_title``; the merge must join it
back into one section); page 3 starts at the section III heading. Each page's
``transcribe_page`` answer is built from that page's own text, so the answers follow the split.
``input.json`` and the stand-in PNGs are removed, as in ``docx-text``.
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_docx_text as short  # noqa: E402
import make_synthetic as base  # noqa: E402

OUT_ROOT = base.TESTS / "cassettes" / "docx-long"
DOCX_NAME = "test.docx"
MARKER = "DOCX-LONG-SYNTHETIC-8"
SECTIONS = (("I", 36), ("II", 24), ("III", 8))
OPTIONS = "A. opt a   B. opt b   C. opt c   D. opt d"
PROMPT_TOKENS = 12_000  # the recorded prompt_eval_count (see main)
_FILLER = "with a synthetic sentence long enough to make the page text grow past the limit"


def lines() -> list[str]:
    out = [base.HEADER]
    n = 1
    for title, count in SECTIONS:
        out.append(f"{title}. Choose the best answer. ({MARKER}) (2.5 pts)")
        for _ in range(count):
            out.append(f"{n}. Long DOCX question {n}: choose the best option {_FILLER} {n}")
            out.append(OPTIONS)
            n += 1
    return out


LINES = lines()
_HEAD = re.compile(r"^(I|II|III)\. (Choose the best answer\.) \(.*\) (\(2\.5 pts\))$")
_QUESTION = re.compile(r"^(\d+)\. (.*)$")


def transcribe(piece: str, *, first: bool) -> dict[str, Any]:
    """The ``TranscribeOut`` a perfect model would give for one page's text."""
    opts = [{"label": x, "text": f"opt {x.lower()}"} for x in "ABCD"]
    sections: list[dict[str, Any]] = []

    def section(title: str, instructions: str, points: str | None) -> dict[str, Any]:
        sec = {
            "printed_title": title,
            "instructions": instructions,
            "kind": "questions",
            "skill": "grammar",
            "points_text": points,
            "range_first": None,
            "range_last": None,
            "groups": [{"stimulus": None, "pictures": [], "questions": []}],
        }
        sections.append(sec)
        return sec

    for line in piece.split("\n"):
        if head := _HEAD.match(line):
            section(head.group(1), head.group(2), head.group(3))
        elif line == OPTIONS or line == base.HEADER:
            continue
        elif q := _QUESTION.match(line):
            sec = sections[-1] if sections else section("", "", None)  # continues a section
            sec["groups"][0]["questions"].append(
                {
                    "printed_number": int(q.group(1)),
                    "answer_form": "choice",
                    "stem": q.group(2),
                    "options": opts,
                    "cue": None,
                }
            )
    return {"header_text": base.HEADER if first else None, "sections": sections}


def main() -> int:
    from etach.domain.llm_schemas import TranscribeOut
    from etach.store.documents import split_text_page

    pieces = split_text_page("\n".join(LINES))
    outs = [transcribe(p, first=i == 0) for i, p in enumerate(pieces)]
    for out in outs:
        TranscribeOut.model_validate(out)
    starts = [p.split("\n", 1)[0].split(".", 1)[0] for p in pieces]
    assert len(pieces) == 3 and starts[0] != "II" and starts[1].isdigit(), starts
    assert starts[2] == "III", starts
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        rec = base.Recorder(work)
        script = rec.fake._script

        def counted() -> Any:
            # FakeOllama reports 123 prompt tokens; a read_answers_page prompt with 68 questions
            # has an upper bound above num_ctx, so the client would take 123 as a dropped prompt
            # (bug B1 check). Report a full count, as a real Ollama would (replay sends 0).
            out = script()
            out.prompt_eval_count = PROMPT_TOKENS
            return out

        rec.fake._script = counted  # type: ignore[method-assign]
        docx = short.write_docx(work / DOCX_NAME, LINES)
        rec.run(
            work / "data",
            [str(docx)],
            {
                "TranscribeOut": outs,
                "ReadAnswersCall": [base.answers("B"), *[base.EMPTY] * (len(pieces) - 1)],
            },
            out=OUT_ROOT,
        )
        (OUT_ROOT / "input.json").unlink()
        for stray in OUT_ROOT.glob("page-*.png"):
            stray.unlink()
        short.write_docx(OUT_ROOT / DOCX_NAME, LINES)
        rec.cli._TEST_TRANSPORT = None
    print(f"wrote {OUT_ROOT} ({len(pieces)} pages: {[len(p) for p in pieces]} characters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
