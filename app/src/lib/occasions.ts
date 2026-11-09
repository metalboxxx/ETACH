/**
 * The occasion list (step 22.3.7, data-model v1.17): code, label (the Occasion editor and chips)
 * and short name (the Test name), from the sidecar's `GET /occasions`. One shared copy, so a
 * change in Settings shows in the Occasion editor and every Test name at once. Before the first
 * load it holds the ten built-ins as migration 0007 seeds them.
 */
import { useEffect, useSyncExternalStore } from "react";
import type { ApiClient, Schemas } from "@/api/client";
import { setOccasionShortNames } from "./testTitle";

export type Occasion = Schemas["OccasionOut"];

const seed = (code: string, label: string, short_name: string, position: number): Occasion => ({
  code,
  label,
  short_name,
  position,
  builtin: true,
  test_count: 0,
});

/** The built-ins before the sidecar answers (the same as migration 0007's seed). */
export const BUILTIN_OCCASIONS: readonly Occasion[] = [
  seed("MidTerm", "Mid-term test", "Mid-term", 0),
  seed("FinalTerm", "Final-term test", "Final Term", 1),
  seed("NationalExam", "National exam", "National Exam", 2),
  seed("EntranceExam", "Entrance exam", "Entrance Exam", 3),
  seed("GiftedExam", "Gifted students' exam", "Gifted Exam", 4),
  seed("UnitTest", "Unit test", "Unit Test", 5),
  seed("FifteenMinuteTest", "15-minute test", "15-minute Test", 6),
  seed("GrammarPractice", "Grammar practice", "Grammar Practice", 7),
  seed("TopicPractice", "Topic practice", "Topic Practice", 8),
  seed("Placement", "Placement test", "Placement", 9),
];

let current: readonly Occasion[] = BUILTIN_OCCASIONS;
let loaded = false;
const listeners = new Set<() => void>();

/** Replace the list (after `GET /occasions` or an edit) and tell every subscriber. */
export function setOccasions(list: readonly Occasion[]): void {
  current = [...list].sort((a, b) => a.position - b.position);
  loaded = true;
  setOccasionShortNames(Object.fromEntries(current.map((o) => [o.code, o.short_name])));
  for (const l of listeners) l();
}

/** Back to the built-ins (tests). */
export function resetOccasions(): void {
  setOccasions(BUILTIN_OCCASIONS);
  loaded = false;
}

export function getOccasions(): readonly Occasion[] {
  return current;
}

/** Load the list from the sidecar; returns it. */
export async function loadOccasions(api: ApiClient): Promise<readonly Occasion[]> {
  setOccasions(await api.get("/occasions"));
  return current;
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

/** The occasion list; loads it once from the sidecar when `api` is given. */
export function useOccasions(api?: ApiClient): readonly Occasion[] {
  const list = useSyncExternalStore(subscribe, getOccasions, getOccasions);
  useEffect(() => {
    if (api && !loaded) loadOccasions(api).catch(() => undefined); // the built-ins stay
  }, [api]);
  return list;
}

/** The label of `code`: "FinalTerm" → "Final-term test"; "Other:<text>" → the text. */
export function occasionLabelOf(code: string | null | undefined): string {
  if (!code) return "";
  const other = /^Other:(.*)$/.exec(code);
  if (other) return other[1] ?? "";
  return current.find((o) => o.code === code)?.label ?? code;
}
