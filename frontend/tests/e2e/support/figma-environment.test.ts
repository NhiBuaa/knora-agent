import { describe, expect, it } from "vitest";

import {
  figmaEnvironment,
  figmaRuntimeEnvironment,
  validateFigmaEnvironment,
} from "./figma-environment";

describe("isolated Figma identity environment", () => {
  it("confines explicit M5 selection to the exact application refusal case", async () => {
    const { figmaTestSelection } = await import(
      "../../../playwright.figma.config"
    );
    expect(typeof figmaTestSelection).toBe("function");
    const selection = figmaTestSelection("application", "m5-refusal");
    expect(selection.testMatch).toBe("m5-user-flows.spec.ts");
    expect(
      selection.grep?.test(
        "a persisted refusal remains a non-answer in the Conversation UI",
      ),
    ).toBe(true);
    expect(
      selection.grep?.test("a persisted failed Turn has no answer or citation"),
    ).toBe(false);
    expect(
      selection.grep?.test(
        "prefix a persisted refusal remains a non-answer in the Conversation UI",
      ),
    ).toBe(false);
    for (const mode of [undefined, "fixture", "unknown"])
      expect(() => figmaTestSelection(mode, "m5-refusal")).toThrow();
    expect(() => figmaTestSelection("application", "other")).toThrow();
    expect(figmaTestSelection(undefined, undefined).testMatch).toBe(
      "figma-identity.spec.ts",
    );
    expect(figmaTestSelection("application", undefined).testMatch).toBe(
      "figma-ui-interactions.spec.ts",
    );
    expect(figmaTestSelection("fixture", undefined).testMatch).toEqual([
      "figma-ui-visual.spec.ts",
      "figma-ui-interactions.spec.ts",
    ]);
  });
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
      "M5_E2E_BASE_URL",
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
