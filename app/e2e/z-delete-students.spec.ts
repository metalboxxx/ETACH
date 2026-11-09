/**
 * Step 22.2.3 (R22.2.3.5) on the replay sidecar: Delete… for a thread and a test, and editing a
 * student in the Students tab. Seeded through the API only, with synthetic names: an empty thread
 * to delete, the S1 thread the earlier specs left (seed.ts; alone, it extracts one), whose test is
 * deleted with its threads, and a student whose class is edited in place.
 *
 * Named "z-…" so it runs last (file order, one worker): it deletes the shared S1 test, and the S1
 * replay cassettes serve only two extract runs (s1 and s3 use them), so it cannot extract its own.
 */
import { expect, test } from "@playwright/test";
import { connect } from "./drop";
import { seedExtractedS1, sidecarApi } from "./seed";
import { settle } from "./settle";

test("delete a thread and a test, and edit a student (R22.2.3.5)", async ({ page }) => {
  test.setTimeout(420_000);
  const empty = await sidecarApi<{ thread_id: string }>("POST", "/threads", { title: "E2E thread to delete" });
  const seeded = await seedExtractedS1();
  const student = await sidecarApi<{ id: string }>("POST", "/students", {
    full_name: "Học Sinh Thử E2E",
    class_name: "8A",
  });

  await connect(page);

  // Students tab: search without accents, edit the class with Enter.
  await page.getByRole("tab", { name: "Students" }).click();
  const students = page.getByTestId("students-tab");
  await students.getByTestId("students-search").fill("hoc sinh thu e2e");
  const row = students.locator(`[data-testid="student-row"][data-student-id="${student.id}"]`);
  await expect(row).toContainText("Class 8A");
  await row.getByTestId("student-edit-button").click();
  await row.getByTestId("student-edit-class").fill("9B");
  await row.getByTestId("student-edit-class").press("Enter");
  await expect(row.getByTestId("student-class")).toHaveText("Class 9B");
  const saved = await sidecarApi<{ id: string; class_name: string | null }[]>("GET", "/students?q=hoc%20sinh%20thu");
  expect(saved.find((s) => s.id === student.id)?.class_name).toBe("9B");

  // Delete the empty thread from its menu.
  await page.getByRole("tab", { name: "Chats" }).click();
  const threadRow = page.locator(`[data-testid="thread-item"][data-thread-id="${empty.thread_id}"]`);
  await expect(threadRow).toBeVisible();
  await threadRow.locator("xpath=..").getByTestId("thread-menu-button").click();
  // Step 22.5.8 (f): the thread menu's brick Delete…, for the teacher's theme review.
  await settle(page);
  await page.screenshot({ path: "test-results/f-theme-thread-menu-delete.png" });
  await page.getByTestId("thread-delete").click();
  const dialog = page.getByTestId("confirm-dialog");
  await expect(dialog).toContainText("E2E thread to delete");
  await dialog.getByRole("button", { name: "Delete thread" }).click();
  await expect(threadRow).toHaveCount(0);
  const threads = await sidecarApi<{ thread: { id: string } }[]>("GET", "/threads");
  expect(threads.some((t) => t.thread.id === empty.thread_id)).toBe(false);

  // Delete the seeded test from the Tests tab: its thread goes too.
  await page.getByRole("tab", { name: "Tests" }).click();
  const testRow = page.locator(`[data-testid="test-item"][data-test-id="${seeded.testId}"]`);
  await expect(testRow).toBeVisible();
  await testRow.locator("xpath=../..").getByTestId("test-menu-button").click();
  await page.getByTestId("test-delete").click();
  const gone = await sidecarApi<{ threads: { id: string; shown_title: string }[] }>(
    "GET",
    `/tests/${seeded.testId}/delete-preview`,
  );
  expect(gone.threads.map((t) => t.id)).toContain(seeded.threadId);
  await expect(dialog.getByTestId("delete-threads").getByRole("listitem")).toHaveCount(gone.threads.length);
  await dialog.getByRole("button", { name: "Delete test" }).click();
  await expect(testRow).toHaveCount(0);
  const tests = await sidecarApi<{ id: string }[]>("GET", "/tests");
  expect(tests.some((t) => t.id === seeded.testId)).toBe(false);
  const after = await sidecarApi<{ thread: { id: string } }[]>("GET", "/threads");
  for (const t of gone.threads) expect(after.some((a) => a.thread.id === t.id)).toBe(false);
  await page.getByRole("tab", { name: "Chats" }).click();
  await expect(page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`)).toHaveCount(0);
});
