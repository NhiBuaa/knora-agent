import { defineConfig } from "@playwright/test";
import identityConfig from "./playwright.figma.config";

export default defineConfig({
  ...identityConfig,
  testMatch: "figma-operator.spec.ts",
  outputDir: "./test-results/figma-operator",
});
