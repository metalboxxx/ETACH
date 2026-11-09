/**
 * Step 22.1.4 (the workspace view, decision 3 = B) on the replay sidecar, synthetic data only.
 * R22.1.4.6: at 1280×720 the panel and the photos are both visible with no horizontal scrolling;
 * below 1024 px the photos fold behind a toggle. Teacher's decision 6: headless screenshots of the
 * conversation and each workspace, light only, go to the gitignored `test-results/` folder
 * (never committed) for the verifier.
 *
 * Runs after s8 (file order, one worker). The Report workspace is shot only when this sidecar holds
 * a graded thread (the S1 replay does not; the Report uses the same viewer as Answers).
 */
import { expect, test, type Locator, type Page } from "@playwright/test";
import { connect } from "./drop";
import { seedExtractedS1, sidecarApi } from "./seed";
import { settle } from "./settle";

interface Message {
  kind: string;
  body: { attempt_id?: string | null };
}

const SHOTS = "test-results/screenshots-22.1.4";

/** PRD §10.1 v8.16: every button and tab label in the workspace bars on one line, never clipped. */
async function labelsFit(page: Page, where: string) {
  const bad = await page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>('[data-testid="workspace"] button, [data-testid="workspace"] [role="tab"]')]
      .filter((e) => e.offsetParent !== null && (e.textContent ?? "").trim().length > 1)
      .flatMap((e) => {
        // lines of text only (an icon beside the label is not a line)
        const tops: number[] = [];
        const walk = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
        for (let n = walk.nextNode(); n; n = walk.nextNode()) {
          if (!(n.textContent ?? "").trim()) continue;
          const r = document.createRange();
          r.selectNodeContents(n);
          for (const x of r.getClientRects()) tops.push(x.top);
        }
        const half = parseFloat(getComputedStyle(e).lineHeight) / 2 || 8;
        const lines = tops.sort((x, y) => x - y).filter((t, i, all) => i === 0 || t - all[i - 1]! > half).length;
        const clipped = e.scrollWidth > e.clientWidth + 1;
        return lines > 1 || clipped ? [`${(e.textContent ?? "").trim()} (lines ${lines}, clipped ${clipped})`] : [];
      }),
  );
  expect(bad, where).toEqual([]);
}

/** PRD §10.1 v8.17: a label's vertical placement in its control. `top` is the gap from the inner
 *  top edge to the top of the capitals, `bottom` the gap from the baseline to the inner bottom
 *  edge; equal gaps mean the capitals sit in the middle. The baseline comes from the text's
 *  content box and the font's ascent and descent (canvas metrics of the same face). */
async function labelGaps(l: Locator): Promise<{ top: number; bottom: number }> {
  return l.evaluate((e) => {
    const s = getComputedStyle(e);
    const box = e.getBoundingClientRect();
    const innerTop = box.top + parseFloat(s.borderTopWidth);
    const innerBottom = box.bottom - parseFloat(s.borderBottomWidth);
    const walk = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
    let text: Node | null = walk.nextNode();
    while (text && !(text.textContent ?? "").trim()) text = walk.nextNode();
    const r = document.createRange();
    r.selectNodeContents(text!);
    const content = r.getClientRects()[0]!;
    const ctx = document.createElement("canvas").getContext("2d")!;
    ctx.font = `${s.fontStyle} ${s.fontWeight} 100px ${s.fontFamily}`;
    const m = ctx.measureText("H");
    const asc = m.fontBoundingBoxAscent;
    const desc = m.fontBoundingBoxDescent;
    const cap = m.actualBoundingBoxAscent;
    const unit = content.height / (asc + desc);
    const baseline = content.bottom - desc * unit;
    const capTop = baseline - cap * unit;
    const round = (v: number) => Math.round(v * 100) / 100;
    return { top: round(capTop - innerTop), bottom: round(innerBottom - baseline) };
  });
}

async function noHorizontalScroll(page: Page) {
  const [scroll, client] = await page.evaluate(() => [
    document.documentElement.scrollWidth,
    document.documentElement.clientWidth,
  ]);
  expect(scroll).toBeLessThanOrEqual(client);
}

async function openThread(page: Page, threadId: string) {
  await page.locator(`[data-testid="thread-item"][data-thread-id="${threadId}"]`).click();
  // Straight to work (step 22.3.2): an extracted thread opens its Test workspace.
  await expect(page.getByTestId("workspace")).toHaveAttribute("data-kind", "test", { timeout: 30_000 });
}

/** A thread whose latest message is a grade card for an attempt (made by s5), if any. */
async function gradedThread(): Promise<string | null> {
  const rows = await sidecarApi<{ thread: { id: string } }[]>("GET", "/threads");
  for (const row of rows) {
    const messages = await sidecarApi<Message[]>("GET", `/threads/${row.thread.id}/messages`);
    if (messages.some((m) => m.kind === "grade_card" && m.body.attempt_id)) return row.thread.id;
  }
  return null;
}

for (const scheme of ["light"] as const) {
  test(`workspace layout and screenshots, ${scheme} (R22.1.4.6)`, async ({ page }) => {
    test.setTimeout(300_000);
    const seeded = await seedExtractedS1();
    await page.emulateMedia({ colorScheme: scheme });
    await page.setViewportSize({ width: 1280, height: 720 });
    await connect(page);
    await openThread(page, seeded.threadId);
    const workspace = page.getByTestId("workspace");
    for (const [tab, name] of [
      ["Test", "test"],
      ["Key", "key"],
      ["Student answers", "answers"],
    ] as const) {
      await workspace.getByRole("tab", { name: tab }).click();
      await expect(workspace).toBeVisible();
      await expect(page.getByTestId("conversation")).toHaveCount(0);
      const panel = workspace.getByTestId("artifact-panel");
      const photos = workspace.getByTestId("workspace-photos");
      await expect(panel).toBeVisible();
      await expect(photos).toBeVisible();
      await expect(workspace.getByTestId("workspace-side-toggle")).toBeHidden();
      // Side by side, each a usable width.
      const a = (await panel.boundingBox())!;
      const b = (await photos.boundingBox())!;
      expect(a.x + a.width).toBeLessThanOrEqual(b.x + 1);
      expect(a.width).toBeGreaterThan(400);
      expect(b.width).toBeGreaterThan(400);
      await noHorizontalScroll(page);
      await expect(workspace.getByTestId("photo-image")).toBeVisible();
      await settle(page);
      await page.screenshot({ path: `${SHOTS}/${scheme}-1280-${name}.png` });
      await labelsFit(page, `1280 ${name}`);
      if (name === "test") {
        // PRD §10.1 v8.16: one font, Faustina, loaded with its Vietnamese glyphs; the tab and button
        // labels drawn with Merriweather's x-height (font-size-adjust 0.56).
        // the faces load on demand (unicode-range), so load the Vietnamese sample first
        expect(
          await page.evaluate(async () => {
            await document.fonts.load('16px "Faustina"', "Câu hỏi giả lập ữ ễ ặ");
            return document.fonts.check('16px "Faustina"', "Câu hỏi giả lập ữ ễ ặ");
          }),
        ).toBe(true);
        expect(await page.evaluate(() => [...document.fonts].some((f) => f.family.replace(/"/g, "") === "Faustina" && f.status === "loaded"))).toBe(true);
        const studentTab = workspace.getByRole("tab", { name: "Student answers" });
        const tabFont = await studentTab.evaluate((e) => {
          const s = getComputedStyle(e);
          const r = document.createRange();
          r.selectNodeContents(e);
          const box = r.getBoundingClientRect();
          return { family: s.fontFamily, size: s.fontSize, adjust: s.fontSizeAdjust, width: Math.round(box.width * 10) / 10 };
        });
        console.log(`v8.16 "Student answers" tab ${JSON.stringify(tabFont)}`);
        expect(tabFont.family).toMatch(/^"?Faustina"?,/);
        expect(tabFont.adjust).toBe("0.56");
        // v8.17: only the workspace tabs and the main action buttons are enlarged.
        const adjust = (l: Locator) => l.evaluate((e) => getComputedStyle(e).fontSizeAdjust);
        for (const l of [
          workspace.getByRole("tab", { name: "Key" }),
          workspace.getByTestId("grade-answers"),
          workspace.getByRole("button", { name: "Extract again" }),
          workspace.getByTestId("test-print"),
          workspace.getByTestId("test-save-docx"),
        ]) expect(await adjust(l)).toBe("0.56");
        for (const l of [
          workspace.getByTestId("test-name-chip"),
          page.getByRole("tab", { name: "Chats" }),
          page.getByTestId("thread-item").first(),
          workspace.getByRole("button", { name: /^Copy details from/ }).first(),
        ]) expect(await adjust(l)).toBe("none");
        const gaps = {
          studentTab: await labelGaps(studentTab),
          grade: await labelGaps(workspace.getByTestId("grade-answers")),
          extract: await labelGaps(workspace.getByRole("button", { name: "Extract again" })),
          chip: await labelGaps(workspace.getByTestId("test-name-chip")),
        };
        console.log(`v8.17 label gaps ${JSON.stringify(gaps)}`);
        // The capitals sit in the middle (Faustina's metric overrides in fonts.css): the gap above
        // them and the gap below the baseline differ by at most 1 px.
        for (const [what, g] of Object.entries(gaps)) expect(Math.abs(g.top - g.bottom), `${what} ${JSON.stringify(g)}`).toBeLessThanOrEqual(1);
        // A close-up of the workspace bar for the teacher (2x, the mouse away).
        await settle(page);
        await page.evaluate(() => (document.documentElement.style.zoom = "2"));
        await settle(page);
        await page.screenshot({ path: `${SHOTS}/${scheme}-buttons-closeup.png`, clip: { x: 512, y: 0, width: 1280, height: 200 } });
        await page.evaluate(() => (document.documentElement.style.zoom = ""));
        // PRD §10.1 v8.20: the blue button turns deep navy on hover (no fade).
        const grade = workspace.getByTestId("grade-answers");
        const fill = () => grade.evaluate((e) => getComputedStyle(e).backgroundColor);
        await expect.poll(fill).toBe("rgb(53, 57, 227)");
        await grade.hover();
        await expect.poll(fill).toBe("rgb(24, 26, 92)");
        expect(await grade.evaluate((e) => getComputedStyle(e).opacity)).toBe("1");
        await page.screenshot({ path: `${SHOTS}/${scheme}-1280-test-grade-hover.png` });
        await page.mouse.move(1, 700);
        await expect.poll(fill).toBe("rgb(53, 57, 227)");
      }
      if (name === "key") {
        await workspace.getByRole("button", { name: "Test text" }).click();
        await expect(workspace.getByTestId("key-test-text").getByTestId("clean-test")).toBeVisible();
        await settle(page);
        await page.screenshot({ path: `${SHOTS}/${scheme}-1280-key-test-text.png` });
      }
    }

    // Zoomed in: the page scrolls inside the viewer, never the window.
    await workspace.getByRole("tab", { name: "Test" }).click();
    await workspace.getByRole("button", { name: "Larger" }).click();
    await workspace.getByRole("button", { name: "Larger" }).click();
    await noHorizontalScroll(page);
    await settle(page);
    await page.screenshot({ path: `${SHOTS}/${scheme}-1280-test-zoom-200.png` });

    // Below 1024 px: one side at a time, with the toggle.
    await page.setViewportSize({ width: 900, height: 700 });
    const toggle = workspace.getByTestId("workspace-side-toggle");
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveText("Show photos");
    await expect(workspace.getByTestId("artifact-panel")).toBeVisible();
    await expect(workspace.getByTestId("workspace-photos")).toBeHidden();
    await noHorizontalScroll(page);
    await labelsFit(page, "900 test");
    await settle(page);
    await page.screenshot({ path: `${SHOTS}/${scheme}-900-test.png` });
    await toggle.click();
    await expect(workspace.getByTestId("workspace-photos")).toBeVisible();
    await expect(workspace.getByTestId("artifact-panel")).toBeHidden();
    await noHorizontalScroll(page);
    await settle(page);
    await page.screenshot({ path: `${SHOTS}/${scheme}-900-photos.png` });
    await page.setViewportSize({ width: 1280, height: 720 });

    // The Report workspace, on a graded thread.
    const graded = await gradedThread();
    if (graded) {
      await openThread(page, graded);
      const report = workspace.getByRole("tab", { name: "Report" });
      await expect(report).toBeVisible({ timeout: 30_000 });
      await report.click();
      await expect(workspace).toHaveAttribute("data-kind", "report");
      await expect(workspace.getByTestId("photo-viewer")).toBeVisible();
      await noHorizontalScroll(page);
      await settle(page);
      await page.screenshot({ path: `${SHOTS}/${scheme}-1280-report.png` });
    }
  });
}
