/**
 * The layout (PRD §10.1): sidebar · conversation, with Review and Settings in the artifact panel on
 * the right, and Test, Key, Answers and Report as a workspace in the conversation's place.
 *
 * With an `api` (connected), the sidebar lists the threads (`threads`, from `GET /threads`) and
 * the conversation shows the open thread (`ThreadView`): drop / paste → photo check → Run.
 * The open thread id is kept in sessionStorage so the reload after a sidecar restart returns to it.
 * `running` fills the sidebar's running slot (step 15 part B: the running indicator).
 *
 * Workspace view (PRD §10 v4.13, step 22.1.4, decision 3 = B): opening Test, Key, Answers or Report
 * hides the conversation (still mounted, so its scroll position and unsent text survive) and shows
 * `Workspace`: the panel on the left, the original photos on the right. Esc returns to the
 * conversation and puts focus back on the control that opened the workspace. Opening a thread in
 * the sidebar also returns to it, the already open thread too.
 *
 * Step 22.5.1 (comment 1, D1): a test opened from the Tests tab has no Back button; the sidebar is
 * the way out. Its header is laid out like a thread's own test: the tabs, then a title bar with
 * the test's name (`TestTitleBar`).
 *
 * Step 22.5.5 checklist (c), R22.5.5.11: clicking a student in the Students tab opens
 * "Skills — {student}" (`StudentSkillsView`) in the conversation's place, over a workspace too.
 * Like a test from the Tests tab it has no Back button: a thread, another sidebar tab, a workspace
 * view or Esc leaves it (Esc puts focus back on the student's row).
 *
 * Print (step 22.1.1, comment 8): the webview's print window covers the whole app, and its only
 * exits are its own Cancel button and Esc, so the teacher left it with the window's ✕, which
 * closes the app. Print in the test, key and report panels therefore opens a print view first:
 * the panel fills the window under a bar (`no-print`) with "Back to …", a note on how to leave the
 * print window, and Print; then the print window opens. Back or Esc returns to the panel, with
 * focus on the panel's Print button (step 22.1.4).
 *
 * Delete (step 22.2.3, data-model §5.7): "Delete…" in the thread menu and on each test in the
 * Tests tab asks first through `useConfirm` (for a test, naming the threads that go, from
 * `GET /tests/{id}/delete-preview`), deletes, reloads the lists, and closes an open thread or
 * workspace of what was deleted to the empty state. A 409 (a run still going) shows as an alert.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { type ApiClient, type Schemas } from "@/api/client";
import { ArtifactPanel } from "@/features/panel/ArtifactPanel";
import { PrintBar } from "@/features/panel/PrintBar";
import { Workspace } from "@/features/panel/Workspace";
import { ThreadBanner, ThreadTabActions } from "@/features/panel/ThreadActions";
import { TestTitleBar } from "@/features/panel/TestTitleBar";
import { Conversation } from "@/features/conversation/Conversation";
import { AnswersPanel } from "@/features/panels/AnswersPanel";
import {
  isWorkspace,
  panelTitle,
  workspaceTabs,
  type PanelView,
  type TabSource,
  type WorkspaceView,
} from "@/features/panels/panelView";
import { TestPanel } from "@/features/panels/TestPanel";
import { KeysPanel } from "@/features/panels/KeysPanel";
import { useKeyRegrade } from "@/features/running/useKeyRegrade";
import { ReportPanel } from "@/features/panels/ReportPanel";
import { SettingsPanel } from "@/features/settings/SettingsPanel";
import { Sidebar, type SidebarTab } from "@/features/sidebar/Sidebar";
import { TestsTab } from "@/features/tests-tab/TestsTab";
import { StudentsTab } from "@/features/students-tab/StudentsTab";
import { StudentSkillsView } from "@/features/students-tab/StudentSkillsView";
import { ThreadList } from "@/features/threads/ThreadList";
import type { ThreadSummary } from "@/features/threads/threads";
import { ThreadView, type ThreadViewHandle } from "@/features/threads/ThreadView";
import { useShortcuts, type ShortcutHandlers } from "@/hooks/useShortcuts";
import type { SystemStatus } from "@/hooks/useSystemStatus";
import { readSession, removeSession, writeSession } from "@/lib/storage";
import { ConnectionNotice, type ConnectionState } from "./ConnectionNotice";
import { ConfirmProvider, useConfirm } from "./ConfirmDialog";
import { LeaveGuardContext, type LeaveCheck } from "@/features/panels/leaveGuard";
import { errorText } from "@/lib/errors";
import type { KeyRuns } from "@/features/running/keyRun";
import { tauriCloseListener, useCloseGuard, type CloseListener } from "@/features/close/closeGuard";

const ACTIVE_KEY = "etach.activeThread";

/** The panels' Print buttons: focus returns to one after the print view (step 22.1.4). */
const PRINT_BUTTONS =
  '[data-testid="artifact-panel"] :is([data-testid="test-print"], [data-testid="key-print"], [data-testid="report-print"])';

/** `el` can take focus now: still in the page and not inside a hidden subtree. */
function focusable(el: HTMLElement | null): el is HTMLElement {
  return !!el && el.isConnected && !el.closest("[hidden]");
}

export interface AppShellProps {
  connection: ConnectionState;
  /** Overrides for the shortcut handlers (tests, later steps). */
  shortcuts?: ShortcutHandlers;
  /** The sidecar client; without it the conversation shows only the start screen. */
  api?: ApiClient | null;
  /** `GET /threads` rows; `null` = not loaded. */
  threads?: readonly ThreadSummary[] | null;
  /** A thread was created or a run started: reload the list. */
  onThreadsChanged?: () => void;
  /** A run was started from the photo check card. */
  onRunStarted?: (run: Schemas["Run"]) => void;
  /** Changes on run events (SSE): the open thread reloads its messages. */
  runEventSeq?: number;
  /** Threads with a run in `GET /runs/active`: they count as "has already run" (D18). */
  activeRunThreadIds?: ReadonlySet<string>;
  /** Step 22.6.4: each thread's key run (pending, or failed / discarded). */
  keyRuns?: KeyRuns;
  /** Threads whose Extract again and Grade wait: active runs other than the key run (D12). */
  busyRunThreadIds?: ReadonlySet<string>;
  /** The running indicator for the sidebar slot (part B). */
  running?: ReactNode;
  /** The progress of the open thread's running run, shown in the thread (step 22.1.3). */
  threadRunning?: (threadId: string) => ReactNode;
  /** Changes on SSE `review.changed`: the Review panel reloads its list. */
  reviewEventSeq?: number;
  /** `GET /system/status` (step 20): the other-Ollama warning and the Settings panel. */
  systemStatus?: SystemStatus | null;
  onSystemStatusReload?: () => void;
  /** The panel open at start (tests). */
  initialPanel?: PanelView | null;
  /** Opens the print window (tests); defaults to `window.print()`. */
  print?: () => void;
  /** The window's close requests (tests); defaults to Tauri's `onCloseRequested`. */
  closeListener?: CloseListener;
}

/** The shell inside a confirm-dialog provider (the leave guard asks through it). */
export function AppShell(props: AppShellProps) {
  return (
    <ConfirmProvider>
      <Shell {...props} />
    </ConfirmProvider>
  );
}

function Shell({
  connection,
  shortcuts,
  api,
  threads = null,
  onThreadsChanged,
  onRunStarted,
  runEventSeq = 0,
  running,
  threadRunning,
  activeRunThreadIds,
  keyRuns,
  busyRunThreadIds,
  reviewEventSeq = 0,
  systemStatus = null,
  onSystemStatusReload,
  initialPanel = null,
  print,
  closeListener = tauriCloseListener,
}: AppShellProps) {
  const [tab, setTab] = useState<SidebarTab>("chats");
  const confirm = useConfirm();
  /** Unsaved typing in a panel (the test page) asks before it is left (R22.1.5.6). */
  const leaveChecks = useRef(new Set<LeaveCheck>());
  const registerLeave = useCallback((check: LeaveCheck) => {
    leaveChecks.current.add(check);
    return () => void leaveChecks.current.delete(check);
  }, []);
  /** Runs `go` now when nothing is unsaved; otherwise after the teacher confirms. */
  const guarded = useCallback(
    (go: () => void) => {
      if (![...leaveChecks.current].some((c) => c())) return go();
      void confirm({
      title: "Leave without saving?",
      body: <p>Your changes to the test text are not saved yet. Leaving now loses them.</p>,
      confirmLabel: "Discard changes",
      cancelLabel: "Keep editing",
        tone: "danger",
      }).then((ok) => {
        if (ok) go();
        // "Keep editing" puts the teacher back in the text (step 22.2.2), after the dialog has put
        // focus back on its opener.
        else setTimeout(() => document.querySelector<HTMLElement>('[data-testid="test-text"]')?.focus(), 0);
      });
    },
    [confirm],
  );
  // Closing the window asks first, and names unsaved text (comment 6).
  useCloseGuard(confirm, () => [...leaveChecks.current].some((c) => c()), closeListener);
  const [panel, setPanel] = useState<PanelView | null>(initialPanel);
  /** The student whose skills view fills the main panel (R22.5.5.11). */
  const [student, setStudent] = useState<{ id: string; name: string } | null>(null);
  const [activeId, setActiveIdState] = useState<string | null>(() =>
    api ? readSession<string>(ACTIVE_KEY) : null,
  );
  /** Bumped by a Review resolve or a student change: the open thread and the Tests tab reload. */
  const [reviewSeq, setReviewSeq] = useState(0);
  /** The open thread (`GET /threads/{id}`): its test, attempt and student. */
  /** Re-grade after checking keys (step 22.4.5); its `seq` reloads the thread detail. */
  const [regradeSeq, setRegradeSeq] = useState(0);
  const detail = useThreadDetail(api ?? null, activeId, reviewSeq + reviewEventSeq + runEventSeq + regradeSeq);
  /** Straight to work (step 22.3.2, D2): an extracted thread shows its Test workspace. */
  const threadTestId = detail?.test?.id ?? null;
  const threadView = useMemo<WorkspaceView | null>(
    () => (threadTestId ? { kind: "test", testId: threadTestId } : null),
    [threadTestId],
  );
  /** The workspace view: an opened Test, Key, Answers or Report, else the thread's own Test. */
  const shown: WorkspaceView | null = isWorkspace(panel) ? panel : threadView;
  /** Test, Key, Answers and Report open as a workspace in the conversation's place. */
  const workspace = !!api && shown !== null;
  const keyRegrade = useKeyRegrade({
    api: api ?? null,
    threadTestId,
    threadPending: detail?.regrade_pending ?? false,
    keyTabTestId: workspace && shown?.kind === "keys" ? shown.testId : null,
    activeId,
    onQueued: () => onThreadsChanged?.(),
    onChanged: () => setRegradeSeq((n) => n + 1),
  });
  /** The panel shown as a print view; it ends when another panel opens (a new object). */
  const [printing, setPrinting] = useState<PanelView | null>(null);
  const inPrint = printing !== null && printing === (isWorkspace(panel) ? panel : threadView);
  const [printSeq, setPrintSeq] = useState(0);
  const printWindow = useRef(print ?? (() => window.print()));
  useEffect(() => {
    printWindow.current = print ?? (() => window.print());
  });
  // The print window opens once the print view has rendered.
  useEffect(() => {
    if (printSeq > 0) printWindow.current();
  }, [printSeq]);

  /** Focus to move after the next render (Back from a workspace or from the print view). */
  const refocus = useRef<(() => void) | null>(null);
  useEffect(() => {
    const move = refocus.current;
    refocus.current = null;
    move?.();
  });
  /** The control that opened the current workspace (a card button, a thumbnail, a Tests row). */
  const opener = useRef<HTMLElement | null>(null);
  /** The Print button the print view was opened from. */
  const printOpener = useRef<HTMLElement | null>(null);

  const startPrint = useCallback(() => {
    const active = document.activeElement;
    printOpener.current = active instanceof HTMLElement ? active : null;
    setPrinting(isWorkspace(panel) ? panel : threadView);
    setPrintSeq((n) => n + 1);
  }, [panel, threadView]);
  /** Back (or Esc) from the print view: the panel again, focus on its Print button. */
  const endPrint = useCallback(() => {
    const from = printOpener.current;
    refocus.current = () => {
      const target =
        focusable(from) && from.closest('[data-testid="artifact-panel"]')
          ? from
          : document.querySelector<HTMLElement>(PRINT_BUTTONS);
      target?.focus();
    };
    setPrinting(null);
  }, []);

  /** Opens a panel. A workspace opened from outside one remembers its opener for Back. */
  const openPanel = useCallback(
    (view: PanelView) => {
      const active = document.activeElement;
      guarded(() => {
        if (isWorkspace(view) && !isWorkspace(panel)) {
          opener.current = active instanceof HTMLElement && active !== document.body ? active : null;
        }
        if (isWorkspace(view)) setStudent(null);
        setPanel(view);
      });
    },
    [guarded, panel],
  );
  /** Esc: the conversation as it was, focus on the workspace's opener. */
  const closeWorkspace = useCallback(() => guarded(() => {
    const from = opener.current;
    opener.current = null;
    refocus.current = () => {
      if (focusable(from)) from.focus();
      else document.querySelector<HTMLElement>('[data-testid="conversation"]')?.focus();
    };
    setPanel(null);
  }), [guarded]);

  /** Esc from the skills view: the conversation or workspace under it, focus on the student's row. */
  const closeStudent = useCallback(() => {
    const id = student?.id;
    refocus.current = () => {
      const row = id
        ? document.querySelector<HTMLElement>(
            `[data-testid="student-row"][data-student-id="${CSS.escape(id)}"] [data-testid="student-item"]`,
          )
        : null;
      if (focusable(row)) row.focus();
    };
    setStudent(null);
  }, [student]);

  /** Bumped by a metadata edit in the test panel: the Tests tab reloads. */
  const [testsSeq, setTestsSeq] = useState(0);
  /** The Tests tab was opened with Ctrl+K: focus its search box. */
  const [focusSearch, setFocusSearch] = useState(false);
  const [fresh, setFresh] = useState<{ seq: number; files: File[] | null }>({ seq: 0, files: null });
  const view = useRef<ThreadViewHandle>(null);

  const setActiveId = useCallback((id: string | null) => {
    setActiveIdState(id);
    if (id) writeSession(ACTIVE_KEY, id);
    else removeSession(ACTIVE_KEY);
  }, []);

  const newThread = (files?: File[]) =>
    guarded(() => {
      setActiveId(null);
      setFresh((f) => ({ seq: f.seq + 1, files: files ?? null }));
      setTab("chats");
      opener.current = null;
      setStudent(null);
      setPanel(null);
    });

  useShortcuts({
    onNewThread: () => newThread(),
    // Behind a workspace the conversation is hidden: pasted photos and Run would go there unseen.
    onPastePhotos: (files) => {
      if (!workspace && !student) view.current?.addFiles(files);
    },
    onRunOrGrade: () => {
      if (!workspace && !student) view.current?.run(); // step 16/19 adds Grade
    },
    onSearchTests: () => {
      setFocusSearch(true);
      setTab("tests");
      document.querySelector<HTMLInputElement>('[data-testid="tests-search"]')?.focus();
    },
    onClosePanel: () =>
      inPrint
        ? endPrint()
        : panel?.kind === "settings"
          ? setPanel(null)
          : student
            ? closeStudent()
            : workspace
              ? closeWorkspace()
              : setPanel(null),
    ...shortcuts,
  });

  /** The open thread's test and attempt, for the workspace tabs. */
  const tabSource: TabSource | null = detail
    ? {
        testId: detail.test?.id ?? detail.attempt?.test_id ?? null,
        attemptId: detail.attempt?.id ?? null,
        graded: detail.attempt ? detail.attempt.status !== "extracted" : false,
      }
    : null;
  /** The workspace view belongs to the open thread: the thread's title bar and actions show. */
  const ownView =
    !!detail &&
    shown !== null &&
    (shown.testId === tabSource?.testId || ("attemptId" in shown && shown.attemptId === tabSource?.attemptId));
  const threadChanged = () => {
    setReviewSeq((n) => n + 1);
    onThreadsChanged?.();
  };

  const notice = <ConnectionNotice state={connection} />;

  /** A delete that failed (a 409 while a run is going): shown above the sidebar list. */
  const [deleteError, setDeleteError] = useState<string | null>(null);
  /** After a delete: forget the open thread / workspace when it was deleted. */
  const closeDeleted = useCallback(
    (threadIds: readonly string[], testIds: readonly string[]) => {
      const threadGone = !!activeId && threadIds.includes(activeId);
      if (threadGone) setActiveId(null);
      const viewTest = panel && "testId" in panel ? panel.testId : null;
      if ((viewTest && testIds.includes(viewTest)) || (threadGone && isWorkspace(panel))) {
        opener.current = null;
        setPanel(null);
      }
    },
    [activeId, panel, setActiveId],
  );
  const deleteThread = useCallback(
    async (id: string, name: string) => {
      if (!api) return;
      setDeleteError(null);
      const ok = await confirm({
        title: `Delete “${name}”?`,
        body: (
          <>
            <p>The thread goes for good, with its photos, student answers and report. The test stays in the bank.</p>
            <p className="text-muted">This can't be undone here; the daily backup is the way back.</p>
          </>
        ),
        confirmLabel: "Delete thread",
        cancelLabel: "Keep thread",
        tone: "danger",
      });
      if (!ok) return;
      try {
        await api.delete("/threads/{id}", { path: { id } });
      } catch (err) {
        setDeleteError(`Could not delete “${name}”: ${errorText(err)}`);
        return;
      }
      closeDeleted([id], []);
      onThreadsChanged?.();
      setTestsSeq((n) => n + 1);
    },
    [api, confirm, closeDeleted, onThreadsChanged],
  );
  const deleteTest = useCallback(
    async (id: string, name: string) => {
      if (!api) return;
      setDeleteError(null);
      let preview: Schemas["TestDeletePreview"];
      try {
        preview = await api.get("/tests/{id}/delete-preview", { path: { id } });
      } catch (err) {
        setDeleteError(`Could not delete “${name}”: ${errorText(err)}`);
        return;
      }
      const ok = await confirm({
        title: `Delete “${name}”?`,
        body: <TestDeleteBody preview={preview} />,
        confirmLabel: "Delete test",
        cancelLabel: "Keep test",
        tone: "danger",
      });
      if (!ok) return;
      try {
        await api.delete("/tests/{id}", { path: { id } });
      } catch (err) {
        setDeleteError(`Could not delete “${name}”: ${errorText(err)}`);
        return;
      }
      const gone = preview.threads.map((t) => t.id);
      const touched = [...gone, ...preview.kept_threads.map((t) => t.id)];
      closeDeleted(gone, [id, ...preview.merged_test_ids]);
      // A thread that lost its attempt on this test keeps its conversation, not a workspace of it.
      if (activeId && touched.includes(activeId) && isWorkspace(panel)) setPanel(null);
      onThreadsChanged?.();
      setTestsSeq((n) => n + 1);
    },
    [api, confirm, closeDeleted, onThreadsChanged, activeId, panel],
  );

  const deleteStudent = useCallback(
    async (id: string, name: string) => {
      if (!api) return;
      setDeleteError(null);
      let preview: Schemas["StudentDeletePreview"];
      try {
        preview = await api.get("/students/{id}/delete-preview", { path: { id } });
      } catch (err) {
        setDeleteError(`Could not delete “${name}”: ${errorText(err)}`);
        return;
      }
      const ok = await confirm({
        title: `Delete “${name}”?`,
        body: <StudentDeleteBody preview={preview} />,
        confirmLabel: "Delete student",
        cancelLabel: "Keep student",
        tone: "danger",
      });
      if (!ok) return;
      try {
        await api.delete("/students/{id}", { path: { id } });
      } catch (err) {
        setDeleteError(`Could not delete “${name}”: ${errorText(err)}`);
        return;
      }
      const gone = preview.threads.map((t) => t.id);
      const touched = [...gone, ...preview.kept_threads.map((t) => t.id)];
      closeDeleted(gone, []);
      if (student?.id === id) setStudent(null);
      // A shared thread that lost this student's paper keeps its conversation, not a workspace of it.
      if (activeId && touched.includes(activeId) && isWorkspace(panel)) setPanel(null);
      onThreadsChanged?.();
      setTestsSeq((n) => n + 1);
    },
    [api, confirm, closeDeleted, onThreadsChanged, activeId, panel, student],
  );

  /** Opens a thread from the sidebar: it shows, also the open one (closes a Tests test or a student). */
  const openThread = (id: string) =>
    guarded(() => {
      setActiveId(id);
      setStudent(null);
      if (isWorkspace(panel)) {
        opener.current = null;
        setPanel(null);
      }
    });

  const renameThread = useCallback(
    async (id: string, title: string | null) => {
      if (!api) return;
      try {
        await api.patch("/threads/{id}", { path: { id }, body: { title } });
      } catch (err) {
        throw new Error(errorText(err), { cause: err });
      }
      onThreadsChanged?.();
      // The open thread's header shows the new (or made) title too.
      setReviewSeq((n) => n + 1);
    },
    [api, onThreadsChanged],
  );

  const contentFor = (forView: PanelView | null) => (
    <PanelContent
      api={api ?? null}
      view={forView}
      onTestChanged={() => {
        setTestsSeq((n) => n + 1);
        // Step 22.3.1 (comment 9): a saved Test name changes thread titles: the sidebar reloads at once.
        onThreadsChanged?.();
      }}
      reviewEventSeq={reviewEventSeq}
      onReviewResolved={() => setReviewSeq((n) => n + 1)}
      systemStatus={systemStatus}
      onSystemStatusReload={onSystemStatusReload}
      print={startPrint}
      printing={inPrint}
      onKeysChanged={keyRegrade.markChanged}
      keyNote={
        // the open thread's key run, on its test's Key tab (step 22.6.4)
        forView?.kind === "keys" && activeId && detail?.test?.id === forView.testId
          ? keyRuns?.pending(activeId)
            ? "making"
            : keyRuns?.failed(activeId)
              ? "failed"
              : null
          : null
      }
    />
  );

  return (
    <LeaveGuardContext.Provider value={registerLeave}>
    <div className="flex h-full bg-bg font-sans text-text" data-testid="app-shell" data-print-view={inPrint || undefined}>
      <div className={inPrint ? "hidden" : "contents"}>
      <Sidebar
        tab={tab}
        onTabChange={(t) => {
          setFocusSearch(false);
          // Another sidebar tab leaves the student's skills view.
          if (t !== tab) setStudent(null);
          setTab(t);
        }}
        onNewThread={() => newThread()}
        onOpenSettings={() => openPanel({ kind: "settings" })}
        running={running}
        otherOllama={systemStatus?.other_ollama_loaded ?? false}
      >
        {deleteError && (
          <p role="alert" data-testid="delete-error" className="pb-2 text-xs text-danger">
            {deleteError}
          </p>
        )}
        {tab === "chats" ? (
          <ThreadList
            threads={threads}
            activeId={activeId}
            onOpen={openThread}
            onRename={api ? renameThread : undefined}
            onDelete={api ? (id, name) => void deleteThread(id, name) : undefined}
          />
        ) : tab === "students" ? (
          <StudentsTab
            api={api ?? null}
            activeStudentId={student?.id ?? null}
            refreshKey={runEventSeq + testsSeq + reviewSeq + reviewEventSeq}
            onOpenStudent={(id, name) => guarded(() => setStudent({ id, name }))}
            onStudentChanged={() => setTestsSeq((n) => n + 1)}
            onDelete={api ? (id, name) => void deleteStudent(id, name) : undefined}
          />
        ) : (
          <TestsTab
            api={api ?? null}
            activeTestId={panel?.kind === "test" ? panel.testId : null}
            onOpen={(testId) => openPanel({ kind: "test", testId })}
            refreshKey={runEventSeq + testsSeq + reviewSeq + reviewEventSeq}
            autoFocus={focusSearch}
            onDelete={api ? (id, name) => void deleteTest(id, name) : undefined}
          />
        )}
      </Sidebar>
      {api && threadView === null ? (
        <ThreadView
          key={activeId ?? `new-${fresh.seq}`}
          ref={view}
          api={api}
          threadId={activeId}
          notice={notice}
          initialFiles={activeId ? null : fresh.files}
          refreshKey={runEventSeq + reviewSeq + reviewEventSeq}
          hasActiveRun={activeId ? (activeRunThreadIds?.has(activeId) ?? false) : false}
          running={activeId ? threadRunning?.(activeId) : undefined}
          hidden={workspace || (!!api && !!student)}
          onThreadCreated={(id) => {
            setActiveId(id);
            onThreadsChanged?.();
          }}
          onNewThread={newThread}
          onOpenPanel={(v) => openPanel(v)}
          onThreadChanged={onThreadsChanged}
          onRunStarted={(run) => {
            onRunStarted?.(run);
            onThreadsChanged?.();
          }}
        />
      ) : api ? null : (
        <Conversation notice={notice} />
      )}
      </div>
      {api && student && (
        <StudentSkillsView
          key={student.id}
          api={api}
          studentId={student.id}
          name={student.name}
          refreshKey={runEventSeq + testsSeq + reviewSeq + reviewEventSeq}
          onOpenThread={openThread}
        />
      )}
      {workspace && api && shown !== null && !student && (
        <Workspace
          api={api}
          view={shown}
          title={panelTitle(shown)}
          tabs={workspaceTabs(shown, tabSource)}
          onTab={(v) => openPanel(v)}
          actions={
            ownView && activeId && detail ? (
              <ThreadTabActions
                api={api}
                threadId={activeId}
                detail={detail}
                busy={(busyRunThreadIds ?? activeRunThreadIds)?.has(activeId) ?? false}
                makingKey={keyRuns?.pending(activeId) ?? false}
                onRunStarted={(run) => {
                  onRunStarted?.(run);
                  onThreadsChanged?.();
                }}
              />
            ) : undefined
          }
          banner={
            ownView && activeId && detail ? (
              <>
              {notice}
              <ThreadBanner
                api={api}
                detail={detail}
                refreshKey={reviewSeq + reviewEventSeq + runEventSeq}
                running={threadRunning?.(activeId)}
                onChanged={threadChanged}
                keysChanged={keyRegrade.pending(detail.test?.id)}
                onRegrade={detail.test ? () => void keyRegrade.regrade(detail.test!.id) : undefined}
                regradeError={keyRegrade.error}
                compact /* step 22.4.8 (answer 7): one line on every workspace tab */
              />
              </>
            ) : (
              <>
                {notice}
                <TestTitleBar api={api} testId={shown.testId} refreshKey={testsSeq} />
              </>
            )
          }
          printBar={inPrint ? <PrintBar title={panelTitle(shown)} onBack={endPrint} onPrint={startPrint} /> : undefined}
        >
          {contentFor(shown)}
        </Workspace>
      )}
      {!isWorkspace(panel) && (
        <ArtifactPanel open={panel !== null} title={panel ? panelTitle(panel) : ""} onClose={() => setPanel(null)}>
          {contentFor(panel)}
        </ArtifactPanel>
      )}
    </div>
    </LeaveGuardContext.Provider>
  );
}

/** The open thread (`GET /threads/{id}`); `null` without one or while loading. */
function useThreadDetail(api: ApiClient | null, threadId: string | null, refreshKey: number): Schemas["ThreadDetail"] | null {
  const [source, setSource] = useState<{ id: string; detail: Schemas["ThreadDetail"] } | null>(null);
  useEffect(() => {
    if (!api || !threadId) return;
    const ctrl = new AbortController();
    api
      .get("/threads/{id}", { path: { id: threadId }, signal: ctrl.signal })
      .then((d) => setSource({ id: threadId, detail: d }))
      .catch(() => {
        // Without the thread the tabs come from the open view alone.
      });
    return () => ctrl.abort();
  }, [api, threadId, refreshKey]);
  return threadId && source?.id === threadId ? source.detail : null;
}

/** The panel's content for `view` (in the workspace or the side panel). */
function PanelContent({
  api,
  view,
  onTestChanged,
  reviewEventSeq,
  onReviewResolved,
  systemStatus = null,
  onSystemStatusReload,
  print,
  printing = false,
  onKeysChanged,
  keyNote = null,
}: {
  api: ApiClient | null;
  view: PanelView | null;
  onTestChanged?: () => void;
  reviewEventSeq?: number;
  onReviewResolved?: () => void;
  systemStatus?: SystemStatus | null;
  onSystemStatusReload?: () => void;
  /** Print in the test, key and report panels: opens the print view. */
  print: () => void;
  /** The print view is showing. */
  printing?: boolean;
  /** A key of this test changed (step 22.4.5): the re-grade waits for the leave or the button. */
  onKeysChanged?: (testId: string) => void;
  /** The open thread's key run on this Key tab (step 22.6.4). */
  keyNote?: "making" | "failed" | null;
}) {
  if (api && view?.kind === "settings") {
    return <SettingsPanel api={api} status={systemStatus} onStatusReload={onSystemStatusReload} />;
  }
  if (api && view?.kind === "test") {
    return <TestPanel
        key={view.testId}
        api={api}
        testId={view.testId}
        onChanged={() => {
          onTestChanged?.();
          onReviewResolved?.();
        }}
        print={print}
        printing={printing}
        refreshKey={reviewEventSeq}
      />;
  }
  if (api && view?.kind === "answers") {
    return <AnswersPanel key={view.attemptId} api={api} attemptId={view.attemptId} testId={view.testId} />;
  }
  if (api && view?.kind === "report") {
    return (
      <ReportPanel
        key={view.attemptId}
        api={api}
        attemptId={view.attemptId}
        refreshKey={reviewEventSeq}
        print={print}
      />
    );
  }
  if (api && view?.kind === "keys") {
    const testId = view.testId;
    return (
      <KeysPanel
        key={testId}
        api={api}
        testId={testId}
        print={print}
        onKeysChanged={onKeysChanged && (() => onKeysChanged(testId))}
        keyNote={keyNote}
      />
    );
  }
  return <p className="text-muted">Nothing here yet.</p>;
}

/** The test delete dialog's body: the threads that go, the threads that only lose a paper. */
/** The student delete dialog's body: the threads that go, by name (data-model §5.7, D1). */
function StudentDeleteBody({ preview }: { preview: Schemas["StudentDeletePreview"] }) {
  const n = preview.threads.length;
  return (
    <>
      <p>
        The student goes for good. Their tests stay in the bank.
        {n === 0 ? " They have no threads." : n === 1 ? " This thread goes with them:" : ` These ${n} threads go with them:`}
      </p>
      {n > 0 && (
        <ul data-testid="delete-threads" className="max-h-40 list-disc overflow-y-auto pl-5">
          {preview.threads.map((t) => (
            <li key={t.id}>{t.shown_title}</li>
          ))}
        </ul>
      )}
      {preview.kept_threads.length > 0 && (
        <p data-testid="delete-kept-threads">
          {preview.kept_threads.length === 1
            ? "1 thread also has another student's paper; it stays and loses only this student's paper."
            : `${preview.kept_threads.length} threads also have another student's paper; they stay and lose only this student's papers.`}
        </p>
      )}
      <p className="text-muted">This can't be undone here; the daily backup is the way back.</p>
    </>
  );
}

function TestDeleteBody({ preview }: { preview: Schemas["TestDeletePreview"] }) {
  const n = preview.threads.length;
  return (
    <>
      <p>
        The test goes for good, with its key and pages
        {preview.merged_test_ids.length > 0 ? " and the tests merged into it" : ""}.
        {n === 0 ? " No thread uses it." : n === 1 ? " This thread goes with it:" : ` These ${n} threads go with it:`}
      </p>
      {n > 0 && (
        <ul data-testid="delete-threads" className="max-h-40 list-disc overflow-y-auto pl-5">
          {preview.threads.map((t) => (
            <li key={t.id}>{t.shown_title}</li>
          ))}
        </ul>
      )}
      {preview.kept_threads.length > 0 && (
        <p data-testid="delete-kept-threads">
          {preview.kept_threads.length === 1
            ? "1 thread keeps its other test and loses only its paper on this one."
            : `${preview.kept_threads.length} threads keep their other tests and lose only their papers on this one.`}
        </p>
      )}
      <p className="text-muted">This can't be undone here; the daily backup is the way back.</p>
    </>
  );
}
