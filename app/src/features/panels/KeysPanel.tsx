/**
 * The key editor and the key print (PRD D4 "the key copy", step 19): `GET /tests/{id}/keys`, one
 * row per question by printed number. Edit sets the accepted answers (`teacher_edit`); Verify
 * confirms a key (`teacher_verified`). Since step 22.4.5 (PRD v8.1) a key change starts no run:
 * the sidecar notes the test in `regrade_pending`, `onKeysChanged` tells the shell, and the thread's
 * top bar shows "Keys changed" with Re-grade; leaving the Key tab starts the one re-grade.
 *
 * Unsure spots in place (step 22.1.5, PRD D27): a key with an open `uncertain_key` is marked
 * "Unsure key" with Keep the key (Accept), Edit (Fix) and Dismiss (Skip); a key entry that matched
 * no question (`key_unmapped`) is a note above the list: attach it to a question (Fix) or discard
 * it (Accept). All through `POST /review/{id}/resolve`.
 *
 * Step R3 (refinements D6, D7): Add key lists the graded questions with no key, by printed number;
 * the key typed for one is a teacher key, and the panel stays open while others have none. Delete
 * asks first, then `DELETE /tests/{id}/keys/{question_id}`; the question simply has no key.
 *
 * The print holds the test's keys only: no student, attempt or answer data.
 */
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { type ApiClient, type Schemas } from "@/api/client";
import { errorText } from "@/lib/errors";
import { accept, fix, itemsOf, resolveItem, skip, str, type Resolution, type ReviewItem } from "@/features/unsure/unsure";
import { SaveAsWord } from "@/components/SaveAsWord";
import { HoverTip } from "@/components/HoverTip";
import { useConfirm } from "@/components/ConfirmDialog";

type Key = Schemas["AnswerKey"];

/** Step 22.5.5b (R22.5.5.6): a check that was cut off or failed twice. */
export const CHECK_NOT_FINISHED = "The check did not finish.";

/** Step 22.6.3 (R22.6.3.3): the checker answered `?`. */
export const CHECK_UNSURE = "The checker was not sure.";

/** What the checker said about an unsure key, for the label's tooltip; null without a check. */
export function checkerTip(check: Key["checker"]): string[] | null {
  if (!check) return null;
  if (check.status === "did_not_finish") return [CHECK_NOT_FINISHED];
  const out = [check.status === "unsure" ? CHECK_UNSURE : `The checker's answer: ${check.answer ?? "?"}`];
  if (check.reasoning) out.push(check.reasoning);
  return out;
}

/** The "AI unsure key" label; with a check, hover or focus shows what the checker said. */
function UnsureLabel({ k, className, testId }: { k: Key; className: string; testId: string }) {
  const tip = checkerTip(k.checker);
  if (!tip) {
    return (
      <span className={className} data-testid={testId}>
        {UNSURE_KEY}
      </span>
    );
  }
  return (
    <HoverTip
      testId={testId}
      tipTestId="key-checker-tip"
      className={className}
      alignEnd
      tip={tip.map((line, i) => (
        <span key={i} className={"block " + (i === 0 ? "font-medium" : "mt-1 text-muted")}>
          {line}
        </span>
      ))}
    >
      {UNSURE_KEY}
    </HoverTip>
  );
}

/** The one label of an unsure key (comment 11). */
export const UNSURE_KEY = "AI unsure key";

/**
 * Where a key comes from (step 22.2.1, comment 11, decision A): "double-checked" means a second
 * AI call agreed with the key. A key read from the key photo and not checked again says so (step
 * 22.5.6, R22.5.6.7). An unsure key has one label only.
 */
export const KEY_STATUS_LABEL: Record<Key["status"], string> = {
  ai_unverified: "AI key · not double-checked",
  ai_verified: "AI key · double-checked",
  from_key_photo: "From the key photo",
  ai_uncertain: UNSURE_KEY,
  teacher_verified: "Teacher",
};

/** Accepted answers typed as `A | B` (or one per comma-free line). */
export function parseAccepted(text: string): string[] {
  return text
    .split("|")
    .map((s) => s.trim())
    .filter(Boolean);
}

export interface KeysPanelProps {
  api: ApiClient;
  testId: string;
  print?: () => void;
  /** After a key change (a PUT or a key Review fix): the test may now need a re-grade. */
  onKeysChanged?: () => void;
  /**
   * Step 22.6.4 (D11, D13): the thread's key run. "making": it is queued or running, so a note shows
   * instead of the keys, which load at once when it ends; "failed": it failed or was discarded, so
   * the empty Key tab says Grade will make the key.
   */
  keyNote?: "making" | "failed" | null;
}

/** The Key tab while the key is being made (R22.6.4.4). */
export const MAKING_KEY = "Making the key…";
/** The empty Key tab after a key run failed or was discarded (R22.6.4.8). */
export const KEY_NOT_MADE = "The key was not made. Grade student answers will make it.";

/** What the delete dialog says after its title (D7). */
export const DELETE_KEY_BODY =
  "The question will have no key, and its explanations go too. A new AI key may be written at the next Grade or Extract Key again. If student answers on this test are graded, that happens when you leave the Key tab.";

const FOCUS_RING = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

/** The key input: Edit on a row, or Add key for a question with no key. */
function KeyEditor({
  label,
  text,
  setText,
  onSave,
  onCancel,
}: {
  label: string;
  text: string;
  setText: (text: string) => void;
  onSave: (accepted: string[]) => void;
  onCancel: () => void;
}) {
  return (
    <form
      data-testid="key-editor"
      className="no-print flex flex-wrap items-center gap-2 pt-1"
      onSubmit={(e) => {
        e.preventDefault();
        const accepted = parseAccepted(text);
        if (accepted.length) onSave(accepted);
      }}
    >
      <input
        autoFocus
        aria-label={label}
        data-testid="key-input"
        // Step 22.5.1 (comment 9): the old value starts selected, so typing replaces it.
        onFocus={(e) => e.currentTarget.select()}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.stopPropagation();
            onCancel();
          }
        }}
        className="flex-1 rounded-paper border border-input bg-surface px-2 py-1"
      />
      <button
        type="submit"
        data-testid="key-save"
        disabled={!parseAccepted(text).length}
        className="rounded-button bg-accent px-2 py-1 text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover disabled:opacity-50"
      >
        Save
      </button>
      {parseAccepted(text).length > 1 && (
        // Each accepted answer, removable (step 22.3.4): a sentence key's forms come from the
        // sidecar; one removed here stays removed while the first answer (the key text) is unchanged.
        <ul data-testid="key-forms" aria-label="Accepted answers" className="flex basis-full flex-wrap gap-1">
          {parseAccepted(text).map((form, i) => (
            <li key={`${i}-${form}`} data-testid="key-form" className="flex items-center gap-1 rounded-paper border border-border px-2 py-0.5 text-sm">
              <span>{form}</span>
              <button
                type="button"
                data-testid="key-form-remove"
                aria-label={`Remove “${form}”`}
                onClick={() => setText(parseAccepted(text).filter((_, j) => j !== i).join(" | "))}
                className="rounded-button px-1 text-muted hover:bg-hover hover:text-text"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}

export function KeysPanel({ api, testId, print, onKeysChanged, keyNote = null }: KeysPanelProps) {
  const [keys, setKeys] = useState<Key[] | null>(null);
  const [numbers, setNumbers] = useState<Map<string, number>>(new Map());
  /** Question id → the paper's printed number, the one shown (D10 v6.0); `numbers` orders the rows. */
  const [printed, setPrinted] = useState<Map<string, number>>(new Map());
  /** The question ids of the graded sections, in test order: the ones Add key can offer (D6). */
  const [graded, setGraded] = useState<string[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  /** Add key is open; `editing` then holds the question picked from its list. */
  const [adding, setAdding] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState<ReviewItem[]>([]);
  const [reload, setReload] = useState(0);
  const [attachTo, setAttachTo] = useState<Record<string, string>>({});
  const confirm = useConfirm();
  const addPanelId = useId();
  const addHeadingId = useId();
  const addButton = useRef<HTMLButtonElement>(null);
  const addList = useRef<HTMLUListElement>(null);
  const printButton = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  /** A save or delete removes the focused control: focus moves on once the keys have changed. */
  const moveFocus = useRef(false);

  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([
      api.get("/tests/{id}/keys", { path: { id: testId }, signal: ctrl.signal }),
      api.get("/tests/{id}", { path: { id: testId }, signal: ctrl.signal }),
    ])
      .then(([k, t]) => {
        const map = new Map<string, number>();
        const shown = new Map<string, number>();
        const inGraded: string[] = [];
        t.content.sections.forEach((s) =>
          s.groups.forEach((g) =>
            g.questions.forEach((q) => {
              map.set(q.id, q.number);
              shown.set(q.id, q.printed_number);
              if (s.graded !== false) inGraded.push(q.id);
            }),
          ),
        );
        setNumbers(map);
        setPrinted(shown);
        setGraded(inGraded);
        setKeys(k);
        setReview(t.review ?? []);
      })
      .catch((err: unknown) => {
        if (!ctrl.signal.aborted) setError(errorText(err));
      });
    return () => ctrl.abort();
    // keyNote: the keys load again, all at once, when the key run ends (R22.6.4.4)
  }, [api, testId, reload, keyNote]);

  useEffect(() => {
    if (!moveFocus.current) return;
    moveFocus.current = false;
    // A key still being typed elsewhere keeps its place: the caret goes to the end of the text.
    const input = panel.current?.querySelector<HTMLInputElement>("form input");
    if (input) {
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
      return;
    }
    (addList.current?.querySelector("button") ?? addButton.current ?? printButton.current)?.focus();
  }, [keys]);

  /**
   * Resolve a question's open items: each run that missed its key adds one. The extra ones are
   * skipped first and `body` goes to the last, so the key is written once, as the final step: a
   * second Fix would overwrite the sentence forms the first one made. On a failure the key is
   * untouched and the editor stays, so Save tries again with the items still open. True when all
   * were resolved.
   */
  const settle = useCallback(
    async (items: ReviewItem[], body: Resolution) => {
      setError(null);
      let closed = 0;
      try {
        for (const [i, item] of items.entries()) {
          await resolveItem(api, item.id, i === items.length - 1 ? body : skip());
          closed += 1;
        }
        setEditing(null);
        onKeysChanged?.();
        return true;
      } catch (err) {
        setError(errorText(err));
        return false;
      } finally {
        if (closed) setReload((n) => n + 1);
      }
    },
    [api, onKeysChanged],
  );
  const unsureKeys = itemsOf(review, "uncertain_key");
  const unmapped = itemsOf(review, "key_unmapped");

  /** True when the key was saved. */
  const put = useCallback(
    async (questionId: string, body: Schemas["KeyPut"]) => {
      setError(null);
      const open = unsureKeys.filter((i) => i.question_id === questionId);
      if (open.length && body.accepted) return settle(open, fix(body.accepted));
      if (open.length && body.verify) return settle(open, accept());
      try {
        const res = await api.put("/tests/{id}/keys/{question_id}", {
          path: { id: testId, question_id: questionId },
          body,
        });
        setKeys((list) => {
          if (!list) return null;
          if (!list.some((k) => k.question_id === questionId)) return [...list, res.key]; // Add key
          return list.map((k) => (k.question_id === questionId ? res.key : k));
        });
        setEditing(null);
        if (res.outcome !== "unchanged") onKeysChanged?.();
        return true;
      } catch (err) {
        setError(errorText(err));
        return false;
      }
    },
    [api, onKeysChanged, settle, testId, unsureKeys],
  );

  /** Open `uncertain_key` items on the question go through `put`'s `settle`, so they close too. */
  const saveAdded = async (questionId: string, accepted: string[]) => {
    moveFocus.current = true;
    if (!(await put(questionId, { accepted, verify: false }))) moveFocus.current = false;
  };

  const startEdit = (k: Key) => {
    setAdding(false);
    setText(k.accepted.join(" | "));
    setEditing(k.question_id);
  };

  const closeAdd = () => {
    addButton.current?.focus();
    setAdding(false);
    setEditing(null);
  };

  // While the key is being made, a short note instead of the keys (R22.6.4.4, D11).
  if (keyNote === "making") {
    return (
      <p role="status" data-testid="key-making" className="text-muted">
        {MAKING_KEY}
      </p>
    );
  }
  if (!keys) {
    return error ? <p role="alert" className="text-danger">{error}</p> : <p className="text-muted">Loading…</p>;
  }
  const order = (k: Key) => numbers.get(k.question_id) ?? 0;
  const num = (k: Key) => printed.get(k.question_id) ?? 0;
  const rows = [...keys].sort((a, b) => order(a) - order(b));
  const keyed = new Set(keys.map((k) => k.question_id));
  const noKey = graded.filter((id) => !keyed.has(id));
  const addOpen = adding && noKey.length > 0;
  const picked = addOpen && editing && noKey.includes(editing) ? editing : null;
  const shownNumber = (id: string) => printed.get(id) ?? numbers.get(id) ?? 0;

  const removeKey = async (k: Key) => {
    setError(null);
    const ok = await confirm({
      title: `Delete the key for question ${shownNumber(k.question_id)}?`,
      body: DELETE_KEY_BODY,
      confirmLabel: "Delete key",
      cancelLabel: "Keep key",
      tone: "danger",
    });
    if (!ok) return;
    moveFocus.current = true;
    try {
      await api.delete("/tests/{id}/keys/{question_id}", { path: { id: testId, question_id: k.question_id } });
      // Only this question's editor goes: a key being typed for another question stays.
      setEditing((id) => (id === k.question_id ? null : id));
      if (!noKey.length) setAdding(false); // an Add key left open by its last save does not come back
      setReload((n) => n + 1);
      onKeysChanged?.();
    } catch (err) {
      moveFocus.current = false;
      setError(errorText(err));
    }
  };

  return (
    <div ref={panel} data-testid="keys-panel" className="flex flex-col gap-3">
      <div className="no-print flex flex-wrap items-center gap-3" data-testid="keys-toolbar">
        <button
          type="button"
          ref={printButton}
          data-testid="key-print"
          onClick={() => (print ?? (() => window.print()))()}
          className="main-label rounded-button border border-border px-3 py-1 hover:bg-hover"
        >
          Print key
        </button>
        <SaveAsWord
          what="key"
          testId="key-save-docx"
          save={() => api.post("/tests/{id}/export", { path: { id: testId }, body: { what: "key" } })}
        />
        {noKey.length > 0 && (
          <button
            type="button"
            ref={addButton}
            data-testid="key-add"
            aria-expanded={addOpen}
            aria-controls={addOpen ? addPanelId : undefined}
            onClick={() => {
              setEditing(null);
              setAdding(!addOpen);
            }}
            className={`main-label rounded-button border border-border px-3 py-1 hover:bg-hover ${FOCUS_RING}`}
          >
            Add key
          </button>
        )}
      </div>
      {error && <p role="alert" className="no-print text-danger">{error}</p>}
      {addOpen && (
        <div
          id={addPanelId}
          data-testid="key-add-panel"
          className="no-print flex flex-col gap-2 rounded-paper border border-border p-2"
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.stopPropagation();
              closeAdd();
            }
          }}
        >
          <div className="flex items-center gap-2">
            <p id={addHeadingId} className="flex-1 text-muted">
              Questions with no key
            </p>
            <button
              type="button"
              data-testid="key-add-close"
              onClick={closeAdd}
              className={`rounded-button px-2 text-muted hover:bg-hover hover:text-text ${FOCUS_RING}`}
            >
              Close
            </button>
          </div>
          <ul ref={addList} aria-labelledby={addHeadingId} data-testid="key-add-list" className="flex flex-wrap gap-1">
            {noKey.map((id) => (
              <li key={id}>
                <button
                  type="button"
                  data-testid="key-add-question"
                  data-question-id={id}
                  aria-label={`Question ${shownNumber(id)}`}
                  aria-pressed={picked === id}
                  onClick={() => {
                    if (picked === id) return; // the key typed so far stays
                    setText("");
                    setEditing(id);
                  }}
                  className={
                    "min-h-9 min-w-9 rounded-button border px-2 hover:bg-hover " +
                    (picked === id ? "border-text bg-hover font-semibold " : "border-border ") +
                    FOCUS_RING
                  }
                >
                  {shownNumber(id)}
                </button>
              </li>
            ))}
          </ul>
          {picked && (
            <>
              <p className="text-muted">Type the key for question {shownNumber(picked)}. Put | between accepted forms.</p>
              <KeyEditor
                key={picked}
                label={`Key for question ${shownNumber(picked)}`}
                text={text}
                setText={setText}
                onSave={(accepted) => void saveAdded(picked, accepted)}
                onCancel={closeAdd}
              />
            </>
          )}
        </div>
      )}
      {unmapped.map((i) => (
        <div key={i.id} data-testid="key-unmapped" className="no-print flex flex-wrap items-center gap-2 rounded-paper border border-border bg-unsure/15 p-2">
          <span className="flex-1">
            A key entry matched no question: “{str(i.proposal.label) ?? "?"}” = “{str(i.proposal.answer) ?? ""}”.
          </span>
          <label className="flex items-center gap-1">
            <span className="sr-only">Question for this entry</span>
            <select
              data-testid="key-unmapped-question"
              value={attachTo[i.id] ?? ""}
              onChange={(e) => setAttachTo((m) => ({ ...m, [i.id]: e.target.value }))}
              className="rounded-paper border border-input bg-surface px-2 py-0.5"
            >
              <option value="">Choose a question…</option>
              {[...numbers.entries()]
                .sort((a, b) => a[1] - b[1])
                .map(([qid, n]) => (
                  <option key={qid} value={qid}>
                    Question {printed.get(qid) ?? n}
                  </option>
                ))}
            </select>
          </label>
          <button
            type="button"
            disabled={!attachTo[i.id]}
            onClick={() => void settle([i], fix(attachTo[i.id]))}
            className="rounded-button border border-border px-2 py-0.5 hover:bg-hover disabled:opacity-50"
          >
            Attach
          </button>
          <button type="button" onClick={() => void settle([i], accept())} className="rounded-button border border-border px-2 py-0.5 hover:bg-hover">
            Discard the entry
          </button>
        </div>
      ))}
      <h3 className="hidden font-serif text-lg print:block">Key</h3>
      <ol data-testid="key-list" className="flex flex-col gap-1">
        {rows.map((k) => (
          <li
            key={k.question_id}
            data-testid="key-row"
            data-question-id={k.question_id}
            data-status={k.status}
            className="print-break-inside-avoid rounded-paper border border-transparent px-2 py-1 hover:border-border"
            onDoubleClick={(e) => {
              // A double-click edits the row (comment 10); the Edit button stays for the keyboard.
              if (editing === k.question_id || (e.target as HTMLElement).closest("button, form")) return;
              startEdit(k);
            }}
          >
            <div className="flex items-center gap-3">
              <span className="w-8 text-right text-muted">{num(k)}.</span>
              <span className="flex-1" data-testid="key-accepted">
                {k.accepted.join(" | ")}
              </span>
              {/* An open unsure note carries the row's one unsure label; the source label steps aside. */}
              {!(unsureKeys.some((i) => i.question_id === k.question_id) && k.status === "ai_uncertain") && (
                k.status === "ai_uncertain" && k.checker ? (
                  <span className="no-print">
                    <UnsureLabel k={k} testId="key-status" className="text-xs text-muted" />
                  </span>
                ) : (
                  <span className="no-print text-xs text-muted" data-testid="key-status">
                    {KEY_STATUS_LABEL[k.status]}
                  </span>
                )
              )}
              {unsureKeys.some((i) => i.question_id === k.question_id) && (
                <span className="no-print flex items-center gap-1" data-testid="key-unsure">
                  <UnsureLabel k={k} testId="key-unsure-label" className="text-xs font-semibold mark-label" />
                  <button
                    type="button"
                    data-testid="key-skip"
                    title="Close this note without changing anything"
                    onClick={() => void settle(unsureKeys.filter((i) => i.question_id === k.question_id), skip())}
                    className="rounded-button px-2 text-muted hover:bg-hover hover:text-text"
                  >
                    Dismiss
                  </button>
                </span>
              )}
              <span className="no-print flex gap-1">
                <button
                  type="button"
                  data-testid="key-edit"
                  onClick={() => startEdit(k)}
                  className="rounded-button px-2 text-muted hover:bg-hover hover:text-text"
                >
                  Edit
                </button>
                <button
                  type="button"
                  data-testid="key-delete"
                  aria-label={`Delete the key for question ${num(k)}`}
                  onClick={() => void removeKey(k)}
                  className={`rounded-button px-2 text-muted hover:bg-hover hover:text-text ${FOCUS_RING}`}
                >
                  Delete
                </button>
                {(k.status !== "teacher_verified" || unsureKeys.some((i) => i.question_id === k.question_id)) && (
                  <button
                    type="button"
                    data-testid="key-verify"
                    onClick={() => void put(k.question_id, { verify: true })}
                    className="rounded-button px-2 text-accent-strong hover:bg-hover"
                  >
                    Verify
                  </button>
                )}
              </span>
            </div>
            {editing === k.question_id && (
              <KeyEditor
                label={`Key for question ${num(k)}`}
                text={text}
                setText={setText}
                onSave={(accepted) => void put(k.question_id, { accepted, verify: false })}
                onCancel={() => setEditing(null)}
              />
            )}
          </li>
        ))}
      </ol>
      {rows.length === 0 && (
        <p className="text-muted" data-testid={keyNote === "failed" ? "key-not-made" : undefined}>
          {keyNote === "failed" ? KEY_NOT_MADE : "No keys yet: grade the test or add a key."}
        </p>
      )}
    </div>
  );
}
