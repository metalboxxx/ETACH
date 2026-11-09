/**
 * The Chats list under the sidebar switch: threads grouped by student, Chưa rõ, Blank tests.
 *
 * Each row shows the thread's `shown_title` (data-model §5.6: the teacher's title, or the student
 * and the test while the title is the default). Step 22.1.1 (comment 7): the row's "⋯" button and
 * a right-click open a menu with Rename; the name is edited in place (`Enter` or leaving the field
 * saves, `Escape` cancels) and saved through `onRename` (`PATCH /threads/{id}`).
 * Step 22.2.3: the menu also has "Delete…" (`onDelete`; the shell asks first, then deletes).
 * A thread with unsure spots (`open_review_count > 0`, step 22.1.5) shows a mark with its count.
 * Step 22.5.1 (comment 10, D4): every row keeps the same slot for that count, empty when there is
 * none, so every name is cut at the same place; the row's tooltip holds the full name.
 */
import { useMemo, useRef, useState } from "react";
import { useDismiss } from "@/hooks/useDismiss";
import { useFocusAfterDelete } from "@/hooks/useFocusAfterDelete";
import { DotsIcon } from "@/components/DotsIcon";
import { GroupHeading } from "@/components/GroupHeading";
import { NEW_THREAD_TESTID, groupThreads, threadName, type ThreadSummary } from "./threads";

export interface ThreadListProps {
  threads: readonly ThreadSummary[] | null;
  activeId: string | null;
  onOpen: (id: string) => void;
  /** Saves a new title; rejects with a message the list shows. Without it, no rename. */
  /** Saves a new title; `null` goes back to the automatic title ("Use automatic name"). */
  onRename?: (id: string, title: string | null) => Promise<void>;
  /** "Delete…" in the menu (step 22.2.3): the caller asks first and deletes. */
  onDelete?: (id: string, name: string) => void;
}

export function ThreadList({ threads, activeId, onOpen, onRename, onDelete }: ThreadListProps) {
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const ids = useMemo(
    () => (threads ? groupThreads(threads).flatMap((g) => g.threads.map((t) => t.thread.id)) : null),
    [threads],
  );
  // After a delete, focus goes to the thread now in its place (F3), or, after the last one, to
  // the sidebar's New thread button (re-verifier F5).
  const markDeleted = useFocusAfterDelete(ids, (id) => {
    if (id) root.current?.querySelector<HTMLElement>(`[data-testid="thread-item"][data-thread-id="${id}"]`)?.focus();
    else document.querySelector<HTMLElement>(`[data-testid="${NEW_THREAD_TESTID}"]`)?.focus();
  });
  if (!threads || threads.length === 0) return <>No threads yet.</>;
  return (
    <div ref={root} className="flex flex-col gap-3" data-testid="thread-list">
      {groupThreads(threads).map((g) => (
        <section key={g.name} data-testid="thread-group" data-group={g.name} aria-label={g.name}>
          <GroupHeading>{g.name}</GroupHeading>
          <ul className="flex flex-col gap-0.5">
            {g.threads.map((t) => (
              <li key={t.thread.id} className="relative">
                {editing === t.thread.id && onRename ? (
                  <RenameField
                    initial={threadName(t)}
                    onDone={async (title, byKey) => {
                      setEditing(null);
                      if (byKey) focusThread(t.thread.id);
                      if (title === null || title === threadName(t)) return;
                      setError(null);
                      try {
                        await onRename(t.thread.id, title);
                      } catch (err) {
                        setError(`Could not rename the thread: ${err instanceof Error ? err.message : String(err)}`);
                      }
                    }}
                  />
                ) : (
                  <ThreadRow
                    thread={t}
                    active={t.thread.id === activeId}
                    menuOpen={menuFor === t.thread.id}
                    canRename={!!onRename}
                    canDelete={!!onDelete}
                    onOpen={() => onOpen(t.thread.id)}
                    onMenu={(open) => setMenuFor(open ? t.thread.id : null)}
                    onRename={() => {
                      setMenuFor(null);
                      setEditing(t.thread.id);
                    }}
                    onDelete={() => {
                      setMenuFor(null);
                      markDeleted(t.thread.id);
                      onDelete?.(t.thread.id, threadName(t));
                    }}
                    onAutoName={() => {
                      setMenuFor(null);
                      focusThread(t.thread.id);
                      setError(null);
                      onRename?.(t.thread.id, null).catch((err: unknown) =>
                        setError(`Could not change the name: ${err instanceof Error ? err.message : String(err)}`),
                      );
                    }}
                  />
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
      {error && (
        <p role="alert" className="px-1 text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

function ThreadRow({
  thread: t,
  active,
  menuOpen,
  canRename,
  canDelete,
  onOpen,
  onMenu,
  onRename,
  onDelete,
  onAutoName,
}: {
  thread: ThreadSummary;
  active: boolean;
  menuOpen: boolean;
  canRename: boolean;
  canDelete: boolean;
  onDelete: () => void;
  onOpen: () => void;
  onMenu: (open: boolean) => void;
  onRename: () => void;
  onAutoName: () => void;
}) {
  const root = useRef<HTMLDivElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  useDismiss(root, menuOpen, (reason) => {
    onMenu(false);
    if (reason === "escape") menuButton.current?.focus();
  });
  const menuId = `thread-menu-${t.thread.id}`;
  const name = threadName(t);
  const unsure = t.open_review_count ?? 0;
  return (
    <div
      ref={root}
      className={
        "group flex items-center rounded-paper " +
        // the open thread: the stronger blue tint; a hovered one the light tint (PRD §10.1 v8.21)
        (active ? "bg-tint-strong text-text" : "text-text hover:bg-tint")
      }
    >
      <button
        type="button"
        data-testid="thread-item"
        data-thread-id={t.thread.id}
        aria-current={active ? "true" : undefined}
        onClick={onOpen}
        onContextMenu={(e) => {
          if (!canRename && !canDelete) return;
          e.preventDefault();
          onMenu(true);
        }}
        title={unsure ? `${name} (${spots(unsure)} to check)` : name}
        data-unsure={unsure || undefined}
        className="flex min-w-0 flex-1 items-center gap-1 rounded-paper py-1 pr-1 pl-2 text-left text-sm focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
      >
        <span className="min-w-0 flex-1 truncate" data-testid="thread-name">
          {name}
        </span>
        <UnsureSlot count={unsure} />
      </button>
      {(canRename || canDelete) && (
        <button
          ref={menuButton}
          type="button"
          data-testid="thread-menu-button"
          aria-label={`More actions for ${name}`}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          aria-controls={menuOpen ? menuId : undefined}
          onClick={() => onMenu(!menuOpen)}
          className="inline-flex h-6 w-5 shrink-0 items-center justify-center rounded-button p-0 text-muted hover:bg-tint-strong hover:text-text focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
        >
          <DotsIcon />
        </button>
      )}
      {menuOpen && (
        <div
          id={menuId}
          role="menu"
          aria-label={`Thread ${name}`}
          data-testid="thread-menu"
          className="absolute right-0 top-full z-10 mt-1 flex min-w-32 flex-col rounded-paper bg-surface p-1 shadow-page"
        >
          {canRename && (
            <button
              type="button"
              role="menuitem"
              autoFocus
              data-testid="thread-rename"
              onClick={onRename}
              className="rounded-button px-3 py-1 text-left text-sm text-text hover:bg-tint focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
            >
              Rename
            </button>
          )}
          {/* Only while the thread has its own title (answer 15). */}
          {canRename && t.thread.title !== AUTOMATIC_TITLE && (
            <button
              type="button"
              role="menuitem"
              data-testid="thread-auto-name"
              onClick={onAutoName}
              className="rounded-button px-3 py-1 text-left text-sm text-text hover:bg-tint focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
            >
              Use automatic name
            </button>
          )}
          {canDelete && (
            <button
              type="button"
              role="menuitem"
              autoFocus={!canRename}
              data-testid="thread-delete"
              onClick={() => {
                // The confirm dialog returns focus to the ⋯ button, not the closed menu (F3).
                menuButton.current?.focus();
                onDelete();
              }}
              className="rounded-button px-3 py-1 text-left text-sm text-danger hover:bg-tint focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
            >
              Delete…
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** The stored title of a thread whose shown title is made automatically (data-model §5.6). */
const AUTOMATIC_TITLE = "New thread";

/** After a rename by keyboard, focus goes back to the thread's row. */
function focusThread(id: string) {
  requestAnimationFrame(() =>
    document.querySelector<HTMLElement>(`[data-testid="thread-item"][data-thread-id="${CSS.escape(id)}"]`)?.focus(),
  );
}

/**
 * The thread's name in place: `Enter` or leaving the field saves, `Escape` cancels (`null`).
 * `byKey` says the field was left with `Enter` / `Escape` (focus returns to the row).
 */
function RenameField({
  initial,
  onDone,
}: {
  initial: string;
  onDone: (title: string | null, byKey: boolean) => void;
}) {
  const [text, setText] = useState(initial);
  const done = useRef(false);
  const finish = (title: string | null, byKey: boolean) => {
    if (done.current) return;
    done.current = true;
    const clean = title?.split(/\s+/).filter(Boolean).join(" ") ?? null;
    onDone(clean ? clean : null, byKey);
  };
  return (
    <input
      autoFocus
      aria-label="Thread name"
      data-testid="thread-rename-input"
      value={text}
      onFocus={(e) => e.currentTarget.select()}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => finish(text, false)}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          finish(text, true);
        } else if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
          finish(null, true);
        }
      }}
      className="w-full rounded-paper border border-accent-strong bg-surface px-2 py-1 text-sm text-text focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
    />
  );
}

export function spots(n: number): string {
  return n === 1 ? "1 spot" : `${n} spots`;
}

/** The sidebar mark for a thread or test that still has unsure spots (PRD D27): a dot plus words
 *  for screen readers, never colour alone (the tooltip says it too). */
export function UnsureMark({ count }: { count: number }) {
  return (
    <span data-testid="unsure-mark" className="ml-auto shrink-0 text-xs font-semibold mark-label">
      <span aria-hidden="true">● {count}</span>
      <span className="sr-only">, {spots(count)} to check</span>
    </span>
  );
}

/**
 * The fixed-width place of the unsure mark at a row's right end (step 22.5.1, D4): the same width
 * on every row, empty without unsure spots, so every name in a list is cut at the same place.
 * Wide enough for "● 99"; only a larger count widens it (that row's name is then cut earlier).
 */
export function UnsureSlot({ count }: { count: number }) {
  return (
    <span data-testid="unsure-slot" className="flex min-w-9 shrink-0 justify-end whitespace-nowrap">
      {count > 0 && <UnsureMark count={count} />}
    </span>
  );
}
