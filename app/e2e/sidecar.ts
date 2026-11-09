/**
 * Starts `etach serve --replay <tmp replay> --data <tmp>` for the E2E tests and stops it.
 * The replay folder holds the S1 cassettes (`sidecar/tests/cassettes/s1`) twice, in `run-1/` and
 * `run-2/`: a cassette is served once, and R16.5 extracts S1 a second time to seed a merge.
 * `uv` comes from PATH, else from the WinGet links folder (%LOCALAPPDATA%\Microsoft\WinGet\Links).
 */
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";
import { createInterface } from "node:readline";

export const SIDECAR_DIR = resolve(import.meta.dirname, "..", "..", "sidecar");
export const CASSETTE_ROOT = join(SIDECAR_DIR, "tests", "cassettes");
export const CASSETTES = join(CASSETTE_ROOT, "s1");

export function findUv(): string {
  const exe = process.platform === "win32" ? "uv.exe" : "uv";
  const probe = spawnSync(exe, ["--version"], { stdio: "ignore" });
  if (probe.status === 0) return exe;
  const local = process.env.LOCALAPPDATA;
  if (local) {
    const winget = join(local, "Microsoft", "WinGet", "Links", "uv.exe");
    if (existsSync(winget)) return winget;
  }
  throw new Error("uv not found on PATH or in %LOCALAPPDATA%\\Microsoft\\WinGet\\Links");
}

/**
 * `[extract]` as the E2E cassettes were recorded: tiles on, the pre-bundle keep rule, the
 * vision photo reader (the default is the OCR reader since R22.5.7.7), and the blank rule
 * before step 22.6.2 (`blank_share = 0`: the recorded S1 paper, 1 of 34 answers read sure,
 * would be a blank test under the 20% rule).
 */
export const RECORDED_WITH_TILES_TOML =
  '[extract]\nretranscribe_tiles = true\nretranscribe_tiles_keep = "always"\nphoto_reader = "vision"\nblank_share = 0\n';

export interface Sidecar {
  port: number;
  token: string;
  /** The `--data` folder (the E2E app folder; `exports` is inside it, step 22.1.6). */
  dataDir: string;
  stop(): Promise<void>;
}

function killTree(child: ChildProcess): void {
  if (child.exitCode !== null || child.pid === undefined) return;
  if (process.platform === "win32") {
    // `uv run` starts python as a child: kill the whole tree.
    spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
  } else {
    child.kill("SIGTERM");
  }
}

/**
 * A temp replay folder with `copies` copies of the S1 cassette files (`NNN-<task>.json`), one per
 * subfolder: the replay serves them in folder order, so each extraction gets a full set.
 */
function replayFolder(copies: number): string {
  const dir = mkdtempSync(join(tmpdir(), "etach-e2e-replay-"));
  const cassettes = readdirSync(CASSETTES).filter((n) => /^\d+-.+\.json$/.test(n));
  for (let i = 1; i <= copies; i++) {
    const sub = join(dir, `run-${i}`);
    mkdirSync(sub);
    for (const name of cassettes) copyFileSync(join(CASSETTES, name), join(sub, name));
  }
  return dir;
}

/**
 * A temp replay folder for a spec's own sidecar: each scenario folder's cassette files copied
 * into `<NN>-<name>/`. The replay serves cassettes with the same match key (e.g. a page's
 * `transcribe_page`, or `weak_points_summary`) in folder order, so the scenarios are listed in the
 * order the spec uses them. Leave out `s1-grade`: its keys would collide with `s1-seeded`'s.
 */
export function scenarioReplayFolder(scenarios: readonly string[]): string {
  const dir = mkdtempSync(join(tmpdir(), "etach-e2e-replay-"));
  scenarios.forEach((src, i) => {
    if (!existsSync(src)) throw new Error(`cassettes not found: ${src}`);
    const sub = join(dir, `${String(i + 1).padStart(2, "0")}-${basename(src)}`);
    mkdirSync(sub);
    for (const name of readdirSync(src).filter((n) => /^\d+-.+\.json$/.test(n))) {
      copyFileSync(join(src, name), join(sub, name));
    }
  });
  return dir;
}

/**
 * `extraArgs` go after the standard ones (e.g. the hidden `--replay-delay-ms`). `replay`: a folder
 * from `scenarioReplayFolder` (removed on stop); by default the S1 cassettes twice. `env` is added
 * to the sidecar's environment (e.g. `ETACH_FAKE_OLLAMA_PULL`, step 20).
 */
export async function startSidecar(
  timeoutMs = 90_000,
  extraArgs: readonly string[] = [],
  replay?: string,
  env: Readonly<Record<string, string>> = {},
): Promise<Sidecar> {
  if (!existsSync(CASSETTES)) throw new Error(`cassettes not found: ${CASSETTES}`);
  const dataDir = mkdtempSync(join(tmpdir(), "etach-e2e-"));
  // The E2E recordings (S1, blank, seeded) were made with the tile re-read on; since M1 speed
  // bundle 1 (93cea8b) the default is off. Replay them with the rules they were recorded with,
  // the same `models.toml` the sidecar replay tests write (tests/replay/test_extract_replay.py).
  writeFileSync(join(dataDir, "models.toml"), RECORDED_WITH_TILES_TOML, "utf8");
  const replayDir = replay ?? replayFolder(2);
  const child = spawn(
    findUv(),
    ["run", "etach", "serve", "--replay", replayDir, "--data", dataDir, ...extraArgs],
    { cwd: SIDECAR_DIR, stdio: ["ignore", "pipe", "pipe"], windowsHide: true, env: { ...process.env, ...env } },
  );
  let stderr = "";
  child.stderr?.on("data", (b: Buffer) => {
    stderr += b.toString();
  });

  const cleanup = async () => {
    killTree(child);
    if (child.exitCode === null) {
      await new Promise<void>((done) => {
        const t = setTimeout(done, 5_000);
        child.once("exit", () => {
          clearTimeout(t);
          done();
        });
      });
    }
    rmSync(replayDir, { recursive: true, force: true });
    // SQLite files may stay locked for a moment after the kill.
    for (let i = 0; i < 10; i++) {
      try {
        rmSync(dataDir, { recursive: true, force: true });
        return;
      } catch {
        await new Promise((r) => setTimeout(r, 300));
      }
    }
  };

  try {
    const first = await new Promise<string>((ok, fail) => {
      const rl = createInterface({ input: child.stdout! });
      const timer = setTimeout(() => fail(new Error("etach serve: no port line in time")), timeoutMs);
      rl.once("line", (line) => {
        clearTimeout(timer);
        ok(line);
      });
      child.once("exit", (code) => {
        clearTimeout(timer);
        fail(new Error(`etach serve exited (${code}) before printing its port:\n${stderr}`));
      });
    });
    const { port, token } = JSON.parse(first) as { port: number; token: string };
    return { port, token, dataDir, stop: cleanup };
  } catch (err) {
    await cleanup();
    throw err;
  }
}
