/**
 * One thread in the conversation area: its messages, the photo check card before Run, and the
 * D18 block after it (PRD D17, D18).
 *
 * - `threadId === null` is a new, not yet created thread: the first drop / paste uploads the
 *   files (`POST /files`), creates the thread (`POST /threads`), stores the draft and calls
 *   `onThreadCreated`, which opens it.
 * - Before Run the card is frontend state only (`photo-check/draft.ts`, sessionStorage).
 * - Run posts `{kind: "extract", input: toExtractInput(draft)}` to `/threads/{id}/runs`, clears
 *   the draft and reports the `Run` through `onRunStarted` (the running indicator, part B, and
 *   the thread list listen there and to SSE). `refreshKey` changes (run events for this thread)
 *   reload the messages, where the extraction card appears (step 16 renders it).
 * - A thread that has already run (an attempt, a non-pending kind, a run card, a run in
 *   `GET /runs/active` (`hasActiveRun`), a Run from this
 *   session, or a 409 from the sidecar) shows no card on drop: a "Start a new thread" button.
 */
import { useCallback, useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { ApiError, type ApiClient, type Schemas } from "@/api/client";
import {
  clearDraft,
  EMPTY_DRAFT,
  loadDraft,
  saveDraft,
  toExtractInput,
  type PhotoCheckDraft,
} from "@/features/photo-check/draft";
import { PhotoCheckCard } from "@/features/photo-check/PhotoCheckCard";
import { uploadFiles } from "@/features/photo-check/upload";
import { Conversation } from "@/features/conversation/Conversation";
import { ExtractionCard, type RunCardBody } from "@/features/cards/ExtractionCard";
import { GradeCard, type GradeCardBody } from "@/features/cards/GradeCard";
import type { PanelView } from "@/features/panels/panelView";
import type { ReactNode } from "react";
import { errorText } from "@/lib/errors";

export interface ThreadViewHandle {
  addFiles: (files: File[]) => void;
  run: () => void;
}

export interface ThreadViewProps {
  api: ApiClient;
  threadId: string | null;
  notice?: ReactNode;
  /** Files to add as soon as the view mounts ("Start a new thread" after a blocked drop). */
  initialFiles?: File[] | null;
  onThreadCreated: (id: string) => void;
  onNewThread: (files?: File[]) => void;
  onRunStarted?: (run: Schemas["Run"]) => void;
  /** The thread has a run in `GET /runs/active` (a reload mid-run): it has already run (D18). */
  hasActiveRun?: boolean;
  /** The progress of this thread's running run, below its messages (step 22.1.3). */
  running?: ReactNode;
  /** Bumped by the owner on run events for this thread: reload the messages. */
  refreshKey?: number;
  /** The extraction card's [Test] / [Answers] (step 16). */
  onOpenPanel?: (view: PanelView) => void;
  /** The teacher changed the thread's student here: the thread list reloads (group, title). */
  onThreadChanged?: () => void;
  /** A workspace is open in the conversation's place (step 22.1.4): hide, but keep everything. */
  hidden?: boolean;
  ref?: Ref<ThreadViewHandle>;
}

type Message = Schemas["Message"];

function useThreadData(api: ApiClient, threadId: string | null, refreshKey: number) {
  const [detail, setDetail] = useState<Schemas["ThreadDetail"] | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  useEffect(() => {
    if (!threadId) return;
    const ctrl = new AbortController();
    const opts = { path: { id: threadId }, signal: ctrl.signal };
    Promise.all([api.get("/threads/{id}", opts), api.get("/threads/{id}/messages", opts)])
      .then(([d, m]) => {
        setDetail(d);
        setMessages(Array.isArray(m) ? m : []);
      })
      .catch(() => {
        /* aborted or offline: keep what is shown */
      });
    return () => ctrl.abort();
  }, [api, threadId, refreshKey]);
  return { detail, messages };
}

export function hasAlreadyRun(detail: Schemas["ThreadDetail"] | null, messages: readonly Message[]): boolean {
  if (detail && (detail.attempt !== null || detail.thread.kind !== "pending")) return true;
  return messages.some((m) => m.kind === "run_card" || m.kind === "grade_card");
}

export function ThreadView({
  api,
  threadId,
  notice,
  initialFiles,
  onThreadCreated,
  onNewThread,
  onRunStarted,
  refreshKey = 0,
  hasActiveRun = false,
  running,
  onOpenPanel,
  onThreadChanged,
  hidden = false,
  ref,
}: ThreadViewProps) {
  // `localSeq` reloads after the teacher's own edits on the card (the student chip).
  const [localSeq, setLocalSeq] = useState(0);
  const { detail, messages } = useThreadData(api, threadId, refreshKey * 1000 + localSeq);
  const [draft, setDraftState] = useState<PhotoCheckDraft>(
    () => (threadId ? loadDraft(threadId) : null) ?? EMPTY_DRAFT,
  );
  const [ranHere, setRanHere] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [blockedFiles, setBlockedFiles] = useState<File[] | null>(null);
  const alreadyRan = ranHere || hasActiveRun || hasAlreadyRun(detail, messages);

  const setDraft = useCallback(
    (next: PhotoCheckDraft) => {
      setDraftState(next);
      if (threadId) saveDraft(threadId, next);
    },
    [threadId],
  );

  const addFiles = useCallback(
    async (files: File[]) => {
      if (!files.length || busy) return;
      if (alreadyRan) {
        setBlockedFiles(files);
        return;
      }
      setBusy(true);
      setError(null);
      try {
        const { pages, errors } = await uploadFiles(api, files);
        setError(errors.length ? errors.join(" · ") : null);
        if (!pages.length) return;
        const next = { ...draft, pages: [...draft.pages, ...pages] };
        if (threadId) {
          setDraft(next);
        } else {
          const created = await api.post("/threads", { body: { title: "" } });
          saveDraft(created.thread_id, next);
          onThreadCreated(created.thread_id);
        }
      } catch (err) {
        setError(errorText(err));
      } finally {
        setBusy(false);
      }
    },
    [alreadyRan, api, busy, draft, onThreadCreated, setDraft, threadId],
  );

  const run = useCallback(async () => {
    if (!threadId || busy || alreadyRan || !draft.pages.length) return;
    setBusy(true);
    setError(null);
    try {
      const started = await api.post("/threads/{id}/runs", {
        path: { id: threadId },
        body: { kind: "extract", input: toExtractInput(draft) },
      });
      clearDraft(threadId);
      setDraftState(EMPTY_DRAFT);
      setRanHere(true);
      onRunStarted?.(started);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setRanHere(true);
      } else {
        setError(errorText(err));
      }
    } finally {
      setBusy(false);
    }
  }, [alreadyRan, api, busy, draft, onRunStarted, threadId]);

  useImperativeHandle(ref, () => ({ addFiles: (f) => void addFiles(f), run: () => void run() }), [addFiles, run]);

  const consumed = useRef<File[] | null>(null);
  useEffect(() => {
    if (!initialFiles?.length || consumed.current === initialFiles) return;
    consumed.current = initialFiles;
    void addFiles(initialFiles);
  }, [initialFiles, addFiles]);

  const showCard = !alreadyRan && draft.pages.length > 0;
  // The last grade card per attempt is shown in full; earlier ones as one line.
  const latestGrade = new Map<string, string>();
  for (const m of messages) if (m.kind === "grade_card") latestGrade.set(gradeAttempt(m), m.id);
  const empty = !threadId && !showCard && !busy && !error;

  return (
    <Conversation notice={notice} onFiles={(f) => void addFiles(f)} empty={empty} hidden={hidden}>
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-6 py-6">
        {detail && (
          <h1 data-testid="thread-title" className="font-serif text-xl text-text">
            {detail.shown_title}
          </h1>
        )}
        {messages.map((m) => (
          <MessageView
            key={m.id}
            message={m}
            api={api}
            threadId={threadId}
            latest={m.id === latestGrade.get(gradeAttempt(m))}
            refreshKey={refreshKey * 1000 + localSeq}
            detail={detail}
            onOpenPanel={onOpenPanel}
            onRunStarted={onRunStarted}
            onChanged={() => {
              setLocalSeq((n) => n + 1);
              onThreadChanged?.();
            }}
          />
        ))}
        {running}
        {showCard && (
          <PhotoCheckCard
            api={api}
            draft={draft}
            onChange={setDraft}
            onAddFiles={(f) => void addFiles(f)}
            onRun={() => void run()}
            busy={busy}
            error={error}
          />
        )}
        {!showCard && busy && (
          <p role="status" className="text-sm text-muted" data-testid="uploading">
            Reading the files…
          </p>
        )}
        {!showCard && error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        {alreadyRan && blockedFiles && (
          <div
            data-testid="thread-blocked"
            className="flex items-center justify-between gap-3 rounded-paper border border-border bg-surface p-4 text-sm"
          >
            <span className="text-text">
              This thread has already run. One thread holds one test.
            </span>
            <button
              type="button"
              onClick={() => onNewThread(blockedFiles)}
              className="rounded-button bg-accent px-3 py-1.5 text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover"
            >
              Start a new thread
            </button>
          </div>
        )}
        {threadId && !showCard && !alreadyRan && !busy && !error && messages.length === 0 && (
          <p className="text-sm text-muted">Drop or paste photos, a PDF or a Word file of the test.</p>
        )}
      </div>
    </Conversation>
  );
}

/**
 * The test's display name for an extraction card: the thread's test when it is the card's test,
 * or when the card's attempt is the current one (its test may have been merged since, so the
 * card's stored `test_id` is the merged-away test). Otherwise `null` (the card shows the id).
 */
function cardTestName(detail: Schemas["ThreadDetail"] | null, body: RunCardBody): string | null {
  if (!detail?.test) return null;
  const same = detail.test.id === body.test_id || (!!body.attempt_id && detail.attempt?.id === body.attempt_id);
  return same ? (detail.test_display_name ?? null) : null;
}

function gradeAttempt(m: Message): string {
  const id = (m.body as GradeCardBody).attempt_id;
  return typeof id === "string" ? id : "";
}

/**
 * A stored message: the run card is the extraction card (step 16), the grade card is step 19's;
 * others render as text.
 */
function MessageView({
  message,
  api,
  threadId,
  latest,
  refreshKey,
  detail,
  onOpenPanel,
  onRunStarted,
  onChanged,
}: {
  message: Message;
  api: ApiClient;
  threadId: string | null;
  latest: boolean;
  refreshKey: number;
  detail: Schemas["ThreadDetail"] | null;
  onOpenPanel?: (view: PanelView) => void;
  onRunStarted?: (run: Schemas["Run"]) => void;
  onChanged: () => void;
}) {
  if (message.kind === "run_card") {
    const body = message.body as RunCardBody;
    return (
      <div data-testid="message" data-kind="run_card">
        <ExtractionCard
          api={api}
          body={body}
          attempt={detail?.attempt ?? null}
          student={detail?.student ?? null}
          testName={cardTestName(detail, body)}
          threadId={threadId}
          refreshKey={refreshKey}
          onOpenPanel={onOpenPanel}
          onRunStarted={onRunStarted}
          onChanged={onChanged}
        />
      </div>
    );
  }
  if (message.kind === "grade_card") {
    return (
      <div data-testid="message" data-kind="grade_card">
        <GradeCard
          api={api}
          body={message.body as GradeCardBody}
          latest={latest}
          refreshKey={refreshKey}
          onOpenPanel={onOpenPanel}
        />
      </div>
    );
  }
  const text = typeof message.body.text === "string" ? message.body.text : null;
  return (
    <div
      data-testid="message"
      data-kind={message.kind}
      className={
        "rounded-paper px-4 py-2 text-sm " +
        (message.role === "teacher" ? "self-end bg-hover text-text" : "border border-border bg-surface text-text")
      }
    >
      {text ?? message.kind.replace("_", " ")}
    </div>
  );
}
