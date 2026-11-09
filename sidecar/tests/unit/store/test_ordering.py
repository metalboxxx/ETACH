"""Monotonic ULIDs, and list functions returning same-timestamp rows in insertion order.

The step 2 verification found ``ORDER BY created_at, id`` was flaky when two rows share a
``created_at``: the tie-break depended on the random bits of ``new_ulid()``.
"""

from __future__ import annotations

import itertools
import sqlite3
import threading
import time
from datetime import UTC, datetime
from typing import Any

import pytest

from etach.domain import models as m
from etach.store import db
from etach.store.repos import files, review, runs, threads

SAME = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
N = 30


def test_ulids_strictly_increase_in_a_tight_loop() -> None:
    ids = [db.new_ulid() for _ in range(10_000)]
    assert all(a < b for a, b in itertools.pairwise(ids))


def test_ulids_strictly_increase_across_threads() -> None:
    per_thread: list[list[str]] = [[] for _ in range(4)]

    def work(out: list[str]) -> None:
        out.extend(db.new_ulid() for _ in range(2_000))

    workers = [threading.Thread(target=work, args=(out,)) for out in per_thread]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    everything = [i for out in per_thread for i in out]
    assert len(set(everything)) == len(everything)
    for out in per_thread:
        assert out == sorted(out)


def test_ulid_random_overflow_moves_to_next_millisecond(monkeypatch: pytest.MonkeyPatch) -> None:
    ms = 1_900_000_000_000
    monkeypatch.setattr(time, "time_ns", lambda: ms * 1_000_000)  # frozen clock
    monkeypatch.setattr(db, "_ulid_last_ms", ms)
    monkeypatch.setattr(db, "_ulid_last_random", db._RANDOM_MAX - 1)
    first = db.new_ulid()  # same millisecond: random part + 1 = the maximum
    assert first.endswith("Z" * 16)
    after = db.new_ulid()  # overflow: borrows the next millisecond
    assert first < after
    assert after[:10] > first[:10]
    assert db._ulid_last_ms == ms + 1


@pytest.fixture
def frozen_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every ``datetime.now()`` in the repositories returns the same instant."""

    class Frozen(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> Frozen:
            return cls(2026, 5, 5, 12, 0, tzinfo=UTC)

    for mod in (threads, review, runs):
        monkeypatch.setattr(mod, "datetime", Frozen)


def test_messages_in_insertion_order(conn: sqlite3.Connection, frozen_now: None) -> None:
    th = threads.create_thread(conn, "t")
    made = [threads.add_message(conn, th.id, "app", "text", {"i": i}) for i in range(N)]
    assert len({x.created_at for x in made}) == 1
    assert [x.body["i"] for x in threads.list_messages(conn, th.id)] == list(range(N))


def test_review_items_in_insertion_order(conn: sqlite3.Connection, frozen_now: None) -> None:
    for i in range(N):
        review.upsert_item(
            conn, kind="uncertain_answer", owner="extract", dedupe_key=f"k{i}", proposal={"i": i}
        )
    items = review.list_items(conn)
    assert len({x.created_at for x in items}) == 1
    assert [x.proposal["i"] for x in items] == list(range(N))


def test_steps_in_insertion_order(conn: sqlite3.Connection, f: Any, frozen_now: None) -> None:
    run = f.make_run(conn)
    made = [runs.insert_step(conn, run.id, f"node{i}", None, 1) for i in range(N)]
    assert len({x.started_at for x in made}) == 1
    assert [x.node for x in runs.list_steps(conn, run.id)] == [f"node{i}" for i in range(N)]


def test_llm_calls_in_insertion_order(conn: sqlite3.Connection, f: Any) -> None:
    step = runs.insert_step(conn, f.make_run(conn).id, "n", None, 1)
    for i in range(N):
        runs.insert_llm_call(
            conn,
            m.LlmCall(
                id=db.new_ulid(),
                step_id=step.id,
                role="vision",
                model="x",
                prompt_hash=str(i),
                request={},
                response_text="",
                thinking_text="",
                logprobs=None,
                status="complete",
                tokens_in=None,
                tokens_out=None,
                ms=None,
                created_at=SAME,
            ),
        )
    got = runs.list_llm_calls(conn, step.id)
    assert [c.prompt_hash for c in got] == [str(i) for i in range(N)]


def test_files_in_insertion_order(conn: sqlite3.Connection) -> None:
    # sha256 IDs in descending order, so an ``id`` tie-break would reverse them
    ids = [f"{255 - i:02x}" * 32 for i in range(N)]
    for fid in ids:
        files.insert_file(
            conn,
            m.File(
                id=fid,
                path=f"files/{fid[:2]}/{fid}",
                kind="upload",
                derived_from=None,
                mime="image/png",
                width=None,
                height=None,
                created_at=SAME,
            ),
        )
    assert [x.id for x in files.list_files(conn)] == ids
