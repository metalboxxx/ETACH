/**
 * Step 22.5.1 on the replay sidecar (headless): what jsdom cannot measure.
 * - R22.5.1.3: the sort button is square and as tall as the search box; its icon and outline and
 *   the menu's text meet WCAG 2.1 AA contrast (light only, PRD §10.1 v8.12). Screenshots go to test-results/.
 * - R22.5.1.7: in the sidebar and the Tests list every name gets the same width, with or without
 *   an unsure count.
 * - R22.5.1.1: a test opened from the Tests tab has no Back, and a title bar with its name.
 *
 * Runs after the earlier specs (file order, one worker) and reuses their S1 thread; alone, it seeds
 * one through the API (seed.ts).
 */
import { expect, test, type Locator, type Page } from "@playwright/test";
import { connect } from "./drop";
import { seedExtractedS1 } from "./seed";
import { settle } from "./settle";

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

async function widths(rows: Locator): Promise<number[]> {
  const out: number[] = [];
  for (const box of await rows.evaluateAll((els) => els.map((e) => e.getBoundingClientRect().width))) out.push(Math.round(box));
  return out;
}

for (const scheme of ["light"] as const) {
  test(`R22.5.1.3, R22.5.1.7: the sort button and the name widths (${scheme})`, async ({ page }) => {
    test.setTimeout(300_000);
    await seedExtractedS1();
    await page.emulateMedia({ colorScheme: scheme });
    await connect(page);

    // R22.5.1.7, the sidebar: every thread name the same width.
    const threadNames = page.getByTestId("thread-name");
    await expect(threadNames.first()).toBeVisible();
    const tw = await widths(threadNames);
    expect(new Set(tw).size, `thread name widths ${tw.join(", ")}`).toBe(1);
    for (const n of await threadNames.all()) expect(await n.locator("xpath=..").getAttribute("title")).toContain((await n.textContent())!.trim());

    await page.getByRole("tab", { name: "Tests" }).click();
    const tab = page.getByTestId("tests-tab");
    const search = tab.getByTestId("tests-search");
    const sort = tab.getByRole("button", { name: "Sort tests" });
    await expect(sort).toBeVisible();

    // R22.5.1.3: square, as tall as the search box, at its right end.
    const s = (await search.boundingBox())!;
    const b = (await sort.boundingBox())!;
    expect(Math.round(b.height)).toBe(Math.round(s.height));
    expect(Math.round(b.width)).toBe(Math.round(b.height));
    expect(Math.round(b.y)).toBe(Math.round(s.y));
    expect(b.x).toBeGreaterThan(s.x + s.width - 1);

    // Contrast: the icon and the outline (non-text, 3:1) on the button's background.
    const bg = await background(sort);
    expect(await contrast(page, await css(sort, "color"), bg)).toBeGreaterThanOrEqual(3);
    expect(await contrast(page, await css(sort, "border-top-color"), await background(tab))).toBeGreaterThanOrEqual(3);
    await tab.getByTestId("tests-search-row").screenshot({ path: `test-results/s22.5.1-sort-button-${scheme}.png`, animations: "disabled" });

    // The menu: four orders, the chosen one checked; its text 4.5:1.
    await sort.click();
    const menu = page.getByRole("menu", { name: "Sort tests" });
    await expect(menu.getByRole("menuitemradio")).toHaveCount(4);
    await expect(menu.getByRole("menuitemradio", { name: "A–Z" })).toHaveAttribute("aria-checked", "true");
    for (const item of await menu.getByRole("menuitemradio").all()) {
      expect(await contrast(page, await css(item, "color"), await background(item))).toBeGreaterThanOrEqual(4.5);
    }
    await page.screenshot({ path: `test-results/s22.5.1-sort-menu-${scheme}.png`, animations: "disabled" });
    await page.keyboard.press("Escape");
    await expect(menu).toHaveCount(0);
    await expect(sort).toBeFocused();

    // R22.5.1.7, the Tests list: every name the same width.
    const names = tab.getByTestId("test-name");
    await expect(names.first()).toBeVisible();
    const nw = await widths(names);
    expect(new Set(nw).size, `test name widths ${nw.join(", ")}`).toBe(1);
    for (const n of await names.all()) expect(await n.getAttribute("title")).toBe((await n.textContent())!.trim());
    await settle(page);
    await page.getByTestId("app-shell").screenshot({ path: `test-results/s22.5.1-lists-${scheme}.png`, animations: "disabled" });

    // R22.5.8.8 (PRD §10.1 v8.18): the wordmark ETACH in Federo (bundled, loaded offline) and the
    // full name under it, each on one line and inside the sidebar.
    const fonts = await page.evaluate(async () => {
      await document.fonts.load('56px "Federo"', "ETACH");
      return {
        federo: document.fonts.check('56px "Federo"', "ETACH"),
        loaded: [...document.fonts].some((f) => f.family.replace(/"/g, "") === "Federo" && f.status === "loaded"),
      };
    });
    expect(fonts).toEqual({ federo: true, loaded: true });
    const wordmark = page.getByTestId("wordmark");
    await expect(wordmark.getByTestId("wordmark-name")).toHaveText("ETACH");
    await expect(wordmark.getByTestId("wordmark-line")).toHaveText("English Test Assistant - Curate & Help");
    expect(await wordmark.getByTestId("wordmark-name").evaluate((e) => getComputedStyle(e).fontFamily)).toMatch(/^"?Federo"?/);
    const fit = await wordmark.evaluate((w) => {
      const nav = w.closest("nav")!.getBoundingClientRect();
      return [...w.querySelectorAll<HTMLElement>('[data-testid^="wordmark-"]')].map((e) => {
        const r = document.createRange();
        r.selectNodeContents(e);
        const lines = new Set([...r.getClientRects()].map((x) => Math.round(x.top))).size;
        const b = e.getBoundingClientRect();
        return { id: e.dataset.testid, lines, inside: b.left >= nav.left && b.right <= nav.right, width: Math.round(b.width) };
      });
    });
    console.log(`R22.5.8.8 wordmark ${JSON.stringify(fit)}`);
    for (const f of fit) expect(f, JSON.stringify(f)).toMatchObject({ lines: 1, inside: true });
    await settle(page);
    await page.getByRole("navigation", { name: "Sidebar" }).screenshot({ path: `test-results/g-etach-sidebar-${scheme}.png`, animations: "disabled" });
  });
}

test("R22.5.1.1: a test opened from the Tests tab has no Back, and a title bar with its name", async ({ page }) => {
  test.setTimeout(300_000);
  const seeded = await seedExtractedS1();
  await connect(page);
  await page.getByRole("tab", { name: "Tests" }).click();
  const row = page.locator(`[data-testid="test-item"][data-test-id="${seeded.testId}"]`);
  const name = (await row.getByTestId("test-name").textContent())!.trim();
  await row.click();
  const workspace = page.getByTestId("workspace");
  await expect(workspace).toHaveAttribute("data-kind", "test");
  await expect(workspace.getByTestId("workspace-back")).toHaveCount(0);
  await expect(workspace.getByRole("button", { name: /back/i })).toHaveCount(0);
  await expect(workspace.getByTestId("workspace-tabs")).toBeVisible();
  // The thread's own title bar or, when no open thread owns the test, the test's.
  const title = workspace.locator('[data-testid="test-bar-title"], [data-testid="thread-title"]');
  await expect(title).toBeVisible();
  if (await workspace.getByTestId("test-bar-title").count()) await expect(title).toHaveText(name);
  await page.screenshot({ path: "test-results/s22.5.1-tests-tab-test.png", animations: "disabled" });
});
