/**
 * The photo check card's state (PRD D17, D19, D1). It is frontend state until Run: there is no
 * route to persist it, so the per-thread draft lives in memory and in `sessionStorage`
 * (`etach.photoCheck.<threadId>`), which survives the page reload after a sidecar restart.
 *
 * Run sends `toExtractInput(draft)`: the pages in strip order with their rotation (clockwise,
 * structure §7) and 🔑 flag, and the picked existing test. Without a picked test, "Same series as"
 * sends `series_name` (data-model v1.21, D5): the new test gets that series, and grade, occasion,
 * term and year from the newest test of the series.
 */
import type { Schemas } from "@/api/client";
import { readSession, removeSession, writeSession } from "@/lib/storage";
import { todayIso } from "@/lib/skills";

export type PageInput = Schemas["PageInput"];
export type ExtractInput = Schemas["ExtractInput"];
export type Rotation = PageInput["rotation"];

export interface PickedTest {
  id: string;
  display_name: string;
}

export interface PhotoCheckDraft {
  pages: PageInput[];
  existingTest: PickedTest | null;
  /** "Same series as": a name from the Series list (D5); used only when no existing test is picked. */
  seriesName?: string | null;
  /** Step 22.5.5b (D11a): the date the student took the paper, `YYYY-MM-DD`; unset = today. */
  takenOn?: string;
}

export const EMPTY_DRAFT: PhotoCheckDraft = { pages: [], existingTest: null };

const memory = new Map<string, PhotoCheckDraft>();
const key = (threadId: string) => `etach.photoCheck.${threadId}`;

export function loadDraft(threadId: string): PhotoCheckDraft | null {
  const hit = memory.get(threadId);
  if (hit) return hit;
  const stored = readSession<PhotoCheckDraft>(key(threadId));
  if (!stored || !Array.isArray(stored.pages)) return null;
  const draft: PhotoCheckDraft = { pages: stored.pages, existingTest: stored.existingTest ?? null };
  if (typeof stored.seriesName === "string" && stored.seriesName) draft.seriesName = stored.seriesName;
  if (typeof stored.takenOn === "string" && stored.takenOn) draft.takenOn = stored.takenOn;
  memory.set(threadId, draft);
  return draft;
}

export function saveDraft(threadId: string, draft: PhotoCheckDraft): void {
  if (!draft.pages.length && !draft.existingTest && !draft.seriesName) {
    clearDraft(threadId);
    return;
  }
  memory.set(threadId, draft);
  writeSession(key(threadId), draft);
}

export function clearDraft(threadId: string): void {
  memory.delete(threadId);
  removeSession(key(threadId));
}

/** Test helper: forget the in-memory copies. */
export function resetDraftMemory(): void {
  memory.clear();
}

/** A DOCX text page: `file_id` is the text file itself (store/documents.py). */
export function isTextPage(page: PageInput): boolean {
  return page.text_file_id !== null && page.text_file_id === page.file_id;
}

export function rotateClockwise(r: Rotation): Rotation {
  return ((r + 90) % 360) as Rotation;
}

export function movePage<T>(list: readonly T[], from: number, to: number): T[] {
  if (from === to || from < 0 || from >= list.length || to < 0 || to >= list.length) {
    return [...list];
  }
  const out = [...list];
  const [item] = out.splice(from, 1);
  out.splice(to, 0, item as T);
  return out;
}

export function toExtractInput(draft: PhotoCheckDraft): ExtractInput {
  const series = !draft.existingTest && draft.seriesName ? { series_name: draft.seriesName } : {};
  return {
    ...series,
    pages: draft.pages.map((p) => ({
      file_id: p.file_id,
      rotation: p.rotation,
      is_key: p.is_key,
      text_file_id: p.text_file_id,
    })),
    existing_test_id: draft.existingTest?.id ?? null,
    supersedes_attempt_id: null,
    taken_on: draft.takenOn || todayIso(),
  };
}
