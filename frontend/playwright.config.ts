import { defineConfig, devices } from "@playwright/test";

import { m5E2EEnvironment } from "./tests/e2e/support/environment";
import type { M5E2EEnvironment } from "./tests/e2e/support/environment";

const environment = m5E2EEnvironment();

export function m5E2ERuntimeEnvironment(values: M5E2EEnvironment) {
  const issuer = values.keycloakIssuer.replace(/\/+$/, "");
  const runtimeValue = (name: string, fallback: string) => process.env[name]?.trim() || fallback;

  return {
    KEYCLOAK_AUTHORIZATION_URL: runtimeValue(
      "KEYCLOAK_AUTHORIZATION_URL",
      `${issuer}/protocol/openid-connect/auth`,
    ),
    KEYCLOAK_TOKEN_URL: runtimeValue(
      "KEYCLOAK_TOKEN_URL",
      `${issuer}/protocol/openid-connect/token`,
    ),
    KEYCLOAK_JWKS_URL: runtimeValue(
      "KEYCLOAK_JWKS_URL",
      `${issuer}/protocol/openid-connect/certs`,
    ),
    KEYCLOAK_ISSUER: runtimeValue("KEYCLOAK_ISSUER", values.keycloakIssuer),
    KEYCLOAK_AUDIENCE: runtimeValue("KEYCLOAK_AUDIENCE", "knora-web"),
    KEYCLOAK_CLIENT_ID: runtimeValue("KEYCLOAK_CLIENT_ID", "knora-web"),
    KEYCLOAK_REDIRECT_URI: runtimeValue(
      "KEYCLOAK_REDIRECT_URI",
      `${values.baseUrl.replace(/\/+$/, "")}/api/auth/callback`,
    ),
    KNORA_API_URL: runtimeValue("KNORA_API_URL", values.apiUrl),
    KNORA_BACKEND_URL: runtimeValue("KNORA_BACKEND_URL", values.apiUrl),
    SESSION_SECRET: runtimeValue("SESSION_SECRET", "m5-e2e-test-session-secret"),
  };
}

const runtimeEnvironment = m5E2ERuntimeEnvironment(environment);

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
