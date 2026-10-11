import { defineConfig, devices } from "@playwright/test";

import {
  figmaEnvironment,
  figmaRuntimeEnvironment,
} from "./tests/e2e/support/figma-environment";

const environment = figmaEnvironment();
const runtime = figmaRuntimeEnvironment(environment);
process.env.PLAYWRIGHT_NO_COPY_PROMPT = "1";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "figma-otp-native.spec.ts",
  outputDir: "./test-results/figma-otp-native",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: "list",
  use: {
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
    baseURL: environment.baseUrl,
    ...devices["Desktop Chrome"],
    colorScheme: "light",
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
  projects: [
    {
      name: "desktop1440x960",
      use: { viewport: { width: 1440, height: 960 } },
    },
    {
      name: "mobile390x844",
      use: { ...devices["Pixel 5"], viewport: { width: 390, height: 844 } },
    },
  ],
});
