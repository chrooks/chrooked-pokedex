import { defineConfig } from "vitest/config";

// The logic under test (boolean evaluator, multi-key sort, URL codec) is pure —
// no DOM, no React — so the lightweight Node environment is enough.
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
