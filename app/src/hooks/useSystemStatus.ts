/**
 * `GET /system/status` (llm-design §2), reloaded on SSE `system.changed`. Shared by the sidebar
 * (the other-Ollama warning, R20.4) and the Settings panel. `null` = not loaded or offline.
 */
import { useCallback, useEffect, useState } from "react";
import type { ApiClient, Schemas } from "@/api/client";
import { useEvents } from "@/api/sse";

export type SystemStatus = Schemas["SystemStatus"];

export function useSystemStatus(api: ApiClient): { status: SystemStatus | null; reload: () => void } {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const reload = useCallback(() => {
    api
      .get("/system/status")
      .then(setStatus)
      .catch(() => setStatus(null));
  }, [api]);
  useEffect(() => reload(), [reload]);
  useEvents(() => reload(), ["system.changed"]);
  return { status, reload };
}
