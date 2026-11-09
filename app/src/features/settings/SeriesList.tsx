/**
 * Settings → Test attributes → Series (step 22.5.2, D5, PRD v8.5): the series tests belong to,
 * such as "Đề dự đoán tuyển sinh vào 10". Built like the Schools list: add one, rename it inline
 * (every test with it, and their automatic Test names, follow), move it up or down, and delete it
 * when no test uses it (after a confirm). When the sidecar refuses a delete (409, "N test(s) use
 * this series."), its words show. Every change reloads the shared list (`lib/series.ts`), so the
 * Series field and "Same series as" follow at once.
 */
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { ApiClient } from "@/api/client";
import { useConfirm } from "@/components/ConfirmDialog";
import { useFocusAfterDelete } from "@/hooks/useFocusAfterDelete";
import { errorText } from "@/lib/errors";
import { loadSeries, useSeries, type Series } from "@/lib/series";

const button = "rounded-button border border-border px-3 py-1 hover:bg-hover disabled:opacity-50";
const input = "min-w-0 rounded-paper border border-input bg-surface px-2 py-1";

/** "2 tests"; "Not used" when no test uses the series. */
export function seriesUsesText(s: Series): string {
  if (!s.test_count) return "Not used";
  return `${s.test_count} test${s.test_count === 1 ? "" : "s"}`;
}

/** Why a series cannot be deleted, or null. */
export function seriesDeleteBlocked(s: Series): string | null {
  if (!s.test_count) return null;
  return `Used by ${seriesUsesText(s)}: change their series first`;
}

interface FocusTarget {
  id: number | null;
  buttons: readonly string[];
}

export function SeriesList({ api }: { api: ApiClient }) {
  const list = useSeries(api);
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
    focusTo.current = { id: next === null ? null : Number(next), buttons: ["series-rename"] };
  });
  // Busy disables the buttons and Rename's form unmounts: put focus back once they are enabled.
  useEffect(() => {
    const t = focusTo.current;
    if (!t || busy || !root.current) return;
    focusTo.current = null;
    if (t.id === null) {
      root.current.querySelector<HTMLElement>('[data-testid="series-new-name"]')?.focus();
      return;
    }
    const row = [...root.current.querySelectorAll<HTMLElement>('[data-testid="series-row"]')].find(
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
      await loadSeries(api).catch(() => undefined);
      setBusy(false);
    }
  };

  const startRename = (s: Series) => {
    setEditing(s.id);
    setName(s.name);
  };

  const endRename = (s: Series) => {
    focusTo.current = { id: s.id, buttons: ["series-rename"] };
    setEditing(null);
  };

  const saveRename = (s: Series) => {
    const n = name.trim();
    if (!n) return;
    endRename(s);
    void run(() => api.patch("/series/{id}", { path: { id: s.id }, body: { name: n } }), `Renamed to ${n}.`);
  };

  const move = (s: Series, to: number, from: "series-up" | "series-down") => {
    focusTo.current = { id: s.id, buttons: [from, from === "series-up" ? "series-down" : "series-up", "series-rename"] };
    void run(
      () => api.patch("/series/{id}", { path: { id: s.id }, body: { position: to } }),
      `${s.name} moved to place ${to + 1}.`,
    );
  };

  const remove = async (s: Series) => {
    const ok = await confirm({
      title: `Delete ${s.name}?`,
      body: "It leaves the series list. No test uses it.",
      confirmLabel: "Delete series",
      cancelLabel: "Keep series",
      tone: "danger",
    });
    if (!ok) return;
    focusTo.current = { id: s.id, buttons: ["series-delete", "series-rename"] }; // kept if it fails
    markDeleted(String(s.id));
    void run(() => api.delete("/series/{id}", { path: { id: s.id } }), `${s.name} deleted.`);
  };

  return (
    <div ref={root} data-testid="series-list" className="flex flex-col gap-3">
      <p className="text-muted">
        The Series field of a test and “Same series as” on a new thread pick from this list; a new series typed on a
        test is added here. Renaming a series changes it on every test, and in their Test names.
      </p>
      {error && (
        <p role="alert" data-testid="series-error" className="text-danger">
          {error}
        </p>
      )}
      <p role="status" className="sr-only">
        {status}
      </p>
      {list.length === 0 ? (
        <p data-testid="series-empty" className="text-muted">
          No series yet. Add one below, or type one in a test's Series field.
        </p>
      ) : (
        <ol aria-label="Series" className="flex flex-col divide-y divide-border">
          {list.map((s, i) => {
            const blocked = seriesDeleteBlocked(s);
            const reasonId = `${id}-why-${i}`;
            return (
              <li key={s.id} data-testid="series-row" data-id={s.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5">
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
                      aria-label={`New name for ${s.name}`}
                      data-testid="series-edit-name"
                      autoFocus
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className={input + " flex-1"}
                    />
                    <button type="submit" data-testid="series-save" disabled={!name.trim()} className={button}>
                      Save
                    </button>
                    <button type="button" onClick={() => endRename(s)} className={button}>
                      Cancel
                    </button>
                  </form>
                ) : (
                  <>
                    <span className="min-w-[12rem] flex-1">
                      <span data-testid="series-name">{s.name}</span>
                    </span>
                    {blocked ? (
                      <span id={reasonId} data-testid="series-blocked" className="text-muted">
                        {blocked}
                      </span>
                    ) : (
                      <span data-testid="series-uses" className="text-muted">
                        {seriesUsesText(s)}
                      </span>
                    )}
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        data-testid="series-rename"
                        aria-label={`Rename ${s.name}`}
                        disabled={busy}
                        onClick={() => startRename(s)}
                        className={button}
                      >
                        Rename
                      </button>
                      <button
                        type="button"
                        data-testid="series-up"
                        aria-label={`Move ${s.name} up`}
                        disabled={busy || i === 0}
                        onClick={() => move(s, i - 1, "series-up")}
                        className={button}
                      >
                        Up
                      </button>
                      <button
                        type="button"
                        data-testid="series-down"
                        aria-label={`Move ${s.name} down`}
                        disabled={busy || i === list.length - 1}
                        onClick={() => move(s, i + 1, "series-down")}
                        className={button}
                      >
                        Down
                      </button>
                      <button
                        type="button"
                        data-testid="series-delete"
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
          void run(() => api.post("/series", { body: { name: n } }), `${n} added.`);
        }}
      >
        <label className="flex flex-1 flex-col gap-1">
          <span className="text-text">Series name</span>
          <input
            data-testid="series-new-name"
            placeholder="e.g. Đề dự đoán tuyển sinh vào 10"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className={input}
          />
        </label>
        <button type="submit" data-testid="series-add" disabled={busy || !newName.trim()} className={button}>
          Add series
        </button>
      </form>
    </div>
  );
}
