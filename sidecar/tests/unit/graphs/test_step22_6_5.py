"""Step 22.6.5: ``[extract] photo_structure`` (R22.6.5.1) and the code way (2b) in the graph.
Synthetic data only."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from unit.graphs.test_extract import HEADER, Harness, _kinds, _state, answers_all, make_harness
from unit.graphs.test_extract import data as data
from unit.graphs.test_extract import hocr as hocr

from etach.appdir import DataPaths
from etach.llm.config import parse_models_config
from etach.store import db

PAGE = f"{HEADER}\nI. Choose the best answer. (0.5 pt)\n1. A. cat B. hat C. map D. late\n"


@pytest_asyncio.fixture
async def hcode(data: DataPaths, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Harness]:
    """The harness with ``[extract] photo_structure = "code"`` (and the default OCR reader)."""
    data.models_toml.write_text('[extract]\nphoto_structure = "code"\n', encoding="utf-8")
    async with make_harness(data, monkeypatch, ocr=None) as harness:
        yield harness


def test_r22_6_5_1_setting_default_and_values() -> None:
    # the default is code (2b) since step 22.6.6 (c), step22.6-plan D16
    assert parse_models_config({}).extract.photo_structure == "code"
    for way in ("qwen", "code", "ocr_format"):
        cfg = parse_models_config({"extract": {"photo_structure": way}})
        assert cfg.extract.photo_structure == way
    with pytest.raises(Exception):  # noqa: B017
        parse_models_config({"extract": {"photo_structure": "other"}})


@pytest.mark.asyncio
async def test_r22_6_5_1_code_makes_no_structuring_call(hcode: Harness) -> None:
    h = hcode
    h.save_mode = "stub"
    h.fake.queues = {"PlainText": [PAGE], "ReadAnswersCall": [answers_all("B")]}
    _, snap = await h.run(h.photos(1))
    s = _state(snap)
    titles = [t for t, _ in h.fake.seen]
    assert "TranscribeOut" not in titles and titles.count("PlainText") == 1
    roles = [r[0] for r in h.conn.execute("SELECT role FROM llm_calls ORDER BY rowid")]
    assert roles.count("ocr") == 1 and "reasoning" not in roles
    (section,) = s["draft"]["content"]["sections"]
    assert section["printed_title"] == "I"
    assert "validator_failed" not in _kinds(s)


@pytest.mark.asyncio
async def test_r22_6_5_2_unplaced_line_flags_the_page(hcode: Harness) -> None:
    h = hcode
    h.save_mode = "stub"
    text = f"{PAGE}A note no rule places.\n"
    h.fake.queues = {"PlainText": [text], "ReadAnswersCall": [answers_all("B")]}
    _, snap = await h.run(h.photos(1))
    s = _state(snap)
    assert _kinds(s).count("validator_failed") == 1
    pending = next(p for p in s["merge_pendings"] if p["kind"] == "validator_failed")
    assert pending["proposal"]["task"] == "ocr_structure"


@pytest.mark.asyncio
async def test_r22_6_5_1_qwen_way_unchanged(hocr: Harness) -> None:
    """``qwen`` (the default before step 22.6.6 (c)): ``ocr_page`` then
    ``structure_text_page``, as before."""
    from unit.graphs.test_extract import page_out

    h = hocr
    h.save_mode = "stub"
    h.fake.queues = {
        "PlainText": [PAGE],
        "TranscribeOut": [page_out(1, header=HEADER)],
        "ReadAnswersCall": [answers_all("B")],
    }
    await h.run(h.photos(1))
    titles = [t for t, _ in h.fake.seen]
    assert titles[:2] == ["PlainText", "TranscribeOut"]


# --- way 2a: GLM-OCR writes the test-text format (R22.6.5.4) ---------------------------------

FORMAT_PAGE = (
    f"{HEADER}\n# I. Choose the best answer.\n"
    "1. She ____ to school every day.\nA. go  B. goes  C. going  D. gone\n"
    "2. I am interested ____ music.\nA. in  B. on  C. at  D. of\n"
)


@pytest_asyncio.fixture
async def hformat(data: DataPaths, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Harness]:
    """The harness with ``[extract] photo_structure = "ocr_format"`` (the default OCR reader)."""
    data.models_toml.write_text('[extract]\nphoto_structure = "ocr_format"\n', encoding="utf-8")
    async with make_harness(data, monkeypatch, ocr=None) as harness:
        yield harness


@pytest.mark.asyncio
async def test_r22_6_5_4_ocr_format_prompt_and_no_structuring_call(hformat: Harness) -> None:
    from etach.prompts.render import FilePromptProvider

    h = hformat
    h.save_mode = "stub"
    h.fake.queues = {"PlainText": [FORMAT_PAGE], "ReadAnswersCall": [answers_all("B")]}
    _, snap = await h.run(h.photos(1))
    s = _state(snap)
    titles = [t for t, _ in h.fake.seen]
    assert "TranscribeOut" not in titles and titles.count("PlainText") == 1
    (body,) = [b for t, b in h.fake.seen if t == "PlainText"]
    assert body["model"] == "glm-ocr" and "format" not in body
    assert [m["role"] for m in body["messages"]] == ["user"]
    content = body["messages"][0]["content"]
    assert content != "Text Recognition:"
    base = FilePromptProvider().base_text("ocr_format_page")
    assert content == base.split("<!-- user -->", 1)[1].strip()
    assert "# II. Choose the best answer." in content and "Start: I wish" in content
    assert body["messages"][0]["images"]
    roles = [r[0] for r in h.conn.execute("SELECT role FROM llm_calls ORDER BY rowid")]
    assert roles.count("ocr") == 1 and "reasoning" not in roles
    (section,) = s["draft"]["content"]["sections"]
    assert section["printed_title"] == "I"
    questions = [q for g in section["groups"] for q in g["questions"]]
    assert [q["printed_number"] for q in questions] == [1, 2]
    assert [o["text"] for o in questions[0]["options"]] == ["go", "goes", "going", "gone"]
    assert "validator_failed" not in _kinds(s)


@pytest.mark.asyncio
async def test_r22_6_5_4_continuation_page_joins_the_previous_section(hformat: Harness) -> None:
    h = hformat
    h.save_mode = "stub"
    page2 = "3. They have lived here ____ 2010.\nA. for  B. since  C. in  D. at\n"
    h.fake.queues = {
        "PlainText": [FORMAT_PAGE, page2],
        "ReadAnswersCall": [answers_all("B"), answers_all("B")],
    }
    _, snap = await h.run(h.photos(2))
    s = _state(snap)
    (section,) = s["draft"]["content"]["sections"]
    questions = [q for g in section["groups"] for q in g["questions"]]
    assert [q["printed_number"] for q in questions] == [1, 2, 3]
    assert "validator_failed" not in _kinds(s)


@pytest.mark.asyncio
async def test_r22_6_5_4_unreadable_page_is_flagged_and_kept(hformat: Harness) -> None:
    h = hformat
    h.save_mode = "stub"
    page2 = "4. A question.\nA. yes  B. no\n[End of passage]\nKEPT-TEXT-MARKER\n"
    h.fake.queues = {
        "PlainText": [FORMAT_PAGE, page2],
        "ReadAnswersCall": [answers_all("B"), answers_all("B")],
    }
    _, snap = await h.run(h.photos(2))
    s = _state(snap)
    flagged = [
        p
        for p in s["merge_pendings"]
        if p["kind"] == "validator_failed" and p["refs"]["page_no"] == 2
    ]
    (pending,) = flagged
    assert "[End of passage] has no [Passage] above it" in pending["proposal"]["call_failure"]
    stimuli = [
        g["stimulus"] or "" for sec in s["draft"]["content"]["sections"] for g in sec["groups"]
    ]
    assert any("KEPT-TEXT-MARKER" in x for x in stimuli)


@pytest.mark.asyncio
async def test_r22_6_5_4_code_way_unchanged(hcode: Harness) -> None:
    """Way 2b still sends GLM-OCR's own prompt (``ocr_page``)."""
    h = hcode
    h.save_mode = "stub"
    h.fake.queues = {"PlainText": [PAGE], "ReadAnswersCall": [answers_all("B")]}
    await h.run(h.photos(1))
    (body,) = [b for t, b in h.fake.seen if t == "PlainText"]
    assert body["messages"][0]["content"] == "Text Recognition:"


# --- R22.6.6.5: the way changes only a photo read by OCR ---------------------------------------


async def _typed_and_vision_calls(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch, way: str, reader: str
) -> list[tuple[str, Any]]:
    """The model calls (title and body) of one run: a typed page, then (``reader = "vision"``)
    a photo, with ``[extract] photo_structure = way``."""
    from unit.graphs.test_extract import _text_pdf, page_out

    from etach.store.documents import ingest

    data.models_toml.write_text(
        f'[extract]\nphoto_structure = "{way}"\nphoto_reader = "{reader}"\n', encoding="utf-8"
    )
    async with make_harness(data, monkeypatch, ocr=None) as h:
        h.save_mode = "stub"
        if reader == "ocr":
            pages = ingest(h.files, _text_pdf(1), "typed.pdf")
            h.fake.queues = {"TranscribeOut": [page_out(1, header=HEADER)]}
        else:
            pages = h.photos(1)
            h.fake.queues = {
                "TranscribeOut": [page_out(1, header=HEADER)],
                "ReadAnswersCall": [answers_all("B")],
            }
        await h.run(pages)
        return list(h.fake.seen)


@pytest.mark.asyncio
@pytest.mark.parametrize("reader", ["ocr", "vision"])
@pytest.mark.parametrize("way", ["code", "ocr_format"])
async def test_r22_6_6_5_typed_and_vision_pages_ignore_the_way(
    data: DataPaths, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, way: str, reader: str
) -> None:
    """A typed page (structure_text_page on its text layer, no OCR call) and a photo read by
    the vision model (one transcribe_page call with the photo) send exactly the calls of
    ``photo_structure = "qwen"``."""
    calls = await _typed_and_vision_calls(data, monkeypatch, way, reader)
    base = DataPaths(tmp_path / "qwen")
    db.open_database(base.db).close()
    expected = await _typed_and_vision_calls(base, monkeypatch, "qwen", reader)
    titles = [t for t, _ in calls]
    assert "PlainText" not in titles and titles.count("TranscribeOut") == 1
    transcribe = next(b for t, b in calls if t == "TranscribeOut")
    has_image = any(m.get("images") for m in transcribe["messages"])
    assert has_image is (reader == "vision")
    assert calls == expected
