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
});
