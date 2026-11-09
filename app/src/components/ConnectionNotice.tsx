/** A calm one-line notice when the sidecar is not configured or the event stream is down. */
import type { StreamStatus } from "@/api/sse";

export type ConnectionState = "none" | StreamStatus;

export function ConnectionNotice({ state }: { state: ConnectionState }) {
  let text: string | null = null;
  if (state === "none") text = "Not connected. Start the app from its shortcut to connect.";
  else if (state === "reconnecting") text = "Reconnecting…";
  if (!text) return null;
  return (
    <div
      role="status"
      data-testid="connection-notice"
      className="border-b border-border bg-surface px-4 py-2 text-center text-sm text-muted"
    >
      {text}
    </div>
  );
}
