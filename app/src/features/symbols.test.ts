// @vitest-environment node
// R22.5.8.9 (PRD §10.1 v8.21): the typed symbols are set in Faustina, so they match the text.
// Faustina has + … × ‹ › − – — · but not ⋯ (U+22EF) or ✕ (U+2715), which fell back to Segoe UI
// Symbol: the row menus show … and the close buttons ×. ⚙ is not in Faustina either: Settings uses an SVG gear.
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const srcDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return p.endsWith(`${path.sep}gen`) ? [] : sources(p);
    return /\.tsx$/.test(e.name) && !/\.test\.tsx$/.test(e.name) ? [p] : [];
  });
}

describe("symbols in Faustina (R22.5.8.9)", () => {
  it("the row menu buttons show the three-dot SVG, not a typed …", () => {
    for (const f of ["features/threads/ThreadList.tsx", "features/tests-tab/TestsTab.tsx"]) {
      const code = readFileSync(path.join(srcDir, f), "utf8");
      expect(code, f).toContain("<DotsIcon />");
      expect(code, f).not.toMatch(/<span aria-hidden="true">…<\/span>/);
    }
  });

  it("no ⚙ character in the sidebar (Settings uses the SVG gear)", () => {
    const code = readFileSync(path.join(srcDir, "features/sidebar/Sidebar.tsx"), "utf8");
    expect(code).not.toContain("⚙");
  });

  it("no rendered ⋯ or ✕ (comments may still name the window's ✕)", () => {
    const hits: string[] = [];
    for (const file of sources(srcDir)) {
      readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, i) => {
          const code = line.trim();
          if (/^(\*|\/\/|\/\*|\{\/\*)/.test(code)) return;
          if (/[⋯✕]/.test(code)) hits.push(`${path.relative(srcDir, file)}:${i + 1}: ${code}`);
        });
    }
    expect(hits).toEqual([]);
  });
});
