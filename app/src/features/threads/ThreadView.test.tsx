// R15.1: the photo check card has exactly its controls, and Run sends the UI state.
// R15.6: dropping into a thread that has already run shows no card, only "Start a new thread".
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { resetDraftMemory, saveDraft } from "@/features/photo-check/draft";
import { fakeApi, FakeStatus, type FakeCall } from "@/lib/testApi";
import { todayIso } from "@/lib/skills";
import { ThreadView } from "./ThreadView";

const page = (id: string, text = false) => ({
  file_id: id,
  rotation: 0 as const,
  is_key: false,
  text_file_id: text ? id : null,
});
const thread = (kind: "pending" | "filled") => ({
  id: "th1",
  title: "New thread",
  kind,
  test_id: null,
  created_at: "2026-10-03T00:00:00Z",
});

function drop(files: File[]) {
  const target = screen.getByTestId("conversation");
  fireEvent.drop(target, { dataTransfer: { files, types: ["Files"] } });
}

afterEach(() => {
  resetDraftMemory();
  window.sessionStorage.clear();
});

describe("photo check card (R15.1)", () => {
  it("drop → POST /files per file → one thumbnail per page; Run sends the UI state", async () => {
    const uploads: Record<string, unknown> = {
      "a.jpg": { file_id: "fa", pages: [page("fa")] },
      "b.pdf": { file_id: "fb", pages: [page("fb1"), page("fb2")] },
      "c.docx": { file_id: "fc", pages: [page("fct", true), page("fci")] },
    };
    const run = { id: "R1", thread_id: "th1", kind: "extract", status: "queued" };
    const { api, calls } = fakeApi({
      "GET /threads/{id}": { thread: thread("pending"), attempt: null, test: null },
      "GET /threads/{id}/messages": [],
      "POST /files": (c: FakeCall) => uploads[c.query.get("name") ?? ""],
      "GET /tests": [
        {
          id: "T-0042",
          display_name: "Grade 8 final test 1",
          attempt_count: 0,
          meta: {},
          points_possible: 10,
          updated_at: "",
        },
      ],
      "POST /threads/{id}/runs": run,
    });
    const onRunStarted = vi.fn();
    render(
      <ThreadView
        api={api}
        threadId="th1"
        onThreadCreated={() => {}}
        onNewThread={() => {}}
        onRunStarted={onRunStarted}
      />,
    );
    await waitFor(() => expect(calls.some((c) => c.path === "/threads/th1/messages")).toBe(true));
    drop([new File(["x"], "a.jpg"), new File(["x"], "b.pdf"), new File(["x"], "c.docx")]);
    const card = await screen.findByTestId("photo-check-card");
    const thumbs = () => within(card).getAllByTestId("photo-thumb");
    expect(thumbs().map((t) => t.dataset.fileId)).toEqual(["fa", "fb1", "fb2", "fct", "fci"]);
    expect(within(card).getAllByTestId("text-page")).toHaveLength(1);
    expect(within(thumbs()[0]!).getByRole("img").getAttribute("src")).toBe(
      "http://127.0.0.1:9/files/fa?token=t&thumb=1",
    );

    // Exactly these controls: per page 🔑 ⟳ ✕, then +, the Existing test search, Same series as (22.3.3), Date taken (22.5.5), Run.
    const controls = Array.from(card.querySelectorAll("button, input, select, textarea")).map(
      (el) => el.getAttribute("aria-label") ?? el.getAttribute("data-testid") ?? el.textContent,
    );
    const perPage = [1, 2, 3, 4, 5].flatMap((n) => [
      `Show page ${n} full size`,
      `Key page ${n}`,
      `Rotate page ${n} 90°`,
      `Delete page ${n}`,
    ]);
    expect(controls).toEqual([
      ...perPage,
      "Add pages",
      "photo-add-input",
      "existing-test-search",
      "series-test-search",
      "photo-taken-on",
      "photo-run",
    ]);

    // Reorder: drag page 3 onto page 1. Rotate the new first page twice. Key page 5. Delete page 4.
    fireEvent.dragStart(thumbs()[2]!, { dataTransfer: { setData() {}, types: [] } });
    fireEvent.dragOver(thumbs()[0]!, { dataTransfer: { types: [] } });
    fireEvent.drop(thumbs()[0]!, { dataTransfer: { types: [], files: [] } });
    expect(thumbs().map((t) => t.dataset.fileId)).toEqual(["fb2", "fa", "fb1", "fct", "fci"]);
    fireEvent.click(within(thumbs()[0]!).getByRole("button", { name: "Rotate page 1 90°" }));
    fireEvent.click(within(thumbs()[0]!).getByRole("button", { name: "Rotate page 1 90°" }));
    expect(thumbs()[0]!.dataset.rotation).toBe("180");
    expect(within(thumbs()[0]!).getByRole("img")).toHaveStyle({ transform: "rotate(180deg)" });
    fireEvent.click(within(card).getByRole("button", { name: "Key page 5" }));
    fireEvent.click(within(card).getByRole("button", { name: "Delete page 4" }));
    expect(thumbs().map((t) => t.dataset.fileId)).toEqual(["fb2", "fa", "fb1", "fci"]);

    // Existing test search → pick T-0042.
    fireEvent.change(within(card).getByTestId("existing-test-search"), {
      target: { value: "grade 8" },
    });
    fireEvent.click(await within(card).findByRole("option", { name: /Grade 8 final test 1/ }));
    expect(within(card).getByTestId("existing-test-picked")).toHaveTextContent("Grade 8 final test 1");
    expect(calls.find((c) => c.path === "/tests")?.query.get("q")).toBe("grade 8");

    fireEvent.click(within(card).getByTestId("photo-run"));
    await waitFor(() => expect(onRunStarted).toHaveBeenCalledWith(run));
    const post = calls.find((c) => c.method === "POST" && c.path === "/threads/th1/runs");
    expect(post?.body).toEqual({
      kind: "extract",
      input: {
        pages: [
          { ...page("fb2"), rotation: 180 },
          page("fa"),
          page("fb1"),
          { ...page("fci"), is_key: true },
        ],
        existing_test_id: "T-0042",
        supersedes_attempt_id: null,
        taken_on: todayIso(),
      },
    });
    expect(screen.queryByTestId("photo-check-card")).toBeNull();
    expect(window.sessionStorage.getItem("etach.photoCheck.th1")).toBeNull();
  });

  it("restores the draft after a reload; a swept thumbnail shows a placeholder that can be deleted", () => {
    saveDraft("th1", { pages: [page("gone"), page("ok")], existingTest: null });
    resetDraftMemory(); // as after a page reload: only sessionStorage is left
    const { api } = fakeApi({
      "GET /threads/{id}": { thread: thread("pending"), attempt: null, test: null },
      "GET /threads/{id}/messages": [],
    });
    render(<ThreadView api={api} threadId="th1" onThreadCreated={() => {}} onNewThread={() => {}} />);
    const card = screen.getByTestId("photo-check-card");
    fireEvent.error(within(card).getAllByRole("img")[0]!);
    expect(within(card).getByTestId("broken-page")).toBeInTheDocument();
    fireEvent.click(within(card).getByRole("button", { name: "Delete page 1" }));
    expect(within(card).getAllByTestId("photo-thumb").map((t) => t.dataset.fileId)).toEqual(["ok"]);
  });

  it("a new thread: the first drop uploads, creates the thread and opens it", async () => {
    const { api, calls } = fakeApi({
      "POST /files": { file_id: "fa", pages: [page("fa")] },
      "POST /threads": { thread_id: "th9" },
    });
    const onThreadCreated = vi.fn();
    render(
      <ThreadView api={api} threadId={null} onThreadCreated={onThreadCreated} onNewThread={() => {}} />,
    );
    // The start screen (PRD §10.1 v8.25): no heading; a dotted, portrait paper-shaped box (A4,
    // 2 px corners, the quiet input-border colour) with the instruction and Choose files centred.
    const start = screen.getByTestId("empty-state");
    expect(screen.queryByRole("heading")).toBeNull();
    for (const c of ["border-2", "border-dotted", "border-input", "rounded-paper", "aspect-[1/1.414]", "text-center", "items-center"]) {
      expect(start.className.split(/\s+/)).toContain(c);
    }
    expect(start).toHaveTextContent("Drop or paste photos, a PDF or a Word file of a test to start a new thread.");
    expect(within(start).getByRole("button", { name: "Choose files…" })).toBeInTheDocument();
    // while files are dragged over it: a blue border and the light tint, no separate overlay
    const area = screen.getByTestId("conversation");
    const files = { types: ["Files"], files: [] };
    fireEvent.dragEnter(area, { dataTransfer: files });
    expect(start).toHaveAttribute("data-dragging", "true");
    expect(start.className.split(/\s+/)).toEqual(expect.arrayContaining(["border-accent-strong", "bg-tint"]));
    expect(screen.queryByTestId("drop-overlay")).toBeNull();
    fireEvent.dragLeave(area, { dataTransfer: files });
    expect(start.className.split(/\s+/)).toContain("border-input");
    drop([new File(["x"], "a.jpg")]);
    await waitFor(() => expect(onThreadCreated).toHaveBeenCalledWith("th9"));
    expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual(["POST /files", "POST /threads"]);
    const stored = JSON.parse(window.sessionStorage.getItem("etach.photoCheck.th9") ?? "{}") as {
      pages?: unknown;
    };
    expect(stored.pages).toEqual([page("fa")]);
  });
});

describe("one test per thread (R15.6)", () => {
  it("dropping into a thread that has already run: no card, a Start a new thread button", async () => {
    const { api, calls } = fakeApi({
      "GET /threads/{id}": { thread: thread("filled"), attempt: { id: "A-0001" }, test: null },
      "GET /threads/{id}/messages": [
        { id: "m1", thread_id: "th1", role: "app", kind: "run_card", body: {}, created_at: "" },
      ],
    });
    const onNewThread = vi.fn();
    render(<ThreadView api={api} threadId="th1" onThreadCreated={() => {}} onNewThread={onNewThread} />);
    await screen.findByTestId("message");
    const files = [new File(["x"], "a.jpg")];
    await act(async () => drop(files));
    expect(screen.queryByTestId("photo-check-card")).toBeNull();
    expect(calls.some((c) => c.path === "/files")).toBe(false);
    const blocked = screen.getByTestId("thread-blocked");
    fireEvent.click(within(blocked).getByRole("button", { name: "Start a new thread" }));
    expect(onNewThread).toHaveBeenCalledWith(files);
  });

  it("a 409 from Run (ran elsewhere) also blocks the thread", async () => {
    saveDraft("th1", { pages: [page("fa")], existingTest: null });
    const { api } = fakeApi({
      "GET /threads/{id}": { thread: thread("pending"), attempt: null, test: null },
      "GET /threads/{id}/messages": [],
      "POST /threads/{id}/runs": new FakeStatus(409, { detail: "thread already ran; start a new thread" }),
    });
    render(<ThreadView api={api} threadId="th1" onThreadCreated={() => {}} onNewThread={() => {}} />);
    fireEvent.click(screen.getByTestId("photo-run"));
    await waitFor(() => expect(screen.queryByTestId("photo-check-card")).toBeNull());
    await act(async () => drop([new File(["x"], "b.jpg")]));
    expect(screen.getByRole("button", { name: "Start a new thread" })).toBeInTheDocument();
  });
});

// Step 22.1.1: the thread's heading is its shown title (R22.1.1.6); the extraction card gets the
// test's display name and the current attempt's student from GET /threads/{id} (R22.1.1.7); a
// student change on the card also reloads the thread list.
describe("titles from GET /threads/{id} (step 22.1.1)", () => {
  const TEST = "Grade 8 · FinalTerm HK1 · Test 1";
  const student = { id: "S-0001", full_name: "Nguyễn Văn An", name_search: "nguyen van an", class_name: null, school: null, grade: null, created_at: "" };
  const detail = {
    thread: thread("filled"),
    shown_title: `${TEST} · Nguyễn Văn An`,
    attempt: { id: "A-0001", test_id: "T-0001", student_id: "S-0001", student_name_read: "An" },
    test: { id: "T-0001" },
    test_display_name: TEST,
    student,
  };
  const card = {
    id: "m1",
    thread_id: "th1",
    role: "app",
    kind: "run_card",
    body: { run_id: "R1", test_id: "T-0001", attempt_id: "A-0001", unsure_count: 0 },
    created_at: "",
  };

  it("the heading is the shown title; the card names the student and the test", async () => {
    const { api } = fakeApi({ "GET /threads/{id}": detail, "GET /threads/{id}/messages": [card] });
    render(<ThreadView api={api} threadId="th1" onThreadCreated={() => {}} onNewThread={() => {}} />);
    expect(await screen.findByTestId("thread-title")).toHaveTextContent(`${TEST} · Nguyễn Văn An`);
    expect(await screen.findByTestId("extraction-heading")).toHaveTextContent(`Extracted: ${TEST} · Nguyễn Văn An`);
  });

  it("a student rename on the card reloads the thread and the thread list", async () => {
    const { api, calls } = fakeApi({
      "GET /threads/{id}": detail,
      "GET /threads/{id}/messages": [card],
      "GET /students": [student],
      "PATCH /students/{id}": { ...student, full_name: "Nguyễn Văn Ân" },
    });
    const onThreadChanged = vi.fn();
    render(
      <ThreadView api={api} threadId="th1" onThreadCreated={() => {}} onNewThread={() => {}} onThreadChanged={onThreadChanged} />,
    );
    fireEvent.click(await screen.findByTestId("student-chip"));
    fireEvent.change(screen.getByTestId("student-name-input"), { target: { value: "Nguyễn Văn Ân" } });
    fireEvent.click(screen.getByTestId("student-name-save"));
    await waitFor(() => expect(onThreadChanged).toHaveBeenCalled());
    await waitFor(() => expect(calls.filter((c) => c.path === "/threads/th1").length).toBe(2));
  });
});

describe("a card whose test was merged since (step 22.1.1)", () => {
  it("the heading names the current test when the card's attempt is the current one", async () => {
    const detail = {
      thread: thread("filled"),
      shown_title: "Grade 8 · FinalTerm HK1 · Test 1",
      attempt: { id: "A-0001", test_id: "T-0001", student_id: null, student_name_read: null },
      test: { id: "T-0001" },
      test_display_name: "Grade 8 · FinalTerm HK1 · Test 1",
      student: null,
    };
    const card = {
      id: "m1",
      thread_id: "th1",
      role: "app",
      kind: "run_card",
      body: { run_id: "R1", test_id: "T-0002", attempt_id: "A-0001", unsure_count: 0 },
      created_at: "",
    };
    const { api } = fakeApi({ "GET /threads/{id}": detail, "GET /threads/{id}/messages": [card] });
    render(<ThreadView api={api} threadId="th1" onThreadCreated={() => {}} onNewThread={() => {}} />);
    expect(await screen.findByTestId("extraction-heading")).toHaveTextContent(
      "Extracted: Grade 8 · FinalTerm HK1 · Test 1",
    );
  });
});
