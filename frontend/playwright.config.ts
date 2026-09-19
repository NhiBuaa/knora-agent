import { defineConfig, devices } from "@playwright/test";

import { m5E2EEnvironment } from "./tests/e2e/support/environment";

const environment = m5E2EEnvironment();

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "**/*.spec.ts",
  outputDir: "./test-results/e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: environment.baseUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: {
    command: "npm run build && npm run start -- --port 3000",
    url: environment.baseUrl,
    timeout: 120_000,
    reuseExistingServer: false,
    env: {
      M5_E2E_BASE_URL: environment.baseUrl,
      M5_E2E_API_URL: environment.apiUrl,
      M5_E2E_KEYCLOAK_ISSUER: environment.keycloakIssuer,
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
