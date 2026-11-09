/**
 * A role's model field (step 22.3.5, comment 12): a combobox over the installed models (name and
 * size). It follows the occasion combobox of step 22.3.1 (TestPanel's detail chip): the full
 * list on open, only the matches once the teacher types, Arrow keys move the active option,
 * Enter picks it, Escape closes the list, and any typed tag is still accepted. A tag that is not
 * installed is flagged "Not installed" with a Download button.
 */
import { useId, useState } from "react";
import type { Schemas } from "@/api/client";

type Installed = Schemas["InstalledModel"];

/** "3.4 GB" / "512 MB": decimal units, as Ollama shows them. */
export function formatSize(bytes: number): string {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  if (bytes >= 1e6) return `${Math.round(bytes / 1e6)} MB`;
  return `${Math.max(1, Math.round(bytes / 1e3))} kB`;
}

/** Compare tags the way Ollama resolves them (the sidecar's `normalize_tag`). */
export function sameTag(a: string, b: string): boolean {
  const norm = (t: string) => {
    let n = t.trim().toLowerCase();
    for (const p of ["registry.ollama.ai/", "library/"]) if (n.startsWith(p)) n = n.slice(p.length);
    return n.split("/").pop()!.includes(":") ? n : n + ":latest";
  };
  return norm(a) === norm(b);
}

export interface ModelComboboxProps {
  role: string;
  /** The accessible name (the visible role name); default "Model for <role>". */
  label?: string;
  /** The id of the role's one-line description. */
  descriptionId?: string;
  value: string;
  onChange: (tag: string) => void;
  /** `GET /models`; `null` while loading or when Ollama does not answer (no flag then). */
  installed: Installed[] | null;
  /** Download the typed tag (shown when it is not installed). */
  onDownload: (tag: string) => void;
  /** The tag is downloading now. */
  downloading?: boolean;
}

export function ModelCombobox({ role, label, descriptionId, value, onChange, installed, onDownload, downloading }: ModelComboboxProps) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState(false);
  const [active, setActive] = useState(-1);
  const listId = useId();
  const flagId = useId();

  const q = value.trim().toLowerCase();
  const options = (installed ?? []).filter((m) => !typed || m.name.toLowerCase().includes(q));
  const missing = installed !== null && value.trim() !== "" && !installed.some((m) => sameTag(m.name, value));
  const expanded = open && options.length > 0;

  const pick = (name: string) => {
    onChange(name);
    setOpen(false);
    setTyped(false);
    setActive(-1);
  };

  return (
    <div className="flex flex-1 flex-col gap-1">
      <div className="relative">
        <input
          data-testid="role-model"
          data-role={role}
          aria-label={label ?? `Model for ${role}`}
          role="combobox"
          aria-expanded={expanded}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={expanded && active >= 0 ? `${listId}-${active}` : undefined}
          aria-invalid={missing || undefined}
          aria-describedby={[descriptionId, missing ? flagId : null].filter(Boolean).join(" ") || undefined}
          autoComplete="off"
          spellCheck={false}
          placeholder="Pick an installed model or type a tag"
          value={value}
          onFocus={() => {
            setOpen(true);
            setTyped(false);
          }}
          onClick={() => setOpen(true)}
          onBlur={() => {
            setOpen(false);
            setActive(-1);
          }}
          onChange={(e) => {
            onChange(e.target.value);
            setOpen(true);
            setTyped(true);
            setActive(-1);
          }}
          onKeyDown={(e) => {
            if ((e.key === "ArrowDown" || e.key === "ArrowUp") && options.length) {
              e.preventDefault();
              setOpen(true);
              const d = e.key === "ArrowDown" ? 1 : -1;
              setActive((a) => (a < 0 ? (d > 0 ? 0 : options.length - 1) : (a + d + options.length) % options.length));
              return;
            }
            if (e.key === "Enter" && expanded && active >= 0) {
              e.preventDefault();
              pick(options[active]!.name);
              return;
            }
            if (e.key === "Escape" && expanded) {
              e.preventDefault();
              e.stopPropagation();
              setOpen(false);
              setActive(-1);
            }
          }}
          className="w-full rounded-paper border border-input bg-surface px-2 py-1"
        />
        {expanded && (
          <ul
            id={listId}
            role="listbox"
            aria-label={`Installed models for ${label ?? role}`}
            data-testid="model-options"
            className="absolute top-full left-0 z-20 mt-1 max-h-64 w-full overflow-auto rounded-paper border border-border bg-panel py-1 text-text shadow-lg"
          >
            {options.map((m, i) => (
              <li
                key={m.name}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                data-testid="model-option"
                data-model={m.name}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(m.name)}
                className={"flex cursor-pointer gap-3 px-3 py-1.5 hover:bg-hover " + (i === active ? "bg-hover" : "")}
              >
                <span className="flex-1 break-all">{m.name}</span>
                <span className="text-muted">{formatSize(m.size)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {missing && (
        <p id={flagId} data-testid="model-missing" data-role={role} className="flex items-center gap-2 text-danger">
          <span>Not installed</span>
          <span aria-hidden="true">—</span>
          <button
            type="button"
            data-testid="model-missing-download"
            disabled={downloading}
            onClick={() => onDownload(value.trim())}
            className="rounded-button border border-border px-2 py-0.5 text-text hover:bg-hover disabled:opacity-50"
          >
            {downloading ? "Downloading…" : "Download"}
          </button>
        </p>
      )}
    </div>
  );
}
