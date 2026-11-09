/**
 * "Later, after the basics (N)" (step 22.5.5b, D11e): weak skills above the lowest weak level wait
 * behind this line, closed at first. The line is a disclosure button (`aria-expanded`); the list
 * it opens follows it.
 */
import { useId, useState, type ReactNode } from "react";

export const LATER_LINE = "Later, after the basics";

export function LaterAfterBasics({ count, children, testId = "later-basics" }: { count: number; children: ReactNode; testId?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  if (count === 0) return null;
  return (
    <div data-testid={testId}>
      <button
        type="button"
        data-testid={`${testId}-toggle`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 rounded-button px-1 py-0.5 text-sm text-muted hover:bg-hover hover:text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      >
        <span aria-hidden className={"inline-block transition-transform motion-reduce:transition-none " + (open ? "rotate-90" : "")}>
          ›
        </span>
        {LATER_LINE} ({count})
      </button>
      <div id={id} hidden={!open} data-testid={`${testId}-list`}>
        {open && children}
      </div>
    </div>
  );
}
