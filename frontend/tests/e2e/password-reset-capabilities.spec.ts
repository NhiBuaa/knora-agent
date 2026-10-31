import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { passwordResetFailure } from "../password-reset/failure";

const keycloak = "http://127.0.0.1:8480";
const realm = `${keycloak}/admin/realms/knora-dev`;
const baseline = ["documents:read", "documents:write", "questions:ask"];

test.beforeEach(({ baseURL }) => {
  test.skip(
    baseURL !== "http://127.0.0.1:3400",
    "Requires the isolated password-reset config",
  );
});

function assertOwnedRuntime() {
  const containers = JSON.parse(
    execFileSync(
      "docker",
      [
        "inspect",
        ...[
          "knora-issue162-reset-keycloak-1",
          "knora-issue162-reset-api-1",
          "knora-issue162-reset-mail-1",
          "knora-issue162-reset-keycloak-db-1",
          "knora-issue162-reset-postgres-1",
        ],
      ],
      { encoding: "utf8", timeout: 10_000 },
    ),
  );
  for (const container of containers) {
    expect(container.Config.Labels["com.docker.compose.project"]).toBe(
      "knora-issue162",
    );
    expect(
      resolve(
        container.Config.Labels["com.docker.compose.project.working_dir"],
      ),
    ).toBe(resolve(".."));
    expect(
      resolve(
        container.Config.Labels["com.docker.compose.project.config_files"],
      ),
    ).toBe(resolve("../docker-compose.dev.yml"));
    const service = container.Config.Labels["com.docker.compose.service"];
    const binding = (
      {
        "reset-keycloak": ["8080/tcp", "8480"],
        "reset-api": ["8000/tcp", "8900"],
        "reset-mail": ["8025/tcp", "8125"],
      } as Record<string, string[]>
    )[service];
    if (binding)
      expect(container.NetworkSettings.Ports[binding[0]]).toEqual([
        { HostIp: "127.0.0.1", HostPort: binding[1] },
      ]);
  }
}

async function session(page: Page) {
  return (await (await page.request.get("/api/auth/session")).json()).session;
}

async function attributes(username: string) {
  expect(/^reset-[0-9a-f-]{36}$/.test(username)).toBe(true);
  // Read only non-secret authorization state. Admin representations hide unmanaged attributes.
  return execFileSync(
    "docker",
    [
      "exec",
      "knora-issue162-reset-keycloak-db-1",
      "psql",
      "-U",
      "keycloak",
      "-d",
      "keycloak",
      "-Atc",
      `select a.name || '=' || a.value from user_attribute a join user_entity u on u.id=a.user_id where u.username='${username}' and a.name in ('capabilities','workspace_id','workspace_ids') order by a.name,a.value`,
    ],
    { encoding: "utf8", timeout: 10_000 },
  ).trim();
}

async function setCapabilities(
  page: Page,
  username: string,
  capabilities: string[],
) {
  const tokenResponse = await page.request.post(
    `${keycloak}/realms/master/protocol/openid-connect/token`,
    {
      form: {
        client_id: "admin-cli",
        grant_type: "password",
        username: "figma-test-admin",
        password: "figma-test-admin-password",
      },
    },
  );
  expect(tokenResponse.ok()).toBe(true);
  const headers = {
    Authorization: `Bearer ${(await tokenResponse.json()).access_token}`,
  };
  const profile = await (
    await page.request.get(`${realm}/users/profile`, { headers })
  ).json();
  if (
    !profile.attributes.some((a: { name: string }) => a.name === "capabilities")
  ) {
    profile.attributes.push({
      name: "capabilities",
      multivalued: true,
      permissions: { view: ["admin"], edit: ["admin"] },
    });
    expect(
      (
        await page.request.put(`${realm}/users/profile`, {
          headers,
          data: profile,
        })
      ).ok(),
    ).toBe(true);
  }
  const users = await (
    await page.request.get(`${realm}/users`, {
      headers,
      params: { username, exact: "true" },
    })
  ).json();
  expect(users.length === 1).toBe(true);
  expect(
    (
      await page.request.put(`${realm}/users/${users[0].id}`, {
        headers,
        data: {
          ...users[0],
          attributes: { ...users[0].attributes, capabilities },
        },
      })
    ).ok(),
  ).toBe(true);
}

for (const { name, capabilities } of [
  { name: "registration baseline", capabilities: baseline },
  {
    name: "additional approved capabilities",
    capabilities: [...baseline, "documents:delete", "operator:read"],
  },
  { name: "restricted reader", capabilities: ["documents:read"] },
  { name: "no capabilities", capabilities: [] },
])
  test(`Forgot Password preserves ${name}, identity and private Workspace`, async ({
    page,
    browser,
  }) => {
    let stage = "OWNERSHIP";
    const contexts = [page.context()];
    try {
      assertOwnedRuntime();
      const username = `reset-${randomUUID()}`;
      const email = `${username}@example.test`;
      const oldPassword = `Old-${randomUUID()}-Password`;
      const newPassword = `New-${randomUUID()}-Password`;
      stage = "REGISTER";
      await page.goto("/api/auth/login");
      await page
        .getByRole("link", { name: "Create account", exact: true })
        .click();
      await page.locator("#username").fill(username);
      await page.locator("#email").fill(email);
      await page.locator("#password").fill(oldPassword);
      await page.locator("#password-confirm").fill(oldPassword);
      await page
        .getByRole("button", { name: "Create account", exact: true })
        .click();
      await page.waitForURL(/\/workspaces(?:\/[^?]+)?(?:\?.*)?$/, {
        timeout: 30_000,
      });
      // Model an administrative grant/revocation before recovery, never inside the reset path.
      expect([...(await session(page)).capabilities].sort()).toEqual(
        [...baseline].sort(),
      );
      stage = "ADMIN_POLICY";
      if (name !== "registration baseline")
        await setCapabilities(page, username, capabilities);
      stage = "BEFORE_LOGIN_NAVIGATE";
      await page.context().clearCookies();
      await page.goto("/api/auth/login?prompt=login");
      stage = "BEFORE_LOGIN_FORM";
      await page.locator("#username").fill(email);
      await page.locator("#password").fill(oldPassword);
      await page.locator("#kc-login").click();
      stage = "BEFORE_LOGIN_CALLBACK";
      await page.waitForURL(/\/workspaces(?:\/[^?]+)?(?:\?.*)?$/);
      stage = "BEFORE_LOGIN_CLAIMS";
      const before = await session(page);
      expect([...before.capabilities].sort()).toEqual([...capabilities].sort());
      const beforeAttributes = await attributes(username);
      const workspaces = await (
        await page.request.get("/api/v1/workspaces")
      ).json();
      const workspace = workspaces.items[0].id;
      stage = "RESET_REQUEST";
      const recovery = await browser.newContext();
      contexts.push(recovery);
      const reset = await recovery.newPage();
      await reset.goto("http://127.0.0.1:3400/api/auth/login?prompt=login");
      await reset.getByRole("link", { name: "Forgot Password?" }).click();
      await reset.locator("#email").fill(email);
      await reset.locator('button[value="request"]').click();
      await expect(reset.locator(".knora-otp-digits")).toBeVisible();
      stage = "MAIL_DELIVERY";
      let messageId = "";
      await expect
        .poll(async () => {
          const mailbox = await (
            await reset.request.get("http://127.0.0.1:8125/api/v1/messages")
          ).json();
          messageId =
            mailbox.messages.find(
              (m: { ID: string; To: { Address: string }[] }) =>
                m.To.some((to) => to.Address === email),
            )?.ID ?? "";
          return Boolean(messageId);
        })
        .toBe(true);
      const message = await (
        await reset.request.get(
          `http://127.0.0.1:8125/api/v1/message/${messageId}`,
        )
      ).json();
      const code = String(message.Text).match(/\b[0-9]{6}\b/)?.[0] ?? "";
      expect(code.length === 6).toBe(true);
      stage = "OTP_VERIFY";
      for (const [i, digit] of [...code].entries())
        await reset.locator(".knora-otp-digit").nth(i).fill(digit);
      // The sixth digit submits the native OTP form.
      await expect(reset.locator("#kc-passwd-update-form")).toBeVisible();
      expect(await attributes(username)).toBe(beforeAttributes);
      stage = "UPDATE_PASSWORD";
      await reset.locator("#password-new").fill(newPassword);
      await reset.locator("#password-confirm").fill(newPassword);
      await reset.locator("#kc-submit").click();
      await expect(reset.locator("#kc-form-login")).toBeVisible();
      expect(await attributes(username)).toBe(beforeAttributes);
      stage = "FRESH_LOGIN";
      await reset.locator("#username").fill(email);
      await reset.locator("#password").fill(newPassword);
      await reset.locator("#kc-login").click();
      await reset.waitForURL(/\/workspaces(?:\/[^?]+)?(?:\?.*)?$/, {
        timeout: 30_000,
      });
      const after = await session(reset);
      expect(after.subject === before.subject).toBe(true);
      expect([...after.capabilities].sort()).toEqual([...capabilities].sort());
      expect(after.workspaceIds).toEqual(before.workspaceIds);
      expect(await attributes(username)).toBe(beforeAttributes);
      const afterWorkspaces = await (
        await reset.request.get("http://127.0.0.1:3400/api/v1/workspaces")
      ).json();
      expect(
        afterWorkspaces.items.some((w: { id: string }) => w.id === workspace),
      ).toBe(true);
      stage = "DOCUMENTS";
      expect(
        (
          await reset.request.get(
            `http://127.0.0.1:3400/api/v1/workspaces/${workspace}/documents`,
          )
        ).status(),
      ).toBe(capabilities.includes("documents:read") ? 200 : 403);
      stage = "DOCUMENT_WRITE";
      const upload = await reset.request.post(
        `http://127.0.0.1:3400/api/v1/workspaces/${workspace}/documents`,
        {
          multipart: {
            source_key: "reset-regression",
            file: {
              name: "reset.txt",
              mimeType: "text/plain",
              buffer: Buffer.from(
                "Password recovery preserves authorization for this private Workspace.",
              ),
            },
          },
        },
      );
      expect(upload.status()).toBe(
        capabilities.includes("documents:write") ? 201 : 403,
      );
      stage = "CHAT";
      const conversation = await reset.request.post(
        `http://127.0.0.1:3400/api/v1/workspaces/${workspace}/conversations`,
        { data: {}, headers: { "Idempotency-Key": randomUUID() } },
      );
      expect(conversation.status()).toBe(
        capabilities.includes("questions:ask") ? 201 : 403,
      );
      if (capabilities.includes("questions:ask")) {
        const id = (await conversation.json()).id;
        const turn = await reset.request.post(
          `http://127.0.0.1:3400/api/v1/workspaces/${workspace}/conversations/${id}/turns`,
          {
            data: { question: "What does this empty Workspace contain?" },
            headers: { "Idempotency-Key": randomUUID() },
          },
        );
        expect(turn.status()).toBe(202);
      }
      stage = "WORKSPACE_ISOLATION";
      // A second real account has its own persisted owner identity.
      const otherContext = await browser.newContext();
      contexts.push(otherContext);
      const other = await otherContext.newPage();
      await other.goto("http://127.0.0.1:3400/api/auth/login");
      await other.locator("#username").fill("m5-other-workspace");
      await other.locator("#password").fill("m5-other-workspace-password");
      await other.locator("#kc-login").click();
      await other.waitForURL(/\/workspaces(?:\/[^?]+)?(?:\?.*)?$/);
      const otherWorkspaces = await (
        await other.request.get("http://127.0.0.1:3400/api/v1/workspaces")
      ).json();
      expect(
        otherWorkspaces.items.every((w: { id: string }) => w.id !== workspace),
      ).toBe(true);
      expect(
        (
          await other.request.get(
            `http://127.0.0.1:3400/api/v1/workspaces/${workspace}/documents`,
          )
        ).status(),
      ).toBe(403);
      expect(
        (
          await other.request.post(
            `http://127.0.0.1:3400/api/v1/workspaces/${workspace}/conversations`,
            { data: {}, headers: { "Idempotency-Key": randomUUID() } },
          )
        ).status(),
      ).toBe(403);
      const foreignWorkspace = otherWorkspaces.items[0].id;
      expect(
        (
          await reset.request.get(
            `http://127.0.0.1:3400/api/v1/workspaces/${foreignWorkspace}/documents`,
          )
        ).status(),
      ).toBe(403);
      expect(
        (
          await reset.request.post(
            `http://127.0.0.1:3400/api/v1/workspaces/${foreignWorkspace}/conversations`,
            { data: {}, headers: { "Idempotency-Key": randomUUID() } },
          )
        ).status(),
      ).toBe(403);
    } catch (error) {
      for (const context of contexts)
        for (const current of context.pages())
          await current.goto("about:blank").catch(() => undefined);
      throw passwordResetFailure(stage, error);
    } finally {
      for (const context of contexts.slice(1))
        await context.close().catch(() => undefined);
    }
  });
