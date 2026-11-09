// Step 22.2.4: printed numbers everywhere the teacher looks (R22.2.4.1), Format help (R22.2.4.4)
// and the Test details order (R22.2.4.6). Synthetic test: a left-out listening part, so the paper
// prints 6–40 while the internal numbers are 1–35.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fakeApi } from "@/lib/testApi";
import { AnswersPanel } from "./AnswersPanel";
import { KeysPanel } from "./KeysPanel";
import { ReportPanel } from "./ReportPanel";
import { FormatHelp, LINE_FORMS, TestPanel } from "./TestPanel";

const N = 35;
const SHIFT = 5;
const qid = (n: number) => `q-${n}`;

const test_ = {
  id: "T-0001",
  meta: { occasion: "FinalTerm", grade: 8, term: 1, school: "THCS A", year: "2025", test_number: "7", edited_fields: [] },
  content: {
    sections: [
      {
        id: "s1",
        number: 1,
        printed_title: "II. Choose the best answer",
        title: "Choose",
        instructions: null,
        points: 8.75,
        points_source: "printed",
        skill: "grammar",
        groups: [
          {
            id: "g1",
            stimulus: null,
            pictures: [],
            questions: Array.from({ length: N }, (_, i) => ({
              id: qid(i + 1),
              number: i + 1,
              printed_number: i + 1 + SHIFT,
              page_no: 1,
              answer_form: "sentence", context: "single",
              stem: `Stem ${i + 1 + SHIFT}`,
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
  points_possible: 8.75,
  source_run_id: "R1",
  merged_into: null,
  created_at: "2026-10-04T00:00:00Z",
  updated_at: "2026-10-04T00:00:00Z",
  picture_paths: {},
  review: [],
};

const printed = Array.from({ length: N }, (_, i) => i + 1 + SHIFT);

/** The leading "<n>." of each element, as numbers. */
const leading = (els: HTMLElement[]) => els.map((e) => Number(/(\d+)\./.exec(e.textContent ?? "")?.[1]));

describe("printed numbers on screen (R22.2.4.1)", () => {
  it("the test page and the print view show 6–40", async () => {
    const { api } = fakeApi({ "GET /tests/{id}": test_ });
    const { rerender } = render(<TestPanel api={api} testId="T-0001" printing />);
    const qs = await screen.findAllByTestId("test-question");
    expect(leading(qs)).toEqual(printed);
    rerender(<TestPanel api={api} testId="T-0001" printing />);
    expect(screen.queryByText(/^1\.$/)).toBeNull();
  });

  it("the Key shows 6–40 in internal order", async () => {
    const keys = Array.from({ length: N }, (_, i) => ({
      test_id: "T-0001",
      question_id: qid(N - i),
      accepted: ["A"],
      status: "ai_fast",
      source: "ai",
    }));
    const { api } = fakeApi({ "GET /tests/{id}/keys": keys, "GET /tests/{id}": test_ });
    render(<KeysPanel api={api} testId="T-0001" />);
    const rows = await screen.findAllByTestId("key-row");
    expect(leading(rows)).toEqual(printed);
  });

  it("Student answers show 6–40", async () => {
    const answers = Array.from({ length: N }, (_, i) => ({
      attempt_id: "A-0001",
      question_id: qid(i + 1),
      printed_number: i + 1 + SHIFT,
      page_no: 1,
      value: "B",
      value_norm: "b",
      location: "circled_option",
      confidence: 0.9,
      reading_unsure: false,
      alt_value: null,
      alt_question_id: null,
      verdict: "ungraded",
      points_awarded: null,
      teacher_override: null,
    }));
    const { api } = fakeApi({ "GET /attempts/{id}": { attempt: {}, answers, pages: [] }, "GET /tests/{id}": test_ });
    render(<AnswersPanel api={api} attemptId="A-0001" testId="T-0001" />);
    const rows = await screen.findAllByTestId("answer-row");
    expect(leading(rows)).toEqual(printed);
  });

  it("the report numbers explanations by the printed number", async () => {
    const report = {
      attempt: { id: "A-0001", test_id: "T-0001", score_earned: 1, score_possible: 8.75 },
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
      verdicts: [{ question_id: qid(1), printed_number: 6, value: "A", verdict: "incorrect", points_awarded: 0, near_miss: false }],
      explanations: [{ question_id: qid(1), wrong_answer_norm: "a", text_vi: "Giải thích." }],
    };
    const { api } = fakeApi({ "GET /attempts/{id}/report": report, "GET /attempts/{id}": { answers: [] } });
    render(<ReportPanel api={api} attemptId="A-0001" />);
    const ex = await screen.findByTestId("explanation");
    expect(ex).toHaveTextContent(/^6\. Giải thích\.$/);
  });
});

describe("Format help (R22.2.4.4)", () => {
  it("a footer button toggles the table of every line form; closed, it leaves focus alone", async () => {
    render(
      <>
        <textarea aria-label="editor" />
        <FormatHelp />
      </>,
    );
    const editor = screen.getByLabelText("editor");
    editor.focus();
    const button = screen.getByTestId("format-help");
    const region = screen.getByTestId("format-help-region");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveAttribute("aria-controls", region.id);
    expect(region).not.toBeVisible();
    expect(document.activeElement).toBe(editor);

    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(region).toBeVisible();
    const rows = within(region).getAllByTestId("format-help-row");
    expect(rows.map((r) => within(r).getByRole("rowheader").textContent)).toEqual([
      "Escaped",
      "Passage",
      "Picture",
      "Page",
      "Section heading",
      "Question",
      "Option",
      "Cue",
      "Text",
    ]);
    expect(LINE_FORMS.every((f) => f.example.length > 0)).toBe(true);

    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "false");
    await waitFor(() => expect(region).not.toBeVisible());
  });

  it("the test page has it under the text", async () => {
    const { api } = fakeApi({ "GET /tests/{id}": test_ });
    render(<TestPanel api={api} testId="T-0001" />);
    expect(await screen.findByTestId("format-help")).toHaveTextContent("Format help");
  });
});

describe("Test details (R22.2.4.6)", () => {
  it("Test name first, then grade, occasion + term, school or series, year, Test number; the rest folded", async () => {
    const { api } = fakeApi({ "GET /tests/{id}": test_ });
    render(<TestPanel api={api} testId="T-0001" />);
    const name = await screen.findByTestId("test-name");
    expect(name).toHaveTextContent("Test name: Grade 8 - Final Term 1 - THCS A - 2025 - Test 7");
    const toolbar = screen.getByTestId("test-toolbar");
    expect(toolbar.firstElementChild).toBe(name);
    const more = screen.getByTestId("more-details");
    const main = within(toolbar)
      .getAllByTestId("meta-chip")
      .filter((c) => !more.contains(c));
    expect(main.map((c) => c.dataset.field)).toEqual(["grade", "occasion", "term", "school", "source", "year", "test_number"]);
    expect(main.at(-1)).toHaveTextContent(/^Test number:/);
    expect(more).not.toHaveAttribute("open");
    expect(within(more).getByText("More details").tagName).toBe("SUMMARY");
    const folded = within(more).getAllByTestId("meta-chip").map((c) => c.dataset.field);
    expect(folded).toContain("variant");
    expect(within(more).getAllByTestId("meta-chip-hint")[0]).toHaveTextContent("The paper's version, e.g. đề A / đề B");
  });
});
