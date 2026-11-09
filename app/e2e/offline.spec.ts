/**
 * R13.3: the built app makes 0 requests to non-localhost origins while loading and navigating.
 * The web build is served by `vite preview` (playwright.config.ts) and talks to a real
 * `etach serve --replay` sidecar started in global-setup.ts.
 */
import { expect, test, type Page } from "@playwright/test";

const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "[::1]"]);

function isLocal(raw: string): boolean {
  const url = new URL(raw);
  if (url.protocol === "data:" || url.protocol === "blob:") return true;
  return LOOPBACK_HOSTS.has(url.hostname);
}

function recordRequests(page: Page): { all: string[]; external: string[] } {
  const seen = { all: [] as string[], external: [] as string[] };
  // Every request from the page, its workers and its frames goes through this route.
  void page.context().route("**/*", (route) => {
    const url = route.request().url();
    seen.all.push(url);
    if (isLocal(url)) return route.continue();
    seen.external.push(url);
    return route.abort("blockedbyclient");
  });
  page.on("request", (req) => {
    const url = req.url();
    if (!isLocal(url) && !seen.external.includes(url)) seen.external.push(url);
  });
  return seen;
}

test("the web build makes no non-loopback requests while loading and navigating", async ({ page }) => {
  const port = process.env.ETACH_E2E_PORT;
  const token = process.env.ETACH_E2E_TOKEN;
  expect(port, "global setup started the sidecar").toBeTruthy();

  const seen = recordRequests(page);
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(String(err)));

  await page.goto(`/#port=${port}&token=${token}`);

  // Connected to the real sidecar: the lists show, no notice. (No Review item since step 22.1.5.)
  await expect(page.getByRole("tab", { name: "Chats" })).toBeVisible();
  await expect(page.getByTestId("connection-notice")).toHaveCount(0);

  const items = page.getByTestId("sidebar-items").locator(":scope > li");
  await expect(items).toHaveCount(4);
  expect(await items.evaluateAll((els) => els.map((e) => e.getAttribute("data-item")))).toEqual([
    "new-thread",
    "running",
    "tabs",
    "settings",
  ]);

  // Navigate: every sidebar item, the panel open / close (button and Esc), the shortcuts.
  const panel = page.getByTestId("artifact-panel");
  await expect(panel).toHaveCount(0);
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(panel).toBeVisible();
  await page.getByRole("button", { name: "Close panel" }).click();
  await expect(panel).toHaveCount(0);

  await page.getByRole("tab", { name: "Tests" }).click();
  await expect(page.getByRole("tab", { name: "Tests" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Chats" }).click();

  await page.getByRole("button", { name: "Settings" }).click();
  await expect(panel).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(panel).toHaveCount(0);

  await page.getByRole("button", { name: "Settings" }).click();
  // By title: threads made by other specs are also named "New thread".
  await page.getByTitle("New thread (Ctrl+N)").click();
  await expect(panel).toHaveCount(0);

  await page.keyboard.press("Control+k");
  await expect(page.getByRole("tab", { name: "Tests" })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Control+n");
  await expect(page.getByRole("tab", { name: "Chats" })).toHaveAttribute("aria-selected", "true");

  // The SSE stream stays open, so no networkidle: give late requests a moment instead.
  await page.waitForTimeout(1_000);

  expect(errors).toEqual([]);
  expect(seen.all.length).toBeGreaterThan(0);
  expect(seen.all.some((u) => u.includes(`:${port}/threads`))).toBe(true);
  expect(seen.external, "requests to non-loopback origins").toEqual([]);
});
