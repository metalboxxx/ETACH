/**
 * Step 22.4.2 (R22.4.2.4) on a replay sidecar of its own: Settings → Schools adds schools; a test's
 * School chip lists every school without typing, filters as the teacher types, picks with ↓/Enter,
 * and a new name typed there joins the list. Light screenshots of the Settings tabs.
 * Synthetic names only.
 */
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { sidecarApi, startExtract, waitRunDone } from "./seed";
import { CASSETTE_ROOT, scenarioReplayFolder, startSidecar, type Sidecar } from "./sidecar";
import { settle } from "./settle";

const EXTRACT = join(CASSETTE_ROOT, "s1-seeded", "extract");

interface ThreadDetail {
  attempt: { id: string; test_id: string } | null;
}

let sidecar: Sidecar;
const saved = { port: process.env.ETACH_E2E_PORT, token: process.env.ETACH_E2E_TOKEN };

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  test.setTimeout(150_000);
  sidecar = await startSidecar(120_000, [], scenarioReplayFolder([EXTRACT]));
  process.env.ETACH_E2E_PORT = String(sidecar.port);
  process.env.ETACH_E2E_TOKEN = sidecar.token;
});

test.afterAll(async () => {
  process.env.ETACH_E2E_PORT = saved.port;
  process.env.ETACH_E2E_TOKEN = saved.token;
  await sidecar?.stop();
});

test("Settings → Schools, and the School chip picks from the list (R22.4.2.4)", async ({ page }) => {
  test.setTimeout(300_000);
  const run = await startExtract(EXTRACT, null);
  await waitRunDone(run.runId);
  const testId = (await sidecarApi<ThreadDetail>("GET", `/threads/${run.threadId}`)).attempt!.test_id;

  await page.goto(`/#port=${sidecar.port}&token=${sidecar.token}`);
  await page.getByRole("button", { name: "Settings" }).click();
  const tabs = page.getByTestId("settings-tabs");
  // Step 22.5.2 (comment 3): Schools is under Test attributes.
  await expect(tabs.getByRole("tab")).toHaveText(["General", "Models", "Test attributes"], { timeout: 30_000 });
  await expect(tabs.getByRole("tab", { name: "General" })).toHaveAttribute("aria-selected", "true");
  for (const scheme of ["light"] as const) {
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" }); // no colour transition mid-shot
    await settle(page);
    await page.screenshot({ path: `test-results/zz-settings-tabs-${scheme}.png` });
  }
  await page.emulateMedia({ colorScheme: "light" });

  // the keyboard reaches Schools: → twice from General, Enter, then Tab to Schools and Enter
  await tabs.getByRole("tab", { name: "General" }).focus();
  for (let i = 0; i < 2; i++) await page.keyboard.press("ArrowRight");
  await expect(tabs.getByRole("tab", { name: "Test attributes" })).toBeFocused();
  await page.keyboard.press("Enter");
  const schoolsItem = page.getByTestId("attributes-menu").getByRole("button", { name: "Schools" });
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await expect(schoolsItem).toBeFocused();
  await page.keyboard.press("Enter");
  const section = page.getByTestId("settings-schools");
  await expect(section).toBeVisible();
  const before = await section.getByTestId("school-row").count();
  for (const name of ["Trường Thử Nghiệm A", "Trường Thử Nghiệm B"]) {
    await section.getByTestId("school-new-name").fill(name);
    await section.getByTestId("school-new-name").press("Enter");
    await expect(section.getByTestId("school-name").last()).toHaveText(name);
  }
  await expect(section.getByTestId("school-row")).toHaveCount(before + 2);
  for (const scheme of ["light"] as const) {
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" }); // no colour transition mid-shot
    await page.screenshot({ path: `test-results/zz-settings-schools-${scheme}.png` });
  }
  await page.emulateMedia({ colorScheme: "light" });

  await page.getByRole("tab", { name: "Tests" }).click();
  await page.locator(`[data-testid="test-item"][data-test-id="${testId}"]`).click();
  const chip = page.locator('[data-testid="meta-chip"][data-field="school"]');
  await chip.click();
  const box = page.locator('[data-testid="meta-chip-input"][data-field="school"]');
  await expect(box).toHaveAttribute("role", "combobox");
  // the whole list without typing
  const options = page.getByTestId("school-option");
  await expect(options).toHaveCount(before + 2);
  await expect(options.filter({ hasText: "Trường Thử Nghiệm A" })).toHaveCount(1);
  await page.screenshot({ path: "test-results/zz-school-chip-open.png" });
  // typing filters; ↓ then Enter picks
  await box.fill("nghiệm b");
  await expect(options).toHaveText(["Trường Thử Nghiệm B"]);
  await box.press("ArrowDown");
  await box.press("Enter");
  await expect(chip).toContainText("Trường Thử Nghiệm B");
  await expect.poll(async () => (await sidecarApi<{ meta: { school: string | null } }>("GET", `/tests/${testId}`)).meta.school).toBe(
    "Trường Thử Nghiệm B",
  );
  await expect(page.getByTestId("test-title-name")).toContainText("Trường Thử Nghiệm B");

  // Esc closes the field without a change
  await chip.click();
  await box.press("Escape");
  await expect(chip).toContainText("Trường Thử Nghiệm B");

  // a new name typed on the chip joins the list
  await chip.click();
  await box.fill("Trường Mới Tổng Hợp");
  await expect(options).toHaveCount(0);
  await box.press("Enter");
  await expect(chip).toContainText("Trường Mới Tổng Hợp");
  await expect
    .poll(async () => (await sidecarApi<{ name: string }[]>("GET", "/schools")).map((s) => s.name))
    .toContain("Trường Mới Tổng Hợp");
  await chip.click();
  await expect(options.filter({ hasText: "Trường Mới Tổng Hợp" })).toHaveCount(1);
  await box.press("Escape");
});
