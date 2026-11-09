# Implementation Plan — ETACH

| | |
|---|---|
| Version | **v2.70.16** (2026-11-03) |
| Scope | Steps 1–22, including step 22.1's sub-steps (the teacher's app review, `docs/initial-plan/phases-testing/step22.1-plan.md`), which come before step 22's acceptance (teacher, v2.10). Work after launch goes into its own folder in `docs/`, named by its content (e.g. `docs/<topic>/plan.md`), never numbered or dated, with its own tracker. |
| Based on | [`PRD.md`](../PRD.md) v9.0.1 · [`data-model.md`](../data-model.md) v1.35.1 · [`llm-design.md`](../llm-design.md) v4.60.1 |
| Purpose | The PRD says **what** must be true. This plan says **in what order** it becomes true and **how an independent checker proves it**. It is also the progress tracker across sessions. |

### Changelog
| Version | Date | Change |
|---|---|---|
| v1.0 | 2026-09-28 | First plan: steps 0–19 |
| **v2.70.16** | 2026-11-03 | Patch, after the initial plan: moved with its waivers, phase documents and both quality plans to `docs/initial-plan/`; the title no longer names the old app; "Based on" → PRD v9.0.1, data-model v1.35.1, llm-design v4.60.1. Later work gets its own folder `docs/<topic>/` |
| v2.70.15 | 2026-11-02 | Patch: after the teacher's sign-off (09cdc04) of `docs/initial-plan/waivers/22.md`, every tracker row is ✅ or ⚠ (R22.4): the initial plan is complete |
| v2.70.14 | 2026-11-02 | Patch: step 22: the teacher concluded the initial plan after using 0.6.1 in the app; the waiver draft `docs/initial-plan/waivers/22.md` awaits the teacher's sign-off |
| v2.70.13 | 2026-11-02 | Patch: R22.6.8.5 (the user's `E2E_SHELL --release`) passes; checklist 22.6.8 (b) ticked; tracker row 22.6.8 ✅ |
| v2.70.12 | 2026-11-02 | Patch: 22.6.8 rebuilt after the light window frame (step22.6-plan D18) |
| v2.70.11 | 2026-11-02 | Patch: step 22.6.8 build and release checks (R22.6.8.2–4) and the verifier's low findings fixed; R22.6.8.5 waits for the user |
| v2.70.10 | 2026-11-02 | Patch: step 22.6.8 (a) verified (R22.6.8.1, verifier notes under 22.6.8); checklist (a) ticked; tracker row 22.6.7 ✅, row 22.6.8 🔄 until (b) |
| v2.70.9 | 2026-11-02 | Minor: step 22.6.8 requirements R22.6.8.1–R22.6.8.5 |
| v2.70.8 | 2026-11-02 | Patch: step 22.6.7 checklist (a) ticked (the teacher's logo, step22.6-plan D17); its row waits for the 22.6.8 verifier |
| v2.70.7 | 2026-11-01 | Patch: tracker row 22.6.6 ✅ (verifier, the teacher's GPU check and choice) |
| v2.70.6 | 2026-11-01 | Patch: "Based on" → llm-design v4.60 (step 22.6.6 (c), step22.6-plan D16: `photo_structure` defaults to `"code"`); step 22.6.6 checklist (b) (the GPU check ran 2026-11-01, results in step22.6-plan §5) and (c) ticked |
| v2.70.5 | 2026-10-31 | Patch, teacher: R22.6.6.2, the GPU check is one script ("One script") |
| v2.70.4 | 2026-10-31 | Patch: step 22.6.6 final re-check notes (R22.6.6.6) at f936d9a: R22.6.6.3–6 pass, S1–S7 and headless E2E pass; checklist (a) ticked |
| v2.70.3 | 2026-10-31 | Patch: "Based on" → data-model v1.35, llm-design v4.59 (step 22.6.6, the re-check's reload holes 1–3 of R22.6.6.3 and the stale `points_fix` passages) |
| v2.70.2 | 2026-10-31 | Patch: step 22.6.6 re-check notes (R22.6.6.6); tracker 22.6.1 ✅; headless E2E R19.6 fails intermittently at HEAD, so 22.6.6 (a) stays open |
| v2.70.1 | 2026-10-31 | Patch: "Based on" → data-model v1.34, llm-design v4.58 (step 22.6.6, step22.6-plan D15, R22.6.6.3: the grade `save` reloads a test that changed since load) |
| v2.70 | 2026-10-31 | Minor, teacher: R22.6.6.3–6, the verifier's findings fixed in step 22.6 (D15 "Fix now" for the grading gap; the English answer-box heading; a typed/vision test for the photo ways; a fresh re-check) |
| v2.69.1 | 2026-10-30 | Patch: step 22.6.6 verifier notes for 22.6.1–22.6.5; tracker 22.6.2–22.6.5 ✅, 22.6.1 🔄 (the English answer-box heading drops a line with text); the §4 open-note test (xfail) |
| v2.69 | 2026-10-30 | Minor: step 22.6.6 requirement R22.6.6.1 (the round verifier); (b)–(c) when the GPU check's start is decided |
| v2.68.2 | 2026-10-30 | Patch: "Based on" → llm-design v4.57 (`photo_structure = "ocr_format"`, way 2a); step 22.6.5 checklist (a) and (c) ticked (second step agent) |
| v2.68.1 | 2026-10-30 | Patch: "Based on" → llm-design v4.56 (`photo_structure`, way 2b); step 22.6.5 checklist (b) and the (2b) half of (a) ticked (first step agent) |
| v2.68 | 2026-10-30 | Minor: step 22.6.5 requirements R22.6.5.1–5 (the `photo_structure` setting, 2b code structure, its offline check on Test K and G8, 2a OCR format); two step agents |
| v2.67.3 | 2026-10-30 | Patch: step 22.6.4 part (b) fixes: Extract again is not held by the key run (D12); the waiting Grade button's focus ring at full colour |
| v2.67.2 | 2026-10-30 | Patch: step 22.6.4 checklist (b), the screens half ticked (part (b), the UI builder) |
| v2.67.1 | 2026-10-30 | Patch: "Based on" → llm-design v4.55 (D14, Delete test and Delete student discard the key run) |
| v2.67 | 2026-10-30 | Minor, teacher: R22.6.4.7 (D14, deleting a test or student cancels the key run) and R22.6.4.8 (D13, no toast for the key run; the E2E waits) |
| v2.66.2 | 2026-10-30 | Patch: step 22.6.4 part (a) checklist ticks ((a), (c), the sidecar half of (b)) |
| v2.66.1 | 2026-10-30 | Patch: "Based on" → llm-design v4.54 (D12, the key run is discarded by Extract again and Delete thread) |
| v2.66 | 2026-10-30 | Minor, teacher: R22.6.4.6, Extract again and Delete thread cancel the key run (step22.6-plan D12); `erh run` / `erh eval` start none |
| v2.65.1 | 2026-10-30 | Patch: step 22.6.4 part (a), checklist not yet ticked (the agent stopped before its last checks); "Based on" → PRD v9.0, data-model v1.33, llm-design v4.53 |
| v2.65 | 2026-10-30 | Minor, teacher: step 22.6.4, the Grade button waits while the key is made (step22.6-plan D11); requirements R22.6.4.1–5; built in two parts (sidecar agent, then the UI builder) |
| v2.64.2 | 2026-10-30 | Patch: step 22.6.3 checklist ticked; "Based on" → data-model v1.32, llm-design v4.52 |
| v2.64.1 | 2026-10-30 | Patch: step 22.6.3 requirements R22.6.3.1–4 |
| v2.64 | 2026-10-30 | Minor, teacher: step 22.6.2 checklist with the teacher's answers (blank under 20% read with confidence; a blank paper becomes a test-only thread, like a paper with nothing read) and requirements R22.6.2.1–4; "Based on" → PRD v8.28, llm-design v4.51 |
| v2.63.1 | 2026-10-30 | Patch: step 22.6.1 requirements R22.6.1.1–4 (R22.6.1.1 widened after Test K's stored OCR text showed "ANSWER" headings and headless rows); "Based on" → llm-design v4.50 |
| v2.63 | 2026-10-30 | Minor, teacher: new step 22.6 (the teacher's sixth look at ETACH 0.6.0: photo structure, blank papers, the checker, the key after extraction, three photo ways compared, the logo, installer 0.6.1; `docs/initial-plan/phases-testing/step22.6-plan.md`), sub-steps 22.6.1–22.6.8 with their checklists; step 22.5.9 is folded into it and removed; step 22 now depends on 22.6.8 |
| v2.62 | 2026-10-30 | Minor: step 22.5.8 ✅; new step 22.5.9 (the teacher's small adjustments and the logo, installer 0.6.1), step 22 now depends on it |
| v2.61.11 | 2026-10-30 | Patch: step 22.5.8, the teacher installed ETACH 0.6.0 and the one-time data copy matched; R22.5.8.4 names the ETACH installer; tracker row |
| v2.61.10 | 2026-10-29 | Patch: step 22.5.8 R22.5.8.5, the user's E2E_SHELL on the ETACH build passed (after a WebDriver update); tracker row |
| v2.61.9 | 2026-10-28 | Patch: step 22.5.8 rebuilt as ETACH after (f)–(h), Defender clean, release notes rewritten; tracker row |
| v2.61.8 | 2026-10-28 | Patch: step 22.5.8 checklist (f), (g), (h) ticked; the verifier's notes (f)–(h) (at ba09eda) |
| v2.61.7 | 2026-10-28 | Patch: (h) and R22.5.8.9 follow PRD v8.27 (motto headings in Chats only; Tests and Students ungrouped); "Based on" → PRD v8.27 |
| v2.61.6 | 2026-10-28 | Patch: the title says ETACH; "Based on" → PRD v8.26.1, data-model v1.31.1, llm-design v4.49.1 |
| v2.61.5 | 2026-10-28 | Patch: "Based on" → PRD v8.26 (the program file `ETACH.exe`) |
| v2.61.4 | 2026-10-28 | Patch: "Based on" → PRD v8.25 (the start screen's paper-shaped drop box, no heading) |
| v2.61.3 | 2026-10-28 | Patch: "Based on" → PRD v8.24 (the start screen back to its simple layout) |
| v2.61.2 | 2026-10-28 | Patch: "Based on" → PRD v8.23 (New thread back to its simple row) |
| v2.61.1 | 2026-10-27 | Patch: "Based on" → PRD v8.22 (no margin mark on the open thread) |
| v2.61 | 2026-10-27 | Minor, teacher: step 22.5.8 (h), the layout (PRD v8.21), on `step/22.5.8d-layout`; R22.5.8.9; "Based on" → PRD v8.21 |
| v2.60.2 | 2026-10-27 | Patch: "Based on" → PRD v8.20 (the deep navy hover) |
| v2.60.1 | 2026-10-27 | Patch: "Based on" → PRD v8.19 (the ETACH gradient) |
| v2.60 | 2026-10-27 | Minor, teacher: step 22.5.8 (g), the app renamed ETACH with the default folder `D:\ETACH` (PRD v8.18), on `step/22.5.8c-rename`; R22.5.8.8; the one-time data move; "Based on" → PRD v8.18, data-model v1.31, llm-design v4.49 |
| v2.59.1 | 2026-10-27 | Patch: R22.5.8.7 follows PRD v8.17 (only the main buttons and workspace tabs enlarged); "Based on" → PRD v8.17 |
| v2.59 | 2026-10-27 | Minor, teacher: step 22.5.8 (f) also sets the font, Faustina for the whole app (PRD v8.16); R22.5.8.7 names it; "Based on" → PRD v8.16 |
| v2.58.3 | 2026-10-27 | Patch: step 22.5.8 (f) follows PRD v8.15; "Based on" → PRD v8.15 |
| v2.58.2 | 2026-10-27 | Patch: step 22.5.8 (f) follows PRD v8.14; "Based on" → PRD v8.14 |
| v2.58.1 | 2026-10-26 | Patch: step 22.5.8 (f) follows PRD v8.13 (the teacher's changes after the theme screenshots); "Based on" → PRD v8.13 |
| v2.58 | 2026-10-26 | Minor, teacher: step 22.5.8 (f), the new light theme (PRD v8.12), on `step/22.5.8b-theme`; R22.5.8.7; the installer steps (c)–(d) and E2E_SHELL run again after it; "Based on" → PRD v8.12 |
| v2.57.5 | 2026-10-26 | Patch: step 22.5.8 build and release checks, the user's E2E_SHELL pass, the next action (theme talk before installing); tracker row |
| v2.57.4 | 2026-10-26 | Patch: step 22.5.8 checklist (b) ticked; the round verifier's notes (at 8cb62ae, re-check at da4552e) |
| v2.57.3 | 2026-10-26 | Minor, teacher: step 22.5.8 (a)(5), the T/F letters (round verifier); "Based on" → data-model v1.30 |
| v2.57.2 | 2026-10-26 | Patch: "Based on" → data-model v1.29 (step 22.5.8 (a)(3): a `key_unmapped` Fix onto a relabelled True/False question stores the T/F letter) |
| v2.57.1 | 2026-10-26 | Patch: "Based on" → data-model v1.28 (step 22.5.8 (a)(2): a key photo settles the replaced key's open `uncertain_key` items) |
| v2.57 | 2026-10-26 | Minor, teacher: step 22.5.8 (installer 0.6.0) gets its checklist and requirements, with the four answers to the parked questions |
| v2.56.2 | 2026-10-26 | Patch: step 22.5.7 R22.5.7.7 verified at e912074 (S1–S7, headless E2E pass); verifier notes; tracker row ✅ |
| v2.56.1 | 2026-10-26 | Patch: "Based on" → PRD v8.11, data-model v1.27, llm-design v4.48 (R22.5.7.7: GLM-OCR the default photo reader, `ocr` a default role); step 22.5.7 last checklist item ticked |
| v2.56 | 2026-10-26 | Minor, teacher (G4): GLM-OCR reads test photos and tiles stay off; step 22.5.7 gets a checklist item and R22.5.7.7 to make the `ocr` reader the default |
| v2.55.2 | 2026-10-26 | Patch: step 22.5.6 tracker row ✅ (G3 accepted, 8ec134d); step 22.5.7 verifier notes and tracker row (🔨 built, verified (R22.5.7.1–5) — awaiting G4) |
| v2.55.1 | 2026-10-26 | Patch: "Based on" → PRD v8.10, data-model v1.26, llm-design v4.47 (step 22.5.7: photo page breaks, the targeted re-read, answer-number errors, the GLM-OCR two-step reader; `LlmCall.role` gains `ocr`); Appendix A unchanged (no field added or removed) |
| v2.55 | 2026-10-26 | Minor: step 22.5.7 (photos: page breaks, the targeted re-read, answer-number errors, GLM-OCR trial) gets its checklist and requirements (D13) |
| v2.54.8 | 2026-10-26 | Patch: step 22.5.6 verifier notes (third re-check at e13aa18) and tracker row (🔨 built, verified (R22.5.6.1–8) — awaiting G3) |
| v2.54.7 | 2026-10-26 | Patch: "Based on" → llm-design v4.46.3 (step 22.5.6 second re-check rework: a joined typed-PDF question's page by a global alignment) |
| v2.54.6 | 2026-10-25 | Patch: step 22.5.6 verifier notes (second re-check at 0cb2a5a) and tracker row (❌ R22.5.6.1) |
| v2.54.5 | 2026-10-25 | Patch: "Based on" → llm-design v4.46.2 (step 22.5.6 re-check fix: a joined typed-PDF question's page found by normalised text matching) |
| v2.54.4 | 2026-10-25 | Patch: step 22.5.6 verifier notes (re-check at e875cfb) and tracker row (❌ R22.5.6.1) |
| v2.54.3 | 2026-10-25 | Patch: "Based on" → llm-design v4.46.1 (step 22.5.6 verifier fixes: how a joined typed-PDF question finds its page; a repeat is a whole block) |
| v2.54.2 | 2026-10-25 | Patch: step 22.5.5 tracker row ✅ (G2 accepted, c754e2f); step 22.5.6 verifier notes and tracker row (❌ R22.5.6.1) |
| v2.54.1 | 2026-10-25 | Patch: "Based on" → PRD v8.9, data-model v1.25, llm-design v4.46 (step 22.5.6a: typed PDFs joined, answer reading per page, key explanations ignored, the `from_key_photo` key status and its pass, the listening range); Appendix A: `OmittedSection.kind` |
| v2.54 | 2026-10-25 | Minor: step 22.5.6 (typed pages; reading student answers and keys) gets its checklist and requirements (D12) |
| v2.53.3 | 2026-10-25 | Patch: step 22.5.5 verifier notes (re-check at bfdf316) and tracker row (verified, awaiting G2) |
| v2.53.2 | 2026-10-25 | Patch: step 22.5.5 checklist (a) item and R22.5.5.4 point to the guessing baseline (D11f) |
| v2.53.1 | 2026-10-25 | Patch: "Based on" → PRD v8.8.1, data-model v1.24.1, llm-design v4.45.1 (step 22.5.5 checklist (d): the guessing baseline D11f, the first grade's levels, `wrong_answers` without held-back skills, `Explanation.llm_call_id` nullable, Accept clears `checker`) |
| v2.53 | 2026-10-25 | Minor, teacher: step 22.5.5 checklist (d) and R22.5.5.12 (guessing baseline D11f; the verifier's blocker and findings) |
| v2.52.1 | 2026-10-25 | Patch: step 22.5.5 verifier notes and tracker row (❌ R22.5.5.3, R22.5.5.5) |
| v2.52 | 2026-10-25 | Minor, teacher: step 22.5.5 checklist (c) and R22.5.5.11 (clicking a student opens the skills view in the main panel) |
| v2.51.2 | 2026-10-24 | Patch: "Based on" → PRD v8.8, data-model v1.24, llm-design v4.45 (step 22.5.5a: checker's answer, date taken, levels, trajectory weak points, the student's skills); Appendix A: `AnswerKey.checker`, `Attempt.taken_on`, `ExtractInput.taken_on`, `WeakPoint` label/level/held_back; the difficulty-notes classes removed (v1.23) |
| v2.51.1 | 2026-10-24 | Patch: R22.5.5.3 counts 58 grammar skills (`grammar.txt` TOTAL), not 120 |
| v2.51 | 2026-10-24 | Minor, teacher: step 22.5.5 (checker's answer on hover; weak points over time, basics first) gets its checklist and requirements (D11, D11a–e; Models tab descriptions on hover) |
| v2.50.4 | 2026-10-24 | Patch: step 22.5.4 verified ✅ at 6ae9c97 (R22.5.4.1–R22.5.4.9, S1–S7 and headless E2E pass); verifier notes |
| v2.50.3 | 2026-10-24 | Patch: "Based on" → llm-design v4.44 (step 22.5.4a item 7: tagging once per graded section) |
| v2.50.2 | 2026-10-24 | Patch: Appendix C.2 without the removed `difficulty_notes` node (step 22.5.4); the step 18 rows that name it stay as dated history |
| v2.50.1 | 2026-10-24 | Patch: "Based on" → PRD v8.7, data-model v1.23, llm-design v4.43 (step 22.5.4a: roles, grading prompts, difficulty notes dropped) |
| v2.50 | 2026-10-24 | Minor: step 22.5.4 (grading calls) gets its checklist and requirements (D10: drop the stored difficulty notes) |
| v2.49.4 | 2026-10-24 | Patch: step 22.5.3 checklist (d) re-verified at d4b71fd (fix 7c85832; R22.5.3.1–R22.5.3.8, S1–S7, headless E2E pass); verifier notes; tracker row ✅ |
| v2.49.3 | 2026-10-24 | Patch: "Based on" → data-model v1.22.3 (step 22.5.3 checklist (d) verifier fix: open Review items relabelled T/F too; swapped labels safe) |
| v2.49.2 | 2026-10-24 | Patch: step 22.5.3 checklist (d) verifier notes (e625707): fails R22.5.3.8 on open Review items; tracker row stays 🔄 |
| v2.49.1 | 2026-10-24 | Patch: "Based on" → data-model v1.22.2 (step 22.5.3 checklist (d): True/False options relabelled T/F); Appendix A `Question` lists `old_options` |
| v2.49 | 2026-10-24 | Minor, teacher (G1): step 22.5.3 gets checklist (d) and R22.5.3.8 (True/False options relabelled T/F) |
| v2.48.5 | 2026-10-24 | Patch: step 22.5.3 verifier notes for the True/False wording fix (accce95, f8369de); tracker row unchanged, awaiting G1 |
| v2.48.4 | 2026-10-24 | Patch: "Based on" → llm-design v4.42.1 (step 22.5.3 verifier notes 1 and 5: wider True/False wording; eval-history `structure_types` not comparable across step 22.5.3) |
| v2.48.3 | 2026-10-24 | Patch: step 22.5.3 verified at 0747252 (R22.5.3.1–R22.5.3.6, S1–S7, headless E2E pass); verifier notes; tracker row built and verified, awaiting G1 (R22.5.3.7) |
| v2.48.2 | 2026-10-24 | Patch: step 22.5.3 fix: the checklist's validator wording (the gap check applies to a `word` question with no cue and no options); "Based on" → data-model v1.22.1 |
| v2.48.1 | 2026-10-24 | Patch: step 22.5.3 docs: Appendix A `Question` has `answer_form`, `context` and `old_type` in place of `type`; Appendix B.5 by answer form (rows 12–13 retired). "Based on" → PRD v8.6, data-model v1.22, llm-design v4.42 |
| v2.48 | 2026-10-23 | Minor: step 22.5.3 (fewer question types) gets its checklist and requirements (D9: built as proposed, signed off after G1) |
| v2.47.2 | 2026-10-23 | Patch: step 22.5.2 re-verified ✅ at 53f15c5 (R22.5.2.1–R22.5.2.12, S1–S7, headless E2E pass); second-pass verifier notes |
| v2.47.1 | 2026-10-23 | Patch: "Based on" → PRD v8.5.1, data-model v1.21.1 (22.5.2c) |
| v2.47 | 2026-10-23 | Minor, teacher: step 22.5.2 gets "Checklist (c)" (AI keys kept on exact matches, the verifier's findings) and R22.5.2.12; its tracker row goes back to 🔨 until a fresh verifier re-checks it |
| v2.46.2 | 2026-10-23 | Patch: steps 22.5.1 and 22.5.2 verified ✅ at 7c79ce4 (R22.5.1.1–R22.5.1.8, R22.5.2.1–R22.5.2.11, S1–S7, headless E2E pass); verifier notes |
| v2.46.1 | 2026-10-23 | Patch: Appendix A `ExtractInput` lists the 22.3.3 and 22.5.2 fields; "Based on" → PRD v8.5, data-model v1.21, llm-design v4.41 (22.5.2a) |
| v2.46 | 2026-10-23 | Minor: step 22.5.2 (settings, series, test text, Extract again) gets its checklist and requirements (D2, D5, D7, D8) |
| v2.45 | 2026-10-23 | Minor, teacher: 22.5.1 sorts numbers in names by value; an exact id match is always the top search row |
| v2.44 | 2026-10-23 | Minor, teacher: step 22.5 has 8 sub-steps instead of 17, with a verifier after 22.5.2, 22.5.3, 22.5.5, 22.5.6 and 22.5.7; step 22 depends on 22.5.8 |
| v2.43 | 2026-10-23 | Minor: step 22.5.1 (moving around and lists) gets its checklist and requirements (D1, D3, D4). "Based on" → llm-design v4.40 |
| v2.42 | 2026-10-23 | Minor, teacher: step 22.5 (fifth review of 0.5.0 plus both quality plans, `docs/initial-plan/phases-testing/step22.5-plan.md`): tracker rows 22.5.1–22.5.17; step 22 depends on 22.5.17; step 22's heading said 22.3.7, now 22.5.17 as the tracker |
| v2.41.1 | 2026-10-23 | Patch: "Based on" → PRD v8.4 |
| v2.41 | 2026-10-20 | Minor: step 22.4.9 (installer 0.5.0) gets its checklist and requirements, as 22.3.8 |
| v2.40 | 2026-10-19 | Minor, teacher (step22.4-plan §6 answers): step 22.4.8 (the answers) gets its checklist and requirements; the installer becomes 22.4.9; step 22 depends on 22.4.9. "Based on" → PRD v8.3, data-model v1.20.1 |
| v2.39 | 2026-10-19 | Minor, teacher (after the 22.4.7 GPU check): the worked example ships for typed files only; R22.4.7.5 puts the photo prompt back to its 0.4.0 text |
| v2.38 | 2026-10-19 | Minor: step 22.4.7 (worked example in the page prompts) gets its checklist and requirements. "Based on" → llm-design v4.38 |
| v2.37 | 2026-10-19 | Minor: step 22.4.6 (report wording and order) gets its checklist and requirements. "Based on" → PRD v8.2, llm-design v4.37 |
| v2.36 | 2026-10-19 | Minor: step 22.4.5 (verifying keys, re-grade) gets its checklist and requirements. "Based on" → PRD v8.1, data-model v1.20, llm-design v4.36 |
| v2.35.1 | 2026-10-19 | Patch: step 22.4.4 notes that D13 v8.0 supersedes the points parts of R8.1.2 and R19.7; "Based on" → data-model v1.19.1 |
| v2.35 | 2026-10-19 | Minor: step 22.4.4 (option letters, points out of 10) gets its checklist and requirements. "Based on" → PRD v8.0, data-model v1.19, llm-design v4.35 |
| v2.34 | 2026-10-19 | Minor: step 22.4.3 (new-thread pickers) gets its checklist and requirements |
| v2.33.1 | 2026-10-19 | Patch: "Based on" → data-model v1.18.1, llm-design v4.34.1 |
| v2.33 | 2026-10-19 | Minor: step 22.4.2 (Settings tabs and the school list) gets its checklist and requirements. "Based on" → PRD v7.3, data-model v1.18, llm-design v4.34 |
| v2.32 | 2026-10-19 | Minor, teacher: step 22.4 (fourth review of 0.4.0, `docs/initial-plan/phases-testing/step22.4-plan.md`): tracker rows 22.4.1–22.4.8; step 22 depends on 22.4.8; step 22.4.1 gets its checklist and requirements |
| v2.31.1 | 2026-10-19 | Patch: 22.3.8 checklist — only migrations 0006–0007 are new in 0.4.0 |
| v2.31 | 2026-10-19 | Minor: the teacher's GPU check (R22.3.6.4) failed; the teacher chose to ship; step 22.3.8 (installer 0.4.0) gets its checklist and requirements |
| v2.30 | 2026-10-18 | Minor, teacher: step 22.3.7 (edit occasions) gets its checklist and requirements; the installer moves to 22.3.8 after the verifier and the teacher's GPU check. "Based on" → PRD v7.2, data-model v1.17, llm-design v4.33 |
| v2.29.1 | 2026-10-18 | Patch: Appendix A `Question` gains `answer_start` (data-model v1.16) |
| v2.29 | 2026-10-18 | Minor, teacher: step 22.3.6 (typed files as text; sentence openings, decision D6) gets its checklist and requirements, with a teacher GPU check before the installer. "Based on" → PRD v7.1, data-model v1.16, llm-design v4.32 |
| v2.28 | 2026-10-18 | Minor, teacher: step 22.3.5 (models) gets its checklist and requirements. "Based on" → PRD v7.0 (D7), llm-design v4.31 |
| v2.27.1 | 2026-10-17 | Patch: "Based on" → data-model v1.15.1; the teacher chose to make extraction keep a rewrite's printed opening words in this round (22.3.6, with one GPU run) |
| v2.27 | 2026-10-17 | Minor: step 22.3.4 (sentence keys) gets its checklist and requirements. "Based on" → data-model v1.15 |
| v2.26.1 | 2026-10-17 | Patch: R22.3.3.2 copies only filled fields; R22.3.3.3 accepts the fake-Ollama graph test. "Based on" → data-model v1.14.1 |
| v2.26 | 2026-10-17 | Minor: step 22.3.3 (delete a student, series details) gets its checklist and requirements. "Based on" → PRD v6.4, data-model v1.14, llm-design v4.30 |
| v2.25.1 | 2026-10-17 | Patch, teacher and orchestrator: 22.3.2 — Grade is disabled only without student answers (grading writes AI keys); "Make the key" on a test-only thread; Extract again through `POST /threads/{id}/extract-again`; no student on a test-only thread. "Based on" → PRD v6.3.1, llm-design v4.29 |
| v2.25 | 2026-10-17 | Minor: step 22.3.2 (straight to work) gets its checklist and requirements. "Based on" → PRD v6.3 |
| v2.24.1 | 2026-10-17 | Patch: R22.3.1.2 — the rotate button's accessible name names its page |
| v2.24 | 2026-10-17 | Minor, teacher: step 22.3 (the teacher's third review of 0.3.0, sub-steps 22.3.1–22.3.7) before step 22; 22.3.1 gets its checklist and requirements |
| v2.23.3 | 2026-10-15 | Patch: step 22.2.7 verified at 8ee6947: R22.2.7.1–R22.2.7.4 and the rest of R22.2.7.5 pass; 🔄 pending R22.2.7.5 `E2E_SHELL --release` (started by the user); new minor F7 (focus after "Use automatic name" and after a chip edit) and F8 (old box text in the release notes' ERH-change list) |
| v2.23.2 | 2026-10-15 | Patch: "Based on" → data-model v1.13.2 |
| v2.23.1 | 2026-10-15 | Patch: "Based on" → data-model v1.13.1 |
| v2.23 | 2026-10-15 | Minor, teacher: step 22.2.7 (the answers to the parked questions, F5, 0.3.0 rebuilt) before step 22. "Based on" → PRD v6.2, data-model v1.13, llm-design v4.28 |
| v2.22.2 | 2026-10-15 | Patch: steps 22.2.2–22.2.6 re-verified at cd67a3c after the F1, F3, F4 fixes: 22.2.2–22.2.5 ✅; 22.2.6 🔄 pending R22.2.6.3; new minor F5 (focus after deleting the last thread) and F6 (0.3.0 build bullet out of date) |
| v2.22.1 | 2026-10-14 | Patch: steps 22.2.1–22.2.6 verified together: 22.2.1 ✅; 22.2.2–22.2.6 🔄 (S7: `vitest run` exits 1 on 19 unhandled rejections from the close guard); 22.2.6 also pending R22.2.6.3 |
| v2.22 | 2026-10-14 | Minor: step 22.2.6 (installer 0.3.0) gets its checklist and requirements |
| v2.21 | 2026-10-14 | Minor: step 22.2.5 (key photos, version, uninstall) gets its checklist and requirements. "Based on" → PRD v6.1, data-model v1.12, llm-design v4.27 |
| v2.20 | 2026-10-14 | Minor, teacher: step 22.2.4 (printed numbers, test text additions, Format help, test details and name) gets its checklist and requirements. "Based on" → PRD v6.0 (D10), data-model v1.11 |
| v2.19.1 | 2026-10-14 | Patch: "Based on" → data-model v1.10.1 |
| v2.19 | 2026-10-14 | Minor: step 22.2.3 (delete, Students tab) gets its checklist and requirements. "Based on" → PRD v5.3, data-model v1.10, llm-design v4.26 |
| v2.18 | 2026-10-14 | Minor: step 22.2.2 (moving around and safety) gets its checklist and requirements. "Based on" → PRD v5.2, data-model v1.9.3, llm-design v4.25 |
| v2.17 | 2026-10-14 | Minor, teacher: step 22.2 (the teacher's second review of 0.2.0, sub-steps 22.2.1–22.2.6) before step 22; 22.2.1 gets its checklist and requirements. One verifier checks 22.2.1–22.2.6 together. "Based on" → PRD v5.1, llm-design v4.24 |
| v2.16 | 2026-10-14 | Minor: step 22.1.7 (new installer, version 0.2.0) gets its checklist and requirements; R22.1.7.3 (`E2E_SHELL --release`) runs in the final verification after the teacher is warned |
| v2.15 | 2026-10-14 | Minor, teacher: step 22.1.6 (DOCX; decision 5 = now; saved into the app folder only) gets its checklist and requirements. "Based on" → PRD v5.0 (D4), llm-design v4.23 |
| v2.14.1 | 2026-10-14 | Patch: R13.1 is superseded by R22.1.5.7 (no Review item in the sidebar). Process, teacher: steps 22.1.5–22.1.7 are verified together by one fresh verifier after all three are built. "Based on" → data-model v1.9.2, llm-design v4.22.1 |
| v2.14 | 2026-10-13 | Minor, teacher: step 22.1.5 (decisions 4a: no Review tab; 4b: the test as one free-text page) gets its checklist and requirements. "Based on" → PRD v4.14 (D27), data-model v1.9, llm-design v4.22 |
| v2.13 | 2026-10-13 | Minor, teacher: step 22.1.4 (workspace view, decision 3 = B) gets its checklist and requirements. "Based on" → PRD v4.13, llm-design v4.21 |
| v2.12.1 | 2026-10-13 | Patch: "Based on" → PRD v4.12.1, llm-design v4.20.1 (`unit` on `run.progress`, found in step 22.1.3) |
| v2.12 | 2026-10-13 | Minor: step 22.1.3 (progress bar) gets its checklist and requirements. "Based on" → PRD v4.12, llm-design v4.20 |
| v2.11 | 2026-10-13 | Minor, teacher: step 22.1.2 (green theme) gets its checklist and requirements after decision 2 (a light green, shades adjusted later). The teacher tests and merges the 22.1 sub-steps together at the end, so each sub-step branches from the previous one. "Based on" → PRD v4.11 |
| v2.10 | 2026-10-13 | Minor, teacher: the step 22.1 sub-steps (22.1.1–22.1.7) come **before** the step 22 acceptance, which runs once on the final build (step 22 now depends on 22.1.7). Tracker rows and the Step 22.1 section; 22.1.1 (small fixes) has its checklist and requirements, the others get theirs before they start. "Based on" → data-model v1.8, llm-design v4.19 |
| v2.9 | 2026-10-13 | Minor, teacher: a Scope row (this plan is steps 1–22 incl. 22.1 sub-steps; post-launch work gets its own content-named plan file); R22.3 reworded to match |
| v2.8.18 | 2026-10-13 | Patch: phase documents moved to `docs/initial-plan/phases-testing/` (m1-report, m2-report; step 22's offline-check and acceptance-report) |
| v2.8.17 | 2026-10-12 | Patch: "Based on" → PRD v4.10.2 (WebView2 stays after uninstall) |
| v2.8.16 | 2026-10-12 | Patch: step 21 re-verified ✅ at f828971 (the uninstaller always deletes the install-folder key; R21.1–R21.5, S1–S7 pass) |
| v2.8.15 | 2026-10-12 | Patch: "Based on" → PRD v4.10.1 (install-folder registry record) |
| v2.8.14 | 2026-10-12 | Patch: step 21 verified 🔄 at 281b140 (R21.1–R21.5 pass; the installer writes and keeps a registry key that PRD §11 v4.10 does not list); step 21 checklist ticked |
| v2.8.13 | 2026-10-12 | Patch: "Based on" → PRD v4.10 (installer exceptions to the one app folder) and llm-design v4.18 (frozen sidecar launch, `/system/status` fields) |
| v2.8.12 | 2026-10-12 | Patch: M2 ✅ at 918964c (teacher's sign-off of the M2 report); M2 checklist ticked |
| v2.8.11 | 2026-10-12 | Patch: "Based on" → llm-design v4.17.2 (explain glosses and sentence meaning) |
| v2.8.10 | 2026-10-12 | Patch: "Based on" → llm-design v4.17.1 (explain key-word gloss) |
| v2.8.9 | 2026-10-12 | Patch: "Based on" → llm-design v4.17; R17.2.4 thinking off for every task (teacher, after M2) |
| v2.8.8 | 2026-10-12 | Patch: "Based on" → PRD v4.9 (§14 level-adapted explanations) |
| v2.8.7 | 2026-10-11 | Patch: R-M1.4 allows `tiles=off` (speed bundle 1 turned tiles off); step 21 / R21.4: thresholds are the `ExtractThresholds` defaults (no TOML setting) |
| v2.8.6 | 2026-10-11 | Patch: "Based on" → llm-design v4.16 (M1 listening safety net) |
| v2.8.5 | 2026-10-10 | Patch: "Based on" → llm-design v4.15.1 |
| v2.8.4 | 2026-10-10 | Patch: "Based on" → PRD v4.8, llm-design v4.15 (D26: typed files skip answer reading; built and measured in M1) |
| v2.8.3 | 2026-10-10 | Patch: "Based on" → llm-design v4.14 (M1 speed bundle 1: tiles switch, per-role capped-output retry) |
| v2.8.2 | 2026-10-09 | Patch: "Based on" → data-model v1.7, llm-design v4.13 (long DOCX text split into pages; transcribe output cap 8192); step 3's DOCX wording |
| v2.8.1 | 2026-10-08 | Patch: "Based on" → llm-design v4.12 (M1 bug B1); Appendix D.1: every request body carries `truncate: false` |
| v2.8 | 2026-10-06 | Minor, teacher decision D25 (unreadable text): "Based on" → PRD v4.7, data-model v1.6, llm-design v4.11. New **step 21a** (`???` in the prompts and answer reading, the `unreadable_text` Review kind, its Review panel editor); step 21 depends on it. Appendix D.2a (the `???` phrases), Appendix E rows for `unreadable_text`, Appendix A and F notes. The photo-check "retake" warning is deferred (PRD §2), not a step |
| v2.7.2 | 2026-10-05 | Patch: R19.1 uses an S1-like synthetic extract seeded to B.6 (the recorded S1 totals 8.5 points; found in step 19) |
| v2.7.1 | 2026-10-05 | Patch: "Based on" → data-model v1.5.3 (`value_norm` comment) |
| v2.7 | 2026-10-05 | Minor, teacher decisions in step 17: `sections.txt` adds PRON-ED and PRON-S (-ed and -s endings); B.7: a blank or missing answer does not trigger `verify_needed` |
| v2.6.2 | 2026-10-04 | Patch: "Based on" → llm-design v4.10 (`picture_paths`, step 16) |
| v2.6.1 | 2026-10-02 | Patch: "Based on" → llm-design v4.9 (CORS) |
| v2.6 | 2026-10-01 | Minor: "Based on" → llm-design v4.8 (`run.discarded` event, step 12) |
| v2.5.2 | 2026-09-30 | Patch: "Based on" → data-model v1.5.2 |
| v2.5.1 | 2026-09-29 | Patch: "Based on" → data-model v1.5.1 |
| v2.5 | 2026-09-29 | Minor: "Based on" → data-model v1.5; Appendix A `File` gains `original_name` (R1.1, R2.1 follow it; step 9 fixes the step 1–3 code and tests) |
| v2.4.2 | 2026-09-29 | Patch: R8.1.9 uses a synthetic student name instead of the worked example's real one (student data stays out of git) |
| v2.4.1 | 2026-09-29 | Patch: "Based on" → llm-design v4.7.1; step 5 checklist ticked (the teacher's items are done: sign-off commits 48844f5, 01b5b2f) |
| v2.4 | 2026-09-29 | Minor: "Based on" → PRD v4.6, data-model v1.4, llm-design v4.7. Step 14 spawn env adds flash attention + q8_0 KV (Phase 0); step 20 adds automatic log retention (R20.8) |
| v2.3 | 2026-09-29 | Minor: "Based on" → PRD v4.5, llm-design v4.6 (reasoning placeholder `qwen3.5:4b`). Phase-0 files move to `docs/initial-plan/phases-testing/` (teacher's choice): the report and the live output (R5.1, R5.2) |
| v2.2 | 2026-09-28 | Minor: "Based on" → data-model v1.3, llm-design v4.5. Step 10 adds the `reviewed` → `graded`/`extracted` rule (checklist + R10.4); `map_key` reads `key_raw` as an ordered list (B.3) |
| v2.1.1 | 2026-09-28 | Patch: step 0's .gitignore list adds `__pycache__/` (Python bytecode from test runs would otherwise show as untracked) |
| v2.1 | 2026-09-28 | Minor, after the whole-docs audit: |
| | | • Fixes: R0.1 "deselected"; S4 matches model tags only; `cd sidecar` in S3–S6. |
| | | • Step 5 records the phase-0 cassettes (R5.4) and R6.1 needs ≥ 3; 8.2 and 17.2 depend on step 4. |
| | | • R19.1 uses a seeded synthetic cassette; R19.3 worded like R18.5. |
| | | • Explicit B.3 key map; B.1 per-section points + B.1b writing variant; B.4 cap = threshold − 0.01; B.5 rows 11–16; B.8 failure rules (R17.1.6). |
| | | • Appendix E: accept rows for every kind, `merge_unaligned`, graded-only follow-ups. |
| | | • Text pages (R3.3); query token (R12.2); restart listing + `run.interrupted` (R12.8); FTS prefix (R2.4); `value_norm` (R17.1.5); other-Ollama detector (R4.9). |
| | | • One app folder: R14.1, **R14.5 (nothing written to AppData)**, and R20.7 becomes portability (no "move data folder"). |
| | | • Reference fixes. |
| v2.0.1 | 2026-09-28 | Patch: P1 answered (PRD v4.3), so the open-question marker is removed from step 15 and the traceability table. R15.6 is unchanged |
| v2.0 | 2026-09-28 | After an independent audit: |
| | | • **Order fixes:** merge and the Review service come before the API (step 10); the file store now depends on the database; the frontend and the Tauri shell are sequential; LLM output schemas move into step 1; the checkpointer check moves into the runtime step. |
| | | • **Measurement tracks M1/M2** (the human-gated quality and model-choice work) run in parallel and only gate packaging and acceptance. |
| | | • **Cassette policy** (recorded, scrubbed, committed) and `erh serve --replay`. |
| | | • **Standing requirements** and a regression rule. |
| | | • **Sign-off commits** for human gates; ⛔ blocked / ⚠ waived statuses; branch flow; verifier setup. |
| | | • **Plan-owned expected values** (appendices A–E) replace self-certifying checks. |
| | | • **Missing features added:** key print, S2 end-to-end, PDF/DOCX input, students, battery and lid warnings, sleep retry, Settings, the full API route inventory (llm-design v4.3), a per-Review-kind resolution table. |
| | | • **Corrected checks:** R5.2 value, CSP, the external-URL check, the offline check. |
| | | • Traceability by requirement ID. |

---

## 1. How to use this plan

### 1.1 Steps, dependencies, tracks
- **`Depends on` is authoritative.** A step may start when every step it depends on is ✅. Numbers only suggest the usual order.
- **Sub-steps** `N.1`, `N.2` have disjoint files and no dependency on each other, so they *may* run in parallel. Doing them one after another is preferred.
- **Measurement tracks M1 and M2** are human-gated (👤) quality work. They run alongside the build track and only gate the late steps that ship their results (steps 21 and 22).

### 1.2 What every step contains
- **Depends on** / **PRD:** the prerequisites, and the decisions and sections it implements.
- **Checklist:** the work items, ticked by the implementer. A ticked checklist is not "done".
- **Requirements** `R<step>.<n>`: each one names **how to check it** (a command, a file, or a query). 👤 marks a teacher gate; its evidence is a sign-off commit (§1.4).
- **Verifier notes:** filled in only by the verifier.

### 1.3 Finishing a step
1. The implementer works on the branch `step/<id>-<slug>`, ticks the checklist, and commits.
2. A **fresh verifier agent** (no implementation context), on a clean checkout of that commit, with the setup in §1.6:
   - runs the **standing requirements** (§1.5);
   - runs every requirement of the step;
   - checks 👤 evidence via `git log --grep "^👤 sign-off:" -- <artifact>`.
3. **All pass** → the verifier sets the tracker row to ✅ (date, commit, "agent") and commits that tracker edit **on the step branch**. **Any failure** → the row stays 🔄 and the failures go under the step's **Verifier notes**.
4. The teacher merges the step branch into `main` (a user-level `branch-guard` hook blocks direct commits to `main`).

### 1.4 Human gates 👤
- **Agents never write teacher fields** (`verified_by`, waiver signatures, acceptance results). The teacher writes them in a commit whose message starts with `👤 sign-off:` and which touches the artifact.
- **A gate that cannot pass** → the row becomes ⛔ blocked. It is unblocked by exactly one of:
  - (a) a waiver file `docs/initial-plan/waivers/<step>.md` listing the shortfall, committed by the teacher with `👤 sign-off:` → the row becomes ⚠ waived (it counts as finished);
  - (b) a new plan version that adds remediation steps.

### 1.5 Standing requirements (checked at **every** verification, from the step where each first applies)
| ID | Requirement | From step |
|---|---|---|
| S1 | `TEST` passes | 0 |
| S2 | `LINT` passes | 0 |
| S3 | Generated artifacts are current: `cd sidecar && uv run erh schema export && git diff --exit-code schema` | 1 |
| S4 | Model **tags** only in config: `grep -rnE "numind/|qwen3" sidecar/src` matches only `src/erh/llm/defaults.py` (the adapter name `nuextract` is allowed) | 4 |
| S5 | Cassettes are scrubbed: `cd sidecar && uv run erh scrub --check tests/cassettes` exits 0 | 4 |
| S6 | The OpenAPI export is current: `cd sidecar && uv run erh openapi export && git diff --exit-code schema/openapi.json` | 12 |
| S7 | `APP_TEST` passes, and the TS types are current (`npm run gen:types` → `git diff --exit-code app/src/gen`) | 13 |

**Regression rule:** if a verification finds that a requirement of an earlier ✅ step now fails, that step's row goes back to 🔄 as well.

**Doc sync rule:** whenever a companion document's version changes, this plan's "Based on" line is updated in the same commit, and the verifier re-runs the requirements of the steps that cite the changed sections.

### 1.6 Verifier setup
Windows 11; `uv` with Python 3.12; Node 20+; Rust stable with the Tauri 2 prerequisites (WebView2, MSVC); `tauri-driver` + `msedgedriver` for the E2E tests that need the real shell. **No GPU or Ollama is needed**: live checks are 👤 and their evidence is committed.

### 1.7 Cassette policy (recorded model responses)
- **What:** a cassette is one recorded model call: the task, the **match key**, the response text, the thinking text, the logprobs, and the status. **No images are stored.** Tests use synthetic stand-in page images (blank PNGs of the same size) committed next to the cassette.
- **Match key** = the task + a digest of the task inputs (page number, question-ID list, schema name). **Not** the prompt hash and **not** the model tag, so prompt tuning (M1) and a model change (M2) don't break replay.
- **Source:**
  - **Recorded** by the teacher on the laptop, with `erh record` during live runs (step 9, step 18), 👤.
  - **Synthetic**, hand-written for edge cases (invalid JSON, validator retry, cut-off streams).
- **Scrubbed** with `erh scrub`: student names and classes read from paper become `Học Sinh A` / `8X1`. The printed test text stays, since it is published exam material.
- **Committed** under `sidecar/tests/cassettes/<scenario>/`. S5 checks the scrubbing.

### 1.8 Standard commands
| Name | Command |
|---|---|
| `TEST` | `cd sidecar && uv run pytest -m "not live" -q` |
| `LINT` | `cd sidecar && uv run ruff check . && uv run ruff format --check . && uv run mypy src` |
| `LIVE` | `cd sidecar && uv run pytest -m live -q` (Ollama + models; teacher's laptop) |
| `APP_TEST` | `cd app && npm test -- --run && npm run lint && npm run typecheck` |
| `E2E` | `cd app && npm run e2e` (Playwright on the web build + `erh serve --replay`) |
| `E2E_SHELL` | `cd app && npm run e2e:shell` (WebDriver via `tauri-driver` on the real Tauri app + replay sidecar) |
| `TAURI_BUILD` | `cd app && npm run tauri build` |

---

## 2. Progress tracker

| Step | Title | Depends on | Status | Date | Commit | Verified by |
|---|---|---|---|---|---|---|
| 0 | Repository & toolchain | – | ✅ | 2026-09-28 | d3e1b4e | agent |
| 1 | Domain classes & LLM output schemas | 0 | ✅ | 2026-09-28 | 050461b | agent |
| 2 | Database layer | 1 | ✅ | 2026-09-28 | 3b6f765 | agent |
| 3 | File store & document input | 2 | ✅ | 2026-09-28 | c193dcf | agent |
| 4 | Ollama client, recorder, cassettes | 2 | ✅ | 2026-09-28 | 72f1dca | agent |
| 5 | Phase 0 live checks 👤 | 4 | ✅ | 2026-09-29 | b7fdf8a | agent |
| 6 | Logprob confidence | 5 | ✅ | 2026-09-29 | 1b44791 | agent |
| 7 | Run runtime | 4 | ✅ | 2026-09-29 | 7eb660c | agent |
| 8.1 | Extraction domain logic | 1 | ✅ | 2026-09-29 | dc32a5b | agent |
| 8.2 | Extraction prompts | 1, 4 | ✅ | 2026-09-29 | 2e9c508 | agent |
| 9 | Extraction graph + `erh run` (+ recording 👤) | 3, 6, 7, 8.1, 8.2 | ✅ | 2026-09-29 | 3d9e994 | agent |
| 10 | Review resolution & merge service | 9 | ✅ | 2026-09-30 | bffb77d | agent |
| 11 | Fixtures & eval harness 👤 | 9 | ✅ | 2026-10-01 | 4c8fb89 | agent |
| 12 | Sidecar API, SSE, `erh serve --replay` | 10 | ✅ | 2026-10-01 | f0bdc34 | agent |
| 13 | Frontend skeleton | 12 | ✅ | 2026-10-02 | c1e87e1 | agent |
| 14 | Tauri shell | 13 | ✅ | 2026-10-03 | 0f44dd1 | agent |
| 15 | Threads, photo check, running indicator | 14 | ✅ | 2026-10-04 | 777b768 | agent |
| 16 | Cards, panels, Tests tab, extraction Review UI | 15 | ✅ | 2026-10-05 | 340f597 | agent |
| 17.1 | Grading domain logic | 10 | ✅ | 2026-10-05 | 5d59d40 | agent |
| 17.2 | Grading prompts | 1, 4 | ✅ | 2026-10-05 | 4d08c75 | agent |
| 18 | Grade graph + `erh grade` (+ recording 👤) | 17.1, 17.2 | ✅ | 2026-10-05 | bd5299a | agent |
| 19 | Grade & Review UI | 16, 18 | ✅ | 2026-10-05 | 277bd37 | agent |
| 20 | Settings, backup, maintenance | 16 | ✅ | 2026-10-05 | 83ef695 | agent |
| 21a | Unreadable text (D25) | 9, 10, 16 | ✅ | 2026-10-06 | 2ccc3b7 | agent |
| 21 | Packaging & first run | 19, 20, 21a, M1, M2 | ✅ | 2026-10-12 | f828971 | agent |
| 22.1.1 | App review: small fixes | 21 | ✅ | 2026-10-13 | b58eebd | agent |
| 22.1.2 | App review: green theme | 22.1.1 | ✅ | 2026-10-13 | 0e90b89 | agent |
| 22.1.3 | App review: progress bar | 22.1.2 | ✅ | 2026-10-13 | cd112ad | agent |
| 22.1.4 | App review: layout and photos | 22.1.2 | ✅ | 2026-10-13 | fe2889d | agent |
| 22.1.5 | App review: document-style editing, Review under each test | 22.1.4 | ✅ | 2026-10-14 | 82b1475 | agent |
| 22.1.6 | App review: save as DOCX | 22.1.5 | ✅ | 2026-10-14 | 82b1475 | agent |
| 22.1.7 | App review: new installer | 22.1.3, 22.1.6 | ✅ | 2026-10-14 | 82b1475 | |
| 22.2.1 | Second review: words on screen | 22.1.7 | ✅ | 2026-10-14 | 6afc3ba | agent |
| 22.2.2 | Second review: moving around and safety | 22.2.1 | ✅ | 2026-10-15 | cf9c12d | agent |
| 22.2.3 | Second review: delete, Students tab | 22.2.2 | ✅ | 2026-10-15 | 0b54aa9 | agent |
| 22.2.4 | Second review: test page, numbers, test details | 22.2.3 | ✅ | 2026-10-15 | f13d9aa | agent |
| 22.2.5 | Second review: key photos, version, uninstall | 22.2.4 | ✅ | 2026-10-15 | 08c76ad | agent |
| 22.2.6 | Second review: installer 0.3.0 | 22.2.5 | ✅ | 2026-10-15 | cd67a3c | |
| 22.2.7 | Second review: the teacher's answers, 0.3.0 rebuilt | 22.2.6 | ✅ | | | |
| 22.3.1 | Third review: photo check and small fixes | 22.2.7 | ✅ | 2026-10-18 | 4c6f768 | agent |
| 22.3.2 | Third review: straight to work | 22.3.1 | ✅ | 2026-10-18 | 0ea6bc6 | agent |
| 22.3.3 | Third review: delete students, series details | 22.3.2 | ✅ | 2026-10-18 | 361062a | agent |
| 22.3.4 | Third review: sentence keys | 22.3.3 | ✅ | 2026-10-18 | e5fad00 | agent |
| 22.3.5 | Third review: models | 22.3.4 | ✅ | 2026-10-18 | 38f49b5 | agent |
| 22.3.6 | Third review: typed files as text | 22.3.5 | ⚠ waived (`docs/initial-plan/waivers/22.3.6.md`) | 2026-10-18 | 45d4932 | agent |
| 22.3.7 | Third review: edit occasions | 22.3.6 | ✅ | 2026-10-18 | e98923b | agent |
| 22.3.8 | Third review: installer 0.4.0 | 22.3.7 | ✅ | 2026-10-19 | 74f8ea1 | agent |
| 22.4.1 | Fourth review: screen fixes | 22.3.8 | ✅ | 2026-10-19 | 96ff9cd | agent |
| 22.4.2 | Fourth review: Settings tabs, schools | 22.4.1 | ✅ | 2026-10-19 | 5be30cb | agent |
| 22.4.3 | Fourth review: new-thread pickers | 22.4.2 | ✅ | 2026-10-19 | 4bd6dfe | agent |
| 22.4.4 | Fourth review: option check, points out of 10 | 22.4.3 | ✅ | 2026-10-19 | 5747af9 | agent |
| 22.4.5 | Fourth review: verifying keys, re-grade | 22.4.4 | ✅ | 2026-10-19 | 53668a8 | agent |
| 22.4.6 | Fourth review: report | 22.4.5 | ✅ | 2026-10-19 | 771ece7 | agent |
| 22.4.7 | Fourth review: worked example in the page prompts | 22.4.6 | ✅ R22.4.7.4 run and accepted by the teacher (step22.4-plan §7): typed files ship with the example; photos keep the 0.4.0 prompt | 2026-10-19 | 7a53991 | agent |
| 22.4.8 | Fourth review: the teacher's answers | 22.4.7 | ✅ | 2026-10-19 | 4718a5a | agent |
| 22.4.9 | Fourth review: installer 0.5.0 | 22.4.8 | ✅ | 2026-10-20 | 0266c79 | agent |
| 22.5.1 | Fifth review: moving around and lists | 22.4.9 | ✅ | 2026-10-23 | 7c79ce4 | agent |
| 22.5.2 | Fifth review: settings, series, test text, extract again | 22.5.1 | ✅ | 2026-10-23 | 53f15c5 | agent |
| 22.5.3 | Fifth review: fewer question types 👤 GPU | 22.5.2 | ✅ | 2026-10-24 | d4b71fd | agent |
| 22.5.4 | Fifth review: grading calls | 22.5.3 | ✅ | 2026-10-24 | 6ae9c97 | agent |
| 22.5.5 | Fifth review: the checker's answer, weak points over time 👤 GPU | 22.5.4 | ✅ | 2026-10-25 | c754e2f | agent |
| 22.5.6 | Fifth review: typed pages, reading student answers and keys 👤 GPU | 22.5.5 | ✅ | 2026-10-26 | 8ec134d | agent |
| 22.5.7 | Fifth review: photos, the re-read, answer-number errors, model trial 👤 GPU | 22.5.6 | ✅ (R22.5.7.1–5 and R22.5.7.7 verified; G4 the teacher's choice, step22.5-plan §5) | 2026-10-26 | e912074 | |
| 22.5.8 | Fifth review: installer 0.6.0 | 22.5.7 | ✅ (R22.5.8.1–2, 7–9 verified; R22.5.8.5 the user; R22.5.8.3, 4, 6 orchestrator, the teacher's choice) | 2026-10-30 | 35f31a3 | |
| 22.6.1 | Sixth look: answer boxes, repeated options, the format example (photos) | 22.5.8 | ✅ | 2026-10-31 | bc97d83 | agent |
| 22.6.2 | Sixth look: blank papers, empty answers | 22.6.1 | ✅ | 2026-10-30 | 5a6d268 | agent |
| 22.6.3 | Sixth look: the checker may be unsure | 22.6.2 | ✅ | 2026-10-30 | 5a6d268 | agent |
| 22.6.4 | Sixth look: the key after every extraction | 22.6.3 | ✅ | 2026-10-30 | 5a6d268 | agent |
| 22.6.5 | Sixth look: two photo ways without qwen | 22.6.4 | ✅ | 2026-10-30 | 5a6d268 | agent |
| 22.6.6 | Sixth look: verifier and the three-way photo check 👤 GPU | 22.6.5 | ✅ ((a) R22.6.6.1, 3–6 verified; (b) the teacher's GPU check 2026-11-01, step22.6-plan §5; (c) the teacher chose 2b code, D16) | 2026-11-01 | f6c250e | agent |
| 22.6.7 | Sixth look: the logo | 22.6.6 | ✅ (verified by the 22.6.8 (a) verifier; seen in the 0.6.1 build at R22.6.8.5) | 2026-11-02 | 0e277bb | agent |
| 22.6.8 | Sixth look: installer 0.6.1 | 22.6.7 | ✅ (R22.6.8.1 verified; R22.6.8.5 the user; R22.6.8.2–4 orchestrator, the teacher's choice) | 2026-11-02 | 6bbbc2c | |
| 22 | Offline check & acceptance 👤 | 21, 22.6.8 | ⚠ waived (`docs/initial-plan/waivers/22.md`) | 2026-11-02 | | |
| M1 | Extraction quality track 👤 | 11 | ⚠ | 2026-10-11 | 98d50ec | agent |
| M2 | Reasoning model choice track 👤 | 11, 18 | ✅ | 2026-10-12 | 918964c | agent |

Legend: ⬜ not started · 🔄 in progress or failed verification · ✅ verified · ⛔ blocked · ⚠ waived (§1.4)

### Open questions for the teacher
None. P1 (D18: dropping into a thread that has already run) was answered: **blocked, with a "Start a new thread" button** (PRD v4.3).

---

## Step 0 — Repository & toolchain
**Depends on:** – · **PRD:** §11, §13

**Checklist**
- [ ] The teacher merges `docs/prd-v4` into `main` (👤). All later work happens on step branches.
- [x] `sidecar/`: a Python 3.12 **uv** project (`pyproject.toml`, `uv.lock`) with the llm-design §2 layout (`src/erh/{api,graphs,llm,prompts,store,domain}`, `src/erh/cli.py`, `tests/{unit,replay,live,cassettes}`).
- [x] Dev dependencies: pytest, pytest-asyncio, ruff, mypy. Runtime dependencies are pinned when first used.
- [x] A pytest marker `live`, skipped by default, plus one placeholder live test.
- [x] A CLI entry point `erh --version`.
- [x] `.gitignore` gains exactly: `sidecar/.venv/`, `app/node_modules/`, `app/src-tauri/target/`, `app/dist/`, `.devdata/` (the development data folder, `erh serve --data .devdata`), `__pycache__/`.
- [x] A root `README.md` with the purpose, the standard commands (§1.8), and links to the PRD and this plan.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R0.1 | `TEST` passes and reports ≥ 1 **deselected** (live) test. | Run `TEST`; read the summary line |
| R0.2 | `uv run erh --version` prints a semver string. | Run it in `sidecar/` |
| R0.3 | The directories listed in the checklist exist. | `ls` |
| R0.4 | `uv sync --frozen` succeeds on a clean clone. | Run it |
| R0.5 | `.gitignore` contains every entry listed in the checklist. | `grep` each entry |
| R0.6 | `README.md` contains the §1.8 command table and links to `docs/PRD.md` and `docs/initial-plan/plan.md`. | Read it |
| R0.7 | `main` contains the planning docs (PRD, data-model, llm-design, plan). | `git log main --oneline -- docs/` |

**Verifier notes:** Fresh clone at d3e1b4e (uv 0.12.19, CPython 3.12.14). S1/R0.1 pass: `2 passed, 1 deselected`; `git status --short` empty afterwards. S2 pass: ruff "All checks passed!", format "11 files already formatted", mypy "no issues found in 9 source files". R0.2 pass: `0.1.0`. R0.3 pass: all listed dirs/files exist. R0.4 pass: `uv sync --frozen` on a clone with no `.venv` exits 0. R0.5 pass: all six entries present as exact lines. R0.6 pass: README §1.8 table identical to the plan's; links to `docs/PRD.md` and `docs/initial-plan/plan.md`. R0.7 pass: `main` has PRD, data-model, llm-design and plan (latest docs commit 9277a71).

---

## Step 1 — Domain classes & LLM output schemas
**Depends on:** 0 · **PRD:** §5–7 → data-model §2; llm-design §4–5

**Checklist**
- [x] Pydantic classes for data-model §2.1–2.9, matching **Appendix A** exactly (class names, field names, literal sets).
- [x] **LLM output schemas** per task (used by 8.x and 17.x): `ReadKeyOut`, `ReadHeaderOut`, `TranscribeOut`, `ReadAnswersOut`, `AiKeyOut`, `VerifyKeyOut`, `TagSkillsOut`, `DifficultyOut`, `JudgeOut`, `ExplainOut`, `SummaryOut`.
- [x] `TestMetadata.display_name()` (English).
- [x] `erh schema export` → `sidecar/schema/*.json`, committed.
- [x] Example instances in `tests/unit/examples/`.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R1.1 | The classes and fields equal Appendix A: a test holds Appendix A as a dict literal copied verbatim from the plan and compares it with `model_fields`. | `TEST` |
| R1.2 | Every example round-trips (`model_validate(model_dump()) == original`). | `TEST` |
| R1.3 | `display_name()` for {grade 8, FinalTerm, term 1, test_number "1", variant "K", no school or year} returns exactly `Grade 8 · FinalTerm HK1 · Test 1 · (K)`. | `TEST` |
| R1.4 | Answer-reading schemas: an MCQ value accepts only `A`,`B`,`C`,`D`,`null`; a T/F value only `T`,`F`,`null` (validation errors asserted for "E" and "Y"). | `TEST` |
| R1.5 | All 11 LLM output schemas exist and appear in `sidecar/schema/`. | `ls sidecar/schema` + S3 |

**Verifier notes:** 2026-09-28, fresh clone at 3223db0 (implementation 050461b; 3223db0 is exempt under structure.md rule 0), uv 0.12.19, `uv sync --frozen` OK. **All pass.** Write scope: the first verification (3ecbebc) failed on scope. `sidecar/src/erh/domain/__init__.py` (the schema writer) was not in §6 row 1, although rule 5 (v1.0.1) allowed the writer there. The fix was the orchestrator's structure.md v1.0.2 patch (2a0d3f5), which adds `domain/__init__.py` to row 1. The implementation did not change. Re-check against v1.0.2: every path in `git diff --name-only main..050461b` is in row 1 or in the "every step may also write" list. S1/R0.1: `217 passed, 1 deselected`. S2: ruff clean, format "18 files already formatted", mypy "no issues found in 12 source files". S3: run twice, each `wrote 42 schema files` and `git diff --exit-code schema` exits 0; `git status --short` empty afterwards. A committed stale schema was caught (exit 1). R0.2: `0.1.0`. R1.1: I parsed Appendix A from this plan and compared it with the test literal. All 31 classes are equal, with the same fields in the same order. I compared all 24 `Literal` fields in data-model §2 with the model annotations: 0 mismatches. The 9 working types match §2.9. R1.2: 36 example files, all 36 round-trip, and a completeness test checks them against the class list. R1.3: the expected string is byte-identical to the plan's (U+00B7). R1.4: "E" and "Y" give `literal_error` on `value`, both in `ReadAnswersOut` and in the per-call schema. R1.5: all 11 `*Out.json` files are in `sidecar/schema/` (42 files). Student data: examples use `Học Sinh A`/`8X1`. The only `Ngô` hit is the negative guard `assert "Ngô Thị" not in text`. The implementer changed only checklist ticks in plan.md.

---

## Step 2 — Database layer
**Depends on:** 1 · **PRD:** data-model §3–5

**Checklist**
- [x] `store/migrations/0001_init.sql` = data-model §3–4 (tables, indexes, the FTS table, the view).
- [x] A migration runner; every connection sets `foreign_keys=ON` and `journal_mode=WAL`.
- [x] Repositories for every table, **including students** (create, find by `name_search`).
- [x] `write_test_meta()` (data-model §5.1).
- [x] Guarded key upsert and deleting that question's explanations on a key change (data-model §2.4).
- [x] Review upsert by `dedupe_key`, `mark_obsolete(owner, attempt_id)`, and `attempt.status → reviewed` when no open items remain.
- [x] A content upgrade hook keyed on `content_schema_version`.
- [x] `backup(path)` via `VACUUM INTO`, and `restore(path, new_folder)`.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R2.1 | Every table in data-model §3 exists with exactly the doc's columns (`PRAGMA table_info`), primary keys, UNIQUE constraints and FKs (`PRAGMA foreign_key_list`). The other tables allowed in `sqlite_master` are FTS shadow tables and, from step 7, LangGraph's `checkpoints`/`writes`. | `TEST` |
| R2.2 | Running migrations twice is a no-op; `schema_migrations` holds 1 row. | `TEST` |
| R2.3 | Each connection reports `PRAGMA foreign_keys` = 1 and `journal_mode` = wal; inserting an answer for a missing attempt raises `IntegrityError`. | `TEST` |
| R2.4 | `write_test_meta` updates `meta`, the columns, `display_name` and the FTS row in one transaction (FTS finds the new name; the prefix query `final` finds a test named "…FinalTerm…"). An exception injected before commit leaves all four unchanged. | `TEST` |
| R2.5 | A non-teacher write does not change fields listed in `edited_fields`; a teacher write adds the field to `edited_fields`. | `TEST` |
| R2.6 | An `ai` key write over `teacher_verified` is a no-op; `from_key_photo` over `ai_*` replaces it; any key change deletes that question's explanations and nothing else. | `TEST` |
| R2.7 | Upserting the same `dedupe_key` twice → 1 row. `mark_obsolete("grade", A)` changes only open grade-owned items of attempt A. Resolving the last open item of A sets A `reviewed`. | `TEST` |
| R2.8 | Content upgrade: with a registered fake upgrader v1→v2, reading a v1 test returns v2 content and writes it back (the stored version becomes 2). | `TEST` |
| R2.9 | `student_skill_stats` over seeded rows: `seen` counts only correct/incorrect; superseded attempts and `student_id` NULL are excluded (the expected numbers are in the test's seed table). | `TEST` |
| R2.10 | `backup` → `restore` into a new folder → identical row counts per table. | `TEST` |

**Verifier notes:** 2026-09-28. **All pass at 3b6f765.** The first verification (359840e, of 32550b2) failed S1 on a flaky ordering bug. `test_threads_and_messages` failed 6 times in 15. Lists ordered by `created_at, id` came back in random order when two rows shared a `created_at`, because `new_ulid()` drew fresh random bits within the same millisecond. Fix commit 3b6f765 makes `new_ulid()` monotonic and thread-safe, and makes `files.list_files` break ties on `rowid` (file IDs are sha256). It adds `tests/unit/store/test_ordering.py`. Re-verified on a fresh clone at 3b6f765, uv 0.12.19, `uv sync --frozen` OK. S1: full `TEST` run 3 times, each `350 passed, 1 deselected`. `test_threads_and_messages` run alone 50 times, 50 passed. S2: ruff clean, "48 files already formatted", mypy "no issues found in 27 source files". S3: `wrote 42 schema files`, `git diff --exit-code schema` exits 0, `git status --short` empty. The ordering tests freeze `datetime.now` or pass one fixed `created_at`, and assert that the timestamps are identical. The file IDs are in descending order, so an `id` tie-break would reverse them. The ULID tests assert strict `<` over 10,000 IDs, sorted IDs per thread and uniqueness across 4 threads, and the overflow case. All 8 fail against the pre-fix `db.py`/`files.py`, so they are not self-certifying. `32550b2..3b6f765` changes only `db.py` (`new_ulid`), `files.py` (`list_files`), the new test file and plan.md; no R2.x test or schema changed. The earlier results, all from 32550b2, still stand. Regression: R0.1 (1 deselected), R0.2 `0.1.0`, R1.1–R1.5 tests pass; no changes under `domain/`, `tests/unit/domain/`, `tests/unit/examples/` or `tests/conftest.py`. R2.1: I compared the test's EXPECTED_COLUMNS/FKS/UNIQUE/INDEXES with §3 table by table (all 18 tables), all equal. `0001_init.sql` is the same as the §3+§4 SQL once comments and whitespace are normalized. R2.2–R2.10 pass as their Check columns say. R2.4: the exception is injected after the real UPDATE and FTS write, inside the transaction, and the snapshot covers meta, the columns, display_name and the FTS row. R2.6: explanations for another question of the same test and for another test survive. R2.9: the expected numbers are hand-written and I re-derived them by hand. R2.10: row counts for every `sqlite_master` table. Write scope: every path is in §6 row 2, the "every step" list, or an accepted placement. Paths: no absolute paths; AppData appears only in the `appdir.py` refusal check. The implementer changed only checklist ticks in plan.md.

---

## Step 3 — File store & document input
**Depends on:** 2 · **PRD:** D11, §11 (documents in), data-model §2.8, §5.5

**Checklist**
- [x] A content-addressed store: `files/<ab>/<sha256>.<ext>`; `put(bytes)` deduplicates and writes a `files` row (`kind=upload`).
- [x] Derived images (rotate, resize) → new rows with `kind=derived` and `derived_from`.
- [x] **Document input:** a PDF → one `PageInput` per page (a rasterized image, plus a text layer if present); a DOCX → its text as one text page (several when over 6 000 characters, data-model v1.7) plus one `PageInput` per embedded image, in order; images → one `PageInput` each.
- [x] The cleanup **sweep**: delete unreferenced files (not referenced by test pages, attempt pages, picture refs, or the inputs of runs that are not finished).

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R3.1 | `put` of identical bytes twice → the same id, 1 file on disk, 1 row. | `TEST` |
| R3.2 | Rotate 90 of a 100×200 PNG → a 200×100 derived file with `derived_from` = the original; the original's hash is unchanged. Resizing to max 1600 px keeps the aspect ratio. | `TEST` |
| R3.3 | A 2-page PDF fixture with a text layer → 2 `PageInput`s, each with an image `file_id` and a `text_file_id` whose `files.kind` = `text` and whose content is non-empty. A DOCX with 1 image and 1 paragraph → 1 text-only page (`file_id` = `text_file_id`) + 1 image page, in document order. | `TEST` |
| R3.4 | The sweep over a seeded set (3 referenced, 2 unreferenced files) deletes exactly the 2 (rows and disk). | `TEST` |

**Verifier notes:** Fresh clone at c193dcf, `uv sync --frozen` OK, `uv lock --check` OK. S1 `TEST` 374 passed (run twice, stable); S2 `LINT` clean; S3 schema export no diff; tree clean after. R0–R2 pass; the diff leaves `domain/`, `store/db.py`, `store/repos/`, `appdir.py` and the step 1/2 tests untouched (`tests/unit/store/conftest.py` only gains a `store` fixture). R3.1–R3.4 tests read and pass (R3.1 counts files on disk; R3.4 checks rows and disk for the 3 kept and 2 deleted). Manual check: an ingested Pillow JPEG lands at `files/<ab>/<sha>.jpg`; an independent PDF with 2 text pages gives 2 PNG pages with non-empty `text` files. Write scope, the exact pins (pillow 12.3.0, pymupdf 1.28.2, python-docx 1.2.0) and the path rules all pass.

---

## Step 4 — Ollama client, recorder, cassettes
**Depends on:** 2 · **PRD:** D7, D20, D22 · llm-design §3

**Checklist**
- [x] The `models.toml` loader; defaults in `src/erh/llm/defaults.py` (the only file allowed to name models, see S4).
- [x] Adapters `nuextract` (template/instructions) and `chat` (system + user + `format`).
- [x] `client.call(...)`:
  - streaming, with `logprobs` and `top_logprobs`;
  - incremental `llm_calls` writes;
  - pydantic validation, `invalid` status, one retry, and a failure object (never writes Review items);
  - a stored `prompt_hash`.
- [x] Cancellation → `cancelled`, with partial text kept. **A dropped stream** (connection reset) → one automatic retry of the call; a second drop → an error that the runtime turns into `interrupted` (step 7).
- [x] The version/model check (Ollama ≥ 0.12.11, role models present).
- [x] The **other-Ollama detector**: query the default port `127.0.0.1:11434` (`/api/ps`) and report whether another Ollama has a model loaded (PRD R7).
- [x] `FakeOllama` (httpx mock transport), `erh record` (records live calls as cassettes, §1.7), `erh scrub` and `erh scrub --check`, and a **replay client** that serves cassettes by match key.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R4.1 | FakeOllama streams 200 tokens → `llm_calls.response_text` is read at ≥ 3 increasing lengths during the stream and ends `complete`, with `prompt_hash` non-empty. | `TEST` |
| R4.2 | Invalid then valid JSON → rows `invalid` + `complete`, and the parsed result is returned. Invalid twice → a failure object, and `review_items` has 0 rows. | `TEST` |
| R4.3 | Cancelling mid-stream → the row is `cancelled` with non-empty partial text; FakeOllama records that the client disconnected. | `TEST` |
| R4.4 | A connection reset once → the call succeeds on retry (2 rows: `error`, `complete`); reset twice → `StreamDropped` is raised. | `TEST` |
| R4.5 | The version check returns `too_old` for 0.12.10, `ok` for 0.12.11, and `missing_model` for an absent tag. | `TEST` |
| R4.6 | Changing `models.toml` changes the request's `model` field; the nuextract adapter sends the template/instructions shape and the chat adapter sends `format` (request bodies asserted against Appendix D.1). | `TEST` |
| R4.7 | Replay: a cassette recorded with prompt hash X and model M is served for a call with a different prompt hash and model but the same match key. An unknown key raises `CassetteMiss`. | `TEST` |
| R4.8 | `erh scrub` replaces `student_name`/`class_name` values with the placeholders; `--check` fails on an unscrubbed synthetic cassette and passes after scrubbing. | `TEST` |
| R4.9 | The other-Ollama detector returns `loaded=true` when a fake server on the default port lists a model in `/api/ps`, `false` when it lists none, and `false` when nothing listens. | `TEST` |

**Verifier notes:** 2026-09-28. **All pass at 72f1dca.** The first verification (90ff470, of af0d730) failed the hands-on scrub: a given name on its own (`"Tam is the student."`, `"Em Tâm …"`) and `" Tâm"`/`"7B4"` as `top_logprobs` alternatives outside the name span survived `erh scrub`, and `--check` still exited 0. Fix commit 72f1dca (only `llm/scrub.py` and `tests/unit/llm/test_scrub.py`) also scrubs the given name alone and the last two words of each collected name, with a stopword guard for given names that are English words; it drops `top_logprobs` alternatives that match a name part (prefix matches only for alternatives of ≥ 3 characters); a family name alone is kept. Re-verified on a fresh clone at 72f1dca, `uv sync --frozen` OK. S1: full `TEST` twice, each `454 passed, 1 deselected`. S2: ruff clean, "70 files already formatted", mypy "no issues found in 38 source files". S3: `git diff --exit-code schema` exits 0. S4: only `src/erh/llm/defaults.py` names models. S5: `erh scrub --check tests/cassettes` exits 0. `git status --short` empty. Hands-on scrub, with the verifier's own cassettes: a transcribe cassette (`Họ và tên: Lê Văn Tâm   Lớp: 7B4`; thinking with "Tam is the student", "Em Tâm viết rõ", "Văn Tâm") and a read_answers cassette (`student_name "Lê Văn Tâm"`, `class_name "7B4"`, byte-split logprob tokens, `" Tâm"`/`"Tam"`/`"7B4"` alternatives on unrelated tokens, and a `"B"` alternative on every token). `--check` gives 1 before and 0 after scrubbing. Afterwards no `tam`/`7b4` is left (accent-folded) in any text, token, token bytes or alternative. The logprob bytes still join exactly to thinking + response. The `"B"` alternatives survive on the tokens next to the name. The printed `Lê Lợi` survives. With the given name `An` (`Trần Văn An`, 6A1), "An apple" survives and "Em An làm bài" becomes "Em Học Sinh A làm bài". `90ff470..72f1dca` touches only `llm/scrub.py` and its test, inside §6 row 4. The new test names (`Nguyễn Thị An`, `Trần Thanh Hải`, `Lê Văn Tâm`, `Nguyễn Văn Bình`) are synthetic. The results from af0d730 still stand, since the fix does not touch them: regression (R0–R3 pass; `runs.py` only adds the llm_calls functions plus `__all__`/imports and the `LlmCallStatus` alias), R4.1–R4.9 (the D.1 request bodies checked by hand), the write scope, `httpx==0.28.1` matching `uv.lock`, and no student data in the committed cassettes. Note: a sentence that starts with the given name before an English word ("An answered C.") is kept by the stopword guard.

---

## Step 5 — Phase 0 live checks 👤
**Depends on:** 4 · **PRD:** §13 Phase 0, R4 · llm-design §9 Q1, Q2

**Checklist**
- [x] Live tests in `tests/live/`:
  1. logprobs with `format`, with an image, and with both;
  2. NuExtract3 template alone vs template + `format`;
  3. an MCQ letter is a single token;
  4. VRAM and speed per role model at `num_ctx` 16384;
  5. flash attention and q8_0 KV cache on Turing;
  6. swap time with `OLLAMA_MAX_LOADED_MODELS=1`.
- [x] The teacher runs `LIVE` and commits `docs/initial-plan/phases-testing/phase0-live-output.txt` (👤).
- [x] `docs/initial-plan/phases-testing/phase0-report.md`: one section per item 1–6, with the measured data, **a decision**, and the chosen confidence fallback (llm-design §6).
- [ ] **Recording 👤:** during the live tests of items 1 and 3, `erh record` saves the calls as cassettes, then `erh scrub` runs on them, and they're committed to `sidecar/tests/cassettes/phase0/` (`👤 sign-off: cassettes phase0`). Step 6 uses them.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R5.1 | The report has sections 1–6, each with a measured value and a line starting `Decision:`, plus a `Fallback:` line. | Read the file |
| R5.2 | `docs/initial-plan/phases-testing/phase0-live-output.txt` exists, shows 0 failed live tests, and was added in a `👤 sign-off:` commit. | Read it + `git log --grep` |
| R5.4 | `sidecar/tests/cassettes/phase0/` holds ≥ 3 cassettes with non-empty `logprobs` (at least one with an image input), committed with `👤 sign-off: cassettes phase0`. | `ls` + `git log --grep` |
| R5.3 | Every decision that contradicts llm-design has a matching llm-design changelog row, and the plan's "Based on" line is updated (§1.5 doc sync). | Compare the report, the llm-design changelog and the plan header |

**Verifier notes:** 2026-09-29. **All pass at b7fdf8a** (fresh clone, `uv sync --frozen` OK, no Ollama). S1: `TEST` 454 passed, 14 deselected (R0–R4 still pass); `pytest -m live --collect-only` collects the 14 live tests. S2: ruff clean, 73 files formatted, mypy no issues in 38 files. S3: schema diff empty. S4: only `src/erh/llm/defaults.py` names models. S5: `scrub --check` exits 0. `git status --short` empty. R5.1: sections 1–6 each have Measured values and a `Decision:` line, plus `Fallback:` lines; spot-checked against the output file: item 1 think 887/888, item 3 reasoning B 0.9992, item 4 vision 9436/7954 MiB, item 5 vision 3526 MiB and 22.55 tok/s, reasoning 3189 MiB, item 6 loads 11.719/14.697/18.069 s, logprob −0.0008233001572079957 at out:L767/L856. R5.2: output shows "14 passed, 0 failed"; added only in 48844f5 `👤 sign-off: phase0 live output` (emoji bytes F0 9F 91 A4). R5.4: 9 cassettes, all with logprobs, 5 with image input (`render_output.py --check-cassettes`), added only in 01b5b2f `👤 sign-off: cassettes phase0`. R5.3: llm-design v4.7 row covers flash attention + q8_0 (§2), `also_format = true` (§3.1), fallback `none` (§6); "Based on" = PRD v4.6, data-model v1.4, llm-design v4.7; §3.1 `also_format = true` matches `defaults.py`; step 14 spawn env has both variables. Student data: no `binh`/`7c3` (accent-folded) in any cassette text, thinking, token, token bytes or alternative; name/class read `Học Sinh A`/`8X1`; no other name-like strings. Write scope: d70b294 and 643b39b touch only `sidecar/tests/live/`, the report and the step 5 checklist tick; teacher commits add only the output file and the cassettes. The only sign-off commits are 48844f5 and 01b5b2f, with no Claude trailer. Notes: the output file keeps the synthetic "Lê Văn Bình / 7C3" unscrubbed (49 lines; it is not a cassette and holds no real student data). The code default `confidence.fallback` is still `None` (`config.py`; `test_config` asserts it), while llm-design §3.1 shows `"none"`; step 6 implements the fallback. `config.py`'s docstring still shows `also_format = false`. llm-design §6 "Unverified (Phase 0)" and §9 Q1/Q2 are not marked answered. The report's Status line still reads "pending teacher review". Step 5 checklist items 2–4 are unticked.

---

## Step 6 — Logprob confidence
**Depends on:** 5 · **PRD:** D20 · llm-design §6

**Checklist**
- [x] Map tokens to JSON field spans (a parser with position tracking).
- [x] Enum margin (restricted to the valid choices, renormalized) and free-text minimum token probability.
- [x] The fallback chosen in the step 5 report, selectable in config (`confidence.fallback = "resample" | "self_report" | "none"`), with results marked `low_trust`.
- [x] Recorded logprob cassettes from step 5 as test data.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R6.1 | The test loads **≥ 3** cassettes from `tests/cassettes/phase0/` (fails if fewer). For each, every leaf field gets a confidence in [0,1], and each span maps back to the exact value text. | `TEST` |
| R6.2 | Enum margin: top_logprobs at the value token = {D: 0.62, B: 0.31, A: 0.01, C: 0.01, "(": 0.05} (5 entries; valid set A–D, sum 0.95) → margin = (0.62−0.31)/0.95 = **0.326 ± 0.001**. | `TEST` |
| R6.3 | Free text: token probabilities [0.9, 0.4, 0.8] → confidence **0.4**. | `TEST` |
| R6.4 | With no logprobs (llm-design §6): `resample` with agreeing samples → 1.0, disagreeing → 0.0; `self_report` → the model's own value; `none` → 0.0. In every case `low_trust=True`. | `TEST` (parametrized over the 3 values) |

**Verifier notes:** Fresh clone at 1b44791, `uv sync --frozen`: TEST 492 passed twice (tree clean), LINT, S3–S5 pass. R6.1: 9 phase-0 cassettes, every leaf in [0,1] and span bytes = value text; with 2 cassettes the count test fails (not skips). R6.2 = 0.3263; R6.3 = 0.4; R6.4 parametrized over resample/self_report/none, all `low_trust=True`. Independent script on 007 (think) and 002 (image): q1 = "B", confidence > 0.9998, spans exact; changing one character of `response_text` gives the fallback (`low_trust`, 0.0). Diff touches only `llm/confidence.py`, its test and the checklist ticks; `confidence.py` imports only json/math/re/dataclasses/typing/pydantic.

---

## Step 7 — Run runtime
**Depends on:** 4 · **PRD:** D21, D22, D23 · llm-design §7

**Checklist**
- [x] A run manager: a FIFO queue, one run at a time, statuses per data-model §2.7, and internal events `run.queued`, `run.step_started`, `run.step_done`, `run.progress`, `run.done`, `run.failed`, `run.stopped`.
- [x] Graph registry by run kind: a queued run whose kind has no registered graph stays `queued` (grade runs can be queued before step 18 exists).
- [x] A step wrapper (a `steps` row with `try_no`) linked to `llm_calls`.
- [x] Async `SqliteSaver` (durability "sync") in the app database; `ainvoke` for start and resume; checkpoints purged on done or discarded.
- [x] Stop, Resume, Discard; startup recovery (llm-design §7); `StreamDropped` → the run `interrupted`.
- [x] Keep-awake (`SetThreadExecutionState`) behind an interface; power source (AC/battery) behind the same interface.
- [x] A **toy graph** (3 nodes + a 3-item loop, FakeOllama) for the tests.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R7.1 | Stopping the toy graph at every node boundary and mid-call, then resuming, gives the same final state and the same database row counts as an uninterrupted run; resumed steps have `try_no` = 2. | `TEST` (parametrized) |
| R7.2 | A subprocess killed mid-run → after restart: the run `interrupted`, open steps `incomplete`, streaming calls `incomplete`; Resume → `done`. | `TEST` |
| R7.3 | Recovery: `stopping` → `stopped`; `queued` → runs after restart. | `TEST` |
| R7.4 | Two runs → the second is `queued` until the first is `done`. A run of an unregistered kind stays `queued` without error. | `TEST` |
| R7.5 | Discard → `discarded`, 0 checkpoint rows for the run, `llm_calls` rows kept. Done → 0 checkpoint rows. | `TEST` |
| R7.6 | Keep-awake is set on `running` and cleared on done, stop, failure and discard (asserted on the fake interface). | `TEST` |
| R7.7 | A `cancelled` call whose partial text is valid JSON is **not** used: after Resume, the node calls the model again (the FakeOllama call count increases). | `TEST` |
| R7.8 | `StreamDropped` in a node → the run `interrupted`, and Resume completes it. | `TEST` |
| R7.9 | 1,000 checkpoint writes interleaved with app writes in the same WAL file → 0 `database is locked` errors. | `TEST` |
| R7.10 | The events for a toy run arrive in the order queued → step_started/step_done pairs → done. | `TEST` |

**Verifier notes:** Fresh clone at 7eb660c, `uv sync --frozen`: TEST 541 passed ×2, `tests/unit/runtime` 49 passed ×3 more (no flakes); LINT, S3, S4, S5 pass; tree clean. R7.1 (12 cases: 6 node starts + 6 mid-call; same final state, steps/calls/domain counts, try_no 2), R7.2 (real subprocess killed), R7.5, R7.7, R7.9 (≥1,000 checkpoint writes, same app.db, 0 locked), R7.10 read and pass. Keep-awake on one dedicated thread, flags correct. Write scope inside row 7; langgraph 1.2.12 and langgraph-checkpoint-sqlite 3.1.1 pinned, `uv lock --check` ok.

---

## Step 8.1 — Extraction domain logic *(may run alongside 8.2)*
**Depends on:** 1 · **PRD:** D1, D3, D10–D14, D17–D19, §8 · llm-design §4

Pure functions (no database, no network), with hand-built inputs.

**Checklist**
- [x] `plan_pages`: the teacher's order and rotation, separating 🔑 pages, attaching text layers (it produces the file operations for step 9 to execute).
- [x] `merge_pages` + renumber (canonical numbers, `printed_number`, `page_no`, listening → `omitted_sections`, `points_possible`).
- [x] Points: printed "(2.5pts)" → per question; none → 0.25 each + pending `points_assumed`.
- [x] Header patterns + file name → metadata.
- [x] Picture placeholders.
- [x] Validators.
- [x] Similarity: normalization, 5-gram shingles, Jaccard, **same-grade filter**, **two tiers** (≥ 0.85 "looks like", 0.5–0.85 "possibly"), question alignment, merged tests excluded. Thresholds come from config.
- [x] `map_key`.
- [x] `resolve_answers` with the reading-unsure threshold from config.
- [x] `match_student(name_read, students)` → a match or none.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R8.1.1 | The worked-example structure in **Appendix B.1** renumbers to exactly the expected output in B.1. | `TEST` |
| R8.1.2 | A section without printed points → 0.25 per question, `points_source="assumed"`, and 1 pending `points_assumed`. | `TEST` |
| R8.1.3 | Header "ĐỀ CUỐI KÌ I LỚP 8 (K)" + file "Lop8-HKI-De1 (1).jpg" → occasion FinalTerm, term 1, grade 8, variant "K", test_number "1". | `TEST` |
| R8.1.4 | A picture on page 3 with file hash h → exactly `[Hình: files/<h[:2]>/<h>.jpg · trang 3]`. | `TEST` |
| R8.1.5 | Each validator (blank `____`, 2–4 options A–D, continuous numbering except the listening gap) has a passing and a failing case. | `TEST` |
| R8.1.6 | Similarity: identical → 1.0 ("looks like"); the B.2 noisy pair ≥ 0.85; the B.2 medium pair in [0.5, 0.85) ("possibly"); a different test < 0.5 (none); other grades and merged tests are never candidates; the alignment on the B.2 reordered-sections case equals the expected map. | `TEST` |
| R8.1.7 | `map_key` on B.3 (a duplicated printed "32", listening numbers present) → the expected question_id map; an unknown number → 1 pending `key_unmapped`. | `TEST` |
| R8.1.8 | `resolve_answers` over B.4: one answer per question; box vs inline → the box value + a pending `box_inline_conflict`; a span near two questions → confidence = threshold − 0.01 + `alt_question_id`; writing questions get no answer row (B.1b); below threshold → `reading_unsure`; no answers → `blank`. | `TEST` |
| R8.1.9 | `match_student`: "Tran Thi Ngoc Anh" matches the profile "Trần Thị Ngọc Ánh" (a synthetic name with the same kinds of diacritics; real student names stay out of git); an unknown name → none. | `TEST` |
| R8.1.10 | Purity: the module's tests run with sockets and the database disabled (an import guard fixture). | `TEST` |

**Verifier notes:** 2026-09-29, fresh clone at dc32a5b: S1 TEST 641 passed ×2 (tree clean), S2 LINT clean, S3 schema current, S4 tags only in llm/defaults.py, S5 scrub --check 0; diff vs main adds only §6 row 8.1 paths + plan.md (ticks, v2.4.2 patch). R8.1.1/B.1b asserts match Appendix B.1 (1 omitted 1.0 pt; sections 1–7 titled II…VIII with VI twice; Q1–36 printed 5–40; 9.0); R8.1.3/R8.1.4 exact inputs/format; R8.1.6 bands (noisy 0.958, medium 0.596, different 0.104), reordered map spot-checked against the texts, grade/merged exclusions tested; R8.1.7 B.3 a (36 rows, 2 key_unmapped) and b; R8.1.8 B.4 incl. 0.69 cap; R8.1.9 synthetic names only; R8.1.10 all ten modules via assert_pure + no_io. Independent merge_pages → map_key → resolve_answers script gave rule-consistent results.

## Step 8.2 — Extraction prompts *(may run alongside 8.1)*
**Depends on:** 1, 4 (adapters, prompt hash) · **PRD:** D7, D11, D12, D14, D15 · llm-design §4, §8

**Checklist**
- [x] `prompts/base/` for `read_key_pages`, `read_header`, `transcribe_page` and `read_answers_page`, using the step 1 output schemas.
- [x] `prompts/profiles/generic.md`.
- [x] The required phrases of **Appendix D.2** in each task prompt.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R8.2.1 | Each extraction task renders with both adapters, without errors. | `TEST` |
| R8.2.2 | Each rendered prompt contains every phrase listed for its task in Appendix D.2 (the test holds D.2 copied verbatim). | `TEST` |
| R8.2.3 | The prompt hash is stable for identical inputs and changes when the prompt file changes. | `TEST` |

**Verifier notes:** Fresh clone at f3d936d, `uv sync --frozen` OK. **All pass.** S1/regression: `TEST` run twice, `580 passed, 14 deselected` both times; S2 ruff clean, "99 files already formatted", mypy "no issues found in 48 source files"; S3 `wrote 42 schema files`, no diff; S4 hits only `llm/defaults.py`; S5 exits 0; `git status --short` empty afterwards. `git diff main..f3d936d` touches no earlier-step file except the 8.2 checklist ticks in plan.md, and every path is in §6 row 8.2 or the "every step may also write" list. R8.2.1: an independent script rendered all 4 tasks and built requests with both adapters: nuextract `template/instructions/user` + `format`, chat `system/user` + `format`, `think: false`, no `{{`, num_predict 512/1024/2048/4096. R8.2.2: the test's D2 dict parsed with `ast` equals Appendix D.2 parsed from this plan (same keys, phrases and order); every phrase found in my own renders (case-sensitive). R8.2.3: the tests copy the prompts, edit a base and the profile file, and assert the hash is stable, then changes; CRLF-insensitive. Prompt review: read_answers_page asks for one entry per listed question (null, location `none`), circled/blank/answer box (also on another page)/margin, box + inline as two entries, `alt_question_id`, student name/class; transcribe_page covers printed text only, `____`, `<u>`/`**`, listening heading + range, writing prompt only, mostly-text pictures, and always uses generic (checked); page hints only when `photo_count == draft_page_count` (checked both ways). Packaging: `uv build --wheel` holds `erh/prompts/base/*.md` (4) and `profiles/generic.md`; `importlib.resources` finds them after `uv sync --frozen`. Minor, not failures: the student name/class rule is a verbless fragment that does not name `student_name`/`class_name`; the page hints ("printed on page N") are not explained in the prompt; `read_answers_schema`'s docstring says a question not on this page is left out, while the prompt asks for a null entry.

Re-check at 2e9c508 (wording fix, fresh clone): only `prompts/base/read_answers_page.md` changed (in row 8.2); `TEST` `580 passed, 14 deselected`; `LINT` clean; D.2 phrases all present in my own render; the new page-hint bullet (only a hint, answers can be on any page, one entry per question) and the `student_name`/`class_name` bullet are clear and consistent with the rest of the prompt. The first two minor notes above are resolved; the third, about the schema docstring, is unchanged.

---

## Step 9 — Extraction graph + `erh run` (+ recording 👤)
**Depends on:** 3, 6, 7, 8.1, 8.2 · **PRD:** D1, D3, D16–D19, S1–S4, S6 · llm-design §4 · data-model §5.2

**Checklist**
- [x] The `extract` graph with exactly the nodes and edges of **Appendix C.1**.
- [x] An idempotent `save` (data-model §5.2), including `attempt_pages`, one answer per question, a student matched or "Chưa rõ" + `unknown_student` (with the read name), `threads.test_id` / `threads.kind`, the extraction card `messages` row, `supersedes_attempt_id` → `superseded_by`, and pending Review items.
- [x] The CLI: `erh run --pages p1.jpg:90 p2.pdf … [--key k.jpg] [--existing T-…] [--thread …]`, and `erh runs stop|resume|discard <id>`.
- [ ] **Recording 👤:** the teacher runs the S1 worked example and one blank test live with `erh record`, runs `erh scrub`, and commits the cassettes (`👤 sign-off: cassettes extract`).
- [x] Synthetic cassettes for: filled picked (match and mismatch), blank picked, key photo, validator retry → `retranscribe_tiles` → `validator_failed`, PDF with a text layer, supersede.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R9.1 | `graph.get_graph()` nodes and edges equal Appendix C.1 (the test holds C.1 verbatim). | `TEST` |
| R9.2 | The recorded S1 cassette → 1 test, 1 attempt, answers = question count, 3 `attempt_pages`, `thread.kind` = `filled`, the run `done`, 1 extraction card message; the attempt's `student_name_read` = "Học Sinh A". | `TEST` |
| R9.3 | Filled picked: 0 `transcribe_page` calls, the attempt is on the picked test. A mismatching header → 1 `picked_test_mismatch`. | `TEST` |
| R9.4 | Blank new → 1 test, 0 attempts, `thread.kind` = `blank`, `thread.test_id` set. Blank picked → 0 new tests, 0 attempts, `thread.test_id` = the picked test, and the card body has `no_answers: true`. | `TEST` |
| R9.5 | A crash injected between `save`'s commit and its checkpoint → Resume → row counts in every table equal the uninterrupted run. | `TEST` |
| R9.6 | A similar bank test at 0.9 → 1 `possible_duplicate` with a non-empty `question_alignment`; at 0.6 → the same kind with `proposal.tier = "possibly"`. | `TEST` |
| R9.7 | Key photo → key rows by question_id with `source=from_key_photo`; an entry below the threshold → `ai_unverified`, the rest `ai_verified`. | `TEST` |
| R9.8 | The graph stopped before `save` → `tests`, `attempts` and `review_items` are all empty. | `TEST` |
| R9.9 | Validator retry: a page failing validation → 1 `retranscribe_tiles` step; failing again → 1 `validator_failed`. | `TEST` |
| R9.10 | PDF with a text layer → `transcribe_page` receives the text (the request contains the text, not an image). | `TEST` |
| R9.11 | Supersede: an extract run with `supersedes_attempt_id=A` → the new attempt B, and `A.superseded_by = B`. | `TEST` |
| R9.12 | Student: the name read matches a profile → `student_id` set, 0 `unknown_student`; no match → `student_id` NULL + 1 `unknown_student` whose proposal holds the name read. | `TEST` |
| R9.13 | `erh run` on the replay S1 cassette exits 0 and prints JSON `{test_id, attempt_id}`. `erh runs stop` then `resume` on a replay run ends `done`. | `TEST` (CLI) |
| R9.14 | The recorded cassettes exist under `sidecar/tests/cassettes/s1/` and `…/blank/`, committed with `👤 sign-off: cassettes extract`. | `git log --grep` + `ls` |

**Verifier notes:** 2026-09-29. **All pass at 3d9e994.** The first verification (648414e, tracker commit 696d9ae) failed R9.14: the sign-off subject of 648414e began with EF BF BD (the Unicode replacement character), not the 👤 bytes F0 9F 91 A4. The teacher re-signed in 3d9e994 (`👤 sign-off: cassettes extract`, bytes F0 9F 91 A4), which adds only `s1/SIGNOFF.txt` and `blank/SIGNOFF.txt` (UTF-16 notes, no student data, no cassette changed); `git log --grep "^👤 sign-off: cassettes extract" -- sidecar/tests/cassettes/s1 sidecar/tests/cassettes/blank` finds 3d9e994. Re-check on a fresh clone at 3d9e994: `TEST` 760 passed, 14 deselected; `pytest tests/replay` 17 passed, 0 skipped (the loader ignores `SIGNOFF.txt`); `scrub --check` exits 0; `git status --short` empty. The first verification (fresh clone at 648414e, `uv sync --frozen`, no Ollama) found the rest passing: S1: `TEST` 760 passed, 14 deselected, 0 skipped, twice (R0–R8 and the R4.8 scrub tests pass; R1.1 Appendix A matches plan v2.5.1 with `File` ending in `original_name`; R2.1/R2.2 expect migration 0002 and `files.original_name`). S2: ruff, format (127 files) and mypy (60 files) clean. S3: schema diff empty. S4: only `llm/defaults.py`. S5: `scrub --check` exits 0. `git status --short` empty. R9.1: the test holds C.1 verbatim and compares nodes and edges. R9.2 and R9.13 run on the recorded `s1/` (PASSED, not skipped) and assert every listed count, `student_name_read == "Học Sinh A"`, JSON `{test_id, attempt_id}` and stop → resume → `done`. R9.3–R9.12: tests exist and assert what the plan says (R9.5: crash after the save commit → resume → equal counts in every table except the one retried `steps` row; R9.8: `tests`/`attempts`/`review_items` empty). Synthetic: `extract-synthetic/` holds the 7 scenarios plus `s1-like`, each with `input.json` and single-colour stand-in PNGs; each replays through the CLI in `tests/replay/`. Student data: no `ngo`/`hoa`/`8tc11` (accent-folded, whole word) in any text, thinking, token, token bytes or alternative of `s1/` and `blank/`, except `ngo` as one alternative token in `blank` 002 and 006; all PNGs single-colour; no base64 image data. Write scope: every non-orchestrator path is in §6 row 9 or the common list; the teacher's commit adds only `s1/` and `blank/`. Doc sync: "Based on" = PRD v4.6, data-model v1.5.1, llm-design v4.7.1 (current). Agents changed only checklist ticks in plan.md. Notes (not failures): the recorded S1 reads 8 of 34 answers, and leaves an open `validator_failed` on page 3 (numbering). The class `8TC11` appears as a shape example in `llm/scrub.py`, `domain/boxes.py` and their tests; it was already in the PRD and data-model.

---

## Step 10 — Review resolution & merge service
**Depends on:** 9 · **PRD:** D1, D2, D3, D13, S3, S7 · data-model §5.3–5.4

**Checklist**
- [x] `resolve(item, action, value)` for **every** kind in data-model §5.3, including Skip, setting `resolution`, `resolved_at` and `followup_run_id`.
- [x] Follow-ups that need grading **enqueue** grade runs (`GradeInput`); they stay `queued` until step 18 registers the grade graph (R7.4).
- [x] **Merge** (data-model §5.4) in one transaction.
- [x] Points edit → recompute `points_possible`. Content edit (for `validator_failed`) → re-validate.
- [x] A `reviewed` attempt that gets a new or reopened open item returns to `graded` (score set) or `extracted` (data-model §5.3, v1.3), in the Review upsert of `store/repos/`.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R10.1 | A table-driven test with one row per `(kind, action)` in **Appendix E** asserts exactly the listed database post-conditions (including `followup_run_id`, the queued `GradeInput` count and reason, and `attempt.version` increments). | `TEST` |
| R10.2 | Skip → status `skipped`, no other row changes. | `TEST` |
| R10.3 | Merge: answers are remapped via the alignment; a collision → a new Review item, and the answer stays on the old question as `ungraded`; `attempts.test_id` and `threads.test_id` point to the survivor; keys and tags are copied only where the survivor has none; `merged_into` is set; the FTS row is removed; 1 queued grade run per moved graded attempt. An exception mid-merge leaves the database unchanged. | `TEST` |
| R10.4 | Upserting an open item on a `reviewed` attempt → the attempt becomes `graded` when `score_earned` is set, else `extracted`; reopening an `obsolete` item does the same. An item on a non-reviewed attempt leaves its status unchanged. | `TEST` |

**Verifier notes:** Verified at bffb77d (fresh clone, `uv sync --frozen`): TEST 869 passed ×2, 0 skipped (incl. recorded `s1` replays), tree clean after; LINT, S3, S4, S5 pass. R10.1: 20 Appendix E labels verbatim, each graded + ungraded; spot-checked 6 rows. R10.2: skip for all 11 kinds compared by full-DB dump. R10.3/R10.4: merge/collision/pointers/copy-if-missing/`merged_into`/FTS/runs/rollback and the `reviewed` rule tested. Independent check on the `s1` replay: unknown_student fix (new student, version+1), uncertain_answer accept on a blank read (`teacher_override` ""), re-accept refused with DB unchanged. Write scope within §6 row 10; repos only gained functions.

---

## Step 11 — Fixtures & eval harness 👤
**Depends on:** 9 · **PRD:** D15, §12 · llm-design §8

**Checklist**
- [x] The fixture format `fixtures/<tuning|heldout>/<name>/{pages/, input.json, expected.json}`, with a schema (`verified_by` and `verified_on` are written only by the teacher).
- [ ] Fixture 1: Lớp 8 HK1 Đề 1. The implementer drafts `expected.json`; the teacher corrects it and signs it off (👤). *Draft done 2026-09-30 (runbook `docs/initial-plan/phases-testing/step11-fixture.md`); awaiting the teacher's correction and sign-off.*
- [ ] `fixtures/MANIFEST.sha256` (committed; the fixtures themselves stay gitignored): the sha256 of each `expected.json` + `verified_by`, generated by `erh fixtures manifest`.
- [x] `erh eval --graph extract --set tuning|heldout [--role vision=<tag>]` → appends to **`eval-history.csv` (committed)**: commit, model tags, prompt hashes, set, and every llm-design §8 metric, including tokens per node.
- [x] Metric functions with unit tests.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R11.1 | Metrics: CER("abc","abd") = 1/3; structure accuracy on a synthetic pair; calibration = wrong-and-flagged / wrong (+ Wilson interval) on a synthetic set. | `TEST` |
| R11.2 | `erh eval --graph extract --set tuning` against a committed **synthetic** fixture in `sidecar/tests/fixtures_synth/` (replay cassettes) appends exactly 1 row with every column in the header. | `TEST` |
| R11.3 | `MANIFEST.sha256` lists fixture 1 with `verified_by: teacher`, and the manifest line was added in a `👤 sign-off:` commit. | `git log --grep` + read |
| R11.4 | `git ls-files fixtures` lists only `fixtures/MANIFEST.sha256`; `eval-history.csv` is tracked. | Run it |

**Verifier notes:** 2026-10-01. **All pass at 938c954** (fresh clone, `uv sync --frozen`). S1: `TEST` 889 passed ×2, no skips (the `s1` replays run), clean `git status`; S2–S5 pass. R11.1: CER 1/3, the synthetic structure pair checked by hand, Wilson 3/4 = (0.3006, 0.9544) recomputed. R11.2: a manual `erh eval --graph extract --set tuning --replay` on `fixtures_synth` appended exactly 1 row of 97/97 columns. R11.3: manifest `verified_by: teacher` added only in 938c954 (subject bytes `f0 9f 91 a4`); the sha256 of the gitignored `expected.json` matches; it holds `verified_by`; agent commits touch no `fixtures/` path. R11.4: `git ls-files fixtures` = the manifest only; `eval-history.csv` tracked. Fixture 1 loads: 8 sections, 8 groups (3 with a stimulus), 36 questions, 36 non-null answers. No student name in committed files; write scope within structure §6 row 11. Baseline row (ecb3e3b, live, nuextract3 Q6_K + qwen3.5:4b): answer_accuracy 0.0556 (2 of 36), calibration 0.7941 (27 of 34 wrong readings flagged; Wilson 0.6320–0.8965, recomputed), flagged_correct_rate 0.0, cer 0.1383, stimulus_cer 0.0396, structure_overall 0.4726 (section_count and question_count 0, underline and bold 0). The very low answer accuracy is a model-quality result for M1, not a harness failure.
Re-check at 4c8fb89 (fresh clone, after the eval partial-credit fix fe157ba and the `resolve_answers` hardening 4c8fb89): `TEST` 908 passed, no skips (the `s1` replays run), clean tree; S2–S5 pass; R11.1/R11.2 tests pass (the section/question counts now min/max, the synthetic pair 1/2 and 3/4 checked by hand); R8.1.8/B.4 assertions unchanged and still match Appendix B.4 (the test draft's mcq/gap_fill types keep every B.4 reading valid); scope of `8d1b1d6..4c8fb89` = `eval/metrics.py`, `tests/unit/eval/`, `domain/boxes.py`, `tests/unit/domain/test_boxes.py` and the orchestrator's `docs/structure.md` v1.1.16. Corrected replay metrics: structure_overall 0.636, calibration 0.941. The committed CSV's baseline row keeps the old exact-match counts (section_count and question_count 0).

---

## Step 12 — Sidecar API, SSE, `erh serve --replay` (route inventory: current llm-design §2)
**Depends on:** 10 · **PRD:** §10, §11 · llm-design §2 (the route inventory, v4.3)

**Checklist**
- [x] FastAPI with **every route in the current llm-design §2 inventory** (files, threads, runs, tests, keys, attempts, students, review, system, settings, maintenance, events).
- [x] Auth token; bound to 127.0.0.1.
- [x] `erh serve [--replay <cassette dir>] [--data <dir>]` prints `{"port":…, "token":…}` as the first stdout line.
- [x] SSE `/events`: run events (including `run.discarded`) + `review.changed` + `system.changed` + `models.pull_progress`.
- [x] `erh openapi export`.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R12.1 | The OpenAPI paths and methods equal the route table in the current llm-design §2 (the test holds that table verbatim). | `TEST` |
| R12.2 | No token or a wrong token → 401 on every route. `GET /files/{id}` and `GET /events` also accept `?token=` (the right token → 200, a wrong one → 401); every other route rejects a query token. The server socket's local address is 127.0.0.1. | `TEST` |
| R12.3 | `erh serve --replay tests/cassettes/s1` prints valid port/token JSON; an extract run over HTTP streams `run.queued`, `run.step_started` × n, `run.done` in order over SSE. | `TEST` |
| R12.4 | `POST /runs/{id}/stop` → status `stopped`; `/resume` → `done`; `/discard` on a stopped run → `discarded`. | `TEST` |
| R12.5 | `PATCH /tests/{id}` `{meta.school}` → FTS search finds the new school, and `edited_fields` contains `school`. | `TEST` |
| R12.6 | `POST /review/{id}/resolve` for each Appendix E row gives the same post-conditions as R10.1, and emits `review.changed`. | `TEST` |
| R12.8 | After a simulated restart, `GET /runs/active` lists the `stopped` and `interrupted` runs; recovery emits `run.interrupted` over SSE. | `TEST` |
| R12.7 | `GET /system/status` returns `ollama_version`, `models_present`, `other_ollama_loaded`, `power_source`, `keep_awake` (from fakes). | `TEST` |

**Verifier notes:** 2026-10-01, f0bdc34: ✅. The first verification (60f5d65) failed only on write scope: the briefs granted additions to `store/repos/{review,runs,students,tests,threads}.py`, but structure row 12 did not list them. structure v1.1.20 (32ead5d) adds `store/repos/*.py` (**add** functions only) to row 12. The re-check found those changes add-only (the one removed line is `students.py`'s `__all__`, reflowed), and the code is unchanged since f0bdc34. Evidence: S1 984 passed, 0 skipped, 3 of 3 runs, flaky failure not reproduced; S2–S6 pass; recorded `s1` replays and R7.x pass; R12.1 test table identical to llm-design §2, OpenAPI = 35 rows; R12.2 walks every route; R12.3 manual `erh serve --replay` subprocess: JSON first line, `run.queued`, 15 × `run.step_started`, `run.done`, exit 0; R12.4–R12.8 pass. Clean tree, no `settings.json`. Worth a look: `delete_llm_calls_before` filters dates in Python over all unreferenced calls (slow on big logs); the R12.3 SSE test keeps a part-A fallback branch that can no longer run.

---

## Step 13 — Frontend skeleton
**Depends on:** 12 · **PRD:** D8, §10

**Checklist**
- [x] React + TS + Vite + Tailwind in `app/`; Vitest, ESLint, `tsc --noEmit`, Playwright.
- [x] TS types generated from `sidecar/schema/*.json` + `openapi.json` into `app/src/gen/` (`npm run gen:types`).
- [x] An API client and an SSE hook (with reconnect).
- [x] The layout: sidebar (New thread · running indicator slot · Review · N · Chats | Tests · ⚙), the conversation area, and the artifact panel. Light/dark theme; bundled fonts **Be Vietnam Pro** and **Noto Serif**.
- [x] Keyboard shortcuts from PRD §10.1.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R13.1 | The sidebar renders exactly these items, in this order: New thread, running indicator slot, Review, Chats/Tests switch, Settings. **Superseded by R22.1.5.7** (v2.14.1): the Review item is gone. | `APP_TEST` |
| R13.2 | Each shortcut (`Ctrl+N`, `Ctrl+V`, `Ctrl+Enter`, `Ctrl+K`, `Esc`) calls its handler. | `APP_TEST` |
| R13.3 | The built app makes **0 requests** to non-localhost origins while loading and navigating (Playwright request interception on the web build). | `E2E` |
| R13.4 | The font files are in `dist/` and `@font-face` points to them; in the dark scheme the root background token differs from light. | `APP_TEST` |
| R13.5 | The SSE hook reconnects after the server drops (mock server) and resumes delivering events. | `APP_TEST` |

**Verifier notes:** 2026-10-02, c1e87e1: ✅. Fresh clone, `npm ci` + `uv sync --frozen`. S1 997 passed, 2 of 2 runs; S2–S6 pass; R12.4 test looped 30 times: 30/30 passed; regression (runtime, replay `s1`, api, extract graph: 186 passed; `-k "r7_ or r9_5 or r12_"`: 78 passed). S7: `APP_TEST` 33 vitest tests pass, lint and typecheck clean; `gen:types` gives no diff in `app/src/gen`. R13.1 test and `Sidebar.tsx` give new-thread, running, review, tabs, settings in that order. R13.2 hook tests cover all five shortcuts (Ctrl+V through the `paste` event). R13.3 `npm run e2e` 1 passed: context-wide `route("**/*")` aborts non-loopback requests and records them, 0 external; Review count read from the real `erh serve --replay`. R13.4 `dist/` holds 12 Be Vietnam Pro and 9 Noto Serif woff2 files, all 36 `@font-face` `url(./…)` refs resolve; `--erh-bg` is #faf9f5 in light and #262624 in dark; the only `http(s)://` strings in `dist/` are XML namespaces, a `react.dev/errors` message prefix and a Tailwind licence comment, none of them fetched. R13.5 mock-EventSource test: reconnects, resumes from Last-Event-ID, no repeats. CORS: `test_cors.py` passes; manual `erh serve`: Origin `https://evil.example` gets no ACAO (preflight 400), Origin `http://127.0.0.1:4173` gets ACAO, and a request with no token gets 401. Write scope: every implementation commit is inside row 13 (v1.1.23); the plan edits are checklist ticks only.

---

## Step 14 — Tauri shell
**Depends on:** 13 · **PRD:** §11, D23, R7 · llm-design §2

**Checklist**
- [x] Tauri 2 in `app/src-tauri`. On start: a Windows **Job Object**; resolve every path relative to the **app folder** (PRD §11; default `D:\ExamRevisionHelper`, nothing in AppData); set the WebView2 user data folder to `<app>\webview`; read `<app>\settings.json`; spawn `ollama serve` with `OLLAMA_HOST=127.0.0.1:<rand>`, `OLLAMA_MODELS=<app>\data\models`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `CUDA_VISIBLE_DEVICES=<nvidia index>`; spawn the sidecar (dev: `uv run erh serve`); pass the port/token to the frontend.
- [x] Notification and dialog plugins.
- [x] CSP: `default-src 'self'; connect-src 'self' ipc: http://ipc.localhost http://127.0.0.1:*; img-src 'self' http://127.0.0.1:* data:; font-src 'self'`.
- [x] The spawn arguments are built by a pure Rust function (testable).

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R14.1 | `cargo test`: the spawn-args function returns exactly the env vars above for a given app folder and GPU index, and the webview data folder = `<app>\webview`. | `cd app/src-tauri && cargo test` |
| R14.5 | `E2E_SHELL`: after a full app start and an S1 replay run, no file or folder was created or modified under `%APPDATA%` or `%LOCALAPPDATA%` by the app (a before/after listing of both, filtered to paths newer than the test start). | `E2E_SHELL` |
| R14.2 | `cargo test`: the children are assigned to a Job Object with `KILL_ON_JOB_CLOSE`. | `cargo test` |
| R14.3 | `tauri.conf.json` CSP equals the checklist string exactly. | `APP_TEST` (the config test) |
| R14.4 | `E2E_SHELL` smoke: the real app starts with a stub `ollama` executable (a test double on PATH) and the replay sidecar; the frontend shows the "ready" state; closing the app → both child processes are gone within 5 s. | `E2E_SHELL` |

**Verifier notes:** 2026-10-03, 0f44dd1: ✅. Fresh clone, `npm ci` + `uv sync --frozen`; Rust builds reused the main copy's gitignored cache (`CARGO_TARGET_DIR=<repo>\app\src-tauri\target`), and `e2e:shell` ran with `ERH_SHELL_EXE` pointing at that build (compiled from the clone's sources, so its sidecar and cassettes are the clone's). S1 `TEST` 1004 passed, 14 deselected (live), replay included; S2 ruff clean, 163 files formatted, `mypy src` no issues in 81 files; S3 no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged. S7: vitest 34 passed (6 files), lint, typecheck and `check:urls` clean, `build` OK, `gen:types` no diff in `app/src/gen`; clean tree. R14.1/R14.2: `cargo test` 13 passed. `ollama_env_is_exactly_the_plan_set` compares the whole env map by equality with the six plan vars (`OLLAMA_MODELS=D:\ExamRevisionHelper\data\models`, GPU 1 → `CUDA_VISIBLE_DEVICES=1`); webview = `<app>\webview`; the sidecar env is exactly `ERH_APP_DIR`, with no `--data`; replay gives `--replay <dir>`. The Job test reads `LimitFlags` back through `QueryInformationJobObject` and checks `KILL_ON_JOB_CLOSE`, then drops the job and waits for a 120 s `ping` child to exit within 5 s. `lib.rs` assigns both children right after spawn. R14.3: the CSP in `tauri.conf.json` is byte-identical to the checklist string (141 bytes), and the vitest test uses `toBe`. R14.4/R14.5: `npm run e2e:shell` ran twice and passed both times (106 s and 82 s). The children were gone 656 ms and 553 ms after the close. The direct children were `cmd.exe` (the stub `ollama.cmd`; `find_ollama` searches PATH first, and the stub dir is first on PATH), `uv.exe` with `python.exe` under it, and `msedgewebview2.exe`. They are tracked by PID with their descendants, and the 5 s is timed from just before `closeWindow`. The S1 replay run (upload, thread, extract run) reached `done`, and `<app>\data\app.db` exists. R14.5 offending paths: 0 in both runs. Excluded: only `%LOCALAPPDATA%\Temp` (1340 and 18 paths) and `%LOCALAPPDATA%\uv` (0 hits). Planted check: a third run, during which I created `%LOCALAPPDATA%\ExamRevisionHelper-verifier-plant\x.txt`, failed with both paths reported as APP WRITE (exit 1); I removed the folder afterwards. Hands-on: the shell has no `app_*_dir` use; the only plugins are notification and dialog, both registered in `lib.rs` and the capability; `tauri.conf.json` has `windows: []`, and the window is built with `data_directory(<app>\webview)`. `ERH_APP_DIR` set to `%APPDATA%\erhtest` or `%LOCALAPPDATA%\erhtest` raises `AppDirError`; Temp and `D:\x\erh` are accepted. The only `http(s)://` strings in `dist/` are w3.org namespaces, `react.dev` and `tailwindcss.com`, as in step 13. Write scope: every implementation path is in §6 row 14 (v1.1.26); the plan edits are checklist ticks only. Worth a look: (1) R14.5 cannot attribute writes inside existing folders; `Microsoft\Edge` (9 and 2 paths) was among the "other programs" writes and may be the WebView2 runtime or msedgedriver. (2) A path that was already newer than the start when the "before" snapshot was taken (14 and 16 paths) is not re-checked. (3) `find_ollama` falls back to reading `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` (no write).

---

## Step 15 — Threads, photo check, running indicator
**Depends on:** 14 · **PRD:** D3, D17–D19, D22, D23, S1, S6 · §10.1

**Checklist**
- [x] Threads: create, list grouped by student + **Chưa rõ** + **Blank tests**, open.
- [x] Drop and paste of images, **PDF** and **DOCX** → `POST /files` → the **photo check card** (drag reorder, ⟳, ✕, +, 🔑, Existing test search, Run). No other fields.
- [x] D18: dropping into a thread that has already run is blocked, with a "Start a new thread" button.
- [x] The **running indicator**: thread name, current step, Stop, "keep the lid open", "on battery" (from `/system/status`), Resume/Discard for stopped or interrupted runs, the queued count.
- [x] A toast on `run.done` / `run.failed` (notification plugin).

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R15.1 | The photo check card contains exactly: the thumbnail strip controls (reorder, rotate, delete, add, 🔑), the Existing test search, and Run. Run sends an `ExtractInput` equal to the UI state (order, rotation, is_key, existing_test_id). | `APP_TEST` |
| R15.2 | **Real drop** of 3 JPGs onto the Tauri window → the photo check card shows 3 thumbnails. | `E2E_SHELL` |
| R15.3 | Dropping a 2-page PDF → 2 thumbnails; a DOCX with 1 image → 1 text page + 1 thumbnail. | `E2E` |
| R15.4 | S1 (replay): reorder + rotate → Run → the indicator shows the step names from SSE → the extraction card appears; Stop mid-run → Resume → done. | `E2E` |
| R15.5 | The indicator shows "keep the lid open" while running, and "on battery" only when `power_source = battery`. | `APP_TEST` |
| R15.6 | Dropping into a thread that has already run → no photo check card; a "Start a new thread" button is shown. | `APP_TEST` |
| R15.7 | `run.done` → the notification plugin mock is called once with the thread name. | `APP_TEST` |
| R15.8 | The sidebar groups: a blank thread appears under "Blank tests", an unknown student under "Chưa rõ". | `APP_TEST` |

**Verifier notes:** 2026-10-04, 777b768: ✅. Fresh clone, `npm ci` + `uv sync --frozen`; the Rust build reused the main copy's gitignored cache (`CARGO_TARGET_DIR=<repo>\app\src-tauri\target`) and was built from the clone (`npm run build`, then `npm run tauri:build -- --debug`, from PowerShell); `e2e:shell` ran with `ERH_SHELL_EXE` pointing at that build. S1 `TEST` 1004 passed, 14 deselected (live); S2 ruff clean, 163 files formatted, `mypy src` no issues in 81 files; S3 no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged. S7: vitest 53 passed (10 files), lint, typecheck and `check:urls` clean, `build` OK, `gen:types` (42 schemas + openapi.ts) no diff in `app/src/gen`; clean tree afterwards. R15.1 (`ThreadView.test.tsx`): a drop of a JPG, a 2-page PDF and a DOCX (text + image) gives 5 thumbnails, 1 of them a text page. The card's control list (every button, input, select and textarea) is compared with `toEqual` to exactly 🔑/⟳/✕ per page, Add pages, the file input, the Existing test search and Run. So there is no student field and no typed-key field (D17, D19); `PhotoCheckCard.tsx` has only the file input and the search input. After a drag reorder, ⟳⟳ (180), 🔑 on page 5, ✕ on page 4 and picking T-0042, the POST body `toEqual`s `{kind: extract, input: {pages: [fb2 r180, fa, fb1, fci is_key], existing_test_id: T-0042, supersedes_attempt_id: null}}`, the data-model `ExtractInput`/`PageInput` fields in UI order. R15.5: on AC, keep-lid-open is shown and on-battery absent; on battery both are shown; on battery with the run stopped, neither. The component renders on-battery only for `running.length > 0 && power === "battery"`. R15.6: a filled thread with an attempt and a run card: a drop gives no card and no `POST /files`, and Start a new thread is called with the dropped files. A 409 from Run and an active run in `/runs/active` also block. R15.7: `@tauri-apps/plugin-notification` is mocked; two `run.done` deliveries for one run → `sendNotification` called exactly once, title = the thread name "Lớp 8 HK1"; without Tauri, an in-app toast. R15.8: a blank test is under Blank tests; an unknown student and a pending thread are under Chưa rõ (the group label comes from `GET /threads`). E2E (`npm run e2e`) twice: 4 passed both times (17.5 s, 17.4 s). R15.3 drops the committed synthetic fixtures. I opened them: `two-pages.pdf` has 2 pages, and `one-image.docx` has 1 text paragraph and 1 inline image. The specs assert 2 thumbnails with 2 imgs for the PDF; for the DOCX, 2 tiles, tile 1 a text page and tile 2 an img; no broken page in either. R15.4 uses the committed `cassettes/s1` stand-ins and `--replay-delay-ms 700`. It checks 3 thumbnails, the reorder by file-id order, the rotate (`data-rotation` 90) and Run. It then checks a `run-step` text other than the "Starting…" placeholder (only SSE step/progress events or the seeded current step set it) and keep the lid open. Stop → Stopped, with no run card; Resume → the slot is empty, then the run card and a done toast. E2E_SHELL from PowerShell, twice: all passed (111 s, 92 s). R15.2 gave `hr=0x40100 effect=1 target=Chrome_RenderWidgetHostHWND root_ok=True drag_started=True` (qcd_calls 84 and 86), then cards 1, thumbs 3. I read `real-drop.ps1` in full. It calls ole32 `DoDragDrop` with a WinForms `DataObject.SetFileDropList` (CF_HDROP) and an IDropSource that drops on button release. The drag starts with a real `mouse_event` press on the helper's own window, and `SetCursorPos`/`mouse_event` moves carry it. The R15.2 path of `run.mjs` has no `dispatchEvent`, DataTransfer or page script; it only reads the conversation rect and DPR, then counts `photo-check-card` / `photo-thumb`. The earlier S1 run is API-only (no UI draft), and the UI is on the empty state before the drop, so the card and its 3 thumbnails come from the drop. R14.4: children gone 639 ms and 554 ms after the close. R14.5: 0 offending paths in both runs (excluded only %TEMP%: 1426 and 29). Dist: the only `http(s)://` strings are w3.org namespaces, `react.dev/errors` and `tailwindcss.com`, as in steps 13–14. Write scope: every implementation path in `f33b6a8..777b768` is in §6 row 15 (v1.1.28); the orchestrator commits 7dd1e1a, 23e5657, 7f84d68 and 777b768 are left out. `lib.rs` gains only `.disable_drag_drop_handler()`; plan.md gains only the five step 15 checklist ticks. Worth a look: (1) R15.2 asserts no "0 cards" before the drop and does not match the thumbnail file IDs to the sha256 of the dropped JPGs; attribution rests on the empty state and the API-only S1 run. (2) R14.5's "already newer than the start" count was 511 and 959 (14 and 16 in step 14), because my builds and tests ran just before; those paths are not re-checked. (3) Run 1 listed `Ollama\server.log` under other programs (an existing folder; the app's child was the stub). (4) R15.8's grouping is the server's `group` field; the UI test only checks that the groups are rendered.

---

## Step 16 — Cards, panels, Tests tab, extraction Review UI
**Depends on:** 15 · **PRD:** D1, D3, D9, D11, S2 (search), S3, S7 · §10.1

**Checklist**
- [x] The **extraction card**: "Extracted ✓", the unsure count, the **student chip** (assign existing / create from the name read), [Test], [Answers], [Grade] (disabled until step 19).
- [x] The **test panel**: the rendered clean test, editable metadata chips (`PATCH /tests`), **Print** (print CSS).
- [x] The **answers panel**: per question, the value read and ✓/✗/? placeholders; clicking a row → override (`PUT /attempts/…/answers/…`).
- [x] The **Tests tab**: search, attempt counts, merged tests hidden.
- [x] The **Review panel**: one item per screen showing the attempt page image + question, Accept / Fix / Skip with keys `Enter` / `E` / `→`, for every kind in Appendix E; **Review · N** updated through SSE `review.changed`.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R16.1 | Editing the school chip → the Tests search finds the new school. | `E2E` |
| R16.2 | Review `unknown_student` → "create from the name read" → the student chip shows "Học Sinh A", and Review · N decreases by 1. | `E2E` |
| R16.3 | The Review panel shows the attempt page image (`GET /files/{id}`) for `uncertain_answer`; `Enter` accepts, `E` opens the editor, `→` skips. | `E2E` |
| R16.4 | Print view: under `@media print` the sidebar and panel chrome are `display:none`, and each placeholder matches `^\[Hình: files/[0-9a-f]{2}/[0-9a-f]{64}\.\w+ · trang \d+\]$`. | `APP_TEST` |
| R16.5 | The Tests tab shows the attempt count per test (seeded: 2 attempts → "2"), and a merged test is absent. | `E2E` |
| R16.6 | Overriding an answer in the answers panel → `answers.teacher_override` is set (checked via `GET /attempts/{id}`). | `E2E` |

**Verifier notes:** 2026-10-05, 340f597: ✅. Fresh clone, `npm ci` + `uv sync --frozen`. S1 `TEST` 1005 passed, 14 deselected (live); S2 ruff clean, 163 files formatted, `mypy src` no issues in 81 files; S3 no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged. S7: vitest 94 passed (13 files), lint, typecheck and `check:urls` clean, `build` OK, `gen:types` (42 schemas + openapi.ts) no diff in `app/src/gen`; clean tree afterwards. E2E (`npm run e2e`) twice: 9 passed both times (37.4 s, 28.0 s). R16.1: the school is edited through the `meta-chip[data-field=school]` input (Enter); the Tests search "lomonoxop" then finds exactly the seeded test (accent-insensitive), and a nonsense query shows the empty state. R16.2: the S1 extraction really raises `unknown_student` (checked via `GET /review?status=open`); the chip reads "Unknown student" before; the panel shows "Học Sinh A"; Review · N is read just before Accept and must become exactly N−1; the chip then reads "Học Sinh A", and the item is in `?status=accepted`. R16.3: the image `src` matches `/files/<sha256>?…` and the image really loaded (`complete && naturalWidth > 0`). A request listener on `POST …/review/` sees 0 posts across the → skips and the E editor (shown, input focused, cancelled), then exactly 1 `…/review/<id>/resolve` on Enter; the item is accepted and the count drops by 1. R16.5: S1 is extracted a second time from the `run-2/` cassette copy (orchestrator decision) and merged with `POST /tests/{id}/merge`; `merged_into` is checked via the API, the survivor's row shows "2", and the merged test has no row. R16.6: an override and a "Confirm blank" are read back via `GET /attempts/{id}` as `"e2e override"` and `""`. R16.4 (`panels.test.tsx`): the real `styles/print.css` is injected into jsdom and the `@media print` rules with `display:none` are collected; the rendered sidebar `nav`, `panel-chrome` and the test toolbar match them, while the panel and the placeholders do not. 2 placeholders match the regex (the test's `PLACEHOLDER_RE` is character for character the plan regex): one `.png` from `picture_paths` and one `.jpg` fallback. The E2E repeats the hidden checks with `emulateMedia(print)`. The `picture_paths` API test (`test_routes_b.py::test_get_test_picture_paths`) stores a PNG and a JPG, references the PNG twice, and asserts the exact map of both stored paths; the route reads only `group.pictures` (the data model has pictures only on groups). Hands-on: `reviewActions.ts` covers all 11 kinds (labels, order, Accept = `{accept, null}`). The Fix values match `domain/review.py`: a `str` answer with `""` = blank, `string[]` key variants, a question id, `{student_id}`/`{full_name}`, an occasion string, `{points_per_question}`/`{section_total}`, `{content}`. `possible_duplicate`/`picked_test_mismatch` have Accept only, as in Appendix E; `ReviewPanel.test.tsx` checks Accept for every kind and a Fix body per kind. [Grade] is a literal `disabled` attribute (`toBeDisabled` in the E2E). `dist/` has only w3.org namespaces, `react.dev/errors` and `tailwindcss.com`, as in steps 13–15. Write scope: every implementation path in `f2d3bc9..340f597` (orchestrator commits b4caae3 and ee1f689 left out) is in §6 row 16 (v1.1.30). `app/src/index.css` was touched in 6aa4ba1 and restored in a766044 (net diff empty). The sidecar changes are only `api/routes/tests.py`, `tests/unit/api/test_routes_b.py` and `schema/openapi.json`; plan.md gains only the five step 16 checklist ticks. Worth a look: (1) the validator_failed Fix sends only `{content}`, so a key change through that editor is not possible (the sidecar accepts `keys`). (2) R16.3 checks that the image comes from `/files/` and loaded, not that its file id is the item's attempt page. (3) R16.4 matches elements against the collected print selectors in jsdom rather than computed styles; the E2E print emulation covers the real rendering. (4) Ctrl+K is wired in `hooks/useShortcuts.ts` but has no E2E.

---

## Step 17.1 — Grading domain logic *(may run alongside 17.2)*
**Depends on:** 10 · **PRD:** D2, D6, D13, D20, D24 · llm-design §5 · data-model §2.4–2.6

**Checklist**
- [x] `grade()` per the verdict table in **Appendix B.5**; no partial credit; score and `uncertain_points`.
- [x] `key_needed`, `verify_needed`.
- [x] Explanation cache with normalization (lowercase, trim, collapse spaces, curly → straight quotes).
- [x] Weak-point ranking: history + in-state verdicts; recency weight `w = 0.5^(rank of attempt, newest = 0)`; careless and spelling kept in `careless_notes`.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R17.1.1 | Every row of Appendix B.5 passes (the test holds B.5 verbatim). | `TEST` |
| R17.1.2 | Every `points_awarded` ∈ {0, full points} or `None` for `?`; the B.6 seeded worked example scores **7.5/9** with `uncertain_points` **0.5**. | `TEST` |
| R17.1.3 | `verify_needed` is true exactly for the B.7 cases and false for teacher-verified and `ai_verified` keys. | `TEST` |
| R17.1.4 | A student with no history still gets a ranking from in-state verdicts; with history, a newer error outweighs an older one on the same skill (weights 1, 0.5). | `TEST` |
| R17.1.5 | Normalization: `" He’s  gone "` and `"he's gone"` give the same `value_norm`, which is the explanation cache key and the weak-point view's join key (a seeded case counts 1 gap error). | `TEST` |
| R17.1.6 | Every row of Appendix B.8 (failure rules) passes. | `TEST` |

**Verifier notes:** 2026-10-05, 5d59d40: ✅. Fresh clone, `uv sync --frozen`. S1 `TEST` 1061 passed, 14 deselected (live); S2 ruff clean, 171 files formatted, `mypy src` no issues in 84 files; S3 no diff; S4 only `llm/defaults.py` (plus its `.pyc`); S5 exits 0; S6 `openapi.json` unchanged; clean tree afterwards. R17.1.1: the test's `B5` list was parsed against this plan's B.5 table: equal, 16 rows, character for character. R17.1.6: the test's `B8` list equals llm-design §5.1's 8 rows exactly; each row's test asserts the verdicts and Review items with no exception. R17.1.2: the B.6 seed (30 A=A, 4 B≠A, 2 unsure) → 7.5/9.0, `uncertain_points` 0.5; points ∈ {0, full, None}. R17.1.3 hands-on (`verify_needed`, threshold 0.8): low margin, `confidence=None`, section skill `pronunciation`/`stress`, a non-blank wrong answer and a wrong override → true; high margin with no attempt, a case/space-only difference, value None, a missing row, an override of `""`, `confidence == threshold`, and `teacher_verified`/`ai_verified`/`ai_uncertain` even with every trigger → false. This is B.7 as v2.7 states it. R17.1.4: weights `{current: 1.0, A-old: 0.5}` (and 0.25 for rank 2); the newer error ranks first; a no-history ranking passes. R17.1.5: `value_norm(" He’s  gone ")` = `value_norm("he's gone")` = `"he's gone"`; the seeded join counts 1 gap error. Purity: `scoring/keys/weakpoints.py` import only stdlib, pydantic and `erh.domain.*`; the tests use `no_io`. Scope: a555051, 909f981, c1899c6 and 5d59d40 touch only the three §6 row-17.1 modules, `tests/unit/domain/` and the plan's 4 checklist ticks (8d340d1, the orchestrator's v2.7, is left out). Nothing in `prompts/` or `llm/`. The teacher's and orchestrator's decisions are applied as recorded: near miss only for gap/word/verb/short; rewrite, combine and writing go to the judge; `""` override = blank; row 8 shadowed by row 1. **Cross-branch** with 17.2 (details in 17.2's notes): the scratch merge conflicts only in `docs/initial-plan/plan.md` (17.2's checklist ticks against v2.7's PRON-ED/PRON-S wording); after the merge, 1090 passed, 14 deselected. No code inconsistency. For step 18: (1) B.7's pronunciation/stress test reads `Section.skill` (`keys.py:33,66`), not the PRON-*/STRESS-* tags, which is correct since `verify_gate` runs before `tag_skills` (C.2). PRON-ED/PRON-S items are covered when extraction labels their section `pronunciation`, but such items in a `mixed` section are missed. (2) The history `SkillStats.careless` and the per-attempt rows need a query that the `student_skill_stats` view doesn't give (no attempt grouping, no careless column; already a known gap). (3) The data-model §2.5 comment `normalize(teacher_override or value)` reads an override of `""` as falsy, while `effective_value` treats it as blank. Step 18 should write `value_norm` the same way and skip `explain` for blank answers. (4) `rank_weak_points` leaves `WeakPoint.note_vi` empty, and `SummaryOut` has no per-weak-point note, so step 18 decides what fills it. (5) The tests use free-form tags (`"tenses"`), which is harmless because the tags are opaque strings.

## Step 17.2 — Grading prompts *(may run alongside 17.1)*
**Depends on:** 1, 4 (adapters, prompt hash) · **PRD:** D5, D6, D24 · llm-design §3.1, §5

**Checklist**
- [x] Base prompts for `ai_key_fast`, `verify_key`, `tag_skills`, `difficulty_notes`, `judge_rewrites`, `explain`, `weak_points_summary`, using the step 1 schemas.
- [x] The taxonomy copied from EnglishTest_Tutor's `ENGLISH_GRAMMAR_SKILL_TAXONOMY_prompt.txt` to `prompts/taxonomy/grammar.txt`, plus `prompts/taxonomy/sections.txt` (PRON-VOWEL, PRON-ED, PRON-S, STRESS-*, VOC-*, WF-*, READ-*, SIGN, REWRITE-*).
- [x] Thinking only for `verify_key` (`num_predict` 1500) and `judge_rewrites` (`num_predict` 400).
- [x] The required phrases of **Appendix D.3**.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R17.2.1 | Each grading task renders with the `chat` adapter. | `TEST` |
| R17.2.2 | Each rendered prompt contains every phrase listed for its task in Appendix D.3. | `TEST` |
| R17.2.3 | The `TagSkillsOut` allowed IDs are exactly the IDs parsed from the two taxonomy files. | `TEST` |
| R17.2.4 | Task configs: `think=false` for every task; output caps `verify_key` 1500 and `judge_rewrites` 400 (thinking was on for these two until llm-design v4.17). | `TEST` |

**Verifier notes:** 2026-10-05, 4d08c75: ✅. Fresh clone, `uv sync --frozen`. S1 `TEST` 1034 passed, 14 deselected (live); S2 ruff clean, 171 files formatted, `mypy src` no issues in 81 files; S3 no diff; S4 only `llm/defaults.py` (plus its `.pyc`); S5 exits 0; S6 `openapi.json` unchanged; clean tree afterwards. R17.2.1: each of the 7 tasks goes through `build_request` with the `chat` role (system + user messages, `format` = the schema, no `{{` left). R17.2.2: D.3 phrases are character for character the appendix's (checked by hand in each `.md`). R17.2.3: `taxonomy_ids()` gives 84 = 58 GR- + 26 section IDs, unique; every `GR-` token in `grammar.txt` is among them; the `TAG_SKILLS_SCHEMA` enum equals the list; PRON-ED, PRON-S and VOC-DICT are present. `grammar.txt`: working-tree sha256 08cf947f… equals the EnglishTest_Tutor file (both CRLF); the git blob is 2ec94e6 in both repos, so the stored (LF) sha256 is 3c115ed7…, as the test pins. R17.2.4 hands-on: `TASKS` shows think on only for verify_key (1500) and judge_rewrites (400); ai_key_fast 1024, tag_skills 2048, difficulty_notes 1024, explain 512, weak_points_summary 1024 (the recorded caps); all 7 use the `reasoning` role. Scope: ba5b0b0, 6448b40, ae102bd and 4d08c75 touch only `prompts/base/` (7 grading prompts), `prompts/taxonomy/`, `llm/tasks.py`, `tests/unit/{llm,prompts}/` and the 4 checklist ticks; nothing in `domain/`. This branch's plan is still v2.6.2, as expected. **Cross-branch (17.1 @ 5d59d40 × 17.2 @ 4d08c75):** a scratch `git merge` conflicts **only** in `docs/initial-plan/plan.md`, at the 17.2 checklist (these ticks against v2.7's "PRON-ED, PRON-S" wording; the resolution is v2.7's text, ticked). With that resolution: 1090 passed, 14 deselected; ruff, format and mypy clean. Consistency: judge `JudgeOut.verdict` ∈ {correct, incorrect} ⊂ 17.1 `JudgeResult` (step 18 adds `"failed"`); `ExplainOut.error_type` is the same `ErrorType` literal that 17.1's `CARELESS_TYPES` {careless, spelling} reads, and `explain.md` defines all 5 values; `TagSkillsCall.items[{question_id, tags}]` fits `attempt_stats(tags: question_id → tags)`, which treats tags as opaque, so section and GR- IDs both work; `AiKeyItem` (accepted ≥ 1, no confidence) + the client's logprob margin → `AnswerKey(status=ai_unverified, confidence=margin\|None)`, and None counts as low; `VerifyKeyOut.answer` is compared in step 18 with `value_norm` against `accepted`, and disagreement → `keys.verify_failed`. B.7's pronunciation/stress test uses `Section.skill` (`keys.py:33`), not the 17.2 tags; that is right because `verify_gate` runs before `tag_skills`, so PRON-ED/PRON-S need no code change. No inconsistency found. For step 18: map a judge failure to `"failed"`; compare `verify_key` answers with `value_norm`; skip `explain` for blanks; `QuestionTags` allows more than 3 tags although the prompt asks for 1–3 (low); `WeakPoint.note_vi` has no source in `SummaryOut`.

---

## Step 18 — Grade graph + `erh grade` (+ recording 👤)
**Depends on:** 17.1, 17.2 · **PRD:** D2, D6, D16, D24, S1, S2, S4, S5 · llm-design §5

**Checklist**
- [x] The `grade` graph with exactly the nodes and edges of **Appendix C.2**; the idempotent, version-checked `save` writing `grade_reports`.
- [x] Register the grade graph with the run manager, so that queued grade runs from step 10 now execute.
- [x] The CLI `erh grade --attempt A-… | --test T-…`.
- [x] **Recording 👤:** grade S1 live, then scrub and commit (`👤 sign-off: cassettes grade`).
- [x] Synthetic cassettes: truncated `verify_key`, a second student (all explanations cached), a key photo.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R18.1 | Nodes and edges equal Appendix C.2. | `TEST` |
| R18.2 | Recorded S1 grade → the keys go `ai_unverified` → `ai_verified`/`ai_uncertain` exactly for the B.7 cases; the score equals the recorded expectation; 1 `grade_reports` row with 3–5 teacher questions; the attempt `graded`; the run `done`. | `TEST` |
| R18.3 | Key photo → 0 `ai_key_fast` calls. | `TEST` |
| R18.4 | Blank test → key, tags and difficulty notes written; 0 `grade_reports`. | `TEST` |
| R18.5 | **S2 path:** a second attempt on an already graded test → 0 `ai_key_fast`, 0 `verify_key` for teacher-verified keys, 0 `tag_skills`, 0 `difficulty_notes`, and 0 `explain` calls for wrong answers already cached. | `TEST` |
| R18.6 | A truncated `verify_key` → the key `ai_uncertain` + 1 `uncertain_key`. | `TEST` |
| R18.7 | Stale state: an override made while a grade run is stopped → after Resume the verdict uses the override, and `grade` ran twice (the version mismatch). | `TEST` |
| R18.8 | Re-grade after a key is verified → only that question's `explain` runs again; the score changes as expected. | `TEST` |
| R18.9 | A crash between `save`'s commit and its checkpoint → no duplicate `grade_reports` or Review items. | `TEST` |
| R18.10 | Grade runs queued in step 10's tests now run to `done`. | `TEST` |
| R18.11 | The recorded grade cassettes are committed with `👤 sign-off: cassettes grade`. | `git log --grep` |

**Verifier notes:** 2026-10-05, bd5299a: ✅. Fresh clone, `uv sync --frozen`. S1 `TEST` twice: 1112 passed, 14 deselected (live), 0 skipped both times (195.6 s and 207.2 s); `test_recorded_s1_grade` ran (no skip). S2 ruff clean, 185 files formatted, `mypy src` no issues in 85 files; S3 no diff; S4 only `llm/defaults.py`; S5 `erh scrub --check tests/cassettes` exits 0; S6 `openapi.json` unchanged; clean tree afterwards. R18.1: the test's `C2_TEXT` equals this plan's C.2 block character for character (checked by script); the compiled graph's edge set and node set are compared by equality with the parsed edges (the version-mismatch `Command(goto="grade")` is not a static edge, as accepted). R18.2 (`test_grade_replay.py::test_recorded_s1_grade`): the expected B.7 set is computed in the test (own trim/casefold norm, margin < `GradeThresholds().key_margin` or None, section skill pronunciation/stress, non-blank override-or-value ∉ accepted), not from `keys.py`; keys that left `ai_unverified` = that set exactly, and the `verify_key` requests (from `llm_calls`) name exactly those questions; status counts 15 unverified / 5 verified / 14 uncertain; score 0.25/8.5 checked against the verdicts × points; 1 `grade_reports` row, 3–5 teacher questions, `uncertain_points` 8.25; attempt `graded` with the score; run `grade`/`done`. R18.3–R18.6, R18.8 (`test_grade_synthetic.py`): counts per node come from `llm_calls` joined to `steps` of the run, through the real CLI replay (no mocks): key photo 0 `ai_key_fast` and keys `from_key_photo`; blank test 6 `ai_key_fast`, 1 tag, 1 notes, 0 explain/summary, 0 reports; S2 path all zero except 1 `weak_points`, explanation reused (still 1 row), same score 1.25; truncated verify 2 `invalid` calls → that key `ai_uncertain` + 1 `uncertain_key`; re-grade after a teacher key → 1 `explain` whose request names only q1, score 1.25 → 1.0. R18.7: stop during `explain`, override + `bump_version`, resume → q2 `correct`, 2 `grade` steps, saves `[version_mismatch, saved]`, 1 report. R18.9: the injected raise comes after the real `save_grade` returned (its own transaction committed) and before the node returns (no checkpoint); the run is `interrupted`, resume → `done`, 2 `save` steps, and reports, Review items, explanations and messages are unchanged (1 report, ≥ 1 item). R18.10: a queued `enqueue_grade` row reaches `done` after `poke`. R18.11: `git log --grep "sign-off: cassettes grade"` → da97a0b only; its subject starts with bytes `f0 9f 91 a4`; it touches only `s1-grade/` (43 files, `SIGNOFF.txt` included) and has no Co-Authored-By trailer, while all 13 implementation commits carry `Claude Opus 5.5`; no other commit in `9e7cb3c..bd5299a` touches `s1-grade/`, and the folder has no diff from da97a0b to bd5299a. Lock race: `test_key_edit_deletes_explanations_and_fans_out` + `test_r12_4_stop_resume_discard_and_d18` looped 20 times: 20/20 passed. Every `async def` route does its DB work through `run_in_threadpool` helpers (`attempts.put_answer`, `review.resolve_item`, `runs.stop/resume/discard` via `_exists`, `tests.put_key/merge_test`, `threads.start_run`, `files.upload_file`); the rest are sync routes or call only the manager / Ollama. Privacy: `s1-grade/` contains no student name at all (not even "Học Sinh A"/"8X1"), no common Vietnamese surname followed by a capitalised word, no `lớp <class>` (only "lớp 8" as a grade level in prose); `grade.json` holds only `../s1`, `attempt`, T-0001, A-0001. Hands-on: `erh grade --help` lists `--data`, `--attempt | --test`, `--spawn-ollama | --ollama | --replay`; `erh run --replay tests/cassettes/s1` into a temp folder → `done`, then `erh grade --replay tests/cassettes/s1-grade --attempt A-0001` → `done`, 0.25/8.5 in 5.8 s; the DB has 1 report (3 teacher questions), the attempt `graded`, calls 6 ai_key_fast / 32 verify_key / 1 tag / 1 notes / 1 summary. Scope: every implementation path in `9e7cb3c..bd5299a` (orchestrator fc6412a, 9948558 and teacher da97a0b left out) is in §6 row 18 (v1.1.34): `store/repos/attempts.py` has only additions, `api/app.py` adds only the `register_grade` lines, `llm/tasks.py` only the 3-tag cap, `llm/cassettes.py` only the grade manifest; plan.md gains only the five step 18 checklist ticks. Accepted and parked as instructed (not failures): the S1 recording's model-quality results (verify_key at the think cap, 0.25/8.5, 0 explain calls), `note_vi` = `""`, and B.7 not firing for pronunciation/stress items in a `mixed` section. Worth a look: (1) in Git Bash, `erh grade --help` prints the metavars `A-…`/`T-…` as `A-�` (console code page; cosmetic). (2) R18.10 counts calls with the test's fake (`h.fake.calls`), not `llm_calls`; R18.10 itself needs only `done`. (3) R18.2's expected values (15/5/14, 0.25/8.5) are pinned from the recording; the B.7 set and the score are cross-checked independently.

---

## Step 19 — Grade & Review UI
**Depends on:** 16, 18 · **PRD:** D2, D4, D6, D9, D13, D24, S1, S2, S3, S5, S7

**Checklist**
- [x] The **Grade** button; the **grade card**: `earned/possible` + unsure points, ✓/✗/`?` by printed number, explanations, weak points, careless notes, teacher questions, and an override per row.
- [x] **Report print** and a separate **key print** (the key copy, D4).
- [x] A **key editor** (verifying triggers re-grades).
- [x] The Review panel actions for grade-related kinds plus `possible_duplicate` → merge with an alignment preview, and `points_assumed` → a points editor.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R19.1 | An S1-like **synthetic extract and grade seeded to B.6** (`tests/cassettes/s1-seeded/`; the recorded S1 has 34 questions = 8.5 points, so it cannot reach B.6) → Grade → the card shows `7.5/9` and "0.5 unsure", 3–5 teacher questions, weak points and careless notes. The report print view hides the chrome and marks `?` rows. | `E2E` |
| R19.2 | S4 blank test → Grade → **key print** lists one key per question and contains no student data. | `E2E` |
| R19.3 | S2 (replay): the Existing test search → pick → Run → Grade → 0 `transcribe_page`, 0 `ai_key_fast`, 0 `verify_key` for `ai_verified`/`teacher_verified` keys, and 0 `explain` calls for wrong answers already cached (via `GET /runs/{id}` step list). | `E2E` |
| R19.4 | Fixing an `uncertain_answer` in Review → 1 grade run queued and `done` → the score on the card updates. | `E2E` |
| R19.5 | Verifying a key in the key editor with 2 graded attempts on the test → 2 grade runs queued. | `E2E` |
| R19.6 | `possible_duplicate` → merge → the moved attempt is listed under the survivor; the merged test is absent from Tests. | `E2E` |
| R19.7 | `points_assumed` → set 0.5 per question → `points_possible` and the score update. | `E2E` |

**Verifier notes:** 2026-10-05, 277bd37: ✅. Fresh clone, `npm ci`, `uv sync --frozen`. S1 `TEST`: 1113 passed, 14 deselected (live), 0 skipped (281 s). S2 ruff clean, 187 files formatted, `mypy src` no issues in 85 files; S3 no diff; S4 only `llm/defaults.py`; S5 `erh scrub --check tests/cassettes` exits 0; S6 `openapi.json` unchanged. S7 `npm test -- --run` 15 files / 101 tests passed; `lint`, `typecheck`, `check:urls` pass; `build` passes (Playwright's webServer runs it); `gen:types` no diff in `src/gen`; clean tree afterwards. `E2E` three times: run 1 16/16 passed; run 2 15/16, **R16.5 failed** in the pre-existing step 16 helper `seed.ts::extractS1` ("ended without an attempt", run `done`): it reads `GET /threads/{id}` and then `GET /runs/{id}`, so a run that saves between the two reads throws (run 2 shared the CPU with vitest/gen:types); run 3 (no other load) 16/16 passed. Not a step 19 regression (step 19 doesn't change `extractS1`; `GET /runs/{id}`'s change only names tasks), so step 16 stays ✅; worth fixing the helper's read order. Specs read against each requirement: R19.1 (`s5-grade.spec.ts`) the card shows `7.5/9`, "0.5 unsure" (`data-points` 0.5), 3–5 `teacher-question`, a `weak-point`, 2 `careless-note`, run `grade`/`done`; the report has 36 rows, 2 `?`, 4 `✗`; under print media nav, panel chrome, toolbar and conversation are hidden, `?` rows have a solid outline and `✓` rows none (`styles/print.css`). R19.2: the key print lists one row per question id, equal as sets to the test's questions, none empty; the printed body has no "Học Sinh A"/"8X1" and no visible answer/report rows or student chip (grade started through the API with `attempt_id: null`, accepted). R19.3 (`s6-grade-review.spec.ts`): counts come from `GET /runs/{id}` step calls (logged: extract `{read_header:1, read_answers_page:3}`, grade `{weak_points_summary:1}`): 0 `transcribe_page`, 0 `ai_key_fast`, 0 `verify_key` (4 keys `ai_verified` after A's grade, which made 4 `explain` calls), 0 `explain`; `test_run_details.py` checks `explain`→`explain`, `weak_points`→`weak_points_summary`, `retranscribe_tiles`→`transcribe_page`, a stored `request.task` wins, and an empty step. R19.4: the fix's `followup_run_ids` has exactly 1 run (`grade`, attempt A, `review_fix`), `done`, card 7.5/9 → 7.75/9, unsure 0.25. R19.5: the key PUT returns 2 `run_ids`, both `grade` on attempts {A, B}, both `done`; `key-regrades` `data-count` 2. R19.6: Accept opens the preview (36 rows, each equal to the proposal's `question_alignment`), the resolve is sent on Merge; the moved attempt's `test_id` is the survivor; the merged test is absent from Tests and the survivor shows 3 attempts. R19.7: the editor shows "12 × 0.5 = 6 points", 1 follow-up run, `points_possible` 6, card 3/3 → 6/6. B.6 cross-check (own script, not the UI): `erh run --replay s1-seeded/extract` + `erh grade --replay s1-seeded/grade --attempt A-0001` into a temp folder → `done`; from the DB, 36 questions all 0.25 (9.0), my own B.5 verdicts (rule 1 unsure without override, rule 3 key `ai_uncertain`, rules 4/5 MCQ = key) equal the stored ones for all 36: 30 correct, 4 incorrect, 2 uncertain (both `reading_unsure`) → earned 7.5, unsure 0.5; attempt `graded` 7.5/9; report `uncertain_points` 0.5, 3 teacher questions, 1 weak point (2 gap errors), careless notes present. `make_s1_seeded.py` re-run in the clone (28 s) reproduces every `s1-seeded` file except `recorded_at` timestamps. Hands-on: the grade card's rows reuse `AnswerRow`, whose save does `PUT /attempts/{id}/answers/{qid}`; the route enqueues a `review_fix` grade for a graded attempt (`test_routes_b.py`, step 12); `KeysPanel` Verify sends `PUT /tests/{id}/keys/{qid}` `{verify: true}` and shows the returned `run_ids` (`GradeCard.test.tsx` "verify → PUT"); report and key prints are separate panel views (`report` and `keys` in `panelView.ts`); `dist/` has only w3.org namespaces, `react.dev` error links and a Tailwind licence comment, none fetched (`offline.spec.ts` passes). Privacy: `s1-seeded/` holds only `student_name` "Học Sinh A"/null and `class_name` "8X1"/null, the made-up header "TRUONG THCS A", file names `De-seeded (n).jpg`/`De-points (1).jpg`, and no common Vietnamese surname followed by a capitalised word. Scope: every implementation path in `main...277bd37` (orchestrator 1028a03, caf5fe1, 4a7b805 left out) is in §6 row 19 (v1.1.36); `store/repos/runs.py` untouched; `routes/runs.py` changes only `_task` and its call; plan.md gains only the four step 19 checklist ticks (8500be2, 6b3a0c3); no commit touches `s1-grade/` or another teacher-signed folder (no diff in `main...277bd37`); all 12 implementation commits carry `Claude Opus 5.5`. Accepted as instructed (not failures): R19.1's synthetic B.6 test, R19.2's API start, the E2E specs' own replay sidecars, the node→task map, R19.3 on the synthetic `student-b-*` scenarios, Merge-only accept, the 3 re-recorded summaries in `fix-a`/`points-regrade`. Worth a look: (1) the `extractS1` race above. (2) No unit test drives the override from the grade card itself; it reuses the tested `AnswerRow` and route.

---

## Step 20 — Settings, backup, maintenance
**Depends on:** 16 · **PRD:** §10.2, R7 · data-model §5.5

**Checklist**
- [x] The **Settings** page: the model tag per role (`PUT /settings` → `models.toml`), backup / restore, "clear logs older than N days", the Ollama status and version, the other-Ollama warning, and **Download models** (`ollama pull` with progress over SSE).
- [x] Scheduled maintenance: the sweep, the checkpoint purge and the **log retention** (delete `llm_calls` older than `log_retention_days`, default 45, except those referenced by explanations) at startup and every 24 h.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R20.1 | Changing the reasoning tag in Settings → `models.toml` is updated, and the next call uses the new tag (FakeOllama request). | `TEST` + `E2E` |
| R20.2 | Backup → restore into a new folder (via the API) → identical row counts and file hashes. | `TEST` |
| R20.3 | Clear logs (N = 7) deletes only `llm_calls` older than 7 days that aren't referenced by explanations. | `TEST` |
| R20.4 | `other_ollama_loaded=true` → the warning banner shows in Settings and the sidebar. | `APP_TEST` |
| R20.5 | Download models shows per-model progress from SSE and ends "ready" (FakeOllama pull stream). | `E2E` |
| R20.6 | The maintenance scheduler runs the sweep and purge at startup (a log line and fake-clock tests for 24 h). | `TEST` |
| R20.7 | Portability: copying the whole app folder to a new location and starting from there → the same threads, tests and files are shown (all paths are relative to the app folder). | `TEST` (sidecar level) + `E2E_SHELL` |
| R20.8 | Log retention: with the default setting (45 days), the maintenance run at startup deletes `llm_calls` older than 45 days that aren't referenced by explanations, and keeps the rest (fake clock). | `TEST` |

**Verifier notes:** 2026-10-05, 83ef695: ✅. Fresh clone at 83ef695 (scratchpad), `npm ci`, `uv sync --frozen`; the Rust build reused `CARGO_TARGET_DIR=D:\Projects\Exam_Revision_Helper\app\src-tauri\target` (the crate recompiled from the clone's path; the exe contains the clone's `dist` asset name `index-C086nYi5.js`, and its sidecar dir comes from the clone's `CARGO_MANIFEST_DIR`). S1 `TEST`: 1122 passed, 14 deselected (live) (220 s); the 9 tests of `test_step20.py` all pass. S2 ruff clean, 189 files formatted, `mypy src` no issues in 86 files; S3 no diff; S4 only `llm/defaults.py`; S5 `erh scrub --check tests/cassettes` exits 0; S6 `openapi.json` unchanged. S7 `npm test -- --run` 16 files / 108 tests passed; `lint`, `typecheck`, `check:urls`, `build` pass; `gen:types` no diff in `src/gen`; clean tree afterwards. `cargo test` 13 passed. `E2E` twice: 18/18 and 18/18. `E2E_SHELL` twice back to back from PowerShell (nothing else running): both "all passed", 0 FAIL (R14.4, R14.5 0 AppData writes, R15.2 real drop 3 thumbs, R20.7). Specs read against each requirement: R20.1 the test calls the client before (old tag in the FakeOllama request), `PUT /settings` the reasoning tag, then `load_models_config` reads the new tag from `models.toml` and the next FakeOllama request carries `qwen3:8b-new`; the E2E (`settings.spec.ts`) fills the role input, saves, and finds the tag in `GET /settings` and in `<data>/models.toml` (old tag gone, other roles unchanged, a reload shows it). R20.2 S1 extracted by replay + a student, `POST /maintenance/backup` → a `.zip` in `backups/`, restore via the API into a new folder → per-table row counts of every table equal and SHA-256 of every file under `files/` equal (non-empty). R20.3 calls 8 d, 30 d (referenced), 6.9 d, 1 d → N = 7 deletes 1, keeps the referenced and the younger ones. R20.4 (`settings.test.tsx`) `other_ollama_loaded=true` → `sidebar-ollama-warning` in the Sidebar navigation and `settings-ollama-warning` in the panel; false → absent, then shown after `system.changed`. R20.5 E2E sidecar started with `ERH_FAKE_OLLAMA_PULL=300`: one row per configured model, the first shows `downloading N%` from SSE, each ends "ready", button re-enabled. R20.6 `api.serving` with maintenance on → exactly one `maintenance: swept 0 files…` record (logger `erh.maintenance`) and 1 report before the app serves; fake clock: runs at t0, +24 h, +48 h (sleeps 86400 s), the unreferenced file survives run 1 (24 h grace) and is swept in run 2, 4 checkpoint/writes rows of the `done` run purged and the `running` run's kept. R20.7 sidecar test copies the app folder, `rmtree`s the original, and gets equal `/threads`, `/tests`, `/tests/{id}` and the bytes of every file; it also scans every text value of the DB for the temp root or a drive path. My own spot check: `erh run --replay s1` into a temp folder, then every string/blob in every table scanned for drive letters, `AppData`, `/Users/` and the scratchpad path: 0 real hits (only JSON `\\"` escapes); `files.path` is `files/3e/<id>.png`. The E2E_SHELL phase (read in `run.mjs`): it captures threads/tests/run thread/first page file through the API after the R15.2 drop, closes the app, `cpSync`s the app folder, deletes the original, relaunches with `ERH_APP_DIR` = the copy, checks `GET /settings` `data_folder` is under the copy, the same thread ids (2/2) and test ids (1/1) in the UI, the S1 extraction card, and a page image (width 1204). The ready check now uses `$$(…).length === 0` (correct; `$` returns one element). R20.8 at startup with the default: 46 d deleted, 90 d (referenced), 44 d and 0 d kept; fake clock: 45.5 d deleted, 44.5 d kept until the next day's run deletes it; `log_retention_days` 7 from `PUT /settings` applies to the next run. Checked by hand: `erh serve --replay` on a folder with an `llm_calls` row from 2026-01-01 and one from 2026-10-01 → after start only the second remains (maintenance runs in `erh serve`; `make_ctx` turns it off only in the API tests). §7 items: retention is one `DELETE … WHERE julianday(created_at) < julianday(?) AND NOT EXISTS (… explanations …)` inside `transaction()` (aware cutoff required); `sweep()` deletes rows in the transaction and unlinks disk files only after it exits (commit), orphans after; `FileStore.put` and `_remove_orphans` use `paths.files_dir`; `run_maintenance` opens its own connection and runs via `asyncio.to_thread`, errors are logged and the loop continues; the purge also covers `failed` runs (not resumable per `runtime/manager.py`). Fake pull hook: only `_pull_transport` reads `ERH_FAKE_OLLAMA_PULL` (no other use in `src`); with it unset and `--replay`, `_pull` publishes "error: no Ollama in replay mode" per model and returns without an HTTP client (tested); `/system/status` also skips Ollama in replay. Backup zip names are relative (`app.db`, `models.toml`, `files/…`); restore rejects absolute/`..`/other members, a non-empty target and AppData. `dist/`: only w3.org namespaces, `react.dev` error links and a Tailwind licence comment, none fetched. Scope: every implementation path in `main...83ef695` (orchestrator 1fd0984 left out) is in §6 row 20 (v1.1.37); plan.md gains only the two step 20 checklist ticks (146fc26, d0aa8f0); all 10 implementation commits carry `Claude Opus 5.5`. Accepted as instructed (not failures): photo-check uploads swept after 24 h (documented in `sweep()`), the fake pull hook, maintenance off in `make_ctx`, the text-input restore / editable retention / read-only data folder, the runner-only fix in 83ef695, the unreproduced vitest flake. Worth a look: (1) `erh serve` sets up no logging handler (uvicorn `log_level="warning"`, no `basicConfig` in `src`), so the INFO `maintenance:` line exists only for the logging system (caplog), not in any visible output or file; a failed run (ERROR) does reach stderr. (2) The scheduler advances `due` by 24 h and sleeps `max(wait, 0)`, so after the wall clock jumps ahead by several days it runs the missed runs back to back (harmless, redundant). (3) The E2E_SHELL R20.7 copy moves `ERH_APP_DIR` (data + webview), not the exe, which lives in `target/debug`; the packaged-folder move belongs to step 21; the second start is not covered by the R14.5 AppData check. (4) Settings labels the data folder "App folder:". (5) A relative `new_folder` in restore resolves against the sidecar's working folder, not the app folder.

---

## Step 21a — Unreadable text (D25)
**Depends on:** 9, 10, 16 · **PRD:** D9, D25, S7, §10.1 · llm-design §4, §8 (v4.11) · data-model §2.5, §2.8, §5.3 (v1.6)

Why not after M1: every check here runs on replay and synthetic cassettes, with no tuned model. M1 tunes prompts, so the `???` rule should be in the prompts M1 tunes, not added after it. M1 may reword the rule; the Appendix D.2a phrases must stay.

**Checklist**
- [x] The `???` rule in `prompts/base/transcribe_page.md` (also used by `retranscribe_tiles`) and `prompts/base/read_answers_page.md`, with the **Appendix D.2a** phrases.
- [x] `ReviewItem.kind` gains `unreadable_text` (data-model v1.6); the schema export and the TS types are regenerated.
- [x] `merge_and_normalize`: the validators accept `???` as text; each page whose final text contains `???` → one pending `unreadable_text` with `{page_no, file_id, spans}` (data-model §2.8); `save` writes it with the other pending items.
- [x] `resolve_answers`: a value containing `???` → `reading_unsure`, confidence capped at threshold − 0.01, value kept.
- [x] `domain/review.py`: Accept and Fix for `unreadable_text` (data-model §5.3, Appendix E); Fix goes through the content edit (re-validated).
- [x] The **Review panel** for `unreadable_text`: the test page image (`proposal.file_id`), each span's text with `???` marked, and an editor per span; `Enter` / `E` / `→` as for the other kinds.
- [x] A synthetic extract scenario `unreadable/` (stand-in PNGs; `???` on pages 1 and 3, two fields on page 1, one student answer `???`).

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R21a.1 | The rendered `transcribe_page` and `read_answers_page` prompts contain every phrase of **Appendix D.2a** (the test holds D.2a verbatim). | `TEST` |
| R21a.2 | The `unreadable/` scenario → exactly **2** `unreadable_text` items, one per page with `???` (pages 1 and 3), none for page 2. Each proposal has the right `page_no`, `file_id` = that page's `test_pages.file_id`, and one span per field with `???` (page 1: 2 spans). A picked-test run (no transcription) → 0 items. | `TEST` (replay) |
| R21a.3 | Fix with typed words → the listed fields hold the typed text and no longer contain `???`; other fields are unchanged; status `fixed`; 0 runs queued. A Fix that fails validation is rejected and the database is unchanged. | `TEST` |
| R21a.4 | Accept → the content is unchanged (the `???` spans stay); status `accepted`; 0 runs queued. | `TEST` |
| R21a.5 | A student answer read as `???` → `reading_unsure = true`, confidence ≤ threshold − 0.01, the value kept; after Grade its verdict is `uncertain` (`?`, B.5 row 1). | `TEST` |
| R21a.6 | The Review panel shows an `unreadable_text` item with the page image (`GET /files/{proposal.file_id}`, loaded), the text with the `???` marked, and the editor (`E`). Typing the words and saving → `GET /tests/{id}` returns them in place of `???`, and Review · N decreases by 1. | `E2E` |
| R21a.7 | R10.1's table covers the two `unreadable_text` rows of Appendix E (graded and ungraded), and R10.2's Skip check covers all 12 kinds. | `TEST` |

**Verifier notes:** 2026-10-06, 2ccc3b7: ✅. Worktree on `step/21a-unreadable-text` (base `step/M1-extraction-quality`), `uv sync --frozen`, existing `node_modules`. S1 `TEST`: 1160 passed, 14 deselected (live) (235 s). S2 ruff clean, 193 files formatted, `mypy src` no issues in 86 files; S3 no diff; S4 only `llm/defaults.py`; S5 `erh scrub --check tests/cassettes` exits 0; S6 `openapi.json` unchanged. S7 `npm test -- --run` 113 passed; `lint`, `typecheck`, `check:urls` pass; `gen:types` no diff in `src/gen`; clean tree afterwards. `E2E` 19/19 (incl. `s7-unreadable.spec.ts`); `E2E_SHELL` not run (not needed for 21a). Specs read against each requirement: R21a.1 (`test_unreadable_prompts.py`) holds D.2a verbatim and renders both prompts with the base and `hk1_lop8` profiles; `retranscribe_tiles` uses the `transcribe_page` task. R21a.2 (`test_unreadable_replay.py`) exactly 2 items, pages [1, 3], none for 2; page 1 spans = instructions + Q1 stem; page 3 one span; each `file_id` = `test_pages.file_id`, dedupe `unreadable_text:<test_id>:p<n>`, each span's text equals the stored field; 0 `retranscribe_tiles` steps, 0 `validator_failed`; the picked run has 0 `transcribe_page` steps and adds no item. Own replay (`erh run --replay unreadable/filled` into a temp folder): `unreadable_text:T-0001:p1` (2 paths) and `:p3` (1 path), file ids match, the `???` answer stored `reading_unsure=1`, confidence 0.69 (threshold 0.7). R21a.3 (`test_review.py`) graded and ungraded: status `fixed`, 0 follow-up and 0 queued runs, content equals the `???`-free original; 7 invalid bodies (empty, unlisted path, text None/missing, bare list, label `Z` failing `validate_mcq`, valid+invalid mixed) raise `InvalidResolution` with the whole-DB dump unchanged. R21a.4: status `accepted`, 0 runs, only `review_items` differs, content keeps the `???`. R21a.5: Q4 (word form) value `???` kept, `reading_unsure`, confidence ≤ 0.69, the attempt's only `uncertain_answer`; `grade_answer` → (`uncertain`, rule 1), `grade` → `points_awarded` None and `uncertain_points` = Q4's points (domain scoring, not a grade-graph replay, as accepted). R21a.6: the item is reached with →, `src` contains `/files/{proposal.file_id}?` and `naturalWidth > 0`, 2 spans each with a `???` mark, `E` opens 2 pre-filled boxes (first focused), save → `POST /review/{id}/resolve` ok, Review · N = before − 1, `GET /tests/{id}` holds the typed text without `???`, item in `status=fixed`. R21a.7: `ROWS` has 22 rows incl. both `unreadable_text` rows (each run graded and ungraded); `test_skip_covers_all_12_kinds` checks `MAKERS` = the 12 `ReviewItem.kind` literals, and R10.2's Skip test is parametrised over `MAKERS`. Scope: every changed path in `step/M1-extraction-quality..2ccc3b7` (orchestrator 9597e5b left out) is in §6 row 21a; `domain/llm_schemas.py` and `api/routes/review.py` untouched; the only cassettes added are the new synthetic `unreadable/{filled,picked}` (stand-in 400×600 PNGs, `Học Sinh A`/`8X1`), no existing cassette changed, no fixture or teacher field committed; all implementation commits carry `Claude Opus 5.5`. Accepted as instructed (not failures): MCQ/T-F answers cannot be `???` (§7, M1); R21a.5's Grade via domain scoring; the Fix uses the `validator_failed` content edit (the `write_test_meta` wording, §7); the run-id dedupe key rewritten in `save`. Worth a look: (1) the step 21a checklist above was left unticked by the implementer (plan §1.3). (2) The Fix rejects only validator failures it adds, so a page already failing a validator stays fixable; a `???` the teacher leaves in a box stays `???` (by design, "Text left as ??? stays").

---

## Step 21 — Packaging & first run
**Depends on:** 19, 20, 21a, M1, M2 · **PRD:** §11, §13 Phase 4, R5

**Checklist**
- [x] The sidecar frozen with **PyInstaller (folder mode)** into Tauri resources; the shell launches the frozen sidecar in release builds.
- [x] The default `models.toml` and confidence/similarity thresholds taken from the M1/M2 reports (the thresholds are the `ExtractThresholds` / `GradeThresholds` defaults in code; there is no TOML setting).
- [x] **First-run setup**: Ollama missing → a link; version < 0.12.11 → "update"; models missing → Download models.
- [x] The NSIS installer; the size recorded in `docs/release-notes.md`; any antivirus flags noted.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R21.1 | `TAURI_BUILD` succeeds and outputs an NSIS installer. | Run it |
| R21.2 | `E2E_SHELL` against the **release build**: the frozen sidecar starts, and Settings shows its version (equal to `erh --version`). | `E2E_SHELL --release` |
| R21.3 | The first-run screen shows the correct message for each of 3 mocked `/system/status` states. | `APP_TEST` |
| R21.4 | The shipped defaults equal the values in `docs/initial-plan/phases-testing/m1-report.md` and `docs/initial-plan/phases-testing/m2-report.md`. | Compare |
| R21.5 | `docs/release-notes.md` records the installer size, the frozen sidecar size and the antivirus scan result (Windows Defender `MpCmdRun -Scan`). | Read the file |

**Verifier notes:** 2026-10-12, 281b140: 🔄. **Fails one check: PRD §11 (v4.10) vs the installer.** The installer always writes `HKCU\Software\examrevisionhelper\Exam Revision Helper` (`WriteRegStr SHCTX "${MANUPRODUCTKEY}" "" $INSTDIR`, plus the MUI `Installer Language` value in the same key: `MUI_LANGDLL_REGISTRY_KEY` = `MANUPRODUCTKEY`, saved on the install-files page). PRD §11's accepted exceptions list only the shortcuts, "its uninstall entry in the registry (HKCU)" and the WebView2 download, and say "the uninstaller removes them". The uninstaller deletes this key **only when "Delete app data" is ticked** (`DeleteRegKey SHCTX "${MANUPRODUCTKEY}"` sits inside `${If} $DeleteAppDataCheckboxState = 1`), so after a default uninstall the key stays. `docs/release-notes.md` lists the key ("Install-folder record") with the right path, but its line "The uninstaller … removes them" is wrong for this key. This is a teacher decision (accept the key in PRD §11 and correct the release notes, or change the template to delete the key on every non-update uninstall); it is not resolved here. Everything else passes. On the branch, `uv sync` state as found, existing `node_modules`. S1 `TEST`: 1307 passed, 14 deselected (live) (293.6 s). S2 ruff clean, 207 files formatted, `mypy src` no issues in 88 files; S3 no diff; S4 only `llm/defaults.py` (and its `.pyc`); S5 `erh scrub --check tests/cassettes` exits 0; S6 `openapi.json` unchanged. S7 `npm test -- --run` 124 tests: run 1 (while pytest was running) 1 failed / 123 passed, not captured; 7 further runs 124/124; `lint`, `typecheck`, `check:urls` pass; `gen:types` no diff in `src/gen`. `cargo test` 16 passed. `E2E` (headless Playwright) 19/19 passed (1.1 min), so the §7 tiles-on regression is fixed (`app/e2e/sidecar.ts` writes `[extract] retranscribe_tiles = true`, `retranscribe_tiles_keep = "always"` into the replay sidecar's `models.toml`; no cassette changed). Clean tree afterwards. R21.1: `npm run tauri build` re-run: exit 0, "Finished 1 bundle", `Exam Revision Helper_0.1.0_x64-setup.exe` **45,013,194 bytes** (42.93 MiB; release notes: 45,000,727, +12,467 bytes; a rebuild of the same commit is not byte-identical); shell exe 10,796,544 bytes and frozen sidecar folder 159 files / 107,518,802 bytes, both equal to the release notes; the generated `target/release/nsis/x64/installer.nsi` carries the ERH default folder and installs `$INSTDIR\sidecar\…`. `tauri-cli.mjs` adds `tauri.release.conf.json` only to a bundling `build` (tested); the base config has no resources. `installer.nsi` = tauri-cli 2.12.1's built-in template (extracted from `cli.win32-x64-msvc.node`) with exactly one change (the currentUser default `$LOCALAPPDATA\${PRODUCTNAME}` → `D:\ExamRevisionHelper`, else `$PROFILE\ExamRevisionHelper`) plus the 5-line header. R21.2: E2E_SHELL `--release` not re-run (it moves the mouse); the orchestrator's run at 281b140 ("all passed") is taken as the result. Read in `run.mjs`: `--release` copies the release exe and its `sidecar\` into a fresh temp app folder and starts it **without** `ERH_APP_DIR`, so the app folder is the exe's own (`paths.rs` `exe_dir`); the sidecar child must be exactly one `erh.exe` directly under the app process, and no `uv.exe`/`python.exe` among the app's children and the tracked descendants; `<app>\data\app.db` exists and `<app>\sidecar\data` does not; Settings' `sidecar-version` text must equal both `uv run erh --version` and the copied `erh.exe --version` (both `0.1.0` by hand here); R20.7 copies the whole folder (exe + sidecar + data) and starts the copy's exe. The shell: release builds take `SidecarMode::Frozen` (`<exe dir>\sidecar\erh.exe serve --ollama|--replay`, cwd = app folder, env only `ERH_APP_DIR`, no `--data`; spawn tests), debug keeps `uv run erh serve`; a missing frozen exe is an error, a missing Ollama is not (no `ollama serve`, the first-run screen shows). DevTools switch: Cargo `devtools` feature; `devtools_enabled(debug, env)` = debug or `ERH_WEBVIEW_DEVTOOLS == "1"` (unit test: off for None/"0" in release); the only setter in the repo is `run.mjs --release`. R21.3 (`firstRun.test.tsx`, through `Connected` with a fake API): `unreachable` → `data-need=install`, "Ollama is not installed or not running", the address `ollama.com/download`, the button calls `invoke("open_ollama_download")`, no app shell; `too_old` (0.11.4) → "Ollama 0.11.4 is too old … update Ollama to 0.12.11 or newer", "Update Ollama"; `missing_model` → the missing tag listed, Download models posts `/settings/models/pull`, a row shows "downloading 25%" from SSE, and `ok` after `success` shows the app. Also hidden for `ok` and replay; "Continue anyway" is kept in sessionStorage. The shell command opens a fixed URL via `explorer.exe`; `src/` holds the address without a scheme (`check:urls` passes). R21.4: `DEFAULT_ROLES` vision `numind/nuextract3:Q6_K` = m1 §4 "Decision: vision=…"; `DEFAULT_EXTRACT["retranscribe_tiles"]` False = m1 "Decision: tiles=off"; reasoning `qwen3.5:4b` = m2 §4 "Decision: reasoning=qwen3.5:4b"; reasoning `think` False and `GRADING_THINK = frozenset()` = m2 §5; `ExtractThresholds` reading 0.7, key_photo 0.7, looks_like 0.85, possibly 0.5, sanity 0.5 and `GradeThresholds.key_margin` 0.7 = the m1 §4 thresholds table. Step 21 changed only comments in `defaults.py`. R21.5: the release notes record the installer size, the frozen sidecar size (and the shell's) and the Defender result. Re-scanned the rebuilt artifacts (`MpCmdRun -Scan -ScanType 3 -File … -DisableRemediation`, no signature update): installer, `target\release\sidecar` and the shell exe all "found no threats". Restore-path fix (§7): `restore(…, base=settings_path(ctx).parent)` makes a relative `backup_path`/`new_folder` absolute against the app folder (the data folder with `--data`); `test_step21.py` checks the app layout (result `<app>/restored`, nothing in the working folder), `--data`, and an absolute path unchanged. Release-notes locations table: start-menu `.lnk` (`$SMPROGRAMS`, `STARTMENUFOLDER` empty, current-user context), desktop `.lnk` (finish-page option, or passive/silent), `HKCU\…\Uninstall\Exam Revision Helper` (`UNINSTKEY`, removed on uninstall) and `HKCU\Software\examrevisionhelper\Exam Revision Helper` (`MANUFACTURER` = `examrevisionhelper` in the generated script) are accurate; only the "removes them" line is wrong (above). Scope: every path in `0e49822..281b140` is in §6 row 21 (v1.1.77) or an orchestrator doc (`docs/{structure,PRD,llm-design,plan}.md`); `sidecar/tests/unit/api/test_routes_c.py` is not named, but its two edits only add `sidecar_version`/`replay` to the exact `/system/status` bodies that the in-scope `system.py` change requires, so I accept it. All 13 commits carry `Claude Opus 5.5`; no teacher field written. Worth a look: (1) the vitest failure in run 1 was not captured or reproduced (as the unreproduced flake at step 20). (2) The release-mode R14.5 AppData snapshot starts after `erh --version` runs and does not cover the moved copy's second start, as in debug mode. (3) Installing and uninstalling also make short-lived files in `%TEMP%` (NSIS `$PLUGINSDIR`, the uninstaller's temporary copy), which NSIS deletes itself; PRD §11 does not mention them. (4) Anyone who sets `ERH_WEBVIEW_DEVTOOLS=1` gets DevTools in the release app (local only).

Re-verification 2026-10-12, f828971: ✅. The 281b140 finding is fixed as the teacher decided (PRD v4.10.1, 8b0ad9e; template, test and release notes, f828971). `installer.nsi` vs tauri-cli 2.12.1's built-in template (re-extracted from `cli.win32-x64-msvc.node`, line endings normalised): the 9-line header plus exactly two "ERH change" edits: (1) `.onInit` currentUser default `$LOCALAPPDATA\${PRODUCTNAME}` → `D:\ExamRevisionHelper`, else `$PROFILE\ExamRevisionHelper` (unchanged); (2) in `Section Uninstall` the `DeleteRegKey SHCTX "${MANUPRODUCTKEY}"` / `/ifempty "${MANUKEY}"` block and the HKCU `Installer Language` cleanup now sit under `${If} $UpdateMode <> 1` alone, so a real uninstall always deletes the key and `/UPDATE` keeps it; the `RmDir /r "$APPDATA\${BUNDLEID}"`/`"$LOCALAPPDATA\${BUNDLEID}"` block keeps its own `$DeleteAppDataCheckboxState = 1` + `$UpdateMode <> 1` guard. Nothing else differs. PRD §11 (v4.10.1: shortcuts, uninstall entry and install-folder record in HKCU, WebView2 download; "the uninstaller removes them"), the release-notes locations table (four rows, `HKCU\Software\examrevisionhelper\Exam Revision Helper` with `MANUFACTURER` = `examrevisionhelper` in the generated script) and its text ("removes all four … leaves `<app>\data`"; the box only adds Tauri's AppData folders) agree with the template for the four registry/shortcut items. R21.1: `npm run tauri build` exit 0, "Finished 1 bundle"; installer **44,990,085 bytes** (release notes 45,006,564, −16,479 bytes, within the documented rebuild variation); shell exe 10,796,544 bytes and sidecar folder 159 files / 107,518,802 bytes, equal to the release notes; the generated `target/release/nsis/x64/installer.nsi` carries both ERH changes. R21.5: the release notes record the sizes and the Defender result; re-scan of the rebuilt installer, `target\release\sidecar` and the shell exe (`MpCmdRun -Scan -ScanType 3 -File … -DisableRemediation`, no signature update): all "found no threats". R21.2: not re-run (moves the mouse); `git diff --stat 281b140..HEAD` touches only `app/scripts/tauri-config.test.ts`, `app/src-tauri/nsis/installer.nsi` (uninstaller only), `docs/{PRD,plan,release-notes}.md`: no shell code, `app/src`, `app/e2e-shell/` or sidecar change, so the orchestrator's run at 281b140 ("E2E_SHELL: all passed") still holds. R21.3: `firstRun.test.tsx` unchanged and passing. R21.4: `defaults.py`, `ExtractThresholds`, `GradeThresholds.key_margin`, `similarity.LOOKS_LIKE/POSSIBLY` and `GRADING_THINK` re-read: equal to the m1 §4 / m2 §4–§5 decisions and table. S1 `TEST`: 1307 passed, 14 deselected (261 s). S2 ruff clean, 207 files formatted, mypy no issues in 88 files. S3, S6 no diff. S4 only `llm/defaults.py` (and its `.pyc`). S5 exits 0. S7 `npm test -- --run` 125/125 (the new uninstall-guard test included), lint, typecheck, `check:urls` pass, `gen:types` no diff. `E2E` 19/19 passed (1.3 min). `cargo test` 16 passed. Scope: `0e49822..HEAD` as at 281b140 plus only in-scope paths. All 16 commits carry `Claude Opus 5.5`; no teacher field written. Clean tree afterwards. Worth a look (low, wording, from v4.10): PRD §11's "The uninstaller removes them" also covers the WebView2 download, but the template leaves the downloaded `$TEMP\MicrosoftEdgeWebview2Setup.exe` and the installed WebView2 runtime in place (Tauri's default; reached only on a PC without WebView2, which Windows 11 ships). A wording patch for the teacher, not a failure here.

---

## Step 22.1 — The teacher's app review

The teacher installed the step 21 build and wrote 16 comments. They are kept verbatim, with the work packages and the
open decisions, in `docs/initial-plan/phases-testing/step22.1-plan.md`; "comment N" below means its §1 item N. The sub-steps run in
the order of their **Depends on** (one at a time, not in parallel as §1.1 allows for `N.1`/`N.2`), and all of them come
before step 22, whose acceptance runs once on the final build (teacher, v2.10). A sub-step whose package changes a
teacher decision updates the PRD first. Sub-steps 22.1.2–22.1.7 get their checklist and requirements in a plan version
written before they start, after the decision each one needs (step22.1-plan §3). UI packages use the user-scope
`ui-ux-builder` and `ui-ux-verifier` agents (step22.1-plan §2); the step's requirements and S1–S7 are still verified
as in §1.3.

### Step 22.1.1 — Small fixes
**Depends on:** 21 · **Comments:** 4, 7 (rename), 8, 10, 11, 13, 16 · data-model §5.6 (v1.8) · llm-design §2 routes (v4.19)

**Checklist**
- [x] Comment 4: the student chip's menu closes on a click outside it and on `Escape`, as well as on the chip.
- [x] Comment 8: find why the teacher leaves Print by closing the app, and give the test, key and report print views a
      visible way back that does not close the app.
- [x] Comment 10: find why the Occasion field cannot be filled, and fix it.
- [x] Comment 11: from the student chip the teacher can type a new name, create that student and assign it, and can edit
      the assigned student's name (`PATCH /students/{id}`).
- [x] Comment 7: a thread can be renamed from the thread list, by right-click and by a visible menu button
      (`PATCH /threads/{id}`).
- [x] Comment 13: a thread the teacher has not renamed shows the student's name and the test's name (data-model §5.6).
- [x] Comment 16: the extraction card's heading says what was extracted (the test's name, and the student when known)
      instead of "Extracted". "Graded" stays.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.1.1.1 | The student menu closes on a pointer-down outside it and on `Escape`, and stays open on clicks inside it (search box, list). | `APP_TEST` |
| R22.1.1.2 | The cause of comment 8 is written in the implementing commit's message. The test, key and report print views each show a visible control, hidden when printing, that returns to the view the teacher came from without closing the window. | Read the commit + `APP_TEST` |
| R22.1.1.3 | The cause of comment 10 is written in the implementing commit's message. Typing an occasion and leaving the field → `PATCH /tests/{id}` → `GET /tests/{id}` returns it. A regression test that fails before the fix passes after it. | `APP_TEST` (+ `TEST` if the cause is in the sidecar) |
| R22.1.1.4 | Student: typing a name that matches no student offers "Create “<typed>”"; choosing it creates the student and assigns it, and the chip shows the name. `PATCH /students/{id}` with a new `full_name` → `GET /students?q=` with the accent-free lowercase form finds it, the old form does not; a blank name → 422; an unknown id → 404. The chip offers the edit for the assigned student. | `TEST` + `APP_TEST` |
| R22.1.1.5 | Thread rename: `PATCH /threads/{id}` `{title}` → `GET /threads` and `GET /threads/{id}` return the title; a blank title → 422; an unknown id → 404. In the thread list, right-click and the menu button both open the rename; `Enter` saves, `Escape` cancels. | `TEST` + `APP_TEST` |
| R22.1.1.6 | A thread titled "New thread" whose current attempt has a student and a test shows both names in the thread list; with no student it shows the test's name; a renamed thread shows its title. | `APP_TEST` (+ `TEST` if made in the sidecar) |
| R22.1.1.7 | The extraction card's heading contains the test's `display_name` (and the student's name when assigned); no card heading is the bare word "Extracted". | `APP_TEST` |
| R22.1.1.8 | R12.1 still holds: the OpenAPI export lists exactly llm-design §2's routes, including the two new ones. `E2E` passes. | `TEST` + `E2E` |

**Verifier notes:** fresh verifier, 2026-10-13, on `step/22.1.1-small-fixes` at b58eebd (implementation commits b40e700..b58eebd after db9f515); the tree was clean before and after.
- **S1** `TEST`: 1313 passed, 14 deselected. **S2** `LINT`: ruff clean, 208 files formatted, mypy clean (88 files). **S3** schema export: no diff. **S4**: matches only `src/erh/llm/defaults.py` (lines 30, 37); `grep -l` also lists its `__pycache__/defaults.cpython-312.pyc`, the same file compiled (the noise the implementer flagged; not a finding). **S5** `erh scrub --check`: exit 0; no cassette changed in db9f515..HEAD. **S6** OpenAPI export: no diff. **S7** `APP_TEST`: 19 files, 160 tests passed; eslint and tsc clean; `gen:types` (42 schemas + openapi.ts): no diff in `app/src/gen`.
- **E2E** (`npm run e2e`, headless; `e2e:shell` not run): 20/20 passed, including the new `s8-small-fixes.spec.ts`.
- **R22.1.1.1** ✅ `ExtractionCard.test.tsx` "the student picker closes like a menu": pointer-down outside closes; Escape closes, focus returns to the chip, and the artifact panel stays open (`useDismiss` marks the key handled; `useShortcuts` skips `defaultPrevented`); clicks in the search box and list keep it open; the chip still toggles it. The E2E checks the same flow.
- **R22.1.1.2** ✅ The cause is in 9f58471's message: `window.print()` opened WebView2's print window over the app with no app control, and its only exits were its own Cancel and Esc, so the teacher used the title bar ✕. Checked in the code: Print in the test, key and report panels now calls `AppShell.startPrint`. That opens a print view (`PrintBar`, `no-print`, with "Back to …" focused, a note and Print), and the print window opens from an effect after it renders. Back, or Esc through `onClosePanel`, returns to the same panel with its content still mounted. `printView.test.tsx` covers the three views, `.no-print` under `@media print`, Esc then a second Esc, and Print again; the E2E checks that the bar is hidden under print media.
- **R22.1.1.3** ✅ The cause is in 79ca92f's message and matches `TestMetadata._check_occasion` (`domain/models.py`), which accepts only an `OCCASIONS` code or `^Other:\S.*$`, so typed words returned 422. The fix is frontend-only (`toOccasion`, datalist), and the test's list equals the sidecar's `OCCASIONS`. **Regression demonstrated:** with `TestPanel.tsx` from db9f515 put back temporarily, `occasion.test.tsx` failed 5 of 6 (one of the five is the type-and-leave → PATCH → GET case); restored with `git checkout`, it passes 6/6. The E2E saves "Giữa kỳ 1" and reads back `Other:Giữa kỳ 1` from `GET /tests/{id}`.
- **R22.1.1.4** ✅ `test_step22_1_1.py`: `name_search` follows the new name, the accent-free query finds it and the old form does not, a blank or null name → 422, an unknown id → 404. The repo `update_student` is an added function that rejects unknown columns or a name without its `name_search`. `ExtractionCard.test.tsx` covers Create “<typed>” (POST /students, then PUT the attempt), no Create for an existing name (accents and case aside), and the edit → PATCH `{full_name}`. The chip shows the name after the reload, in the unit test and in the E2E.
- **R22.1.1.5** ✅ `test_rename_thread` covers 200, `GET /threads` and `/threads/{id}`, a blank or missing title → 422, and unknown → 404. `ThreadList.test.tsx` covers the menu button, right-click, Enter, Escape (which does not reach the global shortcut), and blank or unchanged names; `printView.test.tsx` covers the wiring to PATCH. The E2E renames by the button and by right-click.
- **R22.1.1.6** ✅ `test_shown_title_from_student_and_test` covers the test alone, student · test, the teacher's title winning, the title made on read and not stored, and a student rename showing at once. The list and the thread heading use `shown_title` (unit tests and E2E).
- **R22.1.1.7** ✅ The heading is `<h2>` "Extracted: <student> · <display_name>", or the test's name alone; the tests assert that no heading is the bare word. No "Extracted ✓" is left in `app/src`.
- **R22.1.1.8** ✅ The route table in `test_route_table.py` is line-for-line equal to llm-design §2 v4.19 (37 rows, compared by script; two descriptions were re-copied to match the doc), and its R12.1 test passes in S1. E2E passes.
- **Scope:** every path in db9f515..HEAD is inside §6 row 22.1.1, or is the 22.1.1 checklist ticks in this file. `features/running/` is unchanged (b58eebd put it back). The generated files match the tools' output. All six commits carry `Claude Opus 5.5`. No teacher field, fixture or student data was added.
- **Design review** (code only; no screenshots, app not run): no critical or major accessibility failure in the UI this step adds. Names and roles are in place: the chip has `aria-haspopup`/`aria-expanded`/`aria-controls`; the picker is a labelled non-modal `dialog` with `<label htmlFor>` fields; the "⋯" button has an `aria-label` and is at least 24×24 px; errors use `role="alert"`; decorative glyphs are `aria-hidden`.

**Worth a look** (minor; none blocks):
1. *Contrast, for step 22.1.2* (computed from `tokens.css`): the new Create “<typed>” option uses `text-accent` (`ExtractionCard.tsx:367`). In light mode that is 3.79:1 on the panel and 3.37:1 on hover; in dark mode it is 3.82:1 on hover. All are below the 4.5:1 that WCAG 1.4.3 asks for. `KeysPanel.tsx:141` already used the same pairing. White on accent (Save name, Print) is 4.14:1 in light mode, and input borders (`border` on `surface`) are 1.33:1 light and 1.20:1 dark (1.4.11). These are the current palette, so the new theme should meet them.
2. *Focus after Back* (2.4.3): `AppShell.tsx:222` unmounts the bar, so focus falls to `<body>` rather than going back to the panel's Print button. Esc behaves the same way.
3. *Popovers and Tab:* the thread menu and the student picker close on outside pointer-down and Esc, but not when focus leaves them with Tab. `role="menu"` has a single item and no arrow-key handling (enough for one item).
4. *Error text:* `ExtractionCard.tsx:185` and `AppShell.tsx:150` show `String(err.detail)`. A pydantic 422 list would read "[object Object]". `TestPanel.errorText` already joins the `msg` fields and could be reused. The UI blocks blank names, so this case is unlikely.
5. *Edge cases:* a thread renamed to exactly "New thread" counts as the default title, so its generated title comes back (§5.6 as written). The search has no debounce, so "Create “<typed>”" is judged against the last results that came back, and a fast click could create a duplicate student.
6. *Copy (ux-copy):* the Occasion list shows the raw codes ("FifteenMinuteTest", "Other:…"), and the chip shows `Other:Giữa kỳ 1` with its prefix. The placeholders "Search, or type a new name" and "Pick one or type your own" have no closing "…" (web-design-guidelines). These may overlap the implementer's three open wording questions; I could not see those questions, so they are listed here.
7. *Confirmed as the implementer flagged:* a run notification for a thread that is not in the loaded list still uses `thread.title` (outside scope). The card's [Test]/[Key] buttons still use the card's stored `test_id` after a merge (`ExtractionCard.tsx:63`); only the heading follows the current test. `PATCH /students/{id}` accepts `class_name`, but no UI edits it yet.

### Step 22.1.2 — Green theme
**Depends on:** 22.1.1 · **Comment:** 1 · **PRD:** §10 theme line (v4.11) · decision 2: a light green; the teacher adjusts
the exact shades later, so the palette lives only in the colour tokens.

**Checklist**
- [x] Comment 1: replace the warm-neutral palette (Claude Desktop's greys and orange) with a green theme in
      `app/src/styles/tokens.css`: a light green accent and green-tinted greys, in light and dark mode.
- [x] Every colour in `app/src` comes from the tokens (no colour literal outside `tokens.css`), so a later shade change
      is one file.
- [x] Contrast meets WCAG 2.1 AA in both modes, including the step 22.1.1 carried-forward findings
      (step22.1-plan §5): accent text, text on the accent fill, input borders. A token may be added where one colour
      cannot serve both as a fill and as text (for example a darker green for accent text).
- [x] The print view and printed pages stay black on white.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.1.2.1 | In `tokens.css`, the light block and both dark blocks give the accent a green hue (HSL hue 90°–160°) and the background, surface, sidebar, panel, border and hover tokens a green tint (hue 80°–170°, or exactly grey). No token keeps a value of the step 21 palette. All blocks define the same token names. | `APP_TEST` (a unit test reads `tokens.css`) |
| R22.1.2.2 | Computed from the token values in light and dark: every token used for text, and the text tokens on the accent fill, are ≥ 4.5:1 on each surface they are used on (bg, surface, sidebar, panel, hover); input borders and the focus ring are ≥ 3:1 against their surface. | `APP_TEST` (a unit test computes the ratios) |
| R22.1.2.3 | No colour literal (`#rgb`, `#rrggbb`, `rgb(`, `hsl(`) in `app/src` outside `styles/tokens.css`, generated code and tests, except black and white in `print.css`. The OS preference and `data-theme="light"`/`"dark"` still pick the mode. | `APP_TEST` |
| R22.1.2.4 | S1–S7 hold; `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** fresh verifier, 2026-10-13, on `step/22.1.2-green-theme` at 0e90b89 (implementation 91461e6, checklist ticks 0e90b89, after the docs commit 8e80fa4); the tree was clean before and after.
- **S1** `TEST`: 1313 passed, 14 deselected. **S2** `LINT`: ruff clean, 208 files formatted, mypy clean (88 files). **S3** schema export: no diff. **S4**: matches only `src/erh/llm/defaults.py` (lines 30, 37). **S5** `erh scrub --check`: exit 0. **S6** OpenAPI export: no diff. **S7** `APP_TEST`: 20 files, 171 tests passed; eslint and tsc clean; `gen:types` (42 schemas + openapi.ts): no diff in `app/src/gen`.
- **E2E** (`npm run e2e`, headless; `e2e:shell` not run): 20/20 passed.
- **R22.1.2.1** ✅ Recomputed by an independent script from `tokens.css`: accent, accent-strong and focus hues are 131°–141° in both modes; bg, surface, sidebar, panel, hover, border and input-border hues are 120°–144°. The three blocks define the same 16 names, and the two dark blocks are equal. No value of the step 21 palette remains (`tokens.test.ts` lists all 24 old values; checked against `git show 6df63df:app/src/styles/tokens.css`, which equals 8e80fa4's).
- **R22.1.2.2** ✅ Recomputed (WCAG 2.1 luminance), the minimum over bg/surface/sidebar/panel/hover, light / dark: text 13.24 / 11.33, text-muted 5.49 / 5.78, accent-strong 5.44 / 8.99, success 4.96 / 7.17, warning 5.05 / 6.90, danger 7.09 / 6.86; accent-text on accent 9.33 (≥ 7.30 at the hovered button's 90% opacity); input border 3.39 / 3.33; focus 5.44 / 8.99. The tinted rows also pass: muted on warning/10 ≥ 4.73, danger on danger/20 ≥ 4.57, text on bg/80 ≥ 13.91. The carried-forward findings (step22.1-plan §5) are closed: `text-accent` is gone from `app/src` (now `text-accent-strong` in 4 places), and every input, select and textarea uses `border-input`. **The tests are not self-certifying:** with the step 21 tokens put back (and the two new names filled from the old accent and border so that nothing crashes), `tokens.test.ts` failed 8 of 12 on real values (hue 15.6°, muted on hover 4.35, white on accent 4.14, danger/20 3.96, input border 1.26, the screen-only media check). Restored with `git checkout`.
- **R22.1.2.3** ✅ An independent grep for `#hex`, `rgb(`/`hsl(`/`oklch(`… and Tailwind palette classes finds only `#fff`/`#000` in `print.css` (also nothing in `index.html` or `tauri.conf.json`). Mode: the built CSS (vite build, checked) keeps `@media screen and (prefers-color-scheme:dark){:root:not([data-theme=light])…}` and `@media screen{:root[data-theme=dark]…}`. Both selectors have specificity (0,2,0) over the light `:root` (0,1,0), so the OS preference, `data-theme="light"` and `data-theme="dark"` all still pick the mode on screen, and print gets the light block. The `dark:` variant in `index.css` is unchanged, and no component uses `dark:`.
- **R22.1.2.4** ✅ S1–S7 and E2E above.
- **Scope:** every path in 8e80fa4..HEAD is inside §6 row 22.1.2 (`app/src/styles/`, colour class names in `app/src/features/`, `app/src/index.css` theme colours, tests) or is the 22.1.2 checklist ticks in this file. The `.tsx` diffs only rename colour classes (`text-accent`→`text-accent-strong`, `border-accent`→`border-accent-strong`, `border-border`→`border-input` on inputs), so layout and behaviour do not change. Both commits carry `Claude Opus 5.5`. No teacher field, fixture or student data was added.
- **Design review** (code and token values only; no screenshots, app not run): no critical or major finding. The token roles are clear and documented in `tokens.css`, the light and dark palettes were designed together, `color-scheme` is set per mode, and disabled states (opacity 50%) are exempt from 1.4.3.

**Worth a look** (minor; none blocks):
1. *Print view on screen:* the checklist says "the print view and printed pages stay black on white". Paper is light, but the on-screen print view's sheet is `bg-surface` (`ArtifactPanel.tsx:57`), so in dark mode it is a dark sheet before printing. This was already the case at step 22.1.1, so "stay" holds. Also, `print.css` makes only the containers black on white: text inside with `text-muted`/`text-danger` prints in the light tokens' green-grey and red (as before, now green-tinted).
2. *Light-mode primary button:* the light green fill (`#8ed99c`) is 1.37:1 against the light surfaces. That passes WCAG, since the dark label (9.33:1) identifies the button, but the primary action stands out less than the old orange did. It is a shade question for the teacher's later adjustment, not a contrast failure.
3. *Dividers:* `--erh-border` is 1.11:1 (light) and 1.10:1 (dark), as decided for decorative outlines. Secondary buttons (`border border-border`) rely on their label and hover; that is acceptable under 1.4.11, but they read as plain text until hovered.
4. *Narrow margins:* danger on danger/20 in dark mode (4.57) and muted on warning/10 (4.73 dark, 4.81 light) are close to 4.5:1. A later shade change could push them below it; the unit test will catch that.
5. *Dark tint strength:* the dark greys are only slightly green (e.g. bg `#151b17`). They differ from the step 21 values in every token, but comment 1 complained that the black was "EXACTLY the same". Whether this tint is different enough is the teacher's call when shades are adjusted.

### Step 22.1.3 — Progress bar
**Depends on:** 22.1.2 · **Comment:** 2 · **PRD:** §10 running indicator (v4.12) · **llm-design:** §2 run progress (v4.20)

**Checklist**
- [x] Sidecar: the stage lists of llm-design §2, and `stage`, `stages`, `stage_label`, `percent` on `run.step_started`,
      `run.progress` and `GET /runs/active`.
- [x] Sidecar: while a model call streams, `run.progress` with `tokens` at least every 5 s.
- [x] UI: a progress bar in the running indicator and in the running thread, with the stage in plain words, the count
      ("page 2 of 4"), the elapsed time and a live sign while the model writes. No node names on screen.
- [x] The bar is right after a restart (seeded from `GET /runs/active`) and after Resume.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.1.3.1 | A replayed extract run (S1-like cassettes, one key page, answers) and a replayed grade run publish events whose `percent` starts at or above 0, never goes down, and is 100 at `run.done`; `stage`/`stages`/`stage_label` follow llm-design §2's lists; a skipped stage (no key pages; a test that needs no key check) still lets `percent` reach 100. | `TEST` |
| R22.1.3.2 | With a fake clock, a streaming model call that lasts 12 s publishes at least 2 `run.progress` events with increasing `tokens` and the call's `step_id`; a call shorter than 5 s may publish none. Stop still cancels the call (the step-7 stop/resume tests pass). | `TEST` |
| R22.1.3.3 | `GET /runs/active` returns `stage`, `stages`, `stage_label`, `percent` for a running and a stopped run; after Resume, the first event's `percent` is not lower than the stopped value. R12.1 still holds (no new route). | `TEST` |
| R22.1.3.4 | The running indicator and the running thread show an element with `role="progressbar"`, `aria-valuenow` = `percent`, and a text "<stage_label> · <item> <done> of <total>" (or the stage label alone); the elapsed time counts up; a `tokens` event shows the live sign; no node name (`transcribe_page`, …) appears in the DOM. With `prefers-reduced-motion`, nothing animates except the value. | `APP_TEST` |
| R22.1.3.5 | After a reload with a running run, the bar shows the percent and stage from `GET /runs/active` before any new event. | `APP_TEST` |
| R22.1.3.6 | S1–S7 hold; the E2E checks the bar during a replayed extract run and its removal at `run.done`. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** fresh verifier, 2026-10-13, on `step/22.1.3-progress-bar` at d72bf23 (implementation 4a41e91 sidecar, 2282af5 UI, cd112ad E2E; checklist ticks 1de2260; orchestrator doc patch d72bf23; after the docs commit d2fc361); the tree was clean before and after.
- **S1** `TEST`: 1336 passed, 14 deselected. **S2** `LINT`: ruff clean, 212 files formatted, mypy clean (88 files). **S3** schema export: no diff. **S4**: matches only `src/erh/llm/defaults.py` (lines 30, 37). **S5** `erh scrub --check`: exit 0. **S6** OpenAPI export: no diff. **S7** `APP_TEST`: 21 files, 185 tests passed; eslint and tsc clean; `gen:types` (42 schemas + openapi.ts): no diff in `app/src/gen`.
- **E2E** (`npm run e2e`, headless; `e2e:shell` not run): 20/20 passed.
- **R22.1.3.1** ✅ `EXTRACT_STAGES` and `GRADE_STAGES` match llm-design §2 v4.20.1 word for word (labels and node groups), and their order follows `C1_EDGES`/`C2_EDGES`. `RunProgress`: equal shares, `done/total` inside the stage, a later stage counts the earlier ones as done, `percent = max(previous, …)`, `finish()` gives 100 on `run.done`. The replay test covers key pages, no key pages, an attempt grade and a blank-test grade (Explaining and Weak points skipped). **Not self-certifying:** with the `max(...)` removed from `RunProgress._update`, 2 tests failed (the unit test and the blank-test grade replay). Restored with `git checkout`.
- **R22.1.3.2** ✅ The client calls the step's listener only when `now - last_beat >= HEARTBEAT_SECONDS` (4 s), only while chunks arrive; the listener is set and reset around each step. **Not self-certifying:** with the throttle removed (a beat per chunk), the 12 s and short-call tests failed. Stop: the runtime stop/resume/cancel/interrupt tests (22) pass, plus the new stop-mid-call test (the call is `cancelled`, the step `incomplete`).
- **R22.1.3.3** ✅ `ActiveRun` adds four optional fields (no new route; OpenAPI regenerated). A stopped run keeps its `RunProgress` in memory, so Resume continues from the shown value; a new process seeds it from the latest step (the start of that stage), and the next event is not lower than the seeded value (tested).
- **R22.1.3.4** ✅ `RunProgressBar` is `role="progressbar"` with `aria-valuemin/max/now` and `aria-valuetext`, labelled "Run progress"; text `<stage_label> · <unit> <done> of <total>`; elapsed time ticks every second; a `tokens` event shows "Writing" for 15 s. `RunEntry` no longer keeps the node. The fill moves by `transform`, and its transition and the pulse are `motion-safe:` only. **Not self-certifying:** with `motion-safe:` removed from the transition and `maxPercent` replaced by "take the new value", 3 UI tests failed. Restored. Colours are tokens only. Computed: fill (`accent-strong`) on the track (`hover`) is 5.44:1 light and 8.99:1 dark (≥ 3:1, WCAG 1.4.11); stage text on `surface` 15.91 / 13.20; muted percent and time 6.60 / 6.72.
- **R22.1.3.5** ✅ `progressFromActive` seeds stage and percent from `GET /runs/active`; the app test renders both bars before any event.
- **R22.1.3.6** ✅ S1–S7 and E2E above; `s1-run.spec.ts` checks both progressbars, a §2 stage text, a numeric `aria-valuenow`, no node names in the page, and that every progressbar and the thread card are gone after `run.done`.
- **Diff review:** in `graphs/` only the stage tables, `register(..., stages=)` and the `report_progress` calls changed (they now name their `unit`); no node computation or prompt changed. `read_key_pages` now passes the 1-based index instead of `kp.page_no` as `done`. That is in scope (a `report_progress` argument) and correct (`done` must count 1..n). Today key pages are already numbered 1..k (`ExtractState.key_pages`), so the change has no effect on behaviour and no test can tell the two apart; reverting it keeps all tests green. Events only add fields; the token `run.progress` has no `done`/`total`, and the UI handles that.
- **Scope:** every path in d2fc361..HEAD is inside §6 row 22.1.3, the checklist ticks (1de2260) or the orchestrator's doc commit (d72bf23). All five commits carry `Claude Opus 5.5`. No teacher field, fixture or student data was added.
- **Screenshots** (teacher decision 6): headless Playwright against the E2E replay sidecar (S1 stand-ins, synthetic), light and dark, kept in the verifier's scratchpad and not committed. The indicator and the thread card show the stage, the bar, the percent and the time; both modes are legible. Observed sequence: "Preparing the photos" 0 → "Reading the test" 40 → "· page 1/2/3 of 3" 46/53/60 → "· page 1 of 1" 60 (`retranscribe_tiles`) → "Reading the answers · page 1/2 of 3" 66/73 → "Saving" 80 → done.

**Worth a look** (minor; none blocks):
1. *A second pass looks like a restart:* inside "Reading the test", `retranscribe_tiles` reports its own count, so the text goes "page 3 of 3" → "page 1 of 1" while the bar stays at 60%. Seen in the replay.
2. *Elapsed time has no visible label:* "40%  0:00" says "Elapsed" only to screen readers, so a teacher could read the time as time left.
3. *Screen-reader order:* the indicator's polite live region (`RunningIndicator.tsx`) comes after the time, so a reading-order pass hears the stage twice. Live announcements only happen on a stage change, as intended.
4. *Long counts in the sidebar:* "Explaining mistakes · question 12 of 40" may be cut off in the sidebar; the full text is only in a `title` (a mouse tooltip).
5. *Already with the teacher* (step22.1-plan §5): a restart seeds the start of the stage; the count shows pages finished; the heartbeat only beats while tokens arrive (a slow prompt read before the first token gives no "Writing"); elapsed time includes stopped time; the wording of "Writing".

### Step 22.1.4 — Layout and photos
**Depends on:** 22.1.2 · **Comments:** 3, 12 (photos), 14, 15 · **PRD:** §10 workspace view (v4.13) · **llm-design:** §2
`GET /tests/{id}` (v4.21) · decision 3 = B (step22.1-plan §4). Built on 22.1.3's branch (the teacher merges all sub-steps
together).

**Checklist**
- [x] Sidecar: `GET /tests/{id}` returns `pages` and `key_pages` (find where the extract run keeps key photos; if it
      does not keep them, `key_pages` is empty and the report says so).
- [x] Workspace view: opening Test, Key, Answers or Report hides the conversation and shows the panel on the left and
      the photo viewer on the right; "← Back to thread" and `Esc` return to the conversation unchanged.
- [x] Photo viewer: page by page, page numbers, previous/next, zoom; Test and Key show the test's pages (and key
      pages, labelled); Answers and Report show the attempt's pages. The Key workspace can switch its right side to the
      test text (comment 15).
- [x] Comment 3: the extraction card shows the photo thumbnails; a thumbnail opens the Test workspace at that page;
      each card button says what it opens.
- [x] Carried forward from 22.1.1 (step22.1-plan §5): focus returns to the Print button after Back from the print view;
      the thread menu and the student picker close when focus leaves them by Tab; after a merge the card's buttons open
      the merged-into test.
- [x] Headless screenshots (decision 6) of the conversation and each workspace, light and dark, in a gitignored folder.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.1.4.1 | `GET /tests/{id}` returns `pages` (every `test_pages` row, by `page_no`) and `key_pages`; a test with no stored photos returns empty lists; R12.1 holds; OpenAPI and TS types regenerated. | `TEST` |
| R22.1.4.2 | With no panel open, the conversation shows. Opening Test, Key, Answers or Report from a card or the Tests tab shows the panel and a photo viewer side by side and no conversation; "← Back to thread" and `Esc` bring back the same thread with its scroll position and any unsent text, and focus returns to the control that opened the workspace. Settings and Review open as before. | `APP_TEST` |
| R22.1.4.3 | The viewer shows "Page n of N", previous/next buttons and `←`/`→` keys, and zoom (fit, larger, smaller) with the image at the page's stored rotation; Test and Key list the test's pages then the key pages labelled "Key"; Answers and Report list the attempt's pages; with no photos it says so in words. The Key workspace has a control that switches the right side between the photos and the test text. | `APP_TEST` |
| R22.1.4.4 | The extraction card shows a thumbnail per page; clicking page n opens the Test workspace at page n. Each card button's visible label or accessible description names what it opens. After a merge, the card's Test and Key open the merged-into test. | `APP_TEST` |
| R22.1.4.5 | Back from the print view puts focus on the panel's Print button; the thread menu and the student picker close when focus moves outside them. | `APP_TEST` |
| R22.1.4.6 | At 1280×720 both sides of the workspace are visible without horizontal scrolling; below 1024 px wide the photos fold into a toggle. Colours use tokens only (tokens tests pass). | `APP_TEST` (+ screenshots for the verifier) |
| R22.1.4.7 | S1–S7 hold; the E2E opens the Test workspace from the card, sees the photo viewer and a page image load, goes back, and finds the conversation. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** fresh verifier, 2026-10-13, on `step/22.1.4-workspace` at fe2889d (implementation 5d1349a sidecar, 0387cb0 UI, fe2889d E2E and checklist ticks, after the docs commit b0ccd2b); the tree was clean before and after.
- **S1** `TEST`: 1337 passed, 14 deselected. **S2** `LINT`: ruff clean, 212 files formatted, mypy clean (88 files). **S3** schema export: no diff. **S4**: matches only `src/erh/llm/defaults.py` (lines 30, 37). **S5** `erh scrub --check`: exit 0; no cassette changed. **S6** OpenAPI export: no diff. **S7** `APP_TEST`: 210 tests passed; eslint and tsc clean; `gen:types` (42 schemas + openapi.ts): no diff in `app/src/gen`.
- **E2E** (`npm run e2e`, headless; `e2e:shell` not run): 22/22 passed, including the new `s9-workspace.spec.ts` (light and dark).
- **R22.1.4.1** ✅ `pages` comes from `list_test_pages` (`ORDER BY page_no`); `test_get_test_pages_and_key_pages` inserts pages out of order and checks the order, and checks two empty lists for a test without photos. R12.1 holds (route table copied from llm-design v4.21). **Key photos, confirmed in the code:** `prepare_pages` prepares the 🔑 pages and `read_key_pages` reads them, but `save` writes only the test pages to `test_pages` and `attempt_pages`, and no table refers to a key file. `referenced_file_ids` counts run inputs only while a run is unfinished, so `sweep` deletes the key photos 24 h after the run. `key_pages` is therefore always `[]`. That meets R22.1.4.1 as worded, but the Key workspace shows the test's photos and never a key photo (see "Worth a look" 1). **Not self-certifying:** with the page order reversed in the route, the test failed. Restored.
- **R22.1.4.2** ✅ `AppShell` renders `Workspace` in place of the side panel, and `ThreadView`/`Conversation` stay mounted with `hidden` (the test checks that it is the same DOM node). The scroll position is saved on scroll and restored in a layout effect. Back and Esc (`onClosePanel` → `closeWorkspace`) return focus to the opener (a card button, a thumbnail or a Tests row); the conversation itself is the fallback. Review and Settings still open in `ArtifactPanel`. Ctrl+Enter and pasted photos are ignored while a workspace is open. **Not self-certifying:** with the scroll restore removed, 1 test failed; with the opener focus removed, 2 tests failed. Restored.
- **R22.1.4.3** ✅ `PhotoViewer`: "Page n of N" (`aria-live`), previous/next buttons, ← / →, a page strip, and zoom (Fit, 150–400 %, scrolling inside the stage). The arrow keys are skipped in text fields, selects, sliders, listboxes, menus and tablists, and while the Key shows the test text. **Rotation, confirmed:** `prepare_pages.execute` runs `files.rotate` before storing the page, so the stored file is already turned, and the viewer applies no CSS rotation. Test and Key list the test's pages, then the key pages labelled "Key"; Answers and Report list `attempt_pages`. When there are no photos, a photo has been swept, or a page is text only, the viewer says so in words. The Key workspace has a Photos / Test text switch (`aria-pressed`). **Not self-certifying:** with the typing guard removed, 1 test failed; with the key flag dropped, 2 tests failed. Restored.
- **R22.1.4.4** ✅ There is one thumbnail per page (alt-free image inside a button named "Page n: open it beside the test"). When the test's page n is the same file, page n opens the Test workspace at page n. The card's Test, Answers and Key sit in a group labelled "Open beside the photos:", each with an accessible description; the grade card's Report and Key have one too. After a merge, the card follows `merged_into` (at most 5 hops) or the current attempt's `test_id`. **Judgement on the deviation:** when the attempt's photo differs from the test's page n (the test came from another paper, or after a merge), the thumbnail opens Answers at page n instead, so the teacher sees the photo they clicked. Opening Test there would show a different paper. R22.1.4.4 assumes that the thumbnails are the test's pages, which is true for a new test, so I count this as meeting the requirement and leave it as a question for the teacher. The E2E thread (after s6's merge) shows this case: "Click a page to check it beside the answers". **Not self-certifying:** with page n opening page 1, 1 test failed; with the merge chain not followed, 1 test failed. Restored.
- **R22.1.4.5** ✅ `endPrint` moves focus to the Print button the print view was opened from (or the panel's Print button). `useDismiss` closes a popover on `focusin` outside its root; the chip is inside the root, so Shift+Tab back to it keeps the picker open. **Not self-certifying:** without the focus move, 4 print tests failed; without the `focusin` listener, 2 tests failed (the thread menu and the student picker). Restored.
- **R22.1.4.6** ✅ The s9 E2E measured both sides at 1280×720: each is more than 400 px wide, side by side, with no horizontal scroll (also at 200 % zoom). At 900 px the toggle shows and only one side is visible. No colour literals in the new code (`#fff` only in `print.css`). Contrast computed from `tokens.css`, light / dark: Key badge 6.07 / 10.95, current page 6.54 / 10.47, other pages and the inactive switch 6.12 / 7.03, notes on the stage 5.93 / 7.74, card labels 6.60 / 6.72, focus on panel/sidebar ≥ 5.88. The thumbnail number badge is now opaque (`text` on `surface`, 15.91 / 13.20), which closes the step 22.1.2 carried-forward item.
- **R22.1.4.7** ✅ S1–S7 and E2E above. `s2` opens Test from the card, waits for `naturalWidth > 0`, goes back, and finds the card's Test button focused.
- **Scope:** every path in b0ccd2b..HEAD is inside §6 row 22.1.4, or is the checklist ticks in this file (fe2889d). The docs commit is the orchestrator's (PRD v4.13, llm-design v4.21, plan "Based on" updated). All four commits carry `Claude Opus 5.5`. No teacher field, fixture or student data was added; the screenshots are under gitignored `app/test-results/`.
- **Screenshots** (teacher decision 6; headless Playwright against the E2E replay sidecar, synthetic data, light and dark, not committed): the conversation with thumbnails, the Test, Key, Key test text and Answers workspaces, 200 % zoom, and both 900 px sides. Both modes are legible. The page images are blank synthetic stand-ins, so the photo quality cannot be judged. No Report shot was taken (no graded thread was found at that point); the Report uses the same viewer as Answers (unit test).

**Worth a look** (minor; none blocks):
1. *No key photos* (teacher): the Key workspace cannot show the key photo that comment 15 asks for, because the extract run does not keep key photos. Keeping them needs a change in `graphs/extract.py` (a `key_pages` table or reference), which is outside this step's scope.
2. *A thumbnail opens Answers* when the test came from another paper or after a merge (see R22.1.4.4).
3. *Esc while typing in a panel field* closes the whole workspace, as it closed the side panel before. Unsaved typing in that field is lost.
4. *Arrow keys while the photos are folded* (< 1024 px, panel side shown) still turn the hidden page.
5. *"Page 3 of 3 · Key"*: key photos count in N, while the page strip says "Key 1".
6. *Heading order:* the workspace's `h2` has no visible `h1` (the thread's `h1` is hidden). The photo strip is a `<nav>` landmark ("Page list").
7. *Error text:* `photos.ts:88` uses `String(err.detail)`, the same "[object Object]" pattern already carried forward to 22.1.5.

### Step 22.1.5 — Document-style editing, Review under each test
**Depends on:** 22.1.4 · **Comments:** 5, 6, 7 (review), 12 (locking) · **PRD:** D27 (v4.14), S7, §10 · **data-model:**
§2.3a, §5.3 (v1.9) · **llm-design:** §2 (v4.22) · decisions 4a (no Review tab) and 4b (free text, like a Word page)

**Checklist**
- [x] Sidecar: `domain/test_text.py` (`render`, `read`) per data-model §2.3a, and the text grammar written into §2.3a
      (patch bump of data-model and plan.md's "Based on" line in the same commit).
- [x] Sidecar: `GET /tests/{id}` `content_text` + `review`; `PATCH /tests/{id}` `{content_text, drop_confirmed?}`; a save
      settles items (§5.3 v1.9); `open_review_count` on `GET /threads` and `GET /tests`.
- [x] UI: the Test workspace's left side is one editable page (the document look, the test's serif font), with the
      unsure spots highlighted, Save / Cancel, `Ctrl+S`, line-numbered errors shown at their lines, and a guard against
      leaving with unsaved text. The photos stay on the right.
- [x] UI: unsure spots shown in place (data-model §5.3 v1.9): Answers panel, Key panel, extraction card, chips; Accept,
      Fix and Skip through the existing `POST /review/{id}/resolve`, with plain labels.
- [x] UI: the Review tab, its count and the Review panel are removed; the sidebar marks threads and tests with open
      unsure spots; nothing is locked behind them (comment 12).
- [x] Carried forward from 22.1.1 (step22.1-plan §5): error text never shows "[object Object]" (one shared error-text
      helper); the student search cannot create a duplicate on a fast Create; a thread renamed to exactly "New thread"
      keeps that title.
- [x] Headless screenshots (decision 6) of the test page with unsure spots and an error, light and dark.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.1.5.1 | `read(render(c), c) == c` for every `TestContent` in the synthetic fixtures, the replay outputs and the test-suite builders (at least 10 different tests, incl. passages, cloze, pictures, `???`, writing sections, assumed points). | `TEST` |
| R22.1.5.2 | Editing a stem, an option or a passage keeps every question id; inserting a question in the middle keeps the ids of all others and gives the new one a new id; text that cannot be read returns errors with line numbers and saves nothing. | `TEST` |
| R22.1.5.3 | `PATCH /tests/{id}` `{content_text}`: a valid edit is saved (`GET` returns it); a question with a key row or answers that the text drops → 422 naming it, unless it is in `drop_confirmed`, then its key, answers, tags and explanations are deleted and graded attempts get one grade run each (§5.3 follow-up rule). | `TEST` |
| R22.1.5.4 | After a text save: an `unreadable_text` item with all `???` replaced → `fixed`; with some left → still `open` with updated spans; `validator_failed` → `fixed` when the content validates; `points_assumed` → `fixed` with its follow-up when its points changed; items of dropped questions → `obsolete`. The Appendix E table test (R10.1) still passes. | `TEST` |
| R22.1.5.5 | `GET /threads` and `GET /tests` return `open_review_count`; R12.1 holds (route table equals llm-design §2 v4.22); OpenAPI and TS types regenerated. | `TEST` |
| R22.1.5.6 | The Test workspace shows the test as one editable page with `???` and other unsure spots highlighted; typing and Save (button or `Ctrl+S`) → PATCH with `content_text`; a 422 shows each error at its line; Back or `Esc` with unsaved text asks first; a drop confirmation lists the questions by number. "Leave as is" on a `???` spot accepts its item. | `APP_TEST` |
| R22.1.5.7 | Each kind in data-model §5.3 "Where each kind is shown" appears in that place with its actions, and each action calls `POST /review/{id}/resolve` with the right `action` and `value`. No element named "Review" opens a queue; `features/review/` is gone or unused; the sidebar marks a thread with `open_review_count > 0`. The test page stays editable with open items. | `APP_TEST` |
| R22.1.5.8 | Error text for a 422 with a list of errors is readable (no "[object Object]"); a fast Create after typing cannot create a second student with the same name; a thread renamed "New thread" keeps it. | `APP_TEST` (+ `TEST` if in the sidecar) |
| R22.1.5.9 | S1–S7 hold; the E2E replaces a `???` on the test page, saves, and sees the spot and its count gone; it fixes an unsure answer in the Answers panel. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** fresh verifier for 22.1.5–22.1.7 together (teacher, plan v2.14.1), 2026-10-14, on `step/22.1.7-installer` at 82b1475 (22.1.5 implementation d9dc0e8..b1435a6); the tree was clean before and after.
- **S1** `TEST`: 1407 passed, 14 deselected (5 min 18 s, run alone; `test_step20` backup test passed). **S2** ruff clean, 218 files formatted, `mypy src` no issues in 90 files. **S3** schema export: no diff. **S4** only `src/erh/llm/defaults.py`. **S5** `erh scrub --check`: exit 0. **S6** OpenAPI export: no diff. **S7** vitest 23 files, 189 tests passed (210 at 22.1.4; the `ReviewPanel` tests went with `features/review/`); eslint and tsc clean; `gen:types` (42 schemas + openapi.ts): no diff. **E2E** `npm run e2e` (headless, after pytest, not alongside it): 23/23 passed. `cargo test --lib`: 17 passed.
- **R22.1.5.1** ✅ `test_test_text.py` round-trips 10+ contents (replay outputs, builders, edge cases) and asserts passages, pictures, `???`, ungraded sections and assumed points are among them. **R22.1.5.2** ✅ stem/option/passage edits keep ids, an inserted question gets a new id, unreadable lines give line-numbered errors (tests read). **R22.1.5.3** ✅ `PATCH {content_text}` → `domain.review.save_test_text` in one transaction; drops with a key or answers → 422 `{message, drops}` unless confirmed, then key, answers, explanations and tags are deleted and each graded attempt gets one grade run. **R22.1.5.4** ✅ `_settle` (`domain/review.py`): `unreadable_text` fixed or spans updated, test-level `validator_failed` fixed when content validates, `points_assumed` fixed (with `points_fix` runs when points changed), dropped questions' items obsolete. **Not self-certifying:** with the `unreadable_text` fix branch removed, `test_unreadable_all_replaced_is_fixed` failed. Restored. **R22.1.5.5** ✅ `open_review_count` on `GET /tests` (`review.open_counts_by_test`) and threads; route-table test passes.
- **R22.1.5.6** ✅ `DocEditor`: a native `<textarea>` over an `aria-hidden` mirror that marks `???` (tint + underline) and noted/error lines, with a gutter `?`/`!` beside the line number (not colour alone). Save and `Ctrl+S` send `{content_text, drop_confirmed}`; a 422 lists "Line n: …" buttons that move the caret, and focus goes to the error box; a drop asks in a confirm dialog listing question numbers. `useLeaveGuard` + `AppShell.guarded` ask before Back, Esc, another thread or a new thread; Esc in a text field only leaves the field. **Not self-certifying:** with the guard made a no-op, the "Back or Esc with unsaved text asks first" test failed. Restored. **R22.1.5.7** ✅ every §5.3 kind is handled in its place (grep: `unreadable_text`, `validator_failed`, `points_assumed`, `unknown_occasion` → `TestPanel`; `uncertain_answer`, `box_inline_conflict` → `AnswersPanel` (+ card); `uncertain_key`, `key_unmapped` → `KeysPanel`; `possible_duplicate`, `picked_test_mismatch`, `merge_unaligned`, `unknown_student` → `ExtractionCard`); `features/review/` is deleted; s7 checks no "Review" button. **R22.1.5.8** ✅ `lib/errors.ts` `errorText` turns string, list and `{message, errors|failures}` details into words; double-Create and "New thread" title tests pass. **R22.1.5.9** ✅ s7 replaces page 1's `???`, saves with Ctrl+S, the note goes; s4 fixes an unsure answer.
- **Screenshots** (headless, from the E2E run, gitignored `app/test-results/`): the test page with spots and with a line error, light and dark; the Answers panel with unsure rows. Contrast from `tokens.css` (light / dark): text on the `???` tint 10.99 / 7.70, muted on note cards 5.72 / 5.52, text on the error band 13.36 / 10.88, danger text on surface 8.53 / 7.98, gutter `?` (warning) 6.07 / 8.04, `!` (danger) 8.53 / 7.98. All ≥ 4.5.
- **Scope:** implementation paths are inside §6 row 22.1.5. d9dc0e8 and b1435a6 are the orchestrator's docs commits (PRD, llm-design v4.22.1, step22.1 plan, plan v2.14.1); bdd4e2f is the §2.3a grammar (data-model v1.9.1). All commits carry `Claude Opus 5.5`; no teacher field, fixture or cassette change.

**Worth a look** (minor; none blocks):
1. *Esc in the test text drops focus to the page body* (`hooks/useShortcuts.ts:62`, `blur()`): the next Tab starts from the top of the document, and "Keep editing" in the leave dialog returns focus to the body, not the text (WCAG 2.4.3, minor).
2. *Closing the app window* with unsaved test text does not ask (no `beforeunload` or window-close guard); R22.1.5.6 names Back and Esc only.
3. *The page itself sits low*: at 1280×720 with two notes and an error, the editable text starts below the fold (`s7-test-page-error-light.png`), under the notes and the help paragraph.
4. *Line errors stay* after further typing until the next save, so their line numbers can point at the wrong line once lines are added above.

### Step 22.1.6 — Save as DOCX
**Depends on:** 22.1.5 · **Comment:** 9 · **PRD:** D4 (v5.0), §11 one app folder · **llm-design:** §2 export routes (v4.23)
· decision 5 (DOCX now) and the save place (app folder only), step22.1-plan §4

**Checklist**
- [x] Sidecar: a DOCX writer (python-docx, already a dependency) for the clean test, built from the same structure as the
      test's text form (data-model §2.3a) and with the print view's content and order; the key as a separate file; the
      grade report with the report panel's content.
- [x] Sidecar: the two export routes; files go only into `<app>\exports\` (next to `data\`), named from the test's
      display name and what it is, never overwriting (a " (2)" suffix).
- [x] UI: "Save as Word (.docx)" next to Print in the Test, Key and Report workspaces; afterwards a message with the
      file name and **Open folder**, which opens `<app>\exports\` in Explorer.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.1.6.1 | The test DOCX, read back with python-docx, has the print view's text in the same order: title and metadata line, each section heading with its points and instructions, passages, picture placeholders, numbered questions with their options; Vietnamese text is unchanged (NFC); it contains no key answers. Checked on at least 5 different synthetic tests (incl. passages, cloze, pictures, writing sections). | `TEST` |
| R22.1.6.2 | The key DOCX is a separate file listing each question number with its accepted answers; the report DOCX has the score, each question's verdict, the explanations, the weak points and the questions for the teacher, as the report panel shows them; a not-graded attempt → 409. | `TEST` |
| R22.1.6.3 | With a temporary app folder, every export lands in `<app>\exports\` and nowhere else (a scan of the folder tree before and after); the name is derived from the display name with characters Windows forbids replaced; a second export of the same thing gets " (2)"; the route returns the path. R12.1 holds (the route table equals llm-design §2 v4.23). | `TEST` |
| R22.1.6.4 | The Test, Key and Report workspaces show "Save as Word (.docx)" beside Print; a click calls the route, shows "Saved <file name>" with **Open folder**, and errors are readable. Open folder opens `<app>\exports\` (through the Tauri shell, limited to that folder); in the headless E2E it is not called. | `APP_TEST` |
| R22.1.6.5 | Each saved file is a valid DOCX: python-docx reopens it, and its fonts are the app's print fonts (Be Vietnam Pro / Noto Serif, falling back in Word if not installed). | `TEST` |
| R22.1.6.6 | S1–S7 hold; the E2E saves the test and the key from a replayed S1 thread and finds both files in the E2E app folder's `exports\`. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** same verification as 22.1.5 (2026-10-14, at 82b1475; 22.1.6 implementation b804de6..524455b). S1–S7, E2E 23/23 and `cargo test --lib` 17 passed, as recorded under 22.1.5.
- **R22.1.6.1** ✅ `domain/docx_export.test_document` writes the title, the metadata line, each section heading with points and instructions, passages, picture lines, numbered questions with cues and options; the test compares the read-back paragraphs to the print order on every synthetic test with sections (≥ 5, incl. passages, pictures, writing, cloze) and checks a Vietnamese NFC line and no key text. **R22.1.6.2** ✅ `key_document` (number + accepted answers) and `report_document` (score, verdicts, report sections, explanations); `POST /attempts/{id}/report/export` → 409 "not graded yet" (test reads). **R22.1.6.3** ✅ `appdir.exports_dir` = `<app>\exports` (next to `settings.json` and `data\`; `<dir>\exports` with `--data`), refuses AppData; the shell starts the sidecar with `ERH_APP_DIR` and no `--data`, so the sidecar and `open_exports_folder` (`AppPaths::exports_dir`) name the same folder. `save_unique` opens with `"xb"` and adds " (n)". The test scans the folder tree before and after. **Not self-certifying:** with `"xb"` changed to `"wb"`, `test_r22_1_6_3_exports_land_in_exports_only` failed. Restored. Route table equals llm-design §2. **R22.1.6.4** ✅ `components/SaveAsWord.tsx` beside Print in Test, Key and Report; "Saved <file name>" + Open folder; errors through `errorText`; Open folder calls `invoke("open_exports_folder")` only inside Tauri (the command takes no argument); the unit test checks it is not called outside the shell. **R22.1.6.5** ✅ Normal style Noto Serif, headings Be Vietnam Pro (all four `rFonts` attributes); python-docx reopens each file. **R22.1.6.6** ✅ `s10-docx.spec.ts` saves the test and the key and finds both new files in the E2E data folder's `exports\`.
- **Scope:** implementation paths inside §6 row 22.1.6 (`domain/docx_export.py`, `api/routes/{tests,attempts}.py`, `appdir.py`, `app/src-tauri/src/{lib,paths}.rs`, `components/`, `features/panels/`, `e2e/`, generated files). b804de6 is the orchestrator's docs commit.

**Worth a look** (minor; none blocks): the "Saved …" status uses `role="status"` with `empty:hidden`, so the live region is `display:none` until it fills; some screen readers do not announce a region that appears that way (not confirmed; a check with NVDA would confirm it).

### Step 22.1.7 — New installer
**Depends on:** 22.1.3, 22.1.6 · R21.1, R21.2 and R21.5 again on the final commit (`docs/release-notes.md` updated); the
teacher installs it over the step 21 build, which keeps `<app>\data`. Built on 22.1.6's branch.

**Checklist**
- [x] Version 0.2.0 in `app/package.json` (+ lock), `app/src-tauri/tauri.conf.json`, `app/src-tauri/Cargo.toml`
      (+ lock) and `sidecar/pyproject.toml` (+ `uv.lock`), so the installer updates the step 21 build (0.1.0).
- [x] `TAURI_BUILD` on the final commit; sizes and the Defender scan in a new `docs/release-notes.md` section 0.2.0,
      with what changed since 0.1.0 (steps 22.1.1–22.1.6, the new `<app>\exports\` folder) and how to install it over
      0.1.0 (the data folder stays).
- [x] No `E2E_SHELL` by the builder: R22.1.7.3 runs in the final verification, after the teacher is warned.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.1.7.1 | Every version string listed above is 0.2.0 and the lock files agree; `erh --version` prints 0.2.0; S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |
| R22.1.7.2 | R21.1 on the final commit: `TAURI_BUILD` exits 0 and outputs `Exam Revision Helper_0.2.0_x64-setup.exe`. | Run it |
| R22.1.7.3 | R21.2 on the release build: `E2E_SHELL --release` starts the frozen sidecar and Settings shows 0.2.0, equal to `erh --version`. Run only after the teacher is warned (it moves the mouse). | `E2E_SHELL --release` |
| R22.1.7.4 | R21.5: `docs/release-notes.md` section 0.2.0 records the installer size, the frozen sidecar size and the Defender scan of the installer, the sidecar folder and the shell exe; it lists the changes since 0.1.0 and the update steps; the step 21 sections are unchanged. | Read the file |

**Verifier notes:** same verification as 22.1.5 (2026-10-14, at 82b1475; 22.1.7 commits 581220b..82b1475). **Pending R22.1.7.3** (`E2E_SHELL --release`, after the teacher is warned; it moves the mouse); not run.
- **R22.1.7.1** ✅ 0.2.0 in `app/package.json`, `package-lock.json` (root and `packages[""]`), `tauri.conf.json`, `Cargo.toml`, `Cargo.lock` (`exam-revision-helper`), `sidecar/pyproject.toml`, `uv.lock` (`erh`) and `openapi.json` `info.version`; `uv run erh --version` prints `0.2.0`; S1–S7 and headless E2E as under 22.1.5.
- **R22.1.7.2** ✅ `npm run tauri build` re-run on 82b1475: exit 0, `Finished 1 bundle`, `Exam Revision Helper_0.2.0_x64-setup.exe` (45,071,363 bytes; the release notes' 45,078,560 is the builder's build, the bytes differ between builds). `target\release\sidecar\erh.exe --version` prints `0.2.0`; `_internal` holds only `erh-0.2.0.dist-info`.
- **R22.1.7.3** not run. The command, once the teacher is warned: `cd app && npm run e2e:shell -- --release` (`E2E_SHELL --release`).
- **R22.1.7.3** run 2026-10-14 after the teacher was warned (the permission system blocked the verifier, so the user started the verifier's command `cd app && npm run e2e:shell -- --release` themselves; the orchestrator read the output) on the release build of 82b1475: exit 0, 20 PASS, "E2E_SHELL: all passed". `erh --version: source 0.2.0; frozen 0.2.0`; "R21.2 Settings shows the sidecar version \"0.2.0\" = erh --version \"0.2.0\""; the frozen erh.exe runs, no uv/python; R14.5 nothing new in %APPDATA%/%LOCALAPPDATA%; R20.7 moved-folder checks pass. ✅
- **R22.1.7.4** ✅ The 0.2.0 section records the installer, frozen sidecar and shell exe sizes, the Defender scan of all three, the changes since 0.1.0 (22.1.1–22.1.6, `<app>\exports\`), and the update steps; the diff of `docs/release-notes.md` over 581220b^..82b1475 adds lines only, so the 0.1.0 sections are unchanged.
- **Scope:** every path is in §6 row 22.1.7 (v1.1.88 adds `openapi.json`), plus the orchestrator's docs (581220b, 82b1475: structure, step22.1 plan) and the checklist ticks. The structure header says v1.1.88 dated 2026-10-13 while its changelog row says 2026-10-14 (cosmetic).

---

## Step 22.2 — The teacher's second review

The teacher used installer 0.2.0 and wrote 14 comments, kept verbatim with the packages and decisions in
`docs/initial-plan/phases-testing/step22.2-plan.md`; "comment N" below means its §1 item N, and "answer N" means the teacher's
answers in step22.1-plan §4. It runs like step 22.1: one sub-step at a time, each branch from the previous one, the
checklist and requirements written before each sub-step starts, UI work by `ui-ux-builder`, and **one fresh verifier for
22.2.1–22.2.6 together** at the end (teacher), which runs every sub-step's requirements and S1–S7 and marks each row.
Comment 8 (extraction quality) goes to `docs/initial-plan/plan-extraction-quality.md`, after step 22.

### Step 22.2.1 — Words on screen
**Depends on:** 22.1.7 · **Comments:** 7, 11, 13 · **Answers:** 1, 3–7, 9 · **PRD:** §10 names on screen (v5.1) ·
**llm-design:** §2 run progress (v4.24) · decision A (step22.2-plan §4)

**Checklist**
- [x] Comment 7: "Answers" → "Student answers" on every screen element (card button, workspace title, panel heading,
      print and DOCX titles, empty states, tooltips, aria labels); "Answer key" → "Key"; no text says "correct answer".
- [x] Comment 11: an unsure key shows one label, "AI unsure key"; an unsure student answer shows "AI unsure student
      answer" instead of "?"; the key source reads "AI key · double-checked" / "AI key · not double-checked".
- [x] Comment 13: the grade stage label "Finding weak points" → "Updating student ability".
- [x] Answer 1: occasions in plain English in the list, the chip and titles ("15-minute test", "Mid-term test", …);
      the Other chip shows only the typed text.
- [x] Answer 3: titles and headings put the test first ("Unit 3 test · Phạm Thu Hà"), including the made thread title.
- [x] Answers 4–5: progress text names the current item ("Reading page 3 of 4") and a second pass says "Checking page 2
      again" (llm-design v4.24).
- [x] Answer 6: the live sign beats from the start of a model call, labelled "Model is writing".
- [x] Answers 7, 9: the time reads "Elapsed 0:42" (stopped time still counts); the sidebar's progress text wraps to two
      lines instead of being cut off.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.2.1.1 | No rendered text, `aria-label`, `title` or print/DOCX heading in the app says "Answers" alone, "Answer key" or "correct answer" (a test scans the source strings and the rendered panels); the card, the workspace and its title say "Student answers" and "Key". | `APP_TEST` + `TEST` (DOCX titles) |
| R22.2.1.2 | An unsure key row shows exactly one unsure label, "AI unsure key"; an unsure student-answer row shows "AI unsure student answer" and no bare "?" marker; key sources render "AI key · double-checked" / "AI key · not double-checked". | `APP_TEST` |
| R22.2.1.3 | The grade stage list's label for `weak_points` is "Updating student ability" (sidecar table and llm-design §2 agree); no "Finding weak points" left. | `TEST` |
| R22.2.1.4 | Each occasion value has a plain-English label used by the list, the chip and the titles; `Other:<text>` shows `<text>`; the made thread title and headings read "<test> · <student>". | `APP_TEST` + `TEST` (if titles are made in the sidecar) |
| R22.2.1.5 | A replayed extract run's `run.progress` events give `current` = the page being read (1-based) and `total`; a second pass over page 2 gives `again: true` and page 2, and the text reads "Checking page 2 again"; with a fake clock, a model call whose first token comes after 12 s still publishes ≥ 2 heartbeats before it; the UI's live sign says "Model is writing"; the time reads "Elapsed m:ss"; in the sidebar the progress text wraps (no ellipsis) at the sidebar's width. R22.1.3.1–R22.1.3.4 still hold where not changed here. | `TEST` + `APP_TEST` |
| R22.2.1.6 | S1–S7 hold; headless `E2E` passes (specs updated for the new words). | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** fresh verifier for 22.2.1–22.2.6 together, 2026-10-14, on `step/22.2.6-installer` at c81a707 (tree clean before and after; `git log main..HEAD` read commit by commit). **22.2.1 passes; S7 fails from 22.2.2 on** (F1 under 22.2.2), so 22.2.2–22.2.6 stay 🔄. Checks at c81a707: S1 `TEST` 1451 passed, 14 deselected (5 min 51 s); S2 ruff clean, 227 files formatted, mypy no issues in 91 files; S3 42 schema files, no diff; S4 only `src/erh/llm/defaults.py`; S5 `scrub --check` 0; S6 `openapi.json` unchanged; S7 eslint 0, tsc 0, `gen:types` no diff, but `vitest run` exits **1**: 31 files / 237 tests pass with **19 unhandled errors** (every run; also at 22.2.2's tip 5a232aa; at 22.2.1's tip 6afc3ba 24 files / 198 tests, exit 0). Headless `E2E` 26 passed (1.4 min, run twice). `cargo test --lib` 17 passed, no diff in `src-tauri/gen/`. Write scope: every implementation commit stays inside its §6 row (22.2.4 adds only `remake_display_names` to `store/repos/tests.py`); docs commits are the orchestrator's. Broken on purpose, each caught and restored: Key showing internal numbers (testPage.test, 1 fail); key photos left out of the photo list (workspace.test, 4 fail); close dialog not naming unsaved text / closing without asking (closeGuard.test, 1 and 2 fail); thread and test delete without the transaction (test_step22_2_3, 2 fail); sweep ignoring `test_key_pages` (test_key_pages_replay, 1 fail). Screenshots: only the ones the E2E specs write (s11-tabs, s12-format-help, s4 light/dark, s7 light/dark); none scripted for the Students tab or the delete dialogs. 22.2.1: R22.2.1.1–R22.2.1.5 pass (names.test scan, ExtractionCard/panels/occasion/progress tests, test_progress_replay, test_heartbeat, s1/s8 E2E); R22.2.1.6 passes.

### Step 22.2.2 — Moving around and safety
**Depends on:** 22.2.1 · **Comments:** 1, 5, 6, 10, 14 · **Answers:** 15, 16 · **PRD:** §10 workspace tabs and safety
(v5.2) · **llm-design:** §2 `PATCH /threads/{id}` (v4.25) · **data-model:** §5.6 (v1.9.3)

**Checklist**
- [x] Comment 5: tabs Test · Key · Student answers · Report in the workspace header (only those with something to show
      for this thread); a tab switch keeps the workspace and its photo viewer, and asks first when there is unsaved
      text (reuse `useLeaveGuard`, `features/panels/leaveGuard.ts`).
- [x] Comment 6: a window-close guard (Tauri `onCloseRequested` in the shell or the page): "Close Exam Revision
      Helper?" with Close / Cancel, naming unsaved text when there is some. Headless E2E covers the page side only.
- [x] Comment 1: "Choose files…" on the new-thread screen, using the same path as dropping files (same accepted types).
- [x] Comment 10: double-click on a Key or Student answers row starts editing it; the Edit button stays.
- [x] Comment 14: Student answers rows show the answer first and put their actions and source on the right, like the
      Key rows; an unsure key's accept button reads "Verify" like any key (the "AI unsure key" label stays).
- [x] Answer 15: "Use automatic name" in the thread menu (shown when the thread has its own title).
- [x] Answer 16: the on-screen and printed test show the same title and details line as the test DOCX.
- [x] Step 22.1 verifier's minor findings (step22.1-plan §5): Esc in the test text and "Keep editing" return focus to
      the text; the editable text starts higher (help and notes no longer push it below the fold at 1280×720); line
      errors clear when their line is edited; the DOCX "Saved …" status region is always in the DOM.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.2.2.1 | The workspace shows a tab list (`role="tablist"`) with the tabs that apply; clicking one switches panel without "← Back to thread"; with unsaved test text the leave dialog appears first and Cancel keeps the text; keyboard (arrow keys or Tab + Enter) works; the photo viewer follows the tab (test pages for Test/Key, attempt pages for Student answers/Report). | `APP_TEST` + `E2E` |
| R22.2.2.2 | A close request shows the dialog; Cancel keeps the app open; Close closes it; with unsaved text the dialog says so. The shell side has a Rust or config test where possible; the page side has a unit test. | `APP_TEST` (+ `cargo test` if in Rust) |
| R22.2.2.3 | "Choose files…" opens a file input with the same `accept` as the drop zone, and chosen files go through the same upload function (a unit test shows one function for both). | `APP_TEST` |
| R22.2.2.4 | Double-click on a Key or Student answers row enters edit mode on that row (keyboard users keep the Edit button); Student answer rows render content first and actions/source after it on the right; an unsure key shows "Verify" and calls the same resolve action as before. | `APP_TEST` |
| R22.2.2.5 | "Use automatic name" calls `PATCH /threads/{id}` `{title: null}`; the sidebar and header then show the made title; the item is hidden while the title is already automatic. Sidecar test for the route. R12.1 holds. | `TEST` + `APP_TEST` |
| R22.2.2.6 | The print view and printed test show the DOCX's title and details line (same text, from one function or checked equal by a test). | `APP_TEST` + `TEST` |
| R22.2.2.7 | The four step 22.1 minor findings are fixed, each with a test (focus target after Esc and "Keep editing"; the text's top under 720 px with two notes and an error in a headless screenshot; an error clears when its line changes; the status region is present before saving). | `APP_TEST` + screenshots |
| R22.2.2.8 | S1–S7 hold; headless `E2E` passes, with a flow that switches tabs in the workspace. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** see 22.2.1 (same verification, at c81a707). **Fails S7 → R22.2.2.8 fails; stays 🔄.** **F1 (major, S7):** `tauriCloseListener` (`app/src/features/close/closeGuard.tsx:20-35`, commit 1a5a845) calls `getCurrentWindow()` whenever `isTauri()` is true; the app tests that mock `isTauri → true` and render the shell (`first-run/firstRun.test.tsx:19`, `running/running.test.tsx:20`, `running/progress.test.tsx`) have no `__TAURI_INTERNALS__.metadata`, so line 25 throws `TypeError: Cannot read properties of undefined (reading 'metadata')` in a promise with no `.catch` → 19 unhandled rejections, `vitest run` exit 1. The same missing `.catch` would leave a rejection unhandled in the real app if `onCloseRequested` failed. R22.2.2.1–R22.2.2.7 otherwise pass: a tablist with manual activation (arrows, Home/End, Enter/Space; `Workspace.tsx:84-172`), workspaceTabs/closeGuard/Conversation/panels/step22_2_2 tests, test_step22_2_2, test_title_line, s11-tabs E2E and its 1280×720 screenshot.

**Re-verification:** fresh verifier, 2026-10-15, on `step/22.2.6-installer` at cd67a3c (fixes cf9c12d F1, ff77749 F3, 0b54aa9 F4; release notes 2085a9f, cd67a3c; each inside its §6 row; tree clean before and after). S1 `TEST` 1451 passed, 14 deselected (4 min 46 s); S2 ruff clean, 227 files formatted, mypy no issues in 91 files; S3 no diff; S4 only `src/erh/llm/defaults.py`; S5 `scrub --check` 0; S6 no diff; S7 eslint 0, tsc 0, `gen:types` no diff, `vitest run` **exit 0**, 32 files / 247 tests, no unhandled errors. Headless `E2E` 26 passed (1.3 min). `cargo test --lib` 17 passed, no diff. **F1 fixed:** `makeTauriCloseListener` (`closeGuard.tsx:28-58`) chains load, registration and unlisten in one promise ending in `.catch` (a warning); closeGuard.test covers a throwing `getCurrentWindow`, a rejected `onCloseRequested`, unregister on cleanup and no listener outside Tauri. Broken on purpose (the `.catch` removed): closeGuard.test 2 fail and the full run exits 1 with 20 unhandled errors; restored. R22.2.2.1–R22.2.2.8 pass → **✅**.

### Step 22.2.3 — Delete, and a Students tab
**Depends on:** 22.2.2 · **Comments:** 2, 4 · decisions B1, B2 · **PRD:** §10 delete and Students (v5.3) ·
**data-model:** §5.7 (v1.10) · **llm-design:** §2 (v4.26)

**Checklist**
- [x] Sidecar: `DELETE /threads/{id}`, `GET /tests/{id}/delete-preview`, `DELETE /tests/{id}` doing exactly data-model
      §5.7 in one transaction (409 while a run is active or resumable); `GET /students` with `class_name` and
      `thread_count`; `GET /students/{id}` with the threads.
- [x] UI: "Delete…" in the thread menu and on each test in the Tests tab, through `useConfirm`, naming what goes (for a
      test, the threads from the preview); afterwards the list updates and an open workspace or thread of the deleted
      item closes to the empty state.
- [x] UI: a **Students** tab beside Chats and Tests: list with class and thread count, search, edit name and class
      inline (`PATCH /students/{id}`), and the student's threads (click opens the thread).
- [x] The student chip can switch the paper to another existing student or a new one (`PUT /attempts/{id}/student`),
      and edits the class too (step22.1-plan §5 "outside scope" item); the run notification for a thread not in the
      loaded list shows its real title, not "New thread".

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.2.3.1 | On a seeded database, deleting a thread removes exactly the rows data-model §5.7 lists (a before/after count per table), keeps the test, its keys and the student, and leaves other threads unchanged; deleting a test removes its threads (a thread with attempts on two tests keeps the other attempt), its pages, keys, tags, notes, Review items and tests merged into it; both are atomic (a forced failure mid-way leaves the database unchanged); a later sweep removes the unreferenced files; 409 while a run is active or resumable; 404 for unknown ids. | `TEST` |
| R22.2.3.2 | `GET /tests/{id}/delete-preview` lists exactly the threads `DELETE` would remove; `GET /students` has `class_name` and `thread_count`; `GET /students/{id}` lists the student's threads; R12.1 holds; OpenAPI and TS types regenerated. | `TEST` |
| R22.2.3.3 | Delete… in the thread menu and the Tests tab asks first (Cancel changes nothing), names the item and, for a test, the threads that go; after Delete the item is gone from the lists, `open_review_count` marks update, and an open workspace of it closes; errors (409) are readable. | `APP_TEST` |
| R22.2.3.4 | The Students tab lists students with class and thread count, searches by name (Vietnamese with or without accents, as the student search does), edits name and class with Enter/Escape and saves through `PATCH /students/{id}`, and opens a thread from the student's list; the student chip switches the paper's student and edits the class. | `APP_TEST` |
| R22.2.3.5 | S1–S7 hold; headless `E2E` deletes a thread and a test (seeded), checks they are gone, and edits a student in the Students tab. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** see 22.2.1 (same verification, at c81a707). R22.2.3.1–R22.2.3.5 pass (test_step22_2_3 with the atomicity checks, test_cors, step22_2_3.test, notifyTitle.test, z-delete-students E2E); the deletes run inside `transaction()` (`store/repos/deletes.py:127,214`). **Stays 🔄 only because S7 fails at this tip** (F1 under 22.2.2). **F3 (minor, WCAG 2.4.3):** "Delete…" in a Tests-tab row closes the menu first (`TestsTab.tsx:98-100`) and the shell awaits the delete preview before the dialog opens, so `ConfirmDialog` records `<body>` as the return target (`ConfirmDialog.tsx:54-58`); after Cancel or Delete, keyboard focus is on the page body, not the row's ⋯ button. Read in the code, not confirmed in a browser (a headless check of `document.activeElement` after Esc would confirm it; the thread menu was not checked). **F4 (minor, WCAG 4.1.2):** the thread count in a Students row is a plain `<span aria-label>` inside the row button (`StudentsTab.tsx:120-126`); a name on a generic element is ignored, so the button reads "<name> Class 7A 3". Contrast of the new rows from the tokens: muted on hover 5.49:1 light, 5.78:1 dark.

**Re-verification:** see 22.2.2 (2026-10-15, at cd67a3c); S1–S7 and headless `E2E` pass. **F3 fixed:** "Delete…" focuses the row's ⋯ button before the shell opens the dialog (`TestsTab.tsx:198`, `ThreadList.tsx`), so Cancel and Escape return there; `useFocusAfterDelete` (`hooks/useFocusAfterDelete.ts`) moves focus to the row now in the deleted one's place, or to the Tests search box when none is left (step22_2_focus.test). Broken on purpose, each restored: the ⋯ focus removed (2 fail: Keep test, Escape); the `markDeleted` call removed (2 fail: Delete test, last test). **F4 fixed:** the count badges are `aria-hidden`, with sr-only "3 threads"/"1 thread" (`StudentsTab.tsx:128`) and "n attempts" in the Tests tab; the test checks the button's accessible name. R22.2.3.1–R22.2.3.5 pass → **✅**. **F5 (minor, WCAG 2.4.3, read in the code, not confirmed):** deleting the last thread in the Chats list leaves focus on the page body: `ThreadList` then renders "No threads yet." without its root and its focus callback ignores `null` (`ThreadList.tsx:37-40`), unlike the Tests tab's fallback to the search box. A test that deletes the only thread and checks `document.activeElement` would confirm it.

### Step 22.2.4 — Test page, numbers and test details
**Depends on:** 22.2.3 · **Comments:** 9, 12 · **Answers:** 12, 13 · decision C · **PRD:** D10 (v6.0), §10 test details
and name · **data-model:** `display_name()`, §2.3a, §5.3 (v1.11)

**Checklist**
- [x] Comment 12 / answer 12: find every place the teacher sees a question number (test page, Key, Student answers,
      report, grade card, print, DOCX, Review notes) and show `printed_number` there; the internal `number` stays for
      matching. Report in the hand-back where numbers were the internal ones before (this answers part of comment 8).
- [x] Answer 12: the test text accepts gaps in printed numbers (no error).
- [x] Answer 13: a question added in the text gets answer rows in each attempt, and a graded attempt is re-graded as
      after a key edit; a typed `???` becomes or updates the page's `unreadable_text` note.
- [x] Answer 13b: "Format help" in a footnote under the test page opens and closes a table of the line forms with
      examples (from data-model §2.3a), like a drawer, keyboard-operable.
- [x] Comment 9 / decision C: `display_name()` makes "Grade 8 - Final Term 1 - <school or source> - 2025 - Test 7";
      existing tests get their name remade unless the teacher edited it (`edited_fields`); titles and DOCX file names
      follow. The test details show Test name first, then grade, occasion + term, school or series, year, "Test
      number"; the rest under a folded "More details"; "Variant" has a hint (the paper's version, e.g. đề A / đề B).

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.2.4.1 | For a synthetic test with a left-out listening part (printed 1–5 omitted, questions printed 6–40, internal numbers 1–35), the test page, Key, Student answers, report, print view and DOCX all show 6–40, and no internal number appears on screen (a test renders each). Matching, grading and duplicate comparison still use ids / internal numbers (their tests pass unchanged). | `APP_TEST` + `TEST` |
| R22.2.4.2 | A test text with printed numbers 6, 7, 9 saves without error and keeps them. | `TEST` |
| R22.2.4.3 | Saving a text with a new question adds an answer row (empty, unread) to each attempt of the test; for a graded attempt a follow-up grade run is started as after a key edit (replayed); a typed `???` on page 2 creates the page-2 `unreadable_text` item, or updates its spans if open. | `TEST` |
| R22.2.4.4 | Format help: a button in the page footer with `aria-expanded`, toggles a region listing every line form of §2.3a with an example; it does not take the editor's focus away when closed. | `APP_TEST` |
| R22.2.4.5 | `display_name()` gives "Grade 8 - Final Term 1 - Nguyễn Hữu Thọ - 2025 - Test 7" and "Grade 9 - Entrance Exam - TuoiHocTroLuyenThi - Test 23" for the matching metadata, leaves out empty parts, uses English occasion names; a migration or on-read rule remakes names of tests whose `display_name` is not in `edited_fields`; FTS search finds the new names. | `TEST` |
| R22.2.4.6 | The Test details panel shows Test name, grade, occasion + term, school or series, year and "Test number" first, in that order; the other fields are in a collapsed "More details"; "Variant" has a visible hint. | `APP_TEST` |
| R22.2.4.7 | S1–S7 hold; headless `E2E` checks printed numbers on the Key and Student answers of the S1 thread and opens Format help. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** see 22.2.1 (same verification, at c81a707). R22.2.4.1–R22.2.4.7 pass (test_printed_numbers, test_text_save_adds, test_models, test_test_name_migration, testPage.test, y-test-page E2E; Format help is a button with `aria-expanded` and a labelled region, `TestPanel.tsx:637-653`; More details is a `<details>`; Variant has its hint). **Stays 🔄 only because S7 fails at this tip** (F1 under 22.2.2).

**Re-verification:** see 22.2.2 (2026-10-15, at cd67a3c). The fixes do not touch this step's code; S1–S7 and headless `E2E` (y-test-page) pass; R22.2.4.1–R22.2.4.7 pass → **✅**.

### Step 22.2.5 — Key photos, version, uninstall
**Depends on:** 22.2.4 · **Comment:** 3 · **Answers:** 10, 18 · **PRD:** §11 (v6.1) · **data-model:** `test_key_pages`
(v1.12) · **llm-design:** `GET /tests/{id}` `key_pages` (v4.27)

**Checklist**
- [x] Answer 10: a migration adds `test_key_pages`; the extract run's save writes the key photos there (the files are
      no longer swept); `GET /tests/{id}` `key_pages` reads it; a merge moves them; deleting the test removes them
      (data-model §5.7); the Key workspace shows them in the photo viewer, labelled "Key".
- [x] Answer 18: the sidecar's version is a built-in constant (not `importlib.metadata`), kept equal to
      `pyproject.toml` by a test; the release build clears `target/release/sidecar/` before copying the frozen sidecar.
- [x] Comment 3: the uninstaller's "Delete app data" box also deletes `<app>\data`, `<app>\exports`, `<app>\webview` and
      `<app>\settings.json`, with its label saying so; unticked, they stay as before. A third "ERH change" in
      `installer.nsi`, recorded in the release notes' list.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.2.5.1 | A replayed S1 extract run with a key page stores a `test_key_pages` row; a sweep run afterwards keeps that file; `GET /tests/{id}` returns it in `key_pages`; merging moves it to the surviving test (if that test has none); deleting the test removes the row and a later sweep the file; the migration applies on an existing database. | `TEST` |
| R22.2.5.2 | The Key workspace's photo viewer lists the key photos labelled "Key" after the test pages ("Page n of N" counts both, as R22.1.4.3 says). | `APP_TEST` |
| R22.2.5.3 | `erh --version` and `GET /system/status` give the built-in constant; a test fails if it differs from `pyproject.toml`; with an `erh-0.1.0.dist-info` left beside the frozen sidecar the version is still right (a unit test fakes the metadata). | `TEST` |
| R22.2.5.4 | The release build script removes `target/release/sidecar/` before the copy (a test of the script or config). | `APP_TEST` |
| R22.2.5.5 | `installer.nsi`: the uninstall section deletes the four paths only when the box is ticked (read the diff; a script test that greps the section if one exists); the box's text names them; the update path (`/UPDATE`) deletes nothing. | Read + `APP_TEST` |
| R22.2.5.6 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** see 22.2.1 (same verification, at c81a707). R22.2.5.1–R22.2.5.6 pass (test_key_pages_replay, test_routes_b, test_db, test_version, tauri-config.test, workspace.test R22.2.5.2; a merge moves key photos only when the survivor has none, `domain/merge.py`). R22.2.5.5 read: the four paths are deleted only under `DeleteAppDataCheckboxState = 1` and `UpdateMode <> 1` (`installer.nsi:902-913`); the box names them (line 467). **Stays 🔄 only because S7 fails at this tip** (F1 under 22.2.2). **F2 (minor, data safety):** on an upgrade the "Already installed" page preselects "Uninstall before installing" (lines 305, 342-346), which adds `/UPDATE` to the old uninstaller only when the installer itself got `/UPDATE` (lines 368-373). So from 0.3.0 on, a manual update shows the uninstaller's normal screens, and a ticked box deletes `<app>\data` (database, models, backups), `exports`, `webview` and `settings.json`. Not for 0.2.0 → 0.3.0 (the 0.2.0 uninstaller runs). It needs a deliberate tick on a box that names the folders, and `release-notes.md` says to leave it unticked; a question for the teacher. Read only; the installer was not run.

**Re-verification:** see 22.2.2 (2026-10-15, at cd67a3c). The fixes do not touch this step's code; S1–S7 and headless `E2E` pass (test_key_pages_replay, test_version, tauri-config.test, workspace.test in the runs above); R22.2.5.1–R22.2.5.6 pass → **✅**. F2 is no longer a finding (teacher decision, step22.2-plan §4).

### Step 22.2.6 — Installer 0.3.0
**Depends on:** 22.2.5 · R21.1, R21.2 and R21.5 again on the final commit, as in 22.1.7.

**Checklist**
- [x] Version 0.3.0 in the places 22.1.7 changed plus `sidecar/src/erh/__init__.py` (the built-in constant, 22.2.5),
      the tests that pin it, and `sidecar/schema/openapi.json`.
- [x] Commit the regenerated `app/src-tauri/gen/schemas/capabilities.json` (stale since 22.2.2's
      `core:window:allow-destroy`).
- [x] `TAURI_BUILD`; sizes and the Defender scan in a new `docs/release-notes.md` section 0.3.0 with what changed since
      0.2.0 (steps 22.2.1–22.2.5 in plain words), the new uninstall behaviour, and how to install over 0.2.0.
- [x] No `E2E_SHELL` by the builder: R22.2.6.3 runs in the final verification; the user starts it.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.2.6.1 | Every version string is 0.3.0 and the lock files agree; `erh --version` prints 0.3.0; S1–S7 hold; headless `E2E` passes; `cargo test --lib` passes and leaves no diff in `app/src-tauri/gen/`. | `TEST` + `APP_TEST` + `E2E` |
| R22.2.6.2 | R21.1 on the final commit: `TAURI_BUILD` exits 0 and outputs `Exam Revision Helper_0.3.0_x64-setup.exe`; `target/release/sidecar/erh.exe --version` prints 0.3.0 and only one `erh-*.dist-info` is there. | Run it |
| R22.2.6.3 | R21.2 on the release build: `E2E_SHELL --release`, Settings shows 0.3.0. Run after the teacher is warned. | `E2E_SHELL --release` |
| R22.2.6.4 | R21.5: `docs/release-notes.md` section 0.3.0 records sizes, the Defender scan of installer, sidecar folder and shell exe, the changes since 0.2.0, the uninstall change, and the update steps; earlier sections unchanged. | Read the file |

**Verifier notes:** see 22.2.1 (same verification, at c81a707). R22.2.6.1: every version string and both lock files are 0.3.0, `erh --version` 0.3.0, E2E and `cargo test --lib` pass, but **S7 fails** (F1 under 22.2.2) → R22.2.6.1 fails. R22.2.6.2 (existing build, not rebuilt): `bundle/nsis/Exam Revision Helper_0.3.0_x64-setup.exe` 45,101,213 bytes; `target/release/sidecar/erh.exe --version` 0.3.0; `_internal` has one `erh-*.dist-info` (`erh-0.3.0`); 161 files, 107,591,415 bytes, as the release notes say. R22.2.6.3 not run (`E2E_SHELL`, started by the user). R22.2.6.4 passes (sizes, Defender scan of the three items, changes, uninstall change, update steps; the only edit to an earlier section is the ERH-change list, in 22.2.5's scope). F1's fix changes app code, so the 0.3.0 installer must be rebuilt after it.

**Re-verification:** see 22.2.2 (2026-10-15, at cd67a3c). R22.2.6.1 now passes (S7 fixed; versions, `erh --version`, `E2E`, `cargo test --lib` as above). R22.2.6.2 (rebuilt build, not rebuilt again here): `bundle/nsis/Exam Revision Helper_0.3.0_x64-setup.exe` 45,080,292 bytes, written 2026-10-15 00:03, after the last fix commit 0b54aa9 (00:00); shell `exam-revision-helper.exe` 10,811,392 bytes; `target/release/sidecar/erh.exe --version` 0.3.0, one dist-info (`erh-0.3.0`), 161 files, 107,591,415 bytes; all equal the release notes. The embedded front end is compressed, so its content was not compared; the time order is the evidence. R22.2.6.4: sizes and the 2026-10-15 Defender scan updated; **F6 (minor, R21.5 accuracy):** the 0.3.0 "Build" bullet still says "Result on 2026-10-14 … Built from commit `8ebb0c8` … the later commits of this step change only `docs/`", but the installer was rebuilt on 2026-10-15 from 0b54aa9 after app-code fixes (F1, F3, F4). R22.2.6.3 not run (`E2E_SHELL`, started by the user) → stays 🔄.

**R22.2.6.3** run 2026-10-15 by the user (`cd app && npm ci && npm run e2e:shell -- --release`, after the warning) on the release build rebuilt from 0b54aa9: exit 0, 20 PASS, "E2E_SHELL: all passed"; `erh --version: source 0.3.0; frozen 0.3.0`; "R21.2 Settings shows the sidecar version \"0.3.0\" = erh --version \"0.3.0\"". The orchestrator read the output. ✅

---

### Step 22.2.7 — The teacher's answers, and 0.3.0 rebuilt
**Depends on:** 22.2.6 · step22.2-plan §4 (answers of 2026-10-15) · **PRD:** v6.2 · **data-model:** v1.13 ·
**llm-design:** v4.28. The parked questions were answered after 0.3.0 was built; the code-changing answers are built
here and 0.3.0 is rebuilt before the teacher installs it (the version stays 0.3.0: it was not installed).

**Checklist**
- [x] Answer 2: an uncertain grade reads "AI unsure grade" in Student answers, the report and the report DOCX (no bare
      "?" verdict on screen).
- [x] Answers 4–5: `display_name()` says "Unit Test" / "15-minute Test" and leaves out an unknown occasion; the TS mirror
      and `title_line_cases.json` follow; existing automatic names are remade once (a migration, skipping teacher-set
      names, `updated_at` unchanged).
- [x] Answer 6: the Test name is editable in the details; a typed name is stored and kept (in `edited_fields`), "Use
      automatic name" (a `null`) goes back.
- [x] Answer 7: Units and Tags editable under More details as comma-separated text.
- [x] Answer 9: the uninstaller box text "Delete all app data (tests, students, backups)" (ERH change 3, installer.nsi).
- [x] Re-verifier F5: after the last thread in Chats is deleted, focus goes to the New thread button.
- [x] Rebuild 0.3.0 (`TAURI_BUILD`), re-measure and re-scan; update the 0.3.0 release-notes lines (build, sizes, scan,
      uninstall box text).

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.2.7.1 | An attempt with an uncertain verdict shows "AI unsure grade" in Student answers, the report panel and the report DOCX; no verdict cell shows a bare "?". | `APP_TEST` + `TEST` |
| R22.2.7.2 | `display_name()` gives "Grade 7 - Unit Test - 2025", "Grade 6 - 15-minute Test - 2025" and, with an unknown occasion, "Grade 8 - 2025 - Test 3"; the TS mirror matches on the shared cases; the migration remakes automatic names only, keeps `updated_at`, and search finds the new names. | `TEST` + `APP_TEST` |
| R22.2.7.3 | `PATCH /tests/{id}` with `display_name` "My name" stores it, adds it to `edited_fields`, and later metadata edits keep it; `null` removes it from `edited_fields` and remakes the name; `units` / `tags` round-trip as lists; the UI edits all three (Enter saves, Escape cancels) and shows "Use automatic name" only for a typed name. R12.1 holds. | `TEST` + `APP_TEST` |
| R22.2.7.4 | installer.nsi's box text is the new label (a script test); deleting the last thread puts focus on the New thread button (a unit test). | `APP_TEST` |
| R22.2.7.5 | S1–S7 hold; headless `E2E` passes; `cargo test --lib`; the rebuilt installer exists with `erh.exe --version` 0.3.0 and one dist-info; release notes updated; R22.2.6.3 (`E2E_SHELL --release`) runs again on the rebuild, started by the user. | `TEST` + `APP_TEST` + `E2E` + `E2E_SHELL --release` |

**Verifier notes:** 2026-10-15, fresh verifier, on `step/22.2.7-answers` at 8ee6947 (implementation ff5d6a7, 6ea03af, d69daa2, 8ada52d, a007c60, 18626c8). **Write scope:** every path in those commits is in §6 row 22.2.7 (`docs/initial-plan/plan.md` only the checklist ticks; `docs/release-notes.md` only the 0.3.0 section). **Standing:** S1 `TEST` 1469 passed, 14 deselected; S2 ruff clean, 228 files formatted, mypy `src` no issues in 91 files; S3 42 schema files, no diff; S4 only `llm/defaults.py`; S5 exit 0; S6 openapi unchanged; S7 `vitest run` exit 0, 33 files, 259 tests, no unhandled errors, eslint and `tsc --noEmit` clean, `gen:types` no diff. Headless `E2E` 26 passed; `cargo test --lib` 17 passed. The tree was clean after each run. **R22.2.7.1** passes: `answerMark` and the report's `verdictLabel` give "AI unsure grade"; `VERDICT_MARK["uncertain"]` in `docx_export.py`; tests step22_2_7.test and test_step22_2_7 (DOCX rows). `data-mark="?"` stays only as an attribute for print.css. Contrast of the label (`text-warning`) computed from the tokens: light 6.07:1 on surface, 4.90:1 on `bg-warning/10` over panel; dark 6.60–8.84:1. **R22.2.7.2** passes: test_models cases ("Grade 7 - Unit Test - 2025", "Grade 6 - 15-minute Test - 2025", "Grade 8 - 2025 - Test 3", "Untitled test"); the TS mirror reads the same `title_line_cases.json` (testTitle.test); migration 0005 skips `display_name` in `edited_fields`, does not touch `updated_at`, and updates `tests_fts` (test_0005_remakes_automatic_names_only, and the 0003+0005 chain equals `display_name()`). **R22.2.7.3** passes: `write_test_meta` keeps the trimmed name in `extra["display_name"]` and `edited_fields`, a non-teacher write cannot set or replace it, `null`/blank removes both; the PATCH test covers a later edit keeping it, search, `null` and units/tags lists; the UI test covers Enter, Escape, the automatic name typed again (no PATCH), "Use automatic name" shown only for a typed name, and Units/Tags. R12.1 tests pass in S1. **R22.2.7.4** passes: tauri-config.test checks the new box text and that the old one is gone (`installer.nsi:467`); the F5 unit test (with a stand-in button carrying the Sidebar's `sidebar-new-thread` test id, which `Sidebar.tsx` now has). **Broken on purpose, each restored:** the typed name not added to `edited_fields` in `write_test_meta` (2 fail); migration 0005 not skipping edited names (2 fail); `UNSURE_GRADE` set to "?" (2 fail); the New thread focus fallback removed (1 fail). **R22.2.7.5** (all but `E2E_SHELL`): the existing build, not rebuilt: `bundle/nsis/Exam Revision Helper_0.3.0_x64-setup.exe` 45,095,426 bytes and `exam-revision-helper.exe` 10,811,392 bytes, both written 2026-10-15 01:12:41, after a007c60 (01:09:02); `target/release/sidecar/erh.exe --version` 0.3.0; one dist-info (`erh-0.3.0`); 162 files, 107,594,431 bytes; all equal the release notes, which also record the rescan and the 22.2.7 changes. `E2E_SHELL --release` not run (started by the user). UI review with headless screenshots (light and dark, `app/test-results/verifier-22.2.7-*.png`, gitignored; the temporary spec was deleted): the Test name chip, a long typed name (wraps inside the chip), Use automatic name, and More details with Units and Tags and their hints look consistent with the other chips. **F7 (minor, WCAG 2.4.3, confirmed in jsdom and headless Chromium):** after "Use automatic name" is pressed, the button removes itself and keyboard focus falls to `<body>` (`TestPanel.tsx:439-448`); the same happens after Enter or Escape in any detail chip, since `MetaChip` does not return focus to the chip (`TestPanel.tsx:745-748`; older chips too, now also Test name, Units and Tags). **F8 (minor, docs):** `docs/release-notes.md` 0.1.0 "App folder" list, ERH change 3, still quotes the old box text "Delete app data (data, exports, webview, settings.json)", and the 0.3.0 heading "Uninstall: 'Delete app data' now deletes the data" uses the old name; the 0.3.0 section points to that list. The 0.1.0 section is outside row 22.2.7, so this is for the orchestrator. Neither finding blocks a requirement → **🔄 pending R22.2.7.5 `E2E_SHELL --release` (started by the user).**

---

## Step 22.3 — The teacher's third review

The teacher used installer 0.3.0 and wrote 19 comments, kept verbatim with the packages and decisions D1–D5 in
`docs/initial-plan/phases-testing/step22.3-plan.md`. It runs like step 22.2, with one change (teacher, 2026-10-15): before the
installer step, the questions parked in step22.3-plan §5 are asked and their code-changing answers built. One fresh
verifier checks 22.3.1–22.3.7 together; the user starts `E2E_SHELL --release`.

### Step 22.3.1 — Photo check and small screen fixes
**Depends on:** 22.2.7 · **Comments:** 2, 3, 4, 5, 7, 8, 9, 19 · step22.2-plan §5 F7

**Checklist**
- [x] Comments 3, 19: in the photo check, double-clicking a photo, or an expand button at its top-left corner, opens it
      full size (a dialog: Esc and a close button close it; ←/→ go through the photos; rotation as set), so page order
      and key pages can be checked before the run.
- [x] Comment 2: a short hint in the photo check, under the photos: mark the pages of the answer key as "Key".
- [x] Comment 4: the rotate button shows a quarter-turn arc with an arrow (not a full circle) and its label and
      tooltip say "Rotate 90°".
- [x] Comment 5: the test page's line numbers sit inside the page (same background, no separate box or offset edge),
      lighter, so the page does not look like two layers.
- [x] Comment 7: the intro line above the test page ("Edit the test like a document…") is removed; "Format help" has a
      chevron that turns, and the help slides open and closed (a short animation, none with reduced motion).
- [x] Comment 8: the Occasion editor shows the full list as soon as it opens or is clicked, and filters as the teacher
      types.
- [x] Comment 9: after the Test name (or anything that changes the shown title) is saved, the sidebar list and the
      thread header update at once.
- [x] F7 (step 22.2): focus returns to the chip after Enter/Escape in a detail chip, and to the Test name chip after
      "Use automatic name".

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.3.1.1 | In the photo check, double-click and the expand button open a full-size view of that photo with its rotation; Esc and Close close it and focus returns to the photo; ←/→ move between photos; the dialog has a name and traps focus. | `APP_TEST` + `E2E` |
| R22.3.1.2 | The photo check shows the key-page hint text; the rotate button's tooltip is "Rotate 90°" and its accessible name "Rotate page N 90°" (v2.24.1); its icon is not the reload icon. | `APP_TEST` |
| R22.3.1.3 | The test page's line-number gutter shares the page's background and border box (no second box edge); a headless screenshot shows one page. | `APP_TEST` + screenshot |
| R22.3.1.4 | The intro line is gone; Format help has `aria-expanded`, a chevron that rotates when open, and an open/close transition that is off under `prefers-reduced-motion`. | `APP_TEST` |
| R22.3.1.5 | Opening or clicking the Occasion editor lists all ten occasions without typing; typing filters; keyboard (↓/↑/Enter) works. | `APP_TEST` |
| R22.3.1.6 | Saving a new Test name updates the sidebar row and the thread header without a reload (a test on the list state after the save). | `APP_TEST` + `E2E` |
| R22.3.1.7 | After Enter/Escape in a detail chip, focus is on that chip; after "Use automatic name", on the Test name chip. | `APP_TEST` |
| R22.3.1.8 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-18, one fresh verifier for 22.3.1–22.3.7 (teacher's choice), on `step/22.3.7-occasions` at e98923b, clean tree. **Standing (whole round, at the tip):** S1 `TEST` 1521 passed, 14 deselected; S2 ruff clean, 243 files formatted, mypy `src` no issues in 96 files; S3 42 schema files, no diff; S4 only `llm/defaults.py` (plus its gitignored `.pyc`); S5 exit 0; S6 openapi unchanged; S7 `vitest run` 40 files, 312 tests passed, eslint and `tsc --noEmit` clean, `gen:types` no diff (one run under pytest load failed `step22_2_focus` "Keep test returns focus" once; alone 3/3 and the full rerun pass: a timing flake). Headless `E2E` 31 passed (+2 temporary verifier tests, deleted after); `cargo test --lib` 17 passed. **Write scope:** 9d5805b, dd54e92, 9944cd1, 4c6f768 stay in §6 row 22.3.1. **R22.3.1.1–7** pass: `PhotoFullView.tsx` is a named `role=dialog` `aria-modal` with a Tab trap, Esc/Close and ←/→, focus back to the photo (step22_3_1.test, s8 E2E); rotate tooltip "Rotate 90°", name "Rotate page N 90°"; one-page gutter (E2E y-test-page); Format help `aria-expanded`, no motion under reduced motion; the occasion list on open; sidebar and header update after a rename (E2E); F7 focus return. No finding → **✅**.

### Step 22.3.2 — Straight to work
**Depends on:** 22.3.1 · **Comments:** 14, 18 · decision D2 · **PRD:** §10 "Straight to work" (v6.3)

**Checklist**
- [x] D2: selecting a thread whose extraction is done opens its workspace (Test tab first); the conversation view and
      its cards are no longer reachable for it. A new or still-running thread shows its start screen (drop, photo
      check, progress) and switches to the workspace when the run finishes.
- [x] Comment 14: the Test page's top right, on the tab row, has "Grade student answers" ("Grade again" once graded;
      disabled with a reason only when no student answers were read; on a test-only thread it reads "Make the key" and
      grades the blank test, v2.25.1) and "Extract again" (`POST /threads/{id}/extract-again`, llm-design v4.29; asks
      first, and says what it replaces). Everything the cards offered stays reachable: Grade, the merge /
      duplicate and unsure notes (already in place), the photos (the workspace's photo viewer).
- [x] D2: while a run goes for the thread, a progress bar (the existing `RunProgressBar`) shows at the top of the
      workspace, with Stop; the sidebar's running indicator stays.
- [x] Comment 18: the workspace header shows the student chip on every thread with a student's paper (also when the
      name was not read); setting it uses `PUT /attempts/{id}/student`. A test-only thread has no student (teacher,
      v2.25.1).

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.3.2.1 | Clicking an extracted thread in the sidebar shows the workspace with the Test tab selected and no conversation; a thread with a running extract shows the start screen with progress, and the workspace appears when `run.done` arrives. | `APP_TEST` + `E2E` |
| R22.3.2.2 | "Grade student answers" starts the grade run (as the old card's Grade did; it writes AI keys when there are none) and is disabled with a visible reason only when no student answers were read; on a test-only thread the button reads "Make the key" and grades the blank test; "Grade again" after grading; "Extract again" asks first, calls `POST /threads/{id}/extract-again` (sidecar test: new run on the last pages, supersedes the attempt, 409 while active; R12.1 holds); both are on the tab row at the right and keyboard-reachable. | `APP_TEST` + `E2E` |
| R22.3.2.3 | During a run the workspace shows a `role="progressbar"` with the stage text and Stop; it goes at `run.done`. | `APP_TEST` |
| R22.3.2.4 | A thread whose paper had answers but no name shows the student chip in the workspace; choosing or creating a student saves it, the sidebar title becomes "<test> · <student>", and it survives a reload. A test-only thread shows no student chip. | `APP_TEST` + `TEST` |
| R22.3.2.5 | No feature is lost with the cards: each action the extraction and grade cards had is reachable from the workspace (a test lists them). S1–S7 hold; headless `E2E` passes (specs that clicked card buttons now use the workspace). | `APP_TEST` + `E2E` + `TEST` |

**Verifier notes:** 2026-10-18, one fresh verifier for 22.3.1–22.3.7 (teacher's choice), on `step/22.3.7-occasions` at e98923b, clean tree. **Standing (whole round, at the tip):** S1 `TEST` 1521 passed, 14 deselected; S2 ruff clean, 243 files formatted, mypy `src` no issues in 96 files; S3 42 schema files, no diff; S4 only `llm/defaults.py` (plus its gitignored `.pyc`); S5 exit 0; S6 openapi unchanged; S7 `vitest run` 40 files, 312 tests passed, eslint and `tsc --noEmit` clean, `gen:types` no diff (one run under pytest load failed `step22_2_focus` "Keep test returns focus" once; alone 3/3 and the full rerun pass: a timing flake). Headless `E2E` 31 passed (+2 temporary verifier tests, deleted after); `cargo test --lib` 17 passed. **Write scope:** 6f284a1, 580fef5, 48e74bb, 0ea6bc6 and the test commits stay in §6 row 22.3.2. **R22.3.2.1–5** pass: `AppShell.tsx` `threadView` shows the thread's Test workspace once `detail.test` exists (a running extract has none, so the start screen stays); Grade / Make the key / Grade again / Extract again on the tab row; extract-again 409 while active (test_step22_3_2); progressbar with Stop; the student chip only with a paper; the card actions list test. **Broken on purpose:** `threadView` forced to null → 25 vitest tests fail; restored. Builder note (step22.3-plan §5) confirmed: Grade disabled "without student answers" cannot happen in the UI; such a thread shows Make the key. No finding → **✅**.

### Step 22.3.3 — Delete a student; series details
**Depends on:** 22.3.2 · **Comments:** 1, 15 · decisions D1, D3 · **PRD:** §10 students and series (v6.4) ·
**data-model:** §5.7 student, `series_from_test_id`, copying (v1.14) · **llm-design:** §2 (v4.30)

**Checklist**
- [x] D1: `GET /students/{id}/delete-preview` and `DELETE /students/{id}` (data-model §5.7, one transaction, 409 while
      a run of one of their threads is active or resumable); "Delete…" on each student in the Students tab through
      `useConfirm`, listing the threads; lists update and an open thread of theirs closes.
- [x] D3: `POST /tests/{id}/copy-details` and "Copy details from…" in the test details (a test picker like the
      existing name search; shows what will change before copying).
- [x] D3: "same series as…" at the photo check next to the same-test pick; `ExtractInput.series_from_test_id` applied
      at save so the new test has those details (teacher-set) and the AI's values fill only the rest.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.3.3.1 | Deleting a student removes exactly their threads (row counts per table, as R22.2.3.1) and the student; tests and other students stay; a thread shared with another student keeps that student's attempt; atomic; 409/404 as for threads; the preview lists exactly what goes. | `TEST` |
| R22.3.3.2 | Copy details copies occasion, term, school, source and year that have a value (blank source fields leave the target's value), not grade or test number; the copied fields are in `edited_fields`; the automatic name follows; an extraction run on that test later does not overwrite them. | `TEST` |
| R22.3.3.3 | An extract (the in-process fake-Ollama graph test counts as the replay, v2.26.1) with `series_from_test_id` saves a test whose occasion, term, school, source and year equal the series test's, with grade and test number from the run. | `TEST` |
| R22.3.3.4 | UI: Delete… on a student asks first, lists the threads, and updates the lists; Copy details from… lets the teacher pick a test, shows the five values, and saves; the photo check offers same series as… and sends it. Focus handling as in 22.2.3. | `APP_TEST` |
| R22.3.3.5 | S1–S7 hold (R12.1 with the new routes); headless `E2E` deletes a seeded student and copies details between two tests. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-18, one fresh verifier for 22.3.1–22.3.7 (teacher's choice), on `step/22.3.7-occasions` at e98923b, clean tree. **Standing (whole round, at the tip):** S1 `TEST` 1521 passed, 14 deselected; S2 ruff clean, 243 files formatted, mypy `src` no issues in 96 files; S3 42 schema files, no diff; S4 only `llm/defaults.py` (plus its gitignored `.pyc`); S5 exit 0; S6 openapi unchanged; S7 `vitest run` 40 files, 312 tests passed, eslint and `tsc --noEmit` clean, `gen:types` no diff (one run under pytest load failed `step22_2_focus` "Keep test returns focus" once; alone 3/3 and the full rerun pass: a timing flake). Headless `E2E` 31 passed (+2 temporary verifier tests, deleted after); `cargo test --lib` 17 passed. **Write scope:** ba17713, 67785e3, 909b0ae, 93f4645, 361062a stay in §6 row 22.3.3. **R22.3.3.1** passes: `delete_student` (`store/repos/deletes.py`) deletes the student's whole threads, their attempts in shared threads, then the student, in one `transaction`; 409/404 and the preview are tested. **R22.3.3.2/3** pass: `SERIES_FIELDS` = occasion, term, school, source, year, filled values only, as a teacher write. **R22.3.3.4/5** pass (vitest, E2E yz-students-series). **Broken on purpose, each restored:** `transaction` removed in `delete_student` → `test_delete_student_409_404_and_atomic` fails; `grade` added to `SERIES_FIELDS` → 1 fails. No finding → **✅**.

### Step 22.3.4 — Sentence keys
**Depends on:** 22.3.3 · **Comment:** 10 · **data-model:** §2.4 `accepted` (v1.15)

**Checklist**
- [x] Find where a rewrite/combine question keeps the words the paper already prints for the answer (the "đề" in comment
      10: e.g. "My brother …" given before the line) — stem, cue or both — and write one function that makes the four
      forms from a key sentence and those words.
- [x] Every key write for a `rewrite` / `combine` question (from the key photo, the AI key, a teacher edit) stores the
      four forms in `accepted` (unique, canonical first); existing keys get them once (a migration or a one-time
      upgrade, keeping `updated_at`).
- [x] The Key panel shows the forms as accepted answers; the teacher can remove one, and a removed form does not come
      back unless the key text changes.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.3.4.1 | For the teacher's example (given "My brother", key "My brother used to stay up late playing mobile games.") the function returns exactly the four forms of comment 10, canonical first; with no given words, two forms (with and without the full stop); other punctuation, Vietnamese letters and case are unchanged; it is pure and idempotent. | `TEST` |
| R22.3.4.2 | Saving a rewrite/combine key from each source stores the forms; other question types are unchanged; grading a student answer equal to any form is correct without a model call (the normalized match); the upgrade adds the forms to existing keys once. | `TEST` |
| R22.3.4.3 | The Key panel lists the forms; removing one and saving keeps it removed; editing the key text remakes the forms. | `APP_TEST` |
| R22.3.4.4 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-18, one fresh verifier for 22.3.1–22.3.7 (teacher's choice), on `step/22.3.7-occasions` at e98923b, clean tree. **Standing (whole round, at the tip):** S1 `TEST` 1521 passed, 14 deselected; S2 ruff clean, 243 files formatted, mypy `src` no issues in 96 files; S3 42 schema files, no diff; S4 only `llm/defaults.py` (plus its gitignored `.pyc`); S5 exit 0; S6 openapi unchanged; S7 `vitest run` 40 files, 312 tests passed, eslint and `tsc --noEmit` clean, `gen:types` no diff (one run under pytest load failed `step22_2_focus` "Keep test returns focus" once; alone 3/3 and the full rerun pass: a timing flake). Headless `E2E` 31 passed (+2 temporary verifier tests, deleted after); `cargo test --lib` 17 passed. **Write scope:** df6f325, 7619648, db66934 stay in §6 row 22.3.4 (`domain/review.py` is a key write; `eval/metrics.py` added by structure v1.1.104). **R22.3.4.1–4** pass: `sentence_forms` (`domain/keys.py`) gives full, no full stop, without the given words, both; pure, unique; migration 0006 with `key_forms_pending`; the Key panel lists and removes forms (sentenceKeys.test). §5 note read: the eval counts a key as a sentence at 4 or more words. No finding → **✅**.

### Step 22.3.5 — Models
**Depends on:** 22.3.4 · **Comments:** 12, 12.5, 13, 17 · decision D4 · **PRD:** D7 (v7.0), §10 Settings ·
**llm-design:** §2 model routes (v4.31). The orchestrator reviews the builder's model manager before the step closes
(teacher, 2026-10-17).

**Checklist**
- [x] Sidecar: `GET /models`, `POST /models/pull` (SSE progress, Cancel), `DELETE /models/{name}` through the existing
      Ollama client, against the app's own Ollama (`OLLAMA_MODELS` = `<app>\data\models`); never another Ollama.
- [x] D4: the default vision tag becomes `qwen3.5:4b` in `llm/defaults.py` and the shipped `models.toml`; an existing
      `models.toml` that still names NuExtract keeps it (the teacher changes it in Settings); first run and "Download
      models" pull the configured tags (now one tag for both roles).
- [x] Comment 12: each role's model field in Settings is a combobox listing the installed models (name and size),
      showing the full list on open, filtering as typed, still accepting a typed tag; a tag that is not installed is
      flagged with "Not installed — Download".
- [x] Comments 12.5, 17: a model manager in Settings: installed models with size and the roles using them; Download a
      tag (typed or from suggested tags) with a progress bar and Cancel; Delete with a confirm; a model a role uses
      shows why it cannot be deleted; errors (Ollama not running, no internet, disk full) in plain words.
- [x] The prompt profiles per model tag (llm-design §8) still resolve for `qwen3.5:4b` in the vision role; if no profile
      exists for it, report what the vision prompts fall back to.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.3.5.1 | With a fake Ollama: `GET /models` lists installed models with size and roles; `POST /models/pull` streams progress events and ends done, Cancel stops it and leaves no partial model listed; `DELETE` removes an unused model and gives 409 for one a role uses or during a run; Ollama not running gives a readable 503. R12.1 holds. | `TEST` |
| R22.3.5.2 | Fresh settings give `qwen3.5:4b` for vision and reasoning; an existing `models.toml` naming NuExtract is not rewritten; the vision prompt profile used for `qwen3.5:4b` is named in the test. | `TEST` |
| R22.3.5.3 | Settings: each role's combobox shows the installed models on open, filters, accepts a typed tag, flags a missing tag; the model manager lists, downloads (progress, Cancel) and deletes (confirm; blocked with a reason for a used model); everything works by keyboard and reads correctly to a screen reader. | `APP_TEST` |
| R22.3.5.4 | Network access stays limited to model downloads (R13.3 / the offline check's rules still hold: a headless E2E records no external request outside a pull). S1–S7 hold; headless `E2E` passes, with the model manager on the replay sidecar's fake model list. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-18, one fresh verifier for 22.3.1–22.3.7 (teacher's choice), on `step/22.3.7-occasions` at e98923b, clean tree. **Standing (whole round, at the tip):** S1 `TEST` 1521 passed, 14 deselected; S2 ruff clean, 243 files formatted, mypy `src` no issues in 96 files; S3 42 schema files, no diff; S4 only `llm/defaults.py` (plus its gitignored `.pyc`); S5 exit 0; S6 openapi unchanged; S7 `vitest run` 40 files, 312 tests passed, eslint and `tsc --noEmit` clean, `gen:types` no diff (one run under pytest load failed `step22_2_focus` "Keep test returns focus" once; alone 3/3 and the full rerun pass: a timing flake). Headless `E2E` 31 passed (+2 temporary verifier tests, deleted after); `cargo test --lib` 17 passed. **Write scope:** ca78c7b, 8cca17f, 6a8966c stay in §6 row 22.3.5 (routes are registered through `pkgutil`, no `api/app.py` change). **R22.3.5.1** passes on the fake store. **R22.3.5.2**: vision and reasoning default to `qwen3.5:4b` (`llm/defaults.py:34,41`); `SUGGESTED_TAGS` = qwen3.5:4b and NuExtract (teacher's §5 answer 2). **R22.3.5.3**: `ModelCombobox` is an ARIA combobox (`aria-expanded/controls/activedescendant`, `aria-invalid` with the described flag); the manager uses a named `<progress>`, Cancel and Dismiss named per tag, a used model's Delete described by its reason. **R22.3.5.4**: the settings-models E2E records no non-loopback request; the app's only fetch goes to the loopback sidecar. **Broken on purpose, each restored:** the role 409 in `delete_model` removed → 1 fails; the pull stream's `aclose`/`on_end` removed → 3 fail, incl. `test_cancel_stops_the_pull_and_leaves_nothing_listed`. Worth a look (minor, not run in a browser): `ModelManager.tsx` has no focus code after a confirmed delete (the row and its button go), the same class as F-a under 22.3.7. → **✅**.

**Re-verification (F-a, F-b):** 2026-10-18, fresh verifier on `step/22.3.7-occasions` at c1bf611. **Pass; row stays ✅.** Diff only in `app/src/features/settings/` (OccasionList, ModelManager, models.test), `app/src/features/step22_3_7.test.tsx` and `app/e2e/zy-occasions.spec.ts` (§6 rows 22.3.5/22.3.7). `vitest run` exit 0 (40 files, 314 tests), eslint and `tsc --noEmit` clean, full headless `npm run e2e` 31 passed. F-a: headless Chromium with keyboard, `document.activeElement` after Up = the moved row's Up; Down to the bottom = its Up; Rename Escape and Save = its Rename; Delete middle = next row's Rename; Delete last = the row now in its place; Delete cancelled = its Delete; model delete = next model's Delete, or the Download field when the next is in use (models faked with `page.route`, no Ollama). Commenting out the rename focus target made the 22.3.7 focus test fail (body instead of button); restored. F-b: one note "Built-in occasions can be renamed but not deleted." above the list, given to each built-in's disabled Delete by `aria-describedby`; light/dark screenshots show the name on its own row width and the buttons as one group; muted text 6.1–7.4:1. No findings.

### Step 22.3.6 — Typed files as text, and sentence openings
**Depends on:** 22.3.5 · **Comments:** 6, 10 · decisions D5, D6 · **PRD:** v7.1 · **data-model:** `answer_start`,
§2.3a (v1.16) · **llm-design:** typed pages and sentence openings (v4.32)

**Checklist**
- [x] D5: in the extract graph, a born-digital page (the existing D26 test) goes to `structure_text_page` (text only,
      reasoning role) instead of `transcribe_page`; same output schema; pictures as D11 placeholders; mixed files
      route per page; the tile re-transcription never runs on a typed page.
- [x] D6: `Question.answer_start` (schema, content upgrade not needed: optional); the transcription and structuring
      prompts ask for it on rewrite/combine questions; the test text shows and reads it (`   Start: …`); the sentence
      forms (22.3.4) use it first.
- [x] Synthetic cassettes for `structure_text_page` (a typed page with sections, options, a passage, a rewrite with a
      start) so replay covers the new path; no live model runs.
- [x] A short runbook section for the teacher's GPU check (which files, what to compare), in
      `docs/initial-plan/phases-testing/step22.3-plan.md` §6, written by the builder for the orchestrator to review.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.3.6.1 | A replayed extract of a synthetic typed PDF calls `structure_text_page` for its typed pages and never `transcribe_page` / `retranscribe_tiles` for them; a scanned page in the same file still uses `transcribe_page`; the saved test has the structure from the cassette, its pictures as placeholders, and no answer reading (D26). | `TEST` |
| R22.3.6.2 | `answer_start` round-trips through content JSON, the test text (`   Start: …`, read and render), the DOCX/print (shown as the printed line), and the key forms (a key "My brother used to …" with `answer_start` "My brother" gets the four forms of comment 10). Older content without the field still loads. | `TEST` + `APP_TEST` |
| R22.3.6.3 | The prompts for `transcribe_page` and `structure_text_page` mention `answer_start` only for rewrite/combine; prompt-render tests updated; cassette matching unaffected (llm-design: the match key excludes the prompt). | `TEST` |
| R22.3.6.4 | 👤 Teacher's GPU check before installer 0.4.0, run by the teacher after a warning: one typed national exam PDF and one photographed test with rewrites, with `qwen3.5:4b`; the result (structure correct? opening words kept? time) recorded in step22.3-plan §6. | 👤 run |
| R22.3.6.5 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-18, one fresh verifier for 22.3.1–22.3.7 (teacher's choice), on `step/22.3.7-occasions` at e98923b, clean tree. **Standing (whole round, at the tip):** S1 `TEST` 1521 passed, 14 deselected; S2 ruff clean, 243 files formatted, mypy `src` no issues in 96 files; S3 42 schema files, no diff; S4 only `llm/defaults.py` (plus its gitignored `.pyc`); S5 exit 0; S6 openapi unchanged; S7 `vitest run` 40 files, 312 tests passed, eslint and `tsc --noEmit` clean, `gen:types` no diff (one run under pytest load failed `step22_2_focus` "Keep test returns focus" once; alone 3/3 and the full rerun pass: a timing flake). Headless `E2E` 31 passed (+2 temporary verifier tests, deleted after); `cargo test --lib` 17 passed. **Write scope:** 7ce56bc, 178682b, 9dc2bfe, 9abdfc2, d0ba071, d01e510 stay in §6 row 22.3.6 except two one-line additions: `domain/renumber.py` (`answer_start=tq.answer_start` in `merge_pages`) and `domain/llm_schemas.py` (`TranscribedQuestion.answer_start`); the row names `domain/{models,test_text,keys,docx_export}.py` and "`llm/` (the new task's schema)" — **minor, docs, for the orchestrator** (the row could name them). **R22.3.6.1–3, 5** pass: `graphs/extract.py:909-913` sends a typed page with a text layer to `structure_text_page`; typed-pdf and typed-pdf-mixed replays; `answer_start` through the test text, DOCX, print and `given_words` (`domain/keys.py:157`). **Broken on purpose, each restored:** the typed route set to `transcribe_page` → both typed-PDF replays fail; `answer_start` ignored in `given_words` → 1 fails. R22.3.6.4 (the teacher's GPU check) not run, as instructed → **🔄 pending R22.3.6.4 (teacher's GPU check).**

### Step 22.3.7 — Edit occasions
**Depends on:** 22.3.6 · the teacher's answer of 2026-10-18 (step22.3-plan §4) · **PRD:** occasions (v7.2) ·
**data-model:** `occasions` (v1.17) · **llm-design:** §2 occasion routes (v4.33)

**Checklist**
- [x] A migration creates `occasions` and seeds the ten built-ins with today's labels and short names (22.2.1, 22.2.7);
      `display_name()`, the TS title mirror (`title_line_cases.json`) and the occasion editor read labels and short
      names from it (the sidecar sends them; the app no longer hard-codes them).
- [x] The four routes; renaming remakes automatic Test names (not teacher-typed ones) and their search rows; delete is
      refused while a test uses the code or for a built-in.
- [x] Settings: an **Occasions** list: add (label and short name), rename inline, move up/down, delete (confirm; blocked
      with the reason and the number of tests using it).

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.3.7.1 | After the migration the ten built-ins give exactly today's labels and Test names (the shared title cases pass unchanged); a teacher occasion appears in the editor, the chip and the Test name; renaming a built-in remakes the automatic names of tests using it, leaves typed names alone, and search finds the new name; delete gives 409 while used or built-in. R12.1 holds. | `TEST` |
| R22.3.7.2 | Settings' Occasions list adds, renames, reorders and deletes (with confirm and the blocked reason), by keyboard too; the Occasion editor (22.3.1) lists the new order and labels at once. | `APP_TEST` |
| R22.3.7.3 | S1–S7 hold; headless `E2E` adds an occasion, uses it on a test, and sees it in the Test name. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-18, one fresh verifier for 22.3.1–22.3.7 (teacher's choice), on `step/22.3.7-occasions` at e98923b, clean tree. **Standing (whole round, at the tip):** S1 `TEST` 1521 passed, 14 deselected; S2 ruff clean, 243 files formatted, mypy `src` no issues in 96 files; S3 42 schema files, no diff; S4 only `llm/defaults.py` (plus its gitignored `.pyc`); S5 exit 0; S6 openapi unchanged; S7 `vitest run` 40 files, 312 tests passed, eslint and `tsc --noEmit` clean, `gen:types` no diff (one run under pytest load failed `step22_2_focus` "Keep test returns focus" once; alone 3/3 and the full rerun pass: a timing flake). Headless `E2E` 31 passed (+2 temporary verifier tests, deleted after); `cargo test --lib` 17 passed. **Write scope:** 59f6c66, b9da679, 7dbb0ee, 0dbd5e0, 2c8c82a, dfec857 stay in §6 row 22.3.7 (v1.1.109). **R22.3.7.1** passes: migration 0007; `_remake_names` remakes `display_name` through `TestMetadata.display_name()` (a typed name is kept) and the search row; delete gives 409 for a built-in or a used occasion; merged tests go to `Other:unknown`. **R22.3.7.2/3** pass (step22_3_7.test, E2E zy-occasions). **Broken on purpose, each restored:** no remake on rename → 1 fails; a remake that ignores `edited_fields` (typed name overwritten) → `test_rename_remakes_automatic_names_only` fails. **F-a (minor, WCAG 2.4.3, confirmed in headless Chromium, light and dark):** in Settings → Occasions, after Down (Enter) and after Escape in Rename, `document.activeElement` is `<body>` (`OccasionList.tsx`: `run()` sets `busy`, which disables the focused button; the rename form unmounts; there is no focus code). Moving an occasion several places by keyboard needs Tab back each time; Save and Delete likewise. Same class as 22.2's F7. **F-b (minor, usability, screenshot `app/test-results/verifier-22.3-settings-light.png`, gitignored):** in the Settings drawer every built-in row repeats "Built-in: can be renamed, not deleted", which squeezes the name to about 60px, so "Gifted students' exam · in the Test name: Gifted Exam" wraps one word per line and each row is about 200px tall. Neither blocks a requirement → **✅**.

**Re-verification (F-a, F-b):** 2026-10-18, fresh verifier on `step/22.3.7-occasions` at c1bf611. **Pass; row stays ✅.** Diff only in `app/src/features/settings/` (OccasionList, ModelManager, models.test), `app/src/features/step22_3_7.test.tsx` and `app/e2e/zy-occasions.spec.ts` (§6 rows 22.3.5/22.3.7). `vitest run` exit 0 (40 files, 314 tests), eslint and `tsc --noEmit` clean, full headless `npm run e2e` 31 passed. F-a: headless Chromium with keyboard, `document.activeElement` after Up = the moved row's Up; Down to the bottom = its Up; Rename Escape and Save = its Rename; Delete middle = next row's Rename; Delete last = the row now in its place; Delete cancelled = its Delete; model delete = next model's Delete, or the Download field when the next is in use (models faked with `page.route`, no Ollama). Commenting out the rename focus target made the 22.3.7 focus test fail (body instead of button); restored. F-b: one note "Built-in occasions can be renamed but not deleted." above the list, given to each built-in's disabled Delete by `aria-describedby`; light/dark screenshots show the name on its own row width and the buttons as one group; muted text 6.1–7.4:1. No findings.

### Step 22.3.8 — Installer 0.4.0
**Depends on:** 22.3.7, the round's verifier and the teacher's GPU check (R22.3.6.4: run, failed, the teacher chose to
ship) · R21.1, R21.2 and R21.5 again on the final commit, as in 22.2.6.

**Checklist**
- [x] Version 0.4.0 in the places 22.2.6 changed (incl. `sidecar/src/erh/__init__.py`, the tests that pin it,
      `sidecar/schema/openapi.json`); `app/src-tauri/gen/schemas/` regenerated if the build changes it.
- [x] `TAURI_BUILD`; sizes and the Defender scan in a new `docs/release-notes.md` section 0.4.0: what changed since
      0.3.0 in plain words (steps 22.3.1–22.3.7), the model change (qwen3.5:4b default for images, through the chat
      adapter and the generic profile; an existing models.toml keeps its tags; how to switch and delete NuExtract in the
      model manager), the known limits from step22.3-plan §6 (typed PDFs and opening words), the new migrations
      0006–0007 run at first start (0004–0005 came with 0.3.0; v2.31.1), and how to install over 0.3.0.
- [x] No `E2E_SHELL` by the builder (the user starts it).

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.3.8.1 | Every version string is 0.4.0 and the lock files agree; `erh --version` prints 0.4.0; S1–S7 hold; headless `E2E` passes; `cargo test --lib` passes with no diff in `app/src-tauri/gen/`. | `TEST` + `APP_TEST` + `E2E` |
| R22.3.8.2 | R21.1: `TAURI_BUILD` exits 0 and outputs `Exam Revision Helper_0.4.0_x64-setup.exe`; `target/release/sidecar/erh.exe --version` prints 0.4.0 with one `erh-*.dist-info`. | Run it |
| R22.3.8.3 | R21.2: `E2E_SHELL --release`, Settings shows 0.4.0; started by the user. | `E2E_SHELL --release` |
| R22.3.8.4 | R21.5: release notes 0.4.0 with sizes, the Defender scan of installer, sidecar folder and shell exe, the changes, the model note, the known limits and the update steps; earlier sections unchanged. | Read the file |

**Verifier notes:** 2026-10-19, fresh verifier, on `step/22.3.8-installer` at 74f8ea1 (implementation c12ec94, 0769ac3, cb77e46; f439ebe and 74f8ea1 are the orchestrator's). **Write scope:** every path in the implementation commits is in §6 row 22.3.8 (eleven version files and the two tests that pin it; `docs/release-notes.md` only adds lines, 122 added, 0 removed; `docs/initial-plan/plan.md` only the three checklist ticks). **R22.3.8.1** passes: 0.4.0 in `app/package.json`, `package-lock.json` (both entries), `tauri.conf.json`, `Cargo.toml`, `Cargo.lock` (`exam-revision-helper`), `pyproject.toml`, `uv.lock` (`erh`), `erh/__init__.py`, `schema/openapi.json`, firstRun.test and settings.test; no other 0.3.0 left in app/ or sidecar/ (only the `alloc-stdlib` crate in Cargo.lock); `uv run erh --version` 0.4.0. S1 `TEST` 1521 passed, 14 deselected; S2 ruff clean, 243 files formatted, mypy `src` no issues in 96 files; S3 schema export no diff; S4 only `llm/defaults.py`; S5 exit 0; S6 openapi no diff; S7 `vitest run` 40 files, 314 tests passed, eslint and `tsc --noEmit` clean, `gen:types` no diff. Headless `E2E` 31 passed; `cargo test --lib` 17 passed, no diff in `app/src-tauri/gen/`. The tree was clean after each run. **R22.3.8.2** (the existing build, not rebuilt): `bundle/nsis/Exam Revision Helper_0.4.0_x64-setup.exe` 45,153,255 bytes and `exam-revision-helper.exe` 10,819,072 bytes, both written 2026-10-19 09:58:35, after the last code commit c12ec94 (09:47:01); `target/release/sidecar/erh.exe --version` 0.4.0; one dist-info (`erh-0.4.0`); 165 files (as `sidecar/dist/erh/`), 107,638,161 bytes; all equal the release notes. The embedded front end is compressed, so the time order is the evidence. **R22.3.8.4** passes: the 0.4.0 section has the build, the three sizes (the differences from 0.3.0 add up), the Defender scan of installer, sidecar folder and shell exe (no threats), the changes of 22.3.1–22.3.7, the model note (qwen3.5:4b default through the chat adapter and the generic profile; an existing models.toml keeps NuExtract; how to switch and delete it), the known limits as step22.3-plan §6 records them (typed PDF worse than images, no `Start:` line on either path, page 1 lost once), migrations 0006–0007, and the update steps including leaving the uninstaller's "Delete all app data" box unticked; earlier sections unchanged. No findings. R22.3.8.3 not run (`E2E_SHELL --release`, started by the user). Note: the 22.3.6 row stays 🔄 for the teacher's sign-off on R22.3.6.4; this step's "Depends on" already names that outcome. → **🔄 pending R22.3.8.3 `E2E_SHELL --release` (started by the user).**

**R22.3.8.3 E2E_SHELL** run 2026-10-19 by the user (`cd app && npm run e2e:shell -- --release`) on the 0.4.0 release build: the first run failed one check, "R20.7 the S1 thread opens with its extraction card", because since 22.3.2 a thread opens into its workspace; the orchestrator changed that check in `app/e2e-shell/run.mjs` to wait for the workspace (2d03852, test only, no rebuild). The rerun: 20 PASS, "E2E_SHELL: all passed"; Settings shows 0.4.0 = `erh --version`; R14.5 nothing new in %APPDATA%/%LOCALAPPDATA%; R20.7 moved-folder checks pass. ✅

---

## Step 22.4 — The teacher's fourth review

The teacher used installer 0.4.0 and wrote 14 comments, kept verbatim with the orchestrator's findings, the packages
and decisions D1–D6 in `docs/initial-plan/phases-testing/step22.4-plan.md`. It runs like step 22.3: sub-steps on stacked branches,
parked questions asked and built before the installer, one fresh verifier for 22.4.1–22.4.7 (22.4.7 also needs the
teacher's GPU check), then the user's `E2E_SHELL --release`. Each sub-step gets its checklist and requirements when it
starts.

### Step 22.4.1 — Screen fixes
**Depends on:** 22.3.8 · **Comments:** 4, 6, 9

**Checklist**
- [x] Comment 4: opening "Format help" scrolls the page so the opened help is in view (smooth; instant under
      `prefers-reduced-motion`); focus stays on the button; closing does not scroll.
- [x] Comment 6: the workspace tabs (Test · Key · Student answers · Report) look like buttons: a visible border and
      background, the selected tab filled in the theme green, a hover state and the focus ring; the tablist roles and
      arrow-key behaviour stay.
- [x] Comment 9: when the thread has student answers, the grade button always reads "Grade student answers" (never
      "Grade again"); only the text changes; "Make the key" without answers stays.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.4.1.1 | Opening Format help calls a scroll that brings the help panel into view (smooth, or `auto` under reduced motion); focus stays on the button; closing does not scroll. | `APP_TEST` |
| R22.4.1.2 | Each workspace tab has a visible border and background; the selected tab has the filled style and `aria-selected="true"`; text and border contrast meet WCAG 2.1 AA (4.5:1 text, 3:1 border against the page); a headless screenshot shows them as buttons. | `APP_TEST` + screenshot |
| R22.4.1.3 | With an attempt, graded or not, the button text is "Grade student answers"; "Grade again" appears nowhere in `app/src` outside tests that assert its absence; the button's action is unchanged. | `APP_TEST` |
| R22.4.1.4 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-19, one fresh verifier for 22.4.1–22.4.7. Standing checks run once at the tip `step/22.4.7-worked-example` df35e9a, one after another, clean tree before and after: S1 `TEST` 1564 passed, 14 deselected; S2 ruff clean, 254 files formatted, mypy `src` no issues in 102 files; S3/S6 schema and openapi export, no diff; S4 only `llm/defaults.py` (plus its gitignored `.pyc`); S5 exit 0; S7 `vitest run` 47 files, 351 tests passed, eslint and `tsc --noEmit` clean, `gen:types` no diff; headless `E2E` 33 passed. The earlier one-off flakes (E2E R16.2, R19.3, vitest step22_2_focus Escape) did not recur. No `👤 sign-off:` commit and no teacher field written; no fixture or cassette file changed in b27c29f..df35e9a. **Write scope** (b27c29f..96ff9cd): `app/e2e/`, `app/src/features/`, `docs/initial-plan/plan.md` (three ticks only), all in §6 row 22.4.1.
- **R22.4.1.1** ✅ `step22_4_1.test.tsx`: the scroll is called once on the help region after the slide, `{block: "nearest", behavior: "smooth"}` (`auto` under reduced motion), focus stays on the button, closing (also mid-slide) does not scroll; headless `s12-format-help.png` shows the opened help in view.
- **R22.4.1.2** ✅ same file: border and background classes per tab, the selected one `bg-accent text-accent-text border-accent-strong` with `aria-selected="true"`, arrows still move; contrast from `tokens.css` in light and dark (text ≥ 4.5:1, borders and focus ring ≥ 3:1 on `--erh-panel`; the class-to-token mapping is in `index.css`). Screenshots `s22.4.1-tabs-light/dark.png` show bordered buttons, the selected one filled green. Broken on purpose (no `bg-accent` on the selected tab) → the test fails; restored.
- **R22.4.1.3** ✅ "Grade again" occurs in `app/src` only in `step22_3_2.test.tsx:138` (asserting its absence) and in step22_4_1.test; the graded case reads "Grade student answers" and POSTs the same grade run body.
- **R22.4.1.4** ✅ (standing checks above).

### Step 22.4.2 — Settings tabs and the school list
**Depends on:** 22.4.1 · **Comments:** 1, 10 · decisions D1, D2 (step22.4-plan §5) · **PRD:** v7.3 · **data-model:**
`schools` (v1.18) · **llm-design:** §2 school routes (v4.34)

**Checklist**
- [x] Settings is split into tabs: **General** (everything Settings has today except the next two), **Models** (the
      model manager and the role choices), **Occasions** (the 22.3.7 list), **Schools**; tablist roles and arrow keys
      as the workspace tabs (22.4.1); the chosen tab is kept while the app runs.
- [x] A migration creates `schools` and seeds it from the distinct schools on tests and students (case-insensitive,
      first spelling kept).
- [x] The four routes; renaming updates `tests.school` and `students.school`, remakes automatic Test names (not typed
      ones) and their search rows; delete is refused while a test or student uses it; a school typed on a test or a
      student that is not in the list is added.
- [x] Settings → Schools: add, rename inline, move up/down, delete (confirm; blocked with the reason and the counts),
      by keyboard too; built like the Occasions list.
- [x] Comment 10: the School field of a test (its detail chip) and of a student is a combobox like Occasion and Student:
      the whole list shows as soon as it opens or is clicked, typing filters, a new name can be typed.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.4.2.1 | Settings shows four tabs; each holds what the checklist says; switching keeps the app's state; keyboard works; Settings' existing tests still pass on their tab. | `APP_TEST` |
| R22.4.2.2 | After the migration, the list holds each distinct school once (a case variant does not add a second row); renaming updates tests, students, automatic Test names and search, and leaves typed names alone; delete gives 409 while used; a new school typed on a test is added; R12.1 holds. | `TEST` |
| R22.4.2.3 | The Schools tab adds, renames, reorders and deletes (with confirm and the blocked reason), by keyboard too. | `APP_TEST` |
| R22.4.2.4 | The School combobox lists every school without typing, filters as the teacher types, keyboard works (↓/↑/Enter/Esc), and a new name is saved and appears in the list. | `APP_TEST` + `E2E` |
| R22.4.2.5 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-19, see 22.4.1 for the standing checks. **Write scope** (22.4.1..5be30cb): migration 0008, `repos/{schools,students}.py`, routes `schools.py`/`tests.py`/`students.py`, generated schema/openapi/`app/src/gen`, UI and tests: in §6 row 22.4.2.
- **R22.4.2.1** ✅ `settingsTabs.test.tsx` (four tabs, typed values kept on switching, arrows/Home/End, tab kept on reopening); the existing Settings specs open their tab first. Screenshots `zz-settings-tabs-*.png` show General · Models · Occasions · Schools.
- **R22.4.2.2** ✅ `test_step22_4_2.py`: seeded once per school (Vietnamese case variants merged), rename updates tests, students, automatic Test names and search and leaves a typed name, 409 while used, a typed school is added; `test_route_table.py` (R12.1).
- **R22.4.2.3** ✅ `step22_4_2.test.tsx` (add, rename, move, delete with confirm, the blocked reason); `SchoolList.tsx` returns focus after move, rename and delete (unlike 22.3.7's F-a).
- **R22.4.2.4** ✅ same file (whole list on focus, filter with folded Vietnamese, ↓/Enter/Esc, a new name) and E2E `zz-schools.spec.ts` (a new name is saved and appears in the list); screenshot `zz-school-chip-open.png`.
- **R22.4.2.5** ✅.

### Step 22.4.3 — New-thread pickers
**Depends on:** 22.4.2 · **Comments:** 2, 3

**Checklist**
- [x] Comment 3: in the new-thread screen (photo check), the **Existing test** box and the **Same series as** box show
      suggestions as soon as they are focused or clicked, before any typing (the most recent tests, up to 8, as the Test
      menu does); typing filters as today; ↓/↑/Enter/Esc work; the list closes on Esc, on a pick and on leaving the box.
- [x] Comment 2: the **Same series as** box speaks in series: each suggestion shows the series name (the test's
      `source`, else its school — the part of the Test name between occasion and year) with grade · occasion · year in
      muted text; suggestions with the same series name, grade, occasion, term and year are shown once (the most recent
      test stands for them); after a pick it reads "Same series as: Đề dự đoán tuyển sinh vào 10", not the full Test
      name. What is copied is unchanged (22.3.3: filled series fields, never grade or test number). A test with neither
      source nor school shows its Test name.
- [x] The "Copy details from…" box in the test details, which uses the same search, also shows suggestions on focus.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.4.3.1 | Focusing or clicking the Existing test, Same series as and Copy details boxes lists up to 8 recent tests without typing (one `GET /tests` call); typing filters; keyboard works; the list closes on Esc, pick and blur. | `APP_TEST` + `E2E` |
| R22.4.3.2 | Same series as: suggestions show the series name with grade · occasion · year; duplicates of one series are shown once; the picked chip shows only the series name; the save body still sends the picked test's id (`series_from_test_id`), so what is copied is unchanged. | `APP_TEST` |
| R22.4.3.3 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-19, see 22.4.1. **Write scope** (22.4.2..4bd6dfe): UI, `app/e2e/`, tests, ticks: in §6 row 22.4.3. Three earlier tests changed only to click the option instead of an inner button (the option is now the clickable element); not weakened.
- **R22.4.3.1** ✅ `step22_4_3.test.tsx` (focus or click lists 8 recent tests with one `GET /tests` and no `q`; typing filters; ↓/↑/Enter/Esc; closes on pick, Esc, blur; the copy-details exclusion) and E2E `yz-students-series.spec.ts:123`.
- **R22.4.3.2** ✅ same file: series name with grade · occasion · year, one row per series, the chip reads "Same series as: <series>", the save sends `series_from_test_id`; screenshot `yz-series-picker-*.png`.
- **R22.4.3.3** ✅.

### Step 22.4.4 — Option letters and points out of 10
**Depends on:** 22.4.3 · **Comments:** 7, 14 · decision D3 (step22.4-plan §5) · **PRD:** D13 v8.0 · **data-model:**
v1.19 · **llm-design:** v4.35

PRD D13 v8.0 supersedes the points parts of R8.1.2 (0.25 + `points_assumed`) and R19.7 (a points editor); their
tests are rewritten to the equal rule (no item; points out of 10).

**Checklist**
- [x] Comment 7: option labels such as "A.", "B)", " c " are stored as the bare capital letter, at the extraction merge
      and when the test text is read back; `validate_mcq` compares the same cleaned letters; a cloze passage's options
      with full text pass.
- [x] D3: one function gives every graded question 10 ÷ (graded questions in the test) and each graded section the sum
      of its questions (`points_source="equal"`); it runs on every content save (merge, text save, review fixes, merge
      of tests) so `points_possible` and the grade's `score_possible` are always equal and 10 (0 with no graded
      question); a section with no questions adds nothing.
- [x] `points_assumed` items are no longer created; the test text writes each heading's computed points and ignores a
      typed value; Format help and the heading line help say points are computed (10 ÷ questions).
- [x] At first start (once, recorded so it does not repeat): every stored test is cleaned (option letters) and gets
      equal points; open `points_assumed` items and `validator_failed` items that no longer fail are closed; every
      graded attempt is re-scored from its stored verdicts with no model call (earned = correct questions × the new
      points; unsure stays unsure).
- [x] The score reads `x/10` everywhere it is shown (thread, report, Word file).

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.4.4.1 | A merged page with labels "A.", "B)", "c" stores "A", "B", "C" and passes `validate_mcq`; the same through a text save; a test of the case in comment 7 (cloze options with a dot) gives no failure. | `TEST` |
| R22.4.4.2 | For contents with 40, 50 and 13 graded questions plus a writing section and an empty section, every graded question is worth 10/N, sections sum their questions, `points_possible` = 10 and equals the grade's `score_possible`; this holds after a merge, a text save (typed heading points ignored), a review fix and a merge of tests. | `TEST` |
| R22.4.4.3 | The first-start pass on a copy of a database shaped like the teacher's case (sections with printed 2.5 / 1.5 / 0.5 points, assumed sections, empty sections; one graded attempt) leaves 10 points possible, a score of correct × 0.25 out of 10, no open `points_assumed`, no stale `mcq_options` failure, and makes no model call; a second start changes nothing. | `TEST` |
| R22.4.4.4 | The test page, thread, report and Word file show the score as `x/10`; Format help explains computed points. | `APP_TEST` + `E2E` |
| R22.4.4.5 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-19, see 22.4.1. **Write scope** (22.4.3..5747af9): `domain/{points,renumber,review,test_text,validators}.py`, `models.py` (`points_source`), `store/db.py`, migration 0009, `repos/points.py`, `routes/tests.py`, generated files, UI, tests: in §6 row 22.4.4 (v1.1.115.1). Existing tests were rewritten to the equal rule, as v2.35.1 says.
- **R22.4.4.1** ✅ `test_equal_points.py` ("A.", "B)", "c" stored bare and `validate_mcq` clean, also through the text read-back). Broken on purpose (`clean_label` only strips) → 7 tests fail; restored.
- **R22.4.4.2** ✅ `test_r22_4_4_2_equal_points[40/50/13]`, `..._save_paths_give_ten` (save_content and a text save with typed heading points ignored), review fixes (`test_review.py:382,503`), merge (`test_renumber.py`). Minor: no test asserts the points after a *merge of tests*; it holds by construction (`domain/merge.py` does not rewrite the survivor's content).
- **R22.4.4.3** ✅ `test_r22_4_4_3_first_start_pass` (2.5/1.5/0.5, assumed and empty sections; 7.5/10 = 30 × 0.25; `points_assumed` obsolete, `mcq_options` fixed; `httpx` send patched to fail; a second start changes nothing, snapshot equal).
- **R22.4.4.4** ✅ `step22_4_4.test.tsx` (card, report, test page x/10; Format help) and E2E R19.7/R22.4.4.4, s5 "8.33/10".
- **R22.4.4.5** ✅.

### Step 22.4.5 — Verifying keys and re-grading
**Depends on:** 22.4.4 · **Comments:** 11, 12 · decision D4 (step22.4-plan §5) · **PRD:** v8.1 · **data-model:**
`regrade_pending` (v1.20) · **llm-design:** `POST /tests/{id}/regrade` (v4.36)

**Checklist**
- [x] A migration creates `regrade_pending`. `PUT /tests/{id}/keys/{qid}` and the key review fixes that queued
      `key_verified` runs (`domain/review.py` `_grade_test(..., "key_verified")`) add the test to `regrade_pending`
      instead (only when it has graded attempts); other run reasons (merge, answer fixes) are unchanged.
- [x] `POST /tests/{id}/regrade` and `regrade_pending` on the test the app reads; deleting the test removes the row.
- [x] Comment 12, D4: while keys changed, the thread's top bar reads "Keys changed" with a **Re-grade** button; during a
      run it shows **Re-grade** (disabled) and **Stop**. Leaving the Key tab (to another workspace tab or another thread)
      with keys changed calls the route once; pressing Re-grade calls it. Verifying several keys in a row starts no run.
- [x] Comment 11: on the Key tab the top bar (pending or running) is one compact line, so the key photos keep their
      size; elsewhere it is unchanged.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.4.5.1 | Verifying 3 keys of a test with 2 graded attempts queues no run and leaves one `regrade_pending` row; the route then queues 2 runs and clears it; a second call queues none; a test with no graded attempt gets no row; a key review fix behaves the same; R12.1 holds. | `TEST` |
| R22.4.5.2 | With keys changed, the bar shows "Keys changed" and Re-grade; leaving the Key tab, or switching thread, calls `POST /regrade` exactly once; staying and verifying more calls nothing; Re-grade calls it; Stop still stops a run. | `APP_TEST` |
| R22.4.5.3 | On the Key tab the bar's height is one line (measured in a headless screenshot at 1280×720 against the old bar); the key photo area is taller than before. | `APP_TEST` + screenshot |
| R22.4.5.4 | S1–S7 hold; headless `E2E` verifies two keys, sees no run, leaves the Key tab, sees one re-grade and the new score. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-19, see 22.4.1. **Write scope** (22.4.4..53668a8): migration 0010, `repos/regrade.py`, `domain/review.py`, routes `tests.py`/`threads.py`, generated files, UI, tests: in §6 row 22.4.5.
- **R22.4.5.1** ✅ `test_routes_b.py:487,585`, `test_review.py:657`, `test_routes_c.py:132`. Broken on purpose (no `regrade.mark` in the key route and the review) → 7 tests fail; restored. Minor: the route test makes three key changes on two keys (q-1 edit, q-2 verify, q-2 edit), not three distinct keys.
- **R22.4.5.2** ✅ `keyRegrade.test.tsx` (several changes call nothing; leaving the Key tab or switching thread calls once; Re-grade calls; during a run Re-grade is disabled and Stop works); E2E s5 R22.4.5.4 counts exactly one `POST /regrade`.
- **R22.4.5.3** ✅ E2E: at 1280×720 the compact bar is ≤ 40 px and the photo area loses at most the bar's height; `keyRegrade.test` shows the full card off the Key tab; screenshots `r22.4.5-key-bar-*.png` show "Keys changed · Re-grade" on one line. Minor: the measurement is an absolute bound, not a side-by-side against the old bar.
- **R22.4.5.4** ✅ E2E: two keys verified, no run, leaving the Key tab gives one re-grade of the 2 graded attempts and the score 8.33/10.

### Step 22.4.6 — Report wording and order
**Depends on:** 22.4.5 · **Comment:** 13 · decision D5 (step22.4-plan §5) · **PRD:** v8.2 · **llm-design:** v4.37

**Checklist**
- [x] The sidecar reads the skill names from the taxonomy files (`prompts/taxonomy/*.txt`, "CODE | Name | …") and the
      report route gives each weak point its `skill_name` (the code stays for internal use).
- [x] The report on screen and the Word file show the name, never the code; any taxonomy code inside AI-written report
      text (summary, notes, teacher questions, explanations) is replaced by its name when shown; an unknown code shows
      as "Other skill".
- [x] Explanations, and every per-question list in the report, are ordered by the question's printed number (then by
      the wrong answer), on screen and in the Word file.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.4.6.1 | Every code in the taxonomy files maps to a name; the report route returns `skill_name` for each weak point; R12.1 holds. | `TEST` |
| R22.4.6.2 | A report with weak points VOC-TOPIC and a grammar code, and AI text containing "VOC-TOPIC", shows names only: no taxonomy code appears in the rendered report or in the Word file's text. | `TEST` + `APP_TEST` |
| R22.4.6.3 | Explanations written in the order 28, 17, 27 are shown and exported as 17, 27, 28. | `TEST` + `APP_TEST` |
| R22.4.6.4 | S1–S7 hold; headless `E2E` passes and its report screenshot shows no code. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-19, see 22.4.1. **Write scope** (22.4.5..771ece7): `domain/skills.py`, `docx_export.py`, `routes/attempts.py`, generated files, UI, tests: in §6 row 22.4.6.
- **R22.4.6.1** ✅ `test_step22_4_6.py` (every taxonomy code has a name; `skill_name` per weak point, "Other skill" for an unknown code).
- **R22.4.6.2** ✅ same file (no code in the route's AI text or the Word file) and `step22_4_6.test.tsx`.
- **R22.4.6.3** ✅ same files (28, 17, 27 → 17, 27, 28 on screen and in the Word file). Broken on purpose (explanations sorted by id, codes not replaced) → the route test fails; restored.
- **R22.4.6.4** ✅ E2E s5 checks the card text against the code shapes; `r22.4.6-report-*.png` shows names ("Present Simple — Affirmative Forms") and explanations 4, 15, 23, 34.

### Step 22.4.7 — A worked example in the page prompts
**Depends on:** 22.4.6 · **Comments:** 5, 8 · decision D6 (step22.4-plan §5) · **llm-design:** v4.38 · the teacher's GPU
check (step22.4-plan §7) decides whether it ships in 0.5.0

**Checklist**
- [x] One worked example, shared by `transcribe_page` and `structure_text_page` (one source, put into both prompts): a
      **made-up** page (no words from the teacher's papers or the fixtures) of about 30 lines and its correct output in
      the exact output schema, showing:
      - a heading with printed points and a Vietnamese instruction line under it ("Thí sinh …") that stays in the
        section's instructions;
      - a dictionary entry (headword, word class, a sense, an example) as the stimulus, then two numbered gap
        sentences after it, each with its own sentence as the stem;
      - a new Roman-numeral heading ("VII. Rewrite …") that starts a new section, even with no blank line before it;
      - rewrite questions: one with a cue word in brackets, one with "=>" and opening words, one with opening words
        and no arrow, each with its own sentence as the stem and `answer_start` filled.
- [x] Three rules added to both prompts, in plain words: a numbered sentence's own sentence is its stem and is never
      put into a stimulus (only passage gaps are); a Roman-numeral heading always starts a new section; instruction
      lines, also Vietnamese ones ("Thí sinh …", "Chú ý: …", "Từ câu … đến câu …"), belong to the section's
      instructions and are never a section.
- [x] The example is marked as an example of form only ("do not copy its words"), and placed so the page's own text
      or photo comes after it.
- [x] Budget: the longest system prompt plus the longest text page (`MAX_TEXT_PAGE_CHARS`) plus `num_predict` still
      fits `num_ctx` (16,384), counted with the client's own size estimate.
- [x] No change to the model tags, options or the cassette match key; replay passes unchanged.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.4.7.1 | The example output validates against the page output schema (the pydantic model used for `format`); both prompts render with it; its words do not occur in `fixtures/` text or the cassettes. | `TEST` |
| R22.4.7.2 | The budget test passes for both tasks with the worst-case page; the example is under 1,500 tokens by the client's estimate. | `TEST` |
| R22.4.7.3 | S1–S7 hold; replay and headless `E2E` pass with the existing cassettes. | `TEST` + `APP_TEST` + `E2E` |
| R22.4.7.4 | 👤 The teacher's GPU check (step22.4-plan §7) on the typed PDF (national test 4) and the photos (Test G): questions 35–40 have their sentences as stems, the rewrite part is its own section, opening words are filled, no instruction line became a section, no page loops to the token cap. The teacher decides whether it ships in 0.5.0. | 👤 GPU run |
| R22.4.7.5 | After the GPU check the teacher chose typed files only (step22.4-plan §4): `transcribe_page.md` is back to its 0.4.0 text (no example, no three rules); `structure_text_page.md` keeps them; the tests say so; S1–S7 and headless `E2E` hold. | `TEST` + `E2E` |

**Verifier notes:** 2026-10-19, see 22.4.1. **Write scope** (22.4.6..df35e9a): the two base prompts, `prompts/examples/page_example.md`, `prompts/render.py`, one test file: in §6 row 22.4.7; no cassette changed. The PyInstaller spec needs no change (`collect_data_files("erh")` takes the new folder).
- **R22.4.7.1** ✅ `test_page_example.py`: the output validates as `TranscribeOut` (the `format` schema of both tasks); both prompts render with it in the system part, before the page; its words and lines occur in neither the cassettes nor `fixtures/` (fixtures present here; the test ran, not skipped). Minor: the example page is 19 lines, not "about 30"; every checklist case is in it.
- **R22.4.7.2** ✅ same file: under 1,500 tokens; prompt ceiling + `num_predict` 8,192 ≤ `num_ctx` 16,384 for both tasks with a `MAX_TEXT_PAGE_CHARS` page.
- **R22.4.7.3** ✅ (standing checks; the replay tests in S1 use the existing cassettes).
- **R22.4.7.4** not run (the teacher's GPU check) → **🔄 pending R22.4.7.4.**

**Verifier notes (R22.4.7.5):** 2026-10-19, fresh verifier for 22.4.7 (R22.4.7.5) and 22.4.8, standing checks at 4718a5a (see 22.4.8). **R22.4.7.5** ✅ `git diff c5caa1d HEAD -- …/base/transcribe_page.md` is empty, and its sha256 equals the one pinned in `test_page_example.py` (`fb4eaaaf…`, recomputed from `git show c5caa1d:`); `structure_text_page.md` keeps the `<!-- example: page_example -->` line and the three rules; the tests assert both (photo prompt: hash, no example, no rules). Write scope (7a53991): the photo prompt and `test_page_example.py`, in §6 row 22.4.7. Minor: the `prompts/render.py` docstring still says the example is shared by both tasks. **R22.4.7.4** is the teacher's GPU run (results in step22.4-plan §7, decision typed files only); not marked → **🔄 pending the teacher's sign-off of R22.4.7.4.**

### Step 22.4.8 — The teacher's answers before the installer
**Depends on:** 22.4.7 · step22.4-plan §4 (the §6 answers of 2026-10-19) · **PRD:** v8.3 · **data-model:** v1.20.1

**Checklist**
- [x] Answer 1 (22.4.1): opening Format help scrolls so the **button stays in view** at the top of the panel and the
      help starts right under it (smooth; instant under reduced motion); focus stays on the button.
- [x] Answer 3 (22.4.3): the "Existing test" and "Same series as" labels share one width, so both boxes start at the
      same x position.
- [x] Answer 5 (22.4.4): the test text and the Word file write a heading's points as "[2.5 points, 0.25 each]" (2
      decimals each, trailing zeros dropped); a writing section keeps "not graded"; reading back still ignores typed
      points and still reads the old forms; Format help shows the new form.
- [x] Answer 6 (22.4.5): leaving a thread whose keys changed starts the re-grade from any tab (once), as leaving the Key
      tab does.
- [x] Answer 7 (22.4.5): the top bar (Keys changed and the running card) is the one-line compact form on every workspace
      tab; the full card stays only where the workspace is not shown (if anywhere).
- [x] Teacher (2026-10-19, after the build): the compact "Keys changed" shows its hint ("The scores update when you
      re-grade, leave the Key tab or leave this thread") as a tooltip on hover and keyboard focus. Writing sections
      keep "[0 points, not graded]" (orchestrator).

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.4.8.1 | After opening Format help the button's top is inside the panel's visible area and the first help row is visible (1280×720); focus on the button; reduced motion → `auto`. | `APP_TEST` + `E2E` |
| R22.4.8.2 | The two boxes' left edges are equal (measured in a headless run). | `APP_TEST` + `E2E` |
| R22.4.8.3 | For 40 and 13 graded questions the headings read "[2.5 points, 0.25 each]" and "[3.85 points, 0.77 each]"; read-back ignores them and still accepts the old forms; the Word file shows the same. | `TEST` |
| R22.4.8.4 | Keys changed, then switching thread from the Test, Student answers or Report tab calls `POST /regrade` exactly once; no change → no call. | `APP_TEST` |
| R22.4.8.5 | The top bar is one line on each of the four workspace tabs (pending and running). | `APP_TEST` + screenshot |
| R22.4.8.6 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-19, fresh verifier, at 4718a5a, one after another, clean tree before and after: S1 `TEST` 1569 passed, 14 deselected; S2 ruff clean, 254 files formatted, mypy `src` no issues in 102 files; S3/S6 no diff; S4 only `llm/defaults.py` (plus its gitignored `.pyc`); S5 exit 0; S7 `vitest run` 47 files, 358 tests passed, eslint and `tsc --noEmit` clean, `gen:types` no diff; headless `E2E` 33 passed. Earlier one-off flakes (E2E R16.2, R19.3, vitest step22_2_focus Escape) did not recur. No `👤 sign-off:` commit, no teacher field, no fixture or cassette changed in cade094..4718a5a. **Write scope** (implementer commits f09424c, 717e88b, b7529f9, 1b90a6c, 4d40226, d25bff7, 4718a5a): `domain/test_text.py`, sidecar tests, `app/src/{components,features}/`, `app/e2e/`, `docs/initial-plan/plan.md` (six ticks only), all in §6 row 22.4.8; the doc commits 9fd490f and f633e5a are the orchestrator's. Deliberate breakages, each restored: no ", each" in `_points_tag` → 3 tests fail; no thread-leave re-grade in `useKeyRegrade` → 4 fail; `compact` only on the Key tab → the R22.4.8.5 test fails.
- **R22.4.8.1** ✅ `step22_4_1.test.tsx`: the scroll is on the button, `block: "start"`, smooth, `auto` under reduced motion; focus stays. E2E `y-test-page`: the button is inside the scroll panel's visible box with `scrollTop` > 0, the first help row in the viewport (1280×720). Minor: in `s12-format-help.png` and the reduced-motion shot the button sits mid-panel, not at its top (the measured requirement holds).
- **R22.4.8.2** ✅ `step22_4_3.test.tsx` (both labels carry `STACKED_LABEL`) and E2E `yz-students-series` (left edges differ < 0.5 px); `s22-4-8-aligned-boxes-{light,dark}.png` show them aligned.
- **R22.4.8.3** ✅ `test_equal_points.py`: 40 → "[2.5 points, 0.25 each]", 13 → "[3.85 points, 0.77 each]"/"[3.08 points, 0.77 each]", writing "[0 points, not graded]"; round trip equal, typed points ignored, four old forms read with no errors; the Word file's Heading 2 texts are the same. Format help shows the new form.
- **R22.4.8.4** ✅ `keyRegrade.test.tsx`: switching thread off the Key tab with keys changed calls `/tests/T-0001/regrade` once (no second call on a later switch); staying calls nothing; nothing changed → nothing. Minor: the hook does not know the tab, so the three "test/answers/report" cases are the same case.
- **R22.4.8.5** ✅ `step22_3_2.test.tsx`: on Test, Student answers, Report and Key the bar has `data-compact`, Keys changed and the compact run card; E2E `s5-grade` measures the Test tab bar at 30 px. Tooltip line ✅: unit test plus E2E hover/focus/Escape and the accessible description; `s22-4-8-compact-bar-test-{light,dark}.png` show it readable, the label underlined dotted, no overlap of the buttons.
- **R22.4.8.6** ✅ (the standing checks above).

### Step 22.4.9 — Installer 0.5.0
**Depends on:** 22.4.8 and the round's verifier · R22.4.7.4 accepted by the teacher (31f1a2d) · R21.1, R21.2 and
R21.5 again on the final commit, as in 22.3.8.

**Checklist**
- [x] Version 0.5.0 in the places 22.3.8 changed (incl. `sidecar/src/erh/__init__.py`, the tests that pin it,
      `sidecar/schema/openapi.json`); `app/src-tauri/gen/schemas/` regenerated if the build changes it.
- [x] `TAURI_BUILD`; sizes and the Defender scan in a new `docs/release-notes.md` section 0.5.0: what changed since
      0.4.0 in plain words (steps 22.4.1–22.4.8: Settings tabs, the Schools list, the new-thread pickers, options and
      points, re-grade after key changes, the report's skill names and order, the worked example, the teacher's
      answers); the score is now out of 10 (10 ÷ the graded questions) and existing attempts are re-scored once at
      first start, with no model call; the worked example is used for typed files only, photos keep the 0.4.0 prompt;
      the known limits from step22.4-plan §7 (typed tests: some one-question sections and a stray section; photos
      unchanged from 0.4.0); the new migrations 0008–0010 run at first start; how to install over 0.4.0.
- [x] No `E2E_SHELL` by the builder (the user starts it).

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.4.9.1 | Every version string is 0.5.0 and the lock files agree; `erh --version` prints 0.5.0; S1–S7 hold; headless `E2E` passes; `cargo test --lib` passes with no diff in `app/src-tauri/gen/`. | `TEST` + `APP_TEST` + `E2E` |
| R22.4.9.2 | R21.1: `TAURI_BUILD` exits 0 and outputs `Exam Revision Helper_0.5.0_x64-setup.exe`; `target/release/sidecar/erh.exe --version` prints 0.5.0 with one `erh-*.dist-info`. | Run it |
| R22.4.9.3 | R21.2: `E2E_SHELL --release`, Settings shows 0.5.0; started by the user. | `E2E_SHELL --release` |
| R22.4.9.4 | R21.5: release notes 0.5.0 with sizes, the Defender scan of installer, sidecar folder and shell exe, the changes, the points note, the worked-example note, the known limits, the migrations and the update steps; earlier sections unchanged. | Read the file |

**Verifier notes:** 2026-10-20, fresh verifier, on `step/22.4.9-installer` at 0266c79 (implementation 8b07c24, d6a60ae, 0266c79; 11e23c6 is the orchestrator's). **Write scope:** every path in 8b07c24..0266c79 is in §6 row 22.4.9 (eleven version files and the two tests that pin it; `docs/release-notes.md` only adds lines, 125 added, 0 removed; `docs/initial-plan/plan.md` only the three checklist ticks); no fixture, cassette or teacher field changed, no `👤 sign-off:` commit. **R22.4.9.1** passes: 0.5.0 in `app/package.json`, `package-lock.json` (both entries), `tauri.conf.json`, `Cargo.toml`, `Cargo.lock` (`exam-revision-helper`), `pyproject.toml`, `uv.lock` (`erh`), `erh/__init__.py`, `schema/openapi.json`, firstRun.test and settings.test; the 0.4.0 strings left in app/ and sidecar/ are third-party packages (`type-check`, `winapi-*-gnu`, version ranges in package-lock) or the "0.4.0 text" of the photo prompt in `test_page_example.py`; `uv run erh --version` 0.5.0. Run one after another: S1 `TEST` 1569 passed, 14 deselected (the timing flake in `test_key_edit_deletes_explanations_and_defers_the_regrade` did not recur); S2 ruff clean, 254 files formatted, mypy `src` no issues in 102 files; S3 schema export no diff; S4 only `llm/defaults.py`; S5 exit 0; S6 openapi no diff; S7 `vitest run` 47 files, 358 tests passed, eslint and `tsc --noEmit` clean, `gen:types` no diff. Headless `E2E` 33 passed; `cargo test --lib` 17 passed, no diff in `app/src-tauri/gen/`. The tree was clean after each run. **R22.4.9.2** (the existing build, not rebuilt): `bundle/nsis/Exam Revision Helper_0.5.0_x64-setup.exe` 45,178,966 bytes and `exam-revision-helper.exe` 10,822,144 bytes, both written 2026-10-20 00:21:13, after the last code commit 8b07c24 (00:03:07); `target/release/sidecar/erh.exe --version` 0.5.0; one dist-info (`erh-0.5.0`); 169 files (as `sidecar/dist/erh/`), 107,666,720 bytes; all equal the release notes. A Defender rescan of the three items (signature 1.461.106.0) found no threats. **R22.4.9.4** passes: the 0.5.0 section has the build, the three sizes (the differences from 0.4.0 add up: +25,711, +28,559 and four files, +3,072 bytes), the Defender scan of installer, sidecar folder and shell exe, the changes of 22.4.1–22.4.8 (as their plan sections and step22.4-plan §3/§5 record them; the quoted strings match the code), the points note (out of 10, 10 ÷ graded questions, typed heading points ignored, a one-time re-score at first start from the saved marks with no model call, as `store/repos/points.py` does), the worked-example note (typed files only, photos keep the 0.4.0 prompt), the known limits as step22.4-plan §7 records them (one-question sections 21, 22, 29–34 and the stray section "A" on typed tests; photos as 0.4.0), migrations 0008–0010 (`0008_schools`, `0009_equal_points`, `0010_regrade_pending`, as in the migrations folder), and the update steps including leaving the uninstaller's "Delete all app data" box unticked; earlier sections unchanged. No findings. R22.4.9.3 not run (`E2E_SHELL --release`, started by the user). → **🔄 pending R22.4.9.3 `E2E_SHELL --release` (started by the user).**

**R22.4.9.3 E2E_SHELL** run 2026-10-20 by the user (`cd app && npm run e2e:shell -- --release`) on the 0.5.0 release build: 20 PASS, "E2E_SHELL: all passed"; Settings shows 0.5.0 = `erh --version` (source and frozen); R14.5 nothing new in %APPDATA%/%LOCALAPPDATA%; R15.2 real drop; R20.7 moved-folder checks pass. ✅

## Step 22.5 — The teacher's fifth review and the quality plans

The teacher used installer 0.5.0 and wrote 10 comments, and chose to build both quality plans
(`docs/initial-plan/plan-grading-quality.md`, `docs/initial-plan/plan-extraction-quality.md`) in the same round, before step 22 (2026-10-23). The
comments verbatim, the orchestrator's findings, the 8 sub-steps, the coverage table, decisions D1–D13 and GPU checks
G1–G4 are in `docs/initial-plan/phases-testing/step22.5-plan.md`. It runs like step 22.4: sub-steps on stacked branches, each
sub-step's decisions asked before it is built, parked questions asked and built before the installer. A fresh verifier
runs after 22.5.2, 22.5.3, 22.5.5, 22.5.6 and 22.5.7 (each before its GPU check; teacher, 2026-10-23); then the
installer and the user's `E2E_SHELL --release`. Each sub-step gets its checklist and
requirements when it starts.

### Step 22.5.1 — Moving around and lists
**Depends on:** 22.4.9 · **Comments:** 1 (Back and the two layouts), 6, 8, 9, 10 · decisions D1, D3, D4
(step22.5-plan §5)

**Checklist**
- [x] Comment 1, D1: a test opened from the Tests tab (not the open thread's test) has no Back button. Its header
      is laid out like a thread's own test: the tabs, then a title bar with the test's name. Clicking any thread in
      the sidebar, including the thread that is already active, closes it and shows that thread.
- [x] Comment 6, D3: the Tests list is sorted A–Z by name by default (Vietnamese-aware, numbers by value: `Intl.Collator("vi", {numeric: true})`, so Grade 9 comes before Grade 10). A
      square sort button, as tall as the search box, sits at the box's right end and takes its room from the box.
      It opens a menu: A–Z, Z–A, Newest added, By grade (grade ascending, A–Z inside a grade; no grade last). The
      menu marks the chosen order (`menuitemradio`, `aria-checked`). The order also applies to search results, except that a test whose id equals the search is always the top row. The
      choice is kept for the session. `GET /tests` items carry `created_at` for "Newest added".
- [x] Comment 8: search also finds a test by its id: "T-0008", "t-0008" and "T0008" find T-0008, quietly (no new
      control or text). The "looks like" notice names the other test with its id, e.g. "This test looks like
      Grade 8 - … - Test 2 (T-0008), which is already in the bank."
- [x] Comment 9: starting to edit a key or a student answer, by double-click or the Edit button, selects the old
      value in the input, so typing replaces it.
- [x] Comment 10, D4: in the sidebar thread rows and the Tests rows, the unsure count keeps a fixed-width slot on
      every row (empty when there is none), so every name is cut at the same place. The full name stays on hover.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.5.1.1 | With thread A active, opening test B from the Tests tab shows no "Back" or "Back to thread" button anywhere in the workspace header; the header has the tabs and B's name in a title bar; clicking thread A in the sidebar shows thread A (its conversation, or its own test view), and clicking thread C shows C. "Back to thread" occurs in `app/src` only in tests asserting its absence. | `APP_TEST` |
| R22.5.1.2 | With no choice made, the Tests list is in `Intl.Collator("vi", {numeric: true})` order by name (a test fixture with "Đề …", "Grade 10", "Grade 9", "ảnh" proves the Vietnamese collation and Grade 9 before Grade 10). Each menu choice orders the list as stated (Z–A reverse; Newest added by `created_at` descending; By grade ascending, A–Z inside, no grade last), also for search results, where a test whose id equals the search is the top row under every order; the choice survives switching tabs within the session. | `APP_TEST` |
| R22.5.1.3 | The sort button is square, its height equals the search box's height (measured in a headless screenshot or computed style), it has an accessible name ("Sort tests"), opens a `role="menu"` with four `menuitemradio` items, the current one `aria-checked="true"`, keyboard operable (Enter/Space opens, arrows move, Esc closes and returns focus); contrast meets WCAG 2.1 AA. | `APP_TEST` + screenshot |
| R22.5.1.4 | `GET /tests?q=T-0008`, `q=t-0008` and `q=T0008` return T-0008 first; a name query returns what it returned before; `GET /tests` items carry `created_at`. | `TEST` |
| R22.5.1.5 | The "looks like" notice shows the other test's name and its id. | `APP_TEST` |
| R22.5.1.6 | Double-click and Edit on a Key row and on a Student answers row each leave the input focused with its whole value selected (`selectionStart` 0, `selectionEnd` = length); typing one character replaces the value. | `APP_TEST` |
| R22.5.1.7 | In the sidebar and the Tests list, a row with an unsure count and a row without one give their name the same width (computed width or class proof), and the name's `title` holds the full name. | `APP_TEST` + screenshot |
| R22.5.1.8 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** fresh verifier, 2026-10-23, at 7c79ce4 (verified with 22.5.2). All pass. R22.5.1.1–R22.5.1.3, R22.5.1.5–R22.5.1.7: `step22_5_1.test.tsx` (12 tests) pass; the sort button's size (square, the search box's height and top) and contrast, and the equal name widths, are measured in headless `s12-moving-around.spec.ts` (screenshots `app/test-results/s22.5.1-*.png`, light and dark). R22.5.1.4: `test_step22_5_1.py` (3) pass. R22.5.1.8: S1–S7 below. Changed files are inside the §6 row. Minor, not blocking: the Tab key in the sort menu closes it by focus-out rather than moving inside it (acceptable for a menu).

---

### Step 22.5.2 — Settings, series, test text, Extract again
**Depends on:** 22.5.1 · **Comments:** 1 (headings, "A.."), 2, 3, 5, 7 · decisions D2, D5, D7, D8 (step22.5-plan §5)

Built in two parts: **22.5.2a sidecar** (a general builder), then **22.5.2b UI** (the UI builder), on the same branch.

**Checklist (a, sidecar)**
- [x] Comment 2, D5: a `series` table like `schools` (migration `0011_series`), seeded once from the distinct trimmed,
      non-empty `source` values on tests, oldest first, case variants skipped; routes `GET/POST/PATCH/DELETE /series`
      like `/schools` (delete refused while a test uses the name). Renaming a series renames it on the tests that use
      it, as a school rename does.
- [x] D5: the extraction input takes a series name (`series_name`, replacing `series_from_test_id` for the new-thread
      screen): at save, the test's `source` is that name, and grade, occasion, term and year are copied from the newest
      test (by `created_at`) whose `source` equals it (case-insensitive), as teacher writes; school is not copied. With
      no such test only `source` is set. "Copy details from…" is unchanged.
- [x] Comment 5, D7: section headings carry no points: `test_text.render` and the Word export write no "[x points, y
      each]"; a writing section keeps "[not graded]". The parser still reads old tags and ignores their points.
      `GET /tests/{id}` carries the per-question value (`points_each`, 10 ÷ graded questions) for the line under the
      title.
- [x] D2: an untitled section (empty title, or only a numeral such as "I." / "1.") gets its title from its section
      skill, in capitals ("PRONUNCIATION", "WORD FORM"), at extraction and once for stored tests at first start
      (as the points pass of 22.4.4); a section whose skill is `mixed` or missing stays untitled; a title the teacher
      typed is never changed.
- [x] Comment 1: find why Test G's options render as "A.." with the option word on the next line (from the stored
      shape of the options, reproduced in a synthetic test; no app data is read); fix it in the merge and in render,
      and clean stored tests once at first start if the stored shape is the cause.
- [x] Comment 7, D8: `POST /threads/{id}/extract-again` takes `mode`: `replace` (default when no other thread uses the
      test) or `copy`. With `replace` the new reading is saved into the same test id: questions are matched with
      `similarity.align_questions`; a teacher-typed or verified key stays on a question whose printed number and text
      match, other questions are keyed again from the key photo or by the AI; tags are re-mapped the same way;
      `test_pages` are replaced; every thread on the test follows it: student answers stay on matched questions,
      graded attempts go to `regrade_pending`; Review items on removed questions are closed. With `copy` this thread
      gets a new test as today. Either way `compare_bank` leaves out the test the re-extraction came from, so no
      "looks like" item points at it. `GET /threads/{id}` (or the test read) says how many other threads use the test.
- [x] Docs: data-model (the `series` table, `points_each`, the title fill, Extract again), llm-design (the `/series`
      routes, the extract-again body and the input field), PRD (§10 points line, D13 headings, the Extract again
      behaviour), each bumped with a changelog row and plan.md's "Based on" line.

**Checklist (b, UI)**
- [x] Comment 3: Settings tabs are General · Models · Test attributes. Test attributes shows a menu of Occasions ·
      Schools · Series; each opens its list in the same place, with a Back control that returns to the menu (the
      lists are reached in two clicks).
- [x] Comment 2, D5: a Series list built like `SchoolList.tsx`; the Series field in the test details picks from it
      like School; the new-thread "Same series as" lists series names only (focus shows them at once, as 22.4.3) and
      sends `series_name`.
- [x] Comment 5, D7: the line under the test title reads "10 points · 0.25 each" (the value from `points_each`, at most
      2 decimals, trailing zeros dropped: 0.25, 0.2, 0.22); the print view and Format help match; no heading shows
      points.
- [x] Comment 7, D8: the Extract again confirm dialog says the test is updated in place; when other threads use the
      test it asks "Update the test for every thread" or "Make a separate copy for this thread", naming how many other
      threads there are.

**Checklist (c, after the verifier; teacher, 2026-10-23)**
- [x] D8 addition (teacher): on `replace`, an AI key on a question whose printed number and text match exactly is kept,
      with its unsure state; only changed or new questions are keyed again. data-model §5.8 says so (patch bump,
      changelog row, plan.md's "Based on").
- [x] Verifier finding 1: the UI sends no `mode` when it saw no other threads, so the sidecar decides at that moment and
      its 409 `CHOOSE_MODE` opens the choice; the UI sends `mode` only after the teacher chose.
- [x] Verifier finding 3: the Extract again dialog is short: one line on what is kept and what is replaced, placed
      with the "Update" choice it applies to; neither choice looks recommended.
- [x] Polish: the "Same series as" placeholder ends with "…"; curly quotes in the SeriesList help text; a
      `points_each` case in `sidecar/tests/unit/domain/title_line_cases.json`, used by both the app and the Word export.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.5.2.1 | Migration 0011 creates and seeds `series` from test `source` values (a synthetic DB with "Đề dự đoán…", "đề dự đoán…" and blanks gives one row); the `/series` routes behave as `/schools` (add, rename incl. the tests' `source`, reorder, delete refused while used). | `TEST` |
| R22.5.2.2 | An extraction with `series_name` saves `source` = the name and grade, occasion, term, year from the newest test of that series, as teacher writes; school untouched; with no such test only `source`. "Copy details from…" copies what it did before. | `TEST` |
| R22.5.2.3 | `render` and the Word export contain no "points" text on any heading; a writing section's heading has "[not graded]"; parsing a text with old "[2.5 points, 0.25 each]" tags gives the same test as without them; `points_each` is 10 ÷ graded questions. | `TEST` |
| R22.5.2.4 | Untitled sections with a specific skill get the capitalised skill title at extraction and in the first-start pass; `mixed`/missing skill and teacher-typed titles are unchanged; the pass runs once. | `TEST` |
| R22.5.2.5 | The "A.." case is reproduced in a synthetic test that fails before the fix and passes after; render gives "A. question" on one line. | `TEST` |
| R22.5.2.6 | Extract again `replace`: the test id is unchanged; a matched question keeps a teacher key, an unmatched one is re-keyed; other threads' answers stay on matched questions and graded attempts are `regrade_pending`; no `possible_duplicate` item points at the same test. `copy`: a new test for this thread only, no item pointing at the source. Replay tests with synthetic cassettes, no model. | `TEST` |
| R22.5.2.7 | Settings shows General · Models · Test attributes; Test attributes → Series → Back returns to the Test attributes menu; keyboard and screen-reader names work; WCAG 2.1 AA contrast. | `APP_TEST` + screenshot |
| R22.5.2.8 | The Series field and "Same series as" offer only names from the Series list; picking one in "Same series as" sends `series_name`. | `APP_TEST` |
| R22.5.2.9 | The line under the title reads "10 points · 0.25 each" for 40 graded questions and "10 points · 0.2 each" for 50; no heading in the editor, print view or Format help shows points. | `APP_TEST` |
| R22.5.2.10 | The Extract again dialog offers update / copy only when other threads use the test, and sends the chosen `mode`. | `APP_TEST` |
| R22.5.2.11 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |
| R22.5.2.12 | Extract again `replace` keeps an AI key (and its unsure state) on an exactly matched question and keys a changed one again; with no other threads seen, the UI's request has no `mode`, and a 409 `CHOOSE_MODE` reply opens the choice; the dialog has at most three short lines of text; the shared title-line cases include a `points_each` case that the app and the Word export both pass. | `TEST` + `APP_TEST` |

**Verifier notes:** fresh verifier, 2026-10-23, at 7c79ce4. All pass. S1 `TEST` 1604 passed, 14 deselected; S2 ruff, format, mypy clean; S3 and S6 no diff; S4 only `llm/defaults.py`; S5 exit 0; S7 vitest 389 passed (49 files), lint and typecheck clean, `gen:types` no diff; headless `E2E` 39 passed (screenshots `app/test-results/s22.5.2-*.png`). R22.5.2.5 checked against `main`: the same synthetic labels render "A..." with the word on the next line there and "A. go    B. goes" here. The JS and Python per-question values agree for 10 ÷ n, n = 1–300 (checked by script), so the missing `points_each` case in `title_line_cases.json` is a test gap only. Findings, none blocking: (1) the UI always sends `mode`, so the sidecar's 409 CHOOSE_MODE can never fire from the app: if another thread starts using the test after the thread was loaded, Extract again updates it for every thread without asking (`ThreadActions.tsx` `extractAgain`); (2) AI keys on exactly matched questions are dropped by `replace` and must be made again (a GPU grading call), as the checklist's wording allows; (3) the two-choice Extract again dialog is five paragraphs long; (4) a `#` at the start of a typed line now makes a heading (render escapes stored text, so only typed lines are affected; Format help says so).

Second pass (fresh verifier, 2026-10-23, at 53f15c5; checklist (c), R22.5.2.12, and all of 22.5.2 again). All pass. R22.5.2.12: `extract_again._move_keys` keeps every key on an exact pair; `test_r22_5_2_12_replace_keeps_ai_keys_on_exact_matches` (store: the AI key equal to before apart from its question id, `ai_uncertain` and 0.4 kept, its explanation and open `uncertain_key` item follow; the reworded question's key and item go), the graph test and the replay test all fail when the old teacher-only filter is patched back in at test time and pass without it; vitest: no `mode` in the body when no other threads were seen (`{}`), a 409 CHOOSE_MODE opens the choice and only then sends `mode`; the dialog has at most three `<p>` of at most 90 characters, the kept/replaced line is the Update button's accessible description and sits under it, both choices have the same classes; `title_line_cases.json` has `points_each` cases (40 → "0.25 each", 45 → "0.22 each") read by `test_title_line.py` (Word export `meta_line`) and `testTitle.test.ts`. R22.5.2.1–R22.5.2.11: their tests pass (re-read the ones touched since 7c79ce4). S1 `TEST` 1610 passed, 14 deselected; S2 ruff, format, mypy clean; S3 and S6 no diff; S4 only `llm/defaults.py`; S5 exit 0; S7 vitest 393 passed (49 files) in each of 3 runs (no flaky test seen), lint and typecheck clean, `gen:types` no diff; headless `E2E` 40 passed. Dialog text contrast (from tokens): muted 6.12 (light) / 7.03 (dark) on the panel, danger button text 7.9 / 8.35. Changed files are inside the §6 row. Minor, not blocking: (1) the kept/replaced line (87 characters) wraps to two lines in the dialog, so the body shows four visual lines; (2) "Your details" could read as the teacher's own details ("The test details" is plainer); (3) with a hint the one-action dialog stacks Extract again on the left and Keep this one below at the right, unlike the app's other one-row confirms; (4) rare: a kept AI key with an open `uncertain_key` item that the same run's key photo now replaces leaves that item open on the photo's key (accept would verify the photo's key); (5) PRD v8.5.1 is labelled a patch though it adds behaviour (the versioning rule calls new detail minor).

---

### Step 22.5.3 — Fewer question types 👤 GPU
**Depends on:** 22.5.2 · **Source:** `docs/initial-plan/plan-extraction-quality.md` "Fewer question types" · decision D9
(step22.5-plan §5: built as proposed, the teacher signs it off after G1)

**Checklist**
- [x] Data model: `Question.type` (11 values) is replaced by `answer_form` (`choice` · `word` · `sentence` · `writing`)
      and `context` (`single` · `paragraph`; `null` for `writing`). `context` is set by code from the group's `stimulus`
      (a stimulus → `paragraph`), never by the model. `verb_form` and the other old values go from every schema.
      True/False is a `choice` whose two options the code adds. `cue`, `answer_start` (now for `sentence`) and `options`
      stay.
- [x] Stored tests: a first-start pass (once, in one transaction) maps every stored question: mcq, true_false,
      matching → `choice`; gap_fill, word_form, verb_form → `word`; rewrite, combine, ordering, short_answer →
      `sentence`; writing → `writing`; and sets `context`. Each question keeps its old value in a read-only `old_type`
      field, used by nothing but a revert, so a revert loses nothing (D9). No student answer, key, verdict or grade
      report is changed by the pass; graded attempts are not marked for re-grade.
- [x] Grading (`scoring.py`): `choice` → exact match; `word` → exact match, a 1–2 letter difference is a spelling
      near-miss; `sentence` → exact match after normalising, else the AI judge (the judge rule rewrite uses today;
      combine's separate rule goes); `writing` → not graded. Former `short_answer` and `ordering` questions therefore go
      to the judge when not an exact match (the proposal's change in behaviour). The Appendix B.5 table is updated.
- [x] The page prompts (`transcribe_page`, `structure_text_page`) ask for `answer_form` by the printed layout, one line
      per form, no longer than the old type list; `answer_start` is asked for `sentence`. The LLM output schemas take
      `answer_form`, not `type`. Prompts stay short (CLAUDE.md).
- [x] Every other use of the type follows: answer boxes and `fits_type` (`boxes.py`), validators (the gap check applies
      to a `word` question with no cue and no options, the option check to `choice`), answer reading (`llm_schemas.py`: the reading value shape per form), the
      test text (`test_text.py`: `_infer_type` infers the form; the text format shows no type), the Word export and
      print view if they read the type, the app (generated types; any screen or test that reads `type`), the eval
      (fixtures keep their expected `type` and the loader maps it to a form with the table above, so `fixtures/` is not
      edited; the metric reports form accuracy and a confusion of forms), synthetic fixtures, cassettes and examples.
- [x] Docs: data-model (the two fields, `old_type`, the pass, B.5), llm-design (the page prompts and schemas), PRD
      (where it names question types; the short_answer/ordering judge change), each bumped with a changelog row and
      plan.md's "Based on" line; `docs/initial-plan/plan-extraction-quality.md` tracker row 22.5.3 says built, awaiting G1.

**Checklist (d, after G1; teacher, 2026-10-24)**
- [x] True/False options as T/F: a `choice` whose two options read True and False (any case, either order; also
      Đúng/Sai) gets the options `T. True`, `F. False`, at extraction and once for stored tests; stored keys and student
      answers on those questions are relabelled to match (the letter that meant True → T). Docs: data-model patch.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.5.3.1 | `QuestionType`, `verb_form` and the other old values occur in no schema (`sidecar/schema/`, `openapi.json`, `app/src/gen/`), prompt or LLM schema, except `old_type`; `Question` has `answer_form` and `context`; a group with a stimulus gives `paragraph` and one without gives `single`, whatever the model returns. | `TEST` |
| R22.5.3.2 | The first-start pass maps a synthetic DB holding all 11 old types by the table above, sets `context`, keeps `old_type`, runs once, and leaves student answers, keys, verdicts, grade reports and `regrade_pending` unchanged (row-for-row compare). | `TEST` |
| R22.5.3.3 | Grading: each form follows its rule (exact; exact + near-miss; exact else judge; not graded); a former short_answer and a former ordering question go to the judge when not exact; replay grading of the synthetic grade fixtures gives the same totals as before except where the change in behaviour applies, and each such difference is listed in the test. | `TEST` |
| R22.5.3.4 | Boxes, validators, answer reading, the test text (render → parse keeps `answer_form` for every form), the Word export and the print view work per form; the eval maps fixture types to forms and reports form accuracy. | `TEST` + `APP_TEST` |
| R22.5.3.5 | The page prompts' form part is no longer than the old type part (line count) and names the four forms; replay extraction of the existing cassettes (adapted, no model) gives the expected forms. | `TEST` |
| R22.5.3.6 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |
| R22.5.3.8 | A `choice` with exactly two options whose texts are True/False (any case or order; also Đúng/Sai) is relabelled "T. True", "F. False" in that order, at extraction and in the stored-test pass (a stored key or student answer on such a question is relabelled with it: the letter that meant True becomes T); readings and keys then use T/F; a two-option choice with other texts is unchanged. | `TEST` |
| R22.5.3.7 | G1 (after the verifier; the teacher warned first): typed Test 4 and photo Test G extracted; forms compared with the expected forms, questions found compared with the last 0.5.0 eval row (`eval-history.csv`); results in step22.5-plan §7. The teacher then signs off D9 or asks for a revert. | `GPU` 👤 |

**Verifier notes:** 2026-10-24, at 0747252: R22.5.3.1–R22.5.3.6 pass; R22.5.3.7 (G1) is the teacher's and stays open, so the tracker row is not ✅. S1 `TEST` 1632 passed, 14 deselected (live), no skips; S2 ruff clean, 266 files formatted, `mypy src` no issues in 108 files; S3 `wrote 42 schema files`, no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 vitest 395 passed (50 files), lint and typecheck clean, `gen:types` no diff; headless `npm run e2e` 40 passed; `e2e:shell` not run. R22.5.3.2: the pass runs inside one `transaction`, guarded by `answer_form_pending` (deleted in the same transaction), before the other first-start passes; it writes only `tests.content`; the test compares every other table row-for-row (answers, keys, attempts, grade reports, `regrade_pending`, messages) and `tests.meta/fingerprint/points_possible/updated_at`, and a second start changes nothing. A run paused across the upgrade is mapped on read (`Question` before-validator; `renumber._legacy_section` for page transcripts; answer readings in the state carry no type). Replay: only `s1`, `blank` and `validator-retry` hold tile calls (5/6/5 transcribe calls for 3/2/2 pages); all three replay with tiles on, and `s1-grade` follows `s1` through the imported set. The blank-check finding (cassette `blank/002`): those questions are a broken extraction (section V is A–D choice read as `word`, stems are the bare cue words), so a flag there is right, and with tiles off by default it adds a `validator_failed` item, not a GPU call; acceptable. Minor, not blocking: (1) `renumber._TRUE_FALSE_TEXT` misses "Write T or F" (no "true…false", "T/F" or "(T)…(F)"): such a T/F question stays a choice without options, fails the option check and is read as A–D, so a written "T" is dropped; (2) a former `matching` question (none in the teacher's data, plan-extraction-quality) with no options or more than four fails the option check, and with no options is read as A–D only; (3) `revert_question_data` also removes T/F options that a `true_false` question had stored before the pass (it cannot tell them from the added ones); (4) a revert is a forward step that must run `revert_content_data` (a plain `git revert` leaves stored tests in the new shape the old code cannot read): G1 on a copy of the data folder keeps that open; (5) `structure_types` (and so `structure_overall`) now hold form accuracy; this is stated only in `eval/metrics.py`, so rows before and after 22.5.3 are not comparable in that column. G1 should measure: the forms on Test G's True/False and word-form sections (T/F options added, no stray blank flags), and the questions found against the 0.5.0 row.

2026-10-24, re-check at f8369de (fix for notes 1 and 5): **pass, ready for G1.** `37d5f43..f8369de` changes only `domain/renumber.py`, `tests/unit/domain/test_renumber.py`, `docs/llm-design.md` (v4.42.1, changelog row) and plan.md (v2.48.4 "Based on" = PRD v8.6 · data-model v1.22.1 · llm-design v4.42.1, changelog row), all inside §6 row 22.5.3; no `app/` change, so no E2E. S1 `TEST` 1657 passed, 14 deselected; S2 ruff clean, 266 files formatted, `mypy src` no issues in 108 files. `choice_options` gets only the section instructions and the stem (not the passage or option text), and acts only on a `choice` with no options. Probe (scratch script, deleted): now matched "Write T or F", "WRITE T OR F", "T or F?", "T – F", "Đúng – Sai", "ĐÚNG/SAI", "Đúng hoặc sai"; still matched "True (T) or False (F)", "TRUE or FALSE", "Write T (True) or F (False)", "T/F/NG"; not matched (as before) "T-shirt", "AT&T", "T _ F", "T-Fal", "Unit T - Flowers". Minor, not blocking: (a) new matches in non-T/F stems: "T-F"/"T or F" as letters ("the letter T or F", "point T-F") and Vietnamese "đúng hay sai"/"đúng - sai" in an A–D instruction ("Đúng hay sai, em hãy chọn A, B, C, D"); they matter only when that choice's options were lost, where T/F options then hide the option-check flag (the old "true … false" anywhere had the same effect); (b) lowercase "t/f" no longer matches (the old regex was case-insensitive); rare on print, and the miss only leaves the question flagged and read as A–D; (c) still missed: "Đ/S", "Đ - S", "Đúng (Đ) hay Sai (S)", "Đúng ghi T, sai ghi F", "T F" with only a space; the first three print Đ/S labels, which T/F options would not fit anyway; (d) the Vietnamese words match only in NFC (precomposed) form, which is what the models return.

2026-10-24, checklist (d) at e625707 (built in bbd1f9a; `fc99ea2..HEAD`): **fails R22.5.3.8 on one point; the tracker row stays 🔄.** R22.5.3.7 counts as passed by the teacher's G1 decision ("Sign off + fix T/F", step22.5-plan §7). Checks, run one after another: S1 `TEST` 1675 passed, 14 deselected (live); S2 ruff clean, 266 files formatted, `mypy src` no issues in 108 files; S3 `wrote 42 schema files`, no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 vitest 395 passed (50 files), typecheck and lint clean, `gen:types` no diff; headless `npm run e2e` 40 passed; `e2e:shell` not run; clean tree afterwards. The 18 `r22_5_3_8` tests pass and prove what they claim: `true_false_letters` (any case, either order, trailing punctuation, Đúng/Sai; yes/no, True/True, mixed languages, 3–4 options and longer texts give None), `choice_options` and the merge give `T. True`, `F. False`; the pass relabels the reversed Test G shape (`A. FALSE`, `B. TRUE`), keeps `old_options`, relabels key `["B","b"]` → `["T"]`, value/value_norm/alt_value and the explanation row, leaves the verdict and the other choice alone, and a second start changes nothing; revert gives the old options back; reading offers `["T","F"]`. My own checks (scratch tests, not committed): a key with both letters → `["F","T"]`; a stored "True" written out, "?", "" and NULL stay as they were (the same verdict as before, since they did not match the letter key either); a lower-case `b` and an override `"b "` → `T`; an exception inside `_relabel_rows` rolls back the content, the answers and the guard row, and the next start completes. `value_norm` `t`/`f` is what `scoring.grade_answer` compares (`value_norm` on both sides, choice exact), so a re-grade gives the same verdict. Adding `explanations.wrong_answer_norm` is right: the cache and the weak-point view join on `value_norm`, and without it the old rows would be orphaned. `old_options` is consistent in `sidecar/schema/` (5 files), `openapi.json`, `app/src/gen/` and Appendix A; data-model v1.22.2 and plan v2.49.1 have changelog rows and "Based on" matches. **Failure (should-fix; R22.5.3.8, a stored student answer is relabelled):** open `uncertain_answer` / `box_inline_conflict` Review items keep the old letter in `proposal.value` / `alt_value` / `box_value` / `inline_value`, and Accept writes the proposal, not the answer row (`review._answer_override`). Reproduced: the student wrote B (= TRUE), key B, `reading_unsure`; after the pass the row is `T`/`t`, the key `["T"]`, and the card's button reads Keep "T"; Accept stores `teacher_override` "B", `value_norm` "b", so the re-grade marks it wrong. Likely on the teacher's bank (Test G's True/False answers were read unsurely), and silent. `dedupe_key`s hold question ids, not letters, so they are fine. Minor: (1) a data folder that already ran the 22.5.3 pass before bbd1f9a (guard row gone) is never relabelled, since (d) adds no new guard; the teacher's bank is still at 0.5.0, so this matters only for dev folders; (2) a stored choice labelled `T. False`, `F. True` would make the explanation update `t` → `f` hit the primary key and stop the first start (an unlikely shape); (3) a key given as the word ("True") on a T/F choice, from a key photo or stored, does not match a `T` reading (no word → letter mapping; the same before (d)); (4) explanation `text_vi`, grade report text and resolved Review items may still name A/B (history only).

2026-10-24, checklist (d) re-check at d4b71fd (fix 7c85832, docs d4b71fd; `9a1821d..HEAD`): **pass; R22.5.3.1–R22.5.3.8 and S1–S7 pass, tracker row ✅.** R22.5.3.1–6 as verified at 0747252/f8369de; R22.5.3.7 by the teacher's G1 decision. Checks, run one after another: S2 ruff clean, 266 files formatted, `mypy src` no issues in 108 files; S5 exits 0; S3 `wrote 42 schema files`, no diff; S4 only `llm/defaults.py`; S6 `openapi.json` unchanged; S7 vitest 395 passed (50 files), typecheck and lint clean, `gen:types` no diff; S1 `TEST` 1677 passed, 14 deselected (live); the 20 `r22_5_3_8` tests pass; headless `npm run e2e` 40 passed; `e2e:shell` not run; clean tree afterwards. The fix closes the should-fix: `_relabel_open_items` relabels open items only, matched by `question_id` and by `test_id` or the attempt's test, inside the same `transaction` as the rest of the pass; the new test reproduces the earlier failure (student B = TRUE, key B) and shows Accept on both `uncertain_answer` and `box_inline_conflict` now stores `T`/`t` and grades correct; a resolved item and an item on the other choice keep their letters. `PROPOSAL_LETTERS` is complete: of the 12 review kinds (`store/repos/review.py`) and every creation site (`graphs/extract.py`, `graphs/grade.py`, `domain/boxes.py`, `keys.py`, `keymap.py`, `merge.py`, `renumber.py`, `similarity.py`, `header.py`, `domain/review.py`), only `uncertain_answer`, `box_inline_conflict` (Accept writes the proposal) and `uncertain_key` hold a letter of a known question; `merge_unaligned` `value` is display only (Fix moves the already relabelled answer row) and the rest hold ids, pages or names. Relabelling `uncertain_key` `accepted` is right: Accept keeps the key row (already relabelled) and the card shows the proposal, so the two now agree. The temporary prefix cannot leak: every row of the question is prefixed and the strip runs once, so a real value `~relabel:zz` comes back unchanged. My scratch tests (not committed): an exception after `_relabel_open_items` rolls back the proposals and keeps the guard row, the next start completes and a third changes nothing; an item with `test_id` NULL is still found through its attempt; a real `~relabel:` value survives. Note: at 0.5.0 a `true_false` question was read with the enum `T`/`F` whatever its option labels, so the teacher's stored readings on such questions are mostly `T`/`F` already, which the map leaves as they are (same meaning). The previous minors stay acceptable: (1) only dev folders that ran the pass before bbd1f9a; (3) a word key "True" behaves as before (d); (4) history text only. New minors, none blocking: (5) the temporary value fixes swapped labels, but a question with explanation rows for both an old letter and the T/F letter it maps to (e.g. `A. FALSE`, `B. TRUE` with rows `a` and `f`, from a teacher override typed as `A` next to an `F` reading) still collides on the explanations primary key; the pass rolls back and every start then fails with `IntegrityError` (reproduced). It needs a mixed letter/T-F pair of wrong answers on one question, unlikely at 0.5.0 where `true_false` readings were `T`/`F` only, but the result is an app that does not start; dropping or merging the duplicate row would remove it; (6) an open `key_unmapped` item keeps its key-photo letter in `proposal.answer` (its question is unknown until Fix), so a Fix onto a relabelled True/False question stores `B`, not `T`; (7) the documented revert maps the key and student answers back but not the open Review proposals; (8) data-model §2.3b wording: a comma is missing after "`teacher_override`)".

---

### Step 22.5.4 — Grading calls
**Depends on:** 22.5.3 · **Source:** `docs/initial-plan/plan-grading-quality.md` (model roles, `ai_key_fast`, the judge,
explanations, difficulty notes, skill tagging) · decision D10 (step22.5-plan §5)

Built in two parts on the same branch: **22.5.4a sidecar** (a general builder), then **22.5.4b UI** (the UI builder,
the Models tab). Each item below is its own commit, so one can be reverted alone; G2 (after 22.5.5) measures them.

**Checklist (a, sidecar)**
- [x] Model roles: two new roles, `grading_check` (used by `verify_key`) and `extraction_check` (no task uses it yet;
      the targeted re-read of 22.5.7 will), both defaulting to qwen3.5:4b in `llm/defaults.py`; an existing
      `models.toml` without them uses the defaults; the settings API reads and writes them like `vision` and
      `reasoning`.
- [x] Opening words: `_one_question` (`graphs/grade.py`) adds the printed opening words of a `sentence` question
      (e.g. "Answer line starts with: My brother"), so the judge, `ai_key_fast`, `verify_key` and `explain` all get them;
      the judge prompt says in one line that the student's answer may continue them.
- [x] The judge: `JudgeOut` gives `reason` before `verdict`; the strict rule stays (no partial credit).
- [x] `ai_key_fast`: the section stays as context; the prompt names only the questions that need a key ("Write the key
      for these questions: …"), not "every listed question".
- [x] `explain`: `ExplainOut` gets a hidden reasoning field first, then `text_vi`, then `error_type`; the reasoning is
      kept with the call (`llm_calls`) and never shown or stored elsewhere; the prompt's first line says "a Vietnamese
      student" (no grade range). The output cap is checked against the longer output (raised only if a test shows the
      new shape cannot fit) and stated in llm-design.
- [x] Difficulty notes removed (D10: drop): the `difficulty_notes` node, prompt, schema, cassettes and progress stage
      go; a first-start pass (once, one transaction, the 22.5.2 pass pattern) removes
      `test_difficulty_notice_comment_by_ai` from every stored test's meta and changes nothing else; PRD §4's "plus the
      difficulty notes" goes.
- [x] Skill tagging per section: `tag_skills` makes one call per section with its heading, instructions, passage and
      that section's questions (still once per test, still at most 3 tags per question); the skill list stays in the
      system prompt.
- [x] Carried from 22.5.3 (step22.5-plan §6 item 5): the first-start T/F relabel cannot abort when a question has
      explanation rows for both an old letter and the T/F letter it maps to (the duplicate is merged or dropped, keeping
      one row), with a test; and §6 item 8 (the data-model comma).
- [x] Docs: llm-design (§3.1 roles, the grading prompts and schemas, the explain cap, tagging, the removed node), PRD
      (§4 difficulty notes; the new roles if the PRD names roles), data-model (the meta field dropped, the pass), each
      bumped with a changelog row and plan.md's "Based on"; `docs/initial-plan/plan-grading-quality.md` tracker row 22.5.4.

**Checklist (b, UI)**
- [x] The Settings Models tab shows four model pickers: Reading pages (vision), Grading (reasoning), Grading check,
      Extraction check, each with a one-line description; saving writes the new roles; an existing setup shows
      qwen3.5:4b for the new two.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.5.4.1 | `grading_check` and `extraction_check` exist with qwen3.5:4b defaults; a `models.toml` without them loads; `verify_key` calls the `grading_check` model (a replay with the role set to another tag records that tag); the settings API round-trips all four roles. | `TEST` |
| R22.5.4.2 | The judge, `ai_key_fast`, `verify_key` and `explain` user messages of a `sentence` question with `answer_start` contain the opening words; `JudgeOut`'s JSON schema lists `reason` before `verdict`; a judge replay (synthetic cassette) still marks a one-mistake answer incorrect. | `TEST` |
| R22.5.4.3 | `ai_key_fast`'s user message names exactly the questions without a key (a section with keyed and unkeyed questions); existing keys are untouched. | `TEST` |
| R22.5.4.4 | `ExplainOut`'s schema order is reasoning, `text_vi`, `error_type`; the reasoning appears in no API response, screen, report or Word file; the explain prompt names no grade. | `TEST` |
| R22.5.4.5 | No `difficulty_notes` node, prompt, schema, cassette or progress stage remains; the first-start pass removes the meta field from every stored test once, leaves every other field and table unchanged (row-for-row), and runs once. | `TEST` |
| R22.5.4.6 | `tag_skills` makes one call per graded section with that section's heading, instructions, passage and questions; tags stay at most 3 per question; it still runs once per test. | `TEST` |
| R22.5.4.7 | The T/F relabel with explanation rows `a` and `f` on `A. FALSE`/`B. TRUE` completes and leaves one `f` row; the pass stays once-only. | `TEST` |
| R22.5.4.8 | The Models tab shows the four pickers with accessible names; saving sends the four roles; WCAG 2.1 AA. | `APP_TEST` + screenshot |
| R22.5.4.9 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-24, 6ae9c97: ✅. Checked in the working tree of `step/22.5.4-grading-calls` (no Ollama, GPU or app data). S1 `TEST` 1687 passed, 14 deselected (448 s); S2 ruff clean, 271 files formatted, mypy no issues in 109 files; S3 38 schema files, no diff; S4 only `llm/defaults.py`; S5 `scrub --check` exits 0; S6 `openapi.json` unchanged; S7 vitest 398 passed (50 files), lint and typecheck clean, `gen:types` no diff; headless `E2E` 42 passed; clean tree afterwards. R22.5.4.1: defaults, an old `models.toml`, the settings round-trip of four roles and the replay that records `grading_check`/`checker:1b` for `verify_key` (and `reasoning` for `ai_key_fast`) read and pass. R22.5.4.2: opening words reach all four calls; `JudgeOut` order `reason`, `verdict`. The one-mistake replay is g1-mixed question 5 ("It is so cold to swim." for "too cold", judged incorrect, the teacher agrees), not question 4 ("2 years" for "two years", which the teacher marks correct); it is a scripted synthetic cassette, so it proves the reason-first output parses and an `incorrect` verdict flows, not the model's judgement (G2). `key_questions` outside the cassette match key is safe: it is `", ".join(question_ids)` and `question_ids` and `section_id` are in the key. R22.5.4.3, R22.5.4.4 (a marker reasoning is found only in `llm_calls`; no API, report or Word path reads `response_text`), R22.5.4.6 (two sections, two calls, each only its own heading, passage and questions; ≤ 3 tags; no call on re-grade) and R22.5.4.7 read and pass. R22.5.4.5: the pass runs first in `open_database`, in one transaction, rewrites only the meta of tests holding the key, deletes its guard row; the test compares every table row for row. The tagging cassettes split 10 → 30 keep the same multiset of (question, tags) per scenario (script); the uniform logprobs of `s1-grade/039-tag_skills-1` are harmless, since tags use no confidence. eval-history.csv's 145-column header equals the harness's COLUMNS (retired `difficulty_notes_*` kept in place). R22.5.4.8: four pickers, accessible names = visible names, descriptions linked by `aria-describedby`, contrast ≥ 4.5 in light and dark (E2E); screenshots `app/test-results/s22.5.4-models-tab-{light,dark}.png` read: uncluttered, the 2–3-line descriptions are acceptable. Saving all four roles with unchanged tags leaves the merged config equal to the defaults (script). Worth a look (not failures): (1) `eval/harness.py` changed in 1d4918c is outside structure §6 row 22.5.4 (needed; the orchestrator should add it). (2) `make_synthetic_grade.py` (and `make_s1_seeded.py`, which uses its queues) queue one `TagSkillsCall`, so a regeneration answers the second section's tag call with invalid JSON and records failed calls; fix before the next regeneration. (3) llm-design §3.1's sample `[client]` line says `extraction_check = true`; `DEFAULT_CLIENT` has false, and `config.py`'s docstring omits the role. (4) Save now writes all four role tags to `models.toml` even when only the log retention changes, so a later change of a default tag no longer reaches that setup. (5) plan-grading-quality row 22.5.4 still says "built (sidecar)". (6) Not checked: a grade run stopped at `difficulty_notes` before the upgrade and resumed after it.

---

### Step 22.5.5 — The checker's answer on hover; weak points over time 👤 GPU
**Depends on:** 22.5.4 · **Source:** `docs/initial-plan/plan-grading-quality.md` (the checker's answer on an unsure key; weak points
from the student's trajectory) · decisions D11, D11a–D11e (step22.5-plan §5)

Built in two parts on the same branch: **22.5.5a sidecar** (a general builder), then **22.5.5b UI** (the UI builder).

**Checklist (a, sidecar)**
- [x] The checker's answer: when `verify_key` disagrees, its answer and reasoning are stored with the unsure key (or its
      `uncertain_key` Review item; the data-model says which); when the check fails, that is stored too ("the check did
      not finish"). The Key read (`GET /tests/{id}` keys or the key route) carries them.
- [x] Date taken (D11a): attempts get `taken_on` (a date; migration; stored attempts get the date of `created_at`); the
      extraction input and the attempt update route set it; the trajectory orders by it, then `created_at`.
- [x] Levels (D11d): each skill has a level A1–B2: grammar skills from `prompts/taxonomy/grammar.txt`; the 26 section
      skills from the base levels in step22.5-plan §5 D11d, written into `prompts/taxonomy/sections.txt` (a level
      column) without lengthening the prompt the model sees beyond that column. `tag_skills` also returns a level per
      question (one short output field); stored with the question's tags; a tag's level is the question's level when
      given, else the skill's base level.
- [x] Trajectory (D11, D11b, `domain/weakpoints.py`): per student and skill, the papers in date-taken order; per paper
      the share right, where a right `choice` counts 0.5 (replaced by the guessing baseline, D11f, checklist (d)) and careless and spelling mistakes are left out as today. A
      skill with answers on fewer than 3 papers is "not enough evidence". With 3 or more, "recent" is the last 2
      papers and the label is the first that applies: **improved** (earlier share < 0.5, both recent ≥ 0.5; not a weak
      point), **slipped** (earlier ≥ 0.5, both recent < 0.5), **consistently weak** (share < 0.5 on at least 2/3 of
      the papers), **inconsistent** (overall share 35–65 %), otherwise **solid**. Thresholds are named constants.
- [x] The report's weak points (D11c, D11e): per skill missed on this paper: the trajectory label when the skill has
      one (improved and solid are not weak points); otherwise "this paper only". Ordered from the lowest level up,
      vocabulary first within a level; when any weak point is at a level L, those above L are marked held back
      ("later, after the basics"). The summary call (`weak_points_summary`) gets skill names, not codes, and only the
      weak points not held back.
- [x] Students route: a student's skills with label, level and per-paper results, for the Students tab.
- [x] Docs: data-model (checker fields, `taken_on`, levels, tag level, labels), llm-design (`tag_skills` output, the
      summary input), PRD (weak points by trajectory, basics first, the Students tab, date taken), each with a version
      bump and changelog row and plan.md's "Based on"; `docs/initial-plan/plan-grading-quality.md` tracker row 22.5.5.

**Checklist (b, UI)**
- [x] Key tab: hover or keyboard focus on "AI unsure key" shows the checker's answer and its reasoning (or "The check
      did not finish"), as the Keys changed tooltip of 22.4.8; rows stay as they are.
- [x] Date taken (D11a): the photo check card of a student's paper has a date field (default today); the Student
      answers tab shows it and lets the teacher change it.
- [x] Students tab (D11b): a student's page lists every skill with its label (improved, slipped, inconsistent,
      consistently weak, not enough evidence, solid) and level, ordered basics first; weak skills above the lowest weak
      level sit behind a "Later, after the basics (N)" line that opens (D11e).
- [x] The report: weak points show "this paper only" or their label; held-back ones behind the same "Later, after the
      basics (N)" line.
- [x] Models tab (teacher, 2026-10-24): the picker descriptions show only on hover or keyboard focus, not under the
      names.

**Checklist (c, after the screenshots; teacher, 2026-10-25)**
- [x] Clicking a student in the Students tab opens the student's skills in the main panel (a wider view, like a test
      or a report): "Skills — <student>", a table of level, skill (full name), label and per-paper results in
      date-taken order, basics first, with the "Later, after the basics (N)" line; the sidebar row no longer lists the
      skills.

**Checklist (d, after the verifier; teacher, 2026-10-25)**
- [x] Guessing baseline (D11f, replaces "a right `choice` counts 0.5"): per paper and skill, each question has a chance
      level (a `choice` with k options: 1/k, so 0.25 for A–D and 0.5 for T/F; any other form: 0); the share is
      max(0, right − Σ chance) / (counted − Σ chance), so all right = 100 % and chance-level = 0 %; the thresholds stay.
- [x] Verifier blocker: on a first grade the report uses the levels `tag_skills` just returned (graph state over the
      stored ones), so the report and the Students view agree; a test proves the report uses them.
- [x] Verifier should-fix: the summary request's `wrong_answers` block leaves out held-back skills too.
- [x] Verifier findings: `Explanation.llm_call_id` accepts NULL (a thread delete sets it), so `list_explanations` no
      longer fails for another paper of the same test; Review Accept clears a stale `checker`.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.5.5.1 | A `verify_key` disagreement stores the checker's answer and reasoning; a failed check stores that it did not finish; both reach the Key read; replay with synthetic cassettes. | `TEST` |
| R22.5.5.2 | Migration adds `taken_on`; stored attempts get their `created_at` date; the input and the update route set it; the trajectory orders by it. | `TEST` |
| R22.5.5.3 | Every one of the 58 grammar and 26 section skills has a level; `tag_skills` output carries a level per question (schema), stored and used; a missing level falls back to the base level. | `TEST` |
| R22.5.5.4 | Trajectory cases, one per label, incl. the guessing baseline (D11f; was a right `choice` counting 0.5), careless/spelling left out, ties in date order, and fewer than 3 papers → not enough evidence. | `TEST` |
| R22.5.5.5 | Report weak points: "this paper only" vs labels; improved/solid excluded; basics-first order with vocabulary first in a level; held-back marking; the summary request has names, not codes, and no held-back skills. | `TEST` |
| R22.5.5.6 | Key tab hover/focus shows the checker's answer and reasoning, or "did not finish"; keyboard reachable; screen-reader text. | `APP_TEST` + screenshot |
| R22.5.5.7 | Date taken on the photo check card (default today) and editable on the Student answers tab; the value is sent and shown. | `APP_TEST` |
| R22.5.5.8 | The Students tab shows labels and levels basics first, with the "Later, after the basics (N)" line opening the held-back skills; the report shows the same; the Models tab descriptions show only on hover/focus; WCAG 2.1 AA. | `APP_TEST` + screenshot |
| R22.5.5.11 | Clicking (or Enter on) a student in the Students tab opens the skills view in the main panel with full names, level, label and per-paper results; the "Later" line works there; WCAG 2.1 AA; headless screenshots. | `APP_TEST` + screenshot |
| R22.5.5.12 | Trajectory shares use the guessing baseline (cases: all right on A–D = 100 %, chance-level = 0 %, T/F, mixed forms); a first grade's report levels equal the levels `tag_skills` returned; the summary request names no held-back skill anywhere; an explanation row with NULL `llm_call_id` loads; Accept clears `checker`. | `TEST` |
| R22.5.5.9 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |
| R22.5.5.10 | G2 (after the verifier; the teacher warned first): grade Test G's paper; compare verdicts, explanations, tags and levels, weak points and time with 0.5.0's calls (with the teacher's permission to read them); results in step22.5-plan §7. | `GPU` 👤 |

**Verifier notes:** 2026-10-25, at a6e028b (stacked on `step/22.5.4-grading-calls`): ❌ R22.5.5.3 and R22.5.5.5 (the report's levels on a test's first grade); R22.5.5.1, .2, .4, .6, .7, .8, .9, .11 pass. S1 `TEST` 1719 passed, 14 deselected; S2 ruff clean, 278 files formatted, `mypy src` no issues in 110 files; S3 `wrote 38 schema files`, no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 vitest 407 passed (51 files), lint and typecheck clean, `gen:types` no diff; headless `npm run e2e` 48 passed; screenshots `app/test-results/s22.5.5-*.png` (key tip, Students skills view, report weak points, Models tab; light and dark) read. **Failing:** the `weak_points` node (`graphs/grade.py:724`) reads the question levels from `question_tags` (`list_tag_levels`), but on a test's first grade `tag_skills` has just produced them in state (`tag_levels`) and `save` writes them only after `weak_points`. So the report's levels, basics-first order and held-back marking use the base levels, ignoring the levels the model gave. A verifier scratch test (deleted) on the `test_full_grade_path` harness with every `tag_skills` item at `level: "B2"` stored B2 but reported `GR-PSV-A1` at A1. A later grade of the same test (another student, a re-grade) and the Students view read the stored B2, so the two disagree for the same paper. The replay test `test_r22_5_5_3_tag_levels_are_stored_and_fall_back` checks the stored rows only, not the report. Fix: merge the state's `tag_levels` (through `tag_level`) over the stored ones in `load`, and a test that the report uses them. Domain checks pass: thresholds are named constants; precedence improved → slipped → consistently weak → inconsistent → solid; recent = last 2 by `taken_on`, `created_at`, id; a right `choice` 0.5; careless/spelling out; a paper with 0 counted answers for a skill is left out; superseded attempts are left out; the report's trajectory = stored papers without the graded attempt + this paper, the Students view = all current papers; `2/3·n` has no float edge for n ≤ 30. Migration 0014, `PATCH /attempts/{id}` (date + version, no run), levels kept on merge and Extract again, the checker stored/cleared, the section levels equal D11d, and the prompt diff (one line in `tag_skills.md`, the level column in `sections.txt`, `weak_points_summary.md` unchanged) all check out. Contrast of the label colours on bg/surface/panel ≥ 5.5:1 light and ≥ 6.7:1 dark. Worth a look: (1) the `wrong_answers` block of the summary request still names held-back skills (`grade.py:756`), so the model can mention them; (2) Accept keeps a stale `checker` on a `teacher_verified` key (`api/routes/tests.py:344`, `domain/review.py:271`; hidden, since the tip shows only for `ai_uncertain`); (3) pre-existing since 22.2.3: after a thread delete, `explanations.llm_call_id` is NULL but `Explanation.llm_call_id` is `str`, so `list_explanations` (`graphs/grade.py:286`, `api/routes/attempts.py:241`) raises for another paper of the same test; (4) for the teacher: with a right `choice` = 0.5 and the 0.5 threshold, a skill tested only by `choice` questions can never be solid (all right → share 0.5 → `inconsistent`; one miss per paper → < 0.5 → `consistently_weak`). No teacher field written.

2026-10-25, fresh verifier, re-check at bfdf316 (`fd65eb7..HEAD`; fixes fd4824d, f20cdbe, fe81d52, c2f0cda, docs f693e2b, bbe117a, bfdf316): **pass; R22.5.5.1–9, 11 and 12 pass; the row waits for G2 (R22.5.5.10).** R22.5.5.12: `chance_level` gives 1/k for a `choice` with k ≥ 2 options, 0.25 with no stored options (or < 2), 0 for other forms; `PaperSkill.share` = max(0, right − Σ chance) / (counted − Σ chance), and a paper with counted − Σ chance ≤ 1e-9 is not `scored` (share 0, left out of `trajectories`); since a chance level is ≤ 0.5, that cannot happen with counted ≥ 1 (the guard is defensive). `option_counts` counts only questions with options, so a `choice` that lost them reads as 0.25 (a True/False one too, though code adds T/F options). All right = exactly 1.0, chance level = 0, below chance clamped at 0; mixed forms, T/F and a choice-only skill reaching `solid` are tested; all-careless answers give no row. `weak_points` merges the state's `tag_levels` (through `tag_level`, as `list_tag_levels` does for the stored rows) over the stored levels only when `tags_new`; a re-grade or another paper (`tags_new` False, `grade.py:449`) reads the stored rows. The summary's `wrong_answers` lines drop held-back skills and a line with only held-back skills is left out. `Explanation.llm_call_id: str | None`; Accept (`domain/review.py:271`) and PUT verify (`api/routes/tests.py:344`) set `checker: None`; a PUT with new `accepted` builds a fresh key without a checker. Each fix was reverted on its own (then restored): the `tags_new` merge off → `test_r22_5_5_12_first_grade_report_uses_tag_skills_levels` fails (`[('GR-PSV-A1', 'A1')]` ≠ B2); held-back filter off → `test_r22_5_5_12_summary_request_names_no_held_back_skill` fails; `checker: None` removed → `test_r22_5_5_12_verify_clears_a_stale_checker` and both Appendix E `uncertain_key · accept` rows fail; `llm_call_id: str` → `test_r22_5_5_12_explanation_with_null_llm_call_id_loads` fails. Docs: PRD v8.8.1, data-model v1.24.1 §2.4/§2.6/§4, llm-design v4.45.1 §5, plan "Based on" and plan-grading-quality v0.10.4 match the code; D11f is in step22.5-plan §5; the half rule appears only in changelogs, earlier verifier notes and "was"/"replaces" wording. Run one after another: ruff clean, 278 files formatted, `mypy src` no issues in 110 files; `erh scrub --check tests/cassettes` exit 0; `wrote 38 schema files`, `openapi.json` unchanged, no diff; vitest 407 passed (51 files), typecheck and lint clean, `gen:types` no diff; S1 `TEST` 1730 passed, 14 deselected; headless `npm run e2e` 48 passed. Tree clean after each run. No findings beyond the minor note on a T/F `choice` without stored options. No teacher field written.

2026-10-25, the 22.5.6 verifier: tracker row set to ✅ (c754e2f) on the teacher's recorded G2 acceptance (R22.5.5.10): `docs/initial-plan/phases-testing/step22.5-plan.md` §7 "G2 result" ("Accept", run on c754e2f) and §5 "G2"; no re-verification.

---

### Step 22.5.6 — Typed pages; reading student answers and keys 👤 GPU
**Depends on:** 22.5.5 · **Comment:** 4 (question 31) · **Source:** `docs/initial-plan/plan-extraction-quality.md` (content cut at
page breaks, typed path; answer reading; key-photo keys) · decision D12 (step22.5-plan §5)

Built in two parts on the same branch: **22.5.6a sidecar** (a general builder), then **22.5.6b UI** (the UI builder).
Each item is its own commit.

**Checklist (a, sidecar)**
- [x] Typed PDFs (comment 4, D12): a typed PDF's page texts are joined and cut with `split_text_page`
      (`store/documents.py`) like a Word file's text (at section headings, else question starts, never inside a
      question, at most 6 000 characters), so the printer's page breaks no longer reach the model. The code keeps
      where each PDF page's text starts in the joined text; each question gets the PDF page its text starts on, and
      pictures stay on the PDF page they are printed on. Photos and Word files are unchanged.
- [x] The typed-text prompt (`structure_text_page`): `answer_start` examples with "=>" and with no arrow (one short
      example each), and a guard against repetition on long pages (a code check where possible — e.g. stop and flag
      a page whose output repeats — before any prompt line).
- [x] Answer reading: `read_answers_page` asks each page only for the questions printed on it (by `page_no`),
      strictly the printed number and the answer next to it; an answer written only on another page is not read
      (accepted limit). `resolve_answers` is unchanged.
- [x] Key reading: `read_key_pages` says in one line that explanations on the key pages are ignored.
- [x] Key-photo keys: a key read from the key photo is no longer `ai_verified` without a second model call; it gets
      its own state (e.g. "from the key photo", with its confidence), and "double-checked" (`ai_verified`) means a
      second call agreed. Stored keys: a one-time pass moves key-photo keys that no check verified to the new state
      (the data-model says how they are recognised).
- [x] The listening part: the extraction records which printed range was left out as listening, and the attempt
      read carries it.
- [x] Docs: data-model, llm-design, PRD (each with a version bump and changelog row, and plan.md's "Based on");
      `docs/initial-plan/plan-extraction-quality.md` tracker rows.

**Checklist (b, UI)**
- [x] Key tab: a key-photo key shows "From the key photo" (no "double-checked"); "AI key · double-checked" only for a
      key a second call agreed with; the "AI unsure key" labels stay as they are.
- [x] Student answers tab: one quiet line says how the listening part was handled, e.g. "Listening (questions 1–10)
      left out".

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.5.6.1 | A synthetic typed PDF whose question and options are split across a page break reaches the model as one text piece; the cut never falls inside a question; each question's page is the PDF page its text starts on; a picture stays on its printed page; photos and Word files go through as before. | `TEST` |
| R22.5.6.2 | The typed-text prompt has the two `answer_start` examples; a repeating output on a long page is caught by code and flagged (replay with a synthetic cassette). | `TEST` |
| R22.5.6.3 | Each `read_answers_page` request names only that page's questions; a 4-page, 40-question replay asks for 40 entries in all, not 160; resolution is unchanged. | `TEST` |
| R22.5.6.4 | The key prompt says explanations are ignored; a synthetic key page with explanations gives only label–answer pairs. | `TEST` |
| R22.5.6.5 | A key-photo key without a second call is never `ai_verified`; the stored-key pass moves only such keys, once, and changes nothing else. | `TEST` |
| R22.5.6.6 | The left-out listening range is stored and on the attempt read. | `TEST` |
| R22.5.6.7 | The Key tab and Student answers tab show the new labels and the listening line; WCAG 2.1 AA. | `APP_TEST` + screenshot |
| R22.5.6.8 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |
| R22.5.6.9 | G3 (after the verifier; the teacher warned first): typed Test 4 extracted: questions 29–34 in one section, no stray section "A", `answer_start` on 37–40, each question's page right; results in step22.5-plan §7. | `GPU` 👤 |

**Verifier notes:** 2026-10-25, fresh verifier, at 1a74a91 (`step/22.5.5-checker-weakpoints..HEAD`, 16 commits): **❌ R22.5.6.1**; R22.5.6.2–8 pass (R22.5.6.9 is G3). S1 `TEST` 1748 passed, 14 deselected; S2 ruff clean, 284 files formatted, `mypy src` no issues in 111 files; S3 `wrote 38 schema files`, no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 vitest 413 passed (52 files), lint and typecheck clean, `gen:types` no diff; headless `npm run e2e` 52 passed; clean tree afterwards. Scope: every path is in §6 row 22.5.6. R22.5.6.2: `test_r22_5_6_2_*` (cut at the repeat, `repeated_pages` {"1": 30}, one `validator_failed` "repeated output"; both prompt examples). R22.5.6.3: 4 pages × 10 questions ask 40 IDs in all, each page only its own; 40 answers, all read. R22.5.6.4: one prompt line; `ReadKeyOut` rejects an explanation field. R22.5.6.5: `map_key` never gives `ai_verified`; the pass moves only `from_key_photo` / `ai_verified` / confidence ≥ 0.7 (q-1, q-2 of 8 cases), once, in one transaction, nothing else changed; the rule holds because `verify_key` keeps the confidence and checks only `ai_unverified`, and the threshold is not configurable; no code still reads `ai_verified` as "from the key photo". R22.5.6.6: `OmittedSection.kind`, `listening_range` (old `kind = null` rows: listening when none of their numbers is stored), `AttemptDetail.listening_skipped`. R22.5.6.7: labels in vitest and E2E `s15`, `textAA` in light and dark. Cassettes: in the recorded ones (`s1`, `blank`, `s1-seeded`, `typed-pdf-mixed`) every kept entry equals its own page's recording (cut only, none moved); entries were reassigned only in synthetic ones (`extract-synthetic/*`, `unreadable/filled`). Re-transcribe stays consistent: typed pages get no tile call, `placed` is passed to every merge.
**R22.5.6.1 fails** (D12 "each question gets the PDF page its text starts on"; "Word files go through as before"): (1) `documents.locate_pages` finds a question only by its number at a line start or by its stem; a passage question with `stem` null and no option line of its own (open cloze "(17) ____", word form in a passage) takes the previous question's offset, so a passage on page 2 after a section ending on page 1 gives all its questions page 1 (verifier probe: questions 17–19 → page 1, their group → page 2). A passage holding a numbered list ("1. Wake up early") before questions 1–2 on the next page also puts them on the passage's page. A wrong `page_no` makes per-page answer reading of student photos of that test skip those answers. (2) `renumber.cut_repetition` (every `structure_text_page` call, Word files too) signs a question by number, stem and options only: two sections that both number from 1 with stem-less questions (an open cloze, then a word-form passage; cues are not in the signature) count as a repeat, and everything after is dropped (probe: 3 of 5 questions dropped) and flagged. Minor: `join_typed_pdf_pages` finds picture pages by comparing NFC-normalised page texts with raw `get_text()` (an NFD PDF loses its picture pages; the group falls back to its first page); `docs/initial-plan/plan-extraction-quality.md` row 22.5.6 still says "UI (b) next". No teacher field written.

**Verifier notes (re-check):** 2026-10-25, fresh verifier, at e875cfb (`a9eff27..HEAD`: dd536da, 757690a, 2898cd7, e875cfb): **❌ R22.5.6.1**; R22.5.6.2–8 pass (R22.5.6.9 is G3). S1 `TEST` 1769 passed, 14 deselected; S2 ruff clean, 286 files formatted, `mypy src` no issues in 111 files; S3 `wrote 38 schema files`, no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 vitest 413 passed (52 files), lint and typecheck clean, `gen:types` no diff; headless `npm run e2e` 52 passed; clean tree afterwards. The three test files pass (24); against the a9eff27 sources 13 of them fail, so they cover the fixes. Fixed and holding: a cloze or word-form passage after a section ending on the earlier page; "(17)", "17.", "17 ____", "[17]" markers, "in 1917" and "17.5" not taken for 17; two passages on one page both numbering from 1; a passage over a page break with markers on both sides and stemmed questions after it; a numbered list in a passage; NFD picture pages. `cut_repetition`: a loop of part of a section (same group, or the section heading again with a subset) is cut; two passages or two sections numbering from 1 with different stimulus, title or cues keep every question; a pronunciation section with identical options in two questions keeps both. Docs: llm-design v4.46.1 describes both rules, plan "Based on" v4.46.1, plan-extraction-quality row updated.
**R22.5.6.1 still fails** (blocker; D12 "each question gets the PDF page its text starts on"): `locate_pages` finds a passage's end by its last five words (`_find_words_end`), and `_probe_words` drops any word holding "__" or "…", while `_GAP` skips only spaces, "_", dots and "…". A marker glued to its blank ("__(3)__", "(3)____", "3.____", "……(3)……", the usual Vietnamese layout) in the passage's last five words is dropped from the probe, but its "(3)" stays in the text between two probe words, so the end is not found; `g_end` falls back to the passage start, the marker search range is empty, and every stem-less question falls back. Probe (synthetic, "My town is (1)____ big and quiet." on page 1, "…are (2)____ friendly and the food is (3)____ good." on page 2): alone, questions 1–3 → pages [0, 0, 0] (want [0, 1, 1]); with a section numbering from 1 on page 3, all three passage questions → page 3 ("1. He go home" is taken for question 1 and the cursor moves past the passage). The same layout with "(1) ____" (marker as its own word) is right. Minor: (a) a stem-less question whose marker is missing is searched by number at a line start after the passage, so a later section's "2." captures it and the questions after it (probe: [0, 1, 1] for [0, 0, 0]); (b) a stimulus the model did not copy verbatim (a curly apostrophe "Mary’s" → "Mary's") is not found and its stem-less questions keep the previous question's page (the old behaviour); (c) "aged 17." before the "(17)" marker is taken as the marker. Partial-loop false negatives (a loop that renumbers, or alternates a changed stem) are not cut; acceptable, the output cap still ends them. No teacher field written.

**Verifier notes (second re-check):** 2026-10-25, fresh verifier, at 0cb2a5a (`9936398..HEAD`: 0659be8, 0cb2a5a): **❌ R22.5.6.1**; R22.5.6.2–8 pass (R22.5.6.9 is G3). S1 `TEST` 1782 passed, 14 deselected; S2 ruff clean, 286 files formatted, `mypy src` no issues in 111 files; S3 `wrote 38 schema files`, no diff; S5 exits 0; S6 `openapi.json` unchanged; S7 vitest 413 passed (52 files), lint and typecheck clean, `gen:types` no diff; headless `npm run e2e` 52 passed; clean tree afterwards. The three 22.5.6 test files pass (37); against the 9936398 sources 11 of them fail, so they cover the fix. Docs: llm-design v4.46.2's D12 paragraph matches `_fold`, `_find_marker` and `locate_pages`; plan "Based on" is v4.46.2. Holding (synthetic probes): glued markers; a Vietnamese cloze over a page break; numbered stems whose words fold the same ("Mà tôi…" / "Má tôi…"); a passage under five words, also over a break; a numbered word box "(1) careful (2) happy" on the passage's first page; "in 2017. (TRUE)" and "1917." not taken for 17; numbered paragraphs, then T/F 1–4; unnumbered T/F rows; "Câu 1:"; a key table after a cloze; a passage or a blank exactly at a page start; the offset map exact for accents, "đ", curly quotes, dashes, ligatures and "ß".
**R22.5.6.1 still fails** (major; D12 "each question gets the PDF page its text starts on"; a regression from one call per page for typed PDFs): `locate_pages` tries `_find_question` (the number at a line start, anywhere ahead) before the stem's words, so a question whose number is printed mid-line takes the next line starting with that number later in the piece, and the cursor moves there, so every later question follows it. Probes: two questions per line ("1. He ____ home.     2. She ____ tall.") with an "ĐÁP ÁN" key table on page 3: questions 1–5 → [0, 2, 2, 2, 2] (want [0, 0, 0, 0, 1]); the same with the next section numbering from 1 on page 2: [0, 1, 1, 1] (want [0, 0, 1, 1]). A key table at the end of a typed test is common. A fix could take the nearer of the number match and the stem match. Minor (rare edge cases): (a) a passage's end is the first match of its last five words, so a passage whose closing phrase also occurs earlier in it ends early and its later markers fall back to the previous gap (probe [0, 0, 0] for [0, 0, 1]); (b) a passage ending in a bare blank with no full stop ("…we love it (2) ____") ends before its last marker, so that gap on the next page keeps the previous gap's page ([0, 0, 2] for [0, 1, 2]; with "____." it is right); (c) "Tom turned 17. (He was happy.)" before "(17)" is taken as the marker; (d) a group starts at the first match of its first five words from the cursor, so section instructions or an earlier stem with the same folded words ("Read the passage about my school…"; "Bà ba bán bánh mì" / "Ba bà bán bánh mì") give the group the earlier page (its questions are right); (e) a stimulus the model copied with a small change in its first five words (an added comma) is not found, and its stem-less questions keep the previous question's page; (f) markers printed "(Câu 17)" are not in marker form (they fall back to the passage). No teacher field written.

**Verifier notes (third re-check):** 2026-10-26, fresh verifier, at e13aa18 (`a4f540f..HEAD`: c611c2d, c83de18, e13aa18): **R22.5.6.1–8 pass** (R22.5.6.9 is G3). S1 `TEST` 2092 passed, 14 deselected; S2 ruff clean, 286 files formatted, `mypy src` no issues in 111 files; S3 `wrote 38 schema files`, no diff; S5 exits 0; S6 `openapi.json` unchanged; S7 vitest 413 passed (52 files), lint and typecheck clean, `gen:types` no diff; headless `npm run e2e` 52 passed; clean tree afterwards. The three 22.5.6 test files pass (347, incl. 300 property seeds); against the 0cb2a5a `documents.py` 77 fail, so they cover the rework. Docs: llm-design v4.46.3's D12 paragraph matches `_Words`, `_starts_of`/`_ends_of`, `_question_event`, `_align` and the fallback; plan "Based on" is v4.46.3. The property generator copies stems verbatim from distinct vocabulary and has no model noise, so own probes went beyond it. Holding (synthetic): every earlier verifier probe; a 50-question 5-page Vietnamese test ("Câu n." pronunciation, 20 choice rows with option lines, a cloze, numbered-paragraph reading with T/F, word form with cues, rewrite with "=>" lines) over 12 seeds, clean and with model noise (stems cut short, a wrong first word, a dropped question, a duplicated question, all together): 72 of 72 right; numbered paragraphs 1–4 then questions 1–5 (with and without the paragraph numbers in the stimulus); instructions repeating a stem's words; lightly paraphrased stems; a hallucinated stem (neighbours unaffected); a misnumbered question; a matching table; "According to the passage, …" stems (also with that phrase dropped); T/F statements copied verbatim from a passage, numbered; two sections numbering stem-less questions from 1; no crash on empty text, a group with no questions, no sections, punctuation-only stems, a 60-question single page. Timing: the 50-question test 0.03 s; adversarial 60 stems sharing their first words 0.45 s (100: 3.2 s; the DP is quadratic in candidates). Minor (rare edge cases, one item wrong, its neighbours right): (a) a stem whose first words the model reordered ("Since 2010 we have lived here"), or prefixed with two extra words, on a page's first question, is matched by a shifted three-word probe whose offset lands on the previous page; (b) two questions the model swapped: one takes the previous question's page; (c) unnumbered T/F statements whose first copies the passage's first sentence, across a page break: the group start ties at the passage end and takes the statements' page (the questions are right); (d) the alignment cost grows with candidates per question (above). No teacher field written.

**Verifier notes (G3):** 2026-10-26, step 22.5.7 verifier: the teacher accepted G3 on 2026-10-26, run on 8ec134d (`docs/initial-plan/phases-testing/step22.5-plan.md` §7 "G3 result", §5 "G3"); the tracker row is ✅ (R22.5.6.9 done). No teacher field written.

---

### Step 22.5.7 — Photos: page breaks, the re-read, answer-number errors, model trial 👤 GPU
**Depends on:** 22.5.6 · **Comment:** 4 (photos) · **Source:** `docs/initial-plan/plan-extraction-quality.md` (content cut at page
breaks, photos; the half-page re-read; answer-number errors; tune or replace the model) · decision D13 (step22.5-plan §5)

Sidecar and eval only (no screen change beyond a model setting if needed). Each item is its own commit.

**Checklist**
- [x] Page breaks on photos: `transcribe_page` for page N+1 also gets, as text, the last open unit of page N as already
      read (the last section's title and instructions; the last question with what it lacks, e.g. "14: stem, no
      options"; an open passage's last paragraph from its last blank; about 100–300 tokens), and the prompt says in one
      or two lines: if the page starts with the rest of that question or passage, return it as that question (same
      printed number) or under that section, marked as continued. `merge_and_normalize` joins a continued section into
      the previous one, fills a question's missing options or stem from its continued copy, and joins a split passage.
- [x] The targeted re-read: a page that fails a check gets one call on the `extraction_check` role that returns only
      the broken pieces (by section title and printed number), and code patches them into the page; the whole-page or
      tile re-read stays as it is today behind its setting. Tiles stay off by default; G4 measures them on and off.
- [x] Answer-number errors: the eval splits wrong question numbers into renumbering errors (the code's numbering) and
      reading errors (the model's printed numbers), as two metrics appended to `eval-history.csv`.
- [x] Model trial (D13): GLM-OCR 0.9B as an optional two-step photo reader: photo → OCR text (the `ocr` model) → the
      typed-text path (`structure_text_page` on the text, as for typed PDFs since 22.5.6). Behind a setting
      (`[extract] photo_reader = "vision" | "ocr"`), default `vision` (today's path); the OCR model is a role with no
      default download. Reading the student's answers stays on the vision model.
- [x] Docs: data-model, llm-design, PRD (each with a version bump and changelog row, and plan.md's "Based on");
      `docs/initial-plan/plan-extraction-quality.md` tracker rows.
- [x] After G4 (teacher, 2026-10-26: GLM-OCR reads test photos, tiles stay off; step22.5-plan §5 "G4"): the default
      photo reader becomes `ocr`, and the `ocr` role (`glm-ocr`) becomes a default role, so it is listed, checked and
      offered for download wherever the other default models are (model status, the Models tab, first start). Student
      answers stay on the vision role. A `models.toml` that sets `photo_reader = "vision"` keeps today's path. The docs
      are updated as above.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.5.7.1 | The page N+1 request carries the last open unit of page N (synthetic 2-page photo test: question 14's stem on page 1, options on page 2); the merge gives one question 14 with stem and options, one section, one passage; a page with nothing open sends no hint. | `TEST` |
| R22.5.7.2 | A page failing a check makes one `extraction_check` call naming only the failing pieces; the patch replaces only those pieces; the other pieces are byte-identical; a failed re-read call leaves the page as it was. | `TEST` |
| R22.5.7.3 | The eval reports renumbering and reading errors separately on synthetic fixtures with one of each; the history columns are appended, not reordered. | `TEST` |
| R22.5.7.4 | With `photo_reader = "ocr"`, a photo page goes through the OCR call then `structure_text_page` (replay with synthetic cassettes); with the default nothing changes (all existing photo replays pass unchanged); the student answers are still read by the vision model. | `TEST` |
| R22.5.7.5 | S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |
| R22.5.7.6 | G4 (after the verifier; the teacher warned first): Test G's photos with student answers, three runs: qwen3.5:4b tiles off, tiles on, and GLM-OCR two-step; questions found, duplicates, empty questions, check failures, time per node, answer-reading time, student answers on another page not read; results in step22.5-plan §7; the teacher picks the photo reader for 0.6.0. | `GPU` 👤 |
| R22.5.7.7 | An empty data folder reads a test photo with an `ocr` call (`glm-ocr`) then `structure_text_page`, and its student answers with the vision role; `photo_reader = "vision"` in `models.toml` gives today's calls (the existing photo replays pass with it set); `glm-ocr` appears in the default model list, the model status check and the download offer; tiles stay off by default; S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |

**Verifier notes:** 2026-10-26, fresh verifier, at 9f47c46 (`step/22.5.6-typed-pages-reading..HEAD`: a926f7d, 7f6ed5d, 1d7411d, 721ae6b, 0039b6e, f3b0d14, 9f47c46): **R22.5.7.1–5 pass** (R22.5.7.6 is G4). S1 `TEST` 2122 passed, 14 deselected (a first run with other jobs alongside had one failure in `test_routes_b.py::test_key_edit_deletes_explanations_and_defers_the_regrade`; it passes alone and in the clean full re-run, so load timing); S2 ruff clean, 291 files formatted, `mypy src` no issues in 111 files; S3, S6 no diff; S4 only `defaults.py`; S5 exit 0; S7 vitest 413 passed (52 files), lint and typecheck clean, `gen:types` no diff; `E2E` 52 passed. R22.5.7.1: `tests/replay/test_step22_5_7_page_breaks.py` (question 14 cut, marked and same-number; passage cut, marked and gap numbers; no hint when nothing is open; the replay gives the same test). R22.5.7.2: `tests/unit/graphs/test_extract.py` re-read tests (one `extraction_check` call naming only question 4, only its options replaced, the rest byte-identical; failed call leaves the page; missing numbers inserted; a worse patch dropped; off by default = no call) and `tests/unit/domain/test_reread.py`. R22.5.7.3: `tests/unit/eval/test_eval_numbers.py`; `eval-history.csv` 145 → 147 columns, the two new ones at the end, all 15 old rows unchanged with empty new cells. R22.5.7.4: the `ocr` graph tests (OCR call with no format and no system message, then `structure_text_page` with no image, student answers on vision `qwen3.5:4b`, a failed OCR call → `validator_failed` with no structure call; the default reader sends no OCR call; the `ocr` role is absent from `parse_models_config({})`, so the model, settings and status routes never list or pull it). Docs: PRD v8.10, data-model v1.26, llm-design v4.47 with changelog rows; "Based on" matches. Prompts: `transcribe_page.md` +2 rule lines and the `{{previous_page}}` input; `reread_pieces.md` 14 lines; `ocr_page.md` the prompt alone.
Synthetic merge probes (`merge_pages`): a new section starting at 1 after a section ending at 1, and a new section "II" whose first question is numbered 14 after "I" ends at a complete 14, are **joined into the previous section and the new section's first question is dropped with no flag**. This happens because `_splits_question` (`renumber.py:476`, used at `:538`) matches on the number alone and does not check that the last question lacks anything or that the new section prints its own title. Before this step the same pages gave a duplicate number that the numbering check flagged. **Should-fix**; it is rare on 1–40 numbered papers. Two passages in one continued section (empty title) whose gaps go on (1–2, then 3–4) are joined into one group (`_joins_passage`, `:491`, no `_passage_open` check when reached from `_join`). No question is lost: **minor**. A listening section is never joined; two passages in separate titled sections stay apart. Minor: the `--role` help (`cli.py:806`) does not name `ocr`; the app's `extraction_check` description still says "(used later)"; `number_counts` cannot align a question with no stem, options or cue (it is left out of both rates). No teacher field written.

Verifier notes (R22.5.7.7, the OCR reader as default), 2026-10-26, fresh verifier, at e912074 (`a199d04..HEAD`: 2ab68b7, f83f998, d2c572e, e46066f, 9c39b99, e912074): **pass**. S1 `TEST` 2135 passed, 14 deselected; S2 ruff clean, 293 files formatted, `mypy src` no issues in 111 files; S3, S6 no diff; S4 only `defaults.py` (`glm-ocr` also only there); S5 exit 0; S7 vitest 415 passed (52 files), lint and typecheck clean, `gen:types` no diff; `E2E` 52 passed. Empty data folder: `test_r22_5_7_7_empty_data_folder_reads_photos_with_ocr` (no `models.toml`: `ocr_page` on `glm-ocr`, then `structure_text_page` with no image; the student answers on vision `qwen3.5:4b` with the photo; `llm_calls` rows `ocr`/`glm-ocr`; no tile step). `photo_reader = "vision"`: `parse_models_config` drops `ocr` unless `[roles.ocr]` is set; the photo replays (`test_extract_replay`, `test_extract_again_replay`, `test_key_pages_replay`, `test_progress_replay`, the API s1 fixtures, `make_synthetic`) pin it through `tests/support/reader.py`; no cassette, `fixtures/` or `eval-history.csv` change, so nothing was re-recorded. `glm-ocr` is in `DEFAULT_ROLES`, `SUGGESTED_TAGS`, `/settings`, `/models`, `/system/status` (`missing_models` `["glm-ocr"]`) and `/settings/models/pull` (`tests/unit/api/test_step22_5_7.py`); tiles and `reread_pieces` are off by default. Models tab: "Test reader" / "Reads the test photos" and "Student answer reader" / "Reads the student answers from the photos" (`roles.ts`); the OCR picker shows only when the sidecar sends the role. Docs: PRD v8.11, llm-design v4.48, data-model v1.27 with changelog rows; "Based on" matches. Scope: every path is in §6 row 22.5.7 (`settings-models.spec.ts` and `models.test.tsx` read as label tests of `roles.ts`). Upgrade (code reading and tests only): an existing `models.toml` without `photo_reader` switches to OCR; `/system/status` then reports `missing_model` with `glm-ocr`, so the first-run screen offers **Download models**; a Models tab Save keeps every other section (`write_models_config`). If the teacher chooses "Continue anyway" and extracts without `glm-ocr`, Ollama's 404 is an `OllamaError` that fails the run (`run.failed`, "OllamaError: /api/chat returned 404: ..." naming the model): no crash, as with a missing vision model today, but the text is technical. Worth a look (low): the delete-button sentence "Used for student answer reader and grading" reads badly (a role name where an activity belongs; with the OCR model it gives "Used for test reader"); "Used by the student answer reader and grading" would read normally. Worth a look (low): `docs/initial-plan/plan-extraction-quality.md` row 22.5.7 still says the OCR reader is "behind settings, off"; a `settings.test.tsx` comment still says "after Reading pages". No teacher field written.

### Step 22.5.8 — Installer 0.6.0
**Depends on:** 22.5.7 · the parked questions of step22.5-plan §6, answered by the teacher on 2026-10-26 (§5 "Parked
questions") · R21.1, R21.2 and R21.5 again on the final commit, as in 22.4.9.

**Checklist**
- [x] (a) The teacher's answers to the parked questions, each its own commit:
      (1) the test-details heading "Your details" becomes "Test details";
      (2) when a key photo replaces an AI key in the same run, that key's open `uncertain_key` Review item is closed;
      (3) a Fix of an open `key_unmapped` item onto a True/False question stores T/F through the same relabel map as the
      first-start T/F pass (A → T, B → F as relabelled);
      (4) the unused `rank_weak_points` and its tests are removed;
      (5) (teacher, after the round verifier) a True/False choice relabelled at extraction keeps its options as read in
      `old_options`, and a key-photo letter or a student's letter on a relabelled True/False choice is stored as T/F.
- [x] (b) The round's fresh verifier: steps 22.5.1–22.5.7 together and (a), S1–S7, headless `E2E` with screenshots.
- [x] (c) Version 0.6.0 in the places 22.4.9 changed; `app/src-tauri/gen/schemas/` regenerated if the build changes it.
- [x] (d) `TAURI_BUILD`; sizes and the Defender scan in a new `docs/release-notes.md` section 0.6.0: what changed since
      0.5.0 in plain words (steps 22.5.1–22.5.7); test photos are now read by GLM-OCR (`glm-ocr`, about 2.2 GB, offered
      at first start with the other models) and student answers by qwen3.5:4b; the known limits from step22.5-plan
      §6–§7 (GLM-OCR's section titles, numbering and answer boxes; the parked extraction gaps); the new migrations run
      at first start; how to install over 0.5.0.
- [x] (e) No `E2E_SHELL` by the builder (the user starts it).
- [x] (f) (teacher, 2026-10-26, after the first 0.6.0 build) The new light theme, PRD §10.1 v8.12 to v8.17 (the
      teacher's changes after the screenshots; the latest PRD version wins where the values below differ), on
      `step/22.5.8b-theme`: the green tokens become the teacher's colours (background rgb(230, 232, 242), text
      rgb(14, 14, 1), main blue rgb(31, 35, 224) with white text on it); dark mode is removed (no
      `prefers-color-scheme` or `data-theme="dark"` palette); correct = green rgb(86, 219, 86) fill, unsure = ochre
      rgb(224, 132, 34) fill, both with dark text; wrong and delete = brick rgb(150, 39, 24); the correct and unsure
      labels written as text use letters fading from the text colour (top) to yellow rgb(230, 208, 67) (bottom);
      the other surfaces (cards, sidebar, panels, hover, borders, inputs, focus) are derived from the background and
      the blue. Headless `E2E` screenshots of the main screens are shown to the teacher before (c)–(d) and
      `E2E_SHELL` are run again on the new commit.
- [x] (g) (teacher, 2026-10-27) The app is renamed **ETACH**, PRD v8.18, on `step/22.5.8c-rename`: the sidebar
      wordmark ETACH in Federo (bundled, Latin only) with "English Test Assistant - Curate & Help" under it (Faustina,
      bold, centred, a short rule underneath); the window title, `index.html`, and every user-visible text that names
      the app; `productName` ETACH, a new `identifier`, the installer `ETACH_0.6.0_x64-setup.exe`; the default app
      folder `D:\ETACH` (installer `.onInit`, its `%USERPROFILE%` fallback, the Rust and Python defaults, their tests);
      `e2e:shell` expectations that name the old exe or folder. Internal code names (`erh`, `erh.exe`, `ERH_APP_DIR`,
      the repository) stay. No migration code: after the teacher installs 0.6.0, the orchestrator gives a reviewed
      script that the teacher runs to move `data\` and `settings.json` from `D:\ExamRevisionHelper` to `D:\ETACH`,
      checks the sizes, and the teacher uninstalls the old app only after ETACH opens with the data. The release
      notes 0.6.0 say so.
- [x] (h) (teacher, 2026-10-27) The layout, PRD §10.1 "Layout (v8.21)", on `step/22.5.8d-layout`: corners,
      the sidebar (New thread as its earlier simple row (v8.23), separated tabs, the open thread tinted (v8.22), motto group headings in Chats only (v8.27), a labelled Settings row, blue focus outlines), the workspace panel as paper with a double rule under its
      header, the symbols in Faustina; the start screen as a paper-shaped dotted drop box without a heading (v8.25). Headless `E2E` screenshots are shown to the
      teacher before anything else is built on it.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.5.8.1 | (a) (1)–(4) each have a test: the heading text; the item closed with the photo's key kept; the T/F letter stored; no reference to `rank_weak_points` left; (5) `A. FALSE` / `B. TRUE` read at extraction keeps `old_options`, a key-photo `B` is stored as `T` and a student's `B` is read as `T`. | `TEST` + `APP_TEST` |
| R22.5.8.2 | The round's verifier passes 22.5.1–22.5.7 and R22.5.8.1; S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |
| R22.5.8.3 | Every version string is 0.6.0 and the lock files agree; `erh --version` prints 0.6.0; `cargo test --lib` passes with no diff in `app/src-tauri/gen/`. | `TEST` |
| R22.5.8.4 | R21.1: `TAURI_BUILD` exits 0 and outputs `ETACH_0.6.0_x64-setup.exe` (`Exam Revision Helper_0.6.0_x64-setup.exe` before (g)); `target/release/sidecar/erh.exe --version` prints 0.6.0 with one `erh-*.dist-info`. | Run it |
| R22.5.8.5 | R21.2: `E2E_SHELL --release`, Settings shows 0.6.0; started by the user. | `E2E_SHELL --release` |
| R22.5.8.6 | R21.5: release notes 0.6.0 with sizes, the Defender scan of installer, sidecar folder and shell exe, the changes, the GLM-OCR download, the known limits, the migrations and the update steps; earlier sections unchanged. | Read the file |
| R22.5.8.7 | (f) The tokens are the colours of PRD §10.1 v8.12; no dark palette or dark-mode switch is left; the token test checks the WCAG pairs the app uses (text ≥ 4.5:1, borders, icons and focus ≥ 3:1), with the gradient labels' top colour as their text colour; correct, unsure and wrong are never used as decoration; headless `E2E` passes and its screenshots are shown to the teacher; (v8.16) every text uses Faustina, bundled with its Vietnamese subset and loaded offline, the old font packages are gone, and the text of the main buttons and workspace tabs looks as large as in Merriweather (v8.17: only those). | `APP_TEST` + `E2E` |
| R22.5.8.8 | (g) No user-visible "Exam Revision Helper" or "Exam Helper" is left in the app, the installer or the window title (history text and internal code names excepted); the sidebar shows ETACH in Federo (loaded offline) and the subtitle line; `productName` is ETACH and the identifier is new; the default app folder is `D:\ETACH` in the installer, Rust and Python, with their tests; nothing resolves into AppData; `cargo test --lib`, `TEST`, `APP_TEST` and headless `E2E` pass. | `TEST` + `APP_TEST` + `E2E` |
| R22.5.8.9 | (h) The layout of PRD §10.1 v8.21: the radius scale (papers 2 px, buttons 6 px, chips round, arch-topped workspace tabs); the sidebar items as described, each with the app's blue focus outline and AA contrast for text; the motto headings in the Chats list only, Tests and Students ungrouped (v8.27); the open thread is shown by a tint stronger than the hover tint (v8.22), every name at the same left edge; the workspace panel as paper with the double rule; the symbols in Faustina; the start screen as a dotted drop box without a heading (v8.25); nothing clipped or overlapping at 1280 and 900 px; headless `E2E` passes and its screenshots are shown to the teacher. | `APP_TEST` + `E2E` |

**Verifier notes (f)–(h):** 2026-10-28, fresh verifier (R22.5.8.7–R22.5.8.9), on `step/22.5.8d-layout` at d7bf371, re-checked at 16c7213 and ba09eda: **pass.** No Ollama, GPU, `e2e:shell`, app or app data. An earlier verifier, stopped by its time limit, found lint and typecheck clean, every token equal to the PRD values, the contrast pairs passing, no dark mode, Faustina the only text font with its Vietnamese subset, and the rename consistent (visible names, `tauri.conf.json`, NSIS, paths, `run.mjs`). At d7bf371: vitest 57 files / 457 tests passed; headless `E2E` 44 passed; `cargo test --lib` 17 passed; sidecar `test_appdir.py` (both), `test_step20.py` and `test_routes_c.py` 79 passed; ruff clean, 296 files formatted, `mypy src` no issues in 111 files. R22.5.8.9 by reading: Tailwind's radius scale cleared, papers 2 px, buttons 6 px, chips `rounded-full`, arch-topped workspace tabs (`rounded-t-button`); New thread a plain row (v8.23); the sidebar tabs split by white lines; the open row `bg-tint-strong`, hover `bg-tint` (v8.22); `GroupHeading` used only in the Chats list (v8.27); a labelled Settings row with its ring unclipped; the workspace panel as paper with the `double-rule`; the start screen without a heading, a dotted A4 box tinted on drag-over, the drop going to the same `onFiles` as Choose files (v8.25); `font-mono` in Faustina. No input sits on `--erh-tint-strong` (the rename input is white with a blue border), so the 2.81:1 of `--erh-input-border` on it is unused. The `layout-*` screenshots (workspace at 1280 and 900 px, the start screen and its drag-over, the sidebar lists, Settings focused) match the PRD; nothing clipped or overlapping. Scope: every path of `fc1dd5c..HEAD` is in §6 row 22.5.8 (f), (g) or (h) or in an orchestrator `docs/` / `.claude/` commit; no `👤 sign-off:` commit. Findings, both fixed: (F1) the rename input, the student edit row's inputs, Cancel and Save, and the running slot's Stop, Resume and Discard lacked the blue focus outline (PRD §10.1 v8.21); fixed in 16c7213, with a unit test over every Sidebar control and the running slot and an s16 `sidebarRings` check in five places (vitest 458, `E2E` 44). (F2) that fix drew Save's ring inside its own blue fill (blue on blue, 1:1, invisible; WCAG 2.4.7, 1.4.11); fixed in ba09eda with the outer offset, a source check that every blue-filled sidebar control draws its ring outside, and an s16 contrast check; the Save-focused screenshot shows the ring outside the fill. At ba09eda: vitest 57 files / 459 tests passed, headless `E2E` 44 passed; tree clean (`app/test-results/` is gitignored).

**Verifier notes:** 2026-10-26, round verifier (checklist (b), R22.5.8.1–R22.5.8.2), at 8cb62ae with a re-check at da4552e: **pass.** Checked on `step/22.5.8-installer`, round base `e94e4cf` (no Ollama, GPU, `e2e:shell` or app data). At 8cb62ae: S1 `TEST` 2143 passed, 14 deselected (live); S2 ruff clean, 295 files formatted, `mypy src` no issues in 111 files; S3 39 schema files, no diff; S4 no `numind/`, `qwen3` or `glm-ocr` tag outside `llm/defaults.py`; S5 `scrub --check` exits 0; S6 `openapi.json` unchanged; S7 vitest 52 files / 416 tests passed, lint and typecheck clean, `gen:types` no diff; headless `E2E` 52 passed; screenshots `s22.5.2-extract-again-light`, `s22.5.5-models-tab-dark` and `s22.5.6-key-photo-dark` read fine; tree clean afterwards. R22.5.8.1: (1) `KEPT` reads "Test details and keys on unchanged questions stay; …", pinned by `step22_5_2.test.tsx` and `s13-settings-series.spec.ts`; (2) `save_extract` settles the question's open `uncertain_key` items (`fixed`, `{"action":"fix","value":{"by":"key_photo"}}`) when the photo key is inserted or updated; the photo key stays, other questions' items and other kinds stay open (`test_step22_5_8.py`); `uncertain_key` items are made only by grade runs, so the same save cannot reopen one; (3) `true_false_key` maps a `key_unmapped` Fix letter through `old_options` only when the options are T/F now (`test_step22_5_8_tf_fix.py`); (4) no code reference to `rank_weak_points` is left (history text only). These tests fail without their change (by reading). Scope: the first run found `llm/client.py` and `llm/adapters/{__init__,chat}.py` (0039b6e, the plain-text OCR call) outside §6 row 22.5.7; structure v1.1.135 (61b2822) adds them, and every other path of `e94e4cf..HEAD` is in a 22.5.x row or an orchestrator docs commit. No `👤 sign-off:` commit and no teacher field in the round; no `fixtures/` path committed; `eval-history.csv` only gained header columns (rows padded). Re-check of (a)(5) (d209d24, docs da4552e), run only where it changed: `test_step22_5_8_tf_letters.py`, `tests/unit/domain`, `graphs/test_extract.py`, `graphs/test_unreadable_extract.py`, `graphs/test_step22_5_8.py`, `graphs/test_grade.py`, `unit/examples`, `prompts/test_key_prompt.py`, `store/test_step22_5_3.py`, `store/test_step22_5_6_keys.py` and the replays `test_extract_replay`, `test_key_pages_replay`, `test_step22_5_7_page_breaks`: 834 passed; ruff, format and mypy on `src/erh/domain` clean; schema and OpenAPI exports no diff. `relabelled_from` sets `old_options` only when `choice_options` relabelled options that read True/False (`T. True` / `F. False` as read, or no options, give None); `map_key` and `resolve_answers` map a letter through `true_false_key`. Side effects (reading): the first-start pass skips a question whose options are already `T. True` / `F. False`, so fresh `old_options` stay; its revert restores them, as for a pass-relabelled question; `fingerprint_text` and `question_text` (compare_bank, Extract again alignment) read `options`, not `old_options`, so neither changes. Paths of d209d24 are in §6 row 22.5.8 (v1.1.136). Minor, not blocking: (i) a test-text save rebuilds questions without `old_options` (`domain/test_text.py`, as for pass-relabelled questions before), so a later key photo on that test stores its letter as read; (ii) the v2.57.3 changelog row says "Minor" but its number is a patch bump.

**Build and release checks (orchestrator, 2026-10-26):** R22.5.8.3: every version string 0.6.0, `erh --version` 0.6.0, version tests (sidecar 62, app 20) and `cargo test --lib` (17) pass, no diff in `app/src-tauri/gen/` (faf27f4). R22.5.8.4: `TAURI_BUILD` exit 0, `Exam Revision Helper_0.6.0_x64-setup.exe` (45,280,694 bytes); frozen `erh.exe --version` 0.6.0 with one `erh-0.6.0.dist-info`, 175 files. R22.5.8.6: release notes 0.6.0 (b0f6d95, 61eb155; Defender 1.461.211.0, no threats). Not re-checked by a fresh verifier (the teacher: "re run only the ones needs rerun").

**Rebuild after (f)–(h) (orchestrator, 2026-10-28):** `TAURI_BUILD` from `ed27d65` exit 0, `ETACH_0.6.0_x64-setup.exe` (44,804,084 bytes); `target\release\ETACH.exe` (10,343,424 bytes); frozen `erh.exe --version` 0.6.0 with one `erh-0.6.0.dist-info`, 175 files (107,771,930 bytes). Defender 1.463.1.0: no threats in the installer, the sidecar folder or `ETACH.exe`. Release notes 0.6.0 rewritten for ETACH (build, sizes, scan, what changed incl. (f)–(h), installing next to 0.5.0 with the one-time data copy). R22.5.8.5 (`E2E_SHELL --release`) must be run again by the user on this build.

**Install and data copy (teacher, 2026-10-29/30):** the teacher installed `ETACH_0.6.0_x64-setup.exe` into `D:\ETACH`; the reviewed one-time script set ETACH's fresh `data\` aside as `data-fresh-2026-10-29` and copied `D:\ExamRevisionHelper\data` to `D:\ETACH\data` (robocopy 0 failed; both 146 files, 7,586,272,493 bytes: match; 0.5.0 had no `settings.json`). The teacher opened ETACH and found the tests, students and threads as before ("all are fine").

**R22.5.8.5 E2E_SHELL on the ETACH build** run 2026-10-29 by the user (`cd app && npm run e2e:shell -- --release`, exe `ETACH.exe`): every check PASS, "E2E_SHELL: all passed"; Settings shows 0.6.0 = `erh --version` (source and frozen); R15.2 real drop; R14.5 nothing new in %APPDATA%/%LOCALAPPDATA%; R20.7 moved-folder checks pass. The first attempt stopped before the app opened: the WebView2 runtime had updated to 156.0.4314.50 while `D:\DevTools\msedgedriver` was 154; the user replaced the driver with Microsoft's signed 156.0.4314.50 (the old one kept as `msedgedriver-154.exe`). No app change.

**R22.5.8.5 E2E_SHELL** run 2026-10-26 by the user (`cd app && npm run e2e:shell -- --release`) on the 0.6.0 release build: every check PASS, "E2E_SHELL: all passed"; Settings shows 0.6.0 = `erh --version` (source and frozen); R14.5 nothing new in %APPDATA%/%LOCALAPPDATA%; R15.2 real drop; R20.7 moved-folder checks pass.

**Next (teacher, 2026-10-26):** before installing 0.6.0 the teacher wants to discuss the app's theme (after a context compaction). If theme work is built, the installer is rebuilt (a new build, scan and E2E_SHELL) before the release; otherwise 22.5.8 is ready to be marked ✅ and the branches merged. The teacher chose the new theme, (f); the
installer is rebuilt after it.

---

## Step 22.6 — The teacher's sixth look (ETACH 0.6.0)

The teacher used ETACH 0.6.0 on two Grade 8 photo tests (Test K, Test G8) and wrote 4 comments, to be fixed before
anything else (2026-10-30). The comments verbatim, the orchestrator's findings from the app's data and the teacher's
decisions D1–D9 are in `docs/initial-plan/phases-testing/step22.6-plan.md`. Step 22.5.9 (the logo and installer 0.6.1) is folded
into this step (D1). It runs like step 22.5: sub-steps on stacked branches `step/22.6.N-<slug>`, each change its own
commit, a fresh verifier before the GPU check, the teacher warned before each GPU run. Answer boxes, repeated options,
blank papers and the three photo ways concern photo input only; the key after extraction and the checker apply to
every input (D8). Each sub-step gets its requirements when it starts.

### Step 22.6.1 — Answer boxes, repeated options, the format example (photos)
**Depends on:** 22.5.8 · **Comments:** 2, 3 · decisions D2, D3, D8

**Checklist**
- [ ] (a) D2, first barrier: before `structure_text_page` on a photo page, code removes the answer box from
      GLM-OCR's text: a line starting with "Phần trả lời" (matched without accents and allowing OCR misreads such as
      "Phàn trả lối", "Phàn trà lòi"), with any numbered blanks on it, and the lines right after it that hold only
      numbered blanks (`N. ____`, `N. ...`, one or several per line). Blank-only lines are removed only after such a
      heading, so a real question is never removed.
- [ ] (b) D2, second barrier, and D3: the photo path's structuring prompt says, in one line each, to leave out answer
      boxes and that a question printed as only its number and options has an empty stem (the options are not
      repeated); and it gets one short example of OCR lines and the sections, questions and options made from them.
      The typed-text prompt (DOCX, typed PDF) is unchanged.
- [ ] (c) llm-design (the photo path, the prompt) bumped; cassettes re-recorded or replays updated where the prompt
      changes.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.6.1.1 | (a) The answer-box remover drops a heading line, "Phần trả lời" (with or without accents, and the OCR misreads "Phàn trả lối", "Phàn trà lòi") or "ANSWER"/"ANSWERS"/"Answer:" followed by nothing but numbers, with any numbered blanks on it, and the number-only lines after it (`N. ____`, `N. ...`, `N. …`, `29. 30. 31.`, several per line, empty lines between them allowed); it stops at the first other line, which stays. With no heading, a line of two or more numbered blanks and nothing else goes; a single `N. ____` stays, and so does "Answer the questions". Text with no answer box comes back unchanged. On Test K's and Test G8's stored OCR text it removes every answer box and nothing else (checked read-only, not committed). | `TEST` |
| R22.6.1.2 | On the photo path (`photo_reader = "ocr"`), the text sent to `structure_text_page` has the answer boxes removed; a typed page's document is sent unchanged. | `TEST` |
| R22.6.1.3 | (b) The photo call's prompt holds the answer-box line, the empty-stem line and the small example; the typed call's rendered prompt and its hash are the same as before (the typed replays pass unchanged). | `TEST` |
| R22.6.1.4 | S1–S7 hold. | `TEST` + `APP_TEST` |

### Step 22.6.2 — Blank papers, empty answers
**Depends on:** 22.6.1 · **Comment:** 1 (the made-up student answers) · decisions D5, D8

**Checklist**
- [x] (a) D5: after the student answers of a photo paper are read, code decides from the reading whether the student
      wrote anything. From Test K's and Test G8's stored readings (Test K: 2 of 40 answers read with confidence; G8:
      20 of 42) the teacher chose (2026-10-30): **blank when fewer than 20% of the answers are read with confidence**
      (`boxes.BLANK_SHARE`); an unreadable `???` counts as written. A paper judged blank ends **the same way as a paper
      with nothing read today: a test-only (blank) thread** (the teacher: "if a student do that test in the future, it
      gets its own thread and may be use the 'look like existing test' feature"): the test is saved, no attempt, no
      student answers, no answer Review items, no score and no report; the extraction card records "No student
      answers found".
- [x] (b) A model answer spelled `null`, `none` or `n/a` is stored as empty, not as the text (G8, questions 35–40).
- [x] (c) PRD v8.28 (S4) and llm-design v4.51 bumped; data-model unchanged (no field added).

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.6.2.1 | `resolve_answers` judges a paper blank when fewer than 20% of its answers have a value read with confidence (7 of 36 → blank, 8 → not); a `???` counts as written; a failed page is never blank; a blank result keeps no Review items. The share is `[extract] blank_share` (default 0.2; 0 = the rule before). The recorded S1 paper (1 of 34 read sure) replays as a blank test (the teacher: "20% as built"); its grade replay sets `blank_share = 0` to rebuild the attempt it was recorded on. | `TEST` |
| R22.6.2.2 | A value spelled `null`, `none` or `n/a` (any case, spaces around) is read as no value. | `TEST` |
| R22.6.2.3 | A run whose answers are all read unsure saves the test alone: no attempt, no answers, no `uncertain_answer` or `box_inline_conflict` item, the thread `blank` and pointing at the test, the card `no_answers`. | `TEST` |
| R22.6.2.4 | S1–S7 hold. | `TEST` + `APP_TEST` |

### Step 22.6.3 — The checker may be unsure
**Depends on:** 22.6.2 · **Comment:** 4 · decision D6

**Checklist**
- [x] (a) D6: `verify_key` may answer unsure (`?`); an unsure answer is handled as a disagreement today (the key
      stays, "AI unsure key", an `uncertain_key` Review item), and the Key tab's hover says the checker was unsure.
- [x] (b) D6: its prompt says, in one line, that it has a limited number of tokens and should answer `?` rather than
      run out; the cap becomes 1000 output tokens (was 1500); a cut-off answer stays unsure.
- [x] (c) data-model and llm-design bumped; the `verify_key` cassettes and tests follow.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.6.3.1 | A `verify_key` answer of `?` (spaces around ignored) makes the key `ai_uncertain` with an `uncertain_key` Review item, as a disagreement does, and stores the checker's result as a new `KeyCheck` status `unsure` with its `reasoning` and no `answer`; a real disagreement stays `disagreed`, a cut-off or twice-failed check stays `did_not_finish`. | `TEST` |
| R22.6.3.2 | `base/verify_key.md` says, in at most two short lines, that the checker may answer `?` when not sure and that its output is limited, so it answers `?` rather than run out; `GRADING_NUM_PREDICT["verify_key"]` is 1000. | `TEST` |
| R22.6.3.3 | On the Key tab, hovering or focusing "AI unsure key" for a key whose check is `unsure` shows "The checker was not sure." followed by its reasoning. | `APP_TEST` |
| R22.6.3.4 | The exported schemas, `openapi.json` and `app/src/gen/` are regenerated and differ only by the new status; S1–S7 hold. | `TEST` + `APP_TEST` |

### Step 22.6.4 — The key after every extraction
**Depends on:** 22.6.3 · **Comment:** 1 (the key only at Grade) · decision D4 (changes PRD D2 and D16)

**Checklist**
- [x] (a) D4: when an extraction (or Extract again) finishes, the app makes the key at once, with or without a key
      photo: the AI key for the questions without one (`ai_key_fast`) and its check (`verify_gate`, `verify_key`), as
      grading does today. The teacher can open the Test tab straight away; the Key tab stays blank, with a short note,
      until the key is ready, and then shows it all at once (no update per key).
- [x] (b) Grading uses the key already made and makes it only if it is missing. (teacher, 2026-10-30) While the key
      is still being made, **Grade student answers is greyed out with a short note ("Making the key…")** and becomes
      pressable when the key is ready. *Sidecar half done (part (a)): Grade uses the key already made and makes only
      missing keys; the greyed-out button is part (b).* *Screens half done (part (b)): the Key tab note, Grade
      waiting with "Making the key…", no toast for the key run, the note after a failed or discarded key run.*
- [x] (c) PRD D2 and D16 changed (major bump), data-model and llm-design (the run kinds, the API routes, the progress
      stages) bumped.

Built in two parts: (a) the sidecar part, the generated files and the docs by a step agent; then the screen part
(the Key tab note, the greyed-out button) by the UI builder.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.6.4.1 | An extract run's save (a new test, Extract again, a picked existing test, a blank test, typed or photo input) queues, in the same transaction, one grade run on the same thread with `attempt_id` None and the new `GradeInput.reason` `after_extract` (the existing "Make the key" run: the AI key for the questions without one, its check, the skill tags); a retried save queues no second run; the run starts after the extract run, by the existing FIFO. | `TEST` |
| R22.6.4.2 | That run never grades an attempt; keys from a key photo or the teacher stay; a later Grade uses the keys it made and makes only missing ones; if it fails or is stopped, Grade still works as today. | `TEST` |
| R22.6.4.3 | `GradeInput.reason` gains `after_extract`; the exported schemas, `openapi.json` and `app/src/gen/` differ only by that. | `TEST` |
| R22.6.4.4 | While the thread's `after_extract` run is queued or running, the Key tab shows a short note instead of the keys, and Grade student answers is disabled with "Making the key…" (a tooltip or line the teacher can read, keyboard-focusable); when the run ends, the keys appear at once and the button is enabled. | `APP_TEST` + `E2E` |
| R22.6.4.6 | (teacher, step22.6-plan D12) Extract again and Delete thread, while the thread's only unfinished runs are `after_extract` key runs (queued, running, stopping, stopped or interrupted), discard those runs and go ahead instead of answering 409; any other active run still gives 409. `erh run` and `erh eval` queue no key run. | `TEST` |
| R22.6.4.7 | (teacher, D14) `DELETE /tests/{id}` and the student delete route, when the only unfinished runs on the affected threads are `after_extract` key runs, discard them and go ahead; any other active run still gives 409. | `TEST` |
| R22.6.4.8 | (teacher, D13, screens) The `after_extract` run never shows a toast or notification, done or failed; a failed or discarded key run leaves the Key tab blank with a short note (Grade then makes the key as today). The E2E specs wait for the key run where they read results (`s1-run`, `s4-review`). | `APP_TEST` + `E2E` |
| R22.6.4.5 | PRD D2 and D16 say the key is made after every extraction (major bump); data-model and llm-design follow; S1–S7 hold. | Read the docs + `TEST` + `APP_TEST` |

### Step 22.6.5 — Two photo ways without qwen
**Depends on:** 22.6.4 · decision D7

**Checklist**
- [x] (a) D7: one `models.toml` setting chooses how a photo page's text becomes sections, questions and options
      (the setting and (2b) ✅, first step agent; (2a) ✅, second step agent, llm-design v4.57):
      (1) GLM-OCR then qwen3.5:4b with 22.6.1's prompt (today's way, the default until the teacher chooses);
      (2a) GLM-OCR prompted with the app's test-text format and a short example instead of `Text Recognition:`, its
      output read by the existing test-text parser (`domain/test_text.py`), no qwen;
      (2b) GLM-OCR's plain text, with 22.6.1 (a)'s answer boxes removed, structured by code from the printed layout
      (Roman numerals or "Part" for sections, `N.` for questions, `A.`–`D.` and T/F for options, the text between a
      heading and its first question as the passage, a line under a rewrite question as its opening words), no qwen.
      What (2a) or (2b) cannot place is flagged `?` or sent to Review, never dropped.
- [x] (b) (2b) is tried first on Test K's and Test G8's stored OCR text (read-only, nothing committed); the tests in
      git use made-up texts.
- [x] (c) llm-design (the photo path, the setting) and the Models tab's help, if the setting is shown there, bumped.
      (llm-design v4.56, v4.57; the Models tab does not show the setting.)

Built by two step agents: (2b) and the setting first, then (2a).

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.6.5.1 | `[extract] photo_structure` in `models.toml`: `"qwen"` (way 1, the default; today's calls unchanged), `"code"` (2b) or `"ocr_format"` (2a); it applies only to photo pages on the OCR path (`photo_reader = "ocr"`); typed pages and the vision path are unchanged. `erh eval` can set it for a run, like `--photo-reader`. | `TEST` |
| R22.6.5.2 | (2b) Code turns a page's plain OCR text (answer boxes removed, R22.6.1.1) into the same per-page output the structuring call gives (`TranscribeOut`), so the merge, page-break joins, validators and save run unchanged, with no model call: sections from Roman-numeral or "Part" headings (their instruction lines and printed points kept), questions from `N.` / `Question N.` lines, options `A.`–`D.` on one line or several, True/False statements, a shared passage (the text between a heading and its first question, or a cloze with `(N) ____` gaps) as the group stimulus, a line under a rewrite question as its `answer_start`, the cue in brackets for word form; `answer_form` from the layout as the prompt defines it. A line it cannot place stays in the nearest section's instructions or a question's stem and the page gets a `validator_failed` item; nothing is dropped. | `TEST` |
| R22.6.5.3 | (2b) On Test K's and Test G8's stored GLM-OCR text (read-only from the app's data, the teacher's permission of 2026-10-30; nothing committed), the agent reports per test: questions found against the paper (G8 40, K 40), numbering gaps or repeats, sections and their titles, repeated options, answer-box questions; and fixes what the layout rules should catch. | Report |
| R22.6.5.4 | (2a) The OCR call gets a prompt with the app's test-text format (as `domain/test_text.py` reads it) and one short example instead of `Text Recognition:`; its output is read by the test-text parser into the same per-page output; a page whose text the parser cannot read gets a `validator_failed` item with the reason, and its text is kept for Review. | `TEST` |
| R22.6.5.5 | llm-design (the photo path, the setting) bumped; S1–S7 hold; replays and E2E unchanged with the default. | `TEST` + `APP_TEST` + `E2E` |

### Step 22.6.6 — Verifier and the three-way photo check 👤 GPU
**Depends on:** 22.6.5

**Checklist**
- [x] (a) A fresh verifier: 22.6.1–22.6.5, S1–S7, headless `E2E`.
- [x] (b) After a warning, one GPU check runs Test K and Test G8 the three ways (1), (2a) and (2b) (D7). How the runs
      are started is decided when 22.6.6 starts. Compared with today's data and with each other: questions found
      against the paper (G8 has 40), answer-box questions, repeated options, section titles, numbering, time per page;
      Test K's blank paper (no student answers); the key ready after extraction and its time; the checker's unsure
      count and time. Results in step22.6-plan §5.
- [x] (c) The teacher picks the default way from the comparison; it is set as the default in its own commit.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.6.6.1 | (a) A fresh verifier passes R22.6.1.1–R22.6.5.5 and S1–S7 on the stacked branches (base `fe72e3c`, main), headless `E2E` passes; it writes a test for step22.6-plan §4's open note (a test edit during a first grade run) and reports what it shows; every path committed in the round is in a §6 row 22.6.x or an orchestrator docs commit; it marks the tracker rows 22.6.1–22.6.5. | `TEST` + `APP_TEST` + `E2E` + reading |
| R22.6.6.3 | (verifier findings, teacher D15 "Fix now") A test-text save that deletes questions or changes points while an attempt of that test has an unfinished grade run (queued, running, stopping, stopped, interrupted) ends with that attempt graded against the saved test (its score, points possible and verdicts follow the new content), whether by a queued re-grade or by grading reloading the test; the verifier's `test_step22_6_6_open_note.py` passes without `xfail`; the text save's `points_changed` path is checked and either works or is removed with its reason. | `TEST` |
| R22.6.6.4 | (verifier finding on R22.6.1.1) The English answer-box heading ("ANSWER", "ANSWERS", "Answer:") counts only when nothing but numbered blanks or bare numbers follows on its line; `Answer: 1. He goes to school` and `ANSWERS 5 points` stay. | `TEST` |
| R22.6.6.5 | (verifier finding on R22.6.5.1) A test shows that `photo_structure = "code"` or `"ocr_format"` leaves a typed page and the vision path exactly as with `"qwen"`. | `TEST` |
| R22.6.6.6 | A fresh verifier re-checks 22.6.1 and R22.6.6.3–5, the full suite, S1–S7 and headless `E2E`. | `TEST` + `APP_TEST` + `E2E` |
| R22.6.6.2 | (b) (teacher, 2026-10-31: "One script") One PowerShell script in the session scratchpad, started by the teacher after a warning: it copies Test G8's 4 and Test K's 3 photos read-only from `D:\ETACH\data\files` into the scratchpad (nothing written under `D:\ETACH`), runs `erh run --spawn-ollama` on both tests with `[extract] photo_structure` `qwen`, `code` and `ocr_format` (one scratch data folder per way; the app's models via `ERH_OLLAMA_MODELS`), then `erh grade --test` once per test in the `qwen` folder (the key's time and the checker's unsure count). The orchestrator reads the scratch databases and writes the comparison into step22.6-plan §5; nothing from them is committed except counts and printed test text. (c) The teacher picks the default from it. | Run it + read the results |

**Verifier notes (22.6.1–22.6.5):** 2026-10-30, fresh verifier, at 5a6d268 (`fe72e3c..HEAD`, 45 commits) plus aa49951 (the open-note test). S1 `TEST` 2254 passed, 14 deselected (the open-note test, added after collection, run on its own: 1 xfailed); S2 ruff clean, 311 files formatted, `mypy src` no issues in 113 files; S3 `wrote 39 schema files`, no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 vitest 59 files / 469 tests passed, lint and typecheck clean, `gen:types` no diff in `app/src/gen`; headless `E2E` 45 passed; clean tree afterwards. Verdict: 22.6.2–22.6.5 pass, 22.6.1 stays 🔄 for the one finding below. **22.6.1 🔄:** R22.6.1.2–3 pass (`test_step22_6_1.py`: the photo text loses its box; the typed prompt and hash equal the pre-change render); R22.6.1.1 is met for every case it lists, but the English heading rule (`domain/answer_box.py:30`, `_EN_HEADING` checks only that a digit or `:` comes next) drops a whole line that is not "followed by nothing but numbers": `Answer: 1. He goes to school` and `ANSWERS 5 points` both come back empty (probe, not committed); if OCR prints an example or a question as "Answer: 1. …" that line is lost before structuring (low). The 22.6.1 checklist boxes are not ticked (orchestrator). **22.6.2 ✅:** R22.6.2.1 `sure < blank_share * n` (7/36 blank, 8 not; 7/35, exactly 20%, is not blank, checked for n = 5…95), `???` counts, failed page never blank, pendings cleared; R22.6.2.2 `null`/` None `/`N/A` not read; R22.6.2.3 test-only thread (`test_step22_6_2.py`). **22.6.3 ✅:** R22.6.3.1–4 (`test_step22_6_3.py`, the replay, `step22_6_3.test.tsx`; schemas differ by `unsure` only). **22.6.4 ✅:** R22.6.4.1–8 (`test_step22_6_4.py` 20 tests incl. retried save, 409 kept for other runs, `erh run`/`eval` none; `step22_6_4.test.tsx`; `s17-key-run.spec.ts`, `s4-review.spec.ts`); the toast check fetches `/runs/{id}` per event (`useRunNotifications.ts`). **22.6.5 ✅:** R22.6.5.1–2, 4 (`test_step22_6_5.py`, `test_ocr_structure.py`, `test_ocr_format_page.py`, the eval flag); the way is chosen only under `task == transcribe_page`, no text layer and `ocr_on()` (`graphs/extract.py:1064–1094`), so typed and vision pages are unchanged by construction, but no test sets `photo_structure = "code"` on a vision or typed page (partly covered, low); R22.6.5.3 is a report on app data, not re-checked (no app data). **Scope:** every path is in §6 rows 22.6.1–22.6.6 or an orchestrator docs commit, and `.claude/` is the history move db59ab9; `app/src/App.tsx` and `components/AppShell.tsx` (7a40f49, 94b1bde) only pass the key-run hook to the Key tab and Grade button, not named in row 22.6.4 (b) (low). No teacher field, no `👤 sign-off:` commit, no `fixtures/` or cassette path. **§4 open note (medium, before this round):** `tests/unit/graphs/test_step22_6_6_open_note.py`, `xfail(strict=True)`: a test-text save deleting question 4 while the attempt's first grade run is stopped in `explain` queues no run (`followup_run_ids == []`, `domain/review.py:698` lists the graded attempts before the save, :830–835 queue runs only for them); the run then hits a version mismatch, `grade` reloads only the answers, not the content from `load_context` (`graphs/grade.py:620–627`), and saves `score_possible` 2.0 of the old test where the saved test totals 10. Also `_settle`'s `points_changed` is never set (`domain/review.py:794`), so "points_fix" runs are never queued from a text save (re-scoring is left to `save_content`).

**Verifier notes (re-check, R22.6.6.6):** 2026-10-31, fresh verifier, at bc97d83 (`3cb9410..HEAD`: 6c479b9, 316314a, 6ac8fa9, bc97d83). **R22.6.6.4 pass:** `_EN_HEADING` (`domain/answer_box.py:33`) now needs the rest of the line to be numbers with or without blanks; probes (not committed): `Answer: 1. He goes to school`, `ANSWERS 5 points`, `Answer the questions.`, `ANSWER 2024 exam`, `ANSWER: 1 A`, `ANSWERS (10 points)` stay; `ANSWER 17. ____ 18. ____`, `ANSWER`, `ANSWERS:`, `Answer: 5. ____ 6. ____`, `ANSWERS 1) 2)` go; a box after a heading with an empty line inside goes and stops at `II. Read`; a single `1. ____` stays, `1. ____ 2. ____` goes; `test_r22_6_6_4_*` passes. **22.6.1 pass:** R22.6.1.1 now holds for every case it lists (above, `test_answer_box.py`); R22.6.1.2–3 `test_step22_6_1.py` pass; R22.6.1.4 by S1–S7 below. **R22.6.6.5 pass:** `test_r22_6_6_5_typed_and_vision_pages_ignore_the_way` (code/ocr_format × typed/vision) compares the model calls with `"qwen"`'s, equal. **R22.6.6.3 pass:** grade `save` checks the stored content against `load_context`'s inside the same `BEGIN IMMEDIATE` transaction as its writes (`graphs/grade.py:360–367`, `store/db.py:194`), so a text save cannot slip between the check and the commit; `test_step22_6_6.py` (running, stopped + points-only change, queued) and `test_step22_6_6_open_note.py` pass, no `xfail` left; the key-only run (`attempt_id` None) takes the same check (the queued test's key run). `points_changed` is removed with a true reason: `save_test_text` calls `points.save_content`, which re-scores the graded attempts at once (`store/repos/points.py:98–105`), and `points_changed` was never set before, so no behaviour changed; the `fixed` tuple's run flag is now always False (dead, harmless). Holes found (none blocks R22.6.6.3): (1, low–medium) stale Review items survive the reload: `pending_reviews` has the append reducer `_merge_pendings` (`graphs/grade.py:155–166, 193`), so `load_context`'s `"pending_reviews": []` (:505) clears nothing; `save` drops only pendings for a question the test no longer has (:400–402). Scenario: `verify_key` disagrees on q2 (pending `uncertain_key:{run}:q2`), the teacher fixes q2's stem while the run is stopped, the reload drops the run's q2 key, a new key is made and verified → the old `uncertain_key` item (old key in its proposal) is still written, open, beside an `ai_verified` key. Same for `key_failed_reviews` of a question re-keyed after the reload. (2, low, existed before) the carried keys override the stored ones (`_carry_over`, :288): a teacher key set on an unchanged question while the run was stopped is not used for this grade (the guarded upsert keeps the teacher's row, but the verdicts were made with the AI key); before the fix the run never reloaded keys either. (3, low) after a reload with tags made by this run, a question added or changed by the edit gets no tag (`tag_skills` skips when `tags` is not empty, :636). (4, info) no cap on test-change reloads; each one needs a new teacher save and reloads the latest content, so it converges. **Docs mismatch (fix agent's report):** data-model v1.19/v1.19.1 is true: no code path queues `points_fix` (the only one, `_settle`, is removed; `_grade_test(…, "points_fix")` has no caller, `domain/review.py:172`; the `points_assumed` Fix re-scores through `save_content`, :417–451); llm-design §5 "Re-grade fan-out" (`points_fix` per graded attempt) and data-model §5.3 v1.9 text ("a `points_assumed` item becomes `fixed` … with the table's follow-up") are stale (low, docs only, not edited). **Scope:** every path in `3cb9410..HEAD` is in §6 row 22.6.6 "Fixes"; no teacher field, no `👤 sign-off:` commit, no `fixtures/` path. **S1–S7 at HEAD:** S1 `TEST` 2265 passed, 14 deselected (10:29, the open-note test included, no xfail); S2 ruff clean, 312 files formatted, `mypy src` no issues in 113 files; S3 `wrote 39 schema files`, no diff; S4 only `llm/defaults.py` (and its ignored `.pyc`); S5 exits 0; S6 `openapi.json` unchanged; S7 vitest 59 files / 469 tests passed, lint and typecheck clean, `gen:types` no diff; clean tree afterwards. **Headless `E2E` fails (medium, blocks R22.6.6.6 and checklist (a)):** full runs 43 passed + 1 failed + 1 did not run (twice), 45 passed (once); the failure is `e2e/s6-grade-review.spec.ts:281` R19.6 (`expect(align[from]).toBe(to)` at :310: a merge-preview row's `data-from` is not in the `possible_duplicate` item's `question_alignment`). The spec alone at HEAD: 4/3/4 passed of 4 (1 failed in 3 runs); with `sidecar/src` checked out at 3cb9410 (before the fixes, restored after): 4/4 passed in 4 runs. So the failure most likely comes with 6ac8fa9 (R22.6.6.3), not proven; cause not found (the after-extract key run and the new test check are the first suspects). **Verdict:** 22.6.1 ✅ (R22.6.1.1–4 pass; the E2E failure is not in 22.6.1's change); R22.6.6.3–5 pass their tests; R22.6.6.6 fails on headless `E2E`, so the 22.6.6 checklist (a) is not ticked.

**Verifier notes (final re-check, R22.6.6.6):** 2026-10-31, fresh verifier, at f936d9a (`703d9ab..HEAD`: f415f11, 156257c, b5b06dd, f936d9a). **R22.6.6.3 pass (holes 1–3 closed):** (1) `RESET_PENDINGS` (`graphs/grade.py:156`) as the first entry of an update makes `_merge_pendings` drop every earlier item (:160–173); `_carry_over` sends `[RESET_PENDINGS, *pendings of the kept keys]` (:311–317), so a stale `uncertain_key` of a changed question is no longer written. `key_failed_reviews` (:621) has no dedicated reload test but is covered by the same rule: its items refer to a question with no key, which is never in `key_writes`, so the reset drops them and the reloaded `ai_key_fast` makes them again for the questions still keyless (by reading). (2) `_carry_over` keeps the run's key only when `precedence(mine) >= precedence(stored)` (:300–309, `store/repos/keys.py:37`); an equal-rank stored AI key still yields to the run's. (3) on a `test_changed` reload `tag_skills` tags only `untagged()` questions (:326–335, :678–723), merging into the earlier tags and levels; `save` writes only the questions in `tag_levels` (:430–434); `save_test_text` clears a changed question's tags (`domain/review.py:710`), so it counts as untagged. No regression on a first grade: without a reload `todo` is None, so `tag_skills` tags every graded question when there are no tags and skips when there are (unchanged), `tag_levels` covers every tag so `save` writes all, and `weak_points`' new `q in fresh` filter (:847–851) keeps every question. `test_step22_6_6_reload.py` (2), `test_step22_6_6.py` (3), `test_step22_6_6_open_note.py` (1): 6 passed. **Merge preview pass:** `MergePreview.tsx` keeps a settled flag per fetch set in `finally` (not after an abort), shows `merge-loading` and no rows, no `merge-summary` / `data-aligned` until both are settled; a rejected fetch still settles; `MergePreview.test.tsx` covers survivor-first and a failed merged fetch. **Docs pass:** data-model v1.35 §5.2/§5.3 and llm-design v4.59 §5 match the code: the precedence rule, the pending reset, tagging only untagged questions; no path queues `points_fix` (the only `_grade_test` callers pass `"key_verified"`, `domain/review.py:282, 303, 499`); plan.md "Based on" = data-model v1.35, llm-design v4.59. **Scope:** every path in `703d9ab..HEAD` is in §6 row 22.6.6 (Fixes, Merge preview) or an orchestrator docs commit; no teacher field, no `👤 sign-off:` commit, no `fixtures/` path. **S1–S7 at HEAD:** S1 `TEST` 2267 passed, 14 deselected (12:56); S2 ruff clean, 313 files formatted, `mypy src` no issues in 113 files; S3 schema export no diff; S4 only `llm/defaults.py` (and its ignored `.pyc`); S5 exits 0; S6 `openapi.json` unchanged; S7 vitest 60 files / 471 tests passed, lint and typecheck clean, `gen:types` no diff; clean tree afterwards. **Headless `E2E` pass:** `s6-grade-review.spec.ts` alone 4/4, 4/4, 4/4; full `npm run e2e` 45 passed, 45 passed (after pytest, not at the same time). **Findings (none blocks):** (low) `load_context` does not reset `tag_levels` (`graphs/grade.py:528–550`): if this run tagged every question unsaved, another run then saved tags for the test, and a text edit leaves a question untagged, the reload's `tag_skills` returns `{**old tag_levels, **new}` (:720), so `save` rewrites every stored question's tags with this run's stale levels (the tags stay the stored ones; only the level column changes). (low, existed before, not 22.6.6) a later ordinary grade does not tag a question whose tags a text save cleared, since `tag_skills` runs once per test (llm-design §5 "skipped if question_tags exist"). (info) `MergePreview` sets the settled flags only at mount (:35–36), so a changed `item` on the same instance would show the old rows while refetching; it is re-mounted per item today. **Verdict:** 22.6.1–22.6.5 ✅, R22.6.6.3–6 pass; the 22.6.6 checklist (a) is ticked.

### Step 22.6.7 — The logo
**Depends on:** 22.6.6 · (was step 22.5.9 (b))

**Checklist**
- [x] (a) The app icon (exe, installer, taskbar, window) replaces step 14's placeholder; its design is the teacher's
      decision. Done 2026-11-02 (step22.6-plan D17): the teacher's light version (navy tile, lime E) is `icon.ico`
      (their own 16–256 px ICO) and `icon.png` (256 px, rendered from the SVG); all their files are in
      `app/src-tauri/icons/source/`. Checked by the 22.6.8 verifier and seen in the 0.6.1 build.

### Step 22.6.8 — Installer 0.6.1
**Depends on:** 22.6.7 · (was step 22.5.9 (c))

**Checklist**
- [x] (a) A fresh verifier of what changed after 22.6.6 (the default way, the logo), S1–S7, headless `E2E`.
- [x] (b) Version 0.6.1, `TAURI_BUILD`, the Defender scan and release notes 0.6.1 (what changed, the known limits
      updated), as in 22.5.8 (c)–(d); the user's `E2E_SHELL --release`.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.6.8.1 | (a) A fresh verifier checks what changed after the 22.6.6 verifier's last pass (`b8360b8..`): `photo_structure` defaults to `"code"` in `llm/config.py`, `llm/defaults.py` and `cli.py` (`erh eval --photo-structure` default), `qwen` and `ocr_format` still selectable, llm-design v4.60 agrees; the app icon is the teacher's light version (`icon.ico` holds 16–256 px, `icon.png` is RGBA and square, `tauri.conf.json` names both); S1–S7 hold; headless `E2E` passes. | `TEST` + `APP_TEST` + `E2E` |
| R22.6.8.2 | Every version string is 0.6.1 and the lock files agree; `erh --version` prints 0.6.1; `cargo test --lib` passes with no diff in `app/src-tauri/gen/`. | `TEST` |
| R22.6.8.3 | R21.1: `TAURI_BUILD` exits 0 and outputs `ETACH_0.6.1_x64-setup.exe`; `target/release/sidecar/erh.exe --version` prints 0.6.1 with one `erh-*.dist-info`. | Run it |
| R22.6.8.4 | R21.5: release notes 0.6.1 with sizes, the Defender scan of the installer, sidecar folder and shell exe, the changes of 22.6.1–22.6.7 (D1–D17), the known limits (2b's misses from step22.6-plan §3/§5), any migrations and the update steps; earlier sections unchanged. | Read the file |
| R22.6.8.5 | R21.2: `E2E_SHELL --release`, Settings shows 0.6.1, the new icon on the window and taskbar; started by the user. | `E2E_SHELL --release` |

**Verifier notes:** 2026-11-02, fresh verifier, R22.6.8.1 at 7fb5735 (`b8360b8..HEAD`, 9 commits, 19 paths). **Default way pass:** `DEFAULT_EXTRACT["photo_structure"] = "code"` (`llm/defaults.py:132`), the models.toml template and `ExtractConfig.photo_structure` (`llm/config.py:20, 143`, `Literal["qwen", "code", "ocr_format"]`), `erh eval --photo-structure` (`cli.py:860–868`, `default=None` falling back to `DEFAULT_EXTRACT` at :953, help names code as the default); llm-design v4.60 (changelog, config block :335, §4 :498) says the same, plan.md "Based on" names v4.60. The changed tests test the new default and would fail without it (by reading): `test_step22_6_5.py::test_r22_6_5_1_setting_default_and_values` asserts `"code"` for an empty config and that all three values parse; `test_eval_harness.py::test_r22_6_5_1_photo_structure_flag` asserts the preflight default `code` and `--photo-structure qwen` → `qwen`; `test_r22_5_7_7_ocr_run_mode_and_models_toml` expects mode `replay+ocr+code`; `test_extract.py::test_r22_5_7_7_empty_data_folder_reads_photos_with_ocr` queues no `TranscribeOut`, so with `qwen` as the default its `structure_text_page` call would find no response, and it asserts two `PlainText` calls on `glm-ocr` and no `TranscribeOut`. `qwen` stays tested through the harness that now pins `photo_structure = "qwen"` (`test_extract.py:278–280`, `hocr`, `test_r22_6_5_1_qwen_way_unchanged`), `ocr_format` through `test_ocr_format_page.py` / `test_step22_6_5.py`. **Icon pass:** `app/src-tauri/icons/icon.ico` is byte-equal to `icons/source/etach-icon-light.ico` (`cmp`); it holds 7 images, 16, 24, 32, 48, 64, 128, 256 px, each a 32-bit RGBA PNG entry inside its bounds (header parse in the scratchpad); `icon.png` is 256×256, 8-bit colour type 6 (RGBA); `tauri.conf.json:22` names `icons/icon.ico` and `icons/icon.png`; the four source SVGs hold only `rect`, `path` and one `linearGradient` (no `<script>`, `<text>`, `<image>`, `href` or external URL); the light SVG's tile is `#181a5c` with the lime E, as D17 says. **S1–S7 at HEAD:** S1 `TEST` 2267 passed, 14 deselected (10:33); S2 ruff clean, 313 files formatted, `mypy src` no issues in 113 files; S3 `wrote 39 schema files`, no diff; S4 only `llm/defaults.py` (and its ignored `.pyc`); S5 exits 0; S6 `openapi.json` unchanged; S7 vitest 60 files / 471 tests passed, lint and typecheck clean, `gen:types` no diff in `app/src/gen`. **Headless `E2E` pass:** 45 passed (2.1 min, after pytest, not at the same time); clean tree afterwards. **Scope:** the icons are in §6 row 22.6.7; docs, `.claude/docs/history/` and plan/structure edits are orchestrator commits; no `👤 sign-off:` commit, no `fixtures/` path, no teacher field. **Findings (none blocks):** (low, scope) 3c24613 changes `cli.py`, `llm/config.py`, `llm/defaults.py` and three tests; §6 row 22.6.6 does not name them (its entries are the merge preview, the fixes R22.6.6.3–5 and the verifier), they are named in row 22.6.5 and R22.6.8.1 and checklist 22.6.6 (c) ask for exactly this change. (low, docs) the module docstring of `sidecar/src/erh/eval/harness.py:18–19` still says `--photo-structure` has "default ``qwen``"; the CLI help and config say `code`. (low, missing check) no test pins the icon: `app/scripts/tauri-config.test.ts` checks the product name, CSP and window title but not `bundle.icon` or the ICO's sizes; `app/scripts/` is outside this verifier's write scope (§6 row 22.6.8 (a): tests under `sidecar/tests/` and `app/src/`), so none was added. (info) every ICO entry is PNG-compressed, including 16–128 px; Windows Vista and later read these, R22.6.8.5 shows them on the window and taskbar. **Verdict:** R22.6.8.1 passes; 22.6.8 checklist (a) ticked, tracker row 22.6.7 ✅, row 22.6.8 🔄 until (b) (R22.6.8.2–5).

**Build and release checks (orchestrator, 2026-11-02):** the verifier's low findings fixed in eb1491b: (1) §6 row
22.6.6 now names the default-way paths (structure v1.1.155); (2) the `eval/harness.py` docstring says the default is
`code`; (3) `app/scripts/tauri-config.test.ts` checks the icon (`bundle.icon`, `icon.ico` equal to the teacher's light
ICO with 16–256 px, `icon.png` square RGBA; 14 tests pass). R22.6.8.2: every version string 0.6.1 (47b4eea, the same
11 files as 0.6.0's bump), `uv lock --check` ok, `erh --version` 0.6.1, version tests (sidecar 9, app 46 in the
first-run, settings and scripts files) and `cargo test --lib` (17) pass, S6 no diff, no diff in `app/src-tauri/gen/`.
R22.6.8.3: `TAURI_BUILD` from 47b4eea exit 0, `ETACH_0.6.1_x64-setup.exe` (44,847,430 bytes); frozen `erh.exe
--version` 0.6.1 with one `erh-0.6.1.dist-info`, 177 files (0.6.0's 175 plus the two new prompt files). R22.6.8.4:
release notes 0.6.1 (Defender 1.463.83.0: no threats in the installer, the sidecar folder or `ETACH.exe`). Not
re-checked by a fresh verifier (the teacher: "re run only the ones needs rerun").

**Rebuild after D18 (orchestrator, 2026-11-02):** the teacher saw the navy logo on a dark title bar (Windows dark
theme); the main window now asks for a light frame (abe9150, a check in `tauri-config.test.ts`, 15 tests pass;
`cargo check` and `cargo test --lib` (17) pass). `TAURI_BUILD` from abe9150 exit 0, `ETACH_0.6.1_x64-setup.exe`
(44,837,947 bytes); frozen `erh.exe --version` 0.6.1, 177 files; Defender 1.463.83.0: no threats in the installer,
the sidecar folder or `ETACH.exe`; release notes updated. The first `E2E_SHELL --release` (on the build before D18)
stopped before the app opened (blank page, WebView2 156.0.4314.58 against `msedgedriver` 156.0.4314.50); R22.6.8.5
is run on this build.

**R22.6.8.5 E2E_SHELL on the 0.6.1 build after D18** run 2026-11-02 by the user (`cd app && npm run e2e:shell --
--release`, exe `ETACH.exe`), after replacing `D:\DevTools\msedgedriver\msedgedriver.exe` with Microsoft's
156.0.4314.58 to match WebView2 (the old one kept as `msedgedriver-156.0.4314.50.exe`): every check PASS,
"E2E_SHELL: all passed"; Settings shows 0.6.1 = `erh --version` (source and frozen); R15.2 real drop; R14.5 nothing
new in %APPDATA%/%LOCALAPPDATA%; R20.7 moved-folder checks pass. No app change.

---

## Step 22 — Offline check & acceptance 👤
**Depends on:** 21, 22.6.8 · **PRD:** §12, §13 Phase 4, S1–S7, D23

**Checklist**
- [ ] **Offline check:** a Windows Firewall rule blocks and logs all outbound traffic except loopback; run S1 with the installed build; export the log to `docs/initial-plan/phases-testing/offline-check.txt`.
- [ ] `powercfg /requests` captured during a run (it shows the keep-awake request) → added to `docs/initial-plan/phases-testing/offline-check.txt`.
- [ ] **Acceptance:** S1–S7 on real papers (not tuning fixtures), with the installed build, network blocked. Record for each scenario: result, time to extraction, time to grade, unsure count, issues.
- [ ] `docs/initial-plan/phases-testing/acceptance-report.md`, signed off by the teacher.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R22.1 | The firewall log in `docs/initial-plan/phases-testing/offline-check.txt` has 0 dropped outbound entries from the app's processes (erh, ollama, the app exe) during the S1 run; the `powercfg /requests` capture lists the app under SYSTEM. Added with `👤 sign-off:`. | Read + `git log --grep` |
| R22.2 | The acceptance report lists S1–S7, each **pass**, or **pass-with-deferral** with the plan items the teacher accepted. Signed off with `👤 sign-off:`. | Read + `git log --grep` |
| R22.3 | Every deferral appears as a step 22.1 sub-step in this plan, or as a step in a post-launch plan file (see Scope). | Read the plan and the post-launch plan file |
| R22.4 | Every tracker row above is ✅ or ⚠ with a commit hash. | Read the tracker |

**Verifier notes:** –

---

## M1 — Extraction quality track 👤
**Depends on:** 11 · **Gates:** 21 · **PRD:** §12, D7, D20, R1, R2 · llm-design §9 Q3–Q5

**Checklist**
- [x] Start the 30+ fixture set (PRD §13 Phase 1) — 14 tuning + 5 held-out; a key photo and boxes on other pages waived (`docs/initial-plan/waivers/M1.md` items 5–6): **at least 10 tuning + 5 held-out**, all 👤 signed off. Cover printed-only blank tests, inline answers, answer-box answers, boxes on other pages, a key photo, rotated photos, a PDF and a DOCX. In `expected.json`, text that cannot be read on the paper is written `???` (PRD D25).
- [x] Tune the prompts and profiles on tuning only; decide full page vs half-page tiles — p1 + p2 (minimal M1); tiles off.
- [x] Fit the reading-unsure threshold, the key-photo threshold and the similarity thresholds on tuning — defaults kept; key photo and similarity waived (items 8–10).
- [ ] Try the teacher's candidate vision models (`--role vision=<tag>`) — waived (item 7), after step 22.
- [x] `docs/initial-plan/phases-testing/m1-report.md`: held-out metrics vs PRD §12, speed / VRAM / tokens per node, the thresholds, the tiles decision, the chosen vision model.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R-M1.1 | `MANIFEST.sha256` lists ≥ 10 tuning and ≥ 5 held-out fixtures, all `verified_by: teacher`, added by `👤 sign-off:` commits. | Read + `git log --grep` |
| R-M1.2 | The report states every llm-design §8 extraction metric on **held-out**, citing `eval-history.csv` row numbers that exist in the committed CSV. | Read + CSV |
| R-M1.3 | The PRD §12 goals are met on held-out, **or** `docs/initial-plan/waivers/M1.md` is signed off (→ ⚠). | Read |
| R-M1.4 | The report contains `Decision: tiles=<off\|full\|half>` and `Decision: vision=<tag>`, and the thresholds; the config defaults equal them (checked again in R21.4). | Read + compare |

**Verifier notes:** –

**R22.2.7.5 E2E_SHELL** run 2026-10-15 by the user (`cd app && npm run e2e:shell -- --release`, after the warning) on the release build from a007c60: 20 PASS, "E2E_SHELL: all passed"; `erh --version: source 0.3.0; frozen 0.3.0`; "R21.2 Settings shows the sidecar version \"0.3.0\" = erh --version \"0.3.0\""; R14.5 nothing new in %APPDATA%/%LOCALAPPDATA%; R20.7 moved-folder checks pass. The orchestrator read the output. ✅

Baseline fixes (`step/M1-fix-docx-text-page`), 2026-10-08, 8f12575: pass (M1 itself is not finished). S1 `TEST` 1171 passed, 14 deselected (live); S2 ruff clean, 196 files formatted, `mypy src` no issues in 86 files; S3 `wrote 42 schema files`, no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 vitest 113 passed (16 files), lint and typecheck clean, `gen:types` no diff in `app/src/gen`; headless `npm run e2e` 19 passed; clean tree afterwards. Against the pre-fix code (a worktree with `pages.py`/`extract.py` from `step/M1-extraction-quality`): the DOCX replay fails with the baseline's `ValueError: … text/plain; charset=utf-8, not an image`, and both text-only unit tests fail; with only the `pages.py` fix, the replay and the unit test fail on the missing text in `read_answers_page`; with `extract.py` at 88371f2 (no `retranscribe_tiles` guard), the no-tiles test fails. Both `key_accuracy` tests fail against the pre-fix `harness.py` (`key_n` 2 instead of 0, and 4 instead of 2). The tests assert behaviour: no image ops and no `target_size`, no derived files, the text marker in each request and no `images`, one `TranscribeOut` call and one `validator_failed`, blank `key_accuracy` with `key_n` 0. Regression: a verifier scratch test (deleted afterwards) shows that an image page with a PDF text layer still sends its image, not its text, to `read_answers_page`; the unit test keeps rotate + resize on such a page; `key_accuracy` is still counted for a fixture with a key page. Downstream of `prepare_pages`, `read_header`, `transcribe_page` and `read_key_pages` already send text when a page has a text layer; the grade graphs send no page images. Only the parked §7 item remains: picture refs and the Review image point at the text file. Scope: every non-orchestrator path is in §6 row M1/M2 (v1.1.47); `eval-history.csv` (5 lines), `prompts/` and `fixtures/` are unchanged; the `docx-text/` scenario is synthetic (placeholder name `Học Sinh A`, no pictures, no image data); no teacher field and no sign-off commit.

Answer-prompt fix B1 + B4 (`step/M1-fix-answer-prompt`), 2026-10-08, 1d851ef: pass (M1 itself is not finished). S1 `TEST` 1189 passed, 14 deselected (live); S2 ruff clean, 196 files formatted, `mypy src` no issues in 86 files; S3 no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 vitest 113 passed (16 files), lint and typecheck clean, `gen:types` no diff in `app/src/gen`; `e2e:shell` not run; clean tree afterwards. Size, measured with `schema_to_template` and `model_json_schema` (template / `format` characters): 40 questions 11 741 / 24 049, 80 questions 23 389 / 47 609 (×1.99 / ×1.98); the pre-fix code gives 48 901 / 46 289 and 174 509 / 136 889 (×3.57 / ×2.96). Against the pre-fix code (a worktree at `step/M1-extraction-quality` with the new tests copied in) 17 new tests fail: the linear-size and plain-string schema tests, the 7 `alt_question_id` cases in `test_boxes.py`, the 4 truncation tests (size bound, `truncate: false`, low `prompt_eval_count`, before the call, Ollama context error), the graph test and both `--keep` tests. The tests assert behaviour: an invalid ID (unknown, own, template word, blank, writing question) gives None with no cap, a valid one is stripped and caps at threshold − 0.01; each truncation path gives a `prompt_truncated:` `CallFailure`, 1 request at most and an `error` row; the graph case ends `done`, with `answers_failed` [1], `validator_failed:<run>:answers:1`, every answer None and unsure, and 1 `ReadAnswersCall`; `--keep` writes `llm_calls.json`, `pages.json` and `call_status`. `truncate: false` is set in `OllamaClient.call` after `build_request`, so both adapters' sent and stored bodies carry it; no other code path posts `/api/chat`. False positives: replay reports `prompt_eval_count` 0, so the check is skipped; an instrumented `erh run --replay s1` shows `read_answers_page` at 16 034 characters + 1 image (ceiling 12 113 < 16 384, not even checked) and `transcribe_page` at 4 403. A larger test that is checked trips only if Ollama reads fewer tokens than characters ÷ 8, while a complete prompt counts about 1 915 image tokens + characters ÷ 4, so a full prompt cannot trip it. The before-call bound needs more than about 129k characters for 1 image. Scope: every non-orchestrator path is in §6 row M1/M2 (v1.1.50); `prompts/`, `llm/defaults.py`, cassettes, `fixtures/` and `eval-history.csv` are unchanged; no teacher field and no sign-off commit. Worth a look: the post-call check assumes that `prompt_eval_count` counts the whole prompt, including tokens reused from Ollama's KV cache. Consecutive pages share the template prefix. If a future Ollama counted only the new tokens, large tests could trip it; the first live M1 run's `call_status` will show this.

Speed bundle 1 (`step/M1-speed-bundle1`), 2026-10-10, 7fececb: pass (M1 itself is not finished). S1 `TEST` 1245 passed, 14 deselected (live), no skips; S2 ruff clean, 197 files formatted, `mypy src` no issues in 86 files; S3 and S6 no diff; S4 only `llm/defaults.py`; S5 exits 0; S7 vitest 113 passed (16 files), lint and typecheck clean, `gen:types` no diff; `e2e:shell` not run; clean tree afterwards. Tests read against each item: tiles off → no tile step or call, one `validator_failed` (task `transcribe_page`); `--tiles` and "better" (a no-better tile reading keeps the first pass) and "always" (the old rule); a PDF text-layer page makes no tile call; the tile log `p2 top`…`p3 bottom` in `request.item` and `llm_calls.json`, never sent; a capped vision output → `output_capped` with one call, a capped reasoning output still retries, an uncapped invalid output still retries once; `--only` (repeatable, comma list, unknown name → exit 2 and no row). Revert: a verifier replay of every runnable extract cassette with `retranscribe_tiles = true`, `keep = "always"` and `retry_capped_output.vision = true` passes, `blank` included (it fails with the defaults, as expected); the old settings for `blank`/`validator-retry` are set only in the tests, the defaults are off/"better"/vision false; `s1-grade` replays with the defaults. Script on replay (synthetic fixtures under the mini-test names, temp output and history): a failing check prints CHECK FAILED, exits 3, makes no batch folder and adds no row; `-Mini -CompareTo` writes `CHECK.md` with the differences; `-Runs` defaults to 1; no `&&`, `??` or ternary. Scope: every non-orchestrator path is in §6 row M1/M2 (v1.1.55); no prompt, cassette, `fixtures/` or `eval-history.csv` change; no `num_ctx`, temperature or seed change; no teacher field. The `item=` argument of `client.call` is fine: a log label in the stored request only, outside `prompt_hash`, not sent. Worth a look (low): (1) §6 says `llm/config.py` + `defaults.py` hold "the switch's setting only", but they also hold `[client] retry_capped_output` (documented in llm-design v4.14 §3.1); the row's wording could name it. (2) The check counts a capped call by `tokens_out ≥ num_predict` (rows keep no `done_reason`), and its `prompt_truncated`/`output_capped` status tests never match a row status; truncation is still caught as `error`.

**Long-DOCX fix (orchestrator, 2026-10-10):** branch `step/M1-fix-long-text-page` (eff4a4e, 0b61792, da462aa). Three verifications: the first failed (Roman statement lists inside a question counted as headings; fixed in 0b61792 with NFC and "never break inside a question"), the second failed ("A:"/"A -" option labels; fixed in da462aa), the third found no question cut in 1132 probes, S1 1218 passed, S2/S3/S5/S6 clean, no cassette changed, the real DOCX splits into 4 pages at question starts (5322/5965/5768/1585), and two rare edge cases, parked in structure §7 (v1.1.54). The orchestrator accepted the branch on that basis rather than run a fourth round.

D26 typed files skip answer reading (`step/M1-skip-digital-answers`), 2026-10-10, 4f5fac1 + 09808f2: pass (M1 itself is not finished). S1 `TEST` 1255 passed, 14 deselected; S2 ruff clean, 197 files formatted, `mypy src` no issues in 86 files; S3 and S6 no diff; S4 only `llm/defaults.py`; S5 exits 0; S7 vitest 113 passed (16 files), lint and typecheck clean, `gen:types` no diff; `e2e:shell` not run. Real fixtures (counts only): the 7 PDFs (4/4 pages each; largest image cover 0.08–0.24) and the DOCX (4/4) are born-digital and skip; the 6 photo papers have 0 and read answers. The tests cover each case in the rule; the DOCX replay and text-only test expectations changed only for D26; no cassette, prompt, model option, `fixtures/` or teacher field changed; every path is in §6 "D26". Worth a look (low): a scan whose image covers < 0.8 of its page (for example, placed with margins) **and** that has an OCR layer counts as typed, and the `fraction=0.7` test asserts this. Phone and scanner apps make page-sized images, and the real typed PDFs stay at ≤ 0.24, so a lower threshold such as 0.5 would leave more room.

Verifier notes (p1 question types, `step/M1-p1-types`), 2026-10-10, cabfa66: pass (M1 itself is not finished). S1 `TEST` 1258 passed, 14 deselected (live); S2 ruff clean, 198 files formatted, `mypy src` no issues in 86 files; S3 `wrote 42 schema files`, no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 not run (no `app/` change); clean tree afterwards. Prompt: every type and skill named in the new rules is a `QuestionType`/`SectionSkill` value; all 11 types except `verb_form` are defined (kept in the enum, not offered, per the teacher's decision); printed lettered options → `mcq` incl. "A. True / B. False"; the diff adds only the type and skill rules (no passage, heading or stem rule). `retranscribe_tiles` calls the `transcribe_page` prompt, so there is no second copy. Fixtures: no `verb_form` in any `fixtures/tuning/*/expected.json`; in `lop8-hk1-de1`, `L9-T23-book-lop9-50de`, `L8-GK2-DG-2025-photo` the bracketed verb cues (consume, persuade, cure, create, apply) are `word_form`, the separate MCQ sections are `mixed`, the dictionary-entry gap sections `vocabulary`, the passages `reading`, and True/False without options is `true_false`; `L12-TS12-D1-2025-docx` is all `mcq` with `reading` sections. `test_types_prompt.py` fails if a type is dropped or a non-enum value is named (subset checks both ways). Script (offline, functions extracted, read-only): the default reference resolves to `2026-10-10T18-05-baseline3` (`-baseline3-check` excluded); `Get-RefMetricsPath` reads all 3 mini papers from baseline3 (`run-1` layout) and from `2026-10-10T17-00-d26-check` (check layout) with all 5 metrics; the script parses with 0 errors. Scope: the 4 files are in §6 row M1/M2 (v1.1.60, prompt tuning); no `fixtures/`, cassette or `eval-history.csv` change; no teacher field. Worth a look (low): the skill test pins only `reading`, `vocabulary` and `mixed`, so dropping another skill line would not fail it.

Verifier notes (p2 passages into stimulus, `step/M1-p2-stimulus`), 2026-10-10, 3571c94: pass (M1 itself is not finished). S1 `TEST` 1262 passed, 14 deselected (live); S2 ruff clean, 199 files formatted, `mypy src` no issues in 86 files; S3 `wrote 42 schema files`, no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 not run (no `app/` change); clean tree afterwards. Scope: `d5ec570..HEAD` without structure.md touches only `transcribe_page.md`, the new `test_stimulus_prompt.py` and `test_docx_text_replay.py`, all in §6 row M1/M2 (v1.1.63, prompt tuning incl. length-only replay fixes); no `fixtures/`, cassette, `eval-history.csv` or `app/` change; no teacher field. Prompt: the type and skill block is unchanged; the diff adds only the Passages rule and moves the dictionary out of Pictures (no heading, page-continuation, rewrite or word-form stem rule); its examples are generic, no fixture text. Fixtures agree: `L8-GK2-DL-2025-photo`, `L9-TS10-D4-2025-pdf`, `L9-T29-book-lop9-50de` cloze stimuli use `(17) ____` with `stem` null; reading T/F and MCQ keep printed stems (`L9-T29`, `L9-TS10-D4`); `L9-T29` brochure starts `**WELCOME TO THE HEART OF URBAN LIVING!**`; both dictionary groups hold headword, level, pronunciation, senses and "• " examples in the stimulus, plus a picture, with only the numbered gaps as questions. data-model §2 (`stimulus` cloze blanks "(17) ____", `stem` None for cloze) agrees. Tests: each new assert pins a key phrase, so removing a rule fails it. Replay test: the user message is exactly the page text (5873/4786/1462 chars); the whole DOCX is 12123 chars, so an unsplit DOCX fails the `MAX_TEXT_PAGE_CHARS + 1000` bound; the new bound is tighter on the page text than the old one (+6000 over all messages). Size: `transcribe_page.md` 3632 → 4847 chars (+1215, about 300 tokens); the largest long-DOCX request is 17271 chars of JSON (~5k tokens at ~3.5 chars/token) + `num_predict` 8192 ≈ 13k of `num_ctx` 16384, margin about 3k tokens; `prompt_truncated` still guards the worst case. Worth a look (low): the tests do not pin "keep their own printed sentence as the `stem`" for reading questions, nor the dictionary picture region.

Verifier notes (M1 listening safety net, `step/M1-listening-guard`), 2026-10-11, b3ba5fc + 00c695c: pass (M1 itself is not finished). S1 `TEST` 1269 passed, 14 deselected; S2 ruff clean, 200 files formatted, `mypy src` no issues in 86 files; S3 `wrote 42 schema files`, no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 not run (no `app/` change); clean tree afterwards. Scope: `e604274..HEAD` touches only `domain/renumber.py`, `test_renumber.py`, the new `tests/replay/test_listening_rescue.py`, `llm-design.md` and plan.md, all in §6 row M1/M2 (v1.1.64, listening safety net); no prompt, cassette, `fixtures/`, `eval-history.csv` or `app/` change; no teacher field. Code: the rescue branch runs before the old listening branch, so a heading-only listening section (no questions, or only blank stems and no options) takes the unchanged omit path with its range and points; writing is untouched. A rescued section is stored as graded and numbered with the other stored sections; its printed points count in `points_possible`. The key `validator_failed:<ref>:listening:<page_no>` cannot clash with the transcribe key (`...:transcribe:<page_no>`), and `merge_pendings` is replaced each pass, so a stale item does not survive a later pass. `review.py::_validator_failed` reads only the resolution value (Accept → no change, no run), and the Review UI reads only `task`, `failures[].message/validator` and `call_failure`, all present. The replay test asserts the saved test (4 questions, section graded, no omitted sections) and one open item on that test. Against the old `renumber.py` (e604274) 6 of the 7 new tests fail; the heading-only test passes, as a regression guard should. Real case (baseline4 `pages.json`, offline, old → new): `L8-HK1-NHT-D4-2025-photo` 12 → 28 questions, omitted 1 → 0, `points_possible` 3.0 → 4.0, one pending `validator_failed` for page 1. The other 13 tuning papers are identical old vs new, including the genuine listening papers `L8-HK1-NHT-D6-2026-photo` (2 omitted) and `lop8-hk1-de1` (1 omitted): no false trigger. Worth a look (low): no unit test puts a rescued section between two others; numbering is uniform over the stored sections, so the risk is small.

Verifier notes (M1 milestone, 2026-10-11), at 98d50ec: ⚠ waived (R-M1.3 passes through the signed waiver). R-M1.1 pass: `MANIFEST.sha256` lists 14 tuning + 5 held-out, all `verified_by: teacher`; `manifest_lines(fixtures/)` recomputed read-only equals the committed manifest line for line (hashes and `verified_by`); the manifest was changed only by `👤 sign-off:` commits (938c954, bae4d97, 8f2b2b0, 0e8e8a3). R-M1.2 pass: the report's §1 lists every llm-design §8 extraction metric (CER and structure incl. counts, types, options, blanks, underline, bold; answer accuracy; calibration with interval; key and key-mapping accuracy, blank with `key_n` 0; verdict/score marked as M2; tokens, time, VRAM per node in §3) and cites row 9 (`set=heldout`, commit 6dd2d47) of the 9-line committed `eval-history.csv`; spot checks equal the CSV: CER 0.3916, structure 0.6664, answer accuracy 0.8367 (n 196), calibration 0.2500 (0.1325–0.4211, 32 wrong), wall 1892.0 s, VRAM 4357 MB, 29 calls, tokens 113 837 / 26 311, per-node `transcribe_page` 21 calls / 1177.4 s and `read_answers_page` 8 calls / 700.9 s. R-M1.3 pass via waiver: the PRD §12 goals marked "not met" or "not measured" (printed transcription, answer reading, calibration, key after verification) are waiver items 1–4; stop/resume is covered by Phase 0 and the fixture count is "30+ over time"; all 10 items have a filled "Accepted by teacher" line and the signature block is filled; `docs/initial-plan/waivers/M1.md` history is c17faa0 (agent draft) then 6f65007 and 98d50ec, both `👤 sign-off:` touching only the waiver. R-M1.4 pass: `Decision: tiles=off` = `DEFAULT_EXTRACT["retranscribe_tiles"] = False`; `Decision: vision=numind/nuextract3:Q6_K` = `DEFAULT_ROLES["vision"]["model"]`; the threshold table equals `ExtractThresholds` (reading 0.7, key_photo 0.7, looks_like = `LOOKS_LIKE` 0.85, possibly = `POSSIBLY` 0.5, sanity 0.5). Checklist: tiles decided and report written; the prompts tuned on tuning (p1, p2); `reading` fitted and kept at 0.7 (waiver 10); the key-photo fixture, answer boxes on another page, the vision-model trial, the key-photo threshold and similarity fitting on true duplicates are waiver items 5–9. The `???` convention (D25) inside `expected.json` was not read (student text). S1 `TEST` 1269 passed, 14 deselected; S2 ruff clean, 200 files formatted, `mypy src` no issues in 86 files; S3 `wrote 42 schema files`, no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 not run (`git diff --stat 41209fd..HEAD -- app` is empty); clean tree afterwards. No teacher field written; checklist boxes left for the orchestrator.

## M2 — Reasoning model choice track 👤
**Depends on:** 11, 18 · **Gates:** 21 · **PRD:** D7, R3, §12 · llm-design §9 Q6

**Checklist**
- [ ] `erh eval --graph grade` metrics: key accuracy (fast / verified), judge accuracy, verdict accuracy, exact score match, speed / VRAM / tokens per node.
- [ ] Add grade expectations to the fixtures (👤).
- [x] Run the teacher's candidate small models + the `qwen3.5:4b` placeholder.
- [x] A blind rating sheet via `erh eval --rate-explanations`, filled in by the teacher (👤).
- [x] `docs/initial-plan/phases-testing/m2-report.md` with the choice; bump llm-design if the default changes.

**Requirements**
| ID | Requirement | Check |
|---|---|---|
| R-M2.1 | The report compares ≥ 2 reasoning models on held-out for every metric above, citing existing `eval-history.csv` rows. | Read + CSV |
| R-M2.2 | The blind ratings and `Decision: reasoning=<tag>` are in the report, signed off with `👤 sign-off:`. | Read + `git log --grep` |
| R-M2.3 | If the choice ≠ the placeholder, llm-design has a changelog row and the plan's "Based on" line is updated. | Compare |

Verifier notes (M2 grade eval, `step/M2-grade-eval`), 2026-10-11, 7cf731d..cff2b57 (+ 2f63c03 docs): pass (M2 itself is not finished; checklist and tracker untouched). S1 `TEST` 1290 passed, 14 deselected; S2 ruff clean, 205 files formatted, `mypy src` no issues in 88 files; S3 `wrote 42 schema files`, no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 not run (no `app/` change); clean tree afterwards. Scope: `4625f14..cff2b57` touches only `eval/{grade,ratings,metrics,harness,fixtures}.py`, the `eval` parser in `cli.py`, `eval-history.csv`, `m1-overnight.ps1`, the runbook, `tests/unit/eval/`, `tests/fixtures_synth/grade/` and `tests/cassettes/grade-eval/`, all in §6 row M1/M2 (M2 grade eval); no `graphs/`, `prompts/`, `llm/` or `fixtures/` change; the only `verified_by` is `null` in the synthetic `expected.json`. CSV: the old 97-column header is a prefix of the new 145-column one (48 appended: 8 grade metrics + 40 usage columns for the 10 grade-only nodes); all 8 old data rows keep every cell and gained only empty trailing cells. Code: the key run seeds no key (`with_key=False`) and the verdict run seeds the expected key as `teacher_edit`/`teacher_verified`, each in its own folder (`f<i>/key`, `f<i>/verdict`); truth is `scoring.grade` on the expected key + answers with the teacher `verdicts` overriding; `key_accuracy_fast` = strict set equality over expected keys, `key_accuracy` the same minus `ai_uncertain`; `verdict_accuracy` over answered questions with a truth (`?`/ungraded = miss); `judge_accuracy` over the true-key `to_judge` questions only; `score_exact_match` per fixture with a complete truth; usage from the key run; `--role reasoning=` reaches the run's `models.toml` and every grading task uses the reasoning role. Rating sheet: columns item/fixture(set/name)/question/text/answers/explanation/rating/note, BOM, seeded shuffle, model tags only in `rating-key.json`; `score-ratings` prints tags and counts only; `erh eval` stdout prints counts and the model tag only. Tests: breaking the key run (`with_key=True`), dropping the `ai_uncertain` rule in `grade_key_counts`, removing the shuffle, and dropping the teacher override each fail 1–3 tests. `--list-verdicts` on held-out (no model): needs-verdict 4 in total — `L8-HK1-NHT-D2-2025-photo` 4 items (36 answered, 32 truths from the rules), the other 4 papers 0 (no answers; 40 keyed questions each). Script: parses in PowerShell 5.1 with 0 errors; `-Graph grade -Reasoning <tag>` gives `eval --graph grade --set <set> --role reasoning=<tag>`; no `&&`/`??`/ternary; extract options unchanged; runbook commands match the CLI. Worth a look (medium, outside this branch's scope): `verify_key` and `judge_rewrites` are sent with `think=True` (`llm/tasks.py` `GRADING_THINK`), and nothing handles a model without thinking support; a candidate such as `gemma3:4b` may have those calls rejected by Ollama, which would deflate `key_accuracy`/`judge_accuracy` rather than measure the model — a short live check per candidate before the full run would show it. Worth a look (low): `score_exact_match` and `judge_accuracy` stay empty until the 4 teacher verdicts are in `expected.json`; `--seed 0` falls back to the default seed; a rating of `nan`/`inf` raises a traceback instead of a `RatingError`.

Verifier notes (M2 think off + explain prompt, `step/M2-think-off` and `step/M2-explain-prompt`), 2026-10-12, f68b0bc (+ 6fd5fa2 docs) and 035f12a, 7d36896 (+ ddc7f77 docs): pass on the tip, with one medium item for the think-off branch alone (M2 itself is not finished; checklist and tracker untouched). S1 `TEST` 1299 passed, 14 deselected; S2 ruff clean, 205 files formatted, `mypy src` no issues in 88 files; S3 no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 not run (no `app/` change); clean tree afterwards. Scope: the implementer commits touch only `llm/tasks.py`, `llm/defaults.py` (a comment), `prompts/base/explain.md`, `tests/unit/prompts/test_grading_prompts.py` and `tests/unit/eval/test_eval_grade.py`, all in §6 row M1/M2 (v1.1.72: M2 think off, M2 explain prompt; M2 grade eval for `tests/unit/eval/`); no `fixtures/`, cassette, model option, other prompt or `graphs/` change; no teacher field. Think off: no task in `TASKS` has `think` true; caps unchanged (verify_key 1500, judge_rewrites 400, explain 512; extraction tasks as before); `build_request` for verify_key, judge_rewrites and explain gives `"think": false`, also with a `models.toml` that sets `roles.reasoning.think = true`, because `graphs/grade.py:423` passes `think=spec.think` (always a bool), so `role.think` (`adapters/__init__.py:156`) is never used for a grading call. Explain prompt: the five rating points are each a rule (vocabulary first with key word, sentence meaning, one short why, word form after meaning; no restating; tone for grade 8–10, not childish, no clinical wording; the rule or formula for grammar points; stay on the actual mistake); D5 kept (Vietnamese, English terms and examples); the output contract is unchanged (`text_vi`, the 5 `error_type` values of `ErrorType`, `ExplainOut`); the length rule keeps the D.3 phrase "at most 3 sentences" and adds one short key-word gloss, matching llm-design v4.17.1 §5. Compared with the teacher's notes in the rating sheet (meaning only), every note is covered, including the "real Vietnamese words" point. Size: the system prompt is 2504 chars; a request with a ~1.8k-char synthetic question is 5.1k chars of JSON (~1.7k tokens) + `num_predict` 512, far below `num_ctx` 16384. Tests are real: deleting the vocabulary-first rule fails 2 tests; setting `GRADING_THINK` to `{"verify_key"}` fails `test_r17_2_4_thinking_off_for_every_task`. Revertibility: reverting 035f12a alone on the tip gives 1290 passed, 14 deselected. **Worth a look (medium):** `step/M2-think-off` alone fails S1 (1289 passed, 1 failed: `test_committed_history_has_the_new_header`). The failure is older than this work: base 1d5cacb fails it too, since the M2 grade rows were committed to `eval-history.csv` (8f1c1b0); the fix is 7d36896, which sits on the explain branch. If the teacher keeps think off but drops the explain change, 7d36896 has to move to the think-off branch (or be cherry-picked); the GPU run itself is not affected. Worth a look (low): two formula examples in `explain.md` ("so as to + V0", "-ed/-ing") come from the teacher's notes on rated tuning items, and the example word also occurs in one tuning paper's key; they are generic (no student text), but a later rating of those same items may be slightly favoured. The rule "then the meaning of the sentence" sits next to "do not quote the whole correct sentence"; it reads as a Vietnamese meaning, but a small model may quote the English sentence. `ExplainOut.text_vi`'s comment "at most 3 sentences" (`domain/llm_schemas.py:336`) does not mention the gloss (comment only, outside this scope).

Verifier notes (M2 explain prompt 2, `step/M2-explain-prompt-2`), 2026-10-12, 3d64ee4 (+ 541d4f8 docs): pass (M2 itself is not finished; checklist and tracker untouched). S1 `TEST` 1303 passed, 14 deselected; S2 ruff clean, 205 files formatted, `mypy src` no issues in 88 files; S3 no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 not run (no `app/` change); clean tree afterwards. Scope: the implementer commits touch only `prompts/base/explain.md`, `tests/unit/prompts/test_grading_prompts.py`, `docs/llm-design.md` (v4.17.2), plan.md's version and "Based on" line, and the `ExplainOut.text_vi` comment, all in §6 row M1/M2 (v1.1.73: M2 explain prompt 2); no `llm/`, `graphs/`, cassette or `fixtures/` change; output contract, `explain` cap 512 and `GRADING_THINK` (empty) unchanged. Prompt: each of the teacher's re-rating notes is a rule (gloss every deciding word incl. multi-word terms; the other speaker's sentence first in a dialogue; the rule's Vietnamese meaning; a closing "Nghĩa: …" line for rewrites and sentence building; the answer's meaning; simpler everyday words; no wordy closing; why this word class; -ed/-ing changes the meaning); the earlier rules stay; D.3 phrases present. Length (≤ 3 sentences + glosses + one meaning line, about 70 words) is coherent and well under the 512 cap. Examples: none of the prompt's example words or phrases occurs in the files of `L8-GK2-DG-2025-photo` or `L8-HK1-NHT-D4-2025-photo` (grep); the earlier two examples are gone. Tests are real: dropping the multi-word clause and adding a banned phrase fails 3 tests. Cache: each `erh eval --graph grade` run grades in a new temporary folder with a fresh database (`eval/grade.py:812`, `f<i>/key` and `f<i>/verdict` at :593/:609), so the explain cache (`graphs/grade.py:276`, :670) holds nothing from earlier runs and every wrong answer is explained with the new prompt. **Worth a look (medium, outside this scope):** `--rate-explanations` needs 2 or more kept runs with different reasoning models (`eval/ratings.py:101`, :107); a new qwen3.5:4b run cannot be paired with the earlier qwen3.5:4b run, only with another model's run, or rated from its `explanations.json`. Worth a look (low): PRD D5 says "English example sentences", the prompt now says "English words and phrases" and keeps the English correct sentence out; llm-design §5 says the meaning line is "for a rewrite", the prompt also asks it for sentence building.

Verifier notes (M2 milestone, 2026-10-12), at b255d17: 🔄, awaiting the teacher's `👤 sign-off:` of `docs/m2-report.md` (R-M2.2); everything else passes. R-M2.1 pass: the report compares qwen3.5:4b (row 10) and gemma4:e2b (row 11), both `set=heldout`, on every metric above (fast/verified key, judge, verdict, exact score, wall, VRAM, tokens and calls per node); every number taken from rows 10–16 equals the 16-line committed `eval-history.csv` (accuracies, `key_uncertain_n`, `verdict_uncertain_n`, `wall_s`, `vram_peak_mb`, `n_failed`, commits, `prompt_digest`, per-node usage). The derived counts were recomputed read-only from the kept runs (`grade.json`, `llm_calls.json`; counts only): keys right/wrong/empty, flagged and unflagged keys, verdict pairs, scores, non-complete calls per node, capped and empty calls, explain endings. `--score-ratings` on `m2-rating`, `m2-rating-v2`, `m2-rating-v3` reproduces 2.60/2.78, 3.77/3.44 and 4.08/3.92; the item splits and head-to-head counts match. Every recorded request has `num_ctx` 16384, temperature 0, seed 42 and the `GRADING_NUM_PREDICT` caps; `think` is true only for verify_key/judge_rewrites in rows 10–13. The first pass at 1a14e27 found one wrong number (`difficulty_notes` gemma tuning 2 / 4, data 2 / 5), a stale §5 reference, "111 … end empty" (109 are empty), a parked item missing from structure §7 and the unstated tuning judge result (4 of 4 NHT-D4 rewrites incorrect in rows 15–16); b255d17 fixes all of them (structure v1.1.75) and changes no other number. R-M2.2: the blind ratings (§3, §5) and `Decision: reasoning=qwen3.5:4b` (§4) are in the report; no `👤 sign-off:` commit touches it yet and §9 is blank, so the row stays 🔄 until the teacher signs. R-M2.3 pass: the choice equals `DEFAULT_ROLES["reasoning"]["model"]` (`llm/defaults.py`). Docs: "Based on" equals PRD v4.9, data-model v1.7, llm-design v4.17.2; llm-design's think=false for every grading task matches `GRADING_THINK` (empty) and R17.2.4. S1 `TEST` 1303 passed, 14 deselected; S2 ruff clean, 205 files formatted, `mypy src` no issues in 88 files; S3 `wrote 42 schema files`, no diff; S4 only `llm/defaults.py`; S5 exits 0; S6 `openapi.json` unchanged; S7 not run (no `app/` change against main); clean tree afterwards. No teacher field written; checklist boxes left for the orchestrator.

Verifier notes (M2 milestone close, 2026-10-12), at 918964c, by the orchestrator (the teacher waived a fresh verifier for this check): ✅. R-M2.2 now passes: 918964c is the teacher's commit `👤 sign-off: M2 report (reasoning=qwen3.5:4b, explain prompt 2)` (subject starts with bytes f0 9f 91 a4); it touches only `docs/m2-report.md` (§9 filled). Since f91473e nothing else changed, so R-M2.1, R-M2.3 and S1–S6 stand as recorded above. Checklist ticked.

---

## Appendix A — Class manifest (for R1.1)
Field names per class, as in the current data-model §2 (version pinned in "Based on"). Nested helper types are listed at the end.

```
Student: id, full_name, name_search, class_name, school, grade, notes, created_at
Test: id, meta, content, content_schema_version, fingerprint, points_possible, source_run_id, merged_into, created_at, updated_at
TestMetadata: occasion, grade, year, school, created_by_ai, term, test_number, variant, test_code, region, source, textbook, units, duration_minutes, exam_format, omitted_sections, tags, parent_test_id, extra, edited_fields
TestContent: sections
Section: id, number, printed_title, title, instructions, points, points_source, skill, graded, groups
QuestionGroup: id, stimulus, pictures, questions
Question: id, number, printed_number, page_no, answer_form, context, stem, options, cue, answer_start, points, old_type, old_options
PictureRef: file_id, page_no
AnswerKey: test_id, question_id, accepted, reason_vi, source, status, confidence, updated_at, checker
Attempt: id, test_id, thread_id, student_id, student_name_read, class_read, source_run_id, superseded_by, status, version, score_earned, score_possible, created_at, taken_on
AttemptPage: attempt_id, page_no, file_id, source_file_id, rotation
Answer: attempt_id, question_id, printed_number, page_no, value, value_norm, location, confidence, low_trust, reading_unsure, alt_value, alt_question_id, verdict, near_miss, points_awarded, teacher_override
GradeReport: attempt_id, run_id, weak_points, careless_notes, summary_vi, teacher_questions, uncertain_points, created_at
Explanation: test_id, question_id, wrong_answer_norm, error_type, text_vi, status, llm_call_id
Thread: id, title, test_id, kind, created_at
Message: id, thread_id, role, kind, body, created_at
PageInput: file_id, rotation, is_key, text_file_id
ExtractInput: pages, existing_test_id, supersedes_attempt_id, series_from_test_id, series_name, again_test_id, again_mode, taken_on
GradeInput: test_id, attempt_id, reason
Run: id, thread_id, kind, input, status, started_at, finished_at, error
Step: id, run_id, node, item, try_no, status, started_at, finished_at
LlmCall: id, step_id, role, model, prompt_hash, request, response_text, thinking_text, logprobs, status, tokens_in, tokens_out, ms, created_at
ReviewItem: id, kind, owner, test_id, attempt_id, question_id, dedupe_key, proposal, resolution, followup_run_id, status, created_at, resolved_at
File: id, path, kind, derived_from, mime, width, height, created_at, original_name
Helpers: OmittedSection(title, questions, points, kind)
         Option(label, text) · WeakPoint(skill_tag, wrong, seen, gap_errors, note_vi, label, level, held_back) · TeacherQuestion(question_vi, what_answers_mean_vi)
Working types: as data-model §2.9 (PreparedPage, PageTranscript, TestDraft, PageHeader, KeyEntry, PageAnswers, CompareResult, PendingReview, SavedIds)
```
Literal sets: exactly as written in the current data-model §2. Exception: `ReviewItem.kind`'s `unreadable_text` (data-model v1.6) is added by step 21a; until 21a is ✅, R1.1 checks the set without it.

## Appendix B — Expected values
- **B.1 Renumber (worked example).** Input: printed sections with their printed points:

  | Printed | Questions | Points |
  |---|---|---|
  | I (listening) | Q1–4 | 1.0 |
  | II | Q5–14 | 2.5 |
  | III | Q15–16 | 0.5 |
  | IV | Q17–22 | 1.5 |
  | V | Q23–28 | 1.5 |
  | VI | Q29–34 | 1.5 |
  | VI (duplicate label) | Q35–36 | 0.5 |
  | VIII | Q37–40 | 1.0 |

  Every question is 0.25. Expected:
  - listening → `omitted_sections` (1 entry, 1.0 pt);
  - 7 canonical sections numbered 1–7 whose `printed_title`s keep "II"…"VIII";
  - 36 questions numbered 1–36 with `printed_number` 5–40 (canonical = printed − 4);
  - `points_possible` = 9.0.

  **B.1b (writing variant):** the same input plus "IX (writing, Q41, 1.0)" → section 8 with `graded=False`, the writing entry in `omitted_sections`, `points_possible` still 9.0, and no answer rows for Q41.
- **B.2 Similarity pairs.** Three committed text files (`noisy_pair`, `medium_pair`, `reordered`) with the expected Jaccard band and alignment map stored next to them, **written from the worked example's printed text** (not from implementation output).
- **B.3 map_key.** The input `key_raw` is an ordered list of (label, answer) entries (llm-design v4.5), so a repeated label is kept. The rule: labels map to the question with that printed number. Listening labels are skipped silently. A **duplicate label** maps by position to the next question only if that question's own label is absent from the key; otherwise the duplicate is `key_unmapped`. A label with no matching question is `key_unmapped`.
  - **Case a:** labels `1,2,…,32,32,33,…,40,41` (letters arbitrary) → labels 1–4 skipped; labels 5–32 (first "32") → canonical 1–28; the second "32" → `key_unmapped` (label 33 is present); labels 33–40 → canonical 29–36; "41" → `key_unmapped`. Result: 36 key rows and 2 `key_unmapped` items.
  - **Case b:** labels `…,31,32,32,34,…` (33 missing) → the second "32" maps to canonical 29 (printed 33); 0 `key_unmapped`.
- **B.4 resolve_answers** (reading threshold t = 0.7):
  - Q10 inline "B" + box "C" → "C" + `box_inline_conflict`;
  - "electric fields" between Q35 and Q36 → Q35, confidence = t − 0.01 = **0.69** (so `reading_unsure`), `alt_question_id` = Q36;
  - confidence 0.4 → `reading_unsure`;
  - all answers None → blank.
- **B.5 Verdict rules** (llm-design §5 `grade`; by answer form since step 22.5.3):

  | # | Situation | Verdict |
  |---|---|---|
  | 1 | Reading unsure, no override | uncertain |
  | 2 | Reading unsure, override present | graded normally (confidence 1.0) |
  | 3 | Key `ai_uncertain` | uncertain |
  | 4 | `choice` value = key | correct |
  | 5 | `choice` value ≠ key | incorrect |
  | 6 | `word` or `sentence` normalized value ∈ accepted | correct |
  | 7 | `word`: edit distance 1–2 from accepted, confident reading | incorrect + `near_miss` |
  | 8 | `word`: edit distance 1–2, unsure reading | uncertain |
  | 9 | `sentence`, no normalized match | judge result (correct/incorrect) |
  | 10 | Value None (blank) | incorrect |
  | 11 | No key row for the question (key making failed) | uncertain |
  | 12 | Retired in step 22.5.3: ordering is a `sentence` (row 9), matching a `choice` (rows 4–5) | – |
  | 13 | Retired in step 22.5.3: combine is a `sentence` (row 9) | – |
  | 14 | `judge_rewrites` failed twice | uncertain |
  | 15 | Page reading failed (value None, `reading_unsure`) | uncertain |
  | 16 | Question in a writing section (`graded=False`), or a `writing` question | no answer row, not graded |

- **B.6 Seeded score.** The worked example with seeded verdicts: 30 correct × 0.25, 4 incorrect, 2 uncertain × 0.25 → **7.5/9**, uncertain_points **0.5**.
- **B.7 verify_needed = true** when the key is `ai_unverified` and any of the following holds: the margin is below the threshold; the question is a pronunciation or stress item; an attempt is present and the student gave a **non-blank** answer that ≠ the key (a blank or missing answer does not trigger it: it says nothing about the key, v2.7). False for every other status.
- **B.8 Failure rules** (llm-design §5.1). One test per row there: after two failures of that call, assert the listed verdicts, Review items and the run status (`done`, not `failed`).

## Appendix C — Graph edge lists
- **C.1 extract:**
  - `START→prepare_pages`, `prepare_pages→read_key_pages`;
  - `read_key_pages→load_bank_test` (picked), `read_key_pages→transcribe_page` (not picked);
  - `load_bank_test→read_header`, `read_header→sanity_check`, `sanity_check→map_key`;
  - `transcribe_page→transcribe_page` (more pages), `transcribe_page→merge_and_normalize`;
  - `merge_and_normalize→retranscribe_tiles` (retranscribe), `retranscribe_tiles→merge_and_normalize`, `merge_and_normalize→compare_bank` (no retranscribe);
  - `compare_bank→map_key`, `map_key→read_answers_page`;
  - `read_answers_page→read_answers_page` (more pages), `read_answers_page→resolve_answers`;
  - `resolve_answers→save`, `save→END`.
- **C.2 grade:**
  - `START→load_context`;
  - `load_context→ai_key_fast` (key needed), `load_context→verify_gate` (not needed), `ai_key_fast→verify_gate`;
  - `verify_gate→verify_key` (verify needed), `verify_gate→tag_skills`, `verify_key→tag_skills`;
  - `tag_skills→save` (no attempt), `tag_skills→grade`;
  - `grade→judge_rewrites` (rewrites pending), `grade→explain`, `judge_rewrites→explain`;
  - `explain→weak_points`, `weak_points→save`, `save→END`.

## Appendix D — Required request shapes and prompt phrases
- **D.1 Adapters:** `nuextract` requests carry the template JSON and instructions in NuExtract3's roles and set `think: false`. `chat` requests carry a system message, a user message, and `format` = the task's JSON Schema. Every request body carries `truncate: false` (llm-design v4.12).
- **D.2 Extraction phrases** (in the English prompt text):

  | Task | Required phrases |
  |---|---|
  | `transcribe_page` | "printed text only" · "write every blank as ____" · "<u>" · "**" · "listening: return only the heading and question range" · "writing: return only the task prompt" · "transcribe pictures that are mostly text" |
  | `read_answers_page` | "copy handwriting exactly, including mistakes" · "answer box" · "circled" · "null if no answer" · "student name" |
  | `read_key_pages` | "question number" · "answer" |
  | `read_header` | "header" · "first questions" |

- **D.2a Unreadable-text phrases** (step 21a, PRD D25; checked by R21a.1, not R8.2.2, so the D.2 table above is unchanged):

  | Task | Required phrases |
  |---|---|
  | `transcribe_page` | "???" · "cannot read" · "never guess" |
  | `read_answers_page` | "???" · "cannot read" · "never guess" |

- **D.3 Grading phrases:**

  | Task | Required phrases |
  |---|---|
  | `explain` | "in Vietnamese" · "keep grammar terms in English" · "at most 3 sentences" |
  | `judge_rewrites` | "must be grammatical" · "same meaning" · "no partial credit" |
  | `weak_points_summary` | "3 to 5 questions for the teacher" · "what each answer would mean" |
  | `verify_key` | "solve independently" |
  | `tag_skills` | "use only these skill IDs" |

## Appendix E — Review resolution table (for R10.1, R12.6)
Data-model §5.3 is the source. Each row lists the post-conditions the test asserts. "Graded" = the attempt is `graded` and not superseded. **Every row is tested twice: once with the attempt graded (runs queued as listed) and once ungraded (0 grade runs).** Every non-skip row also sets `resolution`, `resolved_at` and the status (accepted/fixed), and sets `followup_run_id` when a run is queued. Rows marked *(step 21a)* are checked from step 21a on (R21a.7); until then R10.1 and R10.2 cover the other rows and 11 kinds.

| Kind · action | Post-conditions |
|---|---|
| uncertain_answer · accept | `teacher_override` = the value read; `value_norm` recomputed; version+1; graded → 1 grade run (review_fix) |
| uncertain_answer · fix(value) | `teacher_override` = value; `value_norm` recomputed; version+1; graded → 1 grade run (review_fix) |
| box_inline_conflict · accept | `teacher_override` = the box value; version+1; graded → 1 grade run (review_fix) |
| box_inline_conflict · fix(value) | `teacher_override` = value; version+1; graded → 1 grade run (review_fix) |
| uncertain_key · accept | key unchanged, status `teacher_verified`; explanations kept; N grade runs (key_verified), N = graded attempts on the test |
| uncertain_key · fix(key) | key replaced, `teacher_edit`, `teacher_verified`; that question's explanations deleted; N grade runs (key_verified) |
| key_unmapped · accept | the entry is discarded; no key row; no run |
| key_unmapped · fix(question_id) | key row for that question (`teacher_edit`, `teacher_verified`); N grade runs (key_verified) |
| possible_duplicate · accept | merge (R10.3); 1 grade run (merge) per moved graded attempt |
| merge_unaligned · accept | the answer stays `ungraded` on the old question; no run |
| merge_unaligned · fix(question_id) | the answer moved to that question of the survivor; graded → 1 grade run (merge) |
| picked_test_mismatch · accept | 1 queued extract run with `existing_test_id=None` and `supersedes_attempt_id` set |
| unknown_student · accept | a new student from `student_name_read` → `attempts.student_id`; version+1; no run. Rejected if no name was read |
| unknown_student · fix(S or new name) | `attempts.student_id` = S (or a new student); version+1; no run |
| unknown_occasion · accept | occasion stays `Other:unknown`; no run |
| unknown_occasion · fix(occasion) | `write_test_meta(by_teacher)`; `edited_fields` has occasion; no run |
| points_assumed · accept | points stay 0.25 each; no run |
| points_assumed · fix(points) | the section's points updated; `points_possible` recomputed; N grade runs (points_fix) |
| validator_failed · accept | content unchanged; no run |
| validator_failed · fix(content) | content updated and re-validated; no run unless a key changed (then as uncertain_key · fix) |
| unreadable_text · accept *(step 21a)* | content unchanged (the `???` spans stay); no run |
| unreadable_text · fix(spans) *(step 21a)* | each listed field set to the typed text through the content edit (`write_test_meta`, re-validated); other fields unchanged; no run. An invalid edit is rejected and nothing changes |
| any · skip | status `skipped`; nothing else changes |

## Appendix F — Traceability (PRD → requirement IDs)
| PRD item | Requirements |
|---|---|
| D1 duplicates | R8.1.6, R9.6, R10.3, R16.5, R19.6 |
| D2 key | R2.6, R8.1.7, R9.7, R17.1.3, R18.2–R18.6, R19.5 |
| D3 students | R2.7, R8.1.9, R9.12, R16.2 |
| D4 print, key separate | R16.4, R19.1, R19.2 |
| D5 language | R17.2.2, R-M2.2 |
| D6 teacher questions | R17.2.2, R18.2, R19.1 |
| D7 models | R4.5, R4.6, R5.1, R20.1, R-M1.4, R-M2.2, R21.4 |
| D8 UI | R13.1, R13.2, R15.1 |
| D9 glance before print | R16.4, R19.1 |
| D10 standardized test | R8.1.1, R8.1.5 |
| D11 placeholders | R8.1.4, R16.4 |
| D12 listening + writing | R8.1.1 (B.1, B.1b), R8.1.8, R8.2.2 |
| D13 score, 0.25 default | R8.1.2, R17.1.2, R19.7, Appendix E |
| D14 answers anywhere | R8.1.8, R8.2.2, R9.2 |
| D15 profiles + eval | R8.2.3, R11.1–R11.4, R-M1.2 |
| D16 scope split | R9.2, R18.2 |
| D17 photo check | R15.1, R15.2 |
| D18 one test per thread | R15.6 |
| D19 key photo | R8.1.7, R9.7, R18.3 |
| D20 logprob confidence | R6.1–R6.4, R8.1.8, R17.1.1 |
| D21 Python + LangGraph | R0.4, R7.1 |
| D22 stop/resume | R4.3, R7.1–R7.8, R9.5, R12.4, R15.4, R18.9 |
| D23 sleep, lid, battery | R7.6, R15.5, R22.1 |
| D24 no partial credit | R17.1.2, R17.2.2, R19.1 |
| D25 unreadable text | R21a.1–R21a.7 |
| S1 | R9.2, R15.4, R19.1, R22.2 |
| S2 | R18.5, R19.3, R22.2 |
| S3 | R9.6, R10.3, R19.6, R22.2 |
| S4 | R9.4, R18.4, R19.2, R22.2 |
| S5 | R9.7, R18.3, R22.2 |
| S6 | R7.1–R7.3, R15.4, R22.2 |
| S7 | R10.1, R16.3, R16.5, R22.2 |
| §10.2 Settings | R20.1–R20.8 |
| §11 architecture, offline | R12.2, R13.3, R14.1–R14.4, R21.1, R22.1 |
| §12 quality goals | R11.1, R-M1.2, R-M1.3, R-M2.1 |
