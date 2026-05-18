import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx", "tests/**/*.test.ts", "tests/**/*.test.tsx"],
    // Switch to "jsdom" once B starts testing React components (requires `jsdom` devDep)
    environment: "node",
    globals: true,
  },
});
