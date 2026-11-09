/**
 * One error text for the whole app (step 22.1.5): an API error in words, never "[object Object]".
 *
 * FastAPI's `detail` can be a string, pydantic's list of `{loc, msg}`, or an object such as the
 * test-text save's `{message, errors: [{line, message}]}` / `{message, drops}` or the content
 * check's `{message, failures: [{message}]}`.
 */
import { ApiError } from "@/api/client";

function detailText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (d && typeof d === "object" && "msg" in d) return String((d as { msg: unknown }).msg);
        if (d && typeof d === "object" && "message" in d) {
          const { line, message } = d as { line?: unknown; message: unknown };
          return typeof line === "number" ? `Line ${line}: ${String(message)}` : String(message);
        }
        return typeof d === "string" ? d : JSON.stringify(d);
      })
      .join("; ");
  }
  if (detail && typeof detail === "object") {
    const o = detail as Record<string, unknown>;
    const parts: string[] = [];
    if (typeof o.message === "string") parts.push(o.message);
    for (const key of ["errors", "failures"]) {
      if (Array.isArray(o[key]) && (o[key] as unknown[]).length) parts.push(detailText(o[key]));
    }
    if (parts.length) return parts.join(" ");
    return JSON.stringify(detail);
  }
  return detail === undefined || detail === null ? "Unknown error" : String(detail);
}

export function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 0) return "The app's helper could not be reached. Try again in a moment.";
    return detailText(err.detail);
  }
  if (err instanceof Error) return err.message;
  return String(err);
}
