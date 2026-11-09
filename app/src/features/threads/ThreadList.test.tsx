// R15.8: the sidebar groups threads by student, plus Chưa rõ and Blank tests (from GET /threads).
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ThreadList } from "./ThreadList";
import type { ThreadSummary } from "./threads";

function row(id: string, title: string, kind: ThreadSummary["kind"], group: string, at: string): ThreadSummary {
  return {
    thread: { id, title, kind, test_id: null, created_at: at },
    shown_title: title,
    kind,
    group,
    student_id: group === "Chưa rõ" || group === "Blank tests" ? null : "S-0001",
    last_activity: at, open_review_count: 0,
  };
}

describe("thread list (R15.8)", () => {
  it("a blank thread is under Blank tests, an unknown student under Chưa rõ", () => {
    const rows = [
      row("t1", "Blank test", "blank", "Blank tests", "2026-10-03T10:00:00Z"),
      row("t2", "Unknown kid", "filled", "Chưa rõ", "2026-10-03T09:00:00Z"),
      row("t3", "An's test", "filled", "Nguyễn Văn An", "2026-10-03T08:00:00Z"),
      row("t4", "New thread", "pending", "Chưa rõ", "2026-10-03T07:00:00Z"),
    ];
    render(<ThreadList threads={rows} activeId="t3" onOpen={() => {}} />);
    const groups = screen.getAllByTestId("thread-group");
    expect(groups.map((g) => g.getAttribute("data-group"))).toEqual(["Nguyễn Văn An", "Chưa rõ", "Blank tests"]);
    const ids = (g: HTMLElement) =>
      within(g).getAllByTestId("thread-item").map((b) => b.getAttribute("data-thread-id"));
    expect(ids(groups[2]!)).toEqual(["t1"]);
    expect(ids(groups[1]!)).toEqual(["t2", "t4"]);
    expect(within(groups[1]!).getByText("Chưa rõ")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "An's test" })).toHaveAttribute("aria-current", "true");
  });

  it("shows a calm empty line without threads", () => {
    render(<ThreadList threads={[]} activeId={null} onOpen={() => {}} />);
    expect(screen.getByText("No threads yet.")).toBeInTheDocument();
  });
});

// Step 22.1.1. R22.1.1.6: the list shows each thread's shown_title (the sidecar makes it: the
// teacher's title, or the student and the test while the title is "New thread"). R22.1.1.5: the
// rename opens from a right-click and from the row's menu button; Enter saves, Escape cancels.
describe("thread titles and rename (R22.1.1.5, R22.1.1.6)", () => {
  const TEST = "Grade 8 · FinalTerm HK1 · Test 1";
  function titled(id: string, title: string, shown: string, group = "Nguyễn Văn An"): ThreadSummary {
    return { ...row(id, title, "filled", group, "2026-10-03T08:00:00Z"), shown_title: shown };
  }

  it("shows the shown title: student and test, the test alone, or the teacher's title", () => {
    render(
      <ThreadList
        threads={[
          titled("t1", "New thread", `${TEST} · Nguyễn Văn An`),
          titled("t2", "New thread", TEST, "Chưa rõ"),
          titled("t3", "Ánh's mid-term", "Ánh's mid-term"),
        ]}
        activeId={null}
        onOpen={() => {}}
      />,
    );
    const names = screen.getAllByTestId("thread-item").map((b) => b.textContent);
    expect(names).toEqual([`${TEST} · Nguyễn Văn An`, "Ánh's mid-term", TEST]);
  });

  function setup() {
    const onRename = vi.fn(async () => {});
    const onOpen = vi.fn();
    render(
      <ThreadList threads={[titled("t1", "New thread", `${TEST} · Nguyễn Văn An`)]} activeId={null} onOpen={onOpen} onRename={onRename} />,
    );
    return { onRename, onOpen };
  }

  it("the menu button opens a menu with Rename; Enter saves the new title", async () => {
    const { onRename, onOpen } = setup();
    const button = screen.getByRole("button", { name: `More actions for ${TEST} · Nguyễn Văn An` });
    expect(button).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    const item = within(screen.getByRole("menu")).getByRole("menuitem", { name: "Rename" });
    expect(item).toHaveFocus();
    fireEvent.click(item);
    const input = screen.getByRole("textbox", { name: "Thread name" });
    expect(input).toHaveValue(`${TEST} · Nguyễn Văn An`);
    fireEvent.change(input, { target: { value: "  An   – mid-term  " } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(onRename).toHaveBeenCalledWith("t1", "An – mid-term"));
    expect(onRename).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("textbox", { name: "Thread name" })).toBeNull();
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("the menu closes when focus moves outside it, e.g. by Tab (R22.1.4.5)", () => {
    setup();
    fireEvent.contextMenu(screen.getByTestId("thread-item"));
    expect(screen.getByRole("menuitem", { name: "Rename" })).toHaveFocus();
    const outside = document.createElement("button");
    document.body.append(outside);
    try {
      act(() => outside.focus());
      expect(screen.queryByRole("menu")).toBeNull();
      expect(outside).toHaveFocus();
    } finally {
      outside.remove();
    }
  });

  it("right-click opens the same menu", () => {
    setup();
    fireEvent.contextMenu(screen.getByTestId("thread-item"));
    fireEvent.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Rename" }));
    expect(screen.getByRole("textbox", { name: "Thread name" })).toBeInTheDocument();
  });

  it("Escape cancels the rename and does not reach the global shortcuts", () => {
    const { onRename } = setup();
    fireEvent.contextMenu(screen.getByTestId("thread-item"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
    const input = screen.getByRole("textbox", { name: "Thread name" });
    fireEvent.change(input, { target: { value: "Something else" } });
    const onWindowKey = vi.fn();
    window.addEventListener("keydown", onWindowKey);
    fireEvent.keyDown(input, { key: "Escape" });
    window.removeEventListener("keydown", onWindowKey);
    expect(onWindowKey).not.toHaveBeenCalled();
    expect(screen.queryByRole("textbox", { name: "Thread name" })).toBeNull();
    expect(onRename).not.toHaveBeenCalled();
    expect(screen.getByTestId("thread-item")).toHaveTextContent(`${TEST} · Nguyễn Văn An`);
  });

  it("an unchanged or blank name saves nothing", () => {
    const { onRename } = setup();
    for (const value of [`${TEST} · Nguyễn Văn An`, "   "]) {
      fireEvent.click(screen.getByTestId("thread-menu-button"));
      fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
      const input = screen.getByRole("textbox", { name: "Thread name" });
      fireEvent.change(input, { target: { value } });
      fireEvent.keyDown(input, { key: "Enter" });
    }
    expect(onRename).not.toHaveBeenCalled();
  });

  it("the menu closes on Escape and on a click outside", () => {
    setup();
    const button = screen.getByTestId("thread-menu-button");
    fireEvent.click(button);
    fireEvent.keyDown(screen.getByRole("menuitem", { name: "Rename" }), { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(button).toHaveFocus();
    fireEvent.click(button);
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("a refused rename says so", async () => {
    const onRename = vi.fn(async () => {
      throw new Error("title must not be empty");
    });
    render(<ThreadList threads={[titled("t1", "x", "x")]} activeId={null} onOpen={() => {}} onRename={onRename} />);
    fireEvent.click(screen.getByTestId("thread-menu-button"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
    const input = screen.getByRole("textbox", { name: "Thread name" });
    fireEvent.change(input, { target: { value: "y" } });
    fireEvent.blur(input); // leaving the field saves
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not rename the thread: title must not be empty");
  });
});

describe("Use automatic name (R22.2.2.5)", () => {
  const own = (title: string, shown: string): ThreadSummary => ({ ...row("t1", title, "filled", "Nguyễn Văn An", "2026-10-01"), shown_title: shown });

  it("is in the menu while the thread has its own title and sends title null", async () => {
    const onRename = vi.fn(async () => {});
    render(<ThreadList threads={[own("Ánh's mid-term", "Ánh's mid-term")]} activeId={null} onOpen={() => {}} onRename={onRename} />);
    fireEvent.click(screen.getByTestId("thread-menu-button"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Use automatic name" }));
    await waitFor(() => expect(onRename).toHaveBeenCalledWith("t1", null));
    expect(screen.queryByTestId("thread-menu")).toBeNull();
  });

  it("is hidden while the title is already automatic", () => {
    render(<ThreadList threads={[own("New thread", "Test 1 · An")]} activeId={null} onOpen={() => {}} onRename={async () => {}} />);
    fireEvent.click(screen.getByTestId("thread-menu-button"));
    expect(screen.getByRole("menuitem", { name: "Rename" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Use automatic name" })).toBeNull();
  });

  it("shows the made title once the list reloads", () => {
    const { rerender } = render(<ThreadList threads={[own("Ánh", "Ánh")]} activeId={null} onOpen={() => {}} onRename={async () => {}} />);
    rerender(<ThreadList threads={[own("New thread", "Test 1 · An")]} activeId={null} onOpen={() => {}} onRename={async () => {}} />);
    expect(screen.getByTestId("thread-item")).toHaveTextContent("Test 1 · An");
  });
});
