// R22.1.1.3 (comment 10, "Occasion can't be filled"): typing an occasion in the test panel and
// leaving the field saves it (PATCH /tests/{id}) and GET /tests/{id} returns it.
//
// The fake sidecar below validates `occasion` exactly as `TestMetadata._check_occasion` does
// (sidecar/src/etach/domain/models.py): one of the OCCASIONS codes or "Other:<text>", else 422.
// Before the fix the chip sent the typed words as they were ("Giữa kỳ 1"), the sidecar refused
// them with 422, and the chip went back to its old value.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fakeApi, FakeStatus, type FakeCall } from "@/lib/testApi";
import { OCCASIONS, TestPanel } from "./TestPanel";

const SIDECAR_OCCASIONS = [
  "MidTerm",
  "FinalTerm",
  "NationalExam",
  "EntranceExam",
  "GiftedExam",
  "UnitTest",
  "FifteenMinuteTest",
  "GrammarPractice",
  "TopicPractice",
  "Placement",
];

function sidecar(occasion: string) {
  const stored = {
    id: "T-0001",
    meta: { occasion, grade: 8, term: 1, edited_fields: [] as string[] },
    content: { sections: [] },
    picture_paths: {},
  };
  const valid = (v: unknown) => typeof v === "string" && (SIDECAR_OCCASIONS.includes(v) || /^Other:\S.*$/.test(v));
  return fakeApi({
    "GET /tests/{id}": () => stored,
    "PATCH /tests/{id}": (call: FakeCall) => {
      const meta = (call.body as { meta: Record<string, unknown> }).meta;
      if ("occasion" in meta && !valid(meta.occasion)) {
        return new FakeStatus(422, {
          detail: [{ loc: ["occasion"], msg: "Value error, occasion must be one of … or 'Other:<text>'" }],
        });
      }
      Object.assign(stored.meta, meta);
      stored.meta.edited_fields = [...new Set([...stored.meta.edited_fields, ...Object.keys(meta)])];
      return stored;
    },
  });
}

async function typeOccasion(text: string) {
  const chip = (await screen.findAllByTestId("meta-chip")).find((c) => c.dataset.field === "occasion")!;
  fireEvent.click(chip);
  const input = screen.getByTestId("meta-chip-input");
  fireEvent.change(input, { target: { value: text } });
  fireEvent.blur(input); // leaving the field saves
}

const occasionChip = () => screen.getAllByTestId("meta-chip").find((c) => c.dataset.field === "occasion")!;

describe("the Occasion field (R22.1.1.3)", () => {
  it("the panel offers the sidecar's occasions", () => {
    expect([...OCCASIONS]).toEqual(SIDECAR_OCCASIONS);
  });

  it("typed words are saved (as Other:<words>) and GET /tests/{id} returns them", async () => {
    const { api, calls } = sidecar("Other:unknown");
    render(<TestPanel api={api} testId="T-0001" />);
    await typeOccasion("Giữa kỳ 1");
    await waitFor(() => expect(occasionChip()).toHaveTextContent("Giữa kỳ 1"));
    expect(screen.queryByRole("alert")).toBeNull();
    const patch = calls.find((c) => c.method === "PATCH")!;
    expect(patch.body).toEqual({ meta: { occasion: "Other:Giữa kỳ 1" } });
    const got = await api.get("/tests/{id}", { path: { id: "T-0001" } });
    expect(got.meta.occasion).toBe("Other:Giữa kỳ 1");
  });

  it("an occasion's name in any case becomes its code", async () => {
    const { api, calls } = sidecar("Other:unknown");
    render(<TestPanel api={api} testId="T-0001" />);
    await typeOccasion("  midterm ");
    await waitFor(() => expect(occasionChip()).toHaveTextContent("Mid-term test"));
    expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ meta: { occasion: "MidTerm" } });
    expect((await api.get("/tests/{id}", { path: { id: "T-0001" } })).meta.occasion).toBe("MidTerm");
  });

  it("Other: typed by the teacher is kept as it is", async () => {
    const { api, calls } = sidecar("FinalTerm");
    render(<TestPanel api={api} testId="T-0001" />);
    await typeOccasion("other: Olympic");
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ meta: { occasion: "Other:Olympic" } });
  });

  it("a blank occasion is not sent (the occasion is required); the chip keeps its value", async () => {
    const { api, calls } = sidecar("FinalTerm");
    render(<TestPanel api={api} testId="T-0001" />);
    await typeOccasion("   ");
    expect(calls.some((c) => c.method === "PATCH")).toBe(false);
    expect(occasionChip()).toHaveTextContent("Final-term test");
  });

  it("Enter saves once (the field closing does not save it twice)", async () => {
    const { api, calls } = sidecar("FinalTerm");
    render(<TestPanel api={api} testId="T-0001" />);
    const chip = (await screen.findAllByTestId("meta-chip")).find((c) => c.dataset.field === "occasion")!;
    fireEvent.click(chip);
    const input = screen.getByTestId("meta-chip-input");
    fireEvent.change(input, { target: { value: "UnitTest" } });
    fireEvent.keyDown(input, { key: "Enter" });
    fireEvent.blur(input);
    await waitFor(() => expect(occasionChip()).toHaveTextContent("Unit test"));
    expect(calls.filter((c) => c.method === "PATCH")).toHaveLength(1);
  });
});

describe("occasions in plain English (R22.2.1.4, answer 1)", () => {
  it("every occasion has a label; Other:<text> shows only the text", async () => {
    const { OCCASION_LABEL, occasionLabel, toOccasion } = await import("./TestPanel");
    for (const o of OCCASIONS) expect(OCCASION_LABEL[o]).toMatch(/^[A-Z0-9][a-z0-9' -]+$/);
    expect(occasionLabel("FifteenMinuteTest")).toBe("15-minute test");
    expect(occasionLabel("MidTerm")).toBe("Mid-term test");
    expect(occasionLabel("Other:Giữa kỳ 1")).toBe("Giữa kỳ 1");
    for (const o of OCCASIONS) expect(toOccasion(OCCASION_LABEL[o])).toBe(o);
  });

  it("the chip shows the label, and the list offers labels", async () => {
    const { api, calls } = sidecar("FifteenMinuteTest");
    render(<TestPanel api={api} testId="T-0001" />);
    await waitFor(() => expect(occasionChip()).toHaveTextContent("Occasion: 15-minute test"));
    expect(occasionChip().textContent).not.toContain("FifteenMinuteTest");
    await typeOccasion("Mid-term test");
    await waitFor(() => expect(occasionChip()).toHaveTextContent("Occasion: Mid-term test"));
    expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ meta: { occasion: "MidTerm" } });
    fireEvent.click(occasionChip());
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("15-minute test");
    expect(options).not.toContain("FifteenMinuteTest");
  });
});
