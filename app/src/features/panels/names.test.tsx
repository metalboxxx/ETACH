// R22.2.1.1 (comment 7, PRD §10 "Names on screen" v5.1): the student's answers are "Student
// answers", the correct answers are the "Key"; no text says "Answer key" or "correct answer",
// and no label says "Answers" alone. This scans the app's source strings (comments left out) and
// the rendered workspace titles.
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { panelTitle } from "./panelView";

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return name === "gen" ? [] : sources(full);
    return /\.(tsx?|css)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [full] : [];
  });
}

/** The file without its comments (`//` lines and block comments). */
function code(file: string): string {
  return readFileSync(file, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:"'`])\/\/.*$/gm, "$1")
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "");
}

describe("names on screen (R22.2.1.1)", () => {
  const files = sources(SRC);

  it("finds the app's sources", () => {
    expect(files.length).toBeGreaterThan(20);
  });

  it("no string says 'Answer key' or 'correct answer'", () => {
    const hits = files.filter((f) => /answer key|correct answer/i.test(code(f)));
    expect(hits.map((f) => path.relative(SRC, f))).toEqual([]);
  });

  it("no label says 'Answers' alone", () => {
    // a JSX text node, a string or an attribute whose words start with "Answers"
    const label = /(>\s*Answers\b|["'`]Answers\b)/;
    const hits = files.filter((f) => label.test(code(f)));
    expect(hits.map((f) => path.relative(SRC, f))).toEqual([]);
  });

  it("the workspace titles say 'Student answers' and 'Key'", () => {
    expect(panelTitle({ kind: "answers", attemptId: "A-1", testId: "T-1" })).toBe("Student answers");
    expect(panelTitle({ kind: "keys", testId: "T-1" })).toBe("Key");
  });
});
