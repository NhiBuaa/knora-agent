import { describe, expect, it } from "vitest";

process.env.M5_E2E_BASE_URL ??= "http://localhost:3000";
process.env.M5_E2E_API_URL ??= "http://localhost:8000";
process.env.M5_E2E_KEYCLOAK_ISSUER ??= "http://localhost:8180/realms/m5-e2e";
for (const [name, value] of Object.entries({
  KEYCLOAK_AUTHORIZATION_URL: "sentinel-authorization-url",
  KEYCLOAK_TOKEN_URL: "sentinel-token-url",
  KEYCLOAK_JWKS_URL: "sentinel-jwks-url",
  KEYCLOAK_ISSUER: "sentinel-issuer",
  KEYCLOAK_AUDIENCE: "sentinel-audience",
  KEYCLOAK_CLIENT_ID: "sentinel-client-id",
  KEYCLOAK_REDIRECT_URI: "sentinel-redirect-uri",
  KNORA_API_URL: "sentinel-api-url",
  KNORA_BACKEND_URL: "sentinel-backend-url",
  SESSION_SECRET: "sentinel-session-secret",
})) {
  process.env[name] = value;
}

const { default: config, m5E2ERuntimeEnvironment } = await import("../../../playwright.config");

describe("Playwright live runner", () => {
  it("starts a deterministic production web server before tests", () => {
    expect(config.webServer).toMatchObject({
      command: "npm run build && npm run start -- --port 3000",
      url: "http://localhost:3000",
      reuseExistingServer: false,
    });
  });

  it("declares the Next start script and forwards runtime variables", async () => {
    const packageJson = await import("../../../package.json");
    expect(packageJson.default.scripts.start).toBe("next start");

    const webServerEnv = config.webServer && !Array.isArray(config.webServer)
      ? config.webServer.env
      : undefined;
    expect(webServerEnv).toBeDefined();
    const expectedRuntimeEnvironment = {
      KEYCLOAK_AUTHORIZATION_URL: "sentinel-authorization-url",
      KEYCLOAK_TOKEN_URL: "sentinel-token-url",
      KEYCLOAK_JWKS_URL: "sentinel-jwks-url",
      KEYCLOAK_ISSUER: "sentinel-issuer",
      KEYCLOAK_AUDIENCE: "sentinel-audience",
      KEYCLOAK_CLIENT_ID: "sentinel-client-id",
      KEYCLOAK_REDIRECT_URI: "sentinel-redirect-uri",
      KNORA_API_URL: "sentinel-api-url",
      KNORA_BACKEND_URL: "sentinel-backend-url",
      SESSION_SECRET: "sentinel-session-secret",
      M5_E2E_BASE_URL: "http://localhost:3000",
      M5_E2E_API_URL: "http://localhost:8000",
      M5_E2E_KEYCLOAK_ISSUER: "http://localhost:8180/realms/m5-e2e",
    };
    expect(webServerEnv).toMatchObject(expectedRuntimeEnvironment);
  });

  it("derives safe runtime defaults from only the M5 environment", () => {
    const explicitNames = [
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
    ];
    const previous = Object.fromEntries(explicitNames.map((name) => [name, process.env[name]]));
    for (const name of explicitNames) delete process.env[name];

    try {
      expect(m5E2ERuntimeEnvironment({
        baseUrl: "http://localhost:3000",
        apiUrl: "http://localhost:8000",
        keycloakIssuer: "http://localhost:8180/realms/m5-e2e",
      })).toEqual({
        KEYCLOAK_AUTHORIZATION_URL:
          "http://localhost:8180/realms/m5-e2e/protocol/openid-connect/auth",
        KEYCLOAK_TOKEN_URL:
          "http://localhost:8180/realms/m5-e2e/protocol/openid-connect/token",
        KEYCLOAK_JWKS_URL:
          "http://localhost:8180/realms/m5-e2e/protocol/openid-connect/certs",
        KEYCLOAK_ISSUER: "http://localhost:8180/realms/m5-e2e",
        KEYCLOAK_AUDIENCE: "knora-web",
        KEYCLOAK_CLIENT_ID: "knora-web",
        KEYCLOAK_REDIRECT_URI: "http://localhost:3000/api/auth/callback",
        KNORA_API_URL: "http://localhost:8000",
        KNORA_BACKEND_URL: "http://localhost:8000",
        SESSION_SECRET: "m5-e2e-test-session-secret",
      });
    } finally {
      for (const [name, value] of Object.entries(previous)) {
        if (value === undefined) delete process.env[name];
        else process.env[name] = value;
      }
    }
  });
});
