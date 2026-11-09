/**
 * "Same series as" on the new-thread screen (step 22.5.2, D5, PRD v8.5): a combobox over the
 * Series list (`lib/series.ts`), not over tests. Focusing or clicking the box lists every series
 * name at once (as the 22.4.3 boxes do); typing filters the names; ↓/↑ move, Enter picks, Esc
 * closes the list (a second Esc goes to the caller). Only a name from the list can be picked. The
 * pick shows as a chip with ✕, and the extraction input sends it as `series_name`: the new test gets
 * that series, and grade, occasion, term and year from the newest test of the series.
 *
 * The list is loaded again on each focus, so a series typed on a test since shows here too.
 */
import { useId, useState } from "react";
import type { ApiClient } from "@/api/client";
import { foldSchool } from "@/lib/schools";
import { loadSeries, useSeries } from "@/lib/series";
import { SEARCH_INPUT } from "./ExistingTestSearch";

export interface SeriesSearchProps {
  api: ApiClient;
  value: string | null;
  onChange: (name: string | null) => void;
  disabled?: boolean;
  /** Extra classes for the label, such as `STACKED_LABEL` to line up stacked searches. */
  labelClassName?: string;
}

const LABEL = "Same series as";
const TEST_ID = "series-test";

export function SeriesSearch({ api, value, onChange, disabled, labelClassName = "" }: SeriesSearchProps) {
  const list = useSeries(api);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const inputId = useId();
  const listId = useId();

  if (value) {
    return (
      <div className="flex items-center gap-2 text-sm" data-testid={TEST_ID}>
        <span className={`text-muted ${labelClassName}`} data-testid={`${TEST_ID}-label`}>
          {LABEL}:
        </span>
        <span className="rounded-full bg-hover px-2 py-0.5 text-text" data-testid={`${TEST_ID}-picked`}>
          {value}
        </span>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange(null)}
          aria-label={`Clear ${LABEL.toLowerCase()}`}
          className="rounded-button px-1 text-muted hover:text-text focus-visible:outline-2 focus-visible:outline-focus"
        >
          ×
        </button>
      </div>
    );
  }

  const q = foldSchool(query);
  const options = list.map((s) => s.name).filter((n) => !q || foldSchool(n).includes(q));
  const shown = open && !disabled && options.length > 0;

  const openList = () => {
    setOpen(true);
    setActive(-1);
    loadSeries(api).catch(() => undefined); // keep the old list when offline
  };
  const pick = (name: string) => {
    onChange(name);
    setQuery("");
    setOpen(false);
    setActive(-1);
  };

  return (
    <div className="relative text-sm" data-testid={TEST_ID}>
      <div className="flex items-center gap-2">
        <label htmlFor={inputId} className={`text-muted ${labelClassName}`} data-testid={`${TEST_ID}-label`}>
          {LABEL}
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
          placeholder={list.length ? "Pick a series from Settings (optional)…" : "No series yet (add them in Settings)"}
          data-testid={`${TEST_ID}-search`}
          className={SEARCH_INPUT}
        />
      </div>
      {shown && (
        <ul
          id={listId}
          role="listbox"
          aria-label="Series"
          data-testid={`${TEST_ID}-options`}
          className="absolute right-0 left-0 z-10 mt-1 max-h-56 overflow-y-auto rounded-paper border border-border bg-surface py-1 shadow-sm"
        >
          {options.map((name, i) => (
            <li
              key={name}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              data-testid={`${TEST_ID}-option`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => pick(name)}
              className={"cursor-pointer px-3 py-1.5 hover:bg-hover " + (i === active ? "bg-hover" : "")}
            >
              {name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
