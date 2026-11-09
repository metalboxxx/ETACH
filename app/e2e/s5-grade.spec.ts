/**
 * Step 19 part A on a replay sidecar of its own (so the S1 cassettes and the earlier specs'
 * overrides on the shared S1 thread don't mix in): the grade card, the report and key prints, and
 * the key editor's re-grade fan-out.
 *
 * The replay folder holds, in this order, the synthetic `s1-seeded` scenarios (seeded to plan
 * Appendix B.6; `sidecar/tests/replay/make_s1_seeded.py`), then the signed-off `blank` test and
 * its `grade-synthetic/blank-key` grade. Pages share `transcribe_page` keys across scenarios, so
 * the tests run in that order (serial).
 *
 * R19.1: a fresh S1-like thread → Grade → the card shows 8.33/10, "0.56 unsure", 3–5 teacher
 * questions, weak points and careless notes; the report print view hides the chrome and marks the
 * `?` rows.
 * R19.5 / R22.4.5.4 (step 22.4.5, PRD v8.1): a second attempt on the same test, graded → the key
 * editor verifies two keys → no run (the PUTs' `run_ids` are empty) and the top bar reads "Keys
 * changed" → leaving the Key tab calls `POST /tests/{id}/regrade` once → 2 grade runs, and the
 * report shows the score after the re-grade.
 * R19.2: the blank test → Grade → the key print lists one key per question, with no student data.
 */
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { sidecarApi, startExtract, waitRunDone } from "./seed";
import { CASSETTE_ROOT, scenarioReplayFolder, startSidecar, type Sidecar } from "./sidecar";
import { settle } from "./settle";

const SEEDED = join(CASSETTE_ROOT, "s1-seeded");
const BLANK = join(CASSETTE_ROOT, "blank");
const SCENARIOS = [
  join(SEEDED, "extract"),
  join(SEEDED, "grade"),
  join(SEEDED, "student-b-extract"),
  join(SEEDED, "student-b-grade"),
  join(SEEDED, "regrade-a"),
  join(SEEDED, "regrade-b"),
  BLANK,
  join(CASSETTE_ROOT, "grade-synthetic", "blank-key"),
];
/** The synthetic student of `s1-seeded/extract` (scrub's one allowed placeholder) and class. */
const STUDENT = "Học Sinh A";
const CLASS = "8X1";

interface ThreadDetail {
  attempt: { id: string; test_id: string } | null;
  test: { id: string } | null;
}
interface RunDetail {
  run: { id: string; kind: string; status: string; input: { test_id?: string; attempt_id?: string | null } };
}

let sidecar: Sidecar;
const saved = { port: process.env.ETACH_E2E_PORT, token: process.env.ETACH_E2E_TOKEN };
const seeded: { threadA?: string; testId?: string; attemptA?: string } = {};

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  test.setTimeout(150_000);
  sidecar = await startSidecar(120_000, [], scenarioReplayFolder(SCENARIOS));
  // seed.ts and connect() read these; restored in afterAll for the later spec files.
  process.env.ETACH_E2E_PORT = String(sidecar.port);
  process.env.ETACH_E2E_TOKEN = sidecar.token;
});

test.afterAll(async () => {
  process.env.ETACH_E2E_PORT = saved.port;
  process.env.ETACH_E2E_TOKEN = saved.token;
  await sidecar?.stop();
});

async function open(page: Page, threadId: string) {
  await page.goto(`/#port=${sidecar.port}&token=${sidecar.token}`);
  await page.locator(`[data-testid="thread-item"][data-thread-id="${threadId}"]`).click();
}

async function extracted(folder: string, existing: string | null): Promise<{ threadId: string; detail: ThreadDetail }> {
  const { threadId, runId } = await startExtract(folder, existing);
  await waitRunDone(runId);
  return { threadId, detail: await sidecarApi<ThreadDetail>("GET", `/threads/${threadId}`) };
}

test("R19.1: Grade → the card shows 8.33/10 and 0.5 unsure; the report print marks ? rows", async ({ page }) => {
  test.setTimeout(300_000);
  const { threadId, detail } = await extracted(join(SEEDED, "extract"), null);
  expect(detail.attempt).toBeTruthy();
  Object.assign(seeded, { threadA: threadId, testId: detail.attempt!.test_id, attemptA: detail.attempt!.id });

  await open(page, threadId);
  // Straight to work (step 22.3.2): Grade student answers is on the workspace's tab row; the
  // grade card's summary is the Report tab.
  const workspace = page.getByTestId("workspace");
  const gradeButton = workspace.getByTestId("grade-answers");
  await expect(gradeButton).toBeEnabled({ timeout: 30_000 });
  await gradeButton.click();
  await workspace.getByRole("tab", { name: "Report" }).click({ timeout: 120_000 });

  const card = page.getByTestId("report-panel");
  await expect(card.getByTestId("grade-score")).toHaveText("8.33/10", { timeout: 120_000 });
  await expect(card.getByTestId("grade-unsure")).toHaveText("0.56 unsure");
  await expect(card.getByTestId("grade-unsure")).toHaveAttribute("data-points", "0.5556");
  // Step 22.4.1: once graded the button still reads "Grade student answers" (R22.4.1.3); the
  // tabs look like buttons, the selected one filled blue (R22.4.1.2, headless screenshots).
  await expect(gradeButton).toHaveText("Grade student answers");
  const reportTab = workspace.getByRole("tab", { name: "Report" });
  await expect(reportTab).toHaveAttribute("aria-selected", "true");
  for (const scheme of ["light"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await settle(page);
    await workspace.getByTestId("workspace-bar").screenshot({ path: `test-results/s22.4.1-tabs-${scheme}.png`, animations: "disabled" });
  }
  await page.emulateMedia({ colorScheme: "light" });
  const questions = await card.getByTestId("teacher-question").count();
  expect(questions).toBeGreaterThanOrEqual(3);
  expect(questions).toBeLessThanOrEqual(5);
  await expect(card.getByTestId("weak-point").first()).toBeVisible();
  await expect(card.getByTestId("careless-note")).toHaveCount(2);
  // R22.4.6.4 (step 22.4.6): the report shows skill names, never a taxonomy code (such as
  // VOC-TOPIC or GR-PSV-A1); the explanations follow the printed numbers.
  // the code shapes of sidecar/src/etach/prompts/taxonomy/*.txt
  const taxonomyCode = /\b(?:GR-[A-Z]+-[A-Z0-9]+|(?:PRON|STRESS|VOC|WF|READ|REWRITE)(?:-[A-Z0-9]+)+|SIGN)\b/;
  const skills = await card.getByTestId("weak-point").evaluateAll((els) => els.map((e) => e.getAttribute("data-skill")));
  expect(skills.length).toBeGreaterThan(0);
  expect(await card.innerText()).not.toMatch(taxonomyCode);
  const explained = await card.getByTestId("explanation").allInnerTexts();
  const explainedNumbers = explained.map((t) => Number.parseInt(t, 10));
  expect(explainedNumbers).toEqual([...explainedNumbers].sort((a, b) => a - b));
  console.log(`R22.4.6.4 weak points ${JSON.stringify(skills)}; explanations at ${JSON.stringify(explainedNumbers)}`);
  await card.getByTestId("weak-point").first().scrollIntoViewIfNeeded();
  for (const scheme of ["light"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await settle(page);
    await page.screenshot({ path: `test-results/r22.4.6-report-${scheme}.png`, animations: "disabled" });
  }
  await page.emulateMedia({ colorScheme: "light" });
  const messages = await sidecarApi<{ kind: string; body: { run_id?: string } }[]>("GET", `/threads/${threadId}/messages`);
  const runId = messages.filter((m) => m.kind === "grade_card").at(-1)?.body.run_id;
  const run = await sidecarApi<RunDetail>("GET", `/runs/${runId}`);
  expect([run.run.kind, run.run.status]).toEqual(["grade", "done"]);

  // The report and its print view.
  const panel = page.getByTestId("artifact-panel");
  const rows = panel.getByTestId("report-row");
  await expect(rows).toHaveCount(36);
  await expect(panel.locator('[data-testid="report-row"][data-mark="?"]')).toHaveCount(2);
  await expect(panel.locator('[data-testid="report-row"][data-mark="✗"]')).toHaveCount(4);
  await page.emulateMedia({ media: "print" });
  await expect(page.locator("nav").first()).toBeHidden();
  await expect(panel.getByTestId("panel-chrome")).toBeHidden();
  await expect(panel.getByTestId("report-toolbar")).toBeHidden();
  await expect(page.getByTestId("conversation")).toHaveCount(0);
  await expect(panel.getByTestId("report-rows")).toBeVisible();
  const marked = panel.locator('[data-testid="report-row"][data-mark="?"]').first();
  await expect(marked).toHaveCSS("outline-style", "solid");
  await expect(panel.locator('[data-testid="report-row"][data-mark="✓"]').first()).toHaveCSS("outline-style", "none");
  await page.emulateMedia({ media: "screen" });
});

test("R19.5 / R22.4.5.4: verifying 2 keys starts no run; leaving the Key tab re-grades the 2 graded attempts once", async ({ page }) => {
  test.setTimeout(300_000);
  expect(seeded.testId, "R19.1 ran first").toBeTruthy();
  // A second attempt on the same test (the name not read), graded.
  const b = await extracted(join(SEEDED, "student-b-extract"), seeded.testId!);
  expect(b.detail.attempt?.test_id).toBe(seeded.testId);
  const attemptB = b.detail.attempt!.id;
  const grade = await sidecarApi<{ id: string }>("POST", `/threads/${b.threadId}/runs`, {
    kind: "grade",
    input: { test_id: seeded.testId, attempt_id: attemptB, reason: "button" },
  });
  await waitRunDone(grade.id);

  await open(page, seeded.threadA!);
  const workspace = page.getByTestId("workspace");
  await workspace.getByRole("tab", { name: "Report" }).click({ timeout: 30_000 });
  await expect(page.getByTestId("report-panel").getByTestId("grade-score")).toHaveText("8.33/10", { timeout: 30_000 });
  await workspace.getByRole("tab", { name: "Key" }).click();
  const panel = page.getByTestId("keys-panel");
  const regradeCalls: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && /\/tests\/[^/]+\/regrade$/.test(r.url())) regradeCalls.push(r.url());
  });
  // R22.4.5.3: the key photo area before any change, at 1280×720.
  await page.setViewportSize({ width: 1280, height: 720 });
  await expect(panel.getByTestId("key-row").first()).toBeVisible();
  const photos = page.getByTestId("workspace-photos");
  const photosBefore = (await photos.boundingBox())!.height;

  // R22.4.8.5 + the 22.4.8 tooltip: a key verified elsewhere leaves the test pending; reopened, the
  // thread shows Keys changed on the Test tab as one compact line, with its hint on hover and focus.
  // A reload is no leave, so no re-grade starts; the one re-grade below covers this key too.
  const keys = await sidecarApi<{ question_id: string; status: string; accepted: string[] }[]>(
    "GET",
    `/tests/${seeded.testId}/keys`,
  );
  const unverified = keys.find((k) => k.status !== "teacher_verified");
  expect(unverified, "a key left to verify").toBeTruthy();
  await sidecarApi("PUT", `/tests/${seeded.testId}/keys/${unverified!.question_id}`, {
    verify: true,
  });
  expect((await sidecarApi<{ regrade_pending: boolean }>("GET", `/tests/${seeded.testId}`)).regrade_pending).toBe(true);
  await page.reload(); // a fresh window reads the thread's regrade_pending from the sidecar
  await page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadA!}"]`).click();
  const ws2 = page.getByTestId("workspace");
  await ws2.getByRole("tab", { name: "Test" }).click({ timeout: 30_000 });
  await expect(ws2).toHaveAttribute("data-kind", "test");
  const testBar = page.getByTestId("thread-top-bar");
  await expect(testBar).toHaveAttribute("data-compact", "true", { timeout: 30_000 });
  await expect(testBar.getByTestId("keys-changed")).toBeVisible();
  const testBarHeight = (await testBar.boundingBox())!.height;
  expect(testBarHeight).toBeLessThanOrEqual(40);
  console.log(`R22.4.8.5 Test tab bar ${testBarHeight}px`);
  const label = testBar.getByTestId("keys-changed-label");
  const hint = testBar.getByTestId("keys-changed-hint");
  await expect(hint).toBeHidden();
  await label.hover();
  await expect(hint).toBeVisible();
  await expect(hint).toHaveText("The scores update when you re-grade, leave the Key tab or leave this thread.");
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "reduce" });
  await page.screenshot({ path: "test-results/s22-4-8-compact-bar-test-light.png" });
  await page.mouse.move(1, 700);
  await expect(hint).toBeHidden();
  await label.focus();
  await expect(hint).toBeVisible();
  await expect(label).toHaveAccessibleDescription("The scores update when you re-grade, leave the Key tab or leave this thread.");
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "reduce" });
  await page.screenshot({ path: "test-results/s22-4-8-compact-bar-test-focus.png" });
  await page.keyboard.press("Escape");
  await expect(hint).toBeHidden();
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "no-preference" });
  await ws2.getByRole("tab", { name: "Key" }).click();
  await expect(panel.getByTestId("key-row").first()).toBeVisible();

  const verifiedIds: string[] = [];
  for (let i = 0; i < 2; i++) {
    const row = panel.locator('[data-testid="key-row"][data-status="ai_unverified"]').first();
    const qid = (await row.getAttribute("data-question-id"))!;
    const put = page.waitForResponse((r) => r.request().method() === "PUT" && /\/tests\/[^/]+\/keys\//.test(r.url()));
    await row.getByTestId("key-verify").click();
    const res = (await (await put).json()) as { run_ids: string[]; key: { status: string } };
    expect(res.key.status).toBe("teacher_verified");
    expect(res.run_ids).toEqual([]); // no run: the re-grade waits for the leave
    await expect(panel.locator(`[data-testid="key-row"][data-question-id="${qid}"]`)).toHaveAttribute("data-status", "teacher_verified");
    verifiedIds.push(qid);
  }
  const bar = page.getByTestId("keys-changed");
  await expect(bar).toContainText("Keys changed");
  await expect(bar.getByRole("button", { name: "Re-grade" })).toBeEnabled();
  // R22.4.5.3: on the Key tab the bar is one compact line; the photos lose only that line.
  const topBar = page.getByTestId("thread-top-bar");
  await expect(topBar).toHaveAttribute("data-compact", "true");
  const barHeight = (await topBar.boundingBox())!.height;
  expect(barHeight).toBeLessThanOrEqual(40);
  const photosAfter = (await photos.boundingBox())!.height;
  expect(photosBefore - photosAfter).toBeLessThanOrEqual(barHeight + 8);
  console.log(`R22.4.5.3 key bar ${barHeight}px; photos ${photosBefore}px -> ${photosAfter}px`);
  await page.screenshot({ path: "test-results/r22.4.5-key-bar-light.png" });
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "reduce" });
  await page.screenshot({ path: "test-results/r22.4.5-key-bar-reduced.png" });
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "no-preference" });
  await expect(page.getByTestId("thread-run")).toHaveCount(0);
  const pending = await sidecarApi<{ regrade_pending: boolean }>("GET", `/tests/${seeded.testId}`);
  expect(pending.regrade_pending).toBe(true);
  expect(regradeCalls).toHaveLength(0);

  // Leave the Key tab: exactly one re-grade call.
  const regrade = page.waitForResponse((r) => r.request().method() === "POST" && /\/tests\/[^/]+\/regrade$/.test(r.url()));
  await workspace.getByRole("tab", { name: "Report" }).click();
  const res = (await (await regrade).json()) as { run_ids: string[] };
  expect(res.run_ids).toHaveLength(2);
  await expect(page.getByTestId("keys-changed")).toHaveCount(0);

  const attempts = new Set<string>();
  for (const id of res.run_ids) {
    const r = await sidecarApi<RunDetail>("GET", `/runs/${id}`);
    expect(r.run.kind).toBe("grade");
    attempts.add(r.run.input.attempt_id ?? "");
    await waitRunDone(id);
  }
  expect([...attempts].sort()).toEqual([seeded.attemptA, attemptB].sort());
  expect(regradeCalls).toHaveLength(1);
  const after = await sidecarApi<{ regrade_pending: boolean }>("GET", `/tests/${seeded.testId}`);
  expect(after.regrade_pending).toBe(false);
  // The score after the re-grade (verifying keeps the keys, so it is the same value).
  await expect(page.getByTestId("report-panel").getByTestId("grade-score")).toHaveText("8.33/10", { timeout: 30_000 });
  expect(verifiedIds).toHaveLength(2);
});

test("R19.2: blank test → Grade → the key print lists one key per question, no student data", async ({ page }) => {
  test.setTimeout(300_000);
  const { threadId, detail } = await extracted(BLANK, null);
  const testId = detail.test?.id ?? detail.attempt!.test_id;
  const content = await sidecarApi<{ content: { sections: { groups: { questions: { id: string }[] }[] }[] } }>(
    "GET",
    `/tests/${testId}`,
  );
  const qids = content.content.sections.flatMap((s) => s.groups.flatMap((g) => g.questions.map((q) => q.id)));
  expect(qids.length).toBeGreaterThan(0);

  // The recorded S4 page reading returns template words for every answer, so the replayed
  // extraction keeps an attempt of unsure blanks and the card's Grade would grade that attempt.
  // The key copy is the test graded alone: what Grade sends for a card with no answers read
  // (ExtractionCard.test.tsx), and what grade-synthetic/blank-key recorded.
  const run = await sidecarApi<{ id: string }>("POST", `/threads/${threadId}/runs`, {
    kind: "grade",
    input: { test_id: testId, attempt_id: null, reason: "button" },
  });
  await waitRunDone(run.id);

  await open(page, threadId);
  await page.getByTestId("workspace").getByRole("tab", { name: "Key" }).click({ timeout: 30_000 });
  const panel = page.getByTestId("keys-panel");
  const rows = panel.getByTestId("key-row");
  await expect(rows).toHaveCount(qids.length, { timeout: 30_000 });
  const ids = await rows.evaluateAll((els) => els.map((e) => e.getAttribute("data-question-id")));
  expect(new Set(ids).size).toBe(ids.length);
  expect([...ids].sort()).toEqual([...qids].sort());
  for (const text of await panel.getByTestId("key-accepted").allTextContents()) expect(text.trim()).not.toBe("");

  await page.emulateMedia({ media: "print" });
  await expect(page.locator("nav").first()).toBeHidden();
  await expect(panel.getByTestId("keys-toolbar")).toBeHidden();
  await expect(rows.first()).toBeVisible();
  // What prints: the key copy only (no student name or class, no answers).
  const printed = await page.locator("body").innerText();
  expect(printed).not.toContain(STUDENT);
  expect(printed).not.toContain(CLASS);
  await expect(page.locator('[data-testid="answer-row"], [data-testid="report-row"], [data-testid="student-chip"]').filter({ visible: true })).toHaveCount(0);
  await page.emulateMedia({ media: "screen" });
});
