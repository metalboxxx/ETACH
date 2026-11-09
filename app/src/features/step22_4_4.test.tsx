// Step 22.4.4 (R22.4.4.4, PRD D13 v8.0): the score reads x/10 on the grade card, the report and
// the test page; Format help says the points are computed; no points editor note remains (the
// R19.7 points_assumed note is superseded: such items are no longer created). Synthetic data.
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fakeApi } from "@/lib/testApi";
import { testDetailsLine } from "@/lib/testTitle";
import { GradeCard } from "@/features/cards/GradeCard";
import { ReportPanel } from "@/features/panels/ReportPanel";
import { LINE_FORMS, testNotes } from "@/features/panels/TestPanel";

const report = {
  attempt: { id: "A-1", test_id: "T-1", score_earned: 70 / 13, score_possible: 10 },
  report: {
    attempt_id: "A-1",
    run_id: "r1",
    created_at: "",
    summary_vi: "Tóm tắt.",
    uncertain_points: 10 / 13,
    teacher_questions: [],
    weak_points: [],
    careless_notes: [],
  },
  verdicts: [],
  explanations: [],
};

describe("scores out of 10 (R22.4.4.4)", () => {
  it("the latest grade card reads x/10 with up to two decimals", async () => {
    const { api } = fakeApi({ "GET /attempts/{id}/report": report, "GET /attempts/{id}": { answers: [] } });
    render(<GradeCard api={api} latest body={{ attempt_id: "A-1", test_id: "T-1" }} />);
    await waitFor(() => expect(screen.getByTestId("grade-score")).toHaveTextContent("5.38/10"));
    expect(screen.getByTestId("grade-unsure")).toHaveTextContent("0.77 unsure");
  });

  it("an earlier grade card reads x/10", () => {
    const { api } = fakeApi({});
    render(<GradeCard api={api} latest={false} body={{ attempt_id: "A", test_id: "T", score_earned: 7.25, score_possible: 10 }} />);
    expect(screen.getByTestId("grade-card-old")).toHaveTextContent("Graded 7.25/10");
  });

  it("the report reads x/10", async () => {
    const { api } = fakeApi({ "GET /attempts/{id}/report": report });
    render(<ReportPanel api={api} attemptId="A-1" print={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("grade-score")).toHaveTextContent("5.38/10"));
  });

  it("the test page's details line reads 10 points", () => {
    expect(testDetailsLine({ duration_minutes: 45, test_code: null } as never, 10)).toBe("45 minutes · 10 points");
  });
});

describe("computed points (R22.4.4.4)", () => {
  // Step 22.5.2 (D7): the heading carries no points; the value is under the test title.
  it("Format help says every question is worth 10 ÷ the questions and typed points are ignored", () => {
    const heading = LINE_FORMS.find((f) => f.form === "Section heading")!;
    expect(heading.meaning).toContain("10 ÷ the number of graded questions");
    expect(heading.meaning).toContain("Points typed in brackets are ignored");
    expect(heading.meaning).not.toMatch(/assumed/);
  });

  it("a leftover open points_assumed item shows no points editor note", () => {
    const item = {
      id: "R-1",
      kind: "points_assumed",
      status: "open",
      test_id: "T-1",
      attempt_id: null,
      dedupe_key: "points_assumed:s1",
      proposal: { section_id: "s1" },
    };
    const test = { id: "T-1", review: [item], content: { sections: [] } } as never;
    expect(testNotes(test, "I.  [10 points]\n1. Stem\n")).toEqual([]);
  });
});
