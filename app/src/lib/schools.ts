/**
 * The school list (step 22.4.2, data-model v1.18): id, name and how many tests and students use
 * each, from the sidecar's `GET /schools`. One shared copy, so a change in Settings shows in every
 * School field at once, and a school typed on a test or student (the sidecar adds it) shows in
 * the list after the next load.
 */
import { useEffect, useSyncExternalStore } from "react";
import type { ApiClient, Schemas } from "@/api/client";

export type School = Schemas["SchoolOut"];

let current: readonly School[] = [];
let loaded = false;
const listeners = new Set<() => void>();

/** Replace the list (after `GET /schools` or an edit) and tell every subscriber. */
export function setSchools(list: readonly School[]): void {
  current = [...list].sort((a, b) => a.position - b.position);
  loaded = true;
  for (const l of listeners) l();
}

/** Back to empty and not loaded (tests). */
export function resetSchools(): void {
  setSchools([]);
  loaded = false;
}

export function getSchools(): readonly School[] {
  return current;
}

/** Load the list from the sidecar; returns it. */
export async function loadSchools(api: ApiClient): Promise<readonly School[]> {
  setSchools(await api.get("/schools"));
  return current;
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

/** The school list; loads it once from the sidecar when `api` is given. */
export function useSchools(api?: ApiClient): readonly School[] {
  const list = useSyncExternalStore(subscribe, getSchools, getSchools);
  useEffect(() => {
    if (api && !loaded) loadSchools(api).catch(() => undefined); // the field still takes typing
  }, [api]);
  return list;
}

/** The form two names are compared in (the sidecar's `fold`): spaces collapsed, case folded. */
export function foldSchool(name: string): string {
  return name.split(/\s+/).filter(Boolean).join(" ").toLocaleLowerCase("vi");
}
