/**
 * R22.4.5.2 / R22.4.5.3 (step 22.4.5, PRD v8.1): verifying keys starts no run; leaving the Key tab
 * (another tab or another thread) calls `POST /tests/{id}/regrade` exactly once; staying calls
 * nothing; Re-grade calls it; during a run Re-grade is disabled and Stop still stops; on the Key
 * tab the bar is one compact line.
 */
import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { fakeApi } from "@/lib/testApi";
import { useKeyRegrade, type UseKeyRegradeArgs } from "./useKeyRegrade";
import { KEYS_CHANGED_HINT, KeysChangedBar } from "./KeysChangedBar";
import { ThreadRunCard } from "./ThreadRunCard";
import { CompactBarContext } from "./compactBar";
import type { RunEntry } from "./useRunning";

function setup(initial: Partial<UseKeyRegradeArgs> = {}) {
  const fake = fakeApi({ "POST /tests/{id}/regrade": () => ({ run_ids: ["r1", "r2"] }) });
  const onQueued = vi.fn();
  const base: UseKeyRegradeArgs = {
    api: fake.api,
    threadTestId: "T-0001",
    threadPending: false,
    keyTabTestId: "T-0001",
    activeId: "th-1",
    onQueued,
    ...initial,
  };
  const hook = renderHook((props: UseKeyRegradeArgs) => useKeyRegrade(props), { initialProps: base });
  const regrades = () => fake.calls.filter((c) => c.method === "POST" && c.path.endsWith("/regrade"));
  return { ...hook, base, regrades, onQueued };
}

describe("useKeyRegrade", () => {
  it("several key changes call nothing; leaving the Key tab calls the route once", async () => {
    const { result, rerender, base, regrades, onQueued } = setup();
    act(() => result.current.markChanged("T-0001"));
    act(() => result.current.markChanged("T-0001"));
    act(() => result.current.markChanged("T-0001"));
    expect(result.current.pending("T-0001")).toBe(true);
    rerender({ ...base }); // staying on the Key tab
    expect(regrades()).toHaveLength(0);
    rerender({ ...base, keyTabTestId: null }); // to the Report tab
    await waitFor(() => expect(regrades()).toHaveLength(1));
    expect(regrades()[0]!.path).toBe("/tests/T-0001/regrade");
    await waitFor(() => expect(onQueued).toHaveBeenCalledWith(["r1", "r2"]));
    expect(result.current.pending("T-0001")).toBe(false);
    rerender({ ...base }); // back to Key and away again with nothing changed
    rerender({ ...base, keyTabTestId: null });
    expect(regrades()).toHaveLength(1);
  });

  it("switching thread while the Key tab shows a pending test calls it once", async () => {
    const { rerender, base, regrades } = setup({ threadPending: true }); // pending from an earlier session
    rerender({ ...base, threadPending: true });
    rerender({ ...base, activeId: "th-2", threadTestId: null, threadPending: false, keyTabTestId: null });
    await waitFor(() => expect(regrades()).toHaveLength(1));
    expect(regrades()[0]!.path).toBe("/tests/T-0001/regrade");
  });

  it.each(["test", "answers", "report"])(
    "switching thread from the %s tab with keys changed calls it exactly once (R22.4.8.4)",
    async () => {
      // Off the Key tab: keyTabTestId is null all along.
      const { result, rerender, base, regrades } = setup({ keyTabTestId: null });
      act(() => result.current.markChanged("T-0001"));
      rerender({ ...base });
      expect(regrades()).toHaveLength(0); // staying calls nothing
      const away = { ...base, activeId: "th-2", threadTestId: "T-0002", threadPending: false };
      rerender(away);
      rerender(away);
      await waitFor(() => expect(regrades()).toHaveLength(1));
      expect(regrades()[0]!.path).toBe("/tests/T-0001/regrade");
      rerender({ ...away, activeId: "th-3", threadTestId: null });
      expect(regrades()).toHaveLength(1);
    },
  );

  it("switching thread off the Key tab with a pending thread from an earlier session calls it once", async () => {
    const { rerender, base, regrades } = setup({ keyTabTestId: null, threadPending: true });
    rerender({ ...base });
    rerender({ ...base, activeId: "th-2", threadTestId: null, threadPending: false });
    await waitFor(() => expect(regrades()).toHaveLength(1));
    expect(regrades()[0]!.path).toBe("/tests/T-0001/regrade");
  });

  it("leaving with nothing changed calls nothing", () => {
    const { rerender, base, regrades } = setup();
    rerender({ ...base, keyTabTestId: null });
    rerender({ ...base, activeId: "th-2" });
    expect(regrades()).toHaveLength(0);
  });

  it("Re-grade calls the route", async () => {
    const { result, regrades } = setup({ threadPending: true });
    await act(() => result.current.regrade("T-0001"));
    expect(regrades()).toHaveLength(1);
    expect(result.current.pending("T-0001")).toBe(false);
  });
});

const entry = {
  run: { id: "r1", status: "running", thread_id: "th-1" },
  progress: { percent: 40, writingAt: null },
  since: Date.now(),
} as unknown as RunEntry;

describe("KeysChangedBar", () => {
  it("compact: the hint is a tooltip on hover and keyboard focus, and the accessible description (22.4.8)", () => {
    render(<KeysChangedBar running={false} onRegrade={() => {}} compact />);
    const label = screen.getByTestId("keys-changed-label");
    const hint = screen.getByRole("tooltip", { hidden: true });
    expect(hint).toHaveTextContent(KEYS_CHANGED_HINT);
    expect(hint).toHaveAttribute("data-open", "false");
    expect(label).toHaveAccessibleDescription(KEYS_CHANGED_HINT);
    expect(screen.getByRole("button", { name: "Re-grade" })).toHaveAccessibleDescription(KEYS_CHANGED_HINT);
    expect(label).toHaveAttribute("tabindex", "0");
    // Keyboard focus shows it; Esc hides it; blur hides it.
    act(() => label.focus());
    expect(hint).toHaveAttribute("data-open", "true");
    expect(hint).toHaveClass("visible");
    fireEvent.keyDown(label, { key: "Escape" });
    expect(hint).toHaveAttribute("data-open", "false");
    act(() => label.blur());
    // Hover shows it; leaving hides it.
    fireEvent.mouseEnter(screen.getByTestId("keys-changed"));
    expect(hint).toHaveAttribute("data-open", "true");
    fireEvent.mouseLeave(screen.getByTestId("keys-changed"));
    expect(hint).toHaveAttribute("data-open", "false");
    // Focus on Re-grade shows it too.
    act(() => screen.getByRole("button", { name: "Re-grade" }).focus());
    expect(hint).toHaveAttribute("data-open", "true");
    // The hint is not in the polite status (no repeat announcement).
    expect(screen.getByRole("status")).not.toHaveTextContent(KEYS_CHANGED_HINT);
  });

  it("reads Keys changed with Re-grade in a polite status; Re-grade calls back", () => {
    const onRegrade = vi.fn();
    render(<KeysChangedBar running={false} onRegrade={onRegrade} />);
    expect(screen.getByRole("status")).toHaveTextContent("Keys changed");
    fireEvent.click(screen.getByRole("button", { name: "Re-grade" }));
    expect(onRegrade).toHaveBeenCalledTimes(1);
  });

  it("during a run Re-grade is disabled and Stop still stops", () => {
    const onRegrade = vi.fn();
    const onStop = vi.fn();
    render(
      <>
        <KeysChangedBar running onRegrade={onRegrade} compact />
        <CompactBarContext.Provider value>
          <ThreadRunCard entry={entry} onStop={onStop} />
        </CompactBarContext.Provider>
      </>,
    );
    expect(screen.getByRole("button", { name: "Re-grade" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    expect(onStop).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("thread-run")).toHaveAttribute("data-compact", "true");
    expect(screen.getByRole("progressbar", { name: "Run progress" })).toHaveAttribute("aria-valuenow", "40");
  });

  it("outside the workspace (no compact context) the run card is the full card", () => {
    render(<ThreadRunCard entry={entry} onStop={() => {}} />);
    expect(screen.getByTestId("thread-run")).not.toHaveAttribute("data-compact");
    expect(screen.getByTestId("run-elapsed")).toBeInTheDocument();
  });
});
