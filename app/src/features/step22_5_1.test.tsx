// Step 22.5.1, moving around and lists (comments 1, 6, 8, 9, 10; decisions D1, D3, D4).
// R22.5.1.1: a test opened from the Tests tab has no Back; its header is the tabs and a title bar
//   with its name; clicking the open thread, or another, in the sidebar shows that thread.
// R22.5.1.2: the Tests list is in Intl.Collator("vi", {numeric: true}) order by default (Grade 9
//   before Grade 10); each sort choice orders it, search results too, where a test whose id is the
//   search is the top row under every order; the choice survives switching sidebar tabs.
// R22.5.1.3: the sort button: its name, a menu of four menuitemradio, the chosen one checked, keys.
//   (Its size against the search box is measured in the headless E2E, s12-moving-around.spec.ts.)
// R22.5.1.5: the "looks like" notice names the other test and its id.
// R22.5.1.6: Edit and double-click on a Key or Student answers row select the old value.
// R22.5.1.7: every row gives its name the same width (the fixed unsure slot); the full name on hover.
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import type { Schemas } from "@/api/client";
import { AppShell } from "@/components/AppShell";
import { CardNote } from "@/features/cards/ExtractionCard";
import { AnswersPanel } from "@/features/panels/AnswersPanel";
import { KeysPanel } from "@/features/panels/KeysPanel";
import { TestsTab } from "@/features/tests-tab/TestsTab";
import { sortTests } from "@/features/tests-tab/sortTests";
import { ThreadList } from "@/features/threads/ThreadList";
import type { ThreadSummary } from "@/features/threads/threads";
import { writeSession } from "@/lib/storage";
import { fakeApi, type FakeCall } from "@/lib/testApi";

afterEach(() => window.sessionStorage.clear());

const meta = (over: Record<string, unknown> = {}) => ({
  occasion: "FinalTerm",
  created_by_ai: false,
  edited_fields: [],
  extra: {},
  omitted_sections: [],
  tags: [],
  units: [],
  ...over,
});

const summary = (
  id: string,
  name: string,
  over: { grade?: number | null; created?: string; unsure?: number } = {},
): Schemas["TestSummary"] => ({
  id,
  display_name: name,
  meta: meta({ grade: over.grade ?? null }) as Schemas["TestSummary"]["meta"],
  points_possible: 10,
  attempt_count: 0,
  open_review_count: over.unsure ?? 0,
  created_at: over.created ?? "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
});

// --- R22.5.1.1 ----------------------------------------------------------------------------------

const question = (n: number) => ({
  id: `q-${n}`,
  number: n,
  printed_number: n,
  page_no: 1,
  answer_form: "choice", context: "single",
  stem: `Stem ${n}`,
  options: [],
  cue: null,
  points: 0.25,
});
const testDetail = (id: string, over: Record<string, unknown>) => ({
  id,
  meta: meta(over),
  content: {
    sections: [
      {
        id: "s1",
        number: 1,
        printed_title: "I.",
        title: "Choose",
        instructions: null,
        points: 0.25,
        points_source: "printed",
        skill: "grammar",
        groups: [{ id: "g1", stimulus: null, pictures: [], questions: [question(1)] }],
      },
    ],
  },
  picture_paths: {},
  pages: [],
  key_pages: [],
  review: [],
  content_text: "",
  merged_into: null,
  source_run_id: "R1",
});
const TESTS: Record<string, ReturnType<typeof testDetail>> = {
  "T-0001": testDetail("T-0001", { grade: 8, term: 1, school: "THCS A" }),
  "T-0002": testDetail("T-0002", { grade: 9, term: 2, school: "Nguyễn Hữu Thọ", test_number: "G" }),
};
const thread = (id: string, testId: string | null, title: string) => ({
  thread: { id, title: "New thread", kind: testId ? ("filled" as const) : ("pending" as const), test_id: testId, created_at: "" },
  attempt: null,
  test: testId ? { id: testId } : null,
  student: null,
  test_display_name: null,
  shown_title: title,
});
const THREADS: Record<string, ReturnType<typeof thread>> = {
  thA: thread("thA", "T-0001", "Thread A"),
  thC: thread("thC", null, "Thread C"),
};
const listRow = (id: string): ThreadSummary => ({
  thread: THREADS[id]!.thread,
  shown_title: THREADS[id]!.shown_title,
  kind: THREADS[id]!.thread.kind,
  group: "Chưa rõ",
  student_id: null,
  last_activity: "",
  open_review_count: 0,
});
const lastId = (c: FakeCall) => c.path.split("/").pop()!;

function shell() {
  const fake = fakeApi({
    "GET /threads/{id}": (c: FakeCall) => THREADS[lastId(c)],
    "GET /threads/{id}/messages": [],
    "GET /tests/{id}": (c: FakeCall) => TESTS[lastId(c)],
    "GET /tests/{id}/keys": [],
    "GET /tests": [summary("T-0001", "Grade 8 - Final Term 1 - THCS A"), summary("T-0002", "Grade 9 - Final Term 2 - Nguyễn Hữu Thọ - Test G")],
    "GET /review/count": { open: 0 },
  });
  writeSession("etach.activeThread", "thA");
  render(<AppShell connection="open" api={fake.api} threads={[listRow("thA"), listRow("thC")]} />);
  return fake;
}

async function openTestB() {
  fireEvent.click(screen.getByRole("tab", { name: "Tests" }));
  const rows = await screen.findAllByTestId("test-item");
  fireEvent.click(rows.find((r) => r.dataset.testId === "T-0002")!);
  const ws = screen.getByTestId("workspace");
  await waitFor(() => expect(within(ws).getByTestId("test-bar-title")).toHaveTextContent("Grade 9 - Final Term 2 - Nguyễn Hữu Thọ - Test G"));
  return ws;
}

function threadRow(id: string) {
  return screen.getAllByTestId("thread-item").find((r) => r.dataset.threadId === id)!;
}

describe("R22.5.1.1: a test from the Tests tab has no Back; the sidebar is the way out", () => {
  it("no Back; the tabs, then a title bar with the test's name; clicking the open thread shows it", async () => {
    shell();
    const own = await screen.findByTestId("thread-title");
    expect(own).toHaveTextContent("Thread A");
    const ws = await openTestB();
    expect(within(ws).queryByTestId("workspace-back")).toBeNull();
    expect(within(ws).queryByRole("button", { name: /back/i })).toBeNull();
    expect(ws.textContent).not.toMatch(/Back to thread/);
    // The header: the tab row first, then the title bar, like the thread's own test.
    const tabs = within(ws).getByTestId("workspace-tabs");
    expect(within(tabs).getAllByRole("tab").map((t) => t.textContent)).toEqual(["Test", "Key"]);
    const bar = within(ws).getByTestId("test-title-bar");
    expect(tabs.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(bar).getByRole("heading", { level: 1 })).toHaveTextContent("Test G");
    expect(screen.queryByTestId("thread-title")).toBeNull();

    // Thread A is still the open thread: clicking it closes test B and shows A's own test.
    fireEvent.click(screen.getByRole("tab", { name: "Chats" }));
    expect(threadRow("thA")).toHaveAttribute("aria-current", "true");
    fireEvent.click(threadRow("thA"));
    await waitFor(() => expect(screen.getByTestId("thread-title")).toHaveTextContent("Thread A"));
    expect(screen.queryByTestId("test-title-bar")).toBeNull();
  });

  it("clicking another thread shows that thread", async () => {
    shell();
    await screen.findByTestId("thread-title");
    await openTestB();
    fireEvent.click(screen.getByRole("tab", { name: "Chats" }));
    fireEvent.click(threadRow("thC"));
    // Thread C has no test yet: its conversation.
    await waitFor(() => expect(screen.queryByTestId("workspace")).toBeNull());
    expect(threadRow("thC")).toHaveAttribute("aria-current", "true");
    expect(await screen.findByTestId("conversation")).toBeVisible();
  });

  it('"Back to thread" is in app/src only in tests that assert its absence', () => {
    const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
    const hits: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const full = path.join(dir, name);
        if (statSync(full).isDirectory()) walk(full);
        else if (/\.(tsx?|css)$/.test(name) && readFileSync(full, "utf8").includes("Back to thread")) hits.push(full);
      }
    };
    walk(src);
    expect(hits.map((h) => path.basename(h))).toEqual(["step22_5_1.test.tsx"]);
  });
});

// --- R22.5.1.2, R22.5.1.3 -----------------------------------------------------------------------

const MIXED = [
  summary("T-0001", "Grade 9", { grade: 9, created: "2026-10-03T00:00:00Z" }),
  summary("T-0002", "ảnh chụp", { grade: null, created: "2026-10-05T00:00:00Z" }),
  summary("T-0003", "Đề thi thử", { grade: 10, created: "2026-10-01T00:00:00Z" }),
  summary("T-0004", "Grade 10", { grade: 10, created: "2026-10-04T00:00:00Z" }),
  summary("T-0005", "Bài kiểm tra", { grade: 9, created: "2026-10-02T00:00:00Z" }),
];
const shown = () => screen.getAllByTestId("test-name").map((n) => n.textContent);
const byCollator = (names: string[]) => [...names].sort(new Intl.Collator("vi", { numeric: true }).compare);

describe("R22.5.1.2: the Tests list's order", () => {
  it("sortTests: A–Z is the vi collator's order; Z–A reverse; newest added; by grade, no grade last", () => {
    const names = MIXED.map((t) => t.display_name);
    expect(sortTests(MIXED, "az").map((t) => t.display_name)).toEqual(byCollator(names));
    expect(sortTests(MIXED, "za").map((t) => t.display_name)).toEqual(byCollator(names).reverse());
    expect(sortTests(MIXED, "newest").map((t) => t.id)).toEqual(["T-0002", "T-0004", "T-0001", "T-0005", "T-0003"]);
    // Grade 9: "Bài kiểm tra", "Grade 9"; grade 10: "Đề thi thử", "Grade 10" (A–Z); no grade last.
    expect(sortTests(MIXED, "grade").map((t) => t.display_name)).toEqual(
      [...byCollator(["Grade 9", "Bài kiểm tra"]), ...byCollator(["Đề thi thử", "Grade 10"]), "ảnh chụp"],
    );
  });

  it("with no choice made the list is A–Z (collator order), whatever order the sidecar sent", async () => {
    const { api } = fakeApi({ "GET /tests": MIXED });
    render(<TestsTab api={api} onOpen={() => {}} />);
    await screen.findAllByTestId("test-item");
    expect(shown()).toEqual(byCollator(MIXED.map((t) => t.display_name)));
    // Vietnamese collation, not code points: "ảnh" with the a's, "Đề" before "G"; and numbers by
    // value: Grade 9 before Grade 10.
    expect(shown()).toEqual(["ảnh chụp", "Bài kiểm tra", "Đề thi thử", "Grade 9", "Grade 10"]);
  });

  it("a test whose id is the search is the top row under every order; the rest follow the order", async () => {
    const decoy = summary("T-0002", "Zeta - T 0008 School", { grade: 6, created: "2026-10-09T00:00:00Z" });
    const target = summary("T-0008", "Alpha", { grade: 12, created: "2026-10-01T00:00:00Z" });
    const other = summary("T-0003", "Mid T 0008", { grade: 9, created: "2026-10-05T00:00:00Z" });
    const found = [target, decoy, other];
    for (const q of ["T-0008", "t-0008", "T0008", " t0008 "]) {
      for (const sort of ["az", "za", "newest", "grade"] as const) {
        const ids = sortTests(found, sort, q).map((t) => t.id);
        expect(ids[0], `${q} ${sort}`).toBe("T-0008");
        expect(ids.slice(1)).toEqual(sortTests([decoy, other], sort).map((t) => t.id));
      }
    }
    // Not an id search: no pin.
    expect(sortTests(found, "za", "0008").map((t) => t.id)).toEqual(["T-0002", "T-0003", "T-0008"]);

    // In the list: Z–A with the decoy school "T 0008" still shows T-0008 first.
    writeSession("etach.testsSort", "za");
    const { api } = fakeApi({
      "GET /tests": (c: FakeCall) => (c.query.get("q") ? [target, decoy, other] : MIXED),
    });
    render(<TestsTab api={api} onOpen={() => {}} debounceMs={0} />);
    await screen.findAllByTestId("test-item");
    fireEvent.change(screen.getByTestId("tests-search"), { target: { value: "T-0008" } });
    await waitFor(() =>
      expect(screen.getAllByTestId("test-item").map((r) => r.dataset.testId)).toEqual(["T-0008", "T-0002", "T-0003"]),
    );
  });

  it("each choice orders the list, search results too; the choice survives switching tabs", async () => {
    const user = userEvent.setup();
    const fake = fakeApi({
      "GET /tests": (c: FakeCall) => (c.query.get("q") === "grade" ? [MIXED[0]!, MIXED[3]!] : MIXED),
      "GET /threads/{id}": THREADS.thC,
      "GET /threads/{id}/messages": [],
      "GET /review/count": { open: 0 },
    });
    writeSession("etach.activeThread", "thC");
    render(<AppShell connection="open" api={fake.api} threads={[listRow("thC")]} />);
    fireEvent.click(screen.getByRole("tab", { name: "Tests" }));
    await screen.findAllByTestId("test-item");

    const choose = async (label: string) => {
      await user.click(screen.getByRole("button", { name: "Sort tests" }));
      await user.click(screen.getByRole("menuitemradio", { name: label }));
    };
    await choose("Z–A");
    expect(shown()).toEqual(byCollator(MIXED.map((t) => t.display_name)).reverse());
    await choose("Newest added");
    expect(screen.getAllByTestId("test-item").map((r) => r.dataset.testId)).toEqual(["T-0002", "T-0004", "T-0001", "T-0005", "T-0003"]);
    await choose("By grade");
    expect(shown()).toEqual(sortTests(MIXED, "grade").map((t) => t.display_name));
    expect(shown().at(-1)).toBe("ảnh chụp");

    // Search results follow the chosen order (the sidecar sent Grade 9 first).
    await choose("Z–A");
    fireEvent.change(screen.getByTestId("tests-search"), { target: { value: "grade" } });
    await waitFor(() => expect(shown()).toEqual(["Grade 10", "Grade 9"]));

    // Switching sidebar tabs unmounts the list; the choice comes back with it.
    fireEvent.click(screen.getByRole("tab", { name: "Chats" }));
    fireEvent.click(screen.getByRole("tab", { name: "Tests" }));
    await screen.findAllByTestId("test-item");
    expect(shown()).toEqual(byCollator(MIXED.map((t) => t.display_name)).reverse());
    await user.click(screen.getByRole("button", { name: "Sort tests" }));
    expect(screen.getByRole("menuitemradio", { name: "Z–A" })).toHaveAttribute("aria-checked", "true");
  });
});

describe("R22.5.1.3: the sort button and its menu", () => {
  it("named Sort tests; a menu of four menuitemradio, the chosen one checked; keyboard operable", async () => {
    const user = userEvent.setup();
    const { api } = fakeApi({ "GET /tests": MIXED });
    render(<TestsTab api={api} onOpen={() => {}} />);
    await screen.findAllByTestId("test-item");
    const button = screen.getByRole("button", { name: "Sort tests" });
    expect(button).toHaveAttribute("aria-haspopup", "menu");
    expect(button).toHaveAttribute("aria-expanded", "false");
    // Square and as tall as the search box: the same height class on both; the box gives it room.
    expect(button).toHaveClass("h-8", "w-8", "shrink-0");
    expect(screen.getByTestId("tests-search")).toHaveClass("h-8", "min-w-0", "flex-1");
    expect(screen.getByTestId("tests-search").nextElementSibling).toContainElement(button);

    // Enter opens it, focus on the chosen order (A–Z by default).
    button.focus();
    await user.keyboard("{Enter}");
    const menu = screen.getByRole("menu", { name: "Sort tests" });
    const items = within(menu).getAllByRole("menuitemradio");
    expect(items.map((i) => i.textContent?.replace("✓", ""))).toEqual(["A–Z", "Z–A", "Newest added", "By grade"]);
    expect(items.map((i) => i.getAttribute("aria-checked"))).toEqual(["true", "false", "false", "false"]);
    expect(button).toHaveAttribute("aria-expanded", "true");
    await waitFor(() => expect(items[0]).toHaveFocus());
    // Arrows move (and wrap), Home and End jump.
    await user.keyboard("{ArrowDown}");
    expect(items[1]).toHaveFocus();
    await user.keyboard("{ArrowUp}{ArrowUp}");
    expect(items[3]).toHaveFocus();
    await user.keyboard("{Home}");
    expect(items[0]).toHaveFocus();
    // Esc closes and focus returns to the button.
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(button).toHaveFocus();
    // Space opens it too; Enter on an item chooses it, closes the menu and returns focus.
    await user.keyboard(" ");
    await waitFor(() => expect(screen.getAllByRole("menuitemradio")[0]).toHaveFocus());
    await user.keyboard("{ArrowDown}{Enter}");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(button).toHaveFocus();
    expect(shown()).toEqual(byCollator(MIXED.map((t) => t.display_name)).reverse());
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitemradio", { name: "Z–A" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("menuitemradio", { name: "Z–A" })).toHaveFocus();
  });
});

// --- R22.5.1.5 ----------------------------------------------------------------------------------

describe("R22.5.1.5: the looks-like notice names the other test and its id", () => {
  it("This test looks like <name> (T-0008), which is already in the bank.", async () => {
    const { api } = fakeApi({
      "GET /tests/{id}": (c: FakeCall) =>
        lastId(c) === "T-0008" ? testDetail("T-0008", { grade: 8, school: "THCS B", test_number: "2" }) : undefined,
    });
    const item = {
      id: "RV1",
      kind: "possible_duplicate",
      owner: "extract",
      status: "open",
      attempt_id: null,
      question_id: null,
      test_id: "T-0009",
      proposal: { best_test_id: "T-0008", question_alignment: {} },
      dedupe_key: "RV1",
      followup_run_id: null,
      resolution: null,
      created_at: "",
    } as unknown as Parameters<typeof CardNote>[0]["item"];
    render(<CardNote api={api} item={item} onSettle={() => {}} />);
    await waitFor(() =>
      expect(screen.getByTestId("card-note-duplicate")).toHaveTextContent(
        "This test looks like Grade 8 - Final Term - THCS B - Test 2 (T-0008), which is already in the bank.",
      ),
    );
  });
});

// --- R22.5.1.6 ----------------------------------------------------------------------------------

const answer = (qid: string, n: number) => ({
  attempt_id: "A-0001",
  question_id: qid,
  printed_number: n,
  page_no: 1,
  value: "goes",
  value_norm: "goes",
  location: "inline" as const,
  confidence: 0.9,
  reading_unsure: false,
  alt_value: null,
  alt_question_id: null,
  verdict: "ungraded" as const,
  points_awarded: null,
  teacher_override: null,
});

function expectAllSelected(input: HTMLInputElement) {
  expect(input).toHaveFocus();
  expect(input.selectionStart).toBe(0);
  expect(input.selectionEnd).toBe(input.value.length);
  expect(input.value.length).toBeGreaterThan(0);
}

describe("R22.5.1.6: starting an edit selects the old value", () => {
  it.each(["double-click", "Edit"])("a Key row (%s): the whole key selected; one key typed replaces it", async (how) => {
    const user = userEvent.setup();
    const { api } = fakeApi({
      "GET /tests/{id}/keys": [{ test_id: "T-0001", question_id: "q-1", accepted: ["A", "B"], status: "ai_fast", source: "ai" }],
      "GET /tests/{id}": TESTS["T-0001"],
    });
    render(<KeysPanel api={api} testId="T-0001" />);
    const row = await screen.findByTestId("key-row");
    if (how === "Edit") await user.click(within(row).getByTestId("key-edit"));
    else await user.dblClick(within(row).getByTestId("key-accepted"));
    const input = screen.getByTestId<HTMLInputElement>("key-input");
    expect(input).toHaveValue("A | B");
    expectAllSelected(input);
    await user.keyboard("C");
    expect(input).toHaveValue("C");
  });

  it.each(["double-click", "Edit"])("a Student answers row (%s): the whole answer selected; typing replaces it", async (how) => {
    const user = userEvent.setup();
    const { api } = fakeApi({
      "GET /attempts/{id}": { attempt: {}, answers: [answer("q-1", 1)], pages: [] },
      "GET /tests/{id}": TESTS["T-0001"],
    });
    render(<AnswersPanel api={api} attemptId="A-0001" testId="T-0001" />);
    const row = await screen.findByTestId("answer-row");
    if (how === "Edit") await user.click(within(row).getByTestId("answer-edit"));
    else await user.dblClick(within(row).getByTestId("answer-value"));
    const input = screen.getByTestId<HTMLInputElement>("answer-input");
    expect(input).toHaveValue("goes");
    expectAllSelected(input);
    await user.keyboard("x");
    expect(input).toHaveValue("x");
  });
});

// --- R22.5.1.7 ----------------------------------------------------------------------------------

describe("R22.5.1.7: every name is cut at the same place", () => {
  const nameWidthProof = (name: HTMLElement) => {
    // The name takes the room left; the unsure slot after it has the same width on every row.
    expect(name).toHaveClass("min-w-0", "flex-1", "truncate");
    const slot = name.nextElementSibling as HTMLElement;
    expect(slot).toHaveAttribute("data-testid", "unsure-slot");
    expect(slot).toHaveClass("min-w-9", "shrink-0");
    return slot;
  };

  it("sidebar threads: a row with an unsure count and one without have the same layout; full name on hover", () => {
    const long = "Grade 8 - Final Term 2 - Nguyễn Hữu Thọ - 2025 - Test G";
    const rows: ThreadSummary[] = [
      { ...listRow("thA"), shown_title: long, open_review_count: 10 },
      { ...listRow("thC"), shown_title: long + " B", open_review_count: 0 },
    ];
    render(<ThreadList threads={rows} activeId={null} onOpen={() => {}} onRename={async () => {}} onDelete={() => {}} />);
    const names = screen.getAllByTestId("thread-name");
    const slots = names.map(nameWidthProof);
    expect(slots[0]!.className).toBe(slots[1]!.className);
    expect(within(slots[0]!).getByTestId("unsure-mark")).toHaveTextContent("● 10");
    expect(slots[1]!).toBeEmptyDOMElement();
    // The same parts after the name on both rows: the slot, then the ⋯ button.
    for (const name of names) {
      const item = name.closest<HTMLElement>("[data-testid=thread-item]")!;
      expect(item.children).toHaveLength(2);
      expect(item.nextElementSibling).toHaveAttribute("data-testid", "thread-menu-button");
    }
    expect(names[0]!.closest("[data-testid=thread-item]")!.getAttribute("title")).toContain(long);
    expect(names[1]!.closest("[data-testid=thread-item]")!.getAttribute("title")).toBe(long + " B");
  });

  it("Tests rows: the same slot with and without a count; the name's title is the full name", async () => {
    const long = "Grade 8 - Final Term 2 - Nguyễn Hữu Thọ - 2025 - Test G";
    const { api } = fakeApi({
      "GET /tests": [summary("T-0001", long, { unsure: 4 }), summary("T-0002", long + " B")],
    });
    render(<TestsTab api={api} onOpen={() => {}} onDelete={() => {}} />);
    await screen.findAllByTestId("test-item");
    const names = screen.getAllByTestId("test-name");
    const slots = names.map(nameWidthProof);
    expect(slots[0]!.className).toBe(slots[1]!.className);
    expect(within(slots[0]!).getByTestId("unsure-mark")).toHaveTextContent("● 4");
    expect(slots[1]!).toBeEmptyDOMElement();
    expect(names.map((n) => n.getAttribute("title"))).toEqual([long, long + " B"]);
  });
});
