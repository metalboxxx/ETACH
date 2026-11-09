/**
 * First-run setup (plan step 21, PRD §13 Phase 4), driven by `GET /system/status`:
 *
 * - `unreachable` → Ollama is missing or not running: where to install it, then restart the app;
 * - `too_old` → the installed Ollama is older than 0.12.11: update it;
 * - `missing_model` → the configured models are not pulled: **Download models**
 *   (`POST /settings/models/pull`, progress from SSE `models.pull_progress`).
 *
 * The screen replaces the app until the status is `ok`, or the teacher chooses "Continue
 * anyway" (the test bank and reports stay usable without Ollama). It never shows in replay mode
 * (`etach serve --replay`: cassettes stand in for Ollama). While it shows, the status is polled.
 *
 * The download page opens in the teacher's browser through the shell (`open_ollama_download`);
 * the app itself requests nothing outside 127.0.0.1 (PRD §11), so the address is shown as text.
 */
import { useEffect, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { type ApiClient } from "@/api/client";
import { useEvents, type EtachEvent } from "@/api/sse";
import { pullLabel, type PullState } from "@/features/settings/SettingsPanel";
import type { SystemStatus } from "@/hooks/useSystemStatus";
import { errorText } from "@/lib/errors";

/** Shown without a scheme: the offline guard (`check:urls`) allows no external URL in `src/`. */
export const OLLAMA_DOWNLOAD = "ollama.com/download";
export const MIN_OLLAMA = "0.12.11";
/** sessionStorage: "Continue anyway" was chosen (kept for the session; a sidecar restart reloads). */
export const SETUP_SKIPPED_KEY = "etach.firstRunSkipped";
/** How often the status is re-read while the setup screen shows. */
export const POLL_MS = 3_000;

export type SetupNeed = "install" | "update" | "models";

/** What the setup screen must ask for; `null` = nothing (ready, replay, or not loaded yet). */
export function setupNeed(status: SystemStatus | null): SetupNeed | null {
  if (!status || status.replay) return null;
  switch (status.ollama_status) {
    case "unreachable":
      return "install";
    case "too_old":
      return "update";
    case "missing_model":
      return "models";
    default:
      return null;
  }
}

async function openDownloadPage(): Promise<boolean> {
  if (!isTauri()) return false;
  try {
    await invoke("open_ollama_download");
    return true;
  } catch {
    return false;
  }
}

const button = "rounded-button border border-border px-3 py-1.5 hover:bg-hover disabled:opacity-50";
const primary = "rounded-button bg-accent px-3 py-1.5 text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover disabled:opacity-50";

function DownloadLink({ label }: { label: string }) {
  const [opened, setOpened] = useState<boolean | null>(null);
  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        data-testid="ollama-download-link"
        className={primary + " self-start"}
        onClick={() => void openDownloadPage().then(setOpened)}
      >
        {label}
      </button>
      <p className="text-muted">
        Download page: <span data-testid="ollama-download-address" className="text-text">{OLLAMA_DOWNLOAD}</span>
        {opened === false && " (open it in your browser)"}
      </p>
    </div>
  );
}

export interface FirstRunScreenProps {
  api: ApiClient;
  status: SystemStatus;
  /** Re-read `GET /system/status`. */
  onReload: () => void;
  /** "Continue anyway": hide the screen for this session. */
  onContinue: () => void;
}

export function FirstRunScreen({ api, status, onReload, onContinue }: FirstRunScreenProps) {
  const need = setupNeed(status);
  const [pulls, setPulls] = useState<Record<string, PullState> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const id = window.setInterval(onReload, POLL_MS);
    return () => window.clearInterval(id);
  }, [onReload]);

  useEvents((e: EtachEvent) => {
    const model = typeof e.data.model === "string" ? e.data.model : null;
    if (!model) return;
    const next: PullState = {
      status: String(e.data.status ?? ""),
      completed: typeof e.data.completed === "number" ? e.data.completed : null,
      total: typeof e.data.total === "number" ? e.data.total : null,
    };
    setPulls((prev) => ({ ...(prev ?? {}), [model]: next }));
    if (next.status === "success") onReload();
  }, ["models.pull_progress"]);

  const pulling = pulls !== null && Object.values(pulls).some((p) => p.status !== "success" && !p.status.startsWith("error"));

  const download = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post("/settings/models/pull", {});
      setPulls((prev) =>
        Object.fromEntries(
          res.models.map((m) => {
            const p = prev?.[m];
            const live = p && p.status !== "success" && !p.status.startsWith("error");
            return [m, live ? p : { status: "waiting", completed: null, total: null }];
          }),
        ),
      );
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main
      data-testid="first-run"
      data-need={need ?? "none"}
      className="flex h-full items-center justify-center bg-bg font-sans text-sm text-text"
    >
      <div className="flex w-[34rem] max-w-full flex-col gap-4 rounded-paper border border-border bg-surface p-6">
        <h1 className="font-serif text-xl">Set up ETACH</h1>

        {need === "install" && (
          <section data-testid="first-run-install" className="flex flex-col gap-3">
            <p data-testid="first-run-message">
              Ollama is not installed or not running. The app reads the photos with Ollama, on this
              laptop. Install Ollama ({MIN_OLLAMA} or newer), then close and reopen this app.
            </p>
            <DownloadLink label="Install Ollama" />
          </section>
        )}

        {need === "update" && (
          <section data-testid="first-run-update" className="flex flex-col gap-3">
            <p data-testid="first-run-message">
              Ollama {status.ollama_version ?? ""} is too old. Please update Ollama to {MIN_OLLAMA} or newer,
              then close and reopen this app.
            </p>
            <DownloadLink label="Update Ollama" />
          </section>
        )}

        {need === "models" && (
          <section data-testid="first-run-models" className="flex flex-col gap-3">
            <p data-testid="first-run-message">
              Ollama is ready, but these models are not downloaded yet:{" "}
              <span data-testid="first-run-missing" className="text-text">
                {status.missing_models?.join(", ") || "unknown"}
              </span>
              . The download is large and needs the internet once; afterwards the app works offline.
            </p>
            <button
              type="button"
              data-testid="first-run-pull"
              disabled={busy || pulling}
              onClick={() => void download()}
              className={primary + " self-start"}
            >
              Download models
            </button>
            {pulls && (
              <ul data-testid="first-run-pull-list" className="flex flex-col gap-1">
                {Object.entries(pulls).map(([model, p]) => (
                  <li key={model} data-testid="first-run-pull-row" data-model={model} data-status={p.status} className="flex flex-col gap-0.5">
                    <div className="flex gap-2">
                      <span className="flex-1">{model}</span>
                      <span className={p.status.startsWith("error") ? "text-danger" : "text-muted"}>{pullLabel(p)}</span>
                    </div>
                    {p.total ? <progress className="h-1 w-full" max={p.total} value={p.completed ?? 0} /> : null}
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {error && (
          <p role="alert" className="text-danger">
            {error}
          </p>
        )}

        <div className="flex gap-2 border-t border-border pt-4">
          <button type="button" data-testid="first-run-recheck" className={button} onClick={onReload}>
            Check again
          </button>
          <button type="button" data-testid="first-run-continue" className={button} onClick={onContinue}>
            Continue anyway
          </button>
        </div>
      </div>
    </main>
  );
}
