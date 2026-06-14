import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

// Flat config. The point of having it at all (per review): make the
// rules-of-hooks and exhaustive-deps checks enforceable, so dep-array drift is
// caught in the editor and in CI instead of in production.
export default tseslint.config(
  { ignores: ["dist", "node_modules", "*.config.js", "vite.config.*"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-hooks/exhaustive-deps": "error",
      // Honor the leading-underscore convention for intentionally-unused args,
      // matching tsc's noUnusedParameters so the two tools agree.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
);
