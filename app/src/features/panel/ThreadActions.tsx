/**
 * Straight to work (PRD §10 v6.3.1, step 22.3.2, decision D2): what the extraction and grade cards
 * offered, now in the open thread's workspace.
 *
 * - `ThreadTabActions` sits on the tab row at the right: **Extract again** (asks first through
 *   `useChoose`, says what it replaces, then `POST /threads/{id}/extract-again`; step 22.5.2, D8:
 *   the test is updated in place, and when other threads use it the dialog asks whether to update
 *   it for every thread or make a separate copy, sent as `mode`; with no other threads seen it sends
 *   no `mode`, and the sidecar's 409 CHOOSE_MODE opens the same choice) and **Grade
 *   student answers** (the same words once graded, step 22.4.1). The grade run writes AI keys when the test
 *   has none, so a missing key does not block it. A test-only thread (no student's paper) has
 *   **Make the key** instead: it grades the blank test (`attempt_id: null`), as the old card did.
 * - `ThreadBanner` sits under the bar: the thread's name, the student chip (only where a student's
 *   paper exists; a test-only thread has no student, plan v2.25.1), the card's unsure notes
 *   (possible duplicate with its merge preview, picked test mismatch, answers left without a
 *   question) and the run's progress with Stop (`running`).
 *
 * The photos the card showed are the workspace's photo viewer; Test, Key, Student answers and
 * Report are the workspace tabs.
 */
import { useId, useState, type ReactNode } from "react";
import { ApiError, type ApiClient, type Schemas } from "@/api/client";
import { useChoose } from "@/components/ConfirmDialog";
import { CardNote, StudentChip } from "@/features/cards/ExtractionCard";
import { useCardPhotos } from "@/features/cards/CardPhotos";
import { CompactBarContext } from "@/features/running/compactBar";
import { KeysChangedBar } from "@/features/running/KeysChangedBar";
import { itemsOf, resolveItem, type Resolution, type ReviewItem } from "@/features/unsure/unsure";
import { errorText } from "@/lib/errors";

type Detail = Schemas["ThreadDetail"];
type AgainMode = "replace" | "copy";

/** The sidecar's 409 when other threads use the test and no mode was sent (`CHOOSE_MODE`). */
export function isChooseMode(err: unknown): boolean {
  return err instanceof ApiError && err.status === 409 && typeof err.detail === "string" && /choose mode/i.test(err.detail);
}

const threads = (n: number) => `${n} other thread${n === 1 ? "" : "s"}`;

/** What Update (the test in place) keeps and replaces: one line, shown with that choice (D8). */
export const KEPT = "Test details and keys on unchanged questions stay; edits to the test text are replaced.";

const actionButton =
  "main-label inline-flex min-h-8 items-center rounded-button px-3 py-1 text-sm focus-visible:outline-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-50";

export interface ThreadTabActionsProps {
  api: ApiClient;
  threadId: string;
  detail: Detail;
  /** A run other than the key run is going on this thread: both actions wait for it. (Extract again
   *  stays pressable during the key run, which it cancels, step 22.6.4 D12.) */
  busy: boolean;
  /**
   * Step 22.6.4 (D11): the thread's key run is queued or running. Grade student answers waits,
   * greyed, with "Making the key…" beside it; it stays focusable (aria-disabled) so the keyboard
   * reaches it and hears why.
   */
  makingKey?: boolean;
  onRunStarted?: (run: Schemas["Run"]) => void;
}

export function ThreadTabActions({ api, threadId, detail, busy, makingKey = false, onRunStarted }: ThreadTabActionsProps) {
  const makingKeyId = useId();
  const choose = useChoose();
  const testId = detail.test?.id ?? null;
  const attempt = detail.attempt;
  const graded = !!attempt && attempt.status !== "extracted";
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = async (post: () => Promise<Schemas["Run"] | null>) => {
    if (starting) return;
    setStarting(true);
    setError(null);
    try {
      const run = await post();
      if (run) onRunStarted?.(run);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setStarting(false);
    }
  };

  const grade = () => {
    if (!testId || makingKey) return;
    void start(() =>
      api.post("/threads/{id}/runs", {
        path: { id: threadId },
        // A test-only thread: the blank test alone is graded (its key, D4).
        body: { kind: "grade", input: { test_id: testId, attempt_id: attempt?.id ?? null, reason: "button" } },
      }),
    );
  };

  // At most three short lines (step 22.5.2 c): the other threads, this paper, and what Update keeps.
  const paper = attempt ? (
    <p>
      {graded
        ? "This paper’s student answers are read again, and its grade report is cleared."
        : "This paper’s student answers are read again."}
    </p>
  ) : null;
  const update = { value: "replace", tone: "danger", hint: KEPT } as const;

  /** Other threads use the test (`others`, or null when only the sidecar's 409 said so): update it
   * for every thread, or a copy for this one, neither drawn as the default; null = Keep this one. */
  const chooseMode = (others: number | null) =>
    choose<AgainMode>({
      title: "Extract this test again?",
      body: (
        <>
          <p data-testid="again-others">
            {others ? `${threads(others)} ${others === 1 ? "uses" : "use"} this test.` : "Other threads use this test."}
          </p>
          {paper}
        </>
      ),
      cancelLabel: "Keep this one",
      choices: [
        { ...update, label: "Update the test for every thread" },
        { value: "copy", label: "Make a separate copy for this thread", tone: "danger" },
      ],
    });

  /** No `mode` when the thread showed no other threads: the sidecar decides at that moment (its
   * default is replace), and a 409 CHOOSE_MODE means another thread uses the test by now. */
  const post = (mode: AgainMode | null) =>
    api.post("/threads/{id}/extract-again", { path: { id: threadId }, body: mode ? { mode } : {} });

  const extractAgain = async () => {
    const others = detail.other_thread_count ?? 0;
    if (others > 0) {
      const mode = await chooseMode(others);
      if (mode) void start(() => post(mode));
      return;
    }
    const ok = await choose<AgainMode>({
      title: "Extract this test again?",
      body: (
        <>
          <p>The photos are read again and the test is updated in place.</p>
          {paper}
        </>
      ),
      cancelLabel: "Keep this one",
      choices: [{ ...update, label: "Extract again", testId: "confirm-ok" }],
    });
    if (!ok) return;
    void start(async () => {
      try {
        return await post(null);
      } catch (err) {
        if (!isChooseMode(err)) throw err;
        const mode = await chooseMode(null);
        return mode ? await post(mode) : null;
      }
    });
  };

  return (
    <div data-testid="thread-actions" className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        data-testid="extract-again"
        disabled={busy || starting}
        onClick={() => void extractAgain()}
        className={actionButton + " border border-border text-text hover:bg-hover"}
      >
        Extract again
      </button>
      {makingKey && (
        <span id={makingKeyId} data-testid="making-key-note" className="self-center text-xs text-muted">
          Making the key…
        </span>
      )}
      <button
        type="button"
        data-testid="grade-answers"
        disabled={busy || starting || !testId}
        aria-disabled={makingKey || undefined}
        aria-describedby={makingKey ? makingKeyId : undefined}
        onClick={grade}
        title={makingKey ? "Making the key…" : attempt ? undefined : "Make the key of this blank test"}
        // waiting: a half-strength fill, not opacity on the whole button, so its focus ring keeps its full
        // colour (WCAG 2.4.7, 1.4.11)
        className={actionButton + " text-accent-text " + (makingKey ? "cursor-not-allowed bg-accent/50" : "bg-accent enabled:hover:bg-accent-hover enabled:active:bg-accent-hover")}
      >
        {attempt ? "Grade student answers" : "Make the key"}
      </button>
      {error && (
        <p role="alert" className="basis-full text-right text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

export interface ThreadBannerProps {
  api: ApiClient;
  detail: Detail;
  refreshKey: number;
  /** The thread's running run (progress bar with Stop), or nothing. */
  running?: ReactNode;
  /** After the teacher changed the student or settled a note: reload the thread and the list. */
  onChanged: () => void;
  /** The test's keys changed and are not re-graded yet (step 22.4.5): "Keys changed" + Re-grade. */
  keysChanged?: boolean;
  onRegrade?: () => void;
  regradeError?: string | null;
  /** The top bar (keys changed, run progress) is one compact line: on the Key tab (comment 11),
   * and since step 22.4.8 (answer 7) on every workspace tab. */
  compact?: boolean;
}

export function ThreadBanner({
  api,
  detail,
  refreshKey,
  running,
  onChanged,
  keysChanged = false,
  onRegrade,
  regradeError,
  compact = false,
}: ThreadBannerProps) {
  const attempt = detail.attempt;
  const attemptId = attempt?.id ?? null;
  const testId = detail.test?.id ?? null;
  const data = useCardPhotos(api, testId, attemptId, refreshKey);
  const notes = itemsOf(data.review, ["possible_duplicate", "picked_test_mismatch", "merge_unaligned"]).filter(
    (i) => i.kind === "possible_duplicate" || (!!attemptId && i.attempt_id === attemptId),
  );
  const studentItem = attemptId ? itemsOf(data.review, "unknown_student", { attemptId })[0] : undefined;
  const [error, setError] = useState<string | null>(null);
  const settle = async (item: ReviewItem, resolution: Resolution) => {
    setError(null);
    try {
      await resolveItem(api, item.id, resolution);
      onChanged();
    } catch (err) {
      setError(errorText(err));
    }
  };
  return (
    <div data-testid="thread-banner" className="no-print flex flex-col gap-2 px-4 py-2 text-sm">
      {(keysChanged || running) && (
        <div
          data-testid="thread-top-bar"
          data-compact={compact || undefined}
          className={compact ? "flex min-w-0 items-center gap-4" : "flex flex-col gap-2"}
        >
          {keysChanged && onRegrade && (
            <KeysChangedBar running={!!running} onRegrade={onRegrade} error={regradeError} compact={compact} />
          )}
          <CompactBarContext.Provider value={compact}>{running}</CompactBarContext.Provider>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h1 data-testid="thread-title" className="font-serif text-base text-text">
          {detail.shown_title}
        </h1>
        {attemptId && <span className="text-muted">Student:</span>}
        {attemptId && (
          <StudentChip
            api={api}
            attemptId={attemptId}
            studentId={attempt?.student_id ?? null}
            student={detail.student}
            nameRead={attempt?.student_name_read ?? null}
            item={studentItem}
            onChanged={onChanged}
          />
        )}
      </div>
      {notes.map((item) => (
        <CardNote key={item.id} api={api} item={item} onSettle={(r) => void settle(item, r)} />
      ))}
      {error && (
        <p role="alert" className="text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
