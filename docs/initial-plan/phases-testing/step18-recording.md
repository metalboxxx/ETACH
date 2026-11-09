# Step 18: recording the grade cassettes (the teacher's runbook)

This records one real **grading run** of the S1 worked example as cassettes, in
`sidecar/tests/cassettes/s1-grade`. The replay test `test_recorded_s1_grade` uses it (plan Step 18).
The grade run starts from the S1 attempt, which you rebuild first by **replaying** the S1 extract
cassettes you signed off in step 9 (no model is used for that part).

**No agent may be running while you do this.** Wait until every agent has finished (a Claude
Code window may stay open if nothing in it is working). The grade run uses the GPU; an agent
running tests at the same time would slow it or make it fail.

Run everything in **PowerShell**, in order. The whole runbook takes about **15–25 minutes**; the
grade run itself is most of it (model loading, then about 25–35 model calls).

## Before you start

- **Ollama is installed** with the phase-0 settings. `--spawn-ollama` starts a private Ollama with
  exactly these settings (flash attention on, `q8_0` KV cache) and stops it at the end, even on an
  error. Your own Ollama should have **no model loaded**, so this should list nothing:
  ```powershell
  & "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" ps
  ```
- **The models are pulled:** `qwen3.5:4b` and `NuExtract3` (phase 0). `erh grade` checks the
  Ollama version and the models before it starts, and says which `ollama pull` is missing.
- **The PC is otherwise idle:** close games, video, browsers with many tabs and other GPU programs.
- **`tests/cassettes/s1` is signed off** (step 9): it holds `input.json`, `NNN-*.json` and
  `SIGNOFF.txt`.

## How to run

**1. Start clean.** Removes the data folder and the cassettes of an earlier attempt (the recorder
adds to a folder that already has cassettes, so always start with an empty one).
```powershell
cd D:\Projects\Exam_Revision_Helper\sidecar
foreach ($d in "..\.devdata\rec-s1-grade", "tests\cassettes\s1-grade") {
  if (Test-Path $d) { Remove-Item -Recurse -Force $d }
}
```

**2. Rebuild the S1 attempt** by replaying the S1 extract cassettes into the fresh data folder.
This uses no model and takes a few seconds.
```powershell
uv run erh run --data ..\.devdata\rec-s1-grade --replay tests/cassettes/s1
```
It prints **one line** like
`{"test_id": "T-0001", "attempt_id": "A-0001", "run_id": "…", "thread_id": "…", "status": "done"}`.
Note the `attempt_id` (on a fresh folder it is `A-0001`).

**3. Record the grade run.** Put the `attempt_id` from step 2. `--after tests/cassettes/s1` tells
the recorder which extract scenario made the attempt; it is written into
`tests\cassettes\s1-grade\grade.json`, so the replay test can rebuild the same database.
```powershell
uv run erh record --out tests/cassettes/s1-grade --after tests/cassettes/s1 -- grade --data ..\.devdata\rec-s1-grade --attempt A-0001 --spawn-ollama
```
Progress goes to the screen. At the end it prints **one line** like
`{"run_id": "…", "thread_id": "…", "status": "done", "test_id": "T-0001", "attempt_id": "A-0001", "score_earned": …, "score_possible": …}`.
`"status": "done"` is what we need.

**4. Check the recording.**
```powershell
(Get-ChildItem tests\cassettes\s1-grade -Filter "[0-9][0-9][0-9]-*.json").Count
Get-Content tests\cassettes\s1-grade\grade.json
```
The count should be **about 25–35** (one file per model call). `grade.json` must show
`"after": "../s1"` and `"target": "attempt"`.

**5. Check the cassettes are scrubbed.** There is no real name to scrub here: the S1 attempt is
rebuilt from the `s1` cassettes, which were already scrubbed in step 9 (the student is the
placeholder "Học Sinh A"), and the grade run reads no photos. This check confirms it:
```powershell
uv run erh scrub --check tests/cassettes
```
It must print nothing and exit without an error (`$LASTEXITCODE` is `0`).

**6. Run the replay tests.**
```powershell
uv run pytest tests/replay -q -rs
```
Every test must **pass**. `test_recorded_s1_grade` must pass, **not skip**. If one fails, don't
commit: send the output to the orchestrator (see below).

**7. Sign off.** The sign-off commit must touch the recording, so it adds a `SIGNOFF.txt` to the
cassette folder (as in step 9). Its message must start with the 👤 emoji; PowerShell 5 mangles it
when it is typed in `git commit -m`, so the message is written from its raw UTF-8 bytes
(`F0 9F 91 A4`) into a file, and committed with `git commit -F`:
```powershell
cd D:\Projects\Exam_Revision_Helper
$utf8 = New-Object System.Text.UTF8Encoding $false
[IO.File]::WriteAllText("$PWD\sidecar\tests\cassettes\s1-grade\SIGNOFF.txt", "Reviewed and signed off by the teacher, $(Get-Date -Format yyyy-MM-dd)`n", $utf8)
$emoji = [Text.Encoding]::UTF8.GetString([byte[]](0xF0, 0x9F, 0x91, 0xA4))
[IO.File]::WriteAllText("$env:TEMP\erh-signoff.txt", "$emoji sign-off: cassettes grade`n", $utf8)
git add sidecar/tests/cassettes/s1-grade
git commit -F "$env:TEMP\erh-signoff.txt"
git log -1 --format=%s
```
The last line must print `👤 sign-off: cassettes grade` (if the console shows `?` or odd
characters instead of the emoji, check the bytes with
`git log -1 --format=%s | Format-Hex`: the line must start with `F0 9F 91 A4`).

**Or from Git Bash** (same result):
```bash
cd /d/Projects/Exam_Revision_Helper
printf 'Reviewed and signed off by the teacher, %s\n' "$(date +%F)" > sidecar/tests/cassettes/s1-grade/SIGNOFF.txt
git add sidecar/tests/cassettes/s1-grade
printf '\xF0\x9F\x91\xA4 sign-off: cassettes grade\n' | git commit -F -
git log -1 --format=%s
```

## If a run fails or is interrupted

- `erh grade` ends with a non-zero exit code and writes the reason to the screen (for example a
  missing model, or `"status": "failed"` with the error).
- **Keep the files.** `..\.devdata\rec-s1-grade` holds the database and the Ollama log
  (`logs\ollama-serve.log`); the cassettes recorded so far stay in `tests\cassettes\s1-grade`.
  Don't commit them.
- Send the orchestrator the full screen output and the last lines of the Ollama log:
  ```powershell
  Get-Content ..\.devdata\rec-s1-grade\logs\ollama-serve.log -Tail 50
  ```
- **Interrupted** (Ctrl+C, window closed, the PC slept): don't resume it. A resumed run would
  record only the calls after the stop, so the cassettes would not match one whole run. Start again
  from step 1 (it removes both folders).
- If the machine hangs or you close the window mid-run, the private Ollama may still be running:
  `Get-Process ollama*` shows it; end it with `Stop-Process -Name ollama -Force` (your own Ollama
  restarts from its tray icon).
- If step 2 fails, the S1 extract cassettes are not usable: run `uv run pytest tests/replay -q -rs`
  and send the output to the orchestrator; don't record.
