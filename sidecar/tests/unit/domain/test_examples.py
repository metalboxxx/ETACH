"""R1.2: every example instance in tests/unit/examples/ round-trips."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from etach.domain import DATA_MODEL_CLASSES, LLM_SCHEMAS

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
CLASSES: dict[str, type[BaseModel]] = {c.__name__: c for c in (*DATA_MODEL_CLASSES, *LLM_SCHEMAS)}
HELPERS = {
    "OmittedSection",
    "Option",
    "WeakPoint",
    "TeacherQuestion",
}
FILES = sorted(EXAMPLES.glob("*.json"))


def test_one_example_per_top_level_class_and_llm_schema() -> None:
    expected = sorted(set(CLASSES) - HELPERS)
    assert sorted(p.stem for p in FILES) == expected


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_r1_2_example_round_trips(path: Path) -> None:
    cls = CLASSES[path.stem]
    data = json.loads(path.read_text(encoding="utf-8"))
    original = cls.model_validate(data)
    assert cls.model_validate(original.model_dump()) == original
    assert cls.model_validate_json(original.model_dump_json()) == original
    assert original.model_dump(mode="json") == data


def test_examples_use_placeholder_student_names() -> None:
    text = "".join(p.read_text(encoding="utf-8") for p in FILES)
    assert "Học Sinh A" in text
    assert "Ngô Thị" not in text
