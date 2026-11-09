"""Re-shape recorded ``read_answers_page`` cassettes for step 22.5.6 (each page is asked only for
the questions printed on it). Mechanical, never a re-recording.

The match key holds the page's question IDs, so a cassette recorded when every page was asked for
every question misses. While a replay test runs with ``ETACH_RESHAPE_ANSWERS=1`` (and the
``sitecustomize`` shim below on ``PYTHONPATH``), each such miss is served by the cassette recorded
for the same page (found by its old key: the same page number with the question IDs of its
response), cut to the page's questions:

- ``response_text``: the ``answers`` object keeps only the entries of the page's questions, in
  their recorded order and bytes (the student name and class stay);
- ``logprobs``: the tokens of the kept text keep their recorded values; a token cut at a seam is
  split into one-character tokens with its value, and the ", " joins are new tokens of
  probability 1;
- ``match_key``: the new key. The file is rewritten in place under the same name.

Two modes (``ETACH_RESHAPE_MODE``):

- ``cut`` (the default), for cassettes recorded from a live model: each page keeps only the
  entries its own recording holds; an entry is never moved to another page (that would make up
  model output).
- ``assign``, for SYNTHETIC cassettes (made by the ``make_*.py`` generators, whose fake model
  answers whatever IDs it is asked for): each page's response holds the entry of each of its
  questions taken from whichever page's recording has it (its own first), which is what the fixed
  generator gives. Moved entries keep their characters' recorded log-probabilities (one-character
  tokens).

    # PowerShell, from sidecar/ (the shim only imports this module):
    $env:ETACH_RESHAPE_ANSWERS = "1"; $env:ETACH_RESHAPE_MODE = "cut"  # or "assign"
    $env:PYTHONPATH = "<folder holding sitecustomize.py>"
    uv run pytest tests/replay
    # sitecustomize.py:  import reshape_answers_per_page as r; r.install()
    # (with tests/replay on sys.path)

Run ``etach scrub --check tests/cassettes`` afterwards.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncGenerator, Mapping
from pathlib import Path
from typing import Any

_PAGE = re.compile(r"This is page (\d+) of")
_DEC = json.JSONDecoder()


def _page_no(body: Mapping[str, Any]) -> int:
    for message in body.get("messages", []):
        m = _PAGE.search(str(message.get("content", "")))
        if m:
            return int(m.group(1))
    raise LookupError("no page number in the request")


def _question_ids(body: Mapping[str, Any]) -> list[str]:
    schema = body["format"]
    answers = schema["properties"]["answers"]
    if "$ref" in answers:
        name = answers["$ref"].rsplit("/", 1)[-1]
        answers = schema["$defs"][name]
    return list(answers.get("properties", {}))


def _token_text(entry: Mapping[str, Any]) -> str:
    raw = entry.get("bytes")
    return bytes(raw).decode("utf-8", "replace") if raw is not None else str(entry["token"])


def _entry_spans(text: str) -> tuple[int, int, list[tuple[str, int, int]]]:
    """``(start, end, [(question id, start, end)])`` of the ``answers`` object's inside."""
    at = text.index('"answers"')
    at = text.index("{", at) + 1
    inner = at
    spans: list[tuple[str, int, int]] = []
    pos = at
    while True:
        while text[pos] in " \n\t,":
            pos += 1
        if text[pos] == "}":
            return inner, pos, spans
        key, after = _DEC.raw_decode(text, pos)
        colon = text.index(":", after) + 1
        while text[colon] == " ":
            colon += 1
        _, end = _DEC.raw_decode(text, colon)
        spans.append((key, pos, end))
        pos = end


def reshape(response: str, logprobs: list[Any] | None, keep: list[str]) -> tuple[str, list[Any]]:
    """The response cut to the ``keep`` question IDs, with matching logprobs."""
    inner, close, spans = _entry_spans(response)
    segments = [(0, inner)]
    kept = [(s, e) for key, s, e in spans if key in keep]
    pieces: list[tuple[int, int] | str] = [(0, inner)]
    for n, (s, e) in enumerate(kept):
        if n:
            pieces.append(", ")
        pieces.append((s, e))
    pieces.append((close, len(response)))
    del segments
    # map every character of the response to its token
    tokens = list(logprobs or [])
    owner: list[int] = []
    for i, entry in enumerate(tokens):
        owner.extend([i] * len(_token_text(entry)))
    exact = len(owner) == len(response)
    out_text: list[str] = []
    out_lp: list[Any] = []
    for piece in pieces:
        if isinstance(piece, str):
            out_text.append(piece)
            out_lp.extend(
                {"token": ch, "logprob": 0.0, "bytes": list(ch.encode()), "top_logprobs": []}
                for ch in piece
            )
            continue
        s, e = piece
        out_text.append(response[s:e])
        if not exact:
            continue
        pos = s
        while pos < e:
            i = owner[pos]
            t_start = owner.index(i)
            t_end = t_start + len(_token_text(tokens[i]))
            if t_start >= s and t_end <= e:
                out_lp.append(tokens[i])
                pos = t_end
            else:
                ch = response[pos]
                out_lp.append({**tokens[i], "token": ch, "bytes": list(ch.encode())})
                pos += 1
    return "".join(out_text), out_lp if exact else list(logprobs or [])


def _chars(text: str, logprobs: list[Any] | None) -> list[Any]:
    """One token entry per character of ``text`` (each keeps its token's values)."""
    out: list[Any] = []
    for entry in logprobs or []:
        for ch in _token_text(entry):
            out.append({**entry, "token": ch, "bytes": list(ch.encode())})
    if len(out) != len(text):
        raise ValueError("logprobs do not cover the response text")
    return out


def assign(
    own: tuple[str, list[Any] | None], sources: list[tuple[str, list[Any] | None]], keep: list[str]
) -> tuple[str, list[Any]]:
    """``assign`` mode: the page's response with one entry for each ``keep`` ID, from ``own``
    first, else from the first of ``sources`` that holds it (an ID held by none is left out)."""
    own_text, own_lp = own
    own_ids = {key for key, _, _ in _entry_spans(own_text)[2]}
    if all(qid in own_ids for qid in keep):
        return reshape(own_text, own_lp, keep)
    inner, close, _ = _entry_spans(own_text)
    own_chars = _chars(own_text, own_lp)
    text: list[str] = [own_text[:inner]]
    lps: list[Any] = list(own_chars[:inner])
    first = True
    for qid in keep:
        for src_text, src_lp in [own, *sources]:
            found = [(s, e) for key, s, e in _entry_spans(src_text)[2] if key == qid]
            if not found:
                continue
            s, e = found[0]
            if not first:
                text.append(", ")
                lps.extend(
                    {"token": ch, "logprob": 0.0, "bytes": list(ch.encode()), "top_logprobs": []}
                    for ch in ", "
                )
            first = False
            text.append(src_text[s:e])
            lps.extend(_chars(src_text, src_lp)[s:e])
            break
    text.append(own_text[close:])
    lps.extend(own_chars[close:])
    return "".join(text), lps


def install() -> None:
    """Patch the replay backend (only with ``ETACH_RESHAPE_ANSWERS=1``)."""
    if os.environ.get("ETACH_RESHAPE_ANSWERS") != "1":
        return
    from etach.llm import cassettes as cs

    original_from_dir = cs.ReplayBackend.from_dir.__func__  # type: ignore[attr-defined]
    original_stream = cs.ReplayBackend.stream

    def from_dir(cls: Any, folder: Path) -> Any:
        backend = original_from_dir(cls, folder)
        backend._reshape_folder = Path(folder)
        backend._reshape_sources = [
            (c.response_text, c.logprobs)
            for key, queue in backend._queues.items()
            if key.startswith("read_answers_page:")
            for c in queue
        ]
        return backend

    async def stream(
        self: Any, body: Mapping[str, Any], *, task: str, match_key: str
    ) -> AsyncGenerator[dict[str, Any]]:
        if task == "read_answers_page" and not self._queues.get(match_key):
            _reshape_one(self, body, match_key)
        async for chunk in original_stream(self, body, task=task, match_key=match_key):
            yield chunk

    cs.ReplayBackend.from_dir = classmethod(from_dir)  # type: ignore[method-assign,assignment]
    cs.ReplayBackend.stream = stream  # type: ignore[method-assign]


def _reshape_one(backend: Any, body: Mapping[str, Any], new_key: str) -> None:
    from etach.llm import cassettes as cs

    page = _page_no(body)
    keep = _question_ids(body)
    waiting = [
        (k, q) for k, q in backend._queues.items() if k.startswith("read_answers_page:") and q
    ]

    def same_page(item: tuple[str, list[Any]]) -> bool:
        cassette = item[1][0]
        old_ids = list(json.loads(cassette.response_text).get("answers", {}))
        inputs = {"page_no": page, "question_ids": old_ids}
        return cs.match_key("read_answers_page", cassette.meta.schema_, inputs) == item[0]

    # the cassette of the same page; else (an empty response gives no IDs) the next in order
    exact = [item for item in waiting if same_page(item)]
    if not exact:
        print(f"reshape: page {page} matched by order", flush=True)
    for old_key, queue in exact or waiting[:1]:
        cassette = queue[0]
        if os.environ.get("ETACH_RESHAPE_MODE", "cut") == "assign":
            own = (cassette.response_text, cassette.logprobs)
            text, lps = assign(own, backend._reshape_sources, keep)
        else:
            text, lps = reshape(cassette.response_text, cassette.logprobs, keep)
        queue.pop(0)
        new = cassette.model_copy(
            update={"match_key": new_key, "response_text": text, "logprobs": lps}
        )
        backend._queues.setdefault(new_key, []).append(new)
        folder: Path = backend._reshape_folder
        for path in cs.iter_cassette_files(folder):
            data = json.loads(path.read_text(encoding="utf-8"))
            if (
                data.get("match_key") == old_key
                and data.get("response_text") == cassette.response_text
            ):
                path.write_text(
                    json.dumps(new.to_json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                print(f"reshaped {path} (page {page}, {len(keep)} questions)", flush=True)
                return
        raise LookupError(f"no file for {old_key} under {folder}")
    raise LookupError(f"no recorded cassette for page {page} ({new_key})")
