"""Domain package (see docs/llm-design.md section 2) and the JSON Schema export.

``render_schemas()`` is pure; ``export_schemas()`` writes its result to ``sidecar/schema/``
(``etach schema export``, standing requirement S3).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from etach.domain import models
from etach.domain.llm_schemas import LLM_SCHEMAS

__all__ = [
    "DATA_MODEL_CLASSES",
    "DEFAULT_SCHEMA_DIR",
    "KEEP_FILES",
    "LLM_SCHEMAS",
    "export_schemas",
    "render_schemas",
]

# data-model §2.1-2.8 plus the nested helpers, in document order.
DATA_MODEL_CLASSES: tuple[type[BaseModel], ...] = (
    models.Student,
    models.Test,
    models.TestMetadata,
    models.TestContent,
    models.Section,
    models.QuestionGroup,
    models.Question,
    models.PictureRef,
    models.AnswerKey,
    models.Attempt,
    models.AttemptPage,
    models.Answer,
    models.GradeReport,
    models.Explanation,
    models.Thread,
    models.Message,
    models.PageInput,
    models.ExtractInput,
    models.GradeInput,
    models.Run,
    models.Step,
    models.LlmCall,
    models.ReviewItem,
    models.File,
    models.OmittedSection,
    models.Option,
    models.WeakPoint,
    models.TeacherQuestion,
)

# Files in the schema folder that other exports own (step 12: `etach openapi export`).
KEEP_FILES: frozenset[str] = frozenset({"openapi.json"})

# src/etach/domain/__init__.py -> sidecar/schema
DEFAULT_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schema"


def render_schemas() -> dict[str, str]:
    """``{"<ClassName>.json": text}`` for every data-model class and LLM output schema.

    The text is deterministic: pydantic's key order, ``indent=2``, ``\\n`` line ends, a final
    newline.
    """
    out: dict[str, str] = {}
    for cls in (*DATA_MODEL_CLASSES, *LLM_SCHEMAS):
        name = f"{cls.__name__}.json"
        if name in out:
            raise ValueError(f"duplicate schema name {name}")
        schema = cls.model_json_schema()
        out[name] = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    return out


def export_schemas(out_dir: Path = DEFAULT_SCHEMA_DIR) -> list[str]:
    """Regenerate ``out_dir`` completely; return the file names written.

    Stale ``*.json`` files are removed, except those in ``KEEP_FILES``.
    """
    rendered = render_schemas()
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in sorted(out_dir.glob("*.json")):
        if stale.name not in rendered and stale.name not in KEEP_FILES:
            stale.unlink()
    for name, text in rendered.items():
        path = out_dir / name
        data = text.encode("utf-8")
        # A file that differs only by CRLF (a git checkout with core.autocrlf) is left alone,
        # so `git status` stays clean; any other difference is rewritten with \n line ends.
        if not path.exists() or path.read_bytes().replace(b"\r\n", b"\n") != data:
            path.write_bytes(data)
    return sorted(rendered)
