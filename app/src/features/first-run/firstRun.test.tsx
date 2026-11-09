// R21.3 (APP_TEST): the first-run screen shows the correct message for each of 3 mocked
// `/system/status` states: Ollama missing → install link; too old → update; models missing →
// Download models. Also: `ok` and replay show the app; "Continue anyway" hides the screen;
// Download models posts the pull and shows per-model progress.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EtachEvent, EventListenerFn, EventStream } from "@/api/sse";
import { EventsProvider } from "@/api/sse";
import { Connected } from "@/App";
import { fakeApi } from "@/lib/testApi";
import { OLLAMA_DOWNLOAD, SETUP_SKIPPED_KEY, setupNeed } from "./FirstRunScreen";

vi.mock("@tauri-apps/plugin-notification", () => ({
  isPermissionGranted: vi.fn(async () => true),
  requestPermission: vi.fn(async () => "granted"),
  sendNotification: vi.fn(),
}));
const invoke = vi.fn(async () => undefined);
vi.mock("@tauri-apps/api/core", () => ({ isTauri: vi.fn(() => true), invoke: (...a: unknown[]) => invoke(...(a as [])) }));

type Status = Record<string, unknown>;

const BASE: Status = {
  sidecar_version: "0.6.1",
  replay: false,
  other_ollama_loaded: false,
  power_source: "ac",
  keep_awake: false,
};
const UNREACHABLE: Status = { ...BASE, ollama_status: "unreachable", ollama_version: null, models_present: null, missing_models: null };
const TOO_OLD: Status = { ...BASE, ollama_status: "too_old", ollama_version: "0.11.4", models_present: null, missing_models: null };
const MISSING: Status = {
  ...BASE,
  ollama_status: "missing_model",
  ollama_version: "0.13.1",
  models_present: ["qwen3.5:4b"],
  missing_models: ["numind/nuextract3:Q6_K"],
};
const OK: Status = {
  ...BASE,
  ollama_status: "ok",
  ollama_version: "0.13.1",
  models_present: ["numind/nuextract3:Q6_K", "qwen3.5:4b"],
  missing_models: [],
};

function fakeStream() {
  const listeners = new Set<EventListenerFn>();
  let id = 0;
  const stream: EventStream = {
    start() {},
    close() {},
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    onStatus: () => () => {},
    get status() {
      return "open" as const;
    },
    get lastEventId() {
      return id;
    },
  };
  const emit = (type: EtachEvent["type"], data: Record<string, unknown> = {}) =>
    act(() => {
      id += 1;
      const e = { id, type, data: { type, ...data } } as EtachEvent;
      listeners.forEach((fn) => fn(e));
    });
  return { stream, emit };
}

function setup(initial: Status) {
  const state = { status: initial };
  const fake = fakeApi({
    "GET /threads": [],
    "GET /review/count": { open: 0 },
    "GET /runs/active": [],
    "GET /system/status": () => state.status,
    "POST /settings/models/pull": { models: ["numind/nuextract3:Q6_K"] },
  });
  const { stream, emit } = fakeStream();
  render(
    <EventsProvider stream={stream}>
      <Connected api={fake.api} />
    </EventsProvider>,
  );
  return { ...fake, emit, state };
}

beforeEach(() => {
  window.sessionStorage.clear();
  invoke.mockClear();
});

describe("first-run screen (R21.3)", () => {
  it("Ollama missing or not running → install message and a link to the download page", async () => {
    setup(UNREACHABLE);
    const screenEl = await screen.findByTestId("first-run");
    expect(screenEl).toHaveAttribute("data-need", "install");
    expect(screen.getByTestId("first-run-message")).toHaveTextContent(/Ollama is not installed or not running/);
    expect(screen.getByTestId("ollama-download-address")).toHaveTextContent(OLLAMA_DOWNLOAD);
    fireEvent.click(screen.getByTestId("ollama-download-link"));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("open_ollama_download"));
    expect(screen.queryByTestId("app-shell")).toBeNull();
    expect(screen.queryByTestId("first-run-pull")).toBeNull();
  });

  it("Ollama older than 0.12.11 → update message", async () => {
    setup(TOO_OLD);
    expect(await screen.findByTestId("first-run")).toHaveAttribute("data-need", "update");
    const message = screen.getByTestId("first-run-message");
    expect(message).toHaveTextContent(/Ollama 0\.11\.4 is too old/);
    expect(message).toHaveTextContent(/update Ollama to 0\.12\.11 or newer/);
    expect(screen.getByTestId("ollama-download-link")).toHaveTextContent("Update Ollama");
    expect(screen.queryByTestId("first-run-pull")).toBeNull();
  });

  it("models missing → Download models, with per-model progress; the app opens once ready", async () => {
    const { calls, emit, state } = setup(MISSING);
    expect(await screen.findByTestId("first-run")).toHaveAttribute("data-need", "models");
    expect(screen.getByTestId("first-run-missing")).toHaveTextContent("numind/nuextract3:Q6_K");
    expect(screen.queryByTestId("ollama-download-link")).toBeNull();
    fireEvent.click(screen.getByTestId("first-run-pull"));
    const row = await screen.findByTestId("first-run-pull-row");
    expect(calls.some((c) => c.method === "POST" && c.path === "/settings/models/pull")).toBe(true);
    expect(row).toHaveTextContent("waiting");
    emit("models.pull_progress", { model: "numind/nuextract3:Q6_K", status: "downloading", completed: 25, total: 100 });
    expect(screen.getByTestId("first-run-pull-row")).toHaveTextContent("downloading 25%");
    expect(screen.getByTestId("first-run-pull")).toBeDisabled();
    state.status = OK;
    emit("models.pull_progress", { model: "numind/nuextract3:Q6_K", status: "success", completed: null, total: null });
    expect(await screen.findByTestId("app-shell")).toBeInTheDocument();
    expect(screen.queryByTestId("first-run")).toBeNull();
  });
});

describe("first-run screen: when it stays hidden", () => {
  it("is not shown when the status is ok", async () => {
    const { calls } = setup(OK);
    await waitFor(() => expect(calls.some((c) => c.path === "/system/status")).toBe(true));
    expect(await screen.findByTestId("app-shell")).toBeInTheDocument();
    expect(screen.queryByTestId("first-run")).toBeNull();
  });

  it("is not shown in replay mode (no Ollama by design)", async () => {
    const { calls } = setup({ ...UNREACHABLE, replay: true });
    await waitFor(() => expect(calls.some((c) => c.path === "/system/status")).toBe(true));
    expect(screen.getByTestId("app-shell")).toBeInTheDocument();
    expect(screen.queryByTestId("first-run")).toBeNull();
  });

  it("Continue anyway shows the app and is remembered for the session", async () => {
    setup(UNREACHABLE);
    fireEvent.click(await screen.findByTestId("first-run-continue"));
    expect(await screen.findByTestId("app-shell")).toBeInTheDocument();
    expect(window.sessionStorage.getItem(SETUP_SKIPPED_KEY)).toBe("true");
  });

  it("setupNeed maps the status", () => {
    expect(setupNeed(null)).toBeNull();
    expect(setupNeed(UNREACHABLE as never)).toBe("install");
    expect(setupNeed(TOO_OLD as never)).toBe("update");
    expect(setupNeed(MISSING as never)).toBe("models");
    expect(setupNeed(OK as never)).toBeNull();
    expect(setupNeed({ ...MISSING, replay: true } as never)).toBeNull();
  });
});
