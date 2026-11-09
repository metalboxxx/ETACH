/**
 * The test panel (PRD §10.1): the rendered clean test from `GET /tests/{id}`, mirroring the data
 * model (sections → groups with stimulus and pictures → questions), editable metadata chips
 * (`PATCH /tests/{id}` with `{meta: {field: value}}`, which goes through `write_test_meta`), and
 * Print (`window.print()` with `styles/print.css`). The content renders as stored.
 *
 * Occasion (step 22.1.1, comment 10): the sidecar accepts only an `OCCASIONS` code or
 * "Other:<text>", and the chip used to send the typed words as they were, so they came back as
 * 422 and the chip fell back to its old value. The chip now offers the codes and saves other
 * words as "Other:<words>" (`toOccasion`).
 *
 * The test as one editable page (step 22.1.5, PRD D27, decision 4b): the left side of the Test
 * workspace is the test's text form (`content_text`, data-model §2.3a) in `DocEditor`. Save
 * (button or Ctrl+S) sends `PATCH {content_text}`; a 422 shows each error at its line, and a drop
 * of questions with answers or a key asks first and sends `drop_confirmed`. The test's unsure
 * spots are marked in the page and listed as notes with their actions (`POST /review/{id}/resolve`).
 * Unsaved typing guards Back, Esc and thread switches (`useLeaveGuard`). Print shows the clean test.
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { ApiError, type ApiClient, type Schemas } from "@/api/client";
import { pictureLabel } from "./pictures";
import { useConfirm } from "@/components/ConfirmDialog";
import { accept, itemsOf, resolveItem, str, type Resolution, type ReviewItem } from "@/features/unsure/unsure";
import { DocEditor, type DocEditorHandle, type LineMark } from "./DocEditor";
import { useLeaveGuard } from "./leaveGuard";
import { errorText } from "@/lib/errors";
import { TYPED_NAME_KEY, testDetailsLine, testTitle, typedTestName } from "@/lib/testTitle";
import { SaveAsWord } from "@/components/SaveAsWord";
import { CopyDetails } from "./CopyDetails";
import { BUILTIN_OCCASIONS, getOccasions, occasionLabelOf, useOccasions } from "@/lib/occasions";
import { foldSchool, loadSchools, useSchools } from "@/lib/schools";
import { loadSeries, useSeries } from "@/lib/series";

type Test = Schemas["Test"];
type Meta = Test["meta"];

/** The built-in occasion codes (sidecar `OCCASIONS`), besides "Other:<text>" and the teacher's "Custom:<id>". */
export const OCCASIONS = [
  "MidTerm",
  "FinalTerm",
  "NationalExam",
  "EntranceExam",
  "GiftedExam",
  "UnitTest",
  "FifteenMinuteTest",
  "GrammarPractice",
  "TopicPractice",
  "Placement",
] as const;

/** Step 22.2.1, answer 1: each built-in occasion's label as seeded (step 22.3.7: the list comes from the sidecar). */
export const OCCASION_LABEL = Object.fromEntries(BUILTIN_OCCASIONS.map((o) => [o.code, o.label])) as Record<
  (typeof OCCASIONS)[number],
  string
>;

/** The occasion as shown: its label from the occasion list, or for "Other:<text>" only the text. */
export function occasionLabel(value: string | null | undefined): string {
  return occasionLabelOf(value);
}

/**
 * Typed words → an occasion the sidecar accepts: a code or its label in any case or spacing ("mid
 * term", "Mid-term test" → "MidTerm"), "Other:<text>" as typed, any other words as "Other:<words>". `null` when blank
 * (the occasion is required, so a blank edit is not sent). Step 22.3.7: the teacher's occasions match by label too.
 */
export function toOccasion(text: string): string | null {
  const words = text.split(/\s+/).filter(Boolean).join(" ");
  if (!words) return null;
  const squashed = words.replace(/ /g, "").toLowerCase();
  const plain = (s: string) => s.replace(/[\s'-]/g, "").toLowerCase();
  const list = getOccasions();
  const code =
    list.find((o) => o.code.toLowerCase() === squashed)?.code ?? list.find((o) => plain(o.label) === plain(words))?.code;
  if (code) return code;
  const other = /^other\s*:\s*(.*)$/i.exec(words);
  if (other) return other[1] ? `Other:${other[1]}` : null;
  return `Other:${words}`;
}

type ChipType = "text" | "number" | "occasion" | "school" | "series" | "list";
type ChipValue = string | number | string[] | null;

/** "Unit 1, Unit 2" → ["Unit 1", "Unit 2"]: comma-separated text to a list (answer 7). */
export function parseList(text: string): string[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

interface ChipSpec {
  field: keyof Meta & string;
  label: string;
  type: ChipType;
  /** A short visible explanation under the chip. */
  hint?: string;
}

/**
 * The editable chips, in display order: the fields the Test name is made of (PRD §10 "Test details
 * and name", decision C). `number` fields are sent as numbers (or null).
 */
export const META_CHIPS: ChipSpec[] = [
  { field: "grade", label: "Grade", type: "number" },
  { field: "occasion", label: "Occasion", type: "occasion" },
  { field: "term", label: "Term", type: "number" },
  { field: "school", label: "School", type: "school" },
  { field: "source", label: "Series", type: "series" },
  { field: "year", label: "Year", type: "text" },
  { field: "test_number", label: "Test number", type: "text" },
];

/** The other details, under the folded "More details". */
export const MORE_META_CHIPS: ChipSpec[] = [
  { field: "variant", label: "Variant", type: "text", hint: "The paper's version, e.g. đề A / đề B" },
  { field: "test_code", label: "Code", type: "text" },
  { field: "region", label: "Region", type: "text" },
  { field: "textbook", label: "Textbook", type: "text" },
  { field: "duration_minutes", label: "Minutes", type: "number" },
  { field: "exam_format", label: "Exam format", type: "text" },
  { field: "units", label: "Units", type: "list", hint: "Separate with commas, e.g. Unit 1, Unit 2" },
  { field: "tags", label: "Tags", type: "list", hint: "Separate with commas" },
];

export interface TestPanelProps {
  api: ApiClient;
  testId: string;
  /** Called after a metadata or text edit is saved. */
  onChanged?: (test: Test) => void;
  /** Print hook (tests); defaults to `window.print()`. */
  print?: () => void;
  /** The print view is showing: the clean test instead of the editable page. */
  printing?: boolean;
  /** Changes on SSE `review.changed`: reload the notes (the typing is kept). */
  refreshKey?: number;
}

type Detail = Schemas["TestWithPaths"];

export interface SaveError {
  line: number | null;
  message: string;
}

/**
 * The save errors still true after an edit from `before` to `after` (step 22.2.2): an error on a
 * changed line goes; when lines were added or removed, every error from the first changed line on
 * goes too, since its line number may now point at another line. Errors without a line stay.
 */
export function pruneErrors(errors: readonly SaveError[], before: string, after: string): SaveError[] {
  const a = before.split("\n");
  const b = after.split("\n");
  let first = 0;
  while (first < a.length && first < b.length && a[first] === b[first]) first++;
  const shifted = a.length !== b.length;
  return errors.filter((e) => {
    if (e.line === null) return true;
    if (shifted) return e.line <= first;
    return a[e.line - 1] === b[e.line - 1];
  });
}

/** v1.21 (D7): a heading is "# <printed title>" (the sidecar's `_HEADING_MARK`). */
const HEADING_MARK = /^\s*#/;
/** The form before v1.21: a line ending in a points bracket ("II.  [2.5 points, 0.25 each]"). */
const HEADING = /\[([^[\]]*)\]\s*$/;
const POINTS_TAG = /^\s*[\d.,]+\s*(?:points?|pts?|điểm|diem)\b/i;
const PAGE = /^\s*[-—–]+\s*page\s+(\d+)/i;
const QUESTION = /^\s*(\d+)\.(?: |$)/;

interface TextMap {
  /** 1-based line → the paper page it is on. */
  pageOf: number[];
  /** Section index → its heading line. */
  headings: number[];
  /** Printed question number → its lines. */
  questions: Map<number, number[]>;
  /** Lines with `???`. */
  unreadable: number[];
}

/** Where things are in the text (the sidecar's grammar, data-model §2.3a), for the notes. */
export function mapText(text: string): TextMap {
  const out: TextMap = { pageOf: [0], headings: [], questions: new Map(), unreadable: [] };
  let page = 1;
  let inPassage = false;
  text.split("\n").forEach((line, i) => {
    const no = i + 1;
    const t = line.trim().toLowerCase();
    if (!line.startsWith("\\")) {
      if (t === "[passage]") inPassage = true;
      else if (t === "[end of passage]") inPassage = false;
      else if (!inPassage) {
        const p = PAGE.exec(line);
        if (p) page = Number(p[1]);
        const h = HEADING.exec(line);
        if (HEADING_MARK.test(line) || (h && POINTS_TAG.test(h[1]!))) out.headings.push(no);
        else {
          const q = QUESTION.exec(line);
          if (q) out.questions.set(Number(q[1]), [...(out.questions.get(Number(q[1])) ?? []), no]);
        }
      }
    }
    out.pageOf.push(page);
    if (line.includes("???")) out.unreadable.push(no);
  });
  return out;
}

interface Note {
  item: ReviewItem;
  title: string;
  hint: string;
  lines: number[];
  acceptLabel: string;
}

/** The test-page notes (data-model §5.3 "Where each kind is shown"). */
export function testNotes(test: Detail, text: string): Note[] {
  const map = mapText(text);
  const notes: Note[] = [];
  for (const item of test.review ?? []) {
    if (item.status !== "open") continue;
    if (item.kind === "unreadable_text") {
      const page = typeof item.proposal.page_no === "number" ? item.proposal.page_no : 1;
      const lines = map.unreadable.filter((l) => map.pageOf[l] === page);
      notes.push({
        item,
        title: `Page ${page}: words that could not be read (???)`,
        hint: lines.length
          ? "Type the words in place of the ??? and save. Leave them if the paper is gone."
          : "No ??? left on this page. Save to close this note.",
        lines,
        acceptLabel: "Leave as is",
      });
    } else if (item.kind === "validator_failed" && !item.attempt_id) {
      const failures = Array.isArray(item.proposal.failures)
        ? (item.proposal.failures as { message?: string; printed_number?: number | null }[])
        : [];
      const lines = failures.flatMap((f) => (typeof f.printed_number === "number" ? (map.questions.get(f.printed_number) ?? []) : []));
      const page = typeof item.proposal.page_no === "number" ? item.proposal.page_no : null;
      notes.push({
        item,
        title: page ? `Page ${page}: the app's check found a problem` : "The app's check found a problem",
        hint:
          failures.map((f) => f.message).filter(Boolean).join(" ") ||
          str(item.proposal.call_failure) ||
          "Compare this part with the photo and correct it if needed.",
        lines: lines.length ? lines : page ? [map.pageOf.indexOf(page)].filter((l) => l > 0) : [],
        acceptLabel: "Keep as is",
      });
    }
  }
  return notes;
}

export function TestPanel({ api, testId, onChanged, print, printing = false, refreshKey = 0 }: TestPanelProps) {
  useOccasions(api); // step 22.3.7: labels and Test names follow the occasion list
  useSchools(api); // step 22.4.2: the School chip picks from the school list
  useSeries(api); // step 22.5.2 (D5): the Series chip picks from the series list
  const [test, setTest] = useState<Detail | null>(null);
  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveErrors, setSaveErrors] = useState<SaveError[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const editor = useRef<DocEditorHandle>(null);
  const confirm = useConfirm();
  const ids = useId();
  const nameRow = useRef<HTMLParagraphElement>(null);
  const saved = test?.content_text ?? "";
  const text = draft ?? saved;
  const dirty = draft !== null && draft !== saved;
  useLeaveGuard(dirty);

  useEffect(() => {
    const ctrl = new AbortController();
    api
      .get("/tests/{id}", { path: { id: testId }, signal: ctrl.signal })
      .then((t) => setTest(t))
      .catch((err: unknown) => {
        if (!ctrl.signal.aborted) setError(errorText(err));
      });
    return () => ctrl.abort();
  }, [api, testId, refreshKey]);

  const saveMeta = useCallback(
    async (field: string, value: ChipValue) => {
      setError(null);
      try {
        const next = await api.patch("/tests/{id}", {
          path: { id: testId },
          body: { meta: { [field]: value } },
        });
        setTest(next);
        onChanged?.(next);
        // a new school typed here joins the list in the sidecar (data-model v1.18)
        if (field === "school") void loadSchools(api).catch(() => undefined);
        if (field === "source") void loadSeries(api).catch(() => undefined); // a typed series joins the list
      } catch (err) {
        setError(`Could not save the change: ${errorText(err)}`);
      }
    },
    [api, onChanged, testId],
  );

  /** The latest saveText, for the second save after a drop confirmation. */
  const saveTextRef = useRef<(confirmed?: string[]) => Promise<void>>(async () => {});
  const saveText = useCallback(
    async (confirmed: string[] = []) => {
      if (!dirty || (busy && confirmed.length === 0)) return;
      setBusy(true);
      setError(null);
      setStatus("Saving…");
      try {
        const next = await api.patch("/tests/{id}", {
          path: { id: testId },
          body: { content_text: text, drop_confirmed: confirmed },
        });
        setTest(next);
        setDraft(null);
        setSaveErrors([]);
        setStatus("Saved.");
        onChanged?.(next);
      } catch (err) {
        setStatus("");
        const detail = err instanceof ApiError ? (err.detail as Record<string, unknown> | null) : null;
        if (detail && Array.isArray(detail.drops)) {
          const drops = detail.drops as { question_id: string; printed_number: number; has_key: boolean; answers: number }[];
          const nums = drops.map((d) => d.printed_number).join(", ");
          const ok = await confirm({
            title: drops.length === 1 ? `Delete question ${nums}?` : `Delete questions ${nums}?`,
            body: (
              <>
                <p>
                  {drops.length === 1 ? "It has" : "They have"} student answers or a key. Their student answers, key and explanations
                  will be deleted, and graded students are graded again.
                </p>
                <ul className="list-disc pl-5" data-testid="drop-list">
                  {drops.map((d) => (
                    <li key={d.question_id}>
                      Question {d.printed_number}
                      {d.has_key ? ", with a key" : ""}
                      {d.answers ? `, ${d.answers === 1 ? "1 student answer" : `${d.answers} student answers`}` : ""}
                    </li>
                  ))}
                </ul>
              </>
            ),
            confirmLabel: "Delete and save",
            cancelLabel: "Keep editing",
            tone: "danger",
          });
          setBusy(false);
          if (ok) await saveTextRef.current(drops.map((d) => d.question_id));
          return;
        }
        if (detail && Array.isArray(detail.errors)) {
          const errs = (detail.errors as SaveError[]).map((e) => ({ line: e.line ?? null, message: String(e.message) }));
          setSaveErrors(errs);
          setError(
            errs.length === 1
              ? "The text could not be saved: 1 line needs a fix."
              : `The text could not be saved: ${errs.length} lines need a fix.`,
          );
          requestAnimationFrame(() => document.getElementById(`${ids}-errors`)?.focus());
        } else {
          setError(`Could not save the text: ${errorText(err)}`);
        }
      } finally {
        setBusy(false);
      }
    },
    [api, busy, confirm, dirty, ids, onChanged, testId, text],
  );
  useEffect(() => {
    saveTextRef.current = saveText;
  });

  const resolve = useCallback(
    async (item: ReviewItem, body: Resolution) => {
      setError(null);
      try {
        await resolveItem(api, item.id, body);
        setTest((t) => (t ? { ...t, review: (t.review ?? []).filter((i) => i.id !== item.id) } : t));
        if (test) onChanged?.(test);
      } catch (err) {
        setError(`Could not close the note: ${errorText(err)}`);
      }
    },
    [api, onChanged, test],
  );

  const notes = useMemo(() => (test ? testNotes(test, text) : []), [test, text]);
  const marks = useMemo(() => {
    const m = new Map<number, LineMark>();
    for (const n of notes) for (const l of n.lines) m.set(l, { kind: "note", label: n.title });
    for (const l of mapText(text).unreadable) if (!m.has(l)) m.set(l, { kind: "note", label: "Words that could not be read (???)" });
    for (const e of saveErrors) if (e.line) m.set(e.line, { kind: "error", label: e.message });
    return m;
  }, [notes, saveErrors, text]);

  if (!test) {
    return error ? <p role="alert" className="text-danger">{error}</p> : <p className="text-muted">Loading…</p>;
  }
  const occasionItem = itemsOf(test.review, "unknown_occasion")[0];

  return (
    <div data-testid="test-panel" className="flex flex-col gap-4">
      <div className="no-print flex flex-wrap items-center gap-2" data-testid="test-toolbar">
        <p ref={nameRow} data-testid="test-name" className="flex w-full flex-wrap items-center gap-2 text-sm">
          <MetaChip
            field={TYPED_NAME_KEY}
            label="Test name"
            type="text"
            testId="test-name-chip"
            value={testTitle(test.meta)}
            onSave={(v) => {
              // An emptied box goes back to the automatic name; the automatic name typed again saves nothing.
              if (v === null) {
                if (typedTestName(test.meta) !== null) void saveMeta(TYPED_NAME_KEY, null);
              } else void saveMeta(TYPED_NAME_KEY, v);
            }}
          />
          {typedTestName(test.meta) !== null && (
            <button
              type="button"
              data-testid="test-name-auto"
              onClick={() =>
                // F7 (step 22.2): the button removes itself; focus goes to the Test name chip.
                void saveMeta(TYPED_NAME_KEY, null).then(() =>
                  nameRow.current?.querySelector<HTMLElement>('[data-testid="test-name-chip"]')?.focus(),
                )
              }
              className="rounded-full border border-border px-3 py-1 text-xs hover:bg-hover"
            >
              Use automatic name
            </button>
          )}
        </p>
        {META_CHIPS.map((c) => (
          <MetaChip
            key={c.field}
            field={c.field}
            label={c.label}
            type={c.type}
            value={test.meta[c.field] as string | number | null | undefined}
            unsure={c.field === "occasion" && !!occasionItem}
            onKeep={c.field === "occasion" && occasionItem ? () => void resolve(occasionItem, accept()) : undefined}
            onSave={(v) => void saveMeta(c.field, v)}
          />
        ))}
        <button
          type="button"
          data-testid="test-print"
          disabled={dirty}
          aria-describedby={dirty ? `${ids}-printhint` : undefined}
          onClick={() => (print ?? (() => window.print()))()}
          className="main-label ml-auto rounded-button bg-accent px-3 py-1 text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover disabled:opacity-50"
        >
          Print
        </button>
        <SaveAsWord
          what="test"
          testId="test-save-docx"
          disabled={dirty}
          describedBy={dirty ? `${ids}-printhint` : undefined}
          save={() => api.post("/tests/{id}/export", { path: { id: testId }, body: { what: "test" } })}
        />
        {dirty && (
          <span id={`${ids}-printhint`} className="sr-only">
            Save your changes to print them or save them as Word
          </span>
        )}
        <CopyDetails
          api={api}
          test={test}
          occasionLabel={occasionLabel}
          onCopied={(next) => {
            setTest(next);
            onChanged?.(next);
          }}
        />
        <details data-testid="more-details" className="w-full text-sm">
          <summary className="w-fit cursor-pointer rounded-button px-1 text-muted hover:text-text">More details</summary>
          <div className="mt-2 flex flex-wrap items-start gap-2">
            {MORE_META_CHIPS.map((c) => (
              <MetaChip
                key={c.field}
                field={c.field}
                label={c.label}
                type={c.type}
                hint={c.hint}
                value={test.meta[c.field] as ChipValue | undefined}
                onSave={(v) => void saveMeta(c.field, c.type === "list" ? (v ?? []) : v)}
              />
            ))}
          </div>
        </details>
      </div>
      {printing ? (
        <CleanTest test={test} picturePaths={test.picture_paths} />
      ) : (
        <>
          <TestTitle test={test} compact />
          <div className="no-print flex flex-wrap items-center gap-2" data-testid="text-actions">
            <button
              type="button"
              data-testid="text-save"
              disabled={!dirty || busy}
              onClick={() => void saveText()}
              title="Save (Ctrl+S)"
              className="min-h-8 rounded-button bg-accent px-3 py-1 text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              data-testid="text-cancel"
              disabled={!dirty || busy}
              onClick={() => {
                setDraft(null);
                setSaveErrors([]);
                setError(null);
                setStatus("Changes undone.");
              }}
              className="min-h-8 rounded-button border border-border px-3 py-1 hover:bg-hover disabled:opacity-50"
            >
              Undo changes
            </button>
            <span role="status" data-testid="text-status" className="text-muted">
              {dirty && !busy ? "Unsaved changes" : status}
            </span>
          </div>
          {error && (
            <div
              id={`${ids}-errors`}
              tabIndex={-1}
              role="alert"
              data-testid="text-errors"
              className="no-print flex flex-col gap-1 rounded-paper border border-danger p-3 text-danger focus:outline-2 focus:outline-focus"
            >
              <p className="font-medium">{error}</p>
              {saveErrors.length > 0 && (
                <ul className="flex flex-col gap-1">
                  {saveErrors.map((e, i) => (
                    <li key={i} data-testid="text-error" data-line={e.line ?? ""}>
                      {e.line ? (
                        <button
                          type="button"
                          onClick={() => editor.current?.goToLine(e.line!)}
                          className="text-left underline underline-offset-2 hover:no-underline"
                        >
                          Line {e.line}: {e.message}
                        </button>
                      ) : (
                        e.message
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          <DocEditor
            ref={editor}
            value={text}
            onChange={(t) => {
              if (saveErrors.length) {
                const kept = pruneErrors(saveErrors, text, t);
                if (kept.length !== saveErrors.length) {
                  setSaveErrors(kept);
                  if (kept.length === 0) setError(null);
                }
              }
              setDraft(t);
              setStatus("");
            }}
            onSave={() => void saveText()}
            marks={marks}
            label="Test text"
            disabled={busy}
          />
          {/* The help and the notes come after the text, so the text starts near the top (step 22.2.2). */}
          {notes.length > 0 && (
            <section aria-labelledby={`${ids}-notes`} data-testid="test-notes" className="no-print flex flex-col gap-2">
              <h3 id={`${ids}-notes`} className="font-medium">
                {notes.length === 1 ? "1 spot to check" : `${notes.length} spots to check`}
              </h3>
              <ul className="flex flex-col gap-2">
                {notes.map((n) => (
                  <li
                    key={n.item.id}
                    data-testid="test-note"
                    data-kind={n.item.kind}
                    className="flex flex-col gap-1 rounded-paper border border-border bg-unsure/15 p-2"
                  >
                    <p className="font-medium">{n.title}</p>
                    <p className="text-muted">{n.hint}</p>
                    <div className="flex flex-wrap gap-2">
                      {n.lines.length > 0 && (
                        <button
                          type="button"
                          data-testid="note-goto"
                          onClick={() => editor.current?.goToLine(n.lines[0]!)}
                          className="rounded-button border border-border px-2 py-0.5 hover:bg-hover"
                        >
                          Go to line {n.lines[0]}
                        </button>
                      )}
                      <button
                        type="button"
                        data-testid="note-accept"
                        onClick={() => void resolve(n.item, accept())}
                        className="rounded-button border border-border px-2 py-0.5 hover:bg-hover"
                      >
                        {n.acceptLabel}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <footer className="no-print flex flex-col gap-2 text-muted">
            <FormatHelp />
          </footer>
        </>
      )}
    </div>
  );
}

/** Data-model §2.3a: every line form of the test text, in the order they are tried. */
export const LINE_FORMS: { form: string; example: string; meaning: string }[] = [
  { form: "Escaped", example: "\\12. not a question", meaning: "A leading \\ makes the rest plain text." },
  {
    form: "Passage",
    example: "[Passage] … [End of passage]",
    meaning: "A reading text or dialogue, kept exactly as typed. A passage or a picture starts a new group.",
  },
  { form: "Picture", example: "[Hình: files/ab/<id>.jpg · trang 3]", meaning: "A picture from the paper." },
  { form: "Page", example: "— Page 2 —", meaning: "The paper page of the questions below it." },
  {
    form: "Section heading",
    example: "# II. WORD FORM",
    meaning:
      "A # and then the heading as printed. A writing section ends with [not graded]; [title: <title>] gives it a title other than the printed one. Headings carry no points: every graded question is worth 10 ÷ the number of graded questions, shown under the test title. Points typed in brackets are ignored.",
  },
  {
    form: "Question",
    example: "12. She ____ to school.",
    meaning: "A question with the number printed on the paper. Numbers may skip, such as after a left-out listening part.",
  },
  { form: "Option", example: "   A. go    B. goes", meaning: "Answer options A–H; several may share a line, two spaces apart." },
  { form: "Cue", example: "   Cue: (consume)", meaning: "The word to change, for word-form questions." },
  {
    form: "Text",
    example: "Read the passage and answer.",
    meaning: "Anything else continues the line above: instructions, a question, an option or a cue.",
  },
];

/** How long Format help takes to slide open or closed (none under reduced motion). */
export const FORMAT_HELP_MS = 200;

/**
 * "Format help": a footnote button that opens and closes the table of line forms (answer 13b).
 * Step 22.3.1 (comment 7): a chevron that turns, and the table slides open and closed. The slide is
 * a grid-rows transition, off under `prefers-reduced-motion`; once closed the region is `hidden`.
 * Step 22.4.1 (comment 4): opening scrolls the help into view once the slide has given it its
 * height (smooth; instant under reduced motion). Focus stays on the button; closing does not scroll.
 * Step 22.4.8 (answer 1): the scroll brings the button itself to the top of the panel, so the button
 * stays in view and the help starts right under it.
 */
export function FormatHelp() {
  const [open, setOpen] = useState(false);
  // `shown`: the region is in the page (not `hidden`); it stays until the closing slide ends.
  const [shown, setShown] = useState(false);
  const regionId = useId();
  const button = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (open) return; // the click already showed it
    const t = setTimeout(() => setShown(false), FORMAT_HELP_MS);
    return () => clearTimeout(t);
  }, [open]);
  const expanded = open && shown;
  useEffect(() => {
    if (!expanded) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
    // With motion, wait for the slide to end so the panel has its full height.
    const t = setTimeout(
      () => button.current?.scrollIntoView?.({ block: "start", behavior: reduced ? "auto" : "smooth" }),
      reduced ? 0 : FORMAT_HELP_MS,
    );
    return () => clearTimeout(t);
  }, [expanded]);
  return (
    <div className="flex flex-col gap-2 text-sm">
      <button
        ref={button}
        type="button"
        data-testid="format-help"
        aria-expanded={open}
        aria-controls={regionId}
        onClick={() => {
          if (!open) setShown(true);
          setOpen((o) => !o);
        }}
        className="inline-flex w-fit items-center gap-1 rounded-button px-1 underline underline-offset-2 hover:text-text focus-visible:outline-2 focus-visible:outline-focus"
      >
        Format help
        <svg
          aria-hidden
          data-testid="format-help-chevron"
          data-open={open ? "true" : "false"}
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={
            "transition-transform duration-200 motion-reduce:transition-none " + (open ? "rotate-180" : "rotate-0")
          }
        >
          <path d="M2.5 4.5 6 8l3.5-3.5" />
        </svg>
      </button>
      <div
        id={regionId}
        role="region"
        aria-label="Format help"
        data-testid="format-help-region"
        hidden={!shown}
        className={
          "grid transition-[grid-template-rows,opacity] duration-200 ease-out motion-reduce:transition-none " +
          (expanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0")
        }
      >
        <div className="min-h-0 overflow-hidden">
        <table className="w-full border-collapse text-left text-text">
          <thead className="text-muted">
            <tr>
              <th scope="col" className="py-1 pr-3 font-normal">Line</th>
              <th scope="col" className="py-1 pr-3 font-normal">Example</th>
              <th scope="col" className="py-1 font-normal">What it is</th>
            </tr>
          </thead>
          <tbody>
            {LINE_FORMS.map((f) => (
              <tr key={f.form} data-testid="format-help-row" className="border-t border-border align-top">
                <th scope="row" className="py-1 pr-3 font-medium">{f.form}</th>
                <td className="whitespace-pre py-1 pr-3 font-mono text-xs">{f.example}</td>
                <td className="py-1">{f.meaning}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  );
}

function MetaChip({
  field,
  label,
  type,
  value,
  onSave,
  unsure = false,
  onKeep,
  hint,
  testId = "meta-chip",
}: {
  field: string;
  /** The chip's test id (the Test name chip is not one of the detail chips). */
  testId?: string;
  label: string;
  type: ChipType;
  /** A visible explanation shown beside the chip (and read with it). */
  hint?: string;
  value: ChipValue | undefined;
  /** A `list` chip saves a list (an emptied box saves null, sent as []). */
  onSave: (v: ChipValue) => void;
  /** An open unknown_occasion: the chip is marked; editing it is the Fix (data-model §5.3). */
  unsure?: boolean;
  /** Accept: keep the value as it is ("Other:unknown"). */
  onKeep?: () => void;
}) {
  const occasions = useOccasions();
  const schools = useSchools();
  const series = useSeries();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  // Occasion: the full list until the teacher types; then only the matches (step 22.3.1, comment 8).
  const [typed, setTyped] = useState(false);
  const [active, setActive] = useState(-1);
  // Enter closes the field, and closing it fires blur: save once per edit.
  const closed = useRef(false);
  // F7 (step 22.2): after Enter or Escape, focus goes back to the chip (not after a click away).
  const refocus = useRef(false);
  const chipRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!editing && refocus.current) {
      refocus.current = false;
      chipRef.current?.focus();
    }
  }, [editing]);
  const listId = useId();
  const hintId = useId();
  const raw = value === null || value === undefined ? "" : Array.isArray(value) ? value.join(", ") : String(value);
  const shown = raw === "" ? "–" : type === "occasion" ? occasionLabel(raw) || "–" : raw;

  const close = () => {
    closed.current = true;
    setEditing(false);
  };

  // Occasion, School and Series are comboboxes: the whole list when opened, the matches once typing starts.
  const picker = type === "occasion" || type === "school" || type === "series";
  const options =
    type === "occasion"
      ? occasions.map((o) => o.label).filter(
          // A word of the label starts with what was typed ("na" → National exam, not Final-term).
          (l) => !typed || l.toLowerCase().split(/[\s-]+/).some((w) => w.startsWith(text.trim().toLowerCase())),
        )
      : type === "school" || type === "series"
        ? (type === "school" ? schools : series)
            .map((s) => s.name)
            .filter((n) => !typed || foldSchool(n).includes(foldSchool(text)))
        : [];

  const commit = (picked?: string) => {
    if (closed.current) return;
    close();
    const t = (picked ?? text).trim();
    if (type === "occasion") {
      const next = toOccasion(t);
      if (next !== null && next !== value) onSave(next);
      return;
    }
    if (type === "list") {
      const list = parseList(t);
      if (list.join(", ") !== raw) onSave(list.length ? list : null);
      return;
    }
    const next = type === "number" ? (t === "" ? null : Number(t)) : t === "" ? null : t;
    if (type === "number" && next !== null && Number.isNaN(next)) return;
    if (next === (value ?? null)) return;
    onSave(next);
  };

  if (editing) {
    return (
      <>
        <span className={picker ? "relative inline-flex" : "contents"}>
        <input
          autoFocus
          aria-label={label}
          aria-describedby={hint ? hintId : undefined}
          data-testid={`${testId}-input`}
          data-field={field}
          type={type === "number" ? "number" : "text"}
          role={picker ? "combobox" : undefined}
          aria-expanded={picker ? options.length > 0 : undefined}
          aria-controls={picker ? listId : undefined}
          aria-autocomplete={picker ? "list" : undefined}
          aria-activedescendant={picker && active >= 0 ? `${listId}-${active}` : undefined}
          autoComplete="off"
          placeholder={
            type === "occasion"
              ? "Pick one or type your own"
              : type === "school"
                ? "Pick one or type a new school"
                : type === "series"
                  ? "Pick one or type a new series"
                  : undefined
          }
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setTyped(true);
            setActive(-1);
          }}
          onBlur={() => commit()}
          onKeyDown={(e) => {
            if (picker && (e.key === "ArrowDown" || e.key === "ArrowUp") && options.length) {
              e.preventDefault();
              const d = e.key === "ArrowDown" ? 1 : -1;
              setActive((a) => (a < 0 ? (d > 0 ? 0 : options.length - 1) : (a + d + options.length) % options.length));
              return;
            }
            if (e.key === "Enter") {
              // The chip takes focus at once; without this, the same Enter would click it open again.
              e.preventDefault();
              refocus.current = true;
              commit(picker && active >= 0 ? options[active] : undefined);
            }
            if (e.key === "Escape") {
              e.stopPropagation();
              refocus.current = true;
              close();
            }
          }}
          className={
            (field === TYPED_NAME_KEY ? "w-96 max-w-full" : "w-48") +
            " rounded-full border border-accent-strong bg-surface px-3 py-1 text-xs text-text"
          }
        />
        {onKeep && (
          <button
            type="button"
            data-testid="meta-chip-keep"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              close();
              onKeep();
            }}
            className="rounded-full border border-border px-3 py-1 text-xs hover:bg-hover"
          >
            Keep as unknown
          </button>
        )}
        {picker && options.length > 0 && (
          <ul
            id={listId}
            role="listbox"
            aria-label={type === "school" ? "Schools" : type === "series" ? "Series" : "Occasions"}
            data-testid={type === "school" ? "school-options" : type === "series" ? "series-options" : "occasion-list"}
            className="absolute top-full left-0 z-20 mt-1 max-h-64 w-56 overflow-auto rounded-paper border border-border bg-panel py-1 text-xs text-text shadow-lg"
          >
            {options.map((o, i) => (
              <li
                key={o}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                data-testid={type === "school" ? "school-option" : type === "series" ? "series-option" : "occasion-option"}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => commit(o)}
                className={"cursor-pointer px-3 py-1.5 hover:bg-hover " + (i === active ? "bg-hover" : "")}
              >
                {o}
              </li>
            ))}
          </ul>
        )}
        </span>
        {hint && (
          <span id={hintId} data-testid="meta-chip-hint" className="text-xs text-muted">
            {hint}
          </span>
        )}
      </>
    );
  }
  const chip = (
    <button
      ref={chipRef}
      type="button"
      data-testid={testId}
      aria-describedby={hint ? hintId : undefined}
      data-field={field}
      data-unsure={unsure || undefined}
      title={unsure ? `${label} was not found on the paper: click to set it` : `Edit ${label.toLowerCase()}`}
      onClick={() => {
        setText(type === "occasion" ? occasionLabel(raw) : raw);
        setTyped(false);
        setActive(-1);
        closed.current = false;
        setEditing(true);
      }}
      className={
        "rounded-full border px-3 py-1 text-xs hover:bg-hover " +
        (unsure ? "border-input bg-unsure text-text" : "border-border bg-surface text-text")
      }
    >
      <span className={unsure ? "" : "text-muted"}>{label}:</span> {shown}
      {unsure && <span className="font-semibold"> ? (not on the paper)</span>}
    </button>
  );
  if (!hint) return chip;
  return (
    <span className="inline-flex flex-col gap-0.5">
      {chip}
      <span id={hintId} data-testid="meta-chip-hint" className="px-3 text-xs text-muted">
        {hint}
      </span>
    </span>
  );
}

/** A test with the value of each question (`GET /tests/{id}` gives `points_each`, step 22.5.2). */
type TitledTest = Test & { points_each?: number | null };

/**
 * A section heading as the print view and the Word file show it (the sidecar's `heading_text`,
 * v1.21, D7): the printed title (else the title), and "[not graded]" for a writing section. No points.
 */
export function headingText(s: Pick<Test["content"]["sections"][number], "printed_title" | "title" | "graded">): string {
  const title = s.printed_title || s.title;
  return s.graded === false ? `${title}  [not graded]` : title;
}

/** The title and details line the test DOCX starts with (answer 16, `lib/testTitle.ts`). */
export function TestTitle({ test, compact = false }: { test: TitledTest; compact?: boolean }) {
  return (
    <header data-testid="test-title" className="flex flex-col gap-0.5 font-serif text-text">
      <h3 data-testid="test-title-name" className={compact ? "text-base font-semibold" : "text-xl font-semibold"}>
        {testTitle(test.meta)}
      </h3>
      <p data-testid="test-title-details" className="text-sm text-muted print:text-text">
        {testDetailsLine(test.meta, test.points_possible, test.points_each)}
      </p>
    </header>
  );
}

/** The clean test as stored: sections → groups (stimulus, pictures) → questions. */
export function CleanTest({ test, picturePaths }: { test: TitledTest; picturePaths?: Record<string, string> }) {
  return (
    <article data-testid="clean-test" className="flex flex-col gap-5 font-serif text-text">
      <TestTitle test={test} />
      {test.content.sections.map((s) => (
        <section key={s.id} data-testid="test-section" className="flex flex-col gap-3">
          <header>
            <h3 data-testid="test-section-heading" className="font-semibold">
              {headingText(s)}
            </h3>
            {s.instructions && <p className="whitespace-pre-line text-sm italic">{s.instructions}</p>}
          </header>
          {s.groups.map((g) => (
            <div key={g.id} data-testid="test-group" className="print-break-inside-avoid flex flex-col gap-2">
              {g.stimulus && <RichText text={g.stimulus} className="rounded-paper border border-border p-3" />}
              {g.pictures.map((p, i) => (
                <p key={`${p.file_id}-${i}`} data-testid="picture-placeholder" className="font-mono text-xs text-muted">
                  {pictureLabel(p, picturePaths)}
                </p>
              ))}
              <ol className="flex flex-col gap-2">
                {g.questions.map((q) => (
                  <li key={q.id} data-testid="test-question" data-question-id={q.id}>
                    <div className="flex gap-2">
                      <span className="font-semibold">{q.printed_number}.</span>
                      <div className="flex flex-1 flex-col gap-1">
                        {q.stem && <RichText text={q.stem} />}
                        {q.cue && <span className="text-sm">({q.cue})</span>}
                        {q.options && q.options.length > 0 && (
                          <div className="flex flex-wrap gap-x-6 gap-y-1">
                            {q.options.map((o) => (
                              <span key={o.label}>
                                {o.label}. {o.text}
                              </span>
                            ))}
                          </div>
                        )}
                        {q.answer_start && (
                          <span data-testid="answer-start">{q.answer_start} ____</span>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </section>
      ))}
    </article>
  );
}

/** The RichText subset (data-model §2.3): **bold**, <u>underline</u>, line breaks. No raw HTML. */
export function RichText({ text, className }: { text: string; className?: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|<u>.*?<\/u>)/g);
  return (
    <p className={"whitespace-pre-line " + (className ?? "")}>
      {parts.map((p, i) => {
        if (p.startsWith("**") && p.endsWith("**") && p.length > 4) return <strong key={i}>{p.slice(2, -2)}</strong>;
        if (p.startsWith("<u>") && p.endsWith("</u>")) return <u key={i}>{p.slice(3, -4)}</u>;
        return <span key={i}>{p}</span>;
      })}
    </p>
  );
}
