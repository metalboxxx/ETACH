/**
 * Step 22.1.1 (the teacher's app review, small fixes) on the replay sidecar:
 * - R22.1.1.3: typing an occasion and leaving the field → PATCH /tests/{id} → GET returns it.
 * - R22.1.1.2: Print in the test panel opens a print view with a visible Back (hidden on paper)
 *   that returns to the panel. The print window itself is stubbed (headless has none to close).
 * - R22.1.1.1: the student picker closes on a click outside and on Escape.
 * - R22.1.1.4: create a student from a typed name, then edit the name; the search finds it.
 * - R22.1.1.5 / R22.1.1.6 / R22.1.1.7: the thread shows student · test, the card heading names
 *   them, and the thread can be renamed from the list.
 *
 * Runs after s7 (file order, one worker) and reuses the S1 thread (seed.ts).
 */
import { expect, test } from "@playwright/test";
import { connect } from "./drop";
import { seedExtractedS1, sidecarApi } from "./seed";

interface TestDetail {
  meta: { occasion: string };
}
interface ThreadDetail {
  thread: { title: string };
  shown_title: string;
  test_display_name: string | null;
  student: { id: string; full_name: string } | null;
}

test("step 22.1.1: occasion, print view, student picker, titles and rename", async ({ page }) => {
  test.setTimeout(300_000);
  const seeded = await seedExtractedS1();
  // The seeded thread keeps its default title (no spec renames it before this one). Renaming it
  // to "New thread" no longer restores the default: that title is kept as typed (R22.1.5.8).

  await page.addInitScript(() => {
    (window as unknown as { __prints: number }).__prints = 0;
    window.print = () => {
      (window as unknown as { __prints: number }).__prints += 1;
    };
  });
  await connect(page);
  const item = page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`);
  await item.click();
  // Straight to work (step 22.3.2): the thread opens its workspace; the student chip and the
  // thread's name are in the banner under the tab row (the extraction card is gone).
  const card = page.getByTestId("thread-banner");
  await expect(card).toBeVisible({ timeout: 30_000 });

  // R22.1.1.7 / R22.1.1.6: the heading and the thread name carry the test's display name.
  let detail = await sidecarApi<ThreadDetail>("GET", `/threads/${seeded.threadId}`);
  let testName = detail.test_display_name!;
  expect(testName).toBeTruthy();
  await expect(page.getByTestId("thread-title")).toHaveText(detail.shown_title);
  await expect(item.locator("span").first()).toHaveText(detail.shown_title);

  // R22.1.1.3: the Occasion field takes typed words. The test is opened from the Tests tab: this
  // thread's card may name a test an earlier spec merged away (s3), and its [Test] opens that one.
  await page.getByRole("tab", { name: "Tests" }).click();
  await page.locator(`[data-testid="test-item"][data-test-id="${seeded.testId}"]`).click();
  const panel = page.getByTestId("artifact-panel");
  await panel.locator('[data-testid="meta-chip"][data-field="occasion"]').click();
  const occ = panel.getByTestId("meta-chip-input");
  await occ.fill("Giữa kỳ 1");
  await occ.press("Tab"); // leave the field
  await expect(panel.locator('[data-testid="meta-chip"][data-field="occasion"]')).toContainText("Giữa kỳ 1");
  await expect(panel.getByRole("alert")).toHaveCount(0);
  const saved = await sidecarApi<TestDetail>("GET", `/tests/${seeded.testId}`);
  expect(saved.meta.occasion).toBe("Other:Giữa kỳ 1");
  testName = (await sidecarApi<ThreadDetail>("GET", `/threads/${seeded.threadId}`)).test_display_name!;
  expect(testName).toContain("Giữa kỳ 1"); // the new occasion is in the test's name (decision C: no "Other:")

  // R22.1.1.2: Print → print view with Back; the bar is not on paper; Back returns to the panel.
  await panel.getByTestId("test-print").click();
  const back = page.getByRole("button", { name: "Back to test" });
  await expect(back).toBeVisible();
  await expect.poll(() => page.evaluate(() => (window as unknown as { __prints: number }).__prints)).toBe(1);
  await expect(page.locator("nav").first()).toBeHidden();
  await page.emulateMedia({ media: "print" });
  await expect(page.getByTestId("print-bar")).toBeHidden();
  await expect(page.getByTestId("clean-test")).toBeVisible();
  await page.emulateMedia({ media: "screen" });
  await back.click();
  await expect(page.getByTestId("workspace-bar")).toBeVisible();
  await expect(page.getByTestId("test-text")).toBeVisible();
  await expect(page.locator("nav").first()).toBeVisible();
  await expect(panel.getByTestId("test-print")).toBeFocused(); // R22.1.4.5
  // The test opened as a workspace (step 22.1.4): Back returns to the thread.
  await page.getByRole("tab", { name: "Chats" }).click();
  await item.click(); // back to the thread's own workspace
  await expect(card).toBeVisible();

  // R22.1.1.1: the student picker closes on a click outside and on Escape.
  const chip = card.getByTestId("student-chip");
  await chip.click();
  await expect(page.getByTestId("student-picker")).toBeVisible();
  await page.getByTestId("student-search").click(); // inside: stays open
  await expect(page.getByTestId("student-picker")).toBeVisible();
  await page.getByTestId("thread-title").click(); // outside
  await expect(page.getByTestId("student-picker")).toBeHidden();
  await chip.click();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("student-picker")).toBeHidden();
  await expect(chip).toBeFocused();

  // R22.1.1.4: create from a typed name, then edit the name.
  await chip.click();
  await page.getByTestId("student-search").fill("Phạm Thu Hà");
  await page.getByTestId("student-create-typed").click();
  await expect(chip).toHaveText("Phạm Thu Hà");
  detail = await sidecarApi<ThreadDetail>("GET", `/threads/${seeded.threadId}`);
  expect(detail.student?.full_name).toBe("Phạm Thu Hà");
  await expect(page.getByTestId("thread-title")).toContainText("Phạm Thu Hà");
  await expect(item.locator("span").first()).toHaveText(`${testName} · Phạm Thu Hà`);

  await chip.click();
  await page.getByTestId("student-name-input").fill("Phạm Thu Hằng");
  await page.getByTestId("student-name-save").click();
  await expect(chip).toHaveText("Phạm Thu Hằng");
  await expect(item.locator("span").first()).toHaveText(`${testName} · Phạm Thu Hằng`);
  const found = await sidecarApi<{ id: string }[]>("GET", `/students?q=${encodeURIComponent("pham thu hang")}`);
  expect(found.map((s) => s.id)).toContain(detail.student!.id);

  // R22.1.1.5: rename from the row's menu button; Enter saves.
  await page.getByRole("button", { name: `More actions for ${testName} · Phạm Thu Hằng` }).click();
  await page.getByRole("menuitem", { name: "Rename" }).click();
  const name = page.getByRole("textbox", { name: "Thread name" });
  await name.fill("Hằng – giữa kỳ 1");
  await name.press("Enter");
  await expect(item.locator("span").first()).toHaveText("Hằng – giữa kỳ 1");
  detail = await sidecarApi<ThreadDetail>("GET", `/threads/${seeded.threadId}`);
  expect(detail.thread.title).toBe("Hằng – giữa kỳ 1");

  // Right-click opens the same menu; Escape cancels.
  await item.click({ button: "right" });
  await page.getByRole("menuitem", { name: "Rename" }).click();
  await page.getByRole("textbox", { name: "Thread name" }).fill("not this");
  await page.keyboard.press("Escape");
  await expect(item.locator("span").first()).toHaveText("Hằng – giữa kỳ 1");
});
