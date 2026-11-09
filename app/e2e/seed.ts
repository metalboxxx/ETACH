/**
 * Seeding for the E2E specs through the replay sidecar's API only (no DB writes): an extracted S1
 * thread. Reuses one if an earlier spec (s1-run) left it, otherwise uploads the committed S1
 * stand-in PNGs (`POST /files?name=`), creates a thread, starts the extract run and waits for
 * its attempt.
 */
import { readFileSync } from "node:fs";
import { basename, join } from "node:path";
import { CASSETTES } from "./sidecar";

export interface SeededThread {
  threadId: string;
  testId: string;
  attemptId: string;
}

function base() {
  const port = process.env.ETACH_E2E_PORT;
  const token = process.env.ETACH_E2E_TOKEN;
  if (!port || !token) throw new Error("global setup did not start the sidecar");
  return { url: `http://127.0.0.1:${port}`, token };
}

/** A JSON call to the sidecar (throws on a non-2xx). */
export async function sidecarApi<T = unknown>(method: string, path: string, body?: unknown): Promise<T> {
  const { url, token } = base();
  const isBytes = body instanceof Uint8Array;
  const res = await fetch(url + path, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body === undefined ? {} : { "Content-Type": isBytes ? "application/octet-stream" : "application/json" }),
    },
    body: body === undefined ? undefined : isBytes ? new Blob([body as Uint8Array<ArrayBuffer>]) : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${method} ${path}: ${res.status} ${await res.text()}`);
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

interface ThreadDetail {
  thread: { id: string };
  attempt: { id: string; test_id: string } | null;
}

/** An S1 thread with an attempt: an existing one, or a new extract run (a few minutes in replay). */
export async function seedExtractedS1(timeoutMs = 240_000): Promise<SeededThread> {
  const rows = await sidecarApi<{ thread: { id: string }; kind: string }[]>("GET", "/threads");
  for (const row of rows.filter((r) => r.kind === "filled")) {
    const d = await sidecarApi<ThreadDetail>("GET", `/threads/${row.thread.id}`);
    if (d.attempt) return { threadId: d.thread.id, testId: d.attempt.test_id, attemptId: d.attempt.id };
  }

  return extractS1(timeoutMs);
}

/**
 * Uploads a scenario's stand-in pages (its `input.json`), creates a thread and starts an extract
 * run in it (`existingTestId`: the picked bank test, or null to save a new test).
 */
export async function startExtract(folder: string, existingTestId: string | null): Promise<{ threadId: string; runId: string }> {
  const manifest = JSON.parse(readFileSync(join(folder, "input.json"), "utf8")) as { pages: { stand_in: string }[] };
  const pages = [];
  for (const p of manifest.pages) {
    const file = join(folder, p.stand_in);
    const up = await sidecarApi<{ pages: { file_id: string; rotation: number; is_key: boolean; text_file_id: string | null }[] }>(
      "POST",
      `/files?name=${encodeURIComponent(basename(file))}`,
      new Uint8Array(readFileSync(file)) as Uint8Array<ArrayBuffer>,
    );
    pages.push(...up.pages);
  }
  const created = await sidecarApi<{ thread_id: string }>("POST", "/threads", { title: "" });
  const run = await sidecarApi<{ id: string }>("POST", `/threads/${created.thread_id}/runs`, {
    kind: "extract",
    input: { pages, existing_test_id: existingTestId, supersedes_attempt_id: null },
  });
  return { threadId: created.thread_id, runId: run.id };
}

/** Polls `GET /runs/{id}` until the run is `done`; throws on another final status or a time-out. */
export async function waitRunDone(runId: string, timeoutMs = 240_000): Promise<void> {
  const until = Date.now() + timeoutMs;
  let last: unknown = null;
  while (Date.now() < until) {
    const r = await sidecarApi<{ run: { status: string } }>("GET", `/runs/${runId}`);
    last = r.run;
    if (r.run.status === "done") return;
    if (["failed", "discarded", "stopped", "interrupted"].includes(r.run.status)) {
      throw new Error(`run ${runId} ended: ${JSON.stringify(r).slice(0, 2000)}`);
    }
    await new Promise((ok) => setTimeout(ok, 500));
  }
  throw new Error(`run ${runId} did not finish in time: ${JSON.stringify(last)}`);
}

/**
 * Step 22.6.4: every extraction queues a key run on its thread (kind grade, input.reason
 * after_extract). Waits until the thread has none queued, running or stopping, so a spec reads
 * results (unsure counts, toasts, keys) only after it has ended.
 */
export async function waitKeyRunSettled(threadId: string, timeoutMs = 120_000): Promise<void> {
  const until = Date.now() + timeoutMs;
  while (Date.now() < until) {
    const rows = await sidecarApi<{ run: { thread_id: string; kind: string; status: string; input: { reason?: string } | null } }[]>(
      "GET",
      "/runs/active",
    );
    const pending = rows.some(
      (r) =>
        r.run.thread_id === threadId &&
        r.run.kind === "grade" &&
        r.run.input?.reason === "after_extract" &&
        ["queued", "running", "stopping"].includes(r.run.status),
    );
    if (!pending) return;
    await new Promise((ok) => setTimeout(ok, 300));
  }
  throw new Error(`the key run of thread ${threadId} did not settle in time`);
}

/**
 * A new S1 extract run in a new thread, without a picked test (so it saves a new test), and its
 * attempt. Step 16 part B extracts S1 a second time this way to seed a merge (R16.5).
 */
export async function extractS1(timeoutMs = 240_000): Promise<SeededThread> {
  const manifest = JSON.parse(readFileSync(join(CASSETTES, "input.json"), "utf8")) as {
    pages: { stand_in: string }[];
  };
  const pages = [];
  for (const p of manifest.pages) {
    const file = join(CASSETTES, p.stand_in);
    const up = await sidecarApi<{ pages: { file_id: string; rotation: number; is_key: boolean; text_file_id: string | null }[] }>(
      "POST",
      `/files?name=${encodeURIComponent(basename(file))}`,
      new Uint8Array(readFileSync(file)) as Uint8Array<ArrayBuffer>,
    );
    pages.push(...up.pages);
  }
  const created = await sidecarApi<{ thread_id: string }>("POST", "/threads", { title: "" });
  const run = await sidecarApi<{ id: string }>("POST", `/threads/${created.thread_id}/runs`, {
    kind: "extract",
    input: { pages, existing_test_id: null, supersedes_attempt_id: null },
  });
  const until = Date.now() + timeoutMs;
  while (Date.now() < until) {
    // Read the run's status first, then the thread: a run that is final before the thread read
    // has already written its attempt, so a missing attempt then really means none was made.
    // (The other order raced: a run finishing between the two reads looked attempt-less.)
    const r = await sidecarApi<{ run: { status: string; error?: unknown } }>("GET", `/runs/${run.id}`);
    const final = ["failed", "discarded", "succeeded", "done", "stopped", "interrupted"].includes(r.run.status);
    const d = await sidecarApi<ThreadDetail>("GET", `/threads/${created.thread_id}`);
    if (d.attempt) return { threadId: created.thread_id, testId: d.attempt.test_id, attemptId: d.attempt.id };
    if (final) {
      throw new Error(`the seeded S1 extract run ended without an attempt: ${JSON.stringify(r.run)}`);
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  const last = await sidecarApi("GET", `/runs/${run.id}`);
  throw new Error(`the seeded S1 extract run did not finish in time: ${JSON.stringify(last).slice(0, 2000)}`);
}
