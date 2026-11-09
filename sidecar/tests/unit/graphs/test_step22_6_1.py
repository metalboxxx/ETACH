"""Step 22.6.1: on the photo path the answer boxes go before ``structure_text_page`` (R22.6.1.2),
and only the photo call gets the photo rules; the typed prompt renders as before (R22.6.1.3).
Synthetic data only."""

from __future__ import annotations

import json
import shutil
from importlib import resources
from pathlib import Path

import pytest
from unit.graphs.test_extract import HEADER, Harness, answers_all, page_out
from unit.graphs.test_extract import data as data
from unit.graphs.test_extract import hocr as hocr

from etach.llm.tasks import TASKS, extraction_inputs
from etach.prompts.render import FilePromptProvider

BOX = "Phàn trả lối: Thí sinh chỉ ghi A, B, C, hoặc D vào ô trả lời\n1. ____ 2. ____"
RULE = "Leave out answer boxes"
EMPTY_STEM = "never repeat the options"


@pytest.mark.asyncio
async def test_r22_6_1_2_photo_text_loses_its_answer_box(hocr: Harness) -> None:
    h = hocr
    h.save_mode = "stub"
    h.fake.queues = {
        "PlainText": [f"1. A. cat B. hat C. map D. late\n{BOX}\nII. SIGNS-MARK"],
        "TranscribeOut": [page_out(1, header=HEADER)],
        "ReadAnswersCall": [answers_all("B")],
    }
    await h.run(h.photos(1))
    (body,) = [b for t, b in h.fake.seen if t == "TranscribeOut"]
    system = next(m["content"] for m in body["messages"] if m["role"] == "system")
    user = body["messages"][-1]["content"]
    assert user.endswith("1. A. cat B. hat C. map D. late\nII. SIGNS-MARK")
    assert "Phàn trả lối" not in user and "1. ____ 2. ____" not in user
    # the photo rules are in the system prompt
    assert RULE in system and EMPTY_STEM in system
    assert "Phàn trả lối" not in json.dumps(body, ensure_ascii=False)


def _render(root: Path | None, *, photo: bool) -> tuple[str, str]:
    spec = TASKS["structure_text_page"]
    inputs = extraction_inputs(
        "structure_text_page", page_no=1, photo_count=2, document="TYPED TEXT", photo=photo
    )
    provider = FilePromptProvider(root) if root is not None else FilePromptProvider()
    prompt = provider.render("structure_text_page", spec.profile(None), inputs)
    return prompt.system, prompt.hash


def test_r22_6_1_3_only_the_photo_call_gets_the_rules() -> None:
    photo, _ = _render(None, photo=True)
    typed, _ = _render(None, photo=False)
    assert RULE in photo and EMPTY_STEM in photo and '"stem":null' in photo
    assert RULE not in typed and EMPTY_STEM not in typed
    assert "{{" not in photo and "<!-- example" not in photo


def test_r22_6_1_3_typed_prompt_renders_as_before(tmp_path: Path) -> None:
    """The typed prompt equals the one rendered from the file without the placeholder."""
    root = tmp_path / "prompts"
    source = resources.files("etach.prompts")
    for folder in ("base", "profiles", "examples"):
        shutil.copytree(str(source.joinpath(folder)), root / folder)
    base = root / "base" / "structure_text_page.md"
    text = base.read_text(encoding="utf-8")
    assert text.count("{{photo_rules}}") == 1
    base.write_text(text.replace("{{photo_rules}}", ""), encoding="utf-8")
    old_system, old_hash = _render(root, photo=False)
    system, digest = _render(None, photo=False)
    assert (system, digest) == (old_system, old_hash)
