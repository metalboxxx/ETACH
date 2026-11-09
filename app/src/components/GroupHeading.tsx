/**
 * A group heading in the sidebar lists (PRD §10.1 v8.21): centred small capitals, bold, in the text
 * colour, with a short rule under it, like the motto line under the ETACH wordmark. Used by the
 * Chats list (the student names); the Tests and Students lists stay ungrouped (the teacher).
 */
export function GroupHeading({ children }: { children: string }) {
  return (
    <div className="flex flex-col items-center pb-1" data-testid="group-heading">
      <h3 className="px-1 text-center text-sm font-semibold tracking-[0.04em] text-text [font-variant-caps:small-caps]">
        {children}
      </h3>
      <span aria-hidden="true" data-testid="group-rule" className="mt-0.5 h-px w-10 bg-text" />
    </div>
  );
}
