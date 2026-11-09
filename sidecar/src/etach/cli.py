"""The `etach` command line.

Subcommands (grade, eval, serve, ...) are added by later plan steps.

``etach run`` (step 9) runs one extraction to its end in this process and prints ONE JSON line to
stdout: ``{"test_id", "attempt_id", "run_id", "thread_id", "status"}``; everything else goes to
stderr. ``etach runs stop`` only sets the run's status to ``stopping``: the ``etach run`` process
that owns the run polls the database about every 0.5 s and stops it. ``etach runs resume``
continues a stopped or interrupted run in-process; ``etach runs discard`` discards one.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import contextvars
import json
import os
import sys
import tempfile
import time
from collections.abc import AsyncGenerator, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, get_args

import httpx

from etach import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="etach", description="ETACH sidecar CLI.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", metavar="<command>")

    schema = commands.add_parser("schema", help="JSON Schema files in sidecar/schema/")
    schema_commands = schema.add_subparsers(dest="schema_command", metavar="<action>")
    export = schema_commands.add_parser(
        "export", help="regenerate sidecar/schema/<ClassName>.json (data model + LLM outputs)"
    )
    export.add_argument(
        "--out", type=Path, default=None, help="output folder (default: sidecar/schema)"
    )

    record = commands.add_parser(
        "record", help="run an etach subcommand and record its model calls as cassettes"
    )
    record.add_argument("--out", type=Path, required=True, help="cassette folder (a scenario)")
    record.add_argument(
        "--after",
        type=Path,
        default=None,
        metavar="DIR",
        help="grade only: the extract scenario (cassette folder with input.json) whose replay"
        " made the data folder; written into <out>/grade.json",
    )
    record.add_argument("args", nargs=argparse.REMAINDER, help="the etach subcommand, after --")

    scrub = commands.add_parser(
        "scrub", help="replace student names and classes in cassettes with placeholders"
    )
    scrub.add_argument("folder", type=Path, help="a cassette folder (searched recursively)")
    scrub.add_argument(
        "--check",
        action="store_true",
        help="only report student_name/class_name values that are not null or a placeholder"
        " (exit 1 if any). It cannot see names written elsewhere that no field holds: still"
        " read recorded cassettes before committing them",
    )
    scrub.add_argument(
        "--name",
        dest="names",
        action="append",
        default=[],
        metavar="TEXT",
        help="an extra student name to scrub (repeatable)",
    )
    scrub.add_argument(
        "--class",
        dest="classes",
        action="append",
        default=[],
        metavar="TEXT",
        help="an extra class name to scrub (repeatable)",
    )
    _add_run_parsers(commands)
    _add_eval_parsers(commands)
    _add_serve_parsers(commands)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "schema" and args.schema_command == "export":
        from etach.domain import DEFAULT_SCHEMA_DIR, export_schemas

        written = export_schemas(args.out or DEFAULT_SCHEMA_DIR)
        print(f"wrote {len(written)} schema files")
        return 0
    if args.command == "record":
        from etach.llm.cassettes import recording

        rest = list(args.args)
        if rest[:1] == ["--"]:
            rest = rest[1:]
        if not rest or rest[0] == "record":
            parser.error("record needs an etach subcommand after --")
        if rest[0] == "grade":
            from etach.llm.cassettes import load_manifest

            if args.after is None:
                parser.error("record ... -- grade needs --after <the extract scenario folder>")
            if load_manifest(args.after) is None:
                parser.error(f"--after {args.after}: no input.json (not an extract scenario)")
        elif args.after is not None:
            parser.error("--after is only for recording a grade scenario")
        token = _RECORD_AFTER.set(args.after)
        try:
            with recording(args.out):
                return main(rest)
        finally:
            _RECORD_AFTER.reset(token)
    if args.command == "scrub":
        from etach.llm.scrub import ScrubError, check_dir, scrub_dir

        if args.check:
            # Field values only: the teacher still reads recorded cassettes (llm/scrub.py).
            violations = check_dir(args.folder)
            for v in violations:
                print(f"{v.path}: {v.field} = {v.value!a} is not scrubbed")
            return 1 if violations else 0
        try:
            changed = scrub_dir(args.folder, names=args.names, classes=args.classes)
        except ScrubError as exc:
            _eprint(f"etach scrub: {exc}")
            return 2
        print(f"scrubbed {len(changed)} cassette files")
        return 0
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "grade":
        return _cmd_grade(args)
    if args.command == "eval":
        return _cmd_eval(args)
    if args.command == "fixtures":
        if args.fixtures_command is None:
            parser.error("fixtures needs manifest")
        return _cmd_fixtures(args)
    if args.command == "serve":
        return _cmd_serve(args)
    if args.command == "openapi":
        if args.openapi_command != "export":
            parser.error("openapi needs export")
        from etach.api.app import write_openapi
        from etach.domain import DEFAULT_SCHEMA_DIR

        out = args.out or DEFAULT_SCHEMA_DIR / "openapi.json"
        wrote = write_openapi(out)
        print(f"{'wrote' if wrote else 'unchanged'} {out}")
        return 0
    if args.command == "runs":
        if args.runs_command is None:
            parser.error("runs needs stop, resume or discard")
        return _cmd_runs(args)
    parser.print_help()
    return 0


# --- etach run / etach runs (step 9) -------------------------------------------------------------

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
POLL_SECONDS = 0.5

_RECORD_AFTER: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "etach_record_after", default=None
)
"""``etach record --after``: the extract scenario a recorded grade scenario replays first."""
TEXT_LAYER_STAND_IN = "(the text layer is not stored in the cassette)"

#: Tests only: an httpx transport (a FakeOllama) used instead of a real Ollama. With it set, the
#: Ollama version/model check is skipped.
_TEST_TRANSPORT: httpx.AsyncBaseTransport | None = None


class CliError(RuntimeError):
    """A clear error for stderr; ``code`` is the exit code."""

    def __init__(self, message: str, code: int = 2) -> None:
        super().__init__(message)
        self.code = code


def _eprint(*parts: object) -> None:
    print(*parts, file=sys.stderr, flush=True)


def _add_backend_args(p: argparse.ArgumentParser) -> None:
    where = p.add_mutually_exclusive_group()
    where.add_argument(
        "--spawn-ollama",
        action="store_true",
        help="start a private `ollama serve` (phase-0 settings) for this run and stop it after",
    )
    where.add_argument(
        "--ollama", default=None, metavar="URL", help=f"the Ollama to use ({DEFAULT_OLLAMA_URL})"
    )
    where.add_argument(
        "--replay", type=Path, default=None, metavar="DIR", help="replay the cassettes in DIR"
    )
    p.add_argument("--replay-delay-ms", type=int, default=0, help=argparse.SUPPRESS)


def _add_run_parsers(commands: Any) -> None:
    run = commands.add_parser("run", help="run one extraction (prints one JSON line)")
    run.add_argument("--data", type=Path, required=True, help="the data folder")
    run.add_argument(
        "--pages",
        nargs="+",
        default=[],
        metavar="FILE[:ROT][:key]",
        help="the pages in order: an image, PDF or DOCX; ROT = 0|90|180|270 clockwise;"
        " `key` marks an answer-key page",
    )
    run.add_argument(
        "--key", action="append", default=[], metavar="FILE", help="= FILE:0:key (repeatable)"
    )
    run.add_argument("--existing", default=None, metavar="T-…", help="the picked bank test")
    run.add_argument("--supersedes", default=None, metavar="A-…", help="the attempt to supersede")
    run.add_argument("--thread", default=None, metavar="ID", help="the thread (default: a new one)")
    _add_backend_args(run)

    grade = commands.add_parser(
        "grade", help="grade one attempt, or make a blank test's key (prints one JSON line)"
    )
    grade.add_argument("--data", type=Path, required=True, help="the data folder")
    target = grade.add_mutually_exclusive_group(required=True)
    target.add_argument("--attempt", default=None, metavar="A-…", help="the attempt to grade")
    target.add_argument(
        "--test", default=None, metavar="T-…", help="a test with no attempt: key, tags, notes"
    )
    _add_backend_args(grade)

    runs_p = commands.add_parser("runs", help="stop, resume or discard a run")
    actions = runs_p.add_subparsers(dest="runs_command", metavar="<action>")
    for name, text in (
        ("stop", "ask the `etach run` process that owns the run to stop it"),
        ("resume", "continue a stopped or interrupted run here, to its end"),
        ("discard", "discard a stopped, interrupted or queued run"),
    ):
        a = actions.add_parser(name, help=text)
        a.add_argument("run_id")
        a.add_argument("--data", type=Path, required=True, help="the data folder")
        if name == "stop":
            a.add_argument(
                "--wait",
                type=float,
                default=120.0,
                metavar="S",
                help="seconds to wait for the run to be stopped (0 = do not wait)",
            )
        if name == "resume":
            _add_backend_args(a)


def parse_page_arg(text: str, *, key: bool = False) -> tuple[Path, int, bool]:
    """``FILE[:ROT][:key]`` → (path, rotation, is_key). Parsed from the right, so a drive letter
    (``D:\\…``) stays in the path."""
    parts = text.split(":")
    is_key = key
    rotation = 0
    if len(parts) > 1 and parts[-1].strip().lower() == "key":
        is_key = True
        parts.pop()
    if len(parts) > 1 and parts[-1].strip() in ("0", "90", "180", "270"):
        rotation = int(parts.pop().strip())
    path = ":".join(parts)
    if not path:
        raise CliError(f"--pages {text!r}: no file")
    return Path(path), rotation, is_key


class _DelayedBackend:
    """A replay backend that waits before each call (tests stop a run mid-way)."""

    def __init__(self, inner: Any, delay_s: float) -> None:
        self.inner = inner
        self.delay_s = delay_s

    async def stream(
        self, body: Mapping[str, Any], *, task: str, match_key: str
    ) -> AsyncGenerator[dict[str, Any]]:
        await asyncio.sleep(self.delay_s)
        async for chunk in self.inner.stream(body, task=task, match_key=match_key):
            yield chunk


class _NoBackend:
    """``etach runs discard`` makes no model calls."""

    async def stream(
        self, body: Mapping[str, Any], *, task: str, match_key: str
    ) -> AsyncGenerator[dict[str, Any]]:
        raise RuntimeError("no model calls here")
        yield {}  # pragma: no cover


@contextlib.contextmanager
def _backend(args: argparse.Namespace, log_dir: Path) -> Iterator[tuple[Any, str | None, bool]]:
    """(replay backend or None, Ollama base URL or None, live?)."""
    if args.replay is not None:
        from etach.llm.cassettes import CassetteDamaged, ReplayBackend

        folder = Path(args.replay)
        if not folder.is_dir():
            raise CliError(f"--replay {folder}: no such folder")
        try:
            backend: Any = ReplayBackend.from_dir(folder)
        except CassetteDamaged as exc:
            raise CliError(f"--replay {exc}") from exc
        if not backend.cassettes:
            raise CliError(f"--replay {folder}: no cassettes")
        if args.replay_delay_ms:
            backend = _DelayedBackend(backend, args.replay_delay_ms / 1000)
        yield backend, None, False
        return
    if _TEST_TRANSPORT is not None:
        yield None, "http://fake-ollama", False
        return
    if args.spawn_ollama:
        from etach.llm.ollama_serve import OllamaServeError, PrivateOllama

        server = PrivateOllama(log_dir=log_dir)
        _eprint(f"starting a private ollama serve ({server.exe}) ...")
        try:
            server.start()
        except OllamaServeError as exc:
            raise CliError(str(exc), 3) from exc
        _eprint(f"ollama serve on {server.base_url}; log: {server.log_path}")
        try:
            yield None, server.base_url, True
        finally:
            _eprint("stopping the private ollama serve ...")
            server.stop()
        return
    yield None, args.ollama or DEFAULT_OLLAMA_URL, True


async def _check_ollama(base_url: str, config: Any) -> None:
    from etach.llm import ollama_status

    status = await ollama_status.check(base_url, config.roles.values())
    if status.status != "ok":
        detail = f"; missing: {', '.join(status.missing)}" if status.missing else ""
        raise CliError(
            f"Ollama at {base_url}: {status.status} (version {status.version}){detail}", 3
        )
    _eprint(f"Ollama {status.version} at {base_url}: models present")


def _ids_of(conn: Any, run: Any) -> dict[str, Any]:
    from etach.store.repos import threads

    out: dict[str, Any] = {
        "test_id": None,
        "attempt_id": None,
        "run_id": run.id,
        "thread_id": run.thread_id,
        "status": run.status,
    }
    for message in threads.list_messages(conn, run.thread_id):
        if message.kind == "run_card" and message.body.get("run_id") == run.id:
            out["test_id"] = message.body.get("test_id")
            out["attempt_id"] = message.body.get("attempt_id")
    return out


def _finish_output(result: dict[str, Any]) -> int:
    line = json.dumps(result, ensure_ascii=False)
    if result["status"] in ("done", "stopped", "discarded"):
        print(line, flush=True)
        return 0
    _eprint(f"the run ended {result['status']}: {line}")
    return 1


async def _wait_owned(manager: Any, run_id: str) -> None:
    """Wait until the manager is idle; a ``stopping`` set by `etach runs stop` stops the run."""
    from etach.store.repos import runs

    asked = False
    while True:
        try:
            await asyncio.wait_for(manager.wait_idle(), POLL_SECONDS)
            return
        except TimeoutError:
            pass
        if asked:
            continue
        run = await manager.db.run(lambda c: runs.get_run(c, run_id))
        if run is not None and run.status == "stopping":
            asked = True
            _eprint(f"run {run_id}: stop requested")
            try:
                manager.request_stop(run_id)
            except Exception as exc:  # already ended: the loop sees the idle manager
                _eprint(f"run {run_id}: {exc}")


@contextlib.asynccontextmanager
async def _manager(paths: Any, backend: Any, base_url: str | None) -> AsyncGenerator[Any]:
    from etach.graphs.extract import ExtractDeps, register_extract
    from etach.graphs.grade import GradeDeps, register_grade
    from etach.llm.client import OllamaClient
    from etach.llm.config import load_models_config
    from etach.prompts.render import FilePromptProvider
    from etach.runtime.manager import RunManager
    from etach.store import db
    from etach.store.files import FileStore

    config = load_models_config(paths)
    files_conn = db.connect(paths.db)
    client_conn = db.connect(paths.db)
    files = FileStore(files_conn, paths)
    client = OllamaClient(
        client_conn,
        config,
        FilePromptProvider(),
        base_url=base_url if backend is None else None,
        transport=_TEST_TRANSPORT if backend is None else None,
        backend=backend,
        read_image=files.read_bytes,
    )
    manager = RunManager(paths.db)
    # no key run after an extraction (step22.6-plan D12): an eval must not make or score AI keys,
    # and a recording must not get grade calls; the app's sidecar (``etach serve``) keeps it
    register_extract(manager, ExtractDeps(client=client, files=files, key_after_extract=False))
    register_grade(manager, GradeDeps(client=client))
    try:
        await manager.start()
        yield manager
    finally:
        await manager.aclose()
        files_conn.close()
        client_conn.close()


def _open_data(folder: Path) -> Any:
    from etach.appdir import DataPaths
    from etach.store import db

    paths = DataPaths(Path(folder).resolve()).ensure()
    db.open_database(paths.db).close()
    return paths


def _page_inputs(args: argparse.Namespace, files: Any) -> tuple[list[Any], Any]:
    """The run's pages: from ``--pages``/``--key``, else from the replay manifest."""
    from etach.domain.models import PageInput
    from etach.llm.cassettes import load_manifest
    from etach.store import documents

    manifest = load_manifest(args.replay) if args.replay is not None else None
    specs = [parse_page_arg(t) for t in args.pages] + [
        parse_page_arg(t, key=True) for t in args.key
    ]
    out: list[PageInput] = []
    if specs:
        for path, rotation, is_key in specs:
            if not path.is_file():
                raise CliError(f"{path}: no such file")
            try:
                pages = documents.ingest(files, path.read_bytes(), path.name)
            except documents.UnsupportedDocument as exc:
                raise CliError(str(exc)) from exc
            out.extend(p.model_copy(update={"rotation": rotation, "is_key": is_key}) for p in pages)
        return out, manifest
    if manifest is None:
        raise CliError("give --pages (or --replay a folder with input.json)")
    folder = Path(args.replay)
    for page in manifest.pages:
        fid = files.put(
            (folder / page.stand_in).read_bytes(),
            "png",
            kind="upload",
            original_name=page.original_name,
        )
        text_id = files.put_text(TEXT_LAYER_STAND_IN) if page.has_text_layer else None
        out.append(
            PageInput(file_id=fid, rotation=page.rotation, is_key=page.is_key, text_file_id=text_id)
        )
    return out, manifest


def _write_scenario(out_dir: Path, inp: Any, files: Any) -> None:
    """``etach record``: the scenario manifest + stand-in PNGs (no bytes of the pages)."""
    from etach.domain import pages as page_plan
    from etach.llm.cassettes import ScenarioManifest, ScenarioPage, write_manifest

    rows = {p.file_id: files.get(p.file_id) for p in inp.pages}
    plan = page_plan.plan_pages(inp, rows)
    sizes = {pp.source_file_id: pp.target_size for pp in [*plan.pages, *plan.key_pages]}
    manifest_pages = []
    for i, p in enumerate(inp.pages, start=1):
        size = sizes.get(p.file_id)
        if size is None:
            row = rows[p.file_id]
            size = (row.width or 1000, row.height or 1400)
        manifest_pages.append(
            ScenarioPage(
                original_name=rows[p.file_id].original_name,
                width=int(size[0]),
                height=int(size[1]),
                rotation=p.rotation,
                is_key=p.is_key,
                has_text_layer=p.text_file_id is not None,
                stand_in=f"page-{i:02d}.png",
            )
        )
    write_manifest(
        out_dir,
        ScenarioManifest(
            pages=manifest_pages,
            existing_test_id=inp.existing_test_id,
            supersedes_attempt_id=inp.supersedes_attempt_id,
        ),
    )


async def _run_async(args: argparse.Namespace) -> int:
    from etach.domain.models import ExtractInput
    from etach.llm.cassettes import active_recorder
    from etach.llm.config import load_models_config
    from etach.store import db
    from etach.store.files import FileStore
    from etach.store.repos import runs, threads
    from etach.store.repos import tests as test_repo

    paths = _open_data(args.data)
    conn = db.connect(paths.db)
    try:
        files = FileStore(conn, paths)
        page_inputs, manifest = _page_inputs(args, files)
        existing = args.existing or (manifest.existing_test_id if manifest else None)
        supersedes = args.supersedes or (manifest.supersedes_attempt_id if manifest else None)
        if existing and test_repo.get_test(conn, existing) is None:
            raise CliError(f"--existing {existing}: no such test in {paths.root}")
        if args.thread and threads.get_thread(conn, args.thread) is None:
            raise CliError(f"--thread {args.thread}: no such thread")
        inp = ExtractInput(
            pages=page_inputs, existing_test_id=existing, supersedes_attempt_id=supersedes
        )
        recorder = active_recorder()
        if recorder is not None:
            _write_scenario(recorder.out_dir, inp, files)
        thread_id = args.thread or threads.create_thread(conn, "etach run").id
        with _backend(args, paths.root / "logs") as (backend, base_url, live):
            if live:
                assert base_url is not None
                await _check_ollama(base_url, load_models_config(paths))
            async with _manager(paths, backend, base_url) as manager:
                run = await manager.submit(thread_id, "extract", inp)
                _eprint(f"run {run.id} (thread {thread_id}): {len(inp.pages)} pages")
                await _wait_owned(manager, run.id)
        final = runs.get_run(conn, run.id)
        assert final is not None
        if final.status == "stopping":  # stopped before it started running
            runs.set_run_status(conn, run.id, "stopped")
            final = runs.get_run(conn, run.id)
            assert final is not None
        if final.error:
            _eprint(f"run {run.id}: {final.error}")
        return _finish_output(_ids_of(conn, final))
    finally:
        conn.close()


def _write_grade_scenario(out_dir: Path, inp: Any) -> None:
    """``etach record … -- grade``: ``<out>/grade.json`` (the extract scenario to replay first)."""
    from etach.llm.cassettes import GradeScenario, write_grade_scenario

    after = _RECORD_AFTER.get()
    if after is None:
        raise CliError("recording a grade scenario needs `etach record --after <extract dir>`")
    try:
        rel = os.path.relpath(Path(after).resolve(), Path(out_dir).resolve())
    except ValueError as exc:  # another drive: no relative path
        raise CliError(f"--after {after} and --out {out_dir} must be on the same drive") from exc
    write_grade_scenario(
        out_dir,
        GradeScenario(
            after=Path(rel).as_posix(),
            target="attempt" if inp.attempt_id is not None else "test",
            recorded_test_id=inp.test_id,
            recorded_attempt_id=inp.attempt_id,
        ),
    )


async def _grade_async(args: argparse.Namespace) -> int:
    from etach.domain.models import GradeInput
    from etach.llm.cassettes import active_recorder
    from etach.llm.config import load_models_config
    from etach.store import db
    from etach.store.repos import attempts, runs, threads
    from etach.store.repos import tests as test_repo

    paths = _open_data(args.data)
    conn = db.connect(paths.db)
    try:
        if args.attempt is not None:
            att = attempts.get_attempt(conn, args.attempt)
            if att is None:
                raise CliError(f"--attempt {args.attempt}: no such attempt in {paths.root}")
            inp = GradeInput(test_id=att.test_id, attempt_id=att.id, reason="button")
            thread_id = att.thread_id
        else:
            test = test_repo.get_test(conn, args.test)
            if test is None:
                raise CliError(f"--test {args.test}: no such test in {paths.root}")
            inp = GradeInput(test_id=test.id, attempt_id=None, reason="button")
            row = conn.execute(
                "SELECT id FROM threads WHERE test_id = ? ORDER BY id LIMIT 1", (test.id,)
            ).fetchone()
            thread_id = row[0] if row else threads.create_thread(conn, "etach grade").id
        recorder = active_recorder()
        if recorder is not None:
            _write_grade_scenario(recorder.out_dir, inp)
        with _backend(args, paths.root / "logs") as (backend, base_url, live):
            if live:
                assert base_url is not None
                await _check_ollama(base_url, load_models_config(paths))
            async with _manager(paths, backend, base_url) as manager:
                run = await manager.submit(thread_id, "grade", inp)
                _eprint(f"run {run.id} (thread {thread_id}): grade {inp.attempt_id or inp.test_id}")
                await _wait_owned(manager, run.id)
        final = runs.get_run(conn, run.id)
        assert final is not None
        if final.status == "stopping":
            runs.set_run_status(conn, run.id, "stopped")
            final = runs.get_run(conn, run.id)
            assert final is not None
        if final.error:
            _eprint(f"run {run.id}: {final.error}")
        out = _ids_of(conn, final)
        out["test_id"], out["attempt_id"] = inp.test_id, inp.attempt_id
        if inp.attempt_id is not None:
            graded = attempts.get_attempt(conn, inp.attempt_id)
            assert graded is not None
            out["score_earned"], out["score_possible"] = graded.score_earned, graded.score_possible
        return _finish_output(out)
    finally:
        conn.close()


def _cmd_grade(args: argparse.Namespace) -> int:
    started = time.monotonic()
    try:
        code = asyncio.run(_grade_async(args))
    except CliError as exc:
        _eprint(f"etach grade: {exc}")
        return exc.code
    _eprint(f"etach grade: {time.monotonic() - started:.1f} s")
    return code


def _cmd_run(args: argparse.Namespace) -> int:
    started = time.monotonic()
    try:
        code = asyncio.run(_run_async(args))
    except CliError as exc:
        _eprint(f"etach run: {exc}")
        return exc.code
    _eprint(f"etach run: {time.monotonic() - started:.1f} s")
    return code


async def _runs_async(args: argparse.Namespace) -> int:
    from etach.llm.config import load_models_config
    from etach.runtime.manager import InvalidRunState
    from etach.store import db
    from etach.store.repos import runs

    paths = _open_data(args.data)
    conn = db.connect(paths.db)
    try:
        run = runs.get_run(conn, args.run_id)
        if run is None:
            raise CliError(f"no run {args.run_id} in {paths.root}")
        action = args.runs_command
        if action == "stop":
            if run.status not in ("running", "queued", "stopping"):
                raise CliError(f"run {run.id} is {run.status}; only a running run can be stopped")
            runs.set_run_status(conn, run.id, "stopping")
            deadline = time.monotonic() + max(0.0, args.wait)
            while time.monotonic() < deadline:
                current = runs.get_run(conn, run.id)
                if current is not None and current.status != "stopping":
                    break
                await asyncio.sleep(POLL_SECONDS)
            current = runs.get_run(conn, run.id)
            assert current is not None
            if current.status == "stopping" and args.wait > 0:
                _eprint(f"run {run.id}: still stopping (is its `etach run` process alive?)")
            print(json.dumps(_ids_of(conn, current), ensure_ascii=False), flush=True)
            return 0
        if action == "discard":
            if run.status in ("running", "stopping"):
                raise CliError(f"run {run.id} is {run.status}; stop it first")
            async with _manager(paths, _NoBackend(), None) as manager:
                try:
                    await manager.discard(run.id)
                except InvalidRunState as exc:
                    raise CliError(str(exc)) from exc
            final = runs.get_run(conn, run.id)
            assert final is not None
            return _finish_output(_ids_of(conn, final))
        # resume
        if run.status not in ("stopped", "interrupted"):
            raise CliError(f"run {run.id} is {run.status}; only stopped or interrupted runs resume")
        with _backend(args, paths.root / "logs") as (backend, base_url, live):
            if live:
                assert base_url is not None
                await _check_ollama(base_url, load_models_config(paths))
            async with _manager(paths, backend, base_url) as manager:
                try:
                    await manager.resume(run.id)
                except InvalidRunState as exc:
                    raise CliError(str(exc)) from exc
                _eprint(f"run {run.id} resumed")
                await _wait_owned(manager, run.id)
        final = runs.get_run(conn, run.id)
        assert final is not None
        if final.error:
            _eprint(f"run {run.id}: {final.error}")
        return _finish_output(_ids_of(conn, final))
    finally:
        conn.close()


def _cmd_runs(args: argparse.Namespace) -> int:
    try:
        return asyncio.run(_runs_async(args))
    except CliError as exc:
        _eprint(f"etach runs {args.runs_command}: {exc}")
        return exc.code


# --- etach eval / etach fixtures (step 11) -------------------------------------------------------


def _add_eval_parsers(commands: Any) -> None:
    ev = commands.add_parser(
        "eval", help="run a graph over a fixture set; append one row to eval-history.csv"
    )
    ev.add_argument(
        "--graph",
        choices=("extract", "grade"),
        default=None,
        help="the graph to measure (required, except with --score-ratings)",
    )
    ev.add_argument(
        "--set",
        dest="set_name",
        choices=("tuning", "heldout"),
        default=None,
        help="the fixture set (required to run a graph)",
    )
    ev.add_argument(
        "--rate-explanations",
        nargs="+",
        type=Path,
        default=None,
        metavar="RUN_DIR",
        help="with --graph grade: write a blind rating sheet from 2 or more kept grade runs"
        " (their --keep folders, one per reasoning model) into --out; runs nothing",
    )
    ev.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="DIR",
        help="the rating sheet's folder (default <repo>/fixtures/_runs/ratings-<time>)",
    )
    ev.add_argument(
        "--seed", type=int, default=None, help="the rating sheet's shuffle seed (fixed default)"
    )
    ev.add_argument(
        "--list-verdicts",
        action="store_true",
        help="with --graph grade and --keep: write each fixture's needs-verdict.json (the"
        " free-text answers that need the teacher's verdict); runs no model",
    )
    ev.add_argument(
        "--score-ratings",
        type=Path,
        default=None,
        metavar="DIR",
        help="read a filled rating sheet in DIR back and print the ratings per model",
    )
    ev.add_argument(
        "--role",
        action="append",
        default=[],
        metavar="ROLE=TAG",
        help=(
            "use model TAG for ROLE (vision, reasoning, grading_check, extraction_check or ocr)"
            " in this run (repeatable)"
        ),
    )
    ev.add_argument(
        "--fixtures", type=Path, default=None, metavar="DIR", help="default: <repo>/fixtures"
    )
    ev.add_argument(
        "--history", type=Path, default=None, metavar="CSV", help="default: <repo>/eval-history.csv"
    )
    ev.add_argument(
        "--vram-mb", type=float, default=None, help="the peak VRAM seen (MB), if measured"
    )
    ev.add_argument(
        "--vram-mb-file",
        type=Path,
        default=None,
        metavar="FILE",
        help="read the peak VRAM (MB) from FILE when the row is written (a sampler running"
        " beside the eval keeps it up to date); overrides --vram-mb when readable",
    )
    ev.add_argument(
        "--keep",
        type=Path,
        default=None,
        metavar="DIR",
        help="also write each fixture's test, answers, metrics and mismatches to"
        " DIR/<set>/<fixture>/ and the row to DIR/<set>/summary.json (student text:"
        " use a folder under fixtures/)",
    )
    ev.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="NAME",
        help="run only the fixture NAME of the set (repeatable, or comma-separated); an"
        " unknown name is an error",
    )
    ev.add_argument(
        "--tiles",
        action="store_true",
        help="turn [extract] retranscribe_tiles on for this run (off by default); the row's"
        " mode gets '+tiles'",
    )
    ev.add_argument(
        "--photo-reader",
        choices=("ocr", "vision"),
        default=None,
        help="[extract] photo_reader for this run (default: ocr, GLM-OCR then structure_text_page;"
        " vision: one vision call per photo page); the row's mode gets '+ocr' when the OCR"
        " reader runs",
    )
    ev.add_argument(
        "--photo-structure",
        choices=("qwen", "code", "ocr_format"),
        default=None,
        help="[extract] photo_structure for this run (OCR reader only; default: code,"
        " the layout rules, no model call; qwen: structure_text_page; ocr_format: GLM-OCR"
        " writes the test-text format, read by code); the row's mode gets"
        " '+code' or '+ocr_format'",
    )
    ev.add_argument(
        "--preflight",
        action="store_true",
        help="only check the fixtures and Ollama (version, models) and exit; runs nothing",
    )
    _add_backend_args(ev)

    fx = commands.add_parser("fixtures", help="eval fixture tools")
    fx_actions = fx.add_subparsers(dest="fixtures_command", metavar="<action>")
    man = fx_actions.add_parser(
        "manifest", help="write fixtures/MANIFEST.sha256 (the teacher commits it)"
    )
    man.add_argument(
        "--fixtures", type=Path, default=None, metavar="DIR", help="default: <repo>/fixtures"
    )


def _parse_roles(items: Sequence[str]) -> dict[str, str]:
    from etach.llm.config import Role

    roles: dict[str, str] = {}
    for item in items:
        role, sep, tag = item.partition("=")
        role, tag = role.strip(), tag.strip()
        if not sep or role not in get_args(Role) or not tag:
            names = ", ".join(get_args(Role))
            raise CliError(f"--role {item!r}: expected ROLE=<tag>, ROLE one of {names}")
        roles[role] = tag
    return roles


def _only_fixtures(fixtures: list[Any], only: Sequence[str]) -> list[Any]:
    """``--only NAME`` (repeatable or comma-separated): those fixtures, in the set's order."""
    names = [n.strip() for item in only for n in item.split(",") if n.strip()]
    if not names:
        return fixtures
    known = {fx.name for fx in fixtures}
    unknown = [n for n in names if n not in known]
    if unknown:
        raise CliError(f"--only: no fixture {', '.join(unknown)} in the set")
    return [fx for fx in fixtures if fx.name in names]


def _vram_mb(args: argparse.Namespace) -> float | None:
    """``--vram-mb-file`` (when it holds a number), else ``--vram-mb``."""
    path: Path | None = args.vram_mb_file
    if path is not None:
        try:
            return float(path.read_text(encoding="utf-8-sig").strip())
        except (OSError, ValueError):
            _eprint(f"etach eval: --vram-mb-file {path}: no number in it; using --vram-mb")
    value: float | None = args.vram_mb
    return value


async def _eval_async(args: argparse.Namespace) -> int:
    from etach.eval import harness
    from etach.eval.fixtures import FixtureError, discover
    from etach.llm.cassettes import CassetteDamaged, ReplayBackend
    from etach.llm.config import parse_models_config
    from etach.llm.defaults import DEFAULT_EXTRACT

    if args.score_ratings is not None:
        return _score_ratings(args.score_ratings)
    if args.graph is None:
        raise CliError("--graph is required (extract or grade)")
    if args.rate_explanations is not None:
        if args.graph != "grade":
            raise CliError("--rate-explanations is for --graph grade")
        return _rate_explanations(args)
    if args.set_name is None:
        raise CliError("--set is required (tuning or heldout)")
    grade = args.graph == "grade"
    if grade and args.tiles:
        raise CliError("--tiles is for --graph extract")
    if grade and args.photo_reader is not None:
        raise CliError("--photo-reader is for --graph extract")
    if grade and args.photo_structure is not None:
        raise CliError("--photo-structure is for --graph extract")
    # the photo reader of an extract run (R22.5.7.7: ocr unless --photo-reader vision); a grade
    # run reads no test photo
    reader = "vision" if grade else (args.photo_reader or DEFAULT_EXTRACT["photo_reader"])
    # step 22.6.5 (D7): how the OCR text is structured (the default, code since step 22.6.6 (c),
    # unless --photo-structure)
    structure = args.photo_structure or DEFAULT_EXTRACT["photo_structure"]
    if reader != "ocr" and args.photo_structure is not None:
        raise CliError("--photo-structure is for the OCR photo reader")
    roles = _parse_roles(args.role)
    root = args.fixtures or harness.REPO_ROOT / "fixtures"
    try:
        fixtures = discover(root, args.set_name)
    except FixtureError as exc:
        raise CliError(str(exc)) from exc
    if not fixtures:
        raise CliError(f"no fixtures in {root / args.set_name}")
    fixtures = _only_fixtures(fixtures, args.only)
    tags = harness.model_tags(roles)
    replay = args.replay

    def backend_for(fx: Any) -> Any:
        if replay is None:
            return None
        folder = harness.replay_dir_for(Path(replay), fx)
        try:
            backend: Any = ReplayBackend.from_dir(folder)
        except CassetteDamaged as exc:
            raise CliError(f"--replay {exc}") from exc
        if not backend.cassettes:
            raise CliError(f"--replay {folder}: no cassettes for {fx.set}/{fx.name}")
        return backend

    keep: Path | None = args.keep
    if grade:
        from etach.eval import grade as grade_eval

        for fx in fixtures:  # the typed truth must make a test before anything runs
            try:
                grade_eval.check_fixture(fx)
            except FixtureError as exc:
                raise CliError(f"{fx.set}/{fx.name}: {exc}") from exc
        if args.list_verdicts:
            return _list_verdicts(fixtures, keep)
    elif args.list_verdicts:
        raise CliError("--list-verdicts is for --graph grade")

    async def run_set(base_url: str | None) -> list[Any]:
        if grade:
            return await grade_eval.run_grade_set(
                fixtures, backend_for=backend_for, base_url=base_url, roles=roles, keep=keep
            )
        return await harness.run_extract_set(
            fixtures,
            backend_for=backend_for,
            base_url=base_url,
            roles=roles,
            keep=keep,
            tiles=args.tiles,
            photo_reader=reader,
            photo_structure=args.photo_structure,
        )

    def preflight_ok(mode: str) -> int:
        print(
            json.dumps(
                {
                    "preflight": "ok",
                    "mode": mode,
                    "set": args.set_name,
                    "n_fixtures": len(fixtures),
                    "model_vision": tags.get("vision", ""),
                    "model_reasoning": tags.get("reasoning", ""),
                    "tiles": bool(args.tiles),
                    "photo_reader": reader,
                    "photo_structure": structure if reader == "ocr" else None,
                }
            ),
            flush=True,
        )
        return 0

    if replay is not None:
        if not Path(replay).is_dir():
            raise CliError(f"--replay {replay}: no such folder")
        if args.preflight:
            return preflight_ok("replay")
        results = await run_set(None)
        mode = "replay"
    else:
        logs = Path(tempfile.mkdtemp(prefix="etach-eval-logs-"))
        with _backend(args, logs) as (_, base_url, live):
            if live:
                assert base_url is not None
                config = parse_models_config(
                    {
                        "roles": {r: {"model": t} for r, t in roles.items()},
                        "extract": {"photo_reader": reader},
                    }
                )
                await _check_ollama(base_url, config)
            if args.preflight:
                return preflight_ok("live")
            results = await run_set(base_url)
        mode = "live"
    if args.tiles:
        mode += "+tiles"  # which rows compared the tile path
    if reader == "ocr":
        mode += "+ocr"  # the GLM-OCR photo reader (R22.5.7.7); rows without it read with vision
        if structure != "qwen":
            mode += f"+{structure}"  # step 22.6.5: the OCR text structured without qwen
    if grade:
        row = grade_eval.aggregate_grade_row(
            results, set_name=args.set_name, mode=mode, models=tags, vram_mb=_vram_mb(args)
        )
    else:
        row = harness.aggregate_row(
            results,
            graph=args.graph,
            set_name=args.set_name,
            mode=mode,
            models=tags,
            vram_mb=_vram_mb(args),
        )
    history = args.history or harness.default_history_path()
    try:
        harness.append_history(history, row)
    except harness.HistoryHeaderMismatch as exc:
        raise CliError(str(exc)) from exc
    if keep is not None:
        harness.write_summary(keep / args.set_name, row)
    shown: tuple[str, ...] = (
        "n_fixtures",
        "n_failed",
        "cer",
        "structure_overall",
        "answer_accuracy",
        "calibration",
        "key_accuracy",
    )
    extra: dict[str, Any] = {}
    if grade:
        shown = (
            "n_fixtures",
            "n_failed",
            "model_reasoning",
            "key_accuracy_fast",
            "key_accuracy",
            "verdict_accuracy",
            "judge_accuracy",
            "score_exact_match",
        )
        # counts only: the answers themselves are in the --keep folder (student text)
        extra["needs_verdict"] = grade_eval.needs_verdict_count(results)
    summary = {k: row[k] for k in shown}
    print(json.dumps({"history": str(history), **summary, **extra}), flush=True)
    if grade and extra["needs_verdict"]:
        where = "needs-verdict.json in the --keep folder" if keep else "rerun with --keep"
        _eprint(
            f"etach eval: {extra['needs_verdict']} answer(s) need the teacher's verdict"
            f" (expected.json 'verdicts'); see {where}"
        )
    return 0 if row["n_failed"] == "0" else 1


def _list_verdicts(fixtures: list[Any], keep: Path | None) -> int:
    from etach.eval import grade as grade_eval

    if keep is None:
        raise CliError("--list-verdicts needs --keep DIR (a folder under fixtures/)")
    missing = 0
    for fx in fixtures:
        items = grade_eval.needs_verdict_items(fx)
        grade_eval.write_needs_verdict(keep / fx.set / fx.name, fx, items)
        missing += sum(1 for n in items if n["teacher_verdict"] is None)
    # counts only: the answers are in the files (student text)
    print(json.dumps({"needs_verdict": missing, "folder": str(keep)}), flush=True)
    return 0


def _rate_explanations(args: argparse.Namespace) -> int:
    from etach.eval import harness
    from etach.eval.ratings import DEFAULT_SEED, RatingError, write_sheet

    out: Path = args.out or (
        harness.REPO_ROOT / "fixtures" / "_runs" / f"ratings-{time.strftime('%Y-%m-%dT%H-%M')}"
    )
    try:
        n = write_sheet(list(args.rate_explanations), out, seed=args.seed or DEFAULT_SEED)
    except RatingError as exc:
        raise CliError(str(exc)) from exc
    print(json.dumps({"rating_sheet": str(out), "items": n}), flush=True)
    return 0


def _score_ratings(folder: Path) -> int:
    from etach.eval.ratings import RatingError, score_sheet

    try:
        lines = score_sheet(folder)
    except RatingError as exc:
        raise CliError(str(exc)) from exc
    for line in lines:
        print(line)
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    try:
        return asyncio.run(_eval_async(args))
    except CliError as exc:
        _eprint(f"etach eval: {exc}")
        return exc.code


def _cmd_fixtures(args: argparse.Namespace) -> int:
    from etach.eval import harness
    from etach.eval.fixtures import manifest_lines, write_manifest

    root = args.fixtures or harness.REPO_ROOT / "fixtures"
    if not root.is_dir():
        _eprint(f"etach fixtures manifest: {root}: no such folder")
        return 2
    out = write_manifest(root)
    print(f"wrote {out} ({len(manifest_lines(root))} fixtures)")
    return 0


# --- etach serve / etach openapi (step 12) -------------------------------------------------------


def _add_serve_parsers(commands: Any) -> None:
    serve = commands.add_parser(
        "serve",
        help='run the sidecar API on 127.0.0.1 (prints {"port", "token"} as the first line)',
    )
    serve.add_argument(
        "--data",
        type=Path,
        default=None,
        help="the data folder (default: the app folder's data folder)",
    )
    _add_backend_args(serve)

    openapi = commands.add_parser("openapi", help="the sidecar's OpenAPI document")
    actions = openapi.add_subparsers(dest="openapi_command", metavar="<action>")
    export = actions.add_parser("export", help="write sidecar/schema/openapi.json")
    export.add_argument("--out", type=Path, default=None, help="output file")


def _cmd_serve(args: argparse.Namespace) -> int:
    from etach.appdir import AppDirError, resolve_data_dir

    try:
        paths = _open_data(resolve_data_dir(args.data).root)
    except AppDirError as exc:
        _eprint(f"etach serve: {exc}")
        return 2
    try:
        with _backend(args, paths.root / "logs") as (backend, base_url, _live):
            asyncio.run(_serve_async(paths, backend, base_url))
    except CliError as exc:
        _eprint(f"etach serve: {exc}")
        return exc.code
    except KeyboardInterrupt:
        pass
    return 0


async def _serve_async(paths: Any, backend: Any, base_url: str | None) -> None:
    import signal
    import threading

    import uvicorn
    from uvicorn.server import HANDLED_SIGNALS

    from etach.api.app import HOST, bind_socket, build_context, create_app

    ctx = build_context(
        paths,
        backend=backend,
        base_url=base_url,
        transport=_TEST_TRANSPORT if backend is None else None,
    )
    app = create_app(ctx)
    sock = bind_socket(HOST, 0)
    port = sock.getsockname()[1]

    class _Server(uvicorn.Server):
        @contextlib.contextmanager
        def capture_signals(self) -> Iterator[None]:
            # Like uvicorn's, but the signal is not raised again after the clean shutdown:
            # `etach serve` exits 0 and its callers' cleanup (the private Ollama) still runs.
            if threading.current_thread() is not threading.main_thread():
                yield
                return
            original = {sig: signal.signal(sig, self.handle_exit) for sig in HANDLED_SIGNALS}
            try:
                yield
            finally:
                for sig, handler in original.items():
                    signal.signal(sig, handler)

        async def startup(self, sockets: list[Any] | None = None) -> None:
            await super().startup(sockets=sockets)
            if not self.should_exit:
                # The first stdout line: the app connects only after the socket listens.
                print(json.dumps({"port": port, "token": ctx.token}), flush=True)

    config = uvicorn.Config(
        app,
        log_level="warning",
        access_log=False,
        lifespan="on",
        timeout_graceful_shutdown=5,
    )
    server = _Server(config)
    _eprint(f"etach serve: data {paths.root}; listening on {HOST}:{port}")
    try:
        await server.serve(sockets=[sock])
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
