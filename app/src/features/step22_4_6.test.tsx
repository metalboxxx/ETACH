/**
 * Step 22.4.6: report wording and order. R22.4.6.2 the report shows skill names, never a
 * taxonomy code; R22.4.6.3 explanations written as 28, 17, 27 are shown as 17, 27, 28.
 */
import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { fakeApi } from "@/lib/testApi";
import { ReportPanel } from "@/features/panels/ReportPanel";
import { GradeCard } from "@/features/cards/GradeCard";

const CODE = /\b(?:VOC-TOPIC|GR-[A-Z]+-[A-Z0-9]+)\b/;

const verdict = (id: string, n: number) => ({
  question_id: id,
  printed_number: n,
  value: "A",
  verdict: "incorrect" as const,
  points_awarded: 0,
  near_miss: false,
});

const explanation = (id: string, wrong: string) => ({
  test_id: "T-0001",
  question_id: id,
  wrong_answer_norm: wrong,
  error_type: "gap",
  text_vi: `Giải thích ${id} ${wrong}: từ vựng chủ đề.`,
  status: "ai",
  llm_call_id: "c",
});

// What the route sends (the sidecar test checks the route): names, codes only in skill_tag.
const report = {
  attempt: { id: "A-0001", test_id: "T-0001", score_earned: 0, score_possible: 0.75 },
  report: {
    attempt_id: "A-0001",
    run_id: "r1",
    created_at: "",
    summary_vi: "Học sinh yếu Vocabulary — topic words.",
    uncertain_points: 0,
    teacher_questions: [],
    weak_points: [
      { skill_tag: "VOC-TOPIC", skill_name: "Vocabulary — topic words", seen: 5, wrong: 3, gap_errors: 2, note_vi: "" },
      {
        skill_tag: "GR-PSV-A1",
        skill_name: "Present Simple — Affirmative Forms",
        seen: 4,
        wrong: 1,
        gap_errors: 1,
        note_vi: "",
      },
    ],
    careless_notes: [],
  },
  verdicts: [verdict("q-2", 17), verdict("q-3", 27), verdict("q-1", 28)],
  // written (and sent by an older sidecar) in id order: 28, 17, 27
  explanations: [explanation("q-1", "a"), explanation("q-2", "b"), explanation("q-3", "a"), explanation("q-2", "a")],
};

describe("step 22.4.6 report wording and order", () => {
  it("R22.4.6.2: weak points show the skill name; no taxonomy code is rendered", async () => {
    const { api } = fakeApi({ "GET /attempts/{id}/report": report });
    render(<ReportPanel api={api} attemptId="A-0001" print={() => {}} />);
    await waitFor(() => expect(screen.getAllByTestId("weak-point")).toHaveLength(2));
    const items = screen.getAllByTestId("weak-point").map((li) => li.textContent);
    expect(items).toEqual([
      "Vocabulary — topic words: 3/5 wrong",
      "Present Simple — Affirmative Forms: 1/4 wrong",
    ]);
    expect(screen.getByTestId("report-panel").textContent).not.toMatch(CODE);
  });

  it("R22.4.6.3: explanations follow the printed number, then the wrong answer", async () => {
    const { api } = fakeApi({ "GET /attempts/{id}/report": report });
    render(<ReportPanel api={api} attemptId="A-0001" print={() => {}} />);
    await waitFor(() => expect(screen.getAllByTestId("explanation")).toHaveLength(4));
    const shown = screen.getAllByTestId("explanation").map((li) => li.textContent);
    expect(shown).toEqual([
      "17. Giải thích q-2 a: từ vựng chủ đề.",
      "17. Giải thích q-2 b: từ vựng chủ đề.",
      "27. Giải thích q-3 a: từ vựng chủ đề.",
      "28. Giải thích q-1 a: từ vựng chủ đề.",
    ]);
  });

  it("the grade card in the conversation shows names too", async () => {
    const { api } = fakeApi({ "GET /attempts/{id}/report": report, "GET /attempts/{id}": { answers: [] } });
    render(<GradeCard api={api} latest body={{ attempt_id: "A-0001", test_id: "T-0001" }} />);
    await waitFor(() => expect(screen.getAllByTestId("weak-point")).toHaveLength(2));
    expect(screen.getAllByTestId("weak-point")[0]).toHaveTextContent("Vocabulary — topic words: 3/5 wrong");
    expect(document.body.textContent).not.toMatch(CODE);
  });
});
