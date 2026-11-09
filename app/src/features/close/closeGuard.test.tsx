// R22.2.2.2: a close request shows "Close ETACH?"; Cancel keeps the app open, Close
// closes it; with unsaved text the dialog says so (the page side; the shell side is the capability
// test in scripts/tauri-config.test.ts).
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/AppShell";
import { fakeApi } from "@/lib/testApi";
import { makeTauriCloseListener, type CloseHandler, type CloseListener } from "./closeGuard";

function fakeWindow() {
  let handler: CloseHandler | null = null;
  const listen: CloseListener = (h) => {
    handler = h;
    return () => {
      handler = null;
    };
  };
  return { listen, request: () => handler!() };
}

const TEXT = "— Page 1 —\n\n1. One.\n";
const test_ = {
  id: "T-0001",
  meta: {},
  content: { sections: [] },
  content_schema_version: 1,
  fingerprint: "",
  points_possible: 0,
  source_run_id: null,
  merged_into: null,
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
  picture_paths: {},
  pages: [],
  key_pages: [],
  content_text: TEXT,
  review: [],
};

describe("window-close guard (R22.2.2.2)", () => {
  it("asks first; Cancel keeps the app open, Close closes it", async () => {
    const win = fakeWindow();
    render(<AppShell connection="open" closeListener={win.listen} />);
    let answer!: Promise<boolean>;
    act(() => {
      answer = win.request();
    });
    const dialog = await screen.findByTestId("confirm-dialog");
    expect(dialog).toHaveTextContent("Close ETACH?");
    expect(dialog).not.toHaveTextContent("not saved");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await expect(answer).resolves.toBe(false);
    act(() => {
      answer = win.request();
    });
    fireEvent.click(within(await screen.findByTestId("confirm-dialog")).getByRole("button", { name: "Close" }));
    await expect(answer).resolves.toBe(true);
  });

  it("names unsaved test text", async () => {
    const win = fakeWindow();
    const { api } = fakeApi({ "GET /tests/{id}": test_, "GET /threads": [] });
    render(
      <AppShell connection="open" api={api} threads={[]} initialPanel={{ kind: "test", testId: "T-0001" }} closeListener={win.listen} />,
    );
    fireEvent.change(await screen.findByTestId("test-text"), { target: { value: TEXT + "more" } });
    act(() => void win.request());
    expect(await screen.findByTestId("confirm-dialog")).toHaveTextContent("not saved yet");
  });
});

describe("Tauri close listener registration (F1)", () => {
  it("a registration that throws is caught, not left unhandled", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const unhandled = vi.fn();
    process.on("unhandledRejection", unhandled);
    try {
      const listen = makeTauriCloseListener(
        async () => ({
          getCurrentWindow: () => {
            throw new TypeError("Cannot read properties of undefined (reading 'metadata')");
          },
        }),
        () => true,
      );
      const off = listen(async () => true);
      await vi.waitFor(() => expect(warn).toHaveBeenCalledTimes(1));
      await new Promise((r) => setTimeout(r, 0));
      expect(unhandled).not.toHaveBeenCalled();
      expect(() => off()).not.toThrow();
    } finally {
      process.off("unhandledRejection", unhandled);
      warn.mockRestore();
    }
  });

  it("a rejected onCloseRequested is caught too", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      const win = { onCloseRequested: () => Promise.reject(new Error("denied")), destroy: async () => {} };
      const listen = makeTauriCloseListener(
        async () => ({ getCurrentWindow: () => win as never }),
        () => true,
      );
      listen(async () => true);
      await vi.waitFor(() => expect(warn).toHaveBeenCalledWith("Close guard not registered:", expect.any(Error)));
    } finally {
      warn.mockRestore();
    }
  });

  it("registers, and unregisters on cleanup", async () => {
    const unlisten = vi.fn();
    const onCloseRequested = vi.fn(async () => unlisten);
    const listen = makeTauriCloseListener(
      async () => ({ getCurrentWindow: () => ({ onCloseRequested, destroy: async () => {} }) as never }),
      () => true,
    );
    const off = listen(async () => true);
    await vi.waitFor(() => expect(onCloseRequested).toHaveBeenCalledTimes(1));
    await Promise.resolve();
    off();
    expect(unlisten).toHaveBeenCalledTimes(1);
  });

  it("outside Tauri there is no listener", () => {
    const load = vi.fn();
    makeTauriCloseListener(load, () => false)(async () => true)();
    expect(load).not.toHaveBeenCalled();
  });
});
