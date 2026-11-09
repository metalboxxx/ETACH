"""Built-in model configuration: the ONLY file that names model tags (plan S4).

``etach.llm.config`` uses these values when ``<data>/models.toml`` is missing, and for every key
the file leaves out. The shape follows llm-design §3.1.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ADAPTER_BY_TAG",
    "DEFAULT_CLIENT",
    "DEFAULT_EXTRACT",
    "DEFAULT_OLLAMA_URL",
    "DEFAULT_ROLES",
    "MIN_OLLAMA_VERSION",
    "SUGGESTED_TAGS",
    "adapter_for_tag",
]

#: The port a separately installed Ollama listens on (the app's own Ollama uses a random port).
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"

#: The oldest Ollama with ``logprobs`` on ``/api/chat`` (llm-design §3.2).
MIN_OLLAMA_VERSION = (0, 12, 11)

_OPTIONS: dict[str, Any] = {"num_ctx": 16384, "temperature": 0, "seed": 42}

DEFAULT_ROLES: dict[str, dict[str, Any]] = {
    "vision": {
        # D4 (step22.3-plan, teacher 2026-10-17): qwen3.5:4b read the image tests much better
        # than NuExtract (comment 13); before that, the M1 decision (m1-report.md §4).
        "model": "qwen3.5:4b",
        "adapter": "chat",
        "options": dict(_OPTIONS),
        "think": False,
        "adapter_options": {},
    },
    "reasoning": {
        # M2 decision (docs/initial-plan/phases-testing/m2-report.md §4, 2026-10-12)
        "model": "qwen3.5:4b",
        "adapter": "chat",
        "options": dict(_OPTIONS),
        "think": False,  # no grading task thinks (llm-design v4.17)
        "adapter_options": {},
    },
    # step 22.5.4 (plan-grading-quality, the teacher 2026-10-23): a separate role for checking,
    # so another model can check later without code changes
    "grading_check": {  # verify_key
        "model": "qwen3.5:4b",
        "adapter": "chat",
        "options": dict(_OPTIONS),
        "think": False,
        "adapter_options": {},
    },
    "extraction_check": {  # reread_pieces: the targeted re-read (step 22.5.7)
        "model": "qwen3.5:4b",
        "adapter": "chat",
        "options": dict(_OPTIONS),
        "think": False,
        "adapter_options": {},
    },
    # step 22.5.7 (D13; G4, the teacher 2026-10-26): GLM-OCR 0.9B (Z.ai) reads test photos as
    # plain text (``ocr_page``, ``[extract] photo_reader = "ocr"``, the default). A default role
    # since R22.5.7.7, listed, checked and offered for download like the others, unless
    # models.toml sets photo_reader = "vision" and names no [roles.ocr] (config.py).
    "ocr": {
        "model": "glm-ocr",
        "adapter": "chat",
        "options": dict(_OPTIONS),
        "think": False,
        "adapter_options": {},
    },
}

#: The adapter settings a role gets from its model tag when ``models.toml`` names the model but
#: not the adapter (step 22.3.5): an older ``models.toml`` that names NuExtract keeps working
#: with the NuExtract adapter now that the default vision adapter is ``chat``. Prefix match on
#: the lower-cased tag; any other tag uses ``chat``.
ADAPTER_BY_TAG: dict[str, dict[str, Any]] = {
    "numind/nuextract": {
        "adapter": "nuextract",
        "think": False,  # NuMind recommends thinking off (repetition loops)
        "adapter_options": {"also_format": True},  # Phase 0 item 2
    },
}
_CHAT_ADAPTER: dict[str, Any] = {"adapter": "chat", "adapter_options": {}}


def adapter_for_tag(tag: str) -> dict[str, Any]:
    """The adapter settings for a model tag (:data:`ADAPTER_BY_TAG`, else ``chat``)."""
    name = tag.strip().lower()
    for prefix, settings in ADAPTER_BY_TAG.items():
        if name.startswith(prefix):
            return dict(settings)
    return dict(_CHAT_ADAPTER)


#: Tags the model manager offers to download (step 22.3.5): the current defaults first.
SUGGESTED_TAGS: tuple[str, ...] = ("qwen3.5:4b", "glm-ocr", "numind/nuextract3:Q6_K")

#: ``[extract]``: extraction switches (M1 speed bundle 1, 2026-10-10; M1 decision tiles=off,
#: docs/initial-plan/phases-testing/m1-report.md §4).
#: ``retranscribe_tiles``: re-read a page that fails validation as two half-page tiles (llm-design
#: §4). Off by default: the M1 baseline2 run measured the tiles at 26% of extraction time for a
#: worse CER, so a failing page goes straight to ``validator_failed``. Turn it on in
#: ``models.toml`` (or with ``etach eval --tiles``) to compare.
#: ``retranscribe_tiles_keep`` (when the tiles run): ``"better"`` keeps the tile reading only
#: if it reduces that page's validator failures; ``"always"`` is the old rule (the tiles always
#: replace the first pass), kept for the recordings made with it.
#: ``reread_pieces`` (step 22.5.7): a page that fails a check gets one ``extraction_check`` call
#: for only its failing or missing questions, patched into the page. Off by default until G4
#: measures it (one more vision call per failing page).
#: ``photo_reader`` (step 22.5.7, D13): ``"ocr"`` (the ``ocr`` role reads the photo as plain
#: text, then ``structure_text_page`` structures it; the default since G4, R22.5.7.7) or
#: ``"vision"`` (one ``transcribe_page`` call on the vision role, the path before 0.6.0).
#: ``ocr_prompt``: GLM-OCR's own text-recognition prompt.
#: ``photo_structure`` (step 22.6.5, D7; OCR reader only): ``"code"`` (the layout rules of
#: :mod:`etach.domain.ocr_structure`, way 2b, no model call; the default since step 22.6.6 (c),
#: step22.6-plan D16), ``"qwen"`` (``structure_text_page`` on the OCR text, way 1, the default
#: before) or ``"ocr_format"`` (way 2a: GLM-OCR prompted with the test-text format,
#: ``ocr_format_page``, read by ``test_text.read_ocr_page``; ``ocr_prompt`` unused).
#: ``blank_share`` (step 22.6.2, the teacher's 20%): a paper with fewer of its answers read with
#: confidence is blank (``boxes.BLANK_SHARE``); 0 keeps the rule before 22.6.2 (replays of
#: recordings made with it).
DEFAULT_EXTRACT: dict[str, Any] = {
    "retranscribe_tiles": False,
    "retranscribe_tiles_keep": "better",
    "reread_pieces": False,
    "photo_reader": "ocr",
    "ocr_prompt": "Text Recognition:",
    "photo_structure": "code",
    "blank_share": 0.2,
}

#: ``[client]``: the client's retry rules (speed bundle 1, 2026-10-10).
#: ``retry_capped_output``, per role: also retry an invalid output that stopped at ``num_predict``.
#: Off: such a call fails at once as ``output_capped`` (at temperature 0 the retry mostly repeats
#: the cut). Off for extraction (vision); on for grading (reasoning) until M2 reworks
#: ``verify_key``: in the s1-grade recording the retry, which carries the error, rescued 3 calls.
#: ``grading_check`` (``verify_key`` since step 22.5.4) keeps that rule; ``extraction_check``
#: follows extraction.
DEFAULT_CLIENT: dict[str, Any] = {
    "retry_capped_output": {
        "vision": False,
        "reasoning": True,
        "grading_check": True,
        "extraction_check": False,
        "ocr": False,
    }
}
