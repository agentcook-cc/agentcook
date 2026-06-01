/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

const PY_API = "http://localhost:8000";
const JAVA_API = "http://localhost:8080";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "react-vendor": ["react", "react-dom", "react-router-dom"],
          markdown: ["react-markdown", "remark-gfm", "rehype-highlight"],
          virtuoso: ["react-virtuoso"],
          axios: ["axios"],
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    css: true,
  },
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      "/api/v1/agent": { target: PY_API, changeOrigin: true },
      "/api/v1/memory": { target: PY_API, changeOrigin: true },
      "/api/v1/skills": { target: PY_API, changeOrigin: true },
      "/api/v1/plugins": { target: PY_API, changeOrigin: true },
      "/api/v1/users": { target: JAVA_API, changeOrigin: true },
      "/api/v1/sessions": { target: JAVA_API, changeOrigin: true },
      "/api/v1/connectors": { target: JAVA_API, changeOrigin: true },
      "/api/v1/permissions": { target: JAVA_API, changeOrigin: true },
      "/api/v1/auth": { target: JAVA_API, changeOrigin: true },
    },
  },
});
