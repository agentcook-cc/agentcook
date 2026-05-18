import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

// frontend-conventions.md §7.7 — dev mode dual API base.
// Python `agentcook` (Agent / Memory / Skill / Plugin) on :8000.
// Java `agentcook-java` (Users / Sessions / Auth / Connectors) on :8080.
// Production uses Cloudflare Workers path-based routing → no proxy needed.
const PY_API = "http://localhost:8000";
const JAVA_API = "http://localhost:8080";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
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
