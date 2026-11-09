/**
 * Step 22.1.5 (R22.1.5.9, part 1) on a replay sidecar of its own: unreadable text (PRD D25) is
 * fixed on the test page itself (PRD D27). There is no Review panel.
 *
 * The replay folder holds the synthetic `unreadable/filled` scenario (`sidecar/tests/replay/
 * make_unreadable.py`): a 3-page test with `???` on pages 1 and 3.
 *
 * The thread's Test workspace shows the test as one editable page with the `???` marked and a note
 * per page. Replacing page 1's `???` and saving (Ctrl+S) closes that note, lowers the sidebar mark
 * and puts the words into `GET /tests/{id}`. A line the app cannot read shows its error at its line.
 * Headless screenshots (decision 6), light only, go to the gitignored `test-results/`.
 */
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { sidecarApi, startExtract, waitRunDone } from "./seed";
import { CASSETTE_ROOT, scenarioReplayFolder, startSidecar, type Sidecar } from "./sidecar";
import { settle } from "./settle";

const FILLED = join(CASSETTE_ROOT, "unreadable", "filled");

interface Item {
  id: string;
  kind: string;
  status: string;
  proposal: { page_no?: number };
}
interface TestDetail {
  content_text: string;
  review: Item[];
}
interface ThreadDetail {
  attempt: { id: string; test_id: string } | null;
}

let sidecar: Sidecar;
const saved = { port: process.env.ETACH_E2E_PORT, token: process.env.ETACH_E2E_TOKEN };

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  test.setTimeout(150_000);
  sidecar = await startSidecar(120_000, [], scenarioReplayFolder([FILLED]));
  process.env.ETACH_E2E_PORT = String(sidecar.port);
  process.env.ETACH_E2E_TOKEN = sidecar.token;
});

test.afterAll(async () => {
  process.env.ETACH_E2E_PORT = saved.port;
  process.env.ETACH_E2E_TOKEN = saved.token;
  await sidecar?.stop();
});

async function mark(page: Page, threadId: string): Promise<number> {
  const row = page.locator(`[data-testid="thread-item"][data-thread-id="${threadId}"]`);
  const m = row.getByTestId("unsure-mark");
  if ((await m.count()) === 0) return 0;
  return Number(/(\d+)/.exec((await m.textContent()) ?? "")?.[1] ?? 0);
}

/** The text with every `???` before the first "Page 2" marker replaced by `word`. */
function fixPageOne(text: string, word: string): string {
  const cut = text.search(/^— Page 2 —$/m);
  const head = cut < 0 ? text : text.slice(0, cut);
  return head.replaceAll("???", word) + (cut < 0 ? "" : text.slice(cut));
}

test("R22.1.5.9: replace a ??? on the test page, save; the spot and its count go", async ({ page }) => {
  test.setTimeout(300_000);
  const run = await startExtract(FILLED, null);
  await waitRunDone(run.runId);
  const detail = await sidecarApi<ThreadDetail>("GET", `/threads/${run.threadId}`);
  const testId = detail.attempt!.test_id;
  const before = await sidecarApi<TestDetail>("GET", `/tests/${testId}`);
  const pageOne = before.review.find((i) => i.kind === "unreadable_text" && i.proposal.page_no === 1)!;
  expect(pageOne, "page 1 raises an unreadable_text item").toBeTruthy();
  expect(before.content_text).toContain("???");

  await page.goto(`/#port=${sidecar.port}&token=${sidecar.token}`);
  await page.locator(`[data-testid="thread-item"][data-thread-id="${run.threadId}"]`).click();
  await expect.poll(() => mark(page, run.threadId)).toBeGreaterThan(0);
  const countBefore = await mark(page, run.threadId);
  await expect(page.getByRole("button", { name: /^Review/ })).toHaveCount(0); // no Review tab

  await expect(page.getByTestId("workspace")).toHaveAttribute("data-kind", "test"); // straight to work (22.3.2)
  const area = page.getByTestId("test-text");
  await expect(area).toHaveValue(before.content_text);
  await expect(page.getByTestId("unreadable-mark").first()).toBeVisible();
  const notes = page.getByTestId("test-note").filter({ hasText: "Page 1" });
  await expect(notes).toHaveCount(1);

  for (const scheme of ["light"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await settle(page);
    await page.screenshot({ path: `test-results/s7-test-page-${scheme}.png`, fullPage: true });
  }

  // A line the app cannot read: its error shows at its line, nothing is saved.
  await area.fill("stray words\n" + before.content_text);
  await page.getByTestId("text-save").click();
  await expect(page.getByTestId("text-error").first()).toHaveAttribute("data-line", "1");
  // R22.2.2.7: with two notes and an error, the editable text still starts above the fold at
  // 1280×720 (the help and the notes come after it).
  await expect(page.getByTestId("test-note")).toHaveCount(2);
  const viewport = page.viewportSize();
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.getByTestId("artifact-panel").locator(".overflow-y-auto").first().evaluate((el) => el.scrollTo(0, 0));
  const top = (await area.boundingBox())!.y;
  expect(top).toBeLessThan(720 - 100);
  await page.emulateMedia({ colorScheme: "light" });
  await settle(page);
  await page.screenshot({ path: "test-results/s7-test-page-1280x720.png" });
  if (viewport) await page.setViewportSize(viewport);
  for (const scheme of ["light"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await settle(page);
    await page.screenshot({ path: `test-results/s7-test-page-error-${scheme}.png`, fullPage: true });
  }

  // Replace page 1's ??? and save with Ctrl+S.
  await area.fill(fixPageOne(before.content_text, "clear"));
  const res = page.waitForResponse((r) => r.request().method() === "PATCH" && r.url().includes(`/tests/${testId}`));
  await area.press("Control+s");
  expect((await res).ok()).toBe(true);
  await expect(page.getByTestId("text-status")).toHaveText("Saved.");
  await expect(page.getByTestId("test-note").filter({ hasText: "Page 1" })).toHaveCount(0);
  await expect.poll(() => mark(page, run.threadId)).toBe(countBefore - 1);

  const after = await sidecarApi<TestDetail>("GET", `/tests/${testId}`);
  expect(after.content_text).toBe(fixPageOne(before.content_text, "clear"));
  expect(after.review.some((i) => i.id === pageOne.id)).toBe(false);
});
