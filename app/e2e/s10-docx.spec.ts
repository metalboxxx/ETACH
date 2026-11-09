/**
 * Step 22.1.6 (R22.1.6.6) on the replay sidecar, synthetic data only: from the replayed S1 thread
 * the teacher saves the test and the key as Word; both files are in the E2E app folder's
 * `exports\`. Open folder is not clicked here (it needs the Tauri shell).
 */
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { connect } from "./drop";
import { seedExtractedS1 } from "./seed";

test("save the test and the key as Word into exports (R22.1.6.6)", async ({ page }) => {
  test.setTimeout(300_000);
  const dataDir = process.env.ETACH_E2E_DATA;
  if (!dataDir) throw new Error("ETACH_E2E_DATA is not set (global-setup)");
  const exports = join(dataDir, "exports");
  const before = existsSync(exports) ? new Set(readdirSync(exports)) : new Set<string>();

  const seeded = await seedExtractedS1();
  await page.setViewportSize({ width: 1280, height: 720 });
  await connect(page);
  await page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`).click();
  // Straight to work (step 22.3.2): the thread opens its Test workspace; Key is a tab.
  const workspace = page.getByTestId("workspace");
  await expect(workspace).toHaveAttribute("data-kind", "test", { timeout: 30_000 });

  const saved: string[] = [];
  for (const [open, save] of [
    ["Test", "test-save-docx"],
    ["Key", "key-save-docx"],
  ] as const) {
    await workspace.getByRole("tab", { name: open }).click();
    await expect(workspace).toBeVisible();
    const response = page.waitForResponse((r) => r.url().includes("/export") && r.request().method() === "POST");
    await workspace.getByTestId(save).click();
    const body = (await (await response).json()) as { path: string; file_name: string };
    await expect(workspace.getByTestId("save-docx-saved")).toContainText(`Saved ${body.file_name}`);
    await expect(workspace.getByRole("button", { name: "Open folder" })).toBeVisible();
    saved.push(body.file_name);
  }

  expect(saved[0]).toMatch(/ - Test( \(\d+\))?\.docx$/);
  expect(saved[1]).toMatch(/ - Key( \(\d+\))?\.docx$/);
  const added = readdirSync(exports).filter((f) => !before.has(f));
  expect(added.sort()).toEqual([...saved].sort());
});
