// Step 22.5.2 (b, UI), teacher's comments 2, 3, 5 and 7; decisions D5, D7, D8. Synthetic names only.
// R22.5.2.7: Settings shows General · Models · Test attributes; Test attributes → Series → Back
//   returns to the menu; keyboard and screen-reader names (contrast: the E2E screenshots).
// R22.5.2.8: the Series field and "Same series as" offer only names from the Series list; a pick in
//   "Same series as" sends `series_name`.
// R22.5.2.9: the line under the title reads "10 points · 0.25 each" (40 graded questions) and
//   "10 points · 0.2 each" (50); no heading in the editor, the print view or Format help shows points.
// R22.5.2.10: Extract again offers update / copy only when other threads use the test, and sends the
//   chosen `mode`.
import { useState } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiClient } from "@/api/client";
import { EventsProvider, type EventStream } from "@/api/sse";
import { ConfirmProvider } from "@/components/ConfirmDialog";
import { KEPT, ThreadTabActions } from "@/features/panel/ThreadActions";
import { CleanTest, LINE_FORMS, TestPanel, headingText, mapText } from "@/features/panels/TestPanel";
import { PhotoCheckCard } from "@/features/photo-check/PhotoCheckCard";
import { toExtractInput, type PhotoCheckDraft } from "@/features/photo-check/draft";
import { resetSettingsTab, SettingsPanel } from "@/features/settings/SettingsPanel";
import { SeriesList } from "@/features/settings/SeriesList";
import { resetOccasions } from "@/lib/occasions";
import { resetSchools } from "@/lib/schools";
import { resetSeries } from "@/lib/series";
import { fakeApi, FakeStatus, type FakeCall } from "@/lib/testApi";
import { num, testDetailsLine } from "@/lib/testTitle";

afterEach(() => {
  resetSettingsTab();
  resetOccasions();
  resetSchools();
  resetSeries();
  window.sessionStorage.clear();
});

const SERIES = [
  { id: 1, name: "Đề dự đoán tuyển sinh vào 10", position: 0, test_count: 2 },
  { id: 2, name: "Bộ đề luyện thi thử", position: 1, test_count: 0 },
];

const stream: EventStream = {
  start: () => {},
  close: () => {},
  subscribe: () => () => {},
  onStatus: () => () => {},
  status: "open",
  lastEventId: null,
};

const settingsRoutes = {
  "GET /settings": { data_folder: "D:\\ETACH\\data", log_retention_days: 45, roles: {} },
  "GET /models": { models: [], roles: {}, suggested: [] },
  "GET /occasions": [],
  "GET /schools": [{ id: 1, name: "THCS Thử Nghiệm", position: 0, test_count: 0, student_count: 0 }],
  "GET /series": SERIES,
};

function openSettings(api: ApiClient) {
  return render(
    <EventsProvider stream={stream}>
      <ConfirmProvider>
        <SettingsPanel api={api} status={null} />
      </ConfirmProvider>
    </EventsProvider>,
  );
}

describe("Settings → Test attributes (R22.5.2.7)", () => {
  it("has three tabs; the menu lists Occasions, Schools and Series as named buttons", async () => {
    const { api } = fakeApi(settingsRoutes);
    openSettings(api);
    const tabs = await screen.findByRole("tablist", { name: "Settings" });
    expect(within(tabs).getAllByRole("tab").map((t) => t.textContent)).toEqual(["General", "Models", "Test attributes"]);
    fireEvent.click(within(tabs).getByRole("tab", { name: "Test attributes" }));
    const menu = screen.getByRole("list", { name: "Test attributes" });
    const items = within(menu).getAllByRole("button");
    expect(items.map((b) => b.dataset.list)).toEqual(["occasions", "schools", "series"]);
    // each button is named by its list and described by one plain line
    const series = within(menu).getByRole("button", { name: "Series" });
    expect(series).toHaveAccessibleDescription(/belong together/);
    // the lists are hidden until chosen
    expect(screen.getByTestId("settings-series")).not.toBeVisible();
  });

  it("Series opens in place (heading focused); Back returns to the menu, focus on Series", async () => {
    const { api } = fakeApi(settingsRoutes);
    openSettings(api);
    fireEvent.click(within(await screen.findByRole("tablist", { name: "Settings" })).getByRole("tab", { name: "Test attributes" }));
    // two clicks: the tab, then the list
    fireEvent.click(screen.getByRole("button", { name: "Series" }));
    const section = screen.getByTestId("settings-series");
    expect(section).toBeVisible();
    expect(screen.getByTestId("attributes-menu")).not.toBeVisible();
    expect(section).toHaveAccessibleName("Series");
    await waitFor(() => expect(within(section).getByRole("heading", { name: "Series" })).toHaveFocus());
    await waitFor(() => expect(within(section).getAllByTestId("series-name").map((n) => n.textContent)).toEqual(SERIES.map((s) => s.name)));
    const back = within(section).getByRole("button", { name: "Back to Test attributes" });
    expect(back).toHaveTextContent("Test attributes");
    fireEvent.click(back);
    expect(screen.getByTestId("attributes-menu")).toBeVisible();
    expect(section).not.toBeVisible();
    await waitFor(() => expect(screen.getByRole("button", { name: "Series" })).toHaveFocus());
  });

  it("Schools and Occasions open the same way", async () => {
    const { api } = fakeApi(settingsRoutes);
    openSettings(api);
    fireEvent.click(within(await screen.findByRole("tablist", { name: "Settings" })).getByRole("tab", { name: "Test attributes" }));
    fireEvent.click(screen.getByRole("button", { name: "Schools" }));
    expect(screen.getByTestId("settings-schools")).toBeVisible();
    await waitFor(() => expect(screen.getByTestId("school-name")).toHaveTextContent("THCS Thử Nghiệm"));
    fireEvent.click(within(screen.getByTestId("settings-schools")).getByRole("button", { name: "Back to Test attributes" }));
    fireEvent.click(screen.getByRole("button", { name: "Occasions" }));
    expect(screen.getByTestId("settings-occasions")).toBeVisible();
    expect(screen.getByTestId("settings-schools")).not.toBeVisible();
  });
});

describe("the Series list (D5)", () => {
  function renderList(routes: Record<string, unknown>) {
    const fake = fakeApi({ "GET /series": SERIES, ...routes });
    render(
      <ConfirmProvider>
        <SeriesList api={fake.api} />
      </ConfirmProvider>,
    );
    return fake;
  }

  it("adds, renames and moves a series", async () => {
    const fake = renderList({
      "POST /series": (c: FakeCall) => ({ id: 3, name: (c.body as { name: string }).name, position: 2, test_count: 0 }),
      "PATCH /series/{id}": { id: 2, name: "x", position: 0, test_count: 0 },
    });
    await screen.findAllByTestId("series-row");
    fireEvent.change(screen.getByTestId("series-new-name"), { target: { value: "  Bộ đề mới  " } });
    fireEvent.click(screen.getByRole("button", { name: "Add series" }));
    await waitFor(() => expect(fake.calls.find((c) => c.method === "POST")?.body).toEqual({ name: "Bộ đề mới" }));

    fireEvent.click(await screen.findByRole("button", { name: "Rename Bộ đề luyện thi thử" }));
    fireEvent.change(screen.getByRole("textbox", { name: "New name for Bộ đề luyện thi thử" }), { target: { value: "Bộ đề A" } });
    fireEvent.click(screen.getByTestId("series-save"));
    await waitFor(() =>
      expect(fake.calls.find((c) => c.method === "PATCH" && c.path === "/series/2")?.body).toEqual({ name: "Bộ đề A" }),
    );

    await waitFor(() => expect(screen.getByRole("button", { name: "Move Bộ đề luyện thi thử up" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Move Bộ đề luyện thi thử up" }));
    await waitFor(() =>
      expect(fake.calls.filter((c) => c.method === "PATCH" && c.path === "/series/2").at(-1)?.body).toEqual({ position: 0 }),
    );
  });

  it("a used series cannot be deleted and says why; an unused one asks first", async () => {
    const fake = renderList({ "DELETE /series/{id}": null });
    const used = await screen.findByRole("button", { name: "Delete Đề dự đoán tuyển sinh vào 10" });
    expect(used).toBeDisabled();
    expect(used).toHaveAccessibleDescription("Used by 2 tests: change their series first");
    fireEvent.click(screen.getByRole("button", { name: "Delete Bộ đề luyện thi thử" }));
    const dialog = await screen.findByTestId("confirm-dialog");
    expect(dialog).toHaveTextContent("Delete Bộ đề luyện thi thử?");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete series" }));
    await waitFor(() => expect(fake.calls.some((c) => c.method === "DELETE" && c.path === "/series/2")).toBe(true));
  });

  it("shows the sidecar's words when it refuses a delete (409)", async () => {
    renderList({ "DELETE /series/{id}": new FakeStatus(409, { detail: "1 test(s) use this series." }) });
    fireEvent.click(await screen.findByRole("button", { name: "Delete Bộ đề luyện thi thử" }));
    fireEvent.click(within(await screen.findByTestId("confirm-dialog")).getByRole("button", { name: "Delete series" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("1 test(s) use this series.");
  });
});

// --- the test page ---------------------------------------------------------------------------

/** A test with `n` graded questions in one section and a writing section. */
function makeTest(n: number, pointsEach: number) {
  const q = (i: number) => ({
    id: `q-${i}`,
    number: i,
    printed_number: i,
    page_no: 1,
    answer_form: "sentence", context: "single",
    stem: `Stem ${i}`,
    options: null,
    cue: null,
    points: pointsEach,
  });
  return {
    id: "T-0001",
    meta: { occasion: "FinalTerm", grade: 9, term: 2, source: SERIES[0]!.name, edited_fields: [] },
    content: {
      sections: [
        { id: "s1", number: 1, printed_title: "II. WORD FORM", title: "WORD FORM", instructions: null, points: 10, points_source: "computed", skill: "word_form", graded: true, groups: [{ id: "g1", stimulus: null, pictures: [], questions: Array.from({ length: n }, (_, i) => q(i + 1)) }] },
        { id: "s2", number: 2, printed_title: "VI. WRITING", title: "WRITING", instructions: null, points: 0, points_source: "computed", skill: "writing", graded: false, groups: [{ id: "g2", stimulus: null, pictures: [], questions: [] }] },
      ],
    },
    content_text: ["# II. WORD FORM", ...Array.from({ length: n }, (_, i) => `${i + 1}. Stem ${i + 1}`), "", "# VI. WRITING  [not graded]"].join("\n"),
    content_schema_version: 1,
    fingerprint: "f",
    points_possible: 10,
    points_each: pointsEach,
    source_run_id: "R1",
    merged_into: null,
    created_at: "2026-10-04T00:00:00Z",
    updated_at: "2026-10-04T00:00:00Z",
    picture_paths: {},
    review: [],
  };
}

describe("the points line and headings (R22.5.2.9)", () => {
  it("reads at most 2 decimals with trailing zeros dropped", () => {
    expect(testDetailsLine({ occasion: "FinalTerm" }, 10, 10 / 40)).toBe("10 points · 0.25 each");
    expect(testDetailsLine({ occasion: "FinalTerm" }, 10, 10 / 50)).toBe("10 points · 0.2 each");
    expect(testDetailsLine({ occasion: "FinalTerm" }, 10, 10 / 45)).toBe("10 points · 0.22 each");
    expect(testDetailsLine({ occasion: "FinalTerm", duration_minutes: 45 }, 10, 1)).toBe("45 minutes · 10 points · 1 each");
    expect(testDetailsLine({ occasion: "FinalTerm" }, 0, null)).toBe("0 points"); // no graded questions
    // as the sidecar's round(): an exact half goes to the even neighbour, so the Word file agrees
    expect(num(10 / 80)).toBe("0.12");
  });

  it.each([
    [40, "10 points · 0.25 each"],
    [50, "10 points · 0.2 each"],
  ])("%i graded questions: the line under the title reads %s, in the editor and the print view", async (n, line) => {
    const { api } = fakeApi({ "GET /tests/{id}": makeTest(n, 10 / n) });
    const { rerender } = render(<TestPanel api={api} testId="T-0001" />);
    expect(await screen.findByTestId("test-title-details")).toHaveTextContent(line);
    // the editor's text: # headings, no points
    const text = (screen.getByTestId("test-text") as HTMLTextAreaElement).value;
    expect(text).toContain("# II. WORD FORM");
    expect(text).not.toMatch(/points?\b/i);
    rerender(<TestPanel api={api} testId="T-0001" printing />);
    const clean = screen.getByTestId("clean-test");
    expect(within(clean).getByTestId("test-title-details")).toHaveTextContent(line);
    const headings = within(clean).getAllByTestId("test-section-heading").map((h) => h.textContent);
    expect(headings).toEqual(["II. WORD FORM", "VI. WRITING  [not graded]"]);
    for (const h of headings) expect(h).not.toMatch(/point/i);
  });

  it("Format help's heading form has no points", () => {
    const heading = LINE_FORMS.find((f) => f.form === "Section heading")!;
    expect(heading.example).toBe("# II. WORD FORM");
    expect(heading.example).not.toMatch(/point/i);
    expect(heading.meaning).toContain("[not graded]");
  });

  it("the notes find # headings, and the old points brackets still", () => {
    const map = mapText(["# I. PRONUNCIATION", "1. a", "#", "2. b", "III.  [2.5 points, 0.25 each]", "3. c", "\\# not a heading"].join("\n"));
    expect(map.headings).toEqual([1, 3, 5]);
    expect([...map.questions.keys()]).toEqual([1, 2, 3]);
    expect(headingText({ printed_title: "", title: "WRITING", graded: false })).toBe("WRITING  [not graded]");
  });

  it("CleanTest without points_each shows the points alone", () => {
    const t = makeTest(4, 2.5);
    render(<CleanTest test={{ ...t, points_each: undefined } as never} />);
    expect(screen.getByTestId("test-title-details")).toHaveTextContent(/^10 points$/);
  });
});

describe("the Series field and Same series as (R22.5.2.8)", () => {
  it("the Series chip lists the Series list's names, and only those", async () => {
    const { api } = fakeApi({ "GET /tests/{id}": makeTest(4, 2.5), "GET /series": SERIES, "GET /schools": [{ id: 9, name: "THCS Thử Nghiệm", position: 0, test_count: 1, student_count: 0 }] });
    render(<TestPanel api={api} testId="T-0001" />);
    const chip = await screen.findByRole("button", { name: /^Series:/ });
    fireEvent.click(chip);
    const box = screen.getByRole("combobox", { name: "Series" });
    expect(box).toHaveAttribute("placeholder", "Pick one or type a new series");
    const list = await screen.findByRole("listbox", { name: "Series" });
    await waitFor(() => expect(within(list).getAllByRole("option").map((o) => o.textContent)).toEqual(SERIES.map((s) => s.name)));
    fireEvent.change(box, { target: { value: "luyện" } });
    expect(within(list).getAllByRole("option").map((o) => o.textContent)).toEqual(["Bộ đề luyện thi thử"]);
  });

  const start: PhotoCheckDraft = { pages: [{ file_id: "fa", rotation: 0, is_key: false, text_file_id: null }], existingTest: null };
  function Card({ api, onRun }: { api: ApiClient; onRun: (d: PhotoCheckDraft) => void }) {
    const [draft, setDraft] = useState(start);
    return <PhotoCheckCard api={api} draft={draft} onChange={setDraft} onAddFiles={() => {}} onRun={() => onRun(draft)} />;
  }

  it("focus lists every series name at once (no test names); a pick sends series_name", async () => {
    const tests = [{ id: "T-0005", display_name: "Grade 8 - Mid-term 1 - THCS Thử Nghiệm", meta: { occasion: "MidTerm", school: "THCS Thử Nghiệm", edited_fields: [] }, points_possible: 10, attempt_count: 0, open_review_count: 0, updated_at: "" }];
    const { api, calls } = fakeApi({ "GET /series": SERIES, "GET /tests": tests });
    const onRun = vi.fn();
    render(<Card api={api} onRun={onRun} />);
    const box = screen.getByRole("combobox", { name: "Same series as" });
    act(() => box.focus());
    const list = await screen.findByRole("listbox", { name: "Series" });
    expect(within(list).getAllByRole("option").map((o) => o.textContent)).toEqual(SERIES.map((s) => s.name));
    expect(calls.some((c) => c.path === "/tests")).toBe(false); // it does not search the test bank
    // ↓ Enter picks the first
    fireEvent.keyDown(box, { key: "ArrowDown" });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(screen.getByTestId("series-test-picked")).toHaveTextContent(SERIES[0]!.name);
    fireEvent.click(screen.getByTestId("photo-run"));
    const input = toExtractInput(onRun.mock.calls[0]![0] as PhotoCheckDraft);
    expect(input).toMatchObject({ existing_test_id: null, series_name: SERIES[0]!.name });
    expect(input).not.toHaveProperty("series_from_test_id");
    // ✕ clears it
    fireEvent.click(screen.getByRole("button", { name: "Clear same series as" }));
    expect(screen.getByRole("combobox", { name: "Same series as" })).toBeInTheDocument();
  });

  it("typing filters the names; a name not in the list cannot be picked", async () => {
    const { api } = fakeApi({ "GET /series": SERIES });
    const onRun = vi.fn();
    render(<Card api={api} onRun={onRun} />);
    const box = screen.getByRole("combobox", { name: "Same series as" });
    act(() => box.focus());
    await screen.findByRole("listbox", { name: "Series" });
    fireEvent.change(box, { target: { value: "TUYỂN SINH" } });
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([SERIES[0]!.name]);
    fireEvent.change(box, { target: { value: "Không có" } });
    expect(screen.queryByRole("listbox")).toBeNull();
    fireEvent.keyDown(box, { key: "Enter" });
    expect(screen.queryByTestId("series-test-picked")).toBeNull();
    fireEvent.click(screen.getByTestId("photo-run"));
    expect(toExtractInput(onRun.mock.calls[0]![0] as PhotoCheckDraft)).not.toHaveProperty("series_name");
  });
});

// --- Extract again ---------------------------------------------------------------------------

const RUN = { id: "R9", thread_id: "th1", kind: "extract", status: "queued" };

function renderActions(otherThreads: number, route: unknown = RUN, attempt: { status: string } | null = null) {
  const fake = fakeApi({ "POST /threads/{id}/extract-again": route });
  const onRunStarted = vi.fn();
  const detail = {
    thread: { id: "th1", title: "t", kind: "filled", test_id: "T-0001", created_at: "" },
    attempt: attempt && { id: "A-0001", ...attempt },
    test: { id: "T-0001" },
    student: null,
    shown_title: "t",
    other_thread_count: otherThreads,
  };
  const view = render(
    <ConfirmProvider>
      <ThreadTabActions api={fake.api} threadId="th1" detail={detail as never} busy={false} onRunStarted={onRunStarted} />
    </ConfirmProvider>,
  );
  return { ...fake, onRunStarted, unmount: view.unmount };
}

const againBodies = (calls: FakeCall[]) => calls.filter((c) => c.path === "/threads/th1/extract-again").map((c) => c.body);

describe("Extract again into the same test (R22.5.2.10)", () => {
  it("the kept line names the test's details, not the teacher's (R22.5.8.1 (1))", () => {
    expect(KEPT).toBe("Test details and keys on unchanged questions stay; edits to the test text are replaced.");
    expect(KEPT).not.toMatch(/Your details/);
  });

  it("without other threads: says the test is updated in place and sends no mode (R22.5.2.12)", async () => {
    const { calls, onRunStarted } = renderActions(0);
    fireEvent.click(screen.getByRole("button", { name: "Extract again" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Extract this test again?" });
    expect(dialog).toHaveTextContent("The photos are read again and the test is updated in place.");
    const update = within(dialog).getByRole("button", { name: "Extract again" });
    expect(update).toHaveAccessibleDescription(KEPT); // the kept / replaced line goes with Update
    expect(within(dialog).getByRole("button", { name: "Keep this one" })).toHaveFocus();
    expect(within(dialog).queryByRole("button", { name: /separate copy/ })).toBeNull();
    expect(within(dialog).queryByRole("button", { name: /every thread/ })).toBeNull();
    fireEvent.click(update);
    await waitFor(() => expect(againBodies(calls)).toEqual([{}])); // the sidecar decides the mode
    expect(againBodies(calls)[0]).not.toHaveProperty("mode");
    await waitFor(() => expect(onRunStarted).toHaveBeenCalledWith(RUN));
  });

  it("the dialog has at most three short lines of text (R22.5.2.12)", async () => {
    for (const others of [0, 2]) {
      const { unmount } = renderActions(others, RUN, { status: "graded" });
      fireEvent.click(screen.getByRole("button", { name: "Extract again" }));
      const dialog = await screen.findByRole("alertdialog");
      const lines = [...dialog.querySelectorAll("p")].map((p) => p.textContent ?? "");
      expect(lines.length).toBeLessThanOrEqual(3);
      for (const line of lines) expect(line.length).toBeLessThanOrEqual(90);
      expect(lines).toContain(KEPT);
      fireEvent.click(within(dialog).getByRole("button", { name: "Keep this one" }));
      await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
      unmount();
    }
  });

  it("with other threads: names how many, offers update or copy, and sends the choice", async () => {
    const { calls } = renderActions(2);
    fireEvent.click(screen.getByRole("button", { name: "Extract again" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Extract this test again?" });
    expect(within(dialog).getByTestId("again-others")).toHaveTextContent("2 other threads use this test.");
    expect(within(dialog).getByRole("button", { name: "Keep this one" })).toHaveFocus(); // the safe button first
    const update = within(dialog).getByRole("button", { name: "Update the test for every thread" });
    const copy = within(dialog).getByRole("button", { name: "Make a separate copy for this thread" });
    expect(update).toHaveAccessibleDescription(KEPT);
    expect(copy).not.toHaveAccessibleDescription(KEPT);
    expect(update.className).toBe(copy.className); // neither choice looks recommended
    fireEvent.click(within(dialog).getByRole("button", { name: "Make a separate copy for this thread" }));
    await waitFor(() => expect(againBodies(calls)).toEqual([{ mode: "copy" }]));
  });

  it("one other thread: singular, and Update sends replace; Keep this one sends nothing", async () => {
    const { calls } = renderActions(1);
    fireEvent.click(screen.getByRole("button", { name: "Extract again" }));
    let dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByTestId("again-others")).toHaveTextContent("1 other thread uses this test.");
    fireEvent.click(within(dialog).getByRole("button", { name: "Keep this one" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(againBodies(calls)).toEqual([]);
    fireEvent.click(screen.getByRole("button", { name: "Extract again" }));
    dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Update the test for every thread" }));
    await waitFor(() => expect(againBodies(calls)).toEqual([{ mode: "replace" }]));
  });

  it("a 409 CHOOSE_MODE (another thread joined since) shows the choice and sends it (R22.5.2.12)", async () => {
    let n = 0;
    const { calls, onRunStarted } = renderActions(0, () =>
      n++ === 0
        ? new FakeStatus(409, {
            detail: "other threads use this test; choose mode replace (update it for every thread) or copy",
          })
        : RUN,
    );
    fireEvent.click(screen.getByRole("button", { name: "Extract again" }));
    fireEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Extract again" }));
    const choice = await screen.findByRole("button", { name: "Make a separate copy for this thread" });
    expect(screen.getByTestId("again-others")).toHaveTextContent("Other threads use this test.");
    fireEvent.click(choice);
    await waitFor(() => expect(againBodies(calls)).toEqual([{}, { mode: "copy" }])); // mode only after the choice
    await waitFor(() => expect(onRunStarted).toHaveBeenCalledWith(RUN));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
