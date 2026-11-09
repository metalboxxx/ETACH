"""R22.2.5.3: the sidecar's version is a built-in constant equal to ``pyproject.toml``;
``etach --version`` and ``GET /system/status`` (test_routes_c R12.7) give it; stale installed
metadata (an ``etach-0.1.0.dist-info`` beside the frozen sidecar) does not change it."""

from __future__ import annotations

import importlib
import importlib.metadata
import tomllib
from pathlib import Path

import pytest

import etach
from etach import cli

PYPROJECT = Path(__file__).parents[2] / "pyproject.toml"


def test_constant_equals_pyproject() -> None:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    assert etach.__version__ == project["version"]


def test_etach_version_prints_the_constant(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as done:
        cli.main(["--version"])
    assert done.value.code == 0
    assert capsys.readouterr().out.strip() == etach.__version__


def test_stale_dist_info_does_not_change_the_version(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = etach.__version__
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "0.1.0")
    try:
        assert importlib.reload(etach).__version__ == expected
    finally:
        importlib.reload(etach)
