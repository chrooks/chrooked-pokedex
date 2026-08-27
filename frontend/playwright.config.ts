/* Headless-only Playwright config for the drawer proofs (#88).
   `headless: true` is pinned rather than left to the default so no run can pop
   a browser window on this machine. */

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    headless: true,
    baseURL: "http://localhost:5174",
  },
  webServer: {
    command: "npm run dev -- --port 5174 --strictPort",
    url: "http://localhost:5174/e2e/harness.html",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
