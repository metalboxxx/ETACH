"""Cassettes: recorded model calls for tests (plan §1.7, llm-design §2 "Cassettes").

One JSON file per call, ``<scenario>/<NNN>-<task>.json``::

    {"task", "match_key", "response_text", "thinking_text", "logprobs", "status",
     "meta": {"model", "prompt_hash", "recorded_at", "schema"}}

No images and no base64 are stored.

- **Match key** = ``<task>:<sha256>`` over the canonical JSON of the schema name and whichever
  of ``page_no``, ``question_ids``, ``section_id`` appear in the call's inputs. It leaves out
  the prompt hash and the model tag, so prompt tuning (M1) and model changes (M2) keep replaying.
- **Recorder**: the client hands every finished call (``complete``, ``invalid``, ``error``) to
  the active recorder. ``etach record --out <dir> -- <etach args…>`` runs a subcommand inside
  :func:`recording`.
- **Replay**: :class:`ReplayBackend` stands in for Ollama's HTTP stream inside
  ``OllamaClient``, so ``llm_calls`` rows are still written. Several cassettes with the same key
  are served in recorded order (a validation retry replays as invalid → valid); an unknown or
  used-up key raises :class:`CassetteMiss`. A cassette with status ``error`` replays as a
  dropped stream.
- **Damage check**: a ``complete`` cassette passed schema validation when it was recorded, so its
  ``response_text`` is JSON. When it no longer parses, the file was changed after recording (for
  example ``etach scrub`` replacing a number that equals a misread student name or class), and
  replaying it would take the client down its validation-retry path and end in a confusing
  "all cassettes already served". :meth:`ReplayBackend.from_dir` refuses such a folder with
  :class:`CassetteDamaged`, naming the files.
- **Scenario manifest**: ``etach record --out <dir> -- run …`` also writes ``<dir>/input.json``
  (:class:`ScenarioManifest`: the pages in order with their original file name, prepared size,
  rotation and key flag, plus the picked test; no bytes) and one blank **stand-in PNG** per page
  (:func:`write_manifest`). ``etach run --replay <dir>`` feeds the stand-ins back in.
- **Grade scenario manifest**: ``etach record --out <dir> --after <extract dir> -- grade …`` writes
  ``<dir>/grade.json`` (:class:`GradeScenario`): the extract scenario to replay first and whether
  the grade target is that replay's attempt or its (blank) test.
"""

from __future__ import annotations

import contextvars
import io
import json
import re
import threading
from collections.abc import AsyncGenerator, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
from PIL import Image, PngImagePlugin
from pydantic import BaseModel, ConfigDict, Field

from etach.llm.adapters import canonical_json, sha256_hex

__all__ = [
    "GRADE_MANIFEST_NAME",
    "MANIFEST_NAME",
    "MATCH_INPUT_KEYS",
    "Cassette",
    "CassetteDamaged",
    "CassetteMeta",
    "CassetteMiss",
    "CassetteRecorder",
    "GradeScenario",
    "ReplayBackend",
    "ScenarioManifest",
    "ScenarioPage",
    "active_recorder",
    "damaged_cassettes",
    "grade_scenario_extract_dir",
    "iter_cassette_files",
    "load_cassettes",
    "load_grade_scenario",
    "load_manifest",
    "match_key",
    "recording",
    "stand_in_png",
    "write_grade_scenario",
    "write_manifest",
    "write_stand_in",
]

MATCH_INPUT_KEYS = ("page_no", "question_ids", "section_id")

CassetteStatus = Literal["complete", "invalid", "error"]


class CassetteMiss(LookupError):
    """No (more) cassettes for a call's match key."""


class CassetteDamaged(CassetteMiss):
    """A cassette's content no longer matches its recorded status (see the module doc)."""


class CassetteMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str
    prompt_hash: str
    recorded_at: datetime
    schema_: str | None = None

    def dump(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "prompt_hash": self.prompt_hash,
            "recorded_at": self.recorded_at.astimezone(UTC).isoformat(),
            "schema": self.schema_,
        }


class Cassette(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str
    match_key: str
    response_text: str
    thinking_text: str = ""
    logprobs: list[Any] | None = None
    status: CassetteStatus = "complete"
    meta: CassetteMeta

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Cassette:
        raw = dict(data)
        meta = dict(raw.pop("meta", {}))
        if "schema" in meta:
            meta["schema_"] = meta.pop("schema")
        return cls.model_validate({**raw, "meta": meta})

    def to_json(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "match_key": self.match_key,
            "response_text": self.response_text,
            "thinking_text": self.thinking_text,
            "logprobs": self.logprobs,
            "status": self.status,
            "meta": self.meta.dump(),
        }


def match_key(task: str, schema_name: str, inputs: Mapping[str, Any]) -> str:
    """``<task>:<sha256>`` over the schema name + the matching inputs (see the module doc)."""
    key: dict[str, Any] = {"schema": schema_name}
    for name in MATCH_INPUT_KEYS:
        if name in inputs:
            value = inputs[name]
            key[name] = list(value) if isinstance(value, tuple) else value
    return f"{task}:{sha256_hex(canonical_json(key))}"


_FILE_NAME = re.compile(r"^(\d+)-.+\.json$")


def iter_cassette_files(folder: Path) -> list[Path]:
    """The ``NNN-<task>.json`` files under ``folder`` (recursively), in recorded order."""
    if not folder.is_dir():
        return []

    def order(path: Path) -> tuple[str, int, str]:
        match = _FILE_NAME.match(path.name)
        return (str(path.parent), int(match.group(1)) if match else -1, path.name)

    return sorted((p for p in folder.rglob("*.json") if _FILE_NAME.match(p.name)), key=order)


def load_cassettes(folder: Path) -> list[Cassette]:
    return [
        Cassette.from_json(json.loads(p.read_text(encoding="utf-8")))
        for p in iter_cassette_files(folder)
    ]


def _damage(cassette: Cassette) -> str | None:
    """Why a cassette cannot be what was recorded, or ``None``."""
    if cassette.status != "complete":
        return None
    try:
        json.loads(cassette.response_text)
    except json.JSONDecodeError as exc:
        return f"status complete but response_text is not JSON ({exc.msg} at char {exc.pos})"
    return None


def damaged_cassettes(folder: Path) -> list[tuple[Path, str]]:
    """``(file, reason)`` for every cassette under ``folder`` that was changed after recording
    so that it can no longer replay as recorded (see the module doc)."""
    found: list[tuple[Path, str]] = []
    for path in iter_cassette_files(Path(folder)):
        reason = _damage(Cassette.from_json(json.loads(path.read_text(encoding="utf-8"))))
        if reason is not None:
            found.append((path, reason))
    return found


# --- recording -------------------------------------------------------------------------------


class CassetteRecorder:
    """Writes each finished call as ``<out>/<NNN>-<task>.json`` (NNN continues after the files
    already there)."""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = Path(out_dir)
        self._lock = threading.Lock()
        self.written: list[Path] = []

    def _next_number(self) -> int:
        numbers = [
            int(m.group(1))
            for p in self.out_dir.glob("*.json")
            if (m := _FILE_NAME.match(p.name)) is not None
        ]
        return max(numbers, default=0) + 1

    def record(self, cassette: Cassette) -> Path:
        with self._lock:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            safe_task = re.sub(r"[^A-Za-z0-9_.-]", "_", cassette.task)
            path = self.out_dir / f"{self._next_number():03d}-{safe_task}.json"
            text = json.dumps(cassette.to_json(), ensure_ascii=False, indent=2) + "\n"
            path.write_text(text, encoding="utf-8")
            self.written.append(path)
            return path


_active: contextvars.ContextVar[CassetteRecorder | None] = contextvars.ContextVar(
    "etach_cassette_recorder", default=None
)


def active_recorder() -> CassetteRecorder | None:
    """The recorder set by :func:`recording`, if any."""
    return _active.get()


@contextmanager
def recording(out_dir: Path) -> Iterator[CassetteRecorder]:
    """Record every model call made inside the block (``etach record``)."""
    recorder = CassetteRecorder(out_dir)
    token = _active.set(recorder)
    try:
        yield recorder
    finally:
        _active.reset(token)


def new_cassette(
    *,
    task: str,
    key: str,
    response_text: str,
    thinking_text: str,
    logprobs: list[Any] | None,
    status: CassetteStatus,
    model: str,
    prompt_hash: str,
    schema_name: str,
) -> Cassette:
    return Cassette(
        task=task,
        match_key=key,
        response_text=response_text,
        thinking_text=thinking_text,
        logprobs=logprobs,
        status=status,
        meta=CassetteMeta(
            model=model,
            prompt_hash=prompt_hash,
            recorded_at=datetime.now(UTC),
            schema_=schema_name,
        ),
    )


# --- replay ----------------------------------------------------------------------------------


@dataclass
class ReplayBackend:
    """Serves cassettes by match key in place of Ollama's ``/api/chat`` stream."""

    cassettes: list[Cassette]
    served: list[Cassette] = field(default_factory=list)
    _queues: dict[str, list[Cassette]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        for cassette in self.cassettes:
            self._queues.setdefault(cassette.match_key, []).append(cassette)

    @classmethod
    def from_dir(cls, folder: Path) -> ReplayBackend:
        """The cassettes under ``folder``; raises :class:`CassetteDamaged` when any of them was
        changed after recording."""
        damaged = damaged_cassettes(Path(folder))
        if damaged:
            lines = "; ".join(f"{p.name}: {why}" for p, why in damaged)
            raise CassetteDamaged(
                f"{folder}: {len(damaged)} cassette(s) changed after recording, so the run"
                f" cannot replay as recorded ({lines}). A complete call's response was valid"
                " JSON when recorded; check what edited it (etach scrub?)"
            )
        return cls(load_cassettes(Path(folder)))

    def take(self, key: str) -> Cassette:
        queue = self._queues.get(key)
        if not queue:
            known = "no cassette" if key not in self._queues else "all cassettes already served"
            raise CassetteMiss(f"{key}: {known}")
        cassette = queue.pop(0)
        self.served.append(cassette)
        return cassette

    async def stream(
        self, body: Mapping[str, Any], *, task: str, match_key: str
    ) -> AsyncGenerator[dict[str, Any]]:
        cassette = self.take(match_key)
        yield {
            "model": body.get("model"),
            "message": {
                "role": "assistant",
                "content": cassette.response_text,
                "thinking": cassette.thinking_text,
            },
            "logprobs": cassette.logprobs or [],
            "done": False,
        }
        if cassette.status == "error":
            raise httpx.RemoteProtocolError("replayed cassette: the stream dropped")
        yield {
            "model": body.get("model"),
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 0,
            "eval_count": len(cassette.logprobs or []),
            "total_duration": 0,
        }


# --- the scenario manifest and the stand-in pages -----------------------------------------------

MANIFEST_NAME = "input.json"


class ScenarioPage(BaseModel):
    """One input page of a recorded run. ``width``/``height`` are the prepared page's size (after
    rotation and resizing); ``stand_in`` is the blank PNG next to the manifest, stored in the
    source orientation (so that ``rotation`` turns it into the prepared size again)."""

    model_config = ConfigDict(extra="forbid")
    original_name: str | None
    width: int
    height: int
    rotation: Literal[0, 90, 180, 270]
    is_key: bool
    has_text_layer: bool = False
    stand_in: str


class ScenarioManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pages: list[ScenarioPage] = Field(default_factory=list)
    existing_test_id: str | None = None
    supersedes_attempt_id: str | None = None


def stand_in_png(width: int, height: int, tag: str = "") -> bytes:
    """A blank white PNG of the given size. ``tag`` goes into a text chunk, so two stand-ins of
    the same size are different files in the file store (identical bytes share one ID)."""
    info = PngImagePlugin.PngInfo()
    info.add_text("etach-stand-in", tag or f"{width}x{height}")
    buf = io.BytesIO()
    Image.new("L", (max(1, width), max(1, height)), 255).save(buf, format="PNG", pnginfo=info)
    return buf.getvalue()


def write_stand_in(path: Path, width: int, height: int, tag: str = "") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(stand_in_png(width, height, tag))
    return path


def write_manifest(out_dir: Path, manifest: ScenarioManifest) -> Path:
    """Write ``<out_dir>/input.json`` and a stand-in PNG for every page."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, page in enumerate(manifest.pages, start=1):
        turned = page.rotation in (90, 270)
        w, h = (page.height, page.width) if turned else (page.width, page.height)
        write_stand_in(out_dir / page.stand_in, w, h, tag=f"page {i}")
    path = out_dir / MANIFEST_NAME
    text = json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def load_manifest(folder: Path) -> ScenarioManifest | None:
    """``<folder>/input.json``, or ``None`` when there is none."""
    path = Path(folder) / MANIFEST_NAME
    if not path.is_file():
        return None
    return ScenarioManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))


# --- the grade scenario manifest ----------------------------------------------------------------

GRADE_MANIFEST_NAME = "grade.json"


class GradeScenario(BaseModel):
    """``<dir>/grade.json``, written by ``etach record --out <dir> --after <extract dir>
    -- grade …``.

    A grade run needs a graded-from database, so its scenario names the **extract scenario** to
    replay first (``after``: a path relative to ``<dir>``, ``/``-separated) and the **target** in
    that replay's result: ``"attempt"`` (grade its ``attempt_id``) or ``"test"`` (a blank test's
    key: grade its ``test_id``). The recorded IDs are for reading only; a replay takes the IDs
    from its own ``etach run --replay`` output."""

    model_config = ConfigDict(extra="forbid")
    after: str
    target: Literal["attempt", "test"]
    recorded_test_id: str
    recorded_attempt_id: str | None = None


def write_grade_scenario(out_dir: Path, scenario: GradeScenario) -> Path:
    """Write ``<out_dir>/grade.json``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / GRADE_MANIFEST_NAME
    text = json.dumps(scenario.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def load_grade_scenario(folder: Path) -> GradeScenario | None:
    """``<folder>/grade.json``, or ``None`` when there is none."""
    path = Path(folder) / GRADE_MANIFEST_NAME
    if not path.is_file():
        return None
    return GradeScenario.model_validate(json.loads(path.read_text(encoding="utf-8")))


def grade_scenario_extract_dir(folder: Path, scenario: GradeScenario) -> Path:
    """The extract scenario folder that ``scenario`` (stored in ``folder``) replays first."""
    return (Path(folder) / scenario.after).resolve()
