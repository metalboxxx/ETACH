"""Text normalization (data-model §2.5): the one value normalization plus accent folding.

- ``value_norm``: the single normalization for stored/compared values (answers, keys, fingerprints).
- ``fold``: accent-stripped text (``đ`` → ``d``) for search, similarity and names.
- ``name_search``: ``fold`` + lowercase + collapsed spaces (``students.name_search``).

Pure: no I/O.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["collapse_spaces", "fold", "name_search", "value_norm"]

_SPACES = re.compile(r"\s+")
_SINGLE = (0x2018, 0x2019, 0x201A, 0x201B, 0x2032)  # curly/low/reversed single, prime
_DOUBLE = (0x201C, 0x201D, 0x201E, 0x201F, 0x2033)  # curly/low/reversed double, double prime
_QUOTES = {cp: "'" for cp in _SINGLE} | {cp: '"' for cp in _DOUBLE}


def collapse_spaces(s: str) -> str:
    """Trim and collapse every run of whitespace to one space."""
    return _SPACES.sub(" ", s).strip()


def value_norm(s: str) -> str:
    """Lowercase, trim, collapse whitespace, curly → straight quotes (NFC first)."""
    return collapse_spaces(unicodedata.normalize("NFC", s).translate(_QUOTES).lower())


def fold(s: str) -> str:
    """Strip accents; ``đ``/``Đ`` → ``d``/``D``. Case and spacing are kept."""
    s = s.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", s)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return unicodedata.normalize("NFC", stripped)


def name_search(s: str) -> str:
    """The search form of a name: ``fold`` + lowercase + collapsed spaces."""
    return collapse_spaces(fold(s).lower())
