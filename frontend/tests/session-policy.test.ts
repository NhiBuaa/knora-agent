import { expect, it, vi } from "vitest";

vi.mock("./e2e/support/figma-auth", () => ({
  assertFigmaServiceOwnership: () => {},
}));

vi.mock("./e2e/support/figma-environment", () => ({
  figmaEnvironment: () => ({
    project: "knora-figma-e2e-session-reviewprobe",
    keycloakIssuer: "http://127.0.0.1:8380/realms/knora-dev",
  }),
  figmaRuntimeEnvironment: () => ({}),
}));

import { withAcceleratedSessionPolicy } from "./e2e/support/session-policy";

it("REVIEW2_POLICY_PROBE rejects managed realm drift before its first write", async () => {
  let realm = {
    ssoSessionIdleTimeout: 1800,
    ssoSessionMaxLifespan: 28800,
    ssoSessionIdleTimeoutRememberMe: 604800,
    ssoSessionMaxLifespanRememberMe: 2592000,
    clientSessionIdleTimeout: 0,
    clientSessionMaxLifespan: 0,
    accessTokenLifespan: 300,
  };
  let client = {
    id: "owned-client",
    clientId: "knora-web",
    attributes: { "access.token.lifespan": "300" },
  };
  let realmReads = 0;
  let realmWrites = 0;
  const run = vi.fn(async () => "ran");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url, init: RequestInit = {}) => {
      const uri = String(url);
      if (uri.includes("protocol/openid-connect/token"))
        return Response.json({ access_token: "synthetic-probe-token" });
      if (uri.includes("clients?clientId=")) return Response.json([client]);
      if (uri.endsWith("/clients/owned-client")) {
        if (init.method === "PUT")
          client = { ...client, ...JSON.parse(String(init.body)) };
        return Response.json(client);
      }
      if (uri.endsWith("/admin/realms/knora-dev")) {
        if (init.method === "PUT") {
          realmWrites++;
          realm = { ...realm, ...JSON.parse(String(init.body)) };
          return new Response(null, { status: 204 });
        }
        if (++realmReads === 2) realm.ssoSessionIdleTimeout = 999;
        return Response.json(realm);
      }
      throw new Error("Unexpected probe URL");
    }),
  );
  await expect(
    withAcceleratedSessionPolicy("knora-figma-e2e-session-reviewprobe", run),
  ).rejects.toThrow(/drift|concurrent/i);
  expect(realmWrites).toBe(0);
  expect(run).not.toHaveBeenCalled();
});
