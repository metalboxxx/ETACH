# Plan: extraction quality

| | |
|---|---|
| Version | **v0.16.1** (2026-11-03) — built in step 22.5 (`docs/initial-plan/phases-testing/step22.5-plan.md`) |
| Based on | `docs/initial-plan/plan.md` (steps 1–22, step 22.5) |

| Version | Date | Change |
|---|---|---|
| **v0.16.1** | 2026-11-03 | Patch, after the initial plan: moved to `docs/initial-plan/`; the tracker rows are ✅, as in plan.md's tracker |
| v0.16 | 2026-10-26 | Minor: G4 result: GLM-OCR is the default photo reader, tiles and the targeted re-read off (step 22.5.7, R22.5.7.7); tracker row 22.5.7 |
| v0.15 | 2026-10-26 | Minor: step 22.5.7 sidecar is built (photo page breaks, the targeted re-read behind `reread_pieces`, the answer-number error metrics, the GLM-OCR two-step reader behind `photo_reader`); the tracker rows say so |
| v0.14.1 | 2026-10-25 | Patch: tracker row 22.5.6: sidecar and UI built, verifier fixes, G3 next |
| v0.14 | 2026-10-25 | Minor: step 22.5.6 sidecar part (a) is built (typed PDFs joined, typed-text prompt, answer reading per page, key explanations ignored, key-photo keys as `from_key_photo`, the listening range); the tracker row says so |
| v0.13 | 2026-10-24 | Minor: fewer question types is built (step 22.5.3, awaiting G1); the tracker row says so |
| v0.12.1 | 2026-10-23 | Patch: the tracker follows step 22.5's 8 sub-steps |
| v0.12 | 2026-10-23 | Minor, teacher: the work is built in step 22.5, before step 22; the tracker lists its sub-steps |
| v0.11 | 2026-10-23 | Patch: the fewer-question-types proposal notes that what a question tests is already held by the section skill and the skill tags |
| v0.10 | 2026-10-23 | Minor: an extraction-check model role (planned in `docs/initial-plan/plan-grading-quality.md`) |
| v0.9 | 2026-10-22 | Minor, teacher: answer reading is only the page's own questions, number and answer next to it (no answer-box pages); the key reading ignores explanations; key-photo keys are not labelled double-checked |
| v0.8 | 2026-10-22 | Minor: answer reading asks each page only for its own questions (plus answer-box pages); the time saved pays for the re-read |
| v0.7 | 2026-10-22 | Minor: the targeted re-read as a patch the code applies (first), and the teacher's preferred alternative, a model with bounded edit tools (later) |
| v0.6 | 2026-10-22 | Minor: re-measure the half-page re-read on qwen3.5:4b (GPU); how it works today and a targeted re-read |
| v0.5 | 2026-10-22 | Minor: fewer question types (answer form × context), the teacher's proposal |
| v0.4 | 2026-10-22 | Minor: the step 22.4.7 GPU check results; content cut at page breaks (evidence from the teacher's app data) and a proposed fix |
| v0.3 | 2026-10-19 | Minor: the step 22.3.6 GPU check results |
| v0.2 | 2026-10-17 | Minor: the teacher's evidence from the third review (step22.3-plan comments 6, 13, 16) |
| v0.1 | 2026-10-14 | First version: records the teacher's comment 8 from the second review (step22.2-plan §1) |

## Why

The teacher's second review of the app (0.2.0, `docs/initial-plan/phases-testing/step22.2-plan.md` comment 8): the first extraction
model (NuExtract) "is pretty bad". Checking a student's answers was hard because:
- it was unclear whether the answers included the listening part;
- answers sat on the wrong question numbers, and it was unclear whether that came from leaving out the listening part
  or from the image model.

Step 22.2.4 makes the app keep the paper's printed numbers wherever the app itself renumbers. What remains for this plan
is the model side.

## Evidence from the teacher (step22.3-plan, 2026-10-16)

- Comment 13: on the same kind of paper, qwen3.5:4b read the test much better than NuExtract: national test 3 was read
  by NuExtract, national test 5 by qwen3.5 (both in the teacher's app data). qwen3.5:4b became the default image model
  in step 22.3.5 (decision D4).
- Comment 6: NuExtract transcribed a typed PDF badly, worse than a JPEG photo of a paper. Typed pages now go to the
  model as text (step 22.3.6, decision D5).
- Comment 16: qwen3.5's metadata gave a good automatic name ("Grade 8 - Final Term 1 - 2025 - Test 2").

- Step 22.3.6 GPU check (step22.3-plan §6, 2026-10-19), qwen3.5:4b: the typed-PDF text path broke the structure
  (options as sections, missing questions, rewrite stems empty) where image reading of the same test did well; the
  image path on photos looped on page 1 until the 8192-token cap; `answer_start` was never filled on either path (the
  prompt's only example uses "→"; papers print "=>" or nothing). The teacher kept the text path and shipped 0.4.0 to
  judge in real use.

- Step 22.4.7 GPU check (step22.4-plan §7, 2026-10-19), worked example in the page prompts: typed PDF test 4 improved
  (questions 35–40 kept their stems, `answer_start` filled) but questions 21, 22 and 29–34 became one-question sections
  and a stray section "A" appeared; photos (Test G) lost questions 5–12, 15–16 and the header on pages 1–2. The teacher
  shipped the example for typed files only (0.5.0).

## Content cut at page breaks (2026-10-22)

The teacher: a question is sometimes only its number and stem at the bottom of a page ("just 23."), and its multiple
choice options are on the next page. The orchestrator read the page-by-page `transcribe_page` / `structure_text_page`
responses in the teacher's `app.db` (read-only) and found the same cause behind the one-question sections and the stray
section of the 22.4.7 check:

| Test, path | End of page N | Start of page N+1 | Result |
|---|---|---|---|
| Test 4, typed (0.5.0) | p1 ends at question 14 (a dialogue stem, no options) | p2 starts with a section titled "A" whose text is an option | 14's options became the stray section "A" |
| Test 4, typed | p2's cloze passage runs to "(22) ____"; last question read is 20 | p3 starts with a section "Question 21." holding 21–22, no passage | the passage is cut in two |
| Test 4, typed (two runs) | the word-form heading is on p3 | p4 starts with sections "Question 29" … "Question 34" (or 31–34) | one section per question |
| A photo test | p2 ends at reading question 21 | p3 starts with a section "22." | the reading question is cut from its passage |
| A photo test | p2 has section VI | p3 starts with VI again | the section heading repeats |

What the merge does today: `_continues` (`sidecar/src/erh/domain/renumber.py:142`) joins a page's first section into the
previous page's last section only when it has no title, or the same title, kind and points. It does not join a section
with a new invented title ("A", "Question 21."), and it never joins a question split across pages (a stem on one page,
its options on the next) or a passage split across pages.

**Proposed fix** (the teacher asked for it, 2026-10-22; not planned or built yet):

1. **Typed PDFs: join, then cut at headings (code only).** A typed PDF's page texts are joined and cut like a Word
   file's text (`split_text_page`, `sidecar/src/erh/store/documents.py`: at section headings, else question starts,
   never inside a question; at most 6 000 characters). The printer's page breaks then no longer reach the model.
   Tested without the GPU; one GPU check on typed test 4 before it ships. Open point: a typed text page then no longer
   matches one PDF page image (pictures and born-digital matching use the PDF page).
2. **Photos: a continuation hint plus a merge rule.**
   - The hint: `transcribe_page` for page N+1 also gets, as text, the **last open unit** of page N as already read, not
     a number of words: the last section's title and instructions; the last question with what it lacks (e.g.
     "14: stem, no options"); an open passage's last paragraph from its last blank. About 100–300 tokens. The prompt
     says: if the page starts with the rest of that question or passage, return it as that question (same printed
     number) or under that section, marked as continued, not as a new section.
   - The merge rule: `merge_and_normalize` joins a continued section into the previous one, fills a question's missing
     options or stem from its continued copy, and joins a split passage.
   - Risk: a misread page N passes its mistake on as a hint; the picture still decides. One GPU check on a photo test
     with a cut question before it ships.

## Fewer question types (2026-10-22)

**Built in step 22.5.3 (2026-10-24), awaiting G1.** As proposed: `answer_form` (`choice` · `word` · `sentence` ·
`writing`) and `context` (`single` · `paragraph`, set by code from the stimulus) replace the type; stored tests keep
their old type in `old_type` for a revert; True/False is a `choice` with code-added options. Details: data-model v1.22
§2.3b, llm-design v4.42, PRD v8.6. The teacher signs D9 off after G1, or asks for a revert.

The teacher: the list of 11 question types (`QuestionType`, `sidecar/src/erh/domain/models.py:79`) is too long; a few
types cover everything, and whether a question relies on a shared passage should be its own attribute, which is more
structured and more deterministic for the later steps. `verb_form` goes.

Evidence (the teacher's `app.db`, read-only, 9 tests, 348 questions): only 6 types are used (mcq 168, word_form 48,
rewrite 36, gap_fill 32, true_false 38, short_answer 26); combine, ordering, matching and verb_form never appear. The
doubtful labels point at other errors: 14 true_false with no passage (the passage probably lost at a page break), 8
rewrite inside a passage, and short_answer for questions whose options went to the next page. `verb_form` is in the
schema but the page prompts never say when to use it, and it is graded exactly as `word_form`.

What the type is used for: mainly the grading rule (`sidecar/src/erh/domain/scoring.py:50`): exact match for choices,
exact match plus the spelling near-miss for one word, the AI judge for sentences; also the answer boxes, the validators,
sentence keys (`answer_start`), answer reading and the test text format.

**Proposed** (the teacher's direction, 2026-10-22; not planned or built yet). Two attributes replace the type:

1. **Answer form**, chosen by the model (three choices plus writing instead of eleven):

   | Form | The student gives | Graded by | Replaces |
   |---|---|---|---|
   | `choice` | a letter, or True/False | exact match | mcq, true_false, matching |
   | `word` | one word or a short phrase in a blank | exact match; a 1–2 letter difference is a spelling near-miss | word_form, verb_form, gap_fill |
   | `sentence` | a whole sentence | exact match, then the AI judge | rewrite, combine, ordering, short_answer |
   | `writing` | a paragraph or essay | not graded | writing |

2. **Context**, set by code, not by the model: `single` (the group has no `stimulus`) or `paragraph` (the question
   relies on a shared passage, dictionary entry or notice: the group has a `stimulus`). `writing` has no context.

The combinations: `choice` · single (pronunciation, grammar, signs), `choice` · paragraph (cloze with options, reading
multiple choice and True/False), `word` · single (word form), `word` · paragraph (cloze without options, sentences from
a dictionary entry), `sentence` · single (rewrite, combine, ordering), `sentence` · paragraph (reading questions answered
in a sentence), and `writing`.

Kept as fields: the cue word (`word`), `answer_start` (`sentence`), the options (`choice`; for True/False the code adds
the two options).

Changes in behaviour: `short_answer` is graded by the AI judge, so a right answer in the student's own words can be
correct (today it is word grading); an `ordering` answer that is not an exact match goes to the judge.

Why the short list is enough (the teacher, 2026-10-23): what a question **tests** is already held elsewhere, by the
section's `skill` and by the skill tags of grading (`prompts/taxonomy/sections.txt`: pronunciation, stress, word form,
reading, signs, rewriting …). The question type then only has to say the shape of the answer, which is what the code
needs.

Cost: a data-model and PRD change (saved tests need a migration; the grading table, answer reading, the test text
format, the eval fixtures and metrics change); one GPU check that the labels improve. The teacher signs it off before it
is planned.

## The half-page re-read on qwen3.5:4b (2026-10-22)

`retranscribe_tiles` (`sidecar/src/erh/graphs/extract.py:996`) re-reads a photo page that failed a check in
`merge_and_normalize` as two tiles, the top and bottom 55% of the page. It is off (`[extract] retranscribe_tiles =
false`) since M1 speed bundle 1: it measured worse (tuning CER 0.341 with tiles, 0.287 without) and took 19–27% of node
time (`docs/initial-plan/phases-testing/m1-report.md`). That was measured with **NuExtract**; the vision model is qwen3.5:4b since
0.4.0, and the tiles were never measured with it. The teacher wants it measured again with a GPU run.

How it works today (read in the code, 2026-10-22):
- Each tile is a separate `transcribe_page` call with the same prompt as a full page ("This is page N of M. Transcribe
  its printed text."). The `tile` input is not in the prompt, so the model is not told it sees half a page; it does not
  get the first reading, nor what failed the check.
- `_merge_tiles` (line 330) joins the bottom tile's first section into the top tile's last one only when the title
  matches or is empty, and drops a bottom-tile question whose printed number the top tile already has. So a question
  cut by the top tile's lower edge keeps the top tile's **cut** copy (e.g. a stem without its options) and drops the
  bottom tile's whole copy; and when the bottom tile starts with an invented title (as at page breaks), nothing is
  joined and the overlap questions appear twice.
- The tile reading replaces the page only if the page then has fewer check failures (`retranscribe_tiles_keep =
  "better"`).

**The teacher's idea for the re-read** (2026-10-22; not planned): give the re-read the context a person would use: the
first reading, a prompt that says what to fix, and the two halves of the page. The orchestrator's notes for planning:
the check failures already say what is wrong (e.g. "printed number 13 follows 4", "question 14 has no options"), so the
re-read can ask for **only those questions** and return only them, which keeps the output short and stops a full
re-read from adding new errors elsewhere on the page; the code then puts them in. Context: two halves are about the
pixels of one page, plus the first reading (or only its section titles and question numbers) and the output; checked
against `num_ctx` 16384 when planned.

**How the targeted re-read is applied** (2026-10-22). Today a re-read returns the whole page and, if it has fewer check
failures, replaces the whole first reading, so questions that were right can come back wrong. The local model has no
tools: it returns JSON only.

1. **First: a patch the code applies** (the orchestrator's design; the teacher: "let's go with yours first and see what
   happens, it is the more predictable way"). The model returns only the missing or broken pieces, each with its
   section title and printed number (e.g. section I, questions 5–12; section II, question 14's options); code puts
   them in place by section title and printed number. Rules to settle when planned: missing questions in a section the
   first reading never saw (the patch adds a section); missing questions in a passage (its group, and a stimulus that
   may itself be cut); a patch that disagrees with the first reading (the first reading wins unless the patch fills an
   empty field).
2. **Later, if the patch proves unreliable: a model with bounded edit tools** (the teacher's preference: "I don't
   trust the code to deterministically put in the undeterministic output of the fixing model"). The model gets the
   first reading and edit tools limited to it (e.g. insert questions after a printed number, set a question's options,
   replace a passage), runs them in a loop through Ollama tool calling, and the code only checks each edit stays inside
   the bounds. To be compared with the patch on the same GPU check.

**GPU check** (planned with the CLAUDE.md GPU-run rules): one run with `retranscribe_tiles = true` on Test G (pages 1–2
lose questions 5–12 and 15–16, so the numbering check fails) and one without, on qwen3.5:4b; compare the questions
found, the check failures and the time. If the targeted re-read is built, it is measured the same way.

## Answer reading: only the page's own questions (2026-10-22)

Today `read_answers_page` (`sidecar/src/erh/graphs/extract.py:1104`) sends **every** graded question with **every**
page, and the model must return one entry per question per page (null when nothing is there), because an answer can sit
in an answer box on another page. A 4-page, 40-question test asks for 160 entries, most of them null.

Timings in the teacher's `app.db` (read-only, 2026-10-22): `read_answers_page` 13 calls, 50.3 s a page on average
(longest 109 s), about 700 output tokens a page, one test 319 s for 3 pages; it is the largest call (8 275 tokens).
For comparison `read_key_pages` (the 6-page national keys with explanations) is cheap: 7.9 s a page, about 160 output
tokens, 41–55 s for a whole key, because it only lists label–answer pairs. `transcribe_page` on photos: 67.5 s a page.

**Proposed** (the teacher, 2026-10-22; not planned): each page is asked only for the questions printed on it (each
question has its `page_no`), strictly the printed number and the answer written next to it. No extra handling for an
answer box on another page: the teacher finds that rare and does not want the extra work ("rarely student write answer
in the different page of the number next to it"). Accepted limit: an answer written only on another page than its
question is not read (no answer). `resolve_answers` already takes each question's answer from the page that has one.
The key reading (`read_key_pages`) follows the same rule: strictly the number and the answer next to it; the prompt
(`prompts/base/read_key_pages.md`) gets a line that explanations on the key pages (the national keys have them) are
ignored.
The teacher's aim: the time saved here pays for the re-read of failing test pages (the half-page re-read section);
the GPU check measures both together.

## Key-photo keys shown as "double-checked" (2026-10-22)

`map_key` (`sidecar/src/erh/domain/keymap.py`) sets a key read from the key photo to `ai_verified` when its token
confidence is at least `key_photo` (0.7), and the Key tab shows `ai_verified` as "AI key · double-checked"
(`app/src/features/panels/KeysPanel.tsx:32`). No second model call checks it, and `verify_key` skips it because it only
checks `ai_unverified` keys (`sidecar/src/erh/domain/keys.py:70`). The teacher found keys that were confidently wrong.
The teacher keeps the "AI unsure" labels as they are (2026-10-22).

**Proposed** (the teacher, 2026-10-22; not planned): "double-checked" appears only when a second model call agreed; a
key read from the key photo without one is shown as from the key photo, with no claim of a check.

## Work (step 22.5)

- Measure answer-number errors on the eval fixtures, split into renumbering errors and reading errors.
- Show on the answers how the listening part was handled (left out, with its printed range).
- Tune or replace the extraction model; the GPU-run rules in CLAUDE.md apply.
- The text path for typed pages (better prompt, or the page image as well), `answer_start` examples without an arrow
  and with "=>", and a guard against repetition on long pages.
- Content cut at page breaks: the proposed fix above (typed PDFs first, then photos).
- Fewer question types: answer form × context, as proposed above.
- The half-page re-read: the GPU check on qwen3.5:4b, and the targeted re-read, as above.
- Answer reading asks each page only for its own questions, number and answer next to it, as above; the key
  reading ignores explanations.
- Key-photo keys: "AI key · double-checked" only after a real second check, as below.
- An extraction-check model role for the re-read or fix calls: planned with the grading-check role in
  `docs/initial-plan/plan-grading-quality.md` ("Separate model roles for checking").

## Tracker

| Step | Title | Status |
|---|---|---|
| 22.5.3 | Fewer question types (G1) | ✅ |
| 22.5.4 | The extraction-check role (with the grading-check role) | ✅ (used by the targeted re-read, 22.5.7) |
| 22.5.6 | Typed pages; typed-text prompt; reading student answers and keys; key-photo label; the listening part (G3) | ✅ |
| 22.5.7 | Photo page breaks; the half-page and targeted re-read; answer-number errors; vision model trial (G4) | ✅ built; G4 (teacher, 2026-10-26): GLM-OCR reads test photos by default (`photo_reader = "ocr"`), tiles and the targeted re-read stay off |
