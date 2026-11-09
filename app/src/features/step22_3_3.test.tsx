// Step 22.3.3 (R22.3.3.4): Delete… on a student, Copy details from… in the test details, and
// "same series as…" at the photo check. Synthetic names only.
import { useState } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/AppShell";
import { TestPanel } from "@/features/panels/TestPanel";
import { PhotoCheckCard } from "@/features/photo-check/PhotoCheckCard";
import { toExtractInput, type PhotoCheckDraft } from "@/features/photo-check/draft";
import { StudentsTab } from "@/features/students-tab/StudentsTab";
import { resetSeries } from "@/lib/series";
import { fakeApi, FakeStatus, type FakeCall } from "@/lib/testApi";

const T0 = "2026-10-01T00:00:00Z";

afterEach(() => {
  window.sessionStorage.clear();
  resetSeries();
});

const student = (id: string, name: string, count: number) => ({
  id,
  full_name: name,
  name_search: name.toLowerCase(),
  class_name: "8A",
  school: null,
  grade: null,
  created_at: T0,
  thread_count: count,
});

const ref = (id: string, title: string) => ({
  id,
  shown_title: title,
  test_id: "T-0001",
  test_display_name: "Final 8.1",
  last_activity: T0,
});

describe("Delete… on a student (R22.3.3.4)", () => {
  it("asks first, lists the threads, Keep changes nothing, Delete student deletes and reloads", async () => {
    let rows = [student("S-0001", "Học Sinh A", 2), student("S-0002", "Học Sinh B", 0)];
    const { api, calls } = fakeApi({
      "GET /threads/{id}": new FakeStatus(404),
      "GET /students": () => rows,
      "GET /students/{id}/delete-preview": {
        student_id: "S-0001",
        full_name: "Học Sinh A",
        threads: [ref("t1", "Final 8.1 · Học Sinh A"), ref("t2", "Mid 8.1 · Học Sinh A")],
        kept_threads: [ref("t3", "Shared paper")],
        attempt_count: 3,
      },
      "DELETE /students/{id}": () => {
        rows = rows.filter((s) => s.id !== "S-0001");
        return null;
      },
    });
    const onThreadsChanged = vi.fn();
    render(<AppShell connection="open" api={api} threads={[]} onThreadsChanged={onThreadsChanged} />);
    fireEvent.click(screen.getByRole("tab", { name: "Students" }));
    const del = () => screen.getAllByTestId("student-delete-button")[0]!;
    await waitFor(() => expect(screen.getAllByTestId("student-delete-button")).toHaveLength(2));
    expect(del()).toHaveAccessibleName("Delete Học Sinh A…");

    fireEvent.click(del());
    let dialog = await screen.findByTestId("confirm-dialog");
    expect(dialog).toHaveTextContent("Delete “Học Sinh A”?");
    const listed = within(within(dialog).getByTestId("delete-threads")).getAllByRole("listitem");
    expect(listed.map((li) => li.textContent)).toEqual(["Final 8.1 · Học Sinh A", "Mid 8.1 · Học Sinh A"]);
    expect(within(dialog).getByTestId("delete-kept-threads")).toHaveTextContent("1 thread also has another student's paper");
    expect(dialog).toHaveTextContent("Their tests stay in the bank");
    fireEvent.click(within(dialog).getByRole("button", { name: "Keep student" }));
    await waitFor(() => expect(screen.queryByTestId("confirm-dialog")).toBeNull());
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);

    fireEvent.click(del());
    dialog = await screen.findByTestId("confirm-dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete student" }));
    await waitFor(() => expect(onThreadsChanged).toHaveBeenCalled());
    expect(calls.filter((c) => c.method === "DELETE").map((c) => c.path)).toEqual(["/students/S-0001"]);
    await waitFor(() => expect(screen.getAllByTestId("student-row")).toHaveLength(1));
    expect(screen.getByTestId("student-name")).toHaveTextContent("Học Sinh B");
  });

  it("a refused delete (409) shows why and keeps the student", async () => {
    const { api } = fakeApi({
      "GET /threads/{id}": new FakeStatus(404),
      "GET /students": [student("S-0001", "Học Sinh A", 1)],
      "GET /students/{id}/delete-preview": {
        student_id: "S-0001",
        full_name: "Học Sinh A",
        threads: [ref("t1", "Final 8.1 · Học Sinh A")],
        kept_threads: [],
        attempt_count: 1,
      },
      "DELETE /students/{id}": new FakeStatus(409, { detail: "A run is going in this thread; stop or discard it first." }),
    });
    render(<AppShell connection="open" api={api} threads={[]} />);
    fireEvent.click(screen.getByRole("tab", { name: "Students" }));
    fireEvent.click(await screen.findByTestId("student-delete-button"));
    const dialog = await screen.findByTestId("confirm-dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete student" }));
    expect(await screen.findByText(/Could not delete “Học Sinh A”: .*stop or discard/)).toBeInTheDocument();
    expect(screen.getAllByTestId("student-row")).toHaveLength(1);
  });

  it("after a delete, focus goes to the row now in its place, or to the search box", async () => {
    let rows = [student("S-0001", "Học Sinh A", 0), student("S-0002", "Học Sinh B", 0)];
    const { api } = fakeApi({ "GET /students": () => rows });
    const onDelete = vi.fn();
    const { rerender } = render(<StudentsTab api={api} onDelete={onDelete} />);
    await waitFor(() => expect(screen.getAllByTestId("student-row")).toHaveLength(2));
    fireEvent.click(screen.getAllByTestId("student-delete-button")[0]!);
    expect(onDelete).toHaveBeenCalledWith("S-0001", "Học Sinh A");
    (document.activeElement as HTMLElement | null)?.blur();
    rows = [rows[1]!];
    rerender(<StudentsTab api={api} onDelete={onDelete} refreshKey={1} />);
    await waitFor(() => expect(screen.getAllByTestId("student-row")).toHaveLength(1));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId("student-item")));

    fireEvent.click(screen.getByTestId("student-delete-button"));
    (document.activeElement as HTMLElement | null)?.blur();
    rows = [];
    rerender(<StudentsTab api={api} onDelete={onDelete} refreshKey={2} />);
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId("students-search")));
  });
});

describe("Copy details from… (R22.3.3.4)", () => {
  function sidecar() {
    const meta = (over: Record<string, unknown>) => ({
      occasion: "FinalTerm",
      grade: 8,
      term: 1,
      school: "Target School",
      source: null,
      year: "2023",
      test_number: "1",
      edited_fields: [] as string[],
      ...over,
    });
    const target = { id: "T-0001", meta: meta({}), content: { sections: [] }, picture_paths: {}, content_text: "" };
    const source = {
      id: "T-0002",
      meta: meta({ occasion: "MidTerm", term: 2, school: null, source: "Synthetic Book", year: "2024-2025", grade: 6, test_number: "9" }),
      content: { sections: [] },
      picture_paths: {},
      content_text: "",
    };
    return fakeApi({
      "GET /tests": [
        { id: "T-0001", display_name: "Target test", meta: target.meta, points_possible: 10, attempt_count: 0, open_review_count: 0, updated_at: T0 },
        { id: "T-0002", display_name: "Series test", meta: source.meta, points_possible: 10, attempt_count: 0, open_review_count: 0, updated_at: T0 },
      ],
      "GET /tests/{id}": (c: FakeCall) => (c.path.endsWith("T-0002") ? source : target),
      "POST /tests/{id}/copy-details": () => {
        Object.assign(target.meta, { occasion: "MidTerm", term: 2, source: "Synthetic Book", year: "2024-2025" });
        target.meta.edited_fields = ["occasion", "term", "source", "year"];
        return target;
      },
    });
  }

  it("picks a test (not itself), shows the five values, and saves; focus returns to the button", async () => {
    const { api, calls } = sidecar();
    const onChanged = vi.fn();
    render(<TestPanel api={api} testId="T-0001" onChanged={onChanged} />);
    const open = await screen.findByTestId("copy-details-open");
    fireEvent.click(open);
    const search = screen.getByTestId("copy-details-search");
    await waitFor(() => expect(document.activeElement).toBe(search));
    fireEvent.change(search, { target: { value: "test" } });
    const options = await screen.findAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual(["Series test · T-0002"]); // not the test itself
    fireEvent.click(options[0]!);

    const values = await screen.findByTestId("copy-details-values");
    const row = (f: string) => within(values).getAllByTestId("copy-details-row").find((r) => r.dataset.field === f)!;
    expect(within(values).getAllByTestId("copy-details-row").map((r) => r.dataset.field)).toEqual([
      "occasion",
      "term",
      "school",
      "source",
      "year",
    ]);
    expect(row("term")).toHaveTextContent("1 → 2");
    expect(row("year")).toHaveTextContent("2023 → 2024-2025");
    expect(row("school")).toHaveTextContent("Target School · stays");
    expect(screen.getByTestId("copy-details-box")).toHaveTextContent("The grade and test number stay.");

    fireEvent.click(screen.getByTestId("copy-details-save"));
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    const post = calls.find((c) => c.method === "POST")!;
    expect(post.path).toBe("/tests/T-0001/copy-details");
    expect(post.body).toEqual({ from_test_id: "T-0002" });
    await waitFor(() => expect(screen.queryByTestId("copy-details-box")).toBeNull());
    expect(document.activeElement).toBe(screen.getByTestId("copy-details-open"));
  });

  it("Escape closes without copying and returns focus", async () => {
    const { api, calls } = sidecar();
    render(<TestPanel api={api} testId="T-0001" />);
    fireEvent.click(await screen.findByTestId("copy-details-open"));
    fireEvent.keyDown(screen.getByTestId("copy-details-search"), { key: "Escape" });
    expect(screen.queryByTestId("copy-details-box")).toBeNull();
    expect(document.activeElement).toBe(screen.getByTestId("copy-details-open"));
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });
});

describe("same series as… at the photo check (R22.3.3.4)", () => {
  const start: PhotoCheckDraft = { pages: [{ file_id: "fa", rotation: 0, is_key: false, text_file_id: null }], existingTest: null };

  function Card({ api, onRun }: { api: ReturnType<typeof fakeApi>["api"]; onRun: (d: PhotoCheckDraft) => void }) {
    const [draft, setDraft] = useState(start);
    return <PhotoCheckCard api={api} draft={draft} onChange={setDraft} onAddFiles={() => {}} onRun={() => onRun(draft)} />;
  }

  // Step 22.5.2 (D5): the pick is a name from the Series list, sent as series_name (R22.5.2.8).
  it("offers the pick next to the existing test and sends series_name", async () => {
    const { api } = fakeApi({ "GET /series": [{ id: 1, name: "Series test", position: 0, test_count: 1 }] });
    const onRun = vi.fn();
    render(<Card api={api} onRun={onRun} />);
    expect(screen.getByTestId("existing-test")).toBeInTheDocument();
    act(() => screen.getByTestId("series-test-search").focus());
    fireEvent.change(screen.getByTestId("series-test-search"), { target: { value: "series" } });
    fireEvent.click((await screen.findAllByRole("option"))[0]!);
    expect(screen.getByTestId("series-test-picked")).toHaveTextContent("Series test");
    fireEvent.click(screen.getByTestId("photo-run"));
    const sent = onRun.mock.calls[0]![0] as PhotoCheckDraft;
    expect(toExtractInput(sent)).toMatchObject({ existing_test_id: null, series_name: "Series test" });
    expect(toExtractInput(sent)).not.toHaveProperty("series_from_test_id");
  });

  it("a picked existing test hides the series pick and is not sent with it", () => {
    const draft: PhotoCheckDraft = { ...start, existingTest: { id: "T-0001", display_name: "Bank" }, seriesName: "S" };
    expect(toExtractInput(draft)).not.toHaveProperty("series_name");
    const { api } = fakeApi({});
    render(<PhotoCheckCard api={api} draft={draft} onChange={() => {}} onAddFiles={() => {}} onRun={() => {}} />);
    expect(screen.queryByTestId("series-test")).toBeNull();
  });
});
