import { describe, expect, it } from "vitest";

import {
  figmaEnvironment,
  figmaRuntimeEnvironment,
  validateFigmaEnvironment,
} from "./figma-environment";

describe("isolated Figma identity environment", () => {
  it("binds live ownership to an explicitly selected disposable project", () => {
    const environment = figmaEnvironment({
      FIGMA_TEST_PROJECT: "knora-figma-e2e-agent-a123",
    });
    expect(environment.project).toBe("knora-figma-e2e-agent-a123");
    expect(
      validateFigmaEnvironment(environment, {
        FIGMA_TEST_PROJECT: "knora-figma-e2e-agent-a123",
      }),
    ).toEqual(environment);
    expect(() => validateFigmaEnvironment(environment, {})).toThrow(/isolated/);
    for (const project of [
      "knora-dev",
      "knora-figma-e2e-",
      "../other",
      "knora-figma-e2e-A",
    ])
      expect(() => figmaEnvironment({ FIGMA_TEST_PROJECT: project })).toThrow(
        /project/,
      );
  });
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
    expect(figmaTestSelection("application", undefined).testMatch).toEqual([
      "figma-ui-interactions.spec.ts",
      "figma-document-navigation.spec.ts",
      "figma-conversation-navigation.spec.ts",
    ]);
    expect(figmaTestSelection("fixture", undefined).testMatch).toEqual([
      "figma-ui-visual.spec.ts",
      "figma-ui-interactions.spec.ts",
      "conversation-scroll.spec.ts",
    ]);
    expect(
      figmaTestSelection("fixture", undefined).grepInvert?.test(
        "guarded application journeys a live backend scenario",
      ),
    ).toBe(true);
    expect(
      figmaTestSelection("fixture", undefined).grepInvert?.test(
        "source fixtures Document detail action height",
      ),
    ).toBe(false);
    expect(
      figmaTestSelection("fixture", undefined).grepInvert?.test(
        "source fixtures Operator prototype comparison 216:345 Operations",
      ),
    ).toBe(true);
    expect(
      figmaTestSelection("application", undefined).grepInvert?.test(
        "source fixtures Document detail action height",
      ),
    ).toBe(true);
    expect(
      figmaTestSelection("application", undefined).grepInvert?.test(
        "guarded application journeys a live backend scenario",
      ),
    ).toBe(false);
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
