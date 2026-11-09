/**
 * Step 22.6.4 (b), R22.6.4.4 (headless): while the thread's key run is pending the Key tab shows a
 * note instead of the keys and Grade student answers waits, greyed, keyboard-reachable, described by
 * "Making the key…"; with no pending key run the keys show and the button works.
 *
 * In replay the key run ends at once (its model calls are not in the cassettes), so this spec holds
 * it at the screen: `GET /runs/active` answers with a queued key run for the S1 thread. The
 * sidecar's own runs are untouched. Screenshots go to test-results/key-run-*.png (after settle).
 */
import { expect, test, type Page } from "@playwright/test";
import { connect } from "./drop";
import { seedExtractedS1, waitKeyRunSettled } from "./seed";
import { settle } from "./settle";

function holdKeyRun(page: Page, threadId: string) {
  return page.route("**/runs/active*", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          run: {
            id: "01KEYRUNHELDBYTHEE2ESPEC00",
            thread_id: threadId,
            kind: "grade",
            status: "queued",
            input: { attempt_id: null, reason: "after_extract" },
            error: null,
            started_at: null,
            finished_at: null,
          },
          current_step: null,
        },
      ]),
    }),
  );
}

test("R22.6.4.4: the Key tab note and the waiting Grade button while the key is being made", async ({ page }) => {
  test.setTimeout(300_000);
  const seeded = await seedExtractedS1();
  await waitKeyRunSettled(seeded.threadId);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await holdKeyRun(page, seeded.threadId);
  await connect(page);
  await page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`).click();
  const ws = page.getByTestId("workspace");
  await expect(ws).toBeVisible({ timeout: 30_000 });

  // Grade waits: greyed, focusable, described by the note
  const grade = ws.getByTestId("grade-answers");
  await expect(ws.getByTestId("making-key-note")).toHaveText("Making the key…");
  await expect(grade).toHaveAttribute("aria-disabled", "true");
  expect(await grade.evaluate((b) => (b as HTMLButtonElement).disabled)).toBe(false); // focusable: aria-disabled only
  await expect(grade).toHaveAccessibleDescription("Making the key…");
  // Extract again stays pressable during the key run, which it cancels (D12, R22.6.4.6). Not
  // pressed here: it would really extract the shared S1 thread again.
  await expect(ws.getByRole("button", { name: "Extract again" })).toBeEnabled();

  // the Key tab: the note instead of the keys
  await ws.getByRole("tab", { name: "Key" }).click();
  await expect(ws.getByTestId("key-making")).toHaveText("Making the key…");
  await expect(ws.getByTestId("keys-toolbar")).toHaveCount(0);
  await settle(page);
  await page.screenshot({ path: "test-results/key-run-key-tab-note.png" });

  // Grade reached from the keyboard, still waiting; a press starts nothing
  const posts: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && /\/threads\/[^/]+\/runs/.test(r.url())) posts.push(r.url());
  });
  for (let i = 0; i < 40 && !(await grade.evaluate((e) => e === document.activeElement)); i++) await page.keyboard.press("Tab");
  await expect(grade).toBeFocused();
  // the ring is not faded with the button: the button itself is fully opaque, its ring the full blue
  // and >= 3:1 on the bar it sits on (WCAG 2.4.7, 1.4.11)
  const ring = await grade.evaluate((b) => {
    const s = getComputedStyle(b);
    const lum = (c: string) => {
      const [r, g, bl] = (c.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number).map((v) => {
        const x = v / 255;
        return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r! + 0.7152 * g! + 0.0722 * bl!;
    };
    let bg = "rgb(255, 255, 255)";
    for (let p = b.parentElement; p; p = p.parentElement) {
      const c = getComputedStyle(p).backgroundColor;
      if (c && !c.startsWith("rgba(0, 0, 0, 0)") && c !== "transparent") {
        bg = c;
        break;
      }
    }
    const [hi, lo] = [lum(s.outlineColor), lum(bg)].sort((x, y) => y - x);
    return { opacity: s.opacity, style: s.outlineStyle, color: s.outlineColor, ratio: (hi! + 0.05) / (lo! + 0.05) };
  });
  expect(ring.opacity).toBe("1");
  expect(ring.style).toBe("solid");
  expect(ring.color).toBe("rgb(53, 57, 227)");
  expect(ring.ratio).toBeGreaterThanOrEqual(3);
  await page.keyboard.press("Enter");
  await page.mouse.move(0, 0);
  await settle(page);
  await page.screenshot({ path: "test-results/key-run-grade-waiting.png" });
  expect(posts).toEqual([]);

  // the key run has ended: the keys show and Grade works again
  await page.unroute("**/runs/active*");
  await page.reload();
  await page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`).click();
  await expect(ws).toBeVisible({ timeout: 30_000 });
  await ws.getByRole("tab", { name: "Key" }).click();
  await expect(ws.getByTestId("key-making")).toHaveCount(0);
  await expect(ws.getByTestId("keys-toolbar")).toBeVisible();
  await expect(ws.getByTestId("making-key-note")).toHaveCount(0);
  await expect(ws.getByTestId("grade-answers")).not.toHaveAttribute("aria-disabled", "true");
});
