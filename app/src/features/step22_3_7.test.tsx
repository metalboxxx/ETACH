// R22.3.7.2 (APP_TEST): Settings' Occasions list adds, renames, reorders and deletes (with a
// confirm, and the blocked reason), by keyboard too; the shared list (and so the Occasion editor
// and Test names) follows at once.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { createApiClient } from "@/api/client";
import { ConfirmProvider } from "@/components/ConfirmDialog";
import { OccasionList } from "@/features/settings/OccasionList";
import { toOccasion } from "@/features/panels/TestPanel";
import { BUILTIN_OCCASIONS, getOccasions, resetOccasions, type Occasion } from "@/lib/occasions";
import { automaticTestName } from "@/lib/testTitle";

function fakeSidecar() {
  let list: Occasion[] = BUILTIN_OCCASIONS.map((o) => ({ ...o }));
  list[1]!.test_count = 2; // FinalTerm used
  let n = 0;
  const renumber = () => list.forEach((o, i) => (o.position = i));
  const fetchImpl = async (input: string, init?: RequestInit) => {
    const url = new URL(input);
    const method = (init?.method ?? "GET").toUpperCase();
    const code = decodeURIComponent(url.pathname.slice("/occasions/".length));
    const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
    if (method === "GET" && url.pathname === "/occasions") return new Response(JSON.stringify(list));
    if (method === "POST" && url.pathname === "/occasions") {
      const o: Occasion = { code: `Custom:${++n}`, label: String(body.label), short_name: String(body.short_name), position: list.length, builtin: false, test_count: 0 };
      list.push(o);
      return new Response(JSON.stringify(o));
    }
    const o = list.find((x) => x.code === code);
    if (!o) return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    if (method === "PATCH") {
      if (typeof body.label === "string") o.label = body.label;
      if (typeof body.short_name === "string") o.short_name = body.short_name;
      if (typeof body.position === "number") {
        list = list.filter((x) => x !== o);
        list.splice(body.position, 0, o);
        renumber();
      }
      return new Response(JSON.stringify(o));
    }
    if (method === "DELETE") {
      list = list.filter((x) => x !== o);
      renumber();
      return new Response(null, { status: 204 });
    }
    return new Response(JSON.stringify({ detail: "?" }), { status: 405 });
  };
  return createApiClient({ baseUrl: "http://127.0.0.1:9", token: "t" }, fetchImpl);
}

const rows = () => screen.getAllByTestId("occasion-row");
const labels = () => rows().map((r) => within(r).queryByTestId("occasion-label")?.textContent);

afterEach(() => resetOccasions());

describe("Settings → Occasions", () => {
  it("adds, renames, moves and deletes, and the shared list follows", async () => {
    render(
      <ConfirmProvider>
        <OccasionList api={fakeSidecar()} />
      </ConfirmProvider>,
    );
    await waitFor(() => expect(rows()).toHaveLength(10));
    // built-ins: one note above the list (not repeated per row) describes each disabled Delete
    const final = rows()[1]!;
    expect(screen.getByTestId("occasion-builtin-note")).toHaveTextContent("Built-in occasions can be renamed but not deleted.");
    expect(screen.queryAllByTestId("occasion-blocked")).toHaveLength(0);
    const finalDelete = within(final).getByRole("button", { name: "Delete Final-term test" });
    expect(finalDelete).toBeDisabled();
    expect(finalDelete).toHaveAccessibleDescription("Built-in occasions can be renamed but not deleted.");

    // add (Enter submits the form)
    fireEvent.change(screen.getByTestId("occasion-new-label"), { target: { value: "Weekly quiz" } });
    fireEvent.change(screen.getByTestId("occasion-new-short"), { target: { value: "Quiz" } });
    fireEvent.submit(screen.getByTestId("occasion-new-short"));
    await waitFor(() => expect(rows()).toHaveLength(11));
    expect(getOccasions().at(-1)?.label).toBe("Weekly quiz");
    expect(toOccasion("weekly quiz")).toBe("Custom:1");
    expect(automaticTestName({ occasion: "Custom:1", grade: 7 })).toBe("Grade 7 - Quiz");

    // rename a built-in inline; Escape cancels, Enter saves
    fireEvent.click(screen.getByRole("button", { name: "Rename Unit test" }));
    fireEvent.keyDown(screen.getByTestId("occasion-edit-label"), { key: "Escape" });
    expect(screen.queryByTestId("occasion-edit-label")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Rename Unit test" }));
    fireEvent.change(screen.getByTestId("occasion-edit-short"), { target: { value: "Unit Check" } });
    fireEvent.change(screen.getByTestId("occasion-edit-label"), { target: { value: "Unit check" } });
    fireEvent.submit(screen.getByTestId("occasion-edit-label"));
    await waitFor(() => expect(labels()).toContain("Unit check"));
    expect(automaticTestName({ occasion: "UnitTest", grade: 6 })).toBe("Grade 6 - Unit Check");

    // move the new one up: the list order changes at once
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Move Weekly quiz up" })));
    await waitFor(() => expect(labels()[9]).toBe("Weekly quiz"));
    expect(getOccasions()[9]?.code).toBe("Custom:1");
    expect(screen.getByRole("button", { name: "Move Mid-term test up" })).toBeDisabled();

    // delete: confirm, Keep first, then Delete
    fireEvent.click(screen.getByRole("button", { name: "Delete Weekly quiz" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("Delete Weekly quiz?");
    fireEvent.click(within(dialog).getByRole("button", { name: "Keep occasion" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(rows()).toHaveLength(11);
    fireEvent.click(screen.getByRole("button", { name: "Delete Weekly quiz" }));
    fireEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Delete occasion" }));
    await waitFor(() => expect(rows()).toHaveLength(10));
    expect(labels()).not.toContain("Weekly quiz");
  });

  it("keeps keyboard focus in the list after Up/Down, Rename and Delete (WCAG 2.4.3)", async () => {
    render(
      <ConfirmProvider>
        <OccasionList api={fakeSidecar()} />
      </ConfirmProvider>,
    );
    await waitFor(() => expect(rows()).toHaveLength(10));
    const add = async (l: string, s: string) => {
      fireEvent.change(screen.getByTestId("occasion-new-label"), { target: { value: l } });
      fireEvent.change(screen.getByTestId("occasion-new-short"), { target: { value: s } });
      fireEvent.submit(screen.getByTestId("occasion-new-short"));
      await waitFor(() => expect(labels()).toContain(l));
    };
    await add("Weekly quiz", "Quiz");
    await add("Daily check", "Check");
    const button = (name: string) => screen.getByRole("button", { name });
    const press = async (name: string) => {
      const b = button(name);
      b.focus();
      await act(async () => fireEvent.click(b));
    };

    // Up: focus stays on the moved row's Up button
    await press("Move Daily check up");
    await waitFor(() => expect(labels()[10]).toBe("Daily check"));
    await waitFor(() => expect(document.activeElement).toBe(button("Move Daily check up")));
    // Down to the bottom: its Down is disabled there, so focus goes to its Up button
    await press("Move Daily check down");
    await waitFor(() => expect(labels()[11]).toBe("Daily check"));
    await waitFor(() => expect(document.activeElement).toBe(button("Move Daily check up")));

    // Rename: Escape and Save both return focus to the row's Rename button
    await press("Rename Weekly quiz");
    fireEvent.keyDown(screen.getByTestId("occasion-edit-label"), { key: "Escape" });
    await waitFor(() => expect(document.activeElement).toBe(button("Rename Weekly quiz")));
    await press("Rename Weekly quiz");
    fireEvent.change(screen.getByTestId("occasion-edit-label"), { target: { value: "Quiz week" } });
    await act(async () => fireEvent.submit(screen.getByTestId("occasion-edit-label")));
    await waitFor(() => expect(labels()).toContain("Quiz week"));
    await waitFor(() => expect(document.activeElement).toBe(button("Rename Quiz week")));

    // Delete: focus goes to the next row's Rename button
    await press("Delete Quiz week");
    fireEvent.click(await screen.findByRole("button", { name: "Delete occasion" }));
    await waitFor(() => expect(labels()).not.toContain("Quiz week"));
    await waitFor(() => expect(document.activeElement).toBe(button("Rename Daily check")));
    // the last row: nothing follows, so focus goes to the row now in its place (the one before)
    await press("Delete Daily check");
    fireEvent.click(await screen.findByRole("button", { name: "Delete occasion" }));
    await waitFor(() => expect(labels()).not.toContain("Daily check"));
    await waitFor(() => expect(document.activeElement).toBe(button("Rename Placement test")));
  });
});
