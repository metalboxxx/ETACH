"""Helpers for the phase-0 live checks (plan step 5, llm-design §9 Q1/Q2).

- :class:`PrivateOllama`: our own ``ollama serve`` on a free 127.0.0.1 port, the way the app runs
  it (PRD §11). It never talks to the teacher's server on 11434, except the read-only
  ``/api/ps`` of the other-Ollama detector.
- A synthetic test page drawn with Pillow (no student photos, so no student data), its text
  version, and the small output schemas the checks ask for.
- :class:`CapturingBackend`: the step 4 HTTP backend that also keeps each final chunk (load and
  eval durations), so the checks go through ``OllamaClient.call`` unchanged.
- Logprob analysis: presence, and the token(s) covering an answer value with their A-D
  ``top_logprobs``.
- :class:`Results`: ``_out/phase0-results.json``, which ``render_output.py`` turns into
  ``docs/initial-plan/phases-testing/phase0-live-output.txt``.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from collections.abc import AsyncGenerator, Callable, Mapping
from contextlib import aclosing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, ConfigDict

from etach.domain.models import LlmCall
from etach.llm.adapters import RenderedPrompt
from etach.llm.client import HttpBackend, OllamaClient
from etach.llm.config import ModelsConfig
from etach.llm.ollama_status import normalize_tag
from etach.store.files import FileStore
from etach.store.repos import runs

LIVE_DIR = Path(__file__).resolve().parent
OUT_DIR = LIVE_DIR / "_out"
RESULTS_PATH = OUT_DIR / "phase0-results.json"
SUMMARY_PATH = OUT_DIR / "pytest-summary.json"
CASSETTE_DIR = LIVE_DIR.parent / "cassettes" / "phase0"

#: The Ollama that the app would use (``ETACH_OLLAMA_EXE`` overrides it).
DEFAULT_OLLAMA_EXE = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe"


def ollama_exe() -> Path:
    return Path(os.environ.get("ETACH_OLLAMA_EXE") or DEFAULT_OLLAMA_EXE)


def models_dir() -> Path:
    """Where the teacher's models are: ``ETACH_OLLAMA_MODELS``, else the user's ``OLLAMA_MODELS``,
    else Ollama's default ``%USERPROFILE%\\.ollama\\models`` (nothing is downloaded again)."""
    configured = os.environ.get("ETACH_OLLAMA_MODELS") or os.environ.get("OLLAMA_MODELS")
    return Path(configured) if configured else Path.home() / ".ollama" / "models"


def record_enabled() -> bool:
    return os.environ.get("ETACH_PHASE0_RECORD", "0").strip().lower() in {"1", "true", "yes"}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# --- the private server -------------------------------------------------------------------

#: The app's server settings (PRD §11) with flash attention and the KV cache type made explicit,
#: so item 5 compares against a known baseline. ``OLLAMA_NOPRUNE`` keeps this server from pruning
#: blobs in the shared models folder (for example a pull still running on the teacher's server).
BASELINE_ENV: dict[str, str] = {
    "OLLAMA_MAX_LOADED_MODELS": "1",
    "OLLAMA_NUM_PARALLEL": "1",
    "OLLAMA_FLASH_ATTENTION": "0",
    "OLLAMA_KV_CACHE_TYPE": "f16",
    "OLLAMA_NOPRUNE": "1",
}
FA_Q8_ENV: dict[str, str] = {
    **BASELINE_ENV,
    "OLLAMA_FLASH_ATTENTION": "1",
    "OLLAMA_KV_CACHE_TYPE": "q8_0",
}


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class ServerError(RuntimeError):
    pass


@dataclass
class PrivateOllama:
    """``ollama serve`` on a free port with ``env`` on top of the current environment."""

    label: str
    env: dict[str, str]
    exe: Path = field(default_factory=ollama_exe)
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
            raise ServerError(f"Ollama not found at {self.exe} (set ETACH_OLLAMA_EXE)")
        self.port = free_port()
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        self.log_path = OUT_DIR / f"ollama-serve-{self.label}.log"
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
                raise ServerError(f"ollama serve exited ({code}); see {self.log_path}")
            try:
                self.get("/api/version")
                return self
            except httpx.HTTPError:
                time.sleep(0.5)
        self.stop()
        raise ServerError(f"ollama serve did not answer in {timeout:.0f} s; see {self.log_path}")

    def stop(self) -> None:
        """Unload the models, then end the server and its runner processes."""
        if self.proc is None:
            return
        if self.proc.poll() is None:
            with contextlib.suppress(httpx.HTTPError):
                self.unload_all(timeout=20.0)
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

    # --- HTTP helpers --------------------------------------------------------------------

    def get(self, path: str) -> Any:
        response = httpx.get(self.base_url + path, timeout=10.0)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, body: Mapping[str, Any], timeout: float = 60.0) -> Any:
        response = httpx.post(self.base_url + path, json=dict(body), timeout=timeout)
        response.raise_for_status()
        return response.json()

    def version(self) -> str:
        return str(self.get("/api/version").get("version", ""))

    def model_names(self) -> set[str]:
        """The pulled models, spelled as :func:`etach.llm.ollama_status.normalize_tag` does."""
        models = self.get("/api/tags").get("models") or []
        return {normalize_tag(str(m.get("name"))) for m in models}

    def has_model(self, tag: str) -> bool:
        return normalize_tag(tag) in self.model_names()

    def ps(self) -> list[dict[str, Any]]:
        return list(self.get("/api/ps").get("models") or [])

    def capabilities(self, model: str) -> list[str]:
        return list(self.post("/api/show", {"model": model}).get("capabilities") or [])

    def unload_all(self, timeout: float = 60.0) -> None:
        for loaded in self.ps():
            self.post("/api/generate", {"model": loaded["name"], "keep_alive": 0})
        deadline = time.monotonic() + timeout
        while self.ps() and time.monotonic() < deadline:
            time.sleep(0.5)

    def log_lines(self, pattern: str) -> list[str]:
        """Server log lines matching ``pattern`` (e.g. how flash attention was set up)."""
        if self.log_path is None or not self.log_path.exists():
            return []
        text = self.log_path.read_text(encoding="utf-8", errors="replace")
        rx = re.compile(pattern, re.IGNORECASE)
        return [line.strip()[:300] for line in text.splitlines() if rx.search(line)][-10:]


def other_ollama_on_default_port() -> bool | None:
    """The other-Ollama detector (read-only ``GET /api/ps`` on 11434): ``True`` if it has a model
    loaded, which would share the VRAM with our measurements."""
    try:
        response = httpx.get("http://127.0.0.1:11434/api/ps", timeout=2.0)
        response.raise_for_status()
        return bool(response.json().get("models"))
    except (httpx.HTTPError, ValueError):
        return None


def nvidia_smi() -> dict[str, Any] | None:
    """Whole-GPU memory from ``nvidia-smi`` (MiB), or ``None`` if it is not available."""
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return None
    query = "name,memory.used,memory.total,driver_version"
    out = subprocess.run(
        [exe, f"--query-gpu={query}", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0 or not out.stdout.strip():
        return None
    name, used, total, driver = (p.strip() for p in out.stdout.strip().splitlines()[0].split(","))
    return {"name": name, "used_mib": int(used), "total_mib": int(total), "driver": driver}


# --- the synthetic page -------------------------------------------------------------------

#: What the page shows; the student's answers are the expected values. The name and class are
#: made up. They are not the scrub placeholders on purpose: ``etach scrub`` then has a real name to
#: replace, and a misread placeholder ("Hoc Sinh A") cannot make it treat "A" as a given name
#: and drop the "A" alternatives from ``top_logprobs``. The runbook passes both to
#: ``etach scrub --name/--class``.
SYNTHETIC_NAME = "Lê Văn Bình"
SYNTHETIC_CLASS = "7C3"
EXPECTED: dict[str, str] = {
    "student_name": SYNTHETIC_NAME,
    "class_name": SYNTHETIC_CLASS,
    "q1": "B",
    "q2": "plays",
}
MCQ_OPTIONS = ("A. go", "B. goes", "C. going", "D. gone")

PAGE_TEXT = """ENGLISH TEST - GRADE 8 (synthetic page)
Họ và tên: Lê Văn Bình      Lớp: 7C3
I. Choose the best answer (A, B, C or D).
Question 1. She ___ to school every day.
A. go      B. goes      C. going      D. gone
[the student circled: B]
II. Give the correct form of the verb in brackets.
Question 2. My brother ____________ (play) football on Sundays.
[the student wrote in the blank: plays]
"""

#: The printed lines, for the transcription call of items 4-5.
PRINTED_LINES = [
    "ENGLISH TEST - GRADE 8 (synthetic page)",
    "I. Choose the best answer (A, B, C or D).",
    "Question 1. She ___ to school every day.",
    "A. go B. goes C. going D. gone",
    "II. Give the correct form of the verb in brackets.",
    "Question 2. My brother ____________ (play) football on Sundays.",
]


def _font(names: tuple[str, ...], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for name in names:
        path = fonts / name
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def make_page_png() -> bytes:
    """A printed MCQ + gap-fill page with a pen circle around B and a handwritten "plays"."""
    img = Image.new("RGB", (1200, 640), "white")
    d = ImageDraw.Draw(img)
    printed = _font(("arial.ttf",), 30)
    bold = _font(("arialbd.ttf", "arial.ttf"), 32)
    hand = _font(("Inkfree.ttf", "segoesc.ttf"), 40)  # Ink Free has the Vietnamese marks
    ink = (25, 45, 150)

    d.text((60, 30), "ENGLISH TEST - GRADE 8 (synthetic page)", font=bold, fill="black")
    d.text((60, 95), "Họ và tên:", font=printed, fill="black")
    d.text((230, 85), EXPECTED["student_name"], font=hand, fill=ink)
    d.text((620, 95), "Lớp:", font=printed, fill="black")
    d.text((700, 85), EXPECTED["class_name"], font=hand, fill=ink)

    d.text((60, 170), "I. Choose the best answer (A, B, C or D).", font=bold, fill="black")
    d.text((60, 230), "Question 1. She ___ to school every day.", font=printed, fill="black")
    for i, option in enumerate(MCQ_OPTIONS):
        x, y = 100 + i * 260, 290
        d.text((x, y), option, font=printed, fill="black")
        if option.startswith(EXPECTED["q1"] + "."):
            left, top, right, bottom = d.textbbox((x, y), option, font=printed)
            # two slightly offset strokes, like a pen circle
            d.ellipse((left - 22, top - 16, right + 20, bottom + 14), outline=ink, width=3)
            d.ellipse((left - 18, top - 19, right + 25, bottom + 11), outline=ink, width=2)

    d.text((60, 390), "II. Give the correct form of the verb in brackets.", font=bold, fill="black")
    prefix = "Question 2. My brother "
    d.text((60, 450), prefix, font=printed, fill="black")
    x0 = 60 + int(d.textlength(prefix, font=printed))
    d.line((x0, 482, x0 + 210, 482), fill="black", width=2)
    d.text((x0 + 230, 450), "(play) football on Sundays.", font=printed, fill="black")
    d.text((x0 + 30, 432), EXPECTED["q2"], font=hand, fill=ink)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --- schemas and prompts ------------------------------------------------------------------


class Phase0Answers(BaseModel):
    """The answers on the synthetic page (a small stand-in for ``read_answers_page``)."""

    model_config = ConfigDict(extra="forbid")
    student_name: str | None
    class_name: str | None
    q1: Literal["A", "B", "C", "D"] | None
    q2: str | None


class Phase0Transcript(BaseModel):
    """The printed lines of the page (a longer output, for the speed measurements)."""

    model_config = ConfigDict(extra="forbid")
    lines: list[str]


_PROMPTS: dict[str, tuple[str, str]] = {
    "answers": (
        "You read a student's answers on an English test page.",
        "Return the student's name and class as written, the letter the student circled for"
        " Question 1 (A, B, C or D), and the word the student wrote in the blank of Question 2."
        " Use null for a value that is not there. Answer with JSON only.",
    ),
    "transcript": (
        "You copy the printed text of an English test page exactly.",
        "Copy every printed line of the page in reading order, one list item per line."
        " Leave out the handwriting. Answer with JSON only.",
    ),
}


class Phase0Prompts:
    """A :class:`~etach.llm.adapters.PromptProvider` for the phase-0 tasks.

    Tasks named ``phase0_speed_…`` copy the printed lines (:class:`Phase0Transcript`); the others
    read the answers (:class:`Phase0Answers`). The input
    ``document`` (the page as text) is sent as the document when present.
    """

    def render(self, task: str, profile: str, inputs: Mapping[str, Any]) -> RenderedPrompt:
        kind = "transcript" if task.startswith("phase0_speed_") else "answers"
        system, user = _PROMPTS[kind]
        document = inputs.get("document")
        return RenderedPrompt.of(system, user, document if isinstance(document, str) else None)


# --- the capturing backend ----------------------------------------------------------------


class CapturingBackend(HttpBackend):
    """``HttpBackend`` that keeps the final chunk of every stream, plus wall-clock timings."""

    def __init__(self, base_url: str) -> None:
        super().__init__(base_url)
        self.finals: list[dict[str, Any]] = []

    async def stream(
        self, body: Mapping[str, Any], *, task: str, match_key: str
    ) -> AsyncGenerator[dict[str, Any]]:
        started = time.monotonic()
        first: float | None = None
        async with aclosing(super().stream(body, task=task, match_key=match_key)) as inner:
            async for chunk in inner:
                if first is None:
                    first = time.monotonic()
                if chunk.get("done"):
                    final = {k: v for k, v in chunk.items() if k not in ("message", "logprobs")}
                    final["wall_ms"] = int((time.monotonic() - started) * 1000)
                    final["first_chunk_ms"] = int((first - started) * 1000)
                    self.finals.append(final)
                yield chunk


def timing(final: Mapping[str, Any] | None) -> dict[str, Any]:
    """Load time, prompt and generation speed from a final chunk (durations are in ns)."""
    if not final:
        return {}

    def seconds(key: str) -> float | None:
        value = final.get(key)
        return round(value / 1e9, 3) if isinstance(value, int | float) and value else None

    def rate(count_key: str, duration_key: str) -> float | None:
        count, duration = final.get(count_key), final.get(duration_key)
        if isinstance(count, int) and isinstance(duration, int | float) and duration > 0:
            return round(count / (duration / 1e9), 2)
        return None

    return {
        "load_s": seconds("load_duration"),
        "total_s": seconds("total_duration"),
        "prompt_tokens": final.get("prompt_eval_count"),
        "prompt_tok_per_s": rate("prompt_eval_count", "prompt_eval_duration"),
        "eval_tokens": final.get("eval_count"),
        "eval_tok_per_s": rate("eval_count", "eval_duration"),
        "wall_s": round(final.get("wall_ms", 0) / 1000, 3),
        "done_reason": final.get("done_reason"),
    }


def vram(server: PrivateOllama, model: str) -> dict[str, Any]:
    """``/api/ps`` for ``model`` + ``nvidia-smi``: whether the model is fully on the GPU."""
    entry = next((m for m in server.ps() if m.get("name") == model), None)
    out: dict[str, Any] = {"loaded": entry is not None, "nvidia_smi": nvidia_smi()}
    if entry is not None:
        size, size_vram = int(entry.get("size") or 0), int(entry.get("size_vram") or 0)
        out |= {
            "size_mib": size // 2**20,
            "size_vram_mib": size_vram // 2**20,
            "gpu_share": round(size_vram / size, 3) if size else None,
            "fully_on_gpu": size > 0 and size_vram >= size,
            "context_length": entry.get("context_length"),
        }
    return out


# --- logprob analysis ---------------------------------------------------------------------


def logprob_presence(logprobs: list[Any] | None, final: Mapping[str, Any] | None) -> dict[str, Any]:
    """What the stream returned, and what is missing (``missing`` is empty when all is there)."""
    entries = logprobs or []
    with_top = sum(1 for e in entries if isinstance(e, dict) and e.get("top_logprobs"))
    top_sizes = sorted({len(e.get("top_logprobs") or []) for e in entries if isinstance(e, dict)})
    eval_count = (final or {}).get("eval_count")
    missing: list[str] = []
    if not entries:
        missing.append("no logprobs in the stream")
    elif with_top < len(entries):
        missing.append(f"{len(entries) - with_top} of {len(entries)} tokens have no top_logprobs")
    if entries and isinstance(eval_count, int) and eval_count != len(entries):
        missing.append(f"{len(entries)} logprob entries for eval_count {eval_count}")
    return {
        "count": len(entries),
        "with_top_logprobs": with_top,
        "top_logprobs_sizes": top_sizes,
        "eval_count": eval_count,
        "sample": [_short_entry(e) for e in entries[:3]],
        "missing": missing,
    }


def _short_entry(entry: Any) -> Any:
    if not isinstance(entry, dict):
        return entry
    return {
        "token": entry.get("token"),
        "logprob": entry.get("logprob"),
        "top": [t.get("token") for t in entry.get("top_logprobs") or []],
    }


def value_tokens(
    logprobs: list[Any] | None, response_text: str, key: str, choices: str = "ABCD"
) -> dict[str, Any]:
    """The token(s) covering the string value of ``key`` in the response JSON, and their
    ``top_logprobs`` over ``choices`` (as probabilities; alternatives that only differ by quotes
    or spaces are added up)."""
    entries = [e for e in logprobs or [] if isinstance(e, dict)]
    joined = "".join(str(e.get("token", "")) for e in entries)
    match = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]*)"', response_text)
    out: dict[str, Any] = {"found": False, "value": None}
    if match is None:
        out["note"] = f"no string value for {key!r} in the response"
        return out
    # the logprobs may also cover the thinking: the response is their tail
    base = joined.rfind(response_text) if response_text in joined else -1
    if base < 0:
        out["note"] = "the logprob tokens do not join to the response text"
        out["value"] = match.group(1)
        return out
    start, end = base + match.start(1), base + match.end(1)
    covering: list[dict[str, Any]] = []
    pos = 0
    for entry in entries:
        token = str(entry.get("token", ""))
        t_start, t_end = pos, pos + len(token)
        pos = t_end
        if t_end > start and t_start < end:
            probs: dict[str, float] = {}
            others: dict[str, float] = {}
            for alt in entry.get("top_logprobs") or []:
                text = str(alt.get("token", ""))
                p = math.exp(float(alt.get("logprob", -math.inf)))
                letter = text.strip().strip('"').strip()
                if letter in choices and len(letter) == 1:
                    probs[letter] = round(probs.get(letter, 0.0) + p, 4)
                else:
                    others[text] = round(p, 4)
            covering.append(
                {
                    "token": token,
                    "prob": round(math.exp(float(entry.get("logprob", -math.inf))), 4),
                    "choice_probs": dict(sorted(probs.items())),
                    "other_alternatives": others,
                }
            )
    out |= {
        "found": True,
        "value": match.group(1),
        "tokens": covering,
        "token_count": len(covering),
        "single_token": len(covering) == 1,
    }
    return out


# --- the per-test workspace and client (fixtures in conftest.py) ------------------------


@dataclass
class Workspace:
    """A temp data folder: the database, the file store with the page, one ``steps`` row."""

    conn: sqlite3.Connection
    store: FileStore
    page_id: str
    step_id: str

    def rows(self) -> list[LlmCall]:
        return runs.list_llm_calls(self.conn, self.step_id)


@dataclass
class Client:
    client: OllamaClient
    backend: CapturingBackend
    config: ModelsConfig


MakeClient = Callable[..., Client]
RequireRole = Callable[[str], str]


# --- results ------------------------------------------------------------------------------


class Results:
    """``_out/phase0-results.json``: ``{"meta": {...}, "records": [...]}``."""

    def __init__(self, path: Path = RESULTS_PATH) -> None:
        self.path = path

    def reset(self, meta: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write({"meta": meta, "records": []})

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"meta": {}, "records": []}
        data: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        return data

    def update_meta(self, **values: Any) -> None:
        data = self.load()
        data["meta"].update(values)
        self._write(data)

    def add(self, item: int, case: str, **fields: Any) -> dict[str, Any]:
        record = {"item": item, "case": case, "at": now_iso(), **fields}
        data = self.load()
        data["records"].append(record)
        self._write(data)
        # ASCII on screen: a cp1252 console cannot print every Vietnamese letter
        print(f"\n[phase0 item {item}] {case}: {json.dumps(record, ensure_ascii=True)[:1500]}")
        return record

    def records(self, item: int) -> list[dict[str, Any]]:
        return [r for r in self.load()["records"] if r.get("item") == item]

    def _write(self, data: dict[str, Any]) -> None:
        text = json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n"
        self.path.write_text(text, encoding="utf-8")
