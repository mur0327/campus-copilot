/// <reference types="vitest" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import { mockKioskApiPlugin } from "./vite.mock-api";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd());
  const useMockApi = env.VITE_USE_MOCK_API === "true";

  return {
    plugins: [useMockApi ? mockKioskApiPlugin() : null, react(), tailwindcss()],
    server: {
      allowedHosts: ["demo.uiram.com"],
      host: "0.0.0.0",
      port: 5173,
      proxy: {
        "/api": {
          target: env.VITE_API_URL || "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: ["./src/test-setup.ts"],
    },
  };
});
