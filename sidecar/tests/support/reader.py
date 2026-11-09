"""Pin a data folder to the vision photo reader (plan R22.5.7.7).

Since R22.5.7.7 an empty data folder reads test photos with the ``ocr`` role (GLM-OCR) and
``structure_text_page``. The photo cassettes recorded before that hold ``transcribe_page`` calls
on the vision role, so their replays run with ``[extract] photo_reader = "vision"`` in the data
folder's ``models.toml`` (the path they were recorded with) instead of being re-recorded.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["vision_reader"]

_LINE = 'photo_reader = "vision"'


def vision_reader(data: Path | str) -> Path:
    """Add ``[extract] photo_reader = "vision"`` to ``data/models.toml`` (created if missing;
    other settings kept; a file that already sets ``photo_reader`` is left alone)."""
    folder = Path(data)
    folder.mkdir(parents=True, exist_ok=True)
    toml = folder / "models.toml"
    text = toml.read_text(encoding="utf-8") if toml.is_file() else ""
    if "photo_reader" in text:
        return folder
    lines = text.splitlines()
    if "[extract]" in lines:
        lines.insert(lines.index("[extract]") + 1, _LINE)
    else:
        lines += ["[extract]", _LINE]
    toml.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return folder
