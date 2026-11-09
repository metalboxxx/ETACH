/**
 * Step 22.6.4 (D4, D11, D13): the "make the key" run that every extraction queues on its thread
 * (`kind: "grade"`, `attempt_id` null, `input.reason: "after_extract"`). While it is queued, running
 * or stopping, the Key tab shows a note and Grade student answers waits; it never shows a toast;
 * when it fails or is discarded the Key tab says that Grade will make the key.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiClient, Schemas } from "@/api/client";
import { useEvents, type EtachEvent } from "@/api/sse";
import type { RunEntry } from "./useRunning";

type Run = Pick<Schemas["Run"], "kind" | "input">;

/** True for the key run an extraction queues (R22.6.4.1). */
export function isKeyRun(run: Run | null | undefined): boolean {
  if (!run || run.kind !== "grade") return false;
  const input = run.input as { reason?: unknown } | null | undefined;
  return input?.reason === "after_extract";
}

/** Statuses in which the key is still being made. */
const PENDING: ReadonlySet<string> = new Set(["queued", "running", "stopping"]);

export interface KeyRuns {
  /** The thread's key run is queued, running or stopping. */
  pending: (threadId: string) => boolean;
  /** The thread's last key run failed or was discarded (hidden while a new one is pending; cleared when one finishes). */
  failed: (threadId: string) => boolean;
}

export function useKeyRuns(api: ApiClient, runs: readonly RunEntry[]): KeyRuns {
  const known = useRef(new Map<string, string>()); // key run id → thread id
  const [failedThreads, setFailedThreads] = useState<ReadonlySet<string>>(new Set());

  // Remember every key run seen, so its end event can be matched to its thread. (A new pending key
  // run hides an old failure through `failed` below; `run.done` clears it.)
  useEffect(() => {
    for (const r of runs) if (isKeyRun(r.run)) known.current.set(r.run.id, r.run.thread_id);
  }, [runs]);

  const mark = useCallback((threadId: string, failed: boolean) => {
    setFailedThreads((prev) => {
      if (prev.has(threadId) === failed) return prev;
      const next = new Set(prev);
      if (failed) next.add(threadId);
      else next.delete(threadId);
      return next;
    });
  }, []);

  useEvents(
    (e: EtachEvent) => {
      const runId = e.data.run_id;
      if (!runId) return;
      const failed = e.type !== "run.done";
      const threadId = known.current.get(runId);
      if (threadId) {
        mark(threadId, failed);
        return;
      }
      if (!failed) return;
      // a key run that ended before the runs list saw it (a fast failure)
      api
        .get("/runs/{id}", { path: { id: runId } })
        .then((d) => {
          if (isKeyRun(d.run)) mark(d.run.thread_id, true);
        })
        .catch(() => {});
    },
    ["run.done", "run.failed", "run.discarded"],
  );

  const pending = useCallback(
    (threadId: string) => runs.some((r) => r.run.thread_id === threadId && isKeyRun(r.run) && PENDING.has(r.run.status)),
    [runs],
  );
  const failed = useCallback((threadId: string) => failedThreads.has(threadId) && !pending(threadId), [failedThreads, pending]);
  return { pending, failed };
}
