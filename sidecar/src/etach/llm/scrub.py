"""``etach scrub [--check] [--name TEXT]… [--class TEXT]… <dir>``: remove student names and
classes from cassettes (plan §1.7, S5).

A cassette is a ``*.json`` file with a ``response_text`` anywhere under ``<dir>``.

**Scrub** works on the whole folder at once:

1. It collects the values to remove: every ``student_name`` / ``class_name`` value (not ``null``,
   not a placeholder) found in **any** cassette under the folder, plus the ``--name`` /
   ``--class`` values the teacher lists. A field value that does not look like a name (at
   least 2 letters, no digits) or a class (a letter and a digit, 2+ characters: ``8A3``,
   ``8TC11``) is **ignored** and reported on stderr: the model sometimes writes a question
   number, an answer letter or a NuExtract template type word (``string``,
   ``verbatim-string`` …) there, and replacing ``34``, ``B`` or ``string`` everywhere would
   corrupt the recording. A name ending in a class token (``… 8TC11``) yields both targets
   (``etach.domain.boxes.clean_student``). ``--name`` / ``--class`` values are not filtered, but
   an empty value, ``None``, ``null`` or a template word is refused (:class:`ScrubError`).
2. It replaces every occurrence of those values in **every** cassette, but only in text:
   ``thinking_text`` (free text), the **string values** of ``response_text`` (any field: a
   handwritten name line can end up in ``header_text`` or a transcription; never keys, numbers,
   ``null``/``true``/``false`` or structure, so a JSON response stays JSON), and the
   ``logprobs`` tokens covering that text. A ``response_text`` that does not start with ``{``
   or ``[`` is free text. Names become ``Học Sinh A``, classes ``8X1``.

Each full name (family, middle(s), given) is also scrubbed as its last two words (``Văn Tâm``)
and its given name alone (``Tâm``); a family or middle name alone is not (``Lê Lợi`` is printed
test text). A given name alone whose accent-stripped form is a common English word
(:data:`GIVEN_NAME_STOPWORDS`: ``An``, ``Long``, ``Mai`` …) is matched only when it is the exact
accented original, or capitalized and not sentence-initial: ``Em An làm bài`` is scrubbed,
``An apple`` and ``an answer`` are not.

Matching ignores case and Vietnamese accents (``Nguyen van binh`` matches ``Nguyễn Văn Bình``, in
case the model transliterated it) and needs a non-alphanumeric character (or the text edge) on
both sides, so ``8A3`` does not match inside ``18A35``. The original span is replaced. Text that
is already a placeholder is never matched again.

In ``logprobs``, the token entries covering a replaced span are collapsed into one entry whose
token is the placeholder (plus the bytes of the first/last token outside the span), with
``logprob`` = the minimum of the originals and no alternatives, so the tokens still join to the
scrubbed text. In every other entry, a ``top_logprobs`` alternative is removed when its token
(trimmed, accent-stripped, case-folded) equals a scrubbed string (full name, two-word form, given
name, class) or is a prefix of one and at least 3 characters long.

**Check** (``--check``) reports every ``student_name`` / ``class_name`` value that is not ``null``
or a placeholder. It cannot know names the model wrote elsewhere that no field recorded, so the
teacher still reads recorded cassettes before committing them. An empty or missing folder passes.
"""

from __future__ import annotations

import contextlib
import json
import re
import sys
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from etach.domain.boxes import clean_student, not_read_word

__all__ = [
    "CLASS_PLACEHOLDER",
    "GIVEN_NAME_STOPWORDS",
    "PLACEHOLDERS",
    "STUDENT_PLACEHOLDER",
    "Pattern",
    "ScrubError",
    "Targets",
    "Violation",
    "check_dir",
    "collect_targets",
    "field_values",
    "find_spans",
    "fold",
    "json_string_regions",
    "scrub_cassette",
    "scrub_dir",
]

STUDENT_PLACEHOLDER = "Học Sinh A"
CLASS_PLACEHOLDER = "8X1"
PLACEHOLDERS = {"student_name": STUDENT_PLACEHOLDER, "class_name": CLASS_PLACEHOLDER}

_FIELD = re.compile(r'"(student_name|class_name)"\s*:\s*("(?:[^"\\]|\\.)*"|null)')


class ScrubError(ValueError):
    """A cassette could not be scrubbed safely."""


@dataclass(frozen=True)
class Violation:
    path: Path
    field: str
    value: str


#: Vietnamese given names whose accent-stripped form is a common English word (or abbreviation).
#: Alone, such a given name is matched only when it is capitalized and not sentence-initial, or
#: when it is the exact accented original (see :class:`Pattern`).
GIVEN_NAME_STOPWORDS = frozenset(
    {
        "an", "ban", "chi", "dan", "do", "dung", "ha", "hai", "hang", "hung", "kim", "lam",
        "lan", "long", "mai", "may", "my", "nam", "nhung", "son", "tan", "thu", "tin", "van",
    }
)  # fmt: skip


@dataclass(frozen=True)
class Pattern:
    """One string to replace. ``guarded``: a given name alone that is a common English word."""

    value: str
    placeholder: str
    guarded: bool = False


@dataclass(frozen=True)
class Targets:
    """The values to remove: names → ``Học Sinh A``, classes → ``8X1``.

    Each full name (Vietnamese order: family, middle(s), given) also yields its last two words
    (``Văn Tâm``) and its given name alone (``Tâm``). A family or middle name alone is not
    scrubbed: it is too common in printed test text (``Lê Lợi``).
    """

    names: frozenset[str] = frozenset()
    classes: frozenset[str] = frozenset()
    #: ``(field, value)`` pairs found in the cassettes but not used (see ``_targets_of``)
    ignored: frozenset[tuple[str, str]] = frozenset()

    def patterns(self) -> list[Pattern]:
        """Every pattern, longest first (a longer value wins an overlap)."""
        found: dict[str, Pattern] = {}
        for name in self.names:
            words = name.split()
            forms = [" ".join(words)]
            if len(words) >= 3:
                forms.append(" ".join(words[-2:]))
            for form in forms:
                found.setdefault(fold(form), Pattern(form, STUDENT_PLACEHOLDER))
            given = words[-1] if words else ""
            if given and fold(given) not in found:
                guarded = fold(given) in GIVEN_NAME_STOPWORDS
                found[fold(given)] = Pattern(given, STUDENT_PLACEHOLDER, guarded)
        for cls in self.classes:
            found.setdefault(fold(cls.strip()), Pattern(cls.strip(), CLASS_PLACEHOLDER))
        return sorted(found.values(), key=lambda p: (-len(p.value), p.value))

    def folded_parts(self) -> set[str]:
        """The folded strings a ``top_logprobs`` alternative may not spell (rule in the module
        doc)."""
        return {fold(p.value) for p in self.patterns()}


# --- field values ----------------------------------------------------------------------------


def _field_matches(text: str) -> list[tuple[str, str | None]]:
    found: list[tuple[str, str | None]] = []
    for m in _FIELD.finditer(text):
        literal = m.group(2)
        if literal == "null":
            found.append((m.group(1), None))
            continue
        try:
            found.append((m.group(1), json.loads(literal)))
        except json.JSONDecodeError:
            found.append((m.group(1), literal[1:-1]))
    return found


def _walk(value: Any, out: list[tuple[str, str | None]]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in PLACEHOLDERS and (item is None or isinstance(item, str)):
                out.append((key, item))
            else:
                _walk(item, out)
    elif isinstance(value, list):
        for item in value:
            _walk(item, out)


def field_values(text: str) -> list[tuple[str, str | None]]:
    """Every ``(field, value)`` of ``student_name`` / ``class_name`` in a response text (also in
    cut-off JSON)."""
    values = _field_matches(text)
    walked: list[tuple[str, str | None]] = []
    with contextlib.suppress(json.JSONDecodeError, TypeError):
        _walk(json.loads(text), walked)
    return values + [v for v in walked if v not in values]


def _targets_of(field: str, value: str | None) -> list[tuple[str, str]]:
    """The ``("student_name" | "class_name", text)`` targets a field value yields: nothing for a
    template type word or a value of the wrong shape; a name ending in a class token
    (``… 8TC11``) yields both (the same reading as ``etach.domain.boxes.clean_student``).
    Placeholders are never targets."""
    if value is None or not value.strip():
        return []
    if field == "student_name":
        name, cls = clean_student(value, None)
    else:
        name, cls = None, clean_student(None, value)[1]
    out: list[tuple[str, str]] = []
    if name is not None and name != STUDENT_PLACEHOLDER:
        out.append(("student_name", name))
    if cls is not None and cls != CLASS_PLACEHOLDER:
        out.append(("class_name", cls))
    return out


def _filled(field: str, value: str | None) -> bool:
    return value is not None and value.strip() != "" and value != PLACEHOLDERS[field]


def _needs_scrub(field: str, value: str | None) -> bool:
    return bool(_targets_of(field, value))


def _ignored(field: str, value: str | None) -> bool:
    """A filled-in value that yields no target (a question number, an answer, a template word),
    unless it is only placeholders (``Học Sinh A 8X1``)."""
    if value is None or not _filled(field, value) or _targets_of(field, value):
        return False
    rest = value.replace(STUDENT_PLACEHOLDER, "").replace(CLASS_PLACEHOLDER, "")
    return rest.strip() != ""


# --- where text may be replaced ----------------------------------------------------------------


def json_string_regions(text: str) -> list[tuple[int, int]]:
    """The ``[start, end)`` character ranges of ``text`` that may be replaced.

    For JSON (the first non-blank character is ``{`` or ``[``, possibly cut off): the contents
    of the string **values**, without the quotes; keys (a string followed by ``:``) and
    everything outside strings are left out. An unterminated last string runs to the end. Any
    other text is free text: one region covering all of it.
    """
    stripped = text.lstrip()
    if not stripped or stripped[0] not in "{[":
        return [(0, len(text))] if text else []
    regions: list[tuple[int, int]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != '"':
            i += 1
            continue
        start = i + 1
        j = start
        while j < n and text[j] != '"':
            j += 2 if text[j] == "\\" else 1
        end = min(j, n)
        k = end + 1
        while k < n and text[k] in " \t\r\n":
            k += 1
        if not (k < n and text[k] == ":"):
            regions.append((start, end))
        i = end + 1
    return regions


def _shift(regions: Iterable[tuple[int, int]], by: int) -> list[tuple[int, int]]:
    return [(s + by, e + by) for s, e in regions]


# --- accent-insensitive matching -------------------------------------------------------------


def _fold_char(ch: str) -> str:
    if ch in "đĐ":
        return "d"
    decomposed = unicodedata.normalize("NFD", ch)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def fold(text: str) -> str:
    """Lower case without accents (``Nguyễn Văn Bình`` → ``nguyen van binh``)."""
    return "".join(_fold_char(ch) for ch in text)


def _folded_with_index(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    index: list[int] = []
    for i, ch in enumerate(text):
        for c in _fold_char(ch):
            chars.append(c)
            index.append(i)
    return "".join(chars), index


def _is_word(ch: str) -> bool:
    return ch.isalnum() or unicodedata.combining(ch) != 0


_SENTENCE_START = frozenset('.!?\n"“')


def _sentence_initial(text: str, start: int) -> bool:
    """Whether ``text[start]`` starts the text, a sentence, a line or a quoted string."""
    i = start - 1
    while i >= 0 and text[i] in " \t\r":
        i -= 1
    return i < 0 or text[i] in _SENTENCE_START


def _guard_ok(text: str, start: int, end: int, original: str) -> bool:
    """A stopword given name counts only as the exact accented original, or capitalized in the
    middle of a sentence (``Em An làm bài``, not ``An apple`` or ``an answer``)."""
    span = text[start:end]
    if span == original and fold(original) != original.lower():
        return True
    return span[:1].isupper() and not _sentence_initial(text, start)


def find_spans(
    text: str, targets: Targets, regions: Sequence[tuple[int, int]] | None = None
) -> list[tuple[int, int, str]]:
    """Non-overlapping ``(start, end, placeholder)`` character spans of ``text`` to replace;
    with ``regions``, only spans lying inside one of them (see :func:`json_string_regions`)."""
    folded, index = _folded_with_index(text)
    taken: list[tuple[int, int]] = []
    for placeholder in (STUDENT_PLACEHOLDER, CLASS_PLACEHOLDER):
        pos = text.find(placeholder)
        while pos >= 0:
            taken.append((pos, pos + len(placeholder)))
            pos = text.find(placeholder, pos + len(placeholder))
    spans: list[tuple[int, int, str]] = []
    for pattern in targets.patterns():
        needle = fold(pattern.value).strip()
        placeholder = pattern.placeholder
        if not needle:
            continue
        k = folded.find(needle)
        while k >= 0:
            start = index[k]
            end = index[k + len(needle) - 1] + 1
            while end < len(text) and unicodedata.combining(text[end]):
                end += 1
            bounded = (start == 0 or not _is_word(text[start - 1])) and (
                end == len(text) or not _is_word(text[end])
            )
            free = all(end <= s or start >= e for s, e in taken)
            if free and regions is not None:
                free = any(s <= start and end <= e for s, e in regions)
            if bounded and free and pattern.guarded:
                bounded = _guard_ok(text, start, end, pattern.value)
            if bounded and free:
                taken.append((start, end))
                spans.append((start, end, placeholder))
            k = folded.find(needle, k + 1)
    return sorted(spans)


def _replace_text(
    text: str, targets: Targets, regions: Sequence[tuple[int, int]] | None = None
) -> str:
    for start, end, placeholder in reversed(find_spans(text, targets, regions)):
        text = text[:start] + placeholder + text[end:]
    return text


# --- logprobs --------------------------------------------------------------------------------


def _token_bytes(entry: dict[str, Any]) -> bytes:
    raw = entry.get("bytes")
    if isinstance(raw, list):
        return bytes(raw)
    return str(entry.get("token", "")).encode("utf-8")


def _collapse(entries: list[dict[str, Any]], start: int, end: int, new: bytes) -> None:
    """Replace the byte range ``[start, end)`` of the token stream with ``new``, collapsing the
    tokens it touches into one entry (in place)."""
    offsets: list[int] = []
    pos = 0
    for entry in entries:
        offsets.append(pos)
        pos += len(_token_bytes(entry))
    touched = [
        i
        for i, entry in enumerate(entries)
        if offsets[i] < end and offsets[i] + len(_token_bytes(entry)) > start
    ]
    if not touched:
        raise ScrubError("a scrubbed value has no logprob tokens")
    first, last = touched[0], touched[-1]
    prefix = _token_bytes(entries[first])[: start - offsets[first]]
    suffix = _token_bytes(entries[last])[end - offsets[last] :]
    merged = prefix + new + suffix
    collapsed: dict[str, Any] = {
        "token": merged.decode("utf-8", "replace"),
        "logprob": min(float(entries[i].get("logprob", 0.0)) for i in touched),
        "top_logprobs": [],
    }
    if any("bytes" in entries[i] for i in touched):
        collapsed["bytes"] = list(merged)
    entries[first : last + 1] = [collapsed]


def _stream_regions(stream: str, thinking: str, response: str) -> list[tuple[int, int]]:
    """Where the token stream may be replaced: the thinking part (free text) and the string
    values of the response part."""
    if response and stream.endswith(response):
        prefix = len(stream) - len(response)
        head = [(0, prefix)] if prefix else []
        return head + _shift(json_string_regions(response), prefix)
    if thinking and stream.startswith(thinking):
        rest = stream[len(thinking) :]
        return [(0, len(thinking)), *_shift(json_string_regions(rest), len(thinking))]
    return json_string_regions(stream)


def _scrub_logprobs(
    logprobs: list[Any], targets: Targets, thinking: str = "", response: str = ""
) -> list[Any]:
    """The same matching on the joined token stream; spans become collapsed entries."""
    entries = [dict(e) for e in logprobs]
    stream = b"".join(_token_bytes(e) for e in entries).decode("utf-8", "surrogateescape")

    def byte_at(char_index: int) -> int:
        return len(stream[:char_index].encode("utf-8", "surrogateescape"))

    regions = _stream_regions(stream, thinking, response)
    for start, end, placeholder in reversed(find_spans(stream, targets, regions)):
        _collapse(entries, byte_at(start), byte_at(end), placeholder.encode("utf-8"))
    parts = targets.folded_parts()
    for entry in entries:
        alternatives = entry.get("top_logprobs")
        if alternatives:
            entry["top_logprobs"] = [
                alt for alt in alternatives if not _spells_part(str(alt.get("token", "")), parts)
            ]
    return entries


def _spells_part(token: str, parts: set[str]) -> bool:
    """Whether an alternative token (trimmed, folded) equals a scrubbed part, or is a prefix of
    one at least 3 characters long."""
    norm = fold(token.strip())
    if not norm:
        return False
    return any(norm == part or (len(norm) >= 3 and part.startswith(norm)) for part in parts)


# --- cassettes -------------------------------------------------------------------------------


def scrub_cassette(data: dict[str, Any], targets: Targets) -> tuple[dict[str, Any], bool]:
    """The scrubbed cassette and whether anything changed. Raises :class:`ScrubError` when a
    ``student_name`` / ``class_name`` field still holds another value afterwards."""
    response_text = str(data.get("response_text") or "")
    thinking_text = str(data.get("thinking_text") or "")
    out = dict(data)
    out["response_text"] = _replace_text(response_text, targets, json_string_regions(response_text))
    out["thinking_text"] = _replace_text(thinking_text, targets)
    if data.get("logprobs"):
        out["logprobs"] = _scrub_logprobs(data["logprobs"], targets, thinking_text, response_text)
    left = [(f, v) for f, v in field_values(out["response_text"]) if _needs_scrub(f, v)]
    if left:
        raise ScrubError(f"fields still hold values after scrubbing: {[f for f, _ in left]}")
    changed = (
        out["response_text"] != response_text
        or out["thinking_text"] != thinking_text
        or out.get("logprobs") != data.get("logprobs")
    )
    return (out if changed else data), changed


def _cassette_files(folder: Path) -> list[tuple[Path, dict[str, Any]]]:
    if not folder.is_dir():
        return []
    found: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(folder.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(data, dict) and "response_text" in data:
            found.append((path, data))
    return found


def collect_targets(
    cassettes: Iterable[dict[str, Any]],
    names: Iterable[str] = (),
    classes: Iterable[str] = (),
) -> Targets:
    """Every original ``student_name`` / ``class_name`` value in the cassettes that looks like a
    name / class, plus the extras (not filtered). The other values go to ``ignored``."""
    names, classes = list(names), list(classes)
    for flag, values in (("--name", names), ("--class", classes)):
        for v in values:
            if not v.strip() or v.strip().casefold() in {"none", "null"} or not_read_word(v):
                raise ScrubError(
                    f"{flag} {v!a}: not a value to scrub (it would replace that word in every"
                    " cassette); leave the option out when there is nothing to add"
                )
    found_names = {n.strip() for n in names}
    found_classes = {c.strip() for c in classes}
    ignored: set[tuple[str, str]] = set()
    for data in cassettes:
        for field, value in field_values(str(data.get("response_text") or "")):
            for kind, text in _targets_of(field, value):
                (found_names if kind == "student_name" else found_classes).add(text)
            if value is not None and _ignored(field, value):
                ignored.add((field, value.strip()))
    return Targets(frozenset(found_names), frozenset(found_classes), frozenset(ignored))


def _stderr(line: str) -> None:
    print(line, file=sys.stderr)


def scrub_dir(
    folder: Path,
    names: Iterable[str] = (),
    classes: Iterable[str] = (),
    report: Callable[[str], None] = _stderr,
) -> list[Path]:
    """Scrub every cassette under ``folder`` in place; returns the files that changed. Each
    ignored field value goes to ``report`` (stderr by default)."""
    files = _cassette_files(Path(folder))
    targets = collect_targets((data for _, data in files), names, classes)
    for field, value in sorted(targets.ignored):
        kind, flag = ("name", "--name") if field == "student_name" else ("class", "--class")
        report(f"etach scrub: ignored {field} {value!a}: not a {kind}; pass {flag} if needed")
    changed: list[Path] = []
    for path, data in files:
        try:
            new, did_change = scrub_cassette(data, targets)
        except ScrubError as exc:
            raise ScrubError(f"{path}: {exc}") from exc
        if did_change:
            path.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed.append(path)
    return changed


def check_dir(folder: Path) -> list[Violation]:
    """Every unscrubbed ``student_name`` / ``class_name`` value under ``folder``.

    Only field values can be checked: a name the model wrote elsewhere without any field holding
    it is invisible here, so the teacher still reads recorded cassettes before committing them.
    """
    violations: list[Violation] = []
    for path, data in _cassette_files(Path(folder)):
        for field, value in field_values(str(data.get("response_text") or "")):
            if _needs_scrub(field, value) and value is not None:
                violations.append(Violation(path, field, value))
    return violations
