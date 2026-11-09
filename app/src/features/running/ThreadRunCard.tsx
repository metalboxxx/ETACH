/**
 * The running thread's progress (PRD §10.1, v4.12): the same bar as the running indicator,
 * at the top of the thread's workspace while its run is running (step 22.3.2), with Stop when
 * `onStop` is given. Resume and Discard stay in the indicator.
 *
 * In the workspace (`CompactBarContext`: the Key tab since step 22.4.5 comment 11, every tab since
 * step 22.4.8 answer 7) it is one line: the stage, a short bar, the percent and Stop.
 */
import { useCompactBar } from "./compactBar";
import { RunProgressBar } from "./RunProgressBar";
import { progressText, type RunEntry } from "./useRunning";

const stopButton =
  "rounded-button border border-border px-3 py-1 text-sm text-text hover:bg-hover focus-visible:outline-2 focus-visible:outline-focus";

export function ThreadRunCard({ entry, onStop }: { entry: RunEntry; onStop?: () => void }) {
  const stopping = entry.run.status === "stopping";
  const compact = useCompactBar();
  const titleId = `run-${entry.run.id}-title`;
  const stop = onStop && !stopping && (
    <button type="button" data-testid="thread-run-stop" onClick={onStop} className={(compact ? "shrink-0 " : "self-start ") + stopButton}>
      Stop
    </button>
  );
  if (compact) {
    const text = progressText(entry.progress) ?? "Starting…";
    const percent = entry.progress.percent;
    return (
      <section
        aria-labelledby={titleId}
        data-testid="thread-run"
        data-compact="true"
        className="flex min-w-0 flex-1 items-center gap-3 text-sm"
      >
        <h2 id={titleId} className="shrink-0 font-medium text-text">
          {stopping ? "Stopping…" : "Running"}
        </h2>
        <span data-testid="run-step" className="min-w-0 truncate text-xs text-muted" title={text}>
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
          className="h-1.5 w-24 shrink-0 overflow-hidden rounded-full bg-hover"
        >
          <div
            className="h-full w-full origin-left rounded-full bg-accent-strong motion-safe:transition-transform motion-safe:duration-500 motion-safe:ease-out"
            style={{ transform: `scaleX(${(percent ?? 0) / 100})` }}
          />
        </div>
        {percent !== null && (
          <span data-testid="run-percent" className="shrink-0 text-xs tabular-nums text-muted">
            {percent}%
          </span>
        )}
        {stop}
      </section>
    );
  }
  return (
    <section
      aria-labelledby={titleId}
      data-testid="thread-run"
      className="flex flex-col gap-2 rounded-paper border border-border bg-surface p-4"
    >
      <h2 id={titleId} className="text-sm font-medium text-text">
        {stopping ? "Stopping…" : "Running"}
      </h2>
      <RunProgressBar entry={entry} />
      {stop}
    </section>
  );
}
