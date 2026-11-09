/**
 * Step 16 part A on the replay sidecar: the extraction card of an extracted S1 thread, the test
 * panel (print view) and the answers panel. R16.6: an override in the answers panel sets
 * `answers.teacher_override` (checked via `GET /attempts/{id}`), and "Confirm blank" stores "".
 *
 * Step 22.1.4 (R22.1.4.7): the panels open as a workspace in the conversation's place. Test from
 * the card shows the photo viewer and a page image loads (step 22.5.1: no Back button; the
 * sidebar is the way out).
 *
 * Runs after s1-run.spec.ts (file order, one worker) and reuses its thread; alone, it seeds one
 * through the API (seed.ts).
 */
import { expect, test } from "@playwright/test";
import { connect } from "./drop";
import { seedExtractedS1, sidecarApi } from "./seed";

const PLACEHOLDER = /^\[Hình: files\/[0-9a-f]{2}\/[0-9a-f]{64}\.\w+ · trang \d+\]$/;

interface AttemptDetail {
  answers: { question_id: string; teacher_override: string | null }[];
}

test("extraction card → test workspace with photos (print view) → back → answers override (R16.6, R22.1.4.7)", async ({
  page,
}) => {
  test.setTimeout(300_000);
  const seeded = await seedExtractedS1();

  await connect(page);
  await page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`).click();

  // Straight to work (step 22.3.2, D2): the extracted thread opens its Test workspace, with the
  // student chip and Grade on it; no conversation, no extraction card.
  const workspace = page.getByTestId("workspace");
  await expect(workspace).toHaveAttribute("data-kind", "test", { timeout: 30_000 });
  await expect(page.getByTestId("extraction-card")).toHaveCount(0);
  await expect(workspace.getByTestId("student-chip")).toBeVisible();
  await expect(workspace.getByTestId("grade-answers")).toBeVisible();

  const panel = workspace.getByTestId("artifact-panel");
  await expect(panel.getByTestId("test-text")).toBeVisible();
  await expect(page.getByTestId("conversation")).toHaveCount(0);
  const viewer = workspace.getByTestId("photo-viewer");
  await expect(viewer).toBeVisible();
  await expect(viewer.getByTestId("photo-status")).toHaveText(/^Page 1 of \d+$/);
  const image = viewer.getByTestId("photo-image");
  await expect(image).toBeVisible();
  await expect.poll(() => image.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
  // Step 22.5.2 (D7): "# " headings with no points; the value of a question is under the title.
  await expect(panel.getByTestId("test-text")).toHaveValue(/^# /m);
  expect(await panel.getByTestId("test-text").inputValue()).not.toMatch(/\bpoints?\b/i);
  await expect(panel.getByTestId("test-title-details")).toHaveText(/10 points · \d+(\.\d{1,2})? each$/);
  await expect(panel.getByTestId("meta-chip").first()).toBeVisible();
  await page.emulateMedia({ media: "print" });
  await expect(page.locator("nav").first()).toBeHidden();
  await expect(workspace.getByTestId("workspace-bar")).toBeHidden();
  await expect(workspace.getByTestId("workspace-photos")).toBeHidden();
  await expect(panel.getByTestId("test-toolbar")).toBeHidden();
  await expect(panel.getByTestId("test-text")).toBeVisible();
  for (const text of await panel.getByTestId("picture-placeholder").allTextContents()) {
    expect(text).toMatch(PLACEHOLDER);
  }
  await page.emulateMedia({ media: "screen" });

  // The answers workspace (its tab): override one answer, confirm another as blank.
  await workspace.getByRole("tab", { name: "Student answers" }).click();
  await expect(workspace.getByTestId("photo-viewer")).toBeVisible();
  const rows = panel.getByTestId("answer-row");
  await expect(rows.first()).toBeVisible();
  expect(await rows.count()).toBeGreaterThanOrEqual(2);
  const first = rows.nth(0);
  const second = rows.nth(1);
  const q1 = (await first.getAttribute("data-question-id"))!;
  const q2 = (await second.getAttribute("data-question-id"))!;

  await first.getByTestId("answer-edit").click();
  await panel.getByTestId("answer-input").fill("e2e override");
  await panel.getByTestId("answer-save").click();
  await expect(first).toHaveAttribute("data-override", "value");
  await expect(first.getByTestId("answer-value")).toHaveText("e2e override");

  await second.getByTestId("answer-edit").click();
  await panel.getByTestId("answer-confirm-blank").click();
  await expect(second).toHaveAttribute("data-override", "blank");

  const detail = await sidecarApi<AttemptDetail>("GET", `/attempts/${seeded.attemptId}`);
  const byId = new Map(detail.answers.map((a) => [a.question_id, a.teacher_override]));
  expect(byId.get(q1)).toBe("e2e override");
  expect(byId.get(q2)).toBe("");
});
