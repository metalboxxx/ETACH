// R22.5.8.9 (PRD §10.1 v8.21, v8.23): the sidebar's layout. New thread a plain row with a soft hover;
// Chats | Tests | Students with white lines between them, the selected one white, a hovered
// one tinted; Settings a labelled row; every control with the blue focus outline; group headings
// as centred small capitals with a short rule.
import { render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { GroupHeading } from "@/components/GroupHeading";
import { RunningIndicator } from "@/features/running/RunningIndicator";
import type { RunEntry } from "@/features/running/useRunning";
import { Sidebar } from "./Sidebar";

const FOCUS = /\bfocus-visible:outline-2\b.*\bfocus-visible:outline-focus\b/;

function renderSidebar() {
  render(<Sidebar tab="tests" onTabChange={() => {}} onNewThread={() => {}} onOpenSettings={() => {}} />);
  return screen.getByRole("navigation", { name: "Sidebar" });
}

describe("sidebar layout (R22.5.8.9)", () => {
  it("New thread is the plain row again: no fill at rest, a soft hover, 6 px corners, the blue focus outline", () => {
    const nav = renderSidebar();
    const button = within(nav).getByRole("button", { name: /New thread/ });
    expect(button.className).not.toMatch(/(^|\s)bg-tint(-strong)?(\s|$)|hover:bg-tint/);
    expect(button.className).toMatch(/\bhover:bg-hover\b/);
    expect(button.className).toMatch(/\brounded-button\b/);
    expect(button.className).toMatch(FOCUS);
  });

  it("the three tabs: white lines between them, the selected one white, a hovered one tinted, each focusable in blue", () => {
    const nav = renderSidebar();
    const list = within(nav).getByRole("tablist");
    expect(list.className).toMatch(/\bdivide-x-2\b/);
    expect(list.className).toMatch(/\bdivide-surface\b/);
    for (const tab of within(list).getAllByRole("tab")) {
      expect(tab.className).toMatch(FOCUS);
      if (tab.getAttribute("aria-selected") === "true") {
        // the selected tab opens into the white page: the page's white, overlapping its top edge
        expect(tab.textContent).toBe("Tests");
        expect(tab.className).toMatch(/\bbg-surface\b/);
        expect(tab.className).toMatch(/(^|\s)-mb-1(\s|$)/);
        expect(tab.className).toMatch(/\bshadow-tab\b/);
      } else {
        expect(tab.className).toMatch(/\bhover:bg-tint\b/);
        expect(tab.className).not.toMatch(/(^|\s)bg-surface(\s|$)/);
      }
    }
  });

  it("one white page under the tabs, down through Settings, with paper corners and the page shadow", () => {
    const nav = renderSidebar();
    const page = within(nav).getByTestId("sidebar-page");
    const end = within(nav).getByTestId("sidebar-page-end");
    for (const el of [page, end]) {
      expect(el.className).toMatch(/\bbg-surface\b/);
      expect(el.className).toMatch(/\bshadow-page\b/);
    }
    expect(page.className).toMatch(/\brounded-t-paper\b/);
    expect(end.className).toMatch(/\brounded-b-paper\b/);
    expect(within(end).getByRole("button", { name: "Settings" })).toBeInTheDocument();
  });

  it("Settings is a labelled row with the gear", () => {
    const nav = renderSidebar();
    const row = within(nav).getByRole("button", { name: "Settings" });
    // the gear is an outline SVG in the text colour, hidden from screen readers (the teacher)
    expect(row).toHaveTextContent(/^Settings$/);
    const gear = row.querySelector("svg")!;
    expect(gear.getAttribute("aria-hidden")).toBe("true");
    expect(gear.getAttribute("stroke")).toBe("currentColor");
    expect(gear.getAttribute("fill")).toBe("none");
    // no ⚙ character is left in the sidebar
    expect(nav.textContent).not.toContain("⚙");
    expect(row.className).toMatch(FOCUS);
    // the ring lies inside the row, so the page part's clip-path cannot cut its top edge
    expect(row.className).toMatch(/(^|\s)focus-visible:-outline-offset-2(\s|$)/);
  });

  it("every control in the sidebar's own parts has the blue focus outline (the running slot included)", () => {
    const nav = renderSidebar();
    for (const el of nav.querySelectorAll("button, input, select, textarea, [tabindex='0']")) {
      expect(el.className, el.textContent ?? el.outerHTML).toMatch(FOCUS);
    }
    const run = (id: string, status: string) =>
      ({ run: { id, thread_id: "th1", status, kind: "extract" }, progress: { done: 0, total: 0 }, since: 0 }) as unknown as RunEntry;
    const { container } = render(
      <RunningIndicator
        runs={[run("r1", "running"), run("r2", "stopped")]}
        power={null}
        threadName={() => "Thread"}
        onStop={() => {}}
        onResume={() => {}}
        onDiscard={() => {}}
      />,
    );
    const buttons = [...container.querySelectorAll("button")];
    expect(buttons.map((b) => b.textContent)).toEqual(expect.arrayContaining(["Stop", "Resume", "Discard"]));
    for (const b of buttons) expect(b.className, b.textContent ?? "").toMatch(FOCUS);
  });

  it("a blue-filled control in the sidebar draws its ring outside (a ring inside its own blue fill would be invisible)", () => {
    const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
    const files = [
      "features/sidebar/Sidebar.tsx",
      "features/threads/ThreadList.tsx",
      "features/tests-tab/TestsTab.tsx",
      "features/students-tab/StudentsTab.tsx",
      "features/running/RunningIndicator.tsx",
      "components/SchoolCombobox.tsx",
    ];
    const bad: string[] = [];
    let filled = 0;
    for (const f of files) {
      readFileSync(path.join(src, f), "utf8")
        .split("\n")
        .forEach((line, i) => {
          if (!/(?<![\w:-])bg-accent(?![\w/-])/.test(line)) return;
          filled++;
          if (/-outline-offset-/.test(line)) bad.push(`${f}:${i + 1}`);
          if (!/(?<![\w-])focus-visible:outline-offset-2\b/.test(line)) bad.push(`${f}:${i + 1} (no outer offset)`);
        });
    }
    expect(filled).toBeGreaterThan(0);
    expect(bad).toEqual([]);
  });

  it("a group heading is centred bold small capitals in the text colour, with a short rule", () => {
    render(<GroupHeading>Phạm Thu Hằng</GroupHeading>);
    const h = screen.getByRole("heading", { name: "Phạm Thu Hằng" });
    expect(h.className).toMatch(/\btext-center\b/);
    expect(h.className).toMatch(/\bfont-semibold\b/);
    expect(h.className).toMatch(/\btext-text\b/);
    expect(h.className).toContain("[font-variant-caps:small-caps]");
    expect(h.className).not.toMatch(/\buppercase\b|\btext-muted\b/);
    expect(screen.getByTestId("group-rule").className).toMatch(/\bh-px\b.*\bbg-text\b/);
  });

});
