# ruff: noqa: E501  (the route table is copied verbatim from llm-design §2)
"""R12.1: the OpenAPI paths and methods equal llm-design §2's route table.

``ROUTE_TABLE`` is the table copied verbatim from docs/llm-design.md §2 ("API (sidecar):
complete route inventory"). When the table changes, copy it again; do not edit rows here.
"""

from __future__ import annotations

import json

from etach.api.app import openapi_text

ROUTE_TABLE = r"""
| Method | Path | Purpose |
|---|---|---|
| POST | `/files` | Upload a dropped file → `file_id`; for a PDF/DOCX, the list of pages as `PageInput`s (image `file_id`, plus `text_file_id` for text layers and DOCX text) |
| GET | `/files/{id}` | File bytes (`?thumb=1` for a thumbnail): photo check, Review page images |
| POST | `/threads` | Create a thread |
| GET | `/threads` | List threads with the student group, `kind`, last activity and `open_review_count` (sidebar; v4.22) |
| GET | `/threads/{id}` | Thread, current attempt, test; `other_thread_count`: how many other threads use the test (v4.41) |
| DELETE | `/threads/{id}` | Delete the thread for good, with what data-model §5.7 lists; 409 while it has a running run (v4.26) |
| PATCH | `/threads/{id}` | Rename a thread: `{title}` (not blank) (v4.19); `{title: null}` goes back to the automatic title (v4.25) |
| GET | `/threads/{id}/messages` | Cards and messages (survive restarts) |
| POST | `/threads/{id}/extract-again` | Extract again: a new extract run on the pages of the thread's last finished extract run, no picked test, `supersedes_attempt_id` = the current attempt; 409 while a run of the thread is active (v4.29). `{mode?}` (v4.41, D8): `replace` saves the new reading into the thread's test (same id, data-model §5.8), `copy` makes a new test for this thread; without a mode, `replace` when no other thread uses the test, else 409 asking for one. `again_test_id` = the thread's test, left out of `compare_bank` either way |
| POST | `/threads/{id}/runs` | Start a run: `{kind:"extract", input: ExtractInput}` (Run) or `{kind:"grade", input: GradeInput}` (Grade) |
| GET | `/runs/active` | Running, queued, **stopped and interrupted** runs, with the current step (running indicator; Resume/Discard after a restart) |
| GET | `/runs/{id}` | Run status + steps (+ task names of the model calls) |
| POST | `/runs/{id}/stop` | D22 |
| POST | `/runs/{id}/resume` | D22 |
| POST | `/runs/{id}/discard` | D22 |
| GET | `/tests` | `?q=` search (English display names; the test id, v4.40), list with attempt counts, `open_review_count` (v4.22) and `created_at` (v4.40); merged tests excluded |
| GET | `/tests/{id}` | Test metadata + content, plus `picture_paths` (`file_id` → stored path `files/ab/<id>.<ext>`) for the D11 placeholders (v4.10), and `pages` / `key_pages` (`{page_no, file_id}`, the original photos; v4.21), `content_text` (the test as text, data-model §2.3a) and `review` (its open items; v4.22); `points_each` (10 ÷ graded questions, unrounded; null with none; v4.41) |
| PATCH | `/tests/{id}` | Edit metadata or content (through `write_test_meta`; content edits are re-validated). `{content_text, drop_confirmed?}` reads the text back (data-model §2.3a): 422 with line-numbered errors, or with the ids of questions that would be dropped and have keys or answers unless they are in `drop_confirmed`; a save settles Review items (§5.3) (v4.22). 422 bodies: `{message, errors: [{line, message}]}` or `{message, drops: [question ids]}`; success returns the test as `GET /tests/{id}` does (v4.22.1) |
| GET | `/tests/{id}/keys` | Key rows |
| GET | `/tests/{id}/delete-preview` | What deleting the test removes: the threads (id, shown title) and attempt count (v4.26) |
| DELETE | `/tests/{id}` | Delete the test for good, with what data-model §5.7 lists; 409 while a run uses it (v4.26) |
| POST | `/tests/{id}/export` | `{what: "test" \| "key"}`: save the clean test or its key as DOCX into `<app>\exports\`; returns `{path, file_name}` (v4.23) |
| PUT | `/tests/{id}/keys/{question_id}` | Edit or verify a key (triggers re-grade fan-out) |
| DELETE | `/tests/{id}/keys/{question_id}` | Delete a key and its explanations; settles the question's open `uncertain_key` items and notes `regrade_pending`, no run starts (refinements D7) |
| POST | `/tests/{id}/merge` | `{into, alignment}`: merge (also used by Review) |
| GET | `/attempts/{id}` | Attempt, answers, pages |
| PATCH | `/attempts/{id}` | The date taken: `{taken_on}` (a date; D11a), version+1, no run (v4.42) |
| PUT | `/attempts/{id}/student` | Student chip: assign an existing student or create one from `student_name_read` |
| PUT | `/attempts/{id}/answers/{question_id}` | Correct a reading (`teacher_override`, version+1, re-grade) |
| GET | `/attempts/{id}/report` | The grade report (`grade_reports` + verdicts + explanations) |
| POST | `/attempts/{id}/report/export` | Save the grade report as DOCX into `<app>\exports\`; returns `{path, file_name}`; 409 if the attempt is not graded (v4.23) |
| GET | `/occasions` | The occasion list in order: code, label, short name, built-in, test count (v4.33) |
| POST | `/occasions` | `{label, short_name}`: add a teacher occasion (v4.33) |
| PATCH | `/occasions/{code}` | `{label?, short_name?, position?}`: rename or move; remakes automatic Test names (v4.33) |
| DELETE | `/occasions/{code}` | Delete a teacher occasion; 409 while a test uses it or for a built-in (v4.33) |
| POST | `/tests/{id}/regrade` | Queue 1 grade run (`key_verified`) per graded attempt of the test and clear `regrade_pending`; returns the run ids (empty when nothing is pending or nothing is graded) (v4.36) |
| GET | `/schools` | The school list in order: id, name, number of tests and students using it (v4.34) |
| POST | `/schools` | `{name}`: add a school (409 if the name exists, case-insensitive) (v4.34) |
| PATCH | `/schools/{id}` | `{name?, position?}`: rename or move; a rename updates tests and students and remakes automatic Test names (v4.34) |
| DELETE | `/schools/{id}` | Delete a school; 409 while a test or student uses it (v4.34) |
| GET | `/series` | The series list in order: id, name, number of tests using it (v4.41) |
| POST | `/series` | `{name}`: add a series (409 if the name exists, case-insensitive) (v4.41) |
| PATCH | `/series/{id}` | `{name?, position?}`: rename or move; a rename updates the tests' series and remakes automatic Test names (v4.41) |
| DELETE | `/series/{id}` | Delete a series; 409 while a test uses it (v4.41) |
| GET | `/students` | `?q=` search students; each with `class_name` and `thread_count` (v4.26) |
| GET | `/students/{id}/delete-preview` | The threads deleting the student removes (v4.30) |
| DELETE | `/students/{id}` | Delete the student with their threads, data-model §5.7 (v4.30) |
| POST | `/tests/{id}/copy-details` | `{from_test_id}`: copy occasion, term, school, source, year (data-model v1.14) (v4.30) |
| GET | `/students/{id}` | The student and their threads (`id`, shown title, test, last activity) (v4.26); `skills`: each skill with its trajectory label, level, weak and held back, and per-paper results (date taken, share) (D11b; v4.45) |
| POST | `/students` | Create a student |
| PATCH | `/students/{id}` | Edit a student: `{full_name?, class_name?, school?}`; `name_search` is recomputed (v4.19); a new school joins the school list (v4.34.1) |
| GET | `/review` | `?status=open`: the queue |
| GET | `/review/count` | Review · N |
| POST | `/review/{id}/resolve` | `{action, value}`: the resolution dispatch (data-model §5.3) |
| GET | `/system/status` | Ollama version, models present, other-Ollama warning, power source, keep-awake, sidecar version, replay flag |
| GET | `/settings` | Model tag per role, data folder, log retention |
| PUT | `/settings` | Update settings (writes `models.toml`) |
| POST | `/settings/models/pull` | Download the configured models (`ollama pull`; progress over SSE) |
| GET | `/models` | Installed Ollama models: `name`, `size`, `modified_at`, and the roles that use each (v4.31) |
| POST | `/models/pull` | `{name}`: pull one model; progress events over SSE; cancellable (v4.31) |
| DELETE | `/models/{name}` | Delete an installed model; 409 while a role uses it or a run is active (v4.31) |
| POST | `/maintenance/backup` | `VACUUM INTO` + `files/` → .zip |
| POST | `/maintenance/restore` | Restore a .zip into a new data folder |
| POST | `/maintenance/clear-logs` | `{older_than_days}`: delete old `llm_calls` not referenced by explanations |
| GET | `/events` | SSE: `run.queued`, `run.step_started`, `run.step_done`, `run.progress`, `run.done`, `run.failed`, `run.stopped`, `run.interrupted`, `run.discarded`, `review.changed`, `system.changed`, `models.pull_progress` |
"""

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def table_routes() -> set[tuple[str, str]]:
    rows: set[tuple[str, str]] = set()
    for line in ROUTE_TABLE.strip().splitlines()[2:]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        method, path = cells[0], cells[1].strip("`")
        assert (method, path) not in rows, f"duplicate row {method} {path}"
        rows.add((method, path))
    return rows


def openapi_routes() -> set[tuple[str, str]]:
    schema = json.loads(openapi_text())
    return {
        (method.upper(), path)
        for path, item in schema["paths"].items()
        for method in item
        if method in HTTP_METHODS
    }


def test_table_parses() -> None:
    rows = table_routes()
    assert len(rows) == 65  # refinements D7: DELETE /tests/{id}/keys/{question_id}
    assert ("GET", "/events") in rows


def test_r12_1_openapi_equals_the_route_table() -> None:
    table, app = table_routes(), openapi_routes()
    assert sorted(app - table) == [], "routes the table does not list"
    assert sorted(table - app) == [], "table routes the app does not have"
