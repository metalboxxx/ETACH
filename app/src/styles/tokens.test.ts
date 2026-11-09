// @vitest-environment node
// The colour tokens in tokens.css (PRD §10.1, v8.12 and v8.13: the teacher's light theme).
// R22.5.8.7: light only (one :root block, no dark palette, no data-theme switch); the teacher's
//            colours; correct and unsure only as fills (or as the gradient labels), never as text.
// R22.1.2.2: WCAG 2.1 AA contrast, computed from the token values for every pair the app uses.
// R22.1.2.3: no colour literal in app/src outside tokens.css (print.css keeps black and white).
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const srcDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

type Tokens = Record<string, string>;

async function tokens(): Promise<Tokens> {
  const text = await readFile(path.join(srcDir, "styles/tokens.css"), "utf8");
  const m = text.match(/^:root\s*{([^}]*)}/m);
  if (!m) throw new Error("block not found: :root");
  return Object.fromEntries(
    [...m[1]!.matchAll(/(--etach-[\w-]+)\s*:\s*([^;]+);/g)].map((v) => [v[1]!, v[2]!.trim().toLowerCase()]),
  );
}

// --- colour maths (WCAG 2.1 relative luminance and contrast ratio) ---------------------------

type Rgb = [number, number, number];

function rgb(hex: string): Rgb {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) throw new Error(`not a #rrggbb colour: ${hex}`);
  const n = parseInt(m[1]!, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function luminance([r, g, b]: Rgb): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(a: Rgb, b: Rgb): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

/** `top` at `alpha` over `under` (Tailwind's `bg-x/15`, or `opacity-90` on a whole element). */
function over(top: Rgb, alpha: number, under: Rgb): Rgb {
  return top.map((c, i) => c * alpha + under[i]! * (1 - alpha)) as Rgb;
}

/** HSL hue in degrees, or null for an exact grey. */
function hue([r, g, b]: Rgb): number | null {
  const max = Math.max(r, g, b);
  const d = max - Math.min(r, g, b);
  if (d === 0) return null;
  const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return (h * 60 + 360) % 360;
}

// --- what the app puts on what ---------------------------------------------------------------

/** Backgrounds that text and controls sit on (`bg-bg`, `bg-surface`, ..., `hover:bg-hover`). */
const SURFACES = ["--etach-bg", "--etach-surface", "--etach-sidebar", "--etach-panel", "--etach-hover"];

/** Tokens used as text colour on those surfaces (`text-text`, `text-muted`, `text-accent-strong`,
 *  `placeholder:text-muted`, `text-danger`), and the gradient labels (`mark-label`), checked by
 *  their top colour. */
const TEXT_TOKENS = ["--etach-text", "--etach-text-muted", "--etach-accent-strong", "--etach-wrong", "--etach-label-top"];

/** Non-text tokens that must stand out from the surface (WCAG 1.4.11): `border-input` on inputs,
 *  selects, text areas and tabs, and the `outline-focus` ring. */
const UI_TOKENS = ["--etach-input-border", "--etach-focus"];

/** The teacher's colours (PRD §10.1 v8.12), as rgb() there and hex here. */
const TEACHER = {
  "--etach-bg": "#f7f7f9", // rgb(247, 247, 249), v8.14
  "--etach-text": "#0e0e01", // rgb(14, 14, 1)
  "--etach-accent": "#3539e3", // rgb(53, 57, 227), v8.15: button fill and selected tab
  "--etach-accent-hover": "#181a5c", // rgb(24, 26, 92), v8.20: their hover and press
  "--etach-accent-strong": "#3539e3",
  "--etach-focus": "#3539e3",
  "--etach-accent-text": "#ffffff", // white text on the blue
  "--etach-correct": "#56db56", // rgb(86, 219, 86)
  "--etach-unsure": "#e08422", // rgb(224, 132, 34)
  "--etach-wrong": "#962718", // rgb(150, 39, 24)
  "--etach-label-top": "#0e0e01", // the text colour
  "--etach-label-bottom": "#776910", // rgb(119, 105, 16), v8.13
};

/** Every value of the step 21 (warm-neutral) and v4.11 (green) palettes; none may survive.
 *  (White is back, as the text on the blue.) */
const OLD_VALUES = [
  "#faf9f5", "#f3f1ea", "#f6f5f0", "#29261b", "#6f6b5e", "#e3dfd3", "#ebe8de",
  "#c2613f", "#4d7a3a", "#a8701a", "#b5412f", "#262624", "#30302e", "#1f1e1c", "#2b2a27",
  "#f1efe7", "#a8a397", "#3e3c37", "#383732", "#d97757", "#8fb879", "#d9a654", "#e07a68",
  "#f5f9f6", "#fcfefc", "#ecf3ee", "#f1f6f2", "#16241b", "#4f6056", "#d5e1d8", "#6c8274",
  "#e2ebe4", "#8ed99c", "#0d2915", "#1c6a37", "#27703f", "#8a5600", "#921f17", "#151b17",
  "#1c241f", "#111613", "#19201b", "#e4ece6", "#9bada1", "#2c3730", "#6f8276", "#26302a",
  "#9be2a8", "#7fcd8f", "#deb25a", "#f7a294",
  // the first v8.12 neutrals and blue (v8.13 changed them)
  "#e6e8f2", "#f5f6fb", "#dcdfed", "#edeef6", "#d4d8ea", "#c3c7dc", "#686d8c", "#474b63", "#1f23e0", "#e6d043",
  // the v8.13 neutrals (v8.14 made the page whiter)
  "#f4f4f7", "#fbfbfd", "#eaeaf0", "#f8f8fa", "#e2e3eb", "#d4d5df", "#71738a",
  // the v8.14 light button blue, the v8.15 hover navy
  "#6265e9", "#0f1038",
];

const ratio = (t: Tokens, fg: string, bg: string) => contrast(rgb(t[fg]!), rgb(t[bg]!));

describe("theme tokens (R13.4, R22.5.8.7)", () => {
  it("one light block; no dark palette or data-theme switch is left", async () => {
    const css = await readFile(path.join(srcDir, "styles/tokens.css"), "utf8");
    expect(css).toMatch(/color-scheme:\s*light/);
    expect(css).not.toMatch(/prefers-color-scheme|data-theme|color-scheme:\s*dark/);
    expect(css.match(/:root\b/g)).toHaveLength(1);
    const index = await readFile(path.join(srcDir, "index.css"), "utf8");
    expect(index).not.toMatch(/prefers-color-scheme|data-theme|@custom-variant dark/);
  });

  it("every Tailwind colour in index.css maps to a token that exists", async () => {
    const t = await tokens();
    const css = await readFile(path.join(srcDir, "index.css"), "utf8");
    const used = [...css.matchAll(/--color-[\w-]+:\s*var\((--etach-[\w-]+)\)/g)].map((m) => m[1]!);
    expect(used.length).toBeGreaterThan(0);
    for (const name of used) expect(Object.keys(t)).toContain(name);
  });

  it("the gradient labels are one shared utility, top to bottom from the two label tokens", async () => {
    const css = await readFile(path.join(srcDir, "index.css"), "utf8");
    const body = /@utility mark-label\s*{([\s\S]*?)\n}/.exec(css)?.[1] ?? "";
    expect(body).toMatch(/linear-gradient\(to bottom, var\(--etach-label-top\), var\(--etach-label-bottom\)\)/);
    expect(body).toMatch(/(^|\s)background-clip:\s*text/);
    expect(body).toMatch(/-webkit-background-clip:\s*text/);
    expect(body).toMatch(/color:\s*transparent/);
    // plain letters on paper and in Windows high contrast
    expect(body).toMatch(/@media print/);
    expect(body).toMatch(/@media \(forced-colors: active\)/);
  });
});

describe("the teacher's palette (PRD §10.1 v8.12)", () => {
  it("the fixed colours are exactly the teacher's", async () => {
    const t = await tokens();
    for (const [name, value] of Object.entries(TEACHER)) expect(t[name], name).toBe(value);
  });

  it("the surfaces, borders and muted text are quiet blue-greys (hue 215°–245°), or white cards", async () => {
    const t = await tokens();
    for (const name of [...SURFACES, "--etach-border", "--etach-input-border", "--etach-text-muted"]) {
      const h = hue(rgb(t[name]!));
      if (name === "--etach-surface" && t[name] === "#ffffff") continue;
      expect(h, name).not.toBeNull();
      expect(h!, name).toBeGreaterThanOrEqual(215);
      expect(h!, name).toBeLessThanOrEqual(245);
    }
  });

  it("the areas stay distinct (v8.14): cards lighter than the page; sidebar, panel and hover darker", async () => {
    const t = await tokens();
    const lum = (name: string) => luminance(rgb(t[name]!));
    expect(lum("--etach-surface")).toBeGreaterThan(lum("--etach-bg"));
    for (const name of ["--etach-sidebar", "--etach-panel", "--etach-hover"]) expect(lum(name), name).toBeLessThan(lum("--etach-bg"));
    // hover must show on every area it is used on
    for (const name of ["--etach-bg", "--etach-surface", "--etach-sidebar", "--etach-panel"]) expect(lum("--etach-hover"), name).toBeLessThan(lum(name));
  });

  it("no token keeps a value of the step 21 or the green (v4.11) palette", async () => {
    for (const [name, value] of Object.entries(await tokens())) expect(OLD_VALUES, name).not.toContain(value);
  });
});

describe("contrast, computed from the tokens (R22.1.2.2, R22.5.8.7)", () => {
  it("every text token (and the gradient labels' top colour) is ≥ 4.5:1 on every surface", async () => {
    const t = await tokens();
    for (const fg of TEXT_TOKENS) {
      for (const bg of SURFACES) {
        const r = ratio(t, fg, bg);
        expect(r, `${fg} on ${bg} = ${r.toFixed(2)}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it("white is ≥ 4.5:1 on the blue fill and on its darker hover and pressed blue (v8.14)", async () => {
    const t = await tokens();
    expect(ratio(t, "--etach-accent-text", "--etach-accent"), "accent-text on accent").toBeGreaterThanOrEqual(4.5);
    expect(ratio(t, "--etach-accent-text", "--etach-accent-hover"), "accent-text on accent-hover").toBeGreaterThanOrEqual(4.5);
    // the hover is darker than the fill, never lighter or faded
    expect(luminance(rgb(t["--etach-accent-hover"]!))).toBeLessThan(luminance(rgb(t["--etach-accent"]!)));
  });

  it("the fills: dark text on correct and unsure, white on wrong, each ≥ 4.5:1", async () => {
    const t = await tokens();
    expect(ratio(t, "--etach-text", "--etach-correct")).toBeGreaterThanOrEqual(4.5);
    expect(ratio(t, "--etach-text", "--etach-unsure")).toBeGreaterThanOrEqual(4.5);
    expect(ratio(t, "--etach-accent-text", "--etach-wrong")).toBeGreaterThanOrEqual(4.5);
  });

  it("the pairs the theme forbids really fail, so they stay forbidden", async () => {
    const t = await tokens();
    // black on blue; correct and unsure as text; white on unsure
    expect(ratio(t, "--etach-text", "--etach-accent")).toBeLessThan(4.5);
    for (const bg of SURFACES) {
      expect(ratio(t, "--etach-correct", bg)).toBeLessThan(4.5);
      expect(ratio(t, "--etach-unsure", bg)).toBeLessThan(4.5);
    }
    expect(ratio(t, "--etach-accent-text", "--etach-unsure")).toBeLessThan(4.5);
  });

  it("text on the tinted rows is ≥ 4.5:1 (unsure notes and rows, ??? marks, error lines, drop overlay)", async () => {
    const t = await tokens();
    for (const bg of SURFACES) {
      const under = rgb(t[bg]!);
      const tint = (name: string, a: number) => over(rgb(t[name]!), a, under);
      const pairs: [string, string, Rgb][] = [
        ["--etach-text", "unsure/15", tint("--etach-unsure", 0.15)],
        ["--etach-text-muted", "unsure/15", tint("--etach-unsure", 0.15)],
        ["--etach-label-top", "unsure/15", tint("--etach-unsure", 0.15)],
        ["--etach-accent-strong", "unsure/15", tint("--etach-unsure", 0.15)],
        ["--etach-wrong", "unsure/15", tint("--etach-unsure", 0.15)],
        ["--etach-text", "unsure/40", tint("--etach-unsure", 0.4)],
        ["--etach-text", "danger/10", tint("--etach-wrong", 0.1)],
        ["--etach-text", "bg/80", tint("--etach-bg", 0.8)],
      ];
      for (const [fg, label, fill] of pairs) {
        const r = contrast(rgb(t[fg]!), fill);
        expect(r, `${fg} on ${label} over ${bg} = ${r.toFixed(2)}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it("the gradient labels' bottom colour is ≥ 4.5:1 on the page and ≥ 3:1 on every surface and tint (v8.13)", async () => {
    const t = await tokens();
    const bottom = rgb(t["--etach-label-bottom"]!);
    expect(contrast(bottom, rgb(t["--etach-bg"]!)), "label-bottom on bg").toBeGreaterThanOrEqual(4.5);
    for (const bg of SURFACES) {
      const under = rgb(t[bg]!);
      // `mark-label` sits on the surfaces and on the unsure tint (unsure rows and notes)
      for (const [label, fill] of [
        [bg, under],
        [`unsure/15 over ${bg}`, over(rgb(t["--etach-unsure"]!), 0.15, under)],
      ] as [string, Rgb][]) {
        const r = contrast(bottom, fill);
        expect(r, `label-bottom on ${label} = ${r.toFixed(2)}`).toBeGreaterThanOrEqual(3);
      }
    }
  });

  it("input borders and the focus ring are ≥ 3:1 on every surface", async () => {
    const t = await tokens();
    for (const fg of UI_TOKENS) {
      for (const bg of SURFACES) {
        const r = ratio(t, fg, bg);
        expect(r, `${fg} on ${bg} = ${r.toFixed(2)}`).toBeGreaterThanOrEqual(3);
      }
    }
  });
});

async function sourceFiles(dir: string): Promise<string[]> {
  const out: string[] = [];
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (p !== path.join(srcDir, "gen")) out.push(...(await sourceFiles(p)));
    } else if (/\.(tsx?|css)$/.test(e.name) && !/\.test\.tsx?$/.test(e.name) && e.name !== "test-setup.ts") {
      out.push(p);
    }
  }
  return out;
}

describe("colours come only from the tokens (R22.1.2.3)", () => {
  const LITERAL = /#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(/gi;
  // Tailwind's built-in palette (`bg-white`, `text-red-600`, ...) would bypass the tokens too.
  const PALETTE_CLASS =
    /\b(?:bg|text|border(?:-[trblxy])?|ring|outline|fill|stroke|decoration|divide|shadow|caret|accent|from|via|to)-(?:white|black|(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3})\b/g;

  it("no colour literal or palette class outside tokens.css; print.css uses only black and white", async () => {
    const found: string[] = [];
    for (const file of await sourceFiles(srcDir)) {
      const rel = path.relative(srcDir, file).replaceAll("\\", "/");
      if (rel === "styles/tokens.css") continue;
      const text = await readFile(file, "utf8");
      for (const m of text.matchAll(LITERAL)) {
        if (rel === "styles/print.css" && /^#(?:000|fff|000000|ffffff)$/i.test(m[0])) continue;
        found.push(`${rel}: ${m[0]}`);
      }
      for (const m of text.matchAll(PALETTE_CLASS)) found.push(`${rel}: ${m[0]}`);
    }
    expect(found).toEqual([]);
  });
});

describe("meaning colours are used as the theme allows (R22.5.8.7)", () => {
  async function hits(re: RegExp): Promise<string[]> {
    const found: string[] = [];
    for (const file of await sourceFiles(srcDir)) {
      const rel = path.relative(srcDir, file).replaceAll("\\", "/");
      const lines = (await readFile(file, "utf8")).split("\n");
      lines.forEach((line, i) => {
        for (const m of line.matchAll(re)) found.push(`${rel}:${i + 1}: ${m[0]}`);
      });
    }
    return found;
  }

  it("correct and unsure are never text, border, outline or underline colours (fills only)", async () => {
    expect(await hits(/\b(?:text|border(?:-[trblxy])?|outline|ring|decoration|fill|stroke|placeholder)-(?:correct|unsure)\b/g)).toEqual([]);
  });

  it("the old success and warning names are gone", async () => {
    expect(await hits(/\b[a-z-]*-(?:success|warning)\b(?!-)/g).then((h) => h.filter((x) => !/ollama-warning/.test(x)))).toEqual([]);
  });

  it("every blue fill turns the darker blue on hover and press, never an opacity or brightness fade", async () => {
    const found: string[] = [];
    for (const file of await sourceFiles(srcDir)) {
      const rel = path.relative(srcDir, file).replaceAll("\\", "/");
      const lines = (await readFile(file, "utf8")).split("\n");
      lines.forEach((line, i) => {
        if (!/(?<![\w:-])bg-accent(?![\w/-])/.test(line)) return;
        if (!/(?<![\w-])hover:bg-accent-hover\b/.test(line) || !/(?<![\w-])active:bg-accent-hover\b/.test(line)) found.push(`${rel}:${i + 1}: no darker hover/press`);
        if (/hover:(?:opacity|brightness)/.test(line)) found.push(`${rel}:${i + 1}: a faded hover`);
      });
    }
    expect(found).toEqual([]);
  });

  it("the blue fill always carries white text, never black (2.6:1)", async () => {
    const found: string[] = [];
    for (const file of await sourceFiles(srcDir)) {
      const rel = path.relative(srcDir, file).replaceAll("\\", "/");
      const lines = (await readFile(file, "utf8")).split("\n");
      lines.forEach((line, i) => {
        if (/(?<![\w:-])bg-accent(?![\w/-])/.test(line) && !/\btext-accent-text\b/.test(line)) found.push(`${rel}:${i + 1}`);
      });
    }
    expect(found).toEqual([]);
  });
});

describe("the ETACH wordmark (PRD §10.1 v8.18, R22.5.8.8)", () => {
  it("lime and blue tokens, used only by the wordmark gradient", async () => {
    const t = await tokens();
    expect(t["--etach-wordmark-lime"]).toBe("#a5d921");
    // the teacher's pick (PRD §10.1 v8.19)
    expect(t["--etach-wordmark-blue"]).toBe("#3539e3");
    // the wordmark's end is the hover's deep navy, one value (PRD §10.1 v8.20)
    expect(t["--etach-wordmark-end"]).toBe("var(--etach-accent-hover)");
    expect(t["--etach-accent-hover"]).toBe("#181a5c");
    const users: string[] = [];
    for (const file of await sourceFiles(srcDir)) {
      const rel = path.relative(srcDir, file).replaceAll("\\", "/");
      if (rel === "styles/tokens.css") continue;
      if (/--etach-wordmark-/.test(await readFile(file, "utf8"))) users.push(rel);
    }
    expect(users).toEqual(["index.css"]);
  });

  it("the gradient runs lime → blue across E and T, blue A, deep navy from the middle of the C", async () => {
    const css = await readFile(path.join(srcDir, "index.css"), "utf8");
    const body = /@utility wordmark-gradient\s*{([\s\S]*?)\n}/.exec(css)?.[1] ?? "";
    const stops = [...body.matchAll(/^\s*(.+?)\s+([\d.]+)%,?$/gm)].map((m) => [m[1]!.trim(), Number(m[2])] as const);
    expect(stops).toEqual([
      ["var(--etach-wordmark-lime)", 2.5],
      ["color-mix(in srgb, var(--etach-wordmark-lime) 20%, var(--etach-wordmark-blue))", 26.7],
      ["var(--etach-wordmark-blue)", 34.1],
      ["var(--etach-wordmark-blue)", 60.2],
      ["var(--etach-wordmark-end)", 71.2],
      ["var(--etach-wordmark-end)", 100],
    ]);
    expect(body).toMatch(/(^|\s)background-clip:\s*text/);
    expect(body).toMatch(/@media print/);
    expect(body).toMatch(/@media \(forced-colors: active\)/);
  });
});

describe("corners (PRD §10.1 v8.21, R22.5.8.9)", () => {
  it("papers 2 px and buttons 6 px are the only radius tokens", async () => {
    const css = await readFile(path.join(srcDir, "index.css"), "utf8");
    expect(css).toMatch(/--radius-\*:\s*initial;/);
    expect(css).toMatch(/--radius-paper:\s*2px;/);
    expect(css).toMatch(/--radius-button:\s*6px;/);
    expect([...css.matchAll(/--radius-([\w-]+):/g)].map((m) => m[1]).sort()).toEqual(["button", "paper"]);
  });

  it("every corner class is paper (or its top or bottom only), button, the arch (top only) or full", async () => {
    const found: string[] = [];
    for (const file of await sourceFiles(srcDir)) {
      const rel = path.relative(srcDir, file).replaceAll("\\", "/");
      const lines = (await readFile(file, "utf8")).split("\n");
      lines.forEach((line, i) => {
        for (const m of line.matchAll(/(?<![\w-])rounded(?:-([\w-]+))?/g)) {
          if (!["paper", "t-paper", "b-paper", "button", "t-button", "full"].includes(m[1] ?? "")) found.push(`${rel}:${i + 1}: ${m[0]}`);
        }
      });
    }
    expect(found).toEqual([]);
  });
});

describe("sidebar tints (PRD §10.1 v8.21)", () => {
  it("the open row's tint is stronger than the hover tint, and both are the blue over the sidebar", async () => {
    const t = await tokens();
    const lum = (n: string) => luminance(rgb(t[n]!));
    expect(lum("--etach-tint")).toBeLessThan(lum("--etach-sidebar"));
    expect(lum("--etach-tint-strong")).toBeLessThan(lum("--etach-tint"));
    expect(ratio(t, "--etach-tint", "--etach-tint-strong")).toBeGreaterThanOrEqual(1.15);
    for (const n of ["--etach-tint", "--etach-tint-strong"]) {
      const h = hue(rgb(t[n]!))!;
      expect(h, n).toBeGreaterThanOrEqual(235);
      expect(h, n).toBeLessThanOrEqual(245);
    }
  });

  it("text on the tints: ≥ 4.5:1 for text, muted, blue and brick; the gradient labels' bottom ≥ 3:1; the focus ring ≥ 3:1", async () => {
    const t = await tokens();
    for (const bg of ["--etach-tint", "--etach-tint-strong"]) {
      for (const fg of ["--etach-text", "--etach-text-muted", "--etach-accent-strong", "--etach-wrong", "--etach-label-top"]) {
        expect(ratio(t, fg, bg), `${fg} on ${bg}`).toBeGreaterThanOrEqual(4.5);
      }
      expect(ratio(t, "--etach-label-bottom", bg), `label-bottom on ${bg}`).toBeGreaterThanOrEqual(3);
      expect(ratio(t, "--etach-focus", bg), `focus on ${bg}`).toBeGreaterThanOrEqual(3);
    }
  });
});

