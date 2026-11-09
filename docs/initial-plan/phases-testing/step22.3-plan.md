# Step 22.3 plan: the teacher's third look (app 0.3.0)

| | |
|---|---|
| Status | **Started 2026-10-17.** The packages are plan steps 22.3.1–22.3.7 in `docs/initial-plan/plan.md` (v2.24); the tracker there is the current status. |
| Build reviewed | Installer 0.3.0 (step 22.2.7, main at 6f9b777) |
| Owner | The orchestrating session. |
| Next action | Step 22.3.8 (installer 0.4.0), then the user's `E2E_SHELL --release`; the teacher signs off R22.3.6.4. |

Same way of working as steps 22.1 and 22.2: sub-steps built one after another on stacked branches; **before the
installer step, the questions parked in §5 are asked and their code-changing answers built** (teacher, 2026-10-15);
then one fresh verifier for the round and the user's `E2E_SHELL --release`.

## 1. The teacher's comments (verbatim, 2026-10-16)

1. There is no delete for students? I have deleted chats and tests but students are still there. Think more about this and asks me questions later, it really involves database.
2. In photo check page, Little instruction below (I think below exisiting answers, how about you) to tell teachers that marked key pages with key
3. In photo check page, double click a picture to full view it. Or an expand icon on the outer left.
4. In photo check page, the rotate icon should be change. Now it looks like it is to reload the image? ( Solution I think the circle only goes 180, not 360 like now? what ya think)

{After image pdf ẽtraction}
5. UI: The line number next to the text makes it seems like there are 2 layers. At first I thought there another page under "C:\Users\HOME\Pictures\Screenshots\Screenshot 2026-10-16 095119.png"

6. If the file inserted is pdf or doc, then model used should be reasoning model to fit our database structure. The image model transcribe the pdf very badly. This can be acceptable for images but deterministic files like pdf should be better. Funnily, the jpeg immage extraction did better in "Test". "Key" we dont mention because the test is already wrong so the key is of course wrong.

7. remove the line "Edit the test like a document. A section starts with a heading that ends in its points, such as “VII. [2 points]”; a question starts with its number, such as “12.”; options start with “A.”. ??? marks words that could not be read." . Not neccessary. the format help should already be self explanatory enough. Thought the button "Format help" have the down icon, and when click drop down animation like you usually see in modern website.

8. Clicking on occasion, the list of options like nation exams, final term should be already present. Currently, i click on it, it doesnt show anything. When I type "na", only then the suggessted nation exam appear.

9. When test name is updated and I see it updated visually in test page, i dont see the name updated on the left tab. Closing the app and open again did rename tho.

10. Regarding generating key for sentences, lets add multiples correct sentences for a sentence: the full "My brother used to stay up late playing mobile games.", the full without "." : "My brother used to stay up late playing mobile games" , the wihtout the "đề" : "used to stay up late playing mobile games.", the wihtout the "đề" and ".": "used to stay up late playing mobile games"

{After key extraction}

11. Why some keys are double-checked, some are not. What the logic behind this?

12. When I want to test using qwen3.5 for image extraction, i have to retype the whole thing. Do a dropdown of currently downloaded and select, also text . Like the refixed "occasion" above. The idea is that we easily miss spelt a letter and it will backfire the whole.

12.5. so redo the download model? currently hitting download model just downloads qwen3.5. Lets make like a model inventory manager. and for this scoped just get ollama. << This will be a big install?>>

{after qwen3.5 test extraction pdf}
13. qwen 3.5 did a much a better job on image extraction. if you want to investiagte, national test 3 is nullextract, national test 5 is qwen.

14. lets remove this page "C:\Users\HOME\Pictures\Screenshots\Screenshot 2026-10-16 163336.png". feels like redundant . when clicked on the test on the left, the app goes straight to the "test" page currently. On the test page on top same line as Test and Key button now but on the right (top right), there will be buttons to "grade student answer"{I feel grade and "re-gen test again" button, which are the only two things i feel missing of the Test page from the screenshoted page.

15. There is way to copy config. For example, the 2 national exams are from the same series (there might be many series cover the national exam by different teachers), but when creating the 2 tests on the app i have to retype the whole thing: year, grade, series,... Things got very bothersome whone creating 12 tests from the same series. consult me on how to tackle this. My current idea is a way to copy the config, and let the teacher change test number manually.

{after qwen3.5 test extraction photo}
16. "Grade 8 - Final Term 1 - 2025 - Test 2" is a result qwen3.5 and seems like it is good.

17. Now i want to delete the null extract model but the download model button currently is useless. (back to 12.5)

18. i dont see how i tag this test to a student. She didnt write on the paper but i know it, so the teacher want to update but i dont see how

19.  "Grade 8 - Final Term 1 - 2025 - Test 2" i put wrong order because i cant double click to see the big picture => wrong student answer, test. (Back to previous point 3.)

## 2. Work packages, in order

| Step | Package | Comments |
|---|---|---|
| 22.3.1 | Photo check and small screen fixes: full view of a photo (double-click and an expand icon), a hint to mark key pages, a rotate icon that does not read as reload, line numbers that do not look like a second page, Format help with a chevron and a slide-down (the intro line removed), the occasion list on click, the sidebar title after a rename, step 22.2's F7 | 2, 3, 4, 5, 7, 8, 9, 19 |
| 22.3.2 | Straight to work: a thread opens its workspace; Grade student answers and Extract again at the top right of the Test page; the card page goes; a student can be set on any thread | 14, 18 |
| 22.3.3 | Delete a student; copy test details for a series | 1, 15 |
| 22.3.4 | Sentence keys accept the four forms | 10 |
| 22.3.5 | Models: pick from installed models; a model manager (Ollama: list, download, delete); qwen3.5:4b the default image model | 12, 12.5, 13, 17 |
| 22.3.6 | Typed PDF/DOCX pages: the exact text goes to the model as text, no image reading | 6 |
| 22.3.7 | §5 questions asked and built, then installer 0.4.0, the verifier, `E2E_SHELL` | — |

Comment 13's evidence (national test 3 read by NuExtract, test 5 by qwen3.5) goes to `docs/initial-plan/plan-extraction-quality.md`
for the model work after step 22. Comment 16 is a confirmation (qwen3.5's automatic name was good).

**Answers given in chat (2026-10-17):**
- 11: a key gets the second AI check only when the AI wrote it AND (the first answer's confidence was low OR it is a
  pronunciation/stress question OR the student's answer differs from it) — llm-design §4 `verify_gate`. A confident
  key the student agreed with is not checked again.
- 12.5: the installer stays about 43 MB; models are never in it, they download into `<app>\data\models` on demand.
- 4: a short arc with an arrow head and a "Rotate 90°" tooltip, so it reads as a quarter turn, not reload.

## 3. Decisions for the teacher

None open.

## 4. Decisions taken (teacher, 2026-10-17)

- D1 (comment 1): deleting a student deletes them **with their threads**, for good, like deleting a test; the dialog
  lists the threads; tests stay in the bank. (Other options: unlink threads; refuse while they have threads; ask each
  time.)
- D2 (comment 14): a thread opens straight into its workspace; the card page goes. Run progress shows in the sidebar's
  running indicator and as a bar at the top of the workspace; a new thread keeps its drop/photo-check start screen until
  extraction finishes, then opens the workspace. (Other option: keep the card page only for new or running threads.)
- D3 (comment 15): both ways. **"Copy details from…"** on a test's details copies occasion, term, school, series and
  year from another test — not the grade, not the test number. **At extraction**, next to the existing "same test as…"
  pick, a **"same series as…"** pick starts the new test with those details; the AI fills the rest. (Other options:
  only one of the two; a Series list.)
- D4 (comment 13): **qwen3.5:4b becomes the default image model** (PRD D7 changes); NuExtract is no longer needed and
  can be deleted in the model manager. (Other options: keep NuExtract the default; decide after a test run.)
- D5 (comment 6): **typed pages, text first**: a born-digital PDF/DOCX page's exact text goes to the model as text, with
  no image reading; pictures in the file are kept as pictures. (Other options: text plus the page image; not now.)

- D6 (comment 10, 2026-10-17): extraction does not keep a rewrite's printed opening words ("My brother …") today, so most sentence keys would get only two forms. The teacher chose to change the extraction prompt **in this round** (with step 22.3.6) and check it with one GPU run on a test with rewrites before the installer. (Other options: later with the extraction work; a "given words" box the teacher fills.) Already-graded attempts are not re-graded when keys gain forms; the next grade run uses them.
- §5 questions answered by the teacher (2026-10-18), before the installer: (1) a typed page's picture placeholder
  pointing at the whole page is fine; (2) the model manager suggests only `qwen3.5:4b` and NuExtract; (3) "same series
  as…" stays hidden while an existing test is picked; (4) "Copy details" stays blocked when nothing would change;
  (5) **editing occasions comes into this round** as step 22.3.7; the installer becomes 22.3.8.
- Order to the installer (orchestrator, following CLAUDE.md's GPU rule): 22.3.7 → one verifier for 22.3.1–22.3.7 →
  the teacher's GPU check (R22.3.6.4, §6) → 22.3.8 installer 0.4.0 → the user's `E2E_SHELL --release`.
- After the GPU check failed (§6), the teacher chose (2026-10-19): **keep the text path and the prompts as built, ship
  0.4.0**, and judge typed files in real use, changing models in the model manager when needed; no prompt tuning now.
  The throw-away check folder was deleted. (Other options: send typed pages back to image reading and rely on a typed
  "Start:" line; tune the prompts now with more GPU rounds.) R22.3.6.4 failed; whether to accept it is the teacher's
  sign-off (plan §1.4), not written by the orchestrator.

## 5. Carried forward

- Step 22.3.6, for the teacher: on a typed page the model cannot see pictures, so a question that needs a picture gets a placeholder pointing at the whole page image — keep, or find the pictures inside the PDF (more work)?
- Step 22.3.5, for the teacher: the model manager suggests only `qwen3.5:4b` and NuExtract to download (any tag can be typed) — suggest more? Release notes must say `qwen3.5:4b` reads images through the chat adapter with the generic prompt profile.
- Step 22.3.4, for the verifier: the eval counts a key as a sentence when it has ≥ 4 words (the metrics have no question type); the key-photo forms test checks the call, not `save_extract` itself.
- Step 22.3.3 builder, for the teacher: while an existing test is picked at the photo check, "same series as…" is hidden — keep, or show it disabled with a reason?; "Copy details" is disabled ("Nothing to change") when the values already match — keep, or allow saving anyway (which marks the fields as teacher-set)?
- Step 22.3.2 builder, for the verifier: R22.3.2.2's "disabled only when no student answers were read" cannot happen in the UI (such a thread shows "Make the key"); Grade is disabled only while a run goes.

- From step 22.2 (step22.2-plan §5): F7 (focus after "Use automatic name" and after a detail chip edit) — in 22.3.1;
  a way to add and rename occasions (teacher, 2026-10-15) — not yet scheduled.

## 6. Teacher's GPU check for step 22.3.6 (R22.3.6.4)

Written by the 22.3.6 builder for the orchestrator to review. It is the teacher's run, before installer 0.4.0.

**Warning:** this run uses the laptop's GPU for some minutes (about 5–15, depending on the page
count). Do not use the laptop for other work while it runs.

**Files** (real papers, kept out of git):
1. One **typed national exam PDF**: a born-digital file (made on a computer, not scanned), with
   several sections, options, a reading passage and, if possible, a picture.
2. One **photographed test with rewrites**: photos of a paper that has rewrite or combine questions
   with printed opening words on the answer line ("→ My brother ……").

**Models:** in Settings, both the image model and the reasoning model are `qwen3.5:4b`.

**Steps** (the app built from branch `step/22.3.6-typed-files` or later, with the data folder
`D:\ExamRevisionHelper`):
1. Start a new thread, drop file 1, check the pages, start the extraction. Note the time shown
   when it starts and when it ends (or the run's time in its details).
2. Start another new thread with the photos of file 2 and do the same.

The command line does the same (with the app closed): in `sidecar/`, run
`uv run erh run --data D:\ExamRevisionHelper --spawn-ollama --pages "<file 1>"`, then the same
command with `--pages "<photo 1>" "<photo 2>" …` for file 2; it prints the time at the end.

**What to compare and record here:**

| | File 1: typed PDF | File 2: photos with rewrites |
|---|---|---|
| Structure correct? (sections, numbers, options, passage in one block, nothing invented) | | |
| Pictures shown as placeholders where the paper has them? | | – |
| No student answers read from the typed file (a blank test)? | | – |
| Opening words kept? (the Test page shows `   Start: …` under each rewrite/combine question that prints them) | – | |
| Key forms: after Make the key / Grade, the Key tab shows four forms for a sentence key with an opening | – | |
| Time for the extraction | | |
| Result (pass / problems) | | |

### Result of the GPU check (2026-10-19, run by the teacher; read by the orchestrator)

Run with `erh run --spawn-ollama` on branch `step/22.3.7-occasions` (all 22.3 code), qwen3.5:4b for both roles,
into a throw-away data folder (deleted afterwards). Files: national exam test 5 (typed PDF, 4 pages) and the
Grade 8 Final Term 1 Test 2 photos (5 pages, rewrites with printed openings "=> They have", "=> Anna used").

| | File 1: typed PDF (text path) | File 2: photos (image path) |
|---|---|---|
| Path used | 4 `structure_text_page` calls, reasoning role ✓ | 10 vision calls (pages + tiles) ✓ |
| Structure correct? | **No.** Two answer options ("C. Lack of…", "D. Collision…") became sections; questions 13–14 missing; two sections titled "III"; rewrite questions 37–40 saved **without their sentences** (stem empty) | **No.** Page 1 was lost: the model repeated itself until the 8192-token cap (output_capped), so questions 1–9 and the header are missing ("Untitled test"); sections out of order |
| Pictures as placeholders | 3 groups got the whole-page placeholder | – |
| No student answers from the typed file | ✓ (0 answers, a blank test) | – (30 answers read, 7 unsure) |
| Opening words kept (`answer_start`) | **No**: none of "Because of", "The new perfumes are", "Customers don't", "They are" (the text has no arrow; the prompt's example uses "→") | **No**: none of "They have", "Anna used", though printed after "=>" |
| Time | 198 s | 638 s |
| Result | **Fail** | **Fail** |

Notes: the teacher's earlier test 5 read through the image path was much better (comment 13), so for this PDF the
text-only path is worse than image reading. D6's prompt line is not followed by qwen3.5:4b on either path.

