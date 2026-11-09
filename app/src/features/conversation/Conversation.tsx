/**
 * The conversation area and its file drop zone. Images, PDF and DOCX dropped anywhere on it go to
 * `onFiles` (HTML5 drop events: the Tauri window has `dragDropEnabled: false`, so the WebView
 * delivers them as in a browser). Drags that carry no files (a thumbnail reorder) are ignored.
 * `empty` shows the start screen instead of the children.
 *
 * `hidden` (step 22.1.4): a workspace is open in its place. The conversation stays mounted, so its
 * state (unsent text, the photo check) survives; its scroll position is kept and put back when it
 * shows again. It can take focus (`tabIndex=-1`) as the fallback target after Back.
 */
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { ACCEPTED_FILES, dragHasFiles } from "@/features/photo-check/upload";

export interface ConversationProps {
  notice?: ReactNode;
  onFiles?: (files: File[]) => void;
  /** Show the empty state (default when there are no children). */
  empty?: boolean;
  /** A workspace is open in its place (step 22.1.4). */
  hidden?: boolean;
  children?: ReactNode;
}

export function Conversation({ notice, onFiles, empty, hidden = false, children }: ConversationProps) {
  const [dragging, setDragging] = useState(false);
  const depth = useRef(0);
  const showEmpty = empty ?? !children;
  // The scroll position while shown; put back when the conversation shows again.
  const scroller = useRef<HTMLDivElement>(null);
  const scrollTop = useRef(0);
  const picker = useRef<HTMLInputElement>(null);
  useLayoutEffect(() => {
    if (!hidden && scroller.current) scroller.current.scrollTop = scrollTop.current;
  }, [hidden]);

  const handlers = onFiles
    ? {
        onDragEnter: (e: React.DragEvent) => {
          if (!dragHasFiles(e.dataTransfer)) return;
          depth.current += 1;
          setDragging(true);
        },
        onDragLeave: (e: React.DragEvent) => {
          if (!dragHasFiles(e.dataTransfer)) return;
          depth.current = Math.max(0, depth.current - 1);
          if (depth.current === 0) setDragging(false);
        },
        onDragOver: (e: React.DragEvent) => {
          if (!dragHasFiles(e.dataTransfer)) return;
          e.preventDefault();
          e.dataTransfer.dropEffect = "copy";
        },
        onDrop: (e: React.DragEvent) => {
          depth.current = 0;
          setDragging(false);
          const files = Array.from(e.dataTransfer?.files ?? []);
          if (!files.length) return;
          e.preventDefault();
          onFiles(files);
        },
      }
    : {};

  return (
    <main
      className="no-print relative flex min-w-0 flex-1 flex-col bg-bg focus:outline-none"
      aria-label="Conversation"
      data-testid="conversation"
      hidden={hidden}
      tabIndex={-1}
      {...handlers}
    >
      {notice}
      {showEmpty ? (
        // The start screen (PRD §10.1 v8.25): a dotted box shaped like a portrait sheet of paper
        // (A4, 1 : 1.414) that reads as "drop the test here"; the instruction and Choose files sit
        // in its middle. The whole conversation area takes the drop; while files are dragged over
        // it the box's border turns blue and it takes the light tint (no separate overlay).
        <div className="flex min-h-0 flex-1 items-center justify-center p-6">
          <div
            data-testid="empty-state"
            data-dragging={dragging || undefined}
            className={
              "flex aspect-[1/1.414] h-[min(80vh,42rem)] max-h-full max-w-full flex-col items-center justify-center gap-2 rounded-paper border-2 border-dotted px-8 text-center transition-colors motion-reduce:transition-none " +
              (dragging ? "border-accent-strong bg-tint" : "border-input")
            }
          >
            <p className="max-w-sm text-sm text-muted">
              Drop or paste photos, a PDF or a Word file of a test to start a new thread.
            </p>
            {onFiles && (
              <>
                <button
                  type="button"
                  data-testid="choose-files"
                  onClick={() => picker.current?.click()}
                  className="mt-2 inline-flex min-h-9 items-center rounded-button border border-border bg-surface px-4 text-sm text-text hover:bg-hover focus-visible:outline-2 focus-visible:outline-focus"
                >
                  Choose files…
                </button>
                {/* Chosen files go to the same `onFiles` as dropped ones (R22.2.2.3). */}
                <input
                  ref={picker}
                  type="file"
                  multiple
                  hidden
                  accept={ACCEPTED_FILES}
                  data-testid="choose-files-input"
                  onChange={(e) => {
                    const files = Array.from(e.target.files ?? []);
                    e.target.value = "";
                    if (files.length) onFiles(files);
                  }}
                />
              </>
            )}
          </div>
        </div>
      ) : (
        <div
          ref={scroller}
          data-testid="conversation-scroll"
          className="flex-1 overflow-y-auto"
          onScroll={(e) => {
            if (!hidden) scrollTop.current = e.currentTarget.scrollTop;
          }}
        >
          {children}
        </div>
      )}
      {dragging && !showEmpty && (
        <div
          aria-hidden
          data-testid="drop-overlay"
          className="pointer-events-none absolute inset-2 flex items-center justify-center rounded-paper border-2 border-dashed border-accent-strong bg-bg/80 text-sm text-text"
        >
          Drop photos, a PDF or a Word file
        </div>
      )}
    </main>
  );
}
