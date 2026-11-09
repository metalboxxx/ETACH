/**
 * The window-close guard (PRD §10 v5.2, comment 6). The print window's only exit used to be the
 * app window's ✕, which closed the app; now a close request asks "Close ETACH?"
 * first, and names unsaved text when a panel has some (the leave checks, `leaveGuard.ts`).
 *
 * The shell side is Tauri's `onCloseRequested` on the main window: the request is held, and the
 * window is destroyed only after Close (capability `core:window:allow-destroy`). `listen` is
 * injectable so the page side is tested without Tauri; in a plain browser there is no listener.
 */
import { useEffect, useRef } from "react";
import { isTauri } from "@tauri-apps/api/core";
import type { ConfirmOptions } from "@/components/ConfirmDialog";

/** Asks whether to close; resolves true to close the window. */
export type CloseHandler = () => Promise<boolean>;
/** Subscribes `handler` to the window's close requests; returns the unsubscribe. */
export type CloseListener = (handler: CloseHandler) => () => void;

/** Loads the Tauri window API; injectable so a failed registration can be tested. */
export type WindowLoader = () => Promise<Pick<typeof import("@tauri-apps/api/window"), "getCurrentWindow">>;

/**
 * The Tauri main window's close requests. A registration that fails (no Tauri internals, or
 * `onCloseRequested` rejecting) is logged and ignored: the window then closes without asking,
 * and no promise is left unhandled.
 */
export function makeTauriCloseListener(
  load: WindowLoader = () => import("@tauri-apps/api/window"),
  inTauri: () => boolean = isTauri,
): CloseListener {
  return (handler) => {
    if (!inTauri()) return () => {};
    let off: (() => void) | null = null;
    let gone = false;
    load()
      .then(({ getCurrentWindow }) => {
        const win = getCurrentWindow();
        return win.onCloseRequested(async (event) => {
          event.preventDefault();
          if (await handler()) await win.destroy();
        });
      })
      .then((unlisten) => {
        if (gone) unlisten();
        else off = unlisten;
      })
      .catch((err: unknown) => {
        console.warn("Close guard not registered:", err);
      });
    return () => {
      gone = true;
      off?.();
    };
  };
}

/** The Tauri main window's close requests. */
export const tauriCloseListener: CloseListener = makeTauriCloseListener();

/** The dialog's text; `unsaved` says that typing would be lost. */
export function closeDialog(unsaved: boolean): ConfirmOptions {
  return {
    title: "Close ETACH?",
    body: unsaved ? <p>Your changes to the test text are not saved yet. Closing now loses them.</p> : undefined,
    confirmLabel: "Close",
    cancelLabel: "Cancel",
    tone: unsaved ? "danger" : "default",
  };
}

/** Asks before the window closes. `unsaved()` is read when the request comes. */
export function useCloseGuard(
  confirm: (opts: ConfirmOptions) => Promise<boolean>,
  unsaved: () => boolean,
  listen: CloseListener = tauriCloseListener,
): void {
  const latest = useRef({ confirm, unsaved });
  useEffect(() => {
    latest.current = { confirm, unsaved };
  });
  useEffect(() => listen(() => latest.current.confirm(closeDialog(latest.current.unsaved()))), [listen]);
}
