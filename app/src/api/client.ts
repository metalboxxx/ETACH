/**
 * Typed fetch wrappers over the generated OpenAPI types (`src/gen/openapi.ts`).
 *
 *   const api = createApiClient(config);
 *   const thread = await api.get("/threads/{id}", { path: { id } });   // -> ThreadDetail
 *   await api.post("/threads/{id}/runs", { path: { id }, body: input });
 *   const up = await api.uploadFile(blob, "page1.jpg");                // POST /files, raw bytes
 *   <img src={api.fileUrl(fileId)} />                                   // ?token= (no headers in <img>)
 *
 * Every request carries `Authorization: Bearer <token>`. The query token is used only for
 * `/files/{id}` URLs and `/events` (see sse.ts). A non-2xx response throws `ApiError`.
 */
import type { components, paths } from "@/gen/openapi";
import type { SidecarConfig } from "./config";

export type Schemas = components["schemas"];
export type HttpMethod = "get" | "post" | "put" | "patch" | "delete";

/** Paths that support method M. */
export type PathsFor<M extends HttpMethod> = {
  [P in keyof paths]: [NonNullable<paths[P][M]>] extends [never] ? never : P;
}[keyof paths];

export type Operation<P extends keyof paths, M extends HttpMethod> = NonNullable<paths[P][M]>;

type ParamsOf<O> = O extends { parameters: infer X } ? X : never;
type PathParams<O> = ParamsOf<O> extends { path: infer P } ? P : never;
type QueryParams<O> = ParamsOf<O> extends { query?: infer Q } ? Q : never;
type JsonBody<O> = O extends { requestBody?: { content: { "application/json": infer B } } } ? B : never;

/** The JSON body of the 2xx response (`undefined` for 204 / no content). */
export type ResponseOf<O> = O extends { responses: infer R }
  ? {
      [K in keyof R]: K extends 200 | 201 | 202 | 204
        ? R[K] extends { content: { "application/json": infer J } }
          ? J
          : undefined
        : never;
    }[keyof R]
  : never;

export type RequestOptions<O> = {
  query?: QueryParams<O>;
  body?: JsonBody<O>;
  signal?: AbortSignal;
} & ([PathParams<O>] extends [never] ? { path?: undefined } : { path: PathParams<O> });

export type RequestArgs<O> = [PathParams<O>] extends [never]
  ? [opts?: RequestOptions<O>]
  : [opts: RequestOptions<O>];

/** A non-2xx response (or a network failure: status 0). `detail` is FastAPI's `detail` field. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;
  constructor(status: number, detail: unknown, message?: string) {
    super(
      message ??
        `API error ${status}: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`,
    );
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function fillPath(template: string, params: Record<string, unknown> | undefined): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = params?.[key];
    if (value === undefined || value === null) {
      throw new Error(`missing path parameter "${key}" for ${template}`);
    }
    return encodeURIComponent(String(value));
  });
}

export function queryString(query: Record<string, unknown> | undefined): string {
  if (!query) return "";
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null) continue;
    if (Array.isArray(v)) v.forEach((item) => qs.append(k, String(item)));
    else qs.append(k, String(v));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

async function readError(res: Response): Promise<ApiError> {
  let detail: unknown = res.statusText;
  try {
    const text = await res.text();
    if (text) {
      try {
        const json: unknown = JSON.parse(text);
        detail =
          json && typeof json === "object" && "detail" in json
            ? (json as { detail: unknown }).detail
            : json;
      } catch {
        detail = text;
      }
    }
  } catch {
    /* keep statusText */
  }
  return new ApiError(res.status, detail);
}

const LINE_END = /\r?\n/;
const FRAME_END = /\r?\n\r?\n/;

/** One `models.pull_progress` frame of `POST /models/pull` (step 22.3.5). */
export interface PullEvent {
  model: string;
  /** Ollama's status ("pulling manifest", "downloading", …), then "success" or "error". */
  status: string;
  completed: number | null;
  total: number | null;
  /** With `status: "error"`: the reason in plain words. */
  message: string | null;
}

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

type LooseOptions = {
  path?: Record<string, unknown>;
  query?: Record<string, unknown>;
  body?: unknown;
  signal?: AbortSignal;
};

export function createApiClient(
  config: SidecarConfig,
  fetchImpl: FetchLike = (input, init) => fetch(input, init),
) {
  const base = config.baseUrl.replace(/\/+$/, "");

  async function send<T>(
    method: HttpMethod,
    url: string,
    body: BodyInit | undefined,
    contentType: string | undefined,
    signal?: AbortSignal,
  ): Promise<T> {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${config.token}`,
      Accept: "application/json",
    };
    if (contentType) headers["Content-Type"] = contentType;
    let res: Response;
    try {
      res = await fetchImpl(url, { method: method.toUpperCase(), headers, body, signal });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") throw err;
      throw new ApiError(0, String(err), `sidecar unreachable: ${String(err)}`);
    }
    if (!res.ok) throw await readError(res);
    if (res.status === 204) return undefined as T;
    const text = await res.text();
    return (text ? JSON.parse(text) : undefined) as T;
  }

  function request<M extends HttpMethod, P extends PathsFor<M>>(
    method: M,
    path: P,
    ...args: RequestArgs<Operation<P, M>>
  ): Promise<ResponseOf<Operation<P, M>>> {
    const o = (args[0] ?? {}) as LooseOptions;
    const url = base + fillPath(path, o.path) + queryString(o.query);
    const hasBody = o.body !== undefined;
    return send(
      method,
      url,
      hasBody ? JSON.stringify(o.body) : undefined,
      hasBody ? "application/json" : undefined,
      o.signal,
    );
  }

  return {
    config,
    request,
    get: <P extends PathsFor<"get">>(path: P, ...args: RequestArgs<Operation<P, "get">>) =>
      request("get", path, ...args),
    post: <P extends PathsFor<"post">>(path: P, ...args: RequestArgs<Operation<P, "post">>) =>
      request("post", path, ...args),
    put: <P extends PathsFor<"put">>(path: P, ...args: RequestArgs<Operation<P, "put">>) =>
      request("put", path, ...args),
    patch: <P extends PathsFor<"patch">>(path: P, ...args: RequestArgs<Operation<P, "patch">>) =>
      request("patch", path, ...args),
    delete: <P extends PathsFor<"delete">>(path: P, ...args: RequestArgs<Operation<P, "delete">>) =>
      request("delete", path, ...args),

    /** `POST /files?name=…` with the raw bytes (not multipart, structure.md §7). */
    uploadFile(
      data: Blob | ArrayBuffer | Uint8Array,
      name: string,
      signal?: AbortSignal,
    ): Promise<Schemas["UploadResult"]> {
      return send(
        "post",
        `${base}/files${queryString({ name })}`,
        data as BodyInit,
        "application/octet-stream",
        signal,
      );
    },

    /** An `<img src>`-ready URL for a stored file: the only REST URL that carries `?token=`. */
    fileUrl(id: string, opts: { thumb?: boolean } = {}): string {
      const query = { token: config.token, thumb: opts.thumb ? 1 : undefined };
      return `${base}/files/${encodeURIComponent(id)}${queryString(query)}`;
    },

    /**
     * A stored file's type and, for a text file, its text (`GET /files/{id}`). The photo viewer
     * uses it when a page has no image: a text-only page (DOCX or PDF text) stores its text file
     * as the page (step 22.1.4). `text` is `null` for any other type.
     */
    async fileText(id: string, signal?: AbortSignal): Promise<{ mime: string; text: string | null }> {
      const res = await fetchImpl(`${base}/files/${encodeURIComponent(id)}`, {
        headers: { Authorization: `Bearer ${config.token}` },
        signal,
      });
      if (!res.ok) throw await readError(res);
      const mime = res.headers.get("content-type") ?? "";
      return { mime, text: mime.startsWith("text/") ? await res.text() : null };
    },

    /**
     * `POST /models/pull {name}` (step 22.3.5): the response is the progress stream itself
     * (`text/event-stream`, `models.pull_progress` frames). Each event goes to `onEvent`; the
     * promise resolves with the last one. Aborting `signal` closes the request, which is the
     * Cancel: the sidecar stops Ollama's download.
     */
    async pullModel(
      name: string,
      onEvent: (e: PullEvent) => void,
      signal?: AbortSignal,
    ): Promise<PullEvent | null> {
      let res: Response;
      try {
        res = await fetchImpl(`${base}/models/pull`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${config.token}`,
            Accept: "text/event-stream",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ name }),
          signal,
        });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") throw err;
        throw new ApiError(0, String(err), `sidecar unreachable: ${String(err)}`);
      }
      if (!res.ok) throw await readError(res);
      let last: PullEvent | null = null;
      const take = (frame: string) => {
        for (const line of frame.split(LINE_END)) {
          if (!line.startsWith("data:")) continue;
          try {
            last = JSON.parse(line.slice(5).trim()) as PullEvent;
            onEvent(last);
          } catch {
            /* not JSON: skip */
          }
        }
      };
      if (!res.body) {
        (await res.text()).split(FRAME_END).forEach(take);
        return last;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split(FRAME_END);
        buffer = frames.pop() ?? "";
        frames.forEach(take);
      }
      if (buffer.trim()) take(buffer);
      return last;
    },

    /** The SSE URL (query token; `last_event_id` resumes after a drop). Used by sse.ts. */
    eventsUrl(lastEventId?: string | null): string {
      return `${base}/events${queryString({ token: config.token, last_event_id: lastEventId ?? undefined })}`;
    },
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
