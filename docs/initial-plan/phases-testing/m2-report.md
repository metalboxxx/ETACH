# M2 report: reasoning model choice

- **Date:** 2026-10-12
- **Models compared:** `qwen3.5:4b` (the placeholder in `llm/defaults.py`) and `gemma4:e2b`. `gemma3:4b` was dropped before the runs (§6).
- **Options:** `num_ctx` 16384, `temperature` 0, `seed` 42 on every call; 1 run per model (structure §7). Output caps per task: `ai_key_fast` 1024, `verify_key` 1500, `tag_skills` 2048, `difficulty_notes` 1024, `judge_rewrites` 400, `explain` 512, `weak_points` 1024. In rows 10–13 `verify_key` and `judge_rewrites` ran with thinking on; after the decision thinking was turned off for every grading task (§5, rows 14–16).
- **Code:** held-out qwen run on `9e58f04`, held-out gemma run on `8f1c1b0`, both tuning rating runs on `884bb79`. Between `9e58f04` and `884bb79` only `eval-history.csv` and `fixtures/MANIFEST.sha256` changed, so all four runs used the same code and prompts. The follow-up runs (§5) used `370aef6` (rows 14, 15: thinking off, explain prompt 1) and `99a35a4` (row 16: explain prompt 2).
- **Held-out set (structure §7 "M2 scope"):** the 5 held-out papers, 196 questions with a typed key. One paper, `L8-HK1-NHT-D2-2025-photo`, has student answers (36); the other 4 are blank tests.
- **Grading input:** grading starts from the typed `expected.json` (questions and answers), not from extraction output. The key run starts with no key, so the model makes every key. The verdict run seeds the true key, so verdicts and judging are measured on their own.
- **Teacher verdicts:** the teacher wrote the `verdicts` for the 4 rewrite answers on each answered paper that needed one: NHT-D2 (held-out, `9e58f04`) and NHT-D4 (tuning, `884bb79`). The tuning paper DG needed none.

Row numbers below are line numbers in the committed `eval-history.csv` (line 1 is the header). Row 10 = qwen3.5:4b held-out, row 11 = gemma4:e2b held-out, row 12 = gemma4:e2b tuning (DG + NHT-D4), row 13 = qwen3.5:4b tuning (DG + NHT-D4). Rows 14–16 are the qwen3.5:4b follow-up runs after the decision (§5).

## 1. Held-out comparison (R-M2.1, rows 10 and 11)

All llm-design §8 grade metrics. The `prompt_digest` differs (row 10 `14c1e179095d`, row 11 `7b6d3157a91c`) only because qwen made no `explain` call on held-out, so the explain prompt is missing from its digest. The prompts are the same.

| Metric | qwen3.5:4b (row 10) | gemma4:e2b (row 11) |
|---|---|---|
| Fixtures, failed | 5, 0 | 5, 0 |
| Key accuracy, fast (`key_accuracy_fast`, n = 196) | 0.6378 | 0.5765 |
| Key accuracy, verified (`key_accuracy`, n = 196) | 0.5561 | 0.5204 |
| Keys flagged `ai_uncertain` (`key_uncertain_n`) | 60 | 61 |
| Verdict accuracy (n = 36) | 0.8889 | 0.9444 |
| · answers left `?` (`verdict_uncertain_n`) | 4 | 2 |
| Judge accuracy (n = 4) | 0.0000 | 0.5000 |
| Exact score match (n = 1) | 0.0000 | 0.0000 |
| Wall time | 5754.2 s (95.9 min) | 2091.7 s (34.9 min) |
| Time per paper | 1150.8 s (19.2 min) | 418.3 s (7.0 min) |
| Peak VRAM | 4029 MB | 3151 MB |
| Calls | 181 | 236 |
| Tokens in / out | 155 545 / 214 039 | 188 744 / 137 203 |
| Node time (sum) | 5579.8 s | 2022.1 s |

Time per paper comes from the batch `REPORT.md` of each run (wall time / 5).

**Per grade node** (llm-design §5; calls, tokens in / out, time). Usage is from the key run only, as the grade eval records it.

| Node | qwen3.5:4b (row 10) | gemma4:e2b (row 11) |
|---|---|---|
| `ai_key_fast` | 38, 33 729 / 15 453, 471.5 s | 37, 32 506 / 14 299, 209.0 s |
| `verify_key` (think on) | 128, 71 838 / 185 086, 4581.1 s | 184, 104 148 / 108 562, 1529.2 s |
| `tag_skills` | 5, 22 871 / 6 741, 269.8 s | 6, 28 017 / 8 499, 146.4 s |
| `difficulty_notes` | 7, 25 569 / 5 685, 225.4 s | 6, 22 554 / 4 993, 123.2 s |
| `judge_rewrites` (think on) | 2, 1 089 / 800, 23.3 s | 1, 497 / 345, 5.2 s |
| `explain` | 0 | 1, 539 / 104, 3.2 s |
| `weak_points` | 1, 449 / 274, 8.5 s | 1, 483 / 401, 6.0 s |
| Code nodes (`load_context`, `verify_gate`, `grade`, `save`) | 16, 8, 3, 68 ms | 16, 5, 3, 43 ms |

`verify_key` takes most of the time: 4581.1 of 5579.8 s for qwen (82%, 76 of 93 min) and 1529.2 of 2022.1 s for gemma (76%).

**Why verified is lower than fast.** Fast key accuracy counts a key as right when the key the model saved (made by `ai_key_fast`) has the same accepted answers as the typed key, whatever its status. Verified key accuracy counts the same keys, but a key flagged `ai_uncertain` counts as wrong even when it is right, because the teacher would still have to check it. So verified is always at or below fast.

**Derived key counts** (from each held-out `grade.json`, 196 keys per model):

| Count | qwen3.5:4b | gemma4:e2b |
|---|---|---|
| Keys right | 125 | 113 |
| Keys wrong (a key was made) | 57 | 63 |
| Keys empty (no key row saved) | 14 | 20 |
| Wrong keys flagged `ai_uncertain` | 44 | 50 |
| Right keys flagged `ai_uncertain` | 16 | 11 |
| Wrong keys not flagged | 13 (12 `ai_unverified`, 1 `ai_verified`) | 13 (all `ai_verified`) |
| Keys never sent to `verify_key` (`ai_unverified`) | 110 | 0 |

Check: 125 − 16 = 109 = 0.5561 × 196; 113 − 11 = 102 = 0.5204 × 196. An empty key has no key row, so the `grade` node marks its answer `?` (llm-design §5); it is visible to the teacher. On the tuning paper DG, wrong keys not flagged are 1 (qwen) and 4 (gemma).

**Verdict pairs** (NHT-D2, graph vs truth). The student on NHT-D2 made no mistakes, so all 36 truths are `correct`.

| Graph → truth | qwen3.5:4b | gemma4:e2b |
|---|---|---|
| correct → correct | 32 | 34 (2 of them judged) |
| `?` → correct | 4 (all 4 judged rewrites) | 2 (judged rewrites) |
| incorrect → correct | 0 | 0 |

Score on NHT-D2: truth 9.0 points; qwen earned 8.0 and gemma 8.5, both with answers left `?`, so neither matches exactly.

**Tuning runs** (rows 12 and 13, DG + NHT-D4, used for the rating sheet; not the comparison set):

| Metric | gemma4:e2b (row 12) | qwen3.5:4b (row 13) |
|---|---|---|
| Fixtures, failed | 2, 1 | 2, 0 |
| Key accuracy fast / verified (n = 70) | 0.3000 / 0.2571 | 0.7714 / 0.6429 |
| `key_uncertain_n` | 6 | 24 |
| Verdict accuracy (n = 63) | 0.9524 | 0.9365 |
| Judge accuracy (n = 4) | 0.2500 | 0.0000 |
| Exact score match (n = 2) | 0.5000 | 0.5000 |
| Wall time | 872.7 s | 2622.3 s |
| Calls | 94 | 78 |

gemma's tuning key accuracy is low because its NHT-D4 key run failed (§2), leaving all 36 NHT-D4 keys empty. Peak VRAM is blank in rows 12 and 13.

## 2. Reliability

Failed runs: only one of the 4 runs had a failed fixture: gemma4:e2b's NHT-D4 key run on tuning (row 12, `n_failed` 1). Its `difficulty_notes` call hit the 1024-token output cap (`invalid`), and the next attempt ended in `error`, so the key run stopped. Its verdict run finished.

Calls that were not `complete` (`invalid` or `error` / all calls), per node, over the key run and the verdict run (from `llm_calls.json`):

| Node | qwen held-out | gemma held-out | gemma tuning | qwen tuning |
|---|---|---|---|---|
| `ai_key_fast` | 2 / 38 | 1 / 37 | 0 / 12 | 1 / 13 |
| `verify_key` | 111 / 128 | 12 / 184 | 7 / 69 | 45 / 55 |
| `tag_skills` | 0 / 6 | 2 / 7 | 0 / 4 | 0 / 4 |
| `difficulty_notes` | 2 / 8 | 1 / 7 | 2 / 5 (1 `error`) | 0 / 4 |
| `judge_rewrites` | 10 / 10 | 4 / 7 | 5 / 7 | 8 / 8 |
| `explain` | 0 / 0 | 0 / 1 | 0 / 17 | 0 / 13 |
| `weak_points` | 0 / 2 | 0 / 2 | 0 / 3 | 0 / 4 |

- **Output caps:** every `invalid` call in the table used its whole output budget (`tokens_out` = `num_predict`).
- **`verify_key`:** 109 of qwen's 111 invalid held-out calls are empty answers that used all 1500 tokens on thinking (gemma: 12). Under llm-design §5 a truncated verification gives `ai_uncertain`, so most of qwen's flagged keys come from truncation, not from a real disagreement.
- **`judge_rewrites`:** empty answers that used the whole 400-token budget: qwen 10 (held-out) and 8 (tuning), gemma 3 (held-out) and 4 (tuning). gemma also had 1 cut-off non-empty answer in each set. qwen judged none of the 8 rewrites (judge accuracy 0 in rows 10 and 13).
- **Cut-off explanations (qwen):** 2 of qwen's 13 `explain` responses (tuning) end on an opening bracket, without final punctuation. Neither reached the cap (77 of 512 tokens). gemma's 18 `explain` responses all end with punctuation.

## 3. Blind rating (R-M2.2)

The rating used the tuning papers DG and NHT-D4 (rows 12 and 13), not held-out. On held-out NHT-D2 the student made no mistakes, so with the true key there is nothing to explain (qwen made 0 `explain` calls in row 10). The sheet came from `erh eval --rate-explanations`. It holds the explanations from both verdict runs, shuffled with the model hidden: 19 items (gemma 10: DG 8, NHT-D4 2; qwen 9: DG 8, NHT-D4 1). The teacher rated all 19, from 1 to 5.

`erh eval --score-ratings fixtures/_runs/m2-rating`:

```
Blind explanation ratings: 19 items, 19 in the sheet
- reasoning=gemma4:e2b: mean 2.60, 10 rated (0 not rated); per score 1: 1, 2: 4, 3: 3, 4: 2, 5: 0
- reasoning=qwen3.5:4b: mean 2.78, 9 rated (0 not rated); per score 1: 0, 2: 4, 3: 3, 4: 2, 5: 0
```

**Head to head** on the 9 questions both models explained: qwen rated higher on 4, gemma higher on 3, tied on 2. gemma's tenth item is an NHT-D4 rewrite that its judge wrongly marked incorrect, so it explained a correct answer.

**The teacher's notes** (18 of 19 items have one), as themes:
- **Vocabulary first:** translate the key words, then the sentence, then give the logic briefly.
- **Too long:** the explanations restate the question and the answer.
- **Tone:** not childish, and no clinical wording.
- **Grammar points:** state the rule or the formula.
- **Content:** some explanations were off-topic or wrong.

Both means are below 3 and no item got a 5. The explain prompt limits quality more than the choice of model does. The prompt was then revised twice (§5).

## 4. Decision

Decision: reasoning=qwen3.5:4b

The teacher's reasons (structure §7 "M2 result"): slightly better first-try keys (fast 0.6378 vs 0.5765, verified 0.5561 vs 0.5204, rows 10 and 11); no failed runs; and the teacher preferred its tone in the blind rating (mean 2.78 vs 2.60). The cost is speed: about 19 min vs 7 min per paper on a test without a key (row 10 vs row 11).

The teacher confirmed the decision after a correction (2026-10-12). The orchestrator had first told the teacher that qwen leaves fewer wrong keys unflagged (27 vs 33); that count included empty keys, which are graded `?`. Wrong keys without a flag are 13 vs 13. The teacher was also told, before confirming, that most of qwen's `verify_key` calls (111 of 128, 109 of them empty) and all 18 of its `judge_rewrites` calls use their whole output budget on thinking (§2).

**R-M2.3:** the choice equals the placeholder (`llm/defaults.py`, `DEFAULT_ROLES["reasoning"]["model"] = "qwen3.5:4b"`). No llm-design change is needed, and the plan's "Based on" line is not affected.

## 5. After the decision: thinking off and the explain prompt

The teacher asked for two changes before step 21 (structure §7 "Think-off results"): no thinking for qwen, and an explain prompt that follows the rating notes. Each was its own revertible branch with a verifier pass (plan.md M2 verifier notes).

**Thinking off** (`step/M2-think-off`, llm-design v4.17: `think=false` for every grading task). Held-out, row 14 against row 10 (row 14 also has explain prompt 1, which does not change keys or verdicts):

| Metric | qwen, think on (row 10) | qwen, think off (row 14) | gemma4:e2b (row 11) |
|---|---|---|---|
| Wall time (5 papers) | 95.9 min | 33.1 min | 34.9 min |
| Key accuracy fast / verified | 0.6378 / 0.5561 | 0.6327 / 0.5816 | 0.5765 / 0.5204 |
| `verify_key` calls at the cap | 111 of 128 | 5 of 75 | 12 of 184 |
| Wrong keys not flagged | 13 | 23 (13 `ai_unverified`, 10 `ai_verified`) | 13 |
| Verdict accuracy (n = 36) | 0.8889 (4 `?`) | 0.9167 (0 `?`) | 0.9444 (2 `?`) |
| Judge accuracy (n = 4) | 0.0000 (all `?`) | 0.2500 | 0.5000 |
| Correct answers graded incorrect | 0 | 3 | 0 |
| Peak VRAM | 4029 MB | 3947 MB | 3151 MB |

The 3 wrong verdicts are NHT-D2 rewrites Q37–39, which the teacher marked correct; the judge, without thinking, called them incorrect with a confident but wrong reason. The key check now finishes, but it confirms 10 wrong keys it used to leave flagged by running out of budget. **The teacher accepted both as known M2 weaknesses** (2026-10-12): the teacher reviews rewrite verdicts and checks AI keys before trusting them. Thinking stays off everywhere.

Tuning (DG + NHT-D4): verified key 0.6429 (row 13) → 0.7000 (rows 15 and 16); verdict accuracy 0.9365 in all three; wall time 43.7 → 15.9 → 14.1 min.

**Explain prompt** (two rounds; tuning DG + NHT-D4; teacher's blind ratings). Ratings from different days do not compare (the same 9 old explanations got 2.78 at the first rating and 3.44 at the second), so each round put the old and new explanations on one sheet. Both runs use the tag `qwen3.5:4b`, so the older run was relabelled in a scratch copy of its `--keep` folder for `--rate-explanations` (no code change).

| Round | Sheet | New | Old | Head to head |
|---|---|---|---|---|
| Prompt 1 (`035f12a`, llm-design v4.17.1; row 15) vs the original prompt with thinking on (row 13) | `fixtures/_runs/m2-rating-v2` | 3.77 (13 items) | 3.44 (9 items) | prompt 1 wins 3, original 1, tied 5 |
| Prompt 2 (`3d64ee4`, llm-design v4.17.2; row 16) vs prompt 1 (row 15) | `fixtures/_runs/m2-rating-v3` | 4.08 (13 items; no 1 or 2) | 3.92 (13 items; one 1, one 2) | prompt 2 wins 5, prompt 1 wins 4, tied 4 |

- Prompt 1 followed the first notes: vocabulary first, at most 3 sentences, no restating, state the rule, plain tone. Its examples came from the rated items, so round 1 favours it slightly.
- Prompt 2 followed the second notes: gloss every key word or phrase, give the meaning of a rule and of the finished sentence ("Nghĩa: …"), simpler words, no wordy closing. Its examples are not from the rated papers.
- The gap in round 2 is small (0.16 on 13 items); prompt 2 has no low scores, and prompt 1 was rated higher on 4 questions, two of which (Q28, Q40) were behind the new rules.

**The teacher chose prompt 2** (2026-10-12). The four NHT-D4 rewrites (Q37–40) are explained in rows 15 and 16 because the judge now answers; in row 13 they were `?` and had no explanation. The judge called all four incorrect (tuning judge accuracy 0 in rows 15 and 16; the teacher's truth is correct), so these four rating items explain answers that were in fact correct.

## 6. gemma3:4b dropped

gemma3:4b has no thinking mode, and the app sends `think` for `verify_key` and `judge_rewrites`. A run would have measured a technical failure, not the model, so the teacher dropped it before the runs (structure §7 "gemma3:4b dropped").

## 7. D5 kept

PRD D5 stays: explanations are in Vietnamese. The teacher decided this after the blind ratings (structure §7 "M2 result").

## 8. Parked and future

Parked until after step 22 (structure §7 "M2 result", "gemma3:4b dropped" and "Think-off results"):
- The explain prompt beyond prompt 2: the teacher's round-3 notes ("a bit long" on one item); the 4 questions where prompt 1 was rated higher (§5).
- ~~The cut-off qwen explanations~~ (§2; 2 of 13 with thinking on): checked after §5, every explanation in rows 14–16 (5 + 20 + 20) ends with punctuation, so this is no longer seen.
- Accepted known weaknesses with thinking off (§5): the judge graded 3 of 4 correct held-out rewrites incorrect (and 4 of 4 on tuning NHT-D4, rows 15 and 16); 23 wrong keys are not flagged.
- Every call row has `try_no` 1 although `retry_capped_output.reasoning` is true: check whether a capped reasoning output is really retried.
- gemma4:e2b's failed `difficulty_notes` (output cap) and its empty `judge_rewrites` answers.
- Sending `think` only when the model supports it, so the app does not break with a non-thinking reasoning model.
- Grade-eval low items: `--seed 0` falls back to the default seed; a `nan`/`inf` rating crashes `score_sheet` instead of raising `RatingError`.

Future (PRD v4.9, §14): explanations adapted to the student's level. A weaker student gets the meaning of the key words and the sentence; a stronger one also gets the grammar point.

## 9. Sign-off

Signed off by the teacher in a `👤 sign-off:` commit: Teacher, 2026-10-12
