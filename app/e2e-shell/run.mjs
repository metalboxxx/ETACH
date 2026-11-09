/**
 * E2E_SHELL (plan step 14): the real Tauri app, driven through tauri-driver + WebDriver.
 *
 *   R14.4  the app starts with a stub `ollama` (a test double first on PATH) and the replay
 *          sidecar; the frontend shows the ready state; closing the app → both child processes
 *          are gone within 5 s (tracked by PID, as descendants of the app process).
 *   R14.5  after a full app start and an S1 replay run, nothing was created or modified under
 *          %APPDATA% or %LOCALAPPDATA% by the app (before/after listing, paths newer than the start).
 *   R15.2  a real OS drop of 3 JPGs onto the window (OLE DoDragDrop through WebView2's native drop
 *          target, `real-drop.ps1`) → the photo check card shows 3 thumbnails. Needs an unlocked,
 *          interactive desktop: the helper brings the window to the front and holds the cursor on it.
 *   R20.7  portability: after the app is closed, the whole app folder is copied to a new location
 *          and the original deleted; the app started from the copy (`ETACH_APP_DIR` = the copy) shows
 *          the same threads and tests, opens the S1 thread, and loads a page image.
 *
 * `--release` (plan step 21, R21.2): the same phases against the RELEASE build (`npm run tauri
 * build`, which freezes the sidecar). The release exe and its `sidecar\` folder are copied into a
 * fresh app folder, the installed layout, and started WITHOUT `ETACH_APP_DIR`, so the app folder is
 * the exe's own folder, as on the teacher's laptop. It checks:
 *   R21.2  the frozen sidecar starts (`etach-sidecar.exe` under the app, no uv, no python.exe), and Settings
 *          shows its version, equal to `etach --version` (`uv run etach --version` in sidecar/, and
 *          the frozen `etach-sidecar.exe --version`);
 *   R20.7  in this mode the copy moves the packaged exe and the sidecar with the data
 *          (structure §7: the debug phase moves only the data folder).
 *
 * Prerequisites (docs/dev-setup.md): the debug build (`npm run tauri:build -- --debug`), or for
 * `--release` the release build (`npm run tauri build`); tauri-driver on PATH (cargo bin),
 * msedgedriver at D:\DevTools\msedgedriver (or $MSEDGEDRIVER).
 * Nothing here touches the internet: the sidecar replays cassettes; every request is 127.0.0.1.
 */
import { spawn, spawnSync } from "node:child_process";
import { cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve, sep } from "node:path";
import { remote } from "webdriverio";

const HERE = import.meta.dirname;
const APP = resolve(HERE, "..");
const REPO = resolve(APP, "..");
/** `--release`: run the release build with its frozen sidecar (R21.2). */
const RELEASE = process.argv.slice(2).includes("--release");
const EXE_NAME = "ETACH.exe";
/** The built exe; in `--release` mode it is copied into a fresh app folder before the start. */
const BUILT_EXE =
  process.env.ETACH_SHELL_EXE ?? join(APP, "src-tauri", "target", RELEASE ? "release" : "debug", EXE_NAME);
/** The release build's frozen sidecar folder (Tauri resources, copied next to the exe). */
const BUILT_SIDECAR = join(dirname(BUILT_EXE), "sidecar");
const CASSETTES = join(REPO, "sidecar", "tests", "cassettes", "s1");
const STUB_BIN = join(HERE, "stub-bin");
const MSEDGEDRIVER =
  process.env.MSEDGEDRIVER ?? "D:\\DevTools\\msedgedriver\\msedgedriver.exe";
const DRIVER_PORT = 4444;
const CHILDREN_GONE_MS = 5_000;

const failures = [];
function check(ok, what) {
  console.log(`${ok ? "PASS" : "FAIL"}  ${what}`);
  if (!ok) failures.push(what);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// --- AppData snapshot (R14.5) -------------------------------------------------------------------

const APPDATA = process.env.APPDATA;
const LOCALAPPDATA = process.env.LOCALAPPDATA;

/**
 * Paths under AppData that are not the app's writes. Each one says why. Anything else that is new
 * or modified fails the test; an AppData write by the app (WebView2, a Tauri default, the sidecar)
 * must be fixed in the shell, never added here.
 */
const EXCLUDED = [
  // The system temp folder (%TEMP%): appdir.py allows it too, and the test's own fresh app folder
  // lives there. Not AppData in the PRD §11 sense.
  [join(LOCALAPPDATA, "Temp"), "system temp folder (%TEMP%)"],
  // uv's cache: written by `uv run` (the development launcher of the sidecar). The packaged app
  // (step 21) runs a frozen sidecar without uv.
  [join(LOCALAPPDATA, "uv"), "uv cache (dev launcher of the sidecar, test tooling)"],
];

/**
 * Names that tie an AppData path to this app: the Tauri identifier and product name (Tauri's
 * app_data_dir/app_local_data_dir defaults), and the exe name (WebView2's default user data folder
 * is `%LOCALAPPDATA%\<exe>.WebView2\EBWebView`). Since 0.6.0 (PRD v8.18) the product is ETACH with
 * the identifier `vn.etach.app` and the exe `ETACH.exe` (`mainBinaryName`, PRD v8.26; `tauri build`
 * renames Cargo's `etach-shell.exe`). The old product and exe names stay listed, so a write
 * under them still fails. `<sep>etach` is a path segment that starts with the product name
 * (`\ETACH`, `\etach.lnk`, WebView2's `\ETACH.exe.WebView2`), not any word that contains it.
 */
const APP_MARKERS = [
  "vn.etach.app",
  "etach.exe",
  `${sep}etach`,
  "vn.examrevisionhelper.app",
  "examrevisionhelper",
  "exam revision helper",
  "exam-revision-helper",
];

/**
 * The teacher's machine runs other programs during the test (browsers, VS Code, Windows account
 * and cache services, GPU tools); they write inside their own, already existing AppData folders.
 * Those writes are not the app's, and attributing a write to a process needs a kernel tracer, so the
 * test fails on (a) any path that names the app (APP_MARKERS) and (b) any new folder at the first
 * two levels of %APPDATA% / %LOCALAPPDATA% (a new app/vendor folder, which is what a Tauri,
 * WebView2 or Python default would create). Writes inside other programs' existing folders are
 * listed as background noise, not failed.
 */
function isAppWrite(path) {
  const low = path.toLowerCase();
  if (APP_MARKERS.some((m) => low.includes(m))) return true;
  for (const root of [APPDATA, LOCALAPPDATA]) {
    const r = root.toLowerCase() + sep;
    if (!low.startsWith(r)) continue;
    const depth = low.slice(r.length).split(sep).length;
    if (depth <= 2) {
      try {
        return lstatSync(path).birthtimeMs > testStart;
      } catch {
        return false;
      }
    }
  }
  return false;
}
let testStart = 0;

function excludedBy(path) {
  const low = path.toLowerCase();
  for (const [root, why] of EXCLUDED) {
    const r = root.toLowerCase();
    if (low === r || low.startsWith(r + sep)) return why;
  }
  return null;
}

/** Every path under `root` (recursive, no symlink/junction following) with mtime > `since`. */
function changedSince(root, since, out = new Set()) {
  let entries;
  try {
    entries = readdirSync(root, { withFileTypes: true });
  } catch {
    return out; // unreadable: skipped
  }
  for (const e of entries) {
    const p = join(root, e.name);
    let st;
    try {
      st = lstatSync(p);
    } catch {
      continue;
    }
    if (st.mtimeMs > since || st.birthtimeMs > since) out.add(p);
    if (e.isDirectory() && !e.isSymbolicLink()) changedSince(p, since, out);
  }
  return out;
}

function snapshot(since) {
  const all = new Set();
  for (const root of [APPDATA, LOCALAPPDATA]) changedSince(root, since, all);
  return all;
}

// --- processes (R14.4) --------------------------------------------------------------------------

/** pid → {ppid, name} for every process. */
function processTable() {
  const r = spawnSync(
    "powershell.exe",
    [
      "-NoProfile",
      "-NonInteractive",
      "-Command",
      "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name | ConvertTo-Json -Compress",
    ],
    { encoding: "utf8", windowsHide: true },
  );
  const rows = JSON.parse(r.stdout);
  const table = new Map();
  for (const row of rows) table.set(row.ProcessId, { ppid: row.ParentProcessId, name: row.Name });
  return table;
}

function descendants(table, pid) {
  const out = [];
  const stack = [pid];
  while (stack.length) {
    const p = stack.pop();
    for (const [child, info] of table) {
      if (info.ppid === p && child !== p && !out.includes(child)) {
        out.push(child);
        stack.push(child);
      }
    }
  }
  return out;
}

// --- sidecar API (the S1 replay run) ------------------------------------------------------------

async function api(cfg, method, path, body, contentType = "application/json") {
  const res = await fetch(cfg.baseUrl + path, {
    method,
    headers: {
      Authorization: `Bearer ${cfg.token}`,
      ...(body !== undefined ? { "Content-Type": contentType } : {}),
    },
    body: body === undefined ? undefined : contentType === "application/json" ? JSON.stringify(body) : body,
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status}: ${text}`);
  return text ? JSON.parse(text) : null;
}

/** The S1 replay run, as the API tests do it: upload the stand-in pages, start an extract run. */
async function s1Run(cfg) {
  const manifest = JSON.parse(readFileSync(join(CASSETTES, "input.json"), "utf8"));
  const pages = [];
  for (const page of manifest.pages) {
    const bytes = readFileSync(join(CASSETTES, page.stand_in));
    const up = await api(
      cfg,
      "POST",
      `/files?name=${encodeURIComponent(page.original_name)}`,
      bytes,
      "application/octet-stream",
    );
    pages.push({ file_id: up.file_id, rotation: page.rotation, is_key: page.is_key, text_file_id: null });
  }
  const { thread_id } = await api(cfg, "POST", "/threads", {});
  const run = await api(cfg, "POST", `/threads/${thread_id}/runs`, {
    kind: "extract",
    input: {
      pages,
      existing_test_id: manifest.existing_test_id,
      supersedes_attempt_id: manifest.supersedes_attempt_id,
    },
  });
  const deadline = Date.now() + 120_000;
  for (;;) {
    const detail = await api(cfg, "GET", `/runs/${run.id}`);
    const status = detail.run.status;
    if (status === "done") return run.id;
    if (!["queued", "running"].includes(status)) throw new Error(`S1 run ended ${status}`);
    if (Date.now() > deadline) throw new Error("S1 run did not finish in 120 s");
    await sleep(250);
  }
}

// --- the app under tauri-driver ------------------------------------------------------------------

/** Starts tauri-driver and a WebDriver session on `exe` (the debug exe, or the copied release
 * exe), with `env`. */
async function launch(env, exe) {
  const driver = spawn("tauri-driver", ["--port", String(DRIVER_PORT), "--native-driver", MSEDGEDRIVER], {
    env,
    stdio: ["ignore", "inherit", "inherit"],
    windowsHide: true,
  });
  try {
    await sleep(1_500);
    const browser = await remote({
      hostname: "127.0.0.1",
      port: DRIVER_PORT,
      logLevel: "silent",
      connectionRetryTimeout: 240_000,
      capabilities: { browserName: "wry", "tauri:options": { application: exe } },
    });
    return { driver, browser };
  } catch (err) {
    spawnSync("taskkill", ["/pid", String(driver.pid), "/T", "/F"], { stdio: "ignore" });
    throw err;
  }
}

/** Waits for the app shell, connected (no connection notice). */
async function waitReady(browser) {
  const shell = await browser.$('[data-testid="app-shell"]');
  await shell.waitForExist({ timeout: 180_000 }).catch(async (err) => {
    const url = await browser.getUrl().catch((e) => String(e));
    const src = (await browser.getPageSource().catch((e) => String(e))).slice(0, 600);
    throw new Error(`${err.message}\n  url: ${url}\n  page: ${src}`);
  });
  // `$$` (all matches): `$` returns one element, whose `.length` is undefined, so it never passed.
  await browser
    .waitUntil(async () => (await browser.$$('[data-testid="connection-notice"]')).length === 0, {
      timeout: 60_000,
    })
    .catch(async () => {
      const state = await browser
        .execute(() => ({
          notice: document.querySelector('[data-testid="connection-notice"]')?.textContent ?? null,
          etach: window.__ETACH__ ? { baseUrl: window.__ETACH__.baseUrl, token: !!window.__ETACH__.token } : null,
        }))
        .catch((e) => String(e));
      throw new Error(`the connection notice stayed: ${JSON.stringify(state)}`);
    });
}

/** Removes a folder, retrying while WebView2 / SQLite still hold files for a moment. */
async function removeDir(dir, tries = 40) {
  for (let i = 0; i < tries; i++) {
    try {
      rmSync(dir, { recursive: true, force: true });
      return true;
    } catch {
      await sleep(500);
    }
  }
  return !existsSync(dir);
}

// --- portability (R20.7) ------------------------------------------------------------------------

/** What the first start created, read through the API before the app is closed. */
async function capture(cfg, runId) {
  const threads = (await api(cfg, "GET", "/threads")).map((t) => t.thread.id);
  const tests = (await api(cfg, "GET", "/tests")).map((t) => t.id);
  const run = await api(cfg, "GET", `/runs/${runId}`);
  const threadId = run.run.thread_id;
  const detail = await api(cfg, "GET", `/threads/${threadId}`);
  const pages = detail.attempt?.pages ?? (await api(cfg, "GET", `/attempts/${detail.attempt.id}`)).pages;
  return { threads, tests, threadId, fileId: pages[0].file_id };
}

const sameList = (a, b) => JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());

/** R20.7: copy the closed app's folder, delete the original, start from the copy. In `--release`
 * mode the folder holds the exe and the frozen sidecar too, and the copy starts without
 * `ETACH_APP_DIR` (its own folder is the app folder). */
async function portability(appDir, baseEnv, expected) {
  const moved = mkdtempSync(join(tmpdir(), "etach-shell-moved-"));
  for (let i = 0; ; i++) {
    try {
      cpSync(appDir, moved, { recursive: true, force: true });
      break;
    } catch (err) {
      if (i >= 19) throw err;
      await sleep(500);
    }
  }
  check(await removeDir(appDir), `R20.7 app folder copied to ${moved}; the original deleted`);

  const { driver, browser } = RELEASE
    ? await launch(baseEnv, join(moved, EXE_NAME))
    : await launch({ ...baseEnv, ETACH_APP_DIR: moved }, BUILT_EXE);
  try {
    await waitReady(browser);
    const cfg = await browser.execute(() => window.__ETACH__);
    const settings = await api(cfg, "GET", "/settings");
    check(
      resolve(settings.data_folder).toLowerCase().startsWith(resolve(moved).toLowerCase()),
      `R20.7 the sidecar uses the copied folder (${settings.data_folder})`,
    );

    const ids = (sel, attr) =>
      browser.execute((s, a) => [...document.querySelectorAll(s)].map((e) => e.getAttribute(a)), sel, attr);
    const waitIds = (sel, attr, n) =>
      browser
        .waitUntil(async () => (await ids(sel, attr)).length >= n, { timeout: 30_000, interval: 250 })
        .catch(() => {});
    const tab = (name) =>
      browser.execute(
        (t) => [...document.querySelectorAll('[role="tab"]')].find((b) => b.textContent === t)?.click(),
        name,
      );

    await waitIds('[data-testid="thread-item"]', "data-thread-id", expected.threads.length);
    const threads = await ids('[data-testid="thread-item"]', "data-thread-id");
    check(sameList(threads, expected.threads), `R20.7 the same threads shown (${threads.length}/${expected.threads.length})`);

    await tab("Tests");
    await waitIds('[data-testid="test-item"]', "data-test-id", expected.tests.length);
    const tests = await ids('[data-testid="test-item"]', "data-test-id");
    check(sameList(tests, expected.tests), `R20.7 the same tests shown (${tests.length}/${expected.tests.length})`);

    await tab("Chats");
    const item = await browser.$(`[data-testid="thread-item"][data-thread-id="${expected.threadId}"]`);
    await item.waitForExist({ timeout: 10_000 });
    await item.click();
    // Since step 22.3.2 an extracted thread opens straight into its workspace (no cards).
    const card = await browser.$('[data-testid="workspace"]');
    const opened = await card.waitForExist({ timeout: 30_000 }).then(
      () => true,
      () => false,
    );
    check(opened, "R20.7 the S1 thread opens into its workspace");

    const width = await browser.execute(
      (url) =>
        new Promise((done) => {
          const img = new Image();
          img.onload = () => done(img.naturalWidth);
          img.onerror = () => done(0);
          img.src = url;
        }),
      `${cfg.baseUrl}/files/${encodeURIComponent(expected.fileId)}?token=${encodeURIComponent(cfg.token)}`,
    );
    check(width > 0, `R20.7 a page image loads from the copied folder (width ${width})`);
    await browser.closeWindow().catch(() => {});
  } finally {
    await browser.deleteSession().catch(() => {});
    spawnSync("taskkill", ["/pid", String(driver.pid), "/T", "/F"], { stdio: "ignore" });
  }
  return moved;
}

// --- the real drop (R15.2) ----------------------------------------------------------------------

const REAL_DROP = join(HERE, "real-drop.ps1");

function ps(args) {
  return spawnSync(
    "powershell.exe",
    ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", REAL_DROP, ...args],
    { encoding: "utf8", windowsHide: true, timeout: 60_000 },
  );
}

async function realDrop(browser, appPid, appDir) {
  const made = ps(["-MakeJpgs", join(appDir, "drop-src")]);
  const files = made.stdout.split(/\r?\n/).filter((l) => l.endsWith(".jpg"));
  if (files.length !== 3) throw new Error(`synthetic JPGs not made: ${made.stdout}${made.stderr}`);
  // Centre of the conversation area, in CSS px of the viewport (= the window's client area).
  const at = await browser.execute(() => {
    const r = document.querySelector('[data-testid="conversation"]').getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, dpr: window.devicePixelRatio };
  });
  const r = ps([
    "-AppPid", String(appPid),
    "-X", String(at.x),
    "-Y", String(at.y),
    "-Dpr", String(at.dpr),
    "-Files", files.join(","),
  ]);
  const line = (r.stdout + r.stderr).trim();
  check(r.status === 0, `R15.2 OLE DoDragDrop onto the WebView2 window accepted (${line})`);
  const thumbs = async () =>
    (await browser.$$('[data-testid="photo-check-card"] [data-testid="photo-thumb"]')).length;
  await browser.waitUntil(async () => (await thumbs()) === 3, { timeout: 20_000, interval: 250 }).catch(() => {});
  const cards = (await browser.$$('[data-testid="photo-check-card"]')).length;
  const n = await thumbs();
  check(cards === 1 && n === 3, `R15.2 real drop → photo check card with 3 thumbnails (cards ${cards}, thumbs ${n})`);
}

// --- the release build (R21.2) ------------------------------------------------------------------

/** `etach --version` from the source (`uv run`) and from the frozen sidecar. */
function etachVersions(frozenExe) {
  const run = (cmd, args, cwd) => {
    const r = spawnSync(cmd, args, { cwd, encoding: "utf8", windowsHide: true, timeout: 120_000 });
    return `${r.stdout ?? ""}${r.stderr ?? ""}`.trim();
  };
  return {
    source: run("uv", ["run", "etach", "--version"], join(REPO, "sidecar")),
    frozen: run(frozenExe, ["--version"], dirname(frozenExe)),
  };
}

/** The installed layout: the release exe and its `sidecar\` folder in a fresh app folder. */
function installCopy(appDir) {
  cpSync(BUILT_EXE, join(appDir, EXE_NAME));
  cpSync(BUILT_SIDECAR, join(appDir, "sidecar"), { recursive: true });
  return join(appDir, EXE_NAME);
}

/** R21.2: Settings shows the frozen sidecar's version, equal to `etach --version`. */
async function settingsVersion(browser, versions) {
  await browser.execute(() =>
    [...document.querySelectorAll("button")]
      .find((b) => b.getAttribute("aria-label") === "Settings" || b.textContent.trim() === "Settings")
      ?.click(),
  );
  const el = await browser.$('[data-testid="sidecar-version"]');
  await el.waitForExist({ timeout: 30_000 }).catch(() => {});
  await browser
    .waitUntil(async () => (await el.getText().catch(() => "")).trim() !== "", { timeout: 30_000, interval: 250 })
    .catch(() => {});
  const shown = (await el.getText().catch(() => "")).trim();
  check(
    shown !== "" && shown === versions.source && shown === versions.frozen,
    `R21.2 Settings shows the sidecar version ${JSON.stringify(shown)} = etach --version ` +
      `${JSON.stringify(versions.source)} (frozen etach-sidecar.exe --version ${JSON.stringify(versions.frozen)})`,
  );
}

// --- main ---------------------------------------------------------------------------------------

async function main() {
  for (const [what, p] of [
    RELEASE
      ? ["release build (npm run tauri build)", BUILT_EXE]
      : ["debug build (npm run tauri:build -- --debug)", BUILT_EXE],
    ...(RELEASE ? [["the frozen sidecar next to the release exe", join(BUILT_SIDECAR, "etach-sidecar.exe")]] : []),
    ["msedgedriver", MSEDGEDRIVER],
    ["S1 cassettes", CASSETTES],
  ]) {
    if (!existsSync(p)) throw new Error(`missing ${what}: ${p}`);
  }
  if (!existsSync(join(APP, "dist", "index.html"))) throw new Error("missing app/dist: npm run build");

  const appDir = mkdtempSync(join(tmpdir(), "etach-shell-"));
  // `--release`: the installed layout (exe + sidecar folder in the app folder), no ETACH_APP_DIR.
  const exe = RELEASE ? installCopy(appDir) : BUILT_EXE;
  // The S1 cassettes were recorded with the vision photo reader; since R22.5.7.7 the default is
  // the OCR reader, so the app's data folder pins `[extract] photo_reader = "vision"`; and
  // `blank_share = 0` (the blank rule before step 22.6.2: S1 reads 1 of 34 answers sure).
  mkdirSync(join(appDir, "data"), { recursive: true });
  writeFileSync(
    join(appDir, "data", "models.toml"),
    '[extract]\nphoto_reader = "vision"\nblank_share = 0\n',
    "utf8",
  );
  const versions = RELEASE ? etachVersions(join(appDir, "sidecar", "etach-sidecar.exe")) : null;
  if (versions) console.log(`etach --version: source ${versions.source}; frozen ${versions.frozen}`);
  const start = Date.now() - 2_000; // a margin for coarse mtimes
  testStart = start;
  const before = snapshot(start);
  console.log(`app folder: ${appDir}; AppData paths already newer than the start: ${before.size}`);

  const env = {
    ...process.env,
    PATH: `${STUB_BIN};${process.env.PATH}`,
    ETACH_SIDECAR_REPLAY: CASSETTES,
  };
  if (RELEASE) {
    delete env.ETACH_APP_DIR; // the exe's own folder is the app folder
    // A release build turns the WebView2 DevTools off, which also hides the page from
    // msedgedriver (the session only saw about:blank); the shell turns them on for this test.
    env.ETACH_WEBVIEW_DEVTOOLS = "1";
  } else env.ETACH_APP_DIR = appDir;
  console.log(`mode: ${RELEASE ? "release (frozen sidecar)" : "debug (uv sidecar)"}; exe: ${exe}`);
  const { driver, browser } = await launch(env, exe);
  let expected = null;
  try {
    // R14.4: the ready state
    await waitReady(browser);
    check(true, "R14.4 app-shell shown, no connection notice");

    const table = processTable();
    const appPid = [...table].find(
      ([pid, info]) => info.name.toLowerCase() === basename(exe).toLowerCase() && descendants(table, driver.pid).includes(pid),
    )?.[0];
    if (!appPid) throw new Error("app process not found under tauri-driver");
    const direct = [...table].filter(([, i]) => i.ppid === appPid).map(([pid, i]) => ({ pid, name: i.name }));
    const ollama = direct.filter((c) => c.name.toLowerCase() === "cmd.exe");
    const sidecar = direct.filter((c) => c.name.toLowerCase() === (RELEASE ? "etach-sidecar.exe" : "uv.exe"));
    check(ollama.length === 1, `R14.4 stub ollama running under the app (${JSON.stringify(direct)})`);
    const tracked = [
      ...ollama.flatMap((c) => [c.pid, ...descendants(table, c.pid)]),
      ...sidecar.flatMap((c) => [c.pid, ...descendants(table, c.pid)]),
    ];
    if (RELEASE) {
      check(sidecar.length === 1, "R21.2 the frozen sidecar (etach-sidecar.exe) runs under the app");
      const names = [...direct.map((c) => c.pid), ...tracked].map((pid) => table.get(pid)?.name.toLowerCase());
      check(
        !names.includes("uv.exe") && !names.includes("python.exe"),
        "R21.2 no uv.exe / python.exe: the release shell does not use the development launcher",
      );
    } else {
      check(sidecar.length === 1, "R14.4 uv sidecar running under the app");
      check(
        tracked.some((pid) => table.get(pid)?.name.toLowerCase() === "python.exe"),
        "R14.4 python sidecar under uv",
      );
    }

    // R14.5: an S1 replay run through the injected config
    const cfg = await browser.execute(() => window.__ETACH__);
    check(/^http:\/\/127\.0\.0\.1:\d+$/.test(cfg.baseUrl) && !!cfg.token, "window.__ETACH__ injected");
    const runId = await s1Run(cfg);
    check(true, `R14.5 S1 replay run ${runId} done`);
    check(existsSync(join(appDir, "data", "app.db")), "sidecar data in <app>\\data");
    if (RELEASE) {
      check(
        !existsSync(join(appDir, "sidecar", "data")),
        "R21.2 the frozen sidecar writes to <app>\\data, not <app>\\sidecar\\data",
      );
      await settingsVersion(browser, versions);
      await browser.keys("Escape").catch(() => {}); // close the Settings panel before the drop
    }

    // R15.2: a real OS drop of 3 synthetic JPGs onto the conversation area
    await realDrop(browser, appPid, appDir);

    // R20.7: what the copy must show, read last (the drop above creates a second, empty thread).
    expected = await capture(cfg, runId);

    // R14.4: close the app → the children are gone within 5 s
    const closedAt = Date.now();
    await browser.closeWindow().catch(() => {});
    let alive = tracked;
    while (Date.now() - closedAt < CHILDREN_GONE_MS) {
      const now = processTable();
      alive = tracked.filter((pid) => now.has(pid));
      if (alive.length === 0) break;
      await sleep(250);
    }
    check(alive.length === 0, `R14.4 children gone ${Date.now() - closedAt} ms after close (alive: ${alive})`);
  } finally {
    await browser?.deleteSession().catch(() => {});
    spawnSync("taskkill", ["/pid", String(driver.pid), "/T", "/F"], { stdio: "ignore" });
  }

  // R14.5: the AppData listing after
  await sleep(1_000);
  const after = snapshot(start);
  // A self-check of the classifier: a path that names the app is always an app write.
  check(
    isAppWrite(join(LOCALAPPDATA, "vn.etach.app", "x")) &&
      isAppWrite(join(APPDATA, "ETACH", "x")) &&
      isAppWrite(join(LOCALAPPDATA, "ETACH.exe.WebView2", "EBWebView")),
    "R14.5 classifier flags app paths",
  );
  const added = [...after].filter((p) => !before.has(p));
  const excluded = new Map();
  const offending = [];
  const noise = [];
  for (const p of added) {
    const why = excludedBy(p);
    if (why) excluded.set(why, (excluded.get(why) ?? 0) + 1);
    else if (isAppWrite(p)) offending.push(p);
    else noise.push(p);
  }
  for (const [why, n] of excluded) console.log(`  excluded ${n} path(s): ${why}`);
  const noiseRoots = new Map();
  for (const p of noise) {
    const root = [APPDATA, LOCALAPPDATA].find((r) => p.toLowerCase().startsWith(r.toLowerCase() + sep));
    const top = p.slice(root.length + 1).split(sep).slice(0, 2).join(sep);
    noiseRoots.set(top, (noiseRoots.get(top) ?? 0) + 1);
  }
  for (const [top, n] of noiseRoots) console.log(`  other programs (existing folder): ${top} (${n})`);
  for (const p of offending.slice(0, 50)) console.log(`  APP WRITE in AppData: ${p}`);
  check(offending.length === 0, `R14.5 nothing new/modified in %APPDATA% or %LOCALAPPDATA% (${offending.length})`);

  // R20.7: the whole app folder moved → the same data from the copy.
  let moved = null;
  if (expected) moved = await portability(appDir, env, expected);
  else check(false, "R20.7 skipped: the first start did not finish");

  for (const dir of [appDir, moved]) if (dir) await removeDir(dir, 10);
}

main()
  .catch((err) => {
    console.error(err);
    failures.push(String(err));
  })
  .finally(() => {
    console.log(failures.length ? `E2E_SHELL: ${failures.length} failure(s)` : "E2E_SHELL: all passed");
    process.exit(failures.length ? 1 : 0);
  });
