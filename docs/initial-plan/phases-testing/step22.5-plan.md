# Step 22.5 plan: the teacher's fifth look (app 0.5.0) and both quality plans

| | |
|---|---|
| Status | **Planning, 2026-10-23.** Decisions in §4 are asked one at a time before the sub-step that needs them; sub-steps get their checklist and requirements in `docs/initial-plan/plan.md` when they start. |
| Build reviewed | Installer 0.5.0 (step 22.4.9, main at e94e4cf) |
| Owner | The orchestrating session. |
| Next action | 22.5.1–22.5.7 ✅; 22.5.8: installer 0.6.0 built (61eb155), round verified, E2E_SHELL passed. The teacher wants to discuss the theme before installing; any theme work means a rebuild before release. Then the teacher merges and step 22 runs on 0.6.0. |

The teacher chose to build the improvements before step 22's acceptance (2026-10-23), and chose "Everything" for this
round: the teacher's 10 comments on 0.5.0, every item of `docs/initial-plan/plan-grading-quality.md` and every item of
`docs/initial-plan/plan-extraction-quality.md`. The round ends in installer 0.6.0; step 22 then runs on 0.6.0.

Same way of working as steps 22.1–22.4: sub-steps built one after another on stacked branches `step/22.5.N-<slug>`;
before the installer step, parked questions are asked and their answers built; the user's `E2E_SHELL --release`. A
fresh verifier runs after 22.5.2, 22.5.3, 22.5.5, 22.5.6 and 22.5.7 (each before its GPU check), not after every
sub-step (teacher, 2026-10-23). GPU checks G1–G4 (§7) follow the CLAUDE.md rules: the code they run is verified first,
each change is its own commit, and the teacher is warned before each run.

The teacher's planning rule (2026-10-23): every comment and every plan item is covered by a step (one step may cover
several), and the order of the steps must make sense. §3's coverage table checks it.

## 1. The teacher's comments (verbatim, 2026-10-23)

1. Test in "Test" tab have different ways to display them? two are like like this "C:\Users\HOME\Pictures\Screenshots\Screenshot 2026-10-22 111155.png", the others are like this "C:\Users\HOME\Pictures\Screenshots\Screenshot 2026-10-22 111242.png" . Really examine the headings there. Whats the logic here. The inconcistency really kills me. And when I click "Back to thread" in Grade 8 - Final Term 2 - Nguyễn Hữu Thọ - 2025 - Test G Test and it redirect me to Screenshot 2026-10-22 111155.png. ???

   Clarified (2026-10-23): the second screenshot was the wrong file; the other look is a test opened as its thread's own
   test (a title bar, the thread's tabs). "But clicking "back to thread" redirect to here 047.png regardless of which
   test. The 742 image is accessible via "Back to thread" before i click on the left tab for image 047. But after going
   to 047, clicking back to thread redirect to 047. seems like a strange bug."

2. "C:\Users\HOME\Pictures\Screenshots\Screenshot 2026-10-20 112934.png" As you can see in the picture, the series options are messy. I have checked all the test, the series availiable only are "De Du Doan Tuyen Sinh vao 10" . Why does the field lists out Test Names, is there bad data in database or app logic failure? And also, we should add "Series" tab in setting to change, add or delete

3. In settings, Since "Occasions" "School" "Series" are essentially the same: a set of attributes describing a test. They go under a new tab "Test Attributes" in settings. users click in settings and then they chose to change which one to change, which redirect once more to the menu. When they hit back, they go back to the "Test Attributes" menu of Settings. Now a 2 click instead of 1.

4. Extraction quality: 30 is good but 31 is a mess. seems like switching the pages make the reading bad.  Everything seem good until 31. IDK why but isnt all of these turn into text then processing? So why then theres a concept of pages anymore on test?

5. I changed my mind about [1 point, 0.25 each]. lets just be simple. Delete those. Just a simple [10/number of question each] once at the start of each test.

6. Tests tab: test should be arrange default by alphabet. Currently it is sorted by date created and I found that very confusing. Though build a small sort by button feature next search tests, you usually see in other apps. The button is a square and its side is equal to the hieght of the rectangle of the search tests bubble. It will take a bit of space of the search tests bubble

7. "Extract again" create a new test. Which then trigger the "looks like" feature, which tells the test is similar to the test from which it is "extracted again" from. Can you just replace the current one or the technical implementation is hard?

8. It said T-0008, i searched it in search tests but leaves nothing. It is because search test only search for name. In this case, the solution is to make the search test able to search code name too, though quiet feature. It  is bad UI to say T-0008 is similar then when you search T-0008, it returns nothing.

9. In Key tab or Student Answer tab, you double click or click edit to edit. Now you have to backspace and then type the thing you. I want when you double click, it will already have selected the old answer so you only need to type the new value. This saves one click but over a lot of times.

10."C:\Users\HOME\Pictures\Screenshots\Screenshot 2026-10-22 104029.png"  whats the rule for "..." here? some line just "..." at a different spot.

## 2. What the orchestrator found (2026-10-23, from the code, read-only; no app data read)

- **Comment 1: two layouts, and Back.**
  - The test page has two layouts. Opened as the thread's own test, it shows the thread's title bar and the thread's
    tabs (Test · Key, plus Student answers and Report once there is a graded paper). Opened from the Tests tab while
    another thread is open, it shows "← Back to thread" and only Test · Key (`app/src/features/panels/panelView.ts:58`,
    `app/src/components/AppShell.tsx:310`, `:568`).
  - Back does not look up the test's thread. It closes the panel and shows `activeId`, the thread last clicked in the
    sidebar (`AppShell.tsx:251-259`). That thread has a test, so Back lands on that thread's test page every time.
  - Section titles differ from test to test. Test 3 reads "I. PRONUNCIATION" plus an extra line "Question 1. Which
    word…" that repeats the question. Test G and Test 4 read a bare "I.". These are what the model wrote.
  - On Test G, the options show as "A.." with the word on the next line. Not yet traced.
- **Comment 2: the series list is a list of tests.** The "Same series as" picker lists tests, not series. Its bold label
  is `source || school || display_name` (`app/src/features/photo-check/ExistingTestSearch.tsx:32`). A test with no
  series therefore shows its school ("Nguyễn Hữu Thọ") or its name. This is app logic, not bad data. "Series" is the
  free-text `meta.source`; there is no Series list.
- **Comment 3:** Settings has the tabs General · Models · Occasions · Schools
  (`app/src/features/settings/SettingsPanel.tsx:65`). `SchoolList.tsx` is a copy of `OccasionList.tsx`.
- **Comment 4: typed PDFs still go page by page.** A typed PDF's text goes to the model one printed page at a time
  (`sidecar/src/erh/store/documents.py:138`). Only a Word file's text is joined and re-cut at headings
  (`split_text_page`). This is the page-break problem recorded in `docs/initial-plan/plan-extraction-quality.md` ("Content cut at page
  breaks"): on Test 4, questions 29–34 became one-question sections at the page 3/4 break. Photos are pages because each
  photo is a picture of one page.
- **Comment 5:** `_points_tag` (`sidecar/src/erh/domain/test_text.py:217`) writes "[x points, y each]" on each
  heading. The Word export reuses it (`domain/docx_export.py:34`, `:140`), and Format help shows it
  (`TestPanel.tsx:641`). Points are 10 ÷ the graded questions (`domain/points.py:56`); typed points are ignored.
- **Comment 6:** the Tests list is sorted by last change, `updated_at DESC` (`sidecar/src/erh/store/repos/tests.py:204`),
  not by date created. Search results are sorted by match rank.
- **Comment 7: Extract again.**
  - `POST /threads/{id}/extract-again` runs with no existing test, so `save_extract` inserts a new test
    (`sidecar/src/erh/graphs/extract.py:507-530`). The old test stays in the bank.
  - `compare_bank` compares against every test, including the old one, so the new test "looks like" it.
  - Replacing in place is feasible. It needs:
    - the same test id;
    - keys and tags re-mapped by question (`similarity.align_questions`);
    - re-grading of other attempts on the test;
    - Review items re-pointed or closed;
    - `test_pages` replaced;
    - the old test left out of the comparison.
- **Comment 8:** the search index has `test_id` as `UNINDEXED` (`sidecar/src/erh/store/migrations/0001_init.sql:96`), so
  "T-0008" finds nothing. The "looks like" notice shows only the id (`app/src/features/cards/ExtractionCard.tsx:253`).
- **Comment 9:** the Key and Student answers inputs only `autoFocus` (`KeysPanel.tsx:267`, `AnswersPanel.tsx:295`); the
  old value is not selected.
- **Comment 10:** sidebar titles are cut with CSS `truncate`. A row with an unsure count ("● 10") and the "⋯" button
  has less room, so its title is cut earlier. The full name is in a hover tooltip (`ThreadList.tsx:159`).

## 3. Work packages, in order (installer 0.6.0)

Screens first (no model, quick to check); then the question-type change that grading and extraction both build on; then
grading; then extraction; then the installer. Each model-side group gets its GPU check before the next group builds on
it.

| Sub-step | Covers | What | Where | Verifier |
|---|---|---|---|---|
| 22.5.1 Moving around and lists | 1, 6, 8, 9, 10 | No Back button on a test opened from the Tests tab (D1), the same title bar as a thread's own test; Tests list A–Z by default and a square sort button (D3); search matches the test id; the "looks like" notice names the test and its id; editing a key or a student answer selects the old value; the same name width on every row (D4) | UI + sidecar search | with 22.5.2 |
| 22.5.2 Settings, series, test text, Extract again | 2, 3, 5, 7, 1 (headings, "A..") | Settings: General · Models · Test attributes (a menu: Occasions · Schools · Series; Back returns to it); a Series list like Schools, seeded once from today's series values; "Same series as" lists series names and copies grade, occasion, term and year from the series' newest test (D5); headings lose "[x points, y each]" and the line under the title reads "10 points · 0.25 each" (D7), Word file and print too; untitled sections take their title from the section skill (D2); the "A.." options traced and fixed; Extract again keeps the test id (D8) | UI + sidecar | ✔ |
| 22.5.3 Fewer question types | extraction plan | `answer_form` (choice / word / sentence / writing, from the model) × `context` (single / paragraph, from code); `verb_form` goes; a migration; grading rules, validators, answer reading, test text, eval (D9) | Sidecar + docs | ✔, then G1 |
| 22.5.4 Grading calls | grading plan | Roles `grading_check` and `extraction_check` (qwen3.5:4b by default, a picker each); the question text gives `answer_start`; the judge reasons before its verdict, strict; `ai_key_fast` names only the questions needing a key; `explain` reasons first (hidden), no grade in the prompt; `difficulty_notes` removed (D10); `tag_skills` once per section with its heading and passage, cap 3 | Sidecar + UI | with 22.5.5 |
| 22.5.5 The checker's answer, weak points over time | grading plan | The checker's answer and reasoning on an unsure key, on hover or focus; "date taken" on the attempt; the trajectory classification in code; skill names to the summary (D11) | Sidecar + UI | ✔, then G2 |
| 22.5.6 Typed pages, reading student answers and keys | 4, extraction plan | Typed PDF texts joined and cut like a Word file (D12); the typed-text prompt (`answer_start` with "=>" and none, a repetition guard); each page read only for its own questions; the key reading ignores explanations; "double-checked" only after a real check; the listening part shown on the student answers | Sidecar + UI | ✔, then G3 |
| 22.5.7 Photos: page breaks, the re-read, answer-number errors, model trial | 4, extraction plan | The "last open unit" hint and the merge rule; tiles measured on qwen3.5:4b and the targeted re-read (`extraction_check` role); the eval splits renumbering from reading errors; candidate vision models (D13, deferred if none) | Sidecar + eval | ✔, then G4 |
| 22.5.8 Installer 0.6.0 | | As 22.4.9 | Version, build, release notes | its own check |

The split was 17 sub-steps first; the teacher asked to combine them (2026-10-23) and chose these 8 (other options: about
5; keep 17). Sub-steps end where a GPU check needs a verified state, and items touching the same code go together.

**Why this order.** 22.5.3 comes before grading and extraction because the judge, answer reading, the validators and the
weak-point evidence (a right `choice` counts less) all use the question type. 22.5.4 adds the roles that `verify_key`
and the re-read (22.5.7) use. Answer reading per page (22.5.6) and the re-read (22.5.7) are measured together in G4,
because the time saved by reading only a page's own questions pays for the re-read.

**Coverage.**

| Item | Sub-step |
|---|---|
| Comment 1: Back and the two layouts; headings and "A.." | 22.5.1; 22.5.2 |
| Comments 2, 3, 5, 7 | 22.5.2 |
| Comment 4 | 22.5.6 (typed), 22.5.7 (photos) |
| Comments 6, 8, 9, 10 | 22.5.1 |
| Grading plan: model roles, `ai_key_fast`, the judge, explanations, difficulty notes, tagging | 22.5.4 |
| Grading plan: the checker on hover; weak points | 22.5.5 |
| Extraction plan: fewer question types | 22.5.3 |
| Extraction plan: page breaks (typed; photos) | 22.5.6; 22.5.7 |
| Extraction plan: the typed-text prompt (`answer_start`, repetition) | 22.5.6 |
| Extraction plan: answer and key reading, the key-photo label, the listening part | 22.5.6 |
| Extraction plan: the half-page re-read and the targeted re-read; answer-number errors; tune or replace the model | 22.5.7 |
| Extraction plan: the extraction-check role | 22.5.4 |

## 4. Decisions for the teacher (asked one at a time, before the sub-step that needs them)

- **D1 (22.5.1, comment 1):** where Back goes from a test opened in the Tests tab: the Tests tab, the test's thread
  (which one, if several), or no Back button.
- **D2 (22.5.2, comment 1):** untitled sections: leave them, have code fill a title from the section skill, or show only
  the instructions.
- **D3 (22.5.1, comment 6):** what the sort button offers (A–Z, Z–A, newest added, recently changed, by grade).
- **D4 (22.5.1, comment 10):** sidebar titles: keep the cut and the hover tooltip, cut every row at the same width, or
  wrap to two lines.
- **D5 (22.5.2, comment 2):** "Same series as" picks a series name or a test; the Series list is seeded from today's
  series values or starts empty.
- **D7 (22.5.2, comment 5):** the per-question line: wording and place, and in the Word file.
- **D8 (22.5.2, comment 7):** on Extract again, what happens to keys the teacher edited, and to other students' attempts
  on the same test.
- **D9 (22.5.3):** sign-off of the answer-form × context proposal, and how stored tests are migrated.
- **D10 (22.5.4):** the stored difficulty notes: kept as old data, or dropped.
- **D11 (22.5.5):** weak points: the thresholds, where the trajectory is shown, where the date taken is edited.
- **D12 (22.5.6):** typed PDFs: which page a picture or a question belongs to after the texts are joined.
- **D13 (22.5.7):** which vision models to try, if any.

## 5. Decisions taken

- **Scope** (teacher, 2026-10-23): "Everything": the 10 comments, the grading plan and the extraction plan in this round,
  before step 22. Other options: comments + grading + the light extraction items; comments + grading only.
- **D1** (teacher, 2026-10-23): a test opened from the Tests tab has **no Back button**; the sidebar is the way out.
  Other options: back to the Tests list; to the test's thread; both.
- **D3** (teacher, 2026-10-23): the sort button offers **A–Z, Z–A, newest added and by grade** ("I took inspiration
  from … claude ai web"). Not offered: recently changed (today's order).
- **D4** (teacher, 2026-10-23): **the same cut on every row**: every row keeps the same slot for the unsure count,
  empty when there is none, so every name is cut at the same place. Other options: keep as is; remove the count; the
  count under the name. (The teacher first read the count as part of the name; it is a separate mark.)
- **D5** (teacher, 2026-10-23): "Same series as" lists **series names; picking one sets Series and copies grade,
  occasion, term and year from the newest test of that series**. The Series list is **seeded once from today's series
  values**. Other options: a series name only; a test, as today; an empty list.
- **D7** (teacher, 2026-10-23): the per-question value goes **under the title**: "10 points · 0.25 each"; the test
  text has no points; the Word file and print show the same line. Other options: the text's first line; both. Writing
  sections keep "[not graded]", which marks them as not scored (orchestrator).
- **D2** (teacher, 2026-10-23, "I think 1", after asking the orchestrator's view): an untitled section **takes its title
  from its section skill** in capitals (e.g. "I. PRONUNCIATION"), editable; existing tests once. Guard (orchestrator):
  a section whose skill is `mixed` or missing stays untitled. Other options: leave untitled; ask the model.
- **D8** (teacher, 2026-10-23): Extract again keeps the test id. Keys the teacher typed or verified **stay where the
  question matches** (same printed number and text); changed questions are keyed again (other options: by number only;
  start fresh). When other threads use the test, the confirm dialog **asks**: update the test for every thread, or make a
  separate copy for this thread (other options: all follow; only this thread).
  Addition (teacher, 2026-10-23, after the verifier): AI keys on exactly matching questions are **kept** too (other
  option: made again).
- **D9** (teacher, 2026-10-23): build 22.5.3 as the proposal is written (`docs/initial-plan/plan-extraction-quality.md`, "Fewer
  question types"), **without sign-off first**; the teacher signs it off **after G1**, before the grading steps build on
  it (other options asked: sign off as written; `short_answer` as `word`; not this round; sign off after G1–G4). Orchestrator:
  the migration keeps each stored question's old type, so a revert loses nothing.
- **D10** (teacher, 2026-10-24): the stored difficulty notes are **dropped** by a one-time pass when the step is
  removed (other option: keep as old data).
- **D11** (teacher, 2026-10-24): weak points come from the student's trajectory with the **strict** thresholds: a
  label needs answers on 3 or more papers; "recent" is the last 2 papers by date taken; a right `choice` counts half;
  consistently weak = wrong on 2/3 or more of the papers; inconsistent = 35–65 % right (other options: 2+ papers;
  counting questions).
  - **D11a:** the date taken is set on the photo check card (default today) and can be changed on the Student answers
    tab (other options: one of the two only).
  - **D11b:** the trajectory labels show on the **Students tab** (other options: the grade report; both).
  - **D11c:** while a skill has not enough evidence, the report lists this paper's mistakes marked "this paper only";
    a label replaces that once there is evidence (other options: only labelled skills; labelled plus the top 3).
  - **D11d:** skills go **basics first** (the teacher: "if students are to lack fundamental, it is useless to talk
    about more advanced stuff"; vocabulary before grammar: "know the basic vocab (key words) to do the others"). Each
    skill has a level A1–B2 (grammar from its taxonomy; the 26 section skills from these base levels, approved by the
    teacher): A1 VOC-TOPIC; A2 VOC-COMM, PRON-VOWEL, PRON-ED, PRON-S, STRESS-2SYL, WF-NOUN, WF-ADJ, READ-DETAIL,
    READ-REF, SIGN, REWRITE-ORDER; B1 VOC-COLLOC, VOC-SYN-ANT, VOC-DICT, STRESS-3SYL, WF-VERB, WF-ADV, WF-NEG, READ-WORD,
    READ-MAIN, READ-CLOZE, REWRITE-START, REWRITE-CUE, REWRITE-COMBINE; B2 READ-INFER. Because questions of one skill
    differ in level (the teacher), the tagging call also gives each question a level; the base level is the fallback
    (other options: base levels only; change the table).
  - **D11e:** weak points above the lowest weak level are **held back behind a "Later, after the basics (N)" line**
    that the teacher can open (other options: hide them; order only).
- **D11f** (teacher, 2026-10-25, after the 22.5.5 verifier showed a choice-only skill could never be solid under "a
  right choice counts half"): a **guessing baseline** replaces the half rule: the share is rescaled by each question's
  chance level (1/k for a choice with k options), so all right = 100 % and chance-level = 0 % (other options: need more
  papers when all are choice; full credit).
  The teacher (2026-10-25): "lets see if this is too clogged. can be changed in the future": the weak-point rules
  and views ship as built and are judged in use (step 22); simplifying them later is open.
- **Models tab** (teacher, 2026-10-24): the picker descriptions show only on hover or keyboard focus (other options:
  keep under the names; shorter wording).
- **Skills view** (teacher, 2026-10-25, after the 22.5.5 screenshots showed names cut to a few letters): the student's
  skills open in a **wider view in the main panel**, and **clicking a student** in the Students tab opens it ("clicking
  student in student tab doesnt do anything now"). Other options: label under the name; wrap the name; leave as is.
- **D12** (teacher, 2026-10-25, on the orchestrator's recommendation when asked): after a typed PDF's text is joined
  and re-cut, each question gets the PDF page **its text starts on** (code keeps where each page's text starts), and
  pictures stay on the PDF page they are printed on (other options: the piece's first page; cut at page ends too).
- **Answer pages** (teacher, 2026-10-25): answer reading stays **per page** (each page asked only for its own
  questions) although on the recorded S1 sample 2 of 3 student answers sat on another page and are now not read
  (other options: own page plus answer boxes; own page plus the next page; back to all questions). G3/G4 count how often
  it happens.
- **G2** (teacher, 2026-10-25): the grading changes of 22.5.4–22.5.5 are accepted (§7 "G2 result").
- **G3** (teacher, 2026-10-26): typed pages (22.5.6) accepted (§7 "G3 result").
- **D13** (teacher, 2026-10-26, from the orchestrator's 4 proposals with sources, dates and stats): try **GLM-OCR 0.9B**
  (Zhipu/Z.ai, 3 Feb 2026, OmniDocBench v1.5 94.62, Ollama support by the maker) as a two-step photo reader (photo →
  OCR text → the typed-text path), against qwen3.5:4b in G4 (other proposals: Qwen3-VL 4B, PaddleOCR-VL 0.9B,
  DeepSeek-OCR 3B; GPU: GTX 1660 Ti, 6 GB).
- **G4** (teacher, 2026-10-26, from §7 "G4 result"): test photos are read by **GLM-OCR** ("glm-ocr for reading only";
  other options: vision as today; vision default with OCR as a setting). The student answers stay on qwen3.5:4b vision.
  The **tile re-read stays off** (the teacher first asked for the tile results, then a run of tiles with GLM-OCR, then
  chose "Off"; other option: on). The OCR reader becomes the default in a follow-up of 22.5.7 (R22.5.7.7). Models tab
  labels (teacher): "Test reader" / "Reads the test photos" and "Student answer reader" / "Reads the student answers from
  the photos" (other options: the builder's wording; split wording).
- **Parked questions** (teacher, 2026-10-26, one at a time, before 22.5.8; §6). Built in 22.5.8 (a):
  "Your details" → **"Test details"** (other options: keep; "The test details"); a key photo replacing an AI key
  **closes** its open unsure-key item (other: leave it); a Fix of an unmatched key-photo key onto a True/False question
  **turns the letter into T/F** (other: leave it; asked again in plain words); the unused `rank_weak_points` is
  **removed** (other: keep). Left as they are: the Extract again line wraps (other: shorten; widen); the one-action
  dialog's stacked buttons (other: one row); the T/F undo leaves open Review items on T/F (other: complete the undo);
  the skills view opens from the Students tab only (other: also from the paper's chip) and keeps its "Threads" list
  (other: remove); "Date taken" always shows on the upload card (other: only with a paper); Save writes every role's
  tag (other: only changed roles); a missing glm-ocr gives the technical message ("we haven't do this in many version
  for normal users yet"; other: a plain message; fall back to vision). **Later** (extraction plan): the 4 typed-PDF
  alignment gaps; the 2 photo page-break gaps; GLM-OCR's titles, 22 read as 21, "Unless …" stored as the cue (the
  teacher asked whether it is a cue; the orchestrator explained the app's cue vs opening words), the 35–36 answer box.
  Developer notes kept: `make_synthetic_grade.py:180` before the next recording; the resume across the
  difficulty-notes removal.
- **After the 22.5.1 build** (teacher, 2026-10-23): numbers in names sort **by value** (Grade 9 before Grade 10; other
  option: character by character); a test whose id equals the search is **always the top row** (other option: follow
  the sort). The builder's other points are kept as built: the id search matches a whole id only; Esc still closes a
  test opened from the Tests tab.
- **Split** (teacher, 2026-10-23): 8 sub-steps instead of 17, a verifier after 22.5.2, 22.5.3, 22.5.5, 22.5.6 and
  22.5.7.

## 6. Carried forward (ask before the installer)

- From the 22.5.2 second verifier (minor, not blocking): (1) the Extract again kept/replaced line (87 characters) wraps to
  two lines; (2) "Your details" may read as the teacher's own details ("The test details" is plainer); (3) with a hint, the
  one-action dialog stacks its buttons, unlike the other one-row confirms; (4) rare: a kept AI key with an open
  `uncertain_key` item that the same run's key photo replaces leaves the item open on the photo's key; (5) PRD v8.5.1 was
  labelled a patch though it adds behaviour (left as written).
- From the 22.5.3 checklist (d) verifier (294ee43): (5) **fix before the installer** (the app would not start): the
  first-start T/F relabel still collides when a question has explanation rows for both an old letter and the T/F letter
  it maps to (e.g. options `A. FALSE`/`B. TRUE` with rows `a` and `f`); the pass rolls back and every start fails with
  `IntegrityError`; unlikely on 0.5.0 data (readings were T/F only). Minor: (6) an open `key_unmapped` item keeps its
  key-photo letter, so a Fix onto a relabelled T/F question stores `B`, not `T`; (7) the documented revert does not map
  open Review proposals back; (8) data-model §2.3b, a missing comma after "`teacher_override`)".
- From the 22.5.4 verifier (0f73542): **fix before the next cassette regeneration**: `make_synthetic_grade.py:180`
  queues one `TagSkillsCall` answer (and `make_s1_seeded.py` reuses it), so a regenerated second-section tagging call is
  recorded as failed and later sections lose their tags silently. Minor: `llm-design.md:277` shows
  `extraction_check = true` in the sample `[client]` line (code default false; `llm/config.py` docstring omits it); Save
  writes all four role tags to `models.toml`, so a later change of a default tag won't reach that setup; a grade run
  stopped at `difficulty_notes` before the upgrade and resumed after it is untested. Done: items (5) and (8) above
  (22.5.4, R22.5.4.7).

## 7. GPU checks

| Check | After | Runs | Compares |
|---|---|---|---|
| G1 | 22.5.3 | typed Test 4 and photo Test G, extraction | question forms before and after; questions found |
| G2 | 22.5.5 | Test G's attempt, grading | verdicts, explanations, tags and time against 0.5.0's calls |
| G3 | 22.5.6 | typed Test 4, extraction | questions 29–34 in one section, no stray "A", `answer_start` |
| G4 | 22.5.7 | photo Test G, extraction with student answers | questions found, check failures, time, answer-reading time; tiles on and off; student answers not read because they sit on another page |

### G1 runbook (step 22.5.3, answer forms)

**Warning:** this uses the laptop's GPU for about 10–20 minutes. Do not use the laptop for other work while it runs.

Run on branch `step/22.5.3-question-types` (verified at 0747252, the T/F wording fix verified at d89c605), qwen3.5:4b
for both roles (the default of an empty data folder), into the throw-away folder `D:\ERH-gpucheck`, so the teacher's
data is not touched. The files are the same originals as the 22.4.7 check (step22.4-plan §7): national exam test 4
(typed PDF; T-0005) and Test G (4 photos; T-0006).

```
cd /d/Projects/Exam_Revision_Helper/sidecar && uv run erh run --data D:/ERH-gpucheck --spawn-ollama --pages "D:/ExamRevisionHelper/data/files/74/74995cf991339965edb2c55bd0168a175ca5eb500b6d5a5d800daaf3a4df6c88.pdf"
cd /d/Projects/Exam_Revision_Helper/sidecar && uv run erh run --data D:/ERH-gpucheck --spawn-ollama --pages "D:/ExamRevisionHelper/data/files/aa/aa0ca7c0cc9fe4db1b119f387623950a6f2237cddd685352af0151b40bc8ae1c.jpg" "D:/ExamRevisionHelper/data/files/c1/c11d21bbf85e887e4ecfef4f7b5d46d420a9629b4d2955e903504514b2132cc4.jpg" "D:/ExamRevisionHelper/data/files/6e/6e431bd04de05ce909ff16a2d441d5d4cb0b4a5c4ece94a28520940268554de8.jpg" "D:/ExamRevisionHelper/data/files/a3/a39fe6e7db42f734ddf51b1b2056058b7eb89030e43904f96b292e85fbc38d22.jpg"
```

The orchestrator then reads the two new tests in `D:\ERH-gpucheck` (read-only) and, with the teacher's permission,
T-0005 and T-0006 in `app.db` (read-only), and records below: each question's form against the printed layout and
against its 0.5.0 type (by the D9 table); True/False sections given T/F options; new blank-check or option-check flags;
questions found; time. Then the teacher signs off D9 or asks for a revert, and `D:\ERH-gpucheck` is deleted.

### G1 result (2026-10-24, run by the teacher on 0747252 + d89c605; read by the orchestrator, the 0.5.0 tests with the teacher's permission, the teacher running the read)

**Teacher (2026-10-24): "Sign off + fix T/F"**: the answer forms are accepted; a code fix relabels True/False options as
T/F (step 22.5.3 checklist (d)) with its own verifier before 22.5.4; no GPU re-run. (Other options: fix and re-run G1;
revert 22.5.3.)

| | Typed Test 4 (T-0001 vs 0.5.0 T-0005) | Photo Test G (T-0002 vs 0.5.0 T-0006) |
|---|---|---|
| Questions found | 40 (40) | 40 (40) |
| Forms | all 40 equal the D9 mapping of the 0.5.0 type and fit the printed layout; cues (29–34) and opening words (37–40) kept | 5–12 now `choice` with their A–D options (0.5.0 lost them: gap_fill, no options); 23–28 `choice` A–D (0.5.0: short_answer); 29–34 `word` with cues, 37–40 `sentence` as before |
| Still broken (page reading, not the forms) | – | 1–4, 15, 35–36 with empty stems under answer-box lines ("Phần trả lời…"); extraction-plan work (22.5.6–22.5.7) |
| True/False | 23–26: the model wrote options A = True, B = False, so the code added no T/F pair | 17–20: A = FALSE, B = TRUE (reversed); the student's paper read as A, B, B, B; 21 got T/F from the section instructions though its stem reads like an open question |
| Time | 235 s (0.5.0 check 215 s); transcribe 223 s | 481 s (0.5.0 check 361 s): transcribe 285 s, read student answers 186 s; no tile re-read |

### G2 runbook (steps 22.5.4–22.5.5, grading)

**Warning:** this uses the laptop's GPU for about 20–30 minutes. Do not use the laptop for other work while it runs.

Run on branch `step/22.5.5-checker-weakpoints` (22.5.4 verified at 0f73542, 22.5.5 at c754e2f), qwen3.5:4b for every
role (the default of an empty data folder), into the throw-away folder `D:\ERH-g2`, so the teacher's data is not
touched. First extract Test G's 4 photos (as in G1; this also reads the student's paper as A-0001), then grade that
paper (no key photo, so the AI writes and checks the keys, tags each section, judges, explains and summarises).

```
cd /d/Projects/Exam_Revision_Helper/sidecar && uv run erh run --data D:/ERH-g2 --spawn-ollama --pages "D:/ExamRevisionHelper/data/files/aa/aa0ca7c0cc9fe4db1b119f387623950a6f2237cddd685352af0151b40bc8ae1c.jpg" "D:/ExamRevisionHelper/data/files/c1/c11d21bbf85e887e4ecfef4f7b5d46d420a9629b4d2955e903504514b2132cc4.jpg" "D:/ExamRevisionHelper/data/files/6e/6e431bd04de05ce909ff16a2d441d5d4cb0b4a5c4ece94a28520940268554de8.jpg" "D:/ExamRevisionHelper/data/files/a3/a39fe6e7db42f734ddf51b1b2056058b7eb89030e43904f96b292e85fbc38d22.jpg"
cd /d/Projects/Exam_Revision_Helper/sidecar && uv run erh grade --data D:/ERH-g2 --attempt A-0001 --spawn-ollama
```

Then the orchestrator reads `D:\ERH-g2` (read-only) and, with the teacher's permission, 0.5.0's grading of Test G
(T-0006) in `app.db`, and records below: keys (AI keys, unsure keys and the checker's answer), verdicts (the judge on
sentence answers, incl. ones continuing the opening words), explanations (reasoning length, cap hits, the Vietnamese
text), tags and per-question levels (stored, and equal to the report's weak-point levels), the report's weak points
(this paper only, basics first, held back) and the summary (names, no codes, no held-back skill), time per node. Then
the teacher accepts or asks for changes, and `D:\ERH-g2` is deleted.

### G2 result (2026-10-25, run by the teacher on c754e2f; read by the orchestrator, 0.5.0's calls and keys with the teacher's permission, the teacher running the reads)

**Teacher (2026-10-25): "Accept"**: the grading changes of 22.5.4–22.5.5 are accepted as built.

Test G extracted again (472 s; 48 questions for 40 printed: 1–4, 15, 35, 36 twice, 7 empty from answer-box lines; 38–40
without a key; 17 sections), then its paper graded (705 s, 1.46/10; 7 correct, 9 incorrect, 32 uncertain because their
key is unsure). Against 0.5.0's first grading of Test G (≈ 643 s):

| Node | 0.5.0 | G2 |
|---|---|---|
| `ai_key_fast` | 7 calls, 82 s | 13 calls, 104 s (more sections needed keys) |
| `verify_key` | 38 calls, 391 s | 36 calls, 429 s (61 % of the time); 22 keys unsure: 20 disagreed, 2 did not finish |
| `tag_skills` | 1 call, 52 s | 13 calls (per section), 96 s; levels stored (7 A1, 29 A2, 12 B1) |
| `difficulty_notes` | 2 calls, 68 s, both failed | removed |
| `explain` | 8 calls, 38 s, max 117 tokens | 8 calls, 51 s, max 186 tokens (cap 512) |
| `weak_points` | 11 s | 15 s; 1 A1 weak point shown, 6 held back, all "this paper only"; names, no codes |

Keys against the teacher's 40 confirmed 0.5.0 keys, on the 23 questions both readings got the same way: the AI key
matched on 17 (30 "enroll" vs "enrol" counted wrong); wrong on 19, 22, 24, 26, 27 and 37. The checker caught 4 real AI
mistakes (19, 24, 26, 27: its answer equals the teacher's), raised 3 false alarms (16, 17, 35) and answered
"insufficient context" on 22. Questions 5–12 are not comparable (0.5.0 lost their options, so the teacher typed words);
1–4, 15, 35, 36 duplicates and 38–40 are extraction failures (22.5.6–22.5.7).

### G3 runbook (step 22.5.6, typed pages)

**Warning:** this uses the laptop's GPU for about 5 minutes. Do not use the laptop for other work while it runs.

Run on branch `step/22.5.6-typed-pages-reading` (verified at 8ec134d), qwen3.5:4b, into the throw-away folder
`D:\ERH-g3`: typed Test 4 (the national exam PDF, T-0005 in 0.5.0; G1 read it as T-0001).

```
cd /d/Projects/Exam_Revision_Helper/sidecar && uv run erh run --data D:/ERH-g3 --spawn-ollama --pages "D:/ExamRevisionHelper/data/files/74/74995cf991339965edb2c55bd0168a175ca5eb500b6d5a5d800daaf3a4df6c88.pdf"
```

The orchestrator then reads `D:\ERH-g3` (read-only) and records below: questions 29–34 in one section, no stray
section "A", `answer_start` on 37–40, each question's page against the PDF, pictures on their page, any "repeated
output" item, the number of model calls and the time (G1: 4 calls, 235 s). Then `D:\ERH-g3` is deleted.

### G3 result (2026-10-26, run by the teacher on 8ec134d; read by the orchestrator)

**Teacher (2026-10-26): "Accept"**: 22.5.6 is accepted.

Typed Test 4 into `D:\ERH-g3` (T-0001): **done in 187 s with 2 model calls** (G1: 4 calls, 235 s; the 4 PDF pages became
2 text pieces).
- **Sections:** 8, in order, all 40 questions once: I. PRONUNCIATION 1–4 · II 5–14 · III. SIGNS 15–16 · IV. READING
  17–22 · V. READING 23–28 · **VI. WORD FORM 29–34 in one section** · VII. VOCABULARY 35–36 · VIII. REWRITE 37–40. **No
  stray section "A"** (G1 and 0.5.0 had one, and 29–34 as one-question sections).
- **Opening words** on 37–40: "Dean is", "It has been a very", "Despite her", "Although" (as in G1).
- **Pages:** 1–12 p1, 13–22 p2, 23–28 p3, 29–40 p4. Not checked against the PDF: 0.5.0's page 1 ended at question 14,
  so 13–14 may belong to page 1 (the stems start there) — to check in the app.
- **Review items:** one `validator_failed` on page 4: 35 and 36 (VOCABULARY, from a dictionary entry) have no `____`;
  one `unknown_occasion`. No "repeated output" item.

### G4 runbook (step 22.5.7, photos)

**Warning:** this uses the laptop's GPU for about 30 minutes (three runs) plus a download of about 2.2 GB. Do not use
the laptop for other work while it runs.

The join guard found by the 22.5.7 verifier (a new titled section at the same number dropped a question) was fixed in
e6c5af1 with tests; the teacher asked for no full verifier for it ("fix but no need for verifier or a fast lazy
verifier"), so the orchestrator checked the diff and its tests (10 passed) and the builder's full run (2125 passed).

Branch `step/22.5.7-photos` (9468cdb). Three throw-away folders, each with its own `models.toml` (written by the
orchestrator): `D:\ERH-g4a` qwen3.5:4b tiles off; `D:\ERH-g4b` tiles on (`retranscribe_tiles_keep = "better"`);
`D:\ERH-g4c` GLM-OCR two-step (`photo_reader = "ocr"`, `[roles.ocr] model = "glm-ocr"`). `reread_pieces` off in all.
First pull GLM-OCR with the Ollama app running (`ollama pull glm-ocr`), then the same Test G photos into each folder.

The orchestrator then reads the three folders (read-only) and records: questions found, duplicates, empty questions,
check failures, time per node, answer-reading time, student answers on another page not read; the teacher picks the
photo reader (and tiles) for 0.6.0. The three folders are then deleted.

### G4 result (2026-10-26, run by the teacher on a9ae16d; read by the orchestrator, the throw-away folders only)

**Teacher (2026-10-26):** GLM-OCR reads test photos; tiles off (§5 "G4"). A fourth run, `D:\ERH-g4d` (GLM-OCR with tiles
on), was added at the teacher's request. The first paste ran g4a only (three commands in one `!`); g4b–g4d ran one by one.

Test G (4 photos, 40 printed questions) with its student paper:

| | g4a vision, tiles off | g4b vision, tiles on | g4c GLM-OCR, tiles off | g4d GLM-OCR, tiles on |
|---|---|---|---|---|
| Total | 495 s | 914 s | 552 s | ≈ 750 s |
| Reading the test | 317 s (4 calls) | 317 s + tiles 416 s (8 calls) | 376 s (4 OCR + 4 structure) | 374 s + tiles 197 s (4 calls, pages 3–4) |
| Reading student answers | 166 s | 172 s | 168 s | 171 s |
| Questions found | 51 | 53 | 42 | 42 (identical to g4c) |
| Duplicated numbers | 11 (1–4, 17–21, 35–36) | 13 (1, 7–8, 15–22, 35–36) | 3 (21, 35, 36) | 3 |
| Missing numbers | – | – | 22 (read as a second 21) | 22 |
| Word-form 29–34 | sentences lost (cue only) | sentences lost | all 6 complete | all 6 complete |
| Pages failing a check | 4 of 4 | 4 of 4 (tiles fixed none) | 2 of 4 (3: numbering; 4: 35–36 no blank) | 2 of 4 (tile readings not better, dropped) |
| `uncertain_answer` items | 11 | 15 | 19 | 19 |

- **Vision's duplicates** come from reading the "Phần trả lời" student answer boxes as questions and from reading 17–21
  twice across the page 2/3 break. GLM-OCR made only one such box (35–36).
- **GLM-OCR's weaknesses:** section titles "2", "3", "I", "A" instead of the printed titles; 22 numbered 21; 37's opening
  words "Unless …" stored as the cue, not `answer_start`.
- **Tiles** read their halves with qwen3.5:4b vision in both readers; neither run improved a page.
- Not measured by these runs: student answers on another page not read, and the eval's two number-error columns.
