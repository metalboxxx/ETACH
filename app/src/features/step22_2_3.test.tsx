// Step 22.2.3: Delete… for threads and tests (R22.2.3.3), the Students tab and the student chip's
// class (R22.2.3.4). Synthetic names only.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/AppShell";
import { StudentChip } from "@/features/cards/ExtractionCard";
import { StudentsTab } from "@/features/students-tab/StudentsTab";
import type { ThreadSummary } from "@/features/threads/threads";
import { FakeStatus, fakeApi } from "@/lib/testApi";

const T0 = "2026-10-01T00:00:00Z";

function summary(id: string, title: string, review = 0): ThreadSummary {
  return {
    thread: { id, title: "New thread", test_id: "T-0001", kind: "filled", created_at: T0 },
    shown_title: title,
    kind: "filled",
    group: "Học Sinh A",
    student_id: "S-0001",
    last_activity: T0,
    open_review_count: review,
  } as ThreadSummary;
}

const testRow = (id: string, name: string, review = 0) => ({
  id,
  display_name: name,
  meta: { occasion: "FinalTerm", grade: 8, term: 1, edited_fields: [] },
  points_possible: 10,
  attempt_count: 1,
  open_review_count: review,
  updated_at: T0,
});

const ref = (id: string, title: string) => ({
  id,
  shown_title: title,
  test_id: "T-0001",
  test_display_name: "Final 8.1",
  last_activity: T0,
});

afterEach(() => window.sessionStorage.clear());

describe("Delete a thread (R22.2.3.3)", () => {
  it("asks first; Cancel changes nothing; Delete thread deletes, reloads and closes the open thread", async () => {
    window.sessionStorage.setItem("etach.activeThread", JSON.stringify("t1"));
    const { api, calls } = fakeApi({
      "GET /threads/{id}": new FakeStatus(404),
      "GET /threads/{id}/messages": [],
      "DELETE /threads/{id}": null,
    });
    const onThreadsChanged = vi.fn();
    render(
      <AppShell
        connection="open"
        api={api}
        threads={[summary("t1", "Final 8.1 · Học Sinh A"), summary("t2", "Mid 8.1")]}
        onThreadsChanged={onThreadsChanged}
      />,
    );
    const row = () => screen.getAllByTestId("thread-menu-button")[0]!;
    fireEvent.click(row());
    fireEvent.click(screen.getByTestId("thread-delete"));
    let dialog = await screen.findByTestId("confirm-dialog");
    expect(dialog).toHaveTextContent("Delete “Final 8.1 · Học Sinh A”?");
    expect(dialog).toHaveTextContent("The test stays in the bank");
    fireEvent.click(within(dialog).getByRole("button", { name: "Keep thread" }));
    await waitFor(() => expect(screen.queryByTestId("confirm-dialog")).toBeNull());
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);

    fireEvent.click(row());
    fireEvent.click(screen.getByTestId("thread-delete"));
    dialog = await screen.findByTestId("confirm-dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete thread" }));
    await waitFor(() => expect(onThreadsChanged).toHaveBeenCalled());
    expect(calls.filter((c) => c.method === "DELETE").map((c) => c.path)).toEqual(["/threads/t1"]);
    expect(window.sessionStorage.getItem("etach.activeThread")).toBeNull();
  });

  it("shows a 409 in words", async () => {
    const { api } = fakeApi({
      "DELETE /threads/{id}": new FakeStatus(409, {
        detail: "a run is still going or can be resumed here; stop or discard it first",
      }),
    });
    render(<AppShell connection="open" api={api} threads={[summary("t1", "Final 8.1")]} />);
    fireEvent.click(screen.getByTestId("thread-menu-button"));
    fireEvent.click(screen.getByTestId("thread-delete"));
    fireEvent.click(within(await screen.findByTestId("confirm-dialog")).getByRole("button", { name: "Delete thread" }));
    expect(await screen.findByTestId("delete-error")).toHaveTextContent(
      "Could not delete “Final 8.1”: a run is still going or can be resumed here; stop or discard it first",
    );
  });
});

describe("Delete a test (R22.2.3.3)", () => {
  it("names the threads that go, deletes, reloads the list and closes its open workspace", async () => {
    let deleted = false;
    const { api, calls } = fakeApi({
      "GET /tests": () => (deleted ? [testRow("T-0002", "Mid 7.2")] : [testRow("T-0001", "Final 8.1", 2), testRow("T-0002", "Mid 7.2")]),
      "GET /tests/{id}/delete-preview": {
        test_id: "T-0001",
        display_name: "Final 8.1",
        threads: [ref("t1", "Final 8.1 · Học Sinh A"), ref("t3", "Final 8.1 · Học Sinh C")],
        kept_threads: [ref("t2", "Mixed")],
        merged_test_ids: [],
        attempt_count: 3,
      },
      "GET /tests/{id}": new FakeStatus(500),
      "DELETE /tests/{id}": () => {
        deleted = true;
        return null;
      },
    });
    const onThreadsChanged = vi.fn();
    render(
      <AppShell
        connection="open"
        api={api}
        threads={[]}
        onThreadsChanged={onThreadsChanged}
        initialPanel={{ kind: "test", testId: "T-0001" }}
      />,
    );
    expect(screen.getByTestId("artifact-panel")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Tests" }));
    await screen.findAllByTestId("test-item");
    fireEvent.click(screen.getAllByTestId("test-menu-button")[0]!);
    fireEvent.click(screen.getByTestId("test-delete"));
    const dialog = await screen.findByTestId("confirm-dialog");
    expect(dialog).toHaveTextContent("Delete “Final 8.1”?");
    expect(within(dialog).getByTestId("delete-threads")).toHaveTextContent("Final 8.1 · Học Sinh A");
    expect(within(dialog).getByTestId("delete-threads")).toHaveTextContent("Final 8.1 · Học Sinh C");
    expect(within(dialog).getByTestId("delete-kept-threads")).toHaveTextContent("1 thread keeps its other test");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete test" }));
    await waitFor(() => expect(onThreadsChanged).toHaveBeenCalled());
    expect(calls.filter((c) => c.method === "DELETE").map((c) => c.path)).toEqual(["/tests/T-0001"]);
    await waitFor(() =>
      expect(screen.getAllByTestId("test-item").map((i) => i.getAttribute("data-test-id"))).toEqual(["T-0002"]),
    );
    expect(screen.queryByTestId("unsure-mark")).toBeNull();
    await waitFor(() => expect(screen.queryByTestId("workspace")).toBeNull());
    expect(screen.queryByTestId("test-panel")).toBeNull();
  });

  it("Keep test changes nothing", async () => {
    const { api, calls } = fakeApi({
      "GET /tests": [testRow("T-0001", "Final 8.1")],
      "GET /tests/{id}/delete-preview": {
        test_id: "T-0001",
        display_name: "Final 8.1",
        threads: [],
        kept_threads: [],
        merged_test_ids: [],
        attempt_count: 0,
      },
    });
    render(<AppShell connection="open" api={api} threads={[]} />);
    fireEvent.click(screen.getByRole("tab", { name: "Tests" }));
    fireEvent.click((await screen.findAllByTestId("test-menu-button"))[0]!);
    fireEvent.click(screen.getByTestId("test-delete"));
    const dialog = await screen.findByTestId("confirm-dialog");
    expect(dialog).toHaveTextContent("No thread uses it.");
    fireEvent.click(within(dialog).getByRole("button", { name: "Keep test" }));
    await waitFor(() => expect(screen.queryByTestId("confirm-dialog")).toBeNull());
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
  });
});

describe("Students tab (R22.2.3.4)", () => {
  const students = [
    { id: "S-0001", full_name: "Nguyễn Thị Ánh", name_search: "nguyen thi anh", class_name: "8A", created_at: T0, thread_count: 2 },
    { id: "S-0002", full_name: "Lê Văn Bảo", name_search: "le van bao", class_name: null, created_at: T0, thread_count: 0 },
  ];

  it("lists students with class and thread count, searches, and opens the student (R22.5.5.11)", async () => {
    const { api, calls } = fakeApi({
      "GET /students": (c: { query: URLSearchParams }) =>
        c.query.get("q") ? students.filter((s) => s.name_search.includes("anh")) : students,
      "GET /students/{id}": { student: students[0], threads: [ref("t1", "Final 8.1 · Nguyễn Thị Ánh")] },
    });
    const onOpenStudent = vi.fn();
    render(<StudentsTab api={api} onOpenStudent={onOpenStudent} debounceMs={0} />);
    const items = await screen.findAllByTestId("student-item");
    expect(items).toHaveLength(2);
    expect(screen.getAllByTestId("student-class").map((c) => c.textContent)).toEqual(["Class 8A", "No class"]);
    expect(screen.getAllByTestId("student-thread-count").map((c) => c.textContent)).toEqual(["2", "0"]);

    fireEvent.change(screen.getByTestId("students-search"), { target: { value: "Ánh" } });
    await waitFor(() => expect(screen.getAllByTestId("student-item")).toHaveLength(1));
    expect(calls.some((c) => c.path === "/students" && c.query.get("q") === "Ánh")).toBe(true);

    // The student's threads are listed in the skills view now (step22_5_5.test.tsx).
    fireEvent.click(screen.getByTestId("student-item"));
    expect(onOpenStudent).toHaveBeenCalledWith(students[0]!.id, students[0]!.full_name);
  });

  it("edits name and class: Enter saves through PATCH, Escape cancels", async () => {
    const { api, calls } = fakeApi({ "GET /students": students, "PATCH /students/{id}": students[0] });
    render(<StudentsTab api={api} />);
    await screen.findAllByTestId("student-item");
    fireEvent.click(screen.getAllByTestId("student-edit-button")[0]!);
    fireEvent.change(screen.getByTestId("student-edit-name"), { target: { value: "Nguyễn Thị Ánh Hồng" } });
    fireEvent.keyDown(screen.getByTestId("student-edit-name"), { key: "Escape" });
    expect(screen.queryByTestId("student-edit-row")).toBeNull();
    expect(calls.some((c) => c.method === "PATCH")).toBe(false);

    fireEvent.click(screen.getAllByTestId("student-edit-button")[0]!);
    fireEvent.change(screen.getByTestId("student-edit-class"), { target: { value: "9B" } });
    fireEvent.keyDown(screen.getByTestId("student-edit-class"), { key: "Enter" });
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    const patch = calls.find((c) => c.method === "PATCH")!;
    expect(patch.path).toBe("/students/S-0001");
    expect(patch.body).toEqual({ full_name: "Nguyễn Thị Ánh", class_name: "9B", school: null }); // 22.4.2: the School field is sent too
    await waitFor(() => expect(screen.queryByTestId("student-edit-row")).toBeNull());
  });
});

describe("Student chip (R22.2.3.4)", () => {
  const student = { id: "S-0001", full_name: "Học Sinh A", name_search: "hoc sinh a", class_name: "8A", school: null, grade: null, notes: "", created_at: T0 };

  it("edits the class and switches the paper to another student", async () => {
    const { api, calls } = fakeApi({
      "GET /students": [{ ...student, thread_count: 1 }, { ...student, id: "S-0002", full_name: "Học Sinh B", name_search: "hoc sinh b", thread_count: 0 }],
      "PATCH /students/{id}": student,
      "PUT /attempts/{id}/student": {},
    });
    const onChanged = vi.fn();
    render(<StudentChip api={api} attemptId="A-0001" studentId="S-0001" student={student} nameRead={null} onChanged={onChanged} />);
    fireEvent.click(screen.getByTestId("student-chip"));
    expect(screen.getByTestId("student-class-input")).toHaveValue("8A");
    fireEvent.change(screen.getByTestId("student-class-input"), { target: { value: " 9C " } });
    fireEvent.click(screen.getByTestId("student-name-save"));
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ class_name: "9C" });

    fireEvent.click(screen.getByTestId("student-chip"));
    const other = await screen.findByText("Học Sinh B");
    fireEvent.click(other);
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(2));
    const put = calls.find((c) => c.method === "PUT")!;
    expect(put.path).toBe("/attempts/A-0001/student");
    expect(put.body).toEqual({ student_id: "S-0002", create_from_read: false });
  });
});
