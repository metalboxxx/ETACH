/**
 * Starts the replay sidecar once for the run; the returned function is the teardown.
 * `--replay-delay-ms` (hidden, made for this) slows each replayed model call so R15.4 can stop
 * the S1 run part-way.
 */
import { startSidecar } from "./sidecar";

export const REPLAY_DELAY_MS = 700;

export default async function globalSetup(): Promise<() => Promise<void>> {
  const sidecar = await startSidecar(90_000, ["--replay-delay-ms", String(REPLAY_DELAY_MS)]);
  // Workers start after global setup and inherit these.
  process.env.ETACH_E2E_PORT = String(sidecar.port);
  process.env.ETACH_E2E_TOKEN = sidecar.token;
  process.env.ETACH_E2E_DATA = sidecar.dataDir;
  return () => sidecar.stop();
}
