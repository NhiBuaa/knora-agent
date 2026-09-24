import { defineConfig, devices } from "@playwright/test";

import { m5E2EEnvironment } from "./tests/e2e/support/environment";
import type { M5E2EEnvironment } from "./tests/e2e/support/environment";

const requiredM5Environment = [
  ["M5_E2E_BASE_URL", "baseUrl", "http://127.0.0.1:3000"],
  ["M5_E2E_API_URL", "apiUrl", "http://127.0.0.1:8000"],
  ["M5_E2E_KEYCLOAK_ISSUER", "keycloakIssuer", "http://127.0.0.1:8180/realms/m5-e2e"],
] as const;

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

export function validateM5E2EEnvironment(values: M5E2EEnvironment): M5E2EEnvironment {
  for (const [name, key, expected] of requiredM5Environment) {
    const actual = values[key];
    if (actual !== expected) {
      throw new Error(`M5 live E2E configuration error: ${name} must use the isolated local endpoint.`);
    }
  }
  return values;
}

export function m5E2ERuntimeEnvironment(
  values: M5E2EEnvironment,
  ambient: Record<string, string | undefined> = process.env,
) {
  validateM5E2EEnvironment(values);
  for (const name of runtimeEnvironmentNames) {
    if (ambient[name]?.trim()) {
      throw new Error(`M5 live E2E configuration error: ${name} must not override isolated runtime settings.`);
    }
  }

  const issuer = values.keycloakIssuer;

  return {
    KEYCLOAK_AUTHORIZATION_URL: `${issuer}/protocol/openid-connect/auth`,
    KEYCLOAK_TOKEN_URL: `${issuer}/protocol/openid-connect/token`,
    KEYCLOAK_JWKS_URL: `${issuer}/protocol/openid-connect/certs`,
    KEYCLOAK_ISSUER: values.keycloakIssuer,
    KEYCLOAK_AUDIENCE: "knora-web",
    KEYCLOAK_CLIENT_ID: "knora-web",
    KEYCLOAK_REDIRECT_URI: `${values.baseUrl}/api/auth/callback`,
    KNORA_API_URL: values.apiUrl,
    KNORA_BACKEND_URL: values.apiUrl,
    SESSION_SECRET: "m5-e2e-test-session-secret",
  };
}

const environment = validateM5E2EEnvironment(m5E2EEnvironment());
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
    command: "npm run dev -- --hostname 127.0.0.1 --port 3000",
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
