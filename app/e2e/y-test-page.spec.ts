/**
 * Step 22.2.4 (R22.2.4.7) on the replay sidecar: on the S1 thread, the Key and Student answers rows
 * show the paper's printed numbers (not the internal ones), and Format help under the test page
 * opens and closes. Runs after the grade specs, before z-delete (file order), on the shared S1
 * thread; alone, it seeds one (seed.ts). With no key yet it sets one, so the Key has a row.
 */
import { expect, test } from "@playwright/test";
import { connect } from "./drop";
import { seedExtractedS1, sidecarApi } from "./seed";

interface Q {
  id: string;
  number: number;
  printed_number: number;
}
interface TestBody {
  content: { sections: { groups: { questions: Q[] }[] }[] };
}

test("printed numbers on the Key and Student answers; Format help (R22.2.4.7)", async ({ page }) => {
  test.setTimeout(300_000);
  const seeded = await seedExtractedS1();
  const t = await sidecarApi<TestBody>("GET", `/tests/${seeded.testId}`);
  const qs = t.content.sections.flatMap((s) => s.groups.flatMap((g) => g.questions));
  const printed = new Map(qs.map((q) => [q.id, q.printed_number]));
  const keys = await sidecarApi<unknown[]>("GET", `/tests/${seeded.testId}/keys`);
  if (keys.length === 0) {
    await sidecarApi("PUT", `/tests/${seeded.testId}/keys/${qs[qs.length - 1]!.id}`, { accepted: ["A"] });
  }

  await connect(page);
  await page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`).click();
  // Straight to work (step 22.3.2): the thread opens its Test workspace.
  await expect(page.getByTestId("workspace")).toHaveAttribute("data-kind", "test", { timeout: 30_000 });
  const workspace = page.getByTestId("workspace");

  // Format help: closed, then open with the line forms, then closed again.
  const help = workspace.getByTestId("format-help");
  await expect(help).toHaveAttribute("aria-expanded", "false");
  await expect(workspace.getByTestId("format-help-region")).toBeHidden();
  await help.click();
  await expect(help).toHaveAttribute("aria-expanded", "true");
  await expect(workspace.getByTestId("format-help-row")).toHaveCount(9);
  // Step 22.4.1 (R22.4.1.1): the opened help scrolls into view; focus stays on the button.
  // Step 22.4.8 (R22.4.8.1): the button goes to the top of the scroll panel and stays in view; the
  // help's first row is right under it (1280x720).
  await expect(workspace.getByTestId("format-help-row").first()).toBeInViewport({ timeout: 5_000 });
  await expect(help).toBeInViewport();
  await expect
    .poll(
      () =>
        help.evaluate((el) => {
          let p = el.parentElement;
          while (p && !(p.scrollHeight > p.clientHeight && /auto|scroll/.test(getComputedStyle(p).overflowY))) {
            p = p.parentElement;
          }
          const box = (p ?? document.documentElement).getBoundingClientRect();
          const b = el.getBoundingClientRect();
          return b.top >= box.top - 1 && b.bottom <= box.bottom + 1 && (p?.scrollTop ?? 0) > 0;
        }),
      { timeout: 5_000 },
    )
    .toBe(true);
  await expect(help).toBeFocused();
  await page.screenshot({ path: "test-results/s12-format-help.png" });
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "reduce" });
  await page.screenshot({ path: "test-results/s22-4-8-format-help-reduced.png" });
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "no-preference" });
  await help.click();
  await expect(workspace.getByTestId("format-help-region")).toBeHidden();

  const tabs = workspace.getByRole("tablist", { name: "Workspace" });
  const leading = async (rows: ReturnType<typeof workspace.getByTestId>) =>
    (await rows.allTextContents()).map((x) => Number(/(\d+)\./.exec(x)?.[1]));

  // Key rows, by printed number.
  await tabs.getByRole("tab", { name: "Key" }).click();
  const keyRows = workspace.getByTestId("key-row");
  await expect(keyRows.first()).toBeVisible();
  const keyIds = await keyRows.evaluateAll((els) => els.map((e) => (e as HTMLElement).dataset.questionId ?? ""));
  const keyNums = await leading(keyRows);
  expect(keyNums).toEqual(keyIds.map((id) => printed.get(id)));

  // Student answers rows, by printed number.
  await tabs.getByRole("tab", { name: "Student answers" }).click();
  const answerRows = workspace.getByTestId("answer-row");
  await expect(answerRows.first()).toBeVisible();
  const ids = await answerRows.evaluateAll((els) => els.map((e) => (e as HTMLElement).dataset.questionId ?? ""));
  expect(await leading(answerRows)).toEqual(ids.map((id) => printed.get(id)));
});

test("one page with its line numbers; a saved Test name shows at once (R22.3.1.3, R22.3.1.6)", async ({ page }) => {
  test.setTimeout(300_000);
  const seeded = await seedExtractedS1();
  // A title the teacher typed wins over the test's name (data-model §5.6; s8 renames the shared
  // thread), so the thread goes on its automatic title for this check and gets its own back after.
  const before = await sidecarApi<{ thread: { title: string } }>("GET", `/threads/${seeded.threadId}`);
  await sidecarApi("PATCH", `/threads/${seeded.threadId}`, { title: null });
  await connect(page);
  const row = page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`);
  await row.click();
  // Straight to work (step 22.3.2): the thread opens its Test workspace.
  await expect(page.getByTestId("workspace")).toHaveAttribute("data-kind", "test", { timeout: 30_000 });
  const workspace = page.getByTestId("workspace");

  // R22.3.1.3: the gutter is inside the page's one border box, on the same background.
  const editor = workspace.getByTestId("doc-editor");
  await expect(editor).toBeVisible();
  const look = await editor.evaluate((el) => {
    const gutter = el.querySelector('[data-testid="doc-gutter"]')!;
    const text = el.querySelector('[data-testid="doc-page-text"]')!;
    const s = (e: Element) => getComputedStyle(e);
    return {
      pageBorder: s(el).borderTopWidth,
      gutterBg: s(gutter).backgroundColor,
      textBg: s(text).backgroundColor,
      textBorder: s(text).borderTopWidth,
      gutterBorder: s(gutter).borderRightWidth,
    };
  });
  expect(look.pageBorder).toBe("1px");
  expect(look.gutterBg).toBe("rgba(0, 0, 0, 0)");
  expect(look.textBg).toBe("rgba(0, 0, 0, 0)");
  expect(look.textBorder).toBe("0px");
  expect(look.gutterBorder).toBe("0px");
  await editor.screenshot({ path: "test-results/s13-one-page.png" });

  // R22.3.1.6: a typed Test name shows in the sidebar row and the thread header at once.
  const name = `Renamed ${Date.now() % 100000}`;
  await workspace.getByTestId("test-name-chip").click();
  const input = workspace.getByTestId("test-name-chip-input");
  await input.fill(name);
  await input.press("Enter");
  await expect(workspace.getByTestId("test-name-chip")).toContainText(name);
  await expect(row).toContainText(name);
  await expect(page.getByTestId("thread-title")).toContainText(name);

  // Put the automatic name back for the specs after this one.
  await workspace.getByTestId("test-name-auto").click();
  await expect(workspace.getByTestId("test-name-chip")).toBeFocused();
  await expect(row).not.toContainText(name);
  if (before.thread.title !== "New thread") {
    await sidecarApi("PATCH", `/threads/${seeded.threadId}`, { title: before.thread.title });
  }
});
