import { fireEvent, render, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useShortcuts, type ShortcutHandlers } from "./useShortcuts";

function setup() {
  const h = {
    onNewThread: vi.fn(),
    onPastePhotos: vi.fn(),
    onRunOrGrade: vi.fn(),
    onSearchTests: vi.fn(),
    onClosePanel: vi.fn(),
  } satisfies Required<ShortcutHandlers>;
  renderHook(() => useShortcuts(h));
  return h;
}

function paste(target: EventTarget, files: File[]) {
  const ev = new Event("paste", { bubbles: true, cancelable: true });
  Object.defineProperty(ev, "clipboardData", {
    value: { files, items: files.map((f) => ({ kind: "file", getAsFile: () => f })) },
  });
  target.dispatchEvent(ev);
  return ev;
}

describe("useShortcuts (R13.2)", () => {
  it("Ctrl+N calls the new-thread handler", () => {
    const h = setup();
    fireEvent.keyDown(window, { key: "n", ctrlKey: true });
    expect(h.onNewThread).toHaveBeenCalledTimes(1);
  });

  it("Ctrl+Enter calls Run / Grade, also from inside an input", () => {
    const h = setup();
    fireEvent.keyDown(window, { key: "Enter", ctrlKey: true });
    const { getByRole } = render(<input aria-label="x" />);
    fireEvent.keyDown(getByRole("textbox"), { key: "Enter", ctrlKey: true });
    expect(h.onRunOrGrade).toHaveBeenCalledTimes(2);
  });

  it("Ctrl+K calls the test search", () => {
    const h = setup();
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(h.onSearchTests).toHaveBeenCalledTimes(1);
  });

  it("Esc closes the panel", () => {
    const h = setup();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(h.onClosePanel).toHaveBeenCalledTimes(1);
  });

  it("Ctrl+V with files calls the paste-photos handler with the files", () => {
    const h = setup();
    const file = new File(["x"], "p1.jpg", { type: "image/jpeg" });
    const ev = paste(document.body, [file]);
    expect(h.onPastePhotos).toHaveBeenCalledWith([file]);
    expect(ev.defaultPrevented).toBe(true);
  });

  it("Ctrl+V outside an editable field calls the handler even without files", () => {
    const h = setup();
    paste(document.body, []);
    expect(h.onPastePhotos).toHaveBeenCalledWith([]);
  });

  it("Ctrl+V with text into an input is left alone", () => {
    const h = setup();
    const { getByRole } = render(<input aria-label="x" />);
    const input = getByRole("textbox");
    input.focus();
    const ev = paste(input, []);
    expect(h.onPastePhotos).not.toHaveBeenCalled();
    expect(ev.defaultPrevented).toBe(false);
  });

  it("Ctrl+V with files into an input still pastes the photos", () => {
    const h = setup();
    const { getByRole } = render(<input aria-label="x" />);
    const input = getByRole("textbox");
    input.focus();
    const file = new File(["x"], "p1.png", { type: "image/png" });
    paste(input, [file]);
    expect(h.onPastePhotos).toHaveBeenCalledWith([file]);
  });

  it("plain N, Ctrl+Shift+N and Ctrl+Alt+K do nothing", () => {
    const h = setup();
    fireEvent.keyDown(window, { key: "n" });
    fireEvent.keyDown(window, { key: "N", ctrlKey: true, shiftKey: true });
    fireEvent.keyDown(window, { key: "k", ctrlKey: true, altKey: true });
    expect(h.onNewThread).not.toHaveBeenCalled();
    expect(h.onSearchTests).not.toHaveBeenCalled();
  });
});
