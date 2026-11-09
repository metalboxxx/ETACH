/**
 * The sidecar event stream (`GET /events`, llm-design §2) with reconnect and replay.
 *
 * The sidecar's EventHub numbers every event (`id: <n>`) and, given `last_event_id`, replays the
 * buffered events after it. `EventSource` cannot set headers, so the token and the last id go in
 * the query (`/events?token=…&last_event_id=…`). On a drop this module closes the EventSource
 * (no native auto-retry, which would not carry our query id), waits with exponential backoff
 * and reconnects from the last delivered id. Events with an id <= the last delivered one are
 * dropped, so a subscriber never sees an id twice.
 *
 *   const stream = createEventStream((last) => api.eventsUrl(last));
 *   <EventsProvider stream={stream}> … </EventsProvider>
 *   useEvents((e) => { if (e.type === "run.done") … }, ["run.done", "run.failed"]);
 *   const status = useEventStatus();  // "connecting" | "open" | "reconnecting" | "closed"
 *
 * Limitation: the ids restart at 1 when the sidecar process restarts; the shell restarts the
 * page with it (step 14), which creates a fresh stream.
 */
import {
  createContext,
  createElement,
  useContext,
  useEffect,
  useRef,
  useSyncExternalStore,
  type ReactNode,
} from "react";

/** The event names the sidecar sends (sidecar `etach.api.routes.sse.EVENT_TYPES`). */
export const EVENT_TYPES = [
  "run.queued",
  "run.step_started",
  "run.step_done",
  "run.progress",
  "run.done",
  "run.failed",
  "run.stopped",
  "run.interrupted",
  "run.discarded",
  "review.changed",
  "system.changed",
  "models.pull_progress",
] as const;

export type EtachEventType = (typeof EVENT_TYPES)[number];

/** The JSON payload: always `type`; run events add `run_id`, `thread_id` and step details. */
export interface EtachEventData {
  type: EtachEventType;
  run_id?: string;
  thread_id?: string;
  step_id?: string;
  node?: string;
  item?: string | null;
  try_no?: number;
  done?: number;
  total?: number;
  label?: string;
  [key: string]: unknown;
}

export interface EtachEvent {
  /** The EventHub sequence number. */
  id: number;
  type: EtachEventType;
  data: EtachEventData;
}

export type StreamStatus = "idle" | "connecting" | "open" | "reconnecting" | "closed";
export type EventListenerFn = (event: EtachEvent) => void;

/** The subset of the EventSource API used here (a test double can implement it). */
export interface EventSourceLike {
  readonly readyState: number;
  onopen: ((ev: Event) => unknown) | null;
  onerror: ((ev: Event) => unknown) | null;
  addEventListener(type: string, listener: (ev: MessageEvent) => void): void;
  close(): void;
}
export type EventSourceFactory = (url: string) => EventSourceLike;

export interface EventStreamOptions {
  eventSource?: EventSourceFactory;
  /** First reconnect delay; doubles per failed attempt up to `maxDelayMs`. */
  initialDelayMs?: number;
  maxDelayMs?: number;
}

export interface EventStream {
  start(): void;
  close(): void;
  subscribe(listener: EventListenerFn): () => void;
  onStatus(listener: () => void): () => void;
  readonly status: StreamStatus;
  readonly lastEventId: number | null;
}

export function createEventStream(
  urlFor: (lastEventId: string | null) => string,
  options: EventStreamOptions = {},
): EventStream {
  const factory: EventSourceFactory =
    options.eventSource ?? ((url) => new EventSource(url) as unknown as EventSourceLike);
  const initialDelay = options.initialDelayMs ?? 500;
  const maxDelay = options.maxDelayMs ?? 10_000;

  const listeners = new Set<EventListenerFn>();
  const statusListeners = new Set<() => void>();
  let source: EventSourceLike | null = null;
  let status: StreamStatus = "idle";
  let lastId: number | null = null;
  let attempt = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const setStatus = (next: StreamStatus) => {
    if (status === next) return;
    status = next;
    statusListeners.forEach((fn) => fn());
  };

  const deliver = (type: EtachEventType, msg: MessageEvent) => {
    const id = Number(msg.lastEventId);
    if (!Number.isFinite(id) || msg.lastEventId === "") return;
    if (lastId !== null && id <= lastId) return; // replayed duplicate
    let data: EtachEventData;
    try {
      data = JSON.parse(String(msg.data)) as EtachEventData;
    } catch {
      return;
    }
    lastId = id;
    const event: EtachEvent = { id, type, data };
    listeners.forEach((fn) => {
      try {
        fn(event);
      } catch (err) {
        console.error("event listener failed", err);
      }
    });
  };

  const connect = () => {
    timer = null;
    const es = factory(urlFor(lastId === null ? null : String(lastId)));
    source = es;
    es.onopen = () => {
      attempt = 0;
      setStatus("open");
    };
    es.onerror = () => {
      if (source !== es) return;
      es.close();
      source = null;
      scheduleReconnect();
    };
    for (const type of EVENT_TYPES) {
      es.addEventListener(type, (msg) => {
        if (source === es) deliver(type, msg);
      });
    }
  };

  const scheduleReconnect = () => {
    if (status === "closed") return;
    setStatus("reconnecting");
    const delay = Math.min(maxDelay, initialDelay * 2 ** attempt);
    attempt += 1;
    timer = setTimeout(connect, delay);
  };

  return {
    start() {
      if (source || timer || status === "open") return;
      setStatus("connecting");
      connect();
    },
    close() {
      if (timer) clearTimeout(timer);
      timer = null;
      source?.close();
      source = null;
      setStatus("closed");
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    onStatus(listener) {
      statusListeners.add(listener);
      return () => statusListeners.delete(listener);
    },
    get status() {
      return status;
    },
    get lastEventId() {
      return lastId;
    },
  };
}

const EventsContext = createContext<EventStream | null>(null);

/** Provides one shared stream to the tree and starts it; closes it on unmount. */
export function EventsProvider({ stream, children }: { stream: EventStream; children: ReactNode }) {
  useEffect(() => {
    stream.start();
    return () => stream.close();
  }, [stream]);
  return createElement(EventsContext.Provider, { value: stream }, children);
}

function useStream(explicit?: EventStream): EventStream {
  const ctx = useContext(EventsContext);
  const stream = explicit ?? ctx;
  if (!stream) throw new Error("useEvents needs an <EventsProvider> or an explicit stream");
  return stream;
}

/**
 * Calls `handler` for every event (or only the listed `types`). The handler may change between
 * renders without resubscribing.
 */
export function useEvents(
  handler: EventListenerFn,
  types?: readonly EtachEventType[],
  stream?: EventStream,
): void {
  const s = useStream(stream);
  const handlerRef = useRef(handler);
  useEffect(() => {
    handlerRef.current = handler;
  });
  const typeKey = types ? types.join(",") : "";
  useEffect(() => {
    const wanted = typeKey ? new Set(typeKey.split(",")) : null;
    return s.subscribe((e) => {
      if (!wanted || wanted.has(e.type)) handlerRef.current(e);
    });
  }, [s, typeKey]);
}

/** The connection status, for the "running" indicator / an offline banner. */
export function useEventStatus(stream?: EventStream): StreamStatus {
  const s = useStream(stream);
  return useSyncExternalStore(
    (cb) => s.onStatus(cb),
    () => s.status,
  );
}
