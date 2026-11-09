/**
 * The extraction card (PRD §10.1): the `run_card` message of an extract run. Its heading names
 * what was extracted (step 22.1.1, comment 16): "Extracted: <student> · <test display name>", the
 * unsure count, the student chip, [Test] and [Answers] (open the artifact panel), [Key] (the key
 * editor and the key print) and [Grade] (a grade run, step 19; a blank test is graded with
 * `attempt_id: null`, which makes its key copy).
 *
 * The body is what `graphs/extract.py` stores: `{run_id, test_id, attempt_id, unsure_count,
 * no_answers, duplicate, student_name_read}`. The student comes from the thread's current attempt
 * (`GET /threads/{id}`: `attempt`, `student`), used only when it is the card's attempt.
 *
 * The student chip (step 22.1.1, comments 4 and 11): its picker closes on a click outside or on
 * Escape; the teacher can assign an existing student, create one from the name read on paper or
 * from a typed name, and edit the assigned student's name and class (`PATCH /students/{id}`; the
 * class since step 22.2.3).
 *
 * Photos (step 22.1.4, comment 3): the card shows a thumbnail per page of the photos the run read
 * (`CardPhotos`); a thumbnail opens that page beside the test (or beside the answers when the test
 * came from another student's photos). The buttons sit under "Open beside the photos", so the
 * teacher knows where the photos are. After a merge, Test and Key open the merged-into test.
 *
 * Unsure spots in place (step 22.1.5, PRD D27): a possible duplicate (merge preview, then Merge),
 * a picked test that does not match (Extract again without the pick) and answers left without a
 * question after a merge (move them, or leave them ungraded) are notes on the card; an unknown
 * student is settled on the student chip. The unsure-answer count is live from the open items.
 */
import { useEffect, useId, useRef, useState } from "react";
import { type ApiClient, type Schemas } from "@/api/client";
import type { PanelView } from "@/features/panels/panelView";
import { useDismiss } from "@/hooks/useDismiss";
import { useTestName } from "@/hooks/useTestName";
import { nameSearch } from "@/lib/names";
import { CardPhotos, useCardPhotos } from "./CardPhotos";
import { MergePreview } from "./MergePreview";
import { accept, fix, itemsOf, resolveItem, skip, str, type Resolution, type ReviewItem } from "@/features/unsure/unsure";
import { errorText } from "@/lib/errors";

type Student = Schemas["Student"];

export interface RunCardBody {
  run_id?: string;
  test_id?: string | null;
  attempt_id?: string | null;
  unsure_count?: number;
  no_answers?: boolean;
  duplicate?: boolean;
  student_name_read?: string | null;
}

export interface ExtractionCardProps {
  api: ApiClient;
  body: RunCardBody;
  /** The thread's current attempt (may be another attempt than the card's). */
  attempt: Schemas["Attempt"] | null;
  /** The current attempt's student (`GET /threads/{id}` `student`). */
  student?: Student | null;
  /** The test's display name (`GET /threads/{id}` `test_display_name`) when it is the card's test. */
  testName?: string | null;
  onOpenPanel?: (view: PanelView) => void;
  /** After the teacher changed something here (the student): reload the thread. */
  onChanged?: () => void;
  /** The thread (for the grade run). */
  threadId?: string | null;
  /** After the grade run was created (the running indicator shows it). */
  onRunStarted?: (run: Schemas["Run"]) => void;
  /** Changes on the thread's run events: reload the photos (and a merge's target). */
  refreshKey?: number;
}

export function ExtractionCard({
  api,
  body,
  attempt,
  student = null,
  testName = null,
  onOpenPanel,
  onChanged,
  threadId,
  onRunStarted,
  refreshKey = 0,
}: ExtractionCardProps) {
  const attemptId = body.attempt_id ?? null;
  const current = attempt && attempt.id === attemptId ? attempt : null;
  const photos = useCardPhotos(api, body.test_id ?? null, attemptId, refreshKey);
  // After a merge the card's stored test is the merged-away one: its attempt moved to the test it
  // was merged into (the thread's current attempt says so), or the test names it in `merged_into`.
  const testId = current?.test_id ?? photos.testId ?? body.test_id ?? null;
  const ids = useId();
  const cardStudent = current?.student_id && student?.id === current.student_id ? student : null;
  const what = testName ?? testId ?? "the test";
  const live = photos.review.length > 0 || photos.testId !== null;
  const unsure = live
    ? itemsOf(photos.review, ["uncertain_answer", "box_inline_conflict"], { attemptId }).length
    : (body.unsure_count ?? 0);
  const cardItems = itemsOf(photos.review, ["possible_duplicate", "picked_test_mismatch", "merge_unaligned"]).filter(
    (i) => i.kind === "possible_duplicate" || i.attempt_id === attemptId,
  );
  const studentItem = attemptId ? itemsOf(photos.review, "unknown_student", { attemptId })[0] : undefined;
  const [noteError, setNoteError] = useState<string | null>(null);
  const settle = async (item: ReviewItem, resolution: Resolution) => {
    setNoteError(null);
    try {
      await resolveItem(api, item.id, resolution);
      onChanged?.();
    } catch (err) {
      setNoteError(errorText(err));
    }
  };
  const [grading, setGrading] = useState(false);
  const [gradeError, setGradeError] = useState<string | null>(null);

  // [Grade]: a grade run for this attempt, or for the blank test alone (its key copy, D4).
  const grade = async () => {
    if (!threadId || !testId || grading) return;
    setGrading(true);
    setGradeError(null);
    try {
      const run = await api.post("/threads/{id}/runs", {
        path: { id: threadId },
        // No answers read: the blank test alone is graded (its key copy, D4), not the empty attempt.
        body: { kind: "grade", input: { test_id: testId, attempt_id: body.no_answers ? null : attemptId, reason: "button" } },
      });
      onRunStarted?.(run);
    } catch (err) {
      setGradeError(errorText(err));
    } finally {
      setGrading(false);
    }
  };

  return (
    <div
      data-testid="extraction-card"
      data-attempt-id={attemptId ?? ""}
      className="flex flex-col gap-3 rounded-paper border border-border bg-surface p-4 text-sm text-text"
    >
      <h2 data-testid="extraction-heading" className="font-semibold text-text">
        <span aria-hidden="true" className="mark-label">
          ✓{" "}
        </span>
        Extracted: {cardStudent ? `${what} · ${cardStudent.full_name}` : what}
      </h2>
      <div className="flex flex-wrap items-center gap-3">
        {attemptId ? (
          <span data-testid="unsure-count" data-count={unsure} className={unsure ? "mark-label font-semibold" : "text-muted"}>
            {unsure === 1 ? "1 AI unsure student answer" : `${unsure} AI unsure student answers`}
          </span>
        ) : (
          <span className="text-muted" data-testid="no-answers">
            {body.duplicate && testId ? `No student answers found; ${testId} is already in the bank` : "No student answers found"}
          </span>
        )}
        {attemptId && (
          <StudentChip
            api={api}
            attemptId={attemptId}
            studentId={current?.student_id ?? null}
            student={cardStudent}
            nameRead={current?.student_name_read ?? body.student_name_read ?? null}
            item={studentItem}
            onChanged={onChanged}
          />
        )}
      </div>
      {cardItems.map((item) => (
        <CardNote key={item.id} api={api} item={item} onSettle={(r) => void settle(item, r)} />
      ))}
      {noteError && (
        <p role="alert" className="text-danger">
          {noteError}
        </p>
      )}
      {photos.thumbs.length > 0 && <CardPhotos api={api} thumbs={photos.thumbs} onOpen={onOpenPanel} />}
      <div className="flex flex-wrap items-center gap-2">
        {testId && (
          <div role="group" aria-labelledby={`${ids}-open`} className="flex flex-wrap items-center gap-2">
            <span id={`${ids}-open`} className="text-muted">
              Open beside the photos:
            </span>
            <button
              type="button"
              data-testid="card-open-test"
              aria-describedby={`${ids}-test`}
              onClick={() => onOpenPanel?.({ kind: "test", testId })}
              className={openButton}
            >
              Test
            </button>
            <span id={`${ids}-test`} hidden>
              Opens the test beside its original photos
            </span>
            {attemptId && (
              <>
                <button
                  type="button"
                  data-testid="card-open-answers"
                  aria-describedby={`${ids}-answers`}
                  onClick={() => onOpenPanel?.({ kind: "answers", attemptId, testId })}
                  className={openButton}
                >
                  Student answers
                </button>
                <span id={`${ids}-answers`} hidden>
                  Opens the student answers read from the paper beside the student&apos;s photos
                </span>
              </>
            )}
            <button
              type="button"
              data-testid="card-open-keys"
              aria-describedby={`${ids}-keys`}
              onClick={() => onOpenPanel?.({ kind: "keys", testId })}
              className={openButton}
            >
              Key
            </button>
            <span id={`${ids}-keys`} hidden>
              Opens the key beside the test&apos;s photos
            </span>
          </div>
        )}
        <button
          type="button"
          data-testid="card-grade"
          disabled={!threadId || !testId || grading}
          onClick={() => void grade()}
          title={attemptId ? "Grade this attempt" : "Make the key copy of this blank test"}
          className="ml-auto rounded-button bg-accent px-3 py-1 text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover disabled:opacity-50"
        >
          Grade
        </button>
      </div>
      {gradeError && (
        <p role="alert" className="text-danger">
          {gradeError}
        </p>
      )}
    </div>
  );
}

/** One unsure spot that belongs on the card. */
export function CardNote({ api, item, onSettle }: { api: ApiClient; item: ReviewItem; onSettle: (r: Resolution) => void }) {
  const [previewing, setPreviewing] = useState(false);
  const [target, setTarget] = useState("");
  const otherId = item.kind === "possible_duplicate" ? str(item.proposal.best_test_id) : null;
  // Step 22.5.1 (comment 8): the notice names the other test with its id, which the Tests search finds.
  const otherName = useTestName(api, otherId);
  const note = "flex flex-col gap-2 rounded-paper border border-border bg-unsure/15 p-2";
  const button = "rounded-button border border-border px-2 py-0.5 hover:bg-hover disabled:opacity-50";
  const dismiss = (
    <button type="button" data-testid="card-note-skip" title="Close this note without changing anything" onClick={() => onSettle(skip())} className="rounded-button px-2 py-0.5 text-muted hover:bg-hover hover:text-text">
      Dismiss
    </button>
  );
  if (item.kind === "possible_duplicate") {
    const other = otherId ?? "a test in the bank";
    return (
      <div data-testid="card-note" data-kind={item.kind} className={note}>
        <p data-testid="card-note-duplicate">
          This test looks like {otherName ? `${otherName} (${other})` : other}, which is already in the bank.
        </p>
        {previewing ? (
          <MergePreview api={api} item={item} busy={false} onCancel={() => setPreviewing(false)} onConfirm={() => onSettle(accept())} />
        ) : (
          <div className="flex flex-wrap gap-2">
            <button type="button" data-testid="card-merge" onClick={() => setPreviewing(true)} className={button}>
              Merge into {other}…
            </button>
            {dismiss}
          </div>
        )}
      </div>
    );
  }
  if (item.kind === "picked_test_mismatch") {
    return (
      <div data-testid="card-note" data-kind={item.kind} className={note}>
        <p>The photos do not look like the test you picked.</p>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => onSettle(accept())} className={button}>
            Extract again without the pick
          </button>
          {dismiss}
        </div>
      </div>
    );
  }
  const candidates = Array.isArray(item.proposal.candidate_question_ids) ? (item.proposal.candidate_question_ids as string[]) : [];
  return (
    <div data-testid="card-note" data-kind={item.kind} className={note}>
      <p>
        After the merge, the answer “{str(item.proposal.value) ?? ""}” (question {str(item.proposal.printed_number) ?? "?"}) has no
        question in the test.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1">
          <span className="sr-only">Move it to</span>
          <select value={target} onChange={(e) => setTarget(e.target.value)} className="rounded-paper border border-input bg-surface px-2 py-0.5">
            <option value="">Choose a question…</option>
            {candidates.map((q) => (
              <option key={q} value={q}>
                {q}
              </option>
            ))}
          </select>
        </label>
        <button type="button" disabled={!target} onClick={() => onSettle(fix(target))} className={button}>
          Move it
        </button>
        <button type="button" onClick={() => onSettle(accept())} className={button}>
          Leave it ungraded
        </button>
      </div>
    </div>
  );
}

const openButton =
  "rounded-button border border-border px-3 py-1 hover:bg-hover focus-visible:outline-2 focus-visible:outline-focus";

export interface StudentChipProps {
  api: ApiClient;
  attemptId: string;
  studentId: string | null;
  /** The assigned student (from `GET /threads/{id}`), when known. */
  student?: Student | null;
  nameRead: string | null;
  /** An open `unknown_student` item: the chip's choices settle it (resolve accept/fix). */
  item?: ReviewItem;
  onChanged?: () => void;
}


/**
 * The attempt's student: shows the name, or "Unknown student". Click → a picker to edit the
 * assigned student's name, assign an existing student, or create one (from the name read on
 * paper or from the typed name). A click outside or Escape closes it.
 */
export function StudentChip({ api, attemptId, studentId, student = null, nameRead, item, onChanged }: StudentChipProps) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [name, setName] = useState("");
  const [cls, setCls] = useState("");
  const [results, setResults] = useState<Student[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const chip = useRef<HTMLButtonElement>(null);
  const ids = useId();

  const close = (refocus: boolean) => {
    setOpen(false);
    setQ("");
    setError(null);
    if (refocus) chip.current?.focus();
  };
  useDismiss(root, open, (reason) => close(reason === "escape"));

  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    api
      .get("/students", { query: { q }, signal: ctrl.signal })
      .then(setResults)
      .catch(() => {});
    return () => ctrl.abort();
  }, [api, open, q]);

  /** One change at a time: a second click before the first answers does nothing (no duplicate
   *  student from a fast double Create; step 22.1.5). */
  const running = useRef(false);
  /** Runs a change; on success closes the picker and reloads the thread. */
  const act = async (change: () => Promise<unknown>) => {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    setError(null);
    try {
      await change();
      close(true);
      onChanged?.();
    } catch (err) {
      setError(errorText(err));
    } finally {
      running.current = false;
      setBusy(false);
    }
  };

  const assign = (body: Schemas["StudentPut"]) =>
    act(() => {
      if (item) {
        if (body.create_from_read) return resolveItem(api, item.id, accept());
        if (body.student_id) return resolveItem(api, item.id, fix({ student_id: body.student_id }));
      }
      return api.put("/attempts/{id}/student", { path: { id: attemptId }, body });
    });

  const typed = q.split(/\s+/).filter(Boolean).join(" ");
  const typedIsStudent = results.some((s) => s.name_search === nameSearch(typed));
  const createTyped = () =>
    act(async () => {
      // The search may lag behind the typing: look the name up again before creating it.
      const found = await api.get("/students", { query: { q: typed } });
      const same = found.find((st) => st.name_search === nameSearch(typed));
      if (same) {
        if (item) return resolveItem(api, item.id, fix({ student_id: same.id }));
        return api.put("/attempts/{id}/student", {
          path: { id: attemptId },
          body: { student_id: same.id, create_from_read: false },
        });
      }
      if (item) return resolveItem(api, item.id, fix({ full_name: typed }));
      const created = await api.post("/students", { body: { full_name: typed } });
      await api.put("/attempts/{id}/student", {
        path: { id: attemptId },
        body: { student_id: created.id, create_from_read: false },
      });
    });

  const newName = name.split(/\s+/).filter(Boolean).join(" ");
  const newClass = cls.split(/\s+/).filter(Boolean).join(" ");
  const nameChanged = !!student && newName !== student.full_name;
  const classChanged = !!student && newClass !== (student.class_name ?? "");
  const canRename = !!student && newName !== "" && (nameChanged || classChanged);
  /** Saves the name and the class (step 22.2.3: the chip edits the class too). */
  const rename = () =>
    act(() =>
      api.patch("/students/{id}", {
        path: { id: student!.id },
        body: {
          ...(nameChanged ? { full_name: newName } : {}),
          ...(classChanged ? { class_name: newClass } : {}),
        },
      }),
    );

  const label = studentId ? (student?.full_name ?? "…") : "Unknown student";
  return (
    <div ref={root} className="relative">
      <button
        ref={chip}
        type="button"
        data-testid="student-chip"
        data-student-id={studentId ?? ""}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? `${ids}-picker` : undefined}
        title={studentId ? "Edit or change the student" : "Assign a student"}
        onClick={() => {
          if (open) return close(false);
          setName(student?.full_name ?? "");
          setCls(student?.class_name ?? "");
          setOpen(true);
        }}
        className={
          "rounded-full border px-3 py-1 text-xs hover:bg-hover " +
          (studentId ? "border-border text-text" : "border-input bg-unsure text-text")
        }
      >
        {label}
      </button>
      {open && (
        <div
          id={`${ids}-picker`}
          role="dialog"
          aria-label="Student"
          data-testid="student-picker"
          className="absolute left-0 top-full z-10 mt-1 flex w-72 flex-col gap-3 rounded-paper border border-border bg-panel p-3 shadow-lg"
        >
          {student && (
            <form
              data-testid="student-edit"
              className="flex flex-col gap-1"
              onSubmit={(e) => {
                e.preventDefault();
                if (canRename && !busy) void rename();
              }}
            >
              <label htmlFor={`${ids}-name`} className="text-xs text-muted">
                Student name
              </label>
              <div className="flex gap-2">
                <input
                  autoFocus
                  id={`${ids}-name`}
                  data-testid="student-name-input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="min-w-0 flex-1 rounded-paper border border-input bg-surface px-2 py-1"
                />
              </div>
              <label htmlFor={`${ids}-class`} className="text-xs text-muted">
                Class
              </label>
              <div className="flex gap-2">
                <input
                  id={`${ids}-class`}
                  data-testid="student-class-input"
                  value={cls}
                  onChange={(e) => setCls(e.target.value)}
                  className="min-w-0 flex-1 rounded-paper border border-input bg-surface px-2 py-1"
                />
                <button
                  type="submit"
                  data-testid="student-name-save"
                  disabled={!canRename || busy}
                  className="rounded-button bg-accent px-2 py-1 text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover disabled:opacity-50"
                >
                  Save
                </button>
              </div>
            </form>
          )}
          <div className="flex flex-col gap-1">
            <label htmlFor={`${ids}-search`} className="text-xs text-muted">
              {student ? "Assign a different student" : "Assign a student"}
            </label>
            {!studentId && nameRead && (
              <button
                type="button"
                data-testid="student-create-from-read"
                disabled={busy}
                onClick={() => void assign({ create_from_read: true })}
                className="rounded-button bg-accent px-2 py-1 text-left text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover disabled:opacity-50"
              >
                Create “{nameRead}”
              </button>
            )}
            <input
              autoFocus={!student}
              id={`${ids}-search`}
              data-testid="student-search"
              placeholder="Search, or type a new name"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="rounded-paper border border-input bg-surface px-2 py-1"
            />
          </div>
          <ul className="max-h-48 overflow-y-auto">
            {results.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  data-testid="student-option"
                  disabled={busy}
                  onClick={() => void assign({ student_id: s.id, create_from_read: false })}
                  className="w-full rounded-button px-2 py-1 text-left hover:bg-hover"
                >
                  {s.full_name}
                  {s.class_name ? <span className="text-muted"> · {s.class_name}</span> : null}
                </button>
              </li>
            ))}
            {typed && !typedIsStudent && (
              <li>
                <button
                  type="button"
                  data-testid="student-create-typed"
                  disabled={busy}
                  onClick={() => void createTyped()}
                  className="w-full rounded-button px-2 py-1 text-left text-accent-strong hover:bg-hover"
                >
                  Create “{typed}”
                </button>
              </li>
            )}
            {results.length === 0 && !typed && (
              <li className="px-2 py-1 text-muted">No students yet. Type a name to add one.</li>
            )}
          </ul>
          {error && (
            <p role="alert" className="text-danger">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
