/**
 * The running indicator in the sidebar slot (PRD §10.1, D22, D23; R15.5).
 *
 * - A running run: the thread name, **Stop**, its progress (the stage in plain words with its
 *   count, a bar, the percent, the elapsed time and a "Writing" sign; step 22.1.3), "keep the
 *   lid open", and "on battery" only when `/system/status` says `power_source = battery`. A
 *   screen reader hears each new stage (a polite live region); the count and the bar stay quiet.
 * - A stopped or interrupted run (also after a restart): the thread name, **Resume**, **Discard**.
 * - Queued runs: "N queued".
 * - Nothing at all (null) when there are no such runs, so the slot stays empty (R13.1).
 */
import type { Schemas } from "@/api/client";
import { RunProgressBar } from "./RunProgressBar";
import type { RunEntry } from "./useRunning";

export interface RunningIndicatorProps {
  runs: readonly RunEntry[];
  power: Schemas["SystemStatus"]["power_source"] | null;
  /** thread id → name */
  threadName: (threadId: string) => string;
  onStop: (runId: string) => void;
  onResume: (runId: string) => void;
  onDiscard: (runId: string) => void;
}

const btn =
  "rounded-button border border-border px-2 py-0.5 text-xs text-text hover:bg-hover focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus";

export function RunningIndicator({ runs, power, threadName, onStop, onResume, onDiscard }: RunningIndicatorProps) {
  const running = runs.filter((r) => r.run.status === "running" || r.run.status === "stopping");
  const paused = runs.filter((r) => r.run.status === "stopped" || r.run.status === "interrupted");
  const queued = runs.filter((r) => r.run.status === "queued").length;
  if (!running.length && !paused.length && !queued) return null;

  return (
    <div data-testid="running-indicator" className="flex flex-col gap-2 rounded-paper border border-border bg-surface p-2 text-sm">
      {running.map((entry) => (
        <div key={entry.run.id} data-testid="run-running" data-run-id={entry.run.id} className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-medium text-text" data-testid="run-thread">
              {threadName(entry.run.thread_id)}
            </span>
            <button
              type="button"
              className={btn}
              disabled={entry.run.status === "stopping"}
              onClick={() => onStop(entry.run.id)}
            >
              {entry.run.status === "stopping" ? "Stopping…" : "Stop"}
            </button>
          </div>
          <RunProgressBar entry={entry} />
          <span className="sr-only" aria-live="polite">
            {entry.progress.stageLabel ?? ""}
          </span>
        </div>
      ))}
      {running.length > 0 && (
        <p className="text-xs text-muted" data-testid="keep-lid-open">
          Keep the lid open
        </p>
      )}
      {running.length > 0 && power === "battery" && (
        <p className="text-xs text-danger" data-testid="on-battery">
          On battery: the run is slower
        </p>
      )}
      {paused.map(({ run }) => (
        <div key={run.id} data-testid="run-paused" data-run-id={run.id} className="flex flex-col gap-1">
          <span className="truncate font-medium text-text">{threadName(run.thread_id)}</span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted">{run.status === "stopped" ? "Stopped" : "Interrupted"}</span>
            <button type="button" className={btn} onClick={() => onResume(run.id)}>
              Resume
            </button>
            <button type="button" className={btn} onClick={() => onDiscard(run.id)}>
              Discard
            </button>
          </div>
        </div>
      ))}
      {queued > 0 && (
        <p className="text-xs text-muted" data-testid="run-queued">
          {queued} queued
        </p>
      )}
    </div>
  );
}
