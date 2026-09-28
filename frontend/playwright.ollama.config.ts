import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.M5_E2E_BASE_URL;
if (!baseURL || !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(baseURL)) {
  throw new Error("M5_E2E_BASE_URL must name the running local frontend");
}

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "**/ollama-local-acceptance.spec.ts",
  outputDir: "./test-results/e2e/ollama",
  timeout: 300_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: "list",
  use: {
    baseURL,
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
