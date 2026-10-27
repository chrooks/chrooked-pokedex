import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { runtimeCaching } from "./src/pwa/caching";

// During dev the SPA runs on Vite's server and the API on the FastAPI server
// (default :8000). Proxy /api there so the browser sees a single origin.
const API = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [
    react(),
    // #122: installable, works offline. The SPA shell is precached; API reads
    // and sprites are runtime-cached by the rules in src/pwa/caching.ts, which
    // "Save for offline" warms. The service worker exists only in a build —
    // dev keeps plain fetches so a stale cache can never mask a code change.
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["apple-touch-icon.png"],
      manifest: {
        name: "chrooked-pokedex",
        short_name: "pokedex",
        description: "The chrooked Ruleset dex",
        theme_color: "#171512",
        background_color: "#171512",
        display: "standalone",
        icons: [
          { src: "pwa-192.png", sizes: "192x192", type: "image/png" },
          { src: "pwa-512.png", sizes: "512x512", type: "image/png" },
          { src: "pwa-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,png,svg,woff2,json}"],
        // Deep links fall back to the shell; API paths must 404 honestly.
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching,
      },
    }),
  ],
  server: {
    proxy: { "/api": API },
  },
  // `vite preview` serves the built dist with the service worker live — the
  // offline e2e proof (e2e/offline.spec.ts) drives it against the real API.
  preview: {
    port: 5175,
    strictPort: true,
    proxy: { "/api": API },
  },
  build: {
    // `chrooked-pokedex ui` serves this directory when it exists.
    outDir: "dist",
  },
});
