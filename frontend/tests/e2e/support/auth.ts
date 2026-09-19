import { expect, type Browser, type BrowserContext, type Page } from "@playwright/test";

export type M5E2EIdentity = "user" | "operator" | "other-workspace" | "no-operator";

type Credentials = { username: string; password: string };
type SessionShape = { workspaceId: string; capability: string };

const credentialsEnvironmentNames: Record<M5E2EIdentity, readonly [string, string]> = {
  user: ["M5_E2E_USER_USERNAME", "M5_E2E_USER_PASSWORD"],
  operator: ["M5_E2E_OPERATOR_USERNAME", "M5_E2E_OPERATOR_PASSWORD"],
  "other-workspace": ["M5_E2E_OTHER_WORKSPACE_USERNAME", "M5_E2E_OTHER_WORKSPACE_PASSWORD"],
  "no-operator": ["M5_E2E_NO_OPERATOR_USERNAME", "M5_E2E_NO_OPERATOR_PASSWORD"],
};

const expectedSessionShapes: Record<M5E2EIdentity, SessionShape> = {
  user: { workspaceId: "m5-workspace", capability: "documents:read" },
  operator: { workspaceId: "m5-workspace", capability: "operator:read" },
  "other-workspace": { workspaceId: "m5-other-workspace", capability: "documents:read" },
  "no-operator": { workspaceId: "m5-workspace", capability: "documents:read" },
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
  await expect(page.getByRole("heading", { name: "Workspace" })).toBeVisible();
  const response = await page.request.get("/api/auth/session");
  expect(response).toBeOK();
  const body = await response.json() as {
    session?: { workspaceIds?: unknown; capabilities?: unknown } | null;
  };
  const expected = expectedSessionShapes[identity];
  expect(body.session?.workspaceIds).toEqual(expect.arrayContaining([expected.workspaceId]));
  expect(body.session?.capabilities).toEqual(expect.arrayContaining([expected.capability]));
}
