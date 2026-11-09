/**
 * The photo check's full-size view (step 22.3.1, comments 3 and 19): a modal dialog with one photo
 * at a time, shown with the rotation set on its thumbnail, so page order and key pages can be
 * checked before the run. Esc and Close close it; ← / → go through the photos; Tab stays inside
 * (the same pattern as `components/ConfirmDialog.tsx`). The owner returns focus to the photo.
 */
import { useEffect, useId, useRef, useState } from "react";
import type { ApiClient } from "@/api/client";
import { isTextPage, type PageInput } from "./draft";

const control =
  "inline-flex min-h-9 min-w-9 items-center justify-center rounded-button border border-border px-3 text-sm text-text hover:bg-hover disabled:opacity-50 disabled:hover:bg-transparent focus-visible:outline-2 focus-visible:outline-focus";

export interface PhotoFullViewProps {
  api: ApiClient;
  pages: readonly PageInput[];
  /** 0-based index of the photo to open on. */
  index: number;
  /** Closed with the index shown last, so focus can go back to that photo. */
  onClose: (index: number) => void;
}

export function PhotoFullView({ api, pages, index: start, onClose }: PhotoFullViewProps) {
  const ids = useId();
  const root = useRef<HTMLDivElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);
  const count = pages.length;
  const [index, setIndex] = useState(() => Math.max(0, Math.min(count - 1, start)));
  const page = pages[Math.min(index, count - 1)];
  const shown = useRef(index);
  useEffect(() => {
    shown.current = index;
  }, [index]);

  useEffect(() => {
    closeBtn.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose(shown.current);
      } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
        e.preventDefault();
        e.stopPropagation();
        const d = e.key === "ArrowLeft" ? -1 : 1;
        setIndex((i) => Math.max(0, Math.min(count - 1, i + d)));
      } else if (e.key === "Tab" && root.current) {
        const items = [...root.current.querySelectorAll<HTMLElement>("button:not([disabled])")];
        const first = items[0];
        const last = items[items.length - 1];
        if (!root.current.contains(document.activeElement)) {
          e.preventDefault();
          first?.focus();
        } else if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [count, onClose]);

  if (!page) return null;
  const quarter = page.rotation === 90 || page.rotation === 270;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg/90 p-4">
      <div
        ref={root}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${ids}-t`}
        data-testid="photo-full-view"
        data-index={index}
        className="flex h-full max-h-[calc(100vh-2rem)] w-full max-w-5xl flex-col gap-3 rounded-paper border border-border bg-panel p-4 text-sm text-text shadow-lg"
      >
        <div className="flex items-center gap-2">
          <h2 id={`${ids}-t`} className="flex-1 text-base font-semibold" aria-live="polite">
            Page {index + 1} of {count}
            {page.is_key ? " · Key" : ""}
          </h2>
          <button
            type="button"
            className={control}
            disabled={index === 0}
            onClick={() => setIndex((i) => Math.max(0, i - 1))}
            aria-label="Previous page"
            title="Previous page (←)"
          >
            <span aria-hidden>←</span>
          </button>
          <button
            type="button"
            className={control}
            disabled={index >= count - 1}
            onClick={() => setIndex((i) => Math.min(count - 1, i + 1))}
            aria-label="Next page"
            title="Next page (→)"
          >
            <span aria-hidden>→</span>
          </button>
          <button
            ref={closeBtn}
            type="button"
            className={control}
            onClick={() => onClose(index)}
            data-testid="photo-full-close"
            title="Close (Esc)"
          >
            Close
          </button>
        </div>
        <div className="flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded-paper bg-surface">
          {isTextPage(page) ? (
            <p className="text-muted">Text page: it has no photo to show.</p>
          ) : (
            <img
              key={page.file_id}
              src={api.fileUrl(page.file_id)}
              alt={`Page ${index + 1}`}
              data-testid="photo-full-img"
              data-rotation={page.rotation}
              style={{
                transform: `rotate(${page.rotation}deg)`,
                // A quarter-turned photo swaps width and height; keep it inside the frame.
                maxWidth: quarter ? "calc(100vh - 8rem)" : "100%",
              }}
              className="h-full w-full object-contain"
            />
          )}
        </div>
      </div>
    </div>
  );
}
