"""The content-addressed store, derived images and the sweep (plan R3.1, R3.2, R3.4)."""

from __future__ import annotations

import hashlib
import io
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from PIL import Image

from etach.domain import models as m
from etach.store import files as fs
from etach.store.files import FileStore
from etach.store.repos import attempts, files, runs, tests, threads

OLD = "2026-01-01T08:00:00.000000Z"
RED = (255, 0, 0)


def png(w: int, h: int, marker: bool = False, color: tuple[int, int, int] = (0, 0, 255)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    if marker:  # a red block in the top-left corner shows which way the image turned
        img.paste(RED, (0, 0, w // 4, h // 4))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def jpeg(w: int, h: int, orientation: int | None = None, marker: bool = False) -> bytes:
    img = Image.new("RGB", (w, h), (0, 0, 255))
    if marker:
        img.paste(RED, (0, 0, w // 4, h // 4))
    exif = Image.Exif()
    if orientation is not None:
        exif[0x0112] = orientation
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95, exif=exif)
    return buf.getvalue()


def open_image(store: FileStore, file_id: str) -> Image.Image:
    img = Image.open(io.BytesIO(store.read_bytes(file_id)))
    img.load()
    return img


def is_red(pixel: Any) -> bool:
    r, g, b = pixel[:3]
    return bool(r > 200 and g < 60 and b < 60)


def disk_files(store: FileStore) -> list[str]:
    root = store.paths.files_dir
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


# --- R3.1 ------------------------------------------------------------------------------------


def test_r3_1_put_deduplicates(store: FileStore, conn: sqlite3.Connection) -> None:
    data = png(10, 20)
    first = store.put(data, "png")
    second = store.put(data, "image/png")
    assert first == second == hashlib.sha256(data).hexdigest()
    assert disk_files(store) == [f"{first[:2]}/{first}.png"]
    assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 1
    row = files.get_file(conn, first)
    assert row is not None
    assert row.path == f"files/{first[:2]}/{first}.png"
    assert (row.kind, row.derived_from, row.mime, row.width, row.height) == (
        "upload",
        None,
        "image/png",
        10,
        20,
    )
    assert store.abspath(first) == store.paths.root / "files" / first[:2] / f"{first}.png"


def test_put_types_and_checks(store: FileStore) -> None:
    jid = store.put(jpeg(30, 40), ".JPEG")
    assert store.get(jid).path.endswith(".jpg")
    assert store.get(jid).mime == "image/jpeg"
    pdf = store.put(b"%PDF-1.7 fake", "application/pdf")
    row = store.get(pdf)
    assert (row.mime, row.width, row.height) == ("application/pdf", None, None)
    assert row.path.endswith(".pdf")
    with pytest.raises(ValueError, match="not image/jpeg"):
        store.put(png(5, 5), "jpg")
    with pytest.raises(ValueError, match="derived_from"):
        store.put(png(5, 5), "png", kind="derived")
    with pytest.raises(ValueError):
        store.put(b"x", "no/such-type")


def test_put_rewrites_a_missing_disk_file(store: FileStore) -> None:
    data = png(8, 8)
    fid = store.put(data, "png")
    store.abspath(fid).unlink()
    assert store.put(data, "png") == fid
    assert store.read_bytes(fid) == data
    assert not [p for p in disk_files(store) if p.endswith(".tmp")]


def test_dedup_hit_same_id_one_row(store: FileStore, conn: sqlite3.Connection) -> None:
    data = png(6, 9)
    first = store.put(data, "png")
    before = store.get(first)
    again = store.put(data, "png")
    assert again == first
    assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 1
    after = store.get(again)
    assert after.model_dump(exclude={"created_at"}) == before.model_dump(exclude={"created_at"})
    assert after.created_at >= before.created_at


def test_reupload_refreshes_created_at_so_sweep_keeps_it(
    store: FileStore, conn: sqlite3.Connection
) -> None:
    data = png(7, 7)
    fid = store.put(data, "png")
    _age_all(conn)  # an old, unreferenced file (e.g. from a discarded run)
    assert store.put(data, "png") == fid  # the teacher drops the same photo again
    assert store.get(fid).created_at > datetime(2026, 1, 2, tzinfo=UTC)
    assert store.sweep().deleted == []
    assert store.read_bytes(fid) == data
    assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 1


def test_put_text(store: FileStore) -> None:
    text = "Chọn đáp án đúng.\nA. an\nB. a"
    fid = store.put_text(text)
    row = store.get(fid)
    assert (row.kind, row.mime) == ("text", "text/plain; charset=utf-8")
    assert row.path.endswith(".txt")
    assert store.read_text(fid) == text
    assert store.read_bytes(fid) == text.encode("utf-8")


# --- R3.2 ------------------------------------------------------------------------------------


def test_r3_2_rotate_and_resize(store: FileStore) -> None:
    data = png(100, 200, marker=True)
    orig = store.put(data, "png")
    rot = store.rotate(orig, 90)
    row = store.get(rot)
    assert (row.kind, row.derived_from, row.mime) == ("derived", orig, "image/png")
    assert (row.width, row.height) == (200, 100)
    img = open_image(store, rot)
    assert img.format == "PNG" and img.size == (200, 100)
    assert is_red(img.getpixel((199, 0)))  # clockwise: top-left goes to top-right
    assert hashlib.sha256(store.read_bytes(orig)).hexdigest() == orig  # never modified
    assert store.read_bytes(orig) == data

    big = store.put(png(3000, 1500), "png")
    small = store.get(store.resize(big, max_px=1600))
    assert (small.width, small.height) == (1600, 800)
    assert small.derived_from == big and small.kind == "derived"
    tall = store.get(store.resize(store.put(png(900, 2000), "png")))
    assert (tall.width, tall.height) == (720, 1600)


def test_rotate_directions_and_noops(store: FileStore) -> None:
    orig = store.put(png(40, 80, marker=True), "png")
    assert store.rotate(orig, 0) == orig
    assert store.rotate(orig, 360) == orig
    assert is_red(open_image(store, store.rotate(orig, 180)).getpixel((39, 79)))
    assert is_red(open_image(store, store.rotate(orig, 270)).getpixel((0, 39)))
    assert store.rotate(orig, -90) == store.rotate(orig, 270)
    with pytest.raises(ValueError):
        store.rotate(orig, 45)
    with pytest.raises(ValueError, match="not an image"):
        store.rotate(store.put_text("x"), 90)


def test_resize_never_upscales(store: FileStore) -> None:
    orig = store.put(png(800, 600), "png")
    assert store.resize(orig, max_px=1600) == orig


def test_jpeg_stays_jpeg(store: FileStore) -> None:
    orig = store.put(jpeg(2400, 1200), "jpg")
    out = store.get(store.resize(orig))
    assert out.mime == "image/jpeg" and out.path.endswith(".jpg")
    img = open_image(store, out.id)
    assert img.format == "JPEG" and img.mode == "RGB" and img.size == (1600, 800)


def test_exif_orientation_applied_before_the_operation(store: FileStore) -> None:
    # Orientation 6: the stored pixels must turn 90° clockwise to display upright.
    data = jpeg(100, 200, orientation=6, marker=True)
    orig = store.put(data, "jpg")
    assert (store.get(orig).width, store.get(orig).height) == (100, 200)  # stored pixels

    upright = store.resize(orig)  # fits, but the EXIF turn still makes a derived image
    assert upright != orig
    img = open_image(store, upright)
    assert img.size == (200, 100)
    assert is_red(img.getpixel((190, 5)))  # the stored top-left is now top-right
    assert img.getexif().get(0x0112) in (None, 1)
    assert store.get(upright).derived_from == orig

    turned = open_image(store, store.rotate(orig, 90))
    assert turned.size == (100, 200)  # EXIF 90° + requested 90°
    assert store.read_bytes(orig) == data


# --- sweep (R3.4) ----------------------------------------------------------------------------


def _age_all(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE files SET created_at = ?", (OLD,))


def _test_with_picture(conn: sqlite3.Connection, f: Any, file_id: str) -> m.Test:
    content = f.content()
    content.sections[0].groups[0].pictures = [m.PictureRef(file_id=file_id, page_no=1)]
    return f.make_test(conn, content=content)


def _run(conn: sqlite3.Connection, status: Any, *pages: tuple[str, str | None]) -> m.Run:
    thread = threads.create_thread(conn, "photos")
    run_input = m.ExtractInput(
        pages=[
            m.PageInput(file_id=fid, rotation=0, is_key=False, text_file_id=tid)
            for fid, tid in pages
        ],
        existing_test_id=None,
        supersedes_attempt_id=None,
    )
    run = runs.create_run(conn, thread.id, "extract", run_input)
    if status != "queued":
        runs.set_run_status(conn, run.id, status)
    return run


def test_r3_4_sweep_deletes_exactly_the_unreferenced(
    store: FileStore, conn: sqlite3.Connection, f: Any
) -> None:
    page = store.put(png(10, 10, color=(1, 1, 1)), "png")
    picture = store.put(png(10, 10, color=(2, 2, 2)), "png")
    run_photo = store.put(png(10, 10, color=(3, 3, 3)), "png")
    only_done_run = store.put(png(10, 10, color=(4, 4, 4)), "png")
    loose = store.put_text("nobody uses me")
    test = f.make_test(conn)
    tests.add_test_page(conn, test.id, 1, page)
    _test_with_picture(conn, f, picture)
    _run(conn, "queued", (run_photo, None))
    _run(conn, "done", (only_done_run, None))
    _age_all(conn)

    result = store.sweep()
    assert sorted(r.id for r in result.deleted) == sorted([only_done_run, loose])
    remaining = {r.id for r in files.list_files(conn)}
    assert remaining == {page, picture, run_photo}
    on_disk = {p.split("/")[1].split(".")[0] for p in disk_files(store)}
    assert on_disk == remaining
    assert result.orphans_removed == []
    assert store.sweep().deleted == []  # nothing left to do


def test_sweep_keeps_attempt_pages_and_unfinished_run_text(
    store: FileStore, conn: sqlite3.Connection, f: Any
) -> None:
    source = store.put(png(10, 20), "png")
    prepared = store.rotate(source, 90)
    text = store.put_text("page text")
    attempt = f.make_attempt(conn, f.make_test(conn).id)
    attempts.add_attempt_pages(
        conn,
        [
            m.AttemptPage(
                attempt_id=attempt.id,
                page_no=1,
                file_id=prepared,
                source_file_id=source,
                rotation=90,
            )
        ],
    )
    for status in ("running", "stopping", "stopped", "interrupted"):
        _run(conn, status, (text, text))
    _age_all(conn)
    assert store.sweep().deleted == []

    for run in runs.list_runs(conn):
        runs.set_run_status(conn, run.id, "failed")
    assert [r.id for r in store.sweep().deleted] == [text]


def test_sweep_grace_period_and_ancestors(
    store: FileStore, conn: sqlite3.Connection, f: Any
) -> None:
    upload = store.put(png(100, 200), "png")
    rotated = store.rotate(upload, 90)
    resized = store.resize(store.put(png(3000, 100), "png"))
    chain_root = store.get(resized).derived_from
    tests.add_test_page(conn, f.make_test(conn).id, 1, rotated)
    _age_all(conn)
    fresh = store.put(png(12, 12), "png")  # a photo check before Run: inside the grace period

    result = store.sweep(min_age=timedelta(hours=24))
    deleted = {r.id for r in result.deleted}
    assert deleted == {resized, chain_root}  # an unreferenced derived file and its source
    remaining = {r.id for r in files.list_files(conn)}
    assert remaining == {upload, rotated, fresh}  # the referenced file's ancestor is kept

    # Once the grace period has passed, the fresh photo goes too.
    later = datetime.now(UTC) + timedelta(days=2)
    assert [r.id for r in store.sweep(now=later).deleted] == [fresh]


def test_sweep_young_child_keeps_old_parent(store: FileStore, conn: sqlite3.Connection) -> None:
    upload = store.put(png(100, 50), "png")
    _age_all(conn)
    child = store.rotate(upload, 90)  # young
    assert store.sweep().deleted == []
    assert {r.id for r in files.list_files(conn)} == {upload, child}


def test_sweep_with_the_disk_file_already_missing(
    store: FileStore, conn: sqlite3.Connection
) -> None:
    fid = store.put_text("gone")
    store.abspath(fid).unlink()
    _age_all(conn)
    assert [r.id for r in store.sweep().deleted] == [fid]
    assert files.get_file(conn, fid) is None


def test_sweep_removes_old_orphan_disk_files(store: FileStore, conn: sqlite3.Connection) -> None:
    old_id, young_id = "ab" + "0" * 62, "ab" + "1" * 62
    bucket = store.paths.files_dir / "ab"
    bucket.mkdir(parents=True)
    old_file, young_file = bucket / f"{old_id}.png", bucket / f"{young_id}.png"
    stale_tmp = bucket / ".abc.tmp"
    for p in (old_file, young_file, stale_tmp):
        p.write_bytes(b"x")
    past = (datetime.now(UTC) - timedelta(days=3)).timestamp()
    os.utime(old_file, (past, past))
    os.utime(stale_tmp, (past, past))
    loose = store.put_text("unreferenced and old")
    _age_all(conn)

    result = fs.sweep(conn, store.paths)
    assert sorted(result.orphans_removed) == sorted([f"files/ab/{old_id}.png", "files/ab/.abc.tmp"])
    assert [r.id for r in result.deleted] == [loose]
    assert young_file.exists() and not old_file.exists() and not stale_tmp.exists()


# --- File.original_name (data-model v1.5 §2.8) -------------------------------------------------


def test_original_name_stored_and_first_name_kept(
    store: FileStore, conn: sqlite3.Connection
) -> None:
    data = png(10, 12)
    fid = store.put(data, "png", original_name="Lop8-HKI-De1 (1).png")
    assert store.get(fid).original_name == "Lop8-HKI-De1 (1).png"
    # identical bytes under another name keep the first name
    assert store.put(data, "png", original_name="copy.png") == fid
    assert store.get(fid).original_name == "Lop8-HKI-De1 (1).png"
    assert conn.execute("SELECT original_name FROM files WHERE id = ?", (fid,)).fetchone()[0] == (
        "Lop8-HKI-De1 (1).png"
    )


def test_original_name_filled_when_null(store: FileStore) -> None:
    data = png(11, 13)
    fid = store.put(data, "png")
    assert store.get(fid).original_name is None
    store.put(data, "png")  # no name: stays NULL
    assert store.get(fid).original_name is None
    store.put(data, "png", original_name="page1.png")
    assert store.get(fid).original_name == "page1.png"


def test_derived_and_text_files_have_no_name(store: FileStore) -> None:
    fid = store.put(png(40, 20), "png", original_name="page1.png")
    turned = store.rotate(fid, 90)
    assert turned != fid and store.get(turned).original_name is None
    assert store.get(store.put_text("hello")).original_name is None
