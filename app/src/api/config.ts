/**
 * Where the sidecar is and how to authenticate (llm-design §2: every route needs
 * `Authorization: Bearer <token>`; the server binds to 127.0.0.1 only).
 *
 * Two sources, first match wins:
 *  1. `window.__ETACH__ = { baseUrl, token }` (or `{ port, token }`), injected by the Tauri shell
 *     (step 14) before the page scripts run.
 *  2. The URL hash `#port=<port>&token=<token>` (optionally `&host=localhost`), for `npm run dev`
 *     and the E2E tests against `uv run etach serve`, e.g. `http://127.0.0.1:5173/#port=8765&token=abc`.
 *
 * Only loopback hosts are accepted (the built app makes no non-local requests, PRD §11).
 */
export interface SidecarConfig {
  /** e.g. `http://127.0.0.1:8765`, no trailing slash. */
  baseUrl: string;
  token: string;
}

export interface InjectedConfig {
  baseUrl?: string;
  port?: number | string;
  token: string;
}

declare global {
  interface Window {
    __ETACH__?: InjectedConfig;
  }
}

const LOOPBACK = new Set(["127.0.0.1", "localhost", "[::1]"]);

function loopbackOrigin(raw: string): string | null {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return null;
  }
  if (url.protocol !== "http:" || !LOOPBACK.has(url.hostname)) return null;
  return url.origin;
}

function fromParts(host: string, port: string | number | null | undefined): string | null {
  if (port === undefined || port === null || !/^\d{1,5}$/.test(String(port))) return null;
  return loopbackOrigin("http://" + host + ":" + String(port));
}

export type ConfigSource = Pick<Window, "__ETACH__"> & { location: Pick<Location, "hash"> };

export function readSidecarConfig(win: ConfigSource = window): SidecarConfig | null {
  const injected = win.__ETACH__;
  if (injected?.token) {
    const baseUrl = injected.baseUrl
      ? loopbackOrigin(injected.baseUrl)
      : fromParts("127.0.0.1", injected.port);
    if (baseUrl) return { baseUrl, token: injected.token };
  }
  const hash = win.location.hash.replace(/^#/, "");
  if (hash) {
    const params = new URLSearchParams(hash);
    const token = params.get("token");
    const baseUrl = fromParts(params.get("host") ?? "127.0.0.1", params.get("port"));
    if (token && baseUrl) return { baseUrl, token };
  }
  return null;
}
