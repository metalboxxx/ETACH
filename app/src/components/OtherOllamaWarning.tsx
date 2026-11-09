/**
 * The other-Ollama warning (PRD §11, R20.4): the teacher's own Ollama (tray app) has a model
 * loaded, which takes VRAM the app's models need. Shown in the sidebar and in Settings while
 * `GET /system/status` reports `other_ollama_loaded`.
 */
export function OtherOllamaWarning({ testId, compact = false }: { testId: string; compact?: boolean }) {
  return (
    <div
      role="status"
      data-testid={testId}
      className="rounded-paper border border-border bg-unsure/15 px-3 py-2 text-sm text-text"
    >
      <span aria-hidden className="mark-label">
        ⚠{" "}
      </span>
      {compact
        ? "Another Ollama has a model loaded: runs may be slow."
        : "Another Ollama (the tray app) has a model loaded. It uses video memory the app needs, so runs may be slow or fail. Quit it, or unload its model, before a run."}
    </div>
  );
}
