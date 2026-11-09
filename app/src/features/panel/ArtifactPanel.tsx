/**
 * The artifact panel on the right (test, answers, grade, review; steps 16 and 19).
 * Hidden unless open; ✕ or Esc closes it.
 *
 * With `printBar` (step 22.1.1) it is a print view: it fills the window, the bar replaces the
 * chrome, and the content sits on a page-wide sheet (`print-page`, reset for paper in print.css).
 * The content keeps its place in the tree in both modes, so it is not reloaded when the print
 * view opens (the print window opens right after).
 */
import type { ReactNode } from "react";

export interface ArtifactPanelProps {
  open: boolean;
  title: string;
  onClose: () => void;
  /** Shows the panel as a print view under this bar (`PrintBar`). */
  printBar?: ReactNode;
  children?: ReactNode;
}

export function ArtifactPanel({ open, title, onClose, printBar, children }: ArtifactPanelProps) {
  if (!open) return null;
  const printView = printBar !== undefined && printBar !== null;
  return (
    <aside
      aria-label={printView ? `Print preview: ${title}` : title}
      data-testid="artifact-panel"
      className={
        printView
          ? "flex h-full min-w-0 flex-1 flex-col bg-bg"
          : "flex h-full w-[28rem] shrink-0 flex-col border-l border-border bg-panel"
      }
    >
      {printView ? (
        printBar
      ) : (
        <header
          data-testid="panel-chrome"
          className="no-print flex items-center justify-between border-b border-border px-4 py-3"
        >
          <h2 className="font-serif text-base text-text">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close panel"
            title="Close (Esc)"
            className="rounded-button px-2 py-1 text-muted hover:bg-hover hover:text-text"
          >
            ×
          </button>
        </header>
      )}
      <div className={"flex-1 overflow-y-auto text-sm text-text " + (printView ? "p-6" : "p-4")}>
        <div
          data-testid={printView ? "print-page" : undefined}
          className={
            printView ? "print-page mx-auto w-full max-w-3xl rounded-paper border border-border bg-surface p-8" : ""
          }
        >
          {children}
        </div>
      </div>
    </aside>
  );
}
