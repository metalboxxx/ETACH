# Plan: grading quality

| | |
|---|---|
| Version | **v0.10.5** (2026-11-03) — built in step 22.5 (`docs/initial-plan/phases-testing/step22.5-plan.md`) |
| Based on | `docs/initial-plan/plan.md` (steps 1–22, step 22.5) |

| Version | Date | Change |
|---|---|---|
| **v0.10.5** | 2026-11-03 | Patch, after the initial plan: moved to `docs/initial-plan/`; the tracker rows are ✅, as in plan.md's tracker |
| v0.10.4 | 2026-10-25 | Patch: tracker row 22.5.5 built (sidecar, UI, checklists (c) and (d)) |
| v0.10.3 | 2026-10-24 | Patch: tracker row 22.5.5 built (sidecar); the UI part (22.5.5b) follows |
| v0.10.2 | 2026-10-24 | Patch: tracker row 22.5.4 built (sidecar); the UI part (22.5.4b) follows |
| v0.10.1 | 2026-10-23 | Patch: the tracker follows step 22.5's 8 sub-steps |
| v0.10 | 2026-10-23 | Minor, teacher: the work is built in step 22.5, before step 22; the tracker lists its sub-steps |
| v0.9 | 2026-10-23 | Minor: weak points from the student's trajectory over time; skill names for the summary (the teacher) |
| v0.8 | 2026-10-23 | Minor: the explain prompt drops "grade 8 to 10" (the teacher) |
| v0.7 | 2026-10-23 | Minor: explanations get a hidden reasoning step first (the teacher) |
| v0.6 | 2026-10-23 | Minor: the judge sees the printed opening words; reason before verdict; strict stays (the teacher) |
| v0.5 | 2026-10-23 | Minor: remove the difficulty notes step (the teacher's decision) |
| v0.4 | 2026-10-23 | Minor: skill tagging once per section, with the section heading and passage (the teacher) |
| v0.3 | 2026-10-23 | Minor: an unsure key shows the checker's answer and reasoning on hover (the teacher) |
| v0.2 | 2026-10-23 | Minor: separate model roles for the checking calls (grading and extraction), the teacher's request |
| v0.1 | 2026-10-23 | First version: `ai_key_fast` asks only for the missing keys (the teacher, during the walkthrough of the grading pipeline) |

## Why

The teacher walked through the grading pipeline (`sidecar/src/erh/graphs/grade.py`) step by step with the orchestrator
on 2026-10-23 to judge it. Findings the teacher wants acted on are recorded here; the extraction side is in
`docs/initial-plan/plan-extraction-quality.md`.

## `ai_key_fast` asks only for the missing keys (2026-10-23)

`ai_key_fast` (`sidecar/src/erh/graphs/grade.py:488`) makes a key for every graded question without one, one call per
section that has such a question. The user message is the **whole section** (`_section_text`: heading, instructions,
passage, every question), and the prompt (`sidecar/src/erh/prompts/base/ai_key_fast.md`) says "Answer every listed
question". The IDs that need a key (`question_ids`) go to the code, not into the prompt, so the model answers the whole
section and the code keeps only the missing ones.

Nothing goes wrong in the saved keys (the extra answers are dropped, existing keys are untouched), but the extra
answers cost time and use the 1 024-token output cap first, so in a long section the needed question can be cut off and
get no key. In the teacher's `app.db` (read-only, 2026-10-23) it has not happened yet: AI keys exist only on the two
tests without a key photo, where every question needed one. Sizes seen there: system prompt 1 693 characters on every
call, section text 233–2 459 characters, input 533–1 349 tokens, output 74–1 024 tokens (one call hit the cap).

**Proposed** (the teacher, 2026-10-23; not planned): the section stays as context, and the prompt names only the
questions that need a key ("Write the key for these questions: …"). A prompt change plus its tests; no GPU run needed
beyond the usual check of the changed prompt.

## Separate model roles for checking (2026-10-23)

Today there are two model roles, `vision` and `reasoning` (`Role`, `sidecar/src/erh/llm/config.py:59`;
`[roles.*]` in `models.toml`; two model pickers on the Settings Models tab). `verify_key` uses `reasoning`, the same role
as `ai_key_fast`, so the key is checked by the model that wrote it.

**Proposed** (the teacher, 2026-10-23; not planned): two more roles, each with its own picker in the model manager:
- **grading check**: the model for `verify_key` (and later other checking calls in grading);
- **extraction check**: the model for checking or fixing an extraction (e.g. the targeted re-read in
  `docs/initial-plan/plan-extraction-quality.md`).

Both default to qwen3.5:4b, as every role today, so nothing changes until the teacher picks another model; an existing
`models.toml` without them uses the defaults. The point is the architecture: a different model can check later without
code changes. Touches `llm/config.py`, `llm/defaults.py`, `llm/tasks.py` (each task's role), the settings API, the Models
tab and llm-design §3.1.

## The checker's answer on an unsure key (2026-10-23)

When `verify_key` disagrees (or fails), the key becomes `ai_uncertain` ("AI unsure key") but keeps its first answer
(the `ai_key_fast` key or the key-photo key; `verify_failed`, `sidecar/src/erh/domain/keys.py:123`). The checker's
`answer` and `reasoning` are kept only in the model log (`llm_calls`); the `uncertain_key` Review item holds only the
first key. The teacher: the checker's thinking is useful, "sometimes the test question is wrong".

**Proposed** (the teacher, 2026-10-23; not planned): the checker's answer and its reasoning are stored with the unsure
key (or its Review item) and shown in the Key tab **only on hover** over the "AI unsure key" label (and on keyboard
focus, as the Keys changed tooltip of step 22.4.8), so the rows stay uncluttered. A failed check (no answer) shows that
the check did not finish. A data-model change (where the answer and reasoning are stored) plus the Key tab.

## Skill tagging once per section (2026-10-23)

`tag_skills` (`sidecar/src/erh/graphs/grade.py:587`) runs once per test, on its first grading: one call with the 84
skills (`prompts/taxonomy/grammar.txt`, 58 GR- skills copied from EnglishTest_Tutor in step 17.2, and
`prompts/taxonomy/sections.txt`, 26 skills written for this app) in the system prompt (9 087 characters) and every graded
question as one line (ID, number, type, stem, cue, options) in the user message: no section headings, no passages. In
the teacher's `app.db`: two calls, input 4 215–4 489 tokens, output 1 241–1 382, 50–52 s. A reading question or a cloze
gap is tagged without its passage, and the prompt's rule "follow the section" cannot work without the section.

**Proposed** (the teacher, 2026-10-23; not planned): one call per section, with the section heading, instructions and
passage, and that section's questions; about 7 calls for a 40-question test instead of 1 (each repeats the skill list),
still once per test. The cap of 3 tags per question stays (the orchestrator: more tags would count one wrong answer
against more skills in the student's ability).

## Remove the difficulty notes (2026-10-23)

`difficulty_notes` (`sidecar/src/erh/graphs/grade.py:607`) sends the whole test with its keys (7 725–10 541 characters)
and asks for the overall difficulty, a CEFR estimate, per-section notes, trap items and a Vietnamese comment, once per
test. In the teacher's `app.db`: 6 calls, 21–42 s each, **4 hit the 1 024-token cap** (the output is too long, not a
loop) and failed; a failed call is tried again on every grading, because only a success counts as done. The result is
saved in `meta.test_difficulty_notice_comment_by_ai` and **shown nowhere**: no screen, the report and the Word file do
not use it, and no later step reads it.

**Decided** (the teacher, 2026-10-23, option A of: remove it / show it and fix the cap / skip after one failure;
not planned yet): remove the step from the grading graph. To settle when planned: what happens to the stored
`test_difficulty_notice_comment_by_ai` (kept as old data, or dropped by a migration), the prompt, schema and cassettes,
the progress stages, and PRD §4 ("plus the difficulty notes" for a blank test's Grade).

## The judge: opening words, reason first, strict (2026-10-23)

`judge_rewrites` (`sidecar/src/erh/graphs/grade.py:637`) gets the task (`_question_text`: section heading, passage,
question line), the accepted keys and the student's answer, and returns `verdict` then `reason` (`JudgeOut`,
`sidecar/src/erh/domain/llm_schemas.py:331`).

1. **The printed opening words.** The question line (`_one_question`, `grade.py:244`) has the stem, cue and options but
   not `answer_start` (the words printed on the answer line, e.g. "→ My brother ……", data-model v1.15). A student who
   writes only the rest of the sentence is matched correctly by the exact-match step (the key's sentence forms join the
   opening words), but when the answer goes to the judge, the judge sees only a fragment and, under the strict rules,
   likely calls a right answer incorrect. **Decided** (the teacher, 2026-10-23): the judge must know the printed
   opening words: the task text includes them (e.g. "Answer line starts with: My brother"), and the prompt says the
   student's answer may continue them. Other calls that show a rewrite question (`ai_key_fast`, `verify_key`,
   `explain`) use the same `_one_question`, so they get the opening words too.
2. **Reason before verdict.** **Decided** (the teacher, 2026-10-23): `reason` comes before `verdict` in the output, so
   the model checks the sentence before it decides. A field-order change, not a longer prompt.
3. **Strict stays.** **Decided** (the teacher, 2026-10-23): no partial credit; one mistake makes the answer incorrect.

## Explanations: a hidden reasoning step first (2026-10-23)

`explain` (`sidecar/src/erh/graphs/grade.py:666`) writes `error_type` and then `text_vi` (`ExplainOut`,
`sidecar/src/erh/domain/llm_schemas.py:336`), with no room to work the question out first. In the teacher's `app.db`
(28 calls, about 5 s each, 98–151 output tokens) an explanation for "There aren't ____ students … It looks empty"
(key B "any", student D "a lot of") said "a few" needs "of" and that "a lot of" is only for positive sentences, both
wrong; the real reason is "It looks empty", so no students at all.

**Decided** (the teacher, 2026-10-23): the output has a hidden reasoning field first (the model works out why the key is
right and what the student got wrong), then `text_vi` (the explanation shown), then `error_type`. The reasoning is kept
with the call but never displayed. Output gets longer, so the 512-token cap and the time per call are checked when
planned.

**Decided** (the teacher, 2026-10-23): the explain prompt's first line names no grade ("a Vietnamese student in grade 8
to 10" becomes "a Vietnamese student"); the teacher finds the range too specific.

## Weak points from the student's trajectory (2026-10-23)

Today (`sidecar/src/erh/domain/weakpoints.py`): per skill tag, each attempt counts its wrong answers minus careless and
spelling ones; attempts are weighted by recency (this attempt 1, the one before 0.5, then 0.25 …); every skill with a
score above 0 is a weak point. Right answers never lower a score; they only add to `seen`. So one wrong answer makes a
weak point, and a skill the student got wrong before and right now stays a weak point (at half weight). In the
teacher's `app.db` one report listed 17 weak points, many "wrong 1/1". The summary call (`weak_points_summary`) gets the
skill codes ("GR-QNT-A2"), not their names.

Dates: an attempt has only `created_at`, the time the paper was uploaded, which also orders the history
(`skill_stats_by_attempt`, `sidecar/src/erh/store/repos/attempts.py:288`). The test has a `year`; there is no date the
student sat the test. Old papers uploaded late are ordered as new.

**Proposed** (the teacher, 2026-10-23; not planned):
1. **The skill names, not codes, go to the summary call** (the taxonomy names, as the report shows since 22.4.6).
2. **Weak points from the trajectory, not from single mistakes.** For each skill, the code lines up the student's
   results over time, by the date the student sat each test, and classifies the skill, for example:
   - **improved**: wrong earlier, right in the recent tests (not a weak point any more);
   - **slipped, or a lucky right earlier**: right earlier, wrong recently; a right `choice` answer is weaker evidence
     than a right `word` or `sentence` answer, since a choice can be guessed (ties to the answer forms in
     `docs/initial-plan/plan-extraction-quality.md`);
   - **inconsistent** (about 50/50 across tests): the skill to practise most;
   - **consistently weak**: wrong in most tests;
   - **not enough evidence**: seen once or twice; not a weak point yet.
   The thresholds (how many tests, what counts as recent or 50/50) are settled when planned.
3. **The date the student sat the test**: a new field on the attempt, defaulting to the upload date, which the teacher
   can change; the trajectory orders by it.

The orchestrator's notes: the analysis is code (counting over saved answers), so it stays fast; the model only turns
the classified skills into the Vietnamese summary and the teacher's questions, so its context gets shorter, not longer.
Where the trajectory is shown (the report, the Students tab) is asked when planned. A data-model change (the date
field, a migration) and a new ranking in `weakpoints.py`.

## Work (step 22.5)

- `ai_key_fast` asks only for the missing keys, as above.
- Separate model roles for the grading check and the extraction check, as above.
- The checker's answer and reasoning on an unsure key, on hover, as above.
- Skill tagging once per section, with the heading and passage, as above.
- Remove the difficulty notes step, as above.
- The judge sees the printed opening words; reason before verdict; strict stays, as above.
- Explanations: a hidden reasoning step, then the explanation, then the error type; no grade in the prompt, as above.
- Weak points from the student's trajectory over time, skill names for the summary, the test date, as above.

## Tracker

| Step | Title | Status |
|---|---|---|
| 22.5.4 | Model roles; grading prompts (opening words, judge, `ai_key_fast`, explanations); difficulty notes removed; tagging per section | ✅ |
| 22.5.5 | The checker's answer on an unsure key; weak points over time (G2) | ✅ |
