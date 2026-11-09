// Step 22.4.3 (R22.4.3.1, R22.4.3.2): the Existing test, Same series as and Copy details boxes list
// recent tests on focus. Step 22.5.2 (D5) replaced the series-of-a-test picker with the Series list
// (step22_5_2.test.tsx); what stays here is that the Existing test box names tests and the two
// labels line up. Synthetic names only.
import { useState } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExistingTestSearch, STACKED_LABEL } from "@/features/photo-check/ExistingTestSearch";
import { PhotoCheckCard } from "@/features/photo-check/PhotoCheckCard";
import { type PhotoCheckDraft, type PickedTest } from "@/features/photo-check/draft";
import type { Schemas } from "@/api/client";
import { fakeApi } from "@/lib/testApi";

type Meta = { occasion: string; grade?: number; term?: number; year?: string; source?: string; school?: string };

const test = (id: string, name: string, meta: Meta, updated = "2026-10-01T00:00:00Z"): Schemas["TestSummary"] => ({
  id,
  display_name: name,
  meta: { created_by_ai: false, edited_fields: [], extra: {}, omitted_sections: [], tags: [], units: [], ...meta },
  points_possible: 10,
  attempt_count: 0,
  open_review_count: 0,
  created_at: updated,
  updated_at: updated,
});

/** Ten tests, newest first, as `GET /tests` without `q` returns them. */
const recent = Array.from({ length: 10 }, (_, i) =>
  test(`T-${String(i + 1).padStart(4, "0")}`, `Bài kiểm tra ${i + 1}`, { occasion: "MidTerm", grade: 8, school: `Trường ${i + 1}` }),
);

function Search({ api, excludeId }: { api: ReturnType<typeof fakeApi>["api"]; excludeId?: string }) {
  const [value, setValue] = useState<PickedTest | null>(null);
  return <ExistingTestSearch api={api} value={value} onChange={setValue} excludeId={excludeId} />;
}

describe("suggestions on focus (R22.4.3.1)", () => {
  it("focus lists up to 8 recent tests with one GET /tests and no typing", async () => {
    const { api, calls } = fakeApi({ "GET /tests": recent });
    render(<Search api={api} />);
    const box = screen.getByTestId("existing-test-search");
    expect(box).toHaveAttribute("role", "combobox");
    expect(box).toHaveAttribute("aria-expanded", "false");
    act(() => box.focus());
    const options = await screen.findAllByRole("option");
    expect(options).toHaveLength(8);
    expect(options[0]).toHaveTextContent("Bài kiểm tra 1");
    expect(box).toHaveAttribute("aria-expanded", "true");
    expect(box.getAttribute("aria-controls")).toBe(screen.getByRole("listbox").id);
    fireEvent.click(box); // a click on the focused box does not ask again
    const gets = calls.filter((c) => c.path === "/tests");
    expect(gets).toHaveLength(1);
    expect(gets[0]!.query.get("q")).toBeNull();
  });

  it("a click opens the list too, and the copy-details exclusion holds", async () => {
    const { api } = fakeApi({ "GET /tests": recent });
    render(<Search api={api} excludeId="T-0001" />);
    fireEvent.click(screen.getByTestId("existing-test-search"));
    const options = await screen.findAllByRole("option");
    expect(options[0]).toHaveTextContent("Bài kiểm tra 2");
    expect(options.some((o) => o.textContent?.includes("T-0001"))).toBe(false);
  });

  it("typing filters through ?q=", async () => {
    const { api, calls } = fakeApi({
      "GET /tests": (call: { query: URLSearchParams }) => (call.query.get("q") ? [recent[4]] : recent),
    });
    render(<Search api={api} />);
    const box = screen.getByTestId("existing-test-search");
    act(() => box.focus());
    await screen.findAllByRole("option");
    fireEvent.change(box, { target: { value: "kiểm tra 5" } });
    await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(1));
    expect(calls.some((c) => c.path === "/tests" && c.query.get("q") === "kiểm tra 5")).toBe(true);
  });

  it("↓/↑ move the highlight, Enter picks and closes, Esc closes and then goes to the caller", async () => {
    const { api } = fakeApi({ "GET /tests": recent });
    const outer = vi.fn();
    render(
      <div onKeyDown={(e) => e.key === "Escape" && outer()}>
        <Search api={api} />
      </div>,
    );
    const box = screen.getByTestId("existing-test-search");
    act(() => box.focus());
    await screen.findAllByRole("option");
    fireEvent.keyDown(box, { key: "Escape" });
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(outer).not.toHaveBeenCalled();
    fireEvent.keyDown(box, { key: "Escape" });
    expect(outer).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(box, { key: "ArrowDown" }); // reopens
    await screen.findAllByRole("option");
    fireEvent.keyDown(box, { key: "ArrowDown" });
    fireEvent.keyDown(box, { key: "ArrowDown" });
    fireEvent.keyDown(box, { key: "ArrowUp" });
    const second = screen.getAllByRole("option")[0]!;
    expect(second).toHaveAttribute("aria-selected", "true");
    expect(box).toHaveAttribute("aria-activedescendant", second.id);
    fireEvent.keyDown(box, { key: "Enter" });
    expect(screen.getByTestId("existing-test-picked")).toHaveTextContent("Bài kiểm tra 1");
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("the list closes on leaving the box", async () => {
    const { api } = fakeApi({ "GET /tests": recent });
    render(<Search api={api} />);
    const box = screen.getByTestId("existing-test-search");
    act(() => box.focus());
    await screen.findAllByRole("option");
    act(() => box.blur());
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(box).toHaveAttribute("aria-expanded", "false");
  });
});

describe("the photo check's two boxes (R22.4.3.2, R22.4.8.2)", () => {
  const rows = [
    test("T-0009", "Grade 9 - Entrance Exam - Đề dự đoán tuyển sinh vào 10 - 2025–2026 - Test 3", { occasion: "EntranceExam", grade: 9, year: "2025-2026", source: "Đề dự đoán tuyển sinh vào 10" }),
    test("T-0007", "Grade 8 - Mid-term 1 - Trường B - 2025–2026", { occasion: "MidTerm", grade: 8, term: 1, year: "2025-2026", school: "Trường B" }),
  ];

  const start: PhotoCheckDraft = { pages: [{ file_id: "fa", rotation: 0, is_key: false, text_file_id: null }], existingTest: null };
  function Card({ api, onRun }: { api: ReturnType<typeof fakeApi>["api"]; onRun: (d: PhotoCheckDraft) => void }) {
    const [draft, setDraft] = useState(start);
    return <PhotoCheckCard api={api} draft={draft} onChange={setDraft} onAddFiles={() => {}} onRun={() => onRun(draft)} />;
  }

  it("the Existing test box still names tests in full", async () => {
    const { api } = fakeApi({ "GET /tests": rows });
    render(<Card api={api} onRun={() => {}} />);
    act(() => screen.getByTestId("existing-test-search").focus());
    const options = await within(screen.getByTestId("existing-test")).findAllByRole("option");
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveTextContent(rows[0]!.display_name);
  });

  it("the two labels share one width, so both boxes start at the same x (R22.4.8.2)", () => {
    const { api } = fakeApi({ "GET /tests": rows });
    render(<Card api={api} onRun={() => {}} />);
    const a = screen.getByTestId("existing-test-label");
    const b = screen.getByTestId("series-test-label");
    for (const cls of STACKED_LABEL.split(" ")) {
      expect(a).toHaveClass(cls);
      expect(b).toHaveClass(cls);
    }
  });
});
