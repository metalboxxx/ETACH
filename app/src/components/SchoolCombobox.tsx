/**
 * The School field of a student (step 22.4.2, comment 10): a combobox over the school list, like
 * the Occasion chip and the Student picker. The whole list shows as soon as the field gets focus
 * or is clicked; typing filters it; ↓/↑ move, Enter picks the highlighted school, Esc closes the
 * list (a second Esc goes to the caller). A new name can be typed: the sidecar adds it to the list.
 */
import { useId, useState, type KeyboardEvent } from "react";
import { foldSchool, useSchools } from "@/lib/schools";

export interface SchoolComboboxProps {
  id?: string;
  value: string;
  onChange: (name: string) => void;
  /** Keys the combobox does not use (Enter with nothing highlighted, Esc with the list closed). */
  onKeyDown?: (e: KeyboardEvent<HTMLInputElement>) => void;
  testId?: string;
  className?: string;
}

export function SchoolCombobox({ id, value, onChange, onKeyDown, testId = "school-combobox", className }: SchoolComboboxProps) {
  const schools = useSchools();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState(false);
  const [active, setActive] = useState(-1);
  const listId = useId();
  const options = schools.map((s) => s.name).filter((n) => !typed || foldSchool(n).includes(foldSchool(value)));
  const shown = open && options.length > 0;

  const show = () => {
    setOpen(true);
    setTyped(false);
    setActive(-1);
  };
  const pick = (name: string) => {
    onChange(name);
    setOpen(false);
    setActive(-1);
  };

  return (
    <span className="relative flex flex-col">
      <input
        id={id}
        data-testid={testId}
        role="combobox"
        aria-expanded={shown}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={shown && active >= 0 ? `${listId}-${active}` : undefined}
        autoComplete="off"
        placeholder="Pick one or type a new school"
        value={value}
        onFocus={show}
        onClick={() => !open && show()}
        onBlur={() => setOpen(false)}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
          setTyped(true);
          setActive(-1);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            if (!open) {
              show();
              return;
            }
            if (!options.length) return;
            const d = e.key === "ArrowDown" ? 1 : -1;
            setActive((a) => (a < 0 ? (d > 0 ? 0 : options.length - 1) : (a + d + options.length) % options.length));
            return;
          }
          if (e.key === "Enter" && shown && active >= 0) {
            e.preventDefault();
            pick(options[active] ?? value);
            return;
          }
          if (e.key === "Escape" && shown) {
            e.preventDefault();
            e.stopPropagation();
            setOpen(false);
            setActive(-1);
            return;
          }
          onKeyDown?.(e);
        }}
        className={className}
      />
      {shown && (
        <ul
          id={listId}
          role="listbox"
          aria-label="Schools"
          data-testid="school-options"
          className="absolute top-full left-0 z-20 mt-1 max-h-56 w-full overflow-auto rounded-paper border border-border bg-panel py-1 text-xs text-text shadow-lg"
        >
          {options.map((o, i) => (
            <li
              key={o}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              data-testid="school-option"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => pick(o)}
              className={"cursor-pointer px-3 py-1.5 hover:bg-hover " + (i === active ? "bg-hover" : "")}
            >
              {o}
            </li>
          ))}
        </ul>
      )}
    </span>
  );
}
