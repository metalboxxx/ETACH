/** The in-app toast for a finished run when there is no OS notification (browser). */
import type { Toast } from "./useRunNotifications";

export function Toasts({ toasts, onDismiss }: { toasts: readonly Toast[]; onDismiss: (id: string) => void }) {
  if (!toasts.length) return null;
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2" aria-live="polite">
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          data-testid="toast"
          data-kind={t.kind}
          className="flex min-w-60 items-start justify-between gap-3 rounded-paper border border-border bg-surface p-3 text-sm shadow"
        >
          <div className="flex flex-col">
            <span className="font-medium text-text">{t.title}</span>
            <span className={t.kind === "failed" ? "text-danger" : "text-muted"}>{t.body}</span>
          </div>
          <button type="button" aria-label="Dismiss" className="text-muted hover:text-text" onClick={() => onDismiss(t.id)}>
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
