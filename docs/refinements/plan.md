# Refinements plan — ETACH

| | |
|---|---|
| Version | **v0.3.2** (2026-11-09) |
| Scope | The first round after the initial plan: the teacher's list from using 0.6.1 (the Models tab order, Extract again per tab) and the faults found while checking it |
| Based on | [`PRD.md`](../PRD.md) v9.1.1 · [`data-model.md`](../data-model.md) v1.35.3 · [`llm-design.md`](../llm-design.md) v4.60.3 |
| Method | As `docs/initial-plan/plan.md` §1: one branch `step/<id>-<slug>` per step, a fresh verifier per step, the teacher merges and signs off. The standard commands (`TEST`, `LINT`, `APP_TEST`, `E2E`, …) are in [`dev-setup.md`](../dev-setup.md) |

### Changelog
| Version | Date | Change |
|---|---|---|
| v0.3.2 | 2026-11-09 | Patch: the Based on line follows PRD v9.1.1, data-model v1.35.3 and llm-design v4.60.3; the Method line points to `dev-setup.md` for the standard commands |
| v0.3.1 | 2026-11-09 | Patch: the Based on line follows PRD v9.1, data-model v1.35.2 and llm-design v4.60.2; R2's path names `sidecar/src/etach/`; the Method line says the CLI is `etach` |
| v0.3 | 2026-11-06 | Minor, teacher: D10 a line ending in "?" counts as a real question |
| v0.2 | 2026-11-06 | Minor, after the R2 verifier: D10 says what counts as a stray number and a run, and that the rule crosses a heading (teacher); R2.4 the overfit check (teacher) |
| v0.1 | 2026-11-06 | First draft from the teacher's list and decisions D1–D10 |

## 1. Decisions (teacher, 2026-11-06)

| # | Decision |
|---|---|
| D1 | The Models tab follows the order of work on a new test: Test reader, Extraction check, Student answer reader, Grading, Grading check |
| D2 | Only a thread's first run extracts everything. After that, each tab has its own button, in the place of the old Extract again. The full run from the beginning is removed |
| D3 | The buttons say what they do: "Extract Test again" (Test tab), "Extract Key again" (Key tab), "Extract Student answers again" (Student answers tab) |
| D4 | The Report tab gets no such button; Grade student answers stays as it is |
| D5 | Extract Key again remakes the AI keys. Keys the teacher typed or verified stay. A key photo is read again, and the AI writes keys only for the questions the photo does not cover |
| D6 | The Key tab has one Add key button in its toolbar; it lists the questions with no key to pick from. The key list otherwise stays as it is |
| D7 | The Key tab can delete a key. The question then simply has no key, and the next Grade or Extract Key again may write a new AI key |
| D8 | Extract Student answers again keeps the answers the teacher corrected and reads only the others |
| D9 | If that changes the answers of a graded paper, the old report stays and a bar like "Keys changed" offers Re-grade. Nothing runs until the teacher presses it |
| D10 | Question numbers: a run starting at 1 beats a lone earlier number, also across a section heading. The lone number has no options and does not look like a question (no blank, cue or answer start, and it does not end in "?"); the run has a 1 and a 2 with A–D options. Nothing else in the rule changes |

Not in this round, by decision: no retry when the AI returns fewer keys than asked (seen once in 30 calls, "Test 2"
questions 30–34; Add key and Extract Key again cover it). A section that restarts at 1 ("Test V" questions 35–36)
stays text for the teacher to fix by hand.

## 2. Why the keys went missing

From the app's data, read-only, 2026-11-06, with the teacher's permission:

- **"Test V" (T-0011), questions 1–8.** The reader read them correctly, but its first line was
  "8. REVISION 9 GK1 (V)". `ocr_structure.py` took that as question 8, and its rule "a number at or below the last one
  is text" turned the real 1–8 into text. The key run was therefore never asked for them. Replaying the saved reading
  gives the same result; with the first line removed, questions 1–14 are found.
- **"Test V", questions 35–36.** The same rule: the reading numbers them 1 and 2 after question 34.
- **"Test V", question 24.** In no page reading; a reader miss that code cannot recover.
- **"Test 2" (T-0012), questions 30–34.** The AI returned 1 key of 6 and the app accepted it. The five `uncertain_key`
  items exist, but the Key tab lists only questions with a key, so they could not be seen.

## 3. Steps

### R1. Models tab order (D1)
`app/src/features/settings/roles.ts`: reorder `ROLE_INFO`; its order also sets `roleList`'s sentences.
- R1.1 The Models tab shows the five roles in the D1 order; with `photo_reader = "vision"` the Test reader row stays hidden.

### R2. Stray number before a run from 1 (D10)
`sidecar/src/etach/domain/ocr_structure.py`, about 10–15 lines. No prompt change, no GPU.
- R2.1 The saved "Test V" page 1 reading (as a scrubbed test text, no student data) gives questions 1–14 and no fake question 8.
- R2.2 A number at or below the last one is still text in every other case (the dictionary and passage lines stay text).
- R2.3 Replaying every saved reading in `data/app.db` shows no change on any other page, or each change is listed for the teacher.
- R2.4 Not overfit to "Test V": the same before/after comparison on every other OCR reading available outside `data/app.db` (recordings, fixtures), and on made-up pages with varied stray lines and lookalike lists. Each change is listed for the teacher.

**Verifier notes:** fresh verifier, 2026-11-06, at 48b2d1a against plan v0.3 (commit 0a8f6bd). R2.1: questions 1–14, no fake 8, the stray line kept and flagged (1 unplaced line). R2.2: 6 of 6 listed cases hold. R2.3: 21 readings, 6 runs, 1 page changed: run `01M6DX2D7MWRXZ6FJCVQ09Z539`, call `01M6DX2DV99ZEVYSS20TVB9EC5`; through the merge that run goes from 30 to 37 questions, no number twice, the other 5 runs give identical drafts. The `lead` change alters 0 of the 21 pages. R2.4: no OCR readings in `fixtures/` (1382 logged calls in 92 files, none with role `ocr`), none in the cassettes; 34 made-up pages, 0 wrong, 10 fired, 24 did not; 67 pages built from the 19 verified fixture tests, 0 changed; with a stray line added the rule fired on exactly the 13 of 19 pages whose questions 1 and 2 have four options. `TEST` 2276 passed, 1 skipped; `LINT`, S3–S6 pass; S7 not run (no `app/` or schema change).

**Live check (R2.4, teacher, 2026-11-06):** tuning set at 87bec31, 14 papers, 0 failed, 56 minutes, `eval-history.csv` line 17. The 6 papers read by the OCR model gave 17 fresh page readings; the old and new rule give the same result on all 17 (0 changed), so the rule did not fire on any of them. This shows no harm on new OCR text; it adds no new case of the rule working.

### R3. Add key and delete key (D6, D7)
Sidecar: `DELETE /tests/{id}/keys/{question_id}`; a deleted key follows the key-change rules (`regrade_pending`). App: `KeysPanel.tsx`.
- R3.1 Add key lists exactly the graded questions with no key, and the saved key is a teacher key.
- R3.2 Add key is not offered when every question has a key.
- R3.3 Delete asks first, removes the key and its explanations, and settles the question's open `uncertain_key` item.
- R3.4 The next Grade writes a new AI key for that question.
- R3.5 The print and the Word file show the changed keys.

### R4. Extract Key again (D2, D3, D5)
A new route and a key-only run, on the Key tab in the old button's place.
- R4.1 AI keys are remade from the current test text; `teacher_edit` keys and `teacher_verified` keys stay.
- R4.2 With a key photo, the photo is read again first and the AI writes only what it does not cover.
- R4.3 Questions with no key get one (the "Test V" case).
- R4.4 A graded paper gets the "Keys changed" bar; no re-grade starts by itself.
- R4.5 While a run goes on the thread the button waits, as Extract again did; an unfinished key run is discarded first (D12 of step 22.6).

### R5. Extract Test again (D2, D3)
The Test tab's button: the rules of data-model §5.8 without reading the student answers again.
- R5.1 Only the test pages are read; the student answers stay on their matched questions.
- R5.2 The choice between updating for every thread and a copy stays when other threads use the test.
- R5.3 The key run still follows, for changed and new questions.

### R6. Extract Student answers again (D2, D3, D8, D9)
The Student answers tab's button, built on the picked-test path, which reads answers against a saved test.
- R6.1 The test and keys are not touched.
- R6.2 Answers the teacher corrected stay; the others are read again.
- R6.3 On a graded paper with changed answers, the old report stays and the bar offers Re-grade; no run starts by itself.
- R6.4 With no changed answers, no bar shows.

### R7. Documents and installer
- R7.1 PRD (a decision changed: major), data-model §5.8 and llm-design route inventory match what was built; this plan's "Based on" line follows.
- R7.2 No old "Extract again" wording remains in the app. "Extract again without the pick" on the extraction card is checked with the teacher first.
- R7.3 The version number is set in all four files after the teacher chooses it; `docs/release-notes.md` gets its section.

## 4. Tracker

| Step | Title | Depends on | Status | Date | Commit | Verified by |
|---|---|---|---|---|---|---|
| R1 | Models tab order | – | ✅ | 2026-11-06 | bf2eb80 | agent |
| R2 | Stray number before a run from 1 | – | ✅ | 2026-11-06 | 48b2d1a | agent |
| R3 | Add key and delete key | – | ✅ | 2026-11-06 | 2c6a13e | agent |
| R4 | Extract Key again | R3 | ☐ | | | |
| R5 | Extract Test again | R4 | ☐ | | | |
| R6 | Extract Student answers again | R5 | ☐ | | | |
| R7 | Documents and installer | R1–R6 | ☐ | | | |
