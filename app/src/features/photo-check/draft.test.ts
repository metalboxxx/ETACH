import { afterEach, describe, expect, it, vi } from "vitest";
import { clearDraft, loadDraft, movePage, resetDraftMemory, rotateClockwise, saveDraft, toExtractInput } from "./draft";
import { todayIso } from "@/lib/skills";

const page = (id: string) => ({ file_id: id, rotation: 0 as const, is_key: false, text_file_id: null });

afterEach(() => {
  resetDraftMemory();
  window.sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("photo check draft", () => {
  it("survives a reload through sessionStorage", () => {
    saveDraft("th1", { pages: [page("a")], existingTest: { id: "T-0001", display_name: "Test 1" } });
    resetDraftMemory();
    expect(loadDraft("th1")).toEqual({ pages: [page("a")], existingTest: { id: "T-0001", display_name: "Test 1" } });
    clearDraft("th1");
    expect(loadDraft("th1")).toBeNull();
  });

  it("works in memory when storage throws", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    saveDraft("th2", { pages: [page("b")], existingTest: null });
    expect(loadDraft("th2")?.pages).toEqual([page("b")]);
  });

  it("rotates clockwise 0→90→180→270→0, moves pages, maps to ExtractInput", () => {
    expect([0, 90, 180, 270].map((r) => rotateClockwise(r as 0))).toEqual([90, 180, 270, 0]);
    expect(movePage(["a", "b", "c"], 2, 0)).toEqual(["c", "a", "b"]);
    expect(toExtractInput({ pages: [page("a")], existingTest: null })).toEqual({
      pages: [page("a")],
      existing_test_id: null,
      supersedes_attempt_id: null,
      taken_on: todayIso(),
    });
  });
});
