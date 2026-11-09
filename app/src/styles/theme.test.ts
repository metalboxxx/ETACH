// @vitest-environment node
// R13.4: the font is bundled into dist/ and @font-face points at it (PRD §10.1 v8.16: Faustina only). The token checks
// (names, the teacher's colours, contrast) are in tokens.test.ts. Also the offline guard (no external URLs).
import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
// @ts-expect-error -- plain .mjs script without type declarations
import { findExternalUrls } from "../../scripts/check-urls.mjs";

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

describe("bundled fonts in the build (R13.4)", () => {
  let outDir = "";
  let files: string[] = [];
  let css = "";

  beforeAll(async () => {
    outDir = await mkdtemp(path.join(os.tmpdir(), "etach-build-"));
    await build({
      root: appDir,
      configFile: path.join(appDir, "vite.config.ts"),
      logLevel: "silent",
      build: { outDir, emptyOutDir: true },
    });
    files = (await readdir(outDir, { recursive: true })).map((f) => String(f).replaceAll("\\", "/"));
    const cssFiles = files.filter((f) => f.endsWith(".css"));
    css = (await Promise.all(cssFiles.map((f) => readFile(path.join(outDir, f), "utf8")))).join("\n");
  }, 120_000);

  afterAll(async () => {
    if (outDir) await rm(outDir, { recursive: true, force: true });
  });

  it.each([
    ["Faustina", "faustina", "vietnamese"],
    ["Federo", "federo", "latin"],
  ])("%s: woff2 files are in dist/ and every @font-face url() resolves to one", (family, slug, subset) => {
    const fontFiles = files.filter((f) => f.includes(slug) && f.endsWith(".woff2"));
    expect(fontFiles.length).toBeGreaterThan(0);
    expect(fontFiles.some((f) => f.includes(subset))).toBe(true);

    const faces = [...css.matchAll(/@font-face\s*{([^}]*)}/g)]
      .map((m) => m[1]!)
      .filter((body) => body.includes(family));
    expect(faces.length).toBeGreaterThan(0);
    for (const body of faces) {
      const urls = [...body.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)].map((m) => m[1]!);
      expect(urls.length).toBeGreaterThan(0);
      for (const u of urls) {
        expect(u).not.toMatch(/^(https?:|\/\/|data:)/);
        const name = path.posix.basename(u);
        expect(files.some((f) => path.posix.basename(f) === name)).toBe(true);
      }
    }
  });

  it("the built CSS is light only: no dark palette and no way to pick one (R22.5.8.7)", () => {
    expect(css).not.toMatch(/prefers-color-scheme/);
    expect(css).not.toMatch(/data-theme/);
    expect(css).toMatch(/color-scheme:\s*light/);
    expect(css).not.toMatch(/color-scheme:\s*dark/);
    expect(css).toContain("--etach-accent-strong");
    expect(css).toContain("--etach-input-border");
  });

  it("only the main buttons draw Faustina with Merriweather's x-height (main-label, PRD §10.1 v8.17)", () => {
    expect(css).toMatch(/\.main-label\s*{\s*font-size-adjust:\s*0?\.56/);
    // not on every button or tab any more
    expect(css).not.toMatch(/button,\s*\[role=["']?tab["']?\]\s*{\s*font-size-adjust/);
  });

  it("font-mono and the default mono face are Faustina in the built CSS (every text in Faustina)", () => {
    expect(css).toMatch(/--font-mono:\s*Faustina,\s*Times New Roman,\s*serif|--font-mono:\s*"Faustina",\s*"Times New Roman",\s*serif/);
    expect(css).not.toMatch(/--font-mono:\s*ui-monospace/);
  });

  it("the corner classes resolve to the 2 px and 6 px tokens (PRD §10.1 v8.21)", () => {
    expect(css).toMatch(/--radius-paper:\s*2px/);
    expect(css).toMatch(/--radius-button:\s*6px/);
    expect(css).toMatch(/\.rounded-paper\s*{\s*border-radius:\s*(?:var\(--radius-paper\)|2px)/);
    expect(css).toMatch(/\.rounded-button\s*{\s*border-radius:\s*(?:var\(--radius-button\)|6px)/);
    expect(css).toMatch(/\.rounded-t-button\s*{\s*border-top-left-radius:\s*(?:var\(--radius-button\)|6px);\s*border-top-right-radius:\s*(?:var\(--radius-button\)|6px)/);
  });

  it("the double rule and the page shadow are in the built CSS (PRD §10.1 v8.21)", () => {
    expect(css).toMatch(/\.double-rule\s*{[^}]*background-size:\s*100% 2px,\s*100% 1px/);
    expect(css).toMatch(/\.shadow-page\s*{/);
  });

  it("the gradient labels' utility is in the built CSS, with its print and high-contrast fallbacks", () => {
    const rule = /\.mark-label\s*{[^}]*background-clip:\s*text/.exec(css);
    expect(rule).not.toBeNull();
    expect(css).toMatch(/--etach-label-bottom/);
    expect(css).toMatch(/forced-colors:\s*active/);
  });
});

describe("offline guard", () => {
  it("src/ and index.html contain no non-local http(s) URLs", async () => {
    expect(await findExternalUrls(appDir)).toEqual([]);
  });
});

describe("one font, Faustina (PRD §10.1 v8.16, R22.5.8.7)", () => {
  const srcDir = path.join(appDir, "src");

  it("fonts.css loads Faustina (vietnamese, latin and latin-ext at 400, 400 italic, 500 and 600, with the centring overrides) and Federo (latin 400) only", async () => {
    const css = await readFile(path.join(srcDir, "styles/fonts.css"), "utf8");
    expect(css).not.toMatch(/@import/);
    const faces = [...css.matchAll(/@font-face\s*{([^}]*)}/g)].map((m) => m[1]!);
    const federo = faces.filter((f) => /font-family:\s*'Federo'/.test(f));
    expect(federo).toHaveLength(1);
    expect(federo[0]).toMatch(/url\("@fontsource\/federo\/files\/federo-latin-400-normal\.woff2"\)/);
    faces.splice(faces.indexOf(federo[0]!), 1);
    expect(faces).toHaveLength(12);
    const seen = new Set<string>();
    for (const f of faces) {
      expect(f).toMatch(/font-family:\s*'Faustina'/);
      const urls = [...f.matchAll(/url\("([^"]+)"\)/g)].map((m) => m[1]!);
      expect(urls.length).toBeGreaterThan(0);
      for (const u of urls) expect(u).toMatch(/^@fontsource\/faustina\/files\/faustina-(vietnamese|latin|latin-ext)-\d{3}-(normal|italic)\.woff2?$/);
      expect(f).toMatch(/unicode-range:/);
      // the capitals in the middle of the line box (PRD §10.1 v8.17)
      expect(f).toMatch(/ascent-override:\s*95\.8%/);
      expect(f).toMatch(/descent-override:\s*30\.2%/);
      const name = /faustina-([a-z-]+-\d{3}-(?:normal|italic))\.woff2/.exec(urls[0]!)![1]!;
      seen.add(name);
    }
    for (const sub of ["vietnamese", "latin", "latin-ext"]) {
      for (const w of ["400-normal", "400-italic", "500-normal", "600-normal"]) expect(seen).toContain(`${sub}-${w}`);
    }
  });

  it("both font names resolve to Faustina, and nothing names the old fonts", async () => {
    const index = await readFile(path.join(srcDir, "index.css"), "utf8");
    expect(index).toMatch(/--font-sans:\s*"Faustina",/);
    expect(index).toMatch(/--font-serif:\s*"Faustina",/);
    // every text in Faustina: font-mono too (the teacher)
    expect(index).toMatch(/--font-mono:\s*"Faustina",/);
    const pkg = await readFile(path.join(appDir, "package.json"), "utf8");
    expect(pkg).toContain('"@fontsource/faustina"');
    expect(pkg).not.toMatch(/be-vietnam-pro|noto-serif/);
    expect(index + (await readFile(path.join(srcDir, "styles/fonts.css"), "utf8"))).not.toMatch(/Be Vietnam|Noto Serif|be-vietnam|noto-serif/);
  });
});
