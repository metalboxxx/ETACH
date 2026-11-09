/**
 * The Settings panel (PRD §10.2, step 20): the model tag per role (`PUT /settings` →
 * `models.toml`), the log retention (`log_retention_days`), "clear logs older than N days",
 * backup / restore into a new folder, the Ollama status and version, the other-Ollama warning
 * (R20.4) and **Download models** with per-model progress from SSE `models.pull_progress` (R20.5).
 * Step 22.3.5: each role's model is a combobox over the installed models, and the model manager
 * lists, downloads (progress, Cancel) and deletes the app's Ollama models (`/models`).
 * Step 21: the app (sidecar) version from `/system/status`, equal to `etach --version` (R21.2).
 *
 * Step 22.4.2: the panel is split into tabs: General, Models (the role choices and the model
 * manager), Occasions and Schools. Every tab stays mounted (hidden), so switching keeps what was
 * typed; the chosen tab is kept while the app runs. Arrow keys, Home and End move along the tabs,
 * Enter or Space opens one, as the workspace tabs (step 22.4.1).
 *
 * Step 22.5.2 (comment 3): the tabs are General · Models · Test attributes. Test attributes shows
 * a menu of Occasions · Schools · Series (`TestAttributes.tsx`); each opens its list in the same
 * place, with Back to the menu.
 *
 * The data folder is shown read-only: there is no "move data folder" option (PRD v4.4, §11).
 */
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { type ApiClient, type Schemas } from "@/api/client";
import { useEvents, type EtachEvent } from "@/api/sse";
import { OtherOllamaWarning } from "@/components/OtherOllamaWarning";
import type { SystemStatus } from "@/hooks/useSystemStatus";
import { errorText } from "@/lib/errors";
import { ModelCombobox } from "./ModelCombobox";
import { ModelManager, useModelPulls } from "./ModelManager";
import { DEFAULT_MODEL, orderedRoles, ROLE_INFO, roleLabel } from "./roles";
import { HoverTip } from "@/components/HoverTip";
import { TestAttributes } from "./TestAttributes";

type Settings = Schemas["Settings"];

/** One model's download state, from `models.pull_progress {model, status, completed, total}`. */
export interface PullState {
  status: string;
  completed: number | null;
  total: number | null;
}

/** "ready" after `success`; "failed: …" after `error: …`; otherwise the status and a percentage. */
export function pullLabel(p: PullState): string {
  if (p.status === "success") return "ready";
  if (p.status.startsWith("error")) return "failed: " + p.status.replace(/^error:\s*/, "");
  if (p.total) return `${p.status} ${Math.floor(((p.completed ?? 0) / p.total) * 100)}%`;
  return p.status;
}

const OLLAMA_LABEL: Record<SystemStatus["ollama_status"], string> = {
  ok: "running",
  too_old: "too old (update to 0.12.11 or newer)",
  missing_model: "running, models missing",
  unreachable: "not reachable",
};

const errText = (err: unknown) => (errorText(err));
const button = "rounded-button border border-border px-3 py-1 hover:bg-hover disabled:opacity-50";
const input = "rounded-paper border border-input bg-surface px-2 py-1";

function Section({ title, testId, children }: { title: string; testId: string; children: ReactNode }) {
  return (
    <section data-testid={testId} className="flex flex-col gap-2 border-b border-border pb-4">
      <h3 className="font-serif text-base text-text">{title}</h3>
      {children}
    </section>
  );
}

export type SettingsTab = "general" | "models" | "attributes";

export const SETTINGS_TABS: readonly { id: SettingsTab; label: string }[] = [
  { id: "general", label: "General" },
  { id: "models", label: "Models" },
  { id: "attributes", label: "Test attributes" },
];

/** The tab chosen last; kept while the app runs (not saved). */
let lastTab: SettingsTab = "general";

function rememberTab(t: SettingsTab): void {
  lastTab = t;
}

/** Back to General (tests). */
export function resetSettingsTab(): void {
  rememberTab("general");
}

export interface SettingsPanelProps {
  api: ApiClient;
  /** `GET /system/status` (shared with the sidebar); `null` = not loaded. */
  status: SystemStatus | null;
  /** Reload the status (after a download finishes). */
  onStatusReload?: () => void;
}

export function SettingsPanel({ api, status, onStatusReload }: SettingsPanelProps) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [tags, setTags] = useState<Record<string, string>>({});
  const [retention, setRetention] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clearDays, setClearDays] = useState("45");
  const [cleared, setCleared] = useState<number | null>(null);
  const [backupPath, setBackupPath] = useState<string | null>(null);
  const [restoreFrom, setRestoreFrom] = useState("");
  const [restoreTo, setRestoreTo] = useState("");
  const [restored, setRestored] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [pulls, setPulls] = useState<Record<string, PullState> | null>(null);
  const [inventory, setInventory] = useState<Schemas["ModelInventory"] | null>(null);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [tab, setTab] = useState<SettingsTab>(lastTab);
  const ids = useId();
  const tabList = useRef<HTMLDivElement>(null);
  const chooseTab = (t: SettingsTab) => {
    rememberTab(t);
    setTab(t);
  };
  /** Arrow keys, Home and End move focus along the tabs; Enter or Space opens one. */
  const onTabKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const all = Array.from(tabList.current?.querySelectorAll<HTMLElement>('[role="tab"]') ?? []);
    const at = all.indexOf(document.activeElement as HTMLElement);
    if (at < 0) return;
    const next =
      e.key === "ArrowRight" ? (at + 1) % all.length
      : e.key === "ArrowLeft" ? (at - 1 + all.length) % all.length
      : e.key === "Home" ? 0
      : e.key === "End" ? all.length - 1
      : -1;
    if (next < 0) return;
    e.preventDefault();
    all[next]?.focus();
  };

  const loadModels = useCallback(() => {
    api
      .get("/models")
      .then((inv) => {
        setInventory(inv);
        setModelsError(null);
      })
      .catch((err: unknown) => {
        setInventory(null);
        setModelsError(errText(err));
      });
  }, [api]);
  useEffect(loadModels, [loadModels]);
  const onPullFinished = useCallback(() => {
    loadModels();
    onStatusReload?.();
  }, [loadModels, onStatusReload]);
  const modelPulls = useModelPulls(api, onPullFinished);

  const apply = useCallback((s: Settings) => {
    setSettings(s);
    // A setup saved before a role existed shows the default model for it (step 22.5.4b).
    setTags(Object.fromEntries(orderedRoles(Object.keys(s.roles)).map((role) => [role, s.roles[role]?.model ?? DEFAULT_MODEL])));
    setRetention(String(s.log_retention_days));
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    api
      .get("/settings", { signal: ctrl.signal })
      .then(apply)
      .catch((err: unknown) => {
        if (!ctrl.signal.aborted) setError(errText(err));
      });
    return () => ctrl.abort();
  }, [api, apply]);

  useEvents((e: EtachEvent) => {
    const model = typeof e.data.model === "string" ? e.data.model : null;
    if (!model) return;
    const next: PullState = {
      status: String(e.data.status ?? ""),
      completed: typeof e.data.completed === "number" ? e.data.completed : null,
      total: typeof e.data.total === "number" ? e.data.total : null,
    };
    setPulls((prev) => ({ ...(prev ?? {}), [model]: next }));
    if (next.status === "success") onStatusReload?.();
  }, ["models.pull_progress"]);

  const act = async (name: string, fn: () => Promise<void>) => {
    setBusy(name);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(null);
    }
  };

  const save = () =>
    act("save", async () => {
      if (!settings) return;
      // Every role is written on save, so a setup without the newer roles gets them stored.
      const roles: Record<string, Schemas["RoleUpdate"]> = {};
      for (const role of orderedRoles(Object.keys(settings.roles))) {
        const tag = (tags[role] ?? "").trim() || (settings.roles[role]?.model ?? DEFAULT_MODEL);
        roles[role] = { model: tag };
      }
      const days = Number(retention);
      const body: Schemas["SettingsUpdate"] = {};
      if (Object.keys(roles).length) body.roles = roles;
      if (Number.isInteger(days) && days > 0 && days !== settings.log_retention_days) body.log_retention_days = days;
      apply(await api.put("/settings", { body }));
      setSaved(true);
    });

  if (!settings) {
    return (
      <div data-testid="settings-panel" className="flex flex-col gap-3">
        {status?.other_ollama_loaded && <OtherOllamaWarning testId="settings-ollama-warning" />}
        {error ? <p role="alert" className="text-danger">{error}</p> : <p className="text-muted">Loading…</p>}
      </div>
    );
  }

  const dirty =
    orderedRoles(Object.keys(settings.roles)).some(
      (role) => (tags[role] ?? "").trim() !== (settings.roles[role]?.model ?? DEFAULT_MODEL),
    ) ||
    retention !== String(settings.log_retention_days);
  const pulling = pulls !== null && Object.values(pulls).some((p) => p.status !== "success" && !p.status.startsWith("error"));

  return (
    <div data-testid="settings-panel" className="flex flex-col gap-4 text-sm">
      {status?.other_ollama_loaded && <OtherOllamaWarning testId="settings-ollama-warning" />}
      {error && <p role="alert" className="text-danger">{error}</p>}

      <div
        ref={tabList}
        role="tablist"
        aria-label="Settings"
        data-testid="settings-tabs"
        onKeyDown={onTabKey}
        className="flex flex-wrap gap-1"
      >
        {SETTINGS_TABS.map((t) => {
          const selected = t.id === tab;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              id={`${ids}-tab-${t.id}`}
              data-testid="settings-tab"
              data-tab={t.id}
              aria-selected={selected}
              aria-controls={`${ids}-panel-${t.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => chooseTab(t.id)}
              className={
                "min-h-8 rounded-button border px-3 text-sm transition-colors motion-reduce:transition-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus " +
                (selected
                  ? "border-accent-strong bg-accent font-medium text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover"
                  : "border-input bg-surface text-text hover:bg-hover")
              }
            >
              {t.label}
            </button>
          );
        })}
      </div>
      <div
        role="tabpanel"
        id={`${ids}-panel-general`}
        aria-labelledby={`${ids}-tab-general`}
        data-testid="settings-tabpanel-general"
        hidden={tab !== "general"}
        className="flex flex-col gap-4"
      >
        <Section title="Ollama" testId="settings-ollama">
          {status ? (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
              <dt className="text-muted">App version</dt>
              <dd data-testid="sidecar-version">{status.sidecar_version}</dd>
              <dt className="text-muted">Status</dt>
              <dd data-testid="ollama-status" data-status={status.ollama_status}>
                {OLLAMA_LABEL[status.ollama_status]}
              </dd>
              <dt className="text-muted">Version</dt>
              <dd data-testid="ollama-version">{status.ollama_version ?? "unknown"}</dd>
              <dt className="text-muted">Models present</dt>
              <dd data-testid="models-present">{status.models_present?.join(", ") || "none"}</dd>
              <dt className="text-muted">Models missing</dt>
              <dd data-testid="models-missing" className={status.missing_models?.length ? "text-danger" : ""}>
                {status.missing_models?.join(", ") || "none"}
              </dd>
            </dl>
          ) : (
            <p className="text-muted">Status not available.</p>
          )}
        </Section>

        <Section title="Logs" testId="settings-logs">
          <div className="flex items-center gap-2">
            <span>Clear model-call logs older than</span>
            <input
              data-testid="clear-days"
              aria-label="Clear logs older than (days)"
              type="number"
              min={0}
              value={clearDays}
              onChange={(e) => setClearDays(e.target.value)}
              className={input + " w-20"}
            />
            <span>days</span>
            <button
              type="button"
              data-testid="clear-logs"
              disabled={busy !== null || !/^\d+$/.test(clearDays)}
              onClick={() =>
                void act("clear", async () => {
                  const res = await api.post("/maintenance/clear-logs", { body: { older_than_days: Number(clearDays) } });
                  setCleared(res.deleted);
                })
              }
              className={button}
            >
              Clear now
            </button>
          </div>
          {cleared !== null && (
            <p data-testid="logs-cleared" className="text-muted">
              {cleared === 1 ? "1 log deleted" : `${cleared} logs deleted`}
            </p>
          )}
        </Section>

        <Section title="Backup" testId="settings-backup">
          <p className="text-muted">
            App folder: <span data-testid="data-folder">{settings.data_folder}</span>
          </p>
          <button
            type="button"
            data-testid="backup"
            disabled={busy !== null}
            onClick={() =>
              void act("backup", async () => {
                const res = await api.post("/maintenance/backup", {});
                setBackupPath(res.path);
                setRestoreFrom((v) => v || res.path);
              })
            }
            className={button + " self-start"}
          >
            {busy === "backup" ? "Backing up…" : "Back up now"}
          </button>
          {backupPath && (
            <p className="text-muted">
              Saved to <span data-testid="backup-path" className="break-all text-text">{backupPath}</span>
            </p>
          )}
          <form
            className="flex flex-col gap-2 pt-2"
            onSubmit={(e) => {
              e.preventDefault();
              void act("restore", async () => {
                const res = await api.post("/maintenance/restore", {
                  body: { backup_path: restoreFrom.trim(), new_folder: restoreTo.trim() },
                });
                setRestored(res.data_folder);
              });
            }}
          >
            <span>Restore a backup into a new, empty folder (this app folder is not changed):</span>
            <input
              data-testid="restore-from"
              aria-label="Backup file (.zip)"
              placeholder="Backup file (.zip)"
              value={restoreFrom}
              onChange={(e) => setRestoreFrom(e.target.value)}
              className={input}
            />
            <input
              data-testid="restore-to"
              aria-label="New folder"
              placeholder="New folder"
              value={restoreTo}
              onChange={(e) => setRestoreTo(e.target.value)}
              className={input}
            />
            <button
              type="submit"
              data-testid="restore"
              disabled={busy !== null || !restoreFrom.trim() || !restoreTo.trim()}
              className={button + " self-start"}
            >
              Restore
            </button>
          </form>
          {restored && (
            <p className="text-muted">
              Restored into <span data-testid="restore-path" className="break-all text-text">{restored}</span>
            </p>
          )}
        </Section>
      </div>
      <div
        role="tabpanel"
        id={`${ids}-panel-models`}
        aria-labelledby={`${ids}-tab-models`}
        data-testid="settings-tabpanel-models"
        hidden={tab !== "models"}
        className="flex flex-col gap-4"
      >
        <Section title="Models" testId="settings-models">
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              void save();
            }}
          >
            {orderedRoles(Object.keys(settings.roles)).map((role) => (
                <div key={role} data-testid="role-row" data-role={role} className="flex flex-col gap-1 sm:flex-row sm:items-start sm:gap-3">
                  <div className="sm:w-40 sm:shrink-0 sm:pt-1">
                    {/* Step 22.5.5b (teacher): the description shows on hover or focus only; the
                        picker still names it in its aria-describedby. */}
                    {ROLE_INFO[role] ? (
                      <HoverTip
                        tip={ROLE_INFO[role].description}
                        tipId={`${ids}-role-${role}-desc`}
                        testId="role-name"
                        tipTestId="role-description"
                        width="w-60"
                        className="font-medium text-text"
                      >
                        {roleLabel(role)}
                      </HoverTip>
                    ) : (
                      <div className="font-medium text-text">{roleLabel(role)}</div>
                    )}
                  </div>
                  <ModelCombobox
                    role={role}
                    label={roleLabel(role)}
                    descriptionId={ROLE_INFO[role] ? `${ids}-role-${role}-desc` : undefined}
                    value={tags[role] ?? ""}
                    onChange={(tag) => {
                      setSaved(false);
                      setTags((t) => ({ ...t, [role]: tag }));
                    }}
                    installed={inventory?.models ?? null}
                    onDownload={(tag) => void modelPulls.start(tag)}
                    downloading={modelPulls.pulls[(tags[role] ?? "").trim()]?.running}
                  />
                </div>
              ))}
            <label className="flex items-center gap-3">
              <span className="w-40 shrink-0 font-medium text-text">Keep logs</span>
              <input
                data-testid="log-retention"
                aria-label="Keep model-call logs for (days)"
                type="number"
                min={1}
                value={retention}
                onChange={(e) => {
                  setSaved(false);
                  setRetention(e.target.value);
                }}
                className={input + " w-20"}
              />
              <span className="text-muted">days</span>
            </label>
            <div className="flex items-center gap-3">
              <button type="submit" data-testid="settings-save" disabled={!dirty || busy !== null} className={button}>
                Save
              </button>
              {saved && !dirty && (
                <span data-testid="settings-saved" className="text-muted">
                  Saved
                </span>
              )}
            </div>
          </form>
          <div className="flex flex-col gap-1">
            <button
              type="button"
              data-testid="pull-models"
              disabled={pulling || busy !== null}
              onClick={() =>
                void act("pull", async () => {
                  const res = await api.post("/settings/models/pull", {});
                  // Keep a live state an SSE event may already have set before this response.
                  setPulls((prev) =>
                    Object.fromEntries(
                      res.models.map((m) => {
                        const p = prev?.[m];
                        const live = p && p.status !== "success" && !p.status.startsWith("error");
                        return [m, live ? p : { status: "waiting", completed: null, total: null }];
                      }),
                    ),
                  );
                })
              }
              className={button + " self-start"}
            >
              Download missing models
            </button>
            {pulls && (
              <ul data-testid="pull-list" className="flex flex-col gap-1">
                {Object.entries(pulls).map(([model, p]) => (
                  <li key={model} data-testid="pull-row" data-model={model} data-status={p.status} className="flex flex-col gap-0.5">
                    <div className="flex gap-2">
                      <span className="flex-1">{model}</span>
                      <span data-testid="pull-label" className={p.status.startsWith("error") ? "text-danger" : "text-muted"}>
                        {pullLabel(p)}
                      </span>
                    </div>
                    {p.total ? (
                      <progress className="h-1 w-full" max={p.total} value={p.completed ?? 0} />
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Section>

        <Section title="Model manager" testId="settings-model-manager">
          <ModelManager api={api} inventory={inventory} loadError={modelsError} reload={loadModels} pulls={modelPulls} />
        </Section>

      </div>
      <div
        role="tabpanel"
        id={`${ids}-panel-attributes`}
        aria-labelledby={`${ids}-tab-attributes`}
        data-testid="settings-tabpanel-attributes"
        hidden={tab !== "attributes"}
        className="flex flex-col gap-4"
      >
        <TestAttributes api={api} />
      </div>
    </div>
  );
}
