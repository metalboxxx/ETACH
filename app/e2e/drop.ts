/**
 * A synthetic HTML5 file drop: builds a DataTransfer with the files in the page and dispatches
 * dragenter / dragover / drop on the conversation, as WebView2 does once Tauri's own drop
 * handling is off (`disable_drag_drop_handler`, step 15). The real OS drop is R15.2 (E2E_SHELL).
 */
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import type { Page } from "@playwright/test";

const TYPES: Record<string, string> = {
  png: "image/png",
  jpg: "image/jpeg",
  pdf: "application/pdf",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};

export function connect(page: Page) {
  const port = process.env.ETACH_E2E_PORT;
  const token = process.env.ETACH_E2E_TOKEN;
  if (!port || !token) throw new Error("global setup did not start the sidecar");
  return page.goto(`/#port=${port}&token=${token}`);
}

export async function dropFiles(page: Page, paths: readonly string[], target = '[data-testid="conversation"]') {
  const files = paths.map((p) => {
    const name = basename(p);
    const ext = name.split(".").pop()?.toLowerCase() ?? "";
    return { name, type: TYPES[ext] ?? "application/octet-stream", b64: readFileSync(p).toString("base64") };
  });
  const dt = await page.evaluateHandle((list) => {
    const transfer = new DataTransfer();
    for (const f of list) {
      const bytes = Uint8Array.from(atob(f.b64), (c) => c.charCodeAt(0));
      transfer.items.add(new File([bytes], f.name, { type: f.type }));
    }
    return transfer;
  }, files);
  const el = page.locator(target);
  await el.dispatchEvent("dragenter", { dataTransfer: dt });
  await el.dispatchEvent("dragover", { dataTransfer: dt });
  await el.dispatchEvent("drop", { dataTransfer: dt });
}
