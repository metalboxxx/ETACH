"""Student matching by the name read on the test (plan R8.1.9, step 9 ``save``).

The read name and each profile compare in their ``name_search`` form (accent-folded, lowercase,
collapsed spaces), exactly. Several matching profiles → the class read breaks the tie (also in
``name_search`` form); still ambiguous, or no class → None. No name → None.

Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from etach.domain.normalize import name_search

__all__ = ["match_student"]


def _search_form(student: Any) -> str:
    stored = getattr(student, "name_search", None)
    return stored if stored else name_search(str(getattr(student, "full_name", "") or ""))


def match_student(
    name_read: str | None, class_read: str | None, students: Iterable[Any]
) -> str | None:
    """The id of the one student whose name matches ``name_read``, or None.

    ``students`` are ``Student`` rows or any objects with ``id``, ``name_search`` (or
    ``full_name``) and ``class_name``.
    """
    if not name_read or not name_search(name_read):
        return None
    wanted = name_search(name_read)
    matches = [s for s in students if _search_form(s) == wanted]
    if len(matches) == 1:
        return str(matches[0].id)
    if len(matches) > 1 and class_read and name_search(class_read):
        klass = name_search(class_read)
        same_class = [
            s for s in matches if name_search(str(getattr(s, "class_name", "") or "")) == klass
        ]
        if len(same_class) == 1:
            return str(same_class[0].id)
    return None
