/**
 * The Settings gear (PRD §10.1 v8.21, the teacher): an outline drawn to sit beside Faustina text,
 * since Faustina has no ⚙ (it fell back to Segoe UI Symbol). A thin stroke in the text colour
 * (currentColor), about the text's cap height; decorative, so the word "Settings" is the label.
 */
export function GearIcon() {
  return (
    <svg
      aria-hidden="true"
      data-testid="gear-icon"
      viewBox="0 0 24 24"
      width="1em"
      height="1em"
      className="h-[0.8em] w-[0.8em] shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinejoin="round"
    >
      <path d="M19.21 9.61L21.80 10.01L21.80 13.99L19.21 14.39L18.79 15.41L20.33 17.53L17.53 20.33L15.41 18.79L14.39 19.21L13.99 21.80L10.01 21.80L9.61 19.21L8.59 18.79L6.47 20.33L3.67 17.53L5.21 15.41L4.79 14.39L2.20 13.99L2.20 10.01L4.79 9.61L5.21 8.59L3.67 6.47L6.47 3.67L8.59 5.21L9.61 4.79L10.01 2.20L13.99 2.20L14.39 4.79L15.41 5.21L17.53 3.67L20.33 6.47L18.79 8.59Z" />
      <circle cx="12" cy="12" r="3.2" />
    </svg>
  );
}
