import { defineConfig, devices } from "@playwright/test";

import {
  figmaEnvironment,
  figmaRuntimeEnvironment,
} from "./tests/e2e/support/figma-environment";

const environment = figmaEnvironment();
const runtime = figmaRuntimeEnvironment(environment);
// Native error snapshots include action URLs with authentication state.
process.env.PLAYWRIGHT_NO_COPY_PROMPT = "1";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "figma-identity.spec.ts",
  outputDir: "./test-results/figma-identity",
  timeout: 60_000,
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
    command: "npm run dev -- --hostname 127.0.0.1 --port 3300",
    url: `${environment.baseUrl}/api/auth/session`,
    timeout: 120_000,
    reuseExistingServer: false,
    env: runtime,
  },
  projects: [{ name: "chromium" }],
});
