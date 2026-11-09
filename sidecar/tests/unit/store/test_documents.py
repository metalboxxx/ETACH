"""Document input: images, PDF and DOCX → PageInput (plan R3.3). The PDF and DOCX inputs are
built in the tests."""

from __future__ import annotations

import io
import sqlite3
import zipfile

import docx
import pymupdf
import pytest
from docx.shared import Inches
from PIL import Image

from etach.domain.models import PageInput
from etach.domain.pages import skip_answer_reading
from etach.store.documents import (
    BORN_DIGITAL_MIN_TEXT_CHARS,
    FULL_PAGE_IMAGE_FRACTION,
    MAX_TEXT_PAGE_CHARS,
    PDF_DPI,
    UnsupportedDocument,
    born_digital_pages,
    detect_type,
    ingest,
    split_text_page,
)
from etach.store.files import FileStore
from etach.store.repos import files


def png(w: int, h: int, color: tuple[int, int, int] = (0, 128, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def make_pdf(texts: list[str | None]) -> bytes:
    doc = pymupdf.open()
    for text in texts:
        page = doc.new_page(width=595, height=842)  # A4 in points
        if text:
            page.insert_text((72, 72), text)
        else:
            page.draw_rect(pymupdf.Rect(50, 50, 200, 200), color=(0, 0, 0), fill=(0, 0, 0))
    data = doc.tobytes()
    doc.close()
    return bytes(data)


def make_docx(*items: str | bytes) -> bytes:
    """A DOCX with one paragraph per ``str`` and one picture per ``bytes``, in order."""
    document = docx.Document()
    for item in items:
        if isinstance(item, str):
            document.add_paragraph(item)
        else:
            document.add_picture(io.BytesIO(item), width=Inches(1))
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def kind_of(conn: sqlite3.Connection, file_id: str) -> str:
    row = files.get_file(conn, file_id)
    assert row is not None
    return row.kind


# --- R3.3 ------------------------------------------------------------------------------------


def test_r3_3_pdf_with_text_layer(store: FileStore, conn: sqlite3.Connection) -> None:
    data = make_pdf(["I. Choose the best answer.", "II. Read the passage."])
    pages = ingest(store, data, "test.pdf")
    assert len(pages) == 2
    pdf_rows = [r for r in files.list_files(conn) if r.mime == "application/pdf"]
    assert len(pdf_rows) == 1 and pdf_rows[0].kind == "upload"
    for page, expected in zip(pages, ["I. Choose", "II. Read"], strict=True):
        assert (page.rotation, page.is_key) == (0, False)
        image = store.get(page.file_id)
        assert image.kind == "derived" and image.derived_from == pdf_rows[0].id
        assert image.mime == "image/png"
        # A4 at 200 dpi
        assert (image.width, image.height) == (round(595 * PDF_DPI / 72), round(842 * PDF_DPI / 72))
        assert page.text_file_id is not None
        assert kind_of(conn, page.text_file_id) == "text"
        text = store.read_text(page.text_file_id)
        assert text.strip() and text.startswith(expected)
    assert pages[0].file_id != pages[1].file_id


def test_r3_3_docx_text_page_then_image(store: FileStore, conn: sqlite3.Connection) -> None:
    picture = png(64, 32)
    data = make_docx("Read the text and answer the questions.", picture)
    pages = ingest(store, data, "test.docx")
    assert len(pages) == 2
    text_page, image_page = pages
    assert text_page.file_id == text_page.text_file_id
    assert text_page.text_file_id is not None
    assert kind_of(conn, text_page.file_id) == "text"
    assert store.read_text(text_page.file_id) == "Read the text and answer the questions."
    assert image_page.text_file_id is None
    image = store.get(image_page.file_id)
    assert image.kind == "derived" and image.mime == "image/png"
    docx_row = store.get(image.derived_from or "")
    assert docx_row.kind == "upload" and docx_row.path.endswith(".docx")
    assert store.read_bytes(image_page.file_id) == picture
    assert all((p.rotation, p.is_key) == (0, False) for p in pages)


# --- more document cases ---------------------------------------------------------------------


def test_pdf_page_without_text_layer(store: FileStore) -> None:
    pages = ingest(store, make_pdf([None, "Some text"]), "scan.pdf")
    assert [p.text_file_id is None for p in pages] == [True, False]


def test_docx_images_in_document_order_text_first(store: FileStore) -> None:
    first, second = png(10, 10, (255, 0, 0)), png(20, 10, (0, 0, 255))
    data = make_docx(first, "Question 1.", second, "Question 2.")
    document = docx.Document(io.BytesIO(data))
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "31. A", "32. B"
    buf = io.BytesIO()
    document.save(buf)

    pages = ingest(store, buf.getvalue(), "mixed.docx")
    assert len(pages) == 3
    assert store.read_text(pages[0].file_id) == "Question 1.\n\nQuestion 2.\n31. A | 32. B"
    assert [store.read_bytes(p.file_id) for p in pages[1:]] == [first, second]


def test_image_is_one_page(store: FileStore) -> None:
    data = png(30, 40)
    assert ingest(store, data, "photo.png") == [
        PageInput(file_id=store.put(data, "png"), rotation=0, is_key=False, text_file_id=None)
    ]
    jpg = io.BytesIO()
    Image.new("RGB", (8, 8)).save(jpg, "JPEG")
    (page,) = ingest(store, jpg.getvalue(), "photo.jpg")
    assert store.get(page.file_id).mime == "image/jpeg"
    webp = io.BytesIO()
    Image.new("RGB", (8, 8)).save(webp, "WEBP")
    (page,) = ingest(store, webp.getvalue(), "photo.webp")
    assert store.get(page.file_id).kind == "upload"


def test_unsupported_documents(store: FileStore, conn: sqlite3.Connection) -> None:
    heic = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic"
    with pytest.raises(UnsupportedDocument, match="HEIC"):
        ingest(store, heic, "IMG_0001.HEIC")
    with pytest.raises(UnsupportedDocument, match="not a JPEG"):
        ingest(store, b"hello", "notes.txt")
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        zf.writestr("a.txt", "x")
    with pytest.raises(UnsupportedDocument, match="not a Word"):
        ingest(store, zbuf.getvalue(), "a.zip")
    with pytest.raises(UnsupportedDocument, match=r".doc file"):
        ingest(store, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100, "old.doc")
    with pytest.raises(UnsupportedDocument, match="no text or pictures"):
        ingest(store, make_docx(), "empty.docx")
    locked = pymupdf.open()
    locked.new_page().insert_text((72, 72), "secret")
    encrypted = locked.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="user", owner_pw="owner"
    )
    with pytest.raises(UnsupportedDocument, match="password"):
        ingest(store, bytes(encrypted), "locked.pdf")
    with pytest.raises(UnsupportedDocument):
        ingest(store, b"\xff\xd8\xff\xe0 truncated", "broken.jpg")
    assert files.list_files(conn) == []  # nothing stored for a rejected document


def test_detect_type() -> None:
    assert detect_type(png(2, 2)) == "png"
    assert detect_type(make_pdf(["x"])) == "pdf"
    assert detect_type(make_docx("x")) == "docx"


# --- File.original_name (data-model v1.5 §2.8) -------------------------------------------------


def test_ingest_stores_the_upload_name(store: FileStore) -> None:
    (page,) = ingest(store, png(20, 30), "Lop8-HKI-De1 (1).png")
    assert store.get(page.file_id).original_name == "Lop8-HKI-De1 (1).png"
    pages = ingest(store, make_pdf(["I. Choose the best answer."]), "De2.pdf")
    image = store.get(pages[0].file_id)
    assert image.kind == "derived" and image.original_name is None
    assert image.derived_from is not None
    assert store.get(image.derived_from).original_name == "De2.pdf"
    assert pages[0].text_file_id is not None
    assert store.get(pages[0].text_file_id).original_name is None
    docx_pages = ingest(store, make_docx("Some text", png(12, 12, (1, 2, 3))), "De3.docx")
    uploads = {store.get(p.file_id).derived_from for p in docx_pages} - {None}
    assert [store.get(u).original_name for u in uploads if u] == ["De3.docx"]


# --- long text pages (M1 long-DOCX fix) ------------------------------------------------------


def mcq(n: int, filler: int = 120) -> list[str]:
    """One synthetic MCQ: its stem line and its four option lines."""
    return [
        f"{n}. Synthetic question {n}: " + "x" * filler,
        "A. alpha    B. beta",
        "C. gamma    D. delta",
    ]


def sections(count: int, per_section: int, start: int = 1) -> list[str]:
    roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
    lines: list[str] = []
    n = start
    for s in range(count):
        lines.append(f"{roman[s]}. Synthetic section {s + 1}. Choose the best answer.")
        for _ in range(per_section):
            lines.extend(mcq(n))
            n += 1
    return lines


def starts(pieces: list[str]) -> list[str]:
    return [p.split("\n", 1)[0] for p in pieces]


def test_split_short_text_stays_one_piece() -> None:
    text = "\n".join(sections(2, 3))
    assert len(text) < MAX_TEXT_PAGE_CHARS
    assert split_text_page(text) == [text]
    assert split_text_page("  \n ") == []


def test_split_long_text_breaks_at_section_headings() -> None:
    lines = sections(6, 12)  # ~ 6 x 1 900 characters
    text = "\n".join(lines)
    pieces = split_text_page(text)
    assert len(pieces) > 1
    assert all(len(p) <= MAX_TEXT_PAGE_CHARS for p in pieces)
    assert all(
        p.split("\n", 1)[0].split(".")[0] in {"I", "II", "III", "IV", "V", "VI"} for p in pieces
    )
    # nothing lost, nothing reordered
    assert "\n".join(pieces) == text


def test_split_falls_back_to_question_starts_then_blank_lines() -> None:
    lines = sections(1, 80)  # one long section: no heading to break at after the first
    pieces = split_text_page("\n".join(lines))
    assert len(pieces) > 1
    assert all(len(p) <= MAX_TEXT_PAGE_CHARS for p in pieces)
    assert starts(pieces)[0].startswith("I. ")
    assert all(s.split(".")[0].isdigit() for s in starts(pieces)[1:])
    # prose without headings or numbers: blank lines
    paras = [f"Paragraph {i} " + "y" * 900 for i in range(12)]
    pieces = split_text_page("\n\n".join(paras))
    assert len(pieces) > 1
    assert all(len(p) <= MAX_TEXT_PAGE_CHARS for p in pieces)
    assert [p.startswith("Paragraph ") for p in pieces] == [True] * len(pieces)
    assert "\n\n".join(pieces) == "\n\n".join(paras)


def test_split_never_separates_a_question_from_its_options() -> None:
    # blank lines between the stems and their options, and option lines at every position
    lines: list[str] = ["III. Synthetic section."]
    for n in range(1, 70):
        lines += [
            f"{n}. Stem {n} " + "z" * 100,
            "",
            "A. one   B. two",
            "",
            "C. three   D. four",
            "",
        ]
    pieces = split_text_page("\n".join(lines))
    assert len(pieces) > 1
    for p in pieces:
        first = p.split("\n", 1)[0]
        assert not first.startswith(("A.", "C.")), first
        assert p.rstrip().endswith("D. four")


def test_split_keeps_an_overlong_question_whole() -> None:
    long_question = ["1. " + "w" * (MAX_TEXT_PAGE_CHARS + 500), "A. a  B. b  C. c  D. d"]
    text = "\n".join([*long_question, *mcq(2), *mcq(3)])
    pieces = split_text_page(text)
    assert pieces[0] == "\n".join(long_question)
    assert pieces[1].startswith("2. ")


def test_long_docx_becomes_text_pages_in_order(store: FileStore, conn: sqlite3.Connection) -> None:
    lines = sections(6, 12)
    picture = png(40, 20)
    pages = ingest(store, make_docx(*lines, picture), "long.docx")
    text_pages = [p for p in pages if p.text_file_id is not None]
    assert len(text_pages) == len(split_text_page("\n".join(lines))) > 1
    assert pages[: len(text_pages)] == text_pages  # text first, then the picture
    assert pages[-1].text_file_id is None
    texts = [store.read_text(p.file_id) for p in text_pages]
    assert all(p.file_id == p.text_file_id for p in text_pages)
    assert all(kind_of(conn, p.file_id) == "text" for p in text_pages)
    assert len({p.file_id for p in text_pages}) == len(text_pages)
    assert "\n".join(texts) == "\n".join(lines)
    docx_ids = {store.get(p.file_id).derived_from for p in pages}
    assert len(docx_ids) == 1


# --- the splitter never cuts inside a question (verifier probes) ----------------------------


def filler_mcqs(first: int, chars: int) -> list[str]:
    """Synthetic MCQs numbered from ``first`` until they hold about ``chars`` characters."""
    lines: list[str] = []
    n = first
    while len("\n".join(lines)) < chars:
        lines.extend(mcq(n))
        n += 1
    return lines


@pytest.mark.parametrize("roman", [["I", "II", "III"], ["i", "ii", "iii"]])
def test_split_keeps_a_statement_list_question_whole(roman: list[str]) -> None:
    # the statements straddle the page limit, so a split at a Roman line would cut the question
    head = ["IV. Synthetic section. Choose the best answer.", *filler_mcqs(1, 5600)]
    n = 1 + len(head) // 3
    question = [
        f"{n}. Which statements are true? " + "s" * 60,
        *[f"{r}. Synthetic statement {r} " + "t" * 160 for r in roman],
        "A. I and II   B. II and III   C. I and III   D. all",
    ]
    tail = ["V. Synthetic section. Choose the best answer.", *filler_mcqs(n + 1, 4000)]
    text = "\n".join([*head, *question, *tail])
    assert len("\n".join(head)) < MAX_TEXT_PAGE_CHARS < len("\n".join([*head, *question]))
    pieces = split_text_page(text)
    assert "\n".join(pieces) == text
    assert all(len(p) <= MAX_TEXT_PAGE_CHARS for p in pieces)
    block = "\n".join(question)
    assert sum(block in p for p in pieces) == 1
    assert not any(s.startswith(tuple(f"{r}. " for r in roman)) for s in starts(pieces))
    # the break moves back to the question start
    assert starts(pieces)[1] == question[0]


def test_split_dialogue_line_is_not_a_heading() -> None:
    paras = [f"Paragraph {i}: Synthetic speaker asks a question " + "d" * 700 for i in range(10)]
    lines: list[str] = []
    for p in paras:
        lines += [p, "I - think so.", "i. maybe not.", ""]
    text = "\n".join(lines).strip()
    pieces = split_text_page(text)
    assert len(pieces) > 1
    assert all(len(p) <= MAX_TEXT_PAGE_CHARS for p in pieces)
    assert all(p.startswith("Paragraph ") for p in pieces)


def test_split_never_breaks_at_a_blank_line_inside_a_question() -> None:
    long_question = [
        "1. " + "w" * 3000,
        "",
        "More of the same stem " + "v" * 3500,
        "A. a  B. b",
        "",
        "C. c  D. d",
    ]
    text = "\n".join([*long_question, *mcq(2), *mcq(3)])
    pieces = split_text_page(text)
    assert pieces[0] == "\n".join(long_question)
    assert pieces[1].startswith("2. ")


def test_split_normalises_decomposed_vietnamese() -> None:
    import unicodedata

    lines: list[str] = []
    for n in range(1, 60):
        lines += [f"Câu {n}. Chọn đáp án đúng " + "x" * 120, "A. một   B. hai", "C. ba   D. bốn"]
    nfc = "\n".join(lines)
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfd != nfc and "Câu 1." not in nfd
    pieces = split_text_page(nfd)
    assert len(pieces) > 1
    assert all(len(p) <= MAX_TEXT_PAGE_CHARS for p in pieces)
    assert all(p.startswith("Câu ") for p in pieces)
    assert "\n".join(pieces) == nfc  # stored as NFC


def test_split_option_labels_c_and_d_are_never_headings() -> None:
    lines: list[str] = []
    for n in range(1, 60):
        lines += [f"{n}. Stem {n} " + "z" * 100, "A. one", "B. two", "C. three", "(D) four"]
    lines += ["C. a stray line outside any question " + "c" * 50] * 3
    lines += [f"{n}. Stem {n} " + "z" * 100 for n in range(60, 80)]
    pieces = split_text_page("\n".join(lines))
    assert len(pieces) > 1
    assert not any(s.startswith(("A.", "B.", "C.", "(D)", "D.")) for s in starts(pieces))


# --- "A:" / "A -" option labels and "Q5." / bare-number question starts (verifier probes) ---
# The text after the question has no blank line, so the only blank-line break is the one inside
# the question: a splitter that does not see the question would break there.


def run_on(chars: int) -> str:
    """Prose without blank lines, question starts or option labels: no break anywhere."""
    return "\n".join(f"Paragraph {i} " + "p" * 700 for i in range(chars // 712 + 1))


@pytest.mark.parametrize("sep", [":", " -", " \u2013"])
@pytest.mark.parametrize("one_line", [True, False])
def test_split_colon_and_dash_option_labels_stay_with_their_stem(sep: str, one_line: bool) -> None:
    labels = ["A", "B", "C", "D"]
    opts = [f"{a}{sep} {w}" for a, w in zip(labels, ["go", "goes", "went", "gone"], strict=True)]
    question = [
        "12. Read the passage and choose " + "r" * 2400,
        "",
        *([" / ".join(opts)] if one_line else opts),
    ]
    text = "\n".join([*question, run_on(3900)])
    assert len(text) > MAX_TEXT_PAGE_CHARS
    pieces = split_text_page(text)
    assert pieces == [text]  # no break fits: the question is never cut
    assert not any(s.startswith(tuple(labels)) for s in starts(pieces))


@pytest.mark.parametrize(
    "line", ["A man walked in.", "I - think so.", "A-level students.", "a b c"]
)
def test_split_prose_starting_a_or_i_is_not_an_option(line: str) -> None:
    lines: list[str] = []
    for i in range(10):
        lines += [f"Paragraph {i} " + "m" * 700, "", line]
    pieces = split_text_page("\n".join(lines))
    assert len(pieces) > 1  # the blank line before the prose line is still a break
    assert all(len(p) <= MAX_TEXT_PAGE_CHARS for p in pieces)
    assert all(s == line for s in starts(pieces)[1:])


def test_split_dialogue_lines_never_cause_a_break_inside_a_question() -> None:
    # "A: Hello. B: Hi." reads like an option line. Inside a question it only widens the
    # question; outside one it only removes the blank-line break before it.
    question = [
        "5. Read the dialogue and choose the best reply " + "q" * 2400,
        "",
        "A: Hello. B: Hi.",
        "",
        "A: How are you? " + "h" * 2000,
        "",
        "A. Fine   B. Good   C. OK   D. Bad",
    ]
    text = "\n".join([*question, run_on(2000)])
    assert split_text_page(text) == [text]
    lines: list[str] = []
    for i in range(10):
        lines += [f"Paragraph {i} " + "m" * 700, "", "A: Hello. B: Hi.", ""]
    pieces = split_text_page("\n".join(lines).strip())
    assert len(pieces) > 1
    assert all(len(p) <= MAX_TEXT_PAGE_CHARS for p in pieces)
    assert all(s.startswith("Paragraph ") for s in starts(pieces))


def long_stem(head: str) -> list[str]:
    return [
        f"{head} Synthetic stem " + "w" * 3000,
        "",
        "More of the same stem " + "v" * 2500,
        "A. a  B. b  C. c  D. d",
    ]


@pytest.mark.parametrize("head", ["Q5.", "Q 5:", "q5)"])
def test_split_q_number_question_start_keeps_its_stem_whole(head: str) -> None:
    text = "\n".join([*long_stem(head), run_on(1000)])
    assert split_text_page(text) == [text]


def test_split_bare_number_question_start_only_when_next_expected() -> None:
    # "41 The …" right after question 40 is a question start: kept whole, broken before ...
    question = long_stem("41 The")
    text = "\n".join([*mcq(40), *question, run_on(1000)])
    pieces = split_text_page(text)
    assert pieces == ["\n".join(mcq(40)), "\n".join([*question, run_on(1000)])]
    # ... while "7 The …" out of sequence is not a question start
    text = "\n".join([*mcq(40), run_on(3000), "41 The next stem", "A. a  B. b", run_on(3000)])
    assert starts(split_text_page(text))[1] == "41 The next stem"
    text = "\n".join([*mcq(40), run_on(3000), "7 The year was long", run_on(3000)])
    assert split_text_page(text) == [text]


# --- born-digital pages (PRD D26) ----------------------------------------------------------------

TYPED = "\n".join(f"{n}. Choose the best answer: A. cat B. hat C. car D. map" for n in range(1, 6))


def make_scan_pdf(*, ocr: str | None, strips: int = 1, fraction: float = 1.0) -> bytes:
    """A page that is an image covering ``fraction`` of its height (in ``strips`` pieces), with
    an invisible OCR text layer when ``ocr`` is given (``render_mode=3``)."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    height = 842 * fraction / strips
    for i in range(strips):
        rect = pymupdf.Rect(0, i * height, 595, (i + 1) * height)
        page.insert_image(rect, stream=png(60, 80, (240, 240, 240)), keep_proportion=False)
    if ocr:
        page.insert_text((40, 72), ocr, fontsize=9, render_mode=3)
    data = bytes(doc.tobytes())
    doc.close()
    return data


def make_typed_pdf_with_logo() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(pymupdf.Rect(40, 20, 140, 70), stream=png(50, 25))
    page.insert_text((40, 100), TYPED, fontsize=9)
    data = bytes(doc.tobytes())
    doc.close()
    return data


def test_born_digital_text_pdf(store: FileStore) -> None:
    pages = ingest(store, make_pdf([TYPED, TYPED.replace("cat", "dog")]), "typed.pdf")
    assert born_digital_pages(store, pages) == [True, True]
    logo = ingest(store, make_typed_pdf_with_logo(), "logo.pdf")
    assert born_digital_pages(store, logo) == [True]  # a small picture is not a scan


def test_scanned_pdf_with_ocr_layer_is_not_born_digital(store: FileStore) -> None:
    for strips in (1, 3):  # one page-sized image, or a scan cut into strips
        pages = ingest(store, make_scan_pdf(ocr=TYPED, strips=strips), f"scan{strips}.pdf")
        assert pages[0].text_file_id is not None  # the OCR layer was stored
        assert born_digital_pages(store, pages) == [False]
    # below the full-page fraction it is a typed page with a picture
    pages = ingest(store, make_scan_pdf(ocr=TYPED, fraction=0.7), "half.pdf")
    assert born_digital_pages(store, pages) == [True]
    assert FULL_PAGE_IMAGE_FRACTION == 0.8


def test_pdf_page_without_a_full_text_layer_is_not_born_digital(store: FileStore) -> None:
    pages = ingest(store, make_pdf([None, "Page 2", TYPED]), "thin.pdf")
    assert born_digital_pages(store, pages) == [False, False, True]
    assert len("Page 2") < BORN_DIGITAL_MIN_TEXT_CHARS <= len(TYPED)


def test_docx_pages_are_born_digital_with_and_without_pictures(store: FileStore) -> None:
    text_only = ingest(store, make_docx("1. Choose A, B, C or D."), "a.docx")
    assert born_digital_pages(store, text_only) == [True]
    with_pictures = ingest(store, make_docx("1. Choose.", png(30, 30), png(40, 20)), "b.docx")
    assert len(with_pictures) == 3
    assert born_digital_pages(store, with_pictures) == [True, True, True]
    only_picture = ingest(store, make_docx(png(31, 31)), "c.docx")
    assert born_digital_pages(store, only_picture) == [True]


def test_photos_are_not_born_digital(store: FileStore) -> None:
    pages = [*ingest(store, png(300, 400), "1.png"), *ingest(store, png(301, 400), "2.png")]
    assert born_digital_pages(store, pages) == [False, False]


def test_mixed_pages_are_judged_one_by_one(store: FileStore) -> None:
    pages = [
        *ingest(store, png(302, 400), "photo.png"),
        *ingest(store, make_pdf([TYPED]), "typed.pdf"),
    ]
    flags = born_digital_pages(store, pages)
    assert flags == [False, True]
    assert skip_answer_reading(flags) is False
    assert skip_answer_reading([True, True]) is True
    assert skip_answer_reading([]) is False
