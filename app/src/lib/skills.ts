/**
 * Step 22.5.5b (D11, D11c): a skill's trajectory label in plain words, for the Students tab and
 * the report's weak points.
 */
export type SkillLabel =
  | "improved"
  | "slipped"
  | "consistently_weak"
  | "inconsistent"
  | "solid"
  | "not_enough_evidence"
  | "this_paper_only";

export const SKILL_LABEL: Record<SkillLabel, string> = {
  improved: "Improved",
  slipped: "Slipped",
  inconsistent: "Inconsistent",
  consistently_weak: "Consistently weak",
  not_enough_evidence: "Not enough evidence yet",
  solid: "Solid",
  this_paper_only: "This paper only",
};

export function skillLabel(label: string | null | undefined): string | null {
  return label ? (SKILL_LABEL[label as SkillLabel] ?? label) : null;
}

/** Today as `YYYY-MM-DD` in the local time zone (a date input's value). */
export function todayIso(now: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`;
}

/** `2026-10-24` → "24 Oct 2026" (the date as shown; the input keeps the ISO form). */
export function showDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${d} ${months[m - 1]} ${y}`;
}
