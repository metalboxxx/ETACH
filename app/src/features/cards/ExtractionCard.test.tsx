// The extraction card (step 16 part A): the heading, the unsure count, the student chip
// (assign existing / create from the name read), [Test] / [Answers] open the panels, [Grade] (disabled without a thread; else a grade run).
// Step 22.1.1: R22.1.1.7 the heading names the test (and the student); R22.1.1.1 the student
// picker closes on a pointer-down outside it and on Escape; R22.1.1.4 create from a typed name and
// edit the assigned student's name.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApi, FakeStatus, type FakeCall } from "@/lib/testApi";
import { ExtractionCard } from "./ExtractionCard";

const body = {
  run_id: "R1",
  test_id: "T-0001",
  attempt_id: "A-0001",
  unsure_count: 3,
  no_answers: false,
  duplicate: false,
  student_name_read: "Học Sinh A",
};
const attempt = (student_id: string | null) => ({
  id: "A-0001",
  test_id: "T-0001",
  thread_id: "th1",
  student_id,
  student_name_read: "Học Sinh A",
  class_read: "8A",
  source_run_id: "R1",
  superseded_by: null,
  status: "extracted" as const,
  version: 1,
  score_earned: null,
  score_possible: null,
  created_at: "2026-10-04T00:00:00Z",
});
const student = {
  id: "S-0001",
  full_name: "Trần B",
  name_search: "tran b",
  class_name: "8A",
  school: null,
  grade: null,
  notes: "",
  created_at: "",
};
const TEST_NAME = "Grade 8 · FinalTerm HK1 · Test 1";

describe("extraction card", () => {
  it("shows the heading, the unsure count, Grade disabled without a thread; Test / Answers open the panels", () => {
    const { api } = fakeApi({});
    const open = vi.fn();
    render(<ExtractionCard api={api} body={body} attempt={attempt(null)} testName={TEST_NAME} onOpenPanel={open} />);
    expect(screen.getByTestId("extraction-heading")).toHaveTextContent(`Extracted: ${TEST_NAME}`);
    expect(screen.getByTestId("unsure-count")).toHaveTextContent("3 AI unsure student answers");
    expect(screen.getByTestId("card-grade")).toBeDisabled();
    expect(screen.getByTestId("student-chip")).toHaveTextContent("Unknown student");
    fireEvent.click(screen.getByTestId("card-open-test"));
    fireEvent.click(screen.getByTestId("card-open-answers"));
    expect(open.mock.calls).toEqual([
      [{ kind: "test", testId: "T-0001" }],
      [{ kind: "answers", attemptId: "A-0001", testId: "T-0001" }],
    ]);
  });

  it("Grade → POST /threads/{id}/runs {kind: grade} for the attempt", async () => {
    const { api, calls } = fakeApi({ "POST /threads/{id}/runs": { id: "R2", kind: "grade", status: "queued" } });
    const started = vi.fn();
    render(<ExtractionCard api={api} body={body} attempt={attempt(null)} threadId="th1" onRunStarted={started} />);
    fireEvent.click(screen.getByTestId("card-grade"));
    await waitFor(() => expect(started).toHaveBeenCalled());
    const post = calls.find((c) => c.method === "POST");
    expect(post?.path).toBe("/threads/th1/runs");
    expect(post?.body).toEqual({ kind: "grade", input: { test_id: "T-0001", attempt_id: "A-0001", reason: "button" } });
  });

  it("no answers read → Grade grades the test alone (its key copy, D4), not the empty attempt", async () => {
    const { api, calls } = fakeApi({ "POST /threads/{id}/runs": { id: "R2", kind: "grade", status: "queued" } });
    render(<ExtractionCard api={api} body={{ ...body, no_answers: true }} attempt={attempt(null)} threadId="th1" />);
    fireEvent.click(screen.getByTestId("card-grade"));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ kind: "grade", input: { test_id: "T-0001", attempt_id: null, reason: "button" } });
  });

  it("a blank test has no Answers and no student chip", () => {
    const { api } = fakeApi({});
    render(
      <ExtractionCard
        api={api}
        body={{ ...body, attempt_id: null, no_answers: true, duplicate: true }}
        attempt={null}
      />,
    );
    expect(screen.getByTestId("no-answers")).toHaveTextContent("No student answers found; T-0001 is already in the bank");
    expect(screen.queryByTestId("card-open-answers")).toBeNull();
    expect(screen.queryByTestId("student-chip")).toBeNull();
  });

  it("create from the name read → PUT /attempts/{id}/student {create_from_read: true}", async () => {
    const { api, calls } = fakeApi({ "GET /students": [], "PUT /attempts/{id}/student": attempt("S-0002") });
    const changed = vi.fn();
    render(<ExtractionCard api={api} body={body} attempt={attempt(null)} onChanged={changed} />);
    fireEvent.click(screen.getByTestId("student-chip"));
    fireEvent.click(screen.getByTestId("student-create-from-read"));
    await waitFor(() => expect(changed).toHaveBeenCalled());
    expect(calls.find((c) => c.method === "PUT")).toMatchObject({
      path: "/attempts/A-0001/student",
      body: { create_from_read: true },
    });
  });

  it("assign an existing student: search GET /students?q= → PUT {student_id}", async () => {
    const { api, calls } = fakeApi({ "GET /students": [student], "PUT /attempts/{id}/student": attempt("S-0001") });
    render(<ExtractionCard api={api} body={body} attempt={attempt(null)} />);
    fireEvent.click(screen.getByTestId("student-chip"));
    fireEvent.change(screen.getByTestId("student-search"), { target: { value: "tran" } });
    await waitFor(() => expect(calls.some((c) => c.query.get("q") === "tran")).toBe(true));
    fireEvent.click(await screen.findByTestId("student-option"));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    expect(calls.find((c) => c.method === "PUT")!.body).toEqual({ student_id: "S-0001", create_from_read: false });
  });

  it("an assigned student shows the student's name", () => {
    const { api } = fakeApi({ "GET /students": [student] });
    render(<ExtractionCard api={api} body={body} attempt={attempt("S-0001")} student={student} />);
    expect(screen.getByTestId("student-chip")).toHaveTextContent("Trần B");
  });
});

describe("the card heading (R22.1.1.7)", () => {
  const headings = () => screen.getAllByRole("heading").map((h) => h.textContent?.trim());

  it("names the test and, when assigned, the student; never the bare word Extracted", () => {
    const { api } = fakeApi({});
    const { rerender } = render(
      <ExtractionCard api={api} body={body} attempt={attempt("S-0001")} student={student} testName={TEST_NAME} />,
    );
    expect(screen.getByTestId("extraction-heading")).toHaveTextContent(`Extracted: ${TEST_NAME} · Trần B`);
    expect(headings()).not.toContain("Extracted");
    expect(headings()).not.toContain("✓ Extracted");

    rerender(<ExtractionCard api={api} body={body} attempt={attempt(null)} testName={TEST_NAME} />);
    expect(screen.getByTestId("extraction-heading")).toHaveTextContent(`Extracted: ${TEST_NAME}`);
    expect(screen.getByTestId("extraction-heading")).not.toHaveTextContent("Trần B");
  });

  it("a blank test names the test; without its name yet, the test id", () => {
    const { api } = fakeApi({});
    const blank = { ...body, attempt_id: null, no_answers: true };
    const { rerender } = render(<ExtractionCard api={api} body={blank} attempt={null} testName={TEST_NAME} />);
    expect(screen.getByTestId("extraction-heading")).toHaveTextContent(`Extracted: ${TEST_NAME}`);
    rerender(<ExtractionCard api={api} body={blank} attempt={null} />);
    expect(screen.getByTestId("extraction-heading")).toHaveTextContent("Extracted: T-0001");
  });

  it("another attempt's student is not named on this card", () => {
    const { api } = fakeApi({});
    const other = { ...attempt("S-0001"), id: "A-0002" };
    render(<ExtractionCard api={api} body={body} attempt={other} student={student} testName={TEST_NAME} />);
    expect(screen.getByTestId("extraction-heading")).toHaveTextContent(`Extracted: ${TEST_NAME}`);
    expect(screen.getByTestId("extraction-heading")).not.toHaveTextContent("Trần B");
  });
});

describe("the student picker closes like a menu (R22.1.1.1)", () => {
  function renderOpen() {
    const { api } = fakeApi({ "GET /students": [student] });
    render(
      <div>
        <p data-testid="outside">elsewhere</p>
        <ExtractionCard api={api} body={body} attempt={attempt(null)} />
      </div>,
    );
    fireEvent.click(screen.getByTestId("student-chip"));
    expect(screen.getByTestId("student-picker")).toBeInTheDocument();
  }

  it("a pointer-down outside closes it", () => {
    renderOpen();
    fireEvent.pointerDown(screen.getByTestId("outside"));
    expect(screen.queryByTestId("student-picker")).toBeNull();
    expect(screen.getByTestId("student-chip")).toHaveAttribute("aria-expanded", "false");
  });

  it("Escape closes it and returns focus to the chip, without closing anything else", () => {
    renderOpen();
    const seen: boolean[] = [];
    const onWindowKey = (e: KeyboardEvent) => seen.push(e.defaultPrevented);
    window.addEventListener("keydown", onWindowKey);
    fireEvent.keyDown(screen.getByTestId("student-search"), { key: "Escape" });
    window.removeEventListener("keydown", onWindowKey);
    expect(screen.queryByTestId("student-picker")).toBeNull();
    expect(screen.getByTestId("student-chip")).toHaveFocus();
    // The global shortcut (Esc closes the panel) sees this Escape as handled.
    expect(seen).toEqual([true]);
  });

  it("stays open on clicks inside it: the search box and the list", async () => {
    renderOpen();
    const search = screen.getByTestId("student-search");
    fireEvent.pointerDown(search);
    fireEvent.click(search);
    fireEvent.change(search, { target: { value: "tr" } });
    const option = await screen.findByTestId("student-option");
    fireEvent.pointerDown(option.closest("ul")!);
    fireEvent.pointerDown(screen.getByTestId("student-picker"));
    expect(screen.getByTestId("student-picker")).toBeInTheDocument();
  });

  it("the chip still toggles it", () => {
    renderOpen();
    const chip = screen.getByTestId("student-chip");
    fireEvent.pointerDown(chip);
    fireEvent.click(chip);
    expect(screen.queryByTestId("student-picker")).toBeNull();
  });

  it("focus moving outside it (Tab out) closes it and leaves focus there (R22.1.4.5)", () => {
    renderOpen();
    screen.getByTestId("student-search").focus(); // inside: stays open
    expect(screen.getByTestId("student-picker")).toBeInTheDocument();
    const next = screen.getByTestId("card-open-test");
    act(() => next.focus());
    expect(screen.queryByTestId("student-picker")).toBeNull();
    expect(next).toHaveFocus();
  });
});

describe("photos and buttons on the card (R22.1.4.4)", () => {
  const testRoute = (over: Record<string, unknown> = {}) => ({
    id: "T-0001",
    pages: [
      { page_no: 1, file_id: "f1" },
      { page_no: 2, file_id: "f2" },
    ],
    key_pages: [],
    merged_into: null,
    ...over,
  });
  const attemptRoute = (files: string[]) => ({
    answers: [],
    pages: files.map((f, i) => ({ attempt_id: "A-0001", page_no: i + 1, file_id: f, source_file_id: f, rotation: 0 })),
  });

  it("a thumbnail per page; page n opens the Test workspace at page n", async () => {
    const { api } = fakeApi({ "GET /tests/{id}": testRoute(), "GET /attempts/{id}": attemptRoute(["f1", "f2"]) });
    const open = vi.fn();
    render(<ExtractionCard api={api} body={body} attempt={attempt(null)} onOpenPanel={open} />);
    const thumbs = await screen.findAllByTestId("card-photo");
    expect(thumbs).toHaveLength(2);
    expect(thumbs[0]!.querySelector("img")).toHaveAttribute("src", "http://127.0.0.1:9/files/f1?token=t&thumb=1");
    expect(thumbs[1]).toHaveAccessibleName("Page 2: open it beside the test");
    fireEvent.click(thumbs[1]!);
    expect(open).toHaveBeenCalledWith({ kind: "test", testId: "T-0001", page: 2 });
  });

  it("photos of another student's paper (the test came from other photos) open beside the answers", async () => {
    const { api } = fakeApi({ "GET /tests/{id}": testRoute(), "GET /attempts/{id}": attemptRoute(["g1"]) });
    const open = vi.fn();
    render(<ExtractionCard api={api} body={body} attempt={attempt(null)} onOpenPanel={open} />);
    fireEvent.click(await screen.findByTestId("card-photo"));
    expect(open).toHaveBeenCalledWith({ kind: "answers", attemptId: "A-0001", testId: "T-0001", page: 1 });
  });

  it("a blank test shows the test's pages", async () => {
    const { api } = fakeApi({ "GET /tests/{id}": testRoute() });
    render(<ExtractionCard api={api} body={{ ...body, attempt_id: null }} attempt={null} />);
    expect(await screen.findAllByTestId("card-photo")).toHaveLength(2);
  });

  it("each button says what it opens", () => {
    const { api } = fakeApi({});
    render(<ExtractionCard api={api} body={body} attempt={attempt(null)} />);
    expect(screen.getByRole("group", { name: "Open beside the photos:" })).toBeInTheDocument();
    expect(screen.getByTestId("card-open-test")).toHaveAccessibleDescription("Opens the test beside its original photos");
    expect(screen.getByTestId("card-open-answers")).toHaveAccessibleDescription(
      "Opens the student answers read from the paper beside the student's photos",
    );
    expect(screen.getByTestId("card-open-keys")).toHaveAccessibleDescription("Opens the key beside the test's photos");
  });

  it("after a merge, Test and Key open the merged-into test", async () => {
    // A blank test's card: the test says where it was merged.
    const { api } = fakeApi({
      "GET /tests/{id}": (c: FakeCall) =>
        c.path.endsWith("T-0001") ? testRoute({ merged_into: "T-0002" }) : testRoute({ id: "T-0002" }),
    });
    const open = vi.fn();
    render(<ExtractionCard api={api} body={{ ...body, attempt_id: null }} attempt={null} onOpenPanel={open} />);
    await waitFor(() => {
      fireEvent.click(screen.getByTestId("card-open-test"));
      expect(open).toHaveBeenLastCalledWith({ kind: "test", testId: "T-0002" });
    });
    fireEvent.click(screen.getByTestId("card-open-keys"));
    expect(open).toHaveBeenLastCalledWith({ kind: "keys", testId: "T-0002" });
  });

  it("after a merge, an attempt's card follows its attempt to the merged-into test", () => {
    const { api } = fakeApi({});
    const open = vi.fn();
    const moved = { ...attempt(null), test_id: "T-0002" };
    render(<ExtractionCard api={api} body={body} attempt={moved} onOpenPanel={open} />);
    fireEvent.click(screen.getByTestId("card-open-test"));
    fireEvent.click(screen.getByTestId("card-open-keys"));
    expect(open.mock.calls).toEqual([[{ kind: "test", testId: "T-0002" }], [{ kind: "keys", testId: "T-0002" }]]);
  });
});

describe("create from a typed name, edit the name (R22.1.1.4)", () => {
  it("a typed name that matches no student offers Create “<typed>” → POST /students, then PUT the attempt", async () => {
    const created = { ...student, id: "S-0002", full_name: "Nguyễn Thị Ánh", name_search: "nguyen thi anh" };
    const { api, calls } = fakeApi({
      "GET /students": (c: FakeCall) => (c.query.get("q") ? [] : [student]),
      "POST /students": created,
      "PUT /attempts/{id}/student": attempt("S-0002"),
    });
    const changed = vi.fn();
    render(<ExtractionCard api={api} body={body} attempt={attempt(null)} onChanged={changed} />);
    fireEvent.click(screen.getByTestId("student-chip"));
    fireEvent.change(screen.getByTestId("student-search"), { target: { value: "  Nguyễn  Thị Ánh " } });
    const create = await screen.findByTestId("student-create-typed");
    expect(create).toHaveTextContent("Create “Nguyễn Thị Ánh”");
    fireEvent.click(create);
    await waitFor(() => expect(changed).toHaveBeenCalled());
    expect(calls.find((c) => c.method === "POST")).toMatchObject({
      path: "/students",
      body: { full_name: "Nguyễn Thị Ánh" },
    });
    expect(calls.find((c) => c.method === "PUT")).toMatchObject({
      path: "/attempts/A-0001/student",
      body: { student_id: "S-0002", create_from_read: false },
    });
    expect(screen.queryByTestId("student-picker")).toBeNull();
  });

  it("the chip shows the created student once the thread reloads", () => {
    const created = { ...student, id: "S-0002", full_name: "Nguyễn Thị Ánh" };
    const { api } = fakeApi({});
    render(<ExtractionCard api={api} body={body} attempt={attempt("S-0002")} student={created} />);
    expect(screen.getByTestId("student-chip")).toHaveTextContent("Nguyễn Thị Ánh");
  });

  it("a typed name that is already a student (accents and case aside) offers no Create", async () => {
    const { api } = fakeApi({ "GET /students": [student] });
    render(<ExtractionCard api={api} body={body} attempt={attempt(null)} />);
    fireEvent.click(screen.getByTestId("student-chip"));
    fireEvent.change(screen.getByTestId("student-search"), { target: { value: "TRẦN  b" } });
    await screen.findByTestId("student-option");
    await act(async () => {});
    expect(screen.queryByTestId("student-create-typed")).toBeNull();
  });

  it("the assigned student's name can be edited → PATCH /students/{id} {full_name}", async () => {
    const a = { ...student, full_name: "A", name_search: "a" };
    const { api, calls } = fakeApi({
      "GET /students": [a],
      "PATCH /students/{id}": { ...a, full_name: "Trần Bảo", name_search: "tran bao" },
    });
    const changed = vi.fn();
    render(<ExtractionCard api={api} body={body} attempt={attempt("S-0001")} student={a} onChanged={changed} />);
    fireEvent.click(screen.getByTestId("student-chip"));
    const input = screen.getByTestId("student-name-input");
    expect(input).toHaveValue("A");
    expect(input).toHaveFocus();
    expect(screen.getByTestId("student-name-save")).toBeDisabled(); // unchanged
    expect(screen.queryByTestId("student-create-from-read")).toBeNull(); // already assigned
    fireEvent.change(input, { target: { value: " Trần  Bảo " } });
    fireEvent.click(screen.getByTestId("student-name-save"));
    await waitFor(() => expect(changed).toHaveBeenCalled());
    expect(calls.find((c) => c.method === "PATCH")).toMatchObject({
      path: "/students/S-0001",
      body: { full_name: "Trần Bảo" },
    });
  });

  it("a refused edit shows why and keeps the picker open", async () => {
    const { api } = fakeApi({
      "GET /students": [student],
      "PATCH /students/{id}": new FakeStatus(422, { detail: "full_name must not be empty" }),
    });
    render(<ExtractionCard api={api} body={body} attempt={attempt("S-0001")} student={student} />);
    fireEvent.click(screen.getByTestId("student-chip"));
    fireEvent.change(screen.getByTestId("student-name-input"), { target: { value: "X" } });
    fireEvent.submit(screen.getByTestId("student-edit"));
    expect(await screen.findByRole("alert")).toHaveTextContent("full_name must not be empty");
    expect(screen.getByTestId("student-picker")).toBeInTheDocument();
  });
});
