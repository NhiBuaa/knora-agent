import { createHash } from "node:crypto";
import { createRemoteJWKSet, jwtVerify } from "jose";
import type { KnoraSession } from "./session";

export class SessionRefreshUnavailable extends Error {
  constructor() {
    super("SESSION_REFRESH_UNAVAILABLE");
  }
}

// This coordinator is for the current single Next.js server topology. A shared
// coordinator is required before enabling rotated refresh tokens across replicas.
type Coordinator = {
  renewals: Map<
    string,
    { until: number; result: Promise<KnoraSession | null> }
  >;
  revoked: Map<string, number>;
};
// Middleware and app routes have separate compiled module caches. Share one
// coordinator on the Node global object, including across development reloads.
const coordinatorKey = Symbol.for("knora.auth.refresh-coordinator.v1");
const shared = globalThis as typeof globalThis & {
  [coordinatorKey]?: Coordinator;
};
const coordinator = (shared[coordinatorKey] ??= {
  renewals: new Map(),
  revoked: new Map(),
});
const { renewals, revoked } = coordinator;
export function invalidateSession(session: KnoraSession | null) {
  if (session?.sessionId)
    revoked.set(
      session.sessionId,
      session.sessionExpiresAt ?? Math.floor(Date.now() / 1000) + 8 * 3600,
    );
}

export async function renewSession(
  session: KnoraSession,
): Promise<KnoraSession | null> {
  const now = Math.floor(Date.now() / 1000);
  for (const [id, until] of revoked) if (until <= now) revoked.delete(id);
  if (
    (session.sessionId && revoked.has(session.sessionId)) ||
    (session.sessionExpiresAt && session.sessionExpiresAt <= now)
  )
    return null;
  if (session.expiresAt > now + 30) return session;
  if (
    !session.refreshToken ||
    !session.refreshExpiresAt ||
    session.refreshExpiresAt <= now
  ) {
    return session.expiresAt > now ? session : null;
  }
  const key = createHash("sha256").update(session.refreshToken).digest("hex");
  for (const [id, entry] of renewals)
    if (entry.until <= now) renewals.delete(id);
  let renewal = renewals.get(key);
  if (!renewal) {
    if (renewals.size >= 256) throw new SessionRefreshUnavailable();
    renewal = { until: now + 30, result: refresh(session) };
    renewals.set(key, renewal);
    void renewal.result.catch(() => {
      renewals.delete(key);
    });
  }
  try {
    const result = await renewal.result;
    return session.sessionId && revoked.has(session.sessionId) ? null : result;
  } catch {
    if (session.sessionId && revoked.has(session.sessionId)) return null;
    if (session.expiresAt > Math.floor(Date.now() / 1000)) return session;
    throw new SessionRefreshUnavailable();
  }
}

async function refresh(session: KnoraSession): Promise<KnoraSession | null> {
  const endpoint = process.env.KEYCLOAK_TOKEN_URL;
  const issuer = process.env.KEYCLOAK_ISSUER;
  const jwks = process.env.KEYCLOAK_JWKS_URL;
  if (!endpoint || !issuer || !jwks || session.issuer !== issuer)
    throw new SessionRefreshUnavailable();
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: session.refreshToken!,
    client_id: process.env.KEYCLOAK_CLIENT_ID ?? "knora-web",
  });
  if (process.env.KEYCLOAK_CLIENT_SECRET)
    body.set("client_secret", process.env.KEYCLOAK_CLIENT_SECRET);
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body,
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) {
    if (response.status === 400) {
      const error = (await response.json()) as { error?: string };
      if (error.error === "invalid_grant") return null;
    }
    throw new SessionRefreshUnavailable();
  }
  const token = (await response.json()) as {
    access_token?: string;
    refresh_token?: string;
    id_token?: string;
    expires_in?: number;
    refresh_expires_in?: number;
  };
  if (
    !token.access_token ||
    !token.refresh_token ||
    !token.id_token ||
    !token.expires_in ||
    token.expires_in <= 0 ||
    !token.refresh_expires_in ||
    token.refresh_expires_in <= 0
  )
    throw new SessionRefreshUnavailable();
  const { payload } = await jwtVerify(
    token.id_token,
    createRemoteJWKSet(new URL(jwks)),
    {
      issuer,
      audience:
        process.env.KEYCLOAK_AUDIENCE ??
        process.env.KEYCLOAK_CLIENT_ID ??
        "knora-web",
      algorithms: ["RS256"],
    },
  );
  if (payload.sub !== session.subject) throw new SessionRefreshUnavailable();
  const strings = (value: unknown) =>
    Array.isArray(value)
      ? value.filter((v): v is string => typeof v === "string")
      : [];
  const now = Math.floor(Date.now() / 1000);
  return {
    ...session,
    accessToken: token.access_token,
    refreshToken: token.refresh_token,
    expiresAt: now + token.expires_in,
    refreshExpiresAt: Math.min(
      now + token.refresh_expires_in,
      session.sessionExpiresAt ?? now + 8 * 3600,
    ),
    workspaceIds: strings(payload.workspace_ids),
    capabilities: strings(payload.capabilities),
  };
}
