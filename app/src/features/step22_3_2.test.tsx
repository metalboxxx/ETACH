// Step 22.3.2, straight to work (PRD §10 v6.3, decision D2; comments 14 and 18).
// R22.3.2.1: an extracted thread opens its Test workspace (workspace.test.tsx covers the tabs too);
//   a thread whose extract is still running shows the start screen with progress.
// R22.3.2.2: "Grade student answers" starts the grade run; disabled with a visible reason without
//   student answers or a key (the same words after grading, R22.4.1.3); on the tab row, keyboard-reachable.
// R22.3.2.3: during a run the workspace shows a progressbar with the stage and Stop.
// R22.3.2.5: every action the extraction and grade cards had is reachable from the workspace.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AppShell } from "@/components/AppShell";
import { ThreadRunCard } from "@/features/running/ThreadRunCard";
import { EMPTY_PROGRESS, type RunEntry } from "@/features/running/useRunning";
import { resetDraftMemory } from "@/features/photo-check/draft";
import { writeSession } from "@/lib/storage";
import { fakeApi, type FakeRoute } from "@/lib/testApi";

const test = {
  id: "T-0001",
  meta: { occasion: "FinalTerm", grade: 8, term: 1, edited_fields: [] },
  content: { sections: [] },
  picture_paths: {},
  pages: [{ page_no: 1, file_id: "tp1" }],
  key_pages: [],
  merged_into: null,
  source_run_id: "R1",
  review: [] as unknown[],
};
const attempt = {
  id: "A-0001",
  test_id: "T-0001",
  thread_id: "th1",
  student_id: null,
  student_name_read: "Học Sinh A",
  class_read: "8A",
  source_run_id: "R1",
  superseded_by: null,
  status: "extracted",
  version: 1,
  score_earned: null,
  score_possible: null,
  created_at: "",
};
const thread = { id: "th1", title: "New thread", kind: "filled" as const, test_id: "T-0001", created_at: "" };
const detail = (over: Record<string, unknown> = {}) => ({
  thread,
  attempt,
  test: { id: "T-0001" },
  student: null,
  test_display_name: "Grade 8 test",
  shown_title: "Grade 8 test",
  ...over,
});
const summary = {
  thread,
  shown_title: "Grade 8 test",
  kind: "filled" as const,
  group: "Chưa rõ",
  student_id: null,
  last_activity: "",
  open_review_count: 0,
};
const reviewItem = (id: string, kind: string, proposal: Record<string, unknown> = {}) => ({
  id,
  kind,
  owner: "extract",
  status: "open",
  attempt_id: "A-0001",
  question_id: null,
  test_id: "T-0001",
  proposal,
  dedupe_key: id,
  followup_run_id: null,
  resolution: null,
  created_at: "",
});

function routes(extra: Record<string, FakeRoute> = {}) {
  return fakeApi({
    "GET /threads/{id}": detail(),
    "GET /threads/{id}/messages": [],
    "GET /tests/{id}": test,
    "GET /tests/{id}/keys": [{ question_id: "q-1" }],
    "GET /tests": [],
    "GET /attempts/{id}": { attempt, answers: [], pages: [] },
    "GET /students": [],
    "GET /review/count": { open: 0 },
    "POST /threads/{id}/runs": { id: "R2", thread_id: "th1", kind: "grade", status: "queued" },
    ...extra,
  });
}

afterEach(() => {
  resetDraftMemory();
  window.sessionStorage.clear();
});

function renderShell(fake = routes(), threadRunning?: (id: string) => React.ReactNode, active: string[] = []) {
  writeSession("etach.activeThread", "th1");
  return render(
    <AppShell
      connection="open"
      api={fake.api}
      threads={[summary]}
      threadRunning={threadRunning}
      activeRunThreadIds={new Set(active)}
    />,
  );
}

const entry = (status = "running"): RunEntry =>
  ({
    run: { id: "R2", thread_id: "th1", kind: "grade", status },
    progress: { ...EMPTY_PROGRESS, stage: "grading", done: 1, total: 4 },
  }) as unknown as RunEntry;

describe("Grade student answers (R22.3.2.2)", () => {
  it("sits on the tab row, is a keyboard-reachable button and starts the grade run", async () => {
    const fake = routes();
    renderShell(fake);
    const ws = await screen.findByTestId("workspace");
    const bar = within(ws).getByTestId("workspace-bar");
    const grade = await within(bar).findByRole("button", { name: "Grade student answers" });
    await waitFor(() => expect(grade).toBeEnabled());
    expect(grade.tabIndex).toBe(0);
    fireEvent.click(grade);
    await waitFor(() =>
      expect(fake.calls.find((c) => c.method === "POST" && c.path === "/threads/th1/runs")?.body).toEqual({
        kind: "grade",
        input: { test_id: "T-0001", attempt_id: "A-0001", reason: "button" },
      }),
    );
  });

  it("still says Grade student answers once graded, and grades the same way (R22.4.1.3)", async () => {
    const fake = routes({ "GET /threads/{id}": detail({ attempt: { ...attempt, status: "graded" } }) });
    renderShell(fake);
    const grade = await screen.findByRole("button", { name: "Grade student answers" });
    expect(screen.queryByRole("button", { name: "Grade again" })).toBeNull();
    await waitFor(() => expect(grade).toBeEnabled());
    fireEvent.click(grade);
    await waitFor(() =>
      expect(fake.calls.find((c) => c.method === "POST" && c.path === "/threads/th1/runs")?.body).toEqual({
        kind: "grade",
        input: { test_id: "T-0001", attempt_id: "A-0001", reason: "button" },
      }),
    );
  });

  it("is not blocked by a missing key: the grade run writes AI keys (v2.25.1)", async () => {
    const fake = routes({ "GET /tests/{id}/keys": [] });
    renderShell(fake);
    const grade = await screen.findByRole("button", { name: "Grade student answers" });
    expect(grade).toBeEnabled();
    fireEvent.click(grade);
    await waitFor(() => expect(fake.calls.some((c) => c.method === "POST" && c.path === "/threads/th1/runs")).toBe(true));
  });

  it("a test-only thread has Make the key: it grades the blank test; no student chip (R22.3.2.4)", async () => {
    const fake = routes({ "GET /threads/{id}": detail({ attempt: null }) });
    renderShell(fake);
    const ws = await screen.findByTestId("workspace");
    const make = await within(ws).findByRole("button", { name: "Make the key" });
    expect(within(ws).queryByTestId("student-chip")).toBeNull();
    fireEvent.click(make);
    await waitFor(() =>
      expect(fake.calls.find((c) => c.method === "POST" && c.path === "/threads/th1/runs")?.body).toEqual({
        kind: "grade",
        input: { test_id: "T-0001", attempt_id: null, reason: "button" },
      }),
    );
  });
});

describe("Extract again (R22.3.2.2)", () => {
  it("is on the tab row, asks first, and Keep this one sends nothing", async () => {
    const fake = routes();
    renderShell(fake);
    const bar = within(await screen.findByTestId("workspace")).getByTestId("workspace-bar");
    fireEvent.click(within(bar).getByRole("button", { name: "Extract again" }));
    const dialog = await screen.findByTestId("confirm-dialog");
    expect(dialog).toHaveTextContent("student answers are read again");
    fireEvent.click(within(dialog).getByRole("button", { name: "Keep this one" }));
    await waitFor(() => expect(screen.queryByTestId("confirm-dialog")).toBeNull());
    expect(fake.calls.some((c) => c.path.endsWith("/extract-again"))).toBe(false);
  });

  it("confirmed, it calls POST /threads/{id}/extract-again", async () => {
    const fake = routes({
      "POST /threads/{id}/extract-again": { id: "R3", thread_id: "th1", kind: "extract", status: "queued" },
    });
    renderShell(fake);
    fireEvent.click(await screen.findByTestId("extract-again"));
    fireEvent.click(within(await screen.findByTestId("confirm-dialog")).getByRole("button", { name: "Extract again" }));
    await waitFor(() =>
      expect(fake.calls.some((c) => c.method === "POST" && c.path === "/threads/th1/extract-again")).toBe(true),
    );
  });
});

describe("student chip (R22.3.2.4)", () => {
  it("a paper without a name shows the chip; choosing a student saves it on the attempt", async () => {
    const fake = routes({
      "GET /students": [{ id: "S-1", full_name: "Phạm Thu Hà", name_search: "pham thu ha", class_name: null }],
      "PUT /attempts/{id}/student": { ...attempt, student_id: "S-1" },
    });
    renderShell(fake);
    const chip = await within(await screen.findByTestId("thread-banner")).findByTestId("student-chip");
    expect(chip).toHaveTextContent("Unknown student");
    fireEvent.click(chip);
    fireEvent.click(await screen.findByTestId("student-option"));
    await waitFor(() =>
      expect(fake.calls.find((c) => c.method === "PUT" && c.path === "/attempts/A-0001/student")?.body).toEqual({
        student_id: "S-1",
        create_from_read: false,
      }),
    );
  });
});

describe("run progress in the workspace (R22.3.2.3)", () => {
  it("shows a progressbar with the stage and Stop while the run goes", async () => {
    let stopped = 0;
    renderShell(routes(), () => <ThreadRunCard entry={entry()} onStop={() => (stopped += 1)} />, ["th1"]);
    const banner = await screen.findByTestId("thread-banner");
    expect(within(banner).getByRole("progressbar")).toBeInTheDocument();
    fireEvent.click(within(banner).getByRole("button", { name: "Stop" }));
    expect(stopped).toBe(1);
    expect(screen.getByTestId("grade-answers")).toBeDisabled();
  });

  it("the top bar is one compact line on each of the four workspace tabs (R22.4.8.5)", async () => {
    renderShell(
      routes({
        "GET /threads/{id}": detail({ attempt: { ...attempt, status: "graded" }, regrade_pending: true }),
        "POST /tests/{id}/regrade": { run_ids: [] },
        "GET /tests/{id}/keys": [],
      }),
      () => <ThreadRunCard entry={entry()} onStop={() => {}} />,
    );
    const ws = await screen.findByTestId("workspace");
    // Test, Student answers and Report first, then Key: leaving Key re-grades, which clears the bar.
    for (const name of ["Test", "Student answers", "Report", "Key"]) {
      fireEvent.click(await within(ws).findByRole("tab", { name }));
      const bar = await screen.findByTestId("thread-top-bar");
      expect(bar).toHaveAttribute("data-compact", "true");
      expect(within(bar).queryByTestId("keys-changed"), name).not.toBeNull();
      expect(within(bar).getByTestId("thread-run")).toHaveAttribute("data-compact", "true");
      expect(within(bar).queryByTestId("run-elapsed")).toBeNull();
    }
  });

  it("a thread whose extract is still running shows the start screen with the progress (R22.3.2.1)", async () => {
    renderShell(
      routes({ "GET /threads/{id}": detail({ attempt: null, test: null, thread: { ...thread, kind: "pending" } }) }),
      () => <ThreadRunCard entry={entry()} />,
      ["th1"],
    );
    expect(await screen.findByTestId("thread-run")).toBeInTheDocument();
    expect(screen.queryByTestId("workspace")).toBeNull();
    expect(screen.getByTestId("conversation")).toBeVisible();
  });
});

describe("nothing lost with the cards (R22.3.2.5)", () => {
  // Each action the extraction and grade cards offered, and where it is now.
  const CARD_ACTIONS = [
    ["Grade", "grade-answers"],
    ["Extract again (picked test mismatch, now for any thread)", "extract-again"],
    ["Test", "tab:Test"],
    ["Key", "tab:Key"],
    ["Student answers", "tab:Student answers"],
    ["Report (grade card)", "tab:Report"],
    ["Photo thumbnails", "photo-viewer"],
    ["Student chip", "student-chip"],
    ["Merge preview (possible duplicate)", "note:possible_duplicate"],
    ["Picked test mismatch", "note:picked_test_mismatch"],
    ["Answers left after a merge", "note:merge_unaligned"],
    ["Stop", "thread-run-stop"],
  ] as const;

  it.each(CARD_ACTIONS)("%s is reachable from the workspace", async (_name, where) => {
    const review = [
      reviewItem("RV1", "possible_duplicate", { best_test_id: "T-0009" }),
      reviewItem("RV2", "picked_test_mismatch"),
      reviewItem("RV3", "merge_unaligned", { value: "B", printed_number: 3, candidate_question_ids: ["q-3"] }),
    ];
    renderShell(
      routes({
        "GET /threads/{id}": detail({ attempt: { ...attempt, status: "graded" } }),
        "GET /tests/{id}": { ...test, review },
      }),
      () => <ThreadRunCard entry={entry()} onStop={() => {}} />,
    );
    const ws = await screen.findByTestId("workspace");
    if (where.startsWith("tab:")) {
      expect(await within(ws).findByRole("tab", { name: where.slice(4) })).toBeInTheDocument();
    } else if (where.startsWith("note:")) {
      const notes = await within(ws).findAllByTestId("card-note");
      expect(notes.map((n) => n.dataset.kind)).toContain(where.slice(5));
    } else {
      expect(await within(ws).findByTestId(where)).toBeInTheDocument();
    }
  });

  it("the merge note opens its preview from the workspace", async () => {
    renderShell(
      routes({
        "GET /tests/{id}": { ...test, review: [reviewItem("RV1", "possible_duplicate", { best_test_id: "T-0009" })] },
      }),
    );
    fireEvent.click(await screen.findByTestId("card-merge"));
    expect(screen.queryByTestId("card-merge")).toBeNull();
  });
});
