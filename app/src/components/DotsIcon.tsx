/**
 * The row menu's glyph (PRD §10.1 v8.21, the teacher): three horizontal dots, vertically centred,
 * drawn as inline SVG in the text colour (currentColor) to match the Settings gear; decorative,
 * so the button's aria-label names it.
 */
export function DotsIcon() {
  return (
    <svg aria-hidden="true" data-testid="dots-icon" viewBox="0 0 24 24" width="1em" height="1em" className="h-[0.9em] w-[0.9em] shrink-0" fill="currentColor">
      <circle cx="5" cy="12" r="1.7" />
      <circle cx="12" cy="12" r="1.7" />
      <circle cx="19" cy="12" r="1.7" />
    </svg>
  );
}
