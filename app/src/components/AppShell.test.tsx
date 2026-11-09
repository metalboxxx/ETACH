import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "@/App";
import { AppShell } from "./AppShell";

function sidebarOrder(): string[] {
  const list = screen.getByTestId("sidebar-items");
  return Array.from(list.children).map((li) => li.getAttribute("data-item") ?? "?");
}

describe("layout (R13.1, without Review since R22.1.5.7)", () => {
  it("the sidebar renders exactly New thread, running slot, Chats|Tests|Students (step 22.2.3), Settings, in order; no Review", () => {
    render(<AppShell connection="open" />);
    expect(sidebarOrder()).toEqual(["new-thread", "running", "tabs", "settings"]);
    const items = Array.from(screen.getByTestId("sidebar-items").children) as HTMLElement[];
    expect(items[0]).toHaveTextContent("New thread");
    expect(items[1]).toBeEmptyDOMElement();
    expect(screen.queryByRole("button", { name: /Review/ })).toBeNull();
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["Chats", "Tests", "Students"]);
    expect(screen.getByRole("button", { name: "Settings" })).toBe(items[3]?.querySelector("button"));
  });

  it("without a sidecar: a calm Not connected notice, no crash", () => {
    render(<App config={null} />);
    expect(screen.getByTestId("connection-notice")).toHaveTextContent("Not connected");
    expect(screen.queryByTestId("review-count")).toBeNull();
    expect(sidebarOrder()).toEqual(["new-thread", "running", "tabs", "settings"]);
  });

  it("the Chats | Tests switch selects a tab", () => {
    render(<AppShell connection="open" />);
    fireEvent.click(screen.getByRole("tab", { name: "Tests" }));
    expect(screen.getByRole("tab", { name: "Tests" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Chats" })).toHaveAttribute("aria-selected", "false");
  });

  it("the panel is hidden by default, opens, closes with the close button and with Esc", () => {
    render(<AppShell connection="open" />);
    expect(screen.queryByTestId("artifact-panel")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(screen.getByTestId("artifact-panel")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close panel" }));
    expect(screen.queryByTestId("artifact-panel")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(screen.getByTestId("artifact-panel")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByTestId("artifact-panel")).toBeNull();
  });

  it("shortcut handlers can be supplied by later steps", () => {
    const onRunOrGrade = vi.fn();
    render(<AppShell connection="open" shortcuts={{ onRunOrGrade }} />);
    fireEvent.keyDown(window, { key: "Enter", ctrlKey: true });
    expect(onRunOrGrade).toHaveBeenCalledTimes(1);
  });

});
