import { describe, expect, it, vi } from "vitest";
import { ApiError, createApiClient, type FetchLike } from "./client";
import { readSidecarConfig } from "./config";

const cfg = { baseUrl: "http://127.0.0.1:8765", token: "secret" };

function fakeFetch(status: number, body: unknown) {
  return vi.fn<FetchLike>(async () =>
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

describe("api client", () => {
  it("fills path params, sends the Bearer header and parses JSON", async () => {
    const f = fakeFetch(200, { id: "th1" });
    const api = createApiClient(cfg, f);
    const out = await api.get("/threads/{id}", { path: { id: "a b" } });
    expect(out).toEqual({ id: "th1" });
    const [url, init] = f.mock.calls[0]!;
    expect(url).toBe("http://127.0.0.1:8765/threads/a%20b");
    expect(url).not.toContain("token=");
    expect((init!.headers as Record<string, string>).Authorization).toBe("Bearer secret");
    expect(init!.method).toBe("GET");
  });

  it("sends a JSON body", async () => {
    const f = fakeFetch(200, {});
    const api = createApiClient(cfg, f);
    await api.put("/settings", { body: { language: "vi" } as never });
    const [, init] = f.mock.calls[0]!;
    expect(init!.body).toBe('{"language":"vi"}');
    expect((init!.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("uploads raw bytes with ?name= (not multipart)", async () => {
    const f = fakeFetch(200, { id: "f1" });
    const api = createApiClient(cfg, f);
    const bytes = new Uint8Array([1, 2, 3]);
    await api.uploadFile(bytes, "trang 1.jpg");
    const [url, init] = f.mock.calls[0]!;
    expect(url).toBe("http://127.0.0.1:8765/files?name=trang+1.jpg");
    expect(init!.body).toBe(bytes);
    expect((init!.headers as Record<string, string>)["Content-Type"]).toBe("application/octet-stream");
  });

  it("uses the query token only for file and event URLs", () => {
    const api = createApiClient(cfg);
    expect(api.fileUrl("abc")).toBe("http://127.0.0.1:8765/files/abc?token=secret");
    expect(api.eventsUrl()).toBe("http://127.0.0.1:8765/events?token=secret");
    expect(api.eventsUrl("7")).toBe("http://127.0.0.1:8765/events?token=secret&last_event_id=7");
  });

  it("turns a non-2xx response into a typed ApiError with the detail", async () => {
    const api = createApiClient(cfg, fakeFetch(404, { detail: "thread not found" }));
    const err = await api.get("/threads/{id}", { path: { id: "x" } }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(404);
    expect((err as ApiError).detail).toBe("thread not found");
  });

  it("reports a network failure as ApiError status 0", async () => {
    const api = createApiClient(cfg, async () => {
      throw new TypeError("Failed to fetch");
    });
    const err = await api.get("/system/status").catch((e: unknown) => e);
    expect((err as ApiError).status).toBe(0);
  });
});

describe("sidecar config", () => {
  it("prefers the injected window.__ETACH__", () => {
    expect(
      readSidecarConfig({
        __ETACH__: { baseUrl: "http://127.0.0.1:5000/", token: "t" },
        location: { hash: "#port=1&token=x" },
      }),
    ).toEqual({ baseUrl: "http://127.0.0.1:5000", token: "t" });
    expect(readSidecarConfig({ __ETACH__: { port: 5001, token: "t" }, location: { hash: "" } })).toEqual(
      { baseUrl: "http://127.0.0.1:5001", token: "t" },
    );
  });

  it("falls back to #port=…&token=…", () => {
    expect(readSidecarConfig({ location: { hash: "#port=8765&token=abc" } })).toEqual({
      baseUrl: "http://127.0.0.1:8765",
      token: "abc",
    });
  });

  it("rejects non-loopback hosts and missing parts", () => {
    expect(
      readSidecarConfig({ __ETACH__: { baseUrl: ["http:", "", "example.com"].join("/"), token: "t" }, location: { hash: "" } }),
    ).toBeNull();
    expect(readSidecarConfig({ location: { hash: "#port=1&token=a&host=evil.com" } })).toBeNull();
    expect(readSidecarConfig({ location: { hash: "#token=abc" } })).toBeNull();
    expect(readSidecarConfig({ location: { hash: "" } })).toBeNull();
  });
});
