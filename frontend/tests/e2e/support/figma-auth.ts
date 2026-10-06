import { execFileSync } from "node:child_process";
import { expect, type Page } from "@playwright/test";

import {
  figmaEnvironment,
  validateFigmaEnvironment,
} from "./figma-environment";

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

export async function openFigmaLogin(page: Page) {
  assertFigmaServiceOwnership();
  await page.goto("/api/auth/login");
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
