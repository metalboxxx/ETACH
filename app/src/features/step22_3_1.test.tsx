// Step 22.3.1: photo check and small screen fixes (R22.3.1.1–R22.3.1.7). Synthetic data only.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { AppShell } from "@/components/AppShell";
import { DocEditor } from "@/features/panels/DocEditor";
import { FormatHelp, OCCASIONS, OCCASION_LABEL, TestPanel } from "@/features/panels/TestPanel";
import { PhotoCheckCard } from "@/features/photo-check/PhotoCheckCard";
import type { PhotoCheckDraft } from "@/features/photo-check/draft";
import type { ThreadSummary } from "@/features/threads/threads";
import { fakeApi, type FakeCall } from "@/lib/testApi";

afterEach(() => window.sessionStorage.clear());

const T0 = "2026-10-01T00:00:00Z";

function draftOf(): PhotoCheckDraft {
  return {
    pages: [
      { file_id: "fa", rotation: 90, is_key: false },
      { file_id: "fb", rotation: 0, is_key: true },
      { file_id: "fc", rotation: 0, is_key: false },
    ],
    existingTest: null,
  } as unknown as PhotoCheckDraft;
}

function PhotoCheck() {
  const [draft, setDraft] = useState(draftOf);
  const { api } = fakeApi({ "GET /tests": [] });
  return <PhotoCheckCard api={api} draft={draft} onChange={setDraft} onAddFiles={() => {}} onRun={() => {}} />;
}

describe("photo check full view (R22.3.1.1)", () => {
  it("double-click opens the photo full size with its rotation; ←/→ move; Esc closes and focus returns", async () => {
    render(<PhotoCheck />);
    const thumbs = screen.getAllByTestId("photo-thumb");
    fireEvent.doubleClick(within(thumbs[0]!).getByRole("img"));
    const dialog = screen.getByRole("dialog", { name: /Page 1 of 3/ });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    const img = within(dialog).getByTestId("photo-full-img");
    expect(img).toHaveAttribute("data-rotation", "90");
    expect(img).toHaveStyle({ transform: "rotate(90deg)" });
    expect(img.getAttribute("src")).not.toContain("thumb=1");
    expect(document.activeElement).toBe(within(dialog).getByTestId("photo-full-close"));

    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(screen.getByRole("dialog", { name: /Page 2 of 3 · Key/ })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "ArrowRight" });
    fireEvent.keyDown(window, { key: "ArrowRight" }); // stays on the last
    expect(screen.getByRole("dialog", { name: /Page 3 of 3/ })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "ArrowLeft" });
    expect(screen.getByRole("dialog", { name: /Page 2 of 3/ })).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(within(thumbs[1]!).getByTestId("photo-expand")));
  });

  it("the expand button opens it; Close closes it; Tab stays inside", async () => {
    render(<PhotoCheck />);
    const expand = within(screen.getAllByTestId("photo-thumb")[2]!).getByTestId("photo-expand");
    expect(expand).toHaveAccessibleName("Show page 3 full size");
    fireEvent.click(expand);
    const dialog = screen.getByRole("dialog", { name: /Page 3 of 3/ });
    const buttons = within(dialog).getAllByRole("button").filter((b) => !(b as HTMLButtonElement).disabled);
    const close = within(dialog).getByTestId("photo-full-close");
    expect(buttons[buttons.length - 1]).toBe(close);
    close.focus();
    fireEvent.keyDown(window, { key: "Tab" });
    expect(document.activeElement).toBe(buttons[0]);
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(close);
    fireEvent.click(close);
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(expand));
  });
});

describe("photo check hint and rotate (R22.3.1.2)", () => {
  it("shows the key-page hint; rotate is named “Rotate page N 90°” with the tooltip “Rotate 90°” with a quarter-turn icon", () => {
    render(<PhotoCheck />);
    expect(screen.getByTestId("key-hint")).toHaveTextContent("Mark each page of the key with 🔑 Key.");
    const rotate = [1, 2, 3].map((n) => screen.getByRole("button", { name: `Rotate page ${n} 90°` }));
    expect(rotate).toHaveLength(3);
    expect(rotate[0]).toHaveAttribute("title", "Rotate 90°");
    expect(rotate[0]!.textContent).not.toMatch(/[⟳↻🔄]/u);
    expect(within(rotate[0]!).getByTestId("rotate-quarter-icon")).toBeInTheDocument();
    fireEvent.click(rotate[0]!);
    expect(screen.getAllByTestId("photo-thumb")[0]).toHaveAttribute("data-rotation", "180");
  });
});

describe("one page with its line numbers (R22.3.1.3)", () => {
  it("the gutter sits inside the page's border and background; no second box", () => {
    render(<DocEditor value={"I. [2 points]\n1. Stem"} onChange={() => {}} onSave={() => {}} marks={new Map()} label="Test text" />);
    const page = screen.getByTestId("doc-editor");
    expect(page.className).toMatch(/\bborder\b/);
    expect(page.className).toMatch(/\bbg-surface\b/);
    const gutter = screen.getByTestId("doc-gutter");
    expect(page.contains(gutter)).toBe(true);
    expect(gutter.className).not.toMatch(/\bborder\b|\bbg-/);
    expect(screen.getByTestId("doc-page-text").className).not.toMatch(/\bborder\b|\bbg-/);
  });
});

describe("Format help (R22.3.1.4)", () => {
  it("the intro line is gone from the source", () => {
    const src = readFileSync(path.join(__dirname, "panels", "TestPanel.tsx"), "utf8");
    expect(src).not.toContain("Edit the test like a document");
  });

  it("aria-expanded, a chevron that turns, and a transition that is off with reduced motion", async () => {
    render(<FormatHelp />);
    const button = screen.getByTestId("format-help");
    const chevron = screen.getByTestId("format-help-chevron");
    const region = screen.getByTestId("format-help-region");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(chevron.getAttribute("class")).toContain("rotate-0");
    expect(chevron.getAttribute("class")).toContain("motion-reduce:transition-none");
    expect(region.className).toContain("transition-");
    expect(region.className).toContain("motion-reduce:transition-none");
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(chevron.getAttribute("class")).toContain("rotate-180");
    expect(region).toBeVisible();
    expect(region.className).toContain("grid-rows-[1fr]");
    fireEvent.click(button);
    expect(region.className).toContain("grid-rows-[0fr]");
    await waitFor(() => expect(region).not.toBeVisible());
  });

  it("the test page has no intro line", async () => {
    const { api } = fakeApi({ "GET /tests/{id}": testOf({ occasion: "MidTerm", grade: 8, edited_fields: [] }) });
    render(<TestPanel api={api} testId="T-0001" />);
    await screen.findByTestId("format-help");
    expect(document.body.textContent).not.toContain("Edit the test like a document");
  });
});

function testOf(meta: Record<string, unknown>) {
  return { id: "T-0001", meta, content: { sections: [] }, content_text: "", picture_paths: {}, review: [] };
}

/** The sidecar's PATCH, as far as these tests need: a typed name lives in `extra.display_name`. */
function patchMeta(stored: ReturnType<typeof testOf>, call: FakeCall) {
  const meta = stored.meta as { extra?: Record<string, unknown>; edited_fields: string[] } & Record<string, unknown>;
  for (const [k, v] of Object.entries((call.body as { meta: Record<string, unknown> }).meta)) {
    if (k === "display_name") {
      meta.extra = { ...(meta.extra ?? {}), display_name: v };
      meta.edited_fields = v === null ? meta.edited_fields.filter((f) => f !== k) : [...meta.edited_fields, k];
    } else meta[k] = v;
  }
  return { ...stored, meta: { ...meta } };
}

function metaApi(meta: Record<string, unknown>) {
  const stored = testOf({ ...meta });
  return fakeApi({
    "GET /tests/{id}": () => stored,
    "PATCH /tests/{id}": (call: FakeCall) => patchMeta(stored, call),
  });
}

const chip = (field: string) => screen.getAllByTestId("meta-chip").find((c) => c.dataset.field === field)!;

describe("the Occasion list (R22.3.1.5)", () => {
  it("lists all ten on opening, filters as the teacher types, and ↓/↑/Enter pick", async () => {
    const { api, calls } = metaApi({ occasion: "MidTerm", grade: 8, edited_fields: [] });
    render(<TestPanel api={api} testId="T-0001" />);
    await waitFor(() => expect(chip("occasion")).toHaveTextContent("Mid-term test"));
    fireEvent.click(chip("occasion"));
    const input = screen.getByTestId("meta-chip-input");
    expect(input).toHaveAttribute("role", "combobox");
    expect(input).toHaveAttribute("aria-expanded", "true");
    const all = within(screen.getByRole("listbox", { name: "Occasions" })).getAllByRole("option");
    expect(all.map((o) => o.textContent)).toEqual(OCCASIONS.map((o) => OCCASION_LABEL[o]));
    expect(all).toHaveLength(10);

    fireEvent.change(input, { target: { value: "na" } });
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["National exam"]);
    fireEvent.change(input, { target: { value: "exam" } });
    const exams = screen.getAllByRole("option").map((o) => o.textContent);
    expect(exams).toEqual(["National exam", "Entrance exam", "Gifted students' exam"]);

    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowUp" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true");
    expect(input).toHaveAttribute("aria-activedescendant", screen.getAllByRole("option")[1]!.id);
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(chip("occasion")).toHaveTextContent("Entrance exam"));
    expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ meta: { occasion: "EntranceExam" } });
  });

  it("a click on an option saves it", async () => {
    const { api, calls } = metaApi({ occasion: "MidTerm", grade: 8, edited_fields: [] });
    render(<TestPanel api={api} testId="T-0001" />);
    await waitFor(() => expect(chip("occasion")).toBeInTheDocument());
    fireEvent.click(chip("occasion"));
    fireEvent.click(screen.getByRole("option", { name: "National exam" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ meta: { occasion: "NationalExam" } });
  });
});

describe("focus after a chip edit (R22.3.1.7, step 22.2 F7)", () => {
  it("Enter and Escape in a detail chip put focus back on that chip", async () => {
    const { api } = metaApi({ occasion: "MidTerm", grade: 8, edited_fields: [] });
    render(<TestPanel api={api} testId="T-0001" />);
    await waitFor(() => expect(chip("grade")).toBeInTheDocument());
    fireEvent.click(chip("grade"));
    fireEvent.keyDown(screen.getByTestId("meta-chip-input"), { key: "Escape" });
    await waitFor(() => expect(document.activeElement).toBe(chip("grade")));
    fireEvent.click(chip("occasion"));
    const input = screen.getByTestId("meta-chip-input");
    fireEvent.change(input, { target: { value: "Unit test" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(chip("occasion")).toHaveTextContent("Unit test"));
    expect(document.activeElement).toBe(chip("occasion"));
  });

  it("after “Use automatic name”, focus is on the Test name chip", async () => {
    const { api } = metaApi({ occasion: "MidTerm", grade: 8, edited_fields: [], extra: {} });
    render(<TestPanel api={api} testId="T-0001" />);
    const nameChip = await screen.findByTestId("test-name-chip");
    fireEvent.click(nameChip);
    const input = screen.getByTestId("test-name-chip-input");
    fireEvent.change(input, { target: { value: "Typed name" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(screen.getByTestId("test-name-chip")).toHaveTextContent("Typed name"));
    expect(document.activeElement).toBe(screen.getByTestId("test-name-chip"));
    const auto = await screen.findByTestId("test-name-auto");
    auto.focus();
    await act(async () => {
      fireEvent.click(auto);
    });
    await waitFor(() => expect(screen.queryByTestId("test-name-auto")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId("test-name-chip")));
  });
});

function summary(id: string, title: string): ThreadSummary {
  return {
    thread: { id, title: "New thread", test_id: "T-0001", kind: "blank", created_at: T0 },
    shown_title: title,
    kind: "blank",
    group: "Blank tests",
    student_id: null,
    last_activity: T0,
    open_review_count: 0,
  } as ThreadSummary;
}

describe("a saved Test name shows at once (R22.3.1.6)", () => {
  it("the sidebar row and the thread header update without a reload", async () => {
    window.sessionStorage.setItem("etach.activeThread", JSON.stringify("t1"));
    let name = "Grade 8 - Mid-term test";
    const stored = testOf({ occasion: "MidTerm", grade: 8, edited_fields: [] });
    const { api } = fakeApi({
      "GET /threads": () => [summary("t1", name)],
      "GET /threads/{id}": () => ({ thread: summary("t1", name).thread, shown_title: name, test: stored, attempt: null }),
      "GET /threads/{id}/messages": [],
      "GET /tests": [],
      "GET /tests/{id}": () => stored,
      "PATCH /tests/{id}": (call: FakeCall) => {
        name = String(Object.values((call.body as { meta: Record<string, unknown> }).meta)[0]);
        return patchMeta(stored, call);
      },
    });
    function Shell() {
      const [threads, setThreads] = useState<ThreadSummary[]>([summary("t1", name)]);
      return (
        <AppShell
          connection="open"
          api={api}
          threads={threads}
          onThreadsChanged={() => void api.get("/threads").then((rows) => setThreads(rows as ThreadSummary[]))}
          initialPanel={{ kind: "test", testId: "T-0001" }}
        />
      );
    }
    render(<Shell />);
    await waitFor(() => expect(screen.getByTestId("thread-title")).toHaveTextContent("Grade 8 - Mid-term test"));
    const nameChip = await screen.findByTestId("test-name-chip");
    fireEvent.click(nameChip);
    const input = screen.getByTestId("test-name-chip-input");
    fireEvent.change(input, { target: { value: "National test 5" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(screen.getByTestId("test-name-chip")).toHaveTextContent("National test 5"));
    await waitFor(() => expect(screen.getByTestId("thread-list")).toHaveTextContent("National test 5"));
    await waitFor(() => expect(screen.getByTestId("thread-title")).toHaveTextContent("National test 5"));
  });
});
