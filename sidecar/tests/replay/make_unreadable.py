"""Regenerate the SYNTHETIC unreadable-text cassettes in ``tests/cassettes/unreadable/``
(plan step 21a, PRD D25).

    cd sidecar
    uv run python tests/replay/make_unreadable.py

Built like ``make_synthetic.py`` (the real CLI and prompts over the schema-keyed FakeOllama):

- ``filled/``: a filled 3-page test. Page 1 has ``???`` in two fields (the section
  instructions and question 1's stem), page 2 has none, page 3 has ``???`` in question 6's
  stem. The student's answer to question 4 (word form, free text) is read as ``???``. (An MCQ
  or true/false answer cannot be ``???`` yet: the ``read_answers_page`` schema limits those
  values to A-D and T/F.)
- ``picked/``: the same two first photos with that test picked (no transcription), run after
  ``filled/`` in the same data folder.

All data is synthetic (``Học Sinh A`` / ``8X1``).
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_synthetic as base  # noqa: E402

OUT_ROOT = base.TESTS / "cassettes" / "unreadable"

INSTRUCTIONS_P1 = "Choose the ??? answer."
STEM_Q1 = "Page 1 question 1: choose the word with a ??? sound 1"
STEM_Q6 = "Page 3 question 6: ??? the word with a different sound 6"


def unreadable_page(page_no: int, *, header: str | None = None) -> dict[str, Any]:
    out = base.page_out(page_no, header=header)
    section = out["sections"][0]
    questions = section["groups"][0]["questions"]
    if page_no == 1:
        section["instructions"] = INSTRUCTIONS_P1
        questions[0]["stem"] = STEM_Q1
    if page_no == 2:  # question 4 is a word-form question (a free-text answer)
        questions[1].update(
            answer_form="word", stem="Page 2 question 4: She sings ____ . (BEAUTY)", options=None
        )
        questions[1]["cue"] = "BEAUTY"
    if page_no == 3:
        questions[1]["stem"] = STEM_Q6
    return out


def student_answers(q4: str) -> Callable[[list[str]], dict[str, Any]]:
    """MCQs ``A``; question 4 (the 4th ID in canonical order, word form) = ``q4``. One builder
    serves the pages in order (step 22.5.6: each page is asked only for its own questions), so the
    position counts on from the IDs of the pages before."""
    asked: list[str] = []

    def build(ids: list[str]) -> dict[str, Any]:
        offset = len(asked)
        asked.extend(ids)

        def reading(i: int) -> dict[str, Any]:
            if offset + i == 3:
                return {"value": q4, "location": "written_in_blank", "alt_question_id": None}
            return {"value": "A", "location": "circled_option", "alt_question_id": None}

        return {
            "student_name": base.STUDENT,
            "class_name": base.CLASS,
            "answers": {qid: [reading(i)] for i, qid in enumerate(ids)},
        }

    return build


FILLED_QUEUES: dict[str, list[Any]] = {
    "TranscribeOut": [
        unreadable_page(1, header=base.HEADER),
        unreadable_page(2),
        unreadable_page(3),
    ],
    # the student's answer to question 4 is unreadable: read as ??? (D25)
    "ReadAnswersCall": [student_answers("???")] * 3,
}


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        rec = base.Recorder(work)
        p = [base.photo(work, f"De-unreadable ({i}).jpg", 120 + i) for i in (1, 2, 3)]
        data = work / "data"
        first = rec.run(data, [str(x) for x in p], FILLED_QUEUES, out=OUT_ROOT / "filled")

        stems = [
            q["stem"]
            for n in (1, 2)
            for q in unreadable_page(n)["sections"][0]["groups"][0]["questions"]
        ]
        header = {"header_text": base.HEADER, "first_stems": stems[:3]}
        answer_queue: list[Callable[[list[str]], dict[str, Any]] | dict[str, Any]] = [
            student_answers("beautifully"),
            base.EMPTY,
        ]
        rec.run(
            data,
            [str(p[0]), str(p[1])],
            {"ReadHeaderOut": [header], "ReadAnswersCall": answer_queue},
            "--existing",
            first["test_id"],
            out=OUT_ROOT / "picked",
        )
        rec.cli._TEST_TRANSPORT = None
    print(f"wrote {OUT_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
