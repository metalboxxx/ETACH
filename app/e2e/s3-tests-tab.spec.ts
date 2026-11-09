/**
 * Step 16 part B on the replay sidecar: the Tests tab.
 * - R16.1: editing the school chip in the test panel → the Tests tab search finds the new school
 *   (accent-insensitive: "lomonoxop" finds "Trường Lômônôxốp").
 * - R16.5: the attempt count per test, and a merged test is absent. Seeded through the API only:
 *   S1 is extracted a second time without a pick (a second test with one attempt), then that test
 *   is merged into the first with `POST /tests/{id}/merge` (alignment: same question IDs), so the
 *   first test has 2 attempts and the second is merged.
 *
 * Runs after s2-cards-panels.spec.ts (file order, one worker) and reuses its S1 thread.
 */
import { expect, test } from "@playwright/test";
import { connect } from "./drop";
import { extractS1, seedExtractedS1, sidecarApi } from "./seed";

interface TestSummary {
  id: string;
  attempt_count: number;
}
interface TestDetail {
  id: string;
  merged_into: string | null;
  content: { sections: { groups: { questions: { id: string }[] }[] }[] };
}

const questionIds = (t: TestDetail) =>
  t.content.sections.flatMap((s) => s.groups.flatMap((g) => g.questions.map((q) => q.id)));

test("R16.1: editing the school chip → the Tests search finds the new school", async ({ page }) => {
  test.setTimeout(300_000);
  const seeded = await seedExtractedS1();

  await connect(page);
  await page.getByRole("tab", { name: "Tests" }).click();
  const tab = page.getByTestId("tests-tab");
  await tab.locator(`[data-testid="test-item"][data-test-id="${seeded.testId}"]`).click();

  const panel = page.getByTestId("artifact-panel");
  const chip = panel.locator('[data-testid="meta-chip"][data-field="school"]');
  await chip.click();
  const input = panel.getByTestId("meta-chip-input");
  await input.fill("Trường Lômônôxốp");
  await input.press("Enter");
  await expect(panel.locator('[data-testid="meta-chip"][data-field="school"]')).toContainText("Trường Lômônôxốp");

  await tab.getByTestId("tests-search").fill("lomonoxop");
  const items = tab.getByTestId("test-item");
  await expect(items).toHaveCount(1);
  await expect(items.first()).toHaveAttribute("data-test-id", seeded.testId);

  await tab.getByTestId("tests-search").fill("khongcotruongnay");
  await expect(tab.getByTestId("tests-empty")).toBeVisible();
});

test("R16.5: the Tests tab shows 2 attempts for a test, and a merged test is absent", async ({ page }) => {
  test.setTimeout(420_000);
  const first = await seedExtractedS1();
  const before = await sidecarApi<TestSummary[]>("GET", "/tests");
  expect(before.find((t) => t.id === first.testId)?.attempt_count).toBe(1);

  const second = await extractS1();
  expect(second.testId).not.toBe(first.testId);
  const survivor = await sidecarApi<TestDetail>("GET", `/tests/${first.testId}`);
  const merged = await sidecarApi<TestDetail>("GET", `/tests/${second.testId}`);
  const keep = new Set(questionIds(survivor));
  const alignment = Object.fromEntries(questionIds(merged).filter((q) => keep.has(q)).map((q) => [q, q]));
  await sidecarApi("POST", `/tests/${second.testId}/merge`, { into: first.testId, alignment });
  expect((await sidecarApi<TestDetail>("GET", `/tests/${second.testId}`)).merged_into).toBe(first.testId);

  await connect(page);
  await page.getByRole("tab", { name: "Tests" }).click();
  const tab = page.getByTestId("tests-tab");
  const row = tab.locator(`[data-testid="test-item"][data-test-id="${first.testId}"]`);
  await expect(row.getByTestId("test-attempt-count")).toHaveText("2");
  await expect(tab.locator(`[data-testid="test-item"][data-test-id="${second.testId}"]`)).toHaveCount(0);
});
