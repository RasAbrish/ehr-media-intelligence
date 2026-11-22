import { defineConfig, devices } from "@playwright/test";

import { SESSION_FILE } from "./e2e/session.ts";

const API_PORT = "8010";
const WEB_PORT = "5183";
/** Set to test a stack that is already running (docker compose in CI). */
const external = process.env.E2E_BASE_URL;

/**
 * End-to-end tests against the real API (`make e2e`). The tests start their own servers on
 * their own ports over a throwaway copy of the data, so they never write to what `make dev`
 * serves. Needs an indexed database (`make pipeline`).
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 2,
  reporter: [["list"]],
  use: { baseURL: external ?? `http://localhost:${WEB_PORT}`, trace: "retain-on-failure" },
  projects: [
    // Signs in once through the page; the other tests reuse that session.
    { name: "setup", testMatch: /auth\.setup\.ts$/ },
    {
      name: "chromium",
      dependencies: ["setup"],
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
        storageState: SESSION_FILE,
      },
    },
  ],
  ...(external
    ? {}
    : {
        webServer: [
          {
            command: `uv run --project ../backend python ../scripts/e2e_api.py --port ${API_PORT}`,
            url: `http://127.0.0.1:${API_PORT}/health`,
            reuseExistingServer: false,
            gracefulShutdown: { signal: "SIGTERM" as const, timeout: 5000 },
            timeout: 120_000,
          },
          {
            command: `pnpm exec vite --port ${WEB_PORT} --strictPort`,
            env: { API_PROXY_TARGET: `http://127.0.0.1:${API_PORT}` },
            url: `http://localhost:${WEB_PORT}`,
            reuseExistingServer: false,
            timeout: 60_000,
          },
        ],
      }),
});
