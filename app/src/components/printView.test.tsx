// R22.1.1.2 (comment 8): Print in the test, key and report panels opens a print view whose bar
// (hidden when printing: `no-print`) has a visible "Back to …" control that returns to the panel
// the teacher came from, without closing the window. The print window opens after the view.
// Step 22.1.4: these panels open as a workspace (its bar replaces the side panel's chrome), and
// Back from the print view puts focus on the panel's Print button (R22.1.4.5).
// Also the rename wiring of the thread list (R22.1.1.5): PATCH /threads/{id} {title}.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { PanelView } from "@/features/panels/panelView";
import { fakeApi, type FakeCall } from "@/lib/testApi";
import { AppShell } from "./AppShell";

const test_ = {
  id: "T-0001",
  meta: { occasion: "FinalTerm", grade: 8, term: 1, edited_fields: [] },
  content: {
    sections: [
      {
        id: "s1",
        number: 1,
        printed_title: "I. Choose",
        title: "Choose",
        instructions: null,
        points: 0.5,
        points_source: "printed",
        skill: "grammar",
        groups: [
          {
            id: "g1",
            stimulus: null,
            pictures: [],
            questions: [1, 2].map((n) => ({
              id: `q-${n}`,
              number: n,
              printed_number: n,
              page_no: 1,
              answer_form: "choice", context: "single",
              stem: `Stem ${n}`,
              options: [],
              cue: null,
              points: 0.25,
            })),
          },
        ],
      },
    ],
  },
  picture_paths: {},
  pages: [],
  key_pages: [],
};
const key = (n: number) => ({
  test_id: "T-0001",
  question_id: `q-${n}`,
  accepted: ["A"],
  status: "ai_fast",
  source: "ai",
});
const report = {
  attempt: { id: "A-0001", test_id: "T-0001", score_earned: 1, score_possible: 2 },
  report: {
    attempt_id: "A-0001",
    run_id: "r1",
    created_at: "",
    summary_vi: "",
    uncertain_points: 0,
    teacher_questions: [],
    weak_points: [],
    careless_notes: [],
  },
  verdicts: [
    { question_id: "q-1", printed_number: 1, value: "A", verdict: "correct", points_awarded: 0.25, near_miss: false },
  ],
  explanations: [],
};

function api() {
  return fakeApi({
    "GET /tests/{id}": test_,
    "GET /tests/{id}/keys": [key(1), key(2)],
    "GET /attempts/{id}/report": report,
    "GET /attempts/{id}": { answers: [] },
  });
}

const CASES: { name: string; view: PanelView; content: string; printButton: string; back: string }[] = [
  { name: "test", view: { kind: "test", testId: "T-0001" }, content: "test-panel", printButton: "test-print", back: "Back to test" },
  { name: "key", view: { kind: "keys", testId: "T-0001" }, content: "key-list", printButton: "key-print", back: "Back to key" },
  {
    name: "report",
    view: { kind: "report", attemptId: "A-0001", testId: "T-0001" },
    content: "report-rows",
    printButton: "report-print",
    back: "Back to grade report",
  },
];

/** Selectors whose `@media print` rule sets display:none (as in panels.test.tsx). */
function printHidden(): string {
  const dir = path.dirname(fileURLToPath(import.meta.url));
  return readFileSync(path.resolve(dir, "../styles/print.css"), "utf8");
}

describe("print views have a way back (R22.1.1.2)", () => {
  it.each(CASES)("$name: Print → print view with Back; the print window opens after it; Back returns", async (c) => {
    const { api: client } = api();
    let barAtPrint: HTMLElement | null = null;
    const print = vi.fn(() => {
      barAtPrint = screen.queryByTestId("print-bar");
    });
    render(<AppShell connection="open" api={client} initialPanel={c.view} print={print} />);
    await screen.findByTestId(c.content);
    expect(screen.getByTestId("workspace-bar")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId(c.printButton));
    await waitFor(() => expect(print).toHaveBeenCalledOnce());
    expect(barAtPrint).not.toBeNull(); // the view was on screen before the print window opened

    const bar = screen.getByTestId("print-bar");
    expect(bar).toHaveClass("no-print"); // never on paper
    const back = screen.getByRole("button", { name: c.back });
    expect(back).toBeVisible();
    expect(back).toHaveFocus(); // where the teacher lands when the print window closes
    expect(screen.getByTestId("app-shell")).toHaveAttribute("data-print-view", "true");
    expect(screen.queryByTestId("workspace-bar")).toBeNull();
    expect(screen.queryByTestId("workspace-photos")).toBeNull(); // the photos are not printed
    expect(screen.getByTestId(c.content)).toBeInTheDocument(); // same content, not reloaded

    fireEvent.click(back);
    expect(screen.queryByTestId("print-bar")).toBeNull();
    expect(screen.getByTestId("workspace-bar")).toBeInTheDocument(); // the panel the teacher came from
    expect(screen.getByTestId(c.printButton)).toHaveFocus(); // R22.1.4.5
    expect(screen.getByTestId(c.content)).toBeInTheDocument();
    expect(screen.getByTestId("app-shell")).not.toHaveAttribute("data-print-view");
  });

  it("the bar is hidden when printing (.no-print is display:none under @media print)", () => {
    expect(printHidden()).toMatch(/@media print\s*{\s*\.no-print\s*{\s*display:\s*none !important;/);
  });

  it("Esc in the print view goes back to the panel (it does not close it); a second Esc closes the panel", async () => {
    const { api: client } = api();
    render(<AppShell connection="open" api={client} initialPanel={CASES[0]!.view} print={() => {}} />);
    fireEvent.click(await screen.findByTestId("test-print"));
    expect(screen.getByTestId("print-bar")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByTestId("print-bar")).toBeNull();
    expect(screen.getByTestId("artifact-panel")).toBeInTheDocument();
    expect(screen.getByTestId("test-print")).toHaveFocus(); // R22.1.4.5
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByTestId("artifact-panel")).toBeNull();
  });

  it("Print in the bar opens the print window again", async () => {
    const { api: client } = api();
    const print = vi.fn();
    render(<AppShell connection="open" api={client} initialPanel={CASES[0]!.view} print={print} />);
    fireEvent.click(await screen.findByTestId("test-print"));
    await waitFor(() => expect(print).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByTestId("print-again"));
    await waitFor(() => expect(print).toHaveBeenCalledTimes(2));
    expect(screen.getByTestId("print-bar")).toBeInTheDocument();
  });
});

describe("thread rename wiring (R22.1.1.5)", () => {
  it("Rename in the thread list → PATCH /threads/{id} {title}, then the list reloads", async () => {
    const { api: client, calls } = fakeApi({
      "PATCH /threads/{id}": (c: FakeCall) => ({ id: "t1", title: (c.body as { title: string }).title }),
    });
    const reload = vi.fn();
    const threads = [
      {
        thread: { id: "t1", title: "New thread", kind: "filled" as const, test_id: "T-0001", created_at: "" },
        shown_title: "Grade 8 · FinalTerm HK1 · Test 1",
        kind: "filled" as const,
        group: "Chưa rõ",
        student_id: null,
        last_activity: "", open_review_count: 0,
      },
    ];
    render(<AppShell connection="open" api={client} threads={threads} onThreadsChanged={reload} />);
    fireEvent.contextMenu(screen.getByTestId("thread-item"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
    const input = screen.getByRole("textbox", { name: "Thread name" });
    fireEvent.change(input, { target: { value: "An's mid-term" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(reload).toHaveBeenCalled());
    expect(calls.find((c) => c.method === "PATCH")).toMatchObject({ path: "/threads/t1", body: { title: "An's mid-term" } });
  });
});
