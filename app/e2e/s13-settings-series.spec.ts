/**
 * Step 22.5.2 (b, UI) on the replay sidecar (headless): what jsdom cannot measure, and the flows
 * end to end. Synthetic names only. Screenshots go to test-results/.
 * - R22.5.2.7: Settings shows General · Models · Test attributes; by keyboard, Test attributes →
 *   Series → Back returns to the menu with focus on Series; the menu's text, the Back control and
 *   the focus ring meet WCAG 2.1 AA contrast (light only, PRD §10.1 v8.12).
 * - R22.5.2.8: the Series field lists the Series list's names.
 * - R22.5.2.9: the line under the test title reads "10 points · <x> each"; the test text has "#"
 *   headings and no points.
 * - R22.5.2.10: the Extract again dialog says the test is updated in place, or asks update / copy
 *   when other threads use the test (here it is only opened and cancelled: no run starts).
 * - R22.5.2.12: the dialog has at most three short lines; the kept / replaced line sits under the
 *   Update choice; the two choices look the same. The two-choice dialog is shown by raising the
 *   thread's `other_thread_count` in the browser (a routed GET), so no second thread is needed.
 *
 * Runs after the earlier specs (file order, one worker) and reuses their S1 thread; alone, it seeds
 * one through the API (seed.ts).
 */
import { expect, test, type Locator, type Page } from "@playwright/test";
import { connect } from "./drop";
import { seedExtractedS1, sidecarApi } from "./seed";

/** WCAG contrast of two computed CSS colours (`rgb(…)`), in the page. */
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

const css = (el: Locator, prop: string) => el.evaluate((e, p) => getComputedStyle(e).getPropertyValue(p), prop);

/** The first non-transparent background at or above `el`. */
const background = (el: Locator) =>
  el.evaluate((e) => {
    for (let n: Element | null = e; n; n = n.parentElement) {
      const bg = getComputedStyle(n).backgroundColor;
      if (bg && bg !== "transparent" && !bg.startsWith("rgba(0, 0, 0, 0)")) return bg;
    }
    return "rgb(255, 255, 255)";
  });

async function textContrast(page: Page, el: Locator): Promise<number> {
  return contrast(page, await css(el, "color"), await background(el));
}

for (const scheme of ["light"] as const) {
  test(`R22.5.2.7: Settings → Test attributes → Series → Back, by keyboard (${scheme})`, async ({ page }) => {
    test.setTimeout(180_000);
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" }); // no colour transition mid-shot
    await connect(page);
    await page.getByRole("button", { name: "Settings" }).click();
    const tabs = page.getByTestId("settings-tabs");
    await expect(tabs.getByRole("tab")).toHaveText(["General", "Models", "Test attributes"], { timeout: 30_000 });

    // keyboard: → → Enter opens Test attributes; Tab reaches the menu
    await tabs.getByRole("tab", { name: "General" }).focus();
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowRight");
    await expect(tabs.getByRole("tab", { name: "Test attributes" })).toBeFocused();
    await page.keyboard.press("Enter");
    const menu = page.getByTestId("attributes-menu");
    await expect(menu).toBeVisible();
    const items = menu.getByTestId("attributes-item");
    await expect(items).toHaveCount(3);
    for (const [i, name] of ["Occasions", "Schools", "Series"].entries()) {
      await expect(items.nth(i)).toHaveAccessibleName(name);
    }
    for (let i = 0; i < 3; i++) await page.keyboard.press("Tab");
    const seriesItem = menu.getByRole("button", { name: "Series" });
    await expect(seriesItem).toBeFocused();

    // contrast: the names and their lines (text, 4.5:1); the focus ring on the page (3:1)
    for (const item of await items.all()) {
      for (const span of await item.locator("span > span").all()) {
        expect(await textContrast(page, span)).toBeGreaterThanOrEqual(4.5);
      }
    }
    expect(await css(seriesItem, "outline-style")).toBe("solid");
    expect(await contrast(page, await css(seriesItem, "outline-color"), await background(menu))).toBeGreaterThanOrEqual(3);
    await page.getByTestId("settings-panel").screenshot({ path: `test-results/s22.5.2-attributes-menu-${scheme}.png`, animations: "disabled" });

    // Enter opens the Series list in place; focus on its heading
    await page.keyboard.press("Enter");
    const section = page.getByTestId("settings-series");
    await expect(section).toBeVisible();
    await expect(menu).toBeHidden();
    await expect(section.getByRole("heading", { name: "Series" })).toBeFocused();
    const name = `Bộ đề thử E2E (${scheme})`;
    await section.getByTestId("series-new-name").fill(name);
    await section.getByTestId("series-new-name").press("Enter");
    await expect(section.getByTestId("series-name").filter({ hasText: name })).toHaveCount(1);
    const back = section.getByRole("button", { name: "Back to Test attributes" });
    expect(await textContrast(page, back)).toBeGreaterThanOrEqual(4.5);
    for (const row of await section.getByTestId("series-row").all()) {
      expect(await textContrast(page, row.getByTestId("series-name"))).toBeGreaterThanOrEqual(4.5);
      const uses = row.locator('[data-testid="series-uses"], [data-testid="series-blocked"]');
      expect(await textContrast(page, uses)).toBeGreaterThanOrEqual(4.5);
    }
    await page.getByTestId("settings-panel").screenshot({ path: `test-results/s22.5.2-series-list-${scheme}.png`, animations: "disabled" });

    // Back (keyboard) returns to the menu, focus on Series
    await back.focus();
    await page.keyboard.press("Enter");
    await expect(menu).toBeVisible();
    await expect(section).toBeHidden();
    await expect(seriesItem).toBeFocused();
    expect((await sidecarApi<{ name: string }[]>("GET", "/series")).map((s) => s.name)).toContain(name);
  });
}

test("R22.5.2.8–R22.5.2.10: the Series field, the points line, # headings and the Extract again dialog", async ({ page }) => {
  test.setTimeout(300_000);
  const seeded = await seedExtractedS1();
  await sidecarApi("POST", "/series", { name: "Bộ đề trường thử" }).catch(() => undefined); // may exist from a rerun
  const seriesNames = (await sidecarApi<{ name: string }[]>("GET", "/series")).map((s) => s.name);
  const stored = await sidecarApi<{ points_each: number | null; content_text: string }>("GET", `/tests/${seeded.testId}`);
  const others = (await sidecarApi<{ other_thread_count: number }>("GET", `/threads/${seeded.threadId}`)).other_thread_count;

  await connect(page);
  await page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`).click();
  const workspace = page.getByTestId("workspace");
  await expect(workspace).toHaveAttribute("data-kind", "test", { timeout: 30_000 });

  // R22.5.2.9: the points line and the text's headings
  const each = String(Math.round(stored.points_each! * 100) / 100);
  await expect(workspace.getByTestId("test-title-details")).toHaveText(new RegExp(`10 points · ${each.replace(".", "\\.")} each$`));
  const text = await workspace.getByTestId("test-text").inputValue();
  expect(text).toMatch(/^# /m);
  expect(text).not.toMatch(/\bpoints?\b/i);
  await workspace.getByTestId("test-title").screenshot({ path: "test-results/s22.5.2-points-line.png", animations: "disabled" });

  // R22.5.2.8: the Series chip lists the Series list's names, nothing else
  const chip = workspace.locator('[data-testid="meta-chip"][data-field="source"]');
  await chip.click();
  const box = workspace.locator('[data-testid="meta-chip-input"][data-field="source"]');
  await expect(box).toHaveAttribute("role", "combobox");
  await expect(page.getByTestId("series-option")).toHaveText(seriesNames);
  await page.screenshot({ path: "test-results/s22.5.2-series-chip-open.png", animations: "disabled" });
  await box.press("Escape");

  // R22.5.2.10: the Extract again dialog, then Keep this one (nothing is sent)
  const posts: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes("/extract-again")) posts.push(r.url());
  });
  await workspace.getByTestId("extract-again").click();
  const dialog = page.getByRole("alertdialog", { name: "Extract this test again?" });
  await expect(dialog).toBeVisible();
  if (others > 0) {
    await expect(dialog.getByTestId("again-others")).toContainText(`${others} other thread`);
    await expect(dialog.getByRole("button", { name: "Update the test for every thread" })).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Make a separate copy for this thread" })).toBeVisible();
  } else {
    await expect(dialog).toContainText("the test is updated in place");
    await expect(dialog.getByRole("button", { name: /separate copy/ })).toHaveCount(0);
  }
  await expect(dialog.getByRole("button", { name: "Keep this one" })).toBeFocused();
  await checkShortDialog(page, dialog, others > 0 ? "s22.5.2-extract-again" : "s22.5.2-extract-again-single");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  expect(posts).toEqual([]);
});

/** R22.5.2.12: at most three short lines, the kept / replaced line under Update, AA contrast;
 * screenshots (light only, PRD §10.1 v8.12). */
async function checkShortDialog(page: Page, dialog: Locator, shot: string) {
  const lines = dialog.locator("p");
  expect(await lines.count()).toBeLessThanOrEqual(3);
  for (const t of await lines.allTextContents()) expect(t.length).toBeLessThanOrEqual(90);
  const hint = dialog.getByTestId("confirm-hint");
  await expect(hint).toHaveText("Test details and keys on unchanged questions stay; edits to the test text are replaced.");
  const update = dialog.getByRole("button", { name: /^(Update the test for every thread|Extract again)$/ });
  await expect(update).toHaveAccessibleDescription(await hint.innerText());
  const hb = (await hint.boundingBox())!;
  const ub = (await update.boundingBox())!;
  expect(hb.y - (ub.y + ub.height)).toBeLessThan(12); // right under its button
  for (const s of ["light"] as const) {
    await page.emulateMedia({ colorScheme: s, reducedMotion: "reduce" });
    await dialog.screenshot({ path: `test-results/${shot}-${s}.png`, animations: "disabled" });
    for (const p of await lines.all()) expect(await textContrast(page, p)).toBeGreaterThanOrEqual(4.5);
  }
  await page.emulateMedia({ colorScheme: "light" });
}

test("R22.5.2.12: with other threads, the short two-choice Extract again dialog", async ({ page }) => {
  test.setTimeout(180_000);
  const seeded = await seedExtractedS1();
  // The thread as loaded shows two other threads (the sidecar's own count is left as it is).
  await page.route(`**/threads/${seeded.threadId}`, async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const res = await route.fetch();
    const json = (await res.json()) as Record<string, unknown>;
    await route.fulfill({ response: res, json: { ...json, other_thread_count: 2 } });
  });
  const posts: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes("/extract-again")) posts.push(r.url());
  });
  await connect(page);
  await page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`).click();
  const workspace = page.getByTestId("workspace");
  await expect(workspace).toHaveAttribute("data-kind", "test", { timeout: 30_000 });
  await workspace.getByTestId("extract-again").click();
  const dialog = page.getByRole("alertdialog", { name: "Extract this test again?" });
  await expect(dialog.getByTestId("again-others")).toHaveText("2 other threads use this test.");
  await expect(dialog.getByRole("button", { name: "Keep this one" })).toBeFocused();
  const update = dialog.getByRole("button", { name: "Update the test for every thread" });
  const copy = dialog.getByRole("button", { name: "Make a separate copy for this thread" });
  // neither choice looks recommended: the same colours and border
  for (const prop of ["color", "background-color", "border-top-color"]) expect(await css(update, prop)).toBe(await css(copy, prop));
  await checkShortDialog(page, dialog, "s22.5.2-extract-again");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  expect(posts).toEqual([]);
});
