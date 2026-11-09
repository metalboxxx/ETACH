/**
 * The global keyboard shortcuts (PRD §10.1):
 *   Ctrl+N new thread · Ctrl+V paste photos · Ctrl+Enter Run / Grade · Ctrl+K search tests · Esc close panel.
 *
 * Esc while focus is in a text field only leaves the field (step 22.1.5).
 *
 * Ctrl+V listens to the `paste` event (only it can read the clipboard). It is taken over only when the
 * clipboard holds files, or when focus is not in an editable field, so a normal text paste into an input
 * still works. Ctrl+Enter also fires inside inputs (Run / Grade from the keyboard).
 */
import { useEffect, useRef } from "react";

export interface ShortcutHandlers {
  onNewThread?: () => void;
  onPastePhotos?: (files: File[]) => void;
  onRunOrGrade?: () => void;
  onSearchTests?: () => void;
  onClosePanel?: () => void;
}

export function isEditable(el: Element | null): boolean {
  if (!el || !(el instanceof HTMLElement)) return false;
  if (el.isContentEditable) return true;
  const tag = el.tagName;
  if (tag === "TEXTAREA") return true;
  if (tag === "INPUT") {
    const type = (el as HTMLInputElement).type;
    return !["button", "checkbox", "radio", "submit", "reset", "file", "range", "color"].includes(type);
  }
  return false;
}

function clipboardFiles(data: DataTransfer | null): File[] {
  if (!data) return [];
  const files = Array.from(data.files ?? []);
  if (files.length) return files;
  const out: File[] = [];
  for (const item of Array.from(data.items ?? [])) {
    if (item.kind === "file") {
      const f = item.getAsFile();
      if (f) out.push(f);
    }
  }
  return out;
}

export function useShortcuts(handlers: ShortcutHandlers, target: Window | Document = window): void {
  const ref = useRef(handlers);
  useEffect(() => {
    ref.current = handlers;
  });

  useEffect(() => {
    const onKeyDown = (e: Event) => {
      const ev = e as KeyboardEvent;
      if (ev.defaultPrevented || ev.isComposing) return;
      const h = ref.current;
      if (ev.key === "Escape" && !ev.ctrlKey && !ev.altKey && !ev.shiftKey && !ev.metaKey) {
        // Esc in a text field leaves the field first; it never closes the panel under the
        // teacher's typing (step 22.1.5). The next Esc closes the panel.
        const active = document.activeElement;
        if (isEditable(active)) {
          // Focus goes to the field's region (the workspace panel or the conversation), not to
          // the page body, so the next Tab or Esc starts from there (step 22.2.2).
          const region = (active as HTMLElement).closest<HTMLElement>(
            '[data-testid="artifact-panel"], [data-testid="conversation"]',
          );
          (active as HTMLElement).blur();
          region?.focus({ preventScroll: true });
          return;
        }
        if (h.onClosePanel) h.onClosePanel();
        return;
      }
      if (!ev.ctrlKey || ev.altKey || ev.shiftKey || ev.metaKey) return;
      const key = ev.key.toLowerCase();
      let fn: (() => void) | undefined;
      if (key === "n") fn = h.onNewThread;
      else if (key === "k") fn = h.onSearchTests;
      else if (key === "enter") fn = h.onRunOrGrade;
      if (!fn) return;
      ev.preventDefault();
      fn();
    };
    const onPaste = (e: Event) => {
      const ev = e as ClipboardEvent;
      const fn = ref.current.onPastePhotos;
      if (!fn || ev.defaultPrevented) return;
      const files = clipboardFiles(ev.clipboardData);
      if (!files.length && isEditable(document.activeElement)) return; // normal text paste
      if (files.length) ev.preventDefault();
      fn(files);
    };
    target.addEventListener("keydown", onKeyDown);
    target.addEventListener("paste", onPaste);
    return () => {
      target.removeEventListener("keydown", onKeyDown);
      target.removeEventListener("paste", onPaste);
    };
  }, [target]);
}
