// Step 22.6.4 (b), the screens for the key run every extraction queues (D4, D11, D13).
// R22.6.4.4: while the thread's key run is pending the Key tab shows a note instead of the keys,
//   which load at once when it ends; Grade student answers waits, greyed, focusable, described by
//   "Making the key…"; a stopped or interrupted key run does not hold the thread.
// R22.6.4.8: the key run shows no toast, done or failed; a failed or discarded key run leaves the
//   Key tab blank with a note that Grade will make the key.
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { EventListenerFn, EventStream, EtachEvent } from "@/api/sse";
import { EventsProvider } from "@/api/sse";
import { ConfirmProvider } from "@/components/ConfirmDialog";
import { ThreadTabActions } from "@/features/panel/ThreadActions";
import { KEY_NOT_MADE, KeysPanel, MAKING_KEY } from "@/features/panels/KeysPanel";
import { isKeyRun, useKeyRuns } from "@/features/running/keyRun";
import { useRunNotifications } from "@/features/running/useRunNotifications";
import { useRunning, type RunEntry } from "@/features/running/useRunning";
import { fakeApi, type FakeCall } from "@/lib/testApi";

const core = vi.hoisted(() => ({ isTauri: vi.fn(() => false) }));
vi.mock("@tauri-apps/api/core", () => core);

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
      listeners.forEach((fn) => fn({ id, type, data: { type, ...data } } as EtachEvent));
    });
  return { stream, emit };
}

const keyRun = (id: string, status: string, thread_id = "th1") => ({
  id,
  thread_id,
  kind: "grade",
  status,
  input: { attempt_id: null, reason: "after_extract" },
  error: null,
  started_at: null,
  finished_at: null,
});
const extractRun = (id: string, status: string) => ({ ...keyRun(id, status), kind: "extract", input: {} });
const entry = (run: object) => ({ run, progress: {}, since: 0 }) as unknown as RunEntry;

const test_ = {
  id: "T-0001",
  meta: { occasion: "FinalTerm", grade: 8, term: 1, edited_fields: [] },
  content: {
    sections: [
      {
        id: "s1",
        number: 1,
        printed_title: "I. Choose",
        title: "Choose",
        instructions: null,
        points: 0.5,
        points_source: "printed",
        skill: "grammar",
        groups: [
          {
            id: "g1",
            stimulus: null,
            pictures: [],
            questions: [1, 2].map((n) => ({
              id: `q-${n}`,
              number: n,
              printed_number: n,
              page_no: 1,
              answer_form: "choice",
              context: "single",
              stem: `Stem ${n}`,
              options: [],
              cue: null,
              points: 0.25,
            })),
          },
        ],
      },
    ],
  },
};
const key = (n: number) => ({ test_id: "T-0001", question_id: `q-${n}`, accepted: ["A"], status: "ai_fast", source: "ai" });

describe("isKeyRun", () => {
  it("is the grade run with reason after_extract, nothing else", () => {
    expect(isKeyRun(keyRun("K", "queued") as never)).toBe(true);
    expect(isKeyRun({ kind: "grade", input: { attempt_id: "A-1" } } as never)).toBe(false);
    expect(isKeyRun({ kind: "grade", input: { reason: "regrade" } } as never)).toBe(false);
    expect(isKeyRun(extractRun("E", "queued") as never)).toBe(false);
    expect(isKeyRun(null)).toBe(false);
  });
});

describe("R22.6.4.4: the Key tab and Grade while the key is being made", () => {
  it("test_r22_6_4_4_key_tab_note: a note instead of the keys; the keys load at once when the run ends", async () => {
    const { api, calls } = fakeApi({ "GET /tests/{id}": test_, "GET /tests/{id}/keys": [key(1), key(2)] });
    const view = render(<KeysPanel api={api} testId="T-0001" keyNote="making" />);
    expect(screen.getByTestId("key-making")).toHaveTextContent(MAKING_KEY);
    expect(screen.getByRole("status")).toHaveTextContent(MAKING_KEY);
    expect(screen.queryByTestId("keys-toolbar")).toBeNull();
    const loads = () => calls.filter((c) => c.path === "/tests/T-0001/keys").length;
    const before = loads();
    view.rerender(<KeysPanel api={api} testId="T-0001" keyNote={null} />);
    await waitFor(() => expect(screen.queryByTestId("key-making")).toBeNull());
    await waitFor(() => expect(loads()).toBeGreaterThan(before));
    await waitFor(() => expect(screen.getByTestId("keys-toolbar")).toBeInTheDocument());
    expect(screen.queryByText(MAKING_KEY)).toBeNull();
  });

  it("test_r22_6_4_4_grade_waits: greyed, aria-disabled but focusable, described by Making the key…; no run starts", async () => {
    const { api, calls } = fakeApi({ "POST /threads/{id}/runs": keyRun("R1", "queued") });
    const detail = {
      thread: { id: "th1", title: "t", kind: "filled", test_id: "T-0001", created_at: "" },
      attempt: { id: "A-0001", status: "extracted" },
      test: { id: "T-0001" },
      student: null,
      shown_title: "t",
      other_thread_count: 0,
    };
    const view = render(
      <ConfirmProvider>
        <ThreadTabActions api={api} threadId="th1" detail={detail as never} busy={false} makingKey />
      </ConfirmProvider>,
    );
    const grade = screen.getByTestId("grade-answers");
    expect(grade).not.toBeDisabled();
    expect(grade).toHaveAttribute("aria-disabled", "true");
    expect(grade).toHaveAccessibleDescription("Making the key…");
    expect(grade).toHaveAttribute("title", "Making the key…");
    // dimmed by its fill, not by opacity on the button, so the focus ring is not faded (WCAG 2.4.7, 1.4.11)
    expect(grade.className.split(/\s+/)).toContain("bg-accent/50");
    expect(grade.className).not.toMatch(/(^|\s)opacity-/);
    expect(grade.className).toMatch(/\bfocus-visible:outline-focus\b/);
    expect(screen.getByTestId("making-key-note")).toHaveTextContent("Making the key…");
    // Extract again stays pressable: it cancels the key run (D12, R22.6.4.6)
    expect(screen.getByRole("button", { name: "Extract again" })).toBeEnabled();
    grade.focus();
    expect(grade).toHaveFocus();
    fireEvent.click(grade);
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    // the key is ready: the button is enabled and starts the grade run
    view.rerender(
      <ConfirmProvider>
        <ThreadTabActions api={api} threadId="th1" detail={detail as never} busy={false} makingKey={false} />
      </ConfirmProvider>,
    );
    expect(screen.queryByTestId("making-key-note")).toBeNull();
    expect(screen.getByTestId("grade-answers")).not.toHaveAttribute("aria-disabled");
    fireEvent.click(screen.getByTestId("grade-answers"));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/threads/th1/runs")).toBe(true));
  });

  it("test_r22_6_4_4_pending_states: queued, running and stopping are pending; stopped and interrupted are not", () => {
    const seen: Record<string, boolean> = {};
    const { api } = fakeApi({});
    function Probe({ runs }: { runs: RunEntry[] }) {
      const k = useKeyRuns(api, runs);
      seen.th1 = k.pending("th1");
      seen.th2 = k.pending("th2");
      return null;
    }
    const { stream } = fakeStream();
    for (const [status, pending] of [
      ["queued", true],
      ["running", true],
      ["stopping", true],
      ["stopped", false],
      ["interrupted", false],
    ] as const) {
      const v = render(
        <EventsProvider stream={stream}>
          <Probe runs={[entry(keyRun("K", status)), entry({ ...extractRun("E", "running"), thread_id: "th2" })]} />
        </EventsProvider>,
      );
      expect(seen.th1, status).toBe(pending);
      expect(seen.th2).toBe(false);
      v.unmount();
    }
  });
});

describe("R22.6.4.8: no toast for the key run; a failed key run leaves a note", () => {
  function ToastList({ api }: { api: Parameters<typeof useRunNotifications>[0] }) {
    const { toasts } = useRunNotifications(api, () => "Thread");
    return (
      <ul>
        {toasts.map((t) => (
          <li key={t.id} data-testid="toast">
            {t.body}
          </li>
        ))}
      </ul>
    );
  }

  it("test_r22_6_4_8_no_toast: done and failed key runs show nothing; another run still shows its toast", async () => {
    const runs: Record<string, object> = { K1: keyRun("K1", "done"), K2: keyRun("K2", "failed"), E1: extractRun("E1", "done") };
    const { api } = fakeApi({
      "GET /runs/{id}": (c: FakeCall) => ({ run: runs[c.path.split("/")[2] ?? ""], steps: [] }),
      "GET /threads/{id}": { thread: { id: "th1", title: "Lớp 8" }, shown_title: "Lớp 8" },
    });
    const { stream, emit } = fakeStream();
    render(
      <EventsProvider stream={stream}>
        <ToastList api={api} />
      </EventsProvider>,
    );
    emit("run.done", { run_id: "K1", thread_id: "th1" });
    emit("run.failed", { run_id: "K2", thread_id: "th1", error: "CassetteMiss: transcribe" });
    emit("run.done", { run_id: "E1", thread_id: "th1" });
    await waitFor(() => expect(screen.getAllByTestId("toast")).toHaveLength(1));
    await new Promise((r) => setTimeout(r, 30));
    expect(screen.getAllByTestId("toast").map((t) => t.textContent)).toEqual(["Finished."]);
  });

  it("test_r22_6_4_8_failed_note: a failed or discarded key run marks the thread; the empty Key tab says Grade will make the key", async () => {
    const seen: { failed?: boolean } = {};
    const { api } = fakeApi({ "GET /runs/{id}": { run: keyRun("K9", "discarded"), steps: [] } });
    function Probe({ runs }: { runs: RunEntry[] }) {
      seen.failed = useKeyRuns(api, runs).failed("th1");
      return null;
    }
    const { stream, emit } = fakeStream();
    const v = render(
      <EventsProvider stream={stream}>
        <Probe runs={[entry(keyRun("K1", "running"))]} />
      </EventsProvider>,
    );
    v.rerender(
      <EventsProvider stream={stream}>
        <Probe runs={[]} />
      </EventsProvider>,
    );
    emit("run.failed", { run_id: "K1", thread_id: "th1", error: "x" });
    expect(seen.failed).toBe(true);
    emit("run.done", { run_id: "K1", thread_id: "th1" });
    expect(seen.failed).toBe(false);
    // a discarded key run the list never saw is looked up
    emit("run.discarded", { run_id: "K9", thread_id: "th1" });
    await waitFor(() => expect(seen.failed).toBe(true));

    const keys = fakeApi({ "GET /tests/{id}": test_, "GET /tests/{id}/keys": [] });
    render(<KeysPanel api={keys.api} testId="T-0001" keyNote="failed" />);
    expect(await screen.findByTestId("key-not-made")).toHaveTextContent(KEY_NOT_MADE);
    expect(screen.queryByText("No keys yet: grade the test or add a key.")).toBeNull();
  });
});

describe("R22.6.4.6 (D12) on screen: the key run does not hold Extract again; another run does", () => {
  it("test_r22_6_4_6_extract_again: busy (another run) disables both actions; the key run alone disables neither", () => {
    const { api } = fakeApi({});
    const detail = {
      thread: { id: "th1", title: "t", kind: "filled", test_id: "T-0001", created_at: "" },
      attempt: { id: "A-0001", status: "extracted" },
      test: { id: "T-0001" },
      student: null,
      shown_title: "t",
      other_thread_count: 0,
    };
    const v = render(
      <ConfirmProvider>
        <ThreadTabActions api={api} threadId="th1" detail={detail as never} busy makingKey={false} />
      </ConfirmProvider>,
    );
    expect(screen.getByRole("button", { name: "Extract again" })).toBeDisabled();
    expect(screen.getByTestId("grade-answers")).toBeDisabled();
    v.unmount();
    render(
      <ConfirmProvider>
        <ThreadTabActions api={api} threadId="th1" detail={detail as never} busy={false} makingKey />
      </ConfirmProvider>,
    );
    expect(screen.getByRole("button", { name: "Extract again" })).toBeEnabled();
  });
});

describe("useRunning: busyThreadIds leaves the key run out", () => {
  it("test_r22_6_4_6_busy_threads: a thread with only its key run is not busy; one with another run is", async () => {
    const { api } = fakeApi({
      "GET /runs/active": [
        { run: keyRun("K1", "running", "th1"), current_step: null },
        { run: keyRun("K2", "queued", "th2"), current_step: null },
        { run: { ...extractRun("E2", "running"), thread_id: "th2" }, current_step: null },
      ],
      "GET /system/status": { power_source: "ac" },
    });
    const seen: { busy?: string[]; active?: string[] } = {};
    function Probe() {
      const r = useRunning(api);
      seen.busy = [...r.busyThreadIds].sort();
      seen.active = [...r.activeThreadIds].sort();
      return null;
    }
    const { stream } = fakeStream();
    render(
      <EventsProvider stream={stream}>
        <Probe />
      </EventsProvider>,
    );
    await waitFor(() => expect(seen.active).toEqual(["th1", "th2"]));
    expect(seen.busy).toEqual(["th2"]);
  });
});

