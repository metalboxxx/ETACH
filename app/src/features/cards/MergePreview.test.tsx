// Step 22.6.6: the merge preview draws its rows and their count only once both tests have loaded
// (it drew rows from the alignment alone, with an empty data-from, while the merged test was
// still loading; when the survivor came first the preview looked complete too early, R19.6).
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ApiClient } from "@/api/client";
import type { ReviewItem } from "@/features/unsure/unsure";
import { MergePreview } from "./MergePreview";

const test_ = (id: string, prefix: string) => ({
  id,
  meta: {},
  content: {
    sections: [
      {
        id: "s1",
        groups: [
          {
            id: "g1",
            questions: [1, 2].map((n) => ({ id: `${prefix}${n}`, printed_number: n })),
          },
        ],
      },
    ],
  },
});

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

describe("MergePreview waits for both tests (step 22.6.6, R19.6)", () => {
  it("survivor first: no rows and no count; then every row with its question once the merged test loads", async () => {
    const merged = deferred<unknown>();
    const survivor = deferred<unknown>();
    const api = {
      get: (_path: string, opts: { path: { id: string } }) => (opts.path.id === "T-NEW" ? merged.promise : survivor.promise),
    } as unknown as ApiClient;
    const item = {
      id: "R1",
      kind: "possible_duplicate",
      test_id: "T-NEW",
      proposal: { best_test_id: "T-OLD", question_alignment: { n1: "o1", n2: "o2" } },
    } as unknown as ReviewItem;
    render(<MergePreview api={api} item={item} busy={false} onCancel={() => {}} onConfirm={() => {}} />);

    expect(screen.getByTestId("merge-loading")).toHaveTextContent("Loading…");
    await act(async () => survivor.resolve(test_("T-OLD", "o")));
    expect(screen.queryAllByTestId("merge-row")).toHaveLength(0);
    expect(screen.queryByTestId("merge-summary")).toBeNull();
    expect(screen.getByTestId("merge-loading")).toBeInTheDocument();
    expect(screen.getByTestId("review-merge-confirm")).toBeDisabled();

    await act(async () => merged.resolve(test_("T-NEW", "n")));
    const rows = screen.getAllByTestId("merge-row");
    expect(rows.map((r) => [r.getAttribute("data-from"), r.getAttribute("data-to")])).toEqual([
      ["n1", "o1"],
      ["n2", "o2"],
    ]);
    expect(screen.getByTestId("merge-summary")).toHaveAttribute("data-aligned", "2");
    expect(screen.queryByTestId("merge-loading")).toBeNull();
    expect(screen.getByTestId("review-merge-confirm")).toBeEnabled();
  });

  it("a test that fails to load does not leave the preview loading: the rows fall back to the alignment", async () => {
    const survivor = deferred<unknown>();
    const api = {
      get: (_path: string, opts: { path: { id: string } }) =>
        opts.path.id === "T-NEW" ? Promise.reject(new Error("gone")) : survivor.promise,
    } as unknown as ApiClient;
    const item = {
      id: "R1",
      kind: "possible_duplicate",
      test_id: "T-NEW",
      proposal: { best_test_id: "T-OLD", question_alignment: { n1: "o1" } },
    } as unknown as ReviewItem;
    render(<MergePreview api={api} item={item} busy={false} onCancel={() => {}} onConfirm={() => {}} />);
    await act(async () => survivor.resolve(test_("T-OLD", "o")));
    expect(screen.queryByTestId("merge-loading")).toBeNull();
    expect(screen.getAllByTestId("merge-row")).toHaveLength(1);
  });
});
