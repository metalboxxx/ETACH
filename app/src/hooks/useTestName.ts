/**
 * A bank test's name (`testTitle`, the name the Tests list shows), from `GET /tests/{id}`
 * (step 22.5.1). `undefined` while loading, `null` when there is no id or the test could not be
 * read. It reloads when `refreshKey` changes, so a renamed test shows its new name.
 */
import { useEffect, useState } from "react";
import type { ApiClient } from "@/api/client";
import { testTitle } from "@/lib/testTitle";

export function useTestName(api: ApiClient, testId: string | null, refreshKey = 0): string | null | undefined {
  const [loaded, setLoaded] = useState<{ id: string; name: string | null } | null>(null);
  useEffect(() => {
    if (!testId) return;
    const ctrl = new AbortController();
    api
      .get("/tests/{id}", { path: { id: testId }, signal: ctrl.signal })
      .then((t) => setLoaded({ id: testId, name: testTitle(t.meta) }))
      .catch(() => {
        if (!ctrl.signal.aborted) setLoaded({ id: testId, name: null });
      });
    return () => ctrl.abort();
  }, [api, testId, refreshKey]);
  if (!testId) return null;
  return loaded?.id === testId ? loaded.name : undefined;
}
