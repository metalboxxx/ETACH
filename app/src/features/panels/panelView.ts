/**
 * What the artifact panel shows (PRD §10.1). One panel at a time: opening another replaces it.
 * `report` is the printable grade report of an attempt; `keys` is the key editor and the key
 * print (D4, the key copy) of a test (step 19).
 *
 * Workspace view (PRD §10, v4.13; step 22.1.4): Test, Key, Answers and Report open as a workspace
 * that replaces the conversation, with the original photos on the right. `page` is the photo the
 * viewer starts at (1-based, in the viewer's list), e.g. from a thumbnail on the extraction card.
 * Settings opens as the side panel next to the conversation (the Review panel is gone, PRD D27).
 */
export type PanelView =
  | { kind: "settings" }
  | { kind: "test"; testId: string; page?: number }
  | { kind: "answers"; attemptId: string; testId: string; page?: number }
  | { kind: "report"; attemptId: string; testId: string }
  | { kind: "keys"; testId: string };

export type WorkspaceView = Extract<PanelView, { kind: "test" | "answers" | "report" | "keys" }>;

/** Test, Key, Answers and Report open as a workspace; Settings as the side panel. */
export function isWorkspace(view: PanelView | null): view is WorkspaceView {
  return view !== null && view.kind !== "settings";
}

export function panelTitle(view: PanelView): string {
  switch (view.kind) {
    case "settings":
      return "Settings";
    case "test":
      return "Test";
    case "answers":
      return "Student answers";
    case "report":
      return "Grade report";
    case "keys":
      return "Key";
  }
}

/** What the open thread has, for the workspace tabs (from `GET /threads/{id}`). */
export interface TabSource {
  testId: string | null;
  attemptId: string | null;
  /** The attempt has a grade (status graded or reviewed). */
  graded: boolean;
}

export interface WorkspaceTab {
  label: "Test" | "Key" | "Student answers" | "Report";
  view: WorkspaceView;
}

/**
 * The workspace tabs (PRD §10 v5.2, comment 5): Test · Key · Student answers · Report, each only
 * when it has something to show. `thread` is the open thread's test and attempt; it is used when
 * it belongs to the open view (the same test or attempt), otherwise the view alone decides.
 */
export function workspaceTabs(view: WorkspaceView, thread: TabSource | null): WorkspaceTab[] {
  const viewAttempt = "attemptId" in view ? view.attemptId : null;
  const fits = !!thread && (thread.testId === view.testId || (!!viewAttempt && thread.attemptId === viewAttempt));
  const testId = view.testId;
  const attemptId = viewAttempt ?? (fits ? thread.attemptId : null);
  const graded = view.kind === "report" || (fits && !!thread.graded && thread.attemptId === attemptId);
  const tabs: WorkspaceTab[] = [
    { label: "Test", view: { kind: "test", testId } },
    { label: "Key", view: { kind: "keys", testId } },
  ];
  if (attemptId) tabs.push({ label: "Student answers", view: { kind: "answers", attemptId, testId } });
  if (attemptId && graded) tabs.push({ label: "Report", view: { kind: "report", attemptId, testId } });
  return tabs;
}
