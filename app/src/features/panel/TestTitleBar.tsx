/**
 * The title bar of a test opened from the Tests tab (step 22.5.1, comment 1, D1): the same bar as
 * a thread's own test (`ThreadBanner`), with the test's name (`useTestName`, the name the Tests
 * list shows). It reloads when `refreshKey` changes, so a renamed test shows its new name.
 */
import type { ApiClient } from "@/api/client";
import { useTestName } from "@/hooks/useTestName";

export function TestTitleBar({ api, testId, refreshKey = 0 }: { api: ApiClient; testId: string; refreshKey?: number }) {
  const name = useTestName(api, testId, refreshKey);
  return (
    <div data-testid="test-title-bar" className="no-print flex flex-col gap-2 px-4 py-2 text-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h1 data-testid="test-bar-title" className="font-serif text-base text-text">
          {/* While loading, a blank line keeps the bar's height; without the test, its id. */}
          {name === undefined ? "\u00a0" : (name ?? testId)}
        </h1>
      </div>
    </div>
  );
}
