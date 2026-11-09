// Step 22.6.3 (APP_TEST). R22.6.3.3: hovering or focusing "AI unsure key" for a key whose check
// is `unsure` shows "The checker was not sure." followed by its reasoning.
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KeysPanel, CHECK_UNSURE, UNSURE_KEY, checkerTip } from "@/features/panels/KeysPanel";
import { fakeApi } from "@/lib/testApi";

vi.mock("@tauri-apps/api/core", () => ({ isTauri: () => false, invoke: vi.fn(async () => undefined) }));

const question = (n: number) => ({
  id: `q-${n}`,
  number: n,
  printed_number: n,
  page_no: 1,
  context: "single",
  answer_form: "choice",
  stem: `Question ${n}`,
  options: [
    { label: "A", text: "a" },
    { label: "B", text: "b" },
  ],
  cue: null,
  answer_start: null,
  points: 0.25,
});

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
        graded: true,
        groups: [{ id: "g1", stimulus: null, pictures: [], questions: [question(1), question(2)] }],
      },
    ],
  },
  review: [],
};

const REASONING = "Both A and B could fit the sentence.";

describe("R22.6.3.3 Key tab: an unsure checker", () => {
  it("R22.6.3.3 checkerTip says the checker was not sure, then its reasoning", () => {
    expect(CHECK_UNSURE).toBe("The checker was not sure.");
    expect(checkerTip({ status: "unsure", answer: null, reasoning: REASONING })).toEqual([
      "The checker was not sure.",
      REASONING,
    ]);
    expect(checkerTip({ status: "unsure", answer: null, reasoning: null })).toEqual([
      "The checker was not sure.",
    ]);
    expect(checkerTip({ status: "disagreed", answer: "B", reasoning: null })).toEqual([
      "The checker's answer: B",
    ]);
  });

  it("R22.6.3.3 shows it on hover and keyboard focus and as the description", async () => {
    const { api } = fakeApi({
      "GET /tests/{id}/keys": [
        {
          question_id: "q-1",
          accepted: ["A"],
          status: "ai_uncertain",
          checker: { status: "unsure", answer: null, reasoning: REASONING },
        },
        { question_id: "q-2", accepted: ["B"], status: "ai_verified", checker: null },
      ],
      "GET /tests/{id}": test_,
    });
    render(<KeysPanel api={api} testId="T-0001" />);
    const rows = await screen.findAllByTestId("key-row");
    const label = within(rows[0]!).getByTestId("key-status");
    expect(label).toHaveTextContent(UNSURE_KEY);
    expect(label).toHaveAttribute("tabindex", "0");
    expect(label).toHaveAccessibleDescription(`The checker was not sure.${REASONING}`);
    const tip = within(rows[0]!).getByTestId("key-checker-tip");
    expect(tip).toHaveTextContent(`The checker was not sure.${REASONING}`);
    expect(tip).toHaveAttribute("data-open", "false");
    fireEvent.mouseEnter(label.parentElement!);
    expect(tip).toHaveAttribute("data-open", "true");
    fireEvent.mouseLeave(label.parentElement!);
    fireEvent.focus(label);
    expect(tip).toHaveAttribute("data-open", "true");
  });
});
