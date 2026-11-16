import { EncryptJWT, jwtDecrypt } from "jose";
import { createHash, randomUUID } from "node:crypto";
import { TextEncoder } from "node:util";
import type { KnoraSession } from "./session";
import {
  getSupabaseConfig,
  verifySupabaseJwt,
  fetchBackendSession,
  type SupabaseTokens,
} from "./supabase";

export const RECOVERY_COOKIE_NAME = "knora_recovery";

export class SessionRevocationError extends Error {
  status: number;
  constructor(message: string, status = 503) {
    super(message);
    this.name = "SessionRevocationError";
    this.status = status;
  }
}

const secret = () =>
  new TextEncoder().encode(
    process.env.SESSION_SECRET ?? "development-only-session-secret-change-me",
  );
const encryptionKey = () => createHash("sha256").update(secret()).digest();

export async function requestRecovery(email: string): Promise<void> {
  const config = getSupabaseConfig();
  const endpoint = `${config.url}/auth/v1/recover`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      apikey: config.publishableKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email }),
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });

  if (response.status === 429) {
    throw new Error("RATE_LIMIT_EXCEEDED");
  }

  // Supabase returns 200 whether email exists or not.
  // Other non-200 responses are treated as provider errors.
  if (!response.ok && response.status !== 200) {
    throw new Error(
      `Provider recovery request failed with status ${response.status}`,
    );
  }
}

export async function verifyRecovery(
  email: string,
  code: string,
): Promise<KnoraSession> {
  const config = getSupabaseConfig();
  const endpoint = `${config.url}/auth/v1/verify`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      apikey: config.publishableKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      token: code,
      type: "recovery",
    }),
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => ({}))) as {
      error_description?: string;
      msg?: string;
    };
    throw new Error(
      errorBody.error_description ||
        errorBody.msg ||
        "Invalid or expired recovery code",
    );
  }

  const data = (await response.json()) as {
    session?: SupabaseTokens;
    access_token?: string;
  };
  const tokens = (data.session || data) as SupabaseTokens;
  if (!tokens.access_token) {
    throw new Error("Recovery verification succeeded but no session returned");
  }

  const verified = await verifySupabaseJwt(tokens.access_token);
  const backend = await fetchBackendSession(tokens.access_token);

  const now = Math.floor(Date.now() / 1000);
  return {
    provider: "supabase",
    providerSessionId: verified.sessionId,
    issuer: verified.issuer,
    subject: verified.sub,
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    expiresAt: now + (tokens.expires_in || 300),
    sessionExpiresAt: now + 300, // Capped at 5 minutes for recovery flow
    sessionId: randomUUID(),
    capabilities: backend.capabilities,
    workspaceIds: [],
  };
}

export async function updateRecoveredPassword(
  recovery: KnoraSession,
  password: string,
): Promise<void> {
  const config = getSupabaseConfig();

  // First verify backend session state before updating password
  await fetchBackendSession(recovery.accessToken);

  // Update password via PUT /user
  const endpoint = `${config.url}/auth/v1/user`;
  const response = await fetch(endpoint, {
    method: "PUT",
    headers: {
      apikey: config.publishableKey,
      Authorization: `Bearer ${recovery.accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ password }),
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => ({}))) as {
      error_description?: string;
      msg?: string;
    };
    throw new Error(
      errorBody.error_description ||
        errorBody.msg ||
        "Failed to update password",
    );
  }

  // Revoke provider sessions with scope=global
  const logoutEndpoint = `${config.url}/auth/v1/logout?scope=global`;
  let logoutResponse: Response;
  try {
    logoutResponse = await fetch(logoutEndpoint, {
      method: "POST",
      headers: {
        apikey: config.publishableKey,
        Authorization: `Bearer ${recovery.accessToken}`,
        "Content-Type": "application/json",
      },
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
  } catch (_err) {
    throw new SessionRevocationError(
      "Failed to reach authentication provider to revoke active sessions.",
      503,
    );
  }

  if (!logoutResponse.ok) {
    const status = logoutResponse.status >= 500 ? 503 : logoutResponse.status;
    throw new SessionRevocationError(
      `Failed to revoke active sessions after password update (status: ${logoutResponse.status}).`,
      status,
    );
  }
}

export async function encodeRecoverySession(
  session: KnoraSession,
  email: string,
): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const expiresAt = now + 300; // Capped at 5 minutes
  return new EncryptJWT({
    purpose: "recovery",
    email,
    provider: session.provider,
    providerSessionId: session.providerSessionId,
    issuer: session.issuer,
    sub: session.subject,
    accessToken: session.accessToken,
    refreshToken: session.refreshToken,
    sessionId: session.sessionId,
    workspaceIds: session.workspaceIds,
    capabilities: session.capabilities,
    expiresAt,
  })
    .setProtectedHeader({ alg: "dir", enc: "A256GCM" })
    .setIssuedAt(now)
    .setExpirationTime(expiresAt)
    .encrypt(encryptionKey());
}

export async function decodeRecoverySession(
  value: string | undefined,
): Promise<{ session: KnoraSession; email: string } | null> {
  if (!value) return null;
  try {
    const verified = await jwtDecrypt(value, encryptionKey(), {
      keyManagementAlgorithms: ["dir"],
      contentEncryptionAlgorithms: ["A256GCM"],
    });
    const p = verified.payload;
    if (p.purpose !== "recovery") return null;
    if (
      typeof p.sub !== "string" ||
      typeof p.accessToken !== "string" ||
      typeof p.email !== "string"
    ) {
      return null;
    }
    const now = Math.floor(Date.now() / 1000);
    const exp = typeof p.exp === "number" ? p.exp : 0;
    if (exp <= now) return null;

    return {
      email: p.email,
      session: {
        provider: "supabase",
        providerSessionId:
          typeof p.providerSessionId === "string"
            ? p.providerSessionId
            : undefined,
        issuer: typeof p.issuer === "string" ? p.issuer : undefined,
        subject: p.sub,
        accessToken: p.accessToken,
        refreshToken:
          typeof p.refreshToken === "string" ? p.refreshToken : undefined,
        expiresAt: typeof p.expiresAt === "number" ? p.expiresAt : exp,
        sessionExpiresAt: exp,
        sessionId: typeof p.sessionId === "string" ? p.sessionId : undefined,
        workspaceIds: Array.isArray(p.workspaceIds)
          ? p.workspaceIds.filter((x): x is string => typeof x === "string")
          : [],
        capabilities: Array.isArray(p.capabilities)
          ? p.capabilities.filter((x): x is string => typeof x === "string")
          : [],
      },
    };
  } catch {
    return null;
  }
}

export function recoveryCookie(value: string) {
  return {
    name: RECOVERY_COOKIE_NAME,
    value,
    options: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 300,
    },
  };
}

export function clearRecoveryCookie() {
  return {
    name: RECOVERY_COOKIE_NAME,
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
