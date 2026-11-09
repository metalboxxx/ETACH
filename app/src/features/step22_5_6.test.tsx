// Step 22.5.6b (APP_TEST). R22.5.6.7: the Key tab labels a key read from the key photo "From the key
// photo" (no "double-checked"); "AI key · double-checked" is only for a key a second call agreed
// with; the "AI unsure key" label is unchanged. The Student answers tab shows one quiet line when
// the listening part was left out ("Listening (questions 1–10) left out"), and nothing otherwise.
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KeysPanel, KEY_STATUS_LABEL, UNSURE_KEY } from "@/features/panels/KeysPanel";
import { AnswersPanel, listeningLine } from "@/features/panels/AnswersPanel";
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
        points: 1,
        points_source: "printed",
        skill: "grammar",
        graded: true,
        groups: [{ id: "g1", stimulus: null, pictures: [], questions: [1, 2, 3, 4].map(question) }],
      },
    ],
  },
  review: [],
};

const key = (n: number, status: string) => ({ question_id: `q-${n}`, accepted: ["A"], status, checker: null, confidence: 0.8 });

describe("R22.5.6.7 Key tab: where each key comes from", () => {
  it("R22.5.6.7 a key-photo key says 'From the key photo' and never 'double-checked'", async () => {
    const { api } = fakeApi({
      "GET /tests/{id}/keys": [key(1, "from_key_photo"), key(2, "ai_verified"), key(3, "ai_uncertain"), key(4, "ai_unverified")],
      "GET /tests/{id}": test_,
    });
    render(<KeysPanel api={api} testId="T-0001" />);
    const rows = await screen.findAllByTestId("key-row");
    const labels = rows.map((r) => within(r).getByTestId("key-status").textContent);
    expect(labels).toEqual(["From the key photo", "AI key · double-checked", UNSURE_KEY, "AI key · not double-checked"]);
    expect(rows[0]).toHaveAttribute("data-status", "from_key_photo");
    expect(rows[0]).not.toHaveTextContent(/double-checked/);
    // A key-photo key can still be verified by the teacher.
    expect(within(rows[0]!).getByTestId("key-verify")).toBeInTheDocument();
  });

  it("R22.5.6.7 only ai_verified carries the 'double-checked' label", () => {
    const doubled = Object.entries(KEY_STATUS_LABEL).filter(([, label]) => label === "AI key · double-checked");
    expect(doubled.map(([status]) => status)).toEqual(["ai_verified"]);
    expect(KEY_STATUS_LABEL.from_key_photo).toBe("From the key photo");
    expect(KEY_STATUS_LABEL.ai_uncertain).toBe("AI unsure key");
  });
});

describe("R22.5.6.7 Student answers tab: the listening line", () => {
  function renderAnswers(listening: { first: number; last: number } | null | undefined) {
    const attempt = { id: "A-1", taken_on: "2026-10-01", version: 1 };
    const detail: Record<string, unknown> = { attempt, answers: [], pages: [] };
    if (listening !== undefined) detail.listening_skipped = listening;
    const { api } = fakeApi({ "GET /attempts/{id}": detail, "GET /tests/{id}": test_ });
    render(<AnswersPanel api={api} attemptId="A-1" testId="T-0001" />);
  }

  it("R22.5.6.7 a range reads 'Listening (questions 1–10) left out' with an en dash", async () => {
    renderAnswers({ first: 1, last: 10 });
    expect(await screen.findByTestId("answers-listening")).toHaveTextContent("Listening (questions 1–10) left out");
  });

  it("R22.5.6.7 a single question reads 'Listening (question 5) left out'", async () => {
    renderAnswers({ first: 5, last: 5 });
    expect(await screen.findByTestId("answers-listening")).toHaveTextContent("Listening (question 5) left out");
    expect(listeningLine({ first: 5, last: 5 })).toBe("Listening (question 5) left out");
  });

  it("R22.5.6.7 no line when nothing was left out (null or missing)", async () => {
    renderAnswers(null);
    await screen.findByTestId("answers-panel");
    expect(screen.queryByTestId("answers-listening")).toBeNull();
  });

  it("R22.5.6.7 no line on an attempt read without the field", async () => {
    renderAnswers(undefined);
    await screen.findByTestId("answers-panel");
    expect(screen.queryByTestId("answers-listening")).toBeNull();
  });
});
