"""The one-time first-start pass of migration 0011 over the stored tests (data-model v1.21,
step 22.5.2).

It runs only while ``test_text_pending`` holds its row and removes the row in the same
transaction, so a second start changes nothing. For every stored test:

- option labels that still carry punctuation or are not plain letters ("A.", "A..", a fullwidth
  or Cyrillic capital) become the bare capital (``renumber.clean_option_label``); such a label made
  the test text read "A.." with the option's text on the next line (comment 1);
- an untitled section (empty, or only a numeral) takes its title from its section skill (D2,
  ``etach.domain.section_titles``); ``mixed`` and titles with words are left alone.

A test whose content changed is saved through ``points.save_content`` (as the 22.4.4 pass does), and
an open ``validator_failed`` item of a test whose content now validates is closed (``fixed``).
"""

from __future__ import annotations

import json
import sqlite3

from etach.domain.models import TestContent
from etach.domain.renumber import clean_option_labels
from etach.domain.section_titles import fill_titles
from etach.domain.validators import validate_content
from etach.store.db import now_iso, transaction
from etach.store.repos import points as points_repo
from etach.store.repos import tests as tests_repo

__all__ = ["clean_content", "run_test_text_pass"]


def clean_content(content: TestContent) -> TestContent:
    """The content with clean option labels and the untitled sections titled."""
    sections = [
        s.model_copy(
            update={
                "groups": [
                    g.model_copy(
                        update={
                            "questions": [
                                q.model_copy(update={"options": clean_option_labels(q.options)})
                                for q in g.questions
                            ]
                        }
                    )
                    for g in s.groups
                ]
            }
        )
        for s in content.sections
    ]
    return fill_titles(content.model_copy(update={"sections": sections}))


def run_test_text_pass(conn: sqlite3.Connection) -> bool:
    """The first-start pass (see the module docstring). Returns whether it ran."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'test_text_pending'"
    ).fetchone()
    if not exists or not conn.execute("SELECT 1 FROM test_text_pending").fetchone():
        return False
    with transaction(conn):
        for (test_id,) in conn.execute("SELECT id FROM tests ORDER BY id").fetchall():
            test = tests_repo.get_test(conn, test_id)
            if test is None:  # pragma: no cover - the id was just listed
                continue
            cleaned = clean_content(test.content)
            if cleaned == test.content:
                continue
            content = points_repo.save_content(conn, test_id, cleaned)
            if not validate_content(content, test.meta.omitted_sections):
                conn.execute(
                    "UPDATE review_items SET status = 'fixed', resolution = ?, resolved_at = ?"
                    " WHERE test_id = ? AND kind = 'validator_failed' AND status = 'open'"
                    " AND attempt_id IS NULL",
                    (json.dumps({"action": "test_text_pass"}), now_iso(), test_id),
                )
        conn.execute("DELETE FROM test_text_pending")
    return True
