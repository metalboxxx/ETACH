/**
 * "Copy details from…" in the test details (PRD §10 "Students and series", step 22.3.3, D3).
 *
 * The teacher picks another test with the test name search, sees what will change, and saves
 * with `POST /tests/{id}/copy-details`. Only the occasion, term, school, source and year are copied,
 * and only the ones that have a value in the picked test (data-model v1.14.1); grade and test
 * number never change. Focus goes into the search on open and back to the button on close.
 */
import { useEffect, useRef, useState } from "react";
import type { ApiClient, Schemas } from "@/api/client";
import { ExistingTestSearch } from "@/features/photo-check/ExistingTestSearch";
import type { PickedTest } from "@/features/photo-check/draft";
import { errorText } from "@/lib/errors";

type Detail = Schemas["TestWithPaths"];
type Meta = Schemas["Test"]["meta"];

/** The copied fields, in the order the dialog lists them. */
export const SERIES_FIELDS = [
  { field: "occasion", label: "Occasion" },
  { field: "term", label: "Term" },
  { field: "school", label: "School" },
  { field: "source", label: "Series" },
  { field: "year", label: "Year" },
] as const;

function shown(meta: Meta, field: (typeof SERIES_FIELDS)[number]["field"], label: (v: string) => string): string | null {
  const v = meta[field];
  if (v === null || v === undefined || (typeof v === "string" && !v.trim())) return null;
  return field === "occasion" ? label(String(v)) : String(v);
}

export interface CopyDetailsProps {
  api: ApiClient;
  test: Detail;
  /** The occasion code as words (TestPanel's `occasionLabel`). */
  occasionLabel: (value: string) => string;
  onCopied: (next: Detail) => void;
}

export function CopyDetails({ api, test, occasionLabel, onCopied }: CopyDetailsProps) {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<PickedTest | null>(null);
  const [source, setSource] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!picked) return;
    const ctrl = new AbortController();
    api
      .get("/tests/{id}", { path: { id: picked.id }, signal: ctrl.signal })
      .then((t) => setSource(t))
      .catch((err: unknown) => {
        if (!ctrl.signal.aborted) setError(errorText(err));
      });
    return () => ctrl.abort();
  }, [api, picked]);

  useEffect(() => {
    if (open) box.current?.querySelector<HTMLElement>("input, button")?.focus();
  }, [open]);

  const close = () => {
    setOpen(false);
    setPicked(null);
    setSource(null);
    setError(null);
    opener.current?.focus();
  };

  const copy = async () => {
    if (!picked) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.post("/tests/{id}/copy-details", {
        path: { id: test.id },
        body: { from_test_id: picked.id },
      });
      onCopied(next);
      close();
    } catch (err) {
      setError(`Could not copy the details: ${errorText(err)}`);
    } finally {
      setBusy(false);
    }
  };

  const rows = source
    ? SERIES_FIELDS.map((f) => ({
        ...f,
        now: shown(test.meta, f.field, occasionLabel),
        next: shown(source.meta, f.field, occasionLabel),
      }))
    : [];
  const changes = rows.filter((r) => r.next !== null && r.next !== r.now).length;

  return (
    <div className="w-full text-sm">
      <button
        ref={opener}
        type="button"
        data-testid="copy-details-open"
        aria-expanded={open}
        onClick={() => (open ? close() : setOpen(true))}
        className="rounded-full border border-border px-3 py-1 text-xs hover:bg-hover"
      >
        Copy details from…
      </button>
      {open && (
        <div
          ref={box}
          role="group"
          aria-label="Copy details from another test"
          data-testid="copy-details-box"
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.stopPropagation();
              close();
            }
          }}
          className="mt-2 flex flex-col gap-2 rounded-paper border border-border bg-surface p-3"
        >
          <ExistingTestSearch
            api={api}
            value={picked}
            disabled={busy}
            label="Copy details from"
            placeholder="Search tests by name"
            testId="copy-details"
            excludeId={test.id}
            onChange={(t) => {
              setPicked(t);
              setSource(null);
            }}
          />
          {source && (
            <>
              <p className="text-muted">
                Copies the occasion, term, school, series and year. The grade and test number stay.
              </p>
              <dl data-testid="copy-details-values" className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                {rows.map((r) => (
                  <div key={r.field} className="contents" data-testid="copy-details-row" data-field={r.field}>
                    <dt className="text-muted">{r.label}</dt>
                    <dd>
                      {r.next === null ? (
                        <span className="text-muted">{r.now ?? "(blank)"} · stays (blank in that test)</span>
                      ) : r.next === r.now ? (
                        <span>{r.next} · no change</span>
                      ) : (
                        <span>
                          <span className="text-muted line-through">{r.now ?? "(blank)"}</span> → <strong>{r.next}</strong>
                        </span>
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
            </>
          )}
          {error && (
            <p role="alert" className="text-danger">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              data-testid="copy-details-save"
              disabled={!source || busy || changes === 0}
              onClick={() => void copy()}
              className="rounded-button bg-accent px-3 py-1 text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover disabled:opacity-50"
            >
              {source && changes === 0 ? "Nothing to change" : "Copy details"}
            </button>
            <button
              type="button"
              data-testid="copy-details-cancel"
              onClick={close}
              className="rounded-button border border-border px-3 py-1 hover:bg-hover"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
