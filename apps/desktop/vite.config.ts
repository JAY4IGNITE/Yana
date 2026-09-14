import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@yana/protocol": path.resolve(__dirname, "../../packages/protocol/src"),
      "@yana/shared-types": path.resolve(__dirname, "../../packages/shared-types/src"),
    },
  },
  // Tauri expects a fixed port, fail if that port is not available
  server: {
    port: 5173,
    strictPort: true,
  },
  clearScreen: false,
});
