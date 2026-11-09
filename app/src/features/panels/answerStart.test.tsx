// R22.3.6.2 (decision D6): the print view shows a rewrite's printed opening words as its answer
// line ("My brother ____"); a question without `answer_start` shows none (older content).
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CleanTest } from "./TestPanel";

const question = (n: number, answer_start?: string | null) => ({
  id: `q-${n}`,
  number: n,
  printed_number: n,
  page_no: 1,
  answer_form: "sentence", context: "single",
  stem: `He stayed up late ${n}. (used to)`,
  options: null,
  cue: null,
  points: 0.5,
  ...(answer_start === undefined ? {} : { answer_start }),
});

const test_ = {
  id: "T-1",
  meta: { occasion: "FinalTerm", edited_fields: [] },
  content: {
    sections: [
      {
        id: "s1",
        number: 1,
        printed_title: "VI",
        title: "Rewrite",
        instructions: "Rewrite the sentences.",
        points: 1,
        points_source: "printed",
        skill: "rewrite",
        groups: [{ id: "g1", stimulus: null, pictures: [], questions: [question(1, "My brother"), question(2)] }],
      },
    ],
  },
  points_possible: 1,
} as unknown as Parameters<typeof CleanTest>[0]["test"];

describe("answer_start in the print view", () => {
  it("shows the opening words as the answer line, only where there are some", () => {
    render(<CleanTest test={test_} />);
    const starts = screen.getAllByTestId("answer-start");
    expect(starts).toHaveLength(1);
    expect(starts[0]).toHaveTextContent("My brother ____");
    const [first] = screen.getAllByTestId("test-question");
    expect(first).toContainElement(starts[0] ?? null);
  });
});
