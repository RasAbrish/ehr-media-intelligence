import { defineConfig, devices } from "@playwright/test";

/** axe and play functions over the built Storybook (`pnpm test-storybook`, FR-8.4). */
export default defineConfig({
  testDir: "./e2e-storybook",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  reporter: [["list"]],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
  ],
});
