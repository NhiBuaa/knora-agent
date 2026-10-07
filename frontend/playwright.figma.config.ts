import { defineConfig, devices } from "@playwright/test";

import {
  figmaEnvironment,
  figmaRuntimeEnvironment,
} from "./tests/e2e/support/figma-environment";

const fixtureMode = process.env.FIGMA_TEST_MODE === "fixture";
const applicationMode = process.env.FIGMA_TEST_MODE === "application";
if (process.env.FIGMA_TEST_MODE && !fixtureMode && !applicationMode)
  throw new Error("Unknown Figma test mode.");
const environment = figmaEnvironment();
const runtime = figmaRuntimeEnvironment(environment);
// Native error snapshots include action URLs with authentication state.
process.env.PLAYWRIGHT_NO_COPY_PROMPT = "1";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: fixtureMode
    ? ["figma-ui-visual.spec.ts", "figma-ui-interactions.spec.ts"]
    : applicationMode
      ? "figma-ui-interactions.spec.ts"
      : "figma-identity.spec.ts",
  outputDir: fixtureMode
    ? "./test-results/figma-ui"
    : applicationMode
      ? "./test-results/figma-ui-application"
      : "./test-results/figma-identity",
  timeout: fixtureMode ? 20_000 : 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: "list",
  use: {
    baseURL: environment.baseUrl,
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 960 },
    colorScheme: "light",
    // Native actions and email links contain codes. Capture only explicit masked screenshots.
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  webServer: {
    command: fixtureMode
      ? "node tests/e2e/support/figma-fixture-server.mjs"
      : "npm run dev -- --hostname 127.0.0.1 --port 3300",
    url: `${environment.baseUrl}${fixtureMode ? "/fixture-health" : "/api/auth/session"}`,
    timeout: 120_000,
    reuseExistingServer: false,
    env: runtime,
  },
  projects: [{ name: fixtureMode ? "fixtures" : "chromium" }],
});
