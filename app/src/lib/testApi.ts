/**
 * A test double for the sidecar: `createApiClient` over a routing fake `fetch`.
 *
 *   const fake = fakeApi({ "GET /threads": [...], "POST /files": (req) => ({...}) });
 *   fake.calls  // [{ method, path, query, body }]
 */
import { createApiClient } from "@/api/client";

export interface FakeCall {
  method: string;
  path: string;
  query: URLSearchParams;
  body: unknown;
}

export type FakeRoute = unknown | ((call: FakeCall) => unknown);

/** A route value that answers with a status (e.g. 409) instead of 200. */
export class FakeStatus {
  constructor(
    readonly status: number,
    readonly body: unknown = { detail: "error" },
  ) {}
}

export function fakeApi(routes: Record<string, FakeRoute>) {
  const calls: FakeCall[] = [];
  const fetchImpl = async (input: string, init?: RequestInit) => {
    const url = new URL(input);
    const method = (init?.method ?? "GET").toUpperCase();
    let body: unknown = init?.body;
    if (typeof body === "string") body = JSON.parse(body);
    const call: FakeCall = { method, path: url.pathname, query: url.searchParams, body };
    calls.push(call);
    const key = Object.keys(routes).find((k) => {
      const [m, p] = k.split(" ");
      if (m !== method || !p) return false;
      const re = new RegExp("^" + p.replace(/\{\w+\}/g, "[^/]+") + "$");
      return re.test(url.pathname);
    });
    if (!key) return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    const route = routes[key];
    const value = typeof route === "function" ? (route as (c: FakeCall) => unknown)(call) : route;
    if (value instanceof FakeStatus) return new Response(JSON.stringify(value.body), { status: value.status });
    return new Response(JSON.stringify(value), { status: 200 });
  };
  const api = createApiClient({ baseUrl: "http://127.0.0.1:9", token: "t" }, fetchImpl);
  return { api, calls };
}
