# M1: an overnight eval batch (the teacher's runbook)

This runs the extraction eval on the **tuning** fixtures **once**, with the real models, and
writes a short report. M1 judges every change on 1 run (temperature 0 and a fixed seed give the
same output each time). You start it in the evening and read the result in the morning.

**No agent runs while you do this.** The batch uses the GPU for hours; an agent running tests at
the same time would slow it down or make it fail.

The script commits nothing. Its outputs are under `fixtures\_runs\`, which is **gitignored**
(they hold the students' text). The only tracked file it changes is `eval-history.csv`: it gains
one row per run, which you commit later (an agent can help).

## Before you start

- **Ollama is installed, and the models are pulled:** `NuExtract3` and `qwen3.5:4b` (phase 0).
  The script starts its own private Ollama with the phase-0 settings, as the step 11 baseline
  did, and stops it after each run. Your own Ollama may stay in the tray, but should have **no
  model loaded**, so this lists nothing:
  ```powershell
  & "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" ps
  ```
  The script checks the Ollama version and the models before it starts, and stops with the
  missing `ollama pull` if one is missing.
- **The laptop is plugged in**, and **the lid stays open.** The script keeps Windows from
  sleeping while it runs (the screen may still turn off; that is fine), but closing the lid
  still puts the laptop to sleep.
- **Windows Update is not about to restart.** Open Settings → Windows Update: if a restart is
  pending, restart first, or pause updates for a day.
- **No other GPU programs:** close games, video, and browsers with many tabs.
- **The code is committed.** The script warns (and goes on) if `git status` is not clean,
  because the CSV's `commit` column would then not describe all the code that ran.

## The command

Copy this one line into **PowerShell**:

```powershell
powershell -ExecutionPolicy Bypass -File D:\Projects\Exam_Revision_Helper\sidecar\scripts\m1-overnight.ps1 -Check -Label baseline
```

**Before every GPU batch, run with `-Check`** (as above). The script first runs a short live
check on one small paper (`lop8-hk1-de1`): **about 10 minutes, and the laptop is busy** during
it, so stay nearby. It prints `CHECK OK` or `CHECK FAILED: <reason>` with the time it took.

- `CHECK OK`: the batch follows automatically; you can leave it overnight.
- `CHECK FAILED`: the batch does **not** start (the script stops). Send the orchestrator the
  `CHECK FAILED` line. It means a paper failed, a model call failed (`error`, which includes
  `prompt_truncated`) or ran out of output tokens (`output_capped`), or a CER of 1.0.

The check writes to its own folder (`...-check\`) and adds **no** row to `eval-history.csv`.
To run only the check and stop, use `-CheckOnly` instead of `-Check`.

For each paper the check prints a small table: CER, stimulus CER, structure_overall,
answer_accuracy and seconds, next to the same paper in the reference run (the
`fixtures\_runs\*-baseline<N>` folder with the highest N, e.g. `*-baseline3`, or the folder given
with `-CompareTo <folder>`, a batch or a check folder) and the difference. The same table is saved as `CHECK.md` in the check's folder.

**The mini test after each change** checks 3 papers instead of one: `lop8-hk1-de1` (a photo with
student writing), `L9-T23-book-lop9-50de` (a book PDF) and `L12-TS12-D1-2025-docx` (the long
DOCX). It also adds no row to `eval-history.csv`. Run only the mini test with:

```powershell
powershell -ExecutionPolicy Bypass -File D:\Projects\Exam_Revision_Helper\sidecar\scripts\m1-overnight.ps1 -Mini -CheckOnly -Label <change>
```

Change `baseline` to a short name for each batch (for example `vision-qwen25vl` when you try
another model). Other options, only when the orchestrator asks for them:

- another model: `-Role "vision=<tag>"` or `-Role "vision=<tag>,reasoning=<tag>"`;
- another number of runs: `-Runs 1` is the default;
- other check papers: `-CheckFixture <name>` (several: `-CheckFixture "a,b"`);
- another reference run for the comparison: `-CompareTo <run folder>`;
- the held-out set, **only for the final report:** `-Set heldout -Final`. Without `-Final` the
  script refuses held-out, so it is never used for tuning by mistake.

## What it prints

```
[21:30] M1 batch 'baseline': set tuning, a check, then 1 run(s); started 2026-10-06 21:30
[21:30] Check output: D:\Projects\Exam_Revision_Helper\fixtures\_runs\2026-10-06T21-30-baseline-check
[21:30] Output: D:\Projects\Exam_Revision_Helper\fixtures\_runs\2026-10-06T21-30-baseline
[21:30] Pre-flight: fixtures, Ollama version and models ...
  {"preflight": "ok", "mode": "live", "set": "tuning", "n_fixtures": 14, ...}
[21:31] Keeping the PC awake until the batch ends (the screen may still turn off).
[21:31] Check: lop8-hk1-de1 (the laptop is busy); log: ...\check.log
[21:40]   lop8-hk1-de1: done, cer ..., stimulus_cer ..., structure ..., answers ..., 540 s
CHECK OK (time 9m 12s)
[21:40] Run 1/1 started; log: ...\run-1.log
[23:10] Run 1 done in 1h 30m: CSV line 3; cer ..., structure ..., answers ...
[23:10] Total time 1h 40m.
REPORT: D:\Projects\Exam_Revision_Helper\fixtures\_runs\2026-10-06T21-30-baseline\REPORT.md
```

The window shows little during a run; the details go to `run-<k>.log` in the output folder.
A yellow `WARNING` line means a run failed or the git tree was not clean; the script goes on
with the next run either way.

## How long it takes

About **10 minutes for the check**, then about **1.5 hours per run** of the tuning set. With
more than one run, the script prints the estimated end of each remaining run after run 1, based
on the real time.

## Stopping it

Press **Ctrl+C** in the window. It is safe:

- the run in progress stops and adds **no** row to `eval-history.csv`;
- the runs that had already finished are kept: their folders, logs and CSV rows;
- the script still writes `REPORT.md` (marked "STOPPED EARLY") and lets the PC sleep again.

Afterwards check that the private Ollama has stopped: `Get-Process ollama*` should list only
your own Ollama, if any. If a second one is still there, end it with
`Stop-Process -Name ollama -Force` (your own Ollama restarts from its tray icon).

## Where the results are

In `fixtures\_runs\<date>T<time>-<label>\`:

```
REPORT.md          the summary: each key metric for each run, with mean, min and max
preflight.log      the pre-flight check
run-1.log ...      everything each run printed
run-1\tuning\      per fixture: test.json, answers.json, keys.json, metrics.json
                   (metrics.json lists the questions that went wrong, and call_status
                   counts the model calls per node and status), llm_calls.json (every
                   model call, raw), pages.json (each page's reading before merge),
                   and summary.json
```

and the new rows at the end of `eval-history.csv` (REPORT.md gives their line numbers).
The check's outputs are in `fixtures\_runs\<date>T<time>-<label>-check\`: `CHECK.md` (the
comparison table), `check.log`,
`tuning\<paper>\` (the same files as above) and `check-history.csv` (not the repo's
`eval-history.csv`).

## In the morning, tell the orchestrator

- the `CHECK OK` / `CHECK FAILED` line;
- the `REPORT:` path from the last line (or paste the contents of `REPORT.md`; it holds only
  metrics and fixture names, no student text);
- any yellow `WARNING` lines, or that you stopped it early;
- don't commit `eval-history.csv` yourself unless asked; the orchestrator or an agent will
  help with that.

## M2: choosing the reasoning model (the grade eval)

M2 compares reasoning models on the **held-out** papers. It does not read the photos: each
paper's typed `expected.json` becomes a bank test, and only the grade graph runs (the model makes
the key, checks it, judges rewrites and writes the explanations). Per paper, a blank test gets one
run (the key); the paper with student answers gets two (the key, then the grading with your key).
The same rules as above apply: no agent running, the laptop plugged in, the code committed.

**1. Your verdicts on free-text answers (once, no GPU).** A rewrite or combine answer that is not
exactly one of the accepted answers needs your verdict; the app's rules alone cannot say.

```powershell
cd D:\Projects\Exam_Revision_Helper\sidecar
uv run erh eval --graph grade --set heldout --list-verdicts --keep ..\fixtures\_runs\m2-verdicts
```

It prints only a count. For each paper, `fixtures\_runs\m2-verdicts\heldout\<paper>\needs-verdict.json`
lists the questions (question text, the student's answer, the accepted answers). Copy its
`template` into that paper's `expected.json` as `"verdicts"` and write `"correct"` or `"incorrect"`
for each, e.g. `"verdicts": {"37": "correct", "38": "incorrect"}`. Then refresh the manifest
(`uv run erh fixtures manifest`) and commit `fixtures/MANIFEST.sha256` in a `👤 sign-off:` commit,
as for any fixture change. Without your verdicts the eval still runs, but those answers are left
out of `verdict_accuracy`, and `score_exact_match` stays empty.

**2. One held-out grade run per model** (the placeholder first, then each candidate; the tag as
in `ollama list`; pull the model first):

```powershell
powershell -ExecutionPolicy Bypass -File D:\Projects\Exam_Revision_Helper\sidecar\scripts\m1-overnight.ps1 -Graph grade -Set heldout -Final -Reasoning qwen3.5:4b -Label m2-qwen35-4b
powershell -ExecutionPolicy Bypass -File D:\Projects\Exam_Revision_Helper\sidecar\scripts\m1-overnight.ps1 -Graph grade -Set heldout -Final -Reasoning <tag> -Label m2-<short-name>
```

`-Check` and `-Mini` are for the extraction only. Each run adds one `graph=grade` row to
`eval-history.csv`; REPORT.md shows key accuracy (fast and verified), verdict, judge and exact
score accuracy, and the time per paper. The first run tells how long one takes.

**3. The blind rating sheet** (no GPU), from the two (or more) batch folders of step 2:

```powershell
cd D:\Projects\Exam_Revision_Helper\sidecar
uv run erh eval --graph grade --rate-explanations ..\fixtures\_runs\<date>-m2-qwen35-4b ..\fixtures\_runs\<date>-m2-<short-name> --out ..\fixtures\_runs\m2-rating
```

Open `fixtures\_runs\m2-rating\rating-sheet.csv` in Excel. Each row is one explanation of a wrong
answer, shuffled, with no model name. Write a `rating` from 1 (wrong or misleading) to 5 (correct,
clear and useful for the student), and a `note` if you like. Save it as **CSV UTF-8** under the
same name. Do not open `rating-key.json` (it says which model wrote which row).

**4. Score the sheet:**

```powershell
uv run erh eval --score-ratings ..\fixtures\_runs\m2-rating
```

It prints one line per model: the mean rating, how many were rated, and the count per score. The
lines hold no student text; send them to the orchestrator for `docs/initial-plan/phases-testing/m2-report.md`.
