import { describe, expect, it } from "vitest";

process.env.M5_E2E_BASE_URL ??= "http://localhost:3000";
process.env.M5_E2E_API_URL ??= "http://localhost:8000";
process.env.M5_E2E_KEYCLOAK_ISSUER ??= "http://localhost:8180/realms/m5-e2e";

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
    ]) {
      expect(webServerEnv).toHaveProperty(name);
    }
  });
});
