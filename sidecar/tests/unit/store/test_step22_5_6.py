"""Step 22.5.6 (D12, R22.5.6.1): a typed PDF's page texts are joined and cut like a Word file's
text; each question gets the PDF page its text starts on and pictures stay on their printed page.
The PDFs are synthetic, built here."""

from __future__ import annotations

import io
import unicodedata

import pymupdf
import pytest
from PIL import Image

from etach.domain import renumber
from etach.domain.llm_schemas import TranscribeOut
from etach.domain.models import PageInput
from etach.domain.working import PageTranscript
from etach.store import documents
from etach.store.documents import (
    born_digital_pages,
    ingest,
    join_typed_pdf_pages,
    locate_pages,
)
from etach.store.files import FileStore

PAGE_1 = [
    "ENGLISH TEST - GRADE 9",
    "I. Choose the best answer. (2.5 pts)",
    *[
        f"{n}. She ____ to school every day number {n}. A. go B. goes C. going D. gone"
        for n in range(1, 14)
    ],
    "14. Which word has the underlined part pronounced differently from the others?",
]
PAGE_2 = [
    "A. wanted B. needed C. played D. decided",
    "15. They ____ football yesterday afternoon. A. play B. plays C. played D. playing",
    "II. Look at the picture and answer. (0.5 pts)",
    "16. What is the boy doing in the picture?",
]
PAGE_3 = [
    "III. Rewrite the sentences. (1 pt)",
    "17. My brother often stayed up late playing mobile games. (used to)",
    "=> My brother ..........................",
]


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (0, 128, 0)).save(buf, "PNG")
    return buf.getvalue()


def typed_pdf(pages: list[list[str]], picture_on: int | None = None) -> bytes:
    doc = pymupdf.open()
    for n, lines in enumerate(pages):
        page = doc.new_page(width=595, height=842)
        y = 60.0
        for line in lines:
            page.insert_text((40, y), line, fontsize=8)
            y += 12
        if n == picture_on:
            page.insert_image(pymupdf.Rect(400, 600, 500, 700), stream=_png())
    data = doc.tobytes()
    doc.close()
    return bytes(data)


def _q(n: int, stem: str, options: list[str] | None = None) -> dict[str, object]:
    return {
        "printed_number": n,
        "answer_form": "choice" if options else "word",
        "stem": stem,
        "options": None
        if options is None
        else [{"label": "ABCD"[i], "text": t} for i, t in enumerate(options)],
        "cue": None,
    }


def _sec(title: str, groups: list[dict[str, object]]) -> dict[str, object]:
    return {
        "printed_title": title, "instructions": "Do it.", "kind": "questions",
        "skill": "grammar", "points_text": None, "range_first": None, "range_last": None,
        "groups": groups,
    }  # fmt: skip


def structure() -> TranscribeOut:
    """What the model returns for the joined piece of pages 1-3."""
    mcqs = [_q(n, f"She ____ to school every day number {n}.", ["go", "goes", "going", "gone"])
            for n in range(1, 14)]  # fmt: skip
    return TranscribeOut.model_validate(
        {
            "header_text": "ENGLISH TEST - GRADE 9",
            "sections": [
                _sec("I", [{"stimulus": None, "pictures": [], "questions": [
                    *mcqs,
                    _q(14, "Which word has the underlined part pronounced differently from the"
                       " others?", ["wanted", "needed", "played", "decided"]),
                    _q(15, "They ____ football yesterday afternoon.",
                       ["play", "plays", "played", "playing"]),
                ]}]),
                _sec("II", [{"stimulus": None,
                             "pictures": [{"x0": 0, "y0": 0, "x1": 500, "y1": 500}],
                             "questions": [_q(16, "What is the boy doing in the picture?")]}]),
                _sec("III", [{"stimulus": None, "pictures": [], "questions": [
                    _q(17, "My brother often stayed up late playing mobile games. (used to)"),
                ]}]),
            ],
        }
    )  # fmt: skip


def test_r22_5_6_1_typed_pdf_pages_are_joined(store: FileStore) -> None:
    pages = ingest(store, typed_pdf([PAGE_1, PAGE_2, PAGE_3], picture_on=1), "typed.pdf")
    born = born_digital_pages(store, pages)
    assert born == [True, True, True]
    joined = join_typed_pdf_pages(store, pages, born)
    # the whole text fits one piece: it goes with page 1, pages 2 and 3 get no call of their own
    assert list(joined.pieces) == [0] and joined.absorbed == {1, 2}
    piece = joined.pieces[0]
    # question 14's stem (page 1) and its options (page 2) reach the model in one text
    at = piece.text.index("14. Which word")
    assert "A. wanted B. needed" in piece.text[at:]
    assert [p for _, p in piece.page_starts] == [0, 1, 2]
    assert piece.picture_pages == (1,)

    groups, questions = locate_pages(piece, structure().sections)
    assert questions[13] == 0  # question 14 starts on page 1 (index 0)
    assert questions[14] == 1  # question 15 is on page 2
    assert questions[15] == 1 and questions[16] == 2
    assert questions[:13] == [0] * 13
    assert groups == [0, 1, 2]  # the picture group stays on page 2, where it is printed

    transcript = renumber.page_transcript(1, structure(), "call-1")
    merged = renumber.merge_pages(
        [PageTranscript.model_validate(transcript.model_dump())],
        page_files={1: "f1", 2: "f2", 3: "f3"},
        placed={1: renumber.PiecePages(groups=[g + 1 for g in groups],
                                       questions=[q + 1 for q in questions])},
    )  # fmt: skip
    qs = [q for s in merged.draft.content.sections for g in s.groups for q in g.questions]
    assert [q.page_no for q in qs if q.printed_number in (13, 14, 15, 16, 17)] == [1, 1, 2, 2, 3]
    picture_group = merged.draft.content.sections[1].groups[0]
    assert [(p.file_id, p.page_no) for p in picture_group.pictures] == [("f2", 2)]


def test_long_typed_pdf_is_cut_never_inside_a_question(store: FileStore) -> None:
    long_1 = [f"{n}. A long question line number {n} " + "x" * 150 for n in range(1, 25)]
    long_2 = [f"{n}. A long question line number {n} " + "x" * 150 for n in range(25, 41)]
    long_1.append("41. The stem of a split question?")
    long_2 = ["A. one B. two C. three D. four", *long_2]
    pages = ingest(store, typed_pdf([long_1, long_2]), "long.pdf")
    joined = join_typed_pdf_pages(store, pages, born_digital_pages(store, pages))
    texts = [p.text for p in joined.pieces.values()]
    assert all(len(t) <= 6000 for t in texts)
    holder = next(t for t in texts if "41. The stem" in t)
    assert "A. one B. two" in holder  # the cut is never inside question 41


def test_photos_word_and_single_pages_are_unchanged(store: FileStore) -> None:
    one = ingest(store, typed_pdf([PAGE_3]), "one.pdf")
    assert join_typed_pdf_pages(store, one, born_digital_pages(store, one)).pieces == {}
    photo = PageInput(
        file_id=store.put(_png(), "png", kind="upload"), rotation=0, is_key=False, text_file_id=None
    )
    mixed = [photo, *ingest(store, typed_pdf([PAGE_1, PAGE_2]), "two.pdf")]
    joined = join_typed_pdf_pages(store, mixed, born_digital_pages(store, mixed))
    assert list(joined.pieces) == [1] and joined.absorbed == {2}


# --- picture pages under NFD (fix 3) --------------------------------------------------------------


def test_picture_pages_are_found_when_the_text_layer_is_nfd(
    store: FileStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    pages = ingest(
        store,
        typed_pdf([[*PAGE_1, "Le café est à côté."], [*PAGE_2, "La crème brûlée."]], picture_on=1),
        "nfd.pdf",
    )
    real = documents._pdf_page_pictures

    def nfd(store_: FileStore, pdf_id: str) -> list[tuple[str, bool]]:
        return [(unicodedata.normalize("NFD", t), pic) for t, pic in real(store_, pdf_id)]

    monkeypatch.setattr(documents, "_pdf_page_pictures", nfd)
    joined = join_typed_pdf_pages(store, pages, born_digital_pages(store, pages))
    assert joined.pieces[0].picture_pages == (1,)
