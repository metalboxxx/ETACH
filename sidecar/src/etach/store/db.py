"""SQLite access: connections, migrations, transactions, ``write_test_meta`` and test search.

data-model §3 (tables), §5.1 (writing rules) and §5.5 (migrations). The driver is the stdlib
``sqlite3``, synchronous; async callers wrap calls in ``asyncio.to_thread``. A connection may be
used from any thread, but never by two threads at once.

Connections run in autocommit mode (``isolation_level=None``): every write goes through
:func:`transaction`, which nests with savepoints, so a repository function called inside a
caller's transaction joins it.
"""

from __future__ import annotations

import itertools
import json
import os
import re
import sqlite3
import threading
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

from etach.domain.models import TYPED_NAME_KEY, TestMetadata, set_occasion_short_names

__all__ = [
    "BUSY_TIMEOUT_MS",
    "Fts5UnavailableError",
    "MigrationError",
    "apply_migrations",
    "check_fts5",
    "connect",
    "dumps",
    "fts_prefix_query",
    "iso",
    "list_migrations",
    "load_occasion_names",
    "new_ulid",
    "now_iso",
    "open_database",
    "search_tests",
    "sync_test_meta",
    "transaction",
    "write_test_meta",
]

# --- time and ids ----------------------------------------------------------------------------


def iso(dt: datetime) -> str:
    """An aware datetime as a fixed-width ISO-8601 UTC string (sorts as text)."""
    if dt.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def now_iso() -> str:
    return iso(datetime.now(UTC))


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


_RANDOM_MAX = (1 << 80) - 1
_ulid_lock = threading.Lock()
_ulid_last_ms = -1
_ulid_last_random = 0


def new_ulid() -> str:
    """A 26-character monotonic ULID: 48-bit millisecond time + 80 random bits, Crockford base32.

    Monotonic mode: within the same millisecond (or if the clock steps back) the previous random
    part is incremented instead of drawing a new one, so every ID sorts after the IDs generated
    before it in this process. Rows ordered by ``created_at, id`` therefore come back in
    insertion order even when their timestamps are equal. Thread-safe.
    """
    global _ulid_last_ms, _ulid_last_random
    with _ulid_lock:
        ms = time.time_ns() // 1_000_000
        if ms > _ulid_last_ms:
            _ulid_last_ms = ms
            _ulid_last_random = int.from_bytes(os.urandom(10), "big")
        elif _ulid_last_random < _RANDOM_MAX:
            _ulid_last_random += 1
        else:  # the random part overflowed within one millisecond: borrow the next one
            _ulid_last_ms += 1
            _ulid_last_random = int.from_bytes(os.urandom(10), "big") >> 1
        value = (_ulid_last_ms << 80) | _ulid_last_random
    return "".join(_CROCKFORD[(value >> (5 * i)) & 31] for i in range(25, -1, -1))


# --- connections -----------------------------------------------------------------------------


class Fts5UnavailableError(RuntimeError):
    """This SQLite build has no FTS5; the test search (data-model §3) cannot work."""


class MigrationError(RuntimeError):
    """The migration files are inconsistent, or one failed to apply."""


BUSY_TIMEOUT_MS = 10_000
"""How long a connection waits for another writer's lock before ``database is locked``. The app
connections and LangGraph's checkpointer connection share ``app.db`` (llm-design §7), so both
use it (``etach.runtime.checkpoint``)."""


def connect(path: Path | str) -> sqlite3.Connection:
    """Open the database at ``path`` with ``foreign_keys=ON``, ``journal_mode=WAL`` and
    ``busy_timeout`` = :data:`BUSY_TIMEOUT_MS`."""
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        db_path,
        isolation_level=None,
        check_same_thread=False,
        timeout=BUSY_TIMEOUT_MS / 1000,
    )
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys = ON")
    mode = conn.execute("PRAGMA journal_mode = WAL").fetchone()[0]
    if str(mode).lower() != "wal":
        conn.close()
        raise sqlite3.OperationalError(f"could not switch {db_path} to WAL (got {mode!r})")
    return conn


def check_fts5(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("CREATE VIRTUAL TABLE temp.etach_fts5_probe USING fts5(x)")
        conn.execute("DROP TABLE temp.etach_fts5_probe")
    except sqlite3.OperationalError as exc:
        raise Fts5UnavailableError(
            f"SQLite {sqlite3.sqlite_version} has no FTS5 support: {exc}"
        ) from exc


def open_database(path: Path | str) -> sqlite3.Connection:
    """Startup: connect, confirm FTS5, apply pending migrations, run the one-time
    difficulty-notes pass (step 22.5.4), answer-form pass (step 22.5.3), equal-points pass
    (step 22.4.4), test-text pass (step 22.5.2) and key-photo pass (step 22.5.6)."""
    conn = connect(path)
    try:
        check_fts5(conn)
        apply_migrations(conn)
        load_occasion_names(conn)
        from etach.store.repos.answer_form_pass import run_answer_form_pass  # repos import this
        from etach.store.repos.difficulty_pass import run_difficulty_notes_pass
        from etach.store.repos.key_photo_pass import run_key_photo_pass
        from etach.store.repos.points import run_equal_points_pass
        from etach.store.repos.text_pass import run_test_text_pass

        # first: the other passes read the tests through the models (data-model v1.23, v1.22)
        run_difficulty_notes_pass(conn)  # once, after migration 0013 (data-model v1.23)
        run_answer_form_pass(conn)  # once, after migration 0012 (data-model v1.22)
        run_equal_points_pass(conn)  # once, after migration 0009 (data-model v1.19)
        run_test_text_pass(conn)  # once, after migration 0011 (data-model v1.21)
        run_key_photo_pass(conn)  # once, after migration 0015 (data-model v1.25)
    except BaseException:
        conn.close()
        raise
    return conn


# --- transactions ----------------------------------------------------------------------------

_savepoints = itertools.count(1)


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """``BEGIN IMMEDIATE`` … ``COMMIT``; any exception rolls back and propagates.

    Inside an open transaction it uses a savepoint instead, so the outer transaction decides.
    """
    if conn.in_transaction:
        name = f"etach_sp_{next(_savepoints)}"
        conn.execute(f"SAVEPOINT {name}")
        try:
            yield conn
        except BaseException:
            conn.execute(f"ROLLBACK TO {name}")
            conn.execute(f"RELEASE {name}")
            raise
        conn.execute(f"RELEASE {name}")
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


# --- migrations ------------------------------------------------------------------------------

_MIGRATION_NAME = re.compile(r"^(\d{4})_[A-Za-z0-9_]+\.sql$")


def list_migrations() -> list[tuple[int, str, str]]:
    """``(version, file name, sql)`` for every packaged migration, in version order."""
    folder = resources.files("etach.store").joinpath("migrations")
    found: dict[int, tuple[str, str]] = {}
    for entry in folder.iterdir():
        match = _MIGRATION_NAME.match(entry.name)
        if not match:
            continue
        version = int(match.group(1))
        if version in found:
            raise MigrationError(f"two migrations share version {version}")
        found[version] = (entry.name, entry.read_text(encoding="utf-8"))
    if not found:
        raise MigrationError("no migration files found in etach/store/migrations")
    return [(v, *found[v]) for v in sorted(found)]


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if not exists:
        return set()
    return {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    """Apply the pending numbered migrations in order, each in its own transaction, and record
    each in ``schema_migrations``. Returns the versions applied (empty when up to date)."""
    if conn.in_transaction:
        raise MigrationError("apply_migrations must not run inside a transaction")
    applied = _applied_versions(conn)
    done: list[int] = []
    for version, name, sql in list_migrations():
        if version in applied:
            continue
        try:
            conn.executescript(f"BEGIN IMMEDIATE;\n{sql}\n;")
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, now_iso()),
            )
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise MigrationError(f"migration {name} failed: {exc}") from exc
        done.append(version)
    return done


# --- test metadata (data-model §2.2, §5.1) ---------------------------------------------------

_META_FTS_FIELDS = (
    "test_code",
    "region",
    "source",
    "textbook",
    "units",
    "tags",
    "exam_format",
    "extra",
)


def load_occasion_names(conn: sqlite3.Connection) -> None:
    """Give the domain the ``occasions`` table's short names (data-model v1.17), so
    ``TestMetadata.display_name()`` uses the teacher's names. Called when the database opens and
    after every occasion write."""
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'occasions'"
    ).fetchone():
        return  # a database before migration 0007 (tests of older migrations): the defaults stay
    rows = conn.execute("SELECT code, short_name FROM occasions").fetchall()
    set_occasion_short_names({code: short for code, short in rows})


def _occasion_label(conn: sqlite3.Connection, code: str) -> str | None:
    row = conn.execute("SELECT label FROM occasions WHERE code = ?", (code,)).fetchone()
    return row[0] if row else None


def _meta_text(meta: TestMetadata, label: str | None = None) -> str:
    """The searchable metadata that the display name does not already carry."""
    parts: list[str] = []
    for field in _META_FTS_FIELDS:
        value = getattr(meta, field)
        if isinstance(value, dict):
            parts.extend(str(v) for v in value.values() if isinstance(v, str))
        elif isinstance(value, list):
            parts.extend(str(v) for v in value)
        elif value:
            parts.append(str(value))
    parts.append(meta.occasion)  # the code ("FinalTerm") stays searchable beside the name (v1.11)
    if label:
        parts.append(label)  # v1.17: the occasion's label ("Final-term test") too
    return " ".join(parts)


def _write_fts_row(conn: sqlite3.Connection, test_id: str, meta: TestMetadata) -> None:
    conn.execute("DELETE FROM tests_fts WHERE test_id = ?", (test_id,))
    conn.execute(
        "INSERT INTO tests_fts (test_id, display_name, meta_text) VALUES (?, ?, ?)",
        (test_id, meta.display_name(), _meta_text(meta, _occasion_label(conn, meta.occasion))),
    )


def sync_test_meta(conn: sqlite3.Connection, test_id: str, meta: TestMetadata) -> None:
    """Store ``meta`` with everything derived from it: the ``meta`` JSON, the denormalized
    columns, ``display_name``, ``updated_at`` and the ``tests_fts`` row (removed for a merged
    test). Used by :func:`write_test_meta` and by the test insert; call it inside a transaction.
    """
    with transaction(conn):
        cur = conn.execute(
            "UPDATE tests SET meta = ?, display_name = ?, occasion = ?, grade = ?, year = ?,"
            " school = ?, term = ?, test_number = ?, created_by_ai = ?, parent_test_id = ?,"
            " updated_at = ? WHERE id = ?",
            (
                meta.model_dump_json(),
                meta.display_name(),
                meta.occasion,
                meta.grade,
                meta.year,
                meta.school,
                meta.term,
                meta.test_number,
                int(meta.created_by_ai),
                meta.parent_test_id,
                now_iso(),
                test_id,
            ),
        )
        if cur.rowcount != 1:
            raise KeyError(f"no test {test_id}")
        merged = conn.execute("SELECT merged_into FROM tests WHERE id = ?", (test_id,)).fetchone()
        if merged[0] is None:
            _write_fts_row(conn, test_id, meta)
        else:
            conn.execute("DELETE FROM tests_fts WHERE test_id = ?", (test_id,))


def write_test_meta(
    conn: sqlite3.Connection, test_id: str, changes: Mapping[str, Any], by_teacher: bool
) -> TestMetadata:
    """The only way to change a test's metadata (data-model §5.1).

    ``changes`` maps ``TestMetadata`` field names to new values. A teacher write applies every
    change and adds the fields to ``edited_fields``; any other write skips the fields already in
    ``edited_fields``. ``meta``, the columns, ``display_name``, ``edited_fields`` and the FTS row
    change together in one transaction. Returns the stored metadata.
    """
    unknown = set(changes) - set(TestMetadata.model_fields) - {TYPED_NAME_KEY}
    if unknown:
        raise ValueError(f"unknown metadata fields: {sorted(unknown)}")
    if "edited_fields" in changes:
        raise ValueError("edited_fields is maintained by write_test_meta, not changed directly")
    with transaction(conn):
        row = conn.execute("SELECT meta FROM tests WHERE id = ?", (test_id,)).fetchone()
        if row is None:
            raise KeyError(f"no test {test_id}")
        current = TestMetadata.model_validate_json(row[0])
        data = current.model_dump()
        edited = list(current.edited_fields)
        for field, value in changes.items():
            if not by_teacher and field in current.edited_fields:
                continue
            if field == TYPED_NAME_KEY:
                # v1.13: a typed Test name is kept in extra and edited_fields; None (or blank)
                # removes it, so the automatic name is made again. Only the teacher sets it.
                if not by_teacher:
                    continue
                extra = dict(data["extra"])
                typed = value.strip() if isinstance(value, str) else None
                if typed:
                    extra[TYPED_NAME_KEY] = typed
                    if field not in edited:
                        edited.append(field)
                else:
                    extra.pop(TYPED_NAME_KEY, None)
                    edited = [e for e in edited if e != field]
                data["extra"] = extra
                continue
            data[field] = value
            if by_teacher and field not in edited:
                edited.append(field)
        data["edited_fields"] = edited
        meta = TestMetadata.model_validate(data)
        sync_test_meta(conn, test_id, meta)
    return meta


# --- search ----------------------------------------------------------------------------------

_WORD = re.compile(r"\w", re.UNICODE)


def fts_prefix_query(text: str) -> str:
    """Per-token prefix matching: ``grade 8 final`` → ``"grade"* "8"* "final"*``.

    Each whitespace-separated token is quoted (inner quotes doubled), so FTS5 operators and
    punctuation in the input are plain text. Tokens without a letter or digit are dropped.
    Returns ``""`` when nothing searchable is left.
    """
    tokens = [t for t in text.split() if _WORD.search(t)]
    return " ".join('"' + t.replace('"', '""') + '"*' for t in tokens)


def search_tests(conn: sqlite3.Connection, text: str, limit: int = 50) -> list[str]:
    """Test IDs whose display name or metadata match every token of ``text`` as a prefix,
    best match first. Merged tests are never returned.

    ``text`` that is a test's id ("T-0008", "t-0008" or "T0008": any case, with or without the
    dash) finds that test first (llm-design v4.40, step 22.5.1). ``test_id`` is not in the FTS
    index, so the id is matched on ``tests`` directly."""
    key = text.strip().replace("-", "").upper()
    found: list[str] = []
    if key:
        found = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM tests"
                " WHERE UPPER(REPLACE(id, '-', '')) = ? AND merged_into IS NULL",
                (key,),
            )
        ]
    query = fts_prefix_query(text)
    if not query:
        return found
    rows = conn.execute(
        "SELECT f.test_id FROM tests_fts f JOIN tests t ON t.id = f.test_id"
        " WHERE tests_fts MATCH ? AND t.merged_into IS NULL ORDER BY f.rank LIMIT ?",
        (query, limit),
    ).fetchall()
    return found + [row[0] for row in rows if row[0] not in found][: max(limit - len(found), 0)]


def dumps(value: Any) -> str:
    """JSON text for a JSON column (UTF-8 kept as is)."""
    return json.dumps(value, ensure_ascii=False)
