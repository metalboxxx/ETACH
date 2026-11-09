"""Document input: an image, a PDF or a DOCX → the pages of a photo check (PRD §11 "Documents in",
data-model §2.7 ``PageInput``).

- **Image** (JPEG/PNG/WebP): stored as an ``upload``; one page.
- **PDF**: stored as an ``upload``. Each page is rasterized at 200 dpi to a PNG (``derived`` from
  the PDF). A page with a text layer also gets that text as a ``text`` file in ``text_file_id``.
- **DOCX**: stored as an ``upload``. The body text (paragraphs and table rows, in order) becomes
  **text-only pages** (``file_id = text_file_id``), placed first: one page, or several when the
  text is longer than :data:`MAX_TEXT_PAGE_CHARS` (:func:`split_text_page` breaks it at section
  headings, else question starts, else blank lines; never inside a question). The text is
  stored in NFC.
  Then one image page per embedded image, in document order, each ``derived`` from the DOCX.
- Anything else (including HEIC, not supported in this version) raises
  :class:`UnsupportedDocument`.

The type is decided from the bytes; the file name is used only in messages. Every page comes back
with ``rotation=0`` and ``is_key=False`` (the photo check sets them).

**Born-digital pages** (PRD D26, :func:`born_digital_pages`): a typed page cannot hold a student's
handwriting, so the extract graph skips answer reading for it. The marker is not stored (no
``PageInput`` field); it is worked out again from what ingest already stored:

- a **text-only page** (it has no image at all);
- **every page of a DOCX** (its text pages and its embedded pictures, which are printed, not
  handwritten): the page's file comes from a ``.docx`` upload through ``derived_from``;
- a **PDF page** with a text layer of at least :data:`BORN_DIGITAL_MIN_TEXT_CHARS` characters
  whose images together cover less than :data:`FULL_PAGE_IMAGE_FRACTION` of the page. A scanned
  page (a page-sized image, even with an OCR text layer) is read like a photo;
- anything else (a photo) is not born-digital.
"""

from __future__ import annotations

import bisect
import io
import logging
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from typing import Literal

import docx
import pymupdf
from docx.document import Document as DocxDocument
from docx.opc.exceptions import PackageNotFoundError
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from PIL import Image

from etach.domain.llm_schemas import TranscribedGroup, TranscribedQuestion, TranscribedSection
from etach.domain.models import PageInput
from etach.domain.pages import is_text_only
from etach.store.files import FileStore

__all__ = [
    "BORN_DIGITAL_MIN_TEXT_CHARS",
    "FULL_PAGE_IMAGE_FRACTION",
    "MAX_TEXT_PAGE_CHARS",
    "PDF_DPI",
    "DocumentType",
    "JoinedPages",
    "TextPiece",
    "UnsupportedDocument",
    "born_digital_pages",
    "detect_type",
    "ingest",
    "join_typed_pdf_pages",
    "locate_pages",
    "pdf_page_is_born_digital",
    "split_text_page",
]

log = logging.getLogger(__name__)

PDF_DPI = 200

DocumentType = Literal["jpeg", "png", "webp", "pdf", "docx"]

_HEIF_BRANDS = {b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx", b"mif1", b"msf1", b"heif"}
_DOCX_MAIN = "word/document.xml"
_R_EMBED = qn("r:embed")
_R_ID = qn("r:id")
_BLIP = qn("a:blip")
_VML_IMAGEDATA = "{urn:schemas-microsoft-com:vml}imagedata"


class UnsupportedDocument(ValueError):
    """The input is not a JPEG, PNG, WebP, PDF or DOCX, or it cannot be read."""


def detect_type(data: bytes, filename: str = "") -> DocumentType:
    """The document type from its first bytes; raises :class:`UnsupportedDocument`."""
    name = filename or "the file"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if b"%PDF-" in data[:1024]:
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                if _DOCX_MAIN in zf.namelist():
                    return "docx"
        except zipfile.BadZipFile as exc:
            raise UnsupportedDocument(f"{name}: a damaged ZIP/DOCX file") from exc
        raise UnsupportedDocument(f"{name}: a ZIP file that is not a Word document (.docx)")
    if data[4:8] == b"ftyp" and data[8:12] in _HEIF_BRANDS:
        raise UnsupportedDocument(
            f"{name}: HEIC/HEIF photos are not supported in this version;"
            " set the phone camera to JPEG (Most Compatible) or convert the photo"
        )
    if data.startswith(b"\xd0\xcf\x11\xe0"):
        raise UnsupportedDocument(f"{name}: an old Word .doc file; save it as .docx")
    raise UnsupportedDocument(f"{name}: not a JPEG, PNG, WebP, PDF or DOCX file")


def _page(file_id: str, text_file_id: str | None = None) -> PageInput:
    return PageInput(file_id=file_id, rotation=0, is_key=False, text_file_id=text_file_id)


def ingest(store: FileStore, data: bytes, filename: str) -> list[PageInput]:
    """Store a dropped document and return its pages in order."""
    kind = detect_type(data, filename)
    if kind == "pdf":
        return _ingest_pdf(store, data, filename)
    if kind == "docx":
        return _ingest_docx(store, data, filename)
    try:
        file_id = store.put(
            data, "jpg" if kind == "jpeg" else kind, kind="upload", original_name=filename or None
        )
    except ValueError as exc:
        raise UnsupportedDocument(f"{filename}: {exc}") from exc
    return [_page(file_id)]


# --- PDF -------------------------------------------------------------------------------------


def _ingest_pdf(store: FileStore, data: bytes, filename: str) -> list[PageInput]:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")  # type: ignore[no-untyped-call]
    except Exception as exc:
        raise UnsupportedDocument(f"{filename}: a damaged PDF ({exc})") from exc
    with doc:
        if doc.needs_pass:
            raise UnsupportedDocument(f"{filename}: the PDF is password-protected")
        if doc.page_count == 0:
            raise UnsupportedDocument(f"{filename}: the PDF has no pages")
        pdf_id = store.put(data, "pdf", kind="upload", original_name=filename or None)
        pages: list[PageInput] = []
        for page_no in range(doc.page_count):
            page = doc.load_page(page_no)  # type: ignore[no-untyped-call]
            png = page.get_pixmap(dpi=PDF_DPI, alpha=False).tobytes("png")
            image_id = store.put(png, "png", kind="derived", derived_from=pdf_id)
            text = str(page.get_text()).strip()
            text_id = store.put_text(text, derived_from=pdf_id) if text else None
            pages.append(_page(image_id, text_id))
    return pages


# --- DOCX ------------------------------------------------------------------------------------


def _row_text(row_cells: list[object]) -> str:
    seen: set[int] = set()
    parts: list[str] = []
    for cell in row_cells:
        tc = cell._tc  # type: ignore[attr-defined]
        if id(tc) in seen:  # a merged cell repeats in row.cells
            continue
        seen.add(id(tc))
        parts.append(str(cell.text).strip())  # type: ignore[attr-defined]
    return " | ".join(parts)


def _docx_text(doc: DocxDocument) -> str:
    """The body text in document order: one line per paragraph, one line per table row."""
    lines: list[str] = []
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            lines.append(Paragraph(child, doc).text)
        elif child.tag == qn("w:tbl"):
            lines.extend(_row_text(list(row.cells)) for row in Table(child, doc).rows)
    return "\n".join(lines).strip()


def _docx_image_ids(doc: DocxDocument) -> list[str]:
    """The relationship IDs of the body's images, in document order."""
    rids: list[str] = []
    for el in doc.element.body.iter():
        if el.tag == _BLIP:
            rid = el.get(_R_EMBED)  # r:link (an external file) is not embedded; skipped
        elif el.tag == _VML_IMAGEDATA:
            rid = el.get(_R_ID)
        else:
            continue
        if rid:
            rids.append(rid)
    return rids


def _image_for_store(blob: bytes, content_type: str) -> tuple[bytes, str] | None:
    """``(bytes, ext)`` for an embedded image: JPEG/PNG/WebP as is, other formats Pillow reads
    (GIF, BMP, TIFF) converted to PNG. ``None`` when Pillow cannot read it (EMF/WMF/SVG)."""
    try:
        with Image.open(io.BytesIO(blob)) as img:
            fmt = img.format
            if fmt in ("JPEG", "PNG", "WEBP"):
                return blob, {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[fmt]
            img.load()
            converted = img.convert("RGBA" if img.mode in ("RGBA", "LA", "PA", "P") else "RGB")
            buf = io.BytesIO()
            converted.save(buf, "PNG")
            return buf.getvalue(), "png"
    except Exception as exc:
        log.warning("skipped an embedded %s image: %s", content_type, exc)
        return None


#: The longest text-only page, in characters (M1 ``baseline2``: a whole 40-question DOCX as one
#: page made ``transcribe_page`` hit its output cap). A longer text is split into several pages.
MAX_TEXT_PAGE_CHARS = 6000
#: A piece shorter than this is cut only where nothing better fits (avoids tiny pages).
_MIN_TEXT_PAGE_CHARS = MAX_TEXT_PAGE_CHARS // 3

# Break priorities: a boundary is "before this line".
_BREAK_SECTION = 3
_BREAK_QUESTION = 2
_BREAK_BLANK = 1
#: a section heading: an upper-case Roman numeral + "." or ")" + a space ("IV. …", "II) …"),
#: "Part"/"PART"/"Section" + a number or letter, or a question range ("Questions 1-5",
#: "Câu 1 - 5"). Only outside a question (:func:`_inside_questions`): a statement list
#: ("I. …", "II. …") inside a question is part of it.
_SECTION_HEAD = re.compile(
    r"^\s*(?:[IVX]{1,5}[.)]\s"
    r"|(?i:(?:part|section)\s+(?:\d+|[IVX]{1,5}|[A-Z])\b)"
    r"|(?i:(?:questions?|câu|cau)\s*\d+\s*(?:[-\u2013\u2014]|to|đến)\s*\d+))"  # en/em dash
)
#: a question start: "41." / "41)" / "Question 41" / "Câu 41" / "Q5." / "Q 5:"
_QUESTION_HEAD = re.compile(
    r"^\s*(?:(\d{1,3})\s*[.)]|(?:question|câu|cau)\s*(\d{1,3})\b|q\s*(\d{1,3})\s*[.):])", re.I
)
#: a bare question number then an upper-case word ("41 The …"): a question start only when it is
#: the number after the previous question start (:func:`_question_heads`)
_BARE_QUESTION_HEAD = re.compile(r"^\s*(\d{1,3})\s+[A-Z]")
#: an option line ("A. …", "(B) …", "c) …", "A: …", "B - …", or an en dash): never the first
#: line of a page. ":" and dashes need a space after them, so "A-level" is prose; a dialogue
#: line ("A: Hello.") also matches, which only removes breaks.
_OPTION_LINE = re.compile(r"^\s*\(?[A-Da-d]\s*(?:[.)]|[:\-\u2013]\s)")


def _question_heads(lines: list[str]) -> list[bool]:
    """For each line, whether it starts a question."""
    heads = [False] * len(lines)
    last: int | None = None  # the number of the previous question start
    for i, line in enumerate(lines):
        m = _QUESTION_HEAD.match(line)
        if m:
            heads[i] = True
            last = int(next(g for g in m.groups() if g))
            continue
        m = _BARE_QUESTION_HEAD.match(line)
        if m and last is not None and int(m.group(1)) == last + 1:
            heads[i] = True
            last += 1
    return heads


def _inside_questions(lines: list[str], is_head: list[bool]) -> list[bool]:
    """For each line, whether it is inside a question: after a question start, up to and
    including the last option line before the next question start. A question without option
    lines has no inside lines."""
    inside = [False] * len(lines)
    heads = [i for i, h in enumerate(is_head) if h]
    for k, q in enumerate(heads):
        stop = heads[k + 1] if k + 1 < len(heads) else len(lines)
        last = max((j for j in range(q + 1, stop) if _OPTION_LINE.match(lines[j])), default=q)
        for j in range(q + 1, last + 1):
            inside[j] = True
    return inside


def _break_priority(lines: list[str], i: int, inside: bool, is_head: bool) -> int:
    """How good a page break before ``lines[i]`` is (0 = never)."""
    line = lines[i]
    if inside or _OPTION_LINE.match(line):
        return 0
    if line.strip():
        if _SECTION_HEAD.match(line):
            return _BREAK_SECTION
        if is_head:
            return _BREAK_QUESTION
        return 0
    # a blank line: break only when the next text is not an option of the question above
    nxt = next((x for x in lines[i + 1 :] if x.strip()), None)
    return 0 if nxt is None or _OPTION_LINE.match(nxt) else _BREAK_BLANK


def split_text_page(text: str, limit: int = MAX_TEXT_PAGE_CHARS) -> list[str]:
    """``text`` (normalised to NFC) as pieces of at most ``limit`` characters, in order, broken
    between lines.

    A break goes before a section heading if one fits, else before a question start, else at a
    blank line. No break falls inside a question (from its start line up to its last option
    line), so a question always stays whole with its options. Among the breaks that fit, the
    best kind wins and then the latest, preferring pieces of at least ``limit // 3``. When no
    break fits, the piece runs to the first break after the limit (a single question longer than
    ``limit`` is not cut). A text of at most ``limit`` is one piece.
    """
    text = unicodedata.normalize("NFC", text).strip()
    if len(text) <= limit:
        return [text] if text else []
    lines = text.split("\n")
    heads = _question_heads(lines)
    inside = _inside_questions(lines, heads)
    prio = [_break_priority(lines, i, inside[i], heads[i]) for i in range(len(lines))]
    pieces: list[str] = []
    start = 0
    while start < len(lines):
        size = -1  # the joined length of lines[start:i], before adding lines[i]
        best: tuple[bool, int, int] | None = None  # (long enough, priority, index)
        end = len(lines)
        for i in range(start, len(lines)):
            if i > start and prio[i]:
                cand = (size >= _MIN_TEXT_PAGE_CHARS, prio[i], i)
                if size > limit:
                    if best is None:
                        best = cand  # nothing fitted: the first break after the limit
                    break
                if best is None or cand > best:
                    best = cand
            size += len(lines[i]) + 1
        else:
            if size <= limit:
                best = None  # the rest fits: one last piece
        if best is not None:
            end = best[2]
        piece = "\n".join(lines[start:end]).strip()
        if piece:
            pieces.append(piece)
        start = end
    return pieces


def _ingest_docx(store: FileStore, data: bytes, filename: str) -> list[PageInput]:
    try:
        doc = docx.Document(io.BytesIO(data))
    except (PackageNotFoundError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        raise UnsupportedDocument(f"{filename}: a damaged Word document ({exc})") from exc
    text = _docx_text(doc)
    images: list[tuple[bytes, str]] = []
    related = doc.part.related_parts
    for rid in _docx_image_ids(doc):
        part = related.get(rid)
        if part is None:
            continue
        stored = _image_for_store(part.blob, part.content_type)
        if stored is not None:
            images.append(stored)
    if not text and not images:
        raise UnsupportedDocument(f"{filename}: the Word document has no text or pictures")
    docx_id = store.put(data, "docx", kind="upload", original_name=filename or None)
    pages: list[PageInput] = []
    for piece in split_text_page(text):
        text_id = store.put_text(piece, derived_from=docx_id)
        pages.append(_page(text_id, text_id))
    for blob, ext in images:
        image_id = store.put(blob, ext, kind="derived", derived_from=docx_id)
        pages.append(_page(image_id))
    return pages


# --- born-digital pages (PRD D26) ----------------------------------------------------------------

#: A PDF page whose images together cover at least this fraction of the page area is a scan
#: (a full-page image), even with an OCR text layer: it is read like a photo.
FULL_PAGE_IMAGE_FRACTION = 0.8
#: The shortest text layer that counts as a full one (the M1 typed PDFs have 364-3 290 characters
#: per page; a scan without OCR has none).
BORN_DIGITAL_MIN_TEXT_CHARS = 100


def pdf_page_is_born_digital(page: pymupdf.Page) -> bool:
    """A typed PDF page: a text layer of at least :data:`BORN_DIGITAL_MIN_TEXT_CHARS` characters,
    and images covering less than :data:`FULL_PAGE_IMAGE_FRACTION` of the page (each placement
    clipped to the page; the areas are added, so a scan cut into strips still counts)."""
    if len(str(page.get_text()).strip()) < BORN_DIGITAL_MIN_TEXT_CHARS:  # type: ignore[no-untyped-call]
        return False
    rect = page.rect
    area = abs(rect)
    if area <= 0:
        return False
    covered = sum(
        abs(pymupdf.Rect(info["bbox"]) & rect)  # type: ignore[no-untyped-call]
        for info in page.get_image_info()
    )
    return bool(covered / area < FULL_PAGE_IMAGE_FRACTION)


def _upload_of(store: FileStore, file_id: str) -> str | None:
    """The upload a file came from (following ``derived_from``), or ``None``."""
    seen: set[str] = set()
    current: str | None = file_id
    while current is not None and current not in seen:
        seen.add(current)
        try:
            row = store.get(current)
        except KeyError:
            return None
        if row.kind == "upload":
            return row.id
        current = row.derived_from
    return None


def _pdf_page_flags(store: FileStore, pdf_id: str) -> list[tuple[str, bool]]:
    """``(stripped text layer, born-digital)`` for each page of a stored PDF, in order."""
    try:
        doc = pymupdf.open(stream=store.read_bytes(pdf_id), filetype="pdf")  # type: ignore[no-untyped-call]
    except Exception as exc:  # it opened at ingest; when it no longer does, read the answers
        log.warning("born-digital check: cannot open %s: %s", pdf_id, exc)
        return []
    with doc:
        loaded = [doc.load_page(n) for n in range(doc.page_count)]  # type: ignore[no-untyped-call]
        return [(str(p.get_text()).strip(), pdf_page_is_born_digital(p)) for p in loaded]


def born_digital_pages(store: FileStore, pages: list[PageInput]) -> list[bool]:
    """For each page, whether it is born-digital (PRD D26; the rules are in the module
    docstring). A PDF page is found again in its PDF by its text layer (the text ingest stored);
    a page that cannot be matched is not born-digital, so its answers are still read."""
    pdf_cache: dict[str, list[tuple[str, bool]]] = {}
    out: list[bool] = []
    for page in pages:
        if is_text_only(page):
            out.append(True)
            continue
        upload_id = _upload_of(store, page.file_id)
        if upload_id is None:
            out.append(False)
            continue
        path = store.get(upload_id).path.lower()
        if path.endswith(".docx"):
            out.append(True)
        elif path.endswith(".pdf") and page.text_file_id is not None:
            if upload_id not in pdf_cache:
                pdf_cache[upload_id] = _pdf_page_flags(store, upload_id)
            text = store.read_text(page.text_file_id).strip()
            matches = [flag for t, flag in pdf_cache[upload_id] if t == text]
            out.append(bool(matches) and all(matches))
        else:
            out.append(False)
    return out


# --- typed PDFs: joined pages (D12) --------------------------------------------------------------


@dataclass(frozen=True)
class TextPiece:
    """One piece of a typed PDF's joined text (D12), sent to the model in place of its pages.

    ``page_starts``: ``(offset in text, page index)`` ascending, the first at offset 0 (the page
    the piece starts on); ``picture_pages``: the indexes of the PDF pages in the piece that have a
    picture printed on them. Indexes are positions in the page list given to
    :func:`join_typed_pdf_pages`.
    """

    text: str
    page_starts: tuple[tuple[int, int], ...]
    picture_pages: tuple[int, ...]

    def page_at(self, offset: int) -> int:
        """The index of the page whose text holds ``offset``."""
        index = self.page_starts[0][1]
        for start, page in self.page_starts:
            if start > offset:
                break
            index = page
        return index


@dataclass
class JoinedPages:
    """:func:`join_typed_pdf_pages`: ``pieces`` (page index → the piece starting on it) and
    ``absorbed`` (indexes of joined pages that start no piece: no model call of their own)."""

    pieces: dict[int, TextPiece] = field(default_factory=dict)
    absorbed: set[int] = field(default_factory=set)


def _pdf_page_pictures(store: FileStore, pdf_id: str) -> list[tuple[str, bool]]:
    """``(stripped text layer, has a picture)`` for each page of a stored PDF, in order."""
    try:
        doc = pymupdf.open(stream=store.read_bytes(pdf_id), filetype="pdf")  # type: ignore[no-untyped-call]
    except Exception as exc:
        log.warning("typed pages: cannot open %s: %s", pdf_id, exc)
        return []
    with doc:
        loaded = [doc.load_page(n) for n in range(doc.page_count)]  # type: ignore[no-untyped-call]
        return [(str(p.get_text()).strip(), bool(p.get_image_info())) for p in loaded]


def _typed_pdf_runs(store: FileStore, pages: list[PageInput], born: list[bool]) -> list[list[int]]:
    """Runs of consecutive born-digital pages of the same PDF (page indexes)."""
    runs: list[list[int]] = []
    last: str | None = None
    for i, page in enumerate(pages):
        upload = None
        if born[i] and not is_text_only(page) and page.text_file_id is not None:
            upload = _upload_of(store, page.file_id)
            if upload is not None and not store.get(upload).path.lower().endswith(".pdf"):
                upload = None
        if upload is not None and upload == last:
            runs[-1].append(i)
        elif upload is not None:
            runs.append([i])
        last = upload
    return runs


def join_typed_pdf_pages(
    store: FileStore, pages: list[PageInput], born: list[bool], limit: int = MAX_TEXT_PAGE_CHARS
) -> JoinedPages:
    """Join each run of two or more consecutive born-digital pages of the same PDF (D12).

    The run's page texts (NFC) are joined with one line break between pages and cut by
    :func:`split_text_page`, so the printer's page breaks never reach the model. Each piece is
    given to the page its text starts on; the other pages of the run are ``absorbed``. When two
    pieces would start on the same page (a page longer than ``limit``), that run is left as it
    was (one call per page). Photos, Word files and single typed pages are not touched.
    """
    out = JoinedPages()
    pictures_cache: dict[str, list[tuple[str, bool]]] = {}
    for run in _typed_pdf_runs(store, pages, born):
        if len(run) < 2:
            continue
        texts = {
            i: unicodedata.normalize("NFC", store.read_text(str(pages[i].text_file_id))).strip()
            for i in run
        }
        upload = _upload_of(store, pages[run[0]].file_id)
        assert upload is not None
        if upload not in pictures_cache:
            pictures_cache[upload] = _pdf_page_pictures(store, upload)
        with_pictures = {
            unicodedata.normalize("NFC", t) for t, pic in pictures_cache[upload] if pic
        }
        starts: list[tuple[int, int]] = []
        offset = 0
        for i in run:
            starts.append((offset, i))
            offset += len(texts[i]) + 1
        joined = "\n".join(texts[i] for i in run)
        pieces: dict[int, TextPiece] = {}
        cursor = 0
        for piece in split_text_page(joined, limit):
            at = joined.find(piece, cursor)
            if at < 0:  # pieces are whole lines of the text; kept as a guard
                pieces = {}
                break
            end = at + len(piece)
            cursor = end
            local = [(max(0, s - at), i) for s, i in starts if s < end]
            first = max(k for k, (s, _) in enumerate(local) if s == 0)
            local = local[first:]
            owner = local[0][1]
            if owner in pieces:
                pieces = {}
                break
            pics = tuple(i for _, i in local if texts[i] in with_pictures)
            pieces[owner] = TextPiece(piece, tuple(local), pics)
        if not pieces:
            continue
        out.pieces.update(pieces)
        out.absorbed.update(i for i in run if i not in pieces)
    return out


# Matching the model's text against the PDF text: both are folded the same way (accents and
# case dropped, curly quotes and dashes made straight, markdown stars removed, every blank with
# the marker glued to it made one space, spaces collapsed), keeping each folded character's
# offset in the original text so a page stays exact.
_FOLD = str.maketrans(
    {
        "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'", "`": "'",
        "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2033": '"',
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2015": "-",
        "\u2212": "-", "\u00a0": " ", "*": None,
    }
)  # fmt: skip
_BLANK_RUN = r"(?:_+|…+|\.{2,})(?:[ \t]*(?:_+|…+|\.{2,}))*"
_BRACKET_MARK = r"[(\[][ \t]*\d{1,3}[ \t]*[)\]]"
# "(17)" "[17]" anywhere; a blank with the marker glued to it: "__(17)__", "17.____", "17 ____",
# "……17……"
_BLANK = re.compile(
    rf"{_BRACKET_MARK}"
    rf"|(?:(?<![\w.])\d{{1,3}}[.)]?[ \t]*)?{_BLANK_RUN}"
    rf"(?:(?:{_BRACKET_MARK}|\d{{1,3}}(?![\d.]))(?:{_BLANK_RUN})?)?"
)


@dataclass(frozen=True)
class _Folded:
    """A folded text and, for each of its characters, the offset it came from."""

    text: str
    back: tuple[int, ...]  # len(text) + 1 entries; the last is the original length

    def to_original(self, i: int) -> int:
        return self.back[i]

    def from_original(self, offset: int) -> int:
        return bisect.bisect_left(self.back, offset, 0, len(self.text))


def _fold(text: str) -> _Folded:
    chars: list[str] = []
    back: list[int] = []
    for i, c in enumerate(text):
        for d in unicodedata.normalize("NFD", c):
            if unicodedata.combining(d):
                continue
            for e in d.translate(_FOLD).casefold():
                chars.append(e)
                back.append(i)
    s = "".join(chars)
    out_chars: list[str] = []
    out_back: list[int] = []
    pos = 0
    for m in [*_BLANK.finditer(s), None]:
        stop = m.start() if m else len(s)
        for k in range(pos, stop):
            if s[k].isspace():
                if out_chars and out_chars[-1] == " ":
                    continue
                out_chars.append(" ")
            else:
                out_chars.append(s[k])
            out_back.append(back[k])
        if m:
            if not (out_chars and out_chars[-1] == " "):
                out_chars.append(" ")
                out_back.append(back[m.start()])
            pos = m.end()
    return _Folded("".join(out_chars), (*out_back, len(text)))


def _marker_pattern(number: int) -> re.Pattern[str]:
    """Question ``number``'s marker inside a passage, only in marker form: "(17)", "[17]",
    "(Câu 17)", "__(17)__", "17 ____", "17.____", "17……", "17. (CUE)", or "17." / "17)" at a line
    start ("Tom was 17." is not one)."""
    n = number
    return re.compile(
        rf"(?<![^\W_])(?<![(\[])"  # not inside a word or a longer number
        rf"(?:(?P<br>[(\[][ \t]*(?:(?:câu|cau)[ \t]*)?{n}[ \t]*[)\]])"  # (17) [17] (Câu 17)
        rf"|(?P<gl>{n}[.)]?[ \t]*(?=_|\.{{2,}}|…))"  # 17 ____  17.____  17……
        rf"|(?P<cue>{n}[.)][ \t]*(?=\())"  # 17. (SUCCEED)
        rf"|(?P<ln>^[ \t]*{n}[.)](?!\d)))",  # 17. at a line start
        re.M | re.I,
    )


def _find_marker(text: str, number: int, start: int, end: int) -> int:
    """The offset of question ``number``'s marker (:func:`_marker_pattern`) inside ``start``..
    ``end``; -1 when there is none."""
    m = _marker_pattern(number).search(text, start, end)
    return m.start() if m else -1


_WORD = re.compile(r"[^\W_]+")
_BLANK_NEAR = re.compile(r"_|\.{2,}|…")


class _Words:
    """The folded words of a text, each with its original start and end offsets."""

    def __init__(self, text: str) -> None:
        folded = _fold(text)
        found = list(_WORD.finditer(folded.text))
        self.words = [m.group() for m in found]
        self.starts = [folded.to_original(m.start()) for m in found]
        self.ends = [folded.to_original(m.end() - 1) + 1 for m in found]
        self.length = len(text)
        self.index: dict[str, list[int]] = {}
        for i, w in enumerate(self.words):
            self.index.setdefault(w, []).append(i)

    def after(self, j: int) -> int:
        """The offset where word ``j`` starts (the text's end when there is none)."""
        return self.starts[j] if j < len(self.words) else self.length


def _tokens(text: str | None) -> list[str]:
    return _WORD.findall(_fold(text or "").text)


def _starts_of(w: _Words, tokens: list[str]) -> dict[int, int]:
    """Word index → how many words of ``tokens`` match from there, for every place the first
    words (a five-word probe, or a three-word probe at one of the first five words, so one changed
    word still matches) appear."""
    out: dict[int, int] = {}
    if not tokens:
        return out
    probes = [(0, min(5, len(tokens)))]
    if len(tokens) > 3:
        probes += [(s, 3) for s in range(min(5, len(tokens) - 2))]
    for s, k in probes:
        probe = tokens[s : s + k]
        for i in w.index.get(probe[0], ()):
            if i - s < 0 or w.words[i : i + k] != probe:
                continue
            length = k
            while (
                s + length < len(tokens)
                and i + length < len(w.words)
                and w.words[i + length] == tokens[s + length]
            ):
                length += 1
            score = length - (1 if s else 0)
            out[i - s] = max(out.get(i - s, 0), score)
    return out


def _ends_of(w: _Words, tokens: list[str]) -> dict[int, int]:
    """Word index just after the match → matched length, for every place the last words of
    ``tokens`` appear (as :func:`_starts_of`, from the end)."""
    out: dict[int, int] = {}
    if not tokens:
        return out
    rev = tokens[::-1]
    probes = [(0, min(5, len(tokens)))]
    if len(tokens) > 3:
        probes += [(s, 3) for s in range(min(5, len(tokens) - 2))]
    for s, k in probes:
        probe = rev[s : s + k][::-1]  # in reading order
        for i in w.index.get(probe[0], ()):
            j = i + k + s  # the end of the whole stimulus when the last ``s`` words also match
            if w.words[i : i + k] != probe:
                continue
            length = k
            while (
                s + length < len(tokens)
                and i + k - length - 1 >= 0
                and w.words[i + k - length - 1] == rev[s + length]
            ):
                length += 1
            score = length - (1 if s else 0)
            j = min(j, len(w.words))
            out[j] = max(out.get(j, 0), score)
    return out


_KEY_ROW = re.compile(r"[ \t]*[A-Da-d][ \t]*[.)]?[ \t]*(?:$|\d)", re.M)


def _line_numbers(text: str, number: int) -> list[tuple[int, int]]:
    """``(offset, end of the number)`` of each line that starts with question ``number`` ("17.",
    "Câu 17:", "Question 17"), leaving out answer-key rows ("17. B", "17. B  18. C")."""
    pattern = re.compile(
        rf"^[ \t]*(?:(?:question|câu|cau|q)[ \t]*)?{number}(?!\d)[ \t]*[.):]?", re.I | re.M
    )
    return [
        (m.start(), m.end()) for m in pattern.finditer(text) if not _KEY_ROW.match(text, m.end())
    ]


def _number_before(text: str, number: int, offset: int) -> int:
    """The offset of question ``number`` printed just before ``offset`` (a stem's first word),
    with only a blank between them, or -1."""
    head = text[max(0, offset - 40) : offset]
    m = re.search(
        rf"(?<![\w.])(?:(?:question|câu|cau|q)[ \t]*)?{number}[ \t]*[.):]?[ \t_….]*$", head, re.I
    )
    return offset - len(head) + m.start() if m else -1


@dataclass
class _Event:
    """One thing placed in the text: a group's start or end, or a question; ``where`` maps each
    candidate offset to its score."""

    kind: Literal["start", "end", "question"]
    where: dict[int, float] = field(default_factory=dict)

    def add(self, offset: int, score: float) -> None:
        if score > self.where.get(offset, 0.0):
            self.where[offset] = score


def _question_event(text: str, w: _Words, q: TranscribedQuestion) -> _Event:
    """A question's candidates. With a stem: each place its first words appear (stronger the
    longer the match), stronger when its number is printed just before; with none: each of its
    markers. A line starting with its number is a weak candidate either way."""
    ev = _Event("question")
    n = q.printed_number
    tokens = _tokens(q.stem)
    for i, length in _starts_of(w, tokens).items():
        at = w.starts[i]
        before = _number_before(text, n, at)
        if before >= 0:
            ev.add(before, 5.0 + min(length, 10))
        else:
            ev.add(at, 2.0 + min(length, 10))
    if not tokens:
        for m in _marker_pattern(n).finditer(text):
            score = 6.0 if (m.group("br") or m.group("gl")) else 3.0
            if _BLANK_NEAR.match(text[m.end() : m.end() + 4].lstrip(" \t")):
                score += 1.0
            ev.add(m.start(), score)
    first_option = _tokens(q.options[0].text)[:3] if q.options else []
    for at, end in _line_numbers(text, n):
        score = 1.0
        if not tokens and first_option:
            rest = text[end : text.find("\n", end) if "\n" in text[end:] else len(text)]
            if " ".join(first_option) in " ".join(_tokens(rest)):
                score += 2.0
        ev.add(at, score)
    return ev


def _align(events: list[_Event]) -> list[int | None]:
    """One candidate per event, or none, so that the chosen offsets never go back in event order
    (a question strictly after the question before it) and the total score is the largest. Ties go
    to the earlier offset (a group's start: the later one)."""
    nodes: list[tuple[int, int, float, bool]] = []
    first_of: list[int] = []
    for e, ev in enumerate(events):
        first_of.append(len(nodes))
        for at, score in sorted(ev.where.items()):
            tie = 1e-9 * at if ev.kind == "start" else -1e-9 * at
            nodes.append((e, at, score + tie, ev.kind == "question"))
    best = [0.0] * len(nodes)
    back = [-1] * len(nodes)
    for i, (e, at, score, is_q) in enumerate(nodes):
        top, arg = 0.0, -1
        for j in range(first_of[e]):
            _, at_j, _, is_q_j = nodes[j]
            if (at_j < at if is_q and is_q_j else at_j <= at) and best[j] > top:
                top, arg = best[j], j
        best[i] = score + top
        back[i] = arg
    chosen: list[int | None] = [None] * len(events)
    i = max(range(len(nodes)), key=lambda k: best[k], default=-1)
    if i >= 0 and best[i] <= 0:
        i = -1
    while i >= 0:
        chosen[nodes[i][0]] = nodes[i][1]
        i = back[i]
    return chosen


def locate_pages(
    piece: TextPiece, sections: list[TranscribedSection]
) -> tuple[list[int], list[int]]:
    """``(group pages, question pages)``: the page index of each group and each question of a
    piece's structure, flat in document order (D12).

    Texts are matched folded (:func:`_fold`), word by word (punctuation does not count). Every
    group start (its stimulus's first words), group end (its last words) and question gets its
    candidate places with a score: a stem's first words (stronger the longer the match, stronger
    again with its number printed just before it, also mid-line), a stem-less question's marker
    (:func:`_marker_pattern`), and, weakly, a line starting with the question's number (never an
    answer-key row "17. B"). A group's end comes after its last stem-less question and before its
    other questions, so a marker lies inside its passage and a reading question after it. One
    candidate per item, or none, is then chosen for the whole piece at once (:func:`_align`):
    places never go back in document order and the total score is the largest, so one wrong
    match cannot drag the questions after it. A question left without a place takes the place of
    the nearest placed question before it in its group, else its group's start, else the
    previous placed question. It gets the page its text starts on. A group with pictures goes to
    the first page of its span (its start to its last question) with a picture printed on it,
    else to the page where its stimulus or first question starts.
    """
    text = piece.text
    w = _Words(text)
    events: list[_Event] = []
    layout: list[
        tuple[TranscribedGroup, int | None, list[int]]
    ] = []  # start event, question events
    for sec in sections:
        for group in sec.groups:
            tokens = _tokens(group.stimulus)
            start_ev: int | None = None
            q_events: list[int] = []
            end_after = -1
            if tokens:
                start_ev = len(events)
                ev = _Event("start")
                for i, length in _starts_of(w, tokens).items():
                    ev.add(w.starts[i], 1.0 + min(length, 12))
                events.append(ev)
                stemless = [k for k, q in enumerate(group.questions) if not _tokens(q.stem)]
                end_after = stemless[-1] if stemless else -1
            end_ev = _Event("end")
            if tokens:
                for j, length in _ends_of(w, tokens).items():
                    end_ev.add(w.after(j), 1.0 + min(length, 12))
                if end_after < 0:
                    events.append(end_ev)
            for k, q in enumerate(group.questions):
                q_events.append(len(events))
                events.append(_question_event(text, w, q))
                if tokens and k == end_after:
                    events.append(end_ev)
            layout.append((group, start_ev, q_events))
    chosen = _align(events)

    group_pages: list[int] = []
    question_pages: list[int] = []
    previous = 0
    for group, start_ev, q_events in layout:
        g_at = chosen[start_ev] if start_ev is not None else None
        q_offsets: list[int] = []
        for e in q_events:
            at = chosen[e]
            if at is None:
                at = q_offsets[-1] if q_offsets else (g_at if g_at is not None else previous)
            q_offsets.append(at)
            previous = at
            question_pages.append(piece.page_at(at))
        start = g_at if g_at is not None else (q_offsets[0] if q_offsets else previous)
        page = piece.page_at(start)
        if group.pictures:
            last = piece.page_at(q_offsets[-1]) if q_offsets else page
            span = [i for _, i in piece.page_starts if page <= i <= last]
            page = next((i for i in span if i in piece.picture_pages), page)
        group_pages.append(page)
    return group_pages, question_pages
