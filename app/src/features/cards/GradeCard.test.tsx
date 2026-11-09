import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { fakeApi } from "@/lib/testApi";
import { GradeCard } from "./GradeCard";
import { KeysPanel } from "@/features/panels/KeysPanel";
import { ReportPanel } from "@/features/panels/ReportPanel";

const verdict = (n: number, v: "correct" | "incorrect" | "uncertain") => ({
  question_id: `q-${n}`,
  printed_number: n,
  value: "A",
  verdict: v,
  points_awarded: v === "correct" ? 0.25 : v === "incorrect" ? 0 : null,
  near_miss: false,
});

const report = {
  attempt: { id: "A-0001", test_id: "T-0001", score_earned: 7.5, score_possible: 9 },
  report: {
    attempt_id: "A-0001",
    run_id: "r1",
    created_at: "",
    summary_vi: "Tóm tắt.",
    uncertain_points: 0.5,
    teacher_questions: [1, 2, 3].map((i) => ({ question_vi: `Hỏi ${i}?`, what_answers_mean_vi: "" })),
    weak_points: [{ skill_tag: "GR-PSV-A1", skill_name: "Present Simple — Affirmative Forms", seen: 4, wrong: 2, gap_errors: 1, note_vi: "" }],
    careless_notes: ["Câu 3: sai chính tả."],
  },
  verdicts: [verdict(2, "uncertain"), verdict(1, "correct"), verdict(3, "incorrect")],
  explanations: [],
};

describe("grade card", () => {
  it("shows earned/possible, unsure points, teacher questions, weak points and careless notes", async () => {
    const { api } = fakeApi({ "GET /attempts/{id}/report": report, "GET /attempts/{id}": { answers: [] } });
    render(<GradeCard api={api} latest body={{ attempt_id: "A-0001", test_id: "T-0001" }} />);
    await waitFor(() => expect(screen.getByTestId("grade-score")).toHaveTextContent("7.5/9"));
    expect(screen.getByTestId("grade-unsure")).toHaveTextContent("0.5 unsure");
    expect(screen.getAllByTestId("teacher-question")).toHaveLength(3);
    expect(screen.getAllByTestId("weak-point")).toHaveLength(1);
    expect(screen.getAllByTestId("careless-note")).toHaveLength(1);
  });

  it("an earlier card is one line", () => {
    const { api } = fakeApi({});
    render(<GradeCard api={api} latest={false} body={{ attempt_id: "A", test_id: "T", score_earned: 1, score_possible: 2 }} />);
    expect(screen.getByTestId("grade-card-old")).toHaveTextContent("Graded 1/2");
  });

  it("the report lists rows by printed number and marks ? rows", async () => {
    const { api } = fakeApi({ "GET /attempts/{id}/report": report });
    render(<ReportPanel api={api} attemptId="A-0001" print={() => {}} />);
    await waitFor(() => expect(screen.getAllByTestId("report-row")).toHaveLength(3));
    const marks = screen.getAllByTestId("report-row").map((r) => r.getAttribute("data-mark"));
    expect(marks).toEqual(["✓", "?", "✗"]);
  });
});

describe("key editor", () => {
  const key = (q: string) => ({
    test_id: "T-0001",
    question_id: q,
    accepted: ["A"],
    reason_vi: null,
    source: "ai",
    status: "ai_unverified",
    confidence: 0.5,
    updated_at: "",
  });
  const test = {
    content: { sections: [{ groups: [{ questions: [{ id: "q-2", number: 2 }, { id: "q-1", number: 1 }] }] }] },
  };

  it("verify → PUT {verify: true}; the change is reported, no re-grade starts (step 22.4.5)", async () => {
    const { api, calls } = fakeApi({
      "GET /tests/{id}/keys": [key("q-2"), key("q-1")],
      "GET /tests/{id}": test,
      "PUT /tests/{id}/keys/{question_id}": () => ({
        key: { ...key("q-1"), status: "teacher_verified", source: "ai" },
        run_ids: [],
        outcome: "updated",
        explanations_deleted: 0,
      }),
    });
    let changed = 0;
    render(<KeysPanel api={api} testId="T-0001" print={() => {}} onKeysChanged={() => (changed += 1)} />);
    await waitFor(() => expect(screen.getAllByTestId("key-row")).toHaveLength(2));
    const rows = screen.getAllByTestId("key-row");
    expect(rows[0]).toHaveAttribute("data-question-id", "q-1");
    fireEvent.click(rows[0]!.querySelector('[data-testid="key-verify"]')!);
    await waitFor(() => expect(changed).toBe(1));
    expect(screen.queryByTestId("key-regrades")).toBeNull();
    const put = calls.find((c) => c.method === "PUT")!;
    expect(put.path).toBe("/tests/T-0001/keys/q-1");
    expect(put.body).toEqual({ verify: true });
  });
});
