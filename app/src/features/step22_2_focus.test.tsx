// Step 22.2 verifier findings F3 (focus after "Delete…", WCAG 2.4.3) and F4 (the Students row's
// thread count is read as text, WCAG 4.1.2). Synthetic names only.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AppShell } from "@/components/AppShell";
import { StudentsTab } from "@/features/students-tab/StudentsTab";
import type { ThreadSummary } from "@/features/threads/threads";
import { fakeApi } from "@/lib/testApi";

const T0 = "2026-10-01T00:00:00Z";

function summary(id: string, title: string): ThreadSummary {
  return {
    thread: { id, title: "New thread", test_id: "T-0001", kind: "filled", created_at: T0 },
    shown_title: title,
    kind: "filled",
    group: "Học Sinh A",
    student_id: "S-0001",
    last_activity: T0,
    open_review_count: 0,
  } as ThreadSummary;
}

const testRow = (id: string, name: string) => ({
  id,
  display_name: name,
  meta: { occasion: "FinalTerm", grade: 8, term: 1, edited_fields: [] },
  points_possible: 10,
  attempt_count: 1,
  open_review_count: 0,
  updated_at: T0,
});

const preview = (id: string, name: string) => ({
  test_id: id,
  display_name: name,
  threads: [],
  kept_threads: [],
  merged_test_ids: [],
  attempt_count: 0,
});

afterEach(() => window.sessionStorage.clear());

describe("focus after Delete… in the Tests tab (F3)", () => {
  it("Keep test returns focus to the row's ⋯ button", async () => {
    const { api } = fakeApi({
      "GET /tests": [testRow("T-0001", "Final 8.1"), testRow("T-0002", "Mid 7.2")],
      "GET /tests/{id}/delete-preview": preview("T-0001", "Final 8.1"),
    });
    render(<AppShell connection="open" api={api} threads={[]} />);
    fireEvent.click(screen.getByRole("tab", { name: "Tests" }));
    const menuButton = (await screen.findAllByTestId("test-menu-button"))[0]!;
    fireEvent.click(menuButton);
    fireEvent.click(screen.getByTestId("test-delete"));
    const dialog = await screen.findByTestId("confirm-dialog");
    expect(within(dialog).getByRole("button", { name: "Keep test" })).toHaveFocus();
    fireEvent.click(within(dialog).getByRole("button", { name: "Keep test" }));
    await waitFor(() => expect(screen.queryByTestId("confirm-dialog")).toBeNull());
    expect(menuButton).toHaveFocus();
  });

  it("Escape in the dialog returns focus to the row's ⋯ button too", async () => {
    const { api } = fakeApi({
      "GET /tests": [testRow("T-0001", "Final 8.1")],
      "GET /tests/{id}/delete-preview": preview("T-0001", "Final 8.1"),
    });
    render(<AppShell connection="open" api={api} threads={[]} />);
    fireEvent.click(screen.getByRole("tab", { name: "Tests" }));
    const menuButton = (await screen.findAllByTestId("test-menu-button"))[0]!;
    fireEvent.click(menuButton);
    fireEvent.click(screen.getByTestId("test-delete"));
    await screen.findByTestId("confirm-dialog");
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByTestId("confirm-dialog")).toBeNull());
    expect(menuButton).toHaveFocus();
  });

  it("Delete test moves focus to the row now in its place", async () => {
    let deleted = false;
    const { api } = fakeApi({
      "GET /tests": () =>
        deleted ? [testRow("T-0002", "Mid 7.2")] : [testRow("T-0001", "Final 8.1"), testRow("T-0002", "Mid 7.2")],
      "GET /tests/{id}/delete-preview": preview("T-0001", "Final 8.1"),
      "DELETE /tests/{id}": () => {
        deleted = true;
        return null;
      },
    });
    render(<AppShell connection="open" api={api} threads={[]} />);
    fireEvent.click(screen.getByRole("tab", { name: "Tests" }));
    fireEvent.click((await screen.findAllByTestId("test-menu-button"))[0]!);
    fireEvent.click(screen.getByTestId("test-delete"));
    fireEvent.click(within(await screen.findByTestId("confirm-dialog")).getByRole("button", { name: "Delete test" }));
    await waitFor(() => expect(screen.getAllByTestId("test-item")).toHaveLength(1));
    await waitFor(() => expect(screen.getByTestId("test-item")).toHaveFocus());
  });

  it("deleting the last test moves focus to the search box", async () => {
    let deleted = false;
    const { api } = fakeApi({
      "GET /tests": () => (deleted ? [] : [testRow("T-0001", "Final 8.1")]),
      "GET /tests/{id}/delete-preview": preview("T-0001", "Final 8.1"),
      "DELETE /tests/{id}": () => {
        deleted = true;
        return null;
      },
    });
    render(<AppShell connection="open" api={api} threads={[]} />);
    fireEvent.click(screen.getByRole("tab", { name: "Tests" }));
    fireEvent.click((await screen.findAllByTestId("test-menu-button"))[0]!);
    fireEvent.click(screen.getByTestId("test-delete"));
    fireEvent.click(within(await screen.findByTestId("confirm-dialog")).getByRole("button", { name: "Delete test" }));
    await screen.findByTestId("tests-empty");
    await waitFor(() => expect(screen.getByTestId("tests-search")).toHaveFocus());
  });
});

describe("focus after Delete… in the Chats list (F3)", () => {
  it("Keep thread returns focus to the row's ⋯ button; Delete thread moves it to the next thread", async () => {
    const { api } = fakeApi({ "DELETE /threads/{id}": null });
    const threads = [summary("t1", "Final 8.1"), summary("t2", "Mid 7.2")];
    const { rerender } = render(<AppShell connection="open" api={api} threads={threads} />);
    const menuButton = screen.getAllByTestId("thread-menu-button")[0]!;
    fireEvent.click(menuButton);
    fireEvent.click(screen.getByTestId("thread-delete"));
    let dialog = await screen.findByTestId("confirm-dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Keep thread" }));
    await waitFor(() => expect(screen.queryByTestId("confirm-dialog")).toBeNull());
    expect(menuButton).toHaveFocus();

    let reloaded = false;
    const onThreadsChanged = () => {
      reloaded = true;
    };
    rerender(<AppShell connection="open" api={api} threads={threads} onThreadsChanged={onThreadsChanged} />);
    fireEvent.click(menuButton);
    fireEvent.click(screen.getByTestId("thread-delete"));
    dialog = await screen.findByTestId("confirm-dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete thread" }));
    await waitFor(() => expect(reloaded).toBe(true));
    rerender(<AppShell connection="open" api={api} threads={[threads[1]!]} onThreadsChanged={onThreadsChanged} />);
    await waitFor(() => expect(screen.getByTestId("thread-item")).toHaveFocus());
    expect(screen.getByTestId("thread-item")).toHaveAttribute("data-thread-id", "t2");
  });
});

describe("Students tab thread count (F4)", () => {
  it("is part of the row button's name as words", async () => {
    const students = [
      { id: "S-0001", full_name: "Học Sinh A", name_search: "hoc sinh a", class_name: "8A", created_at: T0, thread_count: 3 },
      { id: "S-0002", full_name: "Học Sinh B", name_search: "hoc sinh b", class_name: null, created_at: T0, thread_count: 1 },
    ];
    const { api } = fakeApi({ "GET /students": students });
    render(<StudentsTab api={api} debounceMs={0} />);
    await screen.findAllByTestId("student-item");
    expect(screen.getByRole("button", { name: /^Học Sinh A.*8A ?3 threads$/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Học Sinh B.*class ?1 thread$/ })).toBeInTheDocument();
    expect(screen.getAllByTestId("student-thread-count").map((c) => c.textContent)).toEqual(["3", "1"]);
  });
});
