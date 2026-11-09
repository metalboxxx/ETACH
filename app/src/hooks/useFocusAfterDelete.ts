/**
 * Keeps keyboard focus in a list after a row is deleted (WCAG 2.4.3, step 22.2 F3). Call `mark(id)`
 * when "Delete…" is chosen. When a later `ids` no longer holds that row and focus fell to the page
 * body (the row's ⋯ button was removed), `focus` gets the row now at the deleted one's place (the
 * next row, or the last one), or `null` when the list is empty. A list that still holds the row
 * (Cancel, a failed delete) keeps the mark;
 * marking another row replaces it.
 */
import { useCallback, useEffect, useRef } from "react";

export function useFocusAfterDelete(
  ids: readonly string[] | null,
  focus: (id: string | null) => void,
): (id: string) => void {
  const pending = useRef<{ id: string; index: number } | null>(null);
  const latest = useRef({ ids, focus });
  useEffect(() => {
    latest.current = { ids, focus };
  });
  useEffect(() => {
    const p = pending.current;
    if (!p || !ids) return;
    if (ids.includes(p.id)) return;
    pending.current = null;
    const active = document.activeElement;
    if (active && active !== document.body) return;
    latest.current.focus(ids[Math.min(p.index, ids.length - 1)] ?? null);
  }, [ids]);
  return useCallback((id: string) => {
    pending.current = { id, index: Math.max(0, latest.current.ids?.indexOf(id) ?? 0) };
  }, []);
}
