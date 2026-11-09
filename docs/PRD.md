# PRD — ETACH

| | |
|---|---|
| Version | **v9.1.1** (2026-11-09) |
| Owner | Minh Khang (teacher, sole user) |
| Location | `D:\Projects\ETACH` |
| Scope | Vietnamese English tests at school level (grades 6–12: mid-term, final, TS10 entrance, THPT national, grammar practice) |
| Companions | [`llm-design.md`](llm-design.md): LangGraph workflows, model calls, API, confidence, stop/resume · [`data-model.md`](data-model.md): classes, SQLite tables, write rules · [`initial-plan/plan.md`](initial-plan/plan.md): build order, checks, progress tracker. Each plan pins the versions it builds on in its "Based on" line |

### Changelog
Versioning: **major** = a decision changed (the §3 table) · **minor** = new detail that doesn't change a decision · **patch** = wording and typos.

| Version | Date | Change |
|---|---|---|
| **v9.1.1** | 2026-11-09 | Patch, teacher (maintenance): the changelog rows of the initial plan moved to `initial-plan/changelogs.md` |
| v9.1 | 2026-11-09 | Minor, teacher: the internal code names use ETACH too (§10.1): the Python package and CLI `etach`, the frozen sidecar `etach-sidecar.exe`, `ETACH_*` environment variables, the Cargo package `etach-shell`, the npm package `etach-app`; the repository folder is `D:\Projects\ETACH`. Not a §3 decision |
| v9.0.1 | 2026-11-03 | Patch, after the initial plan: the title, the Name line and §11 no longer name the old app (the rename is v8.18), and the close question reads "Close ETACH?" as the app does; the finished initial plan moved to `docs/initial-plan/`. Not a §3 decision |

Earlier rows (2026-09-26 to 2026-10-30, the initial plan) are in [`initial-plan/changelogs.md`](initial-plan/changelogs.md).

---

## 1. Summary

A local desktop app for Windows, **built for teachers first** (power users). The first user is the author.

1. The teacher opens a **new thread**, drops the photos of **one** test, checks the photos (order, rotation, delete), and presses **Run**. After that the teacher goes back to the student.
2. The app **reads the photos** with a local vision model. It saves the **clean test** once in a searchable test bank, and if the test was filled in, it also saves **the student's answers**.
3. Right after the reading, a local reasoning model makes the **answer key** for the questions without one (a key the teacher gave stays), while the teacher can already look at the test (v9.0).
4. When the teacher is ready, they press **Grade**. The reasoning model grades the answers, and explains the mistakes and weak points.
5. The teacher **glances at the draft** and prints.

Everything runs offline through Ollama. The framework is **model-agnostic**: models are configured per role and are tested and swapped after the framework is built.

### Why a new app (problems with today's EnglishTest_Tutor pipeline)

| Today (`D:\Projects\EnglishTest_Tutor`) | This app |
|---|---|
| Run from VS Code and CLI commands while also teaching a student | Drop, check the photos, Run, walk away |
| Claude, Gemini or OpenAI APIs cost money and need a good internet connection | Local models through Ollama |
| Output folders `Test_1`, `Test_2`; no shared metadata; re-extracted for every student | One canonical record per test with standard metadata, and duplicate warnings |
| Built for the kienthucvang / ktv20 formats | Independent schema. Possible bridge later (§14) |

---

## 2. Goals and non-goals

### Goals (this version)
1. **Low effort during the lesson.** About 30 seconds of teacher time before Run (checking the photos). Nothing is needed while the run is going.
2. **Standardized test bank.** Consistent structure, numbering and metadata, however sloppy the paper was.
3. **A test is stored once.** An optional name search at the photo check, plus a text-comparison warning after extraction.
4. **Honest confidence.** Uncertain readings and uncertain keys show as `?`, never as a confident ✗ or ✓.
5. **Grading and explanations on demand** (the Grade button), with weak points building up across attempts.
6. **Robust runs.** A visible running indicator, a Stop button, and resume after a stop, crash or sleep, without losing finished work.
7. **Model-agnostic and measurable.** Models are swapped per role in settings; an eval harness scores every change.
8. **Offline, native feel, minimal UI** (claude.ai layout, fewer buttons).

### Deferred (planned, not in this version)
- **Generation:** retests from weak points, similar tests from blank tests.
- **Typo fixing** of the saved test (numbering is still fixed in code now; see D10).
- **Vietnamese text normalization:** NFC, tone placement, "đ→d" search folding, KỲ/HK header variants.
- **Encryption** of data and backups.
- **Automatic photo cleanup:** perspective correction, deskew, crop. The teacher's photo check covers this for now.
- **Real picture cropping** (placeholders hold the image path for now).
- **A "retake" warning at the photo check** (teacher, 2026-10-06). Before Run, the photo check warns about pages that look blurry or have text running off the edge. It is an image heuristic, with no model call. The teacher can then retake the photo while the paper is still there. Deferred until after the app is built.
- **Free chat in a thread** with the reasoning model (e.g. "explain Q38 more simply"). Threads have only the photo check, Run, Grade and cards for now.
- **Changing the Windows lid-close setting.**
- **School-name aliases** ("Nguyen Huu Tho" = "THCS Nguyễn Hữu Thọ") and the per-student "already seen" item table (both needed only with generation or at a larger bank size).

### Non-goals
Listening sections (ignored completely); grading students' writing (D12); speaking; students using the app; on-screen test taking; several tests in one run (use one thread per test); Android/iOS; multiple users; cloud sync; ktv20 upload; Cambridge YLE/KET/PET; a parent-facing report version.

---

## 3. Decisions

| # | Topic | Decision |
|---|---|---|
| D1 | Duplicates | **Rev. v4.** The teacher can optionally **search the bank by name** at the photo check and pick the existing test; this skips transcription. Otherwise the app extracts, **compares the extracted text** with the bank, and warns ("looks like T-0042", a Review item to merge). There is **no image comparison**. |
| D2 | Answer key | **Rev. v9.0** (teacher, 2026-10-30, step22.6-plan D4 and D11). **Made after every extraction** (Extract again too), with or without a key photo: the AI writes the key for the questions without one; a key given by a 🔑 photo (D19) or by the teacher stays. The teacher can open the test at once; the Key tab stays blank, with a short note, until the key is ready, then shows it all at once (no update per key). While the key is being made, **Grade student answers** waits, greyed out with "Making the key…". Grade uses the key already made and makes one only where it is still missing. Was: "Made by the Grade button, unless one was given (D19)". AI keys use targeted verification. Doubtful items show `?`. A key verified by the teacher is reused for every later attempt, and verifying one re-grades all attempts on that test. |
| D3 | Students | Light profiles. The name is read from the paper if written (and matched to an existing profile). Otherwise the attempt is "Chưa rõ" (unknown) plus a Review item, and the teacher assigns the student later from Review or the student chip on the extraction card. |
| D4 | Delivery | **Rev. v5.0** (teacher, 2026-10-13). **Print/PDF and DOCX.** The clean test, the key and the report each have Print and **Save as Word (.docx)**. A DOCX is saved into the app folder's `exports\` folder, which then opens in Explorer; the teacher copies it from there (§11 stays: nothing is written outside the app folder). The key is always separate. Was: "PDF/print first; DOCX later". |
| D5 | Language | Vietnamese explanations, keeping English grammar terms and English example sentences. |
| D6 | Diagnosis | No live dialogue. The Grade output includes 3–5 **questions for the teacher to ask** the student. |
| D7 | Models | **Rev. v7.0** (teacher, 2026-10-17, comment 13): the default **image (vision) model is `qwen3.5:4b`**, the same tag as the reasoning default, so one download serves both; NuExtract is no longer a default and can be deleted in the model manager. Each role's model is **picked from the models installed in Ollama** (typing a tag stays possible). Was: **Rev. v4.** **A model-agnostic framework comes first**, with roles configured per model tag in Ollama. **Vision (default): `numind/nuextract3:Q6_K`**, which is assumed capable; if it falls short, it gets more prompting first. **Reasoning: to be chosen by the teacher after testing** small models; `qwen3.5:4b` is only the placeholder default (v4.5; was `qwen3.5:9b`, too large for 6 GB). No speed promises until they are measured. |
| D8 | UI | The claude.ai layout, with fewer buttons and tabs. |
| D9 | Autonomy | **Rev. v4.** There is no interaction **during** a run. The only steps are the photo check before Run, pressing Grade, and **a glance at the draft before printing**. Uncertain items are clearly marked so the glance is quick. |
| D10 | Clean test | **Rev. v6.0** (teacher, 2026-10-14). Re-typeset and standardized. **Question numbers are the paper's printed numbers** everywhere the teacher sees them (test page, Key, Student answers, report, print, DOCX), gaps included, so checking against the paper needs no subtraction; the code keeps its own numbering internally for matching. **Typo fixing is deferred** (it needs the reasoning model). Was: "Section and question numbering is fixed in code (printed numbers kept for reports)". |
| D11 | Pictures | **Rev. v4.** The placeholder is **the image path plus the page**: `[Hình: files/ab/ab12….jpg · trang 3]`. It is meant for the teacher (a power user), not the students. A picture that is mostly text (a dictionary entry, a notice) is still transcribed as text. |
| D12 | Listening and writing | **Listening:** ignored completely; not stored, excluded from the total, recorded as `omittedSections`. **Writing** (paragraph or essay tasks, v4.4): the task prompt is kept in the test for printing, but the student's writing is **not read or graded**, and its points are excluded from the total (e.g. `7.5/8`). |
| D13 | Score format | **Changed v8.0** (teacher, 2026-10-19, step 22.4 D3). The score is always **out of 10**: every graded question is worth 10 ÷ the number of graded questions in the test (usually 0.25; 0.2 with 50 questions), e.g. `7.5/10`. Printed part points are not used for the score; a writing part (not graded) counts for nothing. Earlier: printed points, else 0.25 per question, flagged `points_assumed`. **v8.5** (teacher, step 22.5 D7): section headings show no points; the line under the test title reads "10 points · 0.25 each" (each question's value, at most 2 decimals), in the app, the print view and the Word file; a writing part keeps "[not graded]". |
| D14 | Where answers are written | Anywhere: circled options, in blanks, in answer boxes (**including boxes on a different page from the question**), or in margins. When they disagree, the answer box wins and the item is flagged. |
| D15 | Tuning | Prompt profiles (base + per-format profile) and an eval harness with **tuning and held-out fixture sets**. |
| D16 | Scope split | **New v4; rev. v9.0** (step22.6-plan D4). An **extraction run** is extraction only: the vision model reads the clean test and the student's answers, with no reasoning model. After every extraction, a **key run** follows on its own: the reasoning model makes the key (unless given), checks it where needed and tags the skills; it never grades. The **Grade button** runs the reasoning model: grading, explanations, weak points, questions for the teacher, and a key only where one is still missing. Was: the Grade button made the key and the skill tags too. |
| D17 | Photo check | **New v4.** After dropping photos and before Run: a thumbnail strip where the teacher **reorders, rotates, deletes and adds** photos, optionally marks key pages with 🔑 (D19) and optionally picks an existing test by name (D1), and then confirms. **Only these two optional inputs**, with no student field and no typed key. This replaces automatic page ordering and rotation. |
| D18 | One test per thread | **New v4.** One thread = one test (one attempt, or one blank test). Several tests mean several threads. There is no automatic splitting. **Dropping photos into a thread that has already run is blocked**, and a "Start a new thread" button is shown instead (v4.3). |
| D19 | Answer key input | **New v4.** Optional at the photo check: photos marked **🔑 key** in the strip (the paper's đáp án page), read by the vision model during the run. There is no typed key field. Keys can still be corrected item by item later (Review queue). |
| D20 | Confidence | **New v4.** From **token logprobs** (Ollama `logprobs`/`top_logprobs`), not from the model rating itself. For enum answers, the confidence is the margin between the top two choices; for written answers, it is the weakest token in the answer. **A low-confidence reading, or a near-miss on a low-confidence reading, becomes `?`, never ✗.** Thresholds are calibrated on held-out fixtures. |
| D21 | Pipeline | **New v4.** **Python + LangGraph**, with the SQLite checkpointer, running as a hidden local sidecar process (llm-design §2). |
| D22 | Stop / resume | **New v4.** The running indicator is always visible, with **Stop**. Finished steps are kept. The step in progress, including its partial and thinking text, is saved as an **incomplete** log entry (never used as a result) and **restarts from scratch** on Resume. A crash, shutdown or sleep is handled the same way on the next start. |
| D23 | Laptop sleep | **New v4.** The app blocks **idle** sleep while a run is going. The running indicator says **"keep the lid open"**. If the laptop sleeps anyway, the run resumes from the last finished step. Windows settings are not changed. |
| D24 | Partial credit | **New v4.2.** None. A correct answer gets its full points and a wrong answer gets 0, rewrites included. Near misses are still tagged (`near_miss`, "spelling") for the explanation, but they score 0. `?` items score nothing until resolved and are shown separately ("7.5/9, 0.5 unsure"). |
| D25 | Unreadable text | **New v4.7** (teacher, 2026-10-06). **During the run:** a word or span the vision model cannot read (cut off, blurred, covered) is written as **`???`**. It is never guessed. An unreadable student answer is written `???` too, and counts as an unsure reading (`?`). **After the run:** each page whose transcription contains `???` gets **one Review item, `unreadable_text`**. It shows the page image and the text with the `???` spans. **Fix** = the teacher types the missing words, which replace the `???` spans through the normal content edit (re-validated). **Accept** = keep the `???`, since the paper may be gone. There is no interaction and no retake request during the run (D9). The fixtures' ground truth uses the same `???` rule. |
| D27 | Review in place, test as a page | **New v4.14** (teacher, 2026-10-13). There is **no Review tab or Review panel**. Each unsure spot is shown where it belongs and settled there: unreadable text (`???`, D25), unsure points and failed checks in the **test page**; unsure readings in the **Answers** panel; disputed or unmapped keys in the **Key** panel; possible duplicates, a mismatched pick and unaligned merged answers on the **extraction card**; an unknown student or occasion on its **chip**. The sidebar shows which threads and tests still have unsure spots. Nothing is locked behind them: the test can always be edited. The extracted test is edited as **one free-text page, like a Word document**; on Save the app reads the text back into sections, questions and options, and a line it cannot understand is highlighted for the teacher to fix, with nothing saved until it reads. D25's Fix and Accept still apply, from the page. |
| D26 | Typed files are blank | **New v4.8** (teacher, 2026-10-10). A born-digital file (a DOCX, or a PDF whose pages have a full text layer and no full-page image) cannot hold a student's handwriting, so the app **skips answer reading** on it and treats it as a blank test. A scanned PDF (page images) is read like photos. Found by the M1 workflow review: answer reading is ~44 % of extraction time and invented answers on typed blank tests |

---

## 4. Scenarios

### S1 — Filled test, first time seen (the worked example `Lop8-HKI-De1 (1..3).jpg`)
1. **New thread.** The teacher drops 3 photos. The files are in reverse order and one is rotated 90°.
2. **Photo check:** the teacher drags them into order, rotates page 1, and presses **Run** (about 30 s). The student's name "Ngô Thị Mỹ Hòa 8TC11" is written on the paper, so the run reads it.
3. **The run:**
   - reads the header → `Grade 8 · FinalTerm HK1 · Test 1 · (K)`;
   - skips listening Q1–4 (v8.9: the Student answers tab says so in one quiet line, "Listening (questions 1–4) left out");
   - transcribes the printed test (numbering fixed, pictures → path placeholders);
   - reads the answers (circled options, words written in the blanks) with logprob confidence;
   - compares the text with the bank: nothing similar;
   - saves **T-0042** and the attempt.
4. The thread shows the **extraction card**: the clean test, and the answers read, with `?` where unsure (e.g. Q35/Q36, written between the two questions).
5. While the teacher reads the clean test, the app makes the key (AI, verified where needed; v9.0, D2).
6. The teacher presses **Grade** → score `7.5/9`, explanations, weak points, questions for the teacher.
7. The teacher glances at the draft and prints.

### S2 — The same test, another student
A new thread. At the photo check the teacher types "grade 8 final test 1" in the **Existing test** box and picks T-0042. Display names are English for now; Vietnamese search is deferred. The run reads this photo's header to confirm it matches T-0042, skips transcription, and only reads the answers, using T-0042's known questions. Grade reuses the verified key and cached explanations.

### S3 — The same test, the teacher forgot to pick it
The run transcribes as usual. The text comparison finds T-0042, so the card says **"Looks like T-0042"**. The attempt is attached to the new test and a Review item "merge into T-0042?" is created. Merging moves the attempt and re-grades it.

### S4 — Blank test
Run → the clean test is saved (no attempt, because no answers were found), and the thread is listed under **Blank tests** in the sidebar. **v8.28 (teacher, 2026-10-30):** a photo paper also counts as blank when fewer than 20% of its answers are read with confidence (unreadable handwriting `???` counts as written), because a paper with no student marks still gets made-up, unsure readings; its readings and their Review items are not kept. If a student does that test later, their paper gets its own thread, where the "looks like" notice finds the stored test. The key for the key copy is made after the extraction, as for every test (v9.0, D2); Grade (here **Make the key**) is optional and only makes keys still missing. If the teacher picked an existing test and the paper is blank, nothing new is saved, and the card says "No answers found; T-0042 is already in the bank". **Similar-test generation is deferred.**

### S5 — Key provided
The teacher adds a photo of the đáp án page to the strip and marks it 🔑. The run reads it, marked `from_key_photo`; the key run after the extraction (v9.0, D2) makes AI keys only for the questions the photo gives no key for, and Grade uses them all.

### S6 — Stop and resume
Mid-run the teacher needs the laptop and presses **Stop**. The step in progress is logged as incomplete. Later: **Resume** → it continues from the last finished step. The same happens after a crash or a sleep.

### S7 — Review time and finding tests
- Unsure spots (D27, v4.14) are marked where they sit: uncertain readings in the Answers panel, unreadable text (`???`, D25) on the test page, disputed keys in the Key panel, possible duplicates on the extraction card, unknown students on the chip, each next to the original photo. The sidebar shows which threads and tests still have some.
- **Tests** search: `grade 8 final test 1`, with a count of attempts per test (merged tests are hidden).

---

## 5–7. Data model

Moved to **[`data-model.md`](data-model.md)**. It covers the classes (Test, Student, Attempt, Thread, Run, …), the SQLite tables, the test metadata and content schemas, and migrations.

---

## 8. Duplicate detection

1. **Teacher pick (optional):** at the photo check, an accent-insensitive **name search** over test display names and metadata. Picking a test skips transcription. **Before answers are read**, a sanity check compares this photo's header and first stems with the picked test; a mismatch creates a warning and a Review item.
2. **Text comparison (always, when not picked):** after transcription, compare the normalized printed text (lowercase, diacritics stripped, numbering and punctuation removed, 5-character shingles) with every test of the same grade (all tests if the grade is unknown), using **exact Jaccard similarity**. It is instant at the bank's scale.
   - ≥ 0.85 → **"Looks like T-0042"** plus a Review item (merge);
   - 0.5–0.85 → "possibly T-0042" plus a Review item;
   - < 0.5 → nothing.
   - Thresholds are tuned on the fixtures.
3. **Merge** (from Review) moves the attempts onto the surviving test and re-grades them against its key.

---

## 9. Pipeline (summary)

The full graphs, nodes, model calls, confidence and stop/resume are in **[`llm-design.md`](llm-design.md)**.

```
Photo check (teacher) ─► RUN = extraction graph (vision model only)
   load pages → [key photos: read key]
   → [picked: load bank test → read header → sanity check]
     [not picked: transcribe pages → merge + renumber (code) → compare with bank]
   → map key → read answers (all pages, with the full question list) → save → extraction card

KEY RUN = grading graph without an attempt (reasoning model), queued by every extraction's save (v9.0)
   key (from 🔑 photo / AI + targeted verification) → skill tags (once per test)

GRADE button = grading graph (reasoning model)
   key (only where still missing) + targeted verification → grade (code, confidence-aware) → explanations (cached)
   → weak points + teacher questions → report draft
```

Rules:
- **Code does everything deterministic:** page loading in the teacher's order and rotation, renumbering, points, header patterns, text comparison, scoring, rendering.
- **Photos (v8.10):** each page is read with a short note of what the page before it left open (a section, a question without its options, a passage), so content cut by a page break is joined into one question, section or passage. A page that fails a check can have only its broken or missing questions read again, patched in by code (a setting, off until the teacher's measurement). A test photo is read in two steps, an OCR model's text (GLM-OCR) and then the typed-text reading: the default since the teacher's measurement (G4, 2026-10-26; v8.11), with its model downloaded and checked like the others; reading the test with the vision model in one step stays a setting. Student answers are always read by the vision model. The half-page tile re-read stays off.
- **Answer reading (v8.9):** each page is asked only for the student answers to the questions printed on it: the printed number and the answer next to it. An answer written only on another page than its question is not read (accepted limit, the teacher 2026-10-22). A key read from the key photo is shown as "From the key photo"; "double-checked" only when a second check agreed. The paper's own box numbering is not trusted (the example prints "32." twice); boxes are matched by position within the box row and cross-checked.
- **Grading:**
  - ✓ / ✗ only when the reading is confident;
  - low confidence → `?`;
  - a misspelling on a confident reading → ✗ tagged `near_miss` ("spelling");
  - rewrites are judged by the reasoning model with strict rules.
  - **By answer form (v8.6, step 22.5.3).** Each question has one of four answer forms, read from the printed layout:
    **choice** (lettered options, or True/False), **word** (a word or short phrase in a blank, or a word to put in the
    right form), **sentence** (a whole sentence: rewrite, combine, put words in order, answer a question), **writing**
    (a paragraph or essay). A choice must match the key exactly (matching questions included); a word must match, and
    a misspelling is a near miss; a sentence that does not match the key exactly goes to the AI judge, with the one
    rule rewrites use (so former combine, short-answer and ordering questions are judged too, where ordering used to
    need an exact match); writing is not graded (D12). Tests already in the bank are mapped to the forms once at first
    start, keeping their old type for a possible revert; no student answer, key or grade changes, and nothing is
    re-graded.

---

## 10. UI / UX

The claude.ai layout: sidebar, conversation, artifact panel. **Fewer buttons, fewer tabs.** **v8.4:** extra detail
(a reason, a hint) goes into a tooltip on hover and keyboard focus, not onto the row (the teacher, 2026-10-23).

**Names on screen (v5.1).** The student's answers are **Student answers** (tab, workspace, buttons); the correct answers are the **Key**; no label says "correct answer". Below, "Answers" means Student answers.

**v6.2:** the Test name can be typed over (it then stays as typed; "Use automatic name" goes back); the automatic name uses "Unit Test" / "15-minute Test" and leaves out an unknown occasion; Units and Tags are editable (comma-separated). An uncertain grade shows "AI unsure grade".

**Test details and name (v6.0).** The Test workspace shows the **Test name** first, then the fields the teacher names tests by: grade, occasion and term, school or series, year, test number ("Test number", not "Test"); the rest (variant = the paper's version, e.g. đề A / đề B; code; region; textbook; units; duration; exam format; tags) is under a folded **More details**. The automatic Test name is those fields joined by " - ", empty ones left out: "Grade 8 - Final Term 1 - Nguyễn Hữu Thọ - 2025 - Test 7" (decision C, in English). Duplicates are found by comparing the questions, not the name. Under the test page, **Format help** opens and closes the table of line forms with examples.

**Report wording and order (v8.2).** The report, on screen and in the Word file, never shows the internal skill codes (such as VOC-TOPIC); it shows the skill's English name from the skill list ("Vocabulary — topic words: 3/5 wrong"). A code that appears inside text the AI wrote is replaced by its name. Explanations and the list of wrong answers follow the paper's question order, whatever order they were written in.

**Re-grade after checking keys (v8.1).** Verifying or editing a key no longer starts grading each time. The app notes that the test's keys changed; the top bar then reads "Keys changed" with a **Re-grade** button (and **Stop** while a run goes). One re-grade of every graded attempt of the test starts when the teacher leaves the Key tab (to another tab or another thread) or presses Re-grade. If the app is closed first, the note stays and the bar shows it the next time the thread is opened. On the Key tab the top bar is compact (one line), so the key photos keep their size. **v8.3:** leaving the thread (from any tab) while its keys changed also starts the re-grade, and the top bar is one compact line on every workspace tab.

**Settings tabs and schools (v7.3).** Settings is split into tabs: **General**, **Models** (the model manager and the role choices), **Occasions** and **Schools**. The Schools list works like Occasions: add, rename, reorder, and delete a school no test or student uses. The School field of a test or a student is a dropdown of that list, filtered as the teacher types; a new name typed there is added to the list. Renaming a school updates every test and student with it and every automatic Test name that uses it.

**Occasions (v7.2).** Settings has an **Occasions** list: the ten built-in occasions and the teacher's own. The teacher can add one (its full name, and the short name used in the Test name), rename any (also the built-in ones), reorder them, and delete their own when no test uses it. Renaming updates the Occasion editor, the chips and every automatic Test name that uses it; names the teacher typed are kept.

**Typed files and sentence openings (v7.1).** A born-digital page (D26: DOCX text, or a PDF page with a full text layer) is not read as an image: its exact text goes to the model as text, which fits it into the test structure; pictures in the file stay pictures (D11) (decision D5). For rewrite and combine questions (sentence questions since v8.6), extraction keeps the opening words the paper prints for the answer ("My brother …"), so the key's four sentence forms can be made (decision D6). One GPU run on a typed national exam and a photographed test with rewrites checks both before installer 0.4.0.

**Weak points over time (v8.8, step 22.5.5).** Each paper has a **date taken** (set on the photo check card, default
today; changeable on the Student answers tab). For each skill the app lines up the student's papers by that date and
labels it: **improved**, **slipped**, **consistently weak**, **inconsistent**, **solid**, or **not enough evidence**
(fewer than 3 papers); the share right is measured above guessing (a question with k options can be guessed 1 in k
times, so all right = 100 % and chance level = 0 %; D11f), careless and spelling mistakes are left out (D11).
The report lists the skills missed on this paper with their label, or "this paper only" while there is not enough
evidence; improved and solid skills are not weak points (D11c). Skills go **basics first** (levels A1–B2, vocabulary
first within a level); weak points above the lowest weak level sit behind **"Later, after the basics (N)"** (D11d,
D11e). The **Students tab** shows every skill of a student with its label and level (D11b). On the Key tab, hovering
over or focusing an "AI unsure key" shows the checker's answer and its reasoning, or that the check did not finish.

**Students and series (v6.4).** The Students tab has **Delete…** on each student: the student is deleted for good **with their threads**; the dialog lists them; tests stay in the bank (D1). A test's details have **Copy details from…**: pick another test, and its occasion, term, school, series and year are copied (not the grade, not the test number). At the photo check, next to "same test as…", **same series as…** starts the new test with those same details; the AI fills the rest (D3).

**Series, headings and Extract again (v8.5, step 22.5 decisions D2, D5, D7, D8).** Settings has a **Series** list, built like Schools (add, rename, reorder; delete only when no test uses it); it starts with the series already on tests. **Same series as…** on the new-thread screen picks a series name: the new test gets that series, and grade, occasion, term and year from the newest test of the series (not the school). Section headings show no points; the line under the test title reads "10 points · 0.25 each" (D13). A section with no title (or only "I.") takes its title from its skill, in capitals ("I. PRONUNCIATION", "WORD FORM"); a mixed section stays untitled; a title with words is never changed. **Extract again** reads the photos again into the **same test** (same id), so no "looks like" note points at the old reading: the keys on a question whose number and text are unchanged stay (the teacher's and the AI's, with their unsure state), other questions are keyed again; every thread on the test follows (their student answers stay on the matching questions, graded ones wait for Re-grade). When other threads use the test, the teacher chooses: update the test for every thread, or make a separate copy for this thread.

**Delete and Students (v5.3).** The thread menu and the Tests tab have **Delete…**. Deleting a thread removes it for good with its student's photos, answers and reports; the test stays in the bank. Deleting a test removes it for good together with the threads that use it; the confirm dialog names them. A thread or test with a running run cannot be deleted until the run stops. The daily backups (step 20) are the way back. The sidebar has a third tab, **Students**: each student with their class, editable name and class, and their threads (click opens the thread). On a thread, the student chip can switch the paper to another student or a new one.

**Straight to work (v6.3, decision D2).** A thread whose extraction has finished opens straight into its workspace (Test first); the conversation with its cards is no longer shown. The Test page's top right has **Grade student answers** (or **Grade again**) and **Extract again**. While a run goes, a progress bar sits at the top of the workspace as well as in the sidebar. A new thread shows its start screen (drop, photo check) until its extraction finishes, then opens the workspace. The workspace header has the **student chip** on every thread with a student's paper, so a student can be set or changed also when the paper has no name. A thread with only the test (no answers read) has no student; there the Grade button reads **Make the key** (the AI writes the key, as the old card's Grade did) (v6.3.1). Since v9.0 (D2) the key is made after every extraction, so Make the key only makes keys still missing (for example after a failed or stopped key run).

**Workspace tabs and safety (v5.2).** The workspace header has tabs **Test · Key · Student answers · Report** (a tab is shown when it has something to show); switching keeps the workspace open and asks first if there is unsaved text. Closing the app window asks "Close ETACH?" (and warns about unsaved text), because the print window's only exit is the app's ✕. The new-thread screen has **Choose files…** next to drag and drop. Double-clicking a Key or Student answers row edits it (Edit stays). Rows show the content first and their actions and source on the right. An unsure key has the same **Verify** button as any key. The thread menu has **Use automatic name**.

**Workspace view (v4.13, teacher's decision 3).** The sketch below is the step 13 layout. Since v4.13, opening **Test, Key, Answers or Report** replaces the conversation with a workspace: the panel on the left, where the teacher reads and edits, and the **original photos** on the right, page by page with zoom (for the Key, the right side can also show the test text). **← Back to thread** (or `Esc`) returns to the conversation as it was. The extraction card shows the photo thumbnails, and each button says what it opens.

### 10.1 Layout
```
┌─────────────────────┬──────────────────────────────────────────┬────────────────────────┐
│ ☰  ETACH            │  Thread: Hòa · Lớp 8 Cuối kì 1 Đề 1      │ (artifact panel)       │
│ [+ New thread]      │                                          │                        │
│ ⟳ Running: Hòa…     │  ┌ Photo check ─────────────────────┐    │  T-0042 clean test     │
│   Step 3/6 [Stop]   │  │ [p1⟳][p2][p3]  ← drag to reorder │    │  I. Choose the word…   │
│   keep lid open     │  │ Existing test: [search…      ]   │    │  ...                   │
│ ● Review · 4        │  │ 🔑 on a thumbnail = key page     │    │                        │
│ Chats | Tests       │  │                                  │    │                        │
│ ▾ Ngô Thị Mỹ Hòa    │  │                         [ Run ]  │    │                        │
│   Cuối kì 1 · Đề 1  │  └──────────────────────────────────┘    │                        │
│ ▸ Chưa rõ           │  ┌ Extracted ✓  7 answers unsure (?) ┐   │                        │
│ ⚙                   │  │ [Test] [Answers]          [Grade] │   │ [Print]            ✕   │
└─────────────────────┴──────────────────────────────────────────┴────────────────────────┘
```

- **Sidebar:**
  - **New thread**.
  - **Running indicator** (only while a run is going): the thread name, the current step, **Stop**, and "keep the lid open". It shows a **progress bar** for the whole run, the stage in plain words with its count (e.g. "Reading the answers · page 2 of 4"), the elapsed time, and a sign that the model is still writing, so the teacher can tell a slow run from a frozen one (v4.12). The running thread shows the same bar. A stopped or interrupted run shows **Resume** / **Discard** instead.
  - **Review · N**.
  - A **Chats | Tests** switch. Chats are grouped by student, with "Chưa rõ" for unknown students and **Blank tests** for threads without an attempt.
  - **⚙**.
- **Photo check card:** the thumbnail strip (drag to reorder, ⟳ rotate, ✕ delete, + add, 🔑 mark as key page), and the optional Existing test search, then **Run**. It's the only form in the app, and nothing on it is required.
- **Extraction card** also shows a **student chip** (the name read from the paper, or "Chưa rõ"). Clicking it assigns or changes the student.
- **Extraction card:** "Extracted ✓", with a count of unsure readings. It has **[Test]** and **[Answers]** (open in the panel) and **[Grade]**.
- **Grade card:** score, per-question ✓/✗/`?`, explanations, weak points, questions for the teacher, and **[Print]**.
- **Print** = the webview's print with print-specific CSS, which opens the Windows print dialog ("Microsoft Print to PDF" gives a PDF). The same view is used for the preview and the print.
- **Test panel:** the rendered clean test. Its **metadata chips are editable inline** (occasion, grade, term, test number, school, …). This is where the teacher fixes a wrong header reading.
- **Review panel:** one item per screen, showing the page image and the question side by side. For `unreadable_text` (D25) it shows the page image and that page's text with the `???` spans, and Fix types the missing words. **Accept / Fix / Skip** (keys: `Enter`, `E`, `→`).
- **Keyboard:** `Ctrl+N` new thread · `Ctrl+V` paste photos · `Ctrl+Enter` Run / Grade · `Ctrl+K` search tests · `Esc` close panel.
- **Notifications:** a Windows toast when a run finishes or fails.
- **Theme and fonts (v8.12, the teacher; replaces v4.11's green, light and dark):** light only, no dark mode. Background rgb(247, 247, 249), nearly white (v8.14; v8.13 rgb(244, 244, 247), v8.12 rgb(230, 232, 242), too blue); text rgb(14, 14, 1), black with a hint of yellow; buttons, the selected tab, links and focus blue rgb(53, 57, 227), with white text on blue fills; a blue button or tab turns deep navy rgb(24, 26, 92) on hover and press (v8.20; v8.15 dark navy rgb(15, 16, 56), too black; v8.14 light blue rgb(98, 101, 233) buttons, too light; v8.12 rgb(31, 35, 224)). The other theme colours carry meaning and are not decoration: **correct** green rgb(86, 219, 86) and **unsure** ochre rgb(224, 132, 34) are fills with dark text; **wrong** (and delete, and error messages) is brick rgb(150, 39, 24). The correct and unsure labels written as text use letters fading from the text colour at the top to deeper gold rgb(119, 105, 16) at the bottom (v8.13; was yellow rgb(230, 208, 67), too faint). Each ✓ in the grade report and the Student answers sits on a small green badge and each ✗ on a brick one (v8.13); in the skills table "improved" is a green badge and "inconsistent" an ochre badge, both with dark text (v8.13). The colours come from old Saigon school buildings. **Name (v8.18, the teacher):** the app is **ETACH**, "English Test Assistant - Curate & Help". The sidebar shows the wordmark ETACH in Federo (bundled, Latin only; coloured left to right by a horizontal gradient, v8.19: lime rgb(165, 217, 33) at the E fading to the blue rgb(53, 57, 227), about 20% green left at the T's centre and pure blue from the T's right edge through the A, blue changing to deep navy rgb(24, 26, 92) across the middle of the C, the H deep navy) with the line "English Test Assistant - Curate & Help" under it in Faustina, bold, centred, with a short rule underneath, like "Độc lập – Tự do – Hạnh phúc"; the window title, the dialogs that name the app, the installer, the Start-menu entry, the Windows app ID and the program file (`ETACH.exe`, v8.26) use ETACH. Internal code names use ETACH too (v9.1, the teacher): the Python package and CLI `etach`, the frozen sidecar `sidecar\etach-sidecar.exe`, the `ETACH_*` environment variables, the Cargo package `etach-shell`, the npm package `etach-app`, the repository folder `D:\Projects\ETACH`. **Font (v8.16, the teacher; was Be Vietnam Pro for the interface and Noto Serif for the test text):** one serif font, Faustina, for the whole app, interface and test text alike, bundled (Vietnamese test papers are set in Times New Roman); text on the main buttons and tabs (the workspace tabs Test, Key, Student answers and Report, and the main actions such as Grade student answers, Extract again, Print and Save as Word) is set a little larger so it looks as large as the same text in Merriweather; chips, the sidebar and small row buttons keep the normal size (v8.17).
- **Layout (v8.21, the teacher; the layout looked like Claude Desktop):** corners: papers (cards, panels, inputs, the print page) 2 px, buttons 6 px, chips fully round; the workspace tabs are rounded at the top only, like arched windows, the selected tab joining the panel. Sidebar: **New thread** keeps its earlier simple look, a plain row with "+" and a soft hover (v8.23; the light blue tint of v8.21 was dropped by the teacher); the Chats / Tests / Students tabs are separated by two white vertical lines, the selected tab stays white, and a hovered tab gets the light blue tint; the open thread is shown by a light blue tint only, stronger than the hover tint (v8.22; the notebook-margin mark of v8.21 was dropped by the teacher), and every name starts at the same place; group headings (for example the student names) are centred small capitals, bold, with a short rule under each, like the wordmark's motto line, in the Chats list only; the Tests and Students lists stay ungrouped, without headings (v8.27, the teacher); Settings is a labelled row (the gear and the word) at the bottom. Workspace: the panel is a sheet of paper (white, 2 px corners, a thin page shadow, a small grey margin around it); a double rule (a thin and a thinner line) under the workspace header. The typed symbols (+, ⋯, ⚙, ✕) are set in Faustina. The start screen (New thread) is simple and centred, with no heading (v8.25; no ETACH at all): the instruction and the Choose files button sit inside a dotted-border box shaped like a sheet of paper, which shows that photos can be dragged and dropped there (v8.21's test-paper start screen and v8.24's plain heading were dropped by the teacher). Every sidebar control shows the app's blue focus outline.

### 10.2 Settings (⚙)
- **Models (v7.0):** each role's model is chosen from a list of the models installed in Ollama (a tag can still be typed). A **model manager** lists the installed models with their size and the roles that use them; **Download** pulls a tag (typed, or from a short list of suggested tags) with progress and Cancel; **Delete** removes a model after a confirm (a model a role uses cannot be deleted until another is chosen). Downloads are the only network access; models live in `<app>\data\models`;
- model-call logs are **deleted automatically after 45 days** (configurable; logs used by a cached explanation are kept), plus a manual "clear now";
- backup (a `VACUUM INTO` copy plus the files, as a .zip; not encrypted in this version);
- the Ollama status and version.

---

## 11. Architecture

| Layer | Choice |
|---|---|
| Shell | **Tauri 2** (Rust, kept thin): the window, starting and stopping the two child processes inside a **Windows Job Object** (so they die with the app), notifications, file dialogs |
| Frontend | React + TypeScript + Vite + Tailwind, with all assets bundled. It talks to the sidecar over localhost HTTP + **SSE** (server-sent events) for live progress |
| **Pipeline sidecar** | **Python**: **LangGraph** graphs with the **SQLite checkpointer**; FastAPI on a random 127.0.0.1 port with a random token. It owns the database (the only writer). Packaged with PyInstaller as a **folder, not a single file** (faster start, fewer antivirus false alarms). It also has a **CLI** (`etach run …`, `etach eval …`) so it can be used without the UI |
| Inference | **Ollama** (installed once, minimum version **0.12.11** for logprobs). The app starts its own hidden `ollama serve` on a private port with `OLLAMA_MODELS` in the data folder, `OLLAMA_MAX_LOADED_MODELS=1`, and flash attention with a q8_0 KV cache (`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`; Phase 0: VRAM 7.9 → 3.5 GB, same answers). If the user's own Ollama (tray app) is running and has a model loaded, the app warns because of VRAM |
| Storage | SQLite (WAL) + FTS5, plus a content-addressed file store (`data-model.md`) |
| **One app folder** (v4.4) | Everything the app writes lives in **one folder**, default `D:\ETACH` (v8.18; chosen in the installer): the program, `settings.json`, `data\` (database, files, models, `models.toml`, backups), `exports\` (saved DOCX files, D4 v5.0) and `webview\` (the WebView2 cache). Uninstalling keeps them unless the teacher ticks **Delete all app data (tests, students, backups)** (v6.2), which deletes `data\`, `exports\`, `webview\` and `settings.json` from the app folder (v6.1). **Nothing is written to AppData** or anywhere else. To move or back up the whole app, copy the folder. Exception outside our control: Ollama's own installer places Ollama in `AppData\Local\Programs\Ollama` unless the teacher installs it elsewhere. Exceptions the teacher accepted (v4.10): the app installer's Start-menu and desktop shortcuts, its uninstall entry and install-folder record in the registry (HKCU), and, only when WebView2 is missing, the WebView2 download. The uninstaller removes the shortcuts and the registry entries; WebView2, if it was downloaded, is a shared Windows component and stays. Their exact locations, for removal by hand, are in `docs/release-notes.md` |
| Documents in | PyMuPDF (a PDF with a text layer skips vision transcription: its text goes to the vision model **as text**, since NuExtract3 accepts text too), python-docx (text + embedded images) |
| Printing | The webview print dialog (D4) |
| OS | The sidecar blocks idle sleep while running (`SetThreadExecutionState` through ctypes) (D23) |

**Offline:** CSP `default-src 'self'` plus `connect-src` limited to localhost (`http://127.0.0.1:*`, since the sidecar's port is random); no updater, no analytics, bundled fonts. The only network access is `ollama pull`, started by the teacher.

---

## 12. Quality and measurement

Speed is **not promised yet**. It is measured once the framework exists (Phase 1).

| Area | Goal |
|---|---|
| Printed transcription | ≥ 98% of questions correct without edits (held-out fixtures) |
| Answer reading | ≥ 95% correct; **the logprob confidence flags most wrong readings** (target ≥ 90%, reported with its uncertainty, since the fixture set is small) |
| Key after verification | High accuracy. Wrong keys that are *confident* can still happen, because the same model checks its own work, so the teacher's glance before printing matters (D9) |
| Stop/resume | No finished step lost; an interrupted step restarts cleanly (tested in Phase 0) |
| Fixtures | 30+ over time, split into **tuning** and **held-out** sets |
| Measured, no target yet | Time per step and per run, VRAM, tokens per step |

---

## 13. Delivery plan

> **The authoritative order, the checks and the progress are in [`initial-plan/plan.md`](initial-plan/plan.md).** The phases below are only a summary. The plan runs the extraction-quality and model-choice work (Phases 1 and 3's model testing) as parallel measurement tracks M1/M2, which gate only packaging and acceptance.

### Phase 0 — Framework (model-agnostic, no UI)
- The Python package: pydantic classes, SQLite schema and migrations (`data-model.md`), the content-addressed file store.
- The Ollama client: roles → model tags, `format` schemas, images, `think` on/off, **logprobs**, cancellation, recording every call to `llm_calls` (llm-design §3, §6).
- The LangGraph **extraction graph** with the SQLite checkpointer; **Stop, Resume, crash-resume** (D22); the CLI.
- Tests: pytest unit tests (renumbering, scoring, text comparison, answer-box matching), **replay tests** from recorded Ollama responses, and the eval harness skeleton with the first fixture (Lớp 8 HK1 Đề 1).

### Phase 1 — Extraction quality
NuExtract3 prompts for transcription and answer reading (native template format), logprob confidence, fixtures (the start of the 30+ set), measuring speed and VRAM, and trying the teacher's candidate models.

### Phase 2 — App
Tauri shell, threads, drop, **photo check**, running indicator with Stop/Resume, extraction card, Tests tab and search, duplicate warnings, Review queue, printing the clean test.

### Phase 3 — Grade button
The grading graph (v9.0: its key part, with the skill tags, also runs on its own after every extraction, D2/D16): using a key read from a 🔑 photo, AI key + verification, skill tags, confidence-aware grading, explanations (cached), weak points, questions for the teacher, report draft and print, re-grading after a key is verified or a merge.

### Phase 4 — Packaging
PyInstaller folder build, Ollama detection and version check, first-run model download, backup, and an offline check with the network off.

### Later
Generation (retest, similar test), typo pass, DOCX, Vietnamese normalization, encryption, automatic photo cleanup, picture cropping.

---

## 14. Future
Everything in "Deferred" (§2), plus: phone → PC upload through a LAN QR page; few-shot examples learned from Review corrections; a bridge to EnglishTest_Tutor / ktv20; class-level analytics; explanations adapted to the student's level (a weaker student gets the meaning of the key words and the sentence; a stronger one also gets the grammar point; teacher, M2 ratings 2026-10-12).

---

## 15. Risks and open questions

| # | Risk / question | Mitigation or decision point |
|---|---|---|
| R1 | NuExtract3's reading of handwriting, circles and underlines is undocumented | Assumed capable (D7); more prompting first; the fixtures measure it |
| R2 | Messy handwriting, answers between questions, answer boxes on other pages | Full-question-list conditioning, enums, logprob confidence, `?`, Review |
| R3 | Speed of the reasoning model on 6 GB | The teacher tests small models; measured in Phase 1; Grade is on demand, not on the critical path; the key (v9.0) is made right after the extraction, while the teacher can already read the test |
| R4 | Ollama details: whether logprobs work together with `format` schemas and image input, and how NuExtract3's own template roles interact with `format` | Verified first in Phase 0; fallbacks in llm-design §6 |
| R5 | Python sidecar packaging on Windows (size, antivirus) | PyInstaller folder mode; Phase 4 |
| R6 | A teacher prints before glancing | `?` marks are clearly visible on the draft; the print view shows the unsure count |
| R7 | Two Ollama servers competing for VRAM | Detect and warn (§11) |
| R8 | Laptop conditions: slower on battery, thermal throttling on long runs, an external monitor wired to the NVIDIA GPU using VRAM | Measured in Phase 1; the running indicator warns "on battery" |
| – | No open questions. Q1–Q3 were answered in v4.2 (D13, D24, non-goals); P1 was answered in v4.3 (D18: blocked, with a "Start a new thread" button). | – |

---

## 16. Glossary

| Term | Meaning |
|---|---|
| Đề giữa kì / cuối kì | Mid-term / final-term school test |
| THPT / TS10 | National graduation exam / grade 10 entrance exam |
| Mã đề | Test variant code |
| Thread | One conversation = one test (one attempt or one blank test) |
| Run | One extraction of a thread's photos (the vision model only); since v9.0 each extraction is followed by a **key run** (the reasoning model makes the key, D2/D16) |
| Grade | The button that runs the reasoning model on an extracted attempt |
| Test bank | The set of canonical, standardized tests |
| Review queue | Items the app decided on its own and wants checked later |
| Logprob | The model's probability for each output token, used as confidence |
