/**
 * The toast on `run.done` / `run.failed` (plan step 15). In Tauri: the OS notification
 * (`notify.ts`); in a browser, or when permission is refused: the in-app toast list.
 *
 * The title is the thread's `shown_title` from `GET /threads/{id}`, so a thread that is not in the
 * loaded list yet still shows its real name, not "New thread" (step 22.2.3).
 *
 * Each (run, outcome) notifies once: the stream already drops replayed ids after a reconnect
 * (`api/sse.ts`), and the `seen` set also covers a second delivery of the same run outcome.
 */
import { useCallback, useRef, useState } from "react";
import type { ApiClient } from "@/api/client";
import { useEvents, type EtachEvent } from "@/api/sse";
import { notifyOs, type RunNotice } from "./notify";
import { isKeyRun } from "./keyRun";

export interface Toast extends RunNotice {
  id: string;
  kind: "done" | "failed";
}

export function useRunNotifications(api: ApiClient, fallbackName: (threadId: string) => string) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seen = useRef(new Set<string>());

  const dismiss = useCallback((id: string) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  useEvents(
    (e: EtachEvent) => {
      const runId = e.data.run_id;
      const threadId = e.data.thread_id;
      if (!runId) return;
      const key = `${runId}:${e.type}`;
      if (seen.current.has(key)) return;
      seen.current.add(key);
      // The key run every extraction queues (step 22.6.4, D13) never shows a toast or notice.
      const keyRun = api
        .get("/runs/{id}", { path: { id: runId } })
        .then((d) => isKeyRun(d.run))
        .catch(() => false);
      const kind = e.type === "run.done" ? "done" : "failed";
      const body =
        kind === "done"
          ? "Finished."
          : `Failed${typeof e.data.error === "string" && e.data.error ? `: ${e.data.error}` : "."}`;
      const name = threadId
        ? api
            .get("/threads/{id}", { path: { id: threadId } })
            .then((d) => d.shown_title || d.thread.title || fallbackName(threadId))
            .catch(() => fallbackName(threadId))
        : Promise.resolve("Run");
      void Promise.all([keyRun, name]).then(async ([isKey, title]) => {
        if (isKey) return;
        const notice = { title, body };
        if (await notifyOs(notice)) return;
        setToasts((t) => [...t, { ...notice, id: key, kind }]);
      });
    },
    ["run.done", "run.failed"],
  );

  return { toasts, dismiss };
}
