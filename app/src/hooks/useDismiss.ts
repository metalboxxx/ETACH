/**
 * Closes a popover (a menu, a picker) the way the teacher expects (step 22.1.1, comment 4):
 * a pointer-down outside `ref` or `Escape` calls `onDismiss` with the reason; clicks inside `ref`
 * do not. On "escape" the caller usually returns focus to the control that opened the popover.
 * Focus moving outside `ref` (Tab out of it; step 22.1.4) dismisses it too, with reason "outside",
 * so focus stays where the teacher moved it.
 *
 * `Escape` is marked handled (`preventDefault`), so the global shortcut (`useShortcuts`, Esc
 * closes the artifact panel) leaves the panel open: one Escape closes one thing.
 */
import { useEffect, useRef, type RefObject } from "react";

export type DismissReason = "outside" | "escape";

export function useDismiss(
  ref: RefObject<HTMLElement | null>,
  open: boolean,
  onDismiss: (reason: DismissReason) => void,
): void {
  const latest = useRef(onDismiss);
  useEffect(() => {
    latest.current = onDismiss;
  });

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: Event) => {
      const root = ref.current;
      if (root && e.target instanceof Node && root.contains(e.target)) return;
      latest.current("outside");
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented) return;
      e.preventDefault();
      latest.current("escape");
    };
    const onFocusIn = (e: FocusEvent) => {
      const root = ref.current;
      if (!root || !(e.target instanceof Node) || root.contains(e.target)) return;
      latest.current("outside");
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("focusin", onFocusIn);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("focusin", onFocusIn);
    };
  }, [open, ref]);
}
