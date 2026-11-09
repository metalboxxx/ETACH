/**
 * The sidebar's thread list (PRD §10.1, R15.8). `GET /threads` already says where each thread
 * belongs: `group` is the student's name, "Chưa rõ" (unknown student) or "Blank tests" (sidecar
 * `api/routes/threads.py`). The client only maps those fields: student groups first (newest
 * activity first), then Chưa rõ, then Blank tests.
 */
import { useCallback, useEffect, useState } from "react";
import type { ApiClient, Schemas } from "@/api/client";

export type ThreadSummary = Schemas["ThreadSummary"];

export const UNKNOWN_STUDENT = "Chưa rõ";
export const BLANK_GROUP = "Blank tests";

export interface ThreadGroup {
  name: string;
  threads: ThreadSummary[];
}

export function groupThreads(rows: readonly ThreadSummary[]): ThreadGroup[] {
  const byName = new Map<string, ThreadSummary[]>();
  for (const row of rows) {
    const name = row.group;
    const list = byName.get(name) ?? [];
    list.push(row);
    byName.set(name, list);
  }
  const rank = (name: string) => (name === BLANK_GROUP ? 2 : name === UNKNOWN_STUDENT ? 1 : 0);
  return Array.from(byName, ([name, threads]) => ({ name, threads })).sort(
    (a, b) => rank(a.name) - rank(b.name),
  );
}

/** `GET /threads`; `null` until loaded (or when the sidecar is unreachable). */
export function useThreads(api: ApiClient) {
  const [threads, setThreads] = useState<ThreadSummary[] | null>(null);
  const reload = useCallback(
    (signal?: AbortSignal) =>
      api
        .get("/threads", { signal })
        .then((rows) => setThreads(Array.isArray(rows) ? rows : []))
        .catch((err: unknown) => {
          if (!(err instanceof DOMException && err.name === "AbortError")) setThreads(null);
        }),
    [api],
  );
  useEffect(() => {
    const ctrl = new AbortController();
    void reload(ctrl.signal);
    return () => ctrl.abort();
  }, [reload]);
  return { threads, reload: useCallback(() => void reload(), [reload]) };
}

/** The name a thread row shows: its `shown_title` (data-model §5.6), else its stored title. */
export function threadName(row: ThreadSummary): string {
  return row.shown_title || row.thread.title || "New thread";
}

/** The sidebar's New thread button (`Sidebar.tsx`), where focus goes after the last thread is deleted (F5). */
export const NEW_THREAD_TESTID = "sidebar-new-thread";
