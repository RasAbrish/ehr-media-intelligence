import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against the real API and the Vite dev server (`make e2e`).
 * Both servers are reused when already running (`make dev`); the API needs an indexed
 * database (`make pipeline`).
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:5173", trace: "retain-on-failure" },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
  ],
  webServer: [
    {
      command: "uv run --project ../backend ehr-mip serve --port 8000",
      url: "http://localhost:8000/health",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "pnpm dev",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
