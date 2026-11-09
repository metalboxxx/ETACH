# Step 11: checking and signing off fixture 1 (the teacher's runbook)

Fixture 1 is the worked example **Lớp 8 HK1 Đề 1**, in `fixtures\tuning\lop8-hk1-de1\`. An agent
has drafted its `expected.json` from the photos. You correct it, sign it, write the manifest and
commit the manifest in a `👤 sign-off:` commit (plan Step 11, R11.3).

**No agent runs while you do this.** Close Claude Code sessions for this project first.

The fixture folder is **gitignored** (it holds the student's name and handwriting). Only
`fixtures\MANIFEST.sha256` (and `eval-history.csv`, if you run the baseline) is committed.

Run everything in **PowerShell**, in order.

## What is in the folder

```
fixtures\tuning\lop8-hk1-de1\
  pages\Lop8-HKI-De1 (1).jpg  (2).jpg  (3).jpg   the photos
  input.json      page order (3), (2), (1) as in step 9, rotation 0, no key page
  expected.json   the drafted truth: meta, sections, questions, the student's answers, name/class
```

The file has the same shape as a test in the app: each **section** holds one or more **groups**,
and each group is a passage (`stimulus`, or `null` when there is none) followed by its questions.
For example, section IV (shortened):

```json
{"printed_title": "IV", "instructions": "Choose the word (A, B, C, or D) that best fits ...",
 "printed_points": null, "skill": "reading", "kind": "questions",
 "groups": [{"stimulus": "**How to Cook Giant Spiders**\nIn the Southeast Asian country ... and (17) ____ minutes later ...",
             "pictures": [],
             "questions": [{"printed_number": 17, "type": "mcq", "stem": null,
                            "options": ["much", "more", "less", "a few"], "cue": null, "page_no": 2}]}]}
```

In a cloze passage the blanks are written `(17) ____` inside the passage, and those questions have
`"stem": null`. The full format is described at the top of `sidecar\src\erh\eval\fixtures.py`. Page numbers
(`page_no`) count in `input.json` order: page 1 = `(3).jpg`, page 2 = `(2).jpg`, page 3 = `(1).jpg`.

## How to do it

**1. Correct the draft.** Open the file and the photos side by side:
```powershell
cd D:\Projects\Exam_Revision_Helper
notepad fixtures\tuning\lop8-hk1-de1\expected.json
explorer fixtures\tuning\lop8-hk1-de1\pages
```
Check every field against the paper:
- `meta`: occasion, grade, term, test number, variant, school, year;
- each section: the printed label (`printed_title`, e.g. `IV`), `instructions` and
  `printed_points` as printed, `kind`, `skill`;
- each group: the passage text (`stimulus`) and the `pictures` notes;
- each question: printed number, type, stem (blanks as `____`, underlines as `<u>…</u>`, bold as
  `**…**`), options (without `A.`), cue, `page_no`;
- `answers`: what the **student** wrote or circled, **mistakes included** (this is not the key);
  `null` if blank;
- `student`: name and class as written.

The questions the agent was **unsure of** are listed in the section "Unsure readings" below; look
at those first.

**2. Sign it.** Add these two fields at the end of the JSON object (after `"student": {…}`, with
a comma before them), with today's date:
```json
  "verified_by": "teacher",
  "verified_on": "2026-10-01"
```

**3. Validate.** It prints `OK` and the number of questions, or the first error:
```powershell
cd D:\Projects\Exam_Revision_Helper\sidecar
uv run python -c "from pathlib import Path; from erh.eval.fixtures import load_fixture; f = load_fixture(Path('../fixtures/tuning/lop8-hk1-de1')); print('OK', len(f.expected.question_keys()), 'questions,', f.expected.verified_by)"
```
Fix and rerun until it prints `OK … teacher`.

**4. Write the manifest.**
```powershell
uv run erh fixtures manifest
Get-Content ..\fixtures\MANIFEST.sha256
```
It must show one line ending in
`tuning/lop8-hk1-de1/expected.json  verified_by: teacher`. If you edit `expected.json` again
later, rerun this step (the line holds the file's hash).

**5. Optional baseline** (about 7 minutes, uses the GPU). It extracts the fixture with the real
models and appends the first real row to `eval-history.csv`:
```powershell
uv run erh eval --graph extract --set tuning --spawn-ollama
```

**6. The sign-off commit.** The message must start with the 👤 emoji as real UTF-8 bytes; this
method is known to work in Windows PowerShell 5.1:
```powershell
cd D:\Projects\Exam_Revision_Helper
$enc = New-Object System.Text.UTF8Encoding $false
$msg = [Text.Encoding]::UTF8.GetString([byte[]](0xF0,0x9F,0x91,0xA4)) + " sign-off: fixture lop8-hk1-de1`n"
[IO.File]::WriteAllText("$env:TEMP\msg.txt", $msg, $enc)
git add fixtures/MANIFEST.sha256 eval-history.csv
git commit -F "$env:TEMP\msg.txt"
```
Leave out `eval-history.csv` from `git add` if you did not run step 5.

Git Bash alternative:
```bash
cd /d/Projects/Exam_Revision_Helper
git add fixtures/MANIFEST.sha256 eval-history.csv
printf '\xF0\x9F\x91\xA4 sign-off: fixture lop8-hk1-de1\n' > /tmp/msg.txt
git commit -F /tmp/msg.txt
```

**7. Check.**
```powershell
git log -1 --format=%s
git status --short --ignored fixtures
```
The subject should read `👤 sign-off: fixture lop8-hk1-de1` (the console may show the emoji
garbled; the orchestrator checks the bytes). `git status` must show only `!! fixtures/…`
(ignored) and nothing else under `fixtures/` except the committed manifest.

Then tell the orchestrator it is done.

## Unsure readings

The agent's draft is its best reading of the photos. The notes below list what was hard to read.

The draft has 8 sections (the listening part I is `kind: listening` with no questions; parts
II–VIII hold questions 5–40, 36 questions) and an answer for every one of them (no blanks read).
No section after III shows printed points on the photos, so their `printed_points` are `null`; the
second part printed "VI." (the dictionary part, really VII) keeps its printed label.

Check these first:

- **Each passage text** (`stimulus`), word by word against the paper: the cloze passage of IV
  (with its title), the letter of V, and the dictionary entry of the second VI. The dictionary
  entry is a small, faint screenshot: its text was read as well as possible (the phonetics
  `/ɪˈlektrɪk/` are printed twice, once per accent); fix it, or set it to `null` if unsure.
- **Skills** were chosen by the agent: II `mixed` (pronunciation, stress, grammar and
  communication together), III `signs`, IV `reading` (a cloze passage; `vocabulary` is
  arguable), V `reading`, VI `word_form`, second VI `vocabulary`, VIII `rewrite`.
- **III**: each sign is its own group with a picture note and no stimulus; the elevator notice's
  text is only in the note.
- **5**: the options' underlined letter was taken as the `a` in each word (br<u>a</u>celet, c<u>a</u>ke, m<u>a</u>ke, h<u>a</u>t).
- **10**: the circle around B is drawn over a corrected letter; read as `B`.
- **17–22**: the stems are `null` (the blanks are in the passage); the option rows are
  staggered on the photo (e.g. 17 = much / more / less / a few), check each row.
- **26**: the mark looks like a `T` written as `Y`; read as `T`.
- **32**: read as `adventurously`; check the spelling the student used.
- **35, 36**: "electric fields" is written just **above** the 35 blank and "electric power"
  just **below** the 36 blank; the draft gives 35 = `electric fields`, 36 = `electric power`
  by position, but it may be the other way round.
- **37–40**: the answers are the student's continuation after the printed lead-in
  (`My brother`, `Jimmy`, `In order to`, `Richard is not`), punctuation as written; check the
  exact words and commas (39: `let fresh air in, She opened the window`).
