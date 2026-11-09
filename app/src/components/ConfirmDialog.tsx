/**
 * A confirmation dialog (step 22.1.5): `useConfirm()` returns `confirm({...}) → Promise<boolean>`.
 * One modal at a time, `role="alertdialog"`, focus starts on the safe button, Tab stays inside,
 * Escape cancels (and is marked handled, so it does not also close the workspace). Focus returns
 * to where it was.
 *
 * Step 22.5.2 (D8): `useChoose()` returns `choose({...}) → Promise<value | null>`, the same dialog
 * with several actions (Extract again: update the test for every thread, or make a copy); `null`
 * is Cancel or Escape. `confirm` is `choose` with one action.
 *
 * Step 22.5.2 (c): a choice may carry a `hint`, one short line on what that choice keeps and
 * replaces. With a hint the actions stack, each hint under its own button (and read with it), and
 * Cancel sits at the end on its own; focus still starts on Cancel.
 */
import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";

export interface ConfirmOptions {
  title: string;
  body?: ReactNode;
  confirmLabel: string;
  cancelLabel: string;
  /** "danger" for an action that deletes something. */
  tone?: "danger" | "default";
}

/** One action of a `choose` dialog. */
export interface ChoiceOption<T extends string> {
  value: T;
  label: string;
  tone?: "danger" | "default";
  /** `data-testid` of the button (default "confirm-choice"). */
  testId?: string;
  /** One short line under the button, on what this choice keeps and replaces. */
  hint?: string;
}

export interface ChooseOptions<T extends string> {
  title: string;
  body?: ReactNode;
  /** The actions, in order after Cancel. */
  choices: readonly ChoiceOption<T>[];
  cancelLabel: string;
}

type Confirm = (opts: ConfirmOptions) => Promise<boolean>;
type Choose = <T extends string>(opts: ChooseOptions<T>) => Promise<T | null>;

const ChooseContext = createContext<Choose>(async (opts) => opts.choices[0]?.value ?? null);

export function useChoose(): Choose {
  return useContext(ChooseContext);
}

export function useConfirm(): Confirm {
  const choose = useChoose();
  return useCallback<Confirm>(
    async (opts) =>
      (await choose({
        title: opts.title,
        body: opts.body,
        cancelLabel: opts.cancelLabel,
        choices: [{ value: "ok", label: opts.confirmLabel, tone: opts.tone, testId: "confirm-ok" }],
      })) === "ok",
    [choose],
  );
}

type Open = ChooseOptions<string> & { resolve: (value: string | null) => void };

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState<Open | null>(null);
  const choose = useCallback(
    <T extends string>(opts: ChooseOptions<T>) =>
      new Promise<T | null>((resolve) => setOpen({ ...opts, resolve: resolve as (value: string | null) => void })),
    [],
  ) as Choose;
  return (
    <ChooseContext.Provider value={choose}>
      {children}
      {open && (
        <Dialog
          opts={open}
          onDone={(value) => {
            open.resolve(value);
            setOpen(null);
          }}
        />
      )}
    </ChooseContext.Provider>
  );
}

function Dialog({ opts, onDone }: { opts: ChooseOptions<string>; onDone: (value: string | null) => void }) {
  const ids = useId();
  const root = useRef<HTMLDivElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const before = useRef<Element | null>(null);
  useEffect(() => {
    before.current = document.activeElement;
    cancel.current?.focus();
    const back = before.current;
    return () => {
      if (back instanceof HTMLElement && back.isConnected) back.focus();
    };
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onDone(null);
      } else if (e.key === "Tab" && root.current) {
        const items = [...root.current.querySelectorAll<HTMLElement>("button")];
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onDone]);
  const stacked = opts.choices.some((c) => c.hint);
  const cancelButton = (
    <button
      ref={cancel}
      type="button"
      data-testid="confirm-cancel"
      onClick={() => onDone(null)}
      className="min-h-9 rounded-button border border-border px-3 hover:bg-hover focus-visible:outline-2 focus-visible:outline-focus"
    >
      {opts.cancelLabel}
    </button>
  );
  const choiceButton = (c: ChoiceOption<string>, hintId?: string) => (
    <button
      key={c.value}
      type="button"
      data-testid={c.testId ?? "confirm-choice"}
      data-value={c.value}
      aria-describedby={hintId}
      onClick={() => onDone(c.value)}
      className={
        "min-h-9 rounded-button px-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus " +
        (c.tone === "danger"
          ? "border border-danger text-danger hover:bg-hover"
          : "bg-accent text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover")
      }
    >
      {c.label}
    </button>
  );
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg/80 p-4">
      <div
        ref={root}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={`${ids}-t`}
        aria-describedby={opts.body ? `${ids}-b` : undefined}
        data-testid="confirm-dialog"
        className="flex w-full max-w-md flex-col gap-3 rounded-paper border border-border bg-panel p-5 text-sm text-text shadow-lg"
      >
        <h2 id={`${ids}-t`} className="text-base font-semibold">
          {opts.title}
        </h2>
        {opts.body && (
          <div id={`${ids}-b`} className="flex flex-col gap-2">
            {opts.body}
          </div>
        )}
        {stacked ? (
          <div className="flex flex-col gap-3 pt-1">
            {opts.choices.map((c, i) => (
              <div key={c.value} className="flex flex-col items-start gap-1">
                {choiceButton(c, c.hint ? `${ids}-h${i}` : undefined)}
                {c.hint && (
                  <p id={`${ids}-h${i}`} data-testid="confirm-hint" className="text-muted">
                    {c.hint}
                  </p>
                )}
              </div>
            ))}
            <div className="flex justify-end">{cancelButton}</div>
          </div>
        ) : (
          <div className="flex flex-wrap justify-end gap-2 pt-1">
            {cancelButton}
            {opts.choices.map((c) => choiceButton(c))}
          </div>
        )}
      </div>
    </div>
  );
}
