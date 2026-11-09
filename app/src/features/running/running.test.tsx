// R15.5: "keep the lid open" while running; "on battery" only when power_source = battery.
// R15.7: run.done → the notification plugin mock is called once, with the thread name.
// Also: Resume/Discard for stopped runs, the queued count, the empty slot, and the D18 gap
// (a thread with a run in /runs/active blocks a drop at once).
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EventStream, EtachEvent, EventListenerFn } from "@/api/sse";
import { EventsProvider } from "@/api/sse";
import { Connected } from "@/App";
import { fakeApi, type FakeCall } from "@/lib/testApi";
import { resetDraftMemory } from "@/features/photo-check/draft";
import { ThreadView } from "@/features/threads/ThreadView";

const notification = vi.hoisted(() => ({
  isPermissionGranted: vi.fn(async () => true),
  requestPermission: vi.fn(async () => "granted"),
  sendNotification: vi.fn(),
}));
vi.mock("@tauri-apps/plugin-notification", () => notification);
const core = vi.hoisted(() => ({ isTauri: vi.fn(() => true) }));
vi.mock("@tauri-apps/api/core", () => core);

/** A stream the test drives: `emit` delivers an event with the next id. */
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

const run = (id: string, status: string, thread_id = "th1") => ({
  id,
  thread_id,
  kind: "extract",
  status,
  input: {},
  error: null,
  started_at: null,
  finished_at: null,
});
const summary = (id: string, title: string) => ({
  group: "Blank tests",
  kind: "pending",
  last_activity: "2026-10-03T00:00:00Z",
  student_id: null,
  thread: { id, title, kind: "pending", test_id: null, created_at: "2026-10-03T00:00:00Z" },
});
const step = { id: "s1", run_id: "R1", node: "transcribe_page", item: "page 1", status: "running", try_no: 1, started_at: "", finished_at: null };

function setup(active: unknown[], power: "ac" | "battery" | "unknown" = "ac") {
  const state = { active, power };
  const fake = fakeApi({
    "GET /threads": [summary("th1", "Lớp 8 HK1"), summary("th2", "Đề 2")],
    "GET /threads/{id}": (c: FakeCall) => ({
      thread: { ...summary(c.path.split("/")[2] ?? "", "Lớp 8 HK1").thread },
      attempt: null,
      test: null,
    }),
    "GET /threads/{id}/messages": [],
    "GET /review/count": { count: 0 },
    "GET /runs/active": () => state.active,
    "GET /system/status": () => ({
      power_source: state.power,
      keep_awake: true,
      missing_models: [],
      models_present: [],
      ollama_status: "ok",
      ollama_version: "0.12",
      other_ollama_loaded: false,
    }),
    "POST /runs/{id}/stop": run("R1", "stopping"),
    "POST /runs/{id}/resume": run("R1", "queued"),
    "POST /runs/{id}/discard": run("R1", "discarded"),
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
  notification.sendNotification.mockClear();
  core.isTauri.mockReturnValue(true);
  window.sessionStorage.clear();
  resetDraftMemory();
});

describe("running indicator (R15.5)", () => {
  it("is empty when nothing runs (R13.1)", async () => {
    const { calls } = setup([]);
    await waitFor(() => expect(calls.some((c) => c.path === "/runs/active")).toBe(true));
    expect(screen.queryByTestId("running-indicator")).toBeNull();
    expect(screen.getByTestId("running-slot")).toBeEmptyDOMElement();
  });

  it("running on AC: thread name, stage, Stop, keep the lid open, no battery note", async () => {
    const { emit, calls } = setup(
      [{ run: run("R1", "running"), current_step: step, stage: 3, stages: 5, stage_label: "Reading the test", percent: 40 }],
      "ac",
    );
    expect(await screen.findByTestId("keep-lid-open")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("run-thread")).toHaveTextContent("Lớp 8 HK1"));
    const indicator = screen.getByTestId("running-indicator");
    expect(within(indicator).getByTestId("run-step")).toHaveTextContent("Reading the test");
    await waitFor(() => expect(calls.some((c) => c.path === "/system/status")).toBe(true));
    expect(screen.queryByTestId("on-battery")).toBeNull();

    emit("run.step_started", { run_id: "R1", thread_id: "th1", node: "read_answers_page", item: "page 2", stage: 4, stages: 5, stage_label: "Reading the answers", percent: 60 });
    expect(within(indicator).getByTestId("run-step")).toHaveTextContent("Reading the answers");
    emit("run.progress", { run_id: "R1", thread_id: "th1", node: "read_answers_page", label: "page 2", unit: "page", done: 2, total: 3, stage: 4, stages: 5, stage_label: "Reading the answers", percent: 73 });
    expect(within(indicator).getByTestId("run-step")).toHaveTextContent("Reading the answers · page 2 of 3");
    expect(indicator).not.toHaveTextContent("read_answers_page");

    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/runs/R1/stop")).toBe(true));
  });

  it("running on battery: shows on battery", async () => {
    setup([{ run: run("R1", "running"), current_step: step }], "battery");
    expect(await screen.findByTestId("on-battery")).toBeInTheDocument();
    expect(screen.getByTestId("keep-lid-open")).toBeInTheDocument();
  });

  it("battery but nothing running: no lid or battery note", async () => {
    setup([{ run: run("R1", "stopped"), current_step: null }], "battery");
    expect(await screen.findByTestId("run-paused")).toBeInTheDocument();
    expect(screen.queryByTestId("keep-lid-open")).toBeNull();
    expect(screen.queryByTestId("on-battery")).toBeNull();
  });

  it("stopped / interrupted (after a restart): Resume and Discard; the queued count", async () => {
    const { calls } = setup([
      { run: run("R1", "interrupted"), current_step: null },
      { run: run("R2", "queued", "th2"), current_step: null },
      { run: run("R3", "queued", "th2"), current_step: null },
    ]);
    expect(await screen.findByText("Interrupted")).toBeInTheDocument();
    expect(screen.getByTestId("run-queued")).toHaveTextContent("2 queued");
    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/runs/R1/resume")).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/runs/R1/discard")).toBe(true));
  });

  it("run.done empties the slot after /runs/active is reloaded", async () => {
    const { emit, state } = setup([{ run: run("R1", "running"), current_step: step }]);
    expect(await screen.findByTestId("running-indicator")).toBeInTheDocument();
    state.active = [];
    emit("run.done", { run_id: "R1", thread_id: "th1" });
    await waitFor(() => expect(screen.queryByTestId("running-indicator")).toBeNull());
  });
});

describe("run toast (R15.7)", () => {
  it("run.done → the plugin is called once with the thread name, also on a repeated delivery", async () => {
    const { emit } = setup([]);
    await screen.findAllByText("Lớp 8 HK1");
    emit("run.done", { run_id: "R1", thread_id: "th1" });
    emit("run.done", { run_id: "R1", thread_id: "th1" }); // a replay after reconnect
    await waitFor(() => expect(notification.sendNotification).toHaveBeenCalledTimes(1));
    expect(notification.sendNotification.mock.calls[0]?.[0]).toMatchObject({ title: "Lớp 8 HK1" });
    await new Promise((r) => setTimeout(r, 20));
    expect(notification.sendNotification).toHaveBeenCalledTimes(1);
  });

  it("without Tauri: an in-app toast instead", async () => {
    core.isTauri.mockReturnValue(false);
    const { emit } = setup([]);
    emit("run.failed", { run_id: "R9", thread_id: "th1", error: "model missing" });
    const toast = await screen.findByTestId("toast");
    expect(toast).toHaveTextContent("Lớp 8 HK1");
    expect(toast).toHaveTextContent("model missing");
    expect(notification.sendNotification).not.toHaveBeenCalled();
  });
});

describe("D18 with an active run", () => {
  it("a thread with a run in /runs/active blocks a drop at once (no POST /files)", async () => {
    const { api, calls } = fakeApi({
      "GET /threads/{id}": {
        thread: { id: "th1", title: "x", kind: "pending", test_id: null, created_at: "" },
        attempt: null,
        test: null,
      },
      "GET /threads/{id}/messages": [],
      "POST /files": { file_id: "f", pages: [] },
    });
    render(
      <ThreadView api={api} threadId="th1" hasActiveRun onThreadCreated={() => {}} onNewThread={() => {}} />,
    );
    const target = screen.getByTestId("conversation");
    fireEvent.drop(target, { dataTransfer: { files: [new File(["x"], "a.jpg")], types: ["Files"] } });
    expect(await screen.findByTestId("thread-blocked")).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/files")).toBe(false);
  });
});
