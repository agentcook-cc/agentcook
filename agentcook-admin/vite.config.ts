import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

const PY_API = "http://localhost:8000";
const JAVA_API = "http://localhost:8080";

export default defineConfig({
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
