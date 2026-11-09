import { useCallback, useMemo, useState } from "react";
import { createApiClient, type ApiClient } from "@/api/client";
import { readSidecarConfig, type SidecarConfig } from "@/api/config";
import { createEventStream, EventsProvider, useEvents, useEventStatus } from "@/api/sse";
import { AppShell } from "@/components/AppShell";
import "@/styles/print.css";
import { RunningIndicator } from "@/features/running/RunningIndicator";
import { ThreadRunCard } from "@/features/running/ThreadRunCard";
import { Toasts } from "@/features/running/Toasts";
import { useRunNotifications } from "@/features/running/useRunNotifications";
import { useRunning } from "@/features/running/useRunning";
import { threadName as rowName, useThreads } from "@/features/threads/threads";
import { FirstRunScreen, SETUP_SKIPPED_KEY, setupNeed } from "@/features/first-run/FirstRunScreen";
import { useSystemStatus } from "@/hooks/useSystemStatus";
import { useKeyRuns } from "@/features/running/keyRun";
import { readSession, writeSession } from "@/lib/storage";

/** Run events that change a thread's messages or its sidebar group. */
const THREAD_EVENTS = ["run.done", "run.failed", "run.stopped", "run.interrupted", "run.discarded"] as const;

export function Connected({ api }: { api: ApiClient }) {
  const status = useEventStatus();
  const { threads, reload } = useThreads(api);
  const [runEventSeq, setRunEventSeq] = useState(0);
  useEvents(() => {
    reload();
    setRunEventSeq((n) => n + 1);
  }, THREAD_EVENTS);
  const [reviewEventSeq, setReviewEventSeq] = useState(0);
  useEvents(() => {
    setReviewEventSeq((n) => n + 1);
    reload(); // the sidebar marks threads that still have unsure spots
  }, ["review.changed"]);
  const running = useRunning(api);
  const keyRuns = useKeyRuns(api, running.runs);
  const system = useSystemStatus(api);
  const threadName = useCallback(
    (id: string) => {
      const row = threads?.find((t) => t.thread.id === id);
      return row ? rowName(row) : "New thread";
    },
    [threads],
  );
  const runs = running.runs;
  const act = running.act;
  const threadRunning = useCallback(
    (threadId: string) => {
      const entry = runs.find(
        (r) => r.run.thread_id === threadId && (r.run.status === "running" || r.run.status === "stopping"),
      );
      return entry ? <ThreadRunCard entry={entry} onStop={() => void act("stop", entry.run.id)} /> : null;
    },
    [runs, act],
  );
  const { toasts, dismiss } = useRunNotifications(api, threadName);
  const [setupSkipped, setSetupSkipped] = useState(() => readSession<boolean>(SETUP_SKIPPED_KEY) === true);
  if (system.status && setupNeed(system.status) && !setupSkipped) {
    return (
      <FirstRunScreen
        api={api}
        status={system.status}
        onReload={system.reload}
        onContinue={() => {
          writeSession(SETUP_SKIPPED_KEY, true);
          setSetupSkipped(true);
        }}
      />
    );
  }
  return (
    <>
      <AppShell
        connection={status}
        api={api}
        threads={threads}
        onThreadsChanged={reload}
        onRunStarted={running.reload}
        runEventSeq={runEventSeq}
        reviewEventSeq={reviewEventSeq}
        activeRunThreadIds={running.activeThreadIds}
        busyRunThreadIds={running.busyThreadIds}
        keyRuns={keyRuns}
        threadRunning={threadRunning}
        systemStatus={system.status}
        onSystemStatusReload={system.reload}
        running={
          <RunningIndicator
            runs={running.runs}
            power={running.power}
            threadName={threadName}
            onStop={(id) => void running.act("stop", id)}
            onResume={(id) => void running.act("resume", id)}
            onDiscard={(id) => void running.act("discard", id)}
          />
        }
      />
      <Toasts toasts={toasts} onDismiss={dismiss} />
    </>
  );
}

/** `config` is read from `window.__ETACH__` or the URL hash; without one, the app shows "Not connected". */
export default function App({ config }: { config?: SidecarConfig | null }) {
  const [cfg] = useState(() => (config === undefined ? readSidecarConfig() : config));
  const api = useMemo(() => (cfg ? createApiClient(cfg) : null), [cfg]);
  const stream = useMemo(() => (api ? createEventStream((id) => api.eventsUrl(id)) : null), [api]);
  if (!api || !stream) return <AppShell connection="none" />;
  return (
    <EventsProvider stream={stream}>
      <Connected api={api} />
    </EventsProvider>
  );
}
