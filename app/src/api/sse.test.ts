import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  createEventStream,
  useEvents,
  useEventStatus,
  type EtachEvent,
  type EventSourceLike,
} from "./sse";

/** A controllable stand-in for EventSource: the "server" side pushes events or drops. */
class MockEventSource implements EventSourceLike {
  static instances: MockEventSource[] = [];
  readyState = 0;
  onopen: ((ev: Event) => unknown) | null = null;
  onerror: ((ev: Event) => unknown) | null = null;
  private handlers = new Map<string, ((ev: MessageEvent) => void)[]>();
  constructor(readonly url: string) {
    MockEventSource.instances.push(this);
  }
  addEventListener(type: string, listener: (ev: MessageEvent) => void) {
    this.handlers.set(type, [...(this.handlers.get(type) ?? []), listener]);
  }
  close() {
    this.readyState = 2;
  }
  open() {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }
  emit(id: number, type: string, payload: Record<string, unknown> = {}) {
    if (this.readyState === 2) return;
    const msg = new MessageEvent(type, {
      data: JSON.stringify({ type, ...payload }),
      lastEventId: String(id),
    });
    this.handlers.get(type)?.forEach((h) => h(msg));
  }
  drop() {
    this.readyState = 2;
    this.onerror?.(new Event("error"));
  }
}

const urlFor = (last: string | null) =>
  `http://127.0.0.1:9/events?token=t${last ? `&last_event_id=${last}` : ""}`;

describe("event stream (R13.5)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    MockEventSource.instances = [];
  });
  afterEach(() => vi.useRealTimers());

  it("reconnects after the server drops, resumes from the last id, and never repeats an id", () => {
    const stream = createEventStream(urlFor, {
      eventSource: (url) => new MockEventSource(url),
      initialDelayMs: 100,
    });
    const got: EtachEvent[] = [];
    stream.subscribe((e) => got.push(e));
    stream.start();

    const first = MockEventSource.instances[0]!;
    expect(first.url).not.toContain("last_event_id");
    first.open();
    first.emit(1, "run.queued", { run_id: "r1", thread_id: "t1" });
    first.emit(2, "run.step_started", { run_id: "r1", thread_id: "t1", node: "extract" });
    expect(stream.status).toBe("open");

    first.drop();
    expect(stream.status).toBe("reconnecting");
    first.emit(3, "run.step_done"); // a closed source delivers nothing
    expect(MockEventSource.instances).toHaveLength(1);

    vi.advanceTimersByTime(100);
    const second = MockEventSource.instances[1]!;
    expect(second.url).toContain("last_event_id=2");
    second.open();
    // The EventHub replays the buffer after id 2; an overlapping replay of 2 is ignored.
    second.emit(2, "run.step_started", { run_id: "r1", thread_id: "t1" });
    second.emit(3, "run.step_done", { run_id: "r1", thread_id: "t1" });
    second.emit(4, "run.done", { run_id: "r1", thread_id: "t1" });

    expect(got.map((e) => e.id)).toEqual([1, 2, 3, 4]);
    expect(got.map((e) => e.type)).toEqual([
      "run.queued",
      "run.step_started",
      "run.step_done",
      "run.done",
    ]);
    expect(got[3]!.data.run_id).toBe("r1");
    expect(stream.lastEventId).toBe(4);
    stream.close();
  });

  it("backs off exponentially while the server stays down, then resets after a connect", () => {
    const stream = createEventStream(urlFor, {
      eventSource: (url) => new MockEventSource(url),
      initialDelayMs: 100,
      maxDelayMs: 250,
    });
    stream.start();
    MockEventSource.instances[0]!.drop();
    vi.advanceTimersByTime(99);
    expect(MockEventSource.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(MockEventSource.instances).toHaveLength(2);
    MockEventSource.instances[1]!.drop(); // 200 ms next
    vi.advanceTimersByTime(199);
    expect(MockEventSource.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    MockEventSource.instances[2]!.drop(); // capped at 250 ms
    vi.advanceTimersByTime(250);
    expect(MockEventSource.instances).toHaveLength(4);
    MockEventSource.instances[3]!.open();
    MockEventSource.instances[3]!.drop(); // back to 100 ms after a successful open
    vi.advanceTimersByTime(100);
    expect(MockEventSource.instances).toHaveLength(5);
    stream.close();
    expect(stream.status).toBe("closed");
  });

  it("close() stops reconnecting", () => {
    const stream = createEventStream(urlFor, {
      eventSource: (url) => new MockEventSource(url),
      initialDelayMs: 10,
    });
    stream.start();
    MockEventSource.instances[0]!.drop();
    stream.close();
    vi.advanceTimersByTime(1000);
    expect(MockEventSource.instances).toHaveLength(1);
  });

  it("useEvents delivers filtered events to the latest handler across a reconnect", () => {
    const stream = createEventStream(urlFor, {
      eventSource: (url) => new MockEventSource(url),
      initialDelayMs: 10,
    });
    stream.start();
    const seen: number[] = [];
    const { result } = renderHook(() => {
      useEvents((e) => seen.push(e.id), ["run.done"], stream);
      return useEventStatus(stream);
    });
    const a = MockEventSource.instances[0]!;
    act(() => a.open());
    expect(result.current).toBe("open");
    act(() => {
      a.emit(1, "run.progress");
      a.emit(2, "run.done");
      a.drop();
    });
    expect(result.current).toBe("reconnecting");
    act(() => vi.advanceTimersByTime(10));
    const b = MockEventSource.instances[1]!;
    act(() => {
      b.open();
      b.emit(2, "run.done");
      b.emit(3, "run.done");
    });
    expect(seen).toEqual([2, 3]);
    stream.close();
  });
});
