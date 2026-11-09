/**
 * Step 20 part B on a replay sidecar of its own, started with `ETACH_FAKE_OLLAMA_PULL` (the fake
 * `ollama pull` stream: "pulling manifest", "downloading" 40/100 then 100/100, then `success`).
 *
 * R20.1 (E2E part): change the reasoning tag in Settings → `GET /settings` and
 * `<data>/models.toml` hold the new tag. (The sidecar `TEST` proves the next call uses it.)
 * R20.5: Download models → one row per configured model, progress from SSE
 * `models.pull_progress`, each row ends "ready".
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { sidecarApi } from "./seed";
import { startSidecar, type Sidecar } from "./sidecar";

interface Settings {
  data_folder: string;
  log_retention_days: number;
  roles: Record<string, { model: string }>;
}

let sidecar: Sidecar;
const saved = { port: process.env.ETACH_E2E_PORT, token: process.env.ETACH_E2E_TOKEN };

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  test.setTimeout(150_000);
  sidecar = await startSidecar(120_000, [], undefined, { ETACH_FAKE_OLLAMA_PULL: "300" });
  process.env.ETACH_E2E_PORT = String(sidecar.port);
  process.env.ETACH_E2E_TOKEN = sidecar.token;
});

test.afterAll(async () => {
  process.env.ETACH_E2E_PORT = saved.port;
  process.env.ETACH_E2E_TOKEN = saved.token;
  await sidecar?.stop();
});

async function openSettings(page: Page) {
  await page.goto(`/#port=${sidecar.port}&token=${sidecar.token}`);
  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByTestId("settings-tabs").getByRole("tab", { name: "Models" }).click(); // step 22.4.2
  await expect(page.getByTestId("settings-models")).toBeVisible({ timeout: 30_000 });
}

test("R20.1: the reasoning tag changed in Settings reaches GET /settings and models.toml", async ({ page }) => {
  const before = await sidecarApi<Settings>("GET", "/settings");
  expect(before.roles.reasoning).toBeTruthy();
  const tag = before.roles.reasoning!.model === "e2e-reasoning:1b" ? "e2e-reasoning:2b" : "e2e-reasoning:1b";

  await openSettings(page);
  const input = page.locator('[data-testid="role-model"][data-role="reasoning"]');
  await expect(input).toHaveValue(before.roles.reasoning!.model);
  await input.fill(tag);
  await page.getByTestId("settings-save").click();
  await expect(page.getByTestId("settings-saved")).toBeVisible();

  const after = await sidecarApi<Settings>("GET", "/settings");
  expect(after.roles.reasoning!.model).toBe(tag);
  // The other roles are unchanged.
  for (const [role, r] of Object.entries(before.roles)) {
    if (role !== "reasoning") expect(after.roles[role]!.model).toBe(r.model);
  }
  const toml = readFileSync(join(after.data_folder, "models.toml"), "utf8");
  // The reasoning block holds the new tag (other roles may share the old tag, e.g. qwen3.5:4b).
  const reasoningBlock = /\[roles\.reasoning\]\s*\nmodel = "([^"]*)"/.exec(toml)?.[1];
  expect(reasoningBlock).toBe(tag);

  // A reload shows the saved tag.
  await openSettings(page);
  await expect(page.locator('[data-testid="role-model"][data-role="reasoning"]')).toHaveValue(tag);
});

test("R20.5: Download models shows per-model progress from SSE and ends ready", async ({ page }) => {
  const settings = await sidecarApi<Settings>("GET", "/settings");
  const models = [...new Set(Object.values(settings.roles).map((r) => r.model))];

  await openSettings(page);
  await page.getByTestId("pull-models").click();
  const rows = page.getByTestId("pull-row");
  await expect(rows).toHaveCount(models.length);
  for (const m of models) await expect(page.locator(`[data-testid="pull-row"][data-model="${m}"]`)).toBeVisible();

  // Progress from SSE: the first model shows a percentage before it is ready (fake delay 300 ms).
  const first = page.locator(`[data-testid="pull-row"][data-model="${models[0]}"]`).getByTestId("pull-label");
  await expect(first).toHaveText(/downloading \d+%/, { timeout: 30_000 });

  for (const m of models) {
    await expect(page.locator(`[data-testid="pull-row"][data-model="${m}"]`).getByTestId("pull-label")).toHaveText(
      "ready",
      { timeout: 60_000 },
    );
  }
  await expect(page.getByTestId("pull-models")).toBeEnabled();
});
