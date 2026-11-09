// R16.4: print view. Under `@media print` the sidebar and the panel chrome are display:none, and
// each picture placeholder matches the D11 format. Also the test panel's metadata chips
// (PATCH /tests/{id}) and the answers panel's override editor (PUT …/answers/{qid}; "" = blank).
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/AppShell";
import { fakeApi, type FakeCall } from "@/lib/testApi";
import { AnswersPanel, answerMark, overrideState } from "./AnswersPanel";
import { PLACEHOLDER_RE, pictureLabel, picturePlaceholder } from "./pictures";
import { KeysPanel } from "./KeysPanel";
import { TestPanel } from "./TestPanel";

const SHA = "ab".repeat(32);
const SHA2 = "0f".repeat(32);

const test_ = {
  id: "T-0001",
  meta: { occasion: "FinalTerm", grade: 8, term: 1, school: "THCS A", edited_fields: [] },
  content: {
    sections: [
      {
        id: "s1",
        number: 1,
        printed_title: "I. Choose the best answer",
        title: "Choose",
        instructions: "Khoanh tròn đáp án đúng.",
        points: 1,
        points_source: "printed",
        skill: "grammar",
        groups: [
          {
            id: "g1",
            stimulus: "Read the **notice**.",
            pictures: [
              { file_id: SHA, page_no: 1 },
              { file_id: SHA2, page_no: 3 },
            ],
            questions: [
              {
                id: "q1",
                number: 1,
                printed_number: 1,
                page_no: 1,
                answer_form: "choice", context: "single",
                stem: "She ___ to school.",
                options: [
                  { label: "A", text: "go" },
                  { label: "B", text: "goes" },
                ],
                cue: null,
                points: 0.25,
              },
              {
                id: "q2",
                number: 2,
                printed_number: 2,
                page_no: 1,
                answer_form: "word", context: "single",
                stem: "He ___ (be) here.",
                options: null,
                cue: null,
                points: 0.25,
              },
            ],
          },
        ],
      },
    ],
  },
  content_schema_version: 1,
  fingerprint: "f",
  points_possible: 0.5,
  source_run_id: "R1",
  merged_into: null,
  created_at: "2026-10-04T00:00:00Z",
  updated_at: "2026-10-04T00:00:00Z",
  picture_paths: { [SHA]: `files/ab/${SHA}.png` },
};

function injectPrintCss() {
  const dir = path.dirname(fileURLToPath(import.meta.url));
  const css = readFileSync(path.resolve(dir, "../../styles/print.css"), "utf8");
  const style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);
  return () => style.remove();
}

/** Selectors whose `@media print` rule sets display:none. */
function printHiddenSelectors(): string[] {
  const out: string[] = [];
  for (const sheet of Array.from(document.styleSheets)) {
    for (const rule of Array.from(sheet.cssRules)) {
      if (rule instanceof CSSMediaRule && rule.media.mediaText.includes("print")) {
        for (const inner of Array.from(rule.cssRules)) {
          if (inner instanceof CSSStyleRule && inner.style.getPropertyValue("display") === "none") {
            out.push(inner.selectorText);
          }
        }
      }
    }
  }
  return out;
}

describe("print view (R16.4)", () => {
  it("hides the sidebar and the panel chrome under @media print; placeholders match D11", async () => {
    const remove = injectPrintCss();
    try {
      const hidden = printHiddenSelectors();
      expect(hidden.length).toBeGreaterThan(0);
      const isHidden = (el: Element) => hidden.some((sel) => el.matches(sel));
      const { api } = fakeApi({ "GET /tests/{id}": test_ });
      const shell = render(<AppShell connection="open" threads={[]} />);
      fireEvent.click(screen.getByRole("button", { name: "Settings" }));
      const panel = await screen.findByTestId("artifact-panel");
      const sidebar = shell.container.querySelector("nav")!;
      expect(isHidden(sidebar)).toBe(true);
      expect(isHidden(within(panel).getByTestId("panel-chrome"))).toBe(true);
      expect(isHidden(panel)).toBe(false);
      shell.unmount();

      render(<TestPanel api={api} testId="T-0001" printing />);
      const placeholders = await screen.findAllByTestId("picture-placeholder");
      expect(placeholders).toHaveLength(2);
      for (const p of placeholders) {
        expect(p.textContent).toMatch(PLACEHOLDER_RE);
        expect(isHidden(p)).toBe(false);
      }
      // SHA has a stored .png path in picture_paths; SHA2 has none, so it falls back to .jpg.
      expect(placeholders[0]!.textContent).toBe(`[Hình: files/ab/${SHA}.png · trang 1]`);
      expect(placeholders[1]!.textContent).toBe(`[Hình: files/0f/${SHA2}.jpg · trang 3]`);
      // The test panel's toolbar (chips, Print) is panel chrome too.
      expect(isHidden(screen.getByTestId("test-toolbar"))).toBe(true);
    } finally {
      remove();
    }
  });

  it("pictureLabel uses the stored path's extension (picture_paths, llm-design v4.10)", () => {
    const paths = { [SHA]: `files/ab/${SHA}.png` };
    expect(pictureLabel({ file_id: SHA, page_no: 4 }, paths)).toBe(`[Hình: files/ab/${SHA}.png · trang 4]`);
    expect(pictureLabel({ file_id: SHA, page_no: 4 }, paths)).toMatch(PLACEHOLDER_RE);
    expect(pictureLabel({ file_id: SHA2, page_no: 1 }, paths)).toBe(`[Hình: files/0f/${SHA2}.jpg · trang 1]`);
  });

  it("picturePlaceholder keeps a given extension", () => {
    expect(picturePlaceholder(SHA, 2, ".PNG")).toBe(`[Hình: files/ab/${SHA}.png · trang 2]`);
    expect(picturePlaceholder(SHA, 2)).toMatch(PLACEHOLDER_RE);
  });
});

describe("test panel", () => {
  it("renders sections → groups (stimulus, pictures) → questions as stored", async () => {
    const { api } = fakeApi({ "GET /tests/{id}": test_ });
    render(<TestPanel api={api} testId="T-0001" printing />);
    const article = await screen.findByTestId("clean-test");
    expect(within(article).getByText("I. Choose the best answer")).toBeInTheDocument();
    expect(within(article).getByText("Khoanh tròn đáp án đúng.")).toBeInTheDocument();
    expect(within(article).getByText("notice").tagName).toBe("STRONG");
    expect(within(article).getAllByTestId("test-question")).toHaveLength(2);
    expect(within(article).getByText("B. goes")).toBeInTheDocument();
  });

  it("a chip edit sends PATCH /tests/{id} {meta: {field: value}}; Print calls print", async () => {
    const patched = { ...test_, meta: { ...test_.meta, school: "THCS B" } };
    const { api, calls } = fakeApi({ "GET /tests/{id}": test_, "PATCH /tests/{id}": patched });
    const print = vi.fn();
    render(<TestPanel api={api} testId="T-0001" print={print} />);
    const chip = (await screen.findAllByTestId("meta-chip")).find((c) => c.dataset.field === "school")!;
    expect(chip).toHaveTextContent("THCS A");
    fireEvent.click(chip);
    const input = screen.getByTestId("meta-chip-input");
    fireEvent.change(input, { target: { value: "THCS B" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ meta: { school: "THCS B" } });
    await waitFor(() =>
      expect(screen.getAllByTestId("meta-chip").find((c) => c.dataset.field === "school")).toHaveTextContent(
        "THCS B",
      ),
    );
    fireEvent.click(screen.getByTestId("test-print"));
    expect(print).toHaveBeenCalledOnce();
  });

  it("a numeric chip sends a number", async () => {
    const { api, calls } = fakeApi({ "GET /tests/{id}": test_, "PATCH /tests/{id}": test_ });
    render(<TestPanel api={api} testId="T-0001" printing />);
    fireEvent.click((await screen.findAllByTestId("meta-chip")).find((c) => c.dataset.field === "grade")!);
    const input = screen.getByTestId("meta-chip-input");
    fireEvent.change(input, { target: { value: "9" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ meta: { grade: 9 } }));
  });
});

const answer = (qid: string, n: number, extra: Record<string, unknown> = {}) => ({
  attempt_id: "A-0001",
  question_id: qid,
  printed_number: n,
  page_no: 1,
  value: "B" as string | null,
  value_norm: "b",
  location: "circled_option" as const,
  confidence: 0.9,
  reading_unsure: false,
  alt_value: null,
  alt_question_id: null,
  verdict: "ungraded" as const,
  points_awarded: null,
  teacher_override: null as string | null,
  ...extra,
});

describe("answers panel", () => {
  it("override states: null = none, empty = confirmed blank, text = value; marks are placeholders", () => {
    expect(overrideState({ teacher_override: null })).toBe("none");
    expect(overrideState({ teacher_override: "" })).toBe("blank");
    expect(overrideState({ teacher_override: "x" })).toBe("value");
    expect(answerMark(answer("q", 1) as never)).toBe("–");
    expect(answerMark(answer("q", 1, { reading_unsure: true }) as never)).toBe("–");
    expect(answerMark(answer("q", 1, { verdict: "correct" }) as never)).toBe("✓");
    expect(answerMark(answer("q", 1, { verdict: "incorrect" }) as never)).toBe("✗");
  });

  it("lists answers in question order; a row click opens the editor → PUT; Confirm blank sends empty", async () => {
    const answers = [answer("q2", 2, { value: null, reading_unsure: true }), answer("q1", 1)];
    const { api, calls } = fakeApi({
      "GET /attempts/{id}": { attempt: {}, answers, pages: [] },
      "GET /tests/{id}": test_,
      "PUT /attempts/{id}/answers/{question_id}": (c: FakeCall) => {
        const qid = c.path.split("/").pop()!;
        const value = (c.body as { value: string }).value;
        return {
          answer: answer(qid, qid === "q1" ? 1 : 2, { teacher_override: value.trim() ? value : "" }),
          version: 2,
          run_ids: [],
        };
      },
    });
    const changed = vi.fn();
    render(<AnswersPanel api={api} attemptId="A-0001" testId="T-0001" onChanged={changed} />);
    const rows = await screen.findAllByTestId("answer-row");
    expect(rows.map((r) => r.dataset.questionId)).toEqual(["q1", "q2"]);
    expect(within(rows[1]!).getByTestId("answer-value")).toHaveTextContent("(blank)");
    // R22.2.1.2: an unsure student answer says so in words, never a bare "?"
    expect(within(rows[1]!).getByTestId("answer-unsure-label")).toHaveTextContent(/^AI unsure student answer$/);
    expect(within(rows[1]!).getByTestId("answer-mark").textContent).toBe("");
    expect(rows[1]!.textContent).not.toContain("?");

    fireEvent.click(within(rows[0]!).getByRole("button", { name: /Edit question 1/ }));
    const input = screen.getByTestId("answer-input");
    expect(input).toHaveValue("B");
    fireEvent.change(input, { target: { value: "goes" } });
    fireEvent.click(screen.getByTestId("answer-save"));
    await waitFor(() => expect(screen.getAllByTestId("answer-row")[0]).toHaveAttribute("data-override", "value"));
    expect(calls.find((c) => c.method === "PUT")).toMatchObject({
      path: "/attempts/A-0001/answers/q1",
      body: { value: "goes" },
    });

    fireEvent.click(within(screen.getAllByTestId("answer-row")[1]!).getByRole("button", { name: /Edit question 2/ }));
    fireEvent.click(screen.getByTestId("answer-confirm-blank"));
    await waitFor(() => expect(screen.getAllByTestId("answer-row")[1]).toHaveAttribute("data-override", "blank"));
    expect(calls.filter((c) => c.method === "PUT")[1]!.body).toEqual({ value: "" });
    expect(within(screen.getAllByTestId("answer-row")[1]!).getByTestId("answer-value")).toHaveTextContent(
      "(blank, confirmed)",
    );
    expect(changed).toHaveBeenCalledTimes(2);
  });
});

describe("rows: double-click edits, content first (R22.2.2.4)", () => {
  it("a double-click on a Student answers row opens its editor; Edit stays; content comes before actions", async () => {
    const { api } = fakeApi({
      "GET /attempts/{id}": { attempt: {}, answers: [answer("q1", 1)], pages: [] },
      "GET /tests/{id}": test_,
    });
    render(<AnswersPanel api={api} attemptId="A-0001" testId="T-0001" />);
    const row = await screen.findByTestId("answer-row");
    const value = within(row).getByTestId("answer-value");
    const edit = within(row).getByRole("button", { name: /Edit question 1/ });
    expect(edit).toHaveTextContent("Edit");
    // the answer first, the Edit action after it (on the right)
    expect(value.compareDocumentPosition(edit) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    fireEvent.doubleClick(value);
    expect(screen.getByTestId("answer-input")).toHaveValue("B");
  });

  it("a double-click on a Key row opens its editor; the Edit button still does", async () => {
    const { api } = fakeApi({
      "GET /tests/{id}/keys": [{ test_id: "T-0001", question_id: "q-1", accepted: ["A", "B"], status: "ai_fast", source: "ai" }],
      "GET /tests/{id}": test_,
    });
    render(<KeysPanel api={api} testId="T-0001" />);
    const row = await screen.findByTestId("key-row");
    fireEvent.doubleClick(within(row).getByTestId("key-accepted"));
    expect(screen.getByTestId("key-input")).toHaveValue("A | B");
    fireEvent.keyDown(screen.getByTestId("key-input"), { key: "Escape" });
    expect(screen.queryByTestId("key-input")).toBeNull();
    fireEvent.click(within(row).getByTestId("key-edit"));
    expect(screen.getByTestId("key-input")).toBeInTheDocument();
  });
});

describe("the test's title and details line (R22.2.2.6)", () => {
  it("the print view and the on-screen test show the DOCX's title and details line", async () => {
    const t = { ...test_, meta: { occasion: "FinalTerm", grade: 8, term: 1, duration_minutes: 45 }, points_possible: 10 };
    const { api } = fakeApi({ "GET /tests/{id}": t });
    const { rerender } = render(<TestPanel api={api} testId="T-0001" />);
    expect(await screen.findByTestId("test-title-name")).toHaveTextContent(/^Grade 8 - Final Term 1$/);
    expect(screen.getByTestId("test-title-details")).toHaveTextContent(/^45 minutes · 10 points$/);
    rerender(<TestPanel api={api} testId="T-0001" printing />);
    const printed = within(await screen.findByTestId("clean-test"));
    expect(printed.getByTestId("test-title-name")).toHaveTextContent(/^Grade 8 - Final Term 1$/);
    expect(printed.getByTestId("test-title-details")).toHaveTextContent(/^45 minutes · 10 points$/);
  });
});
