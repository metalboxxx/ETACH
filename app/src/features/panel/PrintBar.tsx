/**
 * The bar above a print view (step 22.1.1, comment 8): "Back to …" returns to the panel the
 * teacher came from, a note says how to leave the print window without closing the app, and
 * Print opens the print window again. The bar is `no-print`, so it never reaches the paper.
 */
export interface PrintBarProps {
  /** The panel's title ("Test", "Key", "Grade report"). */
  title: string;
  onBack: () => void;
  onPrint: () => void;
}

export function PrintBar({ title, onBack, onPrint }: PrintBarProps) {
  return (
    <header
      data-testid="print-bar"
      className="no-print flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border bg-panel px-4 py-3"
    >
      <button
        type="button"
        autoFocus
        data-testid="print-back"
        onClick={onBack}
        title="Back (Esc)"
        className="rounded-button border border-border px-3 py-1 text-sm text-text hover:bg-hover"
      >
        <span aria-hidden="true">← </span>
        Back to {title.toLowerCase()}
      </button>
      <div className="min-w-0 flex-1 text-sm">
        <h2 className="font-serif text-base text-text">Print preview: {title.toLowerCase()}</h2>
        <p className="text-muted">
          The print window opens over the app. To leave it without printing, press Cancel or Esc there; the
          window’s × closes the whole app.
        </p>
      </div>
      <button
        type="button"
        data-testid="print-again"
        onClick={onPrint}
        className="main-label rounded-button bg-accent px-3 py-1 text-sm text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover"
      >
        Print
      </button>
    </header>
  );
}
