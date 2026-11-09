/**
 * The running indicator's state (PRD D22, D23, §10.1; llm-design §2 "Run progress").
 *
 * Seeded from `GET /runs/active` (running, queued, stopped and interrupted runs with their stage
 * and percent, so a reload or a restart shows them again) and kept current by SSE:
 * `run.step_started` / `run.progress` carry `stage`, `stages`, `stage_label` and `percent`; a
 * `run.progress` with `done`/`total`/`unit` is the count inside the stage ("page 2 of 4"), and
 * one with `tokens` means the model is still writing. Every other run event reloads the list.
 * Node names are never kept or shown. `GET /system/status` gives `power_source` ("on battery"),
 * reloaded on `system.changed` and whenever a run starts.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ApiClient, Schemas } from "@/api/client";
import { useEvents, type EtachEvent, type EtachEventData, type EtachEventType } from "@/api/sse";
import { isKeyRun } from "./keyRun";

export type ActiveRun = Schemas["ActiveRun"];
export type RunStatus = Schemas["Run"]["status"];

/** Where a run is, in plain words (no node names). */
export interface RunProgress {
  stage: number | null;
  stages: number | null;
  stageLabel: string | null;
  /** 0–100; never goes down for a run. */
  percent: number | null;
  /** The count inside the stage: "page" 2 of 4. Cleared when the stage changes. */
  unit: string | null;
  done: number | null;
  total: number | null;
  /** The item being worked on, 1-based ("page 3 of 4"; llm-design §2 v4.24). */
  current: number | null;
  /** A second pass over `current` ("Checking page 2 again"). */
  again: boolean;
  /** When (ms) the last `tokens` event arrived: the model is writing. */
  writingAt: number | null;
}

export interface RunEntry {
  run: Schemas["Run"];
  progress: RunProgress;
  /** The start of the elapsed time (ms): the run's `started_at`, else when it was first seen. */
  since: number;
}

export const EMPTY_PROGRESS: RunProgress = {
  stage: null,
  stages: null,
  stageLabel: null,
  percent: null,
  unit: null,
  done: null,
  total: null,
  current: null,
  again: false,
  writingAt: null,
};

const RELOAD_EVENTS: readonly EtachEventType[] = [
  "run.queued",
  "run.step_done",
  "run.done",
  "run.failed",
  "run.stopped",
  "run.interrupted",
  "run.discarded",
];
const PROGRESS_EVENTS: readonly EtachEventType[] = ["run.step_started", "run.progress"];

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);

/** The higher of two percents (a run's percent never goes down). */
function maxPercent(a: number | null, b: number | null): number | null {
  if (a === null) return b;
  if (b === null) return a;
  return Math.max(a, b);
}

/** Stage fields from an event or an active-run row; a stage change clears the count. */
function withStage(
  prev: RunProgress,
  stage: number | null,
  stages: number | null,
  label: string | null,
  percent: number | null,
): RunProgress {
  if (stage === null || label === null) return { ...prev, percent: maxPercent(prev.percent, percent) };
  // An earlier stage than the one shown (a late event) keeps what is shown.
  if (prev.stage !== null && stage < prev.stage) return { ...prev, percent: maxPercent(prev.percent, percent) };
  const sameStage = prev.stage === stage;
  return {
    ...prev,
    stage,
    stages,
    stageLabel: label,
    percent: maxPercent(prev.percent, percent),
    unit: sameStage ? prev.unit : null,
    done: sameStage ? prev.done : null,
    total: sameStage ? prev.total : null,
    current: sameStage ? prev.current : null,
    again: sameStage ? prev.again : false,
  };
}

/** The progress after one `run.step_started` / `run.progress` event. */
export function applyProgressEvent(prev: RunProgress, data: EtachEventData, now: number): RunProgress {
  let next = withStage(prev, num(data.stage), num(data.stages), str(data.stage_label), num(data.percent));
  if (data.type !== "run.progress") return next;
  if (num(data.tokens) !== null) next = { ...next, writingAt: now };
  const done = num(data.done);
  const total = num(data.total);
  if (done !== null && total !== null && total > 0 && next.stage !== null) {
    // v4.24: `current` names the item being worked on; an older sidecar sends only `done`.
    const current = num(data.current) ?? done;
    next = { ...next, done, total, current, again: data.again === true, unit: str(data.unit) };
  }
  return next;
}

/** The progress from a `GET /runs/active` row, keeping what SSE already gave for that stage. */
export function progressFromActive(row: ActiveRun, prev: RunProgress | undefined): RunProgress {
  return withStage(
    prev ?? EMPTY_PROGRESS,
    row.stage ?? null,
    row.stages ?? null,
    row.stage_label ?? null,
    row.percent ?? null,
  );
}

/**
 * "Reading the test · page 3 of 4" (the page being read), "Reading the test · Checking page 2
 * again" for a second pass, or the stage alone; null before the first stage.
 */
export function progressText(p: RunProgress): string | null {
  if (!p.stageLabel) return null;
  const current = p.current ?? p.done;
  if (p.unit && current !== null && p.again) return `${p.stageLabel} · Checking ${p.unit} ${current} again`;
  if (p.unit && current !== null && p.total !== null) return `${p.stageLabel} · ${p.unit} ${current} of ${p.total}`;
  return p.stageLabel;
}

function startOf(run: Schemas["Run"], prev: RunEntry | undefined): number {
  const t = run.started_at ? Date.parse(run.started_at) : NaN;
  if (Number.isFinite(t)) return t;
  return prev?.since ?? Date.now();
}

/** Statuses that keep a run in the indicator. */
const LIVE: ReadonlySet<RunStatus> = new Set(["queued", "running", "stopping", "stopped", "interrupted"]);

export function useRunning(api: ApiClient) {
  const [runs, setRuns] = useState<RunEntry[]>([]);
  const runsRef = useRef(runs);
  useEffect(() => {
    runsRef.current = runs;
  }, [runs]);
  const [power, setPower] = useState<Schemas["SystemStatus"]["power_source"] | null>(null);

  const reload = useCallback(() => {
    api
      .get("/runs/active")
      .then((rows) => {
        const list = Array.isArray(rows) ? rows : [];
        setRuns((prev) =>
          list
            .filter((r) => LIVE.has(r.run.status))
            .map((r) => {
              const before = prev.find((p) => p.run.id === r.run.id);
              return { run: r.run, progress: progressFromActive(r, before?.progress), since: startOf(r.run, before) };
            }),
        );
      })
      .catch(() => {
        /* offline: keep what is shown */
      });
  }, [api]);

  const reloadPower = useCallback(() => {
    api
      .get("/system/status")
      .then((s) => setPower(s.power_source))
      .catch(() => setPower(null));
  }, [api]);

  useEffect(() => {
    reload();
    reloadPower();
  }, [reload, reloadPower]);

  useEvents(() => reload(), RELOAD_EVENTS);
  useEvents(() => reloadPower(), ["system.changed", "run.queued"]);
  useEvents((e: EtachEvent) => {
    const runId = e.data.run_id;
    if (!runId) return;
    if (!runsRef.current.some((r) => r.run.id === runId)) {
      reload();
      return;
    }
    const now = Date.now();
    setRuns((prev) =>
      prev.map((r) =>
        r.run.id !== runId
          ? r
          : {
              ...r,
              run: { ...r.run, status: r.run.status === "queued" ? "running" : r.run.status },
              progress: applyProgressEvent(r.progress, e.data, now),
            },
      ),
    );
  }, PROGRESS_EVENTS);

  const act = useCallback(
    async (action: "stop" | "resume" | "discard", runId: string) => {
      const path = `/runs/{id}/${action}` as const;
      try {
        await api.post(path, { path: { id: runId } });
      } finally {
        reload();
      }
    },
    [api, reload],
  );

  // A stopped or interrupted key run (step 22.6.4) does not hold the thread: Grade makes the key.
  const activeThreadIds = useMemo(
    () =>
      new Set(
        runs
          .filter((r) => !(isKeyRun(r.run) && (r.run.status === "stopped" || r.run.status === "interrupted")))
          .map((r) => r.run.thread_id),
      ),
    [runs],
  );

  // Threads whose actions wait (Extract again, Grade): every active run except the key run, which
  // Extract again and the deletes cancel (step 22.6.4, D12, D14) and Grade waits for on its own.
  const busyThreadIds = useMemo(() => new Set(runs.filter((r) => !isKeyRun(r.run)).map((r) => r.run.thread_id)), [runs]);

  return { runs, power, activeThreadIds, busyThreadIds, reload, act };
}
