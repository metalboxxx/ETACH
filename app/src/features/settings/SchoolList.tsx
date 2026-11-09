/**
 * Settings → Schools (step 22.4.2, PRD v7.3): the schools on tests and students. Add one, rename
 * it inline (every test and student with it, and their automatic Test names, follow), move it up
 * or down, and delete it when no test or student uses it (after a confirm; otherwise the reason
 * and the counts show). Built like the Occasions list; every change reloads the shared list
 * (`lib/schools.ts`), so the School fields follow at once.
 */
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { ApiClient } from "@/api/client";
import { useConfirm } from "@/components/ConfirmDialog";
import { useFocusAfterDelete } from "@/hooks/useFocusAfterDelete";
import { errorText } from "@/lib/errors";
import { loadSchools, useSchools, type School } from "@/lib/schools";

const button = "rounded-button border border-border px-3 py-1 hover:bg-hover disabled:opacity-50";
const input = "min-w-0 rounded-paper border border-input bg-surface px-2 py-1";

const count = (n: number, what: string) => `${n} ${what}${n === 1 ? "" : "s"}`;

/** "2 tests, 1 student"; "Not used" when nothing uses the school. */
export function usesText(s: School): string {
  const parts = [];
  if (s.test_count) parts.push(count(s.test_count, "test"));
  if (s.student_count) parts.push(count(s.student_count, "student"));
  return parts.length ? parts.join(", ") : "Not used";
}

/** Why a school cannot be deleted, or null. */
export function deleteBlocked(s: School): string | null {
  if (!s.test_count && !s.student_count) return null;
  return `Used by ${usesText(s)}: change their school first`;
}

interface FocusTarget {
  id: number | null;
  buttons: readonly string[];
}

export function SchoolList({ api }: { api: ApiClient }) {
  const list = useSchools(api);
  const confirm = useConfirm();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [newName, setNewName] = useState("");
  const [status, setStatus] = useState("");
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const focusTo = useRef<FocusTarget | null>(null);
  const ids = useMemo(() => list.map((s) => String(s.id)), [list]);
  // WCAG 2.4.3: after a delete, focus goes to the row now in its place (or the Add field).
  const markDeleted = useFocusAfterDelete(ids, (next) => {
    focusTo.current = { id: next === null ? null : Number(next), buttons: ["school-rename"] };
  });
  // Busy disables the buttons and Rename's form unmounts: put focus back once they are enabled.
  useEffect(() => {
    const t = focusTo.current;
    if (!t || busy || !root.current) return;
    focusTo.current = null;
    if (t.id === null) {
      root.current.querySelector<HTMLElement>('[data-testid="school-new-name"]')?.focus();
      return;
    }
    const row = [...root.current.querySelectorAll<HTMLElement>('[data-testid="school-row"]')].find(
      (r) => r.dataset.id === String(t.id),
    );
    for (const b of t.buttons) {
      const el = row?.querySelector<HTMLButtonElement>(`[data-testid="${b}"]`);
      if (el && !el.disabled) {
        el.focus();
        return;
      }
    }
  });

  const run = async (work: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setError(null);
    try {
      await work();
      setStatus(done);
    } catch (err) {
      setError(errorText(err));
    } finally {
      await loadSchools(api).catch(() => undefined);
      setBusy(false);
    }
  };

  const startRename = (s: School) => {
    setEditing(s.id);
    setName(s.name);
  };

  const endRename = (s: School) => {
    focusTo.current = { id: s.id, buttons: ["school-rename"] };
    setEditing(null);
  };

  const saveRename = (s: School) => {
    const n = name.trim();
    if (!n) return;
    endRename(s);
    void run(() => api.patch("/schools/{id}", { path: { id: s.id }, body: { name: n } }), `Renamed to ${n}.`);
  };

  const move = (s: School, to: number, from: "school-up" | "school-down") => {
    focusTo.current = { id: s.id, buttons: [from, from === "school-up" ? "school-down" : "school-up", "school-rename"] };
    void run(
      () => api.patch("/schools/{id}", { path: { id: s.id }, body: { position: to } }),
      `${s.name} moved to place ${to + 1}.`,
    );
  };

  const remove = async (s: School) => {
    const ok = await confirm({
      title: `Delete ${s.name}?`,
      body: "It leaves the school list. No test or student uses it.",
      confirmLabel: "Delete school",
      cancelLabel: "Keep school",
      tone: "danger",
    });
    if (!ok) return;
    focusTo.current = { id: s.id, buttons: ["school-delete", "school-rename"] }; // kept if it fails
    markDeleted(String(s.id));
    void run(() => api.delete("/schools/{id}", { path: { id: s.id } }), `${s.name} deleted.`);
  };

  return (
    <div ref={root} data-testid="school-list" className="flex flex-col gap-3">
      <p className="text-muted">
        The School field of a test or a student picks from this list; a new school typed there is added here. Renaming
        a school changes it on every test and student, and in their Test names.
      </p>
      {error && (
        <p role="alert" data-testid="school-error" className="text-danger">
          {error}
        </p>
      )}
      <p role="status" className="sr-only">
        {status}
      </p>
      {list.length === 0 ? (
        <p data-testid="school-empty" className="text-muted">
          No schools yet. Add one below, or type one in a test's or student's School field.
        </p>
      ) : (
        <ol aria-label="Schools" className="flex flex-col divide-y divide-border">
          {list.map((s, i) => {
            const blocked = deleteBlocked(s);
            const reasonId = `${id}-why-${i}`;
            return (
              <li key={s.id} data-testid="school-row" data-id={s.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5">
                {editing === s.id ? (
                  <form
                    className="flex flex-1 flex-wrap items-center gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      saveRename(s);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Escape") {
                        e.stopPropagation();
                        endRename(s);
                      }
                    }}
                  >
                    <input
                      aria-label="School name"
                      data-testid="school-edit-name"
                      autoFocus
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className={input + " flex-1"}
                    />
                    <button type="submit" data-testid="school-save" disabled={!name.trim()} className={button}>
                      Save
                    </button>
                    <button type="button" onClick={() => endRename(s)} className={button}>
                      Cancel
                    </button>
                  </form>
                ) : (
                  <>
                    <span className="min-w-[12rem] flex-1">
                      <span data-testid="school-name">{s.name}</span>
                    </span>
                    {blocked ? (
                      <span id={reasonId} data-testid="school-blocked" className="text-muted">
                        {blocked}
                      </span>
                    ) : (
                      <span data-testid="school-uses" className="text-muted">
                        {usesText(s)}
                      </span>
                    )}
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        data-testid="school-rename"
                        aria-label={`Rename ${s.name}`}
                        disabled={busy}
                        onClick={() => startRename(s)}
                        className={button}
                      >
                        Rename
                      </button>
                      <button
                        type="button"
                        data-testid="school-up"
                        aria-label={`Move ${s.name} up`}
                        disabled={busy || i === 0}
                        onClick={() => move(s, i - 1, "school-up")}
                        className={button}
                      >
                        Up
                      </button>
                      <button
                        type="button"
                        data-testid="school-down"
                        aria-label={`Move ${s.name} down`}
                        disabled={busy || i === list.length - 1}
                        onClick={() => move(s, i + 1, "school-down")}
                        className={button}
                      >
                        Down
                      </button>
                      <button
                        type="button"
                        data-testid="school-delete"
                        aria-label={`Delete ${s.name}`}
                        aria-describedby={blocked ? reasonId : undefined}
                        disabled={busy || blocked !== null}
                        onClick={() => void remove(s)}
                        className={button}
                      >
                        Delete
                      </button>
                    </div>
                  </>
                )}
              </li>
            );
          })}
        </ol>
      )}
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const n = newName.trim();
          if (!n) return;
          setNewName("");
          void run(() => api.post("/schools", { body: { name: n } }), `${n} added.`);
        }}
      >
        <label className="flex flex-1 flex-col gap-1">
          <span className="text-text">School name</span>
          <input
            data-testid="school-new-name"
            placeholder="e.g. THCS Lê Lợi"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className={input}
          />
        </label>
        <button type="submit" data-testid="school-add" disabled={busy || !newName.trim()} className={button}>
          Add school
        </button>
      </form>
    </div>
  );
}
