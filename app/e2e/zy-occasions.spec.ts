/**
 * Step 22.3.7 (R22.3.7.3) on a replay sidecar of its own: Settings → Occasions adds an occasion,
 * the test's occasion chip picks it from the Occasion editor, and the Test name shows its short
 * name. Synthetic names only.
 */
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { sidecarApi, startExtract, waitRunDone } from "./seed";
import { CASSETTE_ROOT, scenarioReplayFolder, startSidecar, type Sidecar } from "./sidecar";

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

test("add an occasion in Settings, use it on a test, see it in the Test name (R22.3.7.3)", async ({ page }) => {
  test.setTimeout(300_000);
  const run = await startExtract(EXTRACT, null);
  await waitRunDone(run.runId);
  const testId = (await sidecarApi<ThreadDetail>("GET", `/threads/${run.threadId}`)).attempt!.test_id;

  await page.goto(`/#port=${sidecar.port}&token=${sidecar.token}`);
  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByTestId("settings-tabs").getByRole("tab", { name: "Test attributes" }).click(); // step 22.5.2
  await page.getByTestId("attributes-menu").getByRole("button", { name: "Occasions" }).click();
  const section = page.getByTestId("settings-occasions");
  await expect(section.getByTestId("occasion-row")).toHaveCount(10, { timeout: 30_000 });
  await section.getByTestId("occasion-new-label").fill("Synthetic weekly quiz");
  await section.getByTestId("occasion-new-short").fill("Synth Quiz");
  await section.getByTestId("occasion-new-short").press("Enter");
  await expect(section.getByTestId("occasion-row")).toHaveCount(11);
  await expect(section.getByTestId("occasion-label").last()).toHaveText("Synthetic weekly quiz");
  // one note above the list for the built-ins; each row keeps its width for the name (light)
  await expect(section.getByTestId("occasion-builtin-note")).toHaveText("Built-in occasions can be renamed but not deleted.");
  for (const scheme of ["light"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await section.getByTestId("occasion-builtin-note").scrollIntoViewIfNeeded();
    await page.screenshot({ path: `test-results/zy-occasions-${scheme}.png` });
  }
  await page.emulateMedia({ colorScheme: "light" });

  await page.getByRole("tab", { name: "Tests" }).click();
  await page.locator(`[data-testid="test-item"][data-test-id="${testId}"]`).click();
  const chip = page.locator('[data-testid="meta-chip"][data-field="occasion"]');
  await chip.click();
  await page.getByRole("option", { name: "Synthetic weekly quiz" }).click();
  await expect(chip).toContainText("Synthetic weekly quiz");
  await expect(page.getByTestId("test-title-name")).toContainText("Synth Quiz");

  const stored = await sidecarApi<{ meta: { occasion: string } }>("GET", `/tests/${testId}`);
  expect(stored.meta.occasion).toMatch(/^Custom:/);
  const bank = await sidecarApi<{ id: string; display_name: string }[]>("GET", "/tests?q=Synth%20Quiz");
  expect(bank.find((t) => t.id === testId)?.display_name).toContain("Synth Quiz");
});
