/**
 * "Keys changed" (PRD v8.1, step 22.4.5, comment 12 / D4): the thread's test has key changes not
 * re-graded yet. Re-grade starts the one re-grade now; while a run goes it is disabled (Stop is in
 * the run's own bar). Leaving the Key tab starts it too (`useKeyRegrade`).
 *
 * The message sits in a polite live region, so a screen reader hears it when the keys change or
 * the re-grade starts; focus is never moved. On the Key tab (`compact`) it shares one line with
 * the run's bar.
 *
 * Step 22.4.8 (teacher, after the build): in the compact form the hint is a tooltip. "Keys changed"
 * takes keyboard focus; hovering or focusing it (or Re-grade) shows the hint, Esc hides it, and
 * both carry it as their accessible description (`aria-describedby`).
 */
import { useId, useState } from "react";

/** What leaving or re-grading does (the full bar's text, the compact bar's tooltip). */
export const KEYS_CHANGED_HINT = "The scores update when you re-grade, leave the Key tab or leave this thread.";
export interface KeysChangedBarProps {
  /** A run goes on this thread: Re-grade is disabled. */
  running: boolean;
  onRegrade: () => void;
  error?: string | null;
  compact?: boolean;
}

export function KeysChangedBar({ running, onRegrade, error, compact = false }: KeysChangedBarProps) {
  const hintId = useId();
  const [tip, setTip] = useState(false);
  const described = compact ? hintId : undefined;
  return (
    <div
      data-testid="keys-changed"
      className={
        "flex min-w-0 items-center gap-3 text-sm " +
        (compact ? "relative shrink-0" : "flex-wrap rounded-paper border border-border bg-surface px-4 py-2")
      }
      onMouseEnter={compact ? () => setTip(true) : undefined}
      onMouseLeave={compact ? () => setTip(false) : undefined}
      onFocus={compact ? () => setTip(true) : undefined}
      onBlur={compact ? () => setTip(false) : undefined}
      onKeyDown={
        compact
          ? (e) => {
              if (e.key === "Escape" && tip) {
                e.stopPropagation();
                setTip(false);
              }
            }
          : undefined
      }
    >
      <p role="status" aria-live="polite" className="text-text">
        {compact ? (
          <span
            tabIndex={0}
            data-testid="keys-changed-label"
            aria-describedby={described}
            className="cursor-help rounded-paper font-medium underline decoration-dotted underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Keys changed
          </span>
        ) : (
          <span className="font-medium">Keys changed</span>
        )}
        {!compact && <span className="text-muted"> · {KEYS_CHANGED_HINT}</span>}
      </p>
      {compact && (
        <span
          id={hintId}
          role="tooltip"
          data-testid="keys-changed-hint"
          data-open={tip ? "true" : "false"}
          className={
            "absolute top-full left-0 z-20 mt-1 w-72 rounded-paper border border-border bg-surface px-3 py-2 text-xs text-text shadow-sm " +
            (tip ? "visible" : "invisible")
          }
        >
          {KEYS_CHANGED_HINT}
        </span>
      )}
      <button
        type="button"
        aria-describedby={described}
        data-testid="keys-regrade"
        onClick={onRegrade}
        disabled={running}
        aria-disabled={running || undefined}
        title={running ? "Wait for the run to finish, or stop it" : undefined}
        className="shrink-0 rounded-button border border-accent-strong bg-accent px-3 py-1 text-sm font-medium text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-60"
      >
        Re-grade
      </button>
      {error && (
        <span role="alert" className="text-danger">
          {error}
        </span>
      )}
    </div>
  );
}
