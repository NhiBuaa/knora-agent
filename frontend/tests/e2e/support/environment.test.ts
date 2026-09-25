import { afterEach, describe, expect, it } from "vitest";

import { m5E2EEnvironment } from "./environment";

const environmentKeys = [
  "M5_E2E_BASE_URL",
  "M5_E2E_API_URL",
  "M5_E2E_KEYCLOAK_ISSUER",
] as const;

describe("m5E2EEnvironment", () => {
  const originalEnvironment = Object.fromEntries(
    environmentKeys.map((key) => [key, process.env[key]]),
  );

  afterEach(() => {
    for (const key of environmentKeys) {
      const value = originalEnvironment[key];
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  });

  it("returns the configured local URLs", () => {
    process.env.M5_E2E_BASE_URL = "http://localhost:3000";
    process.env.M5_E2E_API_URL = "http://localhost:8000";
    process.env.M5_E2E_KEYCLOAK_ISSUER = "http://localhost:8180/realms/knora";

    expect(m5E2EEnvironment()).toEqual({
      baseUrl: "http://localhost:3000",
      apiUrl: "http://localhost:8000",
      keycloakIssuer: "http://localhost:8180/realms/knora",
    });
  });

  it("rejects an empty base URL", () => {
    process.env.M5_E2E_BASE_URL = "";

    expect(() => m5E2EEnvironment()).toThrow(/M5_E2E_BASE_URL/);
  });

  it("keeps the Playwright script and dependency declared", async () => {
    const packageJson = await import("../../../package.json");

    expect(packageJson.default.scripts["test:e2e"]).toBeDefined();
    expect(
      packageJson.default.devDependencies["@playwright/test"],
    ).toBeDefined();
  });
});
