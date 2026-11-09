/**
 * The photo viewer on the right of a workspace (PRD §10, v4.13; step 22.1.4, comments 3, 12, 14).
 *
 * One page at a time: "Page n of N", previous / next (buttons, and ← / → anywhere in the
 * workspace unless the teacher is typing in a field), a numbered page strip (key photos read
 * "Key 1", …), and zoom: Fit, then larger steps that keep the whole page reachable by scrolling.
 *
 * The stored page already carries the photo check's rotation (see `photos.ts`), so the image is
 * shown as stored. A page without an image is said in words: a text-only page (DOCX or PDF text)
 * shows its text; a photo that is no longer stored says so.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { ApiClient } from "@/api/client";
import { isEditable } from "@/hooks/useShortcuts";
import { photoName, type PhotoPage } from "./photos";

/** Zoom steps; 1 is "fit the page to the viewer". */
export const ZOOMS = [1, 1.5, 2, 3, 4] as const;

const control =
  "inline-flex min-h-8 min-w-8 items-center justify-center rounded-button border border-border px-2 text-sm text-text hover:bg-hover disabled:opacity-50 disabled:hover:bg-transparent focus-visible:outline-2 focus-visible:outline-focus";

export interface PhotoViewerProps {
  api: ApiClient;
  /** `null` while loading. */
  pages: readonly PhotoPage[] | null;
  /** 1-based index in `pages` to start at (e.g. a thumbnail on the card). */
  initialIndex?: number;
  /** What the photos belong to, for the empty state ("this test", "these answers"). */
  owner: string;
  /** A load error, said in words instead of the photos. */
  error?: string | null;
  /** Controls before the page controls (the Key workspace's Photos / Test text switch). */
  toolbarStart?: ReactNode;
  /** `false` while hidden (the Key shows the test text): ← / → do nothing. */
  active?: boolean;
}

function keyFromArrows(e: KeyboardEvent): -1 | 1 | 0 {
  if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return 0;
  if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return 0;
  const el = document.activeElement;
  // Typing in a field (or choosing in a list) keeps its own arrow keys.
  if (isEditable(el) || el instanceof HTMLSelectElement) return 0;
  if (el instanceof HTMLElement && el.closest('[role="slider"], [role="listbox"], [role="menu"], [role="tablist"]')) return 0;
  return e.key === "ArrowLeft" ? -1 : 1;
}

export function PhotoViewer({
  api,
  pages,
  initialIndex = 1,
  owner,
  error = null,
  toolbarStart,
  active = true,
}: PhotoViewerProps) {
  const count = pages?.length ?? 0;
  const [index, setIndex] = useState(() => Math.max(0, initialIndex - 1));
  const [zoom, setZoom] = useState(0); // index into ZOOMS
  const current = pages && count ? pages[Math.min(index, count - 1)]! : null;
  const shown = current ? Math.min(index, count - 1) : 0;
  const stage = useRef<HTMLDivElement>(null);

  const go = (to: number) => {
    if (!count) return;
    const next = Math.max(0, Math.min(count - 1, to));
    setIndex(next);
    stage.current?.scrollTo?.({ top: 0, left: 0 });
  };

  // ← / → turn the page, unless focus is in a field (step 22.1.4: never while typing).
  const step = useRef<(d: -1 | 1) => void>(() => {});
  useEffect(() => {
    step.current = (d) => go(shown + d);
  });
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      const d = keyFromArrows(e);
      if (!d) return;
      e.preventDefault();
      step.current(d);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active]);

  const z = ZOOMS[zoom]!;
  return (
    <div data-testid="photo-viewer" className="flex min-h-0 flex-1 flex-col">
      <div
        data-testid="photo-toolbar"
        className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border bg-panel px-3 py-2"
      >
        {toolbarStart}
        <div className="flex items-center gap-1" role="group" aria-label="Turn pages">
          <button
            type="button"
            data-testid="photo-prev"
            className={control}
            aria-label="Previous page"
            title="Previous page (←)"
            disabled={!count || shown === 0}
            onClick={() => go(shown - 1)}
          >
            <span aria-hidden="true" className="text-lg leading-none">‹</span>
          </button>
          <p data-testid="photo-status" aria-live="polite" className="min-w-24 px-1 text-center text-sm text-text">
            {count ? (
              <>
                Page {shown + 1} of {count}
                {current?.isKey && (
                  <span data-testid="photo-key-badge" className="ml-1.5 rounded-full border border-accent-strong px-1 text-xs text-accent-strong">
                    Key
                  </span>
                )}
              </>
            ) : (
              <span className="text-muted">No pages</span>
            )}
          </p>
          <button
            type="button"
            data-testid="photo-next"
            className={control}
            aria-label="Next page"
            title="Next page (→)"
            disabled={!count || shown >= count - 1}
            onClick={() => go(shown + 1)}
          >
            <span aria-hidden="true" className="text-lg leading-none">›</span>
          </button>
        </div>
        {count > 1 && pages && (
        <nav aria-label="Page list" className="flex flex-wrap gap-1">
          {pages.map((p, i) => (
            <button
              key={p.key}
              type="button"
              data-testid="photo-page"
              data-key={p.isKey || undefined}
              aria-label={photoName(p)}
              aria-current={i === shown ? "page" : undefined}
              onClick={() => go(i)}
              className={
                "min-h-7 min-w-7 rounded-button px-1.5 text-xs focus-visible:outline-2 focus-visible:outline-focus " +
                (i === shown
                  ? "border border-accent-strong bg-surface font-semibold text-accent-strong"
                  : "border border-transparent text-muted hover:bg-hover hover:text-text")
              }
            >
              {p.isKey ? `Key ${p.pageNo}` : p.pageNo}
            </button>
          ))}
        </nav>
      )}
        <div className="ml-auto flex items-center gap-1" role="group" aria-label="Zoom">
          <button
            type="button"
            data-testid="photo-zoom-out"
            className={control}
            aria-label="Smaller"
            title="Smaller"
            disabled={!current || zoom === 0}
            onClick={() => setZoom((n) => Math.max(0, n - 1))}
          >
            <span aria-hidden="true" className="text-lg leading-none">−</span>
          </button>
          <button
            type="button"
            data-testid="photo-zoom-fit"
            className={control + " min-w-14"}
            aria-label={zoom === 0 ? "Fit page (now fitted)" : `Fit page (now ${z * 100}%)`}
            title="Fit the page to the viewer"
            disabled={!current}
            onClick={() => setZoom(0)}
          >
            {zoom === 0 ? "Fit" : `${z * 100}%`}
          </button>
          <button
            type="button"
            data-testid="photo-zoom-in"
            className={control}
            aria-label="Larger"
            title="Larger"
            disabled={!current || zoom === ZOOMS.length - 1}
            onClick={() => setZoom((n) => Math.min(ZOOMS.length - 1, n + 1))}
          >
            <span aria-hidden="true" className="text-lg leading-none">+</span>
          </button>
        </div>
      </div>
      <div
        ref={stage}
        data-testid="photo-stage"
        data-zoom={z}
        className="relative min-h-0 flex-1 overflow-auto bg-sidebar"
      >
        {error ? (
          <Note role="alert">Could not load the photos: {error}</Note>
        ) : pages === null ? (
          <Note>Loading the photos…</Note>
        ) : !current ? (
          <Note data-testid="photo-empty">No photos stored for {owner}.</Note>
        ) : (
          <div
            className="absolute left-0 top-0 flex items-center justify-center p-3"
            style={{ width: `${z * 100}%`, height: `${z * 100}%` }}
          >
            <PageImage key={current.key} api={api} page={current} />
          </div>
        )}
      </div>
    </div>
  );
}

function Note({ children, ...rest }: { children: ReactNode; role?: string; "data-testid"?: string }) {
  return (
    <p {...rest} className="p-6 text-center text-sm text-muted">
      {children}
    </p>
  );
}

type ImageState = { kind: "image" } | { kind: "text"; text: string } | { kind: "missing" };

/** One stored page: its image, or its text (a text-only page), or a note that it is gone. */
function PageImage({ api, page }: { api: ApiClient; page: PhotoPage }) {
  const [state, setState] = useState<ImageState>({ kind: "image" });
  const name = photoName(page);

  const onError = () => {
    api
      .fileText(page.fileId)
      .then(({ text }) => setState(text !== null ? { kind: "text", text } : { kind: "missing" }))
      .catch(() => setState({ kind: "missing" }));
  };

  if (state.kind === "text") {
    return (
      <div data-testid="photo-text-page" className="flex h-full w-full flex-col gap-2 overflow-auto rounded-paper border border-border bg-surface p-4 text-sm text-text">
        <p className="text-muted">
          {name} has no photo: it came from a typed file (Word or PDF). Here is its text.
        </p>
        <p className="whitespace-pre-wrap font-serif">{state.text}</p>
      </div>
    );
  }
  if (state.kind === "missing") {
    return (
      <p data-testid="photo-missing" className="text-center text-sm text-muted">
        The photo of {name.toLowerCase()} is no longer stored.
      </p>
    );
  }
  return (
    <img
      data-testid="photo-image"
      data-file-id={page.fileId}
      data-rotation={page.rotation ?? undefined}
      src={api.fileUrl(page.fileId)}
      alt={`${name}, original photo`}
      draggable={false}
      onError={onError}
      className="h-full w-full rounded-paper object-contain"
    />
  );
}
