import type { Page } from "@playwright/test";

/**
 * Before a screenshot for the teacher (step 22.5.8 (f), PRD §10.1 v8.15): move the mouse off every
 * control, so no button or tab shows its hover colour, and wait until the colour transitions have
 * finished. Endless animations (a running pulse) are left alone.
 */
export async function settle(page: Page): Promise<void> {
  await page.mouse.move(0, 0);
  await page.waitForFunction(() =>
    document.getAnimations().every((a) => {
      const iterations = a.effect?.getComputedTiming().iterations;
      return iterations === Infinity || a.playState !== "running";
    }),
  );
}
