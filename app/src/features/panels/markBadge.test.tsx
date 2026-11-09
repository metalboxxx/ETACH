// PRD §10.1 v8.13 (step 22.5.8 (f)): each ✓ in the grade report and the Student answers sits on a
// small green badge with dark text, each ✗ on a brick badge with white text; other marks stay plain.
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkBadge } from "./AnswersPanel";

describe("MarkBadge", () => {
  it("✓ on green with dark text", () => {
    const { container } = render(<MarkBadge mark="✓" />);
    const badge = container.querySelector('[data-badge="correct"]')!;
    expect(badge.textContent).toBe("✓");
    expect(badge.className).toMatch(/\bbg-correct\b/);
    expect(badge.className).toMatch(/\btext-text\b/);
    expect(badge.className).toMatch(/\bprint:bg-transparent\b/);
  });

  it("✗ on brick with white text, black on paper", () => {
    const { container } = render(<MarkBadge mark="✗" />);
    const badge = container.querySelector('[data-badge="wrong"]')!;
    expect(badge.textContent).toBe("✗");
    expect(badge.className).toMatch(/\bbg-wrong\b/);
    expect(badge.className).toMatch(/\btext-on-wrong\b/);
    expect(badge.className).toMatch(/\bprint:text-text\b/);
  });

  it.each(["–", "?", "AI unsure grade", ""])("%j stays plain text", (mark) => {
    const { container } = render(<MarkBadge mark={mark} />);
    expect(container.querySelector("[data-badge]")).toBeNull();
    expect(container.textContent).toBe(mark);
  });
});
