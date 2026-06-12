import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During dev the SPA runs on Vite's server and the API on the FastAPI server
// (default :8000). Proxy /api there so the browser sees a single origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    // `chrooked-pokedex ui` serves this directory when it exists.
    outDir: "dist",
  },
});
