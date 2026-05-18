import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  test: {
    include: ["src/**/*.test.ts", "tests/**/*.test.ts"],
    // Switch to "jsdom" once B starts testing Vue components (requires `jsdom` devDep)
    environment: "node",
    globals: true,
  },
});
