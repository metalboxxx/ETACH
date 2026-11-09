// R22.3.4.3: the Key panel lists a sentence key's accepted forms; removing one and saving keeps it
// removed; editing the key text remakes the forms (the sidecar's rule, faked here).
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fakeApi, type FakeCall } from "@/lib/testApi";
import { KeysPanel } from "./KeysPanel";

const FOUR = [
  "My brother used to stay up late playing mobile games.",
  "My brother used to stay up late playing mobile games",
  "used to stay up late playing mobile games.",
  "used to stay up late playing mobile games",
];

const test_ = {
  id: "T-0001",
  meta: { edited_fields: [] },
  content: {
    sections: [
      {
        id: "s1", number: 1, printed_title: "VIII.", title: "Rewrite", instructions: null, points: 0.5,
        points_source: "printed", skill: "rewrite",
        groups: [{ id: "g1", stimulus: null, pictures: [], questions: [
          { id: "q-37", number: 1, printed_number: 37, page_no: 1, answer_form: "sentence", context: "single",
            stem: "My brother no longer stays up late playing mobile games.", options: [], cue: "My brother ...", points: 0.5 },
        ] }],
      },
    ],
  },
  review: [],
};

const key = (accepted: string[]) => ({
  test_id: "T-0001", question_id: "q-37", accepted, reason_vi: null, source: "ai",
  status: "ai_unverified", confidence: 0.9, updated_at: "2026-10-18T00:00:00Z",
});

/** The sidecar's teacher rule: same first answer → stored as sent; else the forms are remade. */
function serverPut(stored: { accepted: string[] }) {
  return (c: FakeCall) => {
    const sent = (c.body as { accepted: string[] }).accepted;
    if (sent[0] === stored.accepted[0]) stored.accepted = sent;
    else {
      const full = sent[0]!;
      const rest = full.replace(/^My brother /, "");
      stored.accepted = [...new Set([full, full.replace(/\.$/, ""), rest, rest.replace(/\.$/, "")])];
    }
    return { key: { ...key(stored.accepted), source: "teacher_edit", status: "teacher_verified" }, outcome: "updated", explanations_deleted: 0, run_ids: [] };
  };
}

describe("sentence key forms in the Key panel (R22.3.4.3)", () => {
  it("lists the forms; a removed form stays removed after saving", async () => {
    const stored = { accepted: [...FOUR] };
    const { api, calls } = fakeApi({
      "GET /tests/{id}/keys": () => [key(stored.accepted)],
      "GET /tests/{id}": test_,
      "PUT /tests/{id}/keys/{question_id}": serverPut(stored),
    });
    render(<KeysPanel api={api} testId="T-0001" />);
    const row = await screen.findByTestId("key-row");
    expect(within(row).getByTestId("key-accepted")).toHaveTextContent(FOUR.join(" | "));
    fireEvent.click(within(row).getByTestId("key-edit"));
    const forms = screen.getAllByTestId("key-form");
    expect(forms.map((f) => f.firstChild?.textContent)).toEqual(FOUR);
    fireEvent.click(within(forms[3]!).getByRole("button", { name: `Remove “${FOUR[3]}”` }));
    expect(screen.getAllByTestId("key-form")).toHaveLength(3);
    fireEvent.click(screen.getByTestId("key-save"));
    await waitFor(() => expect(screen.queryByTestId("key-editor")).toBeNull());
    expect(calls.find((c) => c.method === "PUT")!.body).toEqual({ accepted: FOUR.slice(0, 3), verify: false });
    expect(within(screen.getByTestId("key-row")).getByTestId("key-accepted")).toHaveTextContent(
      FOUR.slice(0, 3).join(" | "),
    );
    expect(screen.getByTestId("key-accepted").textContent!.split(" | ")).not.toContain(FOUR[3]);
  });

  it("editing the key text remakes the forms", async () => {
    const stored = { accepted: [FOUR[0]!, FOUR[2]!] };
    const { api } = fakeApi({
      "GET /tests/{id}/keys": () => [key(stored.accepted)],
      "GET /tests/{id}": test_,
      "PUT /tests/{id}/keys/{question_id}": serverPut(stored),
    });
    render(<KeysPanel api={api} testId="T-0001" />);
    fireEvent.click(within(await screen.findByTestId("key-row")).getByTestId("key-edit"));
    fireEvent.change(screen.getByTestId("key-input"), { target: { value: "My brother used to stay up very late." } });
    fireEvent.click(screen.getByTestId("key-save"));
    await waitFor(() =>
      expect(screen.getByTestId("key-accepted")).toHaveTextContent(
        "My brother used to stay up very late. | My brother used to stay up very late | used to stay up very late. | used to stay up very late",
      ),
    );
  });
});
