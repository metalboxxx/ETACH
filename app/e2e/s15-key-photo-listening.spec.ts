/**
 * Step 22.5.6 (b, UI) on the replay sidecar (headless): R22.5.6.7 in a real browser. Synthetic data
 * only. Screenshots go to test-results/.
 * - The Key tab labels a key read from the key photo "From the key photo"; "AI key · double-checked"
 *   only for a key a second call agreed with; "AI unsure key" unchanged.
 * - The Student answers tab shows one quiet line "Listening (questions 1–10) left out".
 * Both labels meet 4.5:1 (light only, PRD §10.1 v8.12).
 *
 * The keys and the listening range come from routed GETs (as s13/s14 do): the replay sidecar has no
 * key photo or listening part to make them.
 */
import { appendFileSync } from "node:fs";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { connect } from "./drop";
import { seedExtractedS1, sidecarApi } from "./seed";
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

async function textAA(page: Page, el: Locator, what: string) {
  const ratio = await contrast(page, await css(el, "color"), await background(el));
  appendFileSync("test-results/s22.5.6-contrast.txt", `${test.info().title}: ${what}: ${ratio.toFixed(2)}\n`);
  expect(ratio, what).toBeGreaterThanOrEqual(4.5);
}

for (const scheme of ["light"] as const) {
  test(`R22.5.6.7: the Key tab says "From the key photo" (${scheme})`, async ({ page }) => {
    test.setTimeout(300_000);
    const seeded = await seedExtractedS1();
    const stored = await sidecarApi<{ content: { sections: { groups: { questions: { id: string }[] }[] }[] } }>("GET", `/tests/${seeded.testId}`);
    const ids = stored.content.sections.flatMap((s) => s.groups.flatMap((g) => g.questions.map((q) => q.id))).slice(0, 3);
    const statuses = ["from_key_photo", "ai_verified", "ai_unverified"];
    const keys = ids.map((question_id, i) => ({
      question_id,
      test_id: seeded.testId,
      accepted: ["A"],
      source: "ai",
      status: statuses[i],
      confidence: 0.8,
      reason_vi: null,
      updated_at: "2026-10-25T09:00:00Z",
      checker: null,
    }));
    await page.route(`**/tests/${seeded.testId}/keys`, (route) =>
      route.request().method() === "GET" ? route.fulfill({ json: keys }) : route.continue(),
    );
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await connect(page);
    await page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`).click();
    const workspace = page.getByTestId("workspace");
    await expect(workspace).toHaveAttribute("data-kind", "test", { timeout: 30_000 });
    await workspace.getByRole("tab", { name: "Key" }).click();

    const rows = workspace.getByTestId("key-row");
    await expect(rows).toHaveCount(3, { timeout: 30_000 });
    const photo = workspace.locator('[data-testid="key-row"][data-status="from_key_photo"]').getByTestId("key-status");
    await expect(photo).toHaveText("From the key photo");
    await expect(workspace.locator('[data-testid="key-row"][data-status="from_key_photo"]')).not.toContainText("double-checked");
    await expect(workspace.locator('[data-testid="key-row"][data-status="ai_verified"]').getByTestId("key-status")).toHaveText(
      "AI key · double-checked",
    );
    await textAA(page, photo, "key label (From the key photo)");
    await settle(page);
    await workspace.screenshot({ path: `test-results/s22.5.6-key-photo-${scheme}.png`, animations: "disabled" });
  });

  test(`R22.5.6.7: the Student answers tab's listening line (${scheme})`, async ({ page }) => {
    test.setTimeout(300_000);
    const seeded = await seedExtractedS1();
    await page.route(`**/attempts/${seeded.attemptId}`, async (route) => {
      if (route.request().method() !== "GET") return route.continue();
      const res = await route.fetch();
      const json = (await res.json()) as Record<string, unknown>;
      await route.fulfill({ response: res, json: { ...json, listening_skipped: { first: 1, last: 10 } } });
    });
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await connect(page);
    await page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`).click();
    const workspace = page.getByTestId("workspace");
    await expect(workspace).toHaveAttribute("data-kind", "test", { timeout: 30_000 });
    await workspace.getByRole("tab", { name: "Student answers" }).click();

    const line = workspace.getByTestId("answers-listening");
    await expect(line).toHaveText("Listening (questions 1–10) left out", { timeout: 30_000 });
    await expect(line).toHaveCount(1);
    await textAA(page, line, "listening line");
    await settle(page);
    await workspace.screenshot({ path: `test-results/s22.5.6-listening-${scheme}.png`, animations: "disabled" });
  });
}
