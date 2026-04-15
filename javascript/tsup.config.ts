import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts"],
  format: ["cjs", "esm"],
  dts: true,
  shims: true,       // injects __dirname / __filename for ESM output
  clean: true,
  sourcemap: false,
  target: "node18",
});
