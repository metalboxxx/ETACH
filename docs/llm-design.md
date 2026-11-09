# LLM Workflow Design — ETACH

| | |
|---|---|
| Version | **v4.60.3** (2026-11-09) |
| Companion to | [`PRD.md`](PRD.md) (what) · [`initial-plan/plan.md`](initial-plan/plan.md) (order + verification) · [`data-model.md`](data-model.md) (classes, tables, write rules). Each plan pins the versions it builds on in its "Based on" line |
| Worked example | `D:\Study\Pho Thong\Lop8-HkI\Lop8-HKI-De1 (1..3).jpg` ("ĐỀ CUỐI KÌ I LỚP 8 (K)", filled by a student) |

### Changelog
| Version | Date | Change |
|---|---|---|
| **v4.60.3** | 2026-11-09 | Patch, teacher (maintenance): §2 points to structure.md §3 for the sidecar's folders instead of listing them; the changelog rows of the initial plan moved to `initial-plan/changelogs.md` |
| v4.60.2 | 2026-11-09 | Patch, teacher: the code names follow the app's name: the `etach` package and CLI, the frozen `etach-sidecar.exe`, `ETACH_*` environment variables (PRD v9.1). No workflow or route change |
| v4.60.1 | 2026-11-03 | Patch, after the initial plan: the title no longer names the old app; the finished initial plan moved to `docs/initial-plan/`. No workflow change |

Earlier rows (2026-09-26 to 2026-11-01, the initial plan) are in [`initial-plan/changelogs.md`](initial-plan/changelogs.md).

---

## 1. Principles

| # | Principle | In practice |
|---|---|---|
| P1 | **No interaction during a run.** | Teacher input happens before Run (photo check) and after it (Grade, Review, a glance before printing). Doubt becomes `?` and Review items. Unreadable text becomes `???` and an `unreadable_text` item (D25). |
| P2 | **Code for everything deterministic.** | Page order and rotation (from the teacher), renumbering, points, header patterns, key-to-question mapping, text comparison, scoring. |
| P3 | **Small, conditioned model calls.** | One page per call; answer reading is given the known question list; JSON schemas with enums. |
| P4 | **Expensive work once per test.** | Transcription, key, skill tags and explanations are stored on the bank test and reused. |
| P5 | **Confidence from token probabilities** (D20). | Not from the model rating itself. |
| P6 | **Model-agnostic.** | Roles and adapters are in config; no model name appears in the graph code. |
| P7 | **No change without a measurement.** | Eval harness with tuning and held-out fixtures. |
| P8 | **Interruptible and idempotent.** | Checkpoint after each node. Intermediate nodes write only to state and `llm_calls`. **Domain tables are written only in `save`, and `save` is idempotent** (data-model §5.2). |

---

## 2. Process architecture

```
┌──────────────── Tauri app (Rust, thin) ────────────────┐
│  window · notifications · file dialogs                 │
│  starts + owns (Windows Job Object):                   │
│    ├─ Python sidecar  (FastAPI on 127.0.0.1:<rand>, token; release builds run the frozen
│    │                   PyInstaller folder <app>\sidecar\etach-sidecar.exe serve with ETACH_APP_DIR=<app>)
│    (every path lives inside the one app folder, default D:\ETACH; nothing in AppData;
│     the WebView2 user data folder is set to <app>\webview)
│    └─ ollama serve    (127.0.0.1:<rand>, OLLAMA_MODELS=<app>\data\models, MAX_LOADED_MODELS=1, FLASH_ATTENTION=1, KV_CACHE_TYPE=q8_0,
│                        CUDA_VISIBLE_DEVICES=<the NVIDIA GPU>)
│                        (Ollama missing: no ollama serve; the sidecar reports unreachable and the
│                         first-run screen shows instead of the shell stopping)
└──────────────┬─────────────────────────────────────────┘
               │ HTTP + SSE
┌──────────────▼───────── React frontend ────────────────┐
│ threads · photo check · running indicator · cards · Review · Tests
└────────────────────────────────────────────────────────┘
```

The sidecar's folders and modules are mapped in [`structure.md`](structure.md) §3.

### API (sidecar): complete route inventory
Every route needs `Authorization: Bearer <token>`, except that **`GET /files/{id}` and `GET /events` also accept `?token=<token>`**, because `<img>` and `EventSource` cannot send headers. The server binds to 127.0.0.1 only. The implementation plan's R12.1 checks the OpenAPI export against this exact table. **CORS** (v4.9): the sidecar answers cross-origin requests only from the app's own origins — Tauri (`tauri://localhost`, `http(s)://tauri.localhost`) and loopback (`http://127.0.0.1:*`, `http://localhost:*`, for development and E2E); it allows the `Authorization` header and preflight. The token is still required on every route.

| Method | Path | Purpose |
|---|---|---|
| POST | `/files` | Upload a dropped file → `file_id`; for a PDF/DOCX, the list of pages as `PageInput`s (image `file_id`, plus `text_file_id` for text layers and DOCX text) |
| GET | `/files/{id}` | File bytes (`?thumb=1` for a thumbnail): photo check, Review page images |
| POST | `/threads` | Create a thread |
| GET | `/threads` | List threads with the student group, `kind`, last activity and `open_review_count` (sidebar; v4.22) |
| GET | `/threads/{id}` | Thread, current attempt, test; `other_thread_count`: how many other threads use the test (v4.41) |
| DELETE | `/threads/{id}` | Delete the thread for good, with what data-model §5.7 lists; 409 while it has a running run (v4.26); its `after_extract` key runs, when they are its only unfinished runs, are discarded first (v4.54, D12) |
| PATCH | `/threads/{id}` | Rename a thread: `{title}` (not blank) (v4.19); `{title: null}` goes back to the automatic title (v4.25) |
| GET | `/threads/{id}/messages` | Cards and messages (survive restarts) |
| POST | `/threads/{id}/extract-again` | Extract again: a new extract run on the pages of the thread's last finished extract run, no picked test, `supersedes_attempt_id` = the current attempt; 409 while a run of the thread is active (v4.29), except its `after_extract` key runs, which are discarded first (v4.54, D12). `{mode?}` (v4.41, D8): `replace` saves the new reading into the thread's test (same id, data-model §5.8), `copy` makes a new test for this thread; without a mode, `replace` when no other thread uses the test, else 409 asking for one. `again_test_id` = the thread's test, left out of `compare_bank` either way |
| POST | `/threads/{id}/runs` | Start a run: `{kind:"extract", input: ExtractInput}` (Run) or `{kind:"grade", input: GradeInput}` (Grade) |
| GET | `/runs/active` | Running, queued, **stopped and interrupted** runs, with the current step (running indicator; Resume/Discard after a restart). v4.53: a thread's key run is its grade run with `input.reason` `after_extract` (and `input.attempt_id` null) |
| GET | `/runs/{id}` | Run status + steps (+ task names of the model calls) |
| POST | `/runs/{id}/stop` | D22 |
| POST | `/runs/{id}/resume` | D22 |
| POST | `/runs/{id}/discard` | D22 |
| GET | `/tests` | `?q=` search (English display names; the test id, v4.40), list with attempt counts, `open_review_count` (v4.22) and `created_at` (v4.40); merged tests excluded |
| GET | `/tests/{id}` | Test metadata + content, plus `picture_paths` (`file_id` → stored path `files/ab/<id>.<ext>`) for the D11 placeholders (v4.10), and `pages` / `key_pages` (`{page_no, file_id}`, the original photos; v4.21), `content_text` (the test as text, data-model §2.3a) and `review` (its open items; v4.22); `points_each` (10 ÷ graded questions, unrounded; null with none; v4.41) |
| PATCH | `/tests/{id}` | Edit metadata or content (through `write_test_meta`; content edits are re-validated). `{content_text, drop_confirmed?}` reads the text back (data-model §2.3a): 422 with line-numbered errors, or with the ids of questions that would be dropped and have keys or answers unless they are in `drop_confirmed`; a save settles Review items (§5.3) (v4.22). 422 bodies: `{message, errors: [{line, message}]}` or `{message, drops: [question ids]}`; success returns the test as `GET /tests/{id}` does (v4.22.1) |
| GET | `/tests/{id}/keys` | Key rows |
| GET | `/tests/{id}/delete-preview` | What deleting the test removes: the threads (id, shown title) and attempt count (v4.26) |
| DELETE | `/tests/{id}` | Delete the test for good, with what data-model §5.7 lists; 409 while a run uses it (v4.26); the `after_extract` key runs, when they are the only unfinished runs the delete touches, are discarded first (v4.55, D14) |
| POST | `/tests/{id}/export` | `{what: "test" \| "key"}`: save the clean test or its key as DOCX into `<app>\exports\`; returns `{path, file_name}` (v4.23) |
| PUT | `/tests/{id}/keys/{question_id}` | Edit or verify a key (triggers re-grade fan-out) |
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
| DELETE | `/students/{id}` | Delete the student with their threads, data-model §5.7 (v4.30); 409 while a run in one of those threads is unfinished, except the `after_extract` key runs: when they are the only ones, they are discarded first (v4.55, D14) |
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

**Run progress** (v4.20, step 22.1.3). Each graph has a fixed, ordered list of **stages**, each a group of nodes with a plain-words name:
- extract: Preparing the photos (`prepare_pages`) · Reading the key (`read_key_pages`) · Reading the test (`load_bank_test`, `read_header`, `sanity_check`, `transcribe_page`, `retranscribe_tiles`, `merge_and_normalize`, `compare_bank`, `map_key`) · Reading the answers (`read_answers_page`, `resolve_answers`) · Saving (`save`);
- grade: Getting ready (`load_context`) · Checking the key (`ai_key_fast`, `verify_gate`, `verify_key`) · Grading (`tag_skills`, `grade`, `judge_rewrites`; `difficulty_notes` removed in v4.43) · Explaining mistakes (`explain`) · Updating student ability (`weak_points`; v4.24) · Saving (`save`). The key run (v4.53) uses the same stages; it ends after `tag_skills` (shown under "Grading"), so the stages after it count as done.

`run.step_started` and `run.progress` add `stage` (1-based), `stages`, `stage_label` and `percent` (0–100); `run.progress` also names the `unit` it counts (`page`, `section` or `question`), and `run.done` carries `percent` 100. `percent` gives each stage an equal share and, inside a stage, the `done/total` of its latest `report_progress`; a stage the run skips counts as done, and `percent` never goes down within a run (a Resume continues from the stopped value). While a model call streams, the client publishes `run.progress` with `tokens` (output tokens so far) at least every 5 s, so a long call still shows activity. **v4.24:** these heartbeats start when the call starts (with `tokens` 0 until the first token), so the quiet wait before the first token also shows activity; the progress text names the item being worked on (`current` = done + 1 while it runs, "Reading page 3 of 4"), and a second pass over a page (`retranscribe_tiles`) sets `again: true` with that page's number ("Checking page 2 again") instead of restarting the count. `GET /runs/active` gives each run's latest `stage`, `stages`, `stage_label` and `percent`, so the bar is right after a restart. The UI never shows node names.

**Typed pages and sentence openings (v4.32, step 22.3.6).** A born-digital page (D26) skips `transcribe_page`: a
text-only task, `structure_text_page` (the reasoning role; same output schema as `transcribe_page`; think off; its own
cassette task name), receives the page's exact text (the text layer or DOCX text) and returns the page's sections and
questions; pictures on the page are attached as D11 placeholders as before. `transcribe_page` and `structure_text_page`
both ask for `answer_start` on `sentence` questions (v4.42; was rewrite / combine): the words printed to start the answer line, or null.

**Typed PDFs joined (v4.46, step 22.5.6, D12).** A typed PDF's page texts are joined and cut with `split_text_page` like a
Word file's text (at section headings, else question starts, never inside a question, at most 6 000 characters), so the
printer's page breaks no longer reach the model. State: `text_pieces` (the pieces, with where each PDF page's text
starts), `absorbed_pages` (PDF pages whose whole text went into an earlier piece; no call of their own) and `placed`
(transcript page → `PiecePages`, given to `merge_pages`): each question gets the PDF page its text starts on, each group
keeps the page its pictures are printed on. Code finds that text (`documents.locate_pages`), matching the model's text
against the PDF text with both folded the same way (v4.46.2: Unicode form, accents and case dropped, curly quotes and
dashes made straight, markdown stars removed, every blank — "____", "……", "...." — with the marker glued to it made one
space, spaces collapsed; a map back to the original offsets keeps pages exact) and word by word (punctuation does not
count). The places are chosen for the whole piece at once (v4.46.3, a global alignment, not a forward search): each group
start (its stimulus's first words), group end (its last words) and question gets scored candidate places, a stem's first
words (stronger the longer the match, stronger again with its number printed just before it, also mid-line), a stem-less
question's marker, only in marker form ("(17)", "[17]", "(Câu 17)", "__(17)__", "17 ____", "17……", "17. (CUE)", or
"17." / "17)" at a line start; "Tom was 17." is not one; a blank glued to it scores higher), and, weakly, a line
starting with the question's number (never an answer-key row "17. B"). A group's end comes after its last stem-less
question and before its other questions, so a gap lies inside its passage and a reading question after it. One
candidate per item, or none, is chosen so that places never go back in document order and the total score is largest,
so one wrong match cannot drag later questions. A question left without a place takes the nearest placed question
before it in its group, else its group's start, else the previous placed question. `structure_text_page`
has one `answer_start` example with "=>" and one with no arrow. A page whose output repeats is cut before the repeat by
code (`renumber.cut_repetition`); a repeat is only a whole block again: questions with the same section (title and
instructions), the same group stimulus and the same number, stem, options and cue, two in a row (or the last
question), or a section repeated with no question of its own. Questions under another heading or stimulus, such as two
passages that both number from 1, are never a repeat. Such a page is cut and flagged with a `validator_failed` item, reason "repeated output" (state
`repeated_pages`). Photos and Word files are unchanged. `read_key_pages` says in one line that explanations on the key
pages are ignored.

**Answer form (v4.42, step 22.5.3, D9).** Both page prompts ask for each question's `answer_form` by the printed
layout, not by what the question tests, one line per form: `choice` (printed lettered options, or a True/False
statement), `word` (one word or a short phrase for a blank, or a cue word to put in the right form), `sentence` (a whole
sentence: rewrite, combine, put words in order, answer a question), `writing` (a paragraph or essay). The part is no
longer than the old type list. The output schema (`QuestionOut`) has `answer_form`, not `type`; `context` is never
asked for: code sets it from the group's stimulus (data-model §2.3b). A `choice` with no options whose instructions or
stem say True/False gets the options `T. True` / `F. False` from code. The worked page example uses the forms.
A mixed file (some pages typed, some scanned) uses each page's own path. Cassettes for the new task are synthetic until
the teacher records one.

### CLI
`etach serve [--replay <cassettes>] [--data <dir>]` (prints `{"port","token"}` as the first stdout line) · `etach run …` · `etach runs stop|resume|discard <id>` · `etach grade --attempt|--test …` · `etach eval --graph extract|grade --set tuning|heldout [--role r=tag] [--rate-explanations]` · `etach record` (records live calls as cassettes) · `etach scrub [--check]` · `etach fixtures manifest` · `etach schema export` · `etach openapi export` · `etach --version`.

### Cassettes (recorded model responses for tests)
- A cassette holds the task, the match key, the response and thinking text, the logprobs and the status. It holds **no images**.
- The match key = the task + a digest of its inputs (page, question IDs, schema). It excludes the prompt hash and the model tag, so prompt tuning and model changes don't break replay.
- Cassettes are recorded live by the teacher (`etach record`) or written synthetically for edge cases.
- They are scrubbed (student name/class → placeholders) and committed under `sidecar/tests/cassettes/`.

**Only one run executes at a time** (one GPU). The others wait in a FIFO queue. Re-grade fan-outs are queued the same way. **v4.53 (step 22.6.4, D4):** so is the key run an extraction's `save` queues (§5 "The key run"): after every `done` run the manager loads the `queued` rows that are not in its queue yet (`poke`, publishing `run.queued`), so the key run starts right after its extraction.

---

## 3. Model-agnostic LLM client

### 3.1 Roles in config
```toml
# <data>/models.toml
[roles.vision]
model   = "numind/nuextract3:Q6_K"
adapter = "nuextract"
options = { num_ctx = 16384, temperature = 0, seed = 42 }
think   = false                # NuMind recommends thinking off (repetition loops)
adapter_options = { also_format = true }   # template + `format`: identical output, Phase 0 item 2

[roles.reasoning]
model   = "qwen3.5:4b"         # placeholder until the teacher's small-model tests pick one
adapter = "chat"
options = { num_ctx = 16384, temperature = 0, seed = 42 }
think   = false                # every grading task (v4.17, teacher after M2: qwen3.5:4b used its
                               # whole budget thinking in verify_key and judge_rewrites)

# v4.43, step 22.5.4: an older models.toml without the two roles below uses these defaults
[roles.grading_check]              # the model verify_key uses
model   = "qwen3.5:4b"
adapter = "chat"
options = { num_ctx = 16384, temperature = 0, seed = 42 }
think   = false

[roles.extraction_check]           # v4.47: reread_pieces, the targeted re-read (step 22.5.7)
model   = "qwen3.5:4b"
adapter = "chat"
options = { num_ctx = 16384, temperature = 0, seed = 42 }
think   = false

# v4.48 (R22.5.7.7, G4): a default role (listed, checked, downloaded), except when [extract]
# photo_reader = "vision" and models.toml has no [roles.ocr]: then it is absent (the path before 0.6.0).
[roles.ocr]                        # ocr_page: the two-step photo reader's OCR model (GLM-OCR 0.9B)
model   = "glm-ocr"
adapter = "chat"
options = { num_ctx = 16384, temperature = 0, seed = 42 }
think   = false

[confidence]
fallback = "none"              # Phase 0: logprobs present in every call; see §6

[extract]
retranscribe_tiles = false     # M1 bundle 1: tiles measured worse on baseline2; `etach eval --tiles` turns them on
retranscribe_tiles_keep = "better"   # keep the tile reading only with fewer validator failures ("always" = old rule)
reread_pieces = false          # v4.47: the targeted re-read of a failing page (one extraction_check call); G4 measures it
photo_reader = "ocr"           # v4.48 default (G4); "ocr" = ocr_page, then photo_structure; "vision" = transcribe_page
ocr_prompt = "Text Recognition:"   # v4.47: the whole user message of ocr_page (GLM-OCR's own prompt)
photo_structure = "code"       # v4.56: OCR reader only; "code" = domain/ocr_structure.py (no call; the default since v4.60, D16), "qwen" = structure_text_page, "ocr_format" = way 2a (ocr_format_page, v4.57)
blank_share = 0.2              # v4.51: a paper with fewer answers than this share read with confidence is blank; 0 = the rule before

[client]
retry_capped_output = { vision = false, reasoning = true, grading_check = true, extraction_check = false, ocr = false }   # retry an output cut at num_predict?
```

### 3.2 One call
`client.call(role, task, inputs, schema, images=[file_id…], think=None, num_predict=None) -> CallResult`:
1. The **adapter** builds the messages from `prompts/base/<task>.md` + `prompts/profiles/<profile>.md` + the inputs.
   - `nuextract`: NuExtract3's native template/instructions interface.
   - `chat`: system + user, with the schema in Ollama's `format`.
   - How NuExtract3's template interacts with `format` is checked in Phase 0.
2. It streams `/api/chat` with `logprobs: true`, `top_logprobs: 5` and `truncate: false` (Ollama must never silently drop earlier messages to fit `num_ctx`). A prompt that can't fit, checked before the call, by `prompt_eval_count` after it, or reported by Ollama, is a failed call with reason `prompt_truncated`: no retry, the `llm_calls` row → `error`, and the failure object goes into graph state (§5.1).
3. It writes `llm_calls` **incrementally** (`streaming`, flushed every ~50 tokens or 1 s), so a stop or crash leaves a readable partial record.
4. It validates against the pydantic schema. On failure: the row → `invalid`, then one retry with the error appended, unless the output stopped at `num_predict` and `[client] retry_capped_output` is false for the role (vision by default): then no retry and a failure `output_capped` at once. If the retry fails too, it **returns a failure object into graph state**. The client never writes Review items; `save` does (P8).
5. It returns the parsed object plus the per-field confidence (§6).

Cancellation: the call runs in the graph's asyncio task. Stop cancels it, which closes the HTTP stream, so Ollama stops generating. The row → `cancelled`.

At startup the client checks: Ollama ≥ 0.12.11, and both role models pulled (otherwise Settings shows **Download models**).

---

## 4. Extraction graph (the Run button)

The vision role only. The state holds IDs and small JSON, never image bytes.

```python
class ExtractState(TypedDict):
    run_id: str; thread_id: str
    input: ExtractInput                     # pages (order, rotation, is_key), existing_test_id, supersedes_attempt_id;
                                            # series_name (D5), again_test_id + again_mode (D8, v4.41)
    pages: list[PreparedPage]; key_pages: list[PreparedPage]
    transcribe_cursor: int; answers_cursor: int
    page_results: dict[int, PageTranscript]
    retranscribe: list[int]                 # pages that failed validation
    draft: TestDraft | None                 # new test, or the bank test loaded on the picked path
    header: PageHeader | None               # picked path: this photo's page-1 header + first stems
    compare: CompareResult | None
    key_raw: list[tuple[str, str]] | None   # read from key photos, in page order: (printed label, answer); labels may repeat
    key: list[KeyEntry]                     # mapped to question_ids
    answers_raw: dict[int, PageAnswers]
    pending_reviews: list[PendingReview]    # written by save only
    saved: SavedIds | None
```

```
START
  ▼
prepare_pages ──(code) apply the teacher's rotation, resize (new derived files), keep the colour original;
  │              split 🔑 key pages; attach PDF/DOCX text layers (a long DOCX text is already several
  │              text pages, ≤ 6 000 characters each); transcribe output cap 8192 tokens
  ▼
read_key_pages ──(vision, only if 🔑 pages) → key_raw [("32", "D"), …] (page order; a label may repeat)
  ▼
existing_test_id? ──yes──► load_bank_test ──(code) draft = bank test (content, pages, exam_format profile)
  │ no                          ▼
  │                        read_header ──(vision, page 1 only) header + first 3–5 stems
  │                             ▼
  │                        sanity_check ──(code) similarity(header+stems, bank test) low
  │                             │         → pending picked_test_mismatch
  │                             └──────────────────────────────────────────────┐
  ▼                                                                             │
transcribe_page ◄──┐ (vision, one page per invocation, transcribe_cursor++;     │
  │ more pages ────┘  GENERIC profile: the format isn't known until the header is read;
  ▼                   printed text only, blanks "____", <u>/**bold**, listening → heading + range,
merge_and_normalize   writing → the task prompt only (section graded=False, PRD D12),
                      mostly-text pictures transcribed, others → picture region + page;
                      unreadable words → "???", never guessed (PRD D25))
  │  (code) merge pages → draft: renumber sections and questions (printed_number kept),        │
  │  page_no per question, picture placeholders "[Hình: files/… · trang N]",                   │
  │  metadata from the header patterns + the file name, points (10 ÷ graded questions          │
  │  each, PRD D13 v8.0), option labels as bare letters, fingerprint;                          │
  │  validators → failing pages go to state.retranscribe ("???" is valid text, not a failure); │
  │  pages whose final text contains "???" → one pending unreadable_text each (D25; recomputed │
  │  on every pass, so a page that retranscribe_tiles read fully gets none)                    │
  ▼                                                                                             │
retranscribe? ──yes──► retranscribe_tiles ──(vision, half-page tiles, once; only if [extract] retranscribe_tiles,
  │                      default off; never on a text-layer page; kept only if fewer validator failures) ──► merge_and_normalize
  │ no  (a page failing twice → pending validator_failed)                                       │
  ▼                                                                                             │
compare_bank ──(code) Jaccard vs non-merged bank tests (PRD §8) → compare; the test an Extract │
  │   again came from (again_test_id) is left out (v4.41, D8)                                   │
  │   ≥ 0.5 → pending possible_duplicate with question_alignment                                │
  ▼                                                                                             │
map_key ◄───────────────────────────────────────────────────────────────────────────────────────┘
  │  (code, only if key_raw) printed number → question_id, in page order, skipping omitted (listening)
  │  numbers; a duplicated printed number is resolved by position; unmatched → pending key_unmapped;
  │  key-photo confidence below threshold → the key row is saved as ai_unverified; at or above it →
  │  from_key_photo (v4.46: never ai_verified, which means a second call agreed; verify_key checks only
  │  ai_unverified)
  ▼
read_answers_page ◄──┐ (vision, one page per invocation, answers_cursor++; no model call when every test page
  │                     is born-digital — any page from a DOCX (pictures included), or a PDF page with ≥ 100
  │                     text-layer characters whose images cover < 80 % of it — PRD D26: the node runs once,
  │                     makes no call, and the run saves a blank test)
  │  more pages ─────┘  input: this page + only the questions printed on it (by `page_no`, v4.46) when the
  │                     photo count equals the draft's page count, else every question; no "printed on
  │                     page N" hints; an answer written only on another page is not read (accepted); per-question
  │                     value types by answer form (v4.42: a `choice` reading (`ChoiceReading`)
  │                     takes one of that question's option labels, listed in the per-call schema; A–D when it
  │                     has none; T/F for True/False; a `word`/`sentence` reading (`TextReading`) takes text;
  │                     `writing` is not read); "copy handwriting exactly"; student name/class if written;
  │                     unreadable handwriting → "???", never guessed (D25)
  ▼
resolve_answers ──(code) exactly one answer per graded question (None = blank; writing sections are not read);
  │                value_norm computed; answer box wins over inline
  │                (disagreement → pending box_inline_conflict); box rows matched by position;
  │                a span near two questions → confidence capped at (reading threshold − 0.01), so it is
  │                always "?" whatever threshold M1 fits, + alt_question_id (free text in the
  │                schema, checked in code: not another question's ID → dropped, no cap);
  │                logprob confidence → reading_unsure; a value containing "???" → reading_unsure
  │                (confidence capped at threshold − 0.01, like a span; the value is kept, D25);
  │                no answers at all, or (v4.51) fewer than 20% read with confidence (a "???"
  │                counts) → blank test, its answer Review items dropped; a value spelled
  │                null / none / n/a is not read
  ▼
save ──(code, ONE transaction, idempotent via source_run_id; data-model §5.2)
  │   new test (+ test_pages, write_test_meta → FTS) unless picked · Extract again "replace":
  │   the new reading saved into again_test_id (data-model §5.8, v4.41) · series_name (D5) ·
  │   filled: attempt (+ attempt_pages, answers, student matched by name read, else "Chưa rõ" +
  │   pending unknown_student with the name) · superseded attempt linked if supersedes_attempt_id ·
  │   key rows from `key` (guarded: never downgrade existing keys) · threads.test_id, threads.kind ·
  │   pending reviews upserted by dedupe_key · extraction card message · runs.status = done
  ▼
END → SSE run.done → toast "Extracted: 7 unsure"
```

**Photos (v4.47, step 22.5.7).**
- **Page breaks.** `transcribe_page` for page N+1 sends `previous_page`: empty, or a lead-in line and the last open
  unit of page N as already read (`renumber.open_unit`, about 100–300 tokens): the last `questions` section's title
  and instructions when it has no question yet; the last question and what it lacks ("Question 14: stem, no
  options"); or an open passage's last paragraph from its last blank and the question numbers read so far. A page
  with nothing open sends no hint. The prompt says in two lines that a page starting with the rest of that question
  or passage returns it as that question (same printed number) or group with `continued` true. `TranscribedSection`,
  `TranscribedGroup` and `TranscribedQuestion` carry `continued` (default false). `merge_and_normalize` joins a
  page's first section into the previous page's last one when it is marked `continued` (or a question is split
  across the break); a question's continued copy fills the first copy's missing stem, options or cue; a page's first
  group is joined into the previous open passage when marked `continued`, when its cloze gaps go on from the
  passage's last gap, or when its stem-less questions are that passage's gaps. A listening section, or a group with
  pictures, is never joined.
- **The targeted re-read** (`[extract] reread_pieces`, default off). On the retranscribe pass a failing page first gets
  one `reread_pieces` call (the `extraction_check` role, the page photo, think off, cap 2048 tokens). Its input names
  only the broken pieces, by section title and printed number (`renumber.reread_asks`, `reread_text`): a question
  failing a `choice` or blank check, and for a `numbering` failure the printed numbers missing before it
  (`validators.missing_numbers`; at most a few). The output is `RereadPiecesOut` (`pieces`: section title, printed
  number, answer form, stem, options, cue, `answer_start`). `renumber.apply_reread` replaces a broken question's
  failing field and fills its empty fields, or inserts a missing number after the nearest lower number in the named
  section; a piece not asked for, or under a section title the page lacks, is dropped; every other section, group
  and question is kept as is (byte-identical). The patch is kept only if the page's failures do not increase; a
  failed call, or nothing to ask, leaves the page as it was. The tile re-read (`retranscribe_tiles`) then runs only
  if it is on, as before; with both off a failing page goes straight to `validator_failed`.
- **The two-step photo reader** (`[extract] photo_reader`, D13; default `"ocr"` since v4.48 (G4); `"vision"` is the one-call path). With `"ocr"`, a photo
  page without a text layer gets an `ocr_page` call (the `ocr` role, the photo, the user message `ocr_prompt` only:
  no system message and no `format`; the answer is kept as plain text, an empty answer is invalid; cap 4096 tokens)
  and then `structure_text_page` on that text as its document, like a typed page (no previous-page hint; the merge's
  page-break joins still apply). **v4.50 (step 22.6.1, step22.6-plan D2, D3):** before that call, code removes the
  answer boxes from the OCR text (`domain/answer_box.py`: a "Phần trả lời" or "ANSWER" heading and its rows of
  numbers or blanks, and rows of two or more numbered blanks with no heading), and the photo call's
  `structure_text_page` prompt gets the `photo_rules` input (`examples/photo_rules.md`: leave out answer boxes; a
  question printed as only its number and options has a null `stem`, the options never repeated, with a one-line
  example); a typed page sends `photo_rules` empty, so its prompt renders as before. **v4.56 (step 22.6.5, D7):**
  `[extract] photo_structure` picks how the OCR text is structured: `"qwen"` (the default up to v4.59) is the
  `structure_text_page` call above; `"code"` (the default since v4.60: step 22.6.6 (c), step22.6-plan D16, the
  teacher's pick after the three-way GPU check in step22.6-plan §5) replaces that call with `domain/ocr_structure.py` (no model call; the
  page's transcript points at its `ocr_page` call): Roman-numeral or "Part" headings start sections (instructions
  and points kept), `N.` / `Question N.` start questions, options `A.`–`D.` on one line or several, True/False
  statements, the text between a heading and its first question (or a cloze with `(N) ____` gaps) as the group
  stimulus, the line under a rewrite question as `answer_start`, the bracketed cue for word form, `answer_form`
  and `skill` by the prompt's rules; a line it cannot place is kept in the nearest instructions or stem and the
  page gets one `validator_failed` item (task `ocr_structure`). **v4.57:** `"ocr_format"` (way 2a) replaces both calls with one
  `ocr_format_page` call (the `ocr` role, the photo; its user message is `prompts/base/ocr_format_page.md`, the
  test-text format and one made-up example, not `ocr_prompt`); code removes answer boxes and `test_text.read_ocr_page`
  reads the text into the page's `TranscribeOut` (GLM-OCR habits undone first: options on the question's line or one
  space apart, an arrow line as `Start:`; a page starting without a heading starts with an untitled section; a
  Roman-numeral or "Part" label is the printed title). A page the reader cannot read keeps its text as one group's
  passage and gets one `validator_failed` item (task `ocr_format_page`, the reader's reason). A failed `ocr_page`
  or `ocr_format_page` call fails the page like a failed `transcribe_page`. Pages with
  a text layer, the key photos and `read_answers_page` stay on their roles (the student answers are read by vision).
  `etach eval --photo-reader ocr|vision` sets the reader for an eval run (v4.48); a row read with `ocr` gets `+ocr` in
  its `mode` (rows without it were read with vision).

**Blank tests.**
- Blank (no answers at all, or, v4.51, fewer than 20% read with confidence) and new → the test is saved,
  `threads.kind = blank`, no attempt.
- Blank and picked → nothing new is saved. The card says "No answers found; T-0042 is already in the bank". `threads.test_id = T-0042`, `kind = blank`.

**Worked example** (Lớp 8 HK1 Đề 1):
- Photo check order and rotation → `transcribe_page` ×3 → `merge_and_normalize` fixes the duplicated "VI" and missing "VII", drops listening Q1–4 into `omitted_sections`, and sets `points_possible = 9`.
- `compare_bank`: nothing similar.
- `read_answers_page` ×3: circled options and written words; the answer boxes are empty.
- `resolve_answers` flags Q35/Q36 with `alt_question_id`.
- `save`: T-0042, A-0103 (name "Ngô Thị Mỹ Hòa" read from the paper, matched or "Chưa rõ").

---

## 5. Grade graph (the Grade button)

The reasoning role plus code. The input is `GradeInput {test_id, attempt_id | None, reason}`.

**The key run (v4.53, step 22.6.4, step22.6-plan D4; PRD D2/D16).** Every extract `save` (a new test, Extract
again, a picked test, a blank test, typed or photo input) queues, in its own transaction, one grade run on the same
thread with `attempt_id` None and `reason: after_extract` (data-model §5.2): the same path as Make the key,
`load_context → [ai_key_fast] → verify_gate → [verify_key] → tag_skills → save`. It starts after the extraction
(FIFO, §2) and never grades, even when the thread has an attempt. `ai_key_fast` keys only the questions without a key
row, so a key photo's or the teacher's key stays; `save`'s guarded upsert never downgrades one. A later Grade (or
Make the key) loads those keys and makes only the ones still missing; when the key run failed, was stopped or was
discarded, Grade makes the key as before. Extract again and Delete thread cancel it (v4.54, step22.6-plan D12):
when the thread's only unfinished runs are key runs, the route discards them through the run manager and goes
ahead; any other unfinished run still gives 409. `etach run` / `etach eval` (and their recordings) queue no key run;
only the app's sidecar (`etach serve`) does. The app greys out Grade student answers
("Making the key…") and keeps the Key tab blank while the thread's key run is queued or running (D11).

```
START
  ▼
load_context ──(code) test, its keys and tags; if attempt_id: current answers (teacher overrides
  │             applied, and an override counts as confidence 1.0) + attempts.version
  ▼
key_needed? ── every question has a key row ──► (skip ai_key_fast)
  │ some questions have no key row
  ▼
ai_key_fast ──(reasoning, think off, one section per call) → accepted[] + reason_vi + logprob margin;
  │            rows saved as ai_unverified. Its rules go by answer form (v4.42): a `choice` answer is one of
  │            its option letters; a `word` gets the exact form that fits; a `sentence` the most natural full
  │            sentence first, then other correct sentences. v4.43: the whole section stays as context, but
  │            the prompt names only the questions without a key (input `key_questions`; rule "Write the key
  │            only for the questions named at the end"; last line "Write the key for these questions: …"). Every grading
  │            prompt's question line (judge, ai_key_fast, verify_key, explain) of a `sentence` question
  │            with printed opening words ends "Answer line starts with: …"
  ▼
verify_gate ──(code, node name "verify_gate") verify_needed per question: status ai_unverified AND (low margin OR pronunciation/stress
  │               OR (attempt present AND student answer ≠ key)); none → skip
  ▼
verify_key ──(grading_check role since v4.43, think off since v4.17, fresh context, num_predict 1000 since v4.52, was 1500)
  │           agree → ai_verified · disagree, `?` or truncated → ai_uncertain (+ pending uncertain_key)
  │           v4.45: the key row's `checker` keeps the checker's answer and reasoning (disagreed) or
  │           did_not_finish (cut off or failed twice); the Key read carries it
  │           v4.52 (D6): the prompt says it may answer `?` when not sure and, as its output is
  │           limited, to answer `?` rather than run out; a `?` answer (spaces ignored) → `unsure`
  │           (reasoning only)
  ▼
tag_skills ──(reasoning, once per test: skipped if question_tags exist)
  │           one call per graded section since v4.44: its heading, instructions, passage and
  │           questions (skill list in the system prompt); ≤ 3 tags per question
  │           v4.45 (D11d): output items {question_id, tags, level}; `level` is required and nullable
  │           (A1–B2 or null), stored with the question's tags; a tag's effective level is that level,
  │           else the skill's base level (grammar: the ID's end; sections.txt: the level column)
  ▼
attempt present? ──no──► save  (blank test: keys and tags only; difficulty_notes removed in v4.43, D10)
  │ yes
  ▼
grade ──(code) per answer:
  │      reading_unsure (and no override) → uncertain (?) · key ai_uncertain → uncertain (?)
  │      no key row (key making failed) → uncertain (?)
  │      by answer form (v4.42, D9): choice → exact match (True/False and former matching included)
  │      word → value_norm matched against normalized accepted[]; edit distance 1–2 + confident reading
  │        → incorrect + near_miss · + unsure reading → uncertain
  │      sentence → normalized match, else → judge_rewrites (one judge rule for every sentence: former
  │        combine, ordering and short_answer questions included)
  │      writing → not graded (no answer row)
  ▼
judge_rewrites ──(reasoning, think off since v4.17, num_predict 400, strict rules) correct | incorrect + reason
  │                (no partial credit, PRD D24: correct = full points, incorrect = 0). v4.43: `JudgeOut` =
  │                reason, then verdict; rule line "The student's answer may continue the words the answer
  │                line starts with."
  ▼
explain ──(reasoning, think off) per incorrect answer: cache (question, wrong answer) hit → reuse;
  │        miss → error_type + ≤3 sentences Vietnamese/English terms, plus short Vietnamese glosses and, for a rewrite,
  │        the correct sentence's Vietnamese meaning; about 70 words (v4.17.2; cached in save). v4.43:
  │        `ExplainOut` = reasoning, text_vi, error_type; the reasoning is kept only in `llm_calls` (never
  │        shown, stored elsewhere or sent by the API); line 1 says "a Vietnamese student" (no grade), the
  │        tone "a teenager"; the cap stays 512 (the longer output is about 211 tokens)
  ▼
weak_points ──(code) student_skill_stats (history) + THIS attempt's in-state verdicts and tags
  │            → ranked weak points, careless notes; (reasoning) summary_vi + 3–5 teacher questions
  │            v4.45 (D11, D11c–e): each skill's trajectory over the student's papers by date taken
  │            (data-model §4) gives the label; weak points = skills missed on this paper, labelled or
  │            "this paper only", basics first, those above the lowest weak level held back. The summary
  │            input `weak_points` lists skill names (not codes) and only those not held back; the
  │            `wrong_answers` lines name the skills too, leaving out held-back ones (a line with only
  │            held-back skills is left out; v4.45.1). On a first grade the question levels come
  │            from this run's tag_skills (state), not the stored rows `save` writes later
  ▼
save ──(code, ONE transaction; data-model §5.2) test check (the content changed since load → back to
  │     load_context, keeping the work for unchanged questions; v4.58; v4.59: a stored key
  │     that outranks the run's own (a teacher key) wins, pending items are kept only for the
  │     kept keys, and tag_skills tags the graded questions left without tags);
  │     version check (mismatch → reload, redo grade→weak_points);
  │     guarded key upserts; question_tags; verdicts, points, score;
  │     explanations; grade_reports (replace); this graph's older review items → obsolete;
  │     pending reviews upserted; grade card message; attempts.status = graded; runs.status = done
  ▼
END → report draft in the panel → the teacher glances → Print
```

### 5.1 When a model call fails twice
The client returns a failure object after its one retry, or at once for a truncated prompt or a capped vision output (§3.2). The graph never crashes on it:

| Call | Result |
|---|---|
| `read_answers_page` (a page) | Every graded question on that page: value None, `reading_unsure = true` (→ `?`), plus one `validator_failed` item for the page |
| `transcribe_page` / `retranscribe_tiles` / `ocr_page` (v4.47) / `ocr_format_page` (v4.57) | `validator_failed` for that page; the test is saved with what was read |
| `reread_pieces` (v4.47) | The page stays as it was read; it goes on to the tiles if they are on, else `validator_failed` |
| `read_key_pages` | No key rows from the photo; Grade makes the key |
| `ai_key_fast` (a section) | No key rows for those questions → they grade `uncertain` (no key row) + `uncertain_key` |
| `verify_key` | Key → `ai_uncertain` (+ `uncertain_key`) |
| `judge_rewrites` | That answer `uncertain` |
| `explain` | No explanation; the report shows "no explanation" for that question |
| `tag_skills` / `weak_points_summary` | Skipped (`tag_skills`: that section only, v4.44); tags or notes are missing; the report shows ranked skills without the narrative |

**Listening safety net (M1, v4.16).** `transcribe_page` returns a listening section as its heading and printed range only. If `merge_and_normalize` finds a `listening` section (after pages are joined) whose groups hold at least one question with a non-empty stem or at least one option, the model misread it (for example it merged printed sections I–III under one "listening" label). Then:
- the section is stored, graded and numbered exactly like a `questions` section; it is not added to `omitted_sections`;
- one pending `validator_failed` is raised per page where such a section starts, dedupe key `validator_failed:<run_id>:listening:<page_no>`. Its proposal has the `transcribe_page` item's shape (`task: "transcribe_page"`, `page_no`, `failures` with one `listening_with_questions` entry per section, `call_failure: null`) plus `reason: "listening_with_questions"` and `sections` (`section_id`, `section_number`, `printed_title`, `questions`). Accept keeps the stored content; Fix takes the edited `TestContent` (data-model Review resolution).

A listening section with no question content is unchanged: omitted, with its printed range and points recorded. The code does not split a merged section back into the printed sections; the teacher does that in the Fix.

A run becomes `failed` only on errors outside model calls (for example a database error or a bug). These rules are listed in plan.md Appendix B.5 and B.8.

**Re-grade fan-out** (only for attempts that are **already graded and not superseded**; data-model §5.3):
- Verifying a key (Review or the key editor) queues one grade run per graded, non-superseded attempt on that test (`reason: key_verified`).
- A merge does the same for the moved attempts (`merge`).
- A reading fix queues one run for that attempt (`review_fix`).
- A points fix queues no run (v4.59): `points.save_content` re-scores the graded attempts at once, and the `points_assumed` Fix goes through it. No path queues a `points_fix` run (the reason stays valid in `GradeInput`).

In these runs every "once per test" node is skipped, and explanations are mostly cache hits (the changed question's explanations were deleted with the key change). So only `grade`, a few `explain` calls, `weak_points` and `save` do work.

---

## 6. Confidence from logprobs (D20)

- Ollama returns, for each token, its logprob plus the `top_logprobs` alternatives. The tokens are mapped to JSON field spans by parsing the JSON with position tracking.
- **Enum fields** (a `choice` letter, T/F included): take the first token of the value, restrict it to the valid choices, renormalize. **Margin = p(top) − p(second).**
- **Free text:** the **lowest token probability** in the span (the sequence probability is kept for calibration).
- **Thresholds** are fitted on the **tuning** fixtures and reported on the **held-out** fixtures. Below the threshold → `reading_unsure` (answers) or "low margin" (keys).
- **Verified in Phase 0** (docs/initial-plan/phases-testing/phase0-report.md): logprobs work together with `format` and images on both roles, and the MCQ letter is a single token.
- **Fallbacks** (`confidence.fallback` in config; **Phase 0 chose `none`**, docs/initial-plan/phases-testing/phase0-report.md; any fallback result sets `Answer.low_trust`):
  1. `resample`: a second sample at temperature 0.7; agreement → confidence 1.0, disagreement → 0.0.
  2. `self_report`: the model's own confidence field.
  3. `none`: confidence 0.0, so every value is `reading_unsure` (`?`) and the teacher checks it.

---

## 7. Stop, resume and crashes (D22, D23)

| Situation | What happens |
|---|---|
| **Stop** | The run's asyncio task is cancelled → the Ollama stream closes. The `llm_calls` row → `cancelled` (partial response and thinking text **kept**), the step → `incomplete`, and the run passes through `stopping` to `stopped`. The indicator shows **Resume / Discard**. |
| **Resume** | `await graph.ainvoke(None, {"configurable": {"thread_id": run_id}})`. It continues from the last checkpoint: the interrupted node **restarts from scratch** (a new step row, `try_no + 1`), and finished nodes are not repeated. |
| **Discard** | The run → `discarded`. Its checkpoint is purged, its `llm_calls` are kept for debugging, and no domain rows exist (only `save` writes those). The photos become unreferenced and are removed by the cleanup sweep. |
| **Startup recovery** | `running` → `interrupted` (emits `run.interrupted`), `stopping` → `stopped`, `queued` → re-queued, open steps → `incomplete`, `streaming` calls → `incomplete`. The indicator offers **Resume / Discard** for `interrupted` and `stopped` runs. |
| **Crash between `save`'s commit and its checkpoint** | Resume re-runs `save`, which finds its rows by `source_run_id` and the run already `done`, so nothing is duplicated (data-model §5.2). |
| **Stale state** (the teacher changed something while a grade run was stopped or queued) | Grade's `save` checks the test content (changed → back to `load_context`, v4.58) and `attempts.version` (changed → recompute from `grade`). Guarded upserts never overwrite the teacher's keys or overrides. |
| **Sleep** | Idle sleep is blocked while running (`SetThreadExecutionState` via ctypes). A closed lid can still sleep: on wake the stream errors → the node retries once automatically → otherwise `interrupted`. |
| **Finished run** | The checkpoint is purged. |

The checkpointer is LangGraph's `SqliteSaver` (async variant) in the app database, with **durability "sync"**, so each node's output is persisted before the next node starts. Incomplete, cancelled or invalid `llm_calls` are never read as results; Settings can clear old ones.

---

## 8. Prompts, fixtures, evals, tests

- **Prompts:** `prompts/base/<task>.md` + `prompts/profiles/<profile>.md`.
  - Transcription always uses the **generic** profile.
  - Later calls use the test's `exam_format` profile, falling back to generic.
  - Every `llm_calls` row stores the `prompt_hash`.
  - **Unreadable text** (v4.11, PRD D25): `transcribe_page` (and `retranscribe_tiles`) and `read_answers_page` must write a word or span they cannot read (cut off, blurred, covered) as `???`, and never guess it. The required phrases are in plan Appendix D.2a. The fixtures' `expected.json` uses the same `???` rule.
- **Fixtures** (gitignored: student names and handwriting): `fixtures/<tuning|heldout>/<name>/{pages/, input.json, expected.json}`. `input.json` holds the photo-check choices.
- **`etach eval --graph extract|grade --set heldout [--role vision=<tag>]`** reports:
  - transcription CER and structure (counts, types, options, blanks, underline, bold);
  - answer-reading accuracy;
  - calibration (the share of wrong readings flagged `?`, with its interval);
  - key accuracy, key mapping accuracy (🔑 photos);
  - verdict accuracy, exact score match;
  - tokens, time and VRAM per node;
  - answer-number errors (v4.47, step 22.5.7), over the questions aligned **by content** (each expected question, in
    order, paired with the closest unpaired read question by stem, options and cue, CER ≤ 0.3):
    `number_reading_errors` is the share of pairs whose read **printed** number differs from the paper's (the model
    misread the number); `number_renumbering_errors` is the share whose canonical number (`Question.number`, the
    code's numbering: 1..N over the graded sections, then writing) differs from the expected one (a question left
    out or added before it, or a section numbered elsewhere). A pair may count in both. The two columns are appended
    at the end of `eval-history.csv` (empty in grade rows).

  Results are appended to `eval-history.csv`, which **is committed** (it holds metrics only, no student data). `fixtures/` stays gitignored except `fixtures/MANIFEST.sha256` (the `expected.json` hashes + `verified_by`, written only by the teacher), so a verifier can check sign-offs without seeing the fixtures. From step 22.5.3 the `structure_types` column holds answer-form accuracy instead of question-type accuracy, so rows before and after step 22.5.3 are not comparable in that column or in `structure_overall`, which includes it.
- **Tests (pytest):**
  - unit tests: renumbering, key mapping (duplicate printed numbers, skipped listening), scoring and near-miss, text similarity and question alignment, box-row matching, merge remap, the Review dispatch table;
  - **replay tests** (recorded `llm_calls` through a fake client);
  - **stop/resume tests**: cancel at every node boundary and mid-call, **including between `save`'s commit and the checkpoint**, then resume and assert an identical final database;
  - **stale-state test**: override an answer while a grade run is stopped, then resume and assert the override is respected.

---

## 9. Open questions for Phase 0–1

1. Do Ollama logprobs work together with `format` and images (NuExtract3 and chat models)? **Answered in Phase 0: yes, for both roles.**
2. NuExtract3's template vs Ollama's `format`. **Answered in Phase 0: identical output; `also_format = true`.**
3. How well NuExtract3 does on the fixtures (printed text, underline/bold, handwriting, circles, T/F, answer boxes on other pages, key photos), and what prompting fixes any gaps.
4. Full page vs half-page tiles.
5. Calibration thresholds on held-out fixtures.
6. The teacher's candidate reasoning models: key, judge, explanation quality, speed.
7. Async `SqliteSaver` + durability "sync" in the same WAL database as the app data: locking and speed.
8. PyInstaller folder build: size and antivirus behaviour. Answered at step 21: `docs/release-notes.md`.
