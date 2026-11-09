/**
 * Review in place (PRD D27, data-model §5.3 v1.9, step 22.1.5): there is no Review queue. Each
 * unsure spot is shown where it belongs (the test page, the Answers and Key panels, the
 * extraction card, the chips) and settled there through `POST /review/{id}/resolve`
 * (`{action: accept | fix | skip, value}`; the Fix values are the ones in `domain/review.py`).
 */
import type { ApiClient, Schemas } from "@/api/client";

export type ReviewItem = Schemas["ReviewItem"];
export type ReviewKind = ReviewItem["kind"];
export type Resolution = Schemas["Resolution"];

export async function resolveItem(api: ApiClient, id: string, body: Resolution): Promise<void> {
  await api.post("/review/{id}/resolve", { path: { id }, body });
}

export const accept = (): Resolution => ({ action: "accept", value: null });
export const skip = (): Resolution => ({ action: "skip", value: null });
export const fix = (value: unknown): Resolution => ({ action: "fix", value });

/** The open items of `kind` (optionally for one attempt or question). */
export function itemsOf(
  items: readonly ReviewItem[] | null | undefined,
  kind: ReviewKind | ReviewKind[],
  where: { attemptId?: string | null; questionId?: string | null } = {},
): ReviewItem[] {
  const kinds = Array.isArray(kind) ? kind : [kind];
  return (items ?? []).filter(
    (i) =>
      i.status === "open" &&
      kinds.includes(i.kind) &&
      (where.attemptId === undefined || i.attempt_id === where.attemptId) &&
      (where.questionId === undefined || i.question_id === where.questionId),
  );
}

export function str(v: unknown): string | null {
  return typeof v === "string" ? v : typeof v === "number" ? String(v) : null;
}
