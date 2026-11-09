// @vitest-environment node
// R14.3: the Tauri shell's CSP equals plan step 14's checklist string exactly.
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const CSP =
  "default-src 'self'; connect-src 'self' ipc: http://ipc.localhost http://127.0.0.1:*; " +
  "img-src 'self' http://127.0.0.1:* data:; font-src 'self'";

const confPath = fileURLToPath(new URL("../src-tauri/tauri.conf.json", import.meta.url));

interface TauriConf {
  productName?: string;
  identifier?: string;
  mainBinaryName?: string;
  app?: { security?: { csp?: unknown } };
}

describe("tauri.conf.json", () => {
  const conf = JSON.parse(readFileSync(confPath, "utf8")) as TauriConf;

  it("has the plan's CSP, character for character (R14.3)", () => {
    expect(conf.app?.security?.csp).toBe(CSP);
  });

  // R22.5.8.8 (PRD §10.1 v8.18): the product is ETACH with a new identifier. productName names the
  // installer (ETACH_<version>_x64-setup.exe), its uninstall entry, shortcuts and registry keys.
  // PRD v8.26: the program file is ETACH.exe (mainBinaryName, without ".exe"; `tauri build` renames
  // Cargo's etach-shell.exe; PRD v9.1: the Cargo package is etach-shell).
  it("names the product and the program file ETACH with a new identifier (R22.5.8.8)", () => {
    expect(conf.productName).toBe("ETACH");
    expect(conf.identifier).toBe("vn.etach.app");
    expect(conf.mainBinaryName).toBe("ETACH");
  });

  it("e2e:shell starts ETACH.exe (PRD v8.26)", () => {
    const run = readFileSync(fileURLToPath(new URL("../e2e-shell/run.mjs", import.meta.url)), "utf8");
    expect(run).toContain('const EXE_NAME = "ETACH.exe";');
  });

  it("titles the main window ETACH (R22.5.8.8)", () => {
    const lib = readFileSync(fileURLToPath(new URL("../src-tauri/src/lib.rs", import.meta.url)), "utf8");
    expect(lib).toContain('.title("ETACH")');
    expect(lib).not.toMatch(/Exam (Revision )?Helper/);
  });

  // step22.6-plan D18: the window frame stays light when Windows is dark, so the navy logo shows.
  it("keeps the window frame light whatever the Windows theme (D18)", () => {
    const lib = readFileSync(fileURLToPath(new URL("../src-tauri/src/lib.rs", import.meta.url)), "utf8");
    expect(lib).toContain(".theme(Some(tauri::Theme::Light))");
  });

  // Step 22.6.7 (step22.6-plan D17): the app icon is the teacher's light logo, with every Windows size.
  it("uses the teacher's logo as the app icon, 16 to 256 px (22.6.7)", () => {
    const icons = (conf as { bundle?: { icon?: string[] } }).bundle?.icon;
    expect(icons).toEqual(["icons/icon.ico", "icons/icon.png"]);
    const dir = (name: string) => fileURLToPath(new URL(`../src-tauri/icons/${name}`, import.meta.url));
    const ico = readFileSync(dir("icon.ico"));
    expect(ico.equals(readFileSync(dir("source/etach-icon-light.ico")))).toBe(true);
    const count = ico.readUInt16LE(4);
    const sizes = Array.from({ length: count }, (_, i) => ico[6 + 16 * i] || 256);
    expect(sizes).toEqual([16, 24, 32, 48, 64, 128, 256]);
    const png = readFileSync(dir("icon.png"));
    expect(png.readUInt32BE(16)).toBe(png.readUInt32BE(20)); // square
    expect(png[25]).toBe(6); // RGBA
  });
});

// Step 21: the release build (TAURI_BUILD = `npm run tauri build`).
const releasePath = fileURLToPath(new URL("../src-tauri/tauri.release.conf.json", import.meta.url));
const nsisPath = fileURLToPath(new URL("../src-tauri/nsis/installer.nsi", import.meta.url));
const pkgPath = fileURLToPath(new URL("../package.json", import.meta.url));

interface BundleConf {
  build?: { beforeBuildCommand?: string };
  bundle?: {
    active?: boolean;
    targets?: unknown;
    resources?: Record<string, string> | string[];
    windows?: { nsis?: { template?: string; installMode?: string } };
  };
}

describe("release build config (step 21)", () => {
  const base = JSON.parse(readFileSync(confPath, "utf8")) as BundleConf;
  const release = JSON.parse(readFileSync(releasePath, "utf8")) as BundleConf;
  const pkg = JSON.parse(readFileSync(pkgPath, "utf8")) as { scripts: Record<string, string> };

  it("ships the frozen sidecar folder as resources in <app>\\sidecar and bundles NSIS", () => {
    expect(release.bundle?.active).toBe(true);
    expect(release.bundle?.targets).toEqual(["nsis"]);
    expect(release.bundle?.resources).toEqual({ "../../sidecar/dist/etach-sidecar/": "sidecar/" });
    expect(release.build?.beforeBuildCommand).toContain("npm run freeze:sidecar");
    expect(pkg.scripts["freeze:sidecar"]).toContain("pyinstaller etach.spec");
  });

  it("keeps the base config free of resources, so debug builds need no frozen sidecar", () => {
    expect(base.bundle?.resources).toBeUndefined();
  });

  it("`npm run tauri build` adds the release config; --debug and --no-bundle do not", async () => {
    expect(pkg.scripts.tauri).toBe("node src-tauri/tauri-cli.mjs");
    const mod = (await import("../src-tauri/tauri-cli.mjs" as string)) as {
      tauriArgs: (a: string[]) => string[];
    };
    const cfg = ["--config", "src-tauri/tauri.release.conf.json"];
    expect(mod.tauriArgs(["build"])).toEqual(["build", ...cfg]);
    expect(mod.tauriArgs(["build", "--verbose"])).toEqual(["build", ...cfg, "--verbose"]);
    expect(mod.tauriArgs(["build", "--debug"])).toEqual(["build", "--debug"]);
    expect(mod.tauriArgs(["build", "--no-bundle"])).toEqual(["build", "--no-bundle"]);
    expect(mod.tauriArgs(["dev"])).toEqual(["dev"]);
  });

  it("the installer defaults to D:\\ETACH, never AppData (PRD §11)", () => {
    expect(release.bundle?.windows?.nsis?.installMode).toBe("currentUser");
    expect(release.bundle?.windows?.nsis?.template).toBe("nsis/installer.nsi");
    const nsi = readFileSync(nsisPath, "utf8");
    expect(nsi).toContain('StrCpy $INSTDIR "D:\\ETACH"');
    expect(nsi).toContain('StrCpy $INSTDIR "$PROFILE\\ETACH"');
    expect(nsi).not.toContain("ExamRevisionHelper");
    expect(nsi).not.toMatch(/StrCpy \$INSTDIR "\$LOCALAPPDATA/);
  });

  it("a real uninstall always deletes the install-folder key; an update keeps it (teacher, step 21)", () => {
    const nsi = readFileSync(nsisPath, "utf8").replace(/\r\n/g, "\n");
    const del = 'DeleteRegKey SHCTX "${MANUPRODUCTKEY}"';
    expect(nsi.split(del).length - 1).toBe(1);
    // The `${If}` that guards the deletion is the update check alone, not the "delete app data" box.
    const before = nsi.slice(0, nsi.indexOf(del));
    const guard = before.slice(before.lastIndexOf("${If}"));
    expect(guard).toMatch(/^\$\{If\} \$UpdateMode <> 1\n/);
    expect(guard).not.toContain("DeleteAppDataCheckboxState");
  });
});

// R22.2.5.4: a release build clears the stale frozen sidecar before the bundler copies the new one.
describe("release build clears target/release/sidecar (step 22.2.5)", () => {
  it("removes target/release/sidecar/ with a stale dist-info, only for a release build", async () => {
    const mod = (await import("../src-tauri/tauri-cli.mjs" as string)) as {
      isRelease: (a: string[]) => boolean;
      clearStaleSidecar: (srcTauri?: string) => string;
    };
    expect(mod.isRelease(["build"])).toBe(true);
    expect(mod.isRelease(["build", "--debug"])).toBe(false);
    expect(mod.isRelease(["build", "--no-bundle"])).toBe(false);
    expect(mod.isRelease(["dev"])).toBe(false);
    const root = mkdtempSync(join(tmpdir(), "etach-sidecar-"));
    const stale = join(root, "target", "release", "sidecar", "_internal", "etach-0.1.0.dist-info");
    mkdirSync(stale, { recursive: true });
    writeFileSync(join(stale, "METADATA"), "Version: 0.1.0\n");
    expect(mod.clearStaleSidecar(root)).toBe(join(root, "target", "release", "sidecar"));
    expect(existsSync(join(root, "target", "release", "sidecar"))).toBe(false);
    expect(existsSync(join(root, "target", "release"))).toBe(true);
    expect(() => mod.clearStaleSidecar(root)).not.toThrow(); // nothing there: fine
  });
});

// R22.2.5.5: "Delete app data" also deletes the app's data in the app folder (ETACH change 3).
describe("uninstaller Delete app data (step 22.2.5)", () => {
  const nsi = readFileSync(nsisPath, "utf8").replace(/\r\n/g, "\n");
  const paths = ["data", "exports", "webview", "settings.json"].map((p) => `"$INSTDIR\\${p}"`);

  it("deletes the four paths only inside the ticked-box, not-updating block", () => {
    const open = "${If} $DeleteAppDataCheckboxState = 1\n  ${AndIf} $UpdateMode <> 1\n";
    expect(nsi.split(open).length - 1).toBe(1);
    const start = nsi.indexOf(open);
    const block = nsi.slice(start, nsi.indexOf("${EndIf}", start));
    for (const p of paths) {
      expect(nsi.split(p).length - 1).toBe(1); // nowhere else, so never on /UPDATE or unticked
      expect(block).toContain(p);
    }
    expect(block).toMatch(/RmDir \/r \/REBOOTOK "\$INSTDIR\\data"/);
    expect(block).toMatch(/Delete \/REBOOTOK "\$INSTDIR\\settings\.json"/);
    expect(block).toContain("ETACH change 3");
  });

  it("the box's text names what it deletes; the header lists three ETACH changes", () => {
    // R22.2.7.4: the teacher's answer 9
    expect(nsi).toContain('w "Delete all app data (tests, students, backups)"');
    expect(nsi).not.toContain("data, exports, webview, settings.json)\"");
    expect(nsi).not.toContain('w "$(deleteAppData)"');
    expect(nsi).toContain("with THREE changes");
    expect(nsi.match(/ETACH change/g)?.length).toBeGreaterThanOrEqual(5);
  });
});

// R22.2.2.2: the close guard holds the close request and destroys the window after Close; the
// main window may do that, and nothing else beyond the defaults.
describe("capabilities (step 22.2.2)", () => {
  const capPath = fileURLToPath(new URL("../src-tauri/capabilities/default.json", import.meta.url));
  const cap = JSON.parse(readFileSync(capPath, "utf8")) as { windows: string[]; permissions: string[] };

  it("lets the main window be destroyed after the close guard asks", () => {
    expect(cap.windows).toEqual(["main"]);
    expect(cap.permissions).toEqual(["core:default", "notification:default", "dialog:default", "core:window:allow-destroy"]);
  });
});
