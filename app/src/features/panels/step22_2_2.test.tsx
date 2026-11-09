// R22.2.2.7: the step 22.1 verifier's minor findings (step22.1-plan §5).
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppShell } from "@/components/AppShell";
import { SaveAsWord } from "@/components/SaveAsWord";
import { fakeApi } from "@/lib/testApi";
import { pruneErrors } from "./TestPanel";

const TEXT = "— Page 1 —\n\n1. One.\n   A. a    B. b\n";
const test_ = {
  id: "T-0001",
  meta: { occasion: "FinalTerm" },
  content: { sections: [] },
  content_schema_version: 1,
  fingerprint: "",
  points_possible: 0,
  source_run_id: null,
  merged_into: null,
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
  picture_paths: {},
  pages: [],
  key_pages: [],
  content_text: TEXT,
  review: [],
};

describe("focus after Esc and Keep editing", () => {
  it("Esc in the test text moves focus to the panel, not the page body; Keep editing returns it to the text", async () => {
    const { api } = fakeApi({ "GET /tests/{id}": test_, "GET /threads": [] });
    render(<AppShell connection="open" api={api} threads={[]} initialPanel={{ kind: "test", testId: "T-0001" }} />);
    const area = await screen.findByTestId("test-text");
    fireEvent.change(area, { target: { value: TEXT + "more" } });
    area.focus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(document.activeElement).toBe(screen.getByTestId("artifact-panel"));
    expect(document.activeElement).not.toBe(document.body);
    fireEvent.keyDown(window, { key: "Escape" });
    const dialog = await screen.findByTestId("confirm-dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Keep editing" }));
    await waitFor(() => expect(screen.getByTestId("test-text")).toHaveFocus());
  });
});

describe("line errors clear when their line changes", () => {
  const before = "a\nb\nc\nd";
  const errs = [
    { line: 2, message: "x" },
    { line: 4, message: "y" },
    { line: null, message: "z" },
  ];
  it("an edit on a line drops that line's error only", () => {
    expect(pruneErrors(errs, before, "a\nB\nc\nd")).toEqual([errs[1], errs[2]]);
  });
  it("added lines drop the errors from the first changed line on", () => {
    expect(pruneErrors(errs, before, "a\nnew\nb\nc\nd")).toEqual([errs[2]]);
    expect(pruneErrors(errs, before, "a\nb\nc\nnew\nd")).toEqual([errs[0], errs[2]]);
  });
  it("an unchanged text keeps them all", () => {
    expect(pruneErrors(errs, before, before)).toEqual(errs);
  });
});

describe("the Save as Word status region", () => {
  it("is in the page, and not display:none, before anything is saved", () => {
    render(<SaveAsWord what="test" testId="t" save={async () => ({ path: "x", file_name: "x.docx" }) as never} />);
    const region = screen.getByTestId("save-docx-status");
    expect(region).toHaveAttribute("role", "status");
    expect(region.className).not.toMatch(/(^|\s)(empty:)?hidden(\s|$)/);
  });
});
