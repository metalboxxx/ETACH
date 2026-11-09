// Step 22.5.5b (APP_TEST). R22.5.5.6: hovering or focusing "AI unsure key" shows the checker's
// answer and reasoning, or that the check did not finish; keyboard reachable; screen-reader text.
// R22.5.5.7: the photo check card's date taken (default today) is sent; the Student answers tab
// shows it and saves a change (PATCH). R22.5.5.8: the Students tab and the report show labels and
// levels basics first, with "Later, after the basics (N)" opening the held-back skills. (The
// Models tab part of R22.5.5.8 is in settings/settings.test.tsx.) R22.5.5.11: clicking (or Enter
// on) a student opens "Skills — {student}" in the main panel; the skills table lives there now.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { KeysPanel, CHECK_NOT_FINISHED, UNSURE_KEY } from "@/features/panels/KeysPanel";
import { AnswersPanel } from "@/features/panels/AnswersPanel";
import { ReportSummary, type AttemptReport } from "@/features/panels/ReportPanel";
import { StudentSkillsView } from "@/features/students-tab/StudentSkillsView";
import { AppShell } from "@/components/AppShell";
import userEvent from "@testing-library/user-event";
import { PhotoCheckCard } from "@/features/photo-check/PhotoCheckCard";
import { EMPTY_DRAFT, toExtractInput, type PhotoCheckDraft } from "@/features/photo-check/draft";
import { fakeApi } from "@/lib/testApi";
import { todayIso } from "@/lib/skills";

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
        points: 0.75,
        points_source: "printed",
        skill: "grammar",
        graded: true,
        groups: [{ id: "g1", stimulus: null, pictures: [], questions: [question(1), question(2), question(3)] }],
      },
    ],
  },
  review: [],
};

const key = (n: number, status: string, checker: unknown = null) => ({
  question_id: `q-${n}`,
  accepted: ["A"],
  status,
  checker,
});

describe("R22.5.5.6 Key tab: the checker's answer on hover or focus", () => {
  function renderKeys() {
    const { api } = fakeApi({
      "GET /tests/{id}/keys": [
        key(1, "ai_uncertain", { status: "disagreed", answer: "B", reasoning: "The subject is plural, so the verb has no -s." }),
        key(2, "ai_uncertain", { status: "did_not_finish", answer: null, reasoning: null }),
        key(3, "ai_verified"),
      ],
      "GET /tests/{id}": test_,
    });
    render(<KeysPanel api={api} testId="T-0001" />);
  }

  it("R22.5.5.6 shows the checker's answer and reasoning on hover, keyboard focus and as the description", async () => {
    renderKeys();
    const rows = await screen.findAllByTestId("key-row");
    expect(rows).toHaveLength(3);
    const label = within(rows[0]!).getByTestId("key-status");
    expect(label).toHaveTextContent(UNSURE_KEY);
    expect(label).toHaveAttribute("tabindex", "0");
    expect(label).toHaveAccessibleDescription(
      "The checker's answer: BThe subject is plural, so the verb has no -s.",
    );
    const tip = within(rows[0]!).getByTestId("key-checker-tip");
    expect(tip).toHaveAttribute("role", "tooltip");
    expect(tip).toHaveAttribute("data-open", "false");
    fireEvent.mouseEnter(label.parentElement!);
    expect(tip).toHaveAttribute("data-open", "true");
    fireEvent.mouseLeave(label.parentElement!);
    fireEvent.focus(label);
    expect(tip).toHaveAttribute("data-open", "true");
    fireEvent.keyDown(label, { key: "Escape" });
    expect(tip).toHaveAttribute("data-open", "false");
  });

  it("R22.5.5.6 says the check did not finish; a key without a check keeps its plain label", async () => {
    renderKeys();
    const rows = await screen.findAllByTestId("key-row");
    expect(within(rows[1]!).getByTestId("key-status")).toHaveAccessibleDescription(CHECK_NOT_FINISHED);
    expect(within(rows[1]!).getByTestId("key-checker-tip")).toHaveTextContent("The check did not finish.");
    expect(within(rows[2]!).queryByTestId("key-checker-tip")).toBeNull();
    expect(within(rows[2]!).getByTestId("key-status")).not.toHaveAttribute("tabindex");
  });
});

describe("R22.5.5.7 Date taken", () => {
  function Card() {
    const [draft, setDraft] = useState<PhotoCheckDraft>(EMPTY_DRAFT);
    return (
      <>
        <PhotoCheckCard api={fakeApi({}).api} draft={draft} onChange={setDraft} onAddFiles={() => {}} onRun={() => {}} />
        <output data-testid="sent">{JSON.stringify(toExtractInput(draft))}</output>
      </>
    );
  }

  it("R22.5.5.7 the photo check card's date defaults to today and the chosen date is sent", () => {
    render(<Card />);
    const field = screen.getByLabelText("Date taken");
    expect(field).toHaveValue(todayIso());
    expect(JSON.parse(screen.getByTestId("sent").textContent!).taken_on).toBe(todayIso());
    fireEvent.change(field, { target: { value: "2026-09-15" } });
    expect(field).toHaveValue("2026-09-15");
    expect(JSON.parse(screen.getByTestId("sent").textContent!).taken_on).toBe("2026-09-15");
  });

  it("R22.5.5.7 the Student answers tab shows the date and saves a change with PATCH", async () => {
    const attempt = { id: "A-1", taken_on: "2026-10-01", version: 2 };
    const { api, calls } = fakeApi({
      "GET /attempts/{id}": { attempt, answers: [], pages: [] },
      "GET /tests/{id}": test_,
      "PATCH /attempts/{id}": (c: { body: unknown }) => ({ ...attempt, ...(c.body as object), version: 3 }),
    });
    render(<AnswersPanel api={api} attemptId="A-1" testId="T-0001" />);
    const field = await screen.findByLabelText("Date taken");
    expect(field).toHaveValue("2026-10-01");
    fireEvent.blur(field); // unchanged: nothing is sent
    expect(calls.some((c) => c.method === "PATCH")).toBe(false);
    fireEvent.change(field, { target: { value: "2026-10-05" } });
    fireEvent.blur(field);
    await waitFor(() => expect(screen.getByTestId("answers-date-status")).toHaveTextContent("Date saved"));
    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch?.path).toBe("/attempts/A-1");
    expect(patch?.body).toEqual({ taken_on: "2026-10-05" });
  });
});

const skill = (tag: string, name: string, label: string, level: string | null, held_back = false, weak = false) => ({
  skill_tag: tag,
  skill_name: name,
  label,
  level,
  weak,
  held_back,
  papers: [
    { attempt_id: "A-1", taken_on: "2026-09-01", share: 0.25, counted: 4 },
    { attempt_id: "A-2", taken_on: "2026-10-01", share: 1, counted: 2 },
  ],
});

describe("R22.5.5.8 Students tab and report: labels, levels, basics first", () => {
  it("R22.5.5.8 lists every skill with its label and level, the held-back ones behind the Later line", async () => {
    const { api } = fakeApi({
      "GET /students": [{ id: "S1", full_name: "Lan", class_name: "8A", thread_count: 1 }],
      "GET /students/{id}": {
        student: { id: "S1", full_name: "Lan", class_name: "8A" },
        threads: [],
        skills: [
          skill("VOC-TOPIC", "Topic vocabulary", "consistently_weak", "A1", false, true),
          skill("G-PRES", "Present simple", "improved", "A1"),
          skill("PRON-ED", "-ed endings", "not_enough_evidence", "A2"),
          skill("G-PERF", "Present perfect", "slipped", "B1", true, true),
          skill("READ-INFER", "Inference", "inconsistent", "B2", true, true),
        ],
      },
    });
    render(<StudentSkillsView api={api} studentId="S1" name="Lan" onOpenThread={() => {}} />);
    const box = await screen.findByTestId("student-skills");
    const table = within(box).getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Level", "Skill", "Label", "Papers"]);
    // each row: level, full skill name (a row header), label, the shares in date-taken order
    const shown = () =>
      within(box)
        .getAllByTestId("student-skill")
        .map((tr) =>
          [...tr.children].map((c) => (c.getAttribute("data-testid") === "student-skill-papers" ? c.querySelectorAll('[data-testid="student-skill-share"]').length + " papers" : c.textContent)).join(" | "),
        );
    expect(shown()).toEqual([
      "A1 | Topic vocabulary | Consistently weak | 2 papers",
      "A1 | Present simple | Improved | 2 papers",
      "A2 | -ed endings | Not enough evidence yet | 2 papers",
    ]);
    expect(within(table).getByRole("rowheader", { name: "Present simple" })).toBeInTheDocument();
    const later = within(box).getByRole("button", { name: "Later, after the basics (2)" });
    expect(later).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(later);
    expect(later).toHaveAttribute("aria-expanded", "true");
    expect(shown().slice(3)).toEqual([
      "B1 | Present perfect | Slipped | 2 papers",
      "B2 | Inference | Inconsistent | 2 papers",
    ]);
    // PRD §10.1 v8.13: "improved" on a green badge, "inconsistent" on an ochre one, both with dark
    // text; the weak labels are brick words.
    const labelOf = (text: string) => within(box).getByText(text, { selector: '[data-testid="student-skill-label"] > span' });
    expect(labelOf("Improved").className).toMatch(/\bbg-correct\b/);
    expect(labelOf("Improved").className).toMatch(/\btext-text\b/);
    expect(labelOf("Inconsistent").className).toMatch(/\bbg-unsure\b/);
    expect(labelOf("Inconsistent").className).toMatch(/\btext-text\b/);
    expect(labelOf("Slipped").className).toMatch(/\btext-danger\b/);
    expect(labelOf("Slipped").className).not.toMatch(/\bbg-/);
    // Per-paper results: "25% · 100%", each share's date on hover or focus, as its description.
    const papers = within(box).getAllByTestId("student-skill-papers")[0]!;
    expect(within(papers).getAllByTestId("student-skill-share").map((s) => s.textContent)).toEqual(["25%", "100%"]);
    const share = within(papers).getAllByTestId("student-skill-share")[0]!;
    expect(share).toHaveAttribute("tabindex", "0");
    expect(share).toHaveAccessibleDescription("Taken 1 Sep 2026: 25% right, 4 questions");
    fireEvent.focus(share);
    expect(within(papers).getAllByTestId("student-skill-date")[0]!).toHaveAttribute("data-open", "true");
  });

  it("R22.5.5.8 the report shows 'this paper only' or the label with the level; held-back ones behind the line", () => {
    const wp = (tag: string, name: string, label: string | null, level: string | null, held_back = false) => ({
      skill_tag: tag,
      skill_name: name,
      label,
      level,
      held_back,
      wrong: 2,
      seen: 3,
      gap_errors: 0,
      note_vi: "",
    });
    const report = {
      attempt: {},
      explanations: [],
      verdicts: [],
      report: {
        summary_vi: null,
        teacher_questions: [],
        careless_notes: [],
        uncertain_points: 0,
        weak_points: [
          wp("VOC-TOPIC", "Topic vocabulary", "this_paper_only", "A1"),
          wp("G-PRES", "Present simple", "consistently_weak", "A1"),
          wp("G-PERF", "Present perfect", "slipped", "B1", true),
        ],
      },
    } as unknown as AttemptReport;
    render(<ReportSummary report={report} numbers={new Map()} />);
    const items = () => screen.getAllByTestId("weak-point").map((li) => li.textContent);
    expect(items()).toEqual([
      "Topic vocabulary (A1, this paper only): 2/3 wrong",
      "Present simple (A1, consistently weak): 2/3 wrong",
    ]);
    const later = screen.getByRole("button", { name: "Later, after the basics (1)" });
    fireEvent.click(later);
    expect(items()[2]).toBe("Present perfect (B1, slipped): 2/3 wrong");
  });
});

describe("R22.5.5.11 A student opens the skills view in the main panel", () => {
  const routes = () => ({
    "GET /threads/{id}": { thread: { id: "t1" }, messages: [] },
    "GET /students": [
      { id: "S1", full_name: "Lan", class_name: "8A", thread_count: 1 },
      { id: "S2", full_name: "Bảo", class_name: null, thread_count: 0 },
    ],
    "GET /students/{id}": (c: { path: string }) =>
      c.path.endsWith("S1")
        ? {
            student: { id: "S1", full_name: "Lan", class_name: "8A" },
            threads: [{ id: "t1", shown_title: "Final 8.1 · Lan", test_id: "T-0001" }],
            skills: [skill("G-PRES", "Present simple and present continuous for routines", "consistently_weak", "A1")],
          }
        : { student: { id: "S2", full_name: "Bảo", class_name: null }, threads: [], skills: [] },
  });

  it("R22.5.5.11 clicking a student opens 'Skills — {student}' with full names; the sidebar row lists no skills", async () => {
    const { api } = fakeApi(routes());
    render(<AppShell connection="open" api={api} threads={[]} />);
    fireEvent.click(screen.getByRole("tab", { name: "Students" }));
    const rows = await screen.findAllByTestId("student-item");
    fireEvent.click(rows[0]!);
    const view = await screen.findByTestId("student-view");
    expect(within(view).getByRole("heading", { level: 2 })).toHaveTextContent("Skills — Lan");
    expect(screen.getByRole("main", { name: "Skills — Lan" })).toBe(view);
    expect(await within(view).findByRole("rowheader", { name: "Present simple and present continuous for routines" })).toBeInTheDocument();
    expect(rows[0]).toHaveAttribute("aria-current", "page");
    expect(within(screen.getByTestId("students-tab")).queryByTestId("student-skill")).toBeNull();
    expect(within(view).queryByRole("button", { name: /back/i })).toBeNull();
    // the student's threads are in the view; one opens its thread and leaves the view
    fireEvent.click(within(view).getByTestId("student-thread"));
    await waitFor(() => expect(screen.queryByTestId("student-view")).toBeNull());
  });

  it("R22.5.5.11 Enter on a student opens the view; another student replaces it; Esc or another tab leaves it", async () => {
    const user = userEvent.setup();
    const { api } = fakeApi(routes());
    render(<AppShell connection="open" api={api} threads={[]} />);
    await user.click(screen.getByRole("tab", { name: "Students" }));
    const rows = await screen.findAllByTestId("student-item");
    rows[0]!.focus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("heading", { name: "Skills — Lan" })).toBeInTheDocument();
    rows[1]!.focus();
    await user.keyboard(" ");
    expect(await screen.findByRole("heading", { name: "Skills — Bảo" })).toBeInTheDocument();
    expect(await screen.findByTestId("student-skills-empty")).toHaveTextContent("No skills yet.");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByTestId("student-view")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(screen.getAllByTestId("student-item")[1]));
    await user.keyboard("{Enter}");
    expect(await screen.findByTestId("student-view")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Chats" }));
    expect(screen.queryByTestId("student-view")).toBeNull();
  });
});
