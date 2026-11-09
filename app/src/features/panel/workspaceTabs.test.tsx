// R22.2.2.1: the workspace tabs Test · Key · Student answers · Report (PRD §10 v5.2, comment 5).
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AppShell } from "@/components/AppShell";
import { workspaceTabs } from "@/features/panels/panelView";
import { fakeApi } from "@/lib/testApi";

const TEXT = "— Page 1 —\n\nI.  [0.5 points, assumed]\nChoose.\n\n1. She goes to school.\n   A. go    B. goes\n";

const test_ = {
  id: "T-0001",
  meta: { occasion: "FinalTerm", grade: 8 },
  content: { sections: [] },
  content_schema_version: 1,
  fingerprint: "",
  points_possible: 0.5,
  source_run_id: null,
  merged_into: null,
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
  picture_paths: {},
  pages: [{ page_no: 1, file_id: "f-test" }],
  key_pages: [],
  content_text: TEXT,
  review: [],
};

function thread(status: "extracted" | "graded") {
  return {
    thread: { id: "th1", title: "New thread", kind: "filled", test_id: "T-0001", created_at: "2026-10-01T00:00:00Z" },
    shown_title: "An",
    attempt: { id: "A-0001", test_id: "T-0001", thread_id: "th1", status },
    test: { id: "T-0001" },
    test_display_name: "Test 1",
    student: null,
  };
}

function setup(status: "extracted" | "graded" = "extracted") {
  window.sessionStorage.setItem("etach.activeThread", JSON.stringify("th1"));
  const { api, calls } = fakeApi({
    "GET /tests/{id}": test_,
    "GET /tests/{id}/keys": [],
    "GET /attempts/{id}": { answers: [], pages: [{ page_no: 1, file_id: "f-att" }] },
    "GET /threads/{id}": thread(status),
    "GET /threads/{id}/messages": [],
    "GET /threads": [],
  });
  render(<AppShell connection="open" api={api} threads={[]} initialPanel={{ kind: "test", testId: "T-0001" }} />);
  return { calls };
}

const tabNames = () => within(screen.getByTestId("workspace-tabs")).getAllByRole("tab").map((t) => t.textContent);

afterEach(() => window.sessionStorage.clear());

describe("workspaceTabs", () => {
  const thread_ = { testId: "T-0001", attemptId: "A-0001", graded: false };
  it("shows only the tabs with something to show", () => {
    const view = { kind: "test", testId: "T-0001" } as const;
    expect(workspaceTabs(view, null).map((t) => t.label)).toEqual(["Test", "Key"]);
    expect(workspaceTabs(view, thread_).map((t) => t.label)).toEqual(["Test", "Key", "Student answers"]);
    expect(workspaceTabs(view, { ...thread_, graded: true }).map((t) => t.label)).toEqual([
      "Test",
      "Key",
      "Student answers",
      "Report",
    ]);
  });
  it("ignores a thread that belongs to another test", () => {
    const view = { kind: "keys", testId: "T-0009" } as const;
    expect(workspaceTabs(view, { ...thread_, graded: true }).map((t) => t.label)).toEqual(["Test", "Key"]);
  });
  it("a report view always has its Report tab", () => {
    const view = { kind: "report", attemptId: "A-0001", testId: "T-0001" } as const;
    expect(workspaceTabs(view, null).map((t) => t.label)).toEqual(["Test", "Key", "Student answers", "Report"]);
  });
});

describe("workspace tab list (R22.2.2.1)", () => {
  it("lists the thread's tabs and switches panel without Back", async () => {
    setup("graded");
    await waitFor(() => expect(tabNames()).toEqual(["Test", "Key", "Student answers", "Report"]));
    expect(screen.getByRole("tablist", { name: "Workspace" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Test" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: "Key" }));
    await waitFor(() => expect(screen.getByTestId("workspace")).toHaveAttribute("data-kind", "keys"));
    expect(screen.getByRole("tab", { name: "Key" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Key" })).toHaveFocus();
  });

  it("the photos follow the tab: test pages for Test/Key, attempt pages for Student answers", async () => {
    const { calls } = setup();
    await waitFor(() => expect(tabNames()).toContain("Student answers"));
    fireEvent.click(screen.getByRole("tab", { name: "Student answers" }));
    await waitFor(() => expect(screen.getByTestId("workspace")).toHaveAttribute("data-kind", "answers"));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/attempts/A-0001"))).toBe(true));
    expect(screen.getByTestId("workspace-photos")).toHaveTextContent(/these student answers|1/);
  });

  it("arrow keys move along the tabs and Enter opens one", async () => {
    setup("graded");
    await waitFor(() => expect(tabNames()).toHaveLength(4));
    const first = screen.getByRole("tab", { name: "Test" });
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Key" })).toHaveFocus();
    fireEvent.keyDown(screen.getByRole("tab", { name: "Key" }), { key: "ArrowLeft" });
    fireEvent.keyDown(first, { key: "End" });
    expect(screen.getByRole("tab", { name: "Report" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Report" })).toHaveAttribute("tabindex", "-1");
    // a native button: Enter and Space are a click
    fireEvent.click(screen.getByRole("tab", { name: "Report" }));
    await waitFor(() => expect(screen.getByTestId("workspace")).toHaveAttribute("data-kind", "report"));
  });

  it("with unsaved test text the leave dialog comes first; Cancel keeps the text", async () => {
    setup();
    const area = await screen.findByTestId("test-text");
    await waitFor(() => expect(tabNames()).toContain("Key"));
    fireEvent.change(area, { target: { value: TEXT + "more" } });
    fireEvent.click(screen.getByRole("tab", { name: "Key" }));
    const dialog = await screen.findByTestId("confirm-dialog");
    expect(dialog).toHaveTextContent("Leave without saving?");
    fireEvent.click(within(dialog).getByTestId("confirm-cancel"));
    expect(screen.getByTestId("workspace")).toHaveAttribute("data-kind", "test");
    expect(screen.getByTestId("test-text")).toHaveValue(TEXT + "more");
    fireEvent.click(screen.getByRole("tab", { name: "Key" }));
    fireEvent.click(within(await screen.findByTestId("confirm-dialog")).getByTestId("confirm-ok"));
    await waitFor(() => expect(screen.getByTestId("workspace")).toHaveAttribute("data-kind", "keys"));
  });
});
