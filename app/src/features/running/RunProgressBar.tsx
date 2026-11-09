/**
 * The run's progress (PRD §10.1 running indicator, v4.12; llm-design §2 "Run progress"): the
 * stage in plain words with its count, a bar for the whole run, the percent, the elapsed time
 * and, while the model streams, a "Writing" sign. Used in the sidebar's running indicator and in
 * the running thread, so the teacher can tell a slow run from a frozen one. Step 22.2.1: the time
 * reads "Elapsed 0:42", the sign "Model is writing" (it beats from the start of a model call), and
 * the stage text wraps instead of being cut off at the sidebar's width.
 *
 * Only the bar's value moves: its transition and the sign's pulse are `motion-safe:` only, so
 * with `prefers-reduced-motion` nothing animates. Colours are tokens (accent-strong on hover
 * keeps the fill at ≥ 3:1 against its track in both modes).
 */
import { useEffect, useState } from "react";
import { progressText, type RunEntry } from "./useRunning";

/** How long (ms) a `tokens` event keeps the "Model is writing" sign on: a few missed heartbeats. */
export const WRITING_MS = 15_000;

/** "4:05", or "1:02:09" from an hour on. */
export function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

/** The current time, ticking every second while mounted. */
function useNow(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}

export interface RunProgressBarProps {
  entry: RunEntry;
}

export function RunProgressBar({ entry }: RunProgressBarProps) {
  const now = useNow();
  const { progress, since } = entry;
  const text = progressText(progress) ?? "Starting…";
  const percent = progress.percent;
  const writing = progress.writingAt !== null && now - progress.writingAt < WRITING_MS;

  return (
    <div className="flex min-w-0 flex-col gap-1.5" data-testid="run-progress">
      <span className="text-xs text-text [overflow-wrap:anywhere]" data-testid="run-step">
        {text}
      </span>
      <div
        role="progressbar"
        aria-label="Run progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent ?? undefined}
        aria-valuetext={percent !== null ? `${percent}%, ${text}` : text}
        data-testid="run-progressbar"
        className="h-1.5 w-full overflow-hidden rounded-full bg-hover"
      >
        <div
          className="h-full w-full origin-left rounded-full bg-accent-strong motion-safe:transition-transform motion-safe:duration-500 motion-safe:ease-out"
          style={{ transform: `scaleX(${(percent ?? 0) / 100})` }}
        />
      </div>
      <div className="flex items-center justify-between gap-2 text-xs text-muted">
        <span className="flex items-center gap-2 tabular-nums">
          {percent !== null && <span data-testid="run-percent">{percent}%</span>}
          <span data-testid="run-elapsed">
            Elapsed {formatElapsed(now - since)}
          </span>
        </span>
        {writing && (
          <span className="flex items-center gap-1.5" data-testid="run-writing">
            <span aria-hidden className="size-1.5 rounded-full bg-accent-strong motion-safe:animate-pulse" />
            <span>Model is writing</span>
          </span>
        )}
      </div>
    </div>
  );
}
