/**
 * Step 22.5.4b: the model roles the Models tab shows (llm-design §3.1), in display order, each with
 * a plain name and a one-line description. A role the sidecar adds later still shows, under its key.
 * The display order is the order of work on a new test (refinements D1).
 */
export const DEFAULT_MODEL = "qwen3.5:4b";

export const ROLE_INFO: Record<string, { label: string; description: string }> = {
  // R22.5.7.7: the OCR model reads the test photos (GLM-OCR); the student answers stay on vision
  ocr: { label: "Test reader", description: "Reads the test photos" },
  extraction_check: { label: "Extraction check", description: "Checks and fixes a reading of the pages" },
  vision: { label: "Student answer reader", description: "Reads the student answers from the photos" },
  reasoning: { label: "Grading", description: "Marks student answers and explains the mistakes" },
  grading_check: { label: "Grading check", description: "Double-checks keys the AI wrote" },
};

export const ROLE_ORDER = Object.keys(ROLE_INFO);

/**
 * Roles shown only when the sidecar sends them (R22.5.7.7): `ocr` is absent when `models.toml`
 * sets `photo_reader = "vision"`, and Save must not write it with another role's default tag.
 */
const SHOWN_WHEN_SENT = new Set(["ocr"]);

export function roleLabel(role: string): string {
  return ROLE_INFO[role]?.label ?? role;
}

/** The known roles in display order, then any other role the sidecar sends. */
export function orderedRoles(present: Iterable<string>): string[] {
  const sent = new Set(present);
  const known = ROLE_ORDER.filter((r) => !SHOWN_WHEN_SENT.has(r) || sent.has(r));
  const extra = [...sent].filter((r) => !ROLE_ORDER.includes(r)).sort();
  return [...known, ...extra];
}

/** "a", "a and b", "a, b and c" — the role names in lower case, for a sentence. */
export function roleList(roles: string[]): string {
  const names = [...roles]
    .sort((a, b) => rank(a) - rank(b))
    .map((r) => roleLabel(r).toLowerCase());
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

function rank(role: string): number {
  const i = ROLE_ORDER.indexOf(role);
  return i < 0 ? ROLE_ORDER.length : i;
}
