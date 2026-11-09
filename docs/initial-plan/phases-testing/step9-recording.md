# Step 9: recording the extract cassettes (the teacher's runbook)

This records two real extraction runs as cassettes: the **S1** worked example (a filled test) and
**one blank test**. The replay tests R9.2 and R9.13 use them (plan Step 9, R9.14).

**No agent runs while you do this.** Close Claude Code sessions for this project first. The runs
use the GPU; an agent running tests at the same time would slow them or make them fail.

Run everything in **PowerShell**, in order. Each run takes roughly **5–10 minutes** (most of it is
model loading and reading the pages). The whole runbook takes about 30 minutes.

## How to run

**1. Free the GPU.** Close other GPU programs. Your own Ollama should have no model loaded, so this
should list nothing:
```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" ps
```
The models must already be pulled (phase 0). `erh run` checks the Ollama version and the models
before it starts, and says which `ollama pull` is missing.

**2. Check the photos.** Open each page and decide the **order** and the **rotation** (degrees
clockwise needed to make the page upright: `0`, `90`, `180` or `270`). The worked example is:
```powershell
explorer "D:\Study\Pho Thong\Lop8-HkI"
```
with `Lop8-HKI-De1 (1).jpg`, `Lop8-HKI-De1 (2).jpg` and `Lop8-HKI-De1 (3).jpg`. You choose the
order and rotations; the commands below show all three at `0`. Each page is written
`"<path>:<rotation>"`; add `:key` for an answer-key photo (`"<path>:0:key"`).

**3. Start clean.** The first lines remove data and cassettes from an earlier attempt (the recorder
adds to a folder that already has cassettes, so always start with an empty one).
```powershell
cd D:\Projects\Exam_Revision_Helper\sidecar
foreach ($d in "..\.devdata\rec-s1", "..\.devdata\rec-blank", "tests\cassettes\s1", "tests\cassettes\blank") {
  if (Test-Path $d) { Remove-Item -Recurse -Force $d }
}
```

**4. Record S1.** `--spawn-ollama` starts a private Ollama with the app's settings and stops it
at the end, even on an error.
```powershell
uv run erh record --out tests/cassettes/s1 -- run --data ..\.devdata\rec-s1 --spawn-ollama --pages "D:\Study\Pho Thong\Lop8-HkI\Lop8-HKI-De1 (1).jpg:0" "D:\Study\Pho Thong\Lop8-HkI\Lop8-HKI-De1 (2).jpg:0" "D:\Study\Pho Thong\Lop8-HkI\Lop8-HKI-De1 (3).jpg:0"
```
Progress goes to the screen. At the end it prints **one line** like
`{"test_id": "T-0001", "attempt_id": "A-…", "run_id": "…", "thread_id": "…", "status": "done"}`.
`"status": "done"` is what we need.

**5. Record a blank test.** Same command with the photo(s) of a test that has **no answers
written on it**, into `tests/cassettes/blank`:
```powershell
uv run erh record --out tests/cassettes/blank -- run --data ..\.devdata\rec-blank --spawn-ollama --pages "<path to blank page 1>:0" "<path to blank page 2>:0"
```
It should end with `"status": "done"` and `"attempt_id": null` (a blank test has no attempt).

**6. Scrub the student's name and class.** Put the **real** name and class of the student in S1
(and of the blank test, if a name is written on it). Run it once per folder:
```powershell
uv run erh scrub tests/cassettes/s1 --name "<the student's real name>" --class "<class>"
uv run erh scrub tests/cassettes/blank --name "<the student's real name>" --class "<class>"
uv run erh scrub --check tests/cassettes
```
The last command must print nothing and exit without an error (`$LASTEXITCODE` is `0`).

**7. Search for the real name and class.** Each search must find **nothing**. Search both with
and without accents (for example `Nguyễn Văn An` and `Nguyen Van An`), and the class (`8A1`):
```powershell
Select-String -Path tests\cassettes\s1\*, tests\cassettes\blank\* -Pattern "<name with accents>", "<name without accents>", "<class>" -SimpleMatch
```
Then **read the cassettes by hand**: open each `NNN-*.json` in `tests\cassettes\s1` and
`tests\cassettes\blank` and look for the name, the school, or anything else about the student.
`input.json` holds only the file names and page sizes; the `page-NN.png` files are blank
stand-ins (no photo is stored).

**8. Run the replay tests.**
```powershell
uv run pytest tests/replay -q -rs
```
Every test must **pass**. R9.2 and R9.13 on `s1` (`test_r9_2_recorded_s1`,
`test_r9_13_recorded_s1_run`, `test_r9_13_recorded_s1_stop_resume`) must pass, **not skip**.
If one fails, don't commit: send the output to the orchestrator (see below).

**9. Sign off.**
```powershell
cd D:\Projects\Exam_Revision_Helper
git add sidecar/tests/cassettes/s1 sidecar/tests/cassettes/blank
git commit -m "👤 sign-off: cassettes extract"
```
If PowerShell mangles the emoji, commit from **Git Bash** instead (same two commands, after
`cd /d/Projects/Exam_Revision_Helper`). Check the result with `git log -1 --format=%s`: it must
start with `👤 sign-off:`.

## If a run fails

- `erh run` ends with a non-zero exit code and writes the reason to the screen (for example a
  missing model, or `"status": "failed"` with the error).
- **Keep the files.** The data folder (`.devdata\rec-s1` or `.devdata\rec-blank`) holds the
  database and the Ollama log (`logs\ollama-serve.log`); the cassettes recorded so far stay in
  `tests\cassettes\…`. Don't commit them.
- Send the orchestrator the full screen output and the last lines of the Ollama log:
  ```powershell
  Get-Content ..\.devdata\rec-s1\logs\ollama-serve.log -Tail 50
  ```
- To try again, start from step 3 (it removes the old folders).
- If the machine hangs or you close the window mid-run, the private Ollama may still be running:
  `Get-Process ollama*` shows it; end it with `Stop-Process -Name ollama -Force` (your own Ollama
  restarts from its tray icon).
