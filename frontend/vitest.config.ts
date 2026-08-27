import { defineConfig } from "vitest/config";

// The logic under test (boolean evaluator, multi-key sort, URL codec) is pure —
// no DOM, no React — so the lightweight Node environment is enough.
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
    // One test imports a stylesheet with `?raw` to pin a threshold that lives in
    // both TS and CSS. Without this the import resolves to an empty string and
    // the guard passes vacuously — worse than not having it.
    css: true,
  },
});
