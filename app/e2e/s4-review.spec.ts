/**
 * Review in place on the replay sidecar (step 22.1.5, PRD D27; was the step 16 Review panel).
 *
 * R16.2 (now on the chip): an `unknown_student` item → the student chip's "Create “<name read>”"
 * settles it (accept) → the chip shows "Học Sinh A" and the thread's sidebar mark is one less.
 * R22.1.5.9 part 2: the Answers panel marks unsure readings in place; Keep accepts one, editing
 * another row and saving fixes it (`POST /review/{id}/resolve`), and the mark goes down each time.
 *
 * The S1 extraction really raises these items (`GET /review?status=open` is checked first).
 * Runs after the earlier specs and reuses their S1 thread; alone, it seeds one (seed.ts).
 */
import { expect, test, type Page } from "@playwright/test";
import { connect } from "./drop";
import { seedExtractedS1, sidecarApi, waitKeyRunSettled } from "./seed";
import { settle } from "./settle";

interface Item {
  id: string;
  kind: string;
  attempt_id: string | null;
  question_id: string | null;
  status: string;
}

async function openItems(): Promise<Item[]> {
  return sidecarApi<Item[]>("GET", "/review?status=open");
}

async function mark(page: Page, threadId: string): Promise<number> {
  const m = page.locator(`[data-testid="thread-item"][data-thread-id="${threadId}"]`).getByTestId("unsure-mark");
  if ((await m.count()) === 0) return 0;
  return Number(/(\d+)/.exec((await m.textContent()) ?? "")?.[1] ?? 0);
}

test("in place: unknown_student → the chip creates the student from the name read (R16.2)", async ({ page }) => {
  test.setTimeout(300_000);
  await seedExtractedS1();
  const items = await openItems();
  const student = items.find((i) => i.kind === "unknown_student" && i.attempt_id);
  expect(student, "S1 raises an unknown_student item").toBeTruthy();
  const attemptId = student!.attempt_id!;
  const att = await sidecarApi<{ attempt: { thread_id: string } }>("GET", `/attempts/${attemptId}`);
  const threadId = att.attempt.thread_id;
  // the S1 key run (step 22.6.4) may still be ending; its end changes the unsure count (R22.6.4.8)
  await waitKeyRunSettled(threadId);

  await connect(page);
  await expect(page.getByRole("button", { name: /^Review/ })).toHaveCount(0); // no Review tab
  await page.locator(`[data-testid="thread-item"][data-thread-id="${threadId}"]`).click();
  const chip = page.getByTestId("thread-banner").getByTestId("student-chip");
  await expect(chip).toHaveText("Unknown student", { timeout: 30_000 });
  await expect.poll(() => mark(page, threadId)).toBeGreaterThan(0);
  const before = await mark(page, threadId);

  await chip.click();
  await page.getByTestId("student-create-from-read").click();
  await expect(chip).toHaveText("Học Sinh A");
  await expect.poll(() => mark(page, threadId)).toBe(before - 1);
  const resolved = await sidecarApi<Item[]>("GET", "/review?status=accepted");
  expect(resolved.some((i) => i.id === student!.id)).toBe(true);
});

test("R22.1.5.9: unsure answers in the Answers panel; Keep accepts, editing fixes", async ({ page }) => {
  test.setTimeout(300_000);
  await seedExtractedS1();
  const unsure = (await openItems()).filter((i) => i.kind === "uncertain_answer" && i.attempt_id);
  expect(unsure.length).toBeGreaterThanOrEqual(2);
  const attemptId = unsure[0]!.attempt_id!;
  const att = await sidecarApi<{ attempt: { thread_id: string } }>("GET", `/attempts/${attemptId}`);
  const threadId = att.attempt.thread_id;

  await connect(page);
  await page.locator(`[data-testid="thread-item"][data-thread-id="${threadId}"]`).click();
  await expect.poll(() => mark(page, threadId)).toBeGreaterThan(0);
  const before = await mark(page, threadId);
  await page.getByTestId("workspace").getByRole("tab", { name: "Student answers" }).click();
  const rows = page.locator('[data-testid="answer-row"][data-unsure="uncertain_answer"]');
  await expect(rows.first()).toBeVisible();
  const count = await rows.count();
  expect(count).toBeGreaterThanOrEqual(2);
  for (const scheme of ["light"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await settle(page);
    await page.screenshot({ path: `test-results/s4-answers-unsure-${scheme}.png` });
  }

  // Keep: the first unsure row is accepted.
  const first = rows.first();
  const firstQ = await first.getAttribute("data-question-id");
  await first.getByTestId("answer-accept").click();
  await expect(page.locator(`[data-testid="answer-row"][data-question-id="${firstQ}"]`)).not.toHaveAttribute("data-unsure", /.+/);
  await expect(rows).toHaveCount(count - 1);

  // Edit: the next unsure row gets the typed value (the Fix).
  const second = rows.first();
  const secondQ = (await second.getAttribute("data-question-id"))!;
  await second.getByTestId("answer-edit").click();
  await page.getByTestId("answer-input").fill("B");
  await page.getByTestId("answer-save").click();
  await expect(rows).toHaveCount(count - 2);
  await expect(page.locator(`[data-testid="answer-row"][data-question-id="${secondQ}"]`).getByTestId("answer-value")).toHaveText("B");

  const fixed = await sidecarApi<Item[]>("GET", "/review?status=fixed");
  expect(fixed.some((i) => i.question_id === secondQ && i.attempt_id === attemptId)).toBe(true);
  await page.getByTestId("workspace").getByRole("tab", { name: "Test" }).click();
  await expect.poll(() => mark(page, threadId)).toBe(before - 2);
});
