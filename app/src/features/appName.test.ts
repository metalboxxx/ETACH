// @vitest-environment node
// R22.5.8.8 (PRD §10.1 v8.18): the app is ETACH. No user-visible "Exam Revision Helper" or
// "Exam Helper" is left in app/src or index.html (tests, which quote the old name, excepted).
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return p.endsWith(`${path.sep}gen`) ? [] : sources(p);
    return /\.(tsx?|css|html)$/.test(e.name) && !/\.test\.tsx?$/.test(e.name) ? [p] : [];
  });
}

describe("the app's name (R22.5.8.8)", () => {
  it("no old name in app/src or index.html", () => {
    const files = [...sources(path.join(appDir, "src")), path.join(appDir, "index.html")];
    const hits = files.filter((f) => /Exam (Revision )?Helper/.test(readFileSync(f, "utf8")));
    expect(hits.map((f) => path.relative(appDir, f))).toEqual([]);
  });

  it("the window title is ETACH", () => {
    expect(readFileSync(path.join(appDir, "index.html"), "utf8")).toMatch(/<title>ETACH<\/title>/);
  });
});
