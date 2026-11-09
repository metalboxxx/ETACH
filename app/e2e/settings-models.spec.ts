/**
 * Step 22.3.5 (R22.3.5.3, R22.3.5.4) on a replay sidecar of its own: `etach serve --replay` has no
 * Ollama, so `/models` runs on its in-memory fake model list (the role tags and the suggested
 * tags; a pull takes about 2 s). Nothing here talks to a real Ollama or the internet, and the
 * page makes no request to a non-loopback origin while the model manager lists, downloads,
 * cancels and deletes.
 *
 * Step 22.5.4b (R22.5.4.8, the part jsdom cannot measure): the Models tab shows the four role
 * pickers with their one-line descriptions; the names and descriptions meet WCAG 2.1 AA contrast
 * (light only, PRD §10.1 v8.12). Screenshots go to test-results/. Step 22.5.5b (R22.5.5.8): the descriptions
 * show only on hover or keyboard focus of the role name.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";
import { sidecarApi } from "./seed";
import { startSidecar, type Sidecar } from "./sidecar";
import { settle } from "./settle";

interface Inventory {
  models: { name: string; size: number; roles: string[] }[];
  roles: Record<string, string>;
  suggested: string[];
}

let sidecar: Sidecar;
const saved = { port: process.env.ETACH_E2E_PORT, token: process.env.ETACH_E2E_TOKEN };
const external: string[] = [];

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  test.setTimeout(150_000);
  sidecar = await startSidecar(120_000);
  process.env.ETACH_E2E_PORT = String(sidecar.port);
  process.env.ETACH_E2E_TOKEN = sidecar.token;
});

test.afterAll(async () => {
  process.env.ETACH_E2E_PORT = saved.port;
  process.env.ETACH_E2E_TOKEN = saved.token;
  await sidecar?.stop();
});

const LOOPBACK = new Set(["127.0.0.1", "localhost", "[::1]"]);

async function openSettings(page: Page) {
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (!["data:", "blob:"].includes(url.protocol) && !LOOPBACK.has(url.hostname)) external.push(req.url());
  });
  await page.goto(`/#port=${sidecar.port}&token=${sidecar.token}`);
  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByTestId("settings-tabs").getByRole("tab", { name: "Models" }).click(); // step 22.4.2
  await expect(page.getByTestId("model-manager")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("installed-model").first()).toBeVisible({ timeout: 30_000 });
}

test("the role combobox lists the installed models, filters, and flags a missing tag", async ({ page }) => {
  const inv = await sidecarApi<Inventory>("GET", "/models");
  await openSettings(page);
  const box = page.getByRole("combobox", { name: "Student answer reader" });
  await box.focus();
  const list = page.getByRole("listbox", { name: "Installed models for Student answer reader" });
  await expect(list.getByRole("option")).toHaveCount(inv.models.length);
  await box.fill("nuextract");
  await expect(list.getByRole("option")).toHaveCount(1);
  await box.press("ArrowDown");
  await box.press("Enter");
  await expect(box).toHaveValue(/nuextract/);
  await expect(page.locator('[data-testid="model-missing"][data-role="vision"]')).toHaveCount(0);
  await box.fill("e2e-missing:1b");
  await box.press("Escape");
  await expect(page.locator('[data-testid="model-missing"][data-role="vision"]')).toContainText("Not installed");
});

test("the model manager downloads with progress, cancels, and deletes with a confirm", async ({ page }) => {
  await openSettings(page);
  const inv = await sidecarApi<Inventory>("GET", "/models");
  const used = inv.models.find((m) => m.roles.length > 0)!;
  await expect(page.getByRole("button", { name: `Delete ${used.name}` })).toBeDisabled();

  // Download with progress.
  const field = page.getByLabel("Download a model");
  await field.fill("e2e-tiny:1b");
  await field.press("Enter");
  const row = page.locator('[data-testid="download-row"][data-model="e2e-tiny:1b"]');
  await expect(row.getByTestId("download-status")).toHaveText(/Downloading \d+%/, { timeout: 30_000 });
  await expect(row).toHaveAttribute("data-status", "success", { timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Delete e2e-tiny:1b" })).toBeVisible();

  // Cancel: the request closes and nothing is listed.
  await field.fill("e2e-big:70b");
  await field.press("Enter");
  const big = page.locator('[data-testid="download-row"][data-model="e2e-big:70b"]');
  await expect(big.getByTestId("download-status")).toHaveText(/Downloading \d+%/, { timeout: 30_000 });
  await page.getByRole("button", { name: "Cancel download of e2e-big:70b" }).click();
  await expect(big).toHaveAttribute("data-status", "cancelled");
  await page.waitForTimeout(2500); // longer than the fake pull
  const after = await sidecarApi<Inventory>("GET", "/models");
  expect(after.models.map((m) => m.name)).not.toContain("e2e-big:70b");

  // Delete with a confirm.
  await page.getByRole("button", { name: "Delete e2e-tiny:1b" }).click();
  await page.getByTestId("confirm-ok").click();
  await expect(page.getByRole("button", { name: "Delete e2e-tiny:1b" })).toHaveCount(0);

  expect(external, "requests to non-loopback origins").toEqual([]);
});

/** WCAG contrast of two computed CSS colours (`rgb(…)`), in the page (as in s13). */
async function contrast(page: Page, fg: string, bg: string): Promise<number> {
  return page.evaluate(
    ([a, b]) => {
      const lum = (c: string) => {
        const [r, g, bl] = (c.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number).map((v) => {
          const s = v / 255;
          return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * r! + 0.7152 * g! + 0.0722 * bl!;
      };
      const [hi, lo] = [lum(a!), lum(b!)].sort((x, y) => y - x);
      return (hi! + 0.05) / (lo! + 0.05);
    },
    [fg, bg],
  );
}

const color = (el: Locator) => el.evaluate((e) => getComputedStyle(e).color);
const background = (el: Locator) =>
  el.evaluate((e) => {
    for (let n: Element | null = e; n; n = n.parentElement) {
      const bg = getComputedStyle(n).backgroundColor;
      if (bg && bg !== "transparent" && !bg.startsWith("rgba(0, 0, 0, 0)")) return bg;
    }
    return "rgb(255, 255, 255)";
  });

for (const scheme of ["light"] as const) {
  test(`R22.5.4.8: the Models tab shows four named, described role pickers (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await openSettings(page);
    const panel = page.getByTestId("settings-tabpanel-models");
    const pickers = [
      ["Student answer reader", "Reads the student answers from the photos"],
      ["Grading", "Marks student answers and explains the mistakes"],
      ["Grading check", "Double-checks keys the AI wrote"],
      ["Extraction check", "Checks and fixes a reading of the pages"],
    ] as const;
    await expect(panel.getByTestId("role-model")).toHaveCount(4);
    for (const [name, description] of pickers) {
      const box = panel.getByRole("combobox", { name, exact: true });
      await expect(box).toBeVisible();
      await expect(box).toHaveAccessibleDescription(description);
    }
    // Step 22.5.5b (R22.5.5.8): the description is hidden until hover or keyboard focus on the name.
    const tips = panel.getByTestId("role-description");
    await expect(tips).toHaveCount(4);
    for (const tip of await tips.all()) await expect(tip).toBeHidden();
    await settle(page);
    await page.getByTestId("settings-models").screenshot({ path: `test-results/s22.5.5-models-tab-${scheme}.png`, animations: "disabled" });
    const names = panel.getByTestId("role-name");
    await names.nth(0).hover();
    await expect(tips.nth(0)).toBeVisible();
    await names.nth(1).focus();
    await expect(tips.nth(1)).toBeVisible();
    for (let i = 0; i < 4; i++) {
      await names.nth(i).focus();
      for (const text of [names.nth(i), tips.nth(i)]) {
        expect(await contrast(page, await color(text), await background(text)), `${scheme} contrast`).toBeGreaterThanOrEqual(4.5);
      }
    }
    await names.nth(0).focus();
    await settle(page);
    await page.getByTestId("settings-models").screenshot({ path: `test-results/s22.5.5-models-tab-tip-${scheme}.png`, animations: "disabled" });
    expect(external, "requests to non-loopback origins").toEqual([]);
  });
}
