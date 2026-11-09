// R22.5.3.4 (app part): the print view and Save as Word work per answer form (D9). A test holding
// one question of each form — choice with letters, choice with T/F (the two options the sidecar
// adds), word, sentence with its answer start, writing — renders every question in the print view
// with what its form needs, and Save as Word sends that test to the export route. The .docx itself
// is written by the sidecar and checked by its own tests.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TestPanel } from "@/features/panels/TestPanel";
import { fakeApi } from "@/lib/testApi";

vi.mock("@tauri-apps/api/core", () => ({ isTauri: () => false, invoke: vi.fn(async () => undefined) }));

const q = (n: number, fields: Record<string, unknown>) => ({
  id: `q-${n}`,
  number: n,
  printed_number: n,
  page_no: 1,
  context: "single",
  options: null,
  cue: null,
  answer_start: null,
  points: 0.25,
  ...fields,
});

const test_ = {
  id: "T-0001",
  meta: { occasion: "FinalTerm", grade: 8, term: 1, edited_fields: [] },
  content: {
    sections: [
      {
        id: "s1",
        number: 1,
        printed_title: "I. Mixed",
        title: "Mixed",
        instructions: null,
        points: 1.25,
        points_source: "printed",
        skill: "grammar",
        graded: true,
        groups: [
          {
            id: "g1",
            stimulus: null,
            pictures: [],
            questions: [
              q(1, {
                answer_form: "choice",
                stem: "She ___ to school every day.",
                options: [
                  { label: "A", text: "go" },
                  { label: "B", text: "goes" },
                  { label: "C", text: "going" },
                  { label: "D", text: "gone" },
                ],
              }),
              q(2, {
                answer_form: "choice",
                stem: "Lan lives in Hue.",
                options: [
                  { label: "T", text: "True" },
                  { label: "F", text: "False" },
                ],
              }),
              q(3, { answer_form: "word", stem: "He is very ___.", cue: "HAPPINESS" }),
              q(4, { answer_form: "sentence", stem: "He stayed up late. (used to)", answer_start: "He used to" }),
              q(5, { answer_form: "writing", context: null, stem: "Write about your best friend." }),
            ],
          },
        ],
      },
    ],
  },
  picture_paths: {},
  pages: [],
  key_pages: [],
};

const question = (qs: HTMLElement[], n: number) => {
  const el = qs.find((e) => e.dataset.questionId === `q-${n}`);
  if (!el) throw new Error(`question ${n} not rendered`);
  return el;
};

describe("print view and Save as Word per answer form (R22.5.3.4)", () => {
  it("the print view renders a question of each form with what its form needs", async () => {
    const { api } = fakeApi({ "GET /tests/{id}": test_ });
    render(<TestPanel api={api} testId="T-0001" printing />);
    const qs = await screen.findAllByTestId("test-question");
    expect(qs).toHaveLength(5);

    const choice = question(qs, 1);
    expect(choice).toHaveTextContent("She ___ to school every day.");
    for (const o of ["A. go", "B. goes", "C. going", "D. gone"]) expect(choice).toHaveTextContent(o);

    const trueFalse = question(qs, 2);
    expect(trueFalse).toHaveTextContent("T. True");
    expect(trueFalse).toHaveTextContent("F. False");

    const word = question(qs, 3);
    expect(word).toHaveTextContent("He is very ___.");
    expect(word).toHaveTextContent("(HAPPINESS)");
    expect(within(word).queryByTestId("answer-start")).toBeNull();

    const sentence = question(qs, 4);
    expect(within(sentence).getByTestId("answer-start")).toHaveTextContent("He used to ____");

    const writing = question(qs, 5);
    expect(writing).toHaveTextContent("Write about your best friend.");
    expect(within(writing).queryByTestId("answer-start")).toBeNull();

    // No question type or form name is printed on the page.
    const page = screen.getByTestId("clean-test");
    expect(page.textContent).not.toMatch(/\b(choice|sentence|writing|mcq|true_false|short_answer)\b/);
  });

  it("Save as Word sends the test holding every form to the export route", async () => {
    const { api, calls } = fakeApi({
      "GET /tests/{id}": test_,
      "POST /tests/{id}/export": { path: "D:\\ETACH\\exports\\Test.docx", file_name: "Test.docx" },
    });
    render(<TestPanel api={api} testId="T-0001" print={() => undefined} />);
    const toolbar = await screen.findByTestId("test-toolbar");
    fireEvent.click(within(toolbar).getByRole("button", { name: "Save as Word (.docx)" }));
    await waitFor(() => expect(screen.getByTestId("save-docx-saved")).toHaveTextContent("Saved Test.docx"));
    const call = calls.find((c) => c.method === "POST");
    expect(call?.path).toBe("/tests/T-0001/export");
    expect(call?.body).toEqual({ what: "test" });
  });
});
