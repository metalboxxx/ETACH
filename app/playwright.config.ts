import { defineConfig, devices } from "@playwright/test";

// R13.3: the web build makes 0 non-localhost requests (e2e/offline.spec.ts).
// global-setup.ts starts `etach serve --replay ../sidecar/tests/cassettes/s1` and stops it afterwards.
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  workers: 1,
  retries: 0,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:4173", ...devices["Desktop Chrome"] },
  webServer: {
    command: "npm run build && npm run preview",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
