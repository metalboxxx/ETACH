/**
 * The original photos shown on the right of a workspace (PRD §10, v4.13; step 22.1.4).
 *
 * - Test and Key: the test's pages (`GET /tests/{id}` `pages`), then its key pages (`key_pages`,
 *   labelled "Key"). `key_pages` is the key photos the test was extracted with (data-model
 *   v1.12, step 22.2.5); tests extracted before that have none.
 * - Answers and Report: the attempt's pages (`GET /attempts/{id}` `pages`).
 *
 * Every stored page is the prepared page the run read: the photo check's rotation is already
 * applied to the file (`graphs/extract.py` `prepare_pages`), so the viewer shows it as stored and
 * must not turn it again. `rotation` is kept for reference only.
 */
import { useEffect, useState } from "react";
import { type ApiClient, type Schemas } from "@/api/client";
import type { WorkspaceView } from "@/features/panels/panelView";
import { errorText } from "@/lib/errors";

export interface PhotoPage {
  /** Unique in the list (a file can appear as a test page and a key page). */
  key: string;
  fileId: string;
  /** The page number within its own list (test pages 1..n, key pages 1..k). */
  pageNo: number;
  isKey: boolean;
  /** The rotation the photo check applied (already in the stored file); `null` if unknown. */
  rotation: number | null;
}

type TestDetail = Schemas["TestWithPaths"];

export function testPhotos(test: Pick<TestDetail, "pages" | "key_pages">): PhotoPage[] {
  const byNo = (a: { page_no: number }, b: { page_no: number }) => a.page_no - b.page_no;
  return [
    ...[...test.pages].sort(byNo).map((p) => ({
      key: `p${p.page_no}`,
      fileId: p.file_id,
      pageNo: p.page_no,
      isKey: false,
      rotation: null,
    })),
    ...[...test.key_pages].sort(byNo).map((p) => ({
      key: `k${p.page_no}`,
      fileId: p.file_id,
      pageNo: p.page_no,
      isKey: true,
      rotation: null,
    })),
  ];
}

export function attemptPhotos(pages: readonly Schemas["AttemptPage"][]): PhotoPage[] {
  return [...pages]
    .sort((a, b) => a.page_no - b.page_no)
    .map((p) => ({ key: `p${p.page_no}`, fileId: p.file_id, pageNo: p.page_no, isKey: false, rotation: p.rotation }));
}

/** "Page 2", or "Key page 1" for a key photo. */
export function photoName(p: PhotoPage): string {
  return p.isKey ? `Key page ${p.pageNo}` : `Page ${p.pageNo}`;
}

export interface WorkspacePhotos {
  /** `null` while loading. */
  pages: PhotoPage[] | null;
  /** The test, for Test and Key (the Key workspace can show its text on the right). */
  test: TestDetail | null;
  error: string | null;
}

/** Loads the photos for a workspace: the test's for Test and Key, the attempt's for the others. */
export function useWorkspacePhotos(api: ApiClient, view: WorkspaceView): WorkspacePhotos {
  const fromTest = view.kind === "test" || view.kind === "keys";
  const id = fromTest ? view.testId : view.attemptId;
  const [state, setState] = useState<WorkspacePhotos & { id: string | null }>({
    id: null,
    pages: null,
    test: null,
    error: null,
  });
  useEffect(() => {
    const ctrl = new AbortController();
    const opts = { path: { id }, signal: ctrl.signal };
    const load = fromTest
      ? api.get("/tests/{id}", opts).then((t) => ({ pages: testPhotos(t), test: t }))
      : api.get("/attempts/{id}", opts).then((a) => ({ pages: attemptPhotos(a.pages ?? []), test: null }));
    load
      .then((got) => setState({ id, ...got, error: null }))
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return;
        setState({ id, pages: [], test: null, error: errorText(err) });
      });
    return () => ctrl.abort();
  }, [api, fromTest, id]);
  // While another id loads, show nothing from the previous one.
  return state.id === id ? state : { pages: null, test: null, error: null };
}
