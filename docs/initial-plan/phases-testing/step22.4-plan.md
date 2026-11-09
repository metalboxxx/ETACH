# Step 22.4 plan: the teacher's fourth look (app 0.4.0)

| | |
|---|---|
| Status | **Planning, 2026-10-19.** Decisions in §3 are being asked; sub-steps get their checklist and requirements in `docs/initial-plan/plan.md` when they start. |
| Build reviewed | Installer 0.4.0 (step 22.3.8, main at 029cdf3) |
| Owner | The orchestrating session. |
| Next action | Build 22.4.8 (the teacher's answers), then the verifier, the installer 22.4.9 and the user's `E2E_SHELL --release`. |

Same way of working as steps 22.1–22.3: sub-steps built one after another on stacked branches; before the installer
step, any parked questions are asked and their answers built (teacher, 2026-10-15); then one fresh verifier for the
round and the user's `E2E_SHELL --release`.

## 1. The teacher's comments (verbatim, 2026-10-19)

1. Setting tab: Model manger should be in its own page, or a sub section inside settings. I mean putting it there makes settings too long. "Occasion" too.

2. In new threads page, same series as :"Đề dự đoán tuyển sinh vào 10" (the name of the series) . Not the whole name "Grade 9 - National Exam - Đề dự đoán tuyển sinh vào 10 - 2024 - Test 3"

3. In new thread menu, when click the input "search by name" or "a test of the same name series", a dropdown of suggestion should have already been dispalyed, not when you typed in then you displayed. THIS IS A COMPLAINT FROM LAST TIME which this new thread menu you missed. I see in test menu you have complete this.

{after extracting a test}
4. Format help when clicked and it dropped down, then the user should like automatically scroll to down to see the info right? Now when i click on format help, it did expand but i dont see anything immediately. I have to scroll down to actually see the content.

5. 35->40 qwen3.5 can really read the text, it just put the text in wrong place, formatting wrong. => Queue for refining llm output or more specific question type for this type of question . That said when priting to doc, the formatting is understandable for students to do the actual work (some places do miss the question heading tho like part V) . Regarding this, when transcribe the pdf docs for the llm, it does contains some artifacts about headings and such right? From my experience, the headings assignments are usually wrong; so I suggest turn all of them into normal text and rely on llm to put them into correct formatting. To be more consistent, leave an example for the llm to follow as instruction may not be enough. But this brings up the problem of llm context limit and gpu limitation. Converse, consult me more about this.

6. UI: Make "Test""Key""Student answers" look more like a button. Now they look like just texts. More visual clue.

7.  "Page 3: the app's check found a problem

mcq question 22 has options ['A.', 'B.', 'C.', 'D.'] mcq question 23 has options ['A.', 'B.', 'C.', 'D.'] mcq question 24 has options ['A.', 'B.', 'C.', 'D.'] mcq question 25 has options ['A.', 'B.', 'C.', 'D.'] mcq question 26 has options ['A.', 'B.', 'C.', 'D.'] mcq question 27 has options ['A.', 'B.', 'C.', 'D.'] mcq question 28 has options ['A.', 'B.', 'C.', 'D.']" These are flagged by the app as problem but they are fine. the questions don't have questions tied to them because the questions are tied to the fill in the paragraph question tye.

8. In photos extraction, the qwen did quite well, you can see for yourself at  "Grade 8 - Final Term 2 - Nguyễn Hữu Thọ - 2025 - Test G · Ngô Thị Mỹ Hòa", especially 35-40 compared to pdf one, which is strange.

9. Idk why it say "Grade again" while i havent grade yet. For simplicity, just put the "Grade student answers" button. Just change the text, dont do anything else.

10. Do "school" field similar to "student" and "occasion", where you have the dropdown to pick.

{After generating Key}
11. When you verify key, the grading tab on top should be smaller. Now it is kinda big, makes the picture smaller, subsequently making verifying the key harder.

12. When you verify key, only regrade/update student ability when you go to other tab. So it wont grade everytime you verify a single question; regrade once all you have done verifying all or a lot of. My sugeestion is inside the top tab,the button "stop" now is "Re-garde" and "stop"; and it also automatically regrade when you go to other tab

13. The report currently is quite a mess. The tags like VOC-TOPIC are used internally only. Dont present them in the report read by humans. And because explainations are created everytime I clicked "verify", the order is abysmall , 28>17>27.

14. Also investiage for me why the test is 3.25/13.75. It should only be 10.

## 2. What the orchestrator found (2026-10-19, reading the teacher's app data read-only)

- **Comment 7 is a check bug, not a cloze problem.** The model wrote the option letters as "A.", "B." (with a dot). The
  check (`domain/validators.py` `validate_mcq`) only accepts a bare "A"; the options themselves are complete (e.g.
  T-0005 q21: "A. even / B. in spite / C. though / D. however"). Fix: strip a trailing "." or ")" from option labels
  when the extraction is merged, and in the check.
- **Comment 9:** "Make the key" also grades the attempt (grading writes the AI keys, decided in 22.3), so the attempt is
  already "graded" when the button appears. Only the button text changes, as the teacher asked.
- **Comment 14 (T-0006, Test G):** the stored sections add up to 14.25 points, the grade shows 13.75. Causes:
  - Extraction errors in the points: section I (4 questions) took 2.5 printed points; question "22." became its own
    section with 1.5 points; the dictionary part's points (0.5) sit on an empty section and 2.5 points sit on the
    section titled with the dictionary headword ("professional adjective"), which holds questions 35–40.
  - Three instruction lines in Vietnamese ("Thí sinh chỉ viết mẫu tự…", "Chú ý: …") became empty sections.
  - Sections with no printed points get 0.25 per question (assumed); 12 + 5 + 6 such questions add 5.75.
  - App-side mismatch: the test's total counts an empty section's points (VI., 0.5), the grade counts only questions,
    hence 14.25 vs 13.75.
  - Nothing checks the total against the paper's total (10 on these papers).
- **Comment 8 (photos, Test G) vs comment 5 (typed PDF, T-0005 Test 4), questions 35–40:**
  - Photos: 35–36 have their sentences; 37–40 got their opening words (`answer_start`: "Unless", "They are", "We have
    to", "The man who"), which the step 22.3 GPU check never achieved; but the rewrite heading and sentences were put
    into the passage box ("stimulus") of the dictionary section, so 37–40 have no stem.
  - Typed PDF: 35–40 have no stems at all; every sentence sits in the passage box; no opening words.
  - The PDF text the model receives is plain text (`page.get_text()`), not marked-up headings; what it loses is the
    layout (bold, indentation, columns). Prompt for typed pages: about 1.3k tokens; context 16,384 tokens; answer cap
    8,192 tokens.

## 3. Work packages, in order (installer 0.5.0)

| Sub-step | Comments | What | Where |
|---|---|---|---|
| 22.4.1 Screen fixes | 4, 6, 9 | Format help scrolls its content into view when it opens; the workspace tabs (Test · Key · Student answers · Report) look like buttons (border, fill when selected, hover); the grade button always reads "Grade student answers" | UI |
| 22.4.2 Settings tabs, Schools | 1, 10 | Settings gets tabs: General · Models · Occasions · Schools (D1, D2); the Schools list (add, rename, reorder, delete when unused); the School field picks from it | UI + sidecar |
| 22.4.3 New-thread pickers | 2, 3 | "Same series as…" shows only the series name; both pickers in the new-thread screen show suggestions as soon as they are focused (as the Test menu does) | UI (+ sidecar if the series list needs a route) |
| 22.4.4 Checks and points | 7, 14 | Option labels "A." / "B)" are cleaned and the check accepts them (existing tests cleaned once); every graded question is worth 10 ÷ the number of graded questions, so tests and grades are out of 10 (D3; existing tests and grades recomputed) | Sidecar + UI |
| 22.4.5 Verifying keys | 11, 12 | The run bar is compact on the Key tab; verifying or editing a key no longer starts grading at once; the bar offers "Re-grade" and "Stop"; re-grading starts by itself on leaving the Key tab (details: decision D4) | Sidecar + UI |
| 22.4.6 Report | 13 | No internal skill codes in the report (what replaces them: decision D5); explanations in question order, on screen and in the Word file | UI (+ sidecar if names come from the taxonomy) |
| 22.4.7 Worked example | 5, 8 | A worked example in the page prompts (D6); the teacher's GPU check decides whether it ships | Sidecar prompts + eval |
| 22.4.8 Installer 0.5.0 | | As 22.3.8 | Version, build, release notes |

**Model work (comments 5, 8):** the worked example (D6) is built in this round as 22.4.7; other extraction-quality work
stays in `docs/initial-plan/plan-extraction-quality.md`. With D3, misplaced printed points no longer affect the score.

## 4. Decisions for the teacher

- **D1 (comment 1):** Settings layout: tabs inside Settings, own pages in the sidebar, or folding sections.
- **D2 (comment 10):** where the school list comes from: schools already used, or an editable list in Settings like
  Occasions.
- **D3 (comment 14):** when the test total is not 10: flag it for the teacher to fix the points, scale the score to 10,
  or both.
- **D4 (comment 12):** what starts the automatic re-grade, and whether it also covers key edits.
- **D5 (comment 13):** what the report shows instead of the codes: English skill names, Vietnamese skill names, or
  nothing.
- **D6 (comment 5):** the approach for the model work (plain text, a worked example, the page image with the text).

## 5. Decisions taken (teacher, 2026-10-19)

- **D1:** Settings gets **tabs** (e.g. General · Models · Occasions).
- **D2:** the School dropdown lists an **editable list in Settings**, a Schools tab like Occasions (add, rename,
  reorder, delete when unused).
- **D3:** the score is **always out of 10**: every graded question is worth 10 ÷ the number of graded questions
  (usually 0.25; 0.2 on the grade 12 national test with 50 questions). Printed part points are no longer used for the
  score. Teacher: "each question point ammounts to 10/ammount of question, though usually its 0.25 . From my teaching
  experience, only grade 12 national test have 0.2". This changes the points rule (PRD, data-model: a major change).
- **D4:** the automatic re-grade starts on **leaving the Key tab** (to another tab or another thread) when a key was
  verified or edited; otherwise it waits for the next time the thread is opened. "Re-grade" and "Stop" sit in the top
  bar.
- **D5:** the report shows **English skill names** from the skill list (e.g. "Vocabulary — topic words"), never codes.
- **D6 (model work, comment 5):** **A, a worked example** in the extraction prompts: a made-up mini page with the tricky
  cases (dictionary entry with gaps, rewrites with printed openings, a Vietnamese instruction line that is not a part)
  and its correct output. Other options considered: page image with the text, clean-up rules in code, two passes.
  **In this round**, as 22.4.7 before the installer (other options: its own round after 0.5.0; after step 22).

- **After the GPU check (§7), teacher, 2026-10-19:** the worked example ships for **typed files only** (the
  `structure_text_page` prompt). The photo prompt (`transcribe_page`) goes back to its 0.4.0 wording, without the
  example and the three rules, so photos read as in 0.4.0. (Other options: both paths; neither; tune the photo prompt
  and run another GPU check first.)

- **§6 questions answered by the teacher (2026-10-19), before the installer:** (1) Format help keeps its button in
  view; (2) "Keep logs" stays on the Models tab ("this is log file of the model"); (3) the Existing test and Same series
  as boxes line up; (4) typed heading points are ignored, no note; (5) headings show both the section total and the
  per-question value ("[2.5 points, 0.25 each]"); (6) leaving a thread whose keys changed also starts the re-grade,
  from any tab; (7) the top bar is compact on every workspace tab. Answers 1, 3, 5, 6, 7 are built as step 22.4.8; the
  installer becomes 22.4.9.
- After the 22.4.8 build (teacher, 2026-10-19): the "Keys changed" hint shows as a tooltip (other option: hidden).
  Writing sections keep "[0 points, not graded]" (orchestrator).

## 6. Carried forward (ask before the installer)

- From the 22.4.1 builder: opening Format help lines the help's top up with the panel's top (`block: "nearest"`; the
  help is taller than the panel at 1280×720), so the Format help button itself scrolls just out of view. Ask the
  teacher whether that is fine or the button should stay in view.
- From the 22.4.2 builder: "Keep logs" sits on the Models tab, because it shares one Save button with the role
  models. Ask whether it should move to General.
- From the 22.4.3 builder: the "Existing test" and "Same series as" boxes start at different places because their
  labels differ in width. Ask whether to line them up.
- Orchestrator (22.4.4, D3): heading points typed in the test text are ignored, since points are computed; existing
  grades are re-scored at first start without a model call.
- From the 22.4.4 builder: section headings show computed points to 2 decimals; with 13 questions split 5/4/4 they
  read 3.85 + 3.08 + 3.08 = 10.01 while the total stays 10. Ask: keep, show the per-question value ("[0.77 points
  each]"), or leave headings without points.
- From the 22.4.5 builder: (a) when the app reopens on a thread whose keys changed and the teacher leaves without
  visiting the Key tab, nothing re-grades until Re-grade is pressed or the Key tab is left; ask: keep, or also re-grade
  on any thread switch while pending. (b) The compact top bar is used on the Key tab only; ask: Key tab only, or
  everywhere.

## 7. Teacher's GPU check for step 22.4.7 (R22.4.7.4)

**Warning:** this uses the laptop's GPU for about 10–20 minutes. Do not use the laptop for other work while it runs.

Run on branch `step/22.4.7-worked-example` (all 22.4 code, verified), qwen3.5:4b for both roles (the default of an
empty data folder), into the throw-away folder `D:\ERH-gpucheck`, so the teacher's data is not touched. The files are
the originals kept in the app folder: national exam test 4 (typed PDF, 4 pages; T-0005) and Test G (4 photos, no
rotation; T-0006).

```
cd /d/Projects/Exam_Revision_Helper/sidecar && uv run erh run --data D:/ERH-gpucheck --spawn-ollama --pages "D:/ExamRevisionHelper/data/files/74/74995cf991339965edb2c55bd0168a175ca5eb500b6d5a5d800daaf3a4df6c88.pdf"
cd /d/Projects/Exam_Revision_Helper/sidecar && uv run erh run --data D:/ERH-gpucheck --spawn-ollama --pages "D:/ExamRevisionHelper/data/files/aa/aa0ca7c0cc9fe4db1b119f387623950a6f2237cddd685352af0151b40bc8ae1c.jpg" "D:/ExamRevisionHelper/data/files/c1/c11d21bbf85e887e4ecfef4f7b5d46d420a9629b4d2955e903504514b2132cc4.jpg" "D:/ExamRevisionHelper/data/files/6e/6e431bd04de05ce909ff16a2d441d5d4cb0b4a5c4ece94a28520940268554de8.jpg" "D:/ExamRevisionHelper/data/files/a3/a39fe6e7db42f734ddf51b1b2056058b7eb89030e43904f96b292e85fbc38d22.jpg"
```

The orchestrator then reads the two new tests in `D:\ERH-gpucheck` (read-only), compares them with T-0005 and T-0006
from 0.4.0, records the result below, and deletes `D:\ERH-gpucheck`.

### Result (2026-10-19, run by the teacher; read by the orchestrator)

**Accepted by teacher (2026-10-19):** the worked example ships for typed files (better than 0.4.0 on 35–40: sentences,
the rewrite part and opening words); the photo prompt stays as in 0.4.0 because pages 1–2 got worse. The one-question
sections (21, 22, 29–34) and the stray section "A" on the typed test remain known limits for the extraction-quality
plan.

Compared with what 0.4.0 made of the same files (T-0005, T-0006; step22.4-plan §2).

| | Typed PDF (test 4), text path | Photos (Test G), image path |
|---|---|---|
| 35–40 have their own sentences as stems | **Yes** (0.4.0: none) | **Yes** (0.4.0: 37–40 had none) |
| The rewrite part is its own section | **Yes**, VIII (0.4.0: yes, but empty) | **No**: still inside the dictionary part, whose entry went into the instructions |
| Opening words (`answer_start`) filled | **Yes**, all four (0.4.0: none) | Yes, all four (as 0.4.0) |
| No instruction line became a section | Mostly; but 21, 22 and each of 29–34 became one-question sections, and 13–14 sit under a stray section "A" (as 0.4.0) | **No**: two "Thí sinh chỉ ghi …" answer-box lines became empty sections |
| Other | gap lines repeated in the passage box (harmless) | **Worse than 0.4.0 on pages 1–2**: questions 5–12 and 15–16 missing, 17–22 put under the dictionary heading, the header lost ("Untitled test"); short outputs (583 and 495 tokens) |
| No page looped to the token cap | Yes (about 50 s a page) | Yes |
| Time | 215 s | 361 s (incl. reading the answers) |
| Result | **Better** than 0.4.0 | **Mixed**: 35–40 better, pages 1–2 much worse |

The throw-away folder `D:\ERH-gpucheck` is to be deleted by the teacher (the orchestrator's delete was blocked by a
safety check).
