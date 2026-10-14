import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

const PY_API = process.env.AGENTCOOK_PY_API ?? "http://localhost:8000";
const JAVA_API = process.env.AGENTCOOK_JAVA_API ?? "http://localhost:8080";

export default defineConfig({
  // Behind the swarm gateway the admin is served under /admin/ — set
  // VITE_BASE_PATH=/admin/ at build time so asset URLs and routes include it.
  base: process.env.VITE_BASE_PATH ?? "/",
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vue-vendor": ["vue", "vue-router", "pinia"],
          "element-plus": ["element-plus"],
          echarts: ["echarts", "vue-echarts"],
          axios: ["axios"],
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      // Python agent runtime (docs/api/v1.yaml)
      "/api/v1/agents": { target: PY_API, changeOrigin: true },
      "/api/v1/skills": { target: PY_API, changeOrigin: true },
      "/api/v1/logs": { target: PY_API, changeOrigin: true },
      "/api/v1/toolkits": { target: PY_API, changeOrigin: true },
      "/api/v1/runtime": { target: PY_API, changeOrigin: true },
      "/api/v1/conversations": { target: PY_API, changeOrigin: true },
      "/api/v1/chat": { target: PY_API, changeOrigin: true },
      // Java business backend (docs/api/java-v1.yaml)
      "/api/v1/auth": { target: JAVA_API, changeOrigin: true },
      "/api/v1/users": { target: JAVA_API, changeOrigin: true },
      "/api/v1/sessions": { target: JAVA_API, changeOrigin: true },
      "/api/v1/plugins": { target: JAVA_API, changeOrigin: true },
      "/api/v1/connectors": { target: JAVA_API, changeOrigin: true },
      "/api/v1/permissions": { target: JAVA_API, changeOrigin: true },
      "/api/v1/quota": { target: JAVA_API, changeOrigin: true },
    },
  },
});
