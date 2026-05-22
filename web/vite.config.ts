/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173
  },
  test: {
    environment: "jsdom",
    exclude: ["tests/console/**", "node_modules/**", "dist/**"],
    setupFiles: ["./src/test/setup.ts"]
  }
});
