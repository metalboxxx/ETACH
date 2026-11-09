// Step 22.2.3: the run notice for a thread that is not in the loaded list shows its real title
// (`shown_title` from `GET /threads/{id}`), not "New thread".
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ApiClient } from "@/api/client";
import type { EtachEvent, EventListenerFn, EventStream } from "@/api/sse";
import { EventsProvider } from "@/api/sse";
import { fakeApi } from "@/lib/testApi";
import { useRunNotifications } from "./useRunNotifications";

vi.mock("@tauri-apps/api/core", () => ({ isTauri: () => false }));

function Toasts({ api }: { api: ApiClient }) {
  const { toasts } = useRunNotifications(api, () => "New thread");
  return (
    <ul>
      {toasts.map((t) => (
        <li key={t.id} data-testid="toast">
          {t.title}
        </li>
      ))}
    </ul>
  );
}

describe("run notification title", () => {
  it("uses the thread's shown title for a thread outside the loaded list", async () => {
    const listeners = new Set<EventListenerFn>();
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
        return 1;
      },
    };
    const { api } = fakeApi({
      "GET /threads/{id}": { thread: { id: "t9", title: "New thread" }, shown_title: "Final 8.1 · Học Sinh A" },
    });
    render(
      <EventsProvider stream={stream}>
        <Toasts api={api} />
      </EventsProvider>,
    );
    act(() => {
      const e = { id: 1, type: "run.done", data: { type: "run.done", run_id: "r1", thread_id: "t9" } } as EtachEvent;
      listeners.forEach((fn) => fn(e));
    });
    expect(await screen.findByTestId("toast")).toHaveTextContent("Final 8.1 · Học Sinh A");
  });
});
