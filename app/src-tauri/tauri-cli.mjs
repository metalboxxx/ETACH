/**
 * `npm run tauri <args>` (plan step 21): the Tauri CLI, plus the release config for a release
 * build. `TAURI_BUILD` (`npm run tauri build`) therefore merges `tauri.release.conf.json`: it
 * freezes the sidecar (PyInstaller folder mode, `npm run freeze:sidecar`), ships it as resources
 * in `<app>\sidecar\`, and bundles the NSIS installer.
 *
 * The release config is kept out of `tauri.conf.json` because tauri-build copies `bundle >
 * resources` on every cargo build: debug builds, `tauri dev` and `cargo test` would otherwise
 * need a frozen sidecar. `build --debug` and `build --no-bundle` (`npm run tauri:build`, the
 * E2E_SHELL debug build) keep the base config.
 *
 * A release build first removes `src-tauri/target/release/sidecar/` (step 22.2.5, answer 18): the
 * bundler copies the frozen sidecar over it without clearing, so files of an older build (such as
 * `etach-0.1.0.dist-info`) would otherwise ship again.
 */
import { spawnSync } from "node:child_process";
import { rmSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";

const RELEASE_CONFIG = "src-tauri/tauri.release.conf.json";

/** The CLI arguments for `args`: a release `build` gets `--config <release config>`. */
export function tauriArgs(args) {
  const release = args[0] === "build" && !args.includes("--debug") && !args.includes("--no-bundle");
  return release ? [args[0], "--config", RELEASE_CONFIG, ...args.slice(1)] : [...args];
}

/** True for a release `build` (the one that bundles the frozen sidecar). */
export function isRelease(args) {
  return args[0] === "build" && tauriArgs(args).includes(RELEASE_CONFIG);
}

/** Remove `<srcTauri>/target/release/sidecar/` (a stale frozen sidecar); returns the path. */
export function clearStaleSidecar(srcTauri = dirname(import.meta.filename)) {
  const stale = resolve(srcTauri, "target", "release", "sidecar");
  rmSync(stale, { recursive: true, force: true });
  return stale;
}

if (process.argv[1] && resolve(process.argv[1]) === import.meta.filename) {
  if (isRelease(process.argv.slice(2))) clearStaleSidecar();
  const cli = createRequire(import.meta.url).resolve("@tauri-apps/cli/tauri.js");
  const r = spawnSync(process.execPath, [cli, ...tauriArgs(process.argv.slice(2))], { stdio: "inherit" });
  process.exit(r.status ?? 1);
}
