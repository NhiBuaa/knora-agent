import { describe, expect, it } from "vitest";

import {
  figmaEnvironment,
  figmaRuntimeEnvironment,
  validateFigmaEnvironment,
} from "./figma-environment";

describe("isolated Figma identity environment", () => {
  it("accepts only the approved project, realm and loopback endpoints", () => {
    const environment = figmaEnvironment();
    expect(validateFigmaEnvironment(environment)).toEqual(environment);
    for (const [key, value] of Object.entries(environment)) {
      expect(() =>
        validateFigmaEnvironment({ ...environment, [key]: `${value}-other` }),
      ).toThrow(/isolated/);
    }
  });

  it("rejects ambient runtime and Compose overrides before starting anything", () => {
    for (const name of [
      "KEYCLOAK_ISSUER",
      "KEYCLOAK_REDIRECT_URI",
      "KNORA_BACKEND_URL",
      "SESSION_SECRET",
      "COMPOSE_PROJECT_NAME",
      "COMPOSE_FILE",
      "DOCKER_HOST",
      "DOCKER_CONTEXT",
      "FIGMA_E2E_BASE_URL",
    ]) {
      expect(() =>
        figmaRuntimeEnvironment(figmaEnvironment(), { [name]: "other" }),
      ).toThrow(/override/);
    }
  });

  it("derives callback and issuer only from validated identity endpoints", () => {
    const runtime = figmaRuntimeEnvironment(figmaEnvironment(), {});
    expect(runtime.KEYCLOAK_REDIRECT_URI).toBe(
      "http://127.0.0.1:3300/api/auth/callback",
    );
    expect(runtime.KEYCLOAK_ISSUER).toBe(
      "http://127.0.0.1:8380/realms/knora-dev",
    );
    expect(runtime.KNORA_BACKEND_URL).toBe("http://127.0.0.1:8800");
  });
});
