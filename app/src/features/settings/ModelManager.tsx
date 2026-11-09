/**
 * The model manager in Settings (step 22.3.5, comments 12.5 and 17): the models installed in the
 * app's own Ollama with their size and the roles that use them; Download a tag (typed, or one of
 * the suggested tags) with a progress bar and Cancel; Delete with a confirm. A model a role uses
 * shows why it cannot be deleted. Errors come from the sidecar in plain words.
 *
 * `useModelPulls` keeps the downloads (one `POST /models/pull` stream each, cancelled with its
 * AbortController), so the role fields' "Download" and the manager share them.
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { ApiClient, PullEvent, Schemas } from "@/api/client";
import { useConfirm } from "@/components/ConfirmDialog";
import { useFocusAfterDelete } from "@/hooks/useFocusAfterDelete";
import { errorText } from "@/lib/errors";
import { formatSize, sameTag } from "./ModelCombobox";
import { roleList } from "./roles";

type Inventory = Schemas["ModelInventory"];

export interface PullRow {
  event: PullEvent;
  running: boolean;
}

export function pullPercent(e: PullEvent): number | null {
  return e.total ? Math.floor(((e.completed ?? 0) / e.total) * 100) : null;
}

/** The downloads started in this view: start, cancel, and their last events. */
export function useModelPulls(api: ApiClient, onFinished: () => void) {
  const [pulls, setPulls] = useState<Record<string, PullRow>>({});
  const ctrls = useRef(new Map<string, AbortController>());
  useEffect(() => {
    const map = ctrls.current;
    return () => map.forEach((c) => c.abort()); // leaving Settings cancels nothing silently: it stops
  }, []);

  const set = (tag: string, event: PullEvent, running: boolean) =>
    setPulls((p) => ({ ...p, [tag]: { event, running } }));

  const start = useCallback(
    async (tag: string) => {
      const name = tag.trim();
      if (!name || ctrls.current.has(name)) return;
      const ctrl = new AbortController();
      ctrls.current.set(name, ctrl);
      set(name, { model: name, status: "starting", completed: null, total: null, message: null }, true);
      try {
        const last = await api.pullModel(name, (e) => set(name, e, true), ctrl.signal);
        if (last) set(name, last, false);
        else set(name, { model: name, status: "error", completed: null, total: null, message: "The download stopped." }, false);
      } catch (err) {
        if (ctrl.signal.aborted) {
          set(name, { model: name, status: "cancelled", completed: null, total: null, message: null }, false);
        } else {
          set(name, { model: name, status: "error", completed: null, total: null, message: errorText(err) }, false);
        }
      } finally {
        ctrls.current.delete(name);
        onFinished();
      }
    },
    [api, onFinished],
  );

  const cancel = useCallback((tag: string) => ctrls.current.get(tag)?.abort(), []);
  const dismiss = useCallback(
    (tag: string) =>
      setPulls((p) => {
        const next = { ...p };
        delete next[tag];
        return next;
      }),
    [],
  );
  return { pulls, start, cancel, dismiss };
}

const button = "rounded-button border border-border px-3 py-1 hover:bg-hover disabled:opacity-50";

function statusText(row: PullRow): string {
  const e = row.event;
  if (e.status === "success") return "Downloaded";
  if (e.status === "cancelled") return "Cancelled";
  if (e.status === "error") return e.message ?? "The download failed.";
  const pct = pullPercent(e);
  if (pct !== null) return `Downloading ${pct}%`;
  return e.status === "starting" ? "Starting…" : e.status.charAt(0).toUpperCase() + e.status.slice(1);
}

export interface ModelManagerProps {
  api: ApiClient;
  inventory: Inventory | null;
  /** The `GET /models` error in words (e.g. Ollama not running). */
  loadError: string | null;
  reload: () => void;
  pulls: ReturnType<typeof useModelPulls>;
}

export function ModelManager({ api, inventory, loadError, reload, pulls }: ModelManagerProps) {
  const confirm = useConfirm();
  const [tag, setTag] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const tagId = useId();
  const suggestId = useId();
  const root = useRef<HTMLDivElement>(null);
  const installed = inventory?.models ?? [];
  const names = useMemo(() => inventory?.models.map((m) => m.name) ?? null, [inventory]);
  // WCAG 2.4.3: after a delete, focus goes to the model now in its place (its Delete button when
  // enabled), or else to the Download field.
  const markDeleted = useFocusAfterDelete(names, (name) => {
    const row = [...(root.current?.querySelectorAll<HTMLElement>('[data-testid="installed-model"]') ?? [])].find((r) => r.dataset.model === name);
    const del = row?.querySelector<HTMLButtonElement>('[data-testid="model-delete"]');
    if (del && !del.disabled) del.focus();
    else document.getElementById(tagId)?.focus();
  });

  const remove = async (name: string) => {
    const ok = await confirm({
      title: `Delete ${name}?`,
      body: "The model is removed from this computer. You can download it again later.",
      confirmLabel: "Delete model",
      cancelLabel: "Keep model",
      tone: "danger",
    });
    if (!ok) return;
    markDeleted(name);
    setDeleting(name);
    setError(null);
    try {
      await api.delete("/models/{name}", { path: { name } });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setDeleting(null);
      reload();
    }
  };

  const active = Object.entries(pulls.pulls);

  return (
    <div ref={root} data-testid="model-manager" className="flex flex-col gap-3">
      <h4 className="text-text">Installed models</h4>
      {loadError && (
        <p role="alert" data-testid="models-error" className="text-danger">
          {loadError}
        </p>
      )}
      {error && (
        <p role="alert" data-testid="model-delete-error" className="text-danger">
          {error}
        </p>
      )}
      {inventory && installed.length === 0 && <p className="text-muted">No models installed yet.</p>}
      {installed.length > 0 && (
        <ul data-testid="installed-models" aria-label="Installed models" className="flex flex-col divide-y divide-border">
          {installed.map((m) => {
            const used = m.roles.length > 0;
            const reasonId = `${tagId}-used-${m.name}`;
            return (
              <li key={m.name} data-testid="installed-model" data-model={m.name} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5">
                <span className="min-w-0 flex-1 break-all">{m.name}</span>
                <span className="text-muted">{formatSize(m.size)}</span>
                {used && (
                  <span data-testid="model-used-by" id={reasonId} className="text-muted">
                    Used by: {roleList(m.roles)} — pick another model for it to delete this one
                  </span>
                )}
                <button
                  type="button"
                  data-testid="model-delete"
                  aria-label={`Delete ${m.name}`}
                  aria-describedby={used ? reasonId : undefined}
                  disabled={used || deleting !== null}
                  onClick={() => void remove(m.name)}
                  className={button}
                >
                  {deleting === m.name ? "Deleting…" : "Delete"}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <form
        className="flex flex-col gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (tag.trim()) void pulls.start(tag.trim());
          setTag("");
        }}
      >
        <label htmlFor={tagId} className="text-text">
          Download a model
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <input
            id={tagId}
            data-testid="download-tag"
            list={suggestId}
            autoComplete="off"
            spellCheck={false}
            placeholder="Model tag, e.g. name:4b"
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            className="min-w-0 flex-1 rounded-paper border border-input bg-surface px-2 py-1"
          />
          <datalist id={suggestId}>
            {inventory?.suggested.map((s) => <option key={s} value={s} />)}
          </datalist>
          <button type="submit" data-testid="download-start" disabled={!tag.trim()} className={button}>
            Download
          </button>
        </div>
        {inventory && inventory.suggested.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 text-muted">
            <span>Suggested:</span>
            {inventory.suggested.map((s) => {
              const have = installed.some((m) => sameTag(m.name, s));
              return (
                <button
                  key={s}
                  type="button"
                  data-testid="suggested-tag"
                  data-model={s}
                  disabled={have || pulls.pulls[s]?.running}
                  onClick={() => void pulls.start(s)}
                  className={button + " text-text"}
                >
                  {s}
                  {have ? " (installed)" : ""}
                </button>
              );
            })}
          </div>
        )}
      </form>

      {active.length > 0 && (
        <ul data-testid="downloads" aria-label="Downloads" className="flex flex-col gap-2">
          {active.map(([name, row]) => {
            const pct = pullPercent(row.event);
            const failed = row.event.status === "error";
            return (
              <li key={name} data-testid="download-row" data-model={name} data-status={row.event.status} className="flex flex-col gap-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="min-w-0 flex-1 break-all">{name}</span>
                  <span
                    data-testid="download-status"
                    role={failed ? "alert" : "status"}
                    className={failed ? "text-danger" : "text-muted"}
                  >
                    {statusText(row)}
                  </span>
                  {row.running ? (
                    <button type="button" data-testid="download-cancel" aria-label={`Cancel download of ${name}`} onClick={() => pulls.cancel(name)} className={button}>
                      Cancel
                    </button>
                  ) : (
                    <button type="button" data-testid="download-dismiss" aria-label={`Dismiss ${name}`} onClick={() => pulls.dismiss(name)} className={button}>
                      Dismiss
                    </button>
                  )}
                </div>
                {row.running && (
                  <progress
                    data-testid="download-progress"
                    aria-label={`Download of ${name}`}
                    className="h-1 w-full"
                    max={100}
                    value={pct ?? undefined}
                  />
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
