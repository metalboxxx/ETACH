// Step 22.4.1: screen fixes from the teacher's fourth review (comments 4, 6, 9). Synthetic data only.
// R22.4.1.1: opening Format help scrolls it into view (smooth, or `auto` under reduced motion);
//   focus stays on the button; closing does not scroll.
// R22.4.1.2: the workspace tabs look like buttons (border, background, the selected one filled in
//   the theme green), with WCAG AA contrast computed from the tokens.
// R22.4.1.3: "Grade again" is gone from app/src (the graded case is in step22_3_2.test.tsx).
import { act, fireEvent, render, screen } from "@testing-library/react";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Workspace } from "@/features/panel/Workspace";
import { FORMAT_HELP_MS, FormatHelp } from "@/features/panels/TestPanel";
import type { WorkspaceTab } from "@/features/panels/panelView";
import { fakeApi } from "@/lib/testApi";

const srcDir = path.resolve(__dirname, "..");

describe("Format help scrolls into view when it opens (R22.4.1.1)", () => {
  let scroll: ReturnType<typeof vi.fn>;
  const original = Element.prototype.scrollIntoView;
  const originalMatch = window.matchMedia;

  beforeEach(() => {
    vi.useFakeTimers();
    scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll as unknown as typeof Element.prototype.scrollIntoView;
  });
  afterEach(() => {
    vi.useRealTimers();
    Element.prototype.scrollIntoView = original;
    window.matchMedia = originalMatch;
  });

  const reducedMotion = (on: boolean) => {
    window.matchMedia = ((q: string) => ({
      matches: on && q.includes("prefers-reduced-motion: reduce"),
      media: q,
      addEventListener() {},
      removeEventListener() {},
    })) as unknown as typeof window.matchMedia;
  };

  it("opening scrolls the button to the top smoothly after the slide (R22.4.8.1); focus stays on the button", () => {
    reducedMotion(false);
    render(<FormatHelp />);
    const button = screen.getByTestId("format-help");
    button.focus();
    fireEvent.click(button);
    expect(scroll).not.toHaveBeenCalled(); // not before the panel has its height
    act(() => vi.advanceTimersByTime(FORMAT_HELP_MS));
    expect(scroll).toHaveBeenCalledTimes(1);
    // Step 22.4.8 (answer 1): the button itself goes to the top, so it stays in view.
    expect(scroll.mock.contexts[0]).toBe(button);
    expect(scroll).toHaveBeenCalledWith({ block: "start", behavior: "smooth" });
    expect(document.activeElement).toBe(button);
  });

  it("under reduced motion the scroll is instant", () => {
    reducedMotion(true);
    render(<FormatHelp />);
    fireEvent.click(screen.getByTestId("format-help"));
    act(() => vi.advanceTimersByTime(0));
    expect(scroll).toHaveBeenCalledWith({ block: "start", behavior: "auto" });
  });

  it("closing does not scroll", () => {
    reducedMotion(false);
    render(<FormatHelp />);
    const button = screen.getByTestId("format-help");
    fireEvent.click(button);
    act(() => vi.advanceTimersByTime(FORMAT_HELP_MS));
    scroll.mockClear();
    fireEvent.click(button);
    act(() => vi.advanceTimersByTime(FORMAT_HELP_MS * 3));
    expect(scroll).not.toHaveBeenCalled();
  });

  it("closing before the slide ends cancels the scroll", () => {
    reducedMotion(false);
    render(<FormatHelp />);
    const button = screen.getByTestId("format-help");
    fireEvent.click(button);
    fireEvent.click(button);
    act(() => vi.advanceTimersByTime(FORMAT_HELP_MS * 3));
    expect(scroll).not.toHaveBeenCalled();
  });
});

// --- WCAG contrast from the tokens --------------------------------------------------------------

type Rgb = [number, number, number];
const rgb = (hex: string): Rgb => {
  const n = parseInt(/^#([0-9a-f]{6})$/i.exec(hex)![1]!, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
const lum = ([r, g, b]: Rgb) => {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
};
const contrast = (a: string, b: string) => {
  const [hi, lo] = [lum(rgb(a)), lum(rgb(b))].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
};

function modes(): [string, Record<string, string>][] {
  const text = readFileSync(path.join(srcDir, "styles", "tokens.css"), "utf8");
  const vars = (re: RegExp) =>
    Object.fromEntries([...text.match(re)![1]!.matchAll(/(--etach-[\w-]+)\s*:\s*([^;]+);/g)].map((v) => [v[1]!, v[2]!.trim()]));
  // Light only (PRD §10.1 v8.12).
  return [["light", vars(/^:root\s*{([^}]*)}/m)]];
}

describe("workspace tabs look like buttons (R22.4.1.2)", () => {
  const tabs: WorkspaceTab[] = [
    { label: "Test", view: { kind: "test", testId: "T-0001" } },
    { label: "Key", view: { kind: "keys", testId: "T-0001" } },
    { label: "Student answers", view: { kind: "answers", attemptId: "A-0001", testId: "T-0001" } },
    { label: "Report", view: { kind: "report", attemptId: "A-0001", testId: "T-0001" } },
  ] as WorkspaceTab[];

  it("every tab has a border and a background; the selected one is filled blue (white text); roles and arrows stay", () => {
    const { api } = fakeApi({});
    const onTab = vi.fn();
    render(
      <Workspace
        api={api}
        view={{ kind: "keys", testId: "T-0001" }}
        title="Key"
        tabs={tabs}
        onTab={onTab}
      />,
    );
    const list = screen.getByRole("tablist", { name: "Workspace" });
    const all = screen.getAllByRole("tab");
    expect(all.map((t) => t.textContent)).toEqual(["Test", "Key", "Student answers", "Report"]);
    for (const tab of all) {
      expect(tab.className).toMatch(/(^|\s)border(\s|$)/);
      expect(tab.className).toMatch(/\bfocus-visible:outline-focus\b/);
      if (tab.getAttribute("aria-selected") === "true") {
        expect(tab.className).toMatch(/\bbg-accent\b/);
        expect(tab.className).toMatch(/\btext-accent-text\b/);
        expect(tab.className).toMatch(/\bborder-accent-strong\b/);
      } else {
        expect(tab.className).toMatch(/\bbg-surface\b/);
        expect(tab.className).toMatch(/\bborder-input\b/);
        expect(tab.className).toMatch(/\bhover:bg-hover\b/);
        expect(tab.className).toMatch(/\btext-text\b/);
      }
    }
    const selected = all.filter((t) => t.getAttribute("aria-selected") === "true");
    expect(selected.map((t) => t.textContent)).toEqual(["Key"]);
    // Arrow keys still move between the tabs.
    all[1]!.focus();
    fireEvent.keyDown(list, { key: "ArrowRight" });
    expect(document.activeElement).toBe(all[2]);
  });

  it("text ≥ 4.5:1 and borders ≥ 3:1 (light only)", () => {
    for (const [mode, t] of modes()) {
      const page = t["--etach-panel"]!; // the workspace bar is bg-panel
      const checks: [string, string, string, number][] = [
        ["tab text on surface", t["--etach-text"]!, t["--etach-surface"]!, 4.5],
        ["tab text on hover", t["--etach-text"]!, t["--etach-hover"]!, 4.5],
        ["selected text on accent", t["--etach-accent-text"]!, t["--etach-accent"]!, 4.5],
        ["tab border on the bar", t["--etach-input-border"]!, page, 3],
        ["selected border on the bar", t["--etach-accent-strong"]!, page, 3],
        ["focus ring on the bar", t["--etach-focus"]!, page, 3],
      ];
      for (const [label, fg, bg, min] of checks) {
        expect(contrast(fg, bg), `${mode}: ${label}`).toBeGreaterThanOrEqual(min);
      }
    }
  });
});

describe('"Grade again" is gone (R22.4.1.3)', () => {
  const files = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
      const p = path.join(dir, e.name);
      return e.isDirectory() ? files(p) : /\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name) ? [p] : [];
    });

  it("appears in no source file under app/src", () => {
    const hits = files(srcDir).filter((f) => readFileSync(f, "utf8").includes("Grade again"));
    expect(hits).toEqual([]);
  });
});
