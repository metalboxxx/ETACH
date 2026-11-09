/**
 * The workspace view (PRD §10, v4.13; step 22.1.4, teacher's decision 3 = B). Opening Test, Key,
 * Answers or Report replaces the conversation:
 *
 *   │ Test · Key · …   (the tabs)                   │
 *   │ the title bar (`banner`)                      │
 *   │ the panel (read and edit) │ original photos   │
 *
 * The panel is on the left, where the teacher reads and edits; the original photos are on the
 * right, page by page with zoom (`PhotoViewer`). The Key workspace can switch its right side to
 * the test text (comment 15). Below 1024 px the two sides fold into one, with a toggle in the bar.
 *
 * No Back button (step 22.5.1, D1): the sidebar is the way out, and Esc still closes a workspace
 * the open thread does not own. A test opened from the Tests tab has the same header as a thread's
 * own test: the tabs, then a title bar with its name (`TestTitleBar` as the `banner`).
 *
 * Tabs (PRD §10 v5.2, comment 5): with `tabs`, the bar shows Test · Key · Student answers · Report
 * (`role="tablist"`, arrow keys move between tabs, Enter or Space opens one). A tab opens through
 * `onTab`, which asks first when there is unsaved text; the photos follow the open tab.
 *
 * With `printBar` it is the print view (step 22.1.1): the bar replaces the workspace bar, the
 * photos go away and the panel fills the window on a page-wide sheet. The panel content keeps its
 * place in the tree in both modes, so it is not reloaded.
 */
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { ApiClient } from "@/api/client";
import type { WorkspaceTab, WorkspaceView } from "@/features/panels/panelView";
import { CleanTest } from "@/features/panels/TestPanel";
import { PhotoViewer } from "./PhotoViewer";
import { useWorkspacePhotos } from "./photos";

export interface WorkspaceProps {
  api: ApiClient;
  view: WorkspaceView;
  /** "Test", "Key", "Student answers", "Grade report". */
  title: string;
  /** Shows the workspace as a print view under this bar (`PrintBar`). */
  printBar?: ReactNode;
  /** The tabs that apply to this thread (`workspaceTabs`); none = no tab list. */
  tabs?: readonly WorkspaceTab[];
  /** Opens another tab's view (the shell asks first about unsaved text). */
  onTab?: (view: WorkspaceView) => void;
  /** The thread's actions at the right of the tab row (step 22.3.2: Grade student answers). */
  actions?: ReactNode;
  /** Under the bar: the student chip, unsure notes and the run's progress (step 22.3.2). */
  banner?: ReactNode;
  children?: ReactNode;
}

const barButton =
  "main-label inline-flex min-h-8 items-center gap-1 rounded-button border border-border px-3 py-1 text-sm text-text hover:bg-hover focus-visible:outline-2 focus-visible:outline-focus";

function sameView(a: WorkspaceView, b: WorkspaceView): boolean {
  return a.kind === b.kind && a.testId === b.testId && ("attemptId" in a ? a.attemptId : null) === ("attemptId" in b ? b.attemptId : null);
}

export function Workspace({ api, view, title, printBar, tabs, onTab, actions, banner, children }: WorkspaceProps) {
  const printing = printBar !== undefined && printBar !== null;
  const photos = useWorkspacePhotos(api, view);
  const ids = useId();
  /** Below 1024 px only one side shows; this says which. */
  const [narrow, setNarrow] = useState<"panel" | "photos">("panel");
  /** The Key workspace's right side: the photos or the test text. */
  const [right, setRight] = useState<"photos" | "text">("photos");
  const showText = view.kind === "keys" && right === "text";
  const heading = useRef<HTMLHeadingElement>(null);
  const viewKey = `${view.kind}:${"attemptId" in view ? view.attemptId : view.testId}`;

  const tabList = useRef<HTMLDivElement>(null);
  /** The view changed from the tab list: focus stays on the tabs, not the heading. */
  const fromTab = useRef(false);
  const showTabs = !!tabs && tabs.length > 1 && !!onTab;
  const current = showTabs ? tabs.findIndex((t) => sameView(t.view, view)) : -1;

  // Opening a workspace moves focus to its heading, so a screen reader hears where it is.
  useEffect(() => {
    if (fromTab.current) {
      fromTab.current = false;
      tabList.current?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')?.focus();
      return;
    }
    heading.current?.focus();
  }, [viewKey]);

  const openTab = (tab: WorkspaceTab) => {
    if (sameView(tab.view, view)) return;
    fromTab.current = true;
    onTab?.(tab.view);
  };
  /** Arrow keys, Home and End move focus along the tabs; Enter or Space opens one. */
  const onTabKey = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const all = Array.from(tabList.current?.querySelectorAll<HTMLElement>('[role="tab"]') ?? []);
    const at = all.indexOf(document.activeElement as HTMLElement);
    if (at < 0) return;
    const next =
      e.key === "ArrowRight" ? (at + 1) % all.length
      : e.key === "ArrowLeft" ? (at - 1 + all.length) % all.length
      : e.key === "Home" ? 0
      : e.key === "End" ? all.length - 1
      : -1;
    if (next < 0) return;
    e.preventDefault();
    all[next]?.focus();
  };

  const owner =
    view.kind === "test" || view.kind === "keys" ? "this test" : view.kind === "answers" ? "these student answers" : "this report";
  const initialPage = "page" in view && view.page ? view.page : 1;
  const panelId = `${ids}-panel`;
  const photosId = `${ids}-photos`;

  const keySwitch =
    view.kind === "keys" ? (
      <div role="group" aria-label="Right side shows" className="flex rounded-paper border border-border p-0.5" data-testid="key-right-switch">
        {(["photos", "text"] as const).map((side) => (
          <button
            key={side}
            type="button"
            data-testid={`key-right-${side}`}
            aria-pressed={right === side}
            onClick={() => setRight(side)}
            className={
              "min-h-7 rounded-button px-2 text-sm focus-visible:outline-2 focus-visible:outline-focus " +
              (right === side ? "bg-surface font-medium text-text shadow-sm" : "text-muted hover:text-text")
            }
          >
            {side === "photos" ? "Photos" : "Test text"}
          </button>
        ))}
      </div>
    ) : null;

  return (
    <main
      data-testid="workspace"
      data-kind={view.kind}
      aria-label={printing ? `Print preview: ${title.toLowerCase()}` : `${title} and photos`}
      className="flex h-full min-w-0 flex-1 flex-col bg-bg"
    >
      {printing ? (
        printBar
      ) : (
        <header
          data-testid="workspace-bar"
          className="no-print flex flex-wrap items-end gap-x-4 gap-y-2 px-2 pt-2 lg:px-3"
        >
          <h2
            ref={heading}
            tabIndex={-1}
            className={showTabs ? "sr-only" : "font-serif text-base text-text focus:outline-none"}
          >
            {title}
          </h2>
          {showTabs && (
            <div
              ref={tabList}
              role="tablist"
              aria-label="Workspace"
              data-testid="workspace-tabs"
              onKeyDown={onTabKey}
              className="flex flex-wrap gap-1 pl-2 max-lg:order-last max-lg:basis-full"
            >
              {tabs.map((tab, i) => {
                const selected = i === current;
                return (
                  <button
                    key={tab.label}
                    type="button"
                    role="tab"
                    id={`${ids}-tab-${i}`}
                    data-testid="workspace-tab"
                    aria-selected={selected}
                    aria-controls={selected ? panelId : undefined}
                    tabIndex={selected || (current < 0 && i === 0) ? 0 : -1}
                    onClick={() => openTab(tab)}
                    className={
                      // arch-topped, standing on the paper below: no bottom edge (PRD §10.1 v8.21)
                      "main-label min-h-8 rounded-t-button border border-b-0 px-3 text-sm transition-colors motion-reduce:transition-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus " +
                      (selected
                        ? "border-accent-strong bg-accent font-medium text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover"
                        : "border-input bg-surface text-text hover:bg-hover")
                    }
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
          )}
          <button
            type="button"
            data-testid="workspace-side-toggle"
            aria-controls={narrow === "panel" ? photosId : panelId}
            onClick={() => setNarrow((s) => (s === "panel" ? "photos" : "panel"))}
            className={barButton + " mb-1.5 ml-auto lg:hidden"}
          >
            {narrow === "panel" ? "Show photos" : `Show ${title.toLowerCase()}`}
          </button>
          {actions && <div className="mb-1.5 lg:ml-auto">{actions}</div>}
        </header>
      )}
      {/* The panel as a sheet of paper (PRD §10.1 v8.21): white, 2 px corners, a thin page shadow
          and a small margin on the page background. The arch-topped tabs stand on its top edge;
          it starts with the thread or test line over a double rule, like the head of a test. */}
      <div
        data-testid={printing ? undefined : "workspace-paper"}
        className={
          printing
            ? "flex min-h-0 flex-1 flex-col"
            : "mx-2 mb-2 flex min-h-0 flex-1 flex-col overflow-hidden rounded-paper bg-surface shadow-page lg:mx-3 lg:mb-3"
        }
      >
        {!printing && banner && (
          <div data-testid="workspace-header" className="no-print double-rule pb-1.5">
            {banner}
          </div>
        )}
        <div className="flex min-h-0 flex-1">
          <section
            id={panelId}
            data-testid="artifact-panel"
            tabIndex={-1}
            role={showTabs && current >= 0 && !printing ? "tabpanel" : undefined}
            aria-label={title}
            className={
              "min-h-0 min-w-0 flex-1 flex-col focus:outline-none " +
              (printing ? "flex bg-bg" : narrow === "photos" ? "hidden lg:flex" : "flex")
            }
          >
            <div className={"flex-1 overflow-y-auto text-sm text-text " + (printing ? "p-6" : "p-4")}>
              <div
                data-testid={printing ? "print-page" : undefined}
                className={printing ? "print-page mx-auto w-full max-w-3xl rounded-paper border border-border bg-surface p-8" : ""}
              >
                {children}
              </div>
            </div>
          </section>
          {!printing && (
            <section
              id={photosId}
              data-testid="workspace-photos"
              aria-label={showText ? "Test text" : "Original photos"}
              className={
                "no-print min-h-0 min-w-0 flex-1 flex-col border-l border-border bg-panel " +
                (narrow === "panel" ? "hidden lg:flex" : "flex")
              }
            >
              {showText && (
                <>
                  <div className="flex items-center gap-3 border-b border-border bg-panel px-3 py-2">{keySwitch}</div>
                  <div data-testid="key-test-text" className="min-h-0 flex-1 overflow-y-auto bg-surface p-4 text-sm">
                    {photos.test ? (
                      <CleanTest test={photos.test} picturePaths={photos.test.picture_paths} />
                    ) : (
                      <p className="text-muted">{photos.error ?? "Loading the test…"}</p>
                    )}
                  </div>
                </>
              )}
              {/* Kept mounted while the Key shows the test text, so the page and zoom stay. */}
              <div className={showText ? "hidden" : "flex min-h-0 flex-1 flex-col"}>
                <PhotoViewer
                  key={viewKey + ":" + initialPage}
                  api={api}
                  pages={photos.pages}
                  error={photos.error}
                  initialIndex={initialPage}
                  owner={owner}
                  active={!showText}
                  toolbarStart={keySwitch}
                />
              </div>
            </section>
          )}
        </div>
      </div>
    </main>
  );
}
