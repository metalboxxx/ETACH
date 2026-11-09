/**
 * The Tests list's order (step 22.5.1, comment 6, D3). A–Z by name is the default; the sort
 * button offers Z–A, Newest added (`created_at`, newest first) and By grade (grade ascending, A–Z
 * inside a grade, no grade last). Names compare Vietnamese-aware with `Intl.Collator("vi")`, numbers
 * by value ("Grade 9" before "Grade 10", the teacher). The order applies to search results too,
 * except that a test whose id is the search ("T-0008", "t-0008", "T0008") is always the top row.
 * The choice is kept for the session (sessionStorage), so it survives switching sidebar tabs.
 */
import type { Schemas } from "@/api/client";
import { readSession, writeSession } from "@/lib/storage";

type TestSummary = Schemas["TestSummary"];

export type TestSort = "az" | "za" | "newest" | "grade";

export const TEST_SORTS: readonly { value: TestSort; label: string }[] = [
  { value: "az", label: "A–Z" },
  { value: "za", label: "Z–A" },
  { value: "newest", label: "Newest added" },
  { value: "grade", label: "By grade" },
];

const SORT_KEY = "etach.testsSort";

/** The session's choice, else A–Z. */
export function readTestSort(): TestSort {
  const stored = readSession<string>(SORT_KEY);
  return TEST_SORTS.some((s) => s.value === stored) ? (stored as TestSort) : "az";
}

export function writeTestSort(sort: TestSort): void {
  writeSession(SORT_KEY, sort);
}

const collator = new Intl.Collator("vi", { numeric: true });

/** An id as the search compares it: no dash, upper case, trimmed (as the sidecar's `search_tests`). */
const idKey = (text: string) => text.trim().replaceAll("-", "").toUpperCase();

/**
 * `rows` in `sort` order (a new array); ties fall back to the id, so the order is stable. With a
 * search `query`, a test whose id equals it comes first, whatever the order.
 */
export function sortTests<T extends Pick<TestSummary, "id" | "display_name" | "created_at" | "meta">>(
  rows: readonly T[],
  sort: TestSort,
  query = "",
): T[] {
  const byName = (a: T, b: T) => collator.compare(a.display_name, b.display_name) || collator.compare(a.id, b.id);
  const compare: (a: T, b: T) => number =
    sort === "za"
      ? (a, b) => byName(b, a)
      : sort === "newest"
        ? (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at) || collator.compare(b.id, a.id)
        : sort === "grade"
          ? (a, b) => gradeRank(a) - gradeRank(b) || byName(a, b)
          : byName;
  const sorted = [...rows].sort(compare);
  const key = idKey(query);
  const at = key ? sorted.findIndex((t) => idKey(t.id) === key) : -1;
  if (at > 0) sorted.unshift(...sorted.splice(at, 1));
  return sorted;
}

/** No grade sorts last. */
function gradeRank(t: Pick<TestSummary, "meta">): number {
  const g = t.meta.grade;
  return g === null || g === undefined ? Number.POSITIVE_INFINITY : g;
}
