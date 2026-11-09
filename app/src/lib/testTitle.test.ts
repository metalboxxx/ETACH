// @vitest-environment node
// R22.2.2.6: the app's title and details line equal the DOCX's (the same cases as the sidecar's
// `test_title_line.py`, which checks `display_name()` and `meta_line()` against them).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { testDetailsLine, testTitle, type TitleMeta } from "./testTitle";

const casesPath = fileURLToPath(new URL("../../../sidecar/tests/unit/domain/title_line_cases.json", import.meta.url));
const cases = JSON.parse(readFileSync(casesPath, "utf8")) as {
  meta: TitleMeta;
  points_possible: number;
  /** The value the sidecar sends as `points_each` (10 ÷ graded questions, R22.5.2.12). */
  points_each?: number;
  title: string;
  details: string;
}[];

describe("test title and details line (R22.2.2.6)", () => {
  it.each(cases)("$title", (c) => {
    expect(testTitle(c.meta)).toBe(c.title);
    expect(testDetailsLine(c.meta, c.points_possible, c.points_each)).toBe(c.details);
  });

  it("the shared cases include a points_each case (R22.5.2.12)", () => {
    expect(cases.some((c) => c.points_each === 0.25 && c.details.endsWith("10 points · 0.25 each"))).toBe(true);
  });
});
