import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApi } from "@/lib/testApi";
import { TestsTab } from "./TestsTab";

const row = (id: string, name: string, count: number, school: string | null = null) => ({
  id,
  display_name: name,
  meta: { occasion: "FinalTerm", grade: 8, term: 1, school, edited_fields: [] },
  points_possible: 10,
  attempt_count: count,
  updated_at: "2026-10-04T00:00:00Z",
});

describe("TestsTab", () => {
  it("lists tests with their attempt counts and opens one on click", async () => {
    const { api } = fakeApi({ "GET /tests": [row("T-0001", "FinalTerm 8.1", 2), row("T-0003", "MidTerm 7.2", 0)] });
    const onOpen = vi.fn();
    render(<TestsTab api={api} onOpen={onOpen} />);
    const items = await screen.findAllByTestId("test-item");
    expect(items.map((i) => i.getAttribute("data-test-id"))).toEqual(["T-0001", "T-0003"]);
    expect(screen.getAllByTestId("test-attempt-count").map((c) => c.textContent)).toEqual(["2", "0"]);
    fireEvent.click(items[0]!);
    expect(onOpen).toHaveBeenCalledWith("T-0001");
  });

  it("searches with ?q= and shows an empty state", async () => {
    const { api, calls } = fakeApi({
      "GET /tests": (c: { query: URLSearchParams }) =>
        c.query.get("q") === "lomo" ? [row("T-0001", "FinalTerm 8.1", 1, "Lomonosov")] : [],
    });
    render(<TestsTab api={api} onOpen={() => {}} debounceMs={0} />);
    expect(await screen.findByTestId("tests-empty")).toHaveTextContent("No tests yet.");
    fireEvent.change(screen.getByTestId("tests-search"), { target: { value: " lomo " } });
    await waitFor(() => expect(screen.getAllByTestId("test-item")).toHaveLength(1));
    expect(calls.some((c) => c.path === "/tests" && c.query.get("q") === "lomo")).toBe(true);
    fireEvent.change(screen.getByTestId("tests-search"), { target: { value: "zzz" } });
    expect(await screen.findByTestId("tests-empty")).toHaveTextContent("No tests match.");
  });
});
