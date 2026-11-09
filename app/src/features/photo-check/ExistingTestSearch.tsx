/**
 * The optional **Existing test** search (PRD D1): a combobox over the test bank; pick one to skip
 * transcription; ✕ clears the pick. The same search, with its own `label`, picks the source of
 * "Copy details from…". "Same series as" picks a series name instead (`SeriesSearch.tsx`, step
 * 22.5.2, D5).
 *
 * Step 22.4.3 (comments 2 and 3), like the School and Occasion comboboxes: focusing or clicking
 * the box lists the 8 most recent tests (one `GET /tests`, newest change first) before any typing;
 * typing filters through `GET /tests?q=`; ↓/↑ move, Enter picks, Esc closes the list (a second
 * Esc goes to the caller), and the list closes on a pick and on leaving the box.
 *
 * Step 22.4.8 (answer 3): `labelClassName` sets the label's width, so stacked searches (Existing
 * test over Same series as) share one label width and their boxes start at the same x.
 */
import { useEffect, useId, useState } from "react";
import type { ApiClient, Schemas } from "@/api/client";
import type { PickedTest } from "./draft";

type TestSummary = Schemas["TestSummary"];

/** One label width for searches stacked in a column, wide enough for "Same series as:". */
export const STACKED_LABEL = "min-w-28 shrink-0 whitespace-nowrap";

/** How many suggestions the list shows. */
export const SUGGESTION_LIMIT = 8;

/** The search box (shared with `SeriesSearch`). */
export const SEARCH_INPUT =
  "min-w-0 flex-1 rounded-paper border border-input bg-bg px-2 py-1 text-text focus-visible:outline-2 focus-visible:outline-focus";

export interface ExistingTestSearchProps {
  api: ApiClient;
  value: PickedTest | null;
  onChange: (test: PickedTest | null) => void;
  disabled?: boolean;
  /** Shown before the box and the pick (default "Existing test"). */
  label?: string;
  placeholder?: string;
  /** `data-testid` prefix (default "existing-test"). */
  testId?: string;
  /** A test that cannot be picked (the test itself, for "Copy details from…"). */
  excludeId?: string;
  /** Extra classes for the label, such as `STACKED_LABEL` to line up stacked searches. */
  labelClassName?: string;
}

export function ExistingTestSearch({
  api,
  value,
  onChange,
  disabled,
  label = "Existing test",
  placeholder = "Search by name (optional)",
  testId = "existing-test",
  excludeId,
  labelClassName = "",
}: ExistingTestSearchProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [hits, setHits] = useState<TestSummary[]>([]);
  const inputId = useId();
  const listId = useId();

  useEffect(() => {
    if (!open) return;
    const q = query.trim();
    const ctrl = new AbortController();
    const load = () =>
      api
        .get("/tests", { query: q ? { q } : {}, signal: ctrl.signal })
        .then((rows) => {
          setHits(Array.isArray(rows) ? rows : []);
          setActive(-1);
        })
        .catch(() => {
          /* aborted or offline: keep the old hits */
        });
    // The recent list comes at once; a typed search waits for a pause in the typing.
    const timer = q ? setTimeout(load, 200) : null;
    if (!q) void load();
    return () => {
      if (timer !== null) clearTimeout(timer);
      ctrl.abort();
    };
  }, [api, query, open]);

  if (value) {
    return (
      <div className="flex items-center gap-2 text-sm" data-testid={testId}>
        <span className={`text-muted ${labelClassName}`} data-testid={`${testId}-label`}>
          {label}:
        </span>
        <span className="rounded-full bg-hover px-2 py-0.5 text-text" data-testid={`${testId}-picked`}>
          {value.display_name}
        </span>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange(null)}
          aria-label={`Clear ${label.toLowerCase()}`}
          className="rounded-button px-1 text-muted hover:text-text"
        >
          ×
        </button>
      </div>
    );
  }

  const rows = hits.filter((t) => t.id !== excludeId);
  const options = rows.slice(0, SUGGESTION_LIMIT);
  const shown = open && !disabled && options.length > 0;

  const openList = () => {
    setOpen(true);
    setActive(-1);
  };
  const pick = (t: TestSummary) => {
    onChange({ id: t.id, display_name: t.display_name });
    setQuery("");
    setHits([]);
    setOpen(false);
    setActive(-1);
  };

  return (
    <div className="relative text-sm" data-testid={testId}>
      <div className="flex items-center gap-2">
        <label htmlFor={inputId} className={`text-muted ${labelClassName}`} data-testid={`${testId}-label`}>
          {label}
        </label>
        <input
          id={inputId}
          type="text"
          role="combobox"
          aria-expanded={shown}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={shown && active >= 0 ? `${listId}-${active}` : undefined}
          autoComplete="off"
          value={query}
          disabled={disabled}
          onFocus={openList}
          onClick={() => !open && openList()}
          onBlur={() => {
            setOpen(false);
            setActive(-1);
          }}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown" || e.key === "ArrowUp") {
              e.preventDefault();
              if (!open) {
                openList();
                return;
              }
              if (!options.length) return;
              const d = e.key === "ArrowDown" ? 1 : -1;
              setActive((a) => (a < 0 ? (d > 0 ? 0 : options.length - 1) : (a + d + options.length) % options.length));
              return;
            }
            if (e.key === "Enter" && shown && active >= 0 && options[active]) {
              e.preventDefault();
              pick(options[active]);
              return;
            }
            if (e.key === "Escape" && shown) {
              e.preventDefault();
              e.stopPropagation();
              setOpen(false);
              setActive(-1);
            }
          }}
          placeholder={placeholder}
          data-testid={`${testId}-search`}
          className={SEARCH_INPUT}
        />
      </div>
      {shown && (
        <ul
          id={listId}
          role="listbox"
          aria-label={query.trim() ? `Matching tests: ${label}` : `Recent tests: ${label}`}
          data-testid={`${testId}-options`}
          className="absolute right-0 left-0 z-10 mt-1 max-h-56 overflow-y-auto rounded-paper border border-border bg-surface py-1 shadow-sm"
        >
          {options.map((t, i) => (
              <li
                key={t.id}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                data-testid={`${testId}-option`}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(t)}
                className={"cursor-pointer px-3 py-1.5 hover:bg-hover " + (i === active ? "bg-hover" : "")}
              >
                {t.display_name} <span className="text-muted">· {t.id}</span>
              </li>
          ))}
        </ul>
      )}
    </div>
  );
}
