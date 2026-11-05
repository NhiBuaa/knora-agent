import { cookies } from "next/headers";
import { Buffer } from "node:buffer";
import { TextEncoder } from "node:util";
import {
  createHash,
  createHmac,
  randomBytes,
  randomUUID,
  timingSafeEqual,
} from "node:crypto";
import { createRemoteJWKSet, jwtVerify, EncryptJWT, jwtDecrypt } from "jose";
import { isSessionRevoked, renewSession } from "./session-refresh";
import {
  isSessionPolicy,
  policyFromClaims,
  SessionPolicy,
  SESSION_POLICY_VERSION,
  tokenDeadlines,
} from "./session-policy";

export type KnoraSession = SessionPolicy & {
  issuer: string;
  subject: string;
  accessToken: string;
  refreshToken: string;
  workspaceIds: string[];
  capabilities: string[];
  expiresAt: number;
  refreshExpiresAt: number;
  sessionId: string;
};

export type AuthorizationTransaction = {
  state: string;
  nonce: string;
  codeVerifier: string;
  codeChallenge: string;
  redirectUri: string;
  expiresAt: number;
};

const COOKIE = "knora_session_v2";
const LEGACY_COOKIE = "knora_session";
const TRANSACTION_COOKIE = "knora_oidc_transaction";

const secret = () =>
  new TextEncoder().encode(
    process.env.SESSION_SECRET ?? "development-only-session-secret-change-me",
  );
const encryptionKey = () => createHash("sha256").update(secret()).digest();

export function createAuthorizationTransaction(
  redirectUri: string,
): AuthorizationTransaction {
  const state = randomBytes(32).toString("base64url");
  const nonce = randomBytes(32).toString("base64url");
  const codeVerifier = randomBytes(48).toString("base64url");
  const codeChallenge = createHash("sha256")
    .update(codeVerifier)
    .digest("base64url");
  return {
    state,
    nonce,
    codeVerifier,
    codeChallenge,
    redirectUri,
    expiresAt: Math.floor(Date.now() / 1000) + 600,
  };
}

export async function encodeAuthorizationTransaction(
  transaction: AuthorizationTransaction,
): Promise<string> {
  const payload = Buffer.from(JSON.stringify(transaction)).toString(
    "base64url",
  );
  const signature = createHmac("sha256", secret())
    .update(payload)
    .digest("base64url");
  return `${payload}.${signature}`;
}

export async function decodeAuthorizationTransaction(
  value: string | undefined,
): Promise<AuthorizationTransaction | null> {
  if (!value) return null;
  try {
    const [payloadValue, signatureValue] = value.split(".");
    if (!payloadValue || !signatureValue) return null;
    const expected = createHmac("sha256", secret())
      .update(payloadValue)
      .digest();
    const provided = Buffer.from(signatureValue, "base64url");
    if (
      signatureValue !== expected.toString("base64url") ||
      provided.length !== expected.length ||
      !timingSafeEqual(provided, expected)
    )
      return null;
    const payload = JSON.parse(
      Buffer.from(payloadValue, "base64url").toString("utf8"),
    ) as Record<string, unknown>;
    if (
      typeof payload.state !== "string" ||
      typeof payload.nonce !== "string" ||
      typeof payload.codeVerifier !== "string" ||
      typeof payload.codeChallenge !== "string" ||
      typeof payload.redirectUri !== "string" ||
      typeof payload.expiresAt !== "number"
    )
      return null;
    if (payload.expiresAt <= Math.floor(Date.now() / 1000)) return null;
    return {
      state: payload.state,
      nonce: payload.nonce,
      codeVerifier: payload.codeVerifier,
      codeChallenge: payload.codeChallenge,
      redirectUri: payload.redirectUri,
      expiresAt: payload.expiresAt,
    };
  } catch {
    return null;
  }
}

export async function encodeSession(session: KnoraSession): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  if (!isSessionPolicy(session, now)) {
    throw new Error("SESSION_POLICY_INVALID");
  }
  if (
    typeof session.expiresAt !== "number" ||
    !Number.isSafeInteger(session.expiresAt) ||
    typeof session.refreshExpiresAt !== "number" ||
    !Number.isSafeInteger(session.refreshExpiresAt) ||
    session.expiresAt > session.refreshExpiresAt ||
    session.refreshExpiresAt > session.sessionExpiresAt
  ) {
    throw new Error("SESSION_EXPIRIES_INVALID");
  }

  const exp = Math.min(session.refreshExpiresAt, session.sessionExpiresAt);

  return new EncryptJWT({
    policyVersion: session.policyVersion,
    rememberMe: session.rememberMe,
    sessionStartedAt: session.sessionStartedAt,
    sessionExpiresAt: session.sessionExpiresAt,
    issuer: session.issuer,
    workspaceIds: session.workspaceIds,
    capabilities: session.capabilities,
    accessToken: session.accessToken,
    expiresAt: session.expiresAt,
    refreshToken: session.refreshToken,
    refreshExpiresAt: session.refreshExpiresAt,
    sessionId: session.sessionId,
  })
    .setProtectedHeader({ alg: "dir", enc: "A256GCM" })
    .setSubject(session.subject)
    .setIssuer(session.issuer)
    .setExpirationTime(exp)
    .encrypt(encryptionKey());
}

export async function decodeSession(
  value: string | undefined,
): Promise<KnoraSession | null> {
  if (!value) return null;
  if (value.split(".").length !== 5) return null;
  try {
    const verified = await jwtDecrypt(value, encryptionKey(), {
      keyManagementAlgorithms: ["dir"],
      contentEncryptionAlgorithms: ["A256GCM"],
    });
    const p = verified.payload as Record<string, unknown>;
    if (
      typeof p.sub !== "string" ||
      !p.sub ||
      typeof p.issuer !== "string" ||
      !p.issuer ||
      typeof p.accessToken !== "string" ||
      !p.accessToken ||
      typeof p.refreshToken !== "string" ||
      !p.refreshToken ||
      typeof p.sessionId !== "string" ||
      !p.sessionId ||
      !Array.isArray(p.workspaceIds) ||
      !Array.isArray(p.capabilities)
    ) {
      return null;
    }

    if (
      process.env.KEYCLOAK_ISSUER &&
      p.issuer !== process.env.KEYCLOAK_ISSUER
    ) {
      return null;
    }

    if (p.policyVersion !== SESSION_POLICY_VERSION) return null;
    if (typeof p.rememberMe !== "boolean") return null;
    if (
      typeof p.sessionStartedAt !== "number" ||
      !Number.isSafeInteger(p.sessionStartedAt) ||
      p.sessionStartedAt <= 0
    ) {
      return null;
    }

    const expectedMax = p.rememberMe ? 2_592_000 : 28_800;
    const expectedCap = p.sessionStartedAt + expectedMax;
    if (
      typeof p.sessionExpiresAt !== "number" ||
      !Number.isSafeInteger(p.sessionExpiresAt) ||
      p.sessionExpiresAt !== expectedCap
    ) {
      return null;
    }

    if (
      typeof p.expiresAt !== "number" ||
      !Number.isSafeInteger(p.expiresAt) ||
      typeof p.refreshExpiresAt !== "number" ||
      !Number.isSafeInteger(p.refreshExpiresAt) ||
      p.expiresAt > p.refreshExpiresAt ||
      p.refreshExpiresAt > p.sessionExpiresAt
    ) {
      return null;
    }

    const expectedExp = Math.min(p.refreshExpiresAt, p.sessionExpiresAt);
    if (typeof p.exp !== "number" || p.exp !== expectedExp) {
      return null;
    }

    const now = Math.floor(Date.now() / 1000);
    if (p.sessionExpiresAt <= now || p.refreshExpiresAt <= now) {
      return null;
    }

    return {
      policyVersion: 1,
      rememberMe: p.rememberMe,
      sessionStartedAt: p.sessionStartedAt,
      sessionExpiresAt: p.sessionExpiresAt,
      issuer: p.issuer,
      subject: p.sub,
      accessToken: p.accessToken,
      refreshToken: p.refreshToken,
      sessionId: p.sessionId,
      expiresAt: p.expiresAt,
      refreshExpiresAt: p.refreshExpiresAt,
      workspaceIds: p.workspaceIds.filter(
        (x): x is string => typeof x === "string",
      ),
      capabilities: p.capabilities.filter(
        (x): x is string => typeof x === "string",
      ),
    };
  } catch {
    return null;
  }
}

export async function getSession(
  persist = false,
): Promise<KnoraSession | null> {
  const jar = await cookies();
  const legacyValue = jar.get(LEGACY_COOKIE)?.value;
  const rawValue = jar.get(COOKIE)?.value;
  const previous = await decodeSession(rawValue);

  if (!previous) {
    if (persist && (rawValue || legacyValue)) {
      if (rawValue) {
        const c = clearSessionCookie();
        jar.set(c.name, c.value, c.options as never);
      }
      if (legacyValue) {
        const c = clearLegacySessionCookie();
        jar.set(c.name, c.value, c.options as never);
      }
    }
    return null;
  }

  if (!persist) {
    const now = Math.floor(Date.now() / 1000);
    return previous.expiresAt > now ? previous : null;
  }

  const session = await renewSession(previous);
  if (persist && (session !== previous || legacyValue)) {
    if (legacyValue) {
      const c = clearLegacySessionCookie();
      jar.set(c.name, c.value, c.options as never);
    }
    if (session) {
      const encoded = await encodeSession(session);
      const now = Math.floor(Date.now() / 1000);
      if (
        isSessionRevoked(session.sessionId) ||
        session.sessionExpiresAt <= now ||
        session.refreshExpiresAt <= now
      ) {
        const c = clearSessionCookie();
        jar.set(c.name, c.value, c.options as never);
        return null;
      }
      const cookie = sessionCookie(encoded, session);
      jar.set(cookie.name, cookie.value, cookie.options as never);
    } else {
      const c = clearSessionCookie();
      jar.set(c.name, c.value, c.options as never);
    }
  }
  return session;
}

export function sessionCookie(
  value: string,
  session: KnoraSession,
): {
  name: string;
  value: string;
  options: Record<string, unknown>;
} {
  const options: Record<string, unknown> = {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
  };
  if (session.rememberMe) {
    const now = Math.floor(Date.now() / 1000);
    const deadline = Math.min(
      session.refreshExpiresAt,
      session.sessionExpiresAt,
    );
    options.maxAge = Math.max(0, deadline - now);
  }
  return {
    name: COOKIE,
    value,
    options,
  };
}

export function clearSessionCookie() {
  return {
    name: COOKIE,
    value: "",
    options: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 0,
    },
  };
}

export function clearLegacySessionCookie() {
  return {
    name: LEGACY_COOKIE,
    value: "",
    options: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 0,
    },
  };
}

export async function exchangeCode(
  code: string,
  redirectUri: string,
  codeVerifier: string,
  nonce: string,
): Promise<KnoraSession> {
  const endpoint = process.env.KEYCLOAK_TOKEN_URL;
  if (!endpoint) throw new Error("KEYCLOAK_TOKEN_URL is not configured");
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri,
    client_id: process.env.KEYCLOAK_CLIENT_ID ?? "knora-web",
    code_verifier: codeVerifier,
  });
  if (process.env.KEYCLOAK_CLIENT_SECRET)
    body.set("client_secret", process.env.KEYCLOAK_CLIENT_SECRET);
  const requestedAt = Math.floor(Date.now() / 1000);
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body,
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("OIDC token exchange failed");
  const token = (await response.json()) as {
    access_token?: string;
    expires_in?: number;
    id_token?: string;
    refresh_token?: string;
    refresh_expires_in?: number;
  };
  if (
    typeof token.access_token !== "string" ||
    !token.access_token ||
    typeof token.refresh_token !== "string" ||
    !token.refresh_token ||
    typeof token.id_token !== "string" ||
    !token.id_token
  ) {
    throw new Error("OIDC response did not contain required tokens");
  }
  if (
    typeof token.expires_in !== "number" ||
    !Number.isSafeInteger(token.expires_in) ||
    token.expires_in <= 0 ||
    token.expires_in > 300
  ) {
    throw new Error("OIDC response invalid expires_in");
  }
  if (
    typeof token.refresh_expires_in !== "number" ||
    !Number.isSafeInteger(token.refresh_expires_in) ||
    token.refresh_expires_in <= 0
  ) {
    throw new Error("OIDC response invalid refresh_expires_in");
  }
  const jwksUrl = process.env.KEYCLOAK_JWKS_URL;
  const issuer = process.env.KEYCLOAK_ISSUER;
  const audience =
    process.env.KEYCLOAK_AUDIENCE ??
    process.env.KEYCLOAK_CLIENT_ID ??
    "knora-web";
  if (!jwksUrl || !issuer)
    throw new Error("OIDC verification is not configured");
  const { payload: claims } = await jwtVerify(
    token.id_token,
    createRemoteJWKSet(new URL(jwksUrl)),
    { issuer, audience, algorithms: ["RS256"] },
  );
  if (claims.nonce !== nonce) throw new Error("OIDC nonce mismatch");
  if (typeof claims.sub !== "string" || !claims.sub)
    throw new Error("OIDC identity is missing subject");

  const now = Math.floor(Date.now() / 1000);
  const policy = policyFromClaims(claims, now);
  const deadlines = tokenDeadlines(
    policy,
    token.expires_in,
    token.refresh_expires_in,
    requestedAt,
    now,
  );
  const sessionId = randomUUID();

  return {
    ...policy,
    issuer,
    subject: claims.sub,
    accessToken: token.access_token,
    refreshToken: token.refresh_token,
    workspaceIds: claimStrings(claims.workspace_ids),
    capabilities: claimStrings(claims.capabilities),
    expiresAt: deadlines.expiresAt,
    refreshExpiresAt: deadlines.refreshExpiresAt,
    sessionId,
  };
}

function claimStrings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

export const SESSION_COOKIE_NAME = COOKIE;
export const LEGACY_SESSION_COOKIE_NAME = LEGACY_COOKIE;
export const AUTH_TRANSACTION_COOKIE_NAME = TRANSACTION_COOKIE;

export function authorizationTransactionCookie(value: string): {
  name: string;
  value: string;
  options: Record<string, unknown>;
} {
  return {
    name: TRANSACTION_COOKIE,
    value,
    options: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/api/auth",
      maxAge: 600,
    },
  };
}

export function clearAuthorizationTransactionCookie() {
  return {
    name: TRANSACTION_COOKIE,
    value: "",
    options: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/api/auth",
      maxAge: 0,
    },
  };
}
