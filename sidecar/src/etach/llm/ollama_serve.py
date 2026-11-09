"""A private ``ollama serve`` for CLI runs (``etach run --spawn-ollama``).

It starts on a free ``127.0.0.1`` port with the phase-0 settings (flash attention, q8_0 KV cache,
one loaded model, no pruning of the shared models folder), waits until ``/api/version`` answers,
and is stopped (models unloaded, the process tree killed) when the ``with`` block ends, even on
an error.

- The executable: ``ETACH_OLLAMA_EXE``, else ``%LOCALAPPDATA%\\Programs\\Ollama\\ollama.exe``.
- The models: ``ETACH_OLLAMA_MODELS``, else the user's ``OLLAMA_MODELS``, else
  ``%USERPROFILE%\\.ollama\\models`` (nothing is downloaded again).
- The server log goes to ``log_dir`` (the CLI passes the data folder).
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

__all__ = [
    "SERVE_ENV",
    "OllamaServeError",
    "PrivateOllama",
    "free_port",
    "models_dir",
    "ollama_exe",
]

#: The phase-0 server settings (the FA + q8_0 configuration that phase 0 chose).
SERVE_ENV: dict[str, str] = {
    "OLLAMA_MAX_LOADED_MODELS": "1",
    "OLLAMA_NUM_PARALLEL": "1",
    "OLLAMA_FLASH_ATTENTION": "1",
    "OLLAMA_KV_CACHE_TYPE": "q8_0",
    "OLLAMA_NOPRUNE": "1",
}


class OllamaServeError(RuntimeError):
    pass


def ollama_exe() -> Path:
    default = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return Path(os.environ.get("ETACH_OLLAMA_EXE") or default)


def models_dir() -> Path:
    configured = os.environ.get("ETACH_OLLAMA_MODELS") or os.environ.get("OLLAMA_MODELS")
    return Path(configured) if configured else Path.home() / ".ollama" / "models"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@dataclass
class PrivateOllama:
    """``ollama serve`` on a free port with :data:`SERVE_ENV` on top of the environment."""

    log_dir: Path
    exe: Path = field(default_factory=ollama_exe)
    env: dict[str, str] = field(default_factory=lambda: dict(SERVE_ENV))
    port: int = 0
    proc: subprocess.Popen[bytes] | None = None
    log_path: Path | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def server_env(self) -> dict[str, str]:
        return {
            **self.env,
            "OLLAMA_HOST": f"127.0.0.1:{self.port}",
            "OLLAMA_MODELS": str(models_dir()),
        }

    def start(self, timeout: float = 60.0) -> PrivateOllama:
        if not self.exe.is_file():
            raise OllamaServeError(f"Ollama not found at {self.exe} (set ETACH_OLLAMA_EXE)")
        self.port = free_port()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / "ollama-serve.log"
        env = {**os.environ, **self.server_env}
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with self.log_path.open("wb") as log:
            self.proc = subprocess.Popen(
                [str(self.exe), "serve"],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=flags,
            )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                code = self.proc.returncode
                self.proc = None
                raise OllamaServeError(f"ollama serve exited ({code}); see {self.log_path}")
            try:
                httpx.get(self.base_url + "/api/version", timeout=5.0).raise_for_status()
                return self
            except httpx.HTTPError:
                time.sleep(0.5)
        self.stop()
        raise OllamaServeError(
            f"ollama serve did not answer in {timeout:.0f} s; see {self.log_path}"
        )

    def _unload_all(self) -> None:
        loaded: Any = httpx.get(self.base_url + "/api/ps", timeout=10.0).json()
        for m in loaded.get("models") or []:
            name = m.get("name") or m.get("model")
            if name:
                httpx.post(
                    self.base_url + "/api/generate",
                    json={"model": name, "keep_alive": 0},
                    timeout=20.0,
                )

    def stop(self) -> None:
        """Unload the models, then end the server and its runner processes."""
        if self.proc is None:
            return
        if self.proc.poll() is None:
            with contextlib.suppress(httpx.HTTPError, ValueError):
                self._unload_all()
            if sys.platform == "win32":
                # /T also ends the runner children that hold the VRAM
                subprocess.run(
                    ["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                self.proc.terminate()
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def __enter__(self) -> PrivateOllama:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()
