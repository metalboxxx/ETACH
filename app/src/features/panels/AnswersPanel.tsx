/**
 * The answers panel (PRD §10.1): per question, the value read and a ✓/✗/? mark (placeholders
 * until grading, steps 17+). Clicking a row opens the override editor →
 * `PUT /attempts/{id}/answers/{question_id}` (`teacher_override`, version + 1, re-grade).
 *
 * Unsure spots in place (step 22.1.5, PRD D27): a row with an open `uncertain_answer` or
 * `box_inline_conflict` is marked "Unsure" with its actions: Keep / Use the box value (Accept),
 * editing the row (Fix) and Dismiss (Skip), all through `POST /review/{id}/resolve`. An answers
 * page the app could not read fully (attempt-level `validator_failed`) is a note at the top.
 *
 * Override states (data-model §2.5): `null` = no override; `""` = the teacher confirmed a blank;
 * any other text = the teacher's value. "Confirm blank" sends `""`.
 */
import { useCallback, useEffect, useId, useState } from "react";
import { type ApiClient, type Schemas } from "@/api/client";
import { errorText } from "@/lib/errors";
import { todayIso } from "@/lib/skills";
import { accept, fix, itemsOf, resolveItem, skip, str, type Resolution, type ReviewItem } from "@/features/unsure/unsure";

type Answer = Schemas["Answer"];
type Test = Schemas["TestWithPaths"];

export type OverrideState = "none" | "blank" | "value";

export function overrideState(a: Pick<Answer, "teacher_override">): OverrideState {
  if (a.teacher_override === null || a.teacher_override === undefined) return "none";
  return a.teacher_override === "" ? "blank" : "value";
}

/** The one label of an unsure student answer (comment 11): it replaces the bare "?". */
export const UNSURE_STUDENT_ANSWER = "AI unsure student answer";

/** An uncertain grade's label (the teacher's answer 2, step 22.2.7): no bare "?" verdict. */
export const UNSURE_GRADE = "AI unsure grade";

/** An unsure reading the teacher has not overridden. */
export function readingUnsure(a: Answer): boolean {
  return Boolean(a.reading_unsure) && overrideState(a) === "none";
}

/** The ✓ and ✗ marks on small badges (PRD §10.1 v8.13): ✓ on green with dark text, ✗ on brick
 *  with white text; the mark itself stays, so colour never carries the meaning alone. On paper
 *  the badge is dropped and the mark prints black. Other marks are plain text. */
export function MarkBadge({ mark }: { mark: string }) {
  const badge = "inline-block min-w-5 rounded-full px-1 text-center leading-5 font-semibold print:bg-transparent print:text-text";
  if (mark === "✓") return <span data-badge="correct" className={badge + " bg-correct text-text"}>✓</span>;
  if (mark === "✗") return <span data-badge="wrong" className={badge + " bg-wrong text-on-wrong"}>✗</span>;
  return <>{mark}</>;
}

/** ✓ / ✗ / "AI unsure grade" from the verdict; "–" before grading (an unsure reading shows its label instead). */
export function answerMark(a: Answer): string {
  switch (a.verdict) {
    case "correct":
      return "✓";
    case "incorrect":
      return "✗";
    case "uncertain":
      return UNSURE_GRADE;
    default:
      return "–";
  }
}

export interface AnswersPanelProps {
  api: ApiClient;
  attemptId: string;
  testId: string;
  /** Called after an override is saved. */
  onChanged?: () => void;
}

/** The quiet line on the Student answers tab when the listening part was left out (R22.5.6.7). */
export function listeningLine({ first, last }: Schemas["ListeningSkipped"]): string {
  return first === last ? `Listening (question ${first}) left out` : `Listening (questions ${first}–${last}) left out`;
}

export function AnswersPanel({ api, attemptId, testId, onChanged }: AnswersPanelProps) {
  const [answers, setAnswers] = useState<Answer[] | null>(null);
  const [test, setTest] = useState<Test | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  /** Step 22.5.5b (D11a): the stored date taken and the field's text; a change saves on blur or Enter. */
  const [takenOn, setTakenOn] = useState<string | null>(null);
  const [dateText, setDateText] = useState("");
  const [dateSaved, setDateSaved] = useState(false);
  /** Step 22.5.6 (R22.5.6.7): the printed range left out as listening, if any. */
  const [listening, setListening] = useState<Schemas["ListeningSkipped"] | null>(null);
  const dateId = useId();

  const saveDate = useCallback(async () => {
    if (!dateText || dateText === takenOn) return;
    setError(null);
    setDateSaved(false);
    try {
      const a = await api.patch("/attempts/{id}", { path: { id: attemptId }, body: { taken_on: dateText } });
      setTakenOn(a.taken_on ?? dateText);
      setDateSaved(true);
    } catch (err) {
      setError(errorText(err));
    }
  }, [api, attemptId, dateText, takenOn]);

  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([
      api.get("/attempts/{id}", { path: { id: attemptId }, signal: ctrl.signal }),
      api.get("/tests/{id}", { path: { id: testId }, signal: ctrl.signal }),
    ])
      .then(([a, t]) => {
        setAnswers(a.answers);
        setTest(t);
        setTakenOn(a.attempt.taken_on ?? null);
        setDateText(a.attempt.taken_on ?? "");
        setListening(a.listening_skipped ?? null);
      })
      .catch((err: unknown) => {
        if (!ctrl.signal.aborted) setError(errorText(err));
      });
    return () => ctrl.abort();
  }, [api, attemptId, testId, reload]);

  const items = itemsOf(test?.review, ["uncertain_answer", "box_inline_conflict", "validator_failed"], { attemptId });

  const settle = useCallback(
    async (item: ReviewItem, body: Resolution) => {
      setError(null);
      try {
        await resolveItem(api, item.id, body);
        setEditing(null);
        setReload((n) => n + 1);
        onChanged?.();
      } catch (err) {
        setError(errorText(err));
      }
    },
    [api, onChanged],
  );

  const save = useCallback(
    async (questionId: string, value: string) => {
      setError(null);
      const open = items.find((i) => i.question_id === questionId && i.kind !== "validator_failed");
      if (open) return settle(open, fix(value));
      try {
        const res = await api.put("/attempts/{id}/answers/{question_id}", {
          path: { id: attemptId, question_id: questionId },
          body: { value },
        });
        setAnswers((list) => list?.map((a) => (a.question_id === questionId ? res.answer : a)) ?? null);
        setEditing(null);
        onChanged?.();
      } catch (err) {
        setError(errorText(err));
      }
    },
    [api, attemptId, items, onChanged, settle],
  );

  if (!answers) {
    return error ? <p role="alert" className="text-danger">{error}</p> : <p className="text-muted">Loading…</p>;
  }

  // Question order and numbers come from the test; answers without a question keep their own order.
  // Rows are ordered by the internal number; the paper's printed number is shown (D10 v6.0).
  const order = new Map<string, number>();
  const printed = new Map<string, number>();
  test?.content.sections.forEach((s) =>
    s.groups.forEach((g) =>
      g.questions.forEach((q) => {
        order.set(q.id, q.number);
        printed.set(q.id, q.printed_number);
      }),
    ),
  );
  const rows = [...answers].sort(
    (a, b) => (order.get(a.question_id) ?? a.printed_number) - (order.get(b.question_id) ?? b.printed_number),
  );

  return (
    <div data-testid="answers-panel" className="flex flex-col gap-1">
      <div className="no-print flex flex-wrap items-center gap-2 pb-1 text-sm" data-testid="answers-date">
        <label htmlFor={dateId} className="text-muted">
          Date taken
        </label>
        <input
          id={dateId}
          type="date"
          data-testid="answers-taken-on"
          value={dateText}
          max={todayIso()}
          onChange={(e) => {
            setDateText(e.target.value);
            setDateSaved(false);
          }}
          onBlur={() => void saveDate()}
          onKeyDown={(e) => {
            if (e.key === "Enter") void saveDate();
          }}
          className="rounded-paper border border-input bg-surface px-2 py-0.5 text-text"
        />
        <span role="status" aria-live="polite" className="text-xs text-muted" data-testid="answers-date-status">
          {dateSaved ? "Date saved" : ""}
        </span>
      </div>
      {listening && (
        <p className="pb-1 text-xs text-muted" data-testid="answers-listening">
          {listeningLine(listening)}
        </p>
      )}
      {error && <p role="alert" className="text-danger">{error}</p>}
      {items
        .filter((i) => i.kind === "validator_failed")
        .map((i) => (
          <div key={i.id} data-testid="answers-note" className="flex flex-wrap items-center gap-2 rounded-paper border border-border bg-unsure/15 p-2">
            <span className="flex-1">
              {typeof i.proposal.page_no === "number" ? `Page ${i.proposal.page_no}: ` : ""}
              the app could not read all the student answers on this page. Check them against the photo.
            </span>
            <button type="button" onClick={() => void settle(i, accept())} className="rounded-button border border-border px-2 py-0.5 hover:bg-hover">
              Keep as is
            </button>
          </div>
        ))}
      {rows.map((a) => (
        <AnswerRow
          item={items.find((i) => i.question_id === a.question_id && i.kind !== "validator_failed")}
          onSettle={(item, body) => void settle(item, body)}
          key={a.question_id}
          answer={a}
          number={printed.get(a.question_id) ?? a.printed_number}
          editing={editing === a.question_id}
          onEdit={() => setEditing(a.question_id)}
          onCancel={() => setEditing(null)}
          onSave={(v) => void save(a.question_id, v)}
        />
      ))}
      {rows.length === 0 && <p className="text-muted">No student answers were read.</p>}
    </div>
  );
}

export function AnswerRow({
  item,
  onSettle,
  answer,
  number,
  editing,
  onEdit,
  onCancel,
  onSave,
}: {
  /** The row's open unsure item (uncertain_answer or box_inline_conflict), if any. */
  item?: ReviewItem;
  onSettle?: (item: ReviewItem, body: Resolution) => void;
  answer: Answer;
  number: number;
  editing: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onSave: (value: string) => void;
}) {
  const state = overrideState(answer);
  const [text, setText] = useState("");
  const read = answer.value ?? "";
  let shown: string;
  if (state === "blank") shown = "(blank, confirmed)";
  else if (state === "value") shown = answer.teacher_override ?? "";
  else shown = read === "" ? "(blank)" : read;
  const startEdit = () => {
    setText(state === "value" ? (answer.teacher_override ?? "") : read);
    onEdit();
  };

  return (
    <div
      data-testid="answer-row"
      data-question-id={answer.question_id}
      data-override={state}
      data-unsure={item ? item.kind : undefined}
      className={"rounded-paper border " + (item ? "border-border bg-unsure/15" : "border-transparent hover:border-border")}
    >
      {/* Content first; the source and the actions on the right, like the Key rows (comment 14).
          A double-click edits the row; the Edit button stays for the keyboard (comment 10). */}
      <div
        data-testid="answer-line"
        onDoubleClick={(e) => {
          if (editing || (e.target as HTMLElement).closest("button")) return;
          startEdit();
        }}
        className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-2 py-1 text-left"
      >
        <span className="w-8 text-right text-muted">{number}.</span>
        <span className="flex-1" data-testid="answer-value">
          {shown}
        </span>
        {state !== "none" && (
          <span className="text-xs text-muted" title={state === "value" ? `Read: ${read || "(blank)"}` : undefined}>
            edited
          </span>
        )}
        {!item && readingUnsure(answer) && (
          <span data-testid="answer-unsure-label" className="text-xs font-semibold mark-label">
            {UNSURE_STUDENT_ANSWER}
          </span>
        )}
        <span
          data-testid="answer-mark"
          className={
            answer.verdict === "uncertain"
              ? "whitespace-nowrap text-xs font-semibold mark-label"
              : "w-5 text-center"
          }
        >
          {readingUnsure(answer) && answerMark(answer) === "–" ? "" : <MarkBadge mark={answerMark(answer)} />}
        </span>
      {item && !editing && (
        <span data-testid="answer-unsure" className="flex flex-wrap items-center gap-1" title="Check it against the photo">
          <span className="text-xs font-semibold mark-label">
            {item.kind === "box_inline_conflict"
              ? `${UNSURE_STUDENT_ANSWER}: the box says “${str(item.proposal.box_value) ?? ""}”, the line says “${str(item.proposal.inline_value) ?? ""}”`
              : UNSURE_STUDENT_ANSWER}
          </span>
          <button
            type="button"
            data-testid="answer-accept"
            onClick={() => onSettle?.(item, accept())}
            className="rounded-button border border-border px-2 py-0.5 hover:bg-hover"
          >
            {item.kind === "box_inline_conflict" ? "Use the box value" : `Keep “${read || "(blank)"}”`}
          </button>
          <button
            type="button"
            data-testid="answer-skip"
            title="Close this note without changing anything"
            onClick={() => onSettle?.(item, skip())}
            className="rounded-button px-2 py-0.5 text-muted hover:bg-hover hover:text-text"
          >
            Dismiss
          </button>
        </span>
      )}
        <button
          type="button"
          data-testid="answer-edit"
          onClick={startEdit}
          aria-label={`Edit question ${number}: ${shown}`}
          className="rounded-button px-2 text-muted hover:bg-hover hover:text-text focus-visible:outline-2 focus-visible:outline-focus"
        >
          Edit
        </button>
      </div>
      {editing && (
        <form
          data-testid="answer-editor"
          className="flex items-center gap-2 px-2 pb-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim()) onSave(text);
          }}
        >
          <input
            autoFocus
            aria-label={`Answer for question ${number}`}
            data-testid="answer-input"
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
            data-testid="answer-save"
            disabled={!text.trim()}
            className="rounded-button bg-accent px-2 py-1 text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover disabled:opacity-50"
          >
            Save
          </button>
          <button
            type="button"
            data-testid="answer-confirm-blank"
            onClick={() => onSave("")}
            className="rounded-button border border-border px-2 py-1 hover:bg-hover"
          >
            Confirm blank
          </button>
          <button type="button" onClick={onCancel} className="px-2 py-1 text-muted hover:text-text">
            Cancel
          </button>
        </form>
      )}
    </div>
  );
}
