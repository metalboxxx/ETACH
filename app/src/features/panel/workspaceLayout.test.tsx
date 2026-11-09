// R22.5.8.9 (PRD §10.1 v8.21): the workspace. Arch-topped tabs (rounded at the top only, no bottom
// edge) stand on the panel, which is a sheet of paper (white, 2 px corners, the page shadow, a
// margin on the page background) that starts with the thread or test line over a double rule.
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Workspace } from "@/features/panel/Workspace";
import type { WorkspaceTab } from "@/features/panels/panelView";
import { fakeApi } from "@/lib/testApi";

const tabs: WorkspaceTab[] = [
  { label: "Test", view: { kind: "test", testId: "T-0001" } },
  { label: "Key", view: { kind: "keys", testId: "T-0001" } },
] as WorkspaceTab[];

function renderWorkspace() {
  const { api } = fakeApi({});
  render(
    <Workspace
      api={api}
      view={{ kind: "keys", testId: "T-0001" }}
      title="Key"
      tabs={tabs}
      onTab={() => {}}
      banner={<div data-testid="thread-banner">Hằng – giữa kỳ 1</div>}
    />,
  );
  return screen.getByTestId("workspace");
}

describe("workspace layout (R22.5.8.9)", () => {
  it("the tabs are arch-topped and have no bottom edge", () => {
    const ws = renderWorkspace();
    for (const tab of within(ws).getAllByRole("tab")) {
      expect(tab.className).toMatch(/\brounded-t-button\b/);
      expect(tab.className).toMatch(/\bborder-b-0\b/);
    }
  });

  it("the panel is a sheet of paper that starts with the banner over a double rule, after the tabs", () => {
    const ws = renderWorkspace();
    const paper = within(ws).getByTestId("workspace-paper");
    for (const c of ["rounded-paper", "bg-surface", "shadow-page", "mx-2", "mb-2"]) expect(paper.className.split(/\s+/)).toContain(c);
    const header = within(paper).getByTestId("workspace-header");
    expect(header.className).toMatch(/\bdouble-rule\b/);
    expect(within(header).getByTestId("thread-banner")).toBeInTheDocument();
    expect(within(paper).getByTestId("artifact-panel")).toBeInTheDocument();
    // the tab row comes first and the paper right after it (the selected tab joins the paper)
    const bar = within(ws).getByTestId("workspace-bar");
    expect(bar.nextElementSibling).toBe(paper);
    expect(bar.className).not.toMatch(/\bborder-b\b/);
  });
});
