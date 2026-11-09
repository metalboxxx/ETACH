# Step 22.1 plan: the teacher's first look at the installed app

| | |
|---|---|
| Status | **Started 2026-10-13.** The packages are plan steps 22.1.1–22.1.7 in `docs/initial-plan/plan.md` (v2.10); the tracker there is the current status. |
| Build reviewed | The step 21 installer, `Exam Revision Helper_0.1.0_x64-setup.exe`, installed to `D:\ExamRevisionHelper` (main at 6df63df) |
| Owner | The orchestrating session. When work starts, each package becomes a plan step in a new `plan.md` version, and decisions go to the PRD first. |
| Next action | Step 22.1.7 (installer 0.2.0), then one verifier for 22.1.5–22.1.7 (its `E2E_SHELL --release` after the teacher is warned). All decisions are taken. |

The installed app does not need to be uninstalled. A new installer installs over it and keeps `<app>\data`.

## 1. The teacher's comments (verbatim, 2026-10-13)

> 1. The UI is good but please use theme different from claude desktop. Now it is EXACTLY the same, the same shade of black gray and orange!. use green, use front end skill. Even the shade of black is the same
>
> 2. There needs to be progress bar, so teachers know the app is running and not freezing
>
> *Comments made after the thread is finished and before grading:*
>
> 3. After the thread is finished (and before grading), I dont know where to see the images I just put into the app. Not here or bad UI . Edit: after opening again of 6., I saw the images and click on them which point me to the test, there i dont see the images again (dont need but I need to know the button lead to them). I tried closing and opening again but dont see again.
>
> 4. I click on unknown student, and when i click away it doesnt close that menu => bad ux . On when I click on the unknown student button again does it close
>
> 5. After the thread is finished ( and before grading), Nul-extract is not perfect, and we know that, but there is no apparent way for me to edit within app like .txt or .docx  => bad ux or non feature
>
> 6. After closing the app and open again, i see where to review but not the new menu before i close so i was confused a bit. After a bit , i understand, it is the review panel . I want the review part to be like editing in word, it is more intuitive for non-technical people than doing through "keep the value read" "fix" "skip".
>
> 7. From here step 6, i want to navigate to the UI doc editing stye of previous step, like before. After I figured it is in the thread "new thread" under the descrpition "A"?. I right click it, but there's no way to rename. For problem 6,7, I Suggest Remove Review tab and put it under the test of it want to revew
>
> 8. UI problem: when I hit print and want to go back, I usually hit the "x" button that close the whole app
>
> 9. No way to save as docx. save as only save as html.
>
> 10. Field name of test: Occasion cant be filled.
>
> 11. Now , after step 6, i cant seem to change student name. it is stuck at A
>
> 12. Now after i spam in the review tab, i cant edit the test anymore because everything is locked behind that review tab. I have mixed feelings about this flow. Edit: After tinkering I know where to edit the answers now, but since I forgot which paper i put into the app and i cant see the picture within the app, i cant verify :)
>
> *After running the grading:*
>
> 13. Threads also need to include student's name cuz thats what separate the from test
>
> 14. UI recommendation . It is because you click the 3 buttons there but the tab on the right changes: feels unnatural. switch the tabs: one on the right to the left and vice versa. The right tab should also have the original images
>
> 15. It is heard to verify the key when you have to switch tabs frequently. so when you have to verify key on the left, the original image or the test text must be on the right.
>
> 16. Headings should have more descriptive name more than "Extracted". "Graded" is ok? i see the vision behind this name.

Checked in the code: comment 1 is right. The accent is `#d97757`, Claude's orange (`app/src/styles/tokens.css`). Comment 9 conflicts with PRD D4 ("PDF/print first; DOCX later").

## 2. Work packages, in order

Each package is done by one implementer agent at a time. A fresh verifier checks it, and then the teacher merges. Where the table names agents, the implementer is the user-scope `ui-ux-builder` and the verifier is `ui-ux-verifier` (`~/.claude/agents/`; their skills are in `~/.claude/agent-skills/`, see its README). The `ui-ux-verifier` checks the design; the step's requirements and the standing requirements (plan §1.5) are still verified as for any step. Packages that change a decision update the PRD and plan first, with version bumps.

| # | Package | Comments | Agents | Depends on |
|---|---|---|---|---|
| 1 | **Small fixes:** investigate, then fix. The "Unknown student" menu should close on an outside click. Print needs a visible way back, so the window ✕ is not the only exit. The Occasion field must accept input. The student name must stay editable after Review. Threads must be renamable. Thread titles should show the student's name. Headings should be more descriptive than "Extracted". | 4, 8, 10, 11, 7 (rename), 13, 16 | `ui-ux-builder`, `ui-ux-verifier` (teacher, 2026-10-13) | — |
| 2 | **New theme:** green, with its own greys, clearly different from Claude Desktop, in light and dark. The theme lives in the colour tokens of `app/src/styles/tokens.css`. It goes early so later packages are built in it. | 1 | `ui-ux-builder`, `ui-ux-verifier` | 1 |
| 3 | **Progress bar:** real progress, e.g. "page 2 of 4, reading answers", not only the running indicator. The sidecar may need to report steps done and total. | 2 | `ui-ux-builder`, `ui-ux-verifier` (orchestrator, 2026-10-13: the bar is UI work; the builder also does the sidecar part) | 2 |
| 4 | **Layout:** show the original photos in the app, and make it clear where each button leads. Swap the sides so the original photos (or the test text) sit on the right while the teacher checks the test or the key on the left, which avoids tab switching. | 3, 12 (photos), 14, 15 | `ui-ux-builder`, `ui-ux-verifier` | 2 |
| 5 | **Editing like a document; Review moved under each test:** edit the extracted test in place, like Word, instead of "keep the value read / fix / skip". Remove the separate Review tab and show each item inside its test, so nothing is locked behind it. This touches data-model §5.3 (Review resolution), PRD D9 and the Review queue in PRD §13. | 5, 6, 7 (review), 12 (locking) | `ui-ux-builder`, `ui-ux-verifier` | 4 |
| 6 | **Save as DOCX:** export the clean test and the report as `.docx`, reusing Package 5's document structure. This changes PRD D4. | 9 | — | 5 |
| — | **New installer.** The teacher tries it. Then **step 22** (offline check and acceptance) runs on that final build. | | | 1–6 |

## 3. Decisions for the teacher

Ask them one at a time, each before the package it belongs to. Give options neutrally, without a recommendation unless one is asked for.

1. Do these packages come **before** the step 22 acceptance, as new plan steps, or does acceptance happen on the current build first?
2. Package 2: green for the accent only, or a full green-tinted palette? Keep both light and dark mode?
3. Package 4: which layout? Show a few sketches to choose from.
4. Package 5: remove the Review tab completely, or keep a small list of unsure items as a shortcut? How Word-like should editing be: free text, or click a question and edit it in place?
5. Package 6: bring DOCX into scope now? This changes PRD D4.
6. May UI agents take screenshots of the screens in a headless test browser to check their own design? That is not the running app and does not move the mouse, but CLAUDE.md asks for the teacher's permission first.

## 4. Decisions taken

- The 22.1 packages are sub-steps of step 22 inside `docs/initial-plan/plan.md`, which ends at step 22. Work after launch gets its own content-named plan file (teacher, 2026-10-13; plan v2.9).
- Decision 1: the packages come **before** the step 22 acceptance, which runs once on the final build. They keep the number 22.1: Package N is plan step 22.1.N, and the new installer is 22.1.7 (teacher, 2026-10-13; plan v2.10).
- Decision 2: a light green; the exact shades are adjusted later (teacher, 2026-10-13; PRD v4.11). Light and dark mode both stay, as the PRD already had them, and the greys get a green tint because comment 1 names the shade of black too.
- Decision 3: layout **B, a workspace view**. With no panel open: thread list | conversation. Opening Test, Key, Answers or Report hides the conversation; the panel fills the left, the original photos fill the right (page by page, with zoom), and "← Back to thread" returns to the conversation (teacher, 2026-10-13). The other sketches were A (swap the panel and the conversation), C (split the right panel) and D (panel on the left, tabbed right column).
- Decision 4a: the Review tab is **removed completely**; unsure spots show only inside each test, marked in the text, and the sidebar shows which threads or tests still have them (teacher, 2026-10-13). The other option was a short shortcut list of tests with unsure spots.
- Decision 4b: editing is **free text, like a Word page**: the whole test is one editable page; on save the app reads the text back into questions and options, and a line it cannot understand is highlighted for the teacher to fix (teacher, 2026-10-13). The other option was click-to-edit in place, one piece at a time.
- Decision 5: **DOCX now** for the clean test, the key and the report, next to print/PDF; PRD D4 changes in step 22.1.6 (teacher, 2026-10-13). The other options were not now, or the test only.
- Decision 5, the save place: a DOCX is saved **into the app folder only**, `<app>\exports\`, which then opens in Explorer; PRD §11 stays as written (teacher, 2026-10-13). The other options were a Save-as dialog anywhere, or a dialog starting in the app folder (both needed a §11 exception).
- Decision 6: UI agents **may screenshot the headless test browser** (Playwright, synthetic data, light and dark), kept in a gitignored scratch folder; never the installed app and never `e2e:shell` (teacher, 2026-10-13).
- The teacher tests and merges the 22.1 sub-steps together at the end instead of after each one. Each sub-step's branch starts from the previous sub-step's branch (teacher, 2026-10-13; plan v2.11).
- Steps 22.1.5, 22.1.6 and 22.1.7 are built one after another and then verified together by one fresh verifier, which marks each tracker row (teacher, 2026-10-14; plan v2.14.1).
- §5 questions answered by the teacher after the 0.2.0 build (2026-10-14), for the next round of fixes:
  1. Occasion list and chip in plain English ("15-minute test"); the Other chip shows only the typed text.
  2. Print keeps the print view first.
  3. Titles and headings put the test first ("Unit 3 test · Phạm Thu Hà").
  4. Progress count names the current page: "Reading page 3 of 4".
  5. A second pass over a page says "Checking page 2 again".
  6. The live sign pulses during the quiet wait too, labelled "Model is writing".
  7. Elapsed time gets the word "Elapsed" and still counts stopped time.
  8. After a restart a stopped run's bar showing the stage start is accepted (no migration).
  9. Long progress text in the sidebar wraps to two lines.
  10. Key photos are stored, so the Key workspace can show them.
  11. A card thumbnail for a test from another paper keeps opening Answers.
  12. Question numbers may have gaps; the save accepts them, so numbers match the paper (listening questions, and no subtraction when checking answers).
  13. A question added in the text gets an answer row (and a re-grade if graded); a `???` the teacher types becomes a note. 13b: a "Format help" button in a footnote under the page opens and closes the table of line forms with examples.
  14. Notes keep one button where Accept changes nothing (no Dismiss everywhere).
  15. The thread menu gets "Use automatic name", which restores the test · student title.
  16. The print view gets the same title and details line as the test DOCX.
  17. The report DOCX name keeps the student's name.
  18. The teacher asked for my recommendation; I recommended the professional practice, and the teacher left it to me: the version is built into the app (not read from installed metadata), and the build clears `target/release/sidecar/` first, so installing over 0.1.0 without uninstalling still shows the right version.
  19. Development `--data <dir>` exports stay in `<dir>\exports\`.
  20. Open folder in the plain web build stays, with its message.
  Not asked: the theme shade questions (the teacher adjusts shades later) and the verifier's minor findings (to fix later).
- UI work uses two user-scope agents, `ui-ux-builder` and `ui-ux-verifier`, which alone hold the front-end skills; the `frontend-design` plugin was uninstalled so no other session has it (teacher, 2026-10-13).

## 5. Carried forward

Minor findings from the step 22.1.1 verification (plan Step 22.1.1 Verifier notes), for the package that owns each area:

- Step 22.1.2 (theme): `text-accent` on the panel is 3.79:1 in light mode (Create “<typed>” at `ExtractionCard.tsx`, also `KeysPanel.tsx`); white on accent is 4.14:1; input borders are 1.33:1 (light) and 1.20:1 (dark). The new palette must reach 4.5:1 for text and 3:1 for borders.
- Step 22.1.4 (layout): after Back from the print view, focus falls to the page body instead of the panel's Print button; the thread menu and the student picker stay open when the teacher tabs out; after a merge, the card's [Test] and [Key] buttons still open the merged-away test.
- Step 22.1.5 (editing): error text can show "[object Object]" for a 422 with a list of errors (reuse `TestPanel.errorText`); student search has no debounce, so a fast Create could duplicate a student; a thread renamed to exactly "New thread" falls back to the made title.
- Wording for the teacher (asked when 22.1.1 is reviewed): the Occasion list shows raw codes (e.g. "FifteenMinuteTest") and the chip shows the `Other:` prefix; whether Print opens the print window at once or only from the print view's bar; whether titles and headings put the student or the test first.
- Step 22.1.2 (theme), for when the teacher adjusts the shades: the light green fill on primary buttons is soft (1.37:1 against the page; allowed because the dark label carries it) — keep it, deepen the fill, or add an `accent-strong` outline; success (#27703f) and accent-strong (#1c6a37) are close greens — keep, move success toward teal, or make them one token; whether the dark mode's green tint is different enough from Claude Desktop; whether the on-screen print view should be a white sheet in dark mode too; the page-number badge over photo thumbnails (`text-muted` on `bg-surface/90`) cannot be checked by computation — accept it or make it opaque (step 22.1.4 can do that); dividers and secondary-button outlines are faint (1.1:1, decorative).
- Step 22.1.3 (progress), questions for the teacher: after an app restart a stopped run's bar shows the start of its stage (e.g. 40% not 47%) — accept, or store the progress (a migration); "page 2 of 4" counts finished pages, so it says 2 while page 3 is read — keep, show done + 1, or report before each call; the live sign beats only while the model writes, not during the quiet wait before its first word — keep, or add a timer beat; elapsed time includes time stopped — keep, or count from the latest Resume; the live sign's wording — "Writing", "Model is writing" or "Still working".
- Step 22.1.3 verifier, also for the teacher: a second pass over a page (tiles) restarts the count ("page 3 of 3" → "page 1 of 1") — say "checking page 2 again" instead?; the elapsed time has no visible word ("40%  0:00") — add "Elapsed"?; long counts are cut off in the sidebar ("Explaining mistakes · question 12 of 40"), full text only in a tooltip.
- Step 22.1.4 verifier, for step 22.1.5: `Esc` while typing in a workspace field closes the workspace and loses the typing (22.1.5's unsaved-text guard must cover it); `features/panel/photos.ts:88` uses `String(err.detail)` (the shared error-text helper); below 1024 px, ←/→ turn the hidden photo page while the panel side shows; key photos count in "Page 3 of 3" while the strip says "Key 1".
- Step 22.1.4, for the teacher: **key photos are not kept** after a run (the sweep deletes them after a day), so the Key workspace shows the test text, never the key photo — store them in a later step, or is the test text enough?; when the test came from another paper (or after a merge) a card thumbnail opens Answers with the teacher's own photo rather than the Test at page n — keep, or open the Test?
- Step 22.1.5, for the teacher: deleting a question leaves a gap in the numbering, which the save reports as an error — keep, or renumber on save?; a question added in the text gets no answer row and no re-grade, and a `???` the teacher types is highlighted but makes no new note — keep, or add them?; where Accept changes nothing (unreadable text, assumed points, failed checks, unknown occasion) a note has only one button ("Leave as is", "Keep 0.25 a question", …), and Dismiss appears only on answers, keys and card notes — keep, or add Dismiss everywhere?; renaming a thread to "New thread" now keeps that name, so the made title (student · test) cannot be brought back — keep, or add "Use the default title"? (the name is stored with an invisible marker; a cleaner way is a database change).
- Step 22.1.6, for the teacher: the test's DOCX starts with the test name and a line like "45 minutes · Code X · N points", which the print view does not have — keep, title only, or add the same lines to the print view?; the report's file name includes the student's name (`… - Report - <student>.docx`) — keep, or use the class or a number?; in development and tests (`--data <dir>`) files go to `<dir>\exports\` — keep, or always next to the data folder?; in the plain web build (development only) Open folder is shown and says it works in the app window only — keep, or hide it there?
- Step 22.1.7, for the teacher: when the 0.2.0 installer finds 0.1.0 it offers "Uninstall before installing" (preselected; clean, `<app>\data` stays) or "Do not uninstall", which copies over 0.1.0 and leaves its old version file, so Settings would probably still show 0.1.0 (not tried). The release notes say to use the preselected choice — keep that, or fix it in code (the version from a built-in constant, or an installer step that deletes the old version files)? The same stale file sat in the build folder (`target/release/sidecar/`, not cleared between builds); the builder deleted it.
- Step 22.1.5–22.1.7 verifier (plan Verifier notes), minor findings for a later fix: Esc in the test text drops focus to the page body, and "Keep editing" also returns focus there, not to the text (`hooks/useShortcuts.ts`); closing the app window with unsaved test text does not ask; at 1280×720 with notes and an error the editable text starts below the fold; line errors stay while the teacher types until the next save, so after lines are added above they point at the wrong line; the "Saved …" status region appears hidden-then-filled, which some screen readers may not announce (unconfirmed, needs an NVDA check).
- Step 22.1.5 builder, for the verifier: `test_step20.py::test_r20_2_backup_restore_same_rows_and_files` failed once while the full e2e ran alongside it, then passed 3 of 3 alone — watch for it.
- Outside 22.1 scope so far: a run notification for a thread not in the loaded list still says "New thread" (`features/running/`); the student chip edits the name but not the class.
