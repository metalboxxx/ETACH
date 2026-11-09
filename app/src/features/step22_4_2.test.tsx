// R22.4.2.3 / R22.4.2.4 (APP_TEST): Settings' Schools list adds, renames, reorders and deletes
// (with a confirm and the blocked reason); the School combobox lists every school without typing,
// filters as the teacher types, and works by keyboard.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { createApiClient } from "@/api/client";
import { ConfirmProvider } from "@/components/ConfirmDialog";
import { SchoolCombobox } from "@/components/SchoolCombobox";
import { SchoolList } from "@/features/settings/SchoolList";
import { resetSchools, setSchools, type School } from "@/lib/schools";

function fakeSidecar() {
  let list: School[] = [
    { id: 1, name: "THCS Lê Lợi", position: 0, test_count: 2, student_count: 1 },
    { id: 2, name: "Trường B", position: 1, test_count: 0, student_count: 0 },
  ];
  let n = 2;
  const renumber = () => list.forEach((s, i) => (s.position = i));
  const fetchImpl = async (input: string, init?: RequestInit) => {
    const url = new URL(input);
    const method = (init?.method ?? "GET").toUpperCase();
    const id = Number(url.pathname.slice("/schools/".length));
    const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
    if (method === "GET" && url.pathname === "/schools") return new Response(JSON.stringify(list));
    if (method === "POST" && url.pathname === "/schools") {
      const s: School = { id: ++n, name: String(body.name), position: list.length, test_count: 0, student_count: 0 };
      list.push(s);
      return new Response(JSON.stringify(s));
    }
    const s = list.find((x) => x.id === id);
    if (!s) return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    if (method === "PATCH") {
      if (typeof body.name === "string") s.name = body.name;
      if (typeof body.position === "number") {
        list = list.filter((x) => x !== s);
        list.splice(body.position, 0, s);
        renumber();
      }
      return new Response(JSON.stringify(s));
    }
    if (method === "DELETE") {
      list = list.filter((x) => x !== s);
      renumber();
      return new Response(null, { status: 204 });
    }
    return new Response(JSON.stringify({ detail: "?" }), { status: 405 });
  };
  return createApiClient({ baseUrl: "http://127.0.0.1:9", token: "t" }, fetchImpl);
}

const rows = () => screen.getAllByTestId("school-row");
const names = () => rows().map((r) => within(r).queryByTestId("school-name")?.textContent);

afterEach(() => resetSchools());

describe("Settings → Schools", () => {
  it("adds, renames, moves and deletes; a used school shows why it can't be deleted", async () => {
    render(
      <ConfirmProvider>
        <SchoolList api={fakeSidecar()} />
      </ConfirmProvider>,
    );
    await waitFor(() => expect(rows()).toHaveLength(2));
    const used = rows()[0]!;
    expect(within(used).getByTestId("school-blocked")).toHaveTextContent("Used by 2 tests, 1 student");
    expect(within(used).getByRole("button", { name: "Delete THCS Lê Lợi" })).toBeDisabled();
    expect(within(rows()[1]!).getByTestId("school-uses")).toHaveTextContent("Not used");

    // add
    fireEvent.change(screen.getByTestId("school-new-name"), { target: { value: " Trường C " } });
    await act(async () => fireEvent.submit(screen.getByTestId("school-add").closest("form")!));
    await waitFor(() => expect(names()).toEqual(["THCS Lê Lợi", "Trường B", "Trường C"]));

    // rename inline: Enter saves, focus goes back to Rename
    fireEvent.click(screen.getByRole("button", { name: "Rename Trường B" }));
    const edit = screen.getByTestId("school-edit-name");
    fireEvent.change(edit, { target: { value: "Trường B2" } });
    await act(async () => fireEvent.submit(edit.closest("form")!));
    await waitFor(() => expect(names()).toEqual(["THCS Lê Lợi", "Trường B2", "Trường C"]));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: "Rename Trường B2" })));

    // Esc leaves a rename without saving
    fireEvent.click(screen.getByRole("button", { name: "Rename Trường C" }));
    fireEvent.keyDown(screen.getByTestId("school-edit-name"), { key: "Escape" });
    expect(screen.queryByTestId("school-edit-name")).toBeNull();

    // move up
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Move Trường C up" })));
    await waitFor(() => expect(names()).toEqual(["THCS Lê Lợi", "Trường C", "Trường B2"]));
    expect(screen.getByRole("button", { name: "Move THCS Lê Lợi up" })).toBeDisabled();

    // delete: Keep cancels, Delete removes
    fireEvent.click(screen.getByRole("button", { name: "Delete Trường C" }));
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Keep school" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(names()).toContain("Trường C");
    fireEvent.click(screen.getByRole("button", { name: "Delete Trường C" }));
    fireEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Delete school" }));
    await waitFor(() => expect(names()).toEqual(["THCS Lê Lợi", "Trường B2"]));
  });
});

function Field({ initial = "" }: { initial?: string }) {
  const [v, setV] = useState(initial);
  return (
    <>
      <SchoolCombobox value={v} onChange={setV} />
      <output data-testid="value">{v}</output>
    </>
  );
}

describe("School combobox", () => {
  it("lists every school on focus, filters on typing, and picks by keyboard", () => {
    setSchools([
      { id: 1, name: "THCS Lê Lợi", position: 0, test_count: 0, student_count: 0 },
      { id: 2, name: "THCS Nguyễn Du", position: 1, test_count: 0, student_count: 0 },
      { id: 3, name: "Trường B", position: 2, test_count: 0, student_count: 0 },
    ]);
    render(<Field initial="Trường B" />);
    const box = screen.getByRole("combobox");
    fireEvent.focus(box);
    // the whole list, even with a value already in the field
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["THCS Lê Lợi", "THCS Nguyễn Du", "Trường B"]);
    expect(box).toHaveAttribute("aria-expanded", "true");
    // typing filters (case and Vietnamese letters folded)
    fireEvent.change(box, { target: { value: "NGUYỄN" } });
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["THCS Nguyễn Du"]);
    // ↓ then Enter picks
    fireEvent.keyDown(box, { key: "ArrowDown" });
    expect(box).toHaveAttribute("aria-activedescendant");
    fireEvent.keyDown(box, { key: "Enter" });
    expect(screen.getByTestId("value")).toHaveTextContent("THCS Nguyễn Du");
    expect(screen.queryByRole("listbox")).toBeNull();
    // Esc closes the list; a new name can be typed
    fireEvent.click(box);
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    fireEvent.keyDown(box, { key: "Escape" });
    expect(screen.queryByRole("listbox")).toBeNull();
    fireEvent.change(box, { target: { value: "Trường Mới" } });
    expect(screen.queryByRole("option")).toBeNull();
    expect(screen.getByTestId("value")).toHaveTextContent("Trường Mới");
  });
});
