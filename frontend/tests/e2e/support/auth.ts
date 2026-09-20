import { expect, type Browser, type BrowserContext, type Page } from "@playwright/test";

export type M5E2EIdentity = "user" | "delete-user" | "operator" | "other-workspace" | "no-operator";
export type M5E2EFaultScenario = "provider_failure" | "stream_interruption";
export type M5E2EResult = {
  scenario: string;
  identity: M5E2EIdentity;
  outcome: "passed" | "unavailable" | "denied";
  observedState: string;
};

type Credentials = { username: string; password: string };
type SessionShape = { workspaceId: string; capabilities: readonly string[] };

const credentialsEnvironmentNames: Record<M5E2EIdentity, readonly [string, string]> = {
  user: ["M5_E2E_USER_USERNAME", "M5_E2E_USER_PASSWORD"],
  "delete-user": ["M5_E2E_DELETE_USERNAME", "M5_E2E_DELETE_PASSWORD"],
  operator: ["M5_E2E_OPERATOR_USERNAME", "M5_E2E_OPERATOR_PASSWORD"],
  "other-workspace": ["M5_E2E_OTHER_WORKSPACE_USERNAME", "M5_E2E_OTHER_WORKSPACE_PASSWORD"],
  "no-operator": ["M5_E2E_NO_OPERATOR_USERNAME", "M5_E2E_NO_OPERATOR_PASSWORD"],
};

const expectedSessionShapes: Record<M5E2EIdentity, SessionShape> = {
  user: { workspaceId: "m5-workspace", capabilities: ["documents:read", "documents:write", "questions:ask"] },
  "delete-user": { workspaceId: "m5-workspace", capabilities: ["documents:read", "documents:write", "documents:delete", "questions:ask"] },
  operator: { workspaceId: "m5-workspace", capabilities: ["documents:read", "documents:write", "questions:ask", "operator:read"] },
  "other-workspace": { workspaceId: "m5-other-workspace", capabilities: ["documents:read", "documents:write", "questions:ask", "operator:read"] },
  "no-operator": { workspaceId: "m5-workspace", capabilities: ["documents:read", "documents:write", "questions:ask"] },
};

function credentialsFor(identity: M5E2EIdentity): Credentials {
  const [usernameName, passwordName] = credentialsEnvironmentNames[identity];
  const username = process.env[usernameName]?.trim();
  const password = process.env[passwordName];
  if (!username || !password) {
    throw new Error(
      `M5 live E2E configuration error: credentials for ${identity} are missing. ` +
        "Set the test-only credential environment variables before running Playwright.",
    );
  }
  return { username, password };
}

export async function newRoleContext(browser: Browser, _identity: M5E2EIdentity): Promise<BrowserContext> {
  return browser.newContext();
}

/**
 * Keep evidence records deliberately small and browser-safe. Callers retain the
 * returned value in memory; credentials, cookies, tokens, and raw errors never
 * cross this boundary.
 */
export function observedResult(
  scenario: string,
  identity: M5E2EIdentity,
  outcome: M5E2EResult["outcome"],
  observedState: string,
): M5E2EResult {
  return { scenario, identity, outcome, observedState };
}

export async function loginAs(page: Page, identity: M5E2EIdentity): Promise<void> {
  const credentials = credentialsFor(identity);
  const callback = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/auth/callback");

  await page.goto("/api/auth/login");
  await expect(page.locator("#username")).toBeVisible();
  await page.locator("#username").fill(credentials.username);
  await page.locator("#password").fill(credentials.password);
  await page.locator("#kc-login").click();

  const updateProfile = page.getByRole("heading", { name: "Update Account Information" });
  const outcome = await Promise.race([
    callback.then(() => "callback" as const),
    updateProfile.waitFor({ state: "visible" }).then(() => "profile" as const),
  ]);
  if (outcome === "profile") {
    await page.getByRole("textbox", { name: "First name" }).fill("M5");
    await page.getByRole("textbox", { name: "Last name" }).fill("E2E");
    await Promise.all([callback, page.getByRole("button", { name: "Submit" }).click()]);
  }
  await page.waitForURL("**/app");
  await page.goto("/app", { waitUntil: "load" });
  await expect(page.getByRole("heading", { name: "Workspace" })).toBeVisible();
  const response = await page.request.get("/api/auth/session");
  expect(response).toBeOK();
  const body = await response.json() as {
    session?: { workspaceIds?: unknown; capabilities?: unknown } | null;
  };
  const expected = expectedSessionShapes[identity];
  expect(body.session?.workspaceIds).toEqual([expected.workspaceId]);
  expect(body.session?.capabilities).toEqual(expect.any(Array));
  expect([...(body.session?.capabilities as string[])].sort()).toEqual([...expected.capabilities].sort());
}

export async function armM5E2EFault(page: Page, scenario: M5E2EFaultScenario): Promise<void> {
  const sessionResponse = await page.request.get("/api/auth/session");
  expect(sessionResponse).toBeOK();
  const body = await sessionResponse.json() as { session?: { workspaceIds?: unknown } | null };
  const workspaceIds = Array.isArray(body.session?.workspaceIds)
    ? body.session.workspaceIds.filter((workspaceId): workspaceId is string => typeof workspaceId === "string")
    : [];
  if (workspaceIds.length !== 1) throw new Error("M5 live E2E session did not expose exactly one Workspace.");

  const armedResponse = await page.request.post("/api/m5-e2e/faults", {
    data: { workspace_id: workspaceIds[0], scenario },
  });
  if (!armedResponse.ok()) throw new Error("M5 live E2E fault setup failed.");
}
