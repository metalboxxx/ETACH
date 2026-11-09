// R20.4 (APP_TEST): other_ollama_loaded=true → the warning shows in the sidebar and in Settings.
// Also the Settings panel: the model tag per role and the retention via PUT /settings (R20.1, UI
// side), Download models with per-model progress from SSE (R20.5, UI side), clear logs, backup
// and restore into a new folder.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EtachEvent, EventListenerFn, EventStream } from "@/api/sse";
import { EventsProvider } from "@/api/sse";
import { Connected } from "@/App";
import { fakeApi, type FakeCall } from "@/lib/testApi";
import { SETUP_SKIPPED_KEY } from "@/features/first-run/FirstRunScreen";
import { roleList } from "./roles";
import { pullLabel } from "./SettingsPanel";

vi.mock("@tauri-apps/plugin-notification", () => ({
  isPermissionGranted: vi.fn(async () => true),
  requestPermission: vi.fn(async () => "granted"),
  sendNotification: vi.fn(),
}));
vi.mock("@tauri-apps/api/core", () => ({ isTauri: vi.fn(() => false) }));

function fakeStream() {
  const listeners = new Set<EventListenerFn>();
  let id = 0;
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
      return id;
    },
  };
  const emit = (type: EtachEvent["type"], data: Record<string, unknown> = {}) =>
    act(() => {
      id += 1;
      const e = { id, type, data: { type, ...data } } as EtachEvent;
      listeners.forEach((fn) => fn(e));
    });
  return { stream, emit };
}

function setup(other: boolean) {
  // The status says models are missing: skip the first-run screen (step 21) to reach Settings.
  window.sessionStorage.setItem(SETUP_SKIPPED_KEY, "true");
  const state = {
    other,
    settings: {
      data_folder: "D:\\ETACH\\data",
      log_retention_days: 45,
      roles: {
        reasoning: { model: "qwen3.5:4b", options: {} },
        vision: { model: "qwen3-vl:4b", options: {} },
      } as Record<string, { model: string; options: Record<string, unknown> }>,
    },
  };
  const fake = fakeApi({
    "GET /threads": [],
    "GET /review/count": { count: 0 },
    "GET /runs/active": [],
    "GET /system/status": () => ({
      sidecar_version: "0.6.1",
      replay: false,
      power_source: "ac",
      keep_awake: false,
      missing_models: ["qwen3-vl:4b"],
      models_present: ["qwen3.5:4b"],
      ollama_status: "missing_model",
      ollama_version: "0.12.11",
      other_ollama_loaded: state.other,
    }),
    "GET /settings": () => state.settings,
    "PUT /settings": (c: FakeCall) => {
      const body = c.body as { roles?: Record<string, { model: string }>; log_retention_days?: number };
      for (const [role, r] of Object.entries(body.roles ?? {})) state.settings.roles[role] = { model: r.model, options: {} };
      if (body.log_retention_days) state.settings.log_retention_days = body.log_retention_days;
      return state.settings;
    },
    "POST /settings/models/pull": { models: ["qwen3.5:4b", "qwen3-vl:4b"] },
    "POST /maintenance/clear-logs": { deleted: 3 },
    "POST /maintenance/backup": { path: "D:\\ETACH\\data\\backups\\etach-backup.zip" },
    "POST /maintenance/restore": (c: FakeCall) => ({ data_folder: (c.body as { new_folder: string }).new_folder }),
  });
  const { stream, emit } = fakeStream();
  render(
    <EventsProvider stream={stream}>
      <Connected api={fake.api} />
    </EventsProvider>,
  );
  return { ...fake, emit, state };
}

async function openSettings() {
  fireEvent.click(screen.getByRole("button", { name: "Settings" }));
  return screen.findByTestId("settings-models");
}

beforeEach(() => window.sessionStorage.clear());

describe("other-Ollama warning (R20.4)", () => {
  it("shows in the sidebar and in Settings when other_ollama_loaded=true", async () => {
    setup(true);
    const sidebar = screen.getByRole("navigation", { name: "Sidebar" });
    expect(await within(sidebar).findByTestId("sidebar-ollama-warning")).toBeInTheDocument();
    await openSettings();
    expect(within(screen.getByTestId("settings-panel")).getByTestId("settings-ollama-warning")).toBeInTheDocument();
  });

  it("is absent when other_ollama_loaded=false, and appears on system.changed", async () => {
    const { calls, emit, state } = setup(false);
    await openSettings();
    expect(screen.queryByTestId("sidebar-ollama-warning")).toBeNull();
    expect(screen.queryByTestId("settings-ollama-warning")).toBeNull();
    state.other = true;
    const before = calls.filter((c) => c.path === "/system/status").length;
    emit("system.changed");
    await waitFor(() => expect(calls.filter((c) => c.path === "/system/status").length).toBeGreaterThan(before));
    expect(await screen.findByTestId("sidebar-ollama-warning")).toBeInTheDocument();
    expect(await screen.findByTestId("settings-ollama-warning")).toBeInTheDocument();
  });
});

describe("Settings panel", () => {
  it("shows the Ollama status, version and the present / missing models", async () => {
    setup(false);
    await openSettings();
    await waitFor(() => expect(screen.getByTestId("ollama-version")).toHaveTextContent("0.12.11"));
    expect(screen.getByTestId("ollama-status")).toHaveAttribute("data-status", "missing_model");
    expect(screen.getByTestId("models-present")).toHaveTextContent("qwen3.5:4b");
    expect(screen.getByTestId("models-missing")).toHaveTextContent("qwen3-vl:4b");
    expect(screen.getByTestId("data-folder")).toHaveTextContent("D:\\ETACH\\data");
    expect(screen.getByTestId("sidecar-version")).toHaveTextContent("0.6.1"); // R21.2, UI side
  });

  it("saves a changed role tag and the retention through PUT /settings (R20.1, UI side)", async () => {
    const { calls } = setup(false);
    await openSettings();
    const reasoning = await screen.findByLabelText("Grading");
    expect(reasoning).toHaveValue("qwen3.5:4b");
    expect(screen.getByTestId("settings-save")).toBeDisabled();
    fireEvent.change(reasoning, { target: { value: "qwen3.5:9b" } });
    fireEvent.change(screen.getByTestId("log-retention"), { target: { value: "30" } });
    fireEvent.click(screen.getByTestId("settings-save"));
    expect(await screen.findByTestId("settings-saved")).toBeInTheDocument();
    const put = calls.find((c) => c.method === "PUT" && c.path === "/settings");
    expect(put?.body).toEqual({
      roles: {
        vision: { model: "qwen3-vl:4b" },
        reasoning: { model: "qwen3.5:9b" },
        grading_check: { model: "qwen3.5:4b" },
        extraction_check: { model: "qwen3.5:4b" },
      },
      log_retention_days: 30,
    });
    expect(screen.getByLabelText("Grading")).toHaveValue("qwen3.5:9b");
    expect(screen.getByTestId("settings-save")).toBeDisabled();
  });

  it("Download models: per-model progress from SSE, ending ready (R20.5, UI side)", async () => {
    const { emit } = setup(false);
    await openSettings();
    fireEvent.click(screen.getByTestId("pull-models"));
    const rows = await screen.findAllByTestId("pull-row");
    expect(rows.map((r) => r.getAttribute("data-model"))).toEqual(["qwen3.5:4b", "qwen3-vl:4b"]);
    expect(screen.getByTestId("pull-models")).toBeDisabled();
    const label = (m: string) =>
      within(screen.getByTestId("pull-list").querySelector(`[data-model="${m}"]`) as HTMLElement).getByTestId(
        "pull-label",
      );
    emit("models.pull_progress", { model: "qwen3.5:4b", status: "downloading", completed: 40, total: 100 });
    expect(label("qwen3.5:4b")).toHaveTextContent("downloading 40%");
    expect(label("qwen3-vl:4b")).toHaveTextContent("waiting");
    emit("models.pull_progress", { model: "qwen3.5:4b", status: "success", completed: null, total: null });
    emit("models.pull_progress", { model: "qwen3-vl:4b", status: "error: disk full", completed: null, total: null });
    expect(label("qwen3.5:4b")).toHaveTextContent("ready");
    expect(label("qwen3-vl:4b")).toHaveTextContent("failed: disk full");
    expect(screen.getByTestId("pull-models")).toBeEnabled();
  });

  it("clears logs older than N days, backs up and restores into a new folder", async () => {
    const { calls } = setup(false);
    await openSettings();
    fireEvent.change(screen.getByTestId("clear-days"), { target: { value: "7" } });
    fireEvent.click(screen.getByTestId("clear-logs"));
    expect(await screen.findByTestId("logs-cleared")).toHaveTextContent("3 logs deleted");
    expect(calls.find((c) => c.path === "/maintenance/clear-logs")?.body).toEqual({ older_than_days: 7 });

    fireEvent.click(screen.getByTestId("backup"));
    expect(await screen.findByTestId("backup-path")).toHaveTextContent("etach-backup.zip");
    expect(screen.getByTestId("restore-from")).toHaveValue("D:\\ETACH\\data\\backups\\etach-backup.zip");
    fireEvent.change(screen.getByTestId("restore-to"), { target: { value: "E:\\Restored" } });
    fireEvent.click(screen.getByTestId("restore"));
    expect(await screen.findByTestId("restore-path")).toHaveTextContent("E:\\Restored");
    expect(calls.find((c) => c.path === "/maintenance/restore")?.body).toEqual({
      backup_path: "D:\\ETACH\\data\\backups\\etach-backup.zip",
      new_folder: "E:\\Restored",
    });
  });
});

// R22.5.4.8 (APP_TEST): the Models tab shows four pickers with accessible names and one-line
// descriptions; saving sends the four roles; a setup without the new roles shows qwen3.5:4b.
describe("Models tab: four role pickers (R22.5.4.8)", () => {
  const PICKERS = [
    ["extraction_check", "Extraction check", "Checks and fixes a reading of the pages"],
    ["vision", "Student answer reader", "Reads the student answers from the photos"],
    ["reasoning", "Grading", "Marks student answers and explains the mistakes"],
    ["grading_check", "Grading check", "Double-checks keys the AI wrote"],
  ] as const;

  it("shows the four pickers in order, each named and described", async () => {
    setup(false);
    await openSettings();
    fireEvent.click(screen.getByRole("tab", { name: "Models" }));
    const models = screen.getByTestId("settings-tabpanel-models");
    await within(models).findByRole("combobox", { name: "Student answer reader" });
    const boxes = within(models).getAllByTestId("role-model");
    expect(boxes.map((b) => b.getAttribute("data-role"))).toEqual(PICKERS.map(([role]) => role));
    for (const [role, name, description] of PICKERS) {
      const box = within(models).getByRole("combobox", { name });
      expect(box).toHaveAttribute("data-role", role);
      expect(box).toHaveAccessibleDescription(description);
    }
  });

  // R22.5.5.8 (teacher, 2026-10-24): the descriptions show only on hover or keyboard focus.
  it("R22.5.5.8 shows a picker's description only on hover or focus of its name", async () => {
    setup(false);
    await openSettings();
    fireEvent.click(screen.getByRole("tab", { name: "Models" }));
    const models = screen.getByTestId("settings-tabpanel-models");
    await within(models).findByRole("combobox", { name: "Student answer reader" });
    const tips = within(models).getAllByTestId("role-description");
    expect(tips).toHaveLength(4);
    tips.forEach((t) => expect(t).toHaveAttribute("data-open", "false"));
    expect(tips[0]!).toHaveClass("invisible");
    const name = within(models).getAllByTestId("role-name")[0]!;
    expect(name).toHaveAttribute("tabindex", "0");
    expect(name).toHaveAccessibleDescription(PICKERS[0][2]);
    fireEvent.mouseEnter(name.parentElement!);
    expect(tips[0]!).toHaveAttribute("data-open", "true");
    fireEvent.mouseLeave(name.parentElement!);
    expect(tips[0]!).toHaveAttribute("data-open", "false");
    fireEvent.focus(name);
    expect(tips[0]!).toHaveAttribute("data-open", "true");
    fireEvent.keyDown(name, { key: "Escape" });
    expect(tips[0]!).toHaveAttribute("data-open", "false");
  });

  it("an existing setup without the new roles shows qwen3.5:4b for them, and Save stays off", async () => {
    setup(false);
    await openSettings();
    fireEvent.click(screen.getByRole("tab", { name: "Models" }));
    const models = screen.getByTestId("settings-tabpanel-models");
    expect(await within(models).findByRole("combobox", { name: "Grading check" })).toHaveValue("qwen3.5:4b");
    expect(within(models).getByRole("combobox", { name: "Extraction check" })).toHaveValue("qwen3.5:4b");
    expect(within(models).getByRole("combobox", { name: "Student answer reader" })).toHaveValue("qwen3-vl:4b");
    expect(screen.getByTestId("settings-save")).toBeDisabled();
  });

  it("saving sends all four roles, the new ones included", async () => {
    const { calls, state } = setup(false);
    await openSettings();
    fireEvent.click(screen.getByRole("tab", { name: "Models" }));
    const models = screen.getByTestId("settings-tabpanel-models");
    const check = await within(models).findByRole("combobox", { name: "Grading check" });
    fireEvent.change(check, { target: { value: "qwen3.5:9b" } });
    fireEvent.click(screen.getByTestId("settings-save"));
    expect(await screen.findByTestId("settings-saved")).toBeInTheDocument();
    const put = calls.find((c) => c.method === "PUT" && c.path === "/settings");
    expect(put?.body).toEqual({
      roles: {
        vision: { model: "qwen3-vl:4b" },
        reasoning: { model: "qwen3.5:4b" },
        grading_check: { model: "qwen3.5:9b" },
        extraction_check: { model: "qwen3.5:4b" },
      },
    });
    expect(Object.keys(state.settings.roles).sort()).toEqual(["extraction_check", "grading_check", "reasoning", "vision"]);
    expect(within(models).getByRole("combobox", { name: "Grading check" })).toHaveValue("qwen3.5:9b");
  });
});

// R22.5.7.7 (APP_TEST): the OCR role (glm-ocr) is a default role: its picker ("Test reader") shows
// when the sidecar sends it, and Save keeps its tag; without it (photo_reader = "vision") no
// picker shows and Save does not write it.
describe("Models tab: the OCR role (R22.5.7.7)", () => {
  it("shows the OCR picker when the sidecar sends the role, and Save keeps glm-ocr", async () => {
    const { calls, state } = setup(false);
    state.settings.roles = {
      vision: { model: "qwen3.5:4b", options: {} },
      ocr: { model: "glm-ocr", options: {} },
      reasoning: { model: "qwen3.5:4b", options: {} },
      grading_check: { model: "qwen3.5:4b", options: {} },
      extraction_check: { model: "qwen3.5:4b", options: {} },
    };
    await openSettings();
    fireEvent.click(screen.getByRole("tab", { name: "Models" }));
    const models = screen.getByTestId("settings-tabpanel-models");
    const ocr = await within(models).findByRole("combobox", { name: "Test reader" });
    expect(ocr).toHaveValue("glm-ocr");
    expect(ocr).toHaveAccessibleDescription("Reads the test photos");
    const order = within(models).getAllByTestId("role-model").map((b) => b.getAttribute("data-role"));
    expect(order).toEqual(["ocr", "extraction_check", "vision", "reasoning", "grading_check"]);
    fireEvent.change(within(models).getByRole("combobox", { name: "Grading" }), { target: { value: "qwen3.5:9b" } });
    fireEvent.click(screen.getByTestId("settings-save"));
    expect(await screen.findByTestId("settings-saved")).toBeInTheDocument();
    const put = calls.find((c) => c.method === "PUT" && c.path === "/settings");
    expect((put?.body as { roles: Record<string, { model: string }> }).roles.ocr).toEqual({ model: "glm-ocr" });
  });

  it("shows no OCR picker when the sidecar does not send the role", async () => {
    setup(false);
    await openSettings();
    fireEvent.click(screen.getByRole("tab", { name: "Models" }));
    const models = screen.getByTestId("settings-tabpanel-models");
    await within(models).findByRole("combobox", { name: "Student answer reader" });
    expect(within(models).queryByRole("combobox", { name: "Test reader" })).toBeNull();
  });
});

// R1.1 (APP_TEST, refinements D1): the Models tab follows the order of work on a new test, whatever
// order the sidecar sends the roles in; without `ocr` the other four keep that order.
describe("Models tab: the order of work (R1.1)", () => {
  const rows = (models: HTMLElement) =>
    within(models).getAllByTestId("role-row").map((r) => [
      r.getAttribute("data-role"),
      within(r).getByTestId("role-name").textContent,
    ]);
  const FOUR = [
    ["extraction_check", "Extraction check"],
    ["vision", "Student answer reader"],
    ["reasoning", "Grading"],
    ["grading_check", "Grading check"],
  ];

  it("shows the five roles in the D1 order", async () => {
    const { state } = setup(false);
    state.settings.roles = {
      grading_check: { model: "qwen3.5:4b", options: {} },
      reasoning: { model: "qwen3.5:4b", options: {} },
      vision: { model: "qwen3.5:4b", options: {} },
      extraction_check: { model: "qwen3.5:4b", options: {} },
      ocr: { model: "glm-ocr", options: {} },
    };
    await openSettings();
    fireEvent.click(screen.getByRole("tab", { name: "Models" }));
    const models = screen.getByTestId("settings-tabpanel-models");
    await within(models).findByRole("combobox", { name: "Test reader" });
    expect(rows(models)).toEqual([["ocr", "Test reader"], ...FOUR]);
  });

  it("without ocr sent, shows the other four in order and no Test reader row", async () => {
    setup(false);
    await openSettings();
    fireEvent.click(screen.getByRole("tab", { name: "Models" }));
    const models = screen.getByTestId("settings-tabpanel-models");
    await within(models).findByRole("combobox", { name: "Student answer reader" });
    expect(rows(models)).toEqual(FOUR);
    expect(within(models).queryByText("Test reader")).toBeNull();
  });

  it("names the roles in the same order in a roleList sentence", () => {
    expect(roleList(["grading_check", "reasoning", "vision", "extraction_check", "ocr"])).toBe(
      "test reader, extraction check, student answer reader, grading and grading check",
    );
  });
});

describe("pullLabel", () => {
  it("formats the pull states", () => {
    expect(pullLabel({ status: "pulling manifest", completed: null, total: null })).toBe("pulling manifest");
    expect(pullLabel({ status: "downloading", completed: 100, total: 100 })).toBe("downloading 100%");
    expect(pullLabel({ status: "success", completed: null, total: null })).toBe("ready");
  });
});
