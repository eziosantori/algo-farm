import { defineConfig } from "vitest/config";
import { resolve } from "path";

export default defineConfig({
  resolve: {
    alias: {
      "@algo-farm/shared/strategy": resolve(__dirname, "../shared/src/strategy.ts"),
    },
  },
  test: {
    environment: "node",
    globals: false,
  },
});
