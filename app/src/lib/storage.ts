/**
 * `sessionStorage` JSON helpers that never throw (a private window, blocked site data or a
 * full quota just means "nothing stored"). Per-tab state that should survive the page reload
 * after a sidecar restart (step 14), e.g. the open thread and the photo check drafts.
 */
export function readSession<T>(key: string): T | null {
  try {
    const raw = window.sessionStorage.getItem(key);
    return raw === null ? null : (JSON.parse(raw) as T);
  } catch {
    return null;
  }
}

export function writeSession(key: string, value: unknown): void {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable: the in-memory state still works */
  }
}

export function removeSession(key: string): void {
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}
