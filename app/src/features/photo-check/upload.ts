/**
 * Dropped / pasted / added files → `POST /files` (raw bytes, `?name=`) → `PageInput`s, in the
 * order the files were given. A PDF gives one page per PDF page; a DOCX a text page plus one
 * page per picture (the sidecar decides; nothing is split here).
 */
import { type ApiClient } from "@/api/client";
import type { PageInput } from "./draft";
import { errorText } from "@/lib/errors";

/** The file types the drop zone, "Choose files…" and the photo check's + take (one list). */
export const ACCEPTED_FILES = "image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp,.pdf,.docx";

export interface UploadOutcome {
  pages: PageInput[];
  /** One line per file the sidecar refused (e.g. 415 for HEIC). */
  errors: string[];
}

export async function uploadFiles(api: ApiClient, files: readonly File[]): Promise<UploadOutcome> {
  const pages: PageInput[] = [];
  const errors: string[] = [];
  for (const file of files) {
    try {
      const res = await api.uploadFile(file, file.name || "pasted.png");
      pages.push(...res.pages);
    } catch (err) {
      const detail = errorText(err);
      errors.push(`${file.name || "pasted file"}: ${detail}`);
    }
  }
  return { pages, errors };
}

/** True when a drag carries files from outside (not a thumbnail being reordered). */
export function dragHasFiles(dt: DataTransfer | null): boolean {
  if (!dt) return false;
  return Array.from(dt.types ?? []).includes("Files");
}
