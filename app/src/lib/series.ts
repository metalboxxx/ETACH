/**
 * The series list (step 22.5.2, D5, data-model v1.21): id, name and how many tests use each, from
 * the sidecar's `GET /series`. One shared copy, like `lib/schools.ts`: a change in Settings shows
 * in the Series field and in "Same series as" at once, and a series typed on a test (the sidecar
 * adds it) shows after the next load.
 */
import { useEffect, useSyncExternalStore } from "react";
import type { ApiClient, Schemas } from "@/api/client";

export type Series = Schemas["SeriesOut"];

let current: readonly Series[] = [];
let loaded = false;
const listeners = new Set<() => void>();

/** Replace the list (after `GET /series` or an edit) and tell every subscriber. */
export function setSeries(list: readonly Series[]): void {
  current = [...list].sort((a, b) => a.position - b.position);
  loaded = true;
  for (const l of listeners) l();
}

/** Back to empty and not loaded (tests). */
export function resetSeries(): void {
  setSeries([]);
  loaded = false;
}

export function getSeries(): readonly Series[] {
  return current;
}

/** Load the list from the sidecar; returns it. */
export async function loadSeries(api: ApiClient): Promise<readonly Series[]> {
  setSeries(await api.get("/series"));
  return current;
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

/** The series list; loads it once from the sidecar when `api` is given. */
export function useSeries(api?: ApiClient): readonly Series[] {
  const list = useSyncExternalStore(subscribe, getSeries, getSeries);
  useEffect(() => {
    if (api && !loaded) loadSeries(api).catch(() => undefined); // the field still takes typing
  }, [api]);
  return list;
}
