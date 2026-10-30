import { jwtDecrypt } from "jose";
import type { BrowserContext } from "@playwright/test";

import { assertFigmaServiceOwnership } from "./figma-auth";
import { figmaEnvironment, figmaRuntimeEnvironment } from "./figma-environment";

export type OwnedBrowserPolicyProjection = {
  rememberMe: boolean;
  sessionStartedAt: number;
  sessionExpiresAt: number;
  expiresAt: number;
  refreshExpiresAt: number;
  cookieExpires?: number;
  cookieHttpOnly: boolean;
  cookieSameSite: string;
};

export async function readOwnedBrowserPolicy(
  context: BrowserContext,
): Promise<OwnedBrowserPolicyProjection> {
  assertFigmaServiceOwnership();
  const env = figmaEnvironment();
  const cookies = await context.cookies(env.baseUrl);
  const cookie = cookies.find((c) => c.name === "knora_session_v2");
  if (!cookie) {
    throw new Error("knora_session_v2 cookie not found");
  }

  const runtimeEnv = figmaRuntimeEnvironment(env);
  const secretKey = new Uint8Array(
    await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(runtimeEnv.SESSION_SECRET),
    ),
  );

  const { payload } = await jwtDecrypt(cookie.value, secretKey);
  const p = payload as Record<string, unknown>;

  if (
    typeof p.rememberMe !== "boolean" ||
    typeof p.sessionStartedAt !== "number" ||
    typeof p.sessionExpiresAt !== "number" ||
    typeof p.expiresAt !== "number" ||
    typeof p.refreshExpiresAt !== "number"
  ) {
    throw new Error("Invalid session policy projection in knora_session_v2");
  }

  return {
    rememberMe: p.rememberMe,
    sessionStartedAt: p.sessionStartedAt,
    sessionExpiresAt: p.sessionExpiresAt,
    expiresAt: p.expiresAt,
    refreshExpiresAt: p.refreshExpiresAt,
    cookieExpires: cookie.expires > 0 ? cookie.expires : undefined,
    cookieHttpOnly: cookie.httpOnly,
    cookieSameSite: cookie.sameSite,
  };
}

export async function getKeycloakAdminToken(): Promise<string> {
  const tokenRes = await fetch(
    "http://127.0.0.1:8380/realms/master/protocol/openid-connect/token",
    {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "password",
        client_id: "admin-cli",
        username: "figma-test-admin",
        password: "figma-test-admin-password",
      }),
    },
  );
  if (!tokenRes.ok) {
    throw new Error(
      `Failed to acquire Keycloak admin token: ${tokenRes.status}`,
    );
  }
  const data = (await tokenRes.json()) as { access_token: string };
  return data.access_token;
}

export async function withAcceleratedSessionPolicy<T>(
  project: string,
  run: () => Promise<T>,
): Promise<T> {
  assertFigmaServiceOwnership();
  const env = figmaEnvironment();
  if (project !== env.project) {
    throw new Error(
      `Accelerated session policy rejected: project ${project} is not isolated test project.`,
    );
  }
  if (env.keycloakIssuer !== "http://127.0.0.1:8380/realms/knora-dev") {
    throw new Error(
      `Accelerated session policy rejected: issuer ${env.keycloakIssuer} is not isolated 8380.`,
    );
  }

  const adminToken = await getKeycloakAdminToken();
  const headers = {
    Authorization: `Bearer ${adminToken}`,
    "Content-Type": "application/json",
  };

  // 1. Read current realm projection
  const realmRes = await fetch("http://127.0.0.1:8380/admin/realms/knora-dev", {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  if (!realmRes.ok) {
    throw new Error(`Failed to read realm knora-dev: ${realmRes.status}`);
  }
  const currentRealm = (await realmRes.json()) as Record<string, unknown>;

  const originalRealmProjection: Record<string, unknown> = {
    ssoSessionIdleTimeout: currentRealm.ssoSessionIdleTimeout,
    ssoSessionMaxLifespan: currentRealm.ssoSessionMaxLifespan,
    ssoSessionIdleTimeoutRememberMe:
      currentRealm.ssoSessionIdleTimeoutRememberMe,
    ssoSessionMaxLifespanRememberMe:
      currentRealm.ssoSessionMaxLifespanRememberMe,
    clientSessionIdleTimeout: currentRealm.clientSessionIdleTimeout,
    clientSessionMaxLifespan: currentRealm.clientSessionMaxLifespan,
    accessTokenLifespan: currentRealm.accessTokenLifespan,
  };

  // 2. Read client knora-web
  const clientsRes = await fetch(
    "http://127.0.0.1:8380/admin/realms/knora-dev/clients?clientId=knora-web",
    { headers: { Authorization: `Bearer ${adminToken}` } },
  );
  if (!clientsRes.ok) {
    throw new Error(`Failed to list clients: ${clientsRes.status}`);
  }
  const clients = (await clientsRes.json()) as Array<{
    id: string;
    clientId: string;
    attributes?: Record<string, string>;
  }>;
  if (!clients.length) {
    throw new Error("knora-web client not found in realm knora-dev");
  }
  const client = clients[0];
  const originalAttributes = { ...(client.attributes ?? {}) };
  const originalLifespanPresent = "access.token.lifespan" in originalAttributes;
  const originalLifespanValue = originalAttributes["access.token.lifespan"];

  let realmMutated = false;
  let clientMutated = false;
  const cleanupErrors: Error[] = [];

  const restoreAll = async () => {
    // Independent restore of client
    if (clientMutated) {
      try {
        const freshClientRes = await fetch(
          `http://127.0.0.1:8380/admin/realms/knora-dev/clients/${client.id}`,
          { headers: { Authorization: `Bearer ${adminToken}` } },
        );
        if (!freshClientRes.ok) {
          throw new Error(
            `Failed to fetch fresh client before restore: ${freshClientRes.status}`,
          );
        }
        const freshClient = (await freshClientRes.json()) as {
          id: string;
          clientId: string;
          attributes?: Record<string, string>;
        };
        const currentAttrs = { ...(freshClient.attributes ?? {}) };

        // Drift check on managed attribute
        if (currentAttrs["access.token.lifespan"] !== "5") {
          throw new Error(
            `Client access.token.lifespan drift detected before restore: expected "5", found "${currentAttrs["access.token.lifespan"]}"`,
          );
        }

        // Restore managed attribute without wiping unrelated attributes
        if (originalLifespanPresent) {
          currentAttrs["access.token.lifespan"] = originalLifespanValue;
        } else {
          delete currentAttrs["access.token.lifespan"];
        }

        const restoreClientRes = await fetch(
          `http://127.0.0.1:8380/admin/realms/knora-dev/clients/${client.id}`,
          {
            method: "PUT",
            headers,
            body: JSON.stringify({
              id: client.id,
              clientId: client.clientId,
              attributes: currentAttrs,
            }),
          },
        );
        if (!restoreClientRes.ok) {
          throw new Error(
            `Failed to restore client attributes: ${restoreClientRes.status}`,
          );
        }

        // Readback check
        const verifyClientRes = await fetch(
          `http://127.0.0.1:8380/admin/realms/knora-dev/clients/${client.id}`,
          { headers: { Authorization: `Bearer ${adminToken}` } },
        );
        const verifiedClient = (await verifyClientRes.json()) as {
          attributes?: Record<string, string>;
        };
        const finalLifespan =
          verifiedClient.attributes?.["access.token.lifespan"];
        if (
          originalLifespanPresent &&
          finalLifespan !== originalLifespanValue
        ) {
          throw new Error(
            "Restored client access.token.lifespan readback mismatch",
          );
        }
        if (!originalLifespanPresent && finalLifespan !== undefined) {
          throw new Error(
            "Restored client access.token.lifespan was not removed",
          );
        }
      } catch (err) {
        cleanupErrors.push(err instanceof Error ? err : new Error(String(err)));
      }
    }

    // Independent restore of realm
    if (realmMutated) {
      try {
        const freshRealmRes = await fetch(
          "http://127.0.0.1:8380/admin/realms/knora-dev",
          {
            headers: { Authorization: `Bearer ${adminToken}` },
          },
        );
        if (!freshRealmRes.ok) {
          throw new Error(
            `Failed to fetch fresh realm before restore: ${freshRealmRes.status}`,
          );
        }
        const freshRealm = (await freshRealmRes.json()) as Record<
          string,
          unknown
        >;

        // Drift check on accelerated realm fields
        const acceleratedExpected: Record<string, unknown> = {
          ssoSessionIdleTimeout: 10,
          ssoSessionMaxLifespan: 30,
          ssoSessionIdleTimeoutRememberMe: 20,
          ssoSessionMaxLifespanRememberMe: 60,
          accessTokenLifespan: 5,
          clientSessionIdleTimeout: 0,
          clientSessionMaxLifespan: 0,
        };
        for (const [k, v] of Object.entries(acceleratedExpected)) {
          if (freshRealm[k] !== v) {
            throw new Error(
              `Realm ${k} drift detected before restore: expected ${v}, found ${freshRealm[k]}`,
            );
          }
        }

        const restoreRealmRes = await fetch(
          "http://127.0.0.1:8380/admin/realms/knora-dev",
          {
            method: "PUT",
            headers,
            body: JSON.stringify({
              ...freshRealm,
              ...originalRealmProjection,
            }),
          },
        );
        if (!restoreRealmRes.ok) {
          throw new Error(
            `Failed to restore realm policy: ${restoreRealmRes.status}`,
          );
        }

        // Readback check
        const verifyRealmRes = await fetch(
          "http://127.0.0.1:8380/admin/realms/knora-dev",
          {
            headers: { Authorization: `Bearer ${adminToken}` },
          },
        );
        const finalRealm = (await verifyRealmRes.json()) as Record<
          string,
          unknown
        >;
        for (const [key, val] of Object.entries(originalRealmProjection)) {
          if (finalRealm[key] !== val) {
            throw new Error(
              `Restored realm policy readback mismatch on ${key}`,
            );
          }
        }
      } catch (err) {
        cleanupErrors.push(err instanceof Error ? err : new Error(String(err)));
      }
    }

    if (cleanupErrors.length > 0) {
      const messages = cleanupErrors.map((e) => e.message).join("; ");
      throw new Error(`Accelerated policy cleanup failed: ${messages}`);
    }
  };

  try {
    // 3. Apply accelerated settings: PUT realm
    const freshRealmForPut = (await (
      await fetch("http://127.0.0.1:8380/admin/realms/knora-dev", {
        headers: { Authorization: `Bearer ${adminToken}` },
      })
    ).json()) as Record<string, unknown>;

    const putRealmRes = await fetch(
      "http://127.0.0.1:8380/admin/realms/knora-dev",
      {
        method: "PUT",
        headers,
        body: JSON.stringify({
          ...freshRealmForPut,
          ssoSessionIdleTimeout: 10,
          ssoSessionMaxLifespan: 30,
          ssoSessionIdleTimeoutRememberMe: 20,
          ssoSessionMaxLifespanRememberMe: 60,
          accessTokenLifespan: 5,
          clientSessionIdleTimeout: 0,
          clientSessionMaxLifespan: 0,
        }),
      },
    );
    if (!putRealmRes.ok) {
      throw new Error(
        `Failed to apply accelerated realm policy: ${putRealmRes.status}`,
      );
    }
    realmMutated = true;

    // PUT client
    const freshClientForPut = (await (
      await fetch(
        `http://127.0.0.1:8380/admin/realms/knora-dev/clients/${client.id}`,
        { headers: { Authorization: `Bearer ${adminToken}` } },
      )
    ).json()) as {
      id: string;
      clientId: string;
      attributes?: Record<string, string>;
    };

    const updatedAttributes = {
      ...(freshClientForPut.attributes ?? {}),
      "access.token.lifespan": "5",
    };
    const putClientRes = await fetch(
      `http://127.0.0.1:8380/admin/realms/knora-dev/clients/${client.id}`,
      {
        method: "PUT",
        headers,
        body: JSON.stringify({
          id: client.id,
          clientId: client.clientId,
          attributes: updatedAttributes,
        }),
      },
    );
    if (!putClientRes.ok) {
      throw new Error(
        `Failed to apply accelerated client attribute: ${putClientRes.status}`,
      );
    }
    clientMutated = true;

    // 4. Verify readback before run
    const readbackRealmRes = await fetch(
      "http://127.0.0.1:8380/admin/realms/knora-dev",
      {
        headers: { Authorization: `Bearer ${adminToken}` },
      },
    );
    const verifiedRealm = (await readbackRealmRes.json()) as Record<
      string,
      unknown
    >;
    if (
      verifiedRealm.ssoSessionIdleTimeout !== 10 ||
      verifiedRealm.ssoSessionMaxLifespan !== 30 ||
      verifiedRealm.ssoSessionIdleTimeoutRememberMe !== 20 ||
      verifiedRealm.ssoSessionMaxLifespanRememberMe !== 60 ||
      verifiedRealm.accessTokenLifespan !== 5 ||
      verifiedRealm.clientSessionIdleTimeout !== 0 ||
      verifiedRealm.clientSessionMaxLifespan !== 0
    ) {
      throw new Error("Accelerated realm policy readback mismatch");
    }

    const readbackClientRes = await fetch(
      `http://127.0.0.1:8380/admin/realms/knora-dev/clients/${client.id}`,
      { headers: { Authorization: `Bearer ${adminToken}` } },
    );
    const verifiedClient = (await readbackClientRes.json()) as {
      attributes?: Record<string, string>;
    };
    if (verifiedClient.attributes?.["access.token.lifespan"] !== "5") {
      throw new Error("Accelerated client attribute readback mismatch");
    }

    return await run();
  } finally {
    await restoreAll();
  }
}
