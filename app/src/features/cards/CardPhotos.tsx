/**
 * The photo thumbnails on the extraction card (step 22.1.4, comment 3: "I don't know where to see
 * the images I just put into the app").
 *
 * The thumbnails are the pages the run read: the attempt's pages for a filled test, else the
 * test's pages. A thumbnail opens its page in a workspace: the Test workspace when the test holds
 * that same photo at that page (the usual case: the test was made from these photos), else the
 * Answers workspace, whose photos are the attempt's (the test came from another student's paper).
 *
 * `useCardPhotos` also resolves a merged test: `GET /tests/{id}` of a merged-away test names the
 * test it was merged into (`merged_into`), which the card's Test and Key then open.
 */
import { useEffect, useState } from "react";
import type { ApiClient, Schemas } from "@/api/client";
import type { PanelView } from "@/features/panels/panelView";

export interface CardThumb {
  key: string;
  fileId: string;
  /** 1-based position in the workspace's photo list. */
  pageNo: number;
  opens: PanelView;
}

/** What the card loads: the test it opens, the photo thumbnails, and the test's open Review items
 *  (its own and its current attempts'; step 22.1.5 shows them in place). */
export interface CardData {
  testId: string | null;
  thumbs: CardThumb[];
  review: Schemas["ReviewItem"][];
}

/** Merges are short chains; this bounds a broken one. */
const MAX_MERGE_HOPS = 5;

export function useCardPhotos(
  api: ApiClient,
  cardTestId: string | null,
  attemptId: string | null,
  refreshKey = 0,
): CardData {
  const [state, setState] = useState<CardData>({ testId: null, thumbs: [], review: [] });
  useEffect(() => {
    if (!cardTestId) return;
    const ctrl = new AbortController();
    const signal = ctrl.signal;
    (async () => {
      let test: Schemas["TestWithPaths"] = await api.get("/tests/{id}", { path: { id: cardTestId }, signal });
      for (let hop = 0; test.merged_into && hop < MAX_MERGE_HOPS; hop++) {
        test = await api.get("/tests/{id}", { path: { id: test.merged_into }, signal });
      }
      const testFiles = new Map(test.pages.map((p) => [p.page_no, p.file_id]));
      const testId = test.id;
      let thumbs: CardThumb[];
      if (attemptId) {
        const attempt = await api.get("/attempts/{id}", { path: { id: attemptId }, signal });
        const pages = [...(attempt.pages ?? [])].sort((a, b) => a.page_no - b.page_no);
        thumbs = pages.map((p, i) => ({
          key: `p${p.page_no}`,
          fileId: p.file_id,
          pageNo: i + 1,
          opens:
            testFiles.get(p.page_no) === p.file_id
              ? { kind: "test", testId, page: i + 1 }
              : { kind: "answers", attemptId, testId, page: i + 1 },
        }));
      } else {
        thumbs = [...test.pages]
          .sort((a, b) => a.page_no - b.page_no)
          .map((p, i) => ({ key: `p${p.page_no}`, fileId: p.file_id, pageNo: i + 1, opens: { kind: "test", testId, page: i + 1 } }));
      }
      if (!signal.aborted) setState({ testId, thumbs, review: test.review ?? [] });
    })().catch(() => {
      /* aborted, offline, or the test is gone: the card shows no thumbnails */
    });
    return () => ctrl.abort();
  }, [api, cardTestId, attemptId, refreshKey]);
  return cardTestId ? state : { testId: null, thumbs: [], review: [] };
}

export function CardPhotos({
  api,
  thumbs,
  onOpen,
}: {
  api: ApiClient;
  thumbs: readonly CardThumb[];
  onOpen?: (view: PanelView) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-muted">
        {thumbs.length === 1 ? "Your photo" : `Your photos (${thumbs.length} pages)`}. Click a page to check it beside
        the {thumbs.every((t) => t.opens.kind === "test") ? "test" : "student answers"}.
      </p>
      <ul className="flex flex-wrap gap-2" data-testid="card-photos">
        {thumbs.map((t) => (
          <li key={t.key}>
            <Thumb api={api} thumb={t} onOpen={onOpen} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function Thumb({ api, thumb, onOpen }: { api: ApiClient; thumb: CardThumb; onOpen?: (view: PanelView) => void }) {
  const [broken, setBroken] = useState(false);
  const beside = thumb.opens.kind === "test" ? "the test" : "the student answers";
  return (
    <button
      type="button"
      data-testid="card-photo"
      data-page={thumb.pageNo}
      aria-label={`Page ${thumb.pageNo}: open it beside ${beside}`}
      onClick={() => onOpen?.(thumb.opens)}
      className="group relative flex h-24 w-[4.5rem] items-center justify-center overflow-hidden rounded-button border border-border bg-sidebar hover:border-accent-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
    >
      {broken ? (
        <span className="px-1 text-center text-xs text-muted">No photo</span>
      ) : (
        <img
          src={api.fileUrl(thumb.fileId, { thumb: true })}
          alt=""
          draggable={false}
          onError={() => setBroken(true)}
          className="h-full w-full object-cover"
        />
      )}
      <span
        aria-hidden="true"
        className="absolute bottom-1 left-1 rounded-full border border-border bg-surface px-1 text-xs font-medium text-text"
      >
        {thumb.pageNo}
      </span>
    </button>
  );
}
