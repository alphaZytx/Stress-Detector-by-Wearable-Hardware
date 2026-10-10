/// <reference types="vitest" />
import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  build: {
    rollupOptions: {
      output: {
        // Isolate the charting stack from the main app bundle and split its
        // heavy transitive deps (d3 via victory-vendor, lodash) into their own
        // chunks so no single chunk exceeds Vite's 500 KB warning threshold.
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (id.includes("victory-vendor") || id.includes("/d3-")) return "d3";
            if (id.includes("lodash")) return "lodash";
            if (id.includes("recharts") || id.includes("react-smooth")) return "recharts";
          }
        },
      },
    },
  },
  server: {
    port: 5173,
    strictPort: false,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    css: false,
  },
});
