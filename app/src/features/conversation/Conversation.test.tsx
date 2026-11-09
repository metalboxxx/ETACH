// R22.2.2.3: "Choose files…" on the new-thread screen takes the drop zone's file types, and chosen
// files go to the same `onFiles` as dropped ones (one upload path).
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ACCEPTED_FILES } from "@/features/photo-check/upload";
import { Conversation } from "./Conversation";

describe("Choose files… (R22.2.2.3)", () => {
  it("opens a file input with the drop zone's accepted types", () => {
    render(<Conversation onFiles={() => {}} empty />);
    const input = screen.getByTestId("choose-files-input") as HTMLInputElement;
    expect(input.accept).toBe(ACCEPTED_FILES);
    expect(input.multiple).toBe(true);
    const click = vi.spyOn(input, "click");
    fireEvent.click(screen.getByRole("button", { name: "Choose files…" }));
    expect(click).toHaveBeenCalledTimes(1);
  });

  it("sends chosen and dropped files through the same function", () => {
    const onFiles = vi.fn();
    render(<Conversation onFiles={onFiles} empty />);
    const chosen = new File(["a"], "p1.jpg", { type: "image/jpeg" });
    const dropped = new File(["b"], "p2.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByTestId("choose-files-input"), { target: { files: [chosen] } });
    fireEvent.drop(screen.getByTestId("conversation"), { dataTransfer: { files: [dropped], types: ["Files"] } });
    expect(onFiles.mock.calls).toEqual([[[chosen]], [[dropped]]]);
  });

  it("is not shown without a place to send files", () => {
    render(<Conversation empty />);
    expect(screen.queryByTestId("choose-files")).toBeNull();
  });
});
