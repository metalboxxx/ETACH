// Step 22.1.4, the workspace view (PRD §10 v4.13, decision 3 = B).
// R22.1.4.2: no panel → the conversation; Test / Key / Answers / Report (from a card or the Tests tab)
//   → the panel and the photo viewer side by side, no conversation; Esc brings
//   back the same thread with its scroll position and unsent text, focus on the opener; Settings
//   and Review open as before.
// R22.1.4.3: the viewer: "Page n of N", previous / next and ← / → (not while typing), zoom, the page
//   as stored; Test and Key list the test's pages then the key pages ("Key"); Answers and Report
//   the attempt's; no photos → words; the Key workspace switches its right side to the test text.
// R22.1.4.6: below 1024 px the photos fold behind a toggle (the lg: classes; screenshots check widths).
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AppShell } from "@/components/AppShell";
import { resetDraftMemory, saveDraft } from "@/features/photo-check/draft";
import { writeSession } from "@/lib/storage";
import { fakeApi, type FakeRoute } from "@/lib/testApi";
import { PhotoViewer } from "./PhotoViewer";
import { attemptPhotos, testPhotos, type PhotoPage } from "./photos";
import { Workspace } from "./Workspace";

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
const testDetail = (over: Record<string, unknown> = {}) => ({
  id: "T-0001",
  meta: { occasion: "FinalTerm", grade: 8, term: 1, edited_fields: [] },
  content: {
    sections: [
      {
        id: "s1",
        number: 1,
        printed_title: "I. Choose",
        title: "Choose",
        instructions: null,
        points: 0.5,
        points_source: "printed",
        skill: "grammar",
        groups: [{ id: "g1", stimulus: null, pictures: [], questions: [question(1), question(2)] }],
      },
    ],
  },
  picture_paths: {},
  pages: [
    { page_no: 2, file_id: "tp2" },
    { page_no: 1, file_id: "tp1" },
  ],
  key_pages: [{ page_no: 1, file_id: "kp1" }],
  merged_into: null,
  source_run_id: "R1",
  ...over,
});
const attemptPage = (n: number, rotation = 0) => ({
  attempt_id: "A-0001",
  page_no: n,
  file_id: `ap${n}`,
  source_file_id: `src${n}`,
  rotation,
});
const attempt = {
  id: "A-0001",
  test_id: "T-0001",
  thread_id: "th1",
  student_id: null,
  student_name_read: "Học Sinh A",
  class_read: "8A",
  source_run_id: "R1",
  superseded_by: null,
  status: "extracted",
  version: 1,
  score_earned: null,
  score_possible: null,
  created_at: "",
};
const threadDetail = {
  thread: { id: "th1", title: "New thread", kind: "filled" as const, test_id: "T-0001", created_at: "" },
  attempt,
  test: { id: "T-0001" },
  student: null,
  test_display_name: "Grade 8 · FinalTerm HK1 · Test 1",
  shown_title: "Học Sinh A · Grade 8 test",
};
const runCard = {
  id: "m1",
  thread_id: "th1",
  role: "app",
  kind: "run_card",
  body: { run_id: "R1", test_id: "T-0001", attempt_id: "A-0001", unsure_count: 1, no_answers: false, duplicate: false },
  created_at: "",
};
const summary = {
  thread: threadDetail.thread,
  shown_title: threadDetail.shown_title,
  kind: "filled" as const,
  group: "Chưa rõ",
  student_id: null,
  last_activity: "", open_review_count: 0,
};

function routes(extra: Record<string, FakeRoute> = {}) {
  return fakeApi({
    "GET /threads/{id}": threadDetail,
    "GET /threads/{id}/messages": [runCard],
    "GET /tests/{id}": testDetail(),
    "GET /tests/{id}/keys": [],
    "GET /tests": [
      { id: "T-0001", display_name: "Grade 8 test", attempt_count: 1, meta: {}, points_possible: 0.5, updated_at: "" },
    ],
    "GET /attempts/{id}": { attempt, answers: [], pages: [attemptPage(1), attemptPage(2, 90)] },
    "GET /attempts/{id}/report": {
      attempt,
      report: {
        attempt_id: "A-0001",
        run_id: "r",
        created_at: "",
        summary_vi: "",
        uncertain_points: 0,
        teacher_questions: [],
        weak_points: [],
        careless_notes: [],
      },
      verdicts: [],
      explanations: [],
    },
    "GET /review/count": { open: 0 },
    ...extra,
  });
}

afterEach(() => {
  resetDraftMemory();
  window.sessionStorage.clear();
});

function renderShell(fake = routes()) {
  writeSession("etach.activeThread", "th1");
  return render(<AppShell connection="open" api={fake.api} threads={[summary]} />);
}

describe("workspace view (R22.1.4.2)", () => {
  it("an extracted thread opens straight into its Test workspace: photos, no conversation, no Back (R22.3.2.1)", async () => {
    renderShell();
    const ws = await screen.findByTestId("workspace");
    expect(ws).toHaveAttribute("data-kind", "test");
    expect(screen.queryByTestId("conversation")).toBeNull();
    expect(screen.queryByTestId("extraction-card")).toBeNull();
    expect(within(ws).queryByTestId("workspace-back")).toBeNull();
    expect(within(ws).getByRole("tab", { name: "Test" })).toHaveAttribute("aria-selected", "true");
    expect(within(ws).getByTestId("photo-viewer")).toBeInTheDocument();
    expect(await within(ws).findByTestId("test-text")).toBeInTheDocument();
  });

  it("Esc returns too; the scroll position and the unsent text survive; focus goes back to the Tests row", async () => {
    // A thread before Run: its photo check card holds unsent text (the Existing test search).
    const fake = routes({
      "GET /threads/{id}": { ...threadDetail, thread: { ...threadDetail.thread, kind: "pending" }, attempt: null, test: null },
      "GET /threads/{id}/messages": [],
    });
    saveDraft("th1", { pages: [{ file_id: "f1", rotation: 0, is_key: false, text_file_id: null }], existingTest: null });
    renderShell(fake);
    const search = await screen.findByTestId("existing-test-search");
    fireEvent.change(search, { target: { value: "lớp 8 đề" } });
    const scroller = screen.getByTestId("conversation-scroll");
    scroller.scrollTop = 120;
    fireEvent.scroll(scroller);

    fireEvent.click(screen.getByRole("tab", { name: "Tests" }));
    const row = await screen.findByTestId("test-item");
    row.focus();
    fireEvent.click(row);
    expect(screen.getByTestId("workspace")).toBeInTheDocument();
    expect(screen.getByTestId("conversation")).not.toBeVisible();
    scroller.scrollTop = 0; // what a hidden box may do

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByTestId("workspace")).toBeNull();
    expect(screen.getByTestId("conversation")).toBeVisible();
    expect(scroller.scrollTop).toBe(120);
    expect(screen.getByTestId("existing-test-search")).toHaveValue("lớp 8 đề");
    await waitFor(() => expect(row).toHaveFocus());
  });

  it.each([
    ["Key", "keys"],
    ["Student answers", "answers"],
  ])("the %s tab opens the %s workspace with photos", async (title, kind) => {
    renderShell();
    const ws0 = await screen.findByTestId("workspace");
    fireEvent.click(await within(ws0).findByRole("tab", { name: title }));
    const ws = screen.getByTestId("workspace");
    expect(ws).toHaveAttribute("data-kind", kind);
    expect(within(ws).getByTestId("photo-viewer")).toBeInTheDocument();
    expect(screen.queryByTestId("conversation")).toBeNull();
  });

  it("opening the thread in the sidebar, or Esc, goes back to its Test", async () => {
    renderShell();
    fireEvent.click(await within(await screen.findByTestId("workspace")).findByRole("tab", { name: "Key" }));
    expect(screen.getByTestId("workspace")).toHaveAttribute("data-kind", "keys");
    fireEvent.click(screen.getByTestId("thread-item"));
    expect(screen.getByTestId("workspace")).toHaveAttribute("data-kind", "test");
    fireEvent.click(within(screen.getByTestId("workspace")).getByRole("tab", { name: "Key" }));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByTestId("workspace")).toHaveAttribute("data-kind", "test");
  });
});

describe("photo sources (R22.1.4.3)", () => {
  it("Test and Key: the test's pages by number, then the key pages; Answers and Report: the attempt's", () => {
    const t = testPhotos(testDetail() as never);
    expect(t.map((p) => [p.fileId, p.isKey])).toEqual([
      ["tp1", false],
      ["tp2", false],
      ["kp1", true],
    ]);
    const a = attemptPhotos([attemptPage(2, 90), attemptPage(1)]);
    expect(a.map((p) => [p.fileId, p.rotation])).toEqual([
      ["ap1", 0],
      ["ap2", 90],
    ]);
  });

  it("the Test workspace lists the test's photos (key labelled), the Report workspace the attempt's", async () => {
    const { api } = routes();
    const { unmount } = render(
      <Workspace api={api} view={{ kind: "test", testId: "T-0001" }} title="Test" />,
    );
    await waitFor(() => expect(screen.getByTestId("photo-status")).toHaveTextContent("Page 1 of 3"));
    expect(screen.getAllByTestId("photo-page").map((b) => b.textContent)).toEqual(["1", "2", "Key 1"]);
    expect(screen.getByTestId("photo-image")).toHaveAttribute("src", "http://127.0.0.1:9/files/tp1?token=t");
    unmount();

    render(
      <Workspace
        api={api}
        view={{ kind: "report", attemptId: "A-0001", testId: "T-0001" }}
        title="Grade report"
      />,
    );
    await waitFor(() => expect(screen.getByTestId("photo-status")).toHaveTextContent("Page 1 of 2"));
    expect(screen.getByTestId("photo-image")).toHaveAttribute("data-file-id", "ap1");
  });

  it("the Key workspace switches its right side between the photos and the test text", async () => {
    const { api } = routes();
    render(<Workspace api={api} view={{ kind: "keys", testId: "T-0001" }} title="Key" />);
    await screen.findByTestId("photo-image");
    const photos = screen.getByRole("button", { name: "Photos" });
    expect(photos).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Test text" }));
    const text = screen.getByTestId("key-test-text");
    expect(await within(text).findByTestId("clean-test")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-photos")).toHaveAccessibleName("Test text");
    fireEvent.click(screen.getAllByRole("button", { name: "Photos" })[0]!);
    expect(screen.queryByTestId("key-test-text")).toBeNull();
    expect(screen.getByTestId("photo-image")).toBeVisible();
  });

  it("R22.2.5.2: the Key workspace lists the key photos after the test pages, labelled Key", async () => {
    const { api } = routes();
    render(<Workspace api={api} view={{ kind: "keys", testId: "T-0001" }} title="Key" />);
    await waitFor(() => expect(screen.getByTestId("photo-status")).toHaveTextContent("Page 1 of 3"));
    expect(screen.getAllByTestId("photo-page").map((b) => b.textContent)).toEqual(["1", "2", "Key 1"]);
    fireEvent.click(screen.getByRole("button", { name: "Key page 1" }));
    expect(screen.getByTestId("photo-status")).toHaveTextContent("Page 3 of 3");
    expect(screen.getByTestId("photo-key-badge")).toHaveTextContent("Key");
    expect(screen.getByTestId("photo-image")).toHaveAttribute("data-file-id", "kp1");
  });

  it("the test text stays a Key choice: another workspace in its place shows the photos", async () => {
    const { api } = routes();
    const { rerender } = render(
      <Workspace api={api} view={{ kind: "keys", testId: "T-0001" }} title="Key" />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Test text" }));
    expect(screen.getByTestId("key-test-text")).toBeInTheDocument();
    rerender(<Workspace api={api} view={{ kind: "test", testId: "T-0001" }} title="Test" />);
    expect(screen.queryByTestId("key-test-text")).toBeNull();
    expect(screen.getByTestId("workspace-photos")).toHaveAccessibleName("Original photos");
  });

  it("starts at the page it was opened at", async () => {
    const { api } = routes();
    render(
      <Workspace api={api} view={{ kind: "test", testId: "T-0001", page: 2 }} title="Test" />,
    );
    await waitFor(() => expect(screen.getByTestId("photo-status")).toHaveTextContent("Page 2 of 3"));
    expect(screen.getByTestId("photo-image")).toHaveAttribute("data-file-id", "tp2");
  });

  it("below 1024 px the photos fold behind a toggle in the bar (R22.1.4.6)", async () => {
    const { api } = routes();
    render(<Workspace api={api} view={{ kind: "test", testId: "T-0001" }} title="Test" />);
    const toggle = screen.getByTestId("workspace-side-toggle");
    expect(toggle).toHaveClass("lg:hidden");
    expect(toggle).toHaveTextContent("Show photos");
    expect(screen.getByTestId("workspace-photos")).toHaveClass("hidden", "lg:flex");
    expect(screen.getByTestId("artifact-panel")).not.toHaveClass("hidden");
    fireEvent.click(toggle);
    expect(toggle).toHaveTextContent("Show test");
    expect(screen.getByTestId("workspace-photos")).not.toHaveClass("hidden");
    expect(screen.getByTestId("artifact-panel")).toHaveClass("hidden", "lg:flex");
  });
});

const pages: PhotoPage[] = [
  { key: "p1", fileId: "f1", pageNo: 1, isKey: false, rotation: 90 },
  { key: "p2", fileId: "f2", pageNo: 2, isKey: false, rotation: 0 },
  { key: "k1", fileId: "k1", pageNo: 1, isKey: true, rotation: null },
];

describe("photo viewer (R22.1.4.3)", () => {
  it("Page n of N, previous / next, the page strip; a key page is labelled", () => {
    const { api } = fakeApi({});
    render(<PhotoViewer api={api} pages={pages} owner="this test" />);
    const status = screen.getByTestId("photo-status");
    expect(status).toHaveTextContent("Page 1 of 3");
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(status).toHaveTextContent("Page 2 of 3");
    fireEvent.click(screen.getByRole("button", { name: "Key page 1" }));
    expect(status).toHaveTextContent("Page 3 of 3");
    expect(screen.getByTestId("photo-key-badge")).toHaveTextContent("Key");
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Key page 1" })).toHaveAttribute("aria-current", "page");
  });

  it("← / → turn the page, but not while typing in a field", () => {
    const { api } = fakeApi({});
    render(
      <>
        <input aria-label="Field" />
        <PhotoViewer api={api} pages={pages} owner="this test" />
      </>,
    );
    const status = screen.getByTestId("photo-status");
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(status).toHaveTextContent("Page 2 of 3");
    fireEvent.keyDown(window, { key: "ArrowLeft" });
    expect(status).toHaveTextContent("Page 1 of 3");
    const field = screen.getByRole("textbox", { name: "Field" });
    field.focus();
    fireEvent.keyDown(field, { key: "ArrowRight" });
    expect(status).toHaveTextContent("Page 1 of 3");
  });

  it("zoom: Fit, larger, smaller; the page is shown as stored (the rotation is already in the file)", () => {
    const { api } = fakeApi({});
    render(<PhotoViewer api={api} pages={pages} owner="this test" />);
    const stage = screen.getByTestId("photo-stage");
    const img = screen.getByTestId("photo-image");
    expect(img).toHaveAttribute("data-rotation", "90");
    expect(img.style.transform).toBe(""); // not turned a second time
    expect(img).toHaveAccessibleName("Page 1, original photo");
    expect(stage).toHaveAttribute("data-zoom", "1");
    expect(screen.getByRole("button", { name: "Smaller" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Larger" }));
    fireEvent.click(screen.getByRole("button", { name: "Larger" }));
    expect(stage).toHaveAttribute("data-zoom", "2");
    expect(screen.getByTestId("photo-zoom-fit")).toHaveTextContent("200%");
    fireEvent.click(screen.getByRole("button", { name: "Smaller" }));
    expect(stage).toHaveAttribute("data-zoom", "1.5");
    fireEvent.click(screen.getByTestId("photo-zoom-fit"));
    expect(stage).toHaveAttribute("data-zoom", "1");
    expect(screen.getByTestId("photo-zoom-fit")).toHaveTextContent("Fit");
  });

  it("no photos, or a page without an image, is said in words", async () => {
    const { api } = fakeApi({ "GET /files/{id}": "Unit 3. Choose the best answer." });
    const { unmount } = render(<PhotoViewer api={api} pages={[]} owner="these answers" />);
    expect(screen.getByTestId("photo-empty")).toHaveTextContent("No photos stored for these answers.");
    unmount();

    // A text-only page: the image fails, the file is text, so its text is shown.
    render(<PhotoViewer api={api} pages={[pages[1]!]} owner="this test" />);
    await act(async () => {
      fireEvent.error(screen.getByTestId("photo-image"));
    });
    const text = await screen.findByTestId("photo-text-page");
    expect(text).toHaveTextContent("Page 2 has no photo: it came from a typed file (Word or PDF).");
    expect(text).toHaveTextContent("Unit 3. Choose the best answer.");
  });

  it("a photo that is no longer stored says so", async () => {
    const { api } = fakeApi({}); // 404
    render(<PhotoViewer api={api} pages={[pages[0]!]} owner="this test" />);
    await act(async () => {
      fireEvent.error(screen.getByTestId("photo-image"));
    });
    expect(await screen.findByTestId("photo-missing")).toHaveTextContent("The photo of page 1 is no longer stored.");
  });
});
