"""Fixtures for the phase-0 live checks (`LIVE`, plan step 5).

- ``server``: our own ``ollama serve`` (session) with the app's settings (PRD §11). If the Ollama
  executable is missing, every live test is skipped with a message.
- ``require_role``: the model tag of a role, or a skip that names the ``ollama pull`` to run.
- ``recorder``: the step 4 cassette recorder into ``tests/cassettes/phase0/`` when
  ``ETACH_PHASE0_RECORD=1`` (items 1 and 3 only).
- ``workspace``: a temp data folder (database, file store with the synthetic page, one step).
- The pytest outcome of each live test goes to ``_out/pytest-summary.json`` for
  ``render_output.py``. Nothing is written when no live test ran (``TEST`` deselects them).
"""

from __future__ import annotations

import json
import platform
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from live.phase0 import (
    BASELINE_ENV,
    CASSETTE_DIR,
    SUMMARY_PATH,
    CapturingBackend,
    Client,
    MakeClient,
    Phase0Prompts,
    PrivateOllama,
    RequireRole,
    Results,
    ServerError,
    Workspace,
    make_page_png,
    models_dir,
    now_iso,
    nvidia_smi,
    ollama_exe,
    other_ollama_on_default_port,
    record_enabled,
)

from etach.appdir import DataPaths
from etach.domain import models as m
from etach.llm.cassettes import CassetteRecorder, iter_cassette_files
from etach.llm.client import OllamaClient
from etach.llm.config import ModelsConfig, default_config, parse_models_config
from etach.store import db
from etach.store.files import FileStore
from etach.store.repos import runs, threads

# --- the server and the models ------------------------------------------------------------


@pytest.fixture(scope="session")
def results() -> Results:
    res = Results()
    res.reset(
        {
            "started_at": now_iso(),
            "ollama_exe": str(ollama_exe()),
            "models_dir": str(models_dir()),
            "record": record_enabled(),
            "cassette_dir": str(CASSETTE_DIR),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "gpu_before": nvidia_smi(),
            "other_ollama_11434_loaded": other_ollama_on_default_port(),
        }
    )
    return res


@pytest.fixture(scope="session")
def config() -> ModelsConfig:
    return default_config()


@pytest.fixture(scope="session")
def server(results: Results, config: ModelsConfig) -> Iterator[PrivateOllama]:
    exe = ollama_exe()
    if not exe.is_file():
        pytest.skip(f"Ollama not found at {exe}: install it or set ETACH_OLLAMA_EXE")
    srv = PrivateOllama("baseline", dict(BASELINE_ENV))
    try:
        srv.start()
    except ServerError as exc:
        pytest.fail(f"could not start the private ollama serve: {exc}")
    results.update_meta(
        ollama_version=srv.version(),
        server_env=srv.server_env,
        server_log=str(srv.log_path),
        roles={
            name: {
                "model": role.model,
                "adapter": role.adapter,
                "options": role.options,
                "present": srv.has_model(role.model),
            }
            for name, role in config.roles.items()
        },
    )
    yield srv
    srv.stop()


def pull_hint(tag: str) -> str:
    return f'& "$env:LOCALAPPDATA\\Programs\\Ollama\\ollama.exe" pull {tag}'


@pytest.fixture
def require_role(server: PrivateOllama, config: ModelsConfig) -> RequireRole:
    """``require_role("vision")`` → the model tag, or skip when it is not pulled."""

    def require(role: str) -> str:
        tag = config.role(role).model
        if not server.has_model(tag):
            pytest.skip(f"the {role} model {tag} is not pulled; run: {pull_hint(tag)}")
        return tag

    return require


@pytest.fixture(scope="session")
def recorder() -> CassetteRecorder | None:
    """The cassette recorder for items 1 and 3, when ``ETACH_PHASE0_RECORD=1``."""
    if not record_enabled():
        return None
    existing = iter_cassette_files(CASSETTE_DIR)
    if existing:
        pytest.exit(
            f"{CASSETTE_DIR} already holds {len(existing)} cassettes. Delete the folder before"
            " recording again (or set ETACH_PHASE0_RECORD=0).",
            returncode=4,
        )
    return CassetteRecorder(CASSETTE_DIR)


# --- the workspace and the client ---------------------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> Iterator[Workspace]:
    paths = DataPaths(tmp_path / "data").ensure()
    conn = db.open_database(paths.db)
    store = FileStore(conn, paths)
    page_id = store.put(make_page_png(), "png")
    thread = threads.create_thread(conn, "photos")
    run = runs.create_run(
        conn,
        thread.id,
        "extract",
        m.ExtractInput(pages=[], existing_test_id=None, supersedes_attempt_id=None),
    )
    step_id = runs.insert_step(conn, run.id, "transcribe_page", "phase 0", 1).id
    yield Workspace(conn, store, page_id, step_id)
    conn.close()


@pytest.fixture
def make_client(
    server: PrivateOllama, workspace: Workspace, recorder: CassetteRecorder | None
) -> MakeClient:
    """``make_client(also_format=…, record=…, on=<server>)``: the step 4 client on our server."""

    def make(
        *, also_format: bool = False, record: bool = False, on: PrivateOllama | None = None
    ) -> Client:
        config = parse_models_config(
            {"roles": {"vision": {"adapter_options": {"also_format": also_format}}}}
        )
        backend = CapturingBackend((on or server).base_url)
        client = OllamaClient(
            workspace.conn,
            config,
            Phase0Prompts(),
            backend=backend,
            read_image=workspace.store.read_bytes,
            recorder=recorder if record else None,
        )
        return Client(client, backend, config)

    return make


# --- the pytest summary for render_output.py ----------------------------------------------

_OUTCOMES: dict[str, dict[str, Any]] = {}


def _reason(report: pytest.TestReport) -> str | None:
    longrepr = report.longrepr
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        return str(longrepr[2]).removeprefix("Skipped: ")
    if longrepr is None:
        return None
    text = str(longrepr).strip().splitlines()
    return text[-1][:500] if text else None


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    entry = _OUTCOMES.setdefault(report.nodeid, {"nodeid": report.nodeid, "duration_s": 0.0})
    entry["duration_s"] = round(entry["duration_s"] + report.duration, 2)
    if report.when == "call" or (report.when == "setup" and not report.passed):
        outcome = report.outcome
        if report.when == "setup" and report.failed:
            outcome = "error"
        entry["outcome"] = outcome
        entry["reason"] = None if report.passed else _reason(report)
    elif report.when == "teardown" and report.failed:
        entry["outcome"] = "error"
        entry["reason"] = _reason(report)


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: pytest.Config) -> None:
    if not _OUTCOMES:
        return
    tests = list(_OUTCOMES.values())
    counts: dict[str, int] = {}
    for t in tests:
        counts[t.get("outcome", "unknown")] = counts.get(t.get("outcome", "unknown"), 0) + 1
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "finished_at": now_iso(),
        "exitstatus": int(exitstatus),
        "args": list(config.invocation_params.args),
        "counts": counts,
        "tests": tests,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", "utf-8")
    terminalreporter.write_line(
        f"phase0: {counts} -> {SUMMARY_PATH.parent}; render with"
        " `uv run python tests/live/render_output.py"
        " --out ../docs/initial-plan/phases-testing/phase0-live-output.txt`"
    )
