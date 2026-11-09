/**
 * The OS notification for a finished run (plan step 15, R15.7), wrapped so tests can mock it.
 *
 * In Tauri it goes through `@tauri-apps/plugin-notification` the plugin's way: check
 * `isPermissionGranted()`, ask with `requestPermission()` once if needed, then
 * `sendNotification()`. In a plain browser (no Tauri) `notifyOs` returns false and the caller
 * shows the in-app toast instead.
 */
import { isTauri } from "@tauri-apps/api/core";
import { isPermissionGranted, requestPermission, sendNotification } from "@tauri-apps/plugin-notification";

export interface RunNotice {
  /** The thread name (the notification title). */
  title: string;
  body: string;
}

let permission: Promise<boolean> | null = null;

async function granted(): Promise<boolean> {
  if (await isPermissionGranted()) return true;
  return (await requestPermission()) === "granted";
}

/** Sends the OS notification; false when not in Tauri, or permission was refused. */
export async function notifyOs(notice: RunNotice): Promise<boolean> {
  if (!isTauri()) return false;
  try {
    permission ??= granted();
    if (!(await permission)) {
      permission = null; // ask again next time
      return false;
    }
    sendNotification({ title: notice.title, body: notice.body });
    return true;
  } catch {
    return false;
  }
}
