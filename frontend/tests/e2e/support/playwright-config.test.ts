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

const { default: config } = await import("../../../playwright.config");

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
});
