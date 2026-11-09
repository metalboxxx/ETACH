/**
 * Settings → Test attributes (step 22.5.2, comment 3): occasions, schools and series all describe a
 * test, so they share one tab. The tab shows a menu of the three; a choice opens its list in the
 * same place, with a Back control that returns to the menu. The lists stay mounted (hidden), so a
 * name being typed survives a trip to the menu.
 *
 * Focus: opening a list moves focus to its heading (a screen reader hears where it is); Back
 * returns focus to the menu row that opened the list. Each time Settings opens, the tab starts at
 * the menu.
 */
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { ApiClient } from "@/api/client";
import { OccasionList } from "./OccasionList";
import { SchoolList } from "./SchoolList";
import { SeriesList } from "./SeriesList";

export type AttributeList = "occasions" | "schools" | "series";

export const ATTRIBUTE_LISTS: readonly { id: AttributeList; label: string; about: string }[] = [
  { id: "occasions", label: "Occasions", about: "The kind of test: Mid-term, Final Term, Entrance Exam…" },
  { id: "schools", label: "Schools", about: "The schools on tests and students." },
  { id: "series", label: "Series", about: "Tests that belong together, such as one book of practice tests." },
];

const focusRing = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

function ListView({
  id,
  label,
  shown,
  headingId,
  onBack,
  children,
}: {
  id: AttributeList;
  label: string;
  shown: boolean;
  headingId: string;
  onBack: () => void;
  children: ReactNode;
}) {
  return (
    <section
      data-testid={`settings-${id}`}
      aria-labelledby={headingId}
      hidden={!shown}
      className="flex flex-col gap-3"
    >
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          data-testid="attributes-back"
          aria-label="Back to Test attributes"
          onClick={onBack}
          className={"min-h-8 rounded-button border border-border px-3 py-1 text-text hover:bg-hover " + focusRing}
        >
          <span aria-hidden="true">← </span>Test attributes
        </button>
        <h3 id={headingId} tabIndex={-1} data-testid="attributes-heading" className="font-serif text-base text-text outline-none">
          {label}
        </h3>
      </div>
      {children}
    </section>
  );
}

export function TestAttributes({ api }: { api: ApiClient }) {
  const [view, setView] = useState<AttributeList | null>(null);
  const ids = useId();
  const root = useRef<HTMLDivElement>(null);
  /** Where focus goes after the view changes: a list's heading, or the menu row of a list. */
  const focusTo = useRef<(() => HTMLElement | null | undefined) | null>(null);
  useEffect(() => {
    const target = focusTo.current;
    if (!target) return;
    focusTo.current = null;
    target()?.focus();
  }, [view]);

  const open = (list: AttributeList) => {
    focusTo.current = () => document.getElementById(`${ids}-h-${list}`);
    setView(list);
  };
  const back = () => {
    const from = view;
    focusTo.current = () =>
      root.current?.querySelector<HTMLElement>(`[data-testid="attributes-item"][data-list="${from}"]`);
    setView(null);
  };

  return (
    <div ref={root} data-testid="test-attributes" className="flex flex-col gap-3">
      <div data-testid="attributes-menu" hidden={view !== null} className="flex flex-col gap-2">
        <p className="text-muted">Lists that describe a test. Choose one to change it.</p>
        <ul aria-label="Test attributes" className="flex flex-col gap-2">
          {ATTRIBUTE_LISTS.map((l) => (
            <li key={l.id}>
              <button
                type="button"
                data-testid="attributes-item"
                data-list={l.id}
                aria-labelledby={`${ids}-label-${l.id}`}
                aria-describedby={`${ids}-about-${l.id}`}
                onClick={() => open(l.id)}
                className={
                  "flex min-h-11 w-full items-center gap-3 rounded-button border border-border bg-surface px-3 py-2 text-left hover:bg-hover " +
                  focusRing
                }
              >
                <span className="flex flex-1 flex-col">
                  <span id={`${ids}-label-${l.id}`} className="font-medium text-text">
                    {l.label}
                  </span>
                  <span id={`${ids}-about-${l.id}`} className="text-muted">
                    {l.about}
                  </span>
                </span>
                <span aria-hidden="true" className="text-muted">
                  ›
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
      {ATTRIBUTE_LISTS.map((l) => (
        <ListView key={l.id} id={l.id} label={l.label} shown={view === l.id} headingId={`${ids}-h-${l.id}`} onBack={back}>
          {l.id === "occasions" ? <OccasionList api={api} /> : l.id === "schools" ? <SchoolList api={api} /> : <SeriesList api={api} />}
        </ListView>
      ))}
    </div>
  );
}
