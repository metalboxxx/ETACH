// R22.4.2.1 (APP_TEST): Settings shows its tabs; each holds its part; switching keeps what was
// typed; arrow keys, Home and End move along the tabs and Enter opens one; the chosen tab is kept
// when Settings is opened again. Step 22.5.2 (comment 3): the tabs are General, Models and Test
// attributes; Occasions and Schools are reached through the Test attributes menu.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { createApiClient } from "@/api/client";
import { EventsProvider, type EventStream } from "@/api/sse";
import { ConfirmProvider } from "@/components/ConfirmDialog";
import { resetOccasions } from "@/lib/occasions";
import { resetSchools } from "@/lib/schools";
import { resetSettingsTab, SettingsPanel } from "./SettingsPanel";

const stream: EventStream = {
  start: () => {},
  close: () => {},
  subscribe: () => () => {},
  onStatus: () => () => {},
  status: "open",
  lastEventId: null,
};

function api() {
  const data: Record<string, unknown> = {
    "/settings": {
      data_folder: "D:\\ETACH\\data",
      log_retention_days: 45,
      roles: { reasoning: { model: "qwen3.5:4b", options: {} } },
    },
    "/models": { models: [], roles: {}, suggested: [] },
    "/occasions": [],
    "/schools": [{ id: 1, name: "THCS Lê Lợi", position: 0, test_count: 0, student_count: 0 }],
  };
  const fetchImpl = async (input: string) => {
    const body = data[new URL(input).pathname];
    return body === undefined ? new Response("{}", { status: 404 }) : new Response(JSON.stringify(body));
  };
  return createApiClient({ baseUrl: "http://127.0.0.1:9", token: "t" }, fetchImpl);
}

function open() {
  return render(
    <EventsProvider stream={stream}>
      <ConfirmProvider>
        <SettingsPanel api={api()} status={null} />
      </ConfirmProvider>
    </EventsProvider>,
  );
}

const tab = (name: string) => within(screen.getByRole("tablist", { name: "Settings" })).getByRole("tab", { name });
const panel = (id: string) => screen.getByTestId(`settings-tabpanel-${id}`);

afterEach(() => {
  resetSettingsTab();
  resetOccasions();
  resetSchools();
});

describe("Settings tabs", () => {
  it("shows three tabs, each with its part; switching keeps typed values", async () => {
    open();
    await waitFor(() => expect(screen.getByRole("tablist", { name: "Settings" })).toBeInTheDocument());
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["General", "Models", "Test attributes"]);
    expect(tab("General")).toHaveAttribute("aria-selected", "true");
    // General: Ollama, logs, backup; Models: the roles and the model manager
    expect(within(panel("general")).getByTestId("settings-ollama")).toBeInTheDocument();
    expect(within(panel("general")).getByTestId("settings-backup")).toBeInTheDocument();
    expect(within(panel("models")).getByTestId("settings-models")).toBeInTheDocument();
    expect(within(panel("models")).getByTestId("settings-model-manager")).toBeInTheDocument();
    expect(within(panel("attributes")).getByTestId("settings-occasions")).not.toBeVisible();
    expect(within(panel("attributes")).getByTestId("settings-schools")).not.toBeVisible();
    expect(panel("general")).toBeVisible();
    expect(panel("models")).not.toBeVisible();
    expect(panel("general")).toHaveAttribute("aria-labelledby", tab("General").id);

    fireEvent.change(screen.getByTestId("clear-days"), { target: { value: "12" } });
    fireEvent.click(tab("Test attributes"));
    expect(tab("Test attributes")).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("button", { name: "Schools" }));
    expect(screen.getByTestId("settings-schools")).toBeVisible();
    expect(panel("general")).not.toBeVisible();
    await waitFor(() => expect(screen.getByTestId("school-name")).toHaveTextContent("THCS Lê Lợi"));
    fireEvent.click(tab("General"));
    expect(screen.getByTestId("clear-days")).toHaveValue(12);
  });

  it("moves with arrows, Home and End; Enter opens; one tab in the tab order", async () => {
    open();
    await waitFor(() => expect(screen.getByRole("tablist", { name: "Settings" })).toBeInTheDocument());
    expect(screen.getAllByRole("tab").filter((t) => t.tabIndex === 0)).toEqual([tab("General")]);
    const list = screen.getByRole("tablist", { name: "Settings" });
    tab("General").focus();
    fireEvent.keyDown(list, { key: "ArrowRight" });
    expect(tab("Models")).toHaveFocus();
    fireEvent.keyDown(list, { key: "End" });
    expect(tab("Test attributes")).toHaveFocus();
    fireEvent.keyDown(list, { key: "ArrowRight" }); // wraps
    expect(tab("General")).toHaveFocus();
    fireEvent.keyDown(list, { key: "ArrowLeft" }); // wraps back
    expect(tab("Test attributes")).toHaveFocus();
    fireEvent.keyDown(list, { key: "Home" });
    expect(tab("General")).toHaveFocus();
    fireEvent.keyDown(list, { key: "ArrowRight" });
    fireEvent.keyDown(list, { key: "ArrowRight" });
    expect(tab("Test attributes")).toHaveFocus();
    // focus alone does not open a tab; a button's Enter/Space click does
    expect(tab("General")).toHaveAttribute("aria-selected", "true");
    fireEvent.click(tab("Test attributes"));
    expect(tab("Test attributes")).toHaveAttribute("aria-selected", "true");
    expect(tab("Test attributes").tabIndex).toBe(0);
  });

  it("keeps the chosen tab when Settings is opened again", async () => {
    const first = open();
    await waitFor(() => expect(screen.getByRole("tablist", { name: "Settings" })).toBeInTheDocument());
    fireEvent.click(tab("Models"));
    first.unmount();
    await act(async () => {
      open();
    });
    await waitFor(() => expect(tab("Models")).toHaveAttribute("aria-selected", "true"));
    expect(panel("models")).toBeVisible();
  });
});
