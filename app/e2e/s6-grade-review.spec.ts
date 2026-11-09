/**
 * Step 19 part B on a replay sidecar of its own: the second attempt on a known test (S2 path) and
 * the unsure spots settled in place after grading (step 22.1.5: no Review panel).
 *
 * The replay folder holds the synthetic `s1-seeded` scenarios (`sidecar/tests/replay/
 * make_s1_seeded.py`) in the order the tests use them; the tests run serially.
 *
 * R19.3: test A extracted and graded (seed, via the API) → the photo-check card's Existing test
 * search → pick → Run → Grade on the card → the grade run's `GET /runs/{id}` step list has 0
 * `transcribe_page`, 0 `ai_key_fast`, 0 `verify_key` and 0 `explain` calls (the keys are verified
 * and the wrong answers' explanations cached by A's grade).
 * R19.4: A's Q7 `uncertain_answer` fixed to A in the Answers panel → 1 grade run (review_fix) queued and
 * `done` → A's card shows 8.61/10 (`fix-a`).
 * R19.6: the seeded pages extracted again without a pick → `possible_duplicate` on the card → the
 * alignment preview → Merge → the moved attempt is under the survivor (3 attempts); the merged
 * test is not in Tests.
 * R19.7, rewritten for PRD D13 v8.0 (step 22.4.4, R22.4.4.4): a test with no printed points (`points-*`)
 * gets equal points with no `points_assumed` item; graded all correct, the card shows 10/10; 6 points
 * typed in a heading on the test page are ignored on save: `points_possible` stays 10, the text comes
 * back without them (step 22.5.2, D7: headings carry no points) and the score stays 10/10.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { dropFiles } from "./drop";
import { sidecarApi, startExtract, waitRunDone } from "./seed";
import { settle } from "./settle";
import {
  CASSETTE_ROOT,
  scenarioReplayFolder,
  startSidecar,
  type Sidecar,
} from "./sidecar";

const SEEDED = join(CASSETTE_ROOT, "s1-seeded");
const SCENARIOS = [
  join(SEEDED, "extract"),
  join(SEEDED, "grade"),
  join(SEEDED, "student-b-extract"),
  join(SEEDED, "student-b-grade"),
  join(SEEDED, "fix-a"),
  join(SEEDED, "extract"), // R19.6: the same pages again (a duplicate test)
  join(SEEDED, "points-extract"),
  join(SEEDED, "points-grade"),
];

interface ThreadDetail {
  attempt: { id: string; test_id: string } | null;
}
interface RunDetail {
  run: {
    id: string;
    kind: string;
    status: string;
    input: { test_id?: string; attempt_id?: string | null };
  };
  steps: { step: { node: string }; calls: { task: string | null }[] }[];
}

let sidecar: Sidecar;
const saved = {
  port: process.env.ETACH_E2E_PORT,
  token: process.env.ETACH_E2E_TOKEN,
};
const seeded: { threadA?: string; testId?: string; attemptA?: string } = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  test.setTimeout(150_000);
  sidecar = await startSidecar(120_000, [], scenarioReplayFolder(SCENARIOS));
  process.env.ETACH_E2E_PORT = String(sidecar.port);
  process.env.ETACH_E2E_TOKEN = sidecar.token;
});

test.afterAll(async () => {
  process.env.ETACH_E2E_PORT = saved.port;
  process.env.ETACH_E2E_TOKEN = saved.token;
  await sidecar?.stop();
});

async function home(page: Page) {
  await page.goto(`/#port=${sidecar.port}&token=${sidecar.token}`);
}

/** Task name → number of model calls in the run (from `GET /runs/{id}`). */
async function taskCounts(runId: string): Promise<Record<string, number>> {
  const run = await sidecarApi<RunDetail>("GET", `/runs/${runId}`);
  const counts: Record<string, number> = {};
  for (const s of run.steps)
    for (const c of s.calls)
      counts[c.task ?? s.step.node] = (counts[c.task ?? s.step.node] ?? 0) + 1;
  return counts;
}

test("R19.3: Existing test pick → Run → Grade makes no transcribe, key, verify or cached explain calls", async ({
  page,
}) => {
  test.setTimeout(400_000);
  // Seed: test A extracted and graded (B.6).
  const a = await startExtract(join(SEEDED, "extract"), null);
  await waitRunDone(a.runId);
  const detailA = await sidecarApi<ThreadDetail>(
    "GET",
    `/threads/${a.threadId}`,
  );
  Object.assign(seeded, {
    threadA: a.threadId,
    testId: detailA.attempt!.test_id,
    attemptA: detailA.attempt!.id,
  });
  const gradeA = await sidecarApi<{ id: string }>(
    "POST",
    `/threads/${a.threadId}/runs`,
    {
      kind: "grade",
      input: {
        test_id: seeded.testId,
        attempt_id: seeded.attemptA,
        reason: "button",
      },
    },
  );
  await waitRunDone(gradeA.id);
  const before = await taskCounts(gradeA.id);
  expect(before.explain).toBe(4); // A's grade explained the 4 wrong answers

  const tests = await sidecarApi<{ id: string; display_name: string }[]>(
    "GET",
    "/tests",
  );
  const name = tests.find((t) => t.id === seeded.testId)!.display_name;

  // Student B's pages, through the photo-check card with the Existing test pick.
  const folder = join(SEEDED, "student-b-extract");
  const manifest = JSON.parse(
    readFileSync(join(folder, "input.json"), "utf8"),
  ) as { pages: { stand_in: string }[] };
  await home(page);
  await dropFiles(
    page,
    manifest.pages.map((p) => join(folder, p.stand_in)),
  );
  const check = page.getByTestId("photo-check-card");
  await expect(check.getByTestId("photo-thumb")).toHaveCount(3);
  await check
    .getByTestId("existing-test-search")
    .fill(name.split(" ")[0] ?? name);
  await check
    .getByRole("option")
    .filter({ hasText: seeded.testId! })
    .click();
  await expect(check.getByTestId("existing-test-picked")).toBeVisible();
  const started = page.waitForResponse(
    (r) =>
      r.request().method() === "POST" &&
      /\/threads\/[^/]+\/runs$/.test(r.url()),
  );
  await check.getByTestId("photo-run").click();
  const extractRun = (await (await started).json()) as {
    id: string;
    thread_id: string;
    input: { existing_test_id: string | null };
  };
  expect(extractRun.input.existing_test_id).toBe(seeded.testId);
  await waitRunDone(extractRun.id);
  const extractCounts = await taskCounts(extractRun.id);
  expect(extractCounts.transcribe_page ?? 0).toBe(0);

  // Grade on the workspace's tab row (step 22.3.2); the summary is the Report tab.
  const workspace = page.getByTestId("workspace");
  const gradeButton = workspace.getByTestId("grade-answers");
  await expect(gradeButton).toBeEnabled({ timeout: 60_000 });
  await gradeButton.click();
  await workspace.getByRole("tab", { name: "Report" }).click({ timeout: 120_000 });
  const card = page.getByTestId("report-panel");
  await expect(card.getByTestId("grade-score")).toHaveText("8.33/10", {
    timeout: 120_000,
  });
  const threadMessages = await sidecarApi<{ kind: string; body: { run_id?: string } }[]>(
    "GET",
    `/threads/${extractRun.thread_id}/messages`,
  );
  const runId = threadMessages.filter((m) => m.kind === "grade_card").at(-1)!.body.run_id!;
  const run = await sidecarApi<RunDetail>("GET", `/runs/${runId}`);
  expect([run.run.kind, run.run.status, run.run.input.test_id]).toEqual([
    "grade",
    "done",
    seeded.testId,
  ]);
  expect(run.run.input.attempt_id).not.toBe(seeded.attemptA);

  // The keys the grade saw were verified by A's grade (4 ai_verified, the rest ai_unverified with
  // a high margin): none goes to verify_key again.
  const keys = await sidecarApi<{ status: string }[]>(
    "GET",
    `/tests/${seeded.testId}/keys`,
  );
  expect(keys.filter((k) => k.status === "ai_verified")).toHaveLength(4);

  const counts = await taskCounts(runId);
  console.log(
    `R19.3 extract tasks ${JSON.stringify(extractCounts)}; grade tasks ${JSON.stringify(counts)}`,
  );
  expect(counts.transcribe_page ?? 0).toBe(0);
  expect(counts.ai_key_fast ?? 0).toBe(0);
  expect(counts.verify_key ?? 0).toBe(0);
  expect(counts.explain ?? 0).toBe(0);
  expect(counts.weak_points_summary).toBe(1);
});

interface Item {
  id: string;
  kind: string;
  test_id: string | null;
  attempt_id: string | null;
  question_id: string | null;
  proposal: Record<string, unknown>;
}
interface Resolved {
  followup_run_ids: string[];
}

/** Opens the thread's conversation (review in place, step 22.1.5: no Review panel). */
async function openThread(page: Page, threadId: string) {
  await home(page);
  await page.locator(`[data-testid="thread-item"][data-thread-id="${threadId}"]`).click();
}

function resolveResponse(page: Page) {
  return page.waitForResponse(
    (r) => r.request().method() === "POST" && /\/review\/[^/]+\/resolve$/.test(r.url()),
  );
}

test("R19.4: fixing an uncertain_answer in the Answers panel queues 1 grade run and the score updates", async ({
  page,
}) => {
  test.setTimeout(300_000);
  expect(seeded.attemptA, "R19.3 ran first").toBeTruthy();
  const content = await sidecarApi<{
    content: { sections: { groups: { questions: { id: string; number: number }[] }[] }[] };
  }>("GET", `/tests/${seeded.testId}`);
  const q7 = content.content.sections
    .flatMap((s) => s.groups.flatMap((g) => g.questions))
    .find((q) => q.number === 7)!;
  const open = await sidecarApi<Item[]>("GET", "/review?status=open");
  const item = open.find(
    (i) => i.kind === "uncertain_answer" && i.attempt_id === seeded.attemptA && i.question_id === q7.id,
  )!;
  expect(item, "A's Q7 is unsure (the generator's first UNSURE)").toBeTruthy();

  await openThread(page, seeded.threadA!);
  const workspace = page.getByTestId("workspace");
  await workspace.getByRole("tab", { name: "Report" }).click({ timeout: 30_000 });
  const card = page.getByTestId("report-panel");
  await expect(card.getByTestId("grade-score")).toHaveText("8.33/10", { timeout: 30_000 });
  await workspace.getByRole("tab", { name: "Student answers" }).click();
  const row = page.getByTestId("answers-panel").locator(`[data-testid="answer-row"][data-question-id="${q7.id}"]`);
  await expect(row).toHaveAttribute("data-unsure", "uncertain_answer");
  await row.getByTestId("answer-edit").click();
  await page.getByTestId("answer-input").fill("A");
  const res = resolveResponse(page);
  await page.getByTestId("answer-save").click();
  const resolved = (await (await res).json()) as Resolved;
  expect(resolved.followup_run_ids).toHaveLength(1);
  const runId = resolved.followup_run_ids[0]!;
  const run = await sidecarApi<RunDetail & { run: { input: { reason?: string } } }>("GET", `/runs/${runId}`);
  expect([run.run.kind, run.run.input.attempt_id, run.run.input.reason]).toEqual([
    "grade",
    seeded.attemptA,
    "review_fix",
  ]);
  await waitRunDone(runId);
  console.log(`R19.4 regrade tasks ${JSON.stringify(await taskCounts(runId))}`);
  await workspace.getByRole("tab", { name: "Report" }).click();
  await expect(card.getByTestId("grade-score")).toHaveText("8.61/10", { timeout: 60_000 });
  await expect(card.getByTestId("grade-unsure")).toHaveAttribute("data-points", "0.2778");
});

test("R19.6: possible_duplicate on the card → merge through the preview → the attempt moves to the survivor", async ({
  page,
}) => {
  test.setTimeout(300_000);
  expect(seeded.testId, "R19.3 ran first").toBeTruthy();
  const dup = await startExtract(join(SEEDED, "extract"), null);
  await waitRunDone(dup.runId);
  const detail = await sidecarApi<ThreadDetail>("GET", `/threads/${dup.threadId}`);
  const mergedTest = detail.attempt!.test_id;
  const movedAttempt = detail.attempt!.id;
  expect(mergedTest).not.toBe(seeded.testId);
  const open = await sidecarApi<Item[]>("GET", "/review?status=open");
  const item = open.find((i) => i.kind === "possible_duplicate" && i.test_id === mergedTest)!;
  expect(item.proposal.best_test_id).toBe(seeded.testId);
  const align = item.proposal.question_alignment as Record<string, string>;

  await openThread(page, dup.threadId);
  const note = page.locator('[data-testid="card-note"][data-kind="possible_duplicate"]');
  await expect(note).toBeVisible({ timeout: 30_000 });
  // Step 22.5.8 (h): the card with its note, for the teacher's layout review.
  await settle(page);
  await note.screenshot({ path: "test-results/layout-card.png", animations: "disabled" });
  await note.getByTestId("card-merge").click();
  const preview = note.getByTestId("merge-preview");
  await expect(preview).toBeVisible();
  const rows = preview.getByTestId("merge-row");
  await expect(rows).toHaveCount(36);
  await expect(preview.getByTestId("merge-summary")).toHaveAttribute("data-aligned", "36");
  const pairs = await rows.evaluateAll((els) => els.map((e) => [e.getAttribute("data-from"), e.getAttribute("data-to")]));
  for (const [from, to] of pairs) expect(align[from!]).toBe(to);
  await expect(rows.first()).toContainText("Q1");
  const res = resolveResponse(page);
  await preview.getByTestId("review-merge-confirm").click();
  expect((await res).ok()).toBe(true);
  await expect(page.locator('[data-testid="card-note"][data-kind="possible_duplicate"]')).toHaveCount(0);

  const moved = await sidecarApi<{ attempt: { test_id: string } } | { test_id: string }>(
    "GET",
    `/attempts/${movedAttempt}`,
  );
  expect("attempt" in moved ? moved.attempt.test_id : moved.test_id).toBe(seeded.testId);
  await home(page);
  await page.getByRole("tab", { name: "Tests" }).click();
  const tab = page.getByTestId("tests-tab");
  await expect(tab.locator(`[data-testid="test-item"][data-test-id="${mergedTest}"]`)).toHaveCount(0);
  const survivor = tab.locator(`[data-testid="test-item"][data-test-id="${seeded.testId}"]`);
  await expect(survivor.getByTestId("test-attempt-count")).toHaveText("3");
});

test("R19.7 / R22.4.4.4: equal points out of 10; points typed in a heading are ignored", async ({ page }) => {
  test.setTimeout(300_000);
  const p = await startExtract(join(SEEDED, "points-extract"), null);
  await waitRunDone(p.runId);
  const detail = await sidecarApi<ThreadDetail>("GET", `/threads/${p.threadId}`);
  const { test_id: testId, id: attemptId } = detail.attempt!;
  const before = await sidecarApi<{ points_possible: number }>("GET", `/tests/${testId}`);
  expect(before.points_possible).toBe(10);
  const grade = await sidecarApi<{ id: string }>("POST", `/threads/${p.threadId}/runs`, {
    kind: "grade",
    input: { test_id: testId, attempt_id: attemptId, reason: "button" },
  });
  await waitRunDone(grade.id);
  const open = await sidecarApi<Item[]>("GET", "/review?status=open");
  expect(open.filter((i) => i.kind === "points_assumed" && i.test_id === testId)).toHaveLength(0);

  await openThread(page, p.threadId);
  const workspace = page.getByTestId("workspace");
  await workspace.getByRole("tab", { name: "Report" }).click({ timeout: 30_000 });
  const card = page.getByTestId("report-panel");
  await expect(card.getByTestId("grade-score")).toHaveText("10/10", { timeout: 30_000 });
  await workspace.getByRole("tab", { name: "Test" }).click();
  await expect(page.locator('[data-testid="test-note"][data-kind="points_assumed"]')).toHaveCount(0);
  const area = page.getByTestId("test-text");
  const text = await area.inputValue();
  expect(text).not.toMatch(/assumed/);
  // Step 22.5.2 (D7): headings are "# …" with no points; points typed in a bracket are read and ignored.
  const heading = /^# [^[\]\n]*$/m; // a graded heading (no "[not graded]")
  expect(text).toMatch(heading);
  for (const h of text.match(/^# .*$/gm) ?? []) expect(h).not.toMatch(/\bpoints?\b/i); // the stems may say "Points"
  await area.fill(text.replace(heading, (h) => `${h}  [6 points, 1.5 each]`));
  const res = page.waitForResponse((r) => r.request().method() === "PATCH" && r.url().includes(`/tests/${testId}`));
  await page.getByTestId("text-save").click();
  expect((await res).ok()).toBe(true);
  const t = await sidecarApi<{ points_possible: number; content_text: string }>("GET", `/tests/${testId}`);
  expect(t.points_possible).toBe(10);
  expect(t.content_text).toBe(text); // the typed 6 is ignored: the computed points are written again
  await expect(area).toHaveValue(text);
  await workspace.getByRole("tab", { name: "Report" }).click();
  await expect(card.getByTestId("grade-score")).toHaveText("10/10", { timeout: 60_000 });
});
