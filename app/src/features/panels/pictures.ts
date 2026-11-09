/**
 * Picture placeholders (PRD D11): `[Hình: files/<id[:2]>/<id>.<ext> · trang <n>]`, the same text
 * as the sidecar's `etach.domain.pictures.render_picture` (whose default extension is also "jpg").
 * A picture's `file_id` is the sha256 of the page image. `GET /tests/{id}` returns
 * `picture_paths` (`file_id` → stored path `files/ab/<id>.<ext>`, llm-design v4.10), so the
 * placeholder names the real file; without a path the extension defaults to "jpg".
 */
export const PLACEHOLDER_RE = /^\[Hình: files\/[0-9a-f]{2}\/[0-9a-f]{64}\.\w+ · trang \d+\]$/;

export function picturePlaceholder(fileId: string, pageNo: number, ext = "jpg"): string {
  const e = ext.replace(/^\./, "").toLowerCase();
  return `[Hình: files/${fileId.slice(0, 2)}/${fileId}.${e} · trang ${pageNo}]`;
}

/** The placeholder for a stored picture, using its stored path from `picture_paths` when known. */
export function pictureLabel(
  ref: { file_id: string; page_no: number },
  paths?: Record<string, string> | null,
): string {
  const path = paths?.[ref.file_id];
  const m = path ? /^files\/[0-9a-f]{2}\/[0-9a-f]+\.(\w+)$/.exec(path) : null;
  return picturePlaceholder(ref.file_id, ref.page_no, m ? m[1] : undefined);
}
