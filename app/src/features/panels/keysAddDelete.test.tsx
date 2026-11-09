/**
 * Refinements step R3 (D6, D7): Add key and delete key in the Key tab (R3.1–R3.3, R3.5). R3.4 is
 * the grade graph's: `sidecar/tests/unit/graphs/test_refinements_r3.py`.
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConfirmProvider } from "@/components/ConfirmDialog";
import { FakeStatus, fakeApi, type FakeCall } from "@/lib/testApi";
import { DELETE_KEY_BODY, KeysPanel } from "./KeysPanel";

const question = (n: number, printed = n) => ({ id: `q-${n}`, number: n, printed_number: printed, stem: `Stem ${n}` });

const section = (id: string, qs: object[], graded?: boolean) => ({
  id,
  number: 1,
  title: id,
  printed_title: id,
  instructions: "",
  skill: "grammar",
  ...(graded === undefined ? {} : { graded }),
  groups: [{ id: `g-${id}`, questions: qs }],
});

/** Printed numbers differ from the running numbers: q-3 is printed 13, q-4 is printed 14. */
const CONTENT = {
  sections: [
    section("s1", [question(1), question(2), question(3, 13), question(4, 14)]),
    section("writing", [question(5, 15)], false),
  ],
};

const key = (id: string, accepted = "A") => ({
  test_id: "T-0001",
  question_id: id,
  accepted: [accepted],
  reason_vi: null,
  source: "ai",
  status: "ai_verified",
  confidence: 0.9 as number | null,
  checker: null,
  updated_at: "2026-11-06T00:00:00Z",
});

interface Item {
  id: string;
  kind: string;
  status: string;
  question_id: string;
  proposal: object;
}

const unsure = (id: string, question_id: string): Item => ({
  id,
  kind: "uncertain_key",
  status: "open",
  question_id,
  proposal: { accepted: [] },
});

/** A sidecar with the key rows and open items as state, so a reload shows what each call did. */
function sidecar(ids: string[], review: Item[] = [], failing = new Set<string>()) {
  let rows = ids.map((id) => key(id));
  let open = review;
  const qid = (c: FakeCall) => c.path.split("/").pop()!;
  const fake = fakeApi({
    "GET /tests/{id}/keys": () => rows,
    "GET /tests/{id}": () => ({ id: "T-0001", content: CONTENT, review: open }),
    "PUT /tests/{id}/keys/{question_id}": (c: FakeCall) => {
      const accepted = (c.body as { accepted: string[] }).accepted;
      const row = { ...key(qid(c)), accepted, source: "teacher_edit", status: "teacher_verified", confidence: null };
      rows = [...rows, row];
      return { key: row, outcome: "inserted", explanations_deleted: 0, run_ids: [] };
    },
    "DELETE /tests/{id}/keys/{question_id}": (c: FakeCall) => {
      rows = rows.filter((k) => k.question_id !== qid(c));
      open = open.filter((i) => i.question_id !== qid(c)); // the sidecar settles them all
      return null;
    },
    // Each call closes its one item, as `domain/review.py` does; a Fix writes the teacher key.
    "POST /review/{id}/resolve": (c: FakeCall) => {
      const id = c.path.split("/").at(-2);
      const item = open.find((i) => i.id === id);
      if (!item) return new FakeStatus(409, { detail: `review item ${id} is not open` });
      if (failing.has(item.id)) return new FakeStatus(500, { detail: "disk full" });
      const { action, value } = c.body as { action: string; value?: string[] };
      if (action === "fix") {
        const row = { ...key(item.question_id), accepted: value!, source: "teacher_edit", status: "teacher_verified" };
        rows = [...rows.filter((k) => k.question_id !== item.question_id), row];
      } else if (action === "accept") {
        rows = rows.map((k) => (k.question_id === item.question_id ? { ...k, status: "teacher_verified" } : k));
      }
      open = open.filter((i) => i !== item);
      return {};
    },
  });
  return fake;
}

const numbersOffered = () =>
  within(screen.getByTestId("key-add-list"))
    .getAllByTestId("key-add-question")
    .map((b) => b.textContent);

const pick = (n: string) => fireEvent.click(screen.getByRole("button", { name: `Question ${n}` }));

const typeAndSave = (value: string) => {
  fireEvent.change(screen.getByTestId("key-input"), { target: { value } });
  fireEvent.click(screen.getByTestId("key-save"));
};

describe("R3.1: Add key", () => {
  it("offers exactly the graded questions with no key, by printed number, in test order", async () => {
    const { api } = sidecar(["q-2"]);
    render(<KeysPanel api={api} testId="T-0001" />);
    fireEvent.click(await screen.findByTestId("key-add"));
    expect(numbersOffered()).toEqual(["1", "13", "14"]); // q-2 has a key; q-5 is not graded
  });

  it("leaves the key list as it is: no empty rows", async () => {
    const { api } = sidecar(["q-2"]);
    render(<KeysPanel api={api} testId="T-0001" />);
    fireEvent.click(await screen.findByTestId("key-add"));
    expect(screen.getAllByTestId("key-row")).toHaveLength(1);
  });

  it("is one button that opens the list, and the list closes again", async () => {
    const { api } = sidecar(["q-2"]);
    render(<KeysPanel api={api} testId="T-0001" />);
    const button = await screen.findByTestId("key-add");
    expect(within(screen.getByTestId("keys-toolbar")).getAllByText("Add key")).toHaveLength(1);
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByTestId("key-add-panel")).toBeNull();
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(screen.getByTestId("key-add-close"));
    expect(screen.queryByTestId("key-add-panel")).toBeNull();
    await waitFor(() => expect(button).toHaveFocus());
  });

  it("saves the typed key through PUT, and the row shows as a teacher key", async () => {
    const onKeysChanged = vi.fn();
    const { api, calls } = sidecar(["q-1", "q-2"]);
    render(<KeysPanel api={api} testId="T-0001" onKeysChanged={onKeysChanged} />);
    fireEvent.click(await screen.findByTestId("key-add"));
    pick("13");
    expect(screen.getByLabelText("Key for question 13")).toHaveValue("");
    await waitFor(() => expect(screen.getByLabelText("Key for question 13")).toHaveFocus());
    typeAndSave("has gone | 's gone");
    const row = await waitFor(() => {
      const found = screen.getAllByTestId("key-row").find((r) => r.dataset.questionId === "q-3");
      expect(found).toBeDefined();
      return found!;
    });
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.path).toBe("/tests/T-0001/keys/q-3");
    expect(put?.body).toEqual({ accepted: ["has gone", "'s gone"], verify: false });
    expect(within(row).getByTestId("key-status")).toHaveTextContent("Teacher");
    expect(within(row).getByText("13.")).toBeInTheDocument();
    expect(onKeysChanged).toHaveBeenCalledTimes(1);
  });

  it("stays open for the next question, with focus on the list", async () => {
    const { api } = sidecar(["q-1", "q-2"]);
    render(<KeysPanel api={api} testId="T-0001" />);
    fireEvent.click(await screen.findByTestId("key-add"));
    pick("13");
    typeAndSave("B");
    await waitFor(() => expect(numbersOffered()).toEqual(["14"]));
    expect(screen.queryByTestId("key-input")).toBeNull();
    await waitFor(() => expect(screen.getByRole("button", { name: "Question 14" })).toHaveFocus());
  });

  it("works on a test with no keys at all", async () => {
    const { api, calls } = sidecar([]);
    render(<KeysPanel api={api} testId="T-0001" />);
    expect(await screen.findByText("No keys yet: grade the test or add a key.")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("key-add"));
    expect(numbersOffered()).toEqual(["1", "2", "13", "14"]);
    pick("1");
    typeAndSave("C");
    await screen.findByTestId("key-row");
    expect(calls.some((c) => c.method === "PUT")).toBe(true);
    expect(screen.queryByText("No keys yet: grade the test or add a key.")).toBeNull();
  });

  it("closes an open unsure note on the question with its Fix (a failed key run)", async () => {
    const { api, calls } = sidecar(["q-2", "q-3", "q-4"], [unsure("r-1", "q-1")]);
    render(<KeysPanel api={api} testId="T-0001" />);
    fireEvent.click(await screen.findByTestId("key-add"));
    pick("1");
    typeAndSave("D");
    await waitFor(() => expect(screen.queryByTestId("key-add")).toBeNull());
    const post = calls.find((c) => c.method === "POST");
    expect(post?.path).toBe("/review/r-1/resolve");
    expect(post?.body).toEqual({ action: "fix", value: ["D"] });
    await waitFor(() => expect(screen.getByTestId("key-print")).toHaveFocus());
  });

  it("clicking the picked number again keeps the typed key", async () => {
    const { api } = sidecar(["q-2"]);
    render(<KeysPanel api={api} testId="T-0001" />);
    fireEvent.click(await screen.findByTestId("key-add"));
    pick("1");
    fireEvent.change(screen.getByTestId("key-input"), { target: { value: "half typed" } });
    pick("1");
    expect(screen.getByTestId("key-input")).toHaveValue("half typed");
    pick("13"); // another question starts empty
    expect(screen.getByLabelText("Key for question 13")).toHaveValue("");
  });

  it("Escape in the input closes Add key and does not reach the workspace", async () => {
    const onKeyDown = vi.fn();
    const { api, calls } = sidecar(["q-2"]);
    render(
      <div onKeyDown={onKeyDown}>
        <KeysPanel api={api} testId="T-0001" />
      </div>,
    );
    fireEvent.click(await screen.findByTestId("key-add"));
    pick("1");
    fireEvent.keyDown(screen.getByTestId("key-input"), { key: "Escape" });
    expect(screen.queryByTestId("key-add-panel")).toBeNull();
    await waitFor(() => expect(screen.getByTestId("key-add")).toHaveFocus());
    expect(onKeyDown).not.toHaveBeenCalled();
    expect(calls.some((c) => c.method === "PUT")).toBe(false);
  });

  it("shows the error and keeps the typed key when the save fails", async () => {
    const { api } = fakeApi({
      "GET /tests/{id}/keys": [],
      "GET /tests/{id}": { id: "T-0001", content: CONTENT, review: [] },
      "PUT /tests/{id}/keys/{question_id}": new FakeStatus(500, { detail: "disk full" }),
    });
    render(<KeysPanel api={api} testId="T-0001" />);
    fireEvent.click(await screen.findByTestId("key-add"));
    pick("1");
    typeAndSave("B");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByTestId("key-input")).toHaveValue("B");
  });

  it("has one key input at a time: Edit on a row closes Add key, and Add key closes Edit", async () => {
    const { api } = sidecar(["q-1"]);
    render(<KeysPanel api={api} testId="T-0001" />);
    fireEvent.click(await screen.findByTestId("key-add"));
    pick("2");
    fireEvent.click(screen.getByTestId("key-edit"));
    expect(screen.queryByTestId("key-add-panel")).toBeNull();
    expect(screen.getByTestId("key-input")).toHaveValue("A");
    fireEvent.click(screen.getByTestId("key-add"));
    expect(screen.queryByTestId("key-input")).toBeNull();
  });
});

describe("R3.1, R3.3: a question with two open unsure items (two runs missed its key)", () => {
  const resolves = (calls: FakeCall[]) =>
    calls.filter((c) => c.method === "POST").map((c) => [c.path.split("/").at(-2), (c.body as { action: string }).action]);

  it("Add key closes both and writes the key once, with the last item's Fix", async () => {
    const onKeysChanged = vi.fn();
    const { api, calls } = sidecar(["q-3", "q-4"], [unsure("r-1", "q-1"), unsure("r-2", "q-1")]);
    render(<KeysPanel api={api} testId="T-0001" onKeysChanged={onKeysChanged} />);
    fireEvent.click(await screen.findByTestId("key-add"));
    pick("1");
    typeAndSave("D");
    const row = await waitFor(() => {
      const found = screen.getAllByTestId("key-row").find((r) => r.dataset.questionId === "q-1");
      expect(found).toBeDefined();
      return found!;
    });
    expect(resolves(calls)).toEqual([
      ["r-1", "skip"],
      ["r-2", "fix"],
    ]);
    expect(within(row).getByTestId("key-status")).toHaveTextContent("Teacher");
    expect(screen.queryByTestId("key-unsure")).toBeNull();
    expect(onKeysChanged).toHaveBeenCalledTimes(1);
  });

  it("Edit on a key closes both", async () => {
    const { api, calls } = sidecar(["q-1"], [unsure("r-1", "q-1"), unsure("r-2", "q-1")]);
    render(<KeysPanel api={api} testId="T-0001" />);
    await screen.findByTestId("key-unsure");
    fireEvent.click(screen.getByTestId("key-edit"));
    typeAndSave("B");
    await waitFor(() => expect(screen.queryByTestId("key-unsure")).toBeNull());
    expect(resolves(calls)).toEqual([
      ["r-1", "skip"],
      ["r-2", "fix"],
    ]);
    expect(screen.getByTestId("key-accepted")).toHaveTextContent("B");
  });

  it("Verify and Dismiss close both, and an item on another question stays", async () => {
    for (const [button, action] of [
      ["key-verify", "accept"],
      ["key-skip", "skip"],
    ] as const) {
      const { api, calls } = sidecar(["q-1", "q-2"], [unsure("r-1", "q-1"), unsure("r-2", "q-1"), unsure("r-3", "q-2")]);
      const view = render(<KeysPanel api={api} testId="T-0001" />);
      const rows = await screen.findAllByTestId("key-row");
      await within(rows[0]!).findByTestId("key-unsure");
      fireEvent.click(within(rows[0]!).getByTestId(button));
      await waitFor(() => expect(screen.getAllByTestId("key-unsure")).toHaveLength(1));
      expect(resolves(calls)).toEqual([
        ["r-1", "skip"],
        ["r-2", action],
      ]);
      view.unmount();
    }
  });

  it("the key's save failing leaves no key and keeps the typed text, and Save finishes the job", async () => {
    const failing = new Set(["r-2"]);
    const onKeysChanged = vi.fn();
    const { api, calls } = sidecar(["q-2"], [unsure("r-1", "q-1"), unsure("r-2", "q-1")], failing);
    render(<KeysPanel api={api} testId="T-0001" onKeysChanged={onKeysChanged} />);
    fireEvent.click(await screen.findByTestId("key-add"));
    pick("1");
    typeAndSave("D");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getAllByTestId("key-row")).toHaveLength(1); // no key was written
    expect(screen.getByTestId("key-input")).toHaveValue("D");
    expect(onKeysChanged).not.toHaveBeenCalled();

    failing.clear();
    await waitFor(() => expect(calls.filter((c) => c.path === "/tests/T-0001/keys").length).toBe(2)); // reloaded
    fireEvent.click(screen.getByTestId("key-save"));
    await waitFor(() => expect(screen.getAllByTestId("key-row")).toHaveLength(2));
    expect(resolves(calls)).toEqual([
      ["r-1", "skip"],
      ["r-2", "fix"],
      ["r-2", "fix"],
    ]);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(onKeysChanged).toHaveBeenCalledTimes(1);
  });

  it("the first close failing changes nothing, and the editor stays", async () => {
    const { api, calls } = sidecar(["q-1"], [unsure("r-1", "q-1"), unsure("r-2", "q-1")], new Set(["r-1"]));
    render(<KeysPanel api={api} testId="T-0001" />);
    await screen.findByTestId("key-unsure");
    fireEvent.click(screen.getByTestId("key-edit"));
    typeAndSave("B");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(resolves(calls)).toEqual([["r-1", "skip"]]);
    expect(screen.getByTestId("key-input")).toHaveValue("B");
    expect(screen.getByTestId("key-accepted")).toHaveTextContent("A");
  });
});

describe("R3.2: no Add key when every graded question has a key", () => {
  it("shows no button, even with a question left in a section that is not graded", async () => {
    const { api } = sidecar(["q-1", "q-2", "q-3", "q-4"]);
    render(<KeysPanel api={api} testId="T-0001" />);
    await screen.findAllByTestId("key-row");
    expect(screen.queryByTestId("key-add")).toBeNull();
  });

  it("the button goes once the last question has its key", async () => {
    const { api } = sidecar(["q-1", "q-2", "q-3"]);
    render(<KeysPanel api={api} testId="T-0001" />);
    fireEvent.click(await screen.findByTestId("key-add"));
    pick("14");
    typeAndSave("B");
    await waitFor(() => expect(screen.queryByTestId("key-add")).toBeNull());
    expect(screen.queryByTestId("key-add-panel")).toBeNull();
    await waitFor(() => expect(screen.getByTestId("key-print")).toHaveFocus());
  });
});

describe("R3.3: delete key", () => {
  const panel = (api: ReturnType<typeof sidecar>["api"], onKeysChanged?: () => void) =>
    render(
      <ConfirmProvider>
        <KeysPanel api={api} testId="T-0001" onKeysChanged={onKeysChanged} />
      </ConfirmProvider>,
    );
  const rowOf = (id: string) => screen.getAllByTestId("key-row").find((r) => r.dataset.questionId === id)!;

  it("asks first, naming the printed number and what happens next", async () => {
    const { api, calls } = sidecar(["q-1", "q-3"]);
    panel(api);
    await screen.findAllByTestId("key-row");
    fireEvent.click(within(rowOf("q-3")).getByTestId("key-delete"));
    const dialog = await screen.findByTestId("confirm-dialog");
    expect(dialog).toHaveTextContent("Delete the key for question 13?");
    expect(dialog).toHaveTextContent(DELETE_KEY_BODY);
    expect(DELETE_KEY_BODY).toMatch(/new AI key/);
    expect(DELETE_KEY_BODY).toMatch(/student answers on this test are graded.*leave the Key tab/);
    expect(DELETE_KEY_BODY).not.toMatch(/(?<!student )answers/);
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
  });

  it("Keep key deletes nothing", async () => {
    const onKeysChanged = vi.fn();
    const { api, calls } = sidecar(["q-1"]);
    panel(api, onKeysChanged);
    fireEvent.click(await screen.findByTestId("key-delete"));
    fireEvent.click(await screen.findByTestId("confirm-cancel"));
    await waitFor(() => expect(screen.queryByTestId("confirm-dialog")).toBeNull());
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    expect(onKeysChanged).not.toHaveBeenCalled();
    expect(screen.getByTestId("key-row")).toBeInTheDocument();
  });

  it("deletes, reloads, tells the shell, and the question is offered by Add key", async () => {
    const onKeysChanged = vi.fn();
    const { api, calls } = sidecar(["q-1", "q-2", "q-3", "q-4"]);
    panel(api, onKeysChanged);
    await screen.findAllByTestId("key-row");
    expect(screen.queryByTestId("key-add")).toBeNull();
    fireEvent.click(within(rowOf("q-3")).getByTestId("key-delete"));
    fireEvent.click(await screen.findByTestId("confirm-ok"));
    await waitFor(() => expect(screen.getAllByTestId("key-row")).toHaveLength(3));
    expect(calls.find((c) => c.method === "DELETE")?.path).toBe("/tests/T-0001/keys/q-3");
    expect(onKeysChanged).toHaveBeenCalledTimes(1);
    const add = screen.getByTestId("key-add");
    await waitFor(() => expect(add).toHaveFocus());
    fireEvent.click(add);
    expect(numbersOffered()).toEqual(["13"]);
  });

  it("keeps a key being typed for another row, with focus back in it", async () => {
    const { api } = sidecar(["q-1", "q-2"]);
    panel(api);
    await screen.findAllByTestId("key-row");
    fireEvent.click(within(rowOf("q-2")).getByTestId("key-edit"));
    fireEvent.change(screen.getByTestId("key-input"), { target: { value: "half typed" } });
    fireEvent.click(within(rowOf("q-1")).getByTestId("key-delete"));
    fireEvent.click(await screen.findByTestId("confirm-ok"));
    await waitFor(() => expect(screen.getAllByTestId("key-row")).toHaveLength(1));
    expect(screen.getByTestId("key-input")).toHaveValue("half typed");
    await waitFor(() => expect(screen.getByTestId("key-input")).toHaveFocus());
  });

  it("keeps a key being typed in Add key, and offers the deleted question too", async () => {
    const { api } = sidecar(["q-1", "q-2"]);
    panel(api);
    fireEvent.click(await screen.findByTestId("key-add"));
    pick("13");
    fireEvent.change(screen.getByTestId("key-input"), { target: { value: "half typed" } });
    fireEvent.click(within(rowOf("q-1")).getByTestId("key-delete"));
    fireEvent.click(await screen.findByTestId("confirm-ok"));
    await waitFor(() => expect(numbersOffered()).toEqual(["1", "13", "14"]));
    expect(screen.getByLabelText("Key for question 13")).toHaveValue("half typed");
  });

  it("closes the deleted question's own editor", async () => {
    const { api } = sidecar(["q-1", "q-2"]);
    panel(api);
    await screen.findAllByTestId("key-row");
    fireEvent.click(within(rowOf("q-1")).getByTestId("key-edit"));
    fireEvent.click(within(rowOf("q-1")).getByTestId("key-delete"));
    fireEvent.click(await screen.findByTestId("confirm-ok"));
    await waitFor(() => expect(screen.getAllByTestId("key-row")).toHaveLength(1));
    expect(screen.queryByTestId("key-input")).toBeNull();
  });

  it("does not bring back an Add key that its last save emptied", async () => {
    const { api } = sidecar(["q-1", "q-2", "q-3"]);
    panel(api);
    fireEvent.click(await screen.findByTestId("key-add"));
    pick("14");
    typeAndSave("B");
    await waitFor(() => expect(screen.queryByTestId("key-add")).toBeNull());
    fireEvent.click(within(rowOf("q-1")).getByTestId("key-delete"));
    fireEvent.click(await screen.findByTestId("confirm-ok"));
    await waitFor(() => expect(screen.getByTestId("key-add")).toBeInTheDocument());
    expect(screen.queryByTestId("key-add-panel")).toBeNull();
  });

  it("the row's unsure note goes with the key", async () => {
    const { api } = sidecar(["q-1", "q-2"], [unsure("r-1", "q-1")]);
    panel(api);
    await screen.findByTestId("key-unsure");
    fireEvent.click(within(rowOf("q-1")).getByTestId("key-delete"));
    fireEvent.click(await screen.findByTestId("confirm-ok"));
    await waitFor(() => expect(screen.queryByTestId("key-unsure")).toBeNull());
  });

  it("keeps the row and shows the error when the delete fails", async () => {
    const onKeysChanged = vi.fn();
    const { api } = fakeApi({
      "GET /tests/{id}/keys": [key("q-1")],
      "GET /tests/{id}": { id: "T-0001", content: CONTENT, review: [] },
      "DELETE /tests/{id}/keys/{question_id}": new FakeStatus(404, { detail: "no key row for q-1" }),
    });
    panel(api, onKeysChanged);
    fireEvent.click(await screen.findByTestId("key-delete"));
    fireEvent.click(await screen.findByTestId("confirm-ok"));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByTestId("key-row")).toBeInTheDocument();
    expect(onKeysChanged).not.toHaveBeenCalled();
  });

  it("names the question for a screen reader", async () => {
    const { api } = sidecar(["q-3"]);
    panel(api);
    expect(await screen.findByRole("button", { name: "Delete the key for question 13" })).toBeInTheDocument();
  });
});

describe("R3.5: the print shows the changed keys, without the new controls", () => {
  it("both controls are no-print, and the key list follows the change", async () => {
    const { api } = sidecar(["q-1", "q-2"]);
    render(<KeysPanel api={api} testId="T-0001" />);
    const del = (await screen.findAllByTestId("key-delete"))[0]!;
    expect(del.closest(".no-print")).not.toBeNull();
    expect(screen.getByTestId("key-add").closest(".no-print")).not.toBeNull();
    fireEvent.click(screen.getByTestId("key-add"));
    expect(screen.getByTestId("key-add-panel")).toHaveClass("no-print");
    pick("13");
    typeAndSave("Z");
    const list = screen.getByTestId("key-list");
    await waitFor(() => expect(list).toHaveTextContent("Z"));
    fireEvent.click(del); // no provider: the default dialog says yes
    await waitFor(() => expect(within(list).getAllByTestId("key-row")).toHaveLength(2));
    expect(list).toHaveTextContent("13.");
    expect(list).not.toHaveTextContent("1.A");
  });
});
