import { execFileSync } from "node:child_process";
import { expect, type Page } from "@playwright/test";

import realm from "../../../../test/fixtures/keycloak/figma-realm.json";
import {
  figmaEnvironment,
  validateFigmaEnvironment,
} from "./figma-environment";

type RealmUser = { username: string; credentials?: Array<{ value: string }> };

export function assertFigmaServiceOwnership() {
  const environment = validateFigmaEnvironment(figmaEnvironment());
  const ids = execFileSync("docker", ["ps", "--format", "{{.ID}}"], {
    encoding: "utf8",
  })
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  type Mapping = { HostIp: string; HostPort: string };
  type Container = {
    Config: { Labels: Record<string, string> };
    NetworkSettings: { Ports: Record<string, Mapping[] | null> };
  };
  const containers: Container[] = ids.length
    ? JSON.parse(
        execFileSync("docker", ["inspect", ...ids], { encoding: "utf8" }),
      )
    : [];
  for (const [port, target] of [
    [8380, "8080/tcp"],
    [8800, "8000/tcp"],
    [8025, "8025/tcp"],
  ] as const) {
    const owners = containers.filter((container) =>
      Object.values(container.NetworkSettings.Ports ?? {}).some((mappings) =>
        mappings?.some((mapping) => Number(mapping.HostPort) === port),
      ),
    );
    if (
      owners.length !== 1 ||
      owners[0].Config.Labels["com.docker.compose.project"] !==
        environment.project ||
      !owners[0].NetworkSettings.Ports[target]?.some(
        (mapping: { HostIp: string; HostPort: string }) =>
          mapping.HostIp === "127.0.0.1" && Number(mapping.HostPort) === port,
      )
    ) {
      throw new Error(
        `Figma live service ownership rejected for port ${port}.`,
      );
    }
  }
}

export async function openFigmaLogin(page: Page, forcedReauth = false) {
  assertFigmaServiceOwnership();
  await page.goto(
    forcedReauth ? "/api/auth/login?prompt=login" : "/api/auth/login",
  );
  expect(new URL(page.url()).origin).toBe("http://127.0.0.1:8380");
  await expect(page.locator("#kc-form-login")).toBeVisible();
}

export async function openFigmaRegistration(page: Page) {
  await openFigmaLogin(page);
  await page.getByRole("link", { name: "Create account", exact: true }).click();
  await expect(page.locator("#kc-register-form")).toBeVisible();
}

export async function fillRegistration(
  page: Page,
  identity: { username: string; email: string; password: string },
  confirmation = identity.password,
) {
  await page.locator("#username").fill(identity.username);
  await page.locator("#email").fill(identity.email);
  await page.locator("#password").fill(identity.password);
  await page.locator("#password-confirm").fill(confirmation);
}

export async function captureIdentity(page: Page, path: string) {
  await page.evaluate(() => document.fonts.ready);
  const secrets = page.locator("#password, #password-confirm, #password-new");
  const masks = [];
  for (const input of await secrets.all()) {
    if ((await input.inputValue()).length > 0) masks.push(input);
  }
  await page.screenshot({
    path,
    fullPage: true,
    mask: masks,
    maskColor: "#ffffff",
  });
}

export async function signInFigmaUser(
  page: Page,
  identity: "m5-user" | "m5-other-workspace" | "m5-no-operator",
  rememberMe = false,
  forcedReauth = false,
): Promise<void> {
  const users = (realm as { users: RealmUser[] }).users;
  const user = users.find((u) => u.username === identity);
  if (!user || !user.credentials?.[0]?.value) {
    throw new Error(
      `Synthetic identity ${identity} not found in figma-realm.json`,
    );
  }
  await openFigmaLogin(page, forcedReauth);
  const usernameInput = page.locator("#username");
  if (!(await usernameInput.isVisible())) {
    const resetLogin = page.locator("#reset-login");
    if (await resetLogin.isVisible()) {
      await resetLogin.click();
      await expect(usernameInput).toBeVisible();
    }
  }
  await usernameInput.fill(user.username);
  await page.locator("#password").fill(user.credentials[0].value);
  const checkbox = page.locator("#rememberMe");
  if (rememberMe) {
    await checkbox.check();
  } else {
    await checkbox.uncheck();
  }
  await page.locator("#kc-login").click();
  await page.waitForURL(/\/workspaces(?:\/[^?]+)?$/);
  const sessionRes = await page.request.get("/api/auth/session");
  expect(sessionRes.ok()).toBe(true);
  const body = (await sessionRes.json()) as { session: unknown };
  expect(body.session).not.toBeNull();
}
