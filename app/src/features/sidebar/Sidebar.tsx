/**
 * The sidebar (PRD §10.1). Its items, in this order: New thread · running indicator slot ·
 * Chats | Tests | Students · Settings (Students: step 22.2.3). The Review item is gone (PRD D27, step 22.1.5): the thread and test lists
 * mark what still has unsure spots instead.
 * Step 15 fills the running slot and lists the threads under the switch. Step 20 adds the
 * other-Ollama warning above the list (outside `sidebar-items`, so R13.1 still holds).
 */
import type { ReactNode } from "react";
import { GearIcon } from "@/components/GearIcon";
import { OtherOllamaWarning } from "@/components/OtherOllamaWarning";
import { NEW_THREAD_TESTID } from "@/features/threads/threads";

export type SidebarTab = "chats" | "tests" | "students";

const TAB_LABELS: Record<SidebarTab, string> = { chats: "Chats", tests: "Tests", students: "Students" };

export interface SidebarProps {
  tab: SidebarTab;
  onTabChange: (tab: SidebarTab) => void;
  onNewThread: () => void;
  onOpenSettings: () => void;
  /** The running indicator (step 15). Empty in the skeleton. */
  running?: ReactNode;
  /** The thread / test list under the switch (steps 15–16). */
  children?: ReactNode;
  /** `other_ollama_loaded` from `GET /system/status` (R20.4): a warning above the items. */
  otherOllama?: boolean;
}

const itemButton =
  "flex w-full items-center gap-2 rounded-button px-3 py-2 text-left text-sm text-text hover:bg-hover focus-visible:outline-2 focus-visible:outline-focus";

/** Every sidebar control shows the app's blue focus outline (PRD §10.1 v8.21). */
export const SIDEBAR_FOCUS = "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus";

export function Sidebar({
  tab,
  onTabChange,
  onNewThread,
  onOpenSettings,
  running,
  children,
  otherOllama = false,
}: SidebarProps) {
  return (
    <nav
      aria-label="Sidebar"
      className="no-print flex h-full w-64 shrink-0 flex-col border-r border-border bg-sidebar px-2 py-3"
    >
      {/* The wordmark (PRD §10.1 v8.18): ETACH in Federo, the full name under it, bold and
          centred, and a short rule underneath, like the motto line of an official document. */}
      <div className="flex flex-col items-center px-3 pb-3 text-center" data-testid="wordmark">
        <span
          data-testid="wordmark-name"
          className="wordmark-gradient inline-block whitespace-nowrap font-wordmark text-[56px] leading-none"
        >
          ETACH
        </span>
        <span data-testid="wordmark-line" className="mt-1 whitespace-nowrap font-serif text-[11px] font-semibold text-text">
          English Test Assistant - Curate &amp; Help
        </span>
        <span aria-hidden="true" className="mt-1.5 h-px w-16 bg-text" />
      </div>
      {otherOllama && (
        <div className="px-1 pb-2">
          <OtherOllamaWarning testId="sidebar-ollama-warning" compact />
        </div>
      )}
      <ul className="flex flex-1 flex-col gap-1" data-testid="sidebar-items">
        <li data-item="new-thread">
          <button
            type="button"
            data-testid={NEW_THREAD_TESTID}
            className={itemButton /* the simple row again (PRD §10.1 v8.23): no fill, a soft hover */}
            onClick={onNewThread}
            title="New thread (Ctrl+N)"
          >
            <span aria-hidden className="text-accent-strong">
              +
            </span>
            New thread
          </button>
        </li>
        <li data-item="running" data-testid="running-slot" aria-label="Running" className="empty:hidden">
          {running}
        </li>
        <li data-item="tabs" className="flex flex-1 flex-col">
          {/* Folder tabs (PRD §10.1 v8.21): three tabs with white lines between them; the selected
              tab is white and opens into the white page below it (it overlaps the page's top edge,
              so there is no line or gap); the others stay on the sidebar grey, tinted on hover. */}
          <div role="tablist" aria-label="Chats, tests or students" className="relative z-10 mx-1 mt-1 flex items-start divide-x-2 divide-surface">
            {(["chats", "tests", "students"] as const).map((t) => (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={tab === t}
                onClick={() => onTabChange(t)}
                className={
                  "flex-1 px-3 pt-1 text-sm " +
                  SIDEBAR_FOCUS +
                  " " +
                  (tab === t
                    ? "-mb-1 rounded-t-paper bg-surface pb-2 text-text shadow-tab"
                    : "pb-1 text-muted hover:bg-tint hover:text-text")
                }
              >
                {TAB_LABELS[t]}
              </button>
            ))}
          </div>
          {/* The page: white, 2 px corners and the page shadow, running down through Settings (the
              shadow is clipped where the two parts meet, so they read as one sheet). */}
          <div
            data-testid="sidebar-page"
            className="mx-1 flex-1 overflow-y-auto rounded-t-paper bg-surface px-2 py-2 text-sm text-muted shadow-page [clip-path:inset(-6px_-6px_0_-6px)]"
          >
            {children}
          </div>
        </li>
        <li data-item="settings" data-testid="sidebar-page-end" className="mx-1 -mt-1 rounded-b-paper bg-surface px-1 pb-1 shadow-page [clip-path:inset(0_-6px_-6px_-6px)]">
          <button type="button" data-testid="settings-row" className={itemButton.replace("hover:bg-hover", "hover:bg-tint") + " focus-visible:-outline-offset-2"} onClick={onOpenSettings}>
            <GearIcon />
            Settings
          </button>
        </li>
      </ul>
    </nav>
  );
}
