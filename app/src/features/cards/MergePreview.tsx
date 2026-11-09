/**
 * The merge preview for a `possible_duplicate` on the extraction card (PRD D1, step 22.1.5; moved
 * from the removed Review panel): each question of this (merged) test and the survivor question
 * its answers move to, from the item's `question_alignment`. Questions without a match keep their
 * answers ungraded (a `merge_unaligned` item each).
 */
import { useEffect, useState } from "react";
import type { ApiClient, Schemas } from "@/api/client";
import { str, type ReviewItem } from "@/features/unsure/unsure";

type Test = Schemas["TestWithPaths"];
type Question = Schemas["Question"];

export function MergePreview({
  api,
  item,
  busy,
  onCancel,
  onConfirm,
}: {
  api: ApiClient;
  item: ReviewItem;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const survivorId = str(item.proposal.best_test_id);
  const alignment = (item.proposal.question_alignment ?? {}) as Record<
    string,
    string
  >;
  const [merged, setMerged] = useState<Test | null>(null);
  const [survivor, setSurvivor] = useState<Test | null>(null);
  // Each fetch is settled once it has loaded or failed (a failure falls back to the alignment alone).
  const [mergedSettled, setMergedSettled] = useState(!item.test_id);
  const [survivorSettled, setSurvivorSettled] = useState(!survivorId);
  useEffect(() => {
    const ctrl = new AbortController();
    if (item.test_id) {
      api
        .get("/tests/{id}", { path: { id: item.test_id }, signal: ctrl.signal })
        .then(setMerged)
        .catch(() => {})
        .finally(() => {
          if (!ctrl.signal.aborted) setMergedSettled(true);
        });
    }
    if (survivorId) {
      api
        .get("/tests/{id}", { path: { id: survivorId }, signal: ctrl.signal })
        .then(setSurvivor)
        .catch(() => {})
        .finally(() => {
          if (!ctrl.signal.aborted) setSurvivorSettled(true);
        });
    }
    return () => ctrl.abort();
  }, [api, item.test_id, survivorId]);
  // The rows and their count wait for both tests, so they never show half-made (step 22.6.6).
  const ready = mergedSettled && survivorSettled;

  const into = new Map(allQuestions(survivor).map((q) => [q.id, q]));
  const rows = merged
    ? allQuestions(merged).map((q) => ({
        q,
        to: alignment[q.id] ? (into.get(alignment[q.id]!) ?? null) : null,
      }))
    : Object.entries(alignment).map(([from, to]) => ({
        q: null,
        from,
        to: into.get(to) ?? null,
      }));
  const unaligned = rows.filter((r) => !r.to).length;
  return (
    <div className="flex flex-col gap-2 text-sm" data-testid="merge-preview">
      <p>
        Merge into <span className="font-medium">{survivorId}</span>. Student answers
        move to these questions:
      </p>
      {!ready ? (
        <p className="text-muted" data-testid="merge-loading">
          Loading…
        </p>
      ) : (
        <>
          <table className="w-full max-w-sm text-left">
            <thead className="text-muted">
              <tr>
                <th className="font-normal">This test</th>
                <th className="font-normal">Existing test</th>
              </tr>
            </thead>
            <tbody className="max-h-64 overflow-y-auto">
              {rows.map((r, i) => (
                <tr
                  key={r.q?.id ?? i}
                  data-testid="merge-row"
                  data-from={r.q?.id ?? ""}
                  data-to={r.to?.id ?? ""}
                  className={r.to ? "" : "text-danger"}
                >
                  <td>{r.q ? `Q${r.q.printed_number}` : "?"}</td>
                  <td>
                    {r.to ? `Q${r.to.printed_number}` : "not aligned (stays ungraded)"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p
            className="text-muted"
            data-testid="merge-summary"
            data-aligned={rows.length - unaligned}
            data-unaligned={unaligned}
          >
            {rows.length - unaligned} aligned, {unaligned} not aligned. Graded
            attempts are graded again.
          </p>
        </>
      )}
      <div className="flex gap-2">
        <button
          type="button"
          data-testid="review-merge-confirm"
          disabled={busy || !ready}
          onClick={onConfirm}
          className={primary}
        >
          Merge
        </button>
        <button
          type="button"
          data-testid="review-merge-cancel"
          onClick={onCancel}
          className={secondary}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

/** The test and attempt the item concerns (loaded per item). */
export function allQuestions(test: Test | null): Question[] {
  return (
    test?.content.sections.flatMap((s) =>
      s.groups.flatMap((g) => g.questions),
    ) ?? []
  );
}

const primary =
  "rounded-button bg-accent px-3 py-1 text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover disabled:opacity-50";
const secondary = "rounded-button border border-border px-3 py-1 hover:bg-hover";
