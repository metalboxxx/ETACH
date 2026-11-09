"""Repositories: one module per table group, taking and returning the ``etach.domain.models``
classes (data-model §3). Every write runs in ``etach.store.db.transaction``, so a caller can group
several repository calls in one outer transaction.

students · tests (+ test_pages, question_tags) · keys (answer_keys) · explanations ·
attempts (+ attempt_pages, answers, grade_reports) · threads (+ messages) ·
runs (+ steps, llm_calls) · review (review_items) · files (rows only)
"""
