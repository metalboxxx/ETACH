/**
 * R15.4: S1 (replay). Drop the 3 S1 pages → reorder + rotate → Run → the running indicator shows
 * the stage from SSE → Stop mid-run → Resume → done → the extraction card appears.
 * R22.1.3.6: during the run the indicator and the thread show the progress bar (a stage in plain
 * words, never a node name, and a percent); at run.done both bars go.
 *
 * The pages are the committed stand-in PNGs of sidecar/tests/cassettes/s1 (named in its
 * input.json), the same inputs the sidecar's S1 replay tests and e2e-shell use; the real photos
 * stay in the gitignored fixtures/. Replay matches calls by page number, not by image bytes.
 * global-setup.ts slows each replayed call (`--replay-delay-ms`) so the run can be stopped.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { connect, dropFiles } from "./drop";
import { CASSETTES } from "./sidecar";

/** A stage from SSE or the seeded progress, not the "Starting…" placeholder. */
const STEP_NAME = /^(?!Starting…$).+/;
/**
 * llm-design §2's extract stages; the count is optional: "Reading the test · page 2 of 3" (the page
 * being read) or, for a second pass, "Reading the test · Checking page 2 again".
 */
const STAGE_TEXT = /^(Preparing the photos|Reading the key|Reading the test|Reading the answers|Saving)( · (\w+ \d+ of \d+|Checking \w+ \d+ again))?$/;

test("S1 replay: reorder, rotate, Run, stage and progress bar, Stop, Resume, done", async ({ page }) => {
  test.setTimeout(180_000);
  const manifest = JSON.parse(readFileSync(join(CASSETTES, "input.json"), "utf8")) as {
    pages: { stand_in: string }[];
  };
  const pages = manifest.pages.map((p) => join(CASSETTES, p.stand_in));
  expect(pages).toHaveLength(3);

  await connect(page);
  await expect(page.getByRole("tab", { name: "Chats" })).toBeVisible();
  await expect(page.getByTestId("connection-notice")).toHaveCount(0);
  await expect(page.getByTestId("running-indicator")).toHaveCount(0);

  await dropFiles(page, pages);
  const thumbs = page.getByTestId("photo-check-card").getByTestId("photo-thumb");
  await expect(thumbs).toHaveCount(3);
  const before = await thumbs.evaluateAll((els) => els.map((e) => e.getAttribute("data-file-id")));

  // Reorder: drag page 1 onto page 3.
  const dt = await page.evaluateHandle(() => new DataTransfer());
  await thumbs.nth(0).dispatchEvent("dragstart", { dataTransfer: dt });
  await thumbs.nth(2).dispatchEvent("dragover", { dataTransfer: dt });
  await thumbs.nth(2).dispatchEvent("drop", { dataTransfer: dt });
  await thumbs.nth(0).dispatchEvent("dragend", { dataTransfer: dt });
  await expect
    .poll(() => thumbs.evaluateAll((els) => els.map((e) => e.getAttribute("data-file-id"))))
    .toEqual([before[1], before[2], before[0]]);

  // Rotate the (new) first page once.
  await page.getByTestId("photo-thumb").first().getByRole("button", { name: "Rotate page 1 90°" }).click();
  await expect(thumbs.nth(0)).toHaveAttribute("data-rotation", "90");

  // R22.3.1.1: double-click opens the full-size view with its rotation; → moves; Esc closes.
  await thumbs.nth(0).locator("img").dblclick();
  const full = page.getByRole("dialog", { name: /Page 1 of 3/ });
  await expect(full).toBeVisible();
  await expect(full.getByTestId("photo-full-img")).toHaveAttribute("data-rotation", "90");
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("dialog", { name: /Page 2 of 3/ })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("photo-full-view")).toHaveCount(0);
  await expect(thumbs.nth(1).getByTestId("photo-expand")).toBeFocused();
  await thumbs.nth(0).getByTestId("photo-expand").click();
  await expect(page.getByRole("dialog", { name: /Page 1 of 3/ })).toBeVisible();
  await page.getByTestId("photo-full-close").click();
  await expect(thumbs.nth(0).getByTestId("photo-expand")).toBeFocused();

  await page.getByTestId("photo-run").click();
  await expect(page.getByTestId("photo-check-card")).toHaveCount(0);

  // The indicator shows a step name from SSE (not the placeholder), and the lid note.
  const indicator = page.getByTestId("running-indicator");
  await expect(indicator).toBeVisible();
  const step = indicator.getByTestId("run-step");
  await expect(step).toHaveText(STEP_NAME, { timeout: 30_000 });
  await expect(indicator.getByTestId("keep-lid-open")).toBeVisible();

  // R22.1.3.6: the progress bar in the indicator and in the running thread.
  const bar = indicator.getByRole("progressbar", { name: "Run progress" });
  await expect(bar).toBeVisible();
  await expect(step).toHaveText(STAGE_TEXT);
  const threadRun = page.getByTestId("thread-run");
  await expect(threadRun).toBeVisible();
  await expect(threadRun.getByRole("progressbar", { name: "Run progress" })).toBeVisible();
  await expect(threadRun.getByTestId("run-step")).toHaveText(STAGE_TEXT);
  await expect(bar).toHaveAttribute("aria-valuenow", /^\d+$/);
  const html = await page.content();
  for (const node of ["transcribe_page", "read_answers_page", "prepare_pages", "read_key_pages"]) {
    expect(html).not.toContain(node);
  }

  // Stop mid-run.
  await indicator.getByRole("button", { name: "Stop" }).click();
  const paused = indicator.getByTestId("run-paused");
  await expect(paused).toBeVisible({ timeout: 60_000 });
  await expect(paused).toContainText("Stopped");
  await expect(page.locator('[data-testid="message"][data-kind="run_card"]')).toHaveCount(0);

  // Resume → done.
  await paused.getByRole("button", { name: "Resume" }).click();
  await expect(page.getByTestId("running-indicator")).toHaveCount(0, { timeout: 120_000 });
  await expect(page.getByTestId("running-slot")).toBeEmpty();
  await expect(page.getByTestId("thread-run")).toHaveCount(0);
  await expect(page.getByRole("progressbar")).toHaveCount(0);

  // Straight to work (step 22.3.2, R22.3.2.1): at run.done the thread's Test workspace appears in
  // place of the start screen; and the in-app toast.
  await expect(page.getByTestId("workspace")).toHaveAttribute("data-kind", "test", { timeout: 30_000 });
  await expect(page.getByTestId("conversation")).toHaveCount(0);
  await expect(page.getByTestId("toast")).toHaveAttribute("data-kind", "done");
});
