/**
 * The Tests tab under the sidebar switch (PRD §10.1, S2): a search box over `GET /tests?q=`
 * (the sidecar's accent-insensitive prefix search over display names and metadata) and the list
 * of tests with their attempt counts. Merged tests are never listed (the sidecar leaves them
 * out). Clicking a test opens the test panel. Step 22.2.3: each row has a "⋯" menu with
 * "Delete…" (`onDelete`; the shell asks first, naming the threads that go, then deletes).
 *
 * Step 22.5.1: the list is A–Z by name unless the sort button (at the search box's right end)
 * chose another order (`sortTests`); search results follow the same order. The search also finds
 * a test by its id (the sidecar), and that test is then the top row. Each row keeps the same slot
 * for the unsure count (D4), so every name is cut at the same place; the name's tooltip holds it
 * whole.
 */
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useDismiss } from "@/hooks/useDismiss";
import { useFocusAfterDelete } from "@/hooks/useFocusAfterDelete";
import type { ApiClient, Schemas } from "@/api/client";
import { DotsIcon } from "@/components/DotsIcon";
import { UnsureSlot } from "@/features/threads/ThreadList";
import { TEST_SORTS, readTestSort, sortTests, writeTestSort, type TestSort } from "./sortTests";

type TestSummary = Schemas["TestSummary"];

export interface TestsTabProps {
  api: ApiClient | null;
  activeTestId?: string | null;
  onOpen: (testId: string) => void;
  /** Changes when the list should reload (run events, metadata edits). */
  refreshKey?: number;
  /** Focus the search box when mounted (Ctrl+K). */
  autoFocus?: boolean;
  /** Debounce for typing, in ms. */
  debounceMs?: number;
  /** "Delete…" in a row's menu. Without it, no menu. */
  onDelete?: (testId: string, name: string) => void;
}

export function TestsTab({
  api,
  activeTestId,
  onOpen,
  refreshKey = 0,
  autoFocus,
  debounceMs = 200,
  onDelete,
}: TestsTabProps) {
  const [query, setQuery] = useState("");
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<{ rows: TestSummary[]; q: string } | null>(null);
  const [sort, setSortState] = useState<TestSort>(readTestSort);
  const setSort = (next: TestSort) => {
    setSortState(next);
    writeTestSort(next);
  };
  // The rows are for the search that loaded them (`loaded.q`), so an id match is pinned only then.
  const rows = useMemo(() => (loaded ? sortTests(loaded.rows, sort, loaded.q) : null), [loaded, sort]);
  const [error, setError] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const ids = useMemo(() => rows?.map((t) => t.id) ?? null, [rows]);
  // After a delete, focus goes to the row now in its place, or to the search box (F3).
  const markDeleted = useFocusAfterDelete(ids, (id) => {
    const el = id
      ? root.current?.querySelector<HTMLElement>(`[data-testid="test-item"][data-test-id="${id}"]`)
      : root.current?.querySelector<HTMLElement>("[data-testid=\"tests-search\"]");
    el?.focus();
  });

  useEffect(() => {
    if (!api) return;
    const q = query.trim();
    const ctrl = new AbortController();
    const timer = setTimeout(
      () => {
        api
          .get("/tests", { query: q ? { q } : {}, signal: ctrl.signal })
          .then((r) => {
            setLoaded({ rows: Array.isArray(r) ? r : [], q });
            setError(null);
          })
          .catch((err: unknown) => {
            if (!ctrl.signal.aborted) setError(String(err));
          });
      },
      q ? debounceMs : 0,
    );
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [api, query, refreshKey, debounceMs]);

  return (
    <div ref={root} className="flex flex-col gap-2" data-testid="tests-tab">
      <div className="relative flex gap-1" data-testid="tests-search-row">
        <input
          type="search"
          data-testid="tests-search"
          aria-label="Search tests"
          placeholder="Search tests…"
          value={query}
          autoFocus={autoFocus}
          onChange={(e) => setQuery(e.target.value)}
          className="h-8 min-w-0 flex-1 rounded-paper border border-input bg-surface px-2 text-sm text-text placeholder:text-muted focus-visible:outline-2 focus-visible:outline-focus"
        />
        <SortButton sort={sort} onSort={setSort} />
      </div>
      {error && (
        <p role="alert" className="text-danger">
          {error}
        </p>
      )}
      {rows === null ? (
        api ? (
          <span>Loading…</span>
        ) : null
      ) : rows.length === 0 ? (
        <span data-testid="tests-empty">{query.trim() ? "No tests match." : "No tests yet."}</span>
      ) : (
        <ul className="flex flex-col gap-0.5" data-testid="tests-list">
          {rows.map((t) => (
            <li key={t.id} className="relative">
              <TestRow
                name={t.display_name}
                menuOpen={menuFor === t.id}
                onMenu={onDelete ? (open) => setMenuFor(open ? t.id : null) : undefined}
                onDelete={() => {
                  setMenuFor(null);
                  markDeleted(t.id);
                  onDelete?.(t.id, t.display_name);
                }}
              >
              <button
                type="button"
                data-testid="test-item"
                data-test-id={t.id}
                aria-current={t.id === activeTestId ? "true" : undefined}
                onClick={() => onOpen(t.id)}
                title={t.meta.school ?? undefined}
                className={
                  "flex w-full items-center gap-1.5 rounded-paper py-1 pr-1 pl-2 text-left text-sm focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus " +
                  (t.id === activeTestId ? "bg-tint-strong text-text" : "text-text hover:bg-tint")
                }
              >
                <span className="min-w-0 flex-1 truncate" data-testid="test-name" title={t.display_name}>
                  {t.display_name}
                </span>
                <UnsureSlot count={t.open_review_count} />
                <span
                  data-testid="test-attempt-count"
                  aria-hidden="true"
                  className="shrink-0 rounded-full bg-hover px-1.5 text-xs text-muted"
                >
                  {t.attempt_count}
                </span>
                <span className="sr-only">{t.attempt_count === 1 ? " 1 attempt" : ` ${t.attempt_count} attempts`}</span>
              </button>
              </TestRow>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** A test row with its "⋯" menu (Delete…); without `onMenu`, the row alone. */
function TestRow({
  name,
  menuOpen,
  onMenu,
  onDelete,
  children,
}: {
  name: string;
  menuOpen: boolean;
  onMenu?: (open: boolean) => void;
  onDelete: () => void;
  children: ReactNode;
}) {
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  useDismiss(root, menuOpen, (reason) => {
    onMenu?.(false);
    if (reason === "escape") button.current?.focus();
  });
  if (!onMenu) return <>{children}</>;
  return (
    <div ref={root} className="flex items-center">
      <div className="min-w-0 flex-1">{children}</div>
      <button
        ref={button}
        type="button"
        data-testid="test-menu-button"
        aria-label={`More actions for ${name}`}
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        onClick={() => onMenu(!menuOpen)}
        className="inline-flex h-6 w-5 shrink-0 items-center justify-center rounded-button p-0 text-muted hover:bg-tint-strong focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus hover:text-text"
      >
        <DotsIcon />
      </button>
      {menuOpen && (
        <div
          role="menu"
          aria-label={`Test ${name}`}
          data-testid="test-menu"
          className="absolute right-0 top-full z-10 mt-1 flex min-w-32 flex-col rounded-paper bg-surface p-1 shadow-page"
        >
          <button
            type="button"
            role="menuitem"
            autoFocus
            data-testid="test-delete"
            onClick={() => {
              // The confirm dialog returns focus to the ⋯ button, not the closed menu (F3).
              button.current?.focus();
              onDelete();
            }}
            className="rounded-button px-3 py-1 text-left text-sm text-danger hover:bg-tint focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
          >
            Delete…
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * The square sort button at the search box's right end (step 22.5.1, D3), as tall as the box. It
 * opens a menu of the four orders; the chosen one is checked (`menuitemradio`). Enter, Space or
 * ↓ opens it with focus on the chosen order; ↑ / ↓, Home and End move; Enter or Space chooses;
 * Esc closes and focus goes back to the button.
 */
function SortButton({ sort, onSort }: { sort: TestSort; onSort: (sort: TestSort) => void }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  useDismiss(root, open, (reason) => {
    setOpen(false);
    if (reason === "escape") button.current?.focus();
  });
  // Opening the menu puts focus on the chosen order.
  useEffect(() => {
    if (open) menu.current?.querySelector<HTMLElement>('[aria-checked="true"]')?.focus();
  }, [open]);
  const choose = (next: TestSort) => {
    onSort(next);
    setOpen(false);
    button.current?.focus();
  };
  const onMenuKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(menu.current?.querySelectorAll<HTMLElement>('[role="menuitemradio"]') ?? []);
    const at = items.indexOf(document.activeElement as HTMLElement);
    const next =
      e.key === "ArrowDown" ? (at + 1) % items.length
      : e.key === "ArrowUp" ? (at - 1 + items.length) % items.length
      : e.key === "Home" ? 0
      : e.key === "End" ? items.length - 1
      : -1;
    if (next < 0) return;
    e.preventDefault();
    items[next]?.focus();
  };
  const label = TEST_SORTS.find((s) => s.value === sort)?.label ?? "";
  return (
    <div ref={root} className="flex">
      <button
        ref={button}
        type="button"
        data-testid="tests-sort"
        aria-label="Sort tests"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? "tests-sort-menu" : undefined}
        title={`Sort tests: ${label}`}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" && !open) {
            e.preventDefault();
            setOpen(true);
          }
        }}
        className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-button border border-input bg-surface text-text hover:bg-tint focus-visible:outline-2 focus-visible:outline-focus"
      >
        <SortIcon />
      </button>
      {open && (
        <div
          ref={menu}
          id="tests-sort-menu"
          role="menu"
          aria-label="Sort tests"
          data-testid="tests-sort-menu"
          onKeyDown={onMenuKey}
          className="absolute right-0 top-full z-10 mt-1 flex min-w-36 flex-col rounded-paper bg-surface p-1 shadow-page"
        >
          {TEST_SORTS.map((s) => (
            <button
              key={s.value}
              type="button"
              role="menuitemradio"
              aria-checked={s.value === sort}
              data-testid="tests-sort-option"
              data-sort={s.value}
              tabIndex={-1}
              onClick={() => choose(s.value)}
              className="flex items-center gap-2 rounded-button px-3 py-1 text-left text-sm text-text hover:bg-tint focus-visible:bg-tint focus-visible:outline-2 focus-visible:outline-focus"
            >
              <span aria-hidden="true" className="w-3 shrink-0 text-accent-strong">
                {s.value === sort ? "✓" : ""}
              </span>
              {s.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Lines of falling length with a down arrow: "sort". */
function SortIcon() {
  return (
    <svg
      aria-hidden
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2 4h7M2 8h5M2 12h3M12 3v10M9.5 10.5 12 13l2.5-2.5" />
    </svg>
  );
}
