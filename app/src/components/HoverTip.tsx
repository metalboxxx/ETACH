/**
 * A label with a detail shown on hover or keyboard focus (step 22.5.5b), after the "Keys changed"
 * tooltip of step 22.4.8: the label takes keyboard focus (dotted underline), hovering or focusing
 * it shows the tip, Esc hides it, and the tip is the label's accessible description
 * (`aria-describedby`). The tip stays in the DOM while hidden, so other controls (a model picker)
 * can name it in their own `aria-describedby` too.
 */
import { useId, useState, type ReactNode } from "react";

export interface HoverTipProps {
  /** The visible label. */
  children: ReactNode;
  /** The detail. */
  tip: ReactNode;
  /** The tip's id (default: a generated one). */
  tipId?: string;
  testId?: string;
  tipTestId?: string;
  /** Classes for the label. */
  className?: string;
  /** Tip width class (default `w-72`). */
  width?: string;
  /** Open the tip to the right edge instead of the left (for labels near the right side). */
  alignEnd?: boolean;
}

export function HoverTip({ children, tip, tipId, testId, tipTestId, className = "", width = "w-72", alignEnd = false }: HoverTipProps) {
  const generated = useId();
  const id = tipId ?? generated;
  const [open, setOpen] = useState(false);
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      onKeyDown={(e) => {
        if (e.key === "Escape" && open) {
          e.stopPropagation();
          setOpen(false);
        }
      }}
    >
      <span
        tabIndex={0}
        data-testid={testId}
        aria-describedby={id}
        className={
          "cursor-help rounded-paper underline decoration-dotted underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus " +
          className
        }
      >
        {children}
      </span>
      <span
        id={id}
        role="tooltip"
        data-testid={tipTestId}
        data-open={open ? "true" : "false"}
        className={
          "absolute top-full z-20 mt-1 max-w-[80vw] rounded-paper border border-border bg-surface px-3 py-2 text-left text-xs font-normal text-text normal-case shadow-sm " +
          `${width} ${alignEnd ? "right-0" : "left-0"} ` +
          (open ? "visible" : "invisible")
        }
      >
        {tip}
      </span>
    </span>
  );
}
