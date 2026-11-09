# Step 22.2 plan: the teacher's second look (app 0.2.0)

| | |
|---|---|
| Status | **Started 2026-10-14.** The packages are plan steps 22.2.1–22.2.6 in `docs/initial-plan/plan.md` (v2.17); the tracker there is the current status. |
| Build reviewed | Installer 0.2.0 (step 22.1.7, main at 4bdb53c) |
| Owner | The orchestrating session. |
| Next action | Step 22.2.7 (the teacher's answers, F5, 0.3.0 rebuilt), then its verifier and the user's `E2E_SHELL --release`. |

Same way of working as step 22.1 (step22.1-plan §4): the sub-steps are built one after another, each branch starting from
the previous one; one fresh verifier checks them all at the end; the teacher tests and merges once. The 20 answers to the
step 22.1 questions (step22.1-plan §4) are part of this round.

## 1. The teacher's comments (verbatim, 2026-10-14)

1. beside dragging and dropping into the screen, the new thread screen should also have a normal insert file button.

2. There is no apparent way to delete tests or thread. Currently we only have rename

3. When I uninstall with app data unisstall checked and reinstall, the old tests are still there? HOw? When unistalling should have option to delete user data.

{After extract test}

4. I see "Ngô Thị Mỹ Hòa" has class 8tc11 which is correct. but idk how to add, modify that to 'To Dang Khoa" . Thinking of this, we should have tab dedicated to students, beside chats tests.

5. After cliking on options beside photos, I go to test page. I should able to change the tabs within that menu; not having to go back "back to thread" button and then choose again. The same goes for "answers", "key"

6. The closing the print menu problem still exist from last run. I still accidentally close the app by clicking the "x" button on the top right

7. "Answers" should be named to "Student Answers". Apply all, i got confused so much with "correct answer" and "student answer". I just automatically assocciate "correct answer" with"key"

8. The NullExtract is pretty bad. Note this for after plan 22 of step further refinement. Assessing the answers is hard because idk if the answers include the listening part or not; the answers are also in the wrong number (i dont know if this wrong number is due to subtraction of the listening part or the image model is wrong)

9. What is "variant" attribute of the test do? "Test" attribute should be named to "Test number"? And the test name we use to find duplication is "Test Name"? The blob of attributes on top Test page make it hazy: Important attribute go first, like how we organise the "Test Name", only "Test Name" have duplication value of other attribute because it is created from them. I usually named the test on my computer "Grade 8 - Cuối Kỳ I - Nguyễn Hữu Thọ - 2025 - Test 7" , "Tuyển Sinh 9 - TuoiHocTroLuyenThi{Name of the series} - Test 23": take this as a reference for how certain attribute are important according to me. Might have to rely on image extraction but the way attribute is organised and displayed can be better.

{After grading}

10. Double clicking a row allows teacher to edit it, not just the edit button. But keep the edit button for clarity.

11. Only write "Ai unsure key" . Dont write two times like "ai unsure" "ai unsure key". It clogs the page. The same goes for "student answer" page where it is just a "?", write "ai unsure student answer".  Here i see "AI, checked", "Ai, not checked". What are those? Check what?

12. As mentioned in 8. and in the questionaires you asked, the number should be consistent with the one on the paper. For easier time for time of verifying student answers and key.

13. I see that when i change the "student answer", something uses my gpu, and the thing write "Finding weak points" ,better naming to "Update student ability to newest info".

14. In Key page, the options like "Dismiss" "Edit",... and info are on the right. Do the same for Student Answer page, where the options are on the left which clogged the acutal answer content. Further , even if it is unsure , the button "keep the key" and "verify" should be the same. The text that signifies unsure is already there before.

## 2. Work packages, in order

| Step | Package | Comments | step22.1-plan §4 answers |
|---|---|---|---|
| 22.2.1 | Words on screen: "Student answers", unsure labels, key source, stage names, progress wording | 7, 11, 13 | 1, 3–7, 9 |
| 22.2.2 | Moving around and safety: workspace tabs, close guard, Choose files, double-click to edit, Student answers layout, Verify on unsure keys, "Use automatic name", print title line, the 22.1 verifier's minor findings | 1, 5, 6, 10, 14 | 15, 16 |
| 22.2.3 | Delete threads and tests; a Students tab; change a thread's student | 2, 4 | — |
| 22.2.4 | Test page: printed question numbers, added questions and typed `???`, Format help; the test details reorganised and the automatic Test name | 9, 12 | 12, 13 |
| 22.2.5 | Key photos kept; version built in; uninstall "Delete app data" deletes the app's data | 3 | 10, 18 |
| 22.2.6 | Installer 0.3.0 | — | — |

Comment 8 (NuExtract quality, listening questions in the answer sheet, wrong answer numbers) is extraction tuning after
step 22: it is recorded in `docs/initial-plan/plan-extraction-quality.md` and not built here. Comment 12's numbering is built in
22.2.4 as far as the app renumbers questions itself.

Comment 9 asked whether the Test name is what finds duplicates: no, duplicates are found by comparing the questions
(`compare_bank`: numbers and stem similarity); the name is for the teacher. "Variant" is the paper's version letter
(đề A / đề B, "K" on some papers). PRD D10 v6.0 follows answer 12: every number the teacher sees is the printed one.

Comment 11 asked what "AI, checked" means: the key answer was written by the AI and a second AI pass checked it against
the question ("not checked": no second pass yet). A key the teacher typed or verified shows as the teacher's.

## 3. Decisions for the teacher

None open.

## 4. Decisions taken (teacher, 2026-10-14)

- A: the key source reads "AI key · double-checked" / "AI key · not double-checked".
- B1: deleting a thread removes it **for good** after a confirm dialog: its attempts, the student-answer photos, answers
  and reports. The test stays in the bank. (Other options were a recycle bin, or an Undo for a few seconds.) Backups
  (step 20) are the safety net.
- B2: deleting a test deletes its threads with it, for good; the confirm dialog lists the threads. (The other option was
  to refuse while threads use the test.)
- C: the automatic Test name is Grade – Occasion + term – School or series – Year – Test number, in English, empty parts
  left out: "Grade 8 - Final Term 1 - Nguyễn Hữu Thọ - 2025 - Test 7". (The other option was the occasion in Vietnamese.)
- Update safety (verifier F2): from 0.3.0 on, "Uninstall before installing" during an update shows the old uninstaller's "Delete app data" box; the teacher chose to keep it as built, with the release notes' warning to leave it unticked when updating (2026-10-14). The other options were running the old uninstaller in update mode (no box) or a red warning line on the box.
- §5 questions answered by the teacher (2026-10-15), before the 0.3.0 installer is handed over:
  1. Progress text keeps the stage name ("Reading the test · page 3 of 4").
  2. An uncertain grade shows "AI unsure grade" instead of "?" (Student answers and report).
  3. The ten occasion names stay; a way to add and rename occasions comes later (not in 22.2).
  4. The Test name says "Unit Test" and "15-minute Test" ("Grade 7 - Unit Test - 2025").
  5. An unknown occasion is left out of the Test name.
  6. The Test name is editable; an edited name stays (and is no longer remade) until "Use automatic name".
  7. Units and Tags are editable under More details (comma-separated).
  8. Key photos of a picked test: saved only if it has none (as built).
  9. The uninstaller box reads "Delete all app data (tests, students, backups)".
  10. A test with no name parts is called "Untitled test" (asked during 22.2.7).
  These and the re-verifier's F5 are step 22.2.7, which also rebuilds 0.3.0 (plan v2.23).
- The teacher noted that the parked questions should have been asked before the installer was built and handed over;
  from now on a round's installer step comes after its §5 questions (teacher, 2026-10-15).

## 5. Carried forward

- Step 22.2.1 builder, for the teacher: progress text keeps the stage name ("Reading the test · page 3 of 4") — keep, or drop the stage name for page counts?; a graded answer whose grade is uncertain still shows "?" in Student answers and the report — keep, or a worded label?; the occasion labels were chosen by the builder: "Mid-term test", "Final-term test", "National exam", "Entrance exam", "Gifted students' exam", "Unit test", "15-minute test", "Grammar practice", "Topic practice", "Placement test" — change any?
- Step 22.2.2 builder, for the verifier: no `cargo test` was run (only `capabilities/default.json` changed: `core:window:allow-destroy`); a title typed as exactly "New thread" reads as automatic, so "Use automatic name" is hidden for it; Esc in a field moves focus to its panel region ("Keep editing" returns to the text); no visual review of the tabs and rows yet.
- Step 22.2.4 builder, for the teacher: the Test name's short occasion names drop "test" ("Unit", "15-minute": "Grade 7 - Unit - 2025") — keep, or "Unit Test" / "15-minute Test"?; an unknown occasion shows as "unknown" in the name — keep, "Other", or leave it out?; the Test name is made, not editable — add an edit box (then `edited_fields` keeps it)?
- Step 22.2.4 builder, for the teacher: "More details" has no editors for the list fields `units` and `tags` — make them editable there?
- Step 22.2.5 builder, for the teacher: when the teacher picks an existing test during extraction, the run's key photos are saved to it only if it has none — keep, or never for a picked test?; tests extracted before 0.3.0 have no key photos (their files were already swept); the uninstaller's box now reads "Delete app data (data, exports, webview, settings.json)" in English — check it is not cut off in the real uninstaller.
- 22.2.7 verifier F7 (minor, for a later fix): keyboard focus falls to the page body after "Use automatic name" (the button removes itself) and after Enter/Escape in any detail chip (`MetaChip`, `TestPanel.tsx`); return focus to the chip.
- Re-verifier F5 (minor, for a later fix): after the last thread in Chats is deleted, keyboard focus stays on the page body; move it to the Chats tab or the New thread button (`features/threads/ThreadList.tsx`).
- For 22.2.4: thread and report titles still show occasion codes ("FinalTerm HK1") because they come from `TestMetadata.display_name()` (`domain/models.py`); decision C's automatic Test name replaces it there.
