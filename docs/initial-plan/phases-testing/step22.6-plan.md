# Step 22.6 plan: the teacher's sixth look (ETACH 0.6.0)

| | |
|---|---|
| Status | **Planning, 2026-10-30.** Sub-steps get their requirements in `docs/initial-plan/plan.md` when they start. |
| Build reviewed | Installer 0.6.0 as ETACH (step 22.5.8), with the teacher's data copied from 0.5.0 |
| Owner | The orchestrating session. |
| Next action | The teacher reads `docs/initial-plan/plan.md` step 22.6 and says when 22.6.1 starts. |

The teacher used ETACH 0.6.0 on two Grade 8 photo tests and wrote 4 comments, and asked for them to be fixed
before anything else (2026-10-30). The teacher chose a new step 22.6 for them, with step 22.5.9 (the logo and
installer 0.6.1) folded into it. Step 22 then runs on 0.6.1.

Same way of working as step 22.5: sub-steps on stacked branches `step/22.6.N-<slug>`, each change its own commit, a
fresh verifier before the GPU check, the teacher warned before each GPU run.

## 1. The teacher's comments (verbatim, 2026-10-30)

1. In a test by the student, but the student hasnt done it yet. The app doesn't generate the keys until i pressed grade student answers. Which is stupid since the paper didnt even have student mark but in student answers tab there's already info. See Grade 8 - Mid-term 2 - Nguyễn Hữu Thọ - 2025 - Test K for reference.
2. A lot of  the formatting error because the test inside the app include the answer box, which messed up the logic. My solution is to not put in answer box at all.
3. Some questions like 1,2,3,4 have duplication. I believe this is code error . see Grade 8 - Mid-term 2 - Nguyễn Hữu Thọ - 2025 - Test G8 . Grade 8 - Mid-term 2 - Nguyễn Hữu Thọ - 2025 - Test K is the one I have already fixed.
4. If the checker model is unsure about the key, let it be unsure. Let the model have to choice to be unsure, or if the thinking token is over a certain limit then the app automatically cut and flagged as unsure. The original error was in Grade 8 - Mid-term 2 - Nguyễn Hữu Thọ - 2025 - Test K, but i have fixed it so sadly no edvidence for you. The remaining ai unsure passages are legit tho.

Also: "check Grade 8 - Mid-term 2 - Nguyễn Hữu Thọ - 2025 - Test G8 what part takes long time."

Later, for after 1.0.0 (not in this step): "Which model is the one writting the report? Currently I feel the report is
kinda useless. Despite the student got 0.5/10 (because the student didnt write), the report suggest working on 32
first... which is quite advanced. In these kind of test, we should work on questions like 5,6 (easiest). This we will
work closely after we finished building the 1.0.0 cuz this is quite subjective and require my intuition from teaching
these students"

## 2. Findings (orchestrator, 2026-10-30)

Read from `D:\ETACH\data\app.db`, opened read-only, with the teacher's permission. Test K is T-0008 (extract run
`01M65DEK4FSYN08WGF7H0GGWER`, grade runs `01M65ECPQYZTPY1KFXMZS7HJCV` and `01M65EYYSZXK16QWZX2SFJFA85`); Test G8 is
T-0009 (extract run `01M65F38J772QKDTX6QGRE5YZK`). Both are photo tests.

1. **The reading step is right; the placing step is wrong.** GLM-OCR's text of G8's four pages has the lines in
   order, every question number 1–40, the options, answer boxes, the passage and the rewrite cues where they are on
   the paper. Every placement mistake was made by qwen3.5:4b in `structure_text_page`:
   - questions 1–4 (`1. A. question B. location C. nation D. animation`): the whole line as the stem and again as the
     options, so the app shows it twice (comment 3). The app's code stored and showed what the model returned; it
     made no copy of its own.
   - a second "Choose the correct answer:" became a section title;
   - the answer box at the top of page 2 became a section titled "I" holding 13–14;
   - 21's options at the top of page 3 became a section titled "A" holding 22;
   - the answer box `35. ... 36. ...` became two extra questions, so 37–40 were numbered 39–42 (comment 2);
   - 37's "Unless ..." went into the section instructions.
2. **Blank paper (comment 1).** Test K's paper had no student marks. The answer reader made up a pattern (1–14 and
   23–28: A, B, A, B, A, C, …), every one at low confidence (0–0.48) and flagged unsure: 30 `uncertain_answer` Review
   items, a score of 0.5/10 and a report about knowledge gaps. On G8, an empty answer is stored as the text `"null"`
   (questions 35–40), a code bug.
3. **The key is made at Grade (comment 1).** This is PRD D2 ("Made by the Grade button, unless one was given") and
   D16 (a run is extraction only; the Grade button runs the reasoning model). It is a recorded decision, not a
   direction lost on the way; the teacher's choice (§3 D4) changes it.
4. **The checker (comment 4).** On Test K, `verify_key` ran 1500 tokens on question 1 (cut off, so flagged unsure)
   and 1440 tokens on question 3 (about 33 s each, round in circles, then disagreed, so flagged unsure; the AI key C
   was wrong, the teacher set D). The checker cannot answer "unsure"; it must pick an answer. On a photo the
   underlining of a pronunciation question does not survive the OCR, so the checker cannot see the underlined part.
5. **G8's time (8 min 44 s of model calls).** qwen3.5:4b structuring the 4 pages: 4 min 00 s (41–70 s a page, 46%);
   reading student answers: 2 min 24 s (27%); GLM-OCR: 2 min 20 s (about 35 s a page even for page 4's 289 tokens,
   so mostly a fixed cost, perhaps the model swap between GLM-OCR and qwen on every page; not measured); the rest
   under 1 s. Test K's first grade took 6 min 10 s, of which the checker 3 min 21 s for 30 questions.
6. **The report (after 1.0.0).** The skill counts come from code; qwen3.5:4b writes the summary and the questions
   for the teacher. On Test K every blank answer counted as "does not know".

## 3. The teacher's decisions (2026-10-30)

| | Decision |
|---|---|
| D1 | Where: a new step 22.6 (first 22.5.9; then 22.6, "so we dont have to use a,b,c,d"). 22.5.9 is folded into 22.6, which ends in installer 0.6.1. |
| D2 | Answer boxes: two barriers. Code removes them from GLM-OCR's text, and qwen's structuring prompt says to leave them out. GLM-OCR's own `Text Recognition:` prompt stays (it is a trained task phrase, not free instructions). |
| D3 | Repeated options: one line in qwen's structuring prompt ("the fix here is not repeat"); prompt only, no code check. The prompt also gets a short example of the format. |
| D4 | The key: made automatically after every extraction, with or without a key photo. When extraction finishes the teacher can open the Test tab while the key is made; the Key tab stays blank until it is ready, no live update per key. Changes PRD D2 and D16. |
| D5 | Blank papers: code decides from the reading. At 22.6.2's start (from Test K's 2 of 40 and G8's 20 of 42 answers read with confidence): blank when fewer than 20% are read with confidence. Asked what a blank paper's thread becomes, the teacher first chose "a paper with no answers"; told that a paper with nothing read already becomes a test-only thread, the teacher chose the same for both: "Both: test-only. if a student do that test in the future, it gets its own thread and may be use the 'look like exisiting test' feature!" Then the full test suite showed that the recorded S1 paper (filled, but read almost all empty by its old model: 1 of 34 sure) is blank under the rule; offered a narrower rule (also needing unsure made-up values, or counting only read values), the teacher chose "20% as built". S1 replays as a blank test; its grade replay uses `[extract] blank_share = 0`. |
| D11 | Grade while the key is being made (asked at 22.6.4's start, 2026-10-30): the button waits, greyed out with "Making the key…", until the key is ready (not queued, not taking over). |
| D12 | Extract again and Delete thread while the key run goes (asked after 22.6.4 (a) found they were refused as "a run is active", 2026-10-30): they cancel it, discarding the `after_extract` run first, then go ahead. `erh run` / `erh eval` start no key run (orchestrator: the GPU comparison must not make or score AI keys). |
| D13 | The key run's notice (2026-10-30, after E2E showed a second "Failed" toast beside "Finished."): never a toast for the `after_extract` run; a failed key shows only on the Key tab (blank, with a note), and Grade makes the key as today. |
| D14 | Delete a test or a student while a key run goes on its threads (2026-10-30): they cancel it too, like Extract again and Delete thread (D12); other active runs still refuse. |
| D15 | The §4 gap, confirmed by the 22.6.6 verifier (a test edit during a paper's first grading leaves it scored against the old test, no re-grade; it existed before this round): the teacher chose "Fix now", in step 22.6 before the GPU check (2026-10-30). |
| D16 | The default photo way (22.6.6 (c), 2026-11-01, after §5 and the orchestrator's recommendation, asked for by the teacher): **2b code** (`photo_structure = "code"`); `qwen` and `ocr_format` stay as settings. Caveat recorded with it: two papers of one layout, with 2b's rules tuned on their OCR text; step 22's held-out papers are the real test. |
| D17 | The logo (22.6.7, 2026-11-02): the teacher designed it in Claude Design from the orchestrator's brief (the letter E from the wordmark, the theme's colours) and chose the **light** version, a deep navy tile `#181a5c` with a lime E, as the app icon. The dark version (pale grey tile) is kept in `app/src-tauri/icons/source/` as a spare. |
| D18 | The window frame (22.6.8, 2026-11-02, the teacher on the 0.6.1 build): Windows' dark theme made the title bar and frame dark, so the navy logo was hard to see. The frame is now light whatever the Windows theme (`.theme(Some(Theme::Light))` on the main window), as the app itself is light only (PRD §10.1). |
| D10 | Who builds (2026-10-30): the orchestrator built 22.6.1 and 22.6.2 itself; from 22.6.3 on, step agents build, as in earlier rounds. |
| D6 | The checker may answer unsure; its prompt says it has a token limit, so it says unsure instead of running out; the limit is 1000 output tokens; running out still counts as unsure. |
| D7 | A comparison of three ways on the photo path: (1) GLM-OCR then qwen3.5:4b with the new prompt; (2a) GLM-OCR prompted with the structure and an example, read by the app's test-text parser, no qwen; (2b) GLM-OCR's plain text, structured by code, no qwen. One GPU check runs all three on G8 and K; the teacher picks the default from the comparison. |
| D8 | Scope: D2, D3, D5 and D7 are for photo input only; D4 and D6 apply to every input. |
| D9 | The report's priorities: after 1.0.0, with the teacher. |

## 4. Open

- (for the 22.6.6 verifier, teacher 2026-10-30) A test-text save that changes points or deletes questions queues a
  re-grade only for attempts already graded (`domain/review.py`, `followup_run_ids`). An attempt whose FIRST grade
  run is going at that moment is not graded yet, so it may get no re-grade and be saved with the old points or
  questions. Not tested; the verifier writes a test for it and reports.

- How the GPU check's runs are started (the app's Extract again on copies, or `erh run` on the photos), decided when
  22.6.6 starts.

## 5. The three-way GPU check (22.6.6 (b), 2026-11-01)

Run by the teacher with the one script (R22.6.6.2) at 55580eb: Test G8 (4 photos) and Test K (3 photos), each
extracted with `photo_structure` `qwen` (way 1), `code` (2b) and `ocr_format` (2a), then the key made once per test
in the `qwen` folder. All 8 steps exit 0, 46 min in all. Read by the orchestrator from the scratch databases
(read-only; nothing from them committed beyond these counts and printed test text). Both papers have 40 questions;
Test K's paper is blank, G8's is written on.

| | Way 1 qwen | 2b code | 2a ocr_format |
|---|---|---|---|
| G8: questions found | 39 (21 twice; 13, 14 missing) | **40**, no gaps or repeats | 30 (2–7, 9–12 missing) |
| G8: sections | 13, incl. "Choose the correct answer:", "A", "B", "I. SIGNS" and "II. SIGNS" | 7: "1" (heading misread as a digit), II–VI, "REWRITE" | 1 ("IV") |
| G8: repeated options / answer-box questions | 0 / 0 | 0 / 0 | 0 / 0 |
| G8: pages flagged for Review | 3 | 2 | 4 |
| K: questions found | **40** | **40** | 34 (23–28 missing) |
| K: sections | 8, incl. "15. SIGNS", "IV. WORD FORM" and "V. WORD FORM" | 7: an untitled first section (no heading in the OCR text), II–VII ("IV" twice, as the OCR text prints it) | 4 |
| K: pages flagged | 1 | 2 | 1 |
| K: blank paper → test-only thread | yes | yes | yes |
| Extraction time G8 / K | 482 s / 388 s | **257 s / 229 s** | 262 s / 199 s |
| of which the structuring model | 216 s / 185 s | 0 | 0 |

2b's known misses on G8 (spot check): question 21's options start page 3, so they became a passage and 21 got
True/False options (the page is flagged); question 28's options read "A. so B. and D. but D. that" (an OCR misread,
flagged); the sign's text is in question 15's stem; the misread first heading leaves the section skill `mixed`.

The key after extraction (way 1's tests): G8 546 s (`verify_key` 351 s for 23 calls, 8 of them cut at the 1000-token
cap; `ai_key_fast` 101 s; tags 83 s): 7 verified, 11 unsure (checker: 7 disagreed, 1 answered `?`, 3 did not
finish), 20 not checked (B.7 checks only low-margin keys). K 399 s (`verify_key` 221 s for 25 calls, 1 cut): 6
verified, 18 unsure (14 disagreed, 4 answered `?`), 11 not checked.
