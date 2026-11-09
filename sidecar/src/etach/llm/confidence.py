"""Per-field confidence from token logprobs (D20, llm-design §6, plan step 6).

Pure: no database, network or file I/O. The ``resample`` fallback gets its second sample from an
injected async callable.

How a call's logprobs become per-field confidences:

1. **Tokens → response bytes.** The token ``bytes`` are joined (UTF-8 of ``token`` when ``bytes``
   is missing). With thinking on, the list covers thinking + ``\\n</think>`` + the response, and
   never the end-of-generation token (Phase 0 item 1), so the response is the **suffix** of the
   joined bytes. If the suffix does not equal ``response_text`` byte for byte, the mapping has
   failed and the configured fallback applies. The text ``</think>`` is never searched for.
2. **Response → leaves.** A small JSON scanner with byte positions yields every leaf (string,
   number, bool, null) with its path (``answers.q-7f3a[0].value``) and the byte span of its
   content: a string without its quotes, in its escaped form as the model wrote it.
3. **Leaf → confidence.** The span maps to the tokens that overlap it.
   - Enum leaves (the choices come from the JSON Schema: ``$ref``/``$defs``, ``anyOf``/``oneOf``/
     ``allOf``, ``enum``, ``const``): the first token of the value. Its ``top_logprobs`` plus the
     chosen token are restricted to tokens whose text, trimmed of whitespace and quotes, exactly
     equals a valid choice (case-sensitive: ``b`` is not ``B``; ``top_logprobs`` are taken before
     the grammar, so forbidden tokens are dropped). Renormalized, a missing choice counts 0;
     confidence = the **margin** p(chosen) - p(best other choice), which is p(top) - p(second)
     whenever the chosen value is the model's top choice, and is clamped at 0 otherwise.
   - An enum leaf whose value is ``null``: the probability of the (first) ``null`` token.
   - Free text, numbers, bools (and nulls of non-enum fields): the **minimum** token probability
     over the span. The sequence probability (the product) is kept for calibration.
   - An enum value that is not a single token (e.g. ``"circled_option"``: the first token is not
     itself a choice): the minimum token probability, kind ``enum_multitoken``.
4. **Fallbacks** (``confidence.fallback``; not set = ``"none"``, the Phase 0 decision) when the
   logprobs are missing or empty or the mapping fails. Every fallback result has
   ``low_trust=True``; a logprob result has ``low_trust=False``.
   - ``resample``: the injected callable returns a second sample (temperature 0.7, the caller's
     job); a leaf that agrees → 1.0, one that disagrees or is missing → 0.0.
   - ``self_report``: the model's own ``confidence`` number in the leaf's object or the nearest
     enclosing one, clamped to [0, 1]; none → 0.0.
   - ``none``: 0.0, so every value is flagged for the teacher.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel

__all__ = [
    "FallbackName",
    "FieldConfidence",
    "Kind",
    "Leaf",
    "MappingError",
    "Resample",
    "answer_confidence",
    "answer_path",
    "fallback_confidences",
    "field_confidences",
    "logprob_confidences",
    "parse_leaves",
    "response_offset",
]

FallbackName = Literal["resample", "self_report", "none"]
Kind = Literal["enum", "enum_multitoken", "null", "text", "number", "bool"]
#: A second sample of the same call (temperature 0.7): the response text, or the parsed JSON.
Resample = Callable[[], Awaitable[str | Mapping[str, Any]]]

_TRIM = " \t\r\n\"'"


class MappingError(ValueError):
    """The logprobs cannot be mapped onto the response (the fallback applies)."""


@dataclass(frozen=True)
class Leaf:
    """A JSON leaf: its path, decoded value and the byte span of its content in the response."""

    path: str
    value: Any
    start: int  # byte offset in the response (a string's content, without the quotes)
    end: int
    json_type: Literal["string", "number", "bool", "null"]


@dataclass(frozen=True)
class FieldConfidence:
    value: Any
    confidence: float  # in [0, 1]
    kind: Kind
    token_span: tuple[int, int] | None  # [first, last + 1) indices into the logprob list
    seq_prob: float | None  # product of the span's token probabilities (for calibration)
    low_trust: bool  # True = from a fallback, not from logprobs (Answer.low_trust)
    byte_span: tuple[int, int] | None = None  # the leaf's content bytes in the response


class _HasLogprobs(Protocol):
    @property
    def raw_text(self) -> str: ...
    @property
    def logprobs(self) -> list[Any] | None: ...


# --- JSON scanner with byte positions ----------------------------------------------------------

_WS = b" \t\r\n"
_NUMBER = re.compile(rb"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_LITERALS: dict[bytes, tuple[Any, Literal["bool", "null"]]] = {
    b"true": (True, "bool"),
    b"false": (False, "bool"),
    b"null": (None, "null"),
}


class _Scanner:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0
        self.leaves: list[Leaf] = []

    def fail(self, what: str) -> MappingError:
        return MappingError(f"invalid JSON at byte {self.pos}: {what}")

    def ws(self) -> None:
        while self.pos < len(self.data) and self.data[self.pos] in _WS:
            self.pos += 1

    def peek(self) -> int:
        if self.pos >= len(self.data):
            raise self.fail("unexpected end")
        return self.data[self.pos]

    def expect(self, char: bytes) -> None:
        self.ws()
        if self.data[self.pos : self.pos + 1] != char:
            raise self.fail(f"expected {char.decode()}")
        self.pos += 1

    def string(self) -> tuple[str, int, int]:
        """A string at ``pos`` (on its opening quote): (decoded, content start, content end)."""
        start = self.pos + 1
        i = start
        while True:
            if i >= len(self.data):
                raise self.fail("unterminated string")
            char = self.data[i]
            if char == 0x22:  # "
                break
            i += 2 if char == 0x5C else 1  # a backslash escapes the next byte
        try:
            decoded = json.loads(self.data[start - 1 : i + 1].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise self.fail(f"bad string ({exc})") from exc
        self.pos = i + 1
        return decoded, start, i

    def value(self, path: str) -> None:
        self.ws()
        char = self.peek()
        if char == 0x7B:  # {
            self.pos += 1
            self.ws()
            if self.peek() == 0x7D:
                self.pos += 1
                return
            while True:
                self.ws()
                if self.peek() != 0x22:
                    raise self.fail("expected a key")
                key, _, _ = self.string()
                self.expect(b":")
                self.value(f"{path}.{key}" if path else key)
                self.ws()
                if self.peek() == 0x2C:
                    self.pos += 1
                    continue
                self.expect(b"}")
                return
        if char == 0x5B:  # [
            self.pos += 1
            self.ws()
            if self.peek() == 0x5D:
                self.pos += 1
                return
            index = 0
            while True:
                self.value(f"{path}[{index}]")
                index += 1
                self.ws()
                if self.peek() == 0x2C:
                    self.pos += 1
                    continue
                self.expect(b"]")
                return
        if char == 0x22:
            decoded, start, end = self.string()
            self.leaves.append(Leaf(path, decoded, start, end, "string"))
            return
        for literal, (val, json_type) in _LITERALS.items():
            if self.data.startswith(literal, self.pos):
                self.leaves.append(Leaf(path, val, self.pos, self.pos + len(literal), json_type))
                self.pos += len(literal)
                return
        match = _NUMBER.match(self.data, self.pos)
        if not match:
            raise self.fail("unexpected character")
        number: Any = json.loads(match.group().decode("ascii"))
        self.leaves.append(Leaf(path, number, match.start(), match.end(), "number"))
        self.pos = match.end()


def parse_leaves(response: str | bytes) -> list[Leaf]:
    """Every leaf of the JSON ``response`` with its path and content byte span, in text order."""
    data = response.encode("utf-8") if isinstance(response, str) else response
    scanner = _Scanner(data)
    scanner.value("")
    scanner.ws()
    if scanner.pos != len(data):
        raise scanner.fail("trailing text")
    return scanner.leaves


# --- JSON Schema: the enum choices of a leaf ----------------------------------------------------

_PATH_PART = re.compile(r"\.?([^.\[\]]+)|\[(\d+)\]")


def _deref(schema: Any, root: Mapping[str, Any], depth: int = 0) -> Any:
    while isinstance(schema, Mapping) and "$ref" in schema and depth < 50:
        ref = str(schema["$ref"])
        if not ref.startswith("#/"):
            return {}
        node: Any = root
        for part in ref[2:].split("/"):
            node = node.get(part.replace("~1", "/").replace("~0", "~"), {})
        schema = node
        depth += 1
    return schema


def _branches(schema: Any, root: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The schema split into its alternatives (``$ref`` resolved, ``anyOf``/``oneOf``/``allOf``
    flattened)."""
    schema = _deref(schema, root)
    if not isinstance(schema, Mapping):
        return []
    out: list[Mapping[str, Any]] = []
    nested = False
    for key in ("anyOf", "oneOf", "allOf"):
        for sub in schema.get(key) or []:
            nested = True
            out.extend(_branches(sub, root))
    own = {k: v for k, v in schema.items() if k not in ("anyOf", "oneOf", "allOf")}
    if not nested or any(k in own for k in ("type", "enum", "const", "properties", "items")):
        out.append(own)
    return out


def _child(schema: Any, root: Mapping[str, Any], key: str | int) -> list[Mapping[str, Any]]:
    children: list[Mapping[str, Any]] = []
    for branch in _branches(schema, root):
        if isinstance(key, int):
            prefix = branch.get("prefixItems")
            if isinstance(prefix, list) and key < len(prefix):
                children.append(prefix[key])
            elif isinstance(branch.get("items"), Mapping):
                children.append(branch["items"])
        else:
            props = branch.get("properties")
            if isinstance(props, Mapping) and key in props:
                children.append(props[key])
            elif isinstance(branch.get("additionalProperties"), Mapping):
                children.append(branch["additionalProperties"])
    return children


def _enum_choices(root: Mapping[str, Any], path: str) -> list[str] | None:
    """The valid choices of the leaf at ``path``, or None when it is not an enum (free text, or
    the schema does not say)."""
    nodes: list[Any] = [root]
    for match in _PATH_PART.finditer(path):
        key: str | int = int(match.group(2)) if match.group(2) is not None else match.group(1)
        nodes = [child for node in nodes for child in _child(node, root, key)]
        if not nodes:
            return None
    choices: list[str] = []
    for node in nodes:
        for branch in _branches(node, root):
            if "const" in branch:
                if branch["const"] is not None:
                    choices.append(str(branch["const"]))
            elif "enum" in branch:
                choices.extend(str(c) for c in branch["enum"] if c is not None)
            elif branch.get("type") == "null":
                continue
            else:
                return None  # a free branch: not an enum
    return list(dict.fromkeys(choices)) or None


def _schema_dict(json_schema: Mapping[str, Any] | type[BaseModel]) -> Mapping[str, Any]:
    if isinstance(json_schema, type) and issubclass(json_schema, BaseModel):
        return json_schema.model_json_schema(by_alias=True)
    return json_schema


# --- tokens → response bytes --------------------------------------------------------------------


def _token_bytes(entry: Mapping[str, Any]) -> bytes:
    raw = entry.get("bytes")
    if raw is not None:
        return bytes(raw)
    return str(entry.get("token", "")).encode("utf-8")


def _token_text(entry: Mapping[str, Any]) -> str:
    token = entry.get("token")
    if isinstance(token, str):
        return token
    return _token_bytes(entry).decode("utf-8", "replace")


def _prob(entry: Mapping[str, Any]) -> float:
    logprob = entry.get("logprob")
    if not isinstance(logprob, int | float) or math.isnan(logprob):
        raise MappingError("a token has no logprob")
    return min(1.0, math.exp(logprob))


def response_offset(logprobs: Sequence[Mapping[str, Any]], response_text: str) -> int:
    """Byte offset of the response inside the joined token bytes (the response is the suffix;
    thinking + ``</think>`` come before it). Raises :class:`MappingError` if it is not a suffix."""
    joined = b"".join(_token_bytes(e) for e in logprobs)
    response = response_text.encode("utf-8")
    offset = len(joined) - len(response)
    if offset < 0 or joined[offset:] != response:
        raise MappingError("the joined logprob tokens do not end with the response text")
    return offset


# --- confidence per leaf ------------------------------------------------------------------------


def _covering(starts: Sequence[int], ends: Sequence[int], lo: int, hi: int) -> tuple[int, int]:
    """[first, last + 1) of the tokens overlapping bytes [lo, hi); for an empty span, the token
    holding byte ``lo`` (the closing quote of an empty string)."""
    if hi == lo:
        hi = lo + 1
    idx = [i for i in range(len(starts)) if starts[i] < hi and ends[i] > lo]
    if not idx:
        raise MappingError(f"no token covers bytes {lo}..{hi}")
    return idx[0], idx[-1] + 1


def _enum_margin(entry: Mapping[str, Any], choices: Sequence[str]) -> float | None:
    """The margin at the value's first token, or None if that token is not itself a choice."""
    chosen = _token_text(entry).strip(_TRIM)
    if chosen not in choices:
        return None
    candidates: dict[str, tuple[str, float]] = {_token_text(entry): (chosen, _prob(entry))}
    for alt in entry.get("top_logprobs") or []:
        text = _token_text(alt)
        choice = text.strip(_TRIM)
        if text not in candidates and choice in choices:
            candidates[text] = (choice, _prob(alt))
    mass: dict[str, float] = dict.fromkeys(choices, 0.0)
    for choice, p in candidates.values():
        mass[choice] += p  # distinct tokens spelling the same choice add up
    total = sum(mass.values())
    if total <= 0:
        return 0.0
    best_other = max((p for c, p in mass.items() if c != chosen), default=0.0)
    return max(0.0, min(1.0, (mass[chosen] - best_other) / total))


def logprob_confidences(
    response_text: str,
    logprobs: Sequence[Mapping[str, Any]] | None,
    json_schema: Mapping[str, Any] | type[BaseModel],
) -> dict[str, FieldConfidence]:
    """Per-leaf confidences from logprobs (``low_trust=False``). Raises :class:`MappingError`
    when the logprobs are missing or empty or cannot be mapped onto the response."""
    if not logprobs:
        raise MappingError("no logprobs")
    root = _schema_dict(json_schema)
    offset = response_offset(logprobs, response_text)
    starts: list[int] = []
    ends: list[int] = []
    cursor = 0
    for entry in logprobs:
        starts.append(cursor)
        cursor += len(_token_bytes(entry))
        ends.append(cursor)
    out: dict[str, FieldConfidence] = {}
    for leaf in parse_leaves(response_text):
        first, last = _covering(starts, ends, leaf.start + offset, leaf.end + offset)
        probs = [_prob(logprobs[i]) for i in range(first, last)]
        seq_prob = math.prod(probs)
        choices = _enum_choices(root, leaf.path)
        kind: Kind
        if choices is not None and leaf.json_type == "null":
            kind, confidence = "null", probs[0]
        elif choices is not None and leaf.json_type == "string":
            margin = _enum_margin(logprobs[first], choices)
            if margin is None:
                kind, confidence = "enum_multitoken", min(probs)
            else:
                kind, confidence = "enum", margin
        else:
            kind = "text" if leaf.json_type == "string" else leaf.json_type
            confidence = min(probs)
        out[leaf.path] = FieldConfidence(
            value=leaf.value,
            confidence=confidence,
            kind=kind,
            token_span=(first, last),
            seq_prob=seq_prob,
            low_trust=False,
            byte_span=(leaf.start, leaf.end),
        )
    return out


# --- fallbacks ----------------------------------------------------------------------------------


def _leaf_kind(leaf: Leaf, root: Mapping[str, Any]) -> Kind:
    if leaf.json_type == "string":
        return "enum" if _enum_choices(root, leaf.path) is not None else "text"
    return leaf.json_type


def _self_reported(parsed: Any, path: str) -> float:
    """The nearest ``confidence`` number in the leaf's object or an enclosing one."""
    parts = [
        m.group(1) if m.group(2) is None else int(m.group(2)) for m in _PATH_PART.finditer(path)
    ]
    nodes: list[Any] = [parsed]
    for part in parts[:-1]:
        node = nodes[-1]
        try:
            nodes.append(node[part])
        except (KeyError, IndexError, TypeError):
            break
    for node in reversed(nodes):
        value = node.get("confidence") if isinstance(node, Mapping) else None
        if isinstance(value, int | float) and not isinstance(value, bool):
            return max(0.0, min(1.0, float(value)))
    return 0.0


async def fallback_confidences(
    response_text: str,
    json_schema: Mapping[str, Any] | type[BaseModel],
    fallback: FallbackName | None,
    *,
    resample: Resample | None = None,
) -> dict[str, FieldConfidence]:
    """Per-leaf confidences without logprobs (llm-design §6); every result has ``low_trust=True``.
    ``fallback=None`` (not configured) means ``"none"``."""
    root = _schema_dict(json_schema)
    leaves = parse_leaves(response_text)
    method = fallback or "none"
    scores: dict[str, float]
    if method == "resample":
        if resample is None:
            raise ValueError("confidence.fallback = 'resample' needs a resample callable")
        second = await resample()
        try:
            text = second if isinstance(second, str) else json.dumps(second, ensure_ascii=False)
            other = {leaf.path: leaf.value for leaf in parse_leaves(text)}
        except MappingError:
            other = {}
        scores = {
            leaf.path: 1.0 if leaf.path in other and _same(other[leaf.path], leaf.value) else 0.0
            for leaf in leaves
        }
    elif method == "self_report":
        parsed = json.loads(response_text)
        scores = {leaf.path: _self_reported(parsed, leaf.path) for leaf in leaves}
    elif method == "none":
        scores = {leaf.path: 0.0 for leaf in leaves}
    else:
        raise ValueError(f"unknown confidence fallback: {fallback!r}")
    return {
        leaf.path: FieldConfidence(
            value=leaf.value,
            confidence=scores[leaf.path],
            kind=_leaf_kind(leaf, root),
            token_span=None,
            seq_prob=None,
            low_trust=True,
            byte_span=(leaf.start, leaf.end),
        )
        for leaf in leaves
    }


def _same(a: Any, b: Any) -> bool:
    return type(a) is type(b) and a == b


# --- entry points -------------------------------------------------------------------------------


async def field_confidences(
    result: _HasLogprobs | tuple[str, Sequence[Mapping[str, Any]] | None],
    json_schema: Mapping[str, Any] | type[BaseModel],
    *,
    fallback: FallbackName | None = None,
    resample: Resample | None = None,
) -> dict[str, FieldConfidence]:
    """Confidence for every leaf of a call's JSON response, keyed by path.

    ``result`` is a :class:`~etach.llm.client.CallResult` (``raw_text`` + ``logprobs``) or a
    ``(response_text, logprobs)`` pair. ``json_schema`` is the schema the model was given (a dict,
    or the pydantic class, exported by alias). ``fallback`` is ``config.confidence.fallback``
    (None = ``"none"``); it is used only when the logprobs are missing or cannot be mapped.
    """
    if isinstance(result, tuple):
        response_text, logprobs = result
    else:
        response_text, logprobs = result.raw_text, result.logprobs
    try:
        return logprob_confidences(response_text, logprobs, json_schema)
    except MappingError:
        return await fallback_confidences(response_text, json_schema, fallback, resample=resample)


def answer_path(question_id: str, index: int = 0) -> str:
    """The path of a reading's value in a ``read_answers_schema`` response."""
    return f"answers.{question_id}[{index}].value"


def answer_confidence(
    confidences: Mapping[str, FieldConfidence], question_id: str, index: int = 0
) -> FieldConfidence:
    """The confidence of reading ``index`` (0 = first, 1 = second) of ``question_id`` in a
    ``read_answers_page`` call (the ``read_answers_schema`` shape). Raises ``KeyError`` when the
    call has no such reading."""
    return confidences[answer_path(question_id, index)]
