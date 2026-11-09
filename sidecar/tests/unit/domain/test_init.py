"""`etach schema export`: complete, deterministic regeneration of sidecar/schema/."""

from __future__ import annotations

from pathlib import Path

from etach.cli import main
from etach.domain import DATA_MODEL_CLASSES, LLM_SCHEMAS, export_schemas, render_schemas


def test_render_covers_every_class_once() -> None:
    names = sorted(render_schemas())
    assert names == sorted(f"{c.__name__}.json" for c in (*DATA_MODEL_CLASSES, *LLM_SCHEMAS))
    assert len(names) == 39


def test_render_is_deterministic_text() -> None:
    first, second = render_schemas(), render_schemas()
    assert first == second
    for text in first.values():
        assert text.endswith("}\n") and "\r" not in text and not text.endswith("\n\n")


def test_export_replaces_stale_files_and_keeps_openapi(tmp_path: Path) -> None:
    (tmp_path / "Stale.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "openapi.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "Student.json").write_text("old\r\n", encoding="utf-8")
    written = export_schemas(tmp_path)
    assert not (tmp_path / "Stale.json").exists()
    assert (tmp_path / "openapi.json").read_text(encoding="utf-8") == "{}\n"
    rendered = render_schemas()
    for name in written:
        assert (tmp_path / name).read_bytes() == rendered[name].encode("utf-8")


def test_export_leaves_crlf_checkouts_alone(tmp_path: Path) -> None:
    rendered = render_schemas()
    crlf = rendered["Student.json"].replace("\n", "\r\n").encode("utf-8")
    (tmp_path / "Student.json").write_bytes(crlf)
    export_schemas(tmp_path)
    assert (tmp_path / "Student.json").read_bytes() == crlf


def test_cli_schema_export(tmp_path: Path) -> None:
    assert main(["schema", "export", "--out", str(tmp_path)]) == 0
    assert len(list(tmp_path.glob("*.json"))) == 39


def test_committed_schema_folder_is_current() -> None:
    schema_dir = Path(__file__).resolve().parents[3] / "schema"
    rendered = render_schemas()
    on_disk = {p.name for p in schema_dir.glob("*.json")} - {"openapi.json"}
    assert on_disk == set(rendered)
    for name, text in rendered.items():
        disk = (schema_dir / name).read_bytes().replace(b"\r\n", b"\n")
        assert disk == text.encode("utf-8"), name
