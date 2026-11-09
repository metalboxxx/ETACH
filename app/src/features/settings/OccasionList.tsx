/**
 * Settings → Occasions (step 22.3.7, PRD v7.2): the ten built-in occasions and the teacher's own.
 * Add one (its name and the short name the Test name uses), rename any inline, move up or down,
 * and delete the teacher's own when no test uses it (after a confirm; otherwise the reason shows).
 * Every change reloads the shared list (`lib/occasions.ts`), so the Occasion editor and Test
 * names follow at once.
 */
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { ApiClient } from "@/api/client";
import { useConfirm } from "@/components/ConfirmDialog";
import { useFocusAfterDelete } from "@/hooks/useFocusAfterDelete";
import { errorText } from "@/lib/errors";
import { loadOccasions, useOccasions, type Occasion } from "@/lib/occasions";

const button = "rounded-button border border-border px-3 py-1 hover:bg-hover disabled:opacity-50";
const input = "min-w-0 rounded-paper border border-input bg-surface px-2 py-1";

const tests = (n: number) => `${n} test${n === 1 ? "" : "s"}`;

export const BUILTIN_NOTE = "Built-in occasions can be renamed but not deleted.";

/** Where keyboard focus goes once the list is idle again: a row's button (the first enabled of
 *  `buttons`), or the Add field when `code` is null. */
interface FocusTarget {
  code: string | null;
  buttons: readonly string[];
}

/** Why an occasion cannot be deleted, or null. A built-in's reason is the one note above the list. */
export function deleteBlocked(o: Occasion): string | null {
  if (o.builtin) return BUILTIN_NOTE;
  if (o.test_count > 0) return `Used by ${tests(o.test_count)}: change their occasion first`;
  return null;
}

export function OccasionList({ api }: { api: ApiClient }) {
  const list = useOccasions(api);
  const confirm = useConfirm();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [label, setLabel] = useState("");
  const [short, setShort] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [newShort, setNewShort] = useState("");
  const [status, setStatus] = useState("");
  const id = useId();
  const noteId = `${id}-builtin`;
  const root = useRef<HTMLDivElement>(null);
  const focusTo = useRef<FocusTarget | null>(null);
  const ids = useMemo(() => list.map((o) => o.code), [list]);
  // WCAG 2.4.3: after a delete, focus goes to the row now in its place (or the Add field).
  const markDeleted = useFocusAfterDelete(ids, (code) => {
    focusTo.current = { code, buttons: ["occasion-rename"] };
  });
  // Busy disables the buttons and Rename's form unmounts, so focus would fall to the page body:
  // put it back once the buttons are enabled again.
  useEffect(() => {
    const t = focusTo.current;
    if (!t || busy || !root.current) return;
    focusTo.current = null;
    if (t.code === null) {
      root.current.querySelector<HTMLElement>('[data-testid="occasion-new-label"]')?.focus();
      return;
    }
    const row = [...root.current.querySelectorAll<HTMLElement>('[data-testid="occasion-row"]')].find((r) => r.dataset.code === t.code);
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
      await loadOccasions(api).catch(() => undefined);
      setBusy(false);
    }
  };

  const startRename = (o: Occasion) => {
    setEditing(o.code);
    setLabel(o.label);
    setShort(o.short_name);
  };

  const endRename = (o: Occasion) => {
    focusTo.current = { code: o.code, buttons: ["occasion-rename"] };
    setEditing(null);
  };

  const saveRename = (o: Occasion) => {
    if (!label.trim() || !short.trim()) return;
    endRename(o);
    void run(
      () => api.patch("/occasions/{code}", { path: { code: o.code }, body: { label: label.trim(), short_name: short.trim() } }),
      `Renamed to ${label.trim()}.`,
    );
  };

  const move = (o: Occasion, to: number, from: "occasion-up" | "occasion-down") => {
    // the same button on the moved row; at the top or bottom, its other move button
    focusTo.current = {
      code: o.code,
      buttons: [from, from === "occasion-up" ? "occasion-down" : "occasion-up", "occasion-rename"],
    };
    void run(
      () => api.patch("/occasions/{code}", { path: { code: o.code }, body: { position: to } }),
      `${o.label} moved to place ${to + 1}.`,
    );
  };

  const remove = async (o: Occasion) => {
    const ok = await confirm({
      title: `Delete ${o.label}?`,
      body: "It leaves the occasion list. No test uses it.",
      confirmLabel: "Delete occasion",
      cancelLabel: "Keep occasion",
      tone: "danger",
    });
    if (!ok) return;
    focusTo.current = { code: o.code, buttons: ["occasion-delete", "occasion-rename"] }; // kept if it fails
    markDeleted(o.code);
    void run(() => api.delete("/occasions/{code}", { path: { code: o.code } }), `${o.label} deleted.`);
  };

  return (
    <div ref={root} data-testid="occasion-list" className="flex flex-col gap-3">
      <p className="text-muted">
        The full name shows in the Occasion editor and on chips; the short name goes into the Test name.
      </p>
      {error && (
        <p role="alert" data-testid="occasion-error" className="text-danger">
          {error}
        </p>
      )}
      {list.some((o) => o.builtin) && (
        <p id={noteId} data-testid="occasion-builtin-note" className="text-muted">
          {BUILTIN_NOTE}
        </p>
      )}
      <p role="status" className="sr-only">
        {status}
      </p>
      <ol aria-label="Occasions" className="flex flex-col divide-y divide-border">
        {list.map((o, i) => {
          const blocked = deleteBlocked(o);
          const reasonId = o.builtin ? noteId : `${id}-why-${i}`;
          return (
            <li key={o.code} data-testid="occasion-row" data-code={o.code} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5">
              {editing === o.code ? (
                <form
                  className="flex flex-1 flex-wrap items-center gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    saveRename(o);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") {
                      e.stopPropagation();
                      endRename(o);
                    }
                  }}
                >
                  <input
                    aria-label="Full name"
                    data-testid="occasion-edit-label"
                    autoFocus
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    className={input + " flex-1"}
                  />
                  <input
                    aria-label="Short name"
                    data-testid="occasion-edit-short"
                    value={short}
                    onChange={(e) => setShort(e.target.value)}
                    className={input + " w-40"}
                  />
                  <button type="submit" data-testid="occasion-save" disabled={!label.trim() || !short.trim()} className={button}>
                    Save
                  </button>
                  <button type="button" onClick={() => endRename(o)} className={button}>
                    Cancel
                  </button>
                </form>
              ) : (
                <>
                  <span className="min-w-[12rem] flex-1">
                    <span data-testid="occasion-label">{o.label}</span>
                    <span className="text-muted"> · in the Test name: </span>
                    <span data-testid="occasion-short">{o.short_name}</span>
                  </span>
                  {blocked && !o.builtin && (
                    <span id={reasonId} data-testid="occasion-blocked" className="text-muted">
                      {blocked}
                    </span>
                  )}
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      data-testid="occasion-rename"
                      aria-label={`Rename ${o.label}`}
                      disabled={busy}
                      onClick={() => startRename(o)}
                      className={button}
                    >
                      Rename
                    </button>
                    <button
                      type="button"
                      data-testid="occasion-up"
                      aria-label={`Move ${o.label} up`}
                      disabled={busy || i === 0}
                      onClick={() => move(o, i - 1, "occasion-up")}
                      className={button}
                    >
                      Up
                    </button>
                    <button
                      type="button"
                      data-testid="occasion-down"
                      aria-label={`Move ${o.label} down`}
                      disabled={busy || i === list.length - 1}
                      onClick={() => move(o, i + 1, "occasion-down")}
                      className={button}
                    >
                      Down
                    </button>
                    <button
                      type="button"
                      data-testid="occasion-delete"
                      aria-label={`Delete ${o.label}`}
                      aria-describedby={blocked ? reasonId : undefined}
                      disabled={busy || blocked !== null}
                      onClick={() => void remove(o)}
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
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const l = newLabel.trim();
          const s = newShort.trim();
          if (!l || !s) return;
          setNewLabel("");
          setNewShort("");
          void run(() => api.post("/occasions", { body: { label: l, short_name: s } }), `${l} added.`);
        }}
      >
        <label className="flex flex-1 flex-col gap-1">
          <span className="text-text">Full name</span>
          <input
            data-testid="occasion-new-label"
            placeholder="e.g. Weekly quiz"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            className={input}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-text">Short name</span>
          <input
            data-testid="occasion-new-short"
            placeholder="e.g. Quiz"
            value={newShort}
            onChange={(e) => setNewShort(e.target.value)}
            className={input + " w-40"}
          />
        </label>
        <button type="submit" data-testid="occasion-add" disabled={busy || !newLabel.trim() || !newShort.trim()} className={button}>
          Add occasion
        </button>
      </form>
    </div>
  );
}
