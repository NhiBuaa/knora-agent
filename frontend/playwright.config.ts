import { defineConfig, devices } from "@playwright/test";

import { m5E2EEnvironment } from "./tests/e2e/support/environment";

const environment = m5E2EEnvironment();
const runtimeEnvironmentNames = [
  "KEYCLOAK_AUTHORIZATION_URL",
  "KEYCLOAK_TOKEN_URL",
  "KEYCLOAK_JWKS_URL",
  "KEYCLOAK_ISSUER",
  "KEYCLOAK_AUDIENCE",
  "KEYCLOAK_CLIENT_ID",
  "KEYCLOAK_REDIRECT_URI",
  "KNORA_API_URL",
  "KNORA_BACKEND_URL",
  "SESSION_SECRET",
] as const;

const runtimeEnvironment = Object.fromEntries(
  runtimeEnvironmentNames.map((name) => [name, process.env[name] ?? ""]),
);

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
      ...runtimeEnvironment,
      M5_E2E_BASE_URL: environment.baseUrl,
      M5_E2E_API_URL: environment.apiUrl,
      M5_E2E_KEYCLOAK_ISSUER: environment.keycloakIssuer,
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
