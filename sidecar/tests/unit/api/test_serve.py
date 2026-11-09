"""R12.3 (first part) and R12.2 (bind): ``etach serve --replay tests/cassettes/s1`` prints
``{"port", "token"}`` as its first stdout line, listens on 127.0.0.1 and shuts down on Ctrl+Break.
The extract run over SSE is in ``test_sse.py`` (same wiring, in-process)."""

from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import httpx
import pytest

from etach.cli import main


def _first_line(proc: subprocess.Popen[str], timeout: float) -> str:
    out: queue.Queue[str] = queue.Queue()
    assert proc.stdout is not None
    stdout = proc.stdout
    threading.Thread(target=lambda: out.put(stdout.readline()), daemon=True).start()
    return out.get(timeout=timeout)


def test_r12_3_serve_prints_port_and_token(tmp_path: Path, api: Any) -> None:
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [sys.executable, "-m", "etach", "serve", "--replay", str(api.S1), "--data", str(tmp_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=flags,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    try:
        line = _first_line(proc, 60)
        info = json.loads(line)
        assert set(info) == {"port", "token"}
        assert isinstance(info["port"], int) and info["port"] > 0
        assert isinstance(info["token"], str) and len(info["token"]) >= 32
        base = f"http://127.0.0.1:{info['port']}"
        with httpx.Client(base_url=base, timeout=10) as client:
            assert client.get("/events", params={"token": "wrong"}).status_code == 401
            with client.stream("GET", "/events", params={"token": info["token"]}) as r:
                assert r.status_code == 200
                assert next(r.iter_lines()).startswith(": connected")
        assert (tmp_path / "app.db").is_file()
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.send_signal(signal.SIGINT)
        assert proc.wait(timeout=30) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_openapi_export_is_deterministic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "openapi.json"
    assert main(["openapi", "export", "--out", str(out)]) == 0
    first = out.read_bytes()
    assert main(["openapi", "export", "--out", str(out)]) == 0
    assert out.read_bytes() == first
    assert first.endswith(b"}\n") and b"\r\n" not in first
    doc = json.loads(first)
    assert "/events" in doc["paths"]
    assert json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n" == first.decode()
    assert "unchanged" in capsys.readouterr().out
