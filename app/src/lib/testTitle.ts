/**
 * The test's title and details line, as the test DOCX writes them (answer 16): the title is
 * `TestMetadata.display_name()` and the details line is `docx_export.meta_line()` in the sidecar.
 * The shared cases in `sidecar/tests/unit/domain/title_line_cases.json` hold both sides equal
 * (`testTitle.test.ts` here, `test_title_line.py` there).
 */
const EN_DASH = "–";

export interface TitleMeta {
  occasion: string;
  grade?: number | null;
  term?: number | null;
  test_number?: string | null;
  variant?: string | null;
  school?: string | null;
  source?: string | null;
  year?: string | null;
  duration_minutes?: number | null;
  test_code?: string | null;
  extra?: Record<string, unknown> | null;
  edited_fields?: string[] | null;
}

/** The `edited_fields` entry and `extra` key of a Test name the teacher typed (data-model v1.13). */
export const TYPED_NAME_KEY = "display_name";

/** The unknown occasion (`domain.header.UNKNOWN_OCCASION`): left out of the Test name (answer 5). */
export const UNKNOWN_OCCASION = "Other:unknown";

/** The automatic name when every part is empty (sidecar `UNTITLED_TEST`). */
export const UNTITLED_TEST = "Untitled test";

/**
 * The occasion in the Test name (decision C, answer 4; sidecar `OCCASION_SHORT_NAMES`). Step
 * 22.3.7: the sidecar's `GET /occasions` is the source (`lib/occasions.ts` sets it here through
 * `setOccasionShortNames`); these built-ins are only the values before it answers.
 */
export const OCCASION_SHORT_NAME: Record<string, string> = {
  MidTerm: "Mid-term",
  FinalTerm: "Final Term",
  NationalExam: "National Exam",
  EntranceExam: "Entrance Exam",
  GiftedExam: "Gifted Exam",
  UnitTest: "Unit Test",
  FifteenMinuteTest: "15-minute Test",
  GrammarPractice: "Grammar Practice",
  TopicPractice: "Topic Practice",
  Placement: "Placement",
};

/** Replace the short names (from the sidecar's occasion list). */
export function setOccasionShortNames(names: Record<string, string>): void {
  for (const k of Object.keys(OCCASION_SHORT_NAME)) delete OCCASION_SHORT_NAME[k];
  Object.assign(OCCASION_SHORT_NAME, names);
}

/** `FinalTerm` → "Final Term"; `Other:<text>` → the text; the unknown occasion → "". */
export function occasionShortName(occasion: string): string {
  if (!occasion || occasion === UNKNOWN_OCCASION) return "";
  if (occasion.startsWith("Other:")) return occasion.slice("Other:".length).trim() || "Other";
  return OCCASION_SHORT_NAME[occasion] ?? occasion;
}

/** The Test name the teacher typed, or null (sidecar `TestMetadata.display_name()`). */
export function typedTestName(meta: TitleMeta): string | null {
  const typed = meta.extra?.[TYPED_NAME_KEY];
  if (!meta.edited_fields?.includes(TYPED_NAME_KEY) || typeof typed !== "string" || !typed.trim()) return null;
  return typed;
}

/** The Test name: a typed one, else the automatic one (`automaticTestName`). */
export function testTitle(meta: TitleMeta): string {
  return typedTestName(meta) ?? automaticTestName(meta);
}

/** "Grade 8 - Final Term 1 - <school or source> - 2025 - Test 7"; a missing part is left out. */
export function automaticTestName(meta: TitleMeta): string {
  const parts: string[] = [];
  if (meta.grade !== null && meta.grade !== undefined) parts.push(`Grade ${meta.grade}`);
  const occasion = occasionShortName(meta.occasion);
  if (occasion) parts.push(meta.term === null || meta.term === undefined ? occasion : `${occasion} ${meta.term}`);
  const school = meta.school || meta.source;
  if (school) parts.push(school);
  if (meta.year) parts.push(meta.year.replaceAll("-", EN_DASH));
  if (meta.test_number) parts.push(`Test ${meta.test_number}`);
  return parts.join(" - ") || UNTITLED_TEST;
}

/**
 * At most 2 decimals, trailing zeros dropped (0.25, 0.2, 0.22), as the sidecar's `_num`:
 * `round(x * 100) / 100`, where Python rounds an exact half to the even neighbour (0.125 → 0.12).
 */
export function num(x: number | null | undefined): string {
  if (x === null || x === undefined) return EN_DASH;
  const v = x * 100;
  let r = Math.round(v);
  if (v - Math.floor(v) === 0.5 && r % 2 !== 0) r -= 1;
  return String(r / 100);
}

/**
 * "45 minutes · Code 132 · 10 points · 0.25 each": the parts the title leaves out, then the points
 * and each question's value (`points_each`, step 22.5.2, D7) when the test has graded questions.
 */
export function testDetailsLine(
  meta: TitleMeta,
  pointsPossible: number | null | undefined,
  pointsEach?: number | null,
): string {
  const parts: string[] = [];
  if (meta.duration_minutes) parts.push(`${meta.duration_minutes} minutes`);
  if (meta.test_code) parts.push(`Code ${meta.test_code}`);
  parts.push(`${num(pointsPossible)} points`);
  if (pointsEach !== null && pointsEach !== undefined) parts.push(`${num(pointsEach)} each`);
  return parts.join(" · ");
}
