/**
 * Step 22.2.2 (R22.2.2.1, R22.2.2.8) on the replay sidecar: the workspace tabs. From the extracted
 * S1 thread's Test workspace, the tab list shows Test · Key · Student answers (no grade yet, so no
 * Report); a tab switches panel (no Back button), the photos follow the tab, and with
 * unsaved test text the leave dialog comes first ("Keep editing" keeps the text). Arrow keys move
 * along the tabs and Enter opens one.
 *
 * Runs after the earlier specs (file order, one worker) and reuses their S1 thread; alone, it seeds
 * one through the API (seed.ts).
 */
import { expect, test } from "@playwright/test";
import { connect } from "./drop";
import { seedExtractedS1 } from "./seed";

test("workspace tabs: switch panels, photos follow, unsaved text asks first (R22.2.2.1)", async ({ page }) => {
  test.setTimeout(300_000);
  const seeded = await seedExtractedS1();
  await connect(page);
  await page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`).click();
  // Straight to work (step 22.3.2): the thread opens its Test workspace.
  await expect(page.getByTestId("workspace")).toHaveAttribute("data-kind", "test", { timeout: 30_000 });

  const workspace = page.getByTestId("workspace");
  const tabs = workspace.getByRole("tablist", { name: "Workspace" });
  await expect(tabs.getByRole("tab")).toHaveText(["Test", "Key", "Student answers"]);
  await expect(tabs.getByRole("tab", { name: "Test" })).toHaveAttribute("aria-selected", "true");
  const area = workspace.getByTestId("test-text");
  await expect(area).toBeVisible();

  // Key: another panel, the same workspace, the test photos still there.
  await tabs.getByRole("tab", { name: "Key" }).click();
  await expect(workspace).toHaveAttribute("data-kind", "keys");
  await expect(page.getByTestId("conversation")).toHaveCount(0);
  await expect(workspace.getByTestId("photo-viewer")).toBeVisible();

  // Student answers by keyboard: the attempt's photos.
  const keyTab = tabs.getByRole("tab", { name: "Key" });
  await expect(keyTab).toBeFocused();
  await keyTab.press("ArrowRight");
  await expect(tabs.getByRole("tab", { name: "Student answers" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(workspace).toHaveAttribute("data-kind", "answers");
  await expect(workspace.getByTestId("answers-panel")).toBeVisible();
  await expect(workspace.getByTestId("photo-viewer")).toBeVisible();
  await expect(workspace.getByTestId("photo-status")).toHaveText(/^Page 1 of \d+$/);

  // Back on Test with unsaved text: the leave dialog first; Keep editing keeps the text.
  await tabs.getByRole("tab", { name: "Test" }).click();
  await expect(area).toBeVisible();
  const original = await area.inputValue();
  await area.fill(original + "\nunsaved line");
  await tabs.getByRole("tab", { name: "Key" }).click();
  const dialog = page.getByTestId("confirm-dialog");
  await expect(dialog).toContainText("Leave without saving?");
  await dialog.getByRole("button", { name: "Keep editing" }).click();
  await expect(workspace).toHaveAttribute("data-kind", "test");
  await expect(area).toHaveValue(original + "\nunsaved line");
  await expect(area).toBeFocused();
  await page.screenshot({ path: "test-results/s11-tabs.png" });

  // Discard: the Key opens; nothing was saved.
  await tabs.getByRole("tab", { name: "Key" }).click();
  await page.getByTestId("confirm-dialog").getByRole("button", { name: "Discard changes" }).click();
  await expect(workspace).toHaveAttribute("data-kind", "keys");
  await expect(workspace.getByTestId("workspace-back")).toHaveCount(0); // the thread's own workspace (22.3.2)
});
