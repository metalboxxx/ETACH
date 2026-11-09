/**
 * "Save as Word (.docx)" beside Print in the Test, Key and Report workspaces (step 22.1.6, PRD D4
 * v5.0). A click calls the panel's export route; the sidecar writes the file into `<app>\exports\`
 * and never overwrites. Afterwards "Saved <file name>" with **Open folder**, which asks the shell
 * to open that one folder (`open_exports_folder`, no argument). Outside the app window (the web
 * build, headless E2E) the shell is not there and Open folder is not called.
 */
import { useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { errorText } from "@/lib/errors";

export interface SavedFile {
  path: string;
  file_name: string;
}

export interface SaveAsWordProps {
  /** Calls the export route. */
  save: () => Promise<SavedFile>;
  /** Names what is saved, for screen readers ("test", "key", "grade report"). */
  what: string;
  disabled?: boolean;
  /** Why the button is disabled (an id of a hint already on the page). */
  describedBy?: string;
  testId?: string;
}

type State =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "saved"; fileName: string }
  | { kind: "error"; message: string };

export async function openExportsFolder(): Promise<void> {
  if (!isTauri()) throw new Error("Open folder works in the app window only.");
  await invoke("open_exports_folder");
}

export function SaveAsWord({ save, what, disabled = false, describedBy, testId = "save-docx" }: SaveAsWordProps) {
  const [state, setState] = useState<State>({ kind: "idle" });
  const [folderError, setFolderError] = useState<string | null>(null);

  const onSave = async () => {
    setState({ kind: "saving" });
    setFolderError(null);
    try {
      const file = await save();
      setState({ kind: "saved", fileName: file.file_name });
    } catch (err) {
      setState({ kind: "error", message: `Could not save the ${what} as Word: ${errorText(err)}` });
    }
  };

  const onOpen = async () => {
    setFolderError(null);
    try {
      await openExportsFolder();
    } catch (err) {
      setFolderError(`Could not open the folder: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const saving = state.kind === "saving";
  return (
    <>
      <button
        type="button"
        data-testid={testId}
        disabled={disabled || saving}
        aria-busy={saving || undefined}
        aria-describedby={describedBy}
        onClick={() => void onSave()}
        className="main-label rounded-button border border-border px-3 py-1 hover:bg-hover disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save as Word (.docx)"}
      </button>
      {/* Always rendered (never display:none), so screen readers announce "Saved …" (step 22.2.2). */}
      <span
        role="status"
        aria-atomic="true"
        data-testid="save-docx-status"
        className="flex flex-wrap items-center gap-2 text-sm empty:sr-only"
      >
        {state.kind === "saved" && (
          <span data-testid="save-docx-saved" className="flex flex-wrap items-center gap-2">
            <span>
              Saved <span className="font-medium break-all">{state.fileName}</span>
            </span>
            <button
              type="button"
              data-testid="save-docx-open"
              onClick={() => void onOpen()}
              className="rounded-button border border-border px-2 py-0.5 text-sm hover:bg-hover"
            >
              Open folder
            </button>
          </span>
        )}
      </span>
      {state.kind === "error" && (
        <span role="alert" data-testid="save-docx-error" className="basis-full text-sm text-danger">
          {state.message}
        </span>
      )}
      {folderError && (
        <span role="alert" data-testid="save-docx-folder-error" className="basis-full text-sm text-danger">
          {folderError}
        </span>
      )}
    </>
  );
}
