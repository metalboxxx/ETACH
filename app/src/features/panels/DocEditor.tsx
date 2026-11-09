/**
 * The test as one editable page (step 22.1.5, PRD D27, decision 4b): a plain `<textarea>` over a
 * mirror of the same text. The mirror (aria-hidden, same font, padding and wrapping) paints the
 * marks behind the transparent textarea: every `???` (unreadable on the photo, D25) gets a tint
 * and an underline, and a line with a note or an error gets a tinted band. A gutter on the left
 * shows line numbers, aligned to the mirror's lines, with a mark beside lines that need a look,
 * so the meaning never rests on colour alone. No contenteditable and no editor library: typing,
 * selection, undo and screen readers all stay the browser's own.
 *
 * The textarea grows with the text (the page scrolls, not the field), so the layers never drift.
 * `Ctrl+S` saves. `goToLine` (through `ref`) puts the caret at a line and scrolls it into view.
 */
import { useImperativeHandle, useLayoutEffect, useRef, useState, type Ref } from "react";

export type LineMarkKind = "error" | "note";

export interface LineMark {
  kind: LineMarkKind;
  /** What the gutter mark says to a screen reader and in its tooltip. */
  label: string;
}

export interface DocEditorHandle {
  goToLine: (line: number) => void;
  focus: () => void;
}

export interface DocEditorProps {
  value: string;
  onChange: (text: string) => void;
  onSave: () => void;
  /** 1-based line → its mark. */
  marks: ReadonlyMap<number, LineMark>;
  label: string;
  describedBy?: string;
  disabled?: boolean;
  ref?: Ref<DocEditorHandle>;
}

const TEXT_STYLE =
  "m-0 box-border w-full whitespace-pre-wrap break-words px-6 py-5 font-serif text-[15px] leading-7 [tab-size:4]";

export function DocEditor({ value, onChange, onSave, marks, label, describedBy, disabled, ref }: DocEditorProps) {
  const area = useRef<HTMLTextAreaElement>(null);
  const mirror = useRef<HTMLDivElement>(null);
  const [tops, setTops] = useState<number[]>([]);
  const [height, setHeight] = useState<number | undefined>(undefined);
  const lines = value.split("\n");

  useImperativeHandle(ref, () => ({
    focus: () => area.current?.focus(),
    goToLine: (line: number) => {
      const el = area.current;
      if (!el) return;
      const all = el.value.split("\n");
      const n = Math.min(Math.max(line, 1), all.length);
      let at = 0;
      for (let i = 0; i < n - 1; i++) at += all[i]!.length + 1;
      el.focus();
      el.setSelectionRange(at, at + (all[n - 1]?.length ?? 0));
      const row = mirror.current?.children[n - 1] as HTMLElement | undefined;
      row?.scrollIntoView?.({ block: "center" });
    },
  }));

  // Measure each mirror line, so the gutter and the textarea height follow the wrapping.
  useLayoutEffect(() => {
    const box = mirror.current;
    if (!box) return;
    const measure = () => {
      setTops([...box.children].map((c) => (c as HTMLElement).offsetTop));
      setHeight(box.scrollHeight);
      // The field grows with the text, so it must never keep a scroll offset of its own
      // (typing at the end scrolls it before it has grown); else the marks drift.
      if (area.current) area.current.scrollTop = 0;
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(box);
    return () => ro.disconnect();
  }, [value]);

  return (
    // One page (step 22.3.1, comment 5): the gutter sits inside the page's border and background.
    <div className="flex min-w-0 rounded-paper border border-border bg-surface" data-testid="doc-editor">
      <div
        aria-hidden="true"
        className="relative w-10 shrink-0 select-none font-sans text-xs text-muted/70"
        data-testid="doc-gutter"
      >
        {lines.map((_, i) => {
          const mark = marks.get(i + 1);
          return (
            <span
              key={i}
              data-line={i + 1}
              data-mark={mark?.kind}
              title={mark?.label}
              style={{ top: tops[i] ?? 20 + i * 28 }}
              className={
                "absolute right-1 flex h-7 items-center gap-0.5 leading-7 " +
                (mark?.kind === "error" ? "font-semibold text-danger" : mark ? "font-semibold mark-label" : "")
              }
            >
              {mark && <span>{mark.kind === "error" ? "!" : "?"}</span>}
              {i + 1}
            </span>
          );
        })}
      </div>
      <div className="relative min-w-0 flex-1" data-testid="doc-page-text">
        <div ref={mirror} aria-hidden="true" className={TEXT_STYLE + " pointer-events-none absolute inset-0 text-transparent"} data-testid="doc-mirror">
          {lines.map((line, i) => {
            const mark = marks.get(i + 1);
            return (
              <div
                key={i}
                data-line={i + 1}
                className={mark?.kind === "error" ? "bg-danger/10" : mark ? "bg-unsure/15" : undefined}
              >
                {line === "" ? "​" : <MarkedLine text={line} />}
              </div>
            );
          })}
        </div>
        <textarea
          ref={area}
          aria-label={label}
          aria-describedby={describedBy}
          data-testid="test-text"
          spellCheck={false}
          disabled={disabled}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onScroll={(e) => {
            e.currentTarget.scrollTop = 0;
          }}
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "s") {
              e.preventDefault();
              onSave();
            }
          }}
          style={{ height }}
          className={
            TEXT_STYLE +
            " relative block resize-none overflow-hidden rounded-paper bg-transparent text-text caret-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          }
        />
      </div>
    </div>
  );
}

/** Each `???` run marked: an unsure tint plus an underline (D25). */
function MarkedLine({ text }: { text: string }) {
  const parts = text.split(/(\?{3,})/);
  return (
    <>
      {parts.map((p, i) =>
        /^\?{3,}$/.test(p) ? (
          <mark key={i} data-testid="unreadable-mark" className="rounded-paper bg-unsure/40 text-transparent underline decoration-text decoration-2 underline-offset-4">
            {p}
          </mark>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}
