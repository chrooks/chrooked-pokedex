/* Headless-only Playwright config for the drawer proofs (#88) and the offline
   proof (#122). `headless: true` is pinned rather than left to the default so
   no run can pop a browser window on this machine.

   Two servers: the dev server hosts the component harness; `vite preview`
   hosts the built dist, where the service worker is live. Run `npm run build`
   before the offline spec — preview serves whatever dist holds. */

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
  webServer: [
    {
      command: "npm run dev -- --port 5174 --strictPort",
      url: "http://localhost:5174/e2e/harness.html",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run preview",
      url: "http://localhost:5175/manifest.webmanifest",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
