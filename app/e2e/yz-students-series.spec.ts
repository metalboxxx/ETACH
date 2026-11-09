/**
 * Step 22.3.3 (R22.3.3.5) on a replay sidecar of its own: Delete… on a seeded student in the
 * Students tab, and Copy details from… between two tests. Synthetic names only.
 *
 * The replay folder holds the `s1-seeded/extract` scenario twice (as s6 does for a duplicate):
 * each extract saves a new test. A student is made first with the scrubbed name the papers read
 * ("Học Sinh A", 8X1), so they get both threads. Deleting the student removes the threads
 * the dialog lists and leaves both tests in the bank; then one test copies the other's details.
 */
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { connect, dropFiles } from "./drop";
import { sidecarApi, startExtract, waitRunDone } from "./seed";
import { CASSETTE_ROOT, scenarioReplayFolder, startSidecar, type Sidecar } from "./sidecar";
import { settle } from "./settle";

const EXTRACT = join(CASSETTE_ROOT, "s1-seeded", "extract");
const SERIES = ["occasion", "term", "school", "source", "year"] as const;

type Meta = Record<string, unknown>;
interface ThreadDetail {
  attempt: { id: string; test_id: string } | null;
}
interface Preview {
  threads: { id: string; shown_title: string }[];
  kept_threads: { id: string }[];
}

let sidecar: Sidecar;
const saved = { port: process.env.ETACH_E2E_PORT, token: process.env.ETACH_E2E_TOKEN };

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  test.setTimeout(150_000);
  sidecar = await startSidecar(120_000, [], scenarioReplayFolder([EXTRACT, EXTRACT]));
  process.env.ETACH_E2E_PORT = String(sidecar.port);
  process.env.ETACH_E2E_TOKEN = sidecar.token;
});

test.afterAll(async () => {
  process.env.ETACH_E2E_PORT = saved.port;
  process.env.ETACH_E2E_TOKEN = saved.token;
  await sidecar?.stop();
});

async function extract(folder: string): Promise<{ threadId: string; testId: string }> {
  const run = await startExtract(folder, null);
  await waitRunDone(run.runId);
  const d = await sidecarApi<ThreadDetail>("GET", `/threads/${run.threadId}`);
  return { threadId: run.threadId, testId: d.attempt!.test_id };
}

test("delete a student and copy test details (R22.3.3.5)", async ({ page }) => {
  test.setTimeout(420_000);
  const student = await sidecarApi<{ id: string }>("POST", "/students", {
    full_name: "Học Sinh A",
    class_name: "8X1",
  });
  const a = await extract(EXTRACT);
  const b = await extract(EXTRACT);
  expect(a.testId).not.toBe(b.testId);
  const preview = await sidecarApi<Preview>("GET", `/students/${student.id}/delete-preview`);
  expect(preview.threads.map((t) => t.id).sort()).toEqual([a.threadId, b.threadId].sort());

  await page.goto(`/#port=${sidecar.port}&token=${sidecar.token}`);

  // Students tab: Delete… asks first, lists the threads, then the row goes.
  await page.getByRole("tab", { name: "Students" }).click();
  const row = page.locator(`[data-testid="student-row"][data-student-id="${student.id}"]`);
  await expect(row).toBeVisible();
  await row.getByTestId("student-delete-button").click();
  const dialog = page.getByTestId("confirm-dialog");
  await expect(dialog).toContainText("Delete “Học Sinh A”?");
  if (preview.threads.length > 0) {
    await expect(dialog.getByTestId("delete-threads").getByRole("listitem")).toHaveCount(preview.threads.length);
  }
  // Step 22.5.8 (f): the brick delete button and dialog, for the teacher's theme review.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await settle(page);
  await page.screenshot({ path: "test-results/f-theme-delete-student-dialog.png" });
  await dialog.getByRole("button", { name: "Delete student" }).click();
  await expect(row).toHaveCount(0);
  const students = await sidecarApi<{ id: string }[]>("GET", "/students");
  expect(students.some((s) => s.id === student.id)).toBe(false);
  const threads = await sidecarApi<{ thread: { id: string } }[]>("GET", "/threads");
  for (const t of preview.threads) expect(threads.some((x) => x.thread.id === t.id)).toBe(false);
  const bank = await sidecarApi<{ id: string; display_name: string }[]>("GET", "/tests");
  expect(bank.map((t) => t.id).sort()).toEqual([a.testId, b.testId].sort()); // the tests stay

  // Give the source test series details, then copy them into the other test from the UI.
  const source = bank.find((t) => t.id === a.testId)!;
  await sidecarApi("PATCH", `/tests/${a.testId}`, {
    meta: { occasion: "MidTerm", term: 2, school: "Synthetic School E2E", source: null, year: "2024-2025" },
  });
  const sourceMeta = (await sidecarApi<{ meta: Meta; display_name?: string }>("GET", `/tests/${a.testId}`)).meta;
  const before = (await sidecarApi<{ meta: Meta }>("GET", `/tests/${b.testId}`)).meta;
  const name = (await sidecarApi<{ id: string; display_name: string }[]>("GET", "/tests")).find((t) => t.id === a.testId)!
    .display_name;
  expect(name).not.toBe(source.display_name); // the automatic name followed the edit

  await page.getByRole("tab", { name: "Tests" }).click();
  await page.locator(`[data-testid="test-item"][data-test-id="${b.testId}"]`).click();
  const open = page.getByTestId("copy-details-open");
  await open.click();
  const search = page.getByTestId("copy-details-search");
  await expect(search).toBeFocused();
  // Step 22.4.3 (R22.4.3.1): focus alone lists the recent tests, without the test itself.
  await expect(page.getByTestId("copy-details-options").getByRole("option")).toHaveCount(1);
  await search.fill("Synthetic School");
  await page.getByRole("option").filter({ hasText: a.testId }).click();
  await expect(page.getByTestId("copy-details-values").getByTestId("copy-details-row")).toHaveCount(5);
  await page.getByTestId("copy-details-save").click();
  await expect(page.getByTestId("copy-details-box")).toHaveCount(0);
  await expect(open).toBeFocused();

  const after = (await sidecarApi<{ meta: Meta & { edited_fields: string[] } }>("GET", `/tests/${b.testId}`)).meta;
  for (const f of SERIES) {
    const v = sourceMeta[f];
    const blank = v === null || v === undefined || v === "";
    expect(after[f], f).toEqual(blank ? before[f] : v);
  }
  expect(after.grade).toEqual(before.grade);
  expect(after.test_number).toEqual(before.test_number);
  expect(after.edited_fields).toEqual(expect.arrayContaining(["occasion", "term", "school", "year"]));
});

test("the new-thread pickers list recent tests on focus (R22.4.3.1)", async ({ page }) => {
  // Runs after the test above: the bank holds its two tests, one with the school "Synthetic School E2E".
  const bank = await sidecarApi<{ id: string }[]>("GET", "/tests");
  // Step 22.5.2 (D5, R22.5.2.8): "Same series as" lists the Series list's names, not tests or schools.
  await sidecarApi("POST", "/series", { name: "Synthetic Series E2E" });
  const seriesNames = (await sidecarApi<{ name: string }[]>("GET", "/series")).map((s) => s.name);
  await connect(page);
  await expect(page.getByTestId("connection-notice")).toHaveCount(0);
  await dropFiles(page, [join(import.meta.dirname, "fixtures", "two-pages.pdf")]);
  const card = page.getByTestId("photo-check-card");
  await expect(card.getByTestId("photo-thumb")).toHaveCount(2);

  // Existing test: a click lists the recent tests before any typing; Esc closes the list.
  const existing = card.getByTestId("existing-test-search");
  await existing.click();
  await expect(existing).toHaveAttribute("aria-expanded", "true");
  await expect(card.getByTestId("existing-test-options").getByRole("option")).toHaveCount(Math.min(bank.length, 8));
  await existing.press("Escape");
  await expect(card.getByTestId("existing-test-options")).toHaveCount(0);
  await existing.press("ArrowDown");
  await expect(card.getByTestId("existing-test-options")).toBeVisible();

  // Same series as: leaving the Existing test box closes its list; the series list opens on focus.
  const series = card.getByTestId("series-test-search");
  // Step 22.4.8 (R22.4.8.2): the two boxes start at the same x.
  const left = async (l: typeof series) => (await l.boundingBox())!.x;
  expect(Math.abs((await left(existing)) - (await left(series)))).toBeLessThan(0.5);
  await series.focus();
  await expect(card.getByTestId("existing-test-options")).toHaveCount(0);
  const options = card.getByTestId("series-test-options").getByRole("option");
  await expect(options).toHaveText(seriesNames);
  for (const scheme of ["light"] as const) {
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" }); // no colour transition mid-shot
    await page.screenshot({ path: `test-results/yz-series-picker-${scheme}.png` });
    await card.screenshot({ path: `test-results/s22-4-8-aligned-boxes-${scheme}.png` });
  }
  await page.emulateMedia({ colorScheme: "light" });
  await expect(options.filter({ hasText: "Synthetic School E2E" })).toHaveCount(0);
  const named = options.filter({ hasText: /^Synthetic Series E2E$/ });
  await expect(named).toHaveCount(1);
  await named.click();
  await expect(card.getByTestId("series-test-picked")).toHaveText("Synthetic Series E2E");
  await expect(card.getByTestId("series-test-options")).toHaveCount(0);
});
