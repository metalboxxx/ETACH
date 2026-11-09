// Step 22.1.3, R22.1.3.4: the running indicator and the running thread show a progressbar
// (role, aria-valuenow = percent), "<stage_label> · <unit> <done> of <total>", an elapsed time
// that counts up, and a "Writing" sign after a `tokens` event; no node name is in the DOM; with
// reduced motion only the value changes. R22.1.3.5: after a reload, the bar shows the percent
// and the stage from GET /runs/active before any event.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { EtachEvent, EventListenerFn, EventStream } from "@/api/sse";
import { EventsProvider } from "@/api/sse";
import { Connected } from "@/App";
import { fakeApi, type FakeCall } from "@/lib/testApi";
import { resetDraftMemory } from "@/features/photo-check/draft";
import { formatElapsed, RunProgressBar, WRITING_MS } from "./RunProgressBar";
import {
  applyProgressEvent,
  EMPTY_PROGRESS,
  progressFromActive,
  progressText,
  type RunEntry,
  type RunProgress,
} from "./useRunning";

vi.mock("@tauri-apps/plugin-notification", () => ({
  isPermissionGranted: vi.fn(async () => true),
  requestPermission: vi.fn(async () => "granted"),
  sendNotification: vi.fn(),
}));
vi.mock("@tauri-apps/api/core", () => ({ isTauri: vi.fn(() => true) }));

/** Every node name of llm-design §2's stage lists: none may reach the DOM. */
const NODE_NAMES = [
  "prepare_pages",
  "read_key_pages",
  "load_bank_test",
  "read_header",
  "sanity_check",
  "transcribe_page",
  "retranscribe_tiles",
  "merge_and_normalize",
  "compare_bank",
  "map_key",
  "read_answers_page",
  "resolve_answers",
  "load_context",
  "ai_key_fast",
  "verify_gate",
  "verify_key",
  "tag_skills",
  "judge_rewrites",
  "weak_points",
];

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

const STARTED = "2026-10-13T08:00:00Z";
const run = (status: string) => ({
  id: "R1",
  thread_id: "th1",
  kind: "extract",
  status,
  input: {},
  error: null,
  started_at: STARTED,
  finished_at: null,
});
const thread = { id: "th1", title: "Lớp 8 HK1", kind: "pending", test_id: null, created_at: "2026-10-03T00:00:00Z" };
const step = { id: "s1", run_id: "R1", node: "transcribe_page", item: "page 2", status: "running", try_no: 1, started_at: "", finished_at: null };
const active = (status = "running") => ({
  run: run(status),
  current_step: step,
  stage: 3,
  stages: 5,
  stage_label: "Reading the test",
  percent: 40,
});

function setup(rows: unknown[]) {
  const state = { rows };
  const fake = fakeApi({
    "GET /threads": [
      { group: "Blank tests", kind: "pending", last_activity: "2026-10-03T00:00:00Z", student_id: null, thread },
    ],
    "GET /threads/{id}": (c: FakeCall) => ({ thread: { ...thread, id: c.path.split("/")[2] ?? "" }, attempt: null, test: null }),
    "GET /threads/{id}/messages": [],
    "GET /review/count": { count: 0 },
    "GET /runs/active": () => state.rows,
    "GET /system/status": () => ({
      power_source: "ac",
      keep_awake: true,
      missing_models: [],
      models_present: [],
      ollama_status: "ok",
      ollama_version: "0.12",
      other_ollama_loaded: false,
    }),
  });
  const { stream, emit } = fakeStream();
  const view = render(
    <EventsProvider stream={stream}>
      <Connected api={fake.api} />
    </EventsProvider>,
  );
  return { ...fake, emit, state, view };
}

async function openThread() {
  const item = (await screen.findAllByTestId("thread-item"))[0]!;
  fireEvent.click(item);
  return screen.findByTestId("thread-run");
}

function bars() {
  return screen.getAllByRole("progressbar", { name: "Run progress" });
}

beforeEach(() => {
  window.sessionStorage.clear();
  resetDraftMemory();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("progress state (no node names)", () => {
  const ev = (type: "run.step_started" | "run.progress", data: Record<string, unknown>) =>
    ({ type, ...data }) as Parameters<typeof applyProgressEvent>[1];

  it("a stage change clears the count; the percent never goes down", () => {
    let p: RunProgress = EMPTY_PROGRESS;
    p = applyProgressEvent(p, ev("run.step_started", { node: "transcribe_page", stage: 3, stages: 5, stage_label: "Reading the test", percent: 40 }), 0);
    p = applyProgressEvent(p, ev("run.progress", { unit: "page", done: 2, total: 4, stage: 3, stages: 5, stage_label: "Reading the test", percent: 50 }), 0);
    expect(progressText(p)).toBe("Reading the test · page 2 of 4");
    p = applyProgressEvent(p, ev("run.progress", { stage: 3, stages: 5, stage_label: "Reading the test", percent: 45 }), 0);
    expect(p.percent).toBe(50);
    p = applyProgressEvent(p, ev("run.step_started", { stage: 4, stages: 5, stage_label: "Reading the answers", percent: 60 }), 0);
    expect(progressText(p)).toBe("Reading the answers");
    p = applyProgressEvent(p, ev("run.step_started", { stage: 3, stages: 5, stage_label: "Reading the test", percent: 55 }), 0);
    expect([p.stageLabel, p.percent]).toEqual(["Reading the answers", 60]);
  });

  it("a tokens event marks the model as writing and keeps the count", () => {
    let p = applyProgressEvent(EMPTY_PROGRESS, ev("run.progress", { unit: "question", done: 1, total: 9, stage: 4, stages: 6, stage_label: "Explaining mistakes", percent: 51 }), 0);
    p = applyProgressEvent(p, ev("run.progress", { tokens: 120, stage: 4, stages: 6, stage_label: "Explaining mistakes", percent: 51 }), 1234);
    expect(p.writingAt).toBe(1234);
    expect(progressText(p)).toBe("Explaining mistakes · question 1 of 9");
  });

  it("events without stage fields change nothing shown", () => {
    const p = applyProgressEvent(EMPTY_PROGRESS, ev("run.progress", { node: "pages", done: 1, total: 3, label: "page 1" }), 0);
    expect(progressText(p)).toBeNull();
    expect(p.percent).toBeNull();
  });

  it("an active-run row keeps the count already shown for the same stage", () => {
    const shown = { ...EMPTY_PROGRESS, stage: 3, stages: 5, stageLabel: "Reading the test", percent: 50, unit: "page", done: 2, total: 4 };
    const row = active() as Parameters<typeof progressFromActive>[0];
    expect(progressFromActive(row, shown)).toMatchObject({ percent: 50, done: 2, unit: "page" });
    expect(progressFromActive(row, undefined)).toMatchObject({ percent: 40, stageLabel: "Reading the test", done: null });
  });

  it("R22.2.1.5: the count names the page being read, and a second pass says 'again'", () => {
    let p = applyProgressEvent(EMPTY_PROGRESS, ev("run.progress", { unit: "page", done: 2, total: 4, current: 3, stage: 3, stages: 5, stage_label: "Reading the test", percent: 50 }), 0);
    expect(progressText(p)).toBe("Reading the test · page 3 of 4");
    p = applyProgressEvent(p, ev("run.progress", { unit: "page", done: 0, total: 1, current: 2, again: true, stage: 3, stages: 5, stage_label: "Reading the test", percent: 55 }), 0);
    expect(progressText(p)).toBe("Reading the test · Checking page 2 again");
    p = applyProgressEvent(p, ev("run.progress", { unit: "page", done: 1, total: 4, current: 2, stage: 3, stages: 5, stage_label: "Reading the test", percent: 56 }), 0);
    expect(progressText(p)).toBe("Reading the test · page 2 of 4");
  });

  it("formats the elapsed time", () => {
    expect(formatElapsed(0)).toBe("0:00");
    expect(formatElapsed(65_000)).toBe("1:05");
    expect(formatElapsed(3_729_000)).toBe("1:02:09");
  });
});

describe("RunProgressBar", () => {
  const entry = (progress: Partial<RunProgress>, since = 0): RunEntry => ({
    run: run("running") as RunEntry["run"],
    progress: { ...EMPTY_PROGRESS, ...progress },
    since,
  });

  it("is a labelled progressbar whose value is the percent", () => {
    render(<RunProgressBar entry={entry({ stage: 3, stages: 5, stageLabel: "Reading the test", percent: 47, unit: "page", done: 2, total: 4 })} />);
    const bar = screen.getByRole("progressbar", { name: "Run progress" });
    expect(bar).toHaveAttribute("aria-valuenow", "47");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
    expect(bar).toHaveAttribute("aria-valuetext", "47%, Reading the test · page 2 of 4");
    expect(screen.getByTestId("run-step")).toHaveTextContent("Reading the test · page 2 of 4");
    expect(screen.getByTestId("run-percent")).toHaveTextContent("47%");
  });

  it("R22.2.1.5: the stage text wraps (no ellipsis, no clipping)", () => {
    render(<RunProgressBar entry={entry({ stage: 3, stages: 5, stageLabel: "Reading the answers", percent: 47, unit: "page", current: 2, total: 4, again: true })} />);
    const step = screen.getByTestId("run-step");
    expect(step).toHaveTextContent("Reading the answers · Checking page 2 again");
    expect(step.className).not.toMatch(/truncate|text-ellipsis|whitespace-nowrap|line-clamp/);
  });

  it("before the first stage: 'Starting…' and no value", () => {
    render(<RunProgressBar entry={entry({})} />);
    expect(screen.getByTestId("run-step")).toHaveTextContent("Starting…");
    expect(screen.getByRole("progressbar")).not.toHaveAttribute("aria-valuenow");
  });

  it("the elapsed time counts up", () => {
    vi.useFakeTimers({ now: 100_000 });
    render(<RunProgressBar entry={entry({ stage: 1, stages: 5, stageLabel: "Preparing the photos", percent: 0 }, 100_000 - 64_000)} />);
    expect(screen.getByTestId("run-elapsed")).toHaveTextContent(/^Elapsed 1:04$/);
    act(() => vi.advanceTimersByTime(3_000));
    expect(screen.getByTestId("run-elapsed")).toHaveTextContent("1:07");
  });

  it("the Writing sign shows after a tokens event and goes after a quiet spell", () => {
    vi.useFakeTimers({ now: 50_000 });
    render(<RunProgressBar entry={entry({ stage: 3, stages: 5, stageLabel: "Reading the test", percent: 40, writingAt: 50_000 })} />);
    expect(screen.getByTestId("run-writing")).toHaveTextContent(/^Model is writing$/);
    act(() => vi.advanceTimersByTime(WRITING_MS + 1_000));
    expect(screen.queryByTestId("run-writing")).toBeNull();
  });

  it("with reduced motion nothing animates except the value", () => {
    render(<RunProgressBar entry={entry({ stage: 3, stages: 5, stageLabel: "Reading the test", percent: 40, writingAt: Date.now() })} />);
    const root = screen.getByTestId("run-progress");
    const classes = [root, ...root.querySelectorAll("*")].flatMap((el) => [...el.classList]);
    const moving = classes.filter((c) => /(^|:)(animate-|transition|duration-|ease-)/.test(c));
    expect(moving.length).toBeGreaterThan(0);
    expect(moving.every((c) => c.startsWith("motion-safe:"))).toBe(true);
    // the value is a transform of the fill, not a width animation
    const fill = screen.getByRole("progressbar").firstElementChild as HTMLElement;
    expect(fill.style.transform).toBe("scaleX(0.4)");
  });
});

describe("in the app (R22.1.3.4, R22.1.3.5)", () => {
  it("after a reload the indicator and the thread show the seeded percent and stage before any event", async () => {
    setup([active()]);
    const indicator = await screen.findByTestId("running-indicator");
    await waitFor(() => expect(within(indicator).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40"));
    expect(within(indicator).getByTestId("run-step")).toHaveTextContent("Reading the test");
    const card = await openThread();
    expect(within(card).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
    expect(within(card).getByTestId("run-step")).toHaveTextContent("Reading the test");
    expect(bars()).toHaveLength(2);
  });

  it("events move both bars; tokens show the sign; no node name in the DOM", async () => {
    const { emit, view } = setup([active()]);
    await openThread();
    emit("run.progress", { run_id: "R1", thread_id: "th1", step_id: "s1", node: "transcribe_page", item: "page 2", label: "page 2", unit: "page", done: 2, total: 4, stage: 3, stages: 5, stage_label: "Reading the test", percent: 50 });
    for (const bar of bars()) expect(bar).toHaveAttribute("aria-valuenow", "50");
    for (const t of screen.getAllByTestId("run-step")) expect(t).toHaveTextContent("Reading the test · page 2 of 4");
    expect(screen.queryByTestId("run-writing")).toBeNull();
    emit("run.progress", { run_id: "R1", thread_id: "th1", step_id: "s1", node: "transcribe_page", item: "page 2", tokens: 312, stage: 3, stages: 5, stage_label: "Reading the test", percent: 50 });
    expect(screen.getAllByTestId("run-writing")).toHaveLength(2);
    emit("run.step_started", { run_id: "R1", thread_id: "th1", step_id: "s2", node: "read_answers_page", item: "page 3", try_no: 1, stage: 4, stages: 5, stage_label: "Reading the answers", percent: 60 });
    for (const t of screen.getAllByTestId("run-step")) expect(t).toHaveTextContent(/^Reading the answers$/);
    const html = view.container.innerHTML;
    for (const node of NODE_NAMES) expect(html).not.toContain(node);
  });

  it("the thread's bar goes when the run is done", async () => {
    const { emit, state } = setup([active()]);
    await openThread();
    state.rows = [];
    emit("run.done", { run_id: "R1", thread_id: "th1", stage: 5, stages: 5, stage_label: "Saving", percent: 100 });
    await waitFor(() => expect(screen.queryByTestId("thread-run")).toBeNull());
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("a stopped run shows Resume, not a bar", async () => {
    setup([active("stopped")]);
    expect(await screen.findByTestId("run-paused")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).toBeNull();
  });
});
