/**
 * Step 22.5.8 (h), R22.5.8.9 (PRD §10.1 v8.21): the layout, headless. The corner values (papers
 * 2 px, buttons 6 px, arch-topped tabs, round chips), the sidebar (the open row's tint differs from
 * the hover tint, every name at the same x, the blue focus outline on every sidebar control, the
 * group headings in small capitals), the workspace paper and its double rule, nothing clipped at
 * 1280 and 900 px. Screenshots for the teacher go to test-results/layout-*.png (after settle).
 * Runs after s12 (file order, one worker) and reuses the S1 thread; alone, it seeds one. The students
 * and the thread it adds are deleted at the end, so the later specs see the data they expect.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";
import { connect } from "./drop";
import { seedExtractedS1, sidecarApi } from "./seed";
import { settle } from "./settle";

const SHOTS = "test-results";
const BLUE = "rgb(53, 57, 227)";
const TINT = "rgb(219, 219, 241)"; // --etach-tint
const TINT_STRONG = "rgb(200, 201, 239)"; // --etach-tint-strong

const style = (l: Locator, prop: string) => l.evaluate((e, p) => getComputedStyle(e).getPropertyValue(p), prop);

async function tabTo(page: Page, el: Locator, max = 80) {
  for (let i = 0; i < max; i++) {
    if (await el.evaluate((e) => e === document.activeElement)) return;
    await page.keyboard.press("Tab");
  }
  await expect(el).toBeFocused();
}

/** The control's focus outline, after reaching it with the keyboard. */
async function expectBlueRing(page: Page, el: Locator, what: string) {
  await tabTo(page, el);
  await expect(el, what).toBeFocused();
  expect(await style(el, "outline-style"), what).toBe("solid");
  expect(await style(el, "outline-width"), what).toBe("2px");
  expect(await style(el, "outline-color"), what).toBe(BLUE);
}

/** Every visible, enabled focusable control in the sidebar shows the blue 2 px outline when focused
 *  from the keyboard (PRD §10.1 v8.21: every sidebar control). */
async function sidebarRings(page: Page, nav: Locator, where: string) {
  await page.keyboard.press("Shift"); // keyboard modality, so programmatic focus is :focus-visible
  const bad = await nav.evaluate((n, blue) => {
    const out: string[] = [];
    for (const el of n.querySelectorAll<HTMLElement>("button, input, select, textarea, [tabindex='0']")) {
      if (el.offsetParent === null || (el as HTMLButtonElement).disabled) continue;
      el.focus();
      const s = getComputedStyle(el);
      if (s.outlineStyle !== "solid" || s.outlineWidth !== "2px" || s.outlineColor !== blue) {
        const name = (el.getAttribute("aria-label") ?? el.textContent ?? el.getAttribute("placeholder") ?? "").trim();
        out.push(`${el.tagName.toLowerCase()} "${name}": ${s.outlineStyle} ${s.outlineWidth} ${s.outlineColor}`);
      }
      // A ring drawn inside (negative offset) sits on the control's own background: it must stand
      // out from it (>= 3:1), so a blue-filled control needs its ring outside.
      if (parseFloat(s.outlineOffset) < 0) {
        const lum = (c: string) => {
          const [r, g, b] = (c.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number).map((v) => {
            const x = v / 255;
            return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
          });
          return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!;
        };
        let bg = "rgb(255, 255, 255)";
        for (let p: Element | null = el; p; p = p.parentElement) {
          const c = getComputedStyle(p).backgroundColor;
          if (c && !c.startsWith("rgba(0, 0, 0, 0)") && c !== "transparent") {
            bg = c;
            break;
          }
        }
        const [hi, lo] = [lum(s.outlineColor), lum(bg)].sort((x, y) => y - x);
        const ratio = (hi! + 0.05) / (lo! + 0.05);
        if (ratio < 3) out.push(`${el.tagName.toLowerCase()} "${(el.textContent ?? "").trim()}": inner ring ${ratio.toFixed(2)}:1 on ${bg}`);
      }
    }
    (document.activeElement as HTMLElement | null)?.blur();
    return out;
  }, BLUE);
  expect(bad, where).toEqual([]);
}

/** Every element of `sel` fits its box on one line (nothing clipped or wrapped). */
async function fits(page: Page, sel: string, where: string) {
  const bad = await page.evaluate(
    (s) =>
      [...document.querySelectorAll<HTMLElement>(s)]
        .filter((e) => e.offsetParent !== null)
        .filter((e) => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).textOverflow !== "ellipsis")
        .map((e) => (e.textContent ?? "").trim()),
    sel,
  );
  expect(bad, where).toEqual([]);
}

test("R22.5.8.9: the layout of PRD §10.1 v8.21", async ({ page }) => {
  test.setTimeout(300_000);
  const seeded = await seedExtractedS1();
  // A few students, so the Students list has rows to show.
  const made: { students: string[]; thread: string | null } = { students: [], thread: null };
  for (const [full_name, school] of [
    ["Layout Lan", "Trường Lômônôxốp"],
    ["Layout Minh", "THCS Nguyễn Du"],
    ["Layout Hoa", null],
  ] as const) {
    made.students.push((await sidecarApi<{ id: string }>("POST", "/students", { full_name, class_name: "8A", school })).id);
  }
  // A second thread, so a row that is not open can be hovered.
  made.thread = (await sidecarApi<{ thread_id: string }>("POST", "/threads", { title: "Layout thread with a rather long name that the sidebar cuts" })).thread_id;
  try {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await connect(page);
    const nav = page.getByRole("navigation", { name: "Sidebar" });

    // --- the start screen -------------------------------------------------------------------
    await nav.getByTestId("sidebar-new-thread").click();
    const start = page.getByTestId("empty-state");
    await expect(start).toBeVisible();
    // The start screen (v8.25): no heading; a dotted portrait box like a sheet of A4 (2 px corners,
    // the input-border grey, >= 3:1 on the page) that fits the space without scrolling, at 1280
    // and at 900 px; dragging files over it turns its border blue and fills it with the light tint.
    const conversation = page.getByTestId("conversation");
    await expect(conversation.getByRole("heading")).toHaveCount(0);
    expect(await style(start, "border-top-style")).toBe("dotted");
    expect(await style(start, "border-top-width")).toBe("2px");
    expect(await style(start, "border-top-color")).toBe("rgb(115, 117, 140)");
    expect(await style(start, "border-radius")).toBe("2px");
    for (const [w, h] of [
      [1280, 720],
      [900, 700],
    ] as const) {
      await page.setViewportSize({ width: w, height: h });
      const b = (await start.boundingBox())!;
      const area = (await conversation.boundingBox())!;
      console.log(`R22.5.8.9 start box at ${w}x${h}: ${Math.round(b.width)} x ${Math.round(b.height)}`);
      expect(b.height / b.width, `A4 portrait at ${w}`).toBeCloseTo(1.414, 1);
      expect(b.y >= area.y && b.y + b.height <= area.y + area.height && b.x + b.width <= area.x + area.width, `box fits at ${w}`).toBe(true);
      expect(await conversation.evaluate((c) => c.scrollHeight <= c.clientHeight + 1)).toBe(true);
    }
    await page.setViewportSize({ width: 1280, height: 720 });
    await settle(page);
    await page.screenshot({ path: `${SHOTS}/layout-start-screen.png` });
    const dragged = await page.evaluateHandle(() => {
      const t = new DataTransfer();
      t.items.add(new File(["x"], "page.jpg", { type: "image/jpeg" }));
      return t;
    });
    await conversation.dispatchEvent("dragenter", { dataTransfer: dragged });
    await expect(start).toHaveAttribute("data-dragging", "true");
    await expect.poll(() => style(start, "border-top-color")).toBe(BLUE);
    await expect.poll(() => style(start, "background-color")).toBe(TINT);
    await expect(page.getByTestId("drop-overlay")).toHaveCount(0);
    await settle(page);
    await page.screenshot({ path: `${SHOTS}/layout-start-screen-dragover.png` });
    await conversation.dispatchEvent("dragleave", { dataTransfer: dragged });
    await expect(start).not.toHaveAttribute("data-dragging", "true");

    // --- the open thread, the hover tint, names at one x --------------------------------------
    const open = nav.locator(`[data-testid="thread-item"][data-thread-id="${seeded.threadId}"]`);
    await open.click();
    await expect(page.getByTestId("workspace")).toBeVisible({ timeout: 30_000 });
    await expect(open).toHaveAttribute("aria-current", "true");
    const row = (l: Locator) => l.locator("xpath=..");
    await page.mouse.move(0, 0);
    await expect.poll(() => style(row(open), "background-color")).toBe(TINT_STRONG);
    const other = nav.locator('[data-testid="thread-item"]:not([aria-current])').first();
    await other.hover();
    await expect.poll(() => style(row(other), "background-color")).toBe(TINT);
    expect(TINT).not.toBe(TINT_STRONG);
    await page.mouse.move(0, 0);
    // The space a name gets before it is cut (logged for the report), and the menu button at the
    // row's outer right edge.
    const space = await nav.getByTestId("thread-item").first().evaluate((b) => {
      const row = b.parentElement!.getBoundingClientRect();
      const name = b.querySelector<HTMLElement>('[data-testid="thread-name"]')!.getBoundingClientRect();
      const menu = b.parentElement!.querySelector<HTMLElement>('[data-testid="thread-menu-button"]')?.getBoundingClientRect();
      return { row: Math.round(row.width), name: Math.round(name.width * 10) / 10, menuRightGap: menu ? Math.round((row.right - menu.right) * 10) / 10 : null };
    });
    console.log(`R22.5.8.9 row name space ${JSON.stringify(space)}`);
    expect(space.menuRightGap, "the menu button at the row's outer right edge").toBe(0);
    // The menu button shows the three-dot SVG (no "…" text), its dots in the row's vertical middle.
    for (const b of await nav.getByTestId("thread-menu-button").all()) {
      expect((await b.textContent())!.trim()).toBe("");
      const dots = b.getByTestId("dots-icon");
      await expect(dots).toBeVisible();
      const d = (await dots.boundingBox())!;
      const r = (await b.locator("xpath=..").boundingBox())!;
      expect(Math.abs(d.y + d.height / 2 - (r.y + r.height / 2)), "dots centred on the row").toBeLessThanOrEqual(1);
    }
    // a long name is cut with the text's own ellipsis, before the slot and the menu
    const cut = nav.locator(`[data-testid="thread-item"][data-thread-id="${made.thread}"]`).getByTestId("thread-name");
    expect(await cut.evaluate((e) => e.scrollWidth > e.clientWidth && getComputedStyle(e).textOverflow === "ellipsis")).toBe(true);
    const xs = await nav.getByTestId("thread-name").evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().left)));
    expect(new Set(xs).size, `name x ${xs.join(", ")}`).toBe(1);

    // --- the folder tabs: the selected tab opens into the white page, no line or gap -----------
    const sideTab = nav.locator('[role="tab"][aria-selected="true"]');
    const sidePage = nav.getByTestId("sidebar-page");
    expect(await style(sideTab, "background-color")).toBe(await style(sidePage, "background-color"));
    expect(await style(sidePage, "background-color")).toBe("rgb(255, 255, 255)");
    expect(await style(nav.getByTestId("sidebar-page-end"), "background-color")).toBe("rgb(255, 255, 255)");
    const st = (await sideTab.boundingBox())!;
    const sp = (await sidePage.boundingBox())!;
    expect(st.y + st.height, `tab bottom ${st.y + st.height}, page top ${sp.y}`).toBeGreaterThanOrEqual(sp.y);
    const se = (await nav.getByTestId("sidebar-page-end").boundingBox())!;
    expect(Math.abs(sp.y + sp.height - se.y), "page and Settings meet").toBeLessThanOrEqual(0.5);
    const unselected = nav.locator('[role="tab"]:not([aria-selected="true"])').first();
    expect(await style(unselected, "background-color")).toBe("rgba(0, 0, 0, 0)"); // the sidebar grey shows

    // --- group headings: centred bold small capitals with a short rule ------------------------
    const heading = nav.getByTestId("group-heading").first().getByRole("heading");
    expect(await style(heading, "font-variant-caps")).toBe("small-caps");
    expect(await style(heading, "font-weight")).toBe("600");
    expect(await style(heading, "text-align")).toBe("center");
    expect(await style(nav.getByTestId("group-rule").first(), "height")).toBe("1px");

    // --- corners ---------------------------------------------------------------------------
    const ws = page.getByTestId("workspace");
    expect(await style(ws.getByTestId("workspace-paper"), "border-radius")).toBe("2px");
    expect(await style(ws.getByTestId("grade-answers"), "border-radius")).toBe("6px");
    const tab = ws.getByRole("tab").first();
    expect(await style(tab, "border-top-left-radius")).toBe("6px");
    expect(await style(tab, "border-bottom-left-radius")).toBe("0px");
    expect(await style(tab, "border-bottom-width")).toBe("0px");
    expect(parseFloat(await style(ws.getByTestId("test-name-chip"), "border-top-left-radius"))).toBeGreaterThan(100);
    // the selected tab stands on the paper: its bottom edge meets the paper's top edge
    const selected = ws.locator('[role="tab"][aria-selected="true"]');
    const tb = (await selected.boundingBox())!;
    const pb = (await ws.getByTestId("workspace-paper").boundingBox())!;
    expect(Math.abs(tb.y + tb.height - pb.y), `tab bottom ${tb.y + tb.height}, paper top ${pb.y}`).toBeLessThanOrEqual(1);
    // the double rule under the header
    expect(await style(ws.getByTestId("workspace-header"), "background-size")).toBe("100% 2px, 100% 1px");
    await fits(page, '[data-testid="workspace"] button, [data-testid="workspace"] [role="tab"]', "1280 workspace");
    await settle(page);
    await page.screenshot({ path: `${SHOTS}/layout-workspace-1280.png` });

    // Format help: its examples are Faustina too (every text in Faustina, the teacher).
    await ws.getByTestId("format-help").click();
    const help = ws.getByTestId("format-help-region");
    await expect(help).toBeVisible();
    const example = help.locator("td.font-mono").first();
    await example.scrollIntoViewIfNeeded();
    expect(await style(example, "font-family")).toMatch(/^"?Faustina"?/);
    await help.evaluate((h) => h.scrollIntoView({ block: "center" }));
    await settle(page);
    await page.screenshot({ path: `${SHOTS}/layout-format-help.png` });
    await ws.getByTestId("format-help").click();
    await expect(help).toBeHidden();

    // --- the sidebar close-up at 2x (the open thread) ----------------------------------------
    await settle(page);
    await nav.evaluate((n) => ((n as HTMLElement).style.zoom = "2"));
    await settle(page);
    await nav.screenshot({ path: `${SHOTS}/layout-sidebar-chats-2x.png` });
    // A row with a cut name and its menu dots, close up (the same 2x zoom).
    const longRow = nav.locator(`[data-testid="thread-item"][data-thread-id="${made.thread}"]`).locator("xpath=..");
    await longRow.screenshot({ path: `${SHOTS}/layout-row-menu-dots-2x.png` });
    await nav.evaluate((n) => ((n as HTMLElement).style.zoom = ""));

    // --- focus rings on every kind of sidebar control ----------------------------------------
    await page.locator("body").click({ position: { x: 600, y: 700 } });
    await expectBlueRing(page, nav.getByTestId("sidebar-new-thread"), "New thread");
    await expectBlueRing(page, nav.getByRole("tab", { name: "Chats" }), "Chats tab");
    await expectBlueRing(page, open, "thread row");
    await settle(page);
    await nav.screenshot({ path: `${SHOTS}/layout-sidebar-focused-row.png` });
    await expectBlueRing(page, nav.getByTestId("thread-menu-button").first(), "thread … button");
    await expectBlueRing(page, nav.getByRole("button", { name: "Settings" }), "Settings row");
    // the Settings row's ring is whole: it lies inside the button (the page part's clip-path, which
    // cuts the shadow at its top edge, would cut a ring drawn outside it)
    expect(await style(nav.getByRole("button", { name: "Settings" }), "outline-offset")).toBe("-2px");
    const end = (await nav.getByTestId("sidebar-page-end").boundingBox())!;
    await page.screenshot({
      path: `${SHOTS}/layout-settings-focused.png`,
      clip: { x: end.x - 6, y: end.y - 10, width: end.width + 12, height: end.height + 16 },
      scale: "css",
    });
    await expect(nav.getByRole("button", { name: "Settings" })).toHaveText("Settings");
    await expect(nav.getByTestId("gear-icon")).toBeVisible();
    expect(await nav.textContent()).not.toContain("⚙");

    // --- hovered tab and hovered New thread ---------------------------------------------------
    await nav.getByRole("tab", { name: "Students" }).hover();
    await expect.poll(() => style(nav.getByRole("tab", { name: "Students" }), "background-color")).toBe(TINT);
    await nav.screenshot({ path: `${SHOTS}/layout-sidebar-hover-tab.png` });
    // New thread is the plain row again (v8.23): no fill at rest, the soft --etach-hover grey on hover.
    await page.mouse.move(0, 0);
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
    await expect.poll(() => style(nav.getByTestId("sidebar-new-thread"), "background-color")).toBe("rgba(0, 0, 0, 0)");
    await settle(page);
    await nav.screenshot({ path: `${SHOTS}/layout-sidebar-new-thread-rest.png` });
    await nav.getByTestId("sidebar-new-thread").hover();
    await expect.poll(() => style(nav.getByTestId("sidebar-new-thread"), "background-color")).toBe("rgb(229, 230, 237)");
    await nav.screenshot({ path: `${SHOTS}/layout-sidebar-hover-new-thread.png` });
    await page.mouse.move(0, 0);

    // --- the Tests and Students lists with their headings --------------------------------------
    await nav.getByRole("tab", { name: "Tests" }).click();
    await expect(nav.getByTestId("test-item").first()).toBeVisible();
    // Tests and Students stay ungrouped (the teacher): no group headings there.
    await expect(nav.getByTestId("group-heading")).toHaveCount(0);
    await settle(page);
    await nav.screenshot({ path: `${SHOTS}/layout-sidebar-tests.png` });

    // The sort menu, opened by keyboard: paper corners, the page shadow, Faustina, white like the
    // page, and wholly inside the white page (not clipped by it).
    const sort = nav.getByTestId("tests-sort");
    await tabTo(page, sort);
    await page.keyboard.press("ArrowDown");
    const sortMenu = nav.getByTestId("tests-sort-menu");
    await expect(sortMenu).toBeVisible();
    expect(await style(sortMenu, "border-radius")).toBe("2px");
    expect(await style(sortMenu, "background-color")).toBe("rgb(255, 255, 255)");
    expect(await style(sortMenu, "box-shadow")).toContain("0px 1px 3px");
    expect(await style(sortMenu, "font-family")).toMatch(/^"?Faustina"?/);
    const mb = (await sortMenu.boundingBox())!;
    const pg = (await nav.getByTestId("sidebar-page").boundingBox())!;
    expect(mb.x >= pg.x && mb.x + mb.width <= pg.x + pg.width && mb.y + mb.height <= pg.y + pg.height, "menu inside the page").toBe(true);
    expect(await sortMenu.evaluate((m) => m.scrollHeight <= m.clientHeight + 1)).toBe(true);
    await page.mouse.move(0, 0);
    await settle(page);
    await nav.screenshot({ path: `${SHOTS}/layout-sidebar-tests-sort-open.png` });
    await page.keyboard.press("Escape");
    await expect(sortMenu).toBeHidden();
    await nav.getByRole("tab", { name: "Students" }).click();
    await expect(nav.getByTestId("student-item").first()).toBeVisible();
    await expect(nav.getByTestId("group-heading")).toHaveCount(0);
    await settle(page);
    await nav.screenshot({ path: `${SHOTS}/layout-sidebar-students.png` });
    await expectBlueRing(page, nav.getByTestId("student-item").first(), "student row");

    // Every focusable sidebar control, generically: the Students list, a student's edit row, the
    // Tests list, the Chats list and a thread's rename field.
    await sidebarRings(page, nav, "Students list");
    await nav.getByTestId("student-edit-button").first().click();
    await expect(nav.getByTestId("student-edit-row")).toBeVisible();
    await sidebarRings(page, nav, "student edit row");
    // the blue Save button's ring is outside its fill; a screenshot with Save focused by keyboard
    const save = nav.getByTestId("student-edit-row").getByRole("button", { name: "Save" });
    await tabTo(page, save);
    expect(await style(save, "outline-offset")).toBe("2px");
    await page.mouse.move(0, 0);
    await settle(page);
    await nav.getByTestId("student-edit-row").screenshot({ path: `${SHOTS}/layout-student-save-focused.png` });
    await nav.getByTestId("student-edit-row").getByRole("button", { name: "Cancel" }).click();
    await nav.getByRole("tab", { name: "Tests" }).click();
    await sidebarRings(page, nav, "Tests list");
    await nav.getByRole("tab", { name: "Chats" }).click();
    await sidebarRings(page, nav, "Chats list");
    await nav.getByTestId("thread-menu-button").first().click();
    await nav.getByTestId("thread-rename").click();
    await expect(nav.locator("input").first()).toBeVisible();
    await sidebarRings(page, nav, "rename field");
    await page.keyboard.press("Escape");

    // --- 900 px: the paper keeps its margin, the tabs still stand on it, nothing clipped -------
    await nav.getByRole("tab", { name: "Chats" }).click();
    await open.click();
    await page.setViewportSize({ width: 900, height: 700 });
    await expect(ws.getByTestId("workspace-side-toggle")).toBeVisible();
    const tb9 = (await ws.locator('[role="tab"][aria-selected="true"]').boundingBox())!;
    const pb9 = (await ws.getByTestId("workspace-paper").boundingBox())!;
    expect(Math.abs(tb9.y + tb9.height - pb9.y)).toBeLessThanOrEqual(1);
    expect(pb9.x + pb9.width).toBeLessThanOrEqual(900 - 7);
    await fits(page, '[data-testid="workspace"] button, [data-testid="workspace"] [role="tab"]', "900 workspace");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await settle(page);
    await page.screenshot({ path: `${SHOTS}/layout-workspace-900.png` });
    await page.setViewportSize({ width: 1280, height: 720 });
  } finally {
    for (const id of made.students) await sidecarApi("DELETE", `/students/${id}`);
    if (made.thread) await sidecarApi("DELETE", `/threads/${made.thread}`);
  }
});
