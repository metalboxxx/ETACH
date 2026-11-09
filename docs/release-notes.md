# Release notes

## Build and app folder (every version)

### Build

- Command: `cd app && npm run tauri build` (`TAURI_BUILD`). `npm run tauri` runs `src-tauri/tauri-cli.mjs`, which adds
  `src-tauri/tauri.release.conf.json` to a release `build`. That config freezes the sidecar first
  (`npm run freeze:sidecar` = `uv run pyinstaller etach.spec`, folder mode), ships `sidecar/dist/etach-sidecar/` as Tauri resources in
  `<app>\sidecar\`, and bundles an NSIS installer.
- Toolchain: tauri-cli 2.12.1, PyInstaller 6.22.3 (dev dependency only), Python 3.12.
- On its first NSIS bundle the Tauri CLI downloads NSIS and `nsis_tauri_utils.dll` into `%LOCALAPPDATA%\tauri` on the
  build machine. That is build tooling, not the app; the installed app writes nothing there.
- Models are not in the installer: the first-run screen downloads them into `<app>\data\models` (Ollama's
  `OLLAMA_MODELS`).
- Antivirus: each version's installer, frozen sidecar folder and shell exe are scanned with Windows Defender
  (`MpCmdRun -Scan -ScanType 3 -File <path> -DisableRemediation`, no elevation needed). What keeps false alarms down:
  PyInstaller **folder** mode (no self-extracting one-file exe) and no UPX packing (`upx=False` in `etach.spec`). The
  binaries are not code-signed, so Windows SmartScreen may still warn on the first start of the installer ("More
  info" → "Run anyway").

### App folder (PRD §11)

- The installer's default folder is `D:\ETACH`, or `%USERPROFILE%\ETACH` on a laptop without a D: drive. Tauri's own
  default for a per-user install is `%LOCALAPPDATA%\<product>`.
- `src-tauri/nsis/installer.nsi` is Tauri's template (tauri-cli 2.12.1) with three changes, each marked "ETACH change".
  When the Tauri CLI is upgraded, re-extract its template and re-apply all three:
  1. `.onInit`: the default install folder above (instead of `%LOCALAPPDATA%\<product>`).
  2. Uninstall: a real uninstall always deletes the install-folder record (`HKCU\Software\etach\ETACH`, and the
     parent key when empty). Tauri's template deletes it only when "delete app data" is ticked. An update
     (`/UPDATE`) keeps it, as in Tauri's template.
  3. Uninstall: the "Delete all app data (tests, students, backups)" box, ticked, also deletes `<app>\data`,
     `<app>\exports`, `<app>\webview` and `<app>\settings.json`, and then the app folder if it is empty. Unticked, or
     on an update (`/UPDATE`), they stay.
- The frozen sidecar runs in place (folder mode: no `_MEI*` unpacking into `%TEMP%`). The shell starts it with
  `ETACH_APP_DIR=<app>` and the app folder as its working folder, so its data is `<app>\data`.
- Since PRD v9.1 the frozen sidecar is `<app>\sidecar\etach-sidecar.exe` (0.6.1 and earlier: `erh.exe`). An update
  over 0.6.1 leaves the old `sidecar\erh.exe`, `sidecar\_internal\erh\` (prompts, migrations) and
  `sidecar\_internal\erh-*.dist-info` in place, unused; the uninstaller does not remove them either. They can be
  deleted by hand.
- Outside the app folder, the installer writes only what Windows needs to list, start and remove the app. The teacher
  accepted these as exceptions to PRD §11 on condition that their locations are recorded here. The uninstaller
  (`<app>\uninstall.exe`, or Settings → Apps → ETACH) removes all four: the two shortcuts, the uninstall entry and
  the install-folder record. To remove them by hand:

  | What | Location |
  |---|---|
  | Start-menu shortcut | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\ETACH.lnk` |
  | Desktop shortcut | `%USERPROFILE%\Desktop\ETACH.lnk` |
  | Uninstall entry (Windows' Apps list) | registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\ETACH` |
  | Install-folder record | registry `HKCU\Software\etach\ETACH` (the parent key goes when empty) |

  For example: `reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\ETACH" /f` and
  `reg delete "HKCU\Software\etach" /f`, then delete the two `.lnk` files and the app folder.
- The shell is built with Tauri's `devtools` feature, but a release build keeps the WebView2 DevTools off unless
  `ETACH_WEBVIEW_DEVTOOLS=1` is set (only `E2E_SHELL --release` sets it: with DevTools off, msedgedriver cannot reach the
  page).
- If WebView2 were missing, the installer would download its bootstrapper (Tauri's default). Windows 11 ships
  WebView2. The uninstaller leaves WebView2 (a shared Windows component) and the downloaded
  `%TEMP%\MicrosoftEdgeWebview2Setup.exe` in place.

### First run

The app shows a setup screen while `GET /system/status` is not `ok` (hidden in replay mode, or after
"Continue anyway"):

| Status | The screen shows |
|---|---|
| `unreachable` (Ollama missing or not running) | "Install Ollama": opens `ollama.com/download` in the browser; then reopen the app |
| `too_old` (older than 0.12.11) | "Update Ollama", same page |
| `missing_model` | **Download models** with per-model progress |

The app itself requests nothing outside 127.0.0.1; the download page opens in the teacher's browser.

Versions before 0.6.0 (0.1.0–0.5.0) are in git history and the session logs.


## 0.6.1 (plan step 22.6.8: the teacher's sixth look), 2026-11-02

### Build

- Command: `cd app && npm run tauri build` (`TAURI_BUILD`, see "Build and app folder" above), from `abe9150` (after the light
  window frame, D18): exit 0, `Finished 1 bundle`, output `ETACH_0.6.1_x64-setup.exe`.
- Version 0.6.1 in `app/package.json`, `app/src-tauri/tauri.conf.json`, `app/src-tauri/Cargo.toml`,
  `sidecar/pyproject.toml` and `sidecar/src/erh/__init__.py`, with their lock files and `sidecar/schema/openapi.json`;
  `erh --version` prints `0.6.1`.
- The product name, app ID (`vn.etach.app`) and program file (`ETACH.exe`) are the same as 0.6.0, so the installer
  updates 0.6.0 in place.
- `target\release\sidecar\erh.exe --version` prints `0.6.1`, and `_internal\` holds only `erh-0.6.1.dist-info`; the
  folder has the same 177 files as `sidecar\dist\erh\` (0.6.0's 175 plus the two new prompt files
  `prompts/base/ocr_format_page.md` and `prompts/examples/photo_rules.md`).

### Sizes

| Item | Size |
|---|---|
| Installer `ETACH_0.6.1_x64-setup.exe` | 44,837,947 bytes (42.76 MiB) |
| Frozen sidecar folder (`sidecar\`: `erh.exe` + `_internal\`, 177 files) | 107,807,117 bytes (102.81 MiB) |
| Shell `ETACH.exe` | 10,358,784 bytes (9.88 MiB) |

Compared with 0.6.0: installer +33,863 bytes, sidecar +35,187 bytes, shell exe +15,360 bytes (the new icon and the
round's code). Models are still not in the installer.

### Antivirus scan

Windows Defender (`MpCmdRun -Scan -ScanType 3 -File <path> -DisableRemediation`), signature version 1.463.83.0,
2026-11-02, no elevation needed:

- `...\target\release\bundle\nsis\ETACH_0.6.1_x64-setup.exe`: `found no threats`.
- `...\target\release\sidecar` (the frozen sidecar folder): `found no threats`.
- `...\target\release\ETACH.exe`: `found no threats`.

The same build settings as every version (PyInstaller folder mode, no UPX, not code-signed).

### What changed since 0.6.0

From the teacher's sixth look at 0.6.0 (plan steps 22.6.1–22.6.7; the details and decisions D1–D17 are in
`docs/initial-plan/plan.md` and `docs/initial-plan/phases-testing/step22.6-plan.md`):

- **Test photos are structured by code (22.6.5, 22.6.6, D7, D16).** GLM-OCR still reads the photo; the app now turns
  its text into sections and questions with its own rules instead of asking qwen3.5:4b. In the teacher's check (Test
  G8 and Test K) this found all 40 questions on both, with no repeats, in about half the time (257 s and 229 s instead
  of 482 s and 388 s). The two older ways stay in the settings file (`[extract] photo_structure` = `qwen` or
  `ocr_format`).
- **Answer boxes (22.6.1, D2).** The "Phần trả lời" box and rows of numbered blanks on a photo are left out, so they
  no longer become extra questions. A question that is only a number and its options keeps no repeated options.
- **Blank papers (22.6.2, D5).** When fewer than 20% of a paper's answers are read with confidence, it counts as
  blank: the thread becomes a test-only thread, and the student's answers are not kept.
- **The key is made after every extraction (22.6.4, D4, D11–D14).** Each extraction queues the key in the
  background, with or without a key photo; no notice pops up for it. While it is made, the Key tab is empty and
  **Grade** waits, greyed out, with "Making the key…". Extract again and deleting the thread, test or student stop it
  first.
- **The checker may say it is not sure (22.6.3, D6).** Hovering over "AI unsure key" can now say "The checker was not
  sure."
- **Editing a test during grading (22.6.6, D15).** When the test is changed while a paper is graded, the grading
  picks up the change; keys the teacher typed are kept.
- **The logo (22.6.7, D17).** The app has its own icon, the teacher's design: a lime E on a deep navy tile, on the
  window, the taskbar, the program file and the installer. The window's title bar and frame stay light even when
  Windows uses its dark theme (D18), so the logo shows.

### Known limits (the teacher's GPU check, 2026-11-01)

- **Code structuring was tuned on two papers of one layout** (Test G8 and Test K). Step 22's held-out papers are its
  real test.
- **Its misses seen so far** (the page is flagged for Review): options that start on the next page become a passage
  (Test G8: question 21); a first heading misread by the OCR ("1") or missing leaves the section untitled or with a
  digit as title, and its skill `mixed`; a sign's text stays in the question's stem; an option letter misread by the
  OCR stays as read (Test G8: 28's "A. so B. and D. but D. that"). Check a photo test's page after extraction.
- **The key takes several minutes** after extraction (Test G8: 546 s, Test K: 399 s), and many keys stay "AI
  unsure" (G8: 11 of 38, K: 18 of 35).
- The limits of 0.6.0 on student answers, typed PDFs and True/False letters still apply.

### Database changes

None since 0.6.0.

### Updating from 0.6.0

1. Close ETACH.
2. Run `ETACH_0.6.1_x64-setup.exe` and keep the folder `D:\ETACH`. Windows SmartScreen may warn, as before ("More
   info" → "Run anyway"). The data in `D:\ETACH\data` stays.
3. Start ETACH. Settings shows version 0.6.1, and the new icon is on the window and the taskbar. No new model is
   needed.

## 0.6.0 (plan step 22.5.8: the teacher's fifth review and both quality plans; the app is now ETACH), 2026-10-28

### Build

- Command: `cd app && npm run tauri build` (`TAURI_BUILD`, see "Build and app folder" above). Rebuilt on 2026-10-28 from `ed27d65`
  (after the theme, font, ETACH name and layout, plan step 22.5.8 (f)–(h)): exit 0, `Finished 1 bundle`, output
  `ETACH_0.6.0_x64-setup.exe`. The later commits change only `docs/`. The first 0.6.0 build (2026-10-26, `faf27f4`,
  still under the old name) was never installed and is replaced by this one.
- Version 0.6.0 in `app/package.json`, `app/src-tauri/tauri.conf.json`, `app/src-tauri/Cargo.toml`,
  `sidecar/pyproject.toml` and `sidecar/src/erh/__init__.py`, with their lock files and `sidecar/schema/openapi.json`;
  `erh --version` prints `0.6.0`.
- The product name is **ETACH**, the Windows app ID `vn.etach.app` and the program file `ETACH.exe`, so Windows sees
  0.6.0 as a new app next to the old app (0.5.0): the installer does not offer to update or uninstall 0.5.0
  (see "Installing 0.6.0 as ETACH" below).
- `target\release\sidecar\erh.exe --version` prints `0.6.0`, and `_internal\` holds only `erh-0.6.0.dist-info`; the
  folder has the same 175 files as `sidecar\dist\erh\`.

### Sizes

| Item | Size |
|---|---|
| Installer `ETACH_0.6.0_x64-setup.exe` | 44,804,084 bytes (42.73 MiB) |
| Frozen sidecar folder (`sidecar\`: `erh.exe` + `_internal\`, 175 files) | 107,771,930 bytes (102.78 MiB) |
| Shell `ETACH.exe` | 10,343,424 bytes (9.86 MiB) |

Compared with the first 0.6.0 build: installer −476.6 KB and shell exe −484.4 KB (one font, Faustina, plus the small
Federo wordmark font, instead of Be Vietnam Pro and Noto Serif); the sidecar is unchanged. Compared with 0.5.0 the
installer is about 375 KB smaller. Models are still not in the installer.

### Antivirus scan

Windows Defender (`MpCmdRun -Scan -ScanType 3 -File <path> -DisableRemediation`), signature version 1.463.1.0,
2026-10-28, no elevation needed:

- `...\target\release\bundle\nsis\ETACH_0.6.0_x64-setup.exe`: `found no threats`.
- `...\target\release\sidecar` (the frozen sidecar folder): `found no threats`.
- `...\target\release\ETACH.exe`: `found no threats`.

The same build settings as every version (PyInstaller folder mode, no UPX, not code-signed).

### What changed since 0.5.0

From the teacher's fifth review of the 0.5.0 app and both quality plans (plan steps 22.5.1–22.5.8; the details are in
`docs/initial-plan/plan.md` and `docs/initial-plan/phases-testing/step22.5-plan.md`):

- **Moving around and lists (22.5.1).** A test opened from the Tests tab looks like a thread's own test and has no
  Back button; clicking any thread in the sidebar closes it. The Tests list is A–Z by default (Grade 9 before Grade 10),
  with a sort button for Z–A, Newest added and By grade. Searching "T-0008" finds that test, and the "looks like"
  notice names the other test with its id. Editing a key or a student answer selects the old value, so typing
  replaces it. In the sidebar every name is cut at the same place.
- **Settings, series, test text, Extract again (22.5.2).** Settings has General · Models · Test attributes (Occasions,
  Schools, Series). The new **Series** list works like Schools and starts with the series already on the tests; "Same
  series as" picks a series name. Section headings no longer show points; one line under the test title gives each
  question's value. An untitled section gets its title from its skill ("PRONUNCIATION"). **Extract again** now updates
  the same test instead of adding a new one, and keeps the keys of unchanged questions.
- **Answer forms (22.5.3).** The question types are replaced by four answer forms (choice, word, sentence, writing).
  True/False questions get T and F options, also when the paper prints "A. FALSE / B. TRUE"; a key photo's or a
  student's "B" on such a question is stored as the matching T or F (22.5.8).
- **Grading (22.5.4–22.5.5).** The grading calls see each question's printed opening words; the judge gives its
  reason first. The difficulty notes are gone. Hovering over "AI unsure key" shows the checker's own answer and
  reason. Each paper has a **date taken** (set on the upload card, editable on the Student answers tab). Weak points
  now follow the student over time (improved, slipped, inconsistent, consistently weak), basics first, with levels;
  clicking a student on the Students tab opens **Skills — {student}**.
- **Typed files and reading (22.5.6).** A typed PDF is no longer cut at the printer's page breaks, so a section split
  across two pages stays one section. Each page's student answers are read only for the questions printed on it. A
  key read from a key photo shows as "from the key photo" unless a second check agreed.
- **Photos (22.5.7).** A question or passage cut by a page break is joined. **Test photos are now read by GLM-OCR**
  (`glm-ocr`, a 0.9B text reader; see "The new model" below); student answers are still read by qwen3.5:4b. The Models
  tab calls the two roles **Test reader** and **Student answer reader**.
- **The teacher's answers (22.5.8).** The Extract again line says "Test details and keys on unchanged questions
  stay". When a key photo replaces an AI key, that question's open "AI unsure key" item closes by itself. Fixing an
  unmatched key-photo key onto a True/False question stores T or F.
- **A new look and a new name (22.5.8 (f)–(h)).** The app is now **ETACH** ("English Test Assistant - Curate &
  Help"), with its wordmark at the top of the sidebar. The theme is light only (no dark mode): a near-white page,
  near-black text and a blue for buttons, links and the selected tab, dark navy on hover. Correct, unsure and wrong
  are shown in green, ochre and brick; the ✓ and ✗ marks and the skill labels "improved" and "inconsistent" sit on
  small coloured badges. The whole app uses one font, **Faustina**, with larger labels on the main buttons and tabs.
  Corners are almost square, like paper; the workspace is a sheet of paper under arch-topped tabs; the sidebar's
  Chats · Tests · Students tabs open onto a white page, the open thread is tinted, Chats has the students' names as
  small-capital headings, and Settings is a labelled row. The New thread screen is a dotted, page-shaped box to drop
  photos into. Every sidebar control shows a blue outline when reached with the keyboard.

### The new model

- **GLM-OCR reads test photos.** In the teacher's GPU check on Test G (`docs/initial-plan/phases-testing/step22.5-plan.md` §7 "G4
  result"), it found 42 questions for the 40 printed (0.5.0's reader: 51), kept the word-form sentences 29–34 that
  0.5.0 lost, and needed about 8 small edits instead of about 20 plus typing. A photo test takes about one minute
  longer (552 s against 495 s for Test G with its student paper).
- **A download of about 2.2 GB.** The first start of 0.6.0 lists `glm-ocr` among the missing models and offers
  **Download models**, as for the other models. Without it, reading a test photo fails with a message naming the model.
- The half-page re-read (tiles) stays off: in the check it added 3–7 minutes and improved nothing.

### Known limits (the teacher's GPU checks, 2026-10-24 to 2026-10-26)

- **Test photos (GLM-OCR):** some section titles come out as a bare numeral or letter ("2", "I", "A"); a question
  can repeat the previous number (Test G: 22 read as a second 21); opening words can land in the cue field (Test G:
  37's "Unless …"); an answer box can still become extra questions (Test G: 35–36). Check a photo test's page after
  extraction.
- **Student answers** written on another page than their question are not read (they show as blank).
- **Typed PDFs:** rare cases in matching questions back to their page (`step22.5-plan.md` §6), not seen on the
  teacher's tests.
- After the test text is edited and saved, a True/False question no longer knows its printed A/B letters, so a key
  photo read later stores its letter as written.

### Database changes

Five database migrations were added since 0.5.0 (`0011`: the `series` table, seeded from the tests' series names;
`0012`: answer forms, with a one-time pass over the stored tests that also relabels True/False options as T/F;
`0013`: drops the stored difficulty notes; `0014`: the checker's answer, the date taken and the skill levels;
`0015`: the key-photo key state). They run by themselves on the first start, so 0.6.0 opens the 0.5.0 data once it
has been copied into the new app folder (below).

### Installing 0.6.0 as ETACH

Windows treats ETACH as a new app, so it is installed next to 0.5.0 and the data is copied across once, by hand
(the teacher's choice: no installer or app code for a one-time move).

1. Close the old app (0.5.0).
2. Run `ETACH_0.6.0_x64-setup.exe`. Windows SmartScreen may warn, as before ("More info" → "Run anyway"). Keep the
   default folder `D:\ETACH`. Do not start ETACH at the end yet (untick "Run ETACH" if offered).
3. Copy the data with the script the orchestrator gives (reviewed before it runs): it copies `data\` (the database,
   files, models, `models.toml`, backups) and `settings.json` from the old app folder to `D:\ETACH` and compares
   file counts and sizes. The old folder is left untouched.
4. Start ETACH with Ollama available. The first start applies the five migrations and offers to download `glm-ocr`
   (about 2.2 GB). Settings shows version 0.6.0; the tests, students and threads of 0.5.0 are there.
5. Only then uninstall the old app (Windows Settings → Apps). Its "Delete all app data" box may be ticked
   or not; the data now lives in `D:\ETACH`. Afterwards the old app folder can be deleted.

What is written outside the app folder is the four kinds of item listed under "App folder" above, under
the new name: the install-folder record `HKCU\Software\etach\ETACH`, the uninstall entry
`HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\ETACH`, and the shortcuts `ETACH.lnk` in the Start menu and
on the desktop.
