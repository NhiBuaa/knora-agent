import { describe, expect, it } from "vitest";

const m5Environment = {
  baseUrl: "http://127.0.0.1:3000",
  apiUrl: "http://127.0.0.1:8000",
  keycloakIssuer: "http://127.0.0.1:8180/realms/m5-e2e",
};

process.env.M5_E2E_BASE_URL = m5Environment.baseUrl;
process.env.M5_E2E_API_URL = m5Environment.apiUrl;
process.env.M5_E2E_KEYCLOAK_ISSUER = m5Environment.keycloakIssuer;
for (const name of [
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
])
  delete process.env[name];

const {
  default: config,
  m5E2ERuntimeEnvironment,
  validateM5E2EEnvironment,
} = await import("../../../playwright.config");

describe("Playwright live runner", () => {
  it("starts a deterministic local development web server before tests", () => {
    expect(config.webServer).toMatchObject({
      command: "npm run dev -- --hostname 127.0.0.1 --port 3000",
      url: m5Environment.baseUrl,
      reuseExistingServer: false,
    });
  });

  it("derives runtime settings only from the allowed local M5 environment", async () => {
    const packageJson = await import("../../../package.json");
    expect(packageJson.default.scripts.start).toBe("next start");
    expect(m5E2ERuntimeEnvironment(m5Environment, {})).toEqual({
      KEYCLOAK_AUTHORIZATION_URL:
        "http://127.0.0.1:8180/realms/m5-e2e/protocol/openid-connect/auth",
      KEYCLOAK_TOKEN_URL:
        "http://127.0.0.1:8180/realms/m5-e2e/protocol/openid-connect/token",
      KEYCLOAK_JWKS_URL:
        "http://127.0.0.1:8180/realms/m5-e2e/protocol/openid-connect/certs",
      KEYCLOAK_ISSUER: m5Environment.keycloakIssuer,
      KEYCLOAK_AUDIENCE: "knora-web",
      KEYCLOAK_CLIENT_ID: "knora-web",
      KEYCLOAK_REDIRECT_URI: "http://127.0.0.1:3000/api/auth/callback",
      KNORA_API_URL: m5Environment.apiUrl,
      KNORA_BACKEND_URL: m5Environment.apiUrl,
      SESSION_SECRET: "m5-e2e-test-session-secret",
    });
  });

  it("rejects a non-local M5 endpoint", () => {
    expect(() =>
      validateM5E2EEnvironment({
        ...m5Environment,
        baseUrl: "https://example.test",
      }),
    ).toThrow(/M5_E2E_BASE_URL/);
  });

  it("rejects conflicting ambient runtime settings", () => {
    expect(() =>
      m5E2ERuntimeEnvironment(m5Environment, {
        KEYCLOAK_ISSUER: "https://example.test",
      }),
    ).toThrow(/KEYCLOAK_ISSUER/);
  });
});
