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
import { renewSession } from "./session-refresh";

export type KnoraSession = {
  issuer?: string;
  subject: string;
  accessToken: string;
  workspaceIds: string[];
  capabilities: string[];
  expiresAt: number;
  refreshToken?: string;
  refreshExpiresAt?: number;
  sessionId?: string;
  sessionExpiresAt?: number;
};
export type AuthorizationTransaction = {
  state: string;
  nonce: string;
  codeVerifier: string;
  codeChallenge: string;
  redirectUri: string;
  expiresAt: number;
};
const COOKIE = "knora_session";
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

export async function encodeSession(
  session: Omit<KnoraSession, "expiresAt"> & { expiresAt?: number },
): Promise<string> {
  const expiresAt = session.expiresAt ?? Math.floor(Date.now() / 1000) + 3600;
  const sessionExpiresAt =
    session.sessionExpiresAt ?? Math.floor(Date.now() / 1000) + 8 * 3600;
  return new EncryptJWT({
    issuer: session.issuer,
    workspaceIds: session.workspaceIds,
    capabilities: session.capabilities,
    accessToken: session.accessToken,
    expiresAt,
    refreshToken: session.refreshToken,
    refreshExpiresAt: session.refreshExpiresAt,
    sessionId: session.sessionId ?? randomUUID(),
    sessionExpiresAt,
  })
    .setProtectedHeader({ alg: "dir", enc: "A256GCM" })
    .setSubject(session.subject)
    .setExpirationTime(
      session.refreshToken
        ? Math.min(session.refreshExpiresAt ?? expiresAt, sessionExpiresAt)
        : expiresAt,
    )
    .encrypt(encryptionKey());
}
export async function decodeSession(
  value: string | undefined,
): Promise<KnoraSession | null> {
  if (!value) return null;
  try {
    const verified =
      value.split(".").length === 5
        ? await jwtDecrypt(value, encryptionKey(), {
            keyManagementAlgorithms: ["dir"],
            contentEncryptionAlgorithms: ["A256GCM"],
          })
        : await jwtVerify(value, secret(), { algorithms: ["HS256"] });
    const p = verified.payload;
    if (
      typeof p.sub !== "string" ||
      typeof p.accessToken !== "string" ||
      !Array.isArray(p.workspaceIds) ||
      !Array.isArray(p.capabilities)
    )
      return null;
    return {
      issuer: typeof p.issuer === "string" ? p.issuer : undefined,
      subject: p.sub,
      accessToken: p.accessToken,
      refreshToken:
        typeof p.refreshToken === "string" ? p.refreshToken : undefined,
      refreshExpiresAt:
        typeof p.refreshExpiresAt === "number" ? p.refreshExpiresAt : undefined,
      sessionId: typeof p.sessionId === "string" ? p.sessionId : undefined,
      sessionExpiresAt:
        typeof p.sessionExpiresAt === "number" ? p.sessionExpiresAt : undefined,
      workspaceIds: p.workspaceIds.filter(
        (x): x is string => typeof x === "string",
      ),
      capabilities: p.capabilities.filter(
        (x): x is string => typeof x === "string",
      ),
      expiresAt:
        typeof p.expiresAt === "number" ? p.expiresAt : Number(p.exp ?? 0),
    };
  } catch {
    return null;
  }
}
export async function getSession(
  persist = false,
): Promise<KnoraSession | null> {
  const jar = await cookies();
  const previous = await decodeSession(jar.get(COOKIE)?.value);
  if (!previous) return null;
  if (!persist)
    return previous.expiresAt > Math.floor(Date.now() / 1000) ? previous : null;
  const session = await renewSession(previous);
  if (persist && session !== previous) {
    const cookie = session
      ? sessionCookie(await encodeSession(session), session.refreshExpiresAt)
      : clearSessionCookie();
    jar.set(cookie.name, cookie.value, cookie.options as never);
  }
  return session;
}
export function sessionCookie(
  value: string,
  refreshExpiresAt?: number,
): {
  name: string;
  value: string;
  options: Record<string, unknown>;
} {
  return {
    name: COOKIE,
    value,
    options: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: refreshExpiresAt
        ? Math.max(0, refreshExpiresAt - Math.floor(Date.now() / 1000))
        : 3600,
    },
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
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!response.ok) throw new Error("OIDC token exchange failed");
  const token = (await response.json()) as {
    access_token?: string;
    expires_in?: number;
    id_token?: string;
    refresh_token?: string;
    refresh_expires_in?: number;
  };
  if (!token.access_token || !token.id_token)
    throw new Error("OIDC response did not contain required tokens");
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
  if (typeof claims.sub !== "string")
    throw new Error("OIDC identity is missing subject");
  return {
    issuer,
    subject: claims.sub,
    accessToken: token.access_token,
    workspaceIds: claimStrings(claims.workspace_ids),
    capabilities: claimStrings(claims.capabilities),
    expiresAt: Math.floor(Date.now() / 1000) + (token.expires_in ?? 3600),
    refreshToken: token.refresh_token,
    refreshExpiresAt:
      token.refresh_token &&
      typeof token.refresh_expires_in === "number" &&
      token.refresh_expires_in > 0
        ? Math.floor(Date.now() / 1000) + token.refresh_expires_in
        : undefined,
  };
}
function claimStrings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}
export const SESSION_COOKIE_NAME = COOKIE;
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
