# Changelogs of the lasting docs, up to the end of the initial plan

These rows were moved here on 2026-11-09, unchanged, from the changelog tables of the lasting docs. Each doc keeps
only its rows since the initial plan ended (2026-11-03). Order as in the docs.

## PRD (`docs/PRD.md`)

| Version | Date | Change |
|---|---|---|
| v9.0 | 2026-10-30 | **Major**, teacher (step 22.6.4, step22.6-plan D4 and D11): **D2** and **D16** changed — the key is made after every extraction (Extract again too), with or without a key photo: the AI key for the questions without one, its check and the skill tags, in a key run queued after the extraction; key-photo and teacher keys stay. The Key tab stays blank, with a short note, until the key is ready, then shows it all at once; Grade student answers waits, greyed out with "Making the key…". Grade makes a key only where one is still missing. §1, S1, S4, S5, §9, §10's Make the key, §13 Phase 3, R3 and the glossary follow. Was: the key was made by the Grade button |
| v8.28 | 2026-10-30 | Minor, teacher (step 22.6.2, step22.6-plan D5): S4, a photo paper with fewer than 20% of its answers read with confidence is a blank test too (no attempt, no answer Review items) |
| v8.27 | 2026-10-28 | Minor, teacher (decided during the layout work, recorded late; found by the verifier): the motto group headings are in the Chats list only; Tests and Students stay ungrouped. Not a §3 decision |
| v8.26.1 | 2026-10-28 | Patch: the title and the §10.1 layout sketch say ETACH |
| v8.26 | 2026-10-28 | Minor, teacher: the program file is renamed `ETACH.exe` (it stayed `exam-revision-helper.exe` after the product rename). Not a §3 decision |
| v8.25 | 2026-10-28 | Minor, teacher: the start screen drops the ETACH heading; a dotted, paper-shaped drop box around the instruction and Choose files. Not a §3 decision |
| v8.24 | 2026-10-28 | Minor, teacher: the New thread start screen goes back to its earlier simple centred layout, without the ETACH logo. Not a §3 decision |
| v8.23 | 2026-10-28 | Minor, teacher: New thread goes back to its earlier simple row ("simple and better"); no tint. Not a §3 decision |
| v8.22 | 2026-10-27 | Minor, teacher: the open thread is shown by a light blue tint only; the notebook-margin mark is dropped. Not a §3 decision |
| v8.21 | 2026-10-27 | Minor, teacher, after a layout analysis (it looked like Claude Desktop): paper corners and arch-topped workspace tabs; a tinted New thread, separated sidebar tabs, a notebook-margin mark on the open thread, motto-style group headings, a labelled Settings row; the workspace panel as a sheet of paper with a double rule under its header; symbols in Faustina; a test-paper start screen. Not a §3 decision |
| v8.20 | 2026-10-27 | Minor, teacher: the button and tab hover becomes deep navy rgb(24, 26, 92), the wordmark's end colour (the navy rgb(15, 16, 56) looked black). Not a §3 decision |
| v8.19 | 2026-10-27 | Minor, teacher, from the wordmark trial: the ETACH gradient (lime at the E, blue through the T and A with about 20% green left at the T, deep navy rgb(24, 26, 92) from the middle of the C; black was too black). Not a §3 decision |
| v8.18 | 2026-10-27 | Minor, teacher: the app is renamed ETACH ("English Test Assistant - Curate & Help"), with a Federo wordmark; the product name, the Windows app ID and the default app folder `D:\ETACH` change too, so 0.6.0 installs as a new app; the old folder's data is moved once by hand. Internal code names stay. Not a §3 decision |
| v8.17 | 2026-10-27 | Minor, teacher, after the Faustina screenshots: only the main buttons and the workspace tabs are enlarged; chips, the sidebar and small row buttons keep the normal size. Not a §3 decision |
| v8.16 | 2026-10-27 | Minor, teacher, after a font trial (Faustina, Crimson Pro, Merriweather, Be Vietnam Pro): one font, Faustina, for the whole app; button and tab text larger. Not a §3 decision |
| v8.15 | 2026-10-27 | Minor, teacher: the light button blue was too light; buttons and tabs are blue rgb(53, 57, 227) and turn dark navy rgb(15, 16, 56) on hover. Not a §3 decision |
| v8.14 | 2026-10-27 | Minor, teacher (the v8.13 background and blue changes were too small to notice): background rgb(247, 247, 249); buttons and the selected tab light blue rgb(98, 101, 233), darker rgb(53, 57, 227) on hover; links and focus stay rgb(53, 57, 227). Not a §3 decision |
| v8.13 | 2026-10-26 | Minor, teacher, after the theme screenshots: the background whiter, rgb(244, 244, 247); the blue a little lighter, rgb(53, 57, 227); the gradient labels end in a deeper gold, rgb(119, 105, 16); ✓ and ✗ badges (green, brick); "improved" and "inconsistent" as green and ochre badges; error messages stay brick. Not a §3 decision |
| v8.12 | 2026-10-26 | Minor, teacher (step 22.5.8 (f), before installer 0.6.0): the theme is light only, a blue-grey background, near-black text with a hint of yellow and a blue accent; correct, unsure and wrong take the theme's green, ochre and brick (after old Saigon school buildings), and their labels are written in letters fading from black to yellow. It replaces v4.11's green theme and the dark mode. Not a §3 decision |
| v8.11 | 2026-10-26 | Minor, step 22.5.7 (R22.5.7.7; teacher, G4): test photos are read in two steps by default, the OCR model (GLM-OCR) and then the typed-text reading; its model is downloaded and checked with the others; the vision model stays a setting and always reads the student answers; the tile re-read stays off. No decision changes |
| v8.10 | 2026-10-26 | Minor, step 22.5.7 (comment 4, D13): photos. A page is read with what the page before it left open, so a question or passage cut by a page break is joined; a page that fails a check can have only its broken questions read again (a setting, off until measured); an optional two-step photo reader (an OCR model, then the typed-text reading), a setting that stays on the vision model by default; student answers are always read by the vision model. No decision changes |
| v8.9 | 2026-10-25 | Minor, step 22.5.6 (D12, comment 4): typed PDFs are read as one text, so a question cut by a page break stays whole; each page is read only for the student answers to its own questions (an answer written only on another page is not read: accepted limit); key explanations are ignored; a key read from the key photo is shown as from the key photo, "double-checked" only when a second check agreed; the Student answers tab says how the listening part was handled |
| v8.8.1 | 2026-10-25 | Patch, step 22.5.5 checklist (d) (D11f): the trajectory's share uses a guessing baseline (all right = 100 %, chance level = 0 %) instead of "a right multiple-choice answer counts half" |
| v8.8 | 2026-10-24 | Minor, step 22.5.5 (step 22.5 decisions D11, D11a–e): weak points by the student's trajectory over the papers (by date taken), basics first with the higher levels held back; the Students tab shows each skill's label and level; the date taken on the photo check card and the Student answers tab; the checker's answer on hover over an unsure key |
| v8.7 | 2026-10-24 | Minor, step 22.5.4 (step 22.5 decision D10: drop): §4 a blank test's Grade no longer makes difficulty notes (the step is removed; its stored notes are dropped once at first start) |
| v8.6 | 2026-10-24 | Minor, step 22.5.3 (step 22.5 decision D9, built as proposed; the teacher signs it off after G1): the 11 question types become 4 answer forms (choice, word, sentence, writing). Grading by form: a former short-answer or ordering question whose student answer is not an exact match goes to the AI judge; combine uses the rewrite judge rule; matching is graded as a choice; writing is not graded. Stored tests are mapped once at first start; nothing graded changes |
| v8.5.1 | 2026-10-23 | Patch, teacher (D8 addition after the 22.5.2 verifier): Extract again keeps AI keys too on unchanged questions |
| v8.5 | 2026-10-23 | Minor, teacher (step 22.5 comments 1, 2, 5, 7; decisions D2, D5, D7, D8): headings show no points, the line under the test title reads "10 points · 0.25 each" (D13); an untitled section takes its title from its skill; a Series list like Schools, and "same series as" picks a series name; Extract again updates the same test (or makes a copy when other threads use it) |
| v8.4 | 2026-10-23 | Minor, teacher: §10 extra detail goes into a hover/focus tooltip, not onto the row |
| v8.3 | 2026-10-19 | Minor, teacher (step 22.4 §6 answers): leaving a thread whose keys changed also starts the re-grade; the top bar is compact on every workspace tab; section headings show the total and the per-question points |
| v8.2 | 2026-10-19 | Minor, teacher (step 22.4 D5): the report shows English skill names, never internal codes; explanations in question order |
| v8.1 | 2026-10-19 | Minor, teacher (step 22.4 D4): verifying or editing keys no longer re-grades at once; one re-grade on leaving the Key tab, or by the Re-grade button |
| v8.0 | 2026-10-19 | **Major**, teacher (step 22.4 D3): D13 the score is always out of 10, every graded question worth 10 ÷ the number of graded questions; printed part points no longer count; no more `points_assumed` |
| v7.3 | 2026-10-19 | Minor, teacher (step 22.4 D1, D2): Settings has tabs (General · Models · Occasions · Schools); the school list is editable in Settings and the School field picks from it |
| v7.2 | 2026-10-18 | Minor, teacher (2026-10-15 and 2026-10-18): the occasion list is editable in Settings (add, rename, reorder; delete only when unused) |
| v7.1 | 2026-10-18 | Minor, teacher (step 22.3, comments 6, 10; decisions D5, D6): a typed PDF/DOCX page's exact text goes to the model as text (no image reading); extraction keeps a rewrite's printed opening words so its key gets all four forms |
| v7.0 | 2026-10-18 | Major, teacher (step 22.3, comments 12, 12.5, 13, 17; decision D4): **D7** changed — the default image model is `qwen3.5:4b` (was NuExtract); Settings has a model manager (installed Ollama models, download, delete) and each role is picked from the installed models |
| v6.4 | 2026-10-17 | Minor, teacher (step 22.3, comments 1, 15; decisions D1, D3): a student can be deleted, with their threads; test details can be copied from another test (not grade or test number), and a new extraction can start from "same series as…" |
| v6.3.1 | 2026-10-17 | Patch, teacher (2026-10-17): on a thread with only the test, the Grade button reads "Make the key"; a test-only thread has no student |
| v6.3 | 2026-10-17 | Minor, teacher (step 22.3, comments 14, 18; decision D2): an extracted thread opens straight into its workspace (no card page); Grade student answers and Extract again sit at the top right of the Test page; run progress shows in the sidebar and as a bar at the top of the workspace; a student can be set on any thread |
| v6.2 | 2026-10-15 | Minor, teacher (step22.2-plan §4, answers of 2026-10-15): the Test name is editable (an edited name stays until "Use automatic name"); "Unit Test" / "15-minute Test" in the name, an unknown occasion left out; Units and Tags editable; an uncertain grade reads "AI unsure grade"; the uninstaller box reads "Delete all app data (tests, students, backups)" |
| v6.1 | 2026-10-14 | Minor, teacher (step 22.2, comment 3; answers 10, 18): the key photos are kept with the test and shown in the Key workspace; the uninstaller's "Delete app data" box deletes the app's data in the app folder; the version shown is the one built into the app |
| v6.0 | 2026-10-14 | Major, teacher (step 22.2, comments 9, 12; answers 12, 13; decision C): **D10** changed — every screen, print and DOCX shows the paper's printed question numbers, gaps included (listening left out keeps its numbers); the code's own numbering stays internal. The test name is made as "Grade 8 - Final Term 1 - <school or series> - 2025 - Test 7"; the test details show the important fields first; the test page has Format help; a question typed into the text gets an answer row and a typed `???` becomes a note |
| v5.3 | 2026-10-14 | Minor, teacher (step 22.2, comments 2, 4; decisions B1, B2): threads and tests can be deleted, for good, after a confirm dialog; a **Students** tab next to Chats and Tests lists students with their class, edits them and shows their threads |
| v5.2 | 2026-10-14 | Minor, teacher (step 22.2, comments 1, 5, 6, 10, 14): the workspace has tabs (Test · Key · Student answers · Report); closing the window asks first; the new-thread screen has a Choose files button; double-click edits a row; Student answers rows keep their actions on the right like the Key; the print view shows the test's title and details line |
| v5.1 | 2026-10-14 | Minor, teacher (step 22.2, comment 7): the student's answers are called **Student answers** everywhere on screen and the correct answers are always the **Key**; titles put the test first ("Unit 3 test · Phạm Thu Hà"); occasions show in plain English |
| v5.0 | 2026-10-13 | Major, teacher (step 22.1 decision 5, comment 9): **D4** changed — the clean test, the key and the report can also be saved as **DOCX** (Word), into `<app>\exports\`, which then opens in Explorer (teacher: app folder only; §11 unchanged). DOCX export leaves the out-of-scope list |
| v4.14 | 2026-10-13 | Minor, approved by the teacher (step 22.1 decisions 4a, 4b; comments 5, 6, 7, 12): new decision **D27**. The Review tab and panel are removed; each unsure spot is shown and settled where it sits (the test page, the answers, the key, the card, the chips). The test is edited as one free-text page, like Word, and read back into questions. S7 and §10 follow |
| v4.13 | 2026-10-13 | Minor, teacher (step 22.1 decision 3, comments 3, 12, 14, 15): the workspace view. Opening Test, Key, Answers or Report hides the conversation; the panel fills the left and the original photos fill the right; "← Back to thread" returns. The cards show the photos and say where each button leads |
| v4.12.1 | 2026-10-13 | Patch: the running-indicator example uses llm-design's stage name ("Reading the answers") |
| v4.12 | 2026-10-13 | Minor, step 22.1.3 (teacher's comment 2): the running indicator and the running thread show a progress bar with the stage in plain words, page or item counts, elapsed time and a sign that the model is still answering |
| v4.11 | 2026-10-13 | Minor, teacher (step 22.1 decision 2): the theme is green, a light green accent with green-tinted greys, light and dark; it replaces the warm neutral that matched Claude Desktop. Exact shades may be adjusted later |
| v1.0 | 2026-09-26 | First draft: confirm-before-save flow, live diagnostic chat, NuExtract3 + a Qwen3.5-9B fine-tune on raw llama.cpp |
| v2.0 | 2026-09-26 | The app runs on its own (Review queue later); printed questions for the teacher; standardized clean test; picture placeholders; listening ignored; `earned/possible` scores; answers anywhere on the paper; prompt profiles + eval harness |
| v3.0 | 2026-09-26 | Runtime Ollama; `numind/nuextract3:Q6_K` (vision) + `qwen3.5:9b` (reasoning) |
| **v4.10.2** | 2026-10-12 | Patch (step 21 re-verifier): §11 the uninstaller does not remove WebView2 (a shared Windows component). |
| v4.10.1 | 2026-10-12 | Patch, teacher (step 21 verifier): §11 exceptions name the installer's install-folder record in the registry (HKCU); the uninstaller always removes it. |
| v4.10 | 2026-10-12 | Minor, teacher (step 21): §11 one app folder lists the installer's Windows entries (Start-menu and desktop shortcuts, the HKCU uninstall entry, the WebView2 fallback download) as accepted exceptions, with their locations kept in `docs/release-notes.md` so they can be removed. |
| v4.9 | 2026-10-12 | Minor, from the teacher's M2 explanation ratings: §14 adds explanations adapted to the student's level. No decision changed. |
| v4.8 | 2026-10-10 | Minor, approved by the teacher: new decision **D26**. A born-digital file (DOCX, or a text-layer PDF with no full-page image) skips answer reading and is a blank test. No existing decision changed |
| v4.7 | 2026-10-06 | Minor, approved by the teacher: new decision **D25**. Unreadable text is written `???`, never guessed, and each page with `???` gets one `unreadable_text` Review item. No existing decision changed. The photo-check "retake" warning is deferred (§2) |
| v4.6 | 2026-09-29 | Minor, from the Phase 0 report and the teacher: the app's Ollama runs with flash attention + q8_0 KV cache (§11); model-call logs are deleted automatically after 45 days (§10.2) |
| v4.5 | 2026-09-29 | Minor: the teacher set the reasoning placeholder to `qwen3.5:4b` (D7; the 9b does not fit 6 GB VRAM). The decision itself is unchanged: the model is still chosen after testing (M2) |
| v4.4 | 2026-09-28 | Minor, after the whole-docs audit and the teacher's answers: **writing** tasks are kept as prompts but not graded (D12); **one app folder**, default `D:\ExamRevisionHelper`, nothing in AppData, and Settings has no "move data folder" option (§10.2, §11); the picked-test check and bank comparison run before answer reading (§8, §9); CSP wording |
| v4.3 | 2026-09-28 | Minor: P1 answered by the teacher. D18 adds that dropping into a thread that has already run is blocked, with a "Start a new thread" button. No existing decision reversed |
| v4.2.1 | 2026-09-28 | Patch: `plan.md` is now the authority for build order and verification (§13 is a summary); open question P1 added (§15) |
| v4.2 | 2026-09-28 | Minor: the three open questions answered by the teacher. Points default to 0.25 per question when none are printed (D13); no parent-facing report (non-goal); no partial credit, a wrong answer scores 0 (D24). No existing decision changed |
| v4.1 | 2026-09-28 | Minor (no decision changed): consistency audit of the data model and workflows. Companion docs updated to data-model v1.1 and llm-design v4.1. Here: S2/S7 use English search, since display names stay English and Vietnamese search is deferred; blank-test cards and the "Blank tests" sidebar group; section references fixed |
| v4.0 | 2026-09-28 | After an independent audit: |
| | | • **Scope cut to extraction first.** A run only reads the photos. Key, grading and explanations come from a separate button (D16). |
| | | • **Photo check step** before processing (D17). |
| | | • **One test per thread** (D18). |
| | | • **The teacher glances at a draft before printing** (D9 revised). |
| | | • **Optional answer key input** as a 🔑-marked photo (D19). The photo check has only 🔑 and an existing-test search; there is no student or typed-key field. |
| | | • **Duplicates:** optional name search, plus text comparison after extraction (D1 revised). |
| | | • **Confidence from token logprobs**; a low-confidence reading is never ✗ (D20). |
| | | • **Picture placeholder = image path** (D11 revised). |
| | | • **Pipeline in Python + LangGraph** (D21). |
| | | • **Stop / resume behaviour** (D22). |
| | | • **Model-agnostic framework first; models are tested afterwards** (D7 revised). |
| | | • Generation, typo fixing, Vietnamese text normalization and encryption deferred (§2). |

## Data model (`docs/data-model.md`)

| Version | Date | Change |
|---|---|---|
| v1.0 | 2026-09-28 | First version: classes, tables, content schema, migrations |
| v1.35 | 2026-10-31 | Minor, step 22.6.6 (re-check of R22.6.6.3): §5.2 the Grade reload after a test change lets a stored key that outranks the run's own (a teacher key) win, keeps the run's pending Review items only for the keys it keeps, and tags the graded questions left without tags (only those are written); §5.3 the v1.9 text corrected: a text save makes an open `points_assumed` item `obsolete` and no path queues a `points_fix` run (`points.save_content` re-scores) |
| v1.34 | 2026-10-31 | Minor, step 22.6.6 (step22.6-plan D15, R22.6.6.3): §5.2 Grade `save` first checks the test content against the one loaded at the start; when a text, points or Extract-again save changed it, it writes nothing and loads the test, keys and answers again, keeping its work for unchanged questions. An attempt's first grade, unfinished at a test-text save, so ends against the saved test. No class or table change |
| v1.33 | 2026-10-30 | Minor, step 22.6.4 (step22.6-plan D4, PRD v9.0 D2/D16): §2.7 `GradeInput.reason` gains `after_extract`, the key run; §5.2 every extract `save` queues it in its own transaction (a grade run on the thread, `attempt_id` None: the key, its check and the skill tags; never grading), at most one per extract run. No table change (`runs.input` is JSON) |
| v1.32 | 2026-10-30 | Minor, step 22.6.3 (step22.6-plan D6): §2.4 `KeyCheck.status` gains `unsure` (the checker answered `?`; its `reasoning` is kept, `answer` is None); the key is `ai_uncertain` with an `uncertain_key` item, as on a disagreement. No table change (`answer_keys.checker` is JSON) |
| v1.31.1 | 2026-10-28 | Patch: the title says ETACH |
| v1.31 | 2026-10-27 | Patch, PRD v8.18: the default app folder is `D:\ETACH` (the app is renamed ETACH). No class or table change |
| v1.30 | 2026-10-26 | Minor, step 22.5.8 (a)(5) (teacher, from the round verifier): a True/False choice relabelled at extraction (`A. FALSE` / `B. TRUE` → `T`/`F`, `renumber.choice_options`) keeps its options as read in `old_options` (`renumber.relabelled_from`); a key-photo letter (`keymap.map_key`) and a student's letter (`boxes.resolve_answers`) on such a choice, or one the first-start pass relabelled, are mapped to `T`/`F` through it (`keys.true_false_key`), so a printed `B` is no longer stored as `B` (key) or dropped as the wrong kind (student answer). No class or table change |
| v1.29 | 2026-10-26 | Minor, step 22.5.8 (a)(3) (teacher's answer to a parked question): §5.3 a `key_unmapped` Fix onto a True/False choice the first-start pass relabelled stores the T/F letter, mapped through the same relabel map from `old_options` (on `A. FALSE` / `B. TRUE`, `B` → `T`); §2.3 `old_options` is also read by that Fix. No class or table change |
| v1.28 | 2026-10-26 | Minor, step 22.5.8 (a) (teacher's answers to the parked questions): §5.3 a key-photo key that replaces a question's key (an AI key, or none after `ai_key_fast` failed) settles that question's open `uncertain_key` items (`fixed`, resolution `{"action": "fix", "value": {"by": "key_photo"}}`); the photo's key is kept. Extract again step 2 notes it. No class or table change |
| v1.27 | 2026-10-26 | Patch, step 22.5.7 (R22.5.7.7): `LlmCall.role` `ocr` is now written by default (GLM-OCR reads the test photos; llm-design v4.48); no class or table change |
| v1.26 | 2026-10-26 | Minor, step 22.5.7 (D13): `LlmCall.role` gains `ocr` (the two-step photo reader's OCR model, `ocr_page`; TEXT column, no migration). The model-output changes of this step (`continued` on the transcribed section, group and question; `RereadPiece` / `RereadPiecesOut`) and the `[extract]` settings `reread_pieces`, `photo_reader`, `ocr_prompt` in `models.toml` are LLM-side, described in llm-design v4.47 §3.1 and §4; no stored class or table changes |
| v1.25 | 2026-10-25 | Minor, step 22.5.6a (D12): §2.4 `AnswerKey.status` gets `from_key_photo` (a key read from the key photo at or above the threshold, no second call); `ai_verified` means a second call agreed; migration `0015_key_photo_status` and its one-time first-start pass move stored key-photo keys no check verified (source `from_key_photo`, `ai_verified`, confidence ≥ 0.7) to `from_key_photo`; §2.2 `OmittedSection.kind` (listening / writing; None for sections stored before) and the listening range on the attempt read; a typed-PDF question's `page_no` is the PDF page its text starts on (`merge_pages(placed=…)`, `PiecePages`) |
| v1.24.1 | 2026-10-25 | Patch, step 22.5.5 checklist (d) (D11f; the verifier's findings): §4 the trajectory's share uses a guessing baseline (a `choice` with k options has chance level 1/k, no stored options 0.25, other forms 0; share = max(0, right − Σ chance) / (counted − Σ chance)) instead of "a right `choice` counts 0.5"; a first grade's report uses the levels `tag_skills` just returned; §2.6 `Explanation.llm_call_id: str | None` (a thread delete sets it NULL, v1.10.1); Accept of an unsure key clears `checker` |
| v1.24 | 2026-10-24 | Minor, step 22.5.5 (step 22.5 decisions D11, D11a–e): §2.4 `AnswerKey.checker: KeyCheck` (`status` disagreed / did_not_finish, `answer`, `reasoning`; a JSON column) stored with an unsure key; §2.5 `Attempt.taken_on` (the date taken, default today; a NULL reads as the `created_at` date) and `WeakPoint.label` / `level` / `held_back` (old reports read as None / None / false); §2.7 `ExtractInput.taken_on`; §3 `question_tags.level` (the question's level from `tag_skills`) and the effective-level rule; migration `0014_checker_taken_on_levels`; §4 the trajectory labels and the report's weak points |
| v1.23 | 2026-10-24 | Minor, step 22.5.4 (decision D10: drop): `TestMetadata.test_difficulty_notice_comment_by_ai` and `DifficultyNotes` / `SectionDifficulty` / `TrapItem` removed; migration `0013_drop_difficulty_notes` and its guard table `difficulty_notes_pending` run a one-time first-start pass that removes the key from every stored test's meta and changes nothing else (§2.2); `LlmCall.role` gains `grading_check` and `extraction_check` (TEXT column, no migration); §2.3b the T/F relabel keeps one explanation row when rows exist for both an old letter and its T/F letter (rows `a` and `f`), and the missing comma after `teacher_override`) |
| v1.22.3 | 2026-10-24 | Patch, step 22.5.3 checklist (d) verifier fix (R22.5.3.8): §2.3b the first-start pass also relabels the letters in the `proposal` of open Review items on a relabelled True/False question (`uncertain_answer` `value` / `alt_value`, `box_inline_conflict` `box_value` / `inline_value`, `uncertain_key` `accepted`), so an Accept stores `T`/`F`; resolved items keep their letters; swapped labels (`T. False`, `F. True`) relabel without a primary-key collision on `explanations` |
| v1.22.2 | 2026-10-24 | Patch, step 22.5.3 checklist (d) (G1, R22.5.3.8): §2.3b True/False: a `choice` with exactly two options that read True and False (any case or order, trailing punctuation ignored; also Đúng/Sai) gets the options `T. True`, `F. False` at extraction (`models.true_false_letters`, used by `renumber.choice_options`); the first-start pass relabels such stored questions and, in the same transaction, their key, student answers and explanation rows (True → `T`, False → `F`); read-only `Question.old_options` keeps the stored options for a revert |
| v1.22.1 | 2026-10-24 | Patch, step 22.5.3 fix: §2.3b the blank check applies to a `word` question with no cue and no options (what a `gap_fill` was); a `word` question with a cue or with options is not blank-checked, as `word_form` / `verb_form` were not |
| v1.22 | 2026-10-24 | Minor, step 22.5.3 (step 22.5 decision D9): `Question.type` (11 values) is replaced by `answer_form` (`choice` · `word` · `sentence` · `writing`) and `context` (`single` · `paragraph`, set by code from the group's `stimulus`; none for `writing`); read-only `old_type` for a revert; migration `0012_answer_form` and its guard table `answer_form_pending` run a one-time first-start pass over the stored tests; True/False is a `choice` with code-added `T`/`F` options; validators, sentence keys, the test text and grading (§2.3b) go by form |
| v1.21.1 | 2026-10-23 | Patch, step 22.5.2 checklist (c) (D8 addition, teacher): §5.8 Extract again `replace` keeps every key on an exact pair, an AI key too, with its source, status and confidence (its open `uncertain_key` item moves with it); only changed and new questions are keyed again |
| v1.21 | 2026-10-23 | Minor, step 22.5.2 (PRD v8.5; D2, D5, D7, D8): `series` table (like `schools`, seeded from `meta.source`); `ExtractInput.series_name` (source + grade, occasion, term, year of the series's newest test), `again_test_id`, `again_mode`; §2.3a headings carry no points (`# II. WORD FORM`, a writing section `[not graded]`; old points brackets still read); `points_each`; untitled sections take their title from the section skill (extraction, and once at first start); option labels cleaned wider ("A.."); §5.8 Extract again into the same test |
| v1.20.1 | 2026-10-19 | Patch, step 22.4.8: the test text writes a section heading's computed points as `[<total> points, <each> each]` (2 decimals); typed points are still ignored |
| v1.20 | 2026-10-19 | Minor, step 22.4.5 (PRD v8.1): `regrade_pending` (test_id); a teacher key change (PUT key, `uncertain_key` / key review fixes) adds the test there instead of queueing `key_verified` runs; `POST /tests/{id}/regrade` queues them and clears it |
| v1.19.1 | 2026-10-19 | Patch, step 22.4.4: a content save re-scores graded attempts directly (no `points_fix` run); a leftover `points_assumed` is closed by a text save |
| v1.19 | 2026-10-19 | Minor, step 22.4.4 (PRD D13 v8.0): equal points: `points_source` gains "equal", section and question points are computed (10 ÷ graded questions) on every content save; heading points in the test text are written from that and ignored when typed; `points_assumed` is no longer created; option labels are stored as a bare letter |
| v1.18.1 | 2026-10-19 | Patch, step 22.4.2: school names compare with Unicode case folding (Vietnamese capitals too), not only SQLite NOCASE |
| v1.18 | 2026-10-19 | Minor, step 22.4.2: `schools` table (id, name, position); seeded from the distinct schools already on tests and students; `tests.school` / `students.school` keep the name; renaming updates them and remakes automatic Test names |
| v1.17 | 2026-10-18 | Minor, step 22.3.7: `occasions` table (code, label, short_name, position, builtin); `TestMetadata.occasion` stays a code; labels and short names come from the table; renaming remakes automatic Test names |
| v1.16 | 2026-10-18 | Minor, step 22.3.6 (decision D6): `Question.answer_start` (the printed opening words of a rewrite/combine answer); §2.3a its text line `   Start: …`; the sentence forms use it first |
| v1.15.1 | 2026-10-17 | Patch, step 22.3.4 as built: `key_forms_pending` (one-time upgrade list); the given words are found in the stem after an arrow, a later stem line, or the cue; a teacher write with the same canonical is stored as sent |
| v1.15 | 2026-10-17 | Minor, step 22.3.4 (teacher's comment 10): a sentence key (`rewrite`, `combine`) carries four accepted forms: the full sentence, without its final full stop, without the words the paper already gives, and without both |
| v1.14.1 | 2026-10-17 | Patch, step 22.3.3 as built: §5.5's "not in this version" line replaced by a pointer to §5.7; only series fields that have a value are copied; Extract again keeps the run's `series_from_test_id` |
| v1.14 | 2026-10-17 | Minor, step 22.3.3 (decisions D1, D3): §5.7 deleting a student; `ExtractInput.series_from_test_id`; copying series details |
| v1.13.2 | 2026-10-15 | Patch, teacher: a test with no name parts is called "Untitled test" |
| v1.13.1 | 2026-10-15 | Patch, step 22.2.7 as built: a teacher-set Test name is stored in `meta.extra["display_name"]` (no schema change); an emptied name box goes back to the automatic name |
| v1.13 | 2026-10-15 | Minor, step 22.2.7: the teacher can set the Test name (`write_test_meta` with `display_name`, recorded in `edited_fields`; clearing it remakes the name); `display_name()` drops an unknown occasion and says "Unit Test" / "15-minute Test" |
| v1.12 | 2026-10-14 | Minor, step 22.2.5 (teacher's answer 10): `test_key_pages` keeps the key photos a test was extracted with; the sweep keeps their files; deleting the test removes the rows (§5.7) |
| v1.11 | 2026-10-14 | Minor, step 22.2.4 (PRD D10 v6.0, decision C): `display_name()` follows the teacher's pattern; §2.3a printed numbers may have gaps; §5.3 a test-text save adds answer rows for new questions and turns a typed `???` into an `unreadable_text` item |
| v1.10.1 | 2026-10-14 | Patch, step 22.2.3 as built: §5.7 a thread's runs take their steps and `llm_calls` with them (foreign keys); pointers on kept rows are cleared; threads of a blank test go with the test |
| v1.10 | 2026-10-14 | Minor, step 22.2.3 (decisions B1, B2): §5.7 deleting a thread or a test |
| v1.9.3 | 2026-10-14 | Patch, step 22.2.2: §5.6 "Use automatic name" clears the stored title |
| v1.9.2 | 2026-10-14 | Patch, step 22.1.5 as built: §5.3 a `validator_failed` item for an answers page is shown in the Answers panel; §5.6 a thread the teacher renames to exactly "New thread" keeps that name |
| v1.9.1 | 2026-10-14 | Patch, step 22.1.5: §2.3a the text grammar (line forms, identity, errors), as built in `domain/test_text.py` |
| v1.9 | 2026-10-13 | Minor, step 22.1.5 (PRD D27): §2.3a the test's text form (render and read back, question ids kept); §5.3 where each Review kind is shown and how a test-text save settles items. The exact text grammar is written in §2.3a by step 22.1.5's implementer (patch bump) |
| v1.8 | 2026-10-13 | Minor, step 22.1.1 (the teacher's app review, comments 7, 11, 13): §5.6 `students.name_search` follows every name write (create or edit); a thread's shown title is the teacher's title, or, while it is the default "New thread", made on read from the current attempt's student and the test's `display_name` |
| v1.7 | 2026-10-09 | Minor, found by M1 `baseline2`: a DOCX text longer than 6 000 characters is split at ingest into several text pages, at section or question breaks, never inside a question (§2.7 `PageInput`) |
| v1.6 | 2026-10-06 | Minor, PRD D25 (teacher decision): the Review kind `unreadable_text` (one per test page with `???`), its proposal fields (§2.8) and its Accept/Fix (§5.3); an answer read as `???` is `reading_unsure` (§2.5). No table change (`review_items.kind` is free text) |
| v1.5.3 | 2026-10-05 | Patch: the `value_norm` comment uses the effective value (an override of `""` is a confirmed blank, not "no override"; found in step 17) |
| v1.5.2 | 2026-09-30 | Patch: `teacher_override = ""` means the teacher confirmed a blank answer (Accept on an unsure blank reading) |
| v1.5.1 | 2026-09-29 | Patch: `File.original_name` listed last, as in the code and plan Appendix A |
| v1.5 | 2026-09-29 | Minor: `File.original_name` (+ `files.original_name`, migration 0002), so the file-name metadata source (§2.2) exists; found in step 9 |
| v1.4 | 2026-09-29 | Minor: old `llm_calls` are deleted automatically after `log_retention_days` (default 45), not only by hand (§5.5) |
| v1.3 | 2026-09-28 | Minor: a `reviewed` attempt that gets a new or reopened open Review item returns to `graded` (score set) or `extracted` (§5.3) |
| v1.2 | 2026-09-28 | Minor, after the whole-docs audit: |
| | | • `Section.graded` (writing sections kept but ungraded; PRD D12); one answer per *graded* question. |
| | | • `Answer.value_norm` as the single normalization (view joins on it); `Answer.low_trust`. |
| | | • `PageInput.text_file_id` + `File.kind="text"`. |
| | | • `merge_unaligned` Review kind; §5.3 rewritten with Accept/Fix per kind and graded-only follow-ups; `GradeInput.reason` gains `points_fix`. |
| | | • The `save` "run already done" guard. |
| | | • FTS prefix matching. |
| | | • One-app-folder layout (§5.5). |
| v1.1.3 | 2026-09-28 | Patch: companion links no longer carry version numbers (plan.md pins them) |
| v1.1.2 | 2026-09-28 | Patch: clearing old logs keeps calls referenced by explanations (the FK would otherwise block the delete) |
| v1.1.1 | 2026-09-28 | Patch: comments for the 0.25 default points and no partial credit (PRD D13, D24) |
| v1.1 | 2026-09-28 | Consistency audit fixes: |
| | | • `save` idempotent: `source_run_id UNIQUE`, attempt `version`, guarded upserts. |
| | | • Key lifecycle (`ai_unverified` …) and precedence. |
| | | • New `grade_reports`, `attempt_pages`, `answers.page_no`. |
| | | • Safe merge (`merged_into`, question alignment). |
| | | • Review items: typed refs, `dedupe_key`, `obsolete`, resolution dispatch. |
| | | • Explanation invalidation on key change. |
| | | • Run input types defined; startup recovery statuses. |
| | | • Redundancy removed: skill tags only in `question_tags`; dropped `unsure_count`, `thread.student_id`, `thread.attempt_id`, `run.current_step`, `taken_on`. |
| | | • Indexes and FKs; file tracking and cleanup; renames (`location`, `try_no`). |

## LLM workflow design (`docs/llm-design.md`)

| Version | Date | Change |
|---|---|---|
| v1.0 | 2026-09-26 | First design: NuExtract3 + a Qwen3.5-9B fine-tune on raw llama.cpp |
| v2.0 | 2026-09-26 | An alternative OCR model was evaluated and rejected (see `.claude/docs/history/`) |
| v3.0 | 2026-09-26 | Ollama; `numind/nuextract3:Q6_K` + `qwen3.5:9b` |
| v4.0 | 2026-09-28 | Python + LangGraph, extract/grade graphs, photo check, text comparison for duplicates, logprob confidence, stop/resume |
| v4.60 | 2026-11-01 | Minor, step 22.6.6 (c) (step22.6-plan D16, the teacher's pick after the three-way GPU check, step22.6-plan §5): `[extract] photo_structure` defaults to `"code"` (way 2b, no structuring call); `"qwen"` and `"ocr_format"` stay as settings (§4 the two-step photo reader, the config block) |
| v4.59 | 2026-10-31 | Minor, step 22.6.6 (re-check of R22.6.6.3): §5 grade `save`'s reload after a test change: a stored key that outranks the run's own (a teacher key) wins, the pending Review items are reset to those of the kept keys (`RESET_PENDINGS` in the reducer), `tag_skills` tags the graded questions left without tags; "Re-grade fan-out" corrected: a points fix queues no run, no path queues `points_fix` |
| v4.58 | 2026-10-31 | Minor, step 22.6.6 (step22.6-plan D15, R22.6.6.3): the grade `save` first checks the test content against the one `load_context` loaded; when a test-text, points or Extract-again save changed it (the run queued, running, stopped or interrupted), it writes nothing and goes back to `load_context` (`Command(goto="load_context")`, not a C.2 edge). Keys, skill tags and explanations made for questions whose text is unchanged are kept; those of deleted or changed questions are dropped, and Review items for a question the test no longer has are not written (data-model v1.34 §5.2) |
| v4.57 | 2026-10-30 | Minor, step 22.6.5 (2a; step22.6-plan D7): `[extract] photo_structure = "ocr_format"` is built. The photo page gets one `ocr_format_page` call (the `ocr` role; its user message is `prompts/base/ocr_format_page.md`: the app's test-text format in five short lines and one made-up example, in place of `ocr_prompt`), answer boxes are removed (`strip_answer_boxes`), and `test_text.read_ocr_page` reads the text with the test-text reader into the page's `TranscribeOut`, no structuring call. A page that starts without a heading starts with an untitled section (joined to the previous page's last section, like 2b); a page the reader cannot read keeps its text as one group's passage and gets `validator_failed` (task `ocr_format_page`, the reader's reason). `test_text.read` and way 1's `ocr_page` call are unchanged |
| v4.56 | 2026-10-30 | Minor, step 22.6.5 (step22.6-plan D7): `[extract] photo_structure` = `"qwen"` (way 1, the default; `structure_text_page` as before), `"code"` (way 2b: `domain/ocr_structure.py` structures the OCR text by the printed layout, no model call; lines it cannot place are kept and the page gets a `validator_failed` item, task `ocr_structure`) or `"ocr_format"` (way 2a, built by the second step agent; until then it runs way 1); OCR reader only. `erh eval --photo-structure`; a row's `mode` gets `+code` or `+ocr_format` after `+ocr` (§3.1, §4) |
| v4.55 | 2026-10-30 | Minor, step 22.6.4 (step22.6-plan D14): `DELETE /tests/{id}` and `DELETE /students/{id}` no longer answer 409 for the key run. When the only unfinished runs the delete touches are `after_extract` key runs, they are discarded through the run manager (`run.discarded`) and the delete goes ahead; any other unfinished run still gives 409 and nothing is discarded (§2 route rows) |
| v4.54 | 2026-10-30 | Minor, step 22.6.4 (step22.6-plan D12): Extract again and Delete thread no longer answer 409 for the key run. When the thread's only unfinished runs are `after_extract` key runs (queued, running, stopping, stopped or interrupted), the route discards them through the run manager (a running one is cancelled; `run.discarded`) and goes ahead; any other unfinished run still gives 409, and a 409 for the mode choice discards nothing. `erh run`, `erh eval` and `erh record -- run` queue no key run (`ExtractDeps.key_after_extract` False); `erh serve` keeps it |
| v4.53 | 2026-10-30 | Minor, step 22.6.4 (step22.6-plan D4, PRD v9.0 D2/D16, data-model v1.33): the **key run**. Every extract `save` queues a grade run without an attempt, reason `after_extract` (the AI key for the questions without one, its check, the skill tags; never grading); the run manager loads rows a run queued after every `done` run (`run.queued`) and runs it next (FIFO). Run kinds unchanged (`grade`); it has the grade stages (the skipped ones count as done); `/runs/active` and the run events show it, the UI tells it by `input.reason`. A later Grade keys only questions still without a key. While it is queued or running it counts as an active run of the thread (Extract again and Delete answer 409) |
| v4.52 | 2026-10-30 | Minor, step 22.6.3 (step22.6-plan D6): `verify_key` may answer `?` when not sure; code handles `?` (spaces ignored) as a disagreement (`ai_uncertain` + `uncertain_key`) and stores the `checker` as `unsure` with its reasoning (data-model v1.32); its prompt gets two short lines (answer `?` when not sure; the output is limited, so stop and answer `?` rather than run out, folded into "keep `reasoning` short"); `num_predict` 1500 → 1000; a cut-off answer stays `did_not_finish` |
| v4.51 | 2026-10-30 | Minor, step 22.6.2 (step22.6-plan D5, PRD v8.28): `resolve_answers` judges a paper blank also when fewer than 20% of its answers are read with confidence (`[extract] blank_share`, default `boxes.BLANK_SHARE`; 0 keeps the rule before, for the recorded S1 grade replay; a `???` counts), and then keeps no answer Review items; a value spelled `null`, `none` or `n/a` is not read |
| v4.50 | 2026-10-30 | Minor, step 22.6.1 (step22.6-plan D2, D3): on the photo path, code removes answer boxes from GLM-OCR's text before `structure_text_page`, and that call's prompt gets the `photo_rules` input (leave out answer boxes; a number-and-options question has a null `stem`, with a one-line example); the typed prompt renders unchanged |
| v4.49.1 | 2026-10-28 | Patch: the title says ETACH |
| v4.49 | 2026-10-27 | Patch, PRD v8.18: the default app folder is `D:\ETACH` (§2 diagram) |
| v4.48 | 2026-10-26 | Minor, step 22.5.7 (R22.5.7.7; teacher, G4): `[extract] photo_reader` defaults to `"ocr"`; `ocr` (`glm-ocr`) is a default role, listed, checked and offered for download (settings, `/system/status`, `/settings/models/pull`, `/models` and the suggested tags) unless `photo_reader = "vision"` and no `[roles.ocr]`; tiles stay off; `erh eval --photo-reader`, an OCR-reader row's `mode` gets `+ocr` (§3.1, §4) |
| v4.47 | 2026-10-26 | Minor, step 22.5.7 (comment 4, D13): photo page breaks: `transcribe_page` for page N+1 gets `previous_page`, the last open unit of page N as already read (`renumber.open_unit`), and may mark a section, group or question `continued`; `merge_and_normalize` joins them (§4). The targeted re-read: `[extract] reread_pieces` (default off) gives a page that fails a check one `reread_pieces` call on `extraction_check` for only its failing or missing questions (`RereadPiecesOut`), patched in by code (`renumber.reread_asks`, `apply_reread`), kept only if the page's failures do not increase (§4, §5.1). The two-step photo reader: `[extract] photo_reader` = `"vision"` (default) or `"ocr"`, and `ocr_prompt`; role `ocr` (GLM-OCR, tag `glm-ocr`, present only when used, no default download); task `ocr_page` (plain text, no `format`) then `structure_text_page` on that text; the student answers stay on vision (§3.1, §4). §3.1 `retry_capped_output` sample corrected (`extraction_check = false`) and gains `ocr = false`. §8: the eval's answer-number errors, `number_renumbering_errors` and `number_reading_errors` |
| v4.46.3 | 2026-10-26 | Patch, step 22.5.6 second re-check rework (D12): `locate_pages` chooses every group start, group end and question place for a joined typed-PDF piece at once (a scored monotone alignment) in place of a forward search, so a number printed mid-line, an answer-key table or a later section numbering from 1 no longer drags later questions; "(Câu 17)" is a marker |
| v4.46.2 | 2026-10-25 | Patch, step 22.5.6 re-check fix (D12): `locate_pages` matches the model's text against the PDF text both folded the same way (accents, case, curly quotes, dashes, blanks with their glued markers), so a passage ending in "__(3)__" or "3.____" and "Mary’s" for "Mary's" are found; a marker counts only in marker form; a stem-less question with no marker keeps its passage |
| v4.46.1 | 2026-10-25 | Patch, step 22.5.6 verifier fixes (D12): how a joined typed-PDF question finds its page (a passage question by its marker in the passage, else its passage; other questions after the end of their group's stimulus) and what counts as repeated output (a whole block: the same section, stimulus and questions again) |
| v4.46 | 2026-10-25 | Minor, step 22.5.6a (D12, comment 4): a typed PDF's page texts are joined and cut like a Word file's text (`join_typed_pdf_pages`; state `text_pieces`, `absorbed_pages` for pages whose whole text an earlier piece took, `placed` so a question gets the page its text starts on and a picture stays on its printed page); `structure_text_page` has two `answer_start` examples (with "=>" and with no arrow) and a code guard against repeated output (state `repeated_pages`, a `validator_failed` item "repeated output"); `read_answers_page` asks each page only for its own questions (by `page_no`), with no "printed on page N" hints; `read_key_pages` ignores explanations on the key pages; `map_key` stores a confident key-photo key as `from_key_photo` (not `ai_verified`); `GET /attempts/{id}` carries `listening_skipped` |
| v4.45.1 | 2026-10-25 | Patch, step 22.5.5 checklist (d) (the verifier's findings): §5 `weak_points` uses the state's `tag_skills` levels on a first grade; the summary's `wrong_answers` lines leave out held-back skills (a line with only held-back skills is left out) |
| v4.45 | 2026-10-24 | Minor, step 22.5.5a (step 22.5 decisions D11, D11a–e): §2 `PATCH /attempts/{id}` (the date taken) and `GET /students/{id}` carries `skills` (label, level, weak, held back, per-paper results); §5 `tag_skills` output gets a `level` per question (required, nullable: A1–B2 or null), stored on the question's tag rows; the section taxonomy (`sections.txt`) has a level column (the base levels); `verify_key` stores the checker's answer and reasoning, or that it did not finish, with the unsure key; `weak_points` classifies each skill by the student's trajectory (data-model §4) and the summary input gets skill names, not codes, and only the weak points not held back |
| v4.44 | 2026-10-24 | Minor, step 22.5.4a item 7: §5 `tag_skills` makes one call per graded section (inputs `section_id`, `question_ids`, `skill_list`, `section_text`: the section's heading, instructions, passage and questions), still once per test, at most 3 tags per question; a failed call skips only that section's tags (§5.1) |
| v4.43 | 2026-10-24 | Minor, step 22.5.4a items 1–6 and 8: §3.1 roles `grading_check` (used by `verify_key`) and `extraction_check` (unused until step 22.5.7), both qwen3.5:4b by default; an older `models.toml` uses the defaults; `retry_capped_output` names all four roles. §5 grading prompts: a `sentence` question's line carries "Answer line starts with: …" (judge, `ai_key_fast`, `verify_key`, `explain`); the judge may accept a student answer that continues those words; `JudgeOut` = reason, verdict; `ai_key_fast` names only the questions without a key (`key_questions`); `ExplainOut` = reasoning, text_vi, error_type, the reasoning kept only in `llm_calls`; explain says "a Vietnamese student", tone "a teenager", cap 512 kept (≈211 tokens). `difficulty_notes` removed (D10: drop) from the graph, progress stages and §5.1; `erh eval --role` takes the four roles |
| v4.42.1 | 2026-10-24 | Patch: §8 says eval-history rows before and after step 22.5.3 are not comparable in `structure_types` (it now holds answer-form accuracy) or `structure_overall` |
| v4.42 | 2026-10-24 | Minor, step 22.5.3 (step 22.5 decision D9): the page prompts (`transcribe_page`, `structure_text_page`) ask for `answer_form` (`choice` · `word` · `sentence` · `writing`, one line each, by the printed layout) instead of the 11 types, and `answer_start` for `sentence`; `context` is set by code. The LLM output schemas take `answer_form`, not `type`; answer reading has `ChoiceReading` (`value` = one of the question's option labels, listed per call; A–D without options; T/F for True/False) and `TextReading` (`word`, `sentence`); `ai_key_fast` words its rules by form; `grade` goes by form (§5): combine's own rule, ordering/matching exact-match and the separate T/F rule go |
| v4.41 | 2026-10-23 | Minor, step 22.5.2 (D5, D7, D8): `GET/POST/PATCH/DELETE /series` (like `/schools`); `ExtractInput.series_name`, `again_test_id`, `again_mode`; `POST /threads/{id}/extract-again` takes `{mode?}` ("replace" or "copy"); `GET /threads/{id}` carries `other_thread_count`, `GET /tests/{id}` carries `points_each`; `compare_bank` leaves out the test an Extract again came from |
| v4.40 | 2026-10-23 | Minor, step 22.5.1: `GET /tests` items carry `created_at`; `?q=` also finds a test by its id ("T-0008", "t-0008", "T0008") |
| v4.39 | 2026-10-19 | Minor, teacher (22.4.7 GPU check): the worked example and the three structure rules are in `structure_text_page` only; `transcribe_page` keeps its 0.4.0 text |
| v4.38 | 2026-10-19 | Minor, step 22.4.7 (teacher D6): `transcribe_page` and `structure_text_page` carry one worked example (a made-up page and its correct output) and three structure rules: a numbered sentence keeps its own sentence as its stem; a Roman-numeral heading always starts a new section; instruction lines (also Vietnamese ones such as "Thí sinh …", "Chú ý: …") belong to the section's instructions, never a section |
| v4.37 | 2026-10-19 | Minor, step 22.4.6: the attempt report carries `skill_name` for each weak point (from the taxonomy files) and lists explanations in printed-question order |
| v4.36 | 2026-10-19 | Minor, step 22.4.5: `POST /tests/{id}/regrade`; `GET /tests/{id}` and the thread's test carry `regrade_pending`; `PUT /tests/{id}/keys/{qid}` no longer queues runs (`run_ids` empty) |
| v4.35 | 2026-10-19 | Minor, step 22.4.4: the merge node gives equal points (PRD D13 v8.0) and bare option letters; no `points_assumed` |
| v4.34.1 | 2026-10-19 | Patch, step 22.4.2: `PATCH /students/{id}` also takes `school` |
| v4.34 | 2026-10-19 | Minor, step 22.4.2: `GET /schools`, `POST /schools`, `PATCH /schools/{id}`, `DELETE /schools/{id}` (409 while used) |
| v4.33 | 2026-10-18 | Minor, step 22.3.7: `GET /occasions`, `POST /occasions`, `PATCH /occasions/{code}`, `DELETE /occasions/{code}` (409 while used or built-in) |
| v4.32 | 2026-10-18 | Minor, step 22.3.6 (PRD v7.1, decisions D5, D6): typed pages go through a text-only structuring task instead of `transcribe_page`; transcription and structuring fill `answer_start` for rewrite/combine questions |
| v4.31 | 2026-10-18 | Minor, step 22.3.5 (PRD D7 v7.0): `GET /models` (installed models, sizes, roles using them), `POST /models/pull` `{name}` (progress over SSE, cancellable), `DELETE /models/{name}` (409 while a role uses it); the default vision tag is `qwen3.5:4b` |
| v4.30 | 2026-10-17 | Minor, step 22.3.3: `DELETE /students/{id}` (+ `GET /students/{id}/delete-preview`), `POST /tests/{id}/copy-details` `{from_test_id}`; `ExtractInput.series_from_test_id` applied at save |
| v4.29 | 2026-10-17 | Minor, step 22.3.2 (teacher's comment 14): `POST /threads/{id}/extract-again` reruns the extraction of the thread's last photos and supersedes the current attempt |
| v4.28 | 2026-10-15 | Patch, step 22.2.7: `PATCH /tests/{id}` metadata may set `display_name` (a string keeps it as typed; `null` goes back to the automatic name), `units` and `tags` |
| v4.27 | 2026-10-14 | Patch, step 22.2.5: `key_pages` on `GET /tests/{id}` comes from `test_key_pages` (data-model v1.12), so it is filled for tests extracted from now on |
| v4.26 | 2026-10-14 | Minor, step 22.2.3: `DELETE /threads/{id}`, `DELETE /tests/{id}` (with `GET /tests/{id}/delete-preview`), `GET /students` adds class and thread counts, `GET /students/{id}` lists the student's threads |
| v4.25 | 2026-10-14 | Minor, step 22.2.2: `PATCH /threads/{id}` `{title: null}` goes back to the automatic title |
| v4.24 | 2026-10-14 | Minor, step 22.2.1 (teacher): the grade stage "Finding weak points" is "Updating student ability"; `run.progress` counts the item being worked on ("Reading page 3 of 4") and says when a page is checked again; the streaming heartbeat starts with the call, so the live sign beats during the wait for the first token |
| v4.23 | 2026-10-14 | Minor, step 22.1.6 (PRD D4 v5.0): `POST /tests/{id}/export` `{what: "test" \| "key"}` and `POST /attempts/{id}/report/export` write a DOCX into `<app>\exports\` and return its path |
| v4.22.1 | 2026-10-14 | Patch, step 22.1.5 as built: the `PATCH /tests/{id}` 422 bodies and its response |
| v4.22 | 2026-10-13 | Minor, step 22.1.5 (PRD D27): `GET /tests/{id}` adds `content_text` and the test's open Review items; `PATCH /tests/{id}` accepts `{content_text, drop_confirmed?}`; `GET /threads` and `GET /tests` add `open_review_count`. The `/review` routes stay (the panels call `resolve`); the UI has no queue |
| v4.21 | 2026-10-13 | Minor, step 22.1.4 (photos in the workspace): `GET /tests/{id}` also returns `pages` (the test's page photos, `{page_no, file_id}`) and `key_pages` (the key photos the test was extracted with, if stored) |
| v4.20.1 | 2026-10-13 | Patch, found in step 22.1.3: `run.progress` also carries `unit` (page, section or question); `run.done` carries `percent` 100 |
| v4.20 | 2026-10-13 | Minor, step 22.1.3 (teacher's comment 2): §2 run progress: each graph has a fixed list of stages; `run.step_started` and `run.progress` carry `stage`, `stages` and `percent`; a model call publishes `run.progress` with `tokens` at least every 5 s while it streams; `GET /runs/active` carries the same fields |
| v4.19 | 2026-10-13 | Minor, step 22.1.1 (the teacher's app review, comments 7, 11): §2 routes `PATCH /threads/{id}` (rename) and `PATCH /students/{id}` (edit name or class) |
| v4.18 | 2026-10-12 | Minor, step 21: §2 the release shell starts the frozen sidecar (`<app>\sidecar\erh.exe serve`, PyInstaller folder build, `ERH_APP_DIR=<app>`); a missing Ollama no longer stops the shell (no `ollama serve`, status `unreachable`, the first-run screen shows); `/system/status` also returns `sidecar_version` and `replay`; §9 Q8 answered in `docs/release-notes.md` |
| v4.17.2 | 2026-10-12 | Patch: §5 `explain` length is ≤ 3 sentences plus short Vietnamese glosses (every key word or phrase, the rule's meaning) and, for a rewrite, one line with the correct sentence's Vietnamese meaning; about 70 words (M2 explain prompt 2, teacher's re-rating notes) |
| v4.17.1 | 2026-10-12 | Patch: §5 `explain` allows one short key-word gloss besides the ≤ 3 sentences (the M2 explain prompt, teacher's rating notes) |
| v4.17 | 2026-10-12 | Minor, the teacher's decision after M2: thinking is off for every grading task (`verify_key` and `judge_rewrites` were on). On held-out, qwen3.5:4b ended 111 of 128 `verify_key` and all `judge_rewrites` calls empty after using the whole budget thinking (`docs/m2-report.md` §2). |
| v4.16 | 2026-10-11 | Minor, M1 listening safety net (teacher): in `merge_and_normalize`, a `listening` section whose groups hold a question with a stem or options is stored and graded like a `questions` section (not omitted), with one pending `validator_failed` per start page (`reason: listening_with_questions`) (§5.1) |
| v4.15.1 | 2026-10-10 | Patch: §4 D26 wording matches the build (every DOCX page counts; the 100-character and 80 % thresholds; the node runs once with no call) |
| v4.15 | 2026-10-10 | Minor, PRD D26 (teacher): `read_answers_page` is skipped for born-digital input (DOCX text pages; PDF pages with a full text layer and no full-page image); the run saves a blank test (§4) |
| v4.14 | 2026-10-10 | Minor, M1 speed bundle 1 (teacher): `[extract] retranscribe_tiles` (default off; off → a failing page goes straight to `validator_failed`), a tile reading replaces a page only with fewer validator failures, a text-layer page is never tiled (§4); `[client] retry_capped_output` per role: no invalid-retry for a vision output that hit `num_predict` (`output_capped`), the reasoning role keeps it until M2 (§3.1, §3.2, §5.1) |
| v4.13 | 2026-10-09 | Minor, found by M1 `baseline2`: a long DOCX text arrives as several text pages (data-model v1.7); the `transcribe_page` / `retranscribe_tiles` output cap is 8192 tokens (was 4096), which still fits `num_ctx` 16384 with a 6 000-character text page (§4) |
| v4.12 | 2026-10-08 | Minor, found by the M1 baseline (bug B1): every request sets `truncate: false`; a prompt that can't fit `num_ctx` is a failed call (`prompt_truncated`, no retry, row `error`) handled as in §5.1 (§3.2, §5.1). `alt_question_id` in the `read_answers_page` schema is free text checked in code; an invalid ID is dropped (§4) |
| v4.11 | 2026-10-06 | Minor, PRD D25 (teacher decision): `transcribe_page`, `retranscribe_tiles` and `read_answers_page` write unreadable text as `???`, never a guess (§4, §8); `merge_and_normalize` creates one pending `unreadable_text` per page with `???`; `resolve_answers` makes a `???` answer `reading_unsure`. No new node, no interaction during the run (P1) |
| v4.10 | 2026-10-04 | Minor: `GET /tests/{id}` also returns each picture's stored path (`picture_paths`), so the D11 placeholder names the real file and extension (found in step 16) |
| v4.9 | 2026-10-02 | Minor: CORS for the app's own origins only (the webview and the sidecar are different origins; found in step 13) |
| v4.8 | 2026-10-01 | Minor: SSE adds `run.discarded` (the running indicator must clear on Discard; found in step 7) |
| v4.7.1 | 2026-09-29 | Patch: §6 and §9 mark the Phase 0 questions (Q1, Q2, single-token letter) as answered |
| v4.7 | 2026-09-29 | Minor, Phase 0 decisions: `ollama serve` adds FLASH_ATTENTION=1 + KV_CACHE_TYPE=q8_0 (§2); nuextract `also_format = true` and `[confidence] fallback = "none"` (§3.1, §6) |
| v4.6 | 2026-09-29 | Minor: reasoning placeholder `qwen3.5:4b` in §3.1 (PRD v4.5) |
| v4.5 | 2026-09-28 | Minor: `ExtractState.key_raw` is a list of (printed label, answer) entries in page order, because a key page can print a label twice (plan B.3) |
| v4.4 | 2026-09-28 | Minor, after the whole-docs audit: |
| | | • Writing sections: prompt only, not read or graded. |
| | | • Query token for `/files/{id}` and `/events`. |
| | | • `/runs/active` lists stopped/interrupted runs; `run.interrupted` event. |
| | | • Text pages via `text_file_id`. |
| | | • Confidence cap relative to the threshold. |
| | | • Grading rules for "no key", ordering, matching and combine. |
| | | • §5.1: failure rules when a call fails twice. |
| | | • Fan-out only for graded attempts, plus `points_fix`. |
| | | • Documented fallbacks, including `none`. |
| | | • One-app-folder paths; exact thinking caps. |
| v4.3.1 | 2026-09-28 | Patch: companion links no longer carry version numbers (plan.md pins them) |
| v4.3 | 2026-09-28 | Minor, for plan v2.0: the complete API route inventory (threads, files, students, settings, maintenance, system status); the CLI list; the cassette format and matching; `eval-history.csv` committed + a fixture manifest; thinking caps as numbers (1500/400); grade gate node named `verify_gate` |
| v4.2 | 2026-09-28 | Minor: default of 0.25 points per question when none are printed (flagged `points_assumed`); no partial credit (PRD D24) |
| v4.1 | 2026-09-28 | Consistency audit fixes: |
| | | • Extract graph: `read_header` + sanity check on the picked path; `retranscribe_tiles` node; separate cursors; `compare_bank` before answer reading; new `map_key` node; generic profile for transcription. |
| | | • Grade graph: `load_context` (blank tests); `ai_unverified` + per-attempt verify rule; override = confident; `weak_points` uses in-state verdicts; blank branch; idempotent guarded `save`; re-grade fan-out. |
| | | • Review items are only written in `save`. |
| | | • More API routes. |
| | | • Startup recovery for all statuses, `discarded`, `ainvoke`, checkpoint purge. |

## Repository structure (`docs/structure.md`)

| Version | Date | Change |
|---|---|---|
| v1.1.157 | 2026-11-02 | Patch: §6 row 22 adds `docs/initial-plan/waivers/22.md` (the draft; the teacher signs) |
| v1.1.156 | 2026-11-02 | Patch: §6 row 22.6.8 (b) adds the light window frame (`app/src-tauri/src/lib.rs`, D18) |
| v1.1.155 | 2026-11-02 | Patch: §6 row 22.6.6 (c) names the default-way paths (the 22.6.8 verifier's finding 1); row 22.6.8 (b) adds the 22.6.8 verifier's low fixes (`app/scripts/tauri-config.test.ts` icon check, the `eval/harness.py` docstring) |
| v1.1.154 | 2026-11-02 | Patch: §6 row 22.6.8 (installer 0.6.1) |
| v1.1.153 | 2026-11-02 | Patch: the map names `src-tauri/icons/` (the app icon and its sources, step 22.6.7); §6 row 22.6.7 (the logo) |
| v1.1.152 | 2026-10-31 | Patch: §6 row 22.6.6 adds the merge preview (`app/src/features/cards/`) |
| v1.1.151 | 2026-10-31 | Patch: §6 row 22.6.4 (b) names `App.tsx`, `AppShell.tsx`; row 22.6.6 adds the fixes (R22.6.6.3–5) |
| v1.1.150 | 2026-10-30 | Patch: §6 row 22.6.6 (a) (the round verifier) |
| v1.1.149 | 2026-10-30 | Patch: §6 row 22.6.5 (two photo ways without qwen) |
| v1.1.148 | 2026-10-30 | Patch: §6 row 22.6.4 (a) adds the test and student delete routes (D14) |
| v1.1.147 | 2026-10-30 | Patch: §6 row 22.6.4 (a) adds the thread routes (D12) and `cli.py` |
| v1.1.146 | 2026-10-30 | Patch: §6 row 22.6.4 (the key after every extraction; sidecar and screens) |
| v1.1.145 | 2026-10-30 | Patch: §6 row 22.6.2 adds the E2E seeds (`blank_share = 0` for S1) |
| v1.1.144 | 2026-10-30 | Patch: §6 row 22.6.3 (the checker may be unsure) |
| v1.1.143 | 2026-10-30 | Patch: §6 row 22.6.2 (blank papers, not-read words) |
| v1.1.142 | 2026-10-30 | Patch: §6 row 22.6.1 (answer boxes, repeated options, the photo rules) |
| v1.1.141 | 2026-10-28 | Patch: the title says ETACH |
| v1.1.140 | 2026-10-27 | Minor: §6 row 22.5.8 adds (h), the layout |
| v1.1.139 | 2026-10-27 | Minor: §6 row 22.5.8 adds (g), the rename to ETACH and the default folder `D:\ETACH` |
| v1.1.138 | 2026-10-27 | Minor: §6 row 22.5.8 (f) adds the font change (`app/package.json`, `app/package-lock.json` for the font packages); the directory map names Faustina |
| v1.1.137 | 2026-10-26 | Minor: §6 row 22.5.8 adds (f), the theme (tokens, dark-mode removal, the colour uses under `app/src/`, their tests and the `app/e2e/` screenshots) |
| v1.1.136 | 2026-10-26 | Minor: §6 row 22.5.8 adds the domain paths of (a)(5), the T/F letters |
| v1.1.135 | 2026-10-26 | Patch: §6 row 22.5.7 names `llm/client.py` and `llm/adapters/` (changed in 0039b6e, found by the round verifier) |
| v1.1.134 | 2026-10-26 | Patch: §6 row 22.5.8 also names the `app/e2e/` expectations of (a) |
| v1.1.133 | 2026-10-26 | Minor: §6 row 22.5.8 (the parked answers, installer 0.6.0) |
| v1.1.132 | 2026-10-26 | Minor: §6 row 22.5.7 adds the R22.5.7.7 paths (the OCR reader as default) |
| v1.1.131 | 2026-10-26 | Minor: §6 row 22.5.7 (photos) |
| v1.1.130 | 2026-10-25 | Minor: §6 row 22.5.6 (typed pages; reading student answers and keys) |
| v1.1.129 | 2026-10-24 | Minor: §6 row 22.5.5 adds `domain/merge.py` (question levels kept on a merge; asked by the builder) |
| v1.1.128 | 2026-10-24 | Minor: §6 row 22.5.5 (checker's answer, weak points over time) |
| v1.1.127 | 2026-10-24 | Minor: §6 row 22.5.4 adds `eval/harness.py` (edited by the builder, found by the verifier) |
| v1.1.126 | 2026-10-24 | Minor: §6 row 22.5.4 adds `LlmCall.role` and `cli.py` `--role` names (asked by the builder) |
| v1.1.125 | 2026-10-24 | Minor: §6 row 22.5.4 (grading calls) |
| v1.1.124 | 2026-10-23 | Minor: §6 row 22.5.3 adds `ai_key_fast.md` (type words), `page_example.md`, `llm/tasks.py`, plan.md Appendix A and B.5 (asked by the builder) |
| v1.1.123 | 2026-10-23 | Minor: §6 row 22.5.3 (fewer question types) |
| v1.1.122 | 2026-10-23 | Minor: §6 row 22.5.2 (settings, series, test text, Extract again) |
| v1.1.121 | 2026-10-23 | Minor: §6 row 22.5.1 (moving around and lists) |
| v1.1.120 | 2026-10-20 | Minor: §6 row 22.4.9 (installer 0.5.0) |
| v1.1.119 | 2026-10-19 | Minor: §6 row 22.4.8 (the teacher's answers) |
| v1.1.118 | 2026-10-19 | Minor: §6 row 22.4.7 (worked example) |
| v1.1.117 | 2026-10-19 | Minor: §6 row 22.4.6 (report wording and order) |
| v1.1.116 | 2026-10-19 | Minor: §6 row 22.4.5 (verifying keys, re-grade) |
| v1.1.115.1 | 2026-10-19 | Patch: §6 row 22.4.4 names `domain/models.py` (`points_source` only) |
| v1.1.115 | 2026-10-19 | Minor: §6 row 22.4.4 (option letters, points out of 10) |
| v1.1.114 | 2026-10-19 | Minor: §6 row 22.4.3 (new-thread pickers) |
| v1.1.113 | 2026-10-19 | Minor: §6 row 22.4.2 (Settings tabs, schools) |
| v1.1.112 | 2026-10-19 | Minor: §6 row 22.4.1 (screen fixes) |
| v1.1.111 | 2026-10-19 | Minor: §6 row 22.3.8 (installer 0.4.0) |
| v1.1.110 | 2026-10-18 | Patch: §6 row 22.3.6 names `domain/{renumber,llm_schemas}.py` (one line each, found by the verifier) |
| v1.1.109 | 2026-10-18 | Patch: §6 row 22.3.7: `store/db.py` also loads occasion names at open (found by the builder) |
| v1.1.108 | 2026-10-18 | Minor: §6 row 22.3.7 (edit occasions) |
| v1.1.107 | 2026-10-18 | Patch: §6 row 22.3.6 adds `eval/harness.py` (`PAGE_TASKS`) and the validator card's task name (found by the builder) |
| v1.1.106 | 2026-10-18 | Minor: §6 row 22.3.6 (typed files as text, sentence openings) |
| v1.1.105 | 2026-10-18 | Minor: §6 row 22.3.5 (models) |
| v1.1.104 | 2026-10-18 | Patch: §6 row 22.3.4 adds `eval/metrics.py` (expected keys get the sentence forms before comparing; found by the builder) |
| v1.1.103 | 2026-10-17 | Minor: §6 row 22.3.4 (sentence keys) |
| v1.1.102 | 2026-10-17 | Minor: §6 row 22.3.3 (delete a student, series details) |
| v1.1.101 | 2026-10-17 | Patch: §6 row 22.3.2 adds the extract-again route (`api/routes/{threads,runs}.py`, `runtime/`) |
| v1.1.100 | 2026-10-17 | Minor: §6 row 22.3.2 (straight to work) |
| v1.1.99 | 2026-10-17 | Minor: §6 row 22.3.1 (photo check and small fixes); `docs/initial-plan/phases-testing/step22.3-plan.md` added |
| v1.1.98 | 2026-10-15 | Patch: §6 row 22.2.7: installer.nsi header comment too; `docs/initial-plan/plan.md` checklist ticks |
| v1.1.97 | 2026-10-15 | Minor: §6 row 22.2.7 (the teacher's answers, 0.3.0 rebuilt) |
| v1.1.96 | 2026-10-14 | Minor: §6 row 22.2.6 (installer 0.3.0) |
| v1.1.95 | 2026-10-14 | Minor: §6 row 22.2.5 (key photos, version, uninstall) |
| v1.1.94 | 2026-10-14 | Patch: §6 row 22.2.4 adds `store/db.py` (`_meta_text` only: occasion codes stay searchable) |
| v1.1.93 | 2026-10-14 | Minor: §6 row 22.2.4 (printed numbers, test text, test details and name) |
| v1.1.92 | 2026-10-14 | Patch: §6 row 22.2.3 adds `api/app.py` (`CORS_METHODS` gains DELETE) and `tests/unit/api/test_cors.py` (found by the builder) |
| v1.1.91 | 2026-10-14 | Minor: §6 row 22.2.3 (delete, Students tab) |
| v1.1.90 | 2026-10-14 | Minor: §6 row 22.2.2 (moving around and safety) |
| v1.1.89 | 2026-10-14 | Minor: §6 row 22.2.1 (words on screen); `docs/initial-plan/plan-extraction-quality.md` and `docs/initial-plan/phases-testing/step22.2-plan.md` added |
| v1.1.88 | 2026-10-14 | Patch: §6 row 22.1.7 adds `sidecar/schema/openapi.json` (its `info.version` follows the version; found by the builder) |
| v1.1.87 | 2026-10-14 | Minor: §6 row 22.1.7 (new installer) |
| v1.1.86 | 2026-10-13 | Minor: §6 row 22.1.6 (DOCX export) |
| v1.1.85 | 2026-10-13 | Minor: §6 row 22.1.5 (the test as a page, Review in place) |
| v1.1.84 | 2026-10-13 | Minor: §6 row 22.1.4 (workspace view and photos) |
| v1.1.83 | 2026-10-13 | Minor: §6 row 22.1.3 (progress bar) |
| v1.1.82 | 2026-10-13 | Minor: §6 row 22.1.2 (green theme) |
| v1.1.81 | 2026-10-13 | Minor: §6 row 22.1.1 (small fixes from the teacher's app review) |
| v1.1.80 | 2026-10-13 | Patch: `ui-review-22.1.md` renamed `step22.1-plan.md` (teacher) |
| v1.1.79 | 2026-10-13 | Patch: `docs/` keeps only project-wide documents; phase documents (m1/m2 reports, ui-review-22.1, step 22's drafts) live in `docs/initial-plan/phases-testing/` (§5 map, §6 rows 22 and M1/M2) |
| v1.1.78 | 2026-10-13 | Patch: §5 map adds `docs/ui-review-22.1.md` (the teacher's first app review and the work-package plan) |
| v1.1.77 | 2026-10-12 | Patch: §6 row 21 adds `app/e2e/` (tiles-on replay for the Playwright e2e, broken since 93cea8b); §7 note |
| v1.1.76 | 2026-10-12 | Patch: §6 row 21 widened (sidecar freeze entry and dev dependency, first-run mount, release E2E_SHELL, the relative restore-path fix from §7, `.gitignore` build output); header version corrected |
| v1.1.75 | 2026-10-12 | Patch: §7 M2 wording (109 of 111 empty), parked explain notes, tuning judge (M2 verifier) |
| v1.1.74 | 2026-10-12 | Patch: §7 explain prompt 2 chosen (teacher) |
| v1.1.73 | 2026-10-12 | Patch: §6 row M1/M2 adds M2 explain prompt 2; §7 think-off results (judge and key check accepted; teacher) |
| v1.1.72 | 2026-10-12 | Patch: §6 row M1/M2 adds M2 think off and the M2 explain prompt (teacher) |
| v1.1.71 | 2026-10-12 | Patch: §7 M2 result corrected (unflagged keys 13 vs 13; qwen thinking-budget failures; retry check) |
| v1.1.70 | 2026-10-12 | Patch: §7 M2 result (qwen3.5:4b kept, D5 kept; teacher) and the parked explain/speed items |
| v1.1.69 | 2026-10-11 | Patch: §7 gemma3:4b dropped (teacher); non-thinking models and two grade-eval low items parked |
| v1.1.68 | 2026-10-11 | Patch: §7 M2 scope, candidates and the D5 deferral (teacher) |
| v1.1.67 | 2026-10-11 | Patch: §6 row M1/M2 adds the M2 grade eval (full M2, held-out only; teacher) |
| v1.1.66 | 2026-10-11 | Patch: §6 M1 report adds the waiver draft `docs/initial-plan/waivers/M1.md`; §7 held-out result, refinement after a working app (teacher) |
| v1.1.65 | 2026-10-11 | Patch: §7 M1 thresholds (teacher kept all defaults) |
| v1.1.64 | 2026-10-11 | Patch: §6 row M1/M2 adds the listening safety net (teacher); §7 baseline4 result, p1 + p2 kept |
| v1.1.63 | 2026-10-10 | Patch: §6 prompt tuning includes replay tests a prompt edit breaks only by its length; §7 parks the signs/notices mismatch |
| v1.1.62 | 2026-10-10 | Patch: §7 minimal M1 adds p2 (passages into `stimulus`; teacher, after p1's mini test) |
| v1.1.61 | 2026-10-10 | Patch: §7 minimal M1 (teacher): keep p1, park prompt tuning p2–p4 until after step 22 |
| v1.1.60 | 2026-10-10 | Patch: §6 row M1/M2 adds prompt tuning (one change per branch) and the `-CompareTo` script fix |
| v1.1.59 | 2026-10-10 | Patch: §7 parks the D26 margin-scan case (teacher kept 80 %) |
| v1.1.58 | 2026-10-10 | Patch: §6 row M1/M2 adds D26 (typed files skip answer reading) |
| v1.1.57 | 2026-10-10 | Patch: §7 bundle 1 mini-test results (teacher accepted): the DOCX stays in M1; T23 page-continuation finding; the butterfly effect of setting changes |
| v1.1.56 | 2026-10-10 | Patch: §6 bundle 1 wording names `[client] retry_capped_output` (verifier) |
| v1.1.55 | 2026-10-10 | Patch: §6 row M1/M2 adds speed bundle 1 (tiles switch, no retry on a length-capped output, tile fixes, a 1-paper live check) |
| v1.1.54 | 2026-10-10 | Patch: §7 parks two rare text-splitter edge cases found by the third verification (orchestrator's recommendation, to stop the edge-case loop) |
| v1.1.53 | 2026-10-09 | Patch: §7 records the teacher's DOCX scope-out rule for M1 |
| v1.1.52 | 2026-10-09 | Patch: §6 M1 row adds the `docx-long/` scenario and its generator; §7 DOCX wording |
| v1.1.51 | 2026-10-09 | Patch: §6 row M1/M2 adds the long-text-page fix (split a long text page at ingest; a higher `transcribe_page` output cap) |
| v1.1.50 | 2026-10-08 | Patch: §6 row M1/M2 adds the answer-prompt fix (B1) and keeping raw calls in `--keep` (B4) |
| v1.1.49 | 2026-10-08 | Patch: §7 M1 tuning is judged on 1 run while sampling is deterministic (teacher); baseline analysis findings |
| v1.1.48 | 2026-10-08 | Patch: §7 parks the DOCX-fix verifier's two test gaps |
| v1.1.47 | 2026-10-08 | Patch: §6 M1 baseline fixes add `sidecar/tests/cassettes/docx-text/` and the `retranscribe_tiles` text-page guard; §7 parks pictures / Review image on a text page |
| v1.1.46 | 2026-10-08 | Patch: §6 row M1/M2 adds the baseline fixes (a picture-free DOCX text page crashes `prepare_pages`; `key_accuracy` is 0 instead of blank with no key pages) |
| v1.1.45 | 2026-10-06 | Patch: §7 M1 finding: DOCX input loses bold/underline (teacher keeps them in ground truth); publisher watermarks left out |
| v1.1.44 | 2026-10-06 | Patch: §6 row M1/M2 adds the overnight batch tooling (the script, `erh eval --keep`, its tests, the runbook); per-fixture outputs go under gitignored `fixtures/_runs/` |
| v1.1.43 | 2026-10-06 | Patch: §7 adds the step 21a verifier's note (Fix blocked only by new validator failures) |
| v1.1.42 | 2026-10-06 | Patch: §7 records step 21a part A's open items (MCQ/T-F answers cannot be `???`; the docs name `write_test_meta` for the content edit) |
| v1.1.41 | 2026-10-06 | Patch: §7 records the teacher's incomplete-paper requirement and the keep-quirks rule |
| v1.1.40 | 2026-10-06 | Patch: §6 row 21a (unreadable text, PRD D25, plan v2.8); §7 notes the deferred photo-check "retake" warning |
| v1.1.39 | 2026-10-06 | Patch: §7 records the M1 fixture intake convention (teacher-agreed folder names, books index) |
| v1.1.38 | 2026-10-05 | Patch: §7 parks the step 20 verifier's items (relative restore path flagged for step 21) |
| v1.1.37 | 2026-10-05 | Patch: §6 row 20 adds the step 20 open items (sweep robustness, log retention in SQL), the app wiring for maintenance and the warning banner, and the flaky step 16 E2E helper |
| v1.1.36 | 2026-10-05 | Patch: §7 parks the S4 blank-detection finding (placeholder echo) for an M1 retest |
| v1.1.35 | 2026-10-05 | Patch: §6 row 19 names the shared folders, the seeded-cassette generator and the run-details route for R19.3 |
| v1.1.34 | 2026-10-05 | Patch: §7 parks the step 18 grade-recording findings for M1, with the teacher's 3-runs rule |
| v1.1.33 | 2026-10-05 | Patch: step 18 registers the graph in `api/app.py`; fixes the "database is locked" race between write routes and a running grade run; `erh record` for grade scenarios |
| v1.1.32 | 2026-10-05 | Patch: §6 row 18 lists the registration, store, CLI-runbook and cassette paths the grade graph needs |
| v1.1.31 | 2026-10-05 | Patch: §7 hands the step 17 verifier's grading-graph items to step 18 |
| v1.1.30 | 2026-10-04 | Patch: step 16 may add `picture_paths` to `GET /tests/{id}` (llm-design v4.10): the tests route, its API tests, the OpenAPI export and `app/src/gen/` |
| v1.1.29 | 2026-10-04 | Patch: §6 row 16 names the shared folders explicitly; §7 parks the steps 14–15 "worth a look" items until the app is built |
| v1.1.28 | 2026-10-03 | Patch: the shell builds its window in Rust, so step 15 disables Tauri drop handling in `lib.rs` (the config key has no effect) |
| v1.1.27 | 2026-10-03 | Patch: step 15 may edit the step-13 sidebar, conversation and panel features, `App.tsx`, `test-setup.ts`, and `dragDropEnabled` in `tauri.conf.json` |
| v1.1.26 | 2026-10-03 | Patch: step 14 may add ESLint ignores for Tauri build output and let the sidecar take the app folder from `ERH_APP_DIR` (settings.json at `<app>/settings.json`, PRD §11) |
| v1.1.25 | 2026-10-03 | Patch: step 14 may add Tauri JS dependencies (`package.json`, `package-lock.json`) and the CSP config test `app/scripts/tauri-config.test.ts` |
| v1.1.24 | 2026-10-02 | Patch: step 14 may write `docs/dev-setup.md` |
| v1.1.23 | 2026-10-02 | Patch: step 13 may add CORS to `api/app.py` |
| v1.1.22 | 2026-10-02 | Patch: step 13 may fix the stop/lock races in `runtime/steps.py` and `runtime/checkpoint.py` |
| v1.1.21 | 2026-10-02 | Patch: step 13 scope adds the step 12 flaky-test fix; fonts from @fontsource; §7 Frontend row |
| v1.1.20 | 2026-10-01 | Patch: §6 row 12 lists the repo additions the orchestrator granted to parts B and C (the row and the briefs disagreed) |
| v1.1.19 | 2026-10-01 | Patch: §7 API conventions (raw-bytes upload) and the run-details open item |
| v1.1.18 | 2026-10-01 | Patch: step 12 part B may clean up `runtime/events.py` |
| v1.1.17 | 2026-10-01 | Patch: step 12 scope adds `run.discarded` and DB-queued run pickup in the runtime |
| v1.1.16 | 2026-10-01 | Patch: step 11 may harden `resolve_answers` (wrong-page inline readings, disagreements, type checks) |
| v1.1.15 | 2026-09-30 | Patch: step 11 scope adds eval tests, CLI subcommands and the fixture runbook |
| v1.1.14 | 2026-09-30 | Patch: §7 Review conventions (step 10) |
| v1.1.13 | 2026-09-30 | Patch: step 10 may add `uncertain_answer` creation to `save_extract` (missing since step 9) |
| v1.1.12 | 2026-09-30 | Patch: step 10 may add repo functions |
| v1.1.11 | 2026-09-29 | Patch: step 9 may fix the name/class read in `domain/boxes.py` (template words, name+class in one field) |
| v1.1.10 | 2026-09-29 | Patch: step 9 may fix `llm/scrub.py` (it corrupted numeric JSON tokens in the S1 recording) |
| v1.1.9 | 2026-09-29 | Patch: step 9 part C scope: `llm/ollama_serve.py`, the cassette input manifest |
| v1.1.8 | 2026-09-29 | Patch: step 9 scope adds the `File.original_name` plumbing (data-model v1.5) |
| v1.1.7 | 2026-09-29 | Patch: step 9 scope adds graph unit tests, the stand-in PNG writer and the recording runbook |
| v1.1.6 | 2026-09-29 | Patch: §7 extraction-logic conventions and the omitted-answer open item (step 8.1) |
| v1.1.5 | 2026-09-29 | Patch: §7 runtime conventions and the `run.discarded` open item (step 7) |
| v1.1.4 | 2026-09-29 | Patch: step 7 may add run/step functions to `store/repos/runs.py` and connection pragmas to `store/db.py` |
| v1.1.3 | 2026-09-29 | Patch: §7 adds the step 6 confidence conventions |
| v1.1.2 | 2026-09-29 | Patch: phase-0 report and live output live in `docs/initial-plan/phases-testing/` |
| v1.1.1 | 2026-09-28 | Patch: step 4 may add `llm_calls` update functions to `store/repos/runs.py` (keeps SQL in the repo layer) |
| v1.1 | 2026-09-28 | Minor: §7 cross-step conventions and open items from steps 1–3 |
| v1.0.3 | 2026-09-28 | Patch: step 10 may also write `store/repos/review.py` (plan v2.2 R10.4) |
| v1.0.2 | 2026-09-28 | Patch: §6 row 1 adds `domain/__init__.py`, matching the rule 5 exception (the two parts disagreed) |
| v1.0.1 | 2026-09-28 | Patch: rule 5 names the schema writer `export_schemas()` as an allowed I/O exception in `domain/`; rule 0 exempts the orchestrator's structure.md commits |
| v1.0 | 2026-09-28 | First map: every folder and module that plan steps 0–22 create, with the step that creates it |
