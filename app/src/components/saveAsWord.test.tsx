// R22.1.6.4: "Save as Word (.docx)" beside Print in the Test, Key and Report workspaces. A click
// calls the export route and shows "Saved <file name>" with Open folder; errors are readable;
// Open folder asks the shell (`open_exports_folder`, no argument) and is not called outside it.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { KeysPanel } from "@/features/panels/KeysPanel";
import { ReportPanel } from "@/features/panels/ReportPanel";
import { TestPanel } from "@/features/panels/TestPanel";
import { FakeStatus, fakeApi } from "@/lib/testApi";

const tauri = vi.hoisted(() => ({ isTauri: vi.fn(() => true), invoke: vi.fn(async () => undefined) }));
vi.mock("@tauri-apps/api/core", () => ({
  isTauri: () => tauri.isTauri(),
  invoke: (...a: unknown[]) => tauri.invoke(...(a as [])),
}));

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
const key = (n: number) => ({ test_id: "T-0001", question_id: `q-${n}`, accepted: ["A"], status: "ai_fast", source: "ai" });
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
  verdicts: [{ question_id: "q-1", printed_number: 1, value: "A", verdict: "correct", points_awarded: 0.25, near_miss: false }],
  explanations: [],
};
const saved = (name: string) => ({ path: `D:\\ETACH\\exports\\${name}`, file_name: name });

beforeEach(() => {
  tauri.isTauri.mockReturnValue(true);
  tauri.invoke.mockClear();
});

describe("save as Word", () => {
  it("test workspace: beside Print, saves the test, then Open folder opens the exports folder", async () => {
    const { api, calls } = fakeApi({
      "GET /tests/{id}": test_,
      "POST /tests/{id}/export": saved("Grade 8 · FinalTerm HK1 - Test.docx"),
    });
    render(<TestPanel api={api} testId="T-0001" print={() => undefined} />);
    const toolbar = await screen.findByTestId("test-toolbar");
    const button = within(toolbar).getByRole("button", { name: "Save as Word (.docx)" });
    expect(within(toolbar).getByTestId("test-print")).toBeInTheDocument();
    fireEvent.click(button);
    const status = await screen.findByTestId("save-docx-saved");
    expect(status.closest("[role=status]")).not.toBeNull();
    await waitFor(() => expect(status).toHaveTextContent("Saved Grade 8 · FinalTerm HK1 - Test.docx"));
    const call = calls.find((c) => c.method === "POST");
    expect(call?.path).toBe("/tests/T-0001/export");
    expect(call?.body).toEqual({ what: "test" });
    fireEvent.click(within(status).getByRole("button", { name: "Open folder" }));
    await waitFor(() => expect(tauri.invoke).toHaveBeenCalledWith("open_exports_folder"));
  });

  it("key workspace: saves the key as its own file", async () => {
    const { api, calls } = fakeApi({
      "GET /tests/{id}": test_,
      "GET /tests/{id}/keys": [key(1), key(2)],
      "POST /tests/{id}/export": saved("Grade 8 - Key.docx"),
    });
    render(<KeysPanel api={api} testId="T-0001" />);
    const toolbar = await screen.findByTestId("keys-toolbar");
    expect(within(toolbar).getByTestId("key-print")).toBeInTheDocument();
    fireEvent.click(within(toolbar).getByRole("button", { name: "Save as Word (.docx)" }));
    await screen.findByText("Grade 8 - Key.docx");
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ what: "key" });
  });

  it("report workspace: a not-graded attempt shows the sidecar's reason, not a code", async () => {
    const { api } = fakeApi({
      "GET /attempts/{id}/report": report,
      "POST /attempts/{id}/report/export": new FakeStatus(409, {
        detail: "This attempt is not graded yet. Grade it first, then save the report.",
      }),
    });
    render(<ReportPanel api={api} attemptId="A-0001" />);
    const toolbar = await screen.findByTestId("report-toolbar");
    expect(within(toolbar).getByTestId("report-print")).toBeInTheDocument();
    fireEvent.click(within(toolbar).getByRole("button", { name: "Save as Word (.docx)" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "Could not save the grade report as Word: This attempt is not graded yet. Grade it first, then save the report.",
    );
    expect(alert.textContent).not.toMatch(/object Object|409/);
  });

  it("outside the app window Open folder does not call the shell and says why", async () => {
    tauri.isTauri.mockReturnValue(false);
    const { api } = fakeApi({
      "GET /attempts/{id}/report": report,
      "POST /attempts/{id}/report/export": saved("Report.docx"),
    });
    render(<ReportPanel api={api} attemptId="A-0001" />);
    fireEvent.click(await screen.findByRole("button", { name: "Save as Word (.docx)" }));
    fireEvent.click(await screen.findByRole("button", { name: "Open folder" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Open folder works in the app window only.");
    expect(tauri.invoke).not.toHaveBeenCalled();
  });
});
