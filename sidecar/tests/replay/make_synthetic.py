"""Regenerate the SYNTHETIC extract cassettes in ``tests/cassettes/extract-synthetic/``.

    cd sidecar
    uv run python tests/replay/make_synthetic.py

Each scenario is recorded with ``etach record --out <scenario> -- run …`` (the real CLI, the real
prompts) over the schema-keyed FakeOllama of the step 9 graph tests, so every folder holds the
cassettes, ``input.json`` and the stand-in PNGs, exactly like a live recording. All data is
synthetic (``Học Sinh A`` / ``8X1``). Scenarios that need a bank test or an earlier attempt first
run ``s1-like`` (not recorded) in the same data folder; the replay tests do the same.
"""

from __future__ import annotations

import importlib.util
import io
import json
import shutil
import sys
import tempfile
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PIL import Image

HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
OUT_ROOT = TESTS / "cassettes" / "extract-synthetic"
STUDENT = "Học Sinh A"
CLASS = "8X1"
HEADER = "TRUONG THCS A - DE KIEM TRA HOC KI I - LOP 8 - NAM HOC 2025-2026"

sys.path.insert(0, str(TESTS))


def _load_graph_tests() -> Any:
    path = TESTS / "unit" / "graphs" / "test_extract.py"
    spec = importlib.util.spec_from_file_location("_etach_extract_scenarios", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


G = _load_graph_tests()
page_out = G.page_out
EMPTY = {"student_name": None, "class_name": None, "answers": {}}


def answers(value: str = "A") -> Callable[[list[str]], dict[str, Any]]:
    def build(ids: list[str]) -> dict[str, Any]:
        return {
            "student_name": STUDENT,
            "class_name": CLASS,
            "answers": {
                qid: [{"value": value, "location": "circled_option", "alt_question_id": None}]
                for qid in ids
            },
        }

    return build


def photo(folder: Path, name: str, shade: int, size: tuple[int, int] = (400, 600)) -> Path:
    img = Image.linear_gradient("L").resize(size).convert("RGB")
    img = Image.blend(img, Image.new("RGB", size, (shade, 250, 250 - shade % 50)), 0.5)
    path = folder / name
    img.save(path, format="JPEG" if name.endswith(".jpg") else "PNG")
    return path


def text_pdf(path: Path, text: str) -> Path:
    """A one-page PDF with a real text layer (hand-written, Helvetica)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    )
    path.write_bytes(out.getvalue())
    _ = zlib  # (no compression: the text stays readable)
    return path


class Recorder:
    def __init__(self, work: Path) -> None:
        from etach import cli

        self.cli = cli
        self.work = work
        self.fake = G.Routed()
        cli._TEST_TRANSPORT = self.fake.transport

    def run(
        self,
        data: Path,
        pages: list[str],
        queues: dict[str, list[Any]],
        *extra: str,
        out: Path | None = None,
    ) -> dict[str, Any]:
        from support.reader import vision_reader

        self.fake.queues = {k: list(v) for k, v in queues.items()}
        vision_reader(data)  # the scenarios read photos with the vision role (R22.5.7.7)
        args = ["run", "--data", str(data), "--pages", *pages, *extra]
        if out is not None:
            if out.exists():
                shutil.rmtree(out)
            args = ["record", "--out", str(out), "--", *args]
        buf = io.StringIO()
        real = sys.stdout
        sys.stdout = buf
        try:
            code = self.cli.main(args)
        finally:
            sys.stdout = real
        assert code == 0, f"etach {' '.join(args)} exited {code}"
        return json.loads(buf.getvalue().strip().splitlines()[-1])


S1_QUEUES: dict[str, list[Any]] = {
    "TranscribeOut": [page_out(1, header=HEADER), page_out(2), page_out(3)],
    # step 22.5.6: each page is asked only for its own questions, so each page answers them
    "ReadAnswersCall": [answers(), answers(), answers()],
}


def stems() -> list[str]:
    return [q["stem"] for p in (1, 2) for q in page_out(p)["sections"][0]["groups"][0]["questions"]]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        rec = Recorder(work)
        p = [photo(work, f"De-synthetic ({i}).jpg", 200 + i) for i in (1, 2, 3)]
        s1_pages = [str(p[0]), f"{p[1]}:90", str(p[2])]

        def fresh(name: str) -> Path:
            return work / f"data-{name}"

        # s1-like: a filled 3-page test, page 2 turned 90°
        rec.run(fresh("s1"), s1_pages, S1_QUEUES, out=OUT_ROOT / "s1-like")

        def with_bank(name: str) -> tuple[Path, dict[str, Any]]:
            data = fresh(name)
            return data, rec.run(data, s1_pages, S1_QUEUES)

        header_ok = {"header_text": HEADER, "first_stems": stems()[:3]}
        header_bad = {"header_text": "UNRELATED", "first_stems": ["Zebras jump lazily"]}
        two = [str(p[0]), str(p[1])]
        for name, header, answer_queue in (
            ("filled-picked-match", header_ok, [answers(), EMPTY]),
            ("filled-picked-mismatch", header_bad, [answers(), EMPTY]),
            ("blank-picked", header_ok, [EMPTY, EMPTY]),
        ):
            data, first = with_bank(name)
            queues = {"ReadHeaderOut": [header], "ReadAnswersCall": answer_queue}
            rec.run(data, two, queues, "--existing", first["test_id"], out=OUT_ROOT / name)

        # key-photo: one test page + two answer-key photos (one unsure)
        k1, k2 = photo(work, "key (1).png", 10), photo(work, "key (2).png", 20)
        sure = json.dumps({"entries": [{"label": "1", "answer": "A"}]})
        unsure = json.dumps({"entries": [{"label": "2", "answer": "C"}]})
        rec.run(
            fresh("key"),
            [str(p[0]), f"{k1}:0:key", f"{k2}:key"],
            {
                "ReadKeyOut": [
                    G.ChatScript(tokens=list(sure)),
                    G.ChatScript(tokens=list(unsure), logprob=-3.0),
                ],
                "TranscribeOut": [page_out(1, header=HEADER)],
                "ReadAnswersCall": [answers()],
            },
            out=OUT_ROOT / "key-photo",
        )

        # validator-retry: page 2 invalid JSON once (retry), then a bad page → tiles → failed
        rec.run(
            fresh("retry"),
            two,
            {
                "TranscribeOut": [
                    page_out(1, header=HEADER),
                    G.BAD,
                    *[page_out(2, bad=True)] * 3,
                ],
                "ReadAnswersCall": [answers(), answers()],
            },
            out=OUT_ROOT / "validator-retry",
        )

        # pdf-text: a PDF page with a text layer
        pdf = text_pdf(work / "De-synthetic-text.pdf", "TEXT LAYER SYNTHETIC")
        rec.run(
            fresh("pdf"),
            [str(pdf)],
            {"TranscribeOut": [page_out(1, header=HEADER)], "ReadAnswersCall": [answers()]},
            out=OUT_ROOT / "pdf-text",
        )

        # supersede: s1-like first (attempt A), then the same photos again superseding A
        data, first = with_bank("supersede")
        rec.run(
            data,
            s1_pages,
            S1_QUEUES,
            "--thread",
            first["thread_id"],
            "--supersedes",
            first["attempt_id"],
            out=OUT_ROOT / "supersede",
        )
        rec.cli._TEST_TRANSPORT = None
    print(f"wrote {OUT_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
