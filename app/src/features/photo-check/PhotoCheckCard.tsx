/**
 * The photo check card (PRD D17, R15.1). Exactly: the thumbnail strip (drag to reorder, ⟳ rotate
 * 90°, ✕ delete, + add, 🔑 key page, expand to full size; double-click also opens it), the key-page
 * hint, the optional **Existing test** search, **Date taken** (step 22.5.5b, default today) and **Run**.
 * No other fields. It is controlled: the owner keeps the `PhotoCheckDraft` and sends
 * `toExtractInput(draft)` on Run.
 *
 * Reorder uses native HTML5 drag and drop; the dragged index is kept in a ref, so a thumbnail
 * drag never looks like a file drop (the conversation drop zone checks `types` for "Files").
 */
import { useCallback, useId, useRef, useState } from "react";
import type { ApiClient } from "@/api/client";
import { todayIso } from "@/lib/skills";
import { ExistingTestSearch, STACKED_LABEL } from "./ExistingTestSearch";
import { SeriesSearch } from "./SeriesSearch";
import { PhotoFullView } from "./PhotoFullView";
import { isTextPage, movePage, rotateClockwise, type PageInput, type PhotoCheckDraft } from "./draft";

export { ACCEPTED_FILES } from "./upload";
import { ACCEPTED_FILES } from "./upload";

export interface PhotoCheckCardProps {
  api: ApiClient;
  draft: PhotoCheckDraft;
  onChange: (draft: PhotoCheckDraft) => void;
  onAddFiles: (files: File[]) => void;
  onRun: () => void;
  /** Uploading or submitting: the controls are disabled. */
  busy?: boolean;
  /** A line under the strip (upload refused, Run failed). */
  error?: string | null;
}

const tileButton =
  "flex h-6 w-6 items-center justify-center rounded-button bg-surface/90 text-xs text-text shadow-sm hover:bg-hover disabled:opacity-50";

export function PhotoCheckCard({ api, draft, onChange, onAddFiles, onRun, busy, error }: PhotoCheckCardProps) {
  const dragFrom = useRef<number | null>(null);
  const [over, setOver] = useState<number | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const strip = useRef<HTMLOListElement>(null);
  const [full, setFull] = useState<number | null>(null);
  const { pages } = draft;
  const dateId = useId();
  const closeFull = useCallback((last: number) => {
    setFull(null);
    // Focus goes back to the photo that was shown last (its expand button).
    requestAnimationFrame(() =>
      strip.current?.querySelectorAll<HTMLElement>('[data-testid="photo-expand"]')[last]?.focus(),
    );
  }, []);

  const setPages = (next: PageInput[]) => onChange({ ...draft, pages: next });
  const update = (i: number, patch: Partial<PageInput>) =>
    setPages(pages.map((p, j) => (j === i ? { ...p, ...patch } : p)));

  return (
    <section
      aria-label="Photo check"
      data-testid="photo-check-card"
      className="flex flex-col gap-3 rounded-paper border border-border bg-surface p-4 shadow-sm"
    >
      <h2 className="font-serif text-base text-text">Photo check</h2>
      <ol ref={strip} className="flex flex-wrap gap-3" data-testid="photo-strip" aria-label="Pages">
        {pages.map((page, i) => (
          <li
            key={`${page.file_id}-${i}`}
            data-testid="photo-thumb"
            data-file-id={page.file_id}
            data-rotation={page.rotation}
            data-key={page.is_key ? "true" : "false"}
            draggable={!busy}
            onDragStart={(e) => {
              dragFrom.current = i;
              e.dataTransfer?.setData("text/plain", String(i));
              if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
            }}
            onDragOver={(e) => {
              if (dragFrom.current === null) return;
              e.preventDefault();
              setOver(i);
            }}
            onDragLeave={() => setOver((o) => (o === i ? null : o))}
            onDrop={(e) => {
              if (dragFrom.current === null) return;
              e.preventDefault();
              e.stopPropagation();
              setPages(movePage(pages, dragFrom.current, i));
              dragFrom.current = null;
              setOver(null);
            }}
            onDragEnd={() => {
              dragFrom.current = null;
              setOver(null);
            }}
            onDoubleClick={(e) => {
              if ((e.target as HTMLElement).closest("button")) return;
              setFull(i);
            }}
            className={
              "relative flex h-36 w-28 cursor-grab flex-col items-center justify-center overflow-hidden rounded-paper border bg-panel " +
              (page.is_key ? "border-accent-strong " : "border-border ") +
              (over === i ? "outline-2 outline-focus" : "")
            }
          >
            <Thumb api={api} page={page} index={i} />
            <span className="absolute bottom-1 left-1 rounded-full bg-surface/90 px-1 text-xs text-muted">
              {i + 1}
            </span>
            <div className="absolute top-1 left-1">
              <button
                type="button"
                className={tileButton}
                onClick={() => setFull(i)}
                data-testid="photo-expand"
                aria-label={`Show page ${i + 1} full size`}
                title="Full size (or double-click the photo)"
              >
                <ExpandIcon />
              </button>
            </div>
            <div className="absolute top-1 right-1 flex gap-1">
              <button
                type="button"
                className={tileButton}
                disabled={busy}
                onClick={() => update(i, { is_key: !page.is_key })}
                aria-label={`Key page ${i + 1}`}
                aria-pressed={page.is_key}
                title="Key page (đáp án)"
              >
                <span className={page.is_key ? "" : "opacity-40 grayscale"}>🔑</span>
              </button>
              <button
                type="button"
                className={tileButton}
                disabled={busy}
                onClick={() => update(i, { rotation: rotateClockwise(page.rotation) })}
                aria-label={`Rotate page ${i + 1} 90°`}
                data-testid="photo-rotate"
                title="Rotate 90°"
              >
                <RotateQuarterIcon />
              </button>
              <button
                type="button"
                className={tileButton}
                disabled={busy}
                onClick={() => setPages(pages.filter((_, j) => j !== i))}
                aria-label={`Delete page ${i + 1}`}
                title="Delete"
              >
                ×
              </button>
            </div>
          </li>
        ))}
        <li className="flex h-36 w-28">
          <button
            type="button"
            disabled={busy}
            onClick={() => fileInput.current?.click()}
            aria-label="Add pages"
            data-testid="photo-add"
            className="flex flex-1 items-center justify-center rounded-button border border-dashed border-border text-2xl text-muted hover:bg-hover hover:text-text"
          >
            +
          </button>
          <input
            ref={fileInput}
            type="file"
            multiple
            hidden
            accept={ACCEPTED_FILES}
            data-testid="photo-add-input"
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              e.target.value = "";
              if (files.length) onAddFiles(files);
            }}
          />
        </li>
      </ol>
      <p className="text-sm text-muted" data-testid="key-hint">
        Mark each page of the key with 🔑 Key. Double-click a photo to see it full size.
      </p>
      {full !== null && pages.length > 0 && (
        <PhotoFullView api={api} pages={pages} index={full} onClose={closeFull} />
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <div className="flex items-end gap-3">
        <div className="flex-1">
          <ExistingTestSearch
            api={api}
            value={draft.existingTest}
            disabled={busy}
            labelClassName={STACKED_LABEL}
            onChange={(existingTest) => onChange({ ...draft, existingTest })}
          />
          {/* With a picked test the bank test keeps its own details, so the series pick hides. */}
          {!draft.existingTest && (
            <div className="mt-2">
              <SeriesSearch
                api={api}
                value={draft.seriesName ?? null}
                disabled={busy}
                labelClassName={STACKED_LABEL}
                onChange={(seriesName) => onChange({ ...draft, seriesName })}
              />
            </div>
          )}
          {/* Step 22.5.5b (D11a): when the student took the paper; it orders the weak points over time. */}
          <div className="mt-2 flex items-center gap-2 text-sm">
            <label htmlFor={dateId} className={`text-muted ${STACKED_LABEL}`}>
              Date taken
            </label>
            <input
              id={dateId}
              type="date"
              data-testid="photo-taken-on"
              required
              max={todayIso()}
              value={draft.takenOn || todayIso()}
              disabled={busy}
              onChange={(e) => onChange({ ...draft, takenOn: e.target.value || undefined })}
              className="rounded-paper border border-input bg-surface px-2 py-1 text-text disabled:opacity-50"
            />
          </div>
        </div>
        <button
          type="button"
          onClick={onRun}
          disabled={busy || pages.length === 0}
          data-testid="photo-run"
          title="Run (Ctrl+Enter)"
          className="rounded-button bg-accent px-4 py-1.5 text-sm text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover disabled:opacity-50"
        >
          Run
        </button>
      </div>
    </section>
  );
}

function Thumb({ api, page, index }: { api: ApiClient; page: PageInput; index: number }) {
  const [broken, setBroken] = useState(false);
  if (isTextPage(page)) {
    return (
      <div data-testid="text-page" className="flex flex-col items-center gap-1 px-2 text-center text-xs text-muted">
        <span aria-hidden className="text-2xl">¶</span>
        Text page
      </div>
    );
  }
  if (broken) {
    return (
      <div data-testid="broken-page" className="px-2 text-center text-xs text-muted">
        Page missing. Delete it with ×.
      </div>
    );
  }
  return (
    <img
      src={api.fileUrl(page.file_id, { thumb: true })}
      alt={`Page ${index + 1}`}
      draggable={false}
      onError={() => setBroken(true)}
      style={{ transform: `rotate(${page.rotation}deg)` }}
      className="max-h-32 max-w-26 object-contain transition-transform"
    />
  );
}

/** A quarter-turn arc with an arrow head (step 22.3.1, comment 4): not a full circle, so it does not read as reload. */
function RotateQuarterIcon() {
  return (
    <svg
      data-testid="rotate-quarter-icon"
      aria-hidden
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 13 A 10 10 0 0 1 13 3" />
      <path d="M10 1.5 L13 3 L11.2 5.8" />
    </svg>
  );
}

/** Four corner marks: open full size. */
function ExpandIcon() {
  return (
    <svg
      aria-hidden
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4" />
    </svg>
  );
}
