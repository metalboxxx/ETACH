/**
 * Step 22.5.5 (b, UI) on the replay sidecar (headless): what jsdom cannot measure. Synthetic names
 * only. Screenshots go to test-results/.
 * - R22.5.5.6: the Key tab's "AI unsure key" label is reached with Tab; focus or hover shows the
 *   checker's answer and reasoning, or "The check did not finish."; Esc hides it.
 * - R22.5.5.8 / R22.5.5.11: a student opened from the Students tab (click; Enter) shows
 *   "Skills — {student}" in the main panel: a table of level, skill, label and per-paper shares
 *   (date on focus); and the report's weak points
 *   ("{Skill} ({level}, {label}): {wrong}/{seen} wrong"), each with the "Later, after the basics (N)"
 *   line opened by Enter / Space; text meets 4.5:1 and the focus ring 3:1 (light only, PRD §10.1 v8.12).
 *
 * The checker results, skills and weak points come from routed GETs (as s13 raises
 * `other_thread_count`): the replay sidecar has no checker or grade run to make them.
 */
import { appendFileSync } from "node:fs";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { connect } from "./drop";
import { seedExtractedS1, sidecarApi } from "./seed";
import { settle } from "./settle";

/** WCAG contrast of two computed CSS colours (`rgb(…)`), in the page. */
async function contrast(page: Page, fg: string, bg: string): Promise<number> {
  return page.evaluate(
    ([a, b]) => {
      const lum = (c: string) => {
        const [r, g, bl] = (c.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number).map((v) => {
          const s = v / 255;
          return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * r! + 0.7152 * g! + 0.0722 * bl!;
      };
      const [hi, lo] = [lum(a!), lum(b!)].sort((x, y) => y - x);
      return (hi! + 0.05) / (lo! + 0.05);
    },
    [fg, bg],
  );
}

const css = (el: Locator, prop: string) => el.evaluate((e, p) => getComputedStyle(e).getPropertyValue(p), prop);

/** The first non-transparent background at or above `el`. */
const background = (el: Locator) =>
  el.evaluate((e) => {
    for (let n: Element | null = e; n; n = n.parentElement) {
      const bg = getComputedStyle(n).backgroundColor;
      if (bg && bg !== "transparent" && !bg.startsWith("rgba(0, 0, 0, 0)")) return bg;
    }
    return "rgb(255, 255, 255)";
  });

/** Every measured ratio, printed at the end of each test for the report. */
const measured: string[] = [];
const logContrast = () =>
  appendFileSync("test-results/s22.5.5-contrast.txt", `${test.info().title}\n  ${measured.join("\n  ")}\n`);

async function textAA(page: Page, el: Locator, what: string) {
  const ratio = await contrast(page, await css(el, "color"), await background(el));
  measured.push(`${what}: ${ratio.toFixed(2)}`);
  expect(ratio, what).toBeGreaterThanOrEqual(4.5);
}

/** The focus ring is drawn (solid outline) and meets 3:1 against what is around it. */
async function ringAA(page: Page, el: Locator, what: string) {
  expect(await css(el, "outline-style"), what).toBe("solid");
  const ratio = await contrast(page, await css(el, "outline-color"), await background(el.locator("..")));
  measured.push(`${what} focus ring: ${ratio.toFixed(2)}`);
  expect(ratio, what).toBeGreaterThanOrEqual(3);
}

/** Presses Tab until `el` has focus (keyboard reachable), at most `max` times. */
async function tabTo(page: Page, el: Locator, max = 80) {
  for (let i = 0; i < max; i++) {
    if (await el.evaluate((e) => e === document.activeElement)) return;
    await page.keyboard.press("Tab");
  }
  await expect(el).toBeFocused();
}

/** Routes a GET to the sidecar's own answer, changed by `edit`. */
async function editGet(page: Page, url: string, edit: (json: never) => unknown) {
  await page.route(url, async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const res = await route.fetch();
    await route.fulfill({ response: res, json: edit((await res.json()) as never) });
  });
}

const REASONING = "The subject is plural, so the verb has no -s.";

for (const scheme of ["light"] as const) {
  test(`R22.5.5.6: the Key tab's checker tip, by keyboard and hover (${scheme})`, async ({ page }) => {
    test.setTimeout(300_000);
    measured.length = 0;
    const seeded = await seedExtractedS1();
    // The replay test has no keys yet (not graded): the Key tab gets three, two of them unsure.
    const stored = await sidecarApi<{ content: { sections: { groups: { questions: { id: string }[] }[] }[] } }>("GET", `/tests/${seeded.testId}`);
    const ids = stored.content.sections.flatMap((s) => s.groups.flatMap((g) => g.questions.map((q) => q.id))).slice(0, 3);
    const checkers = [
      { status: "disagreed", answer: "B", reasoning: REASONING },
      { status: "did_not_finish", answer: null, reasoning: null },
      null,
    ];
    const keys = ids.map((question_id, i) => ({
      question_id,
      test_id: seeded.testId,
      accepted: ["A"],
      source: "ai",
      status: checkers[i] ? "ai_uncertain" : "ai_verified",
      confidence: null,
      reason_vi: null,
      updated_at: "2026-10-24T09:00:00Z",
      checker: checkers[i],
    }));
    await page.route(`**/tests/${seeded.testId}/keys`, (route) =>
      route.request().method() === "GET" ? route.fulfill({ json: keys }) : route.continue(),
    );
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await connect(page);
    await page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`).click();
    const workspace = page.getByTestId("workspace");
    await expect(workspace).toHaveAttribute("data-kind", "test", { timeout: 30_000 });
    await workspace.getByRole("tab", { name: "Key" }).click();

    const tips = workspace.getByTestId("key-checker-tip");
    await expect(tips).toHaveCount(2, { timeout: 30_000 });
    const first = page.locator('[tabindex="0"][aria-describedby]').filter({ hasText: "AI unsure key" }).first();
    const second = page.locator('[tabindex="0"][aria-describedby]').filter({ hasText: "AI unsure key" }).nth(1);
    const tip1 = tips.nth(0);
    const tip2 = tips.nth(1);
    await expect(first).toHaveAccessibleDescription(`The checker's answer: B ${REASONING}`);
    await expect(second).toHaveAccessibleDescription("The check did not finish.");

    // keyboard: Tab reaches the label, the tip opens; Esc hides it
    await tabTo(page, first);
    await expect(tip1).toHaveAttribute("data-open", "true");
    await expect(tip1).toBeVisible();
    await ringAA(page, first, "key label");
    await textAA(page, first, "key label (AI unsure key)");
    for (const line of await tip1.locator("span").all()) await textAA(page, line, `key tip line "${(await line.innerText()).slice(0, 24)}"`);
    await settle(page);
    await workspace.screenshot({ path: `test-results/s22.5.5-key-tip-${scheme}.png`, animations: "disabled" });
    await page.keyboard.press("Escape");
    await expect(tip1).toHaveAttribute("data-open", "false");
    await expect(tip1).toBeHidden();

    // hover: the second label says the check did not finish
    await page.keyboard.press("Tab"); // focus leaves the first label
    await second.hover();
    await expect(tip2).toHaveAttribute("data-open", "true");
    await expect(tip2).toHaveText("The check did not finish.");
    await textAA(page, tip2.locator("span").first(), "key tip (did not finish)");
    logContrast();
  });

  test(`R22.5.5.11: a student opens the skills view in the main panel (${scheme})`, async ({ page }) => {
    test.setTimeout(300_000);
    measured.length = 0;
    const seeded = await seedExtractedS1();
    const name = "Học Sinh Kỹ Năng";
    const existing = (await sidecarApi<{ id: string; full_name: string }[]>("GET", "/students")).find((s) => s.full_name === name);
    const student = existing ?? (await sidecarApi<{ id: string }>("POST", "/students", { full_name: name, class_name: "9X1" }));
    const papers = [
      { attempt_id: seeded.attemptId, counted: 4, share: 0.25, taken_on: "2026-09-15" },
      { attempt_id: `${seeded.attemptId}-b`, counted: 5, share: 0.4, taken_on: "2026-10-01" },
      { attempt_id: `${seeded.attemptId}-c`, counted: 4, share: 0.75, taken_on: "2026-10-20" },
    ];
    const skill = (tag: string, skill_name: string, level: string | null, label: string, weak: boolean, held_back: boolean) => ({
      skill_tag: tag,
      skill_name,
      level,
      label,
      weak,
      held_back,
      papers,
    });
    await editGet(page, `**/students/${student.id}`, (d: Record<string, unknown>) => ({
      ...d,
      skills: [
        skill("G.PRES", "Present simple and present continuous for habits and routines", "A1", "consistently_weak", true, false),
        skill("G.PAST", "Past simple", "A1", "slipped", true, false),
        skill("V.FAM", "Family words", "A1", "improved", false, false),
        skill("G.ART", "Articles", "A2", "solid", false, false),
        { ...skill("P.STR", "Word stress", null, "not_enough_evidence", false, false), papers: papers.slice(0, 1) },
        skill("G.COND", "Conditionals", "B1", "inconsistent", true, true),
        skill("G.PASS", "Passive voice", "B2", "consistently_weak", true, true),
      ],
    }));
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await connect(page);
    await page.getByRole("tab", { name: "Students" }).click();
    const row = page.locator(`[data-testid="student-row"][data-student-id="${student.id}"]`);
    const item = row.getByTestId("student-item");
    // click opens the view; the sidebar row lists no skills
    await item.click();
    const view = page.getByTestId("student-view");
    await expect(view).toBeVisible({ timeout: 30_000 });
    await expect(view.getByRole("heading", { level: 2 })).toHaveText(`Skills — ${name}`);
    await expect(page.getByTestId("students-tab").getByTestId("student-skill")).toHaveCount(0);
    await expect(item).toHaveAttribute("aria-current", "page");
    // Esc leaves; Enter on the row opens it again
    await page.keyboard.press("Escape");
    await expect(view).toBeHidden();
    await expect(item).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(view).toBeVisible();

    const table = view.getByTestId("student-skills-table").first();
    await expect(table.getByRole("columnheader")).toHaveText(["Level", "Skill", "Label", "Papers"]);
    const rows = view.getByTestId("student-skill");
    await expect(rows).toHaveCount(5, { timeout: 30_000 });
    await expect(view.getByTestId("student-skill-label")).toHaveText([
      "Consistently weak",
      "Slipped",
      "Improved",
      "Solid",
      "Not enough evidence yet",
    ]);
    // the full name wraps, not cut
    const longName = rows.first().getByTestId("student-skill-name");
    await expect(longName).toHaveText("Present simple and present continuous for habits and routines");
    expect(await longName.evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(true);
    await expect(rows.first().getByTestId("student-skill-share")).toHaveText(["25%", "40%", "75%"]);

    // Enter opens the Later line, Space closes and opens it again
    const toggle = view.getByTestId("skills-later-toggle");
    await expect(toggle).toHaveText(/Later, after the basics \(2\)$/);
    await tabTo(page, toggle);
    await ringAA(page, toggle, "skills Later line");
    await page.keyboard.press("Enter");
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await page.keyboard.press("Space");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(view.getByTestId("skills-later-list")).toBeHidden();
    await page.keyboard.press("Space");
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(rows).toHaveCount(7);
    await textAA(page, toggle, "skills Later line");

    await textAA(page, table.locator("caption"), "table caption");
    await textAA(page, table.getByRole("columnheader").first(), "column header");
    await textAA(page, view.getByRole("heading", { level: 2 }), "view title");
    for (const s of await rows.all()) {
      const tag = await s.getAttribute("data-skill");
      const level = s.getByTestId("student-skill-level");
      await textAA(page, level, `skill ${tag} level`);
      await textAA(page, s.getByTestId("student-skill-name"), `skill ${tag} name`);
      await textAA(page, s.getByTestId("student-skill-label").locator("span"), `skill ${tag} label (${await s.getAttribute("data-label")})`);
      await textAA(page, s.getByTestId("student-skill-share").first(), `skill ${tag} share`);
    }

    // a share's date: reached with Tab, shown on focus, Esc hides it
    const share = rows.first().getByTestId("student-skill-share").first();
    await share.focus();
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Tab");
    await expect(share).toBeFocused();
    await ringAA(page, share, "paper share");
    const tip = rows.first().getByTestId("student-skill-date").first();
    await expect(tip).toBeVisible();
    await expect(tip).toHaveText("Taken 15 Sep 2026: 25% right, 4 questions");
    await textAA(page, tip.locator("span").first(), "share date tip");
    await settle(page);
    await page.screenshot({ path: `test-results/s22.5.5-students-skills-${scheme}.png`, animations: "disabled" });
    await page.keyboard.press("Escape");
    await expect(tip).toBeHidden();
    await expect(view).toBeVisible(); // Esc on the tip closes only the tip

    // the student's thread is listed and opens its thread, leaving the view
    const threadLink = view.getByTestId("student-thread");
    if ((await threadLink.count()) > 0) await textAA(page, threadLink.first(), "thread link");
    await page.getByRole("tab", { name: "Chats" }).click();
    await expect(view).toBeHidden();
    logContrast();
  });

  test(`R22.5.5.8: the report's weak points and the Later line (${scheme})`, async ({ page }) => {
    test.setTimeout(300_000);
    measured.length = 0;
    const seeded = await seedExtractedS1();
    const thread = await sidecarApi<{ attempt: Record<string, unknown> }>("GET", `/threads/${seeded.threadId}`);
    // The thread as loaded has a graded attempt, and its report has weak points.
    await editGet(page, `**/threads/${seeded.threadId}`, (d: { attempt: Record<string, unknown> | null }) => ({
      ...d,
      attempt: d.attempt && { ...d.attempt, status: "graded" },
    }));
    const weak = (tag: string, skill_name: string, level: string | null, label: string | null, wrong: number, seen: number, held_back: boolean) => ({
      skill_tag: tag,
      skill_name,
      level,
      label,
      wrong,
      seen,
      gap_errors: wrong,
      note_vi: "",
      held_back,
    });
    const report = {
      attempt: { ...thread.attempt, status: "graded", score_earned: 6.5, score_possible: 10 },
      verdicts: [
        { question_id: "q-e2e-1", printed_number: 1, value: "B", verdict: "correct", points: 0.25 },
        { question_id: "q-e2e-2", printed_number: 2, value: "A", verdict: "wrong", points: 0 },
      ],
      explanations: [],
      report: {
        attempt_id: seeded.attemptId,
        run_id: "run-e2e",
        created_at: "2026-10-24T09:00:00Z",
        summary_vi: "Em cần ôn lại thì hiện tại đơn.",
        teacher_questions: [],
        careless_notes: [],
        uncertain_points: 0,
        weak_points: [
          weak("G.PRES", "Present simple", "A1", "consistently_weak", 3, 4, false),
          weak("G.ART", "Articles", "A2", "this_paper_only", 2, 3, false),
          weak("G.COND", "Conditionals", "B1", "inconsistent", 2, 2, true),
        ],
      },
    };
    await page.route(`**/attempts/${seeded.attemptId}/report`, (route) =>
      route.request().method() === "GET" ? route.fulfill({ json: report }) : route.continue(),
    );
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await connect(page);
    await page.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`).click();
    const workspace = page.getByTestId("workspace");
    await expect(workspace).toHaveAttribute("data-kind", "test", { timeout: 30_000 });
    await workspace.getByRole("tab", { name: "Report" }).click({ timeout: 30_000 });
    const panel = workspace.getByTestId("report-panel");
    await expect(panel).toBeVisible({ timeout: 30_000 });
    const points = panel.getByTestId("weak-point");
    await expect(points).toHaveText([
      "Present simple (A1, consistently weak): 3/4 wrong",
      "Articles (A2, this paper only): 2/3 wrong",
    ]);

    const toggle = panel.getByTestId("weak-later-toggle");
    await expect(toggle).toHaveText(/Later, after the basics \(1\)$/);
    await tabTo(page, toggle);
    await ringAA(page, toggle, "report Later line");
    await page.keyboard.press("Space");
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await page.keyboard.press("Enter");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await page.keyboard.press("Enter");
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(points).toHaveCount(3);
    await expect(points.nth(2)).toHaveText("Conditionals (B1, inconsistent): 2/2 wrong");
    await textAA(page, toggle, "report Later line");
    for (const p of await points.all()) {
      const tag = await p.getAttribute("data-skill");
      await textAA(page, p, `weak point ${tag}`);
      await textAA(page, p.locator("span.font-medium"), `weak point ${tag} skill`);
      await textAA(page, p.getByTestId("weak-point-tags"), `weak point ${tag} level and label`);
    }
    await settle(page);
    await panel.locator("section").filter({ has: page.getByTestId("weak-point") }).screenshot({
      path: `test-results/s22.5.5-report-weak-${scheme}.png`,
      animations: "disabled",
    });
    logContrast();
  });
}
