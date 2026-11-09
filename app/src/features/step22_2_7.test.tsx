// Step 22.2.7: the teacher's answers. R22.2.7.1 (AI unsure grade), R22.2.7.3 (Test name, Units,
// Tags) and R22.2.7.4 (focus after the last thread is deleted, re-verifier F5). Synthetic data only.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnswersPanel, UNSURE_GRADE } from "@/features/panels/AnswersPanel";
import { ReportPanel } from "@/features/panels/ReportPanel";
import { TestPanel, parseList } from "@/features/panels/TestPanel";
import { ThreadList } from "@/features/threads/ThreadList";
import { NEW_THREAD_TESTID, type ThreadSummary } from "@/features/threads/threads";
import { fakeApi, type FakeCall } from "@/lib/testApi";

const meta0 = { occasion: "UnitTest", grade: 7, year: "2025", edited_fields: [] as string[], extra: {}, units: [], tags: [] };

function testOf(meta: Record<string, unknown>) {
  return {
    id: "T-0001",
    meta,
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
                answer_form: "sentence", context: "single",
                stem: `Stem ${n}`,
                options: null,
                cue: null,
                points: 0.25,
              })),
            },
          ],
        },
      ],
    },
    content_schema_version: 1,
    fingerprint: "f",
    points_possible: 0.5,
    source_run_id: "R1",
    merged_into: null,
    created_at: "2026-10-04T00:00:00Z",
    updated_at: "2026-10-04T00:00:00Z",
    picture_paths: {},
    review: [],
  };
}

/** A PATCH that applies `display_name` / `units` / `tags` the way the sidecar does. */
function patching() {
  let meta: Record<string, unknown> = { ...meta0 };
  return {
    "GET /tests/{id}": () => testOf(meta),
    "PATCH /tests/{id}": (call: FakeCall) => {
      const change = (call.body as { meta: Record<string, unknown> }).meta;
      const next = { ...meta, ...change };
      if ("display_name" in change) {
        delete next.display_name;
        const typed = change.display_name;
        const edited = (meta.edited_fields as string[]).filter((f) => f !== "display_name");
        next.extra = typed ? { display_name: typed } : {};
        next.edited_fields = typed ? [...edited, "display_name"] : edited;
      }
      meta = next;
      return testOf(meta);
    },
  };
}

describe("AI unsure grade (R22.2.7.1)", () => {
  const answer = (verdict: string) => ({
    question_id: "q-1",
    printed_number: 1,
    page_no: 1,
    value: "B",
    value_norm: "b",
    location: "circled_option",
    confidence: 0.9,
    reading_unsure: false,
    alt_value: null,
    alt_question_id: null,
    verdict,
    points_awarded: null,
    teacher_override: null,
  });

  it("Student answers shows the label, not a bare ?", async () => {
    const { api } = fakeApi({
      "GET /attempts/{id}": { attempt: {}, answers: [answer("uncertain")], pages: [] },
      "GET /tests/{id}": testOf(meta0),
    });
    render(<AnswersPanel api={api} attemptId="A-0001" testId="T-0001" />);
    const mark = await screen.findByTestId("answer-mark");
    expect(mark).toHaveTextContent(UNSURE_GRADE);
    expect(UNSURE_GRADE).toBe("AI unsure grade");
  });

  it("the report panel shows the label; no verdict cell is a bare ?", async () => {
    const report = {
      attempt: { id: "A-0001", test_id: "T-0001", score_earned: 0.25, score_possible: 0.5 },
      report: {
        attempt_id: "A-0001",
        run_id: "r1",
        created_at: "",
        summary_vi: "",
        uncertain_points: 0.25,
        teacher_questions: [],
        weak_points: [],
        careless_notes: [],
      },
      verdicts: [
        { question_id: "q-1", printed_number: 1, value: "A", verdict: "uncertain", points_awarded: null, near_miss: false },
        { question_id: "q-2", printed_number: 2, value: "B", verdict: "correct", points_awarded: 0.25, near_miss: false },
      ],
      explanations: [],
    };
    const { api } = fakeApi({ "GET /attempts/{id}/report": report, "GET /attempts/{id}": { answers: [] } });
    render(<ReportPanel api={api} attemptId="A-0001" />);
    const marks = await screen.findAllByTestId("report-mark");
    expect(marks.map((m) => m.textContent)).toEqual(["AI unsure grade", "✓"]);
    expect(marks.some((m) => m.textContent === "?")).toBe(false);
  });
});

describe("Test name, Units and Tags (R22.2.7.3)", () => {
  it("parseList splits comma-separated text", () => {
    expect(parseList(" Unit 1, Unit 2 ,, ")).toEqual(["Unit 1", "Unit 2"]);
    expect(parseList("")).toEqual([]);
  });

  it("a typed name is saved on Enter; Use automatic name sends null and goes back", async () => {
    const { api, calls } = fakeApi(patching());
    render(<TestPanel api={api} testId="T-0001" />);
    const chip = await screen.findByTestId("test-name-chip");
    expect(chip).toHaveTextContent("Test name: Grade 7 - Unit Test - 2025");
    expect(screen.queryByTestId("test-name-auto")).toBeNull();
    fireEvent.click(chip);
    const input = screen.getByTestId("test-name-chip-input");
    fireEvent.change(input, { target: { value: "Đề ôn tập 1" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(screen.getByTestId("test-name-chip")).toHaveTextContent("Test name: Đề ôn tập 1"));
    const patches = () => calls.filter((c) => c.method === "PATCH").map((c) => c.body);
    expect(patches()).toEqual([{ meta: { display_name: "Đề ôn tập 1" } }]);
    fireEvent.click(screen.getByRole("button", { name: "Use automatic name" }));
    await waitFor(() => expect(screen.getByTestId("test-name-chip")).toHaveTextContent("Test name: Grade 7 - Unit Test - 2025"));
    expect(patches().at(-1)).toEqual({ meta: { display_name: null } });
    expect(screen.queryByTestId("test-name-auto")).toBeNull();
  });

  it("Escape cancels the name edit; the automatic name typed again saves nothing", async () => {
    const { api, calls } = fakeApi(patching());
    render(<TestPanel api={api} testId="T-0001" />);
    fireEvent.click(await screen.findByTestId("test-name-chip"));
    let input = screen.getByTestId("test-name-chip-input");
    fireEvent.change(input, { target: { value: "Other" } });
    fireEvent.keyDown(input, { key: "Escape" });
    fireEvent.click(screen.getByTestId("test-name-chip"));
    input = screen.getByTestId("test-name-chip-input");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(calls.filter((c) => c.method === "PATCH")).toEqual([]);
  });

  it("Units and Tags are edited as comma-separated text under More details", async () => {
    const { api, calls } = fakeApi(patching());
    render(<TestPanel api={api} testId="T-0001" />);
    await screen.findByTestId("test-name-chip");
    const units = document.querySelector<HTMLElement>('[data-testid="meta-chip"][data-field="units"]')!;
    expect(units).toHaveTextContent("Units: –");
    fireEvent.click(units);
    const input = screen.getByRole("textbox", { name: "Units" });
    fireEvent.change(input, { target: { value: "Unit 1, Unit 2" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() =>
      expect(document.querySelector('[data-testid="meta-chip"][data-field="units"]')).toHaveTextContent("Units: Unit 1, Unit 2"),
    );
    const tags = document.querySelector<HTMLElement>('[data-testid="meta-chip"][data-field="tags"]')!;
    fireEvent.click(tags);
    const tagInput = screen.getByRole("textbox", { name: "Tags" });
    fireEvent.change(tagInput, { target: { value: "hard" } });
    fireEvent.keyDown(tagInput, { key: "Enter" });
    await waitFor(() => expect(document.querySelector('[data-testid="meta-chip"][data-field="tags"]')).toHaveTextContent("Tags: hard"));
    const patches = calls.filter((c) => c.method === "PATCH").map((c) => c.body);
    expect(patches).toEqual([{ meta: { units: ["Unit 1", "Unit 2"] } }, { meta: { tags: ["hard"] } }]);
  });
});

describe("focus after the last thread is deleted (R22.2.7.4, F5)", () => {
  it("goes to the New thread button", () => {
    const row = {
      thread: { id: "t1", title: "New thread", test_id: "T-0001", kind: "filled", created_at: "2026-10-01T00:00:00Z" },
      shown_title: "Học Sinh A - Grade 7",
      kind: "filled",
      group: "Học Sinh A",
      student_id: "S-0001",
      last_activity: "2026-10-01T00:00:00Z",
      open_review_count: 0,
    } as ThreadSummary;
    const view = (threads: ThreadSummary[]) => (
      <>
        <button type="button" data-testid={NEW_THREAD_TESTID}>
          New thread
        </button>
        <ThreadList threads={threads} activeId={null} onOpen={() => {}} onDelete={() => {}} />
      </>
    );
    const { rerender } = render(view([row]));
    fireEvent.click(screen.getByTestId("thread-menu-button"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete…" }));
    act(() => (document.activeElement as HTMLElement | null)?.blur());
    rerender(view([]));
    expect(screen.getByTestId(NEW_THREAD_TESTID)).toHaveFocus();
  });
});
