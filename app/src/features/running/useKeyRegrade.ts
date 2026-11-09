/**
 * Re-grade after checking keys (PRD v8.1, step 22.4.5, decision D4). A key change starts no run:
 * the sidecar notes the test in `regrade_pending` (data-model v1.20). This hook
 *
 * - knows whether a test has key changes not re-graded yet: the thread's `regrade_pending`
 *   (`GET /threads/{id}`), or a change made in this window (`markChanged`, so a quick leave right
 *   after a verify still counts before the thread reloads);
 * - calls `POST /tests/{id}/regrade` once when the teacher leaves the Key tab (to another
 *   workspace tab, another thread, or out of the workspace) with keys changed;
 * - step 22.4.8 (answer 6): also once when the teacher leaves a thread whose test has keys
 *   changed, from any tab (one call even when the Key tab was showing);
 * - and `regrade(testId)` for the Re-grade button.
 *
 * Verifying several keys in a row calls nothing: only the leave (or the button) does.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiClient } from "@/api/client";

export interface KeyRegrade {
  /** The test's keys changed and no re-grade has started since. */
  pending: (testId: string | null | undefined) => boolean;
  /** A key of `testId` changed (a PUT or a key Review fix). */
  markChanged: (testId: string) => void;
  /** Starts the re-grade now (the Re-grade button). */
  regrade: (testId: string) => Promise<void>;
  /** The last re-grade's error, for the bar. */
  error: string | null;
}

export interface UseKeyRegradeArgs {
  api: ApiClient | null;
  /** The open thread's test and whether the sidecar says it is pending. */
  threadTestId: string | null;
  threadPending: boolean;
  /** The Key tab's test while the Key tab shows; `null` on any other view. */
  keyTabTestId: string | null;
  /** The open thread (a thread switch while the Key tab shows is a leave). */
  activeId: string | null;
  /** After `POST /regrade` queued runs (the sidebar and the run list reload). */
  onQueued?: (runIds: string[]) => void;
  /** After every change and re-grade: the thread detail reloads. */
  onChanged?: () => void;
}

export function useKeyRegrade({ api, threadTestId, threadPending, keyTabTestId, activeId, onQueued, onChanged }: UseKeyRegradeArgs): KeyRegrade {
  const [changed, setChanged] = useState<ReadonlySet<string>>(() => new Set());
  const [error, setError] = useState<string | null>(null);
  /** Tests the sidecar reported pending and no re-grade has cleared in this window since. */
  const cleared = useRef(new Set<string>());

  const pending = useCallback(
    (testId: string | null | undefined) =>
      !!testId && (changed.has(testId) || (testId === threadTestId && threadPending && !cleared.current.has(testId))),
    [changed, threadTestId, threadPending],
  );

  const onQueuedRef = useRef(onQueued);
  const onChangedRef = useRef(onChanged);
  useEffect(() => {
    onQueuedRef.current = onQueued;
    onChangedRef.current = onChanged;
  });

  const markChanged = useCallback((testId: string) => {
    cleared.current.delete(testId);
    setChanged((s) => (s.has(testId) ? s : new Set(s).add(testId)));
    onChangedRef.current?.();
  }, []);

  const regrade = useCallback(
    async (testId: string) => {
      if (!api) return;
      cleared.current.add(testId);
      setChanged((s) => {
        if (!s.has(testId)) return s;
        const next = new Set(s);
        next.delete(testId);
        return next;
      });
      setError(null);
      try {
        const res = await api.post("/tests/{id}/regrade", { path: { id: testId } });
        if (res.run_ids.length) onQueuedRef.current?.(res.run_ids);
      } catch (err) {
        cleared.current.delete(testId);
        setChanged((s) => new Set(s).add(testId));
        setError(err instanceof Error ? err.message : "The re-grade did not start.");
      } finally {
        onChangedRef.current?.();
      }
    },
    [api],
  );

  // Leaving the Key tab: the view moved off Key, to another test's Key, or to another thread.
  // This effect runs before the refs below are updated, so it sees what the Key tab's test was
  // pending as of the last render (a thread switch drops that thread's detail at once).
  // Leaving a thread (step 22.4.8): the open thread's test, as of the last render, if pending.
  const left = useRef<{ testId: string; threadId: string | null } | null>(null);
  const keyTabPending = useRef(false);
  const thread = useRef<{ threadId: string | null; testId: string | null; pending: boolean }>({
    threadId: activeId,
    testId: null,
    pending: false,
  });
  const regradeRef = useRef(regrade);
  useEffect(() => {
    const prev = left.current;
    const wasPending = keyTabPending.current;
    const prevThread = thread.current;
    left.current = keyTabTestId ? { testId: keyTabTestId, threadId: activeId } : null;
    const started = new Set<string>();
    if (prev && !(prev.testId === keyTabTestId && prev.threadId === activeId) && wasPending) {
      started.add(prev.testId);
      void regradeRef.current(prev.testId);
    }
    if (prevThread.threadId !== activeId && prevThread.pending && prevThread.testId && !started.has(prevThread.testId)) {
      void regradeRef.current(prevThread.testId);
    }
  }, [keyTabTestId, activeId]);
  useEffect(() => {
    regradeRef.current = regrade;
    keyTabPending.current = pending(keyTabTestId);
    thread.current = { threadId: activeId, testId: threadTestId, pending: pending(threadTestId) };
  });

  return { pending, markChanged, regrade, error };
}
