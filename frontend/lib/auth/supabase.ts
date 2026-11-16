import { createLocalJWKSet, jwtVerify } from "jose";
import { randomUUID } from "node:crypto";
import type { KnoraSession } from "./session";

export type SupabaseTokens = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};

export function getSupabaseConfig() {
  const url = process.env.SUPABASE_URL?.replace(/\/$/, "");
  const publishableKey = process.env.SUPABASE_PUBLISHABLE_KEY;
  const algorithm = (process.env.SUPABASE_JWT_ALGORITHM ?? "ES256") as
    | "ES256"
    | "RS256";
  if (!url || !publishableKey) {
    throw new Error(
      "SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be configured",
    );
  }
  return {
    url,
    publishableKey,
    algorithm,
    issuer: `${url}/auth/v1`,
    audience: "authenticated",
    jwksUrl: `${url}/auth/v1/.well-known/jwks.json`,
  };
}

let jwksCache: ReturnType<typeof createLocalJWKSet> | null = null;
let jwksCachedUrl: string | null = null;
let jwksExpiresAt = 0;

export function _resetJwksCache(): void {
  jwksCache = null;
  jwksCachedUrl = null;
  jwksExpiresAt = 0;
}

async function getJWKS(url: string) {
  const now = Math.floor(Date.now() / 1000);
  if (!jwksCache || jwksCachedUrl !== url || now > jwksExpiresAt) {
    let res: Response;
    try {
      res = await fetch(url, {
        cache: "no-store",
        signal: AbortSignal.timeout(5000),
      });
    } catch {
      const err = new Error(`Failed to fetch Supabase JWKS from ${url}`);
      (err as unknown as { status: number }).status = 503;
      throw err;
    }
    if (!res.ok) {
      const err = new Error(
        `Failed to fetch Supabase JWKS from ${url}: status ${res.status}`,
      );
      (err as unknown as { status: number }).status =
        res.status === 429 ? 429 : 503;
      throw err;
    }
    const jwksJson = (await res.json()) as { keys: any[] };
    jwksCache = createLocalJWKSet(jwksJson);
    jwksCachedUrl = url;
    jwksExpiresAt = now + 300;
  }
  return jwksCache;
}

export async function verifySupabaseJwt(accessToken: string): Promise<{
  sub: string;
  sessionId: string;
  issuer: string;
}> {
  const config = getSupabaseConfig();
  const jwks = await getJWKS(config.jwksUrl);
  const { payload } = await jwtVerify(accessToken, jwks, {
    issuer: config.issuer,
    audience: config.audience,
    algorithms: [config.algorithm],
  });

  if (typeof payload.sub !== "string" || !payload.sub) {
    throw new Error("Supabase JWT missing valid sub claim");
  }
  if (typeof payload.session_id !== "string" || !payload.session_id) {
    throw new Error("Supabase JWT missing valid session_id claim");
  }
  if (payload.role !== "authenticated" || payload.is_anonymous === true) {
    throw new Error(
      "Supabase JWT must have role authenticated and not be anonymous",
    );
  }

  return {
    sub: payload.sub,
    sessionId: payload.session_id,
    issuer: config.issuer,
  };
}

export async function fetchBackendSession(accessToken: string): Promise<{
  capabilities: string[];
  sessionId: string | null;
}> {
  const apiUrl = process.env.KNORA_API_URL || "http://127.0.0.1:8000";
  let res: Response;
  try {
    res = await fetch(`${apiUrl}/v1/auth/session`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
  } catch (_err) {
    const error = new Error("AUTH_PROVIDER_UNAVAILABLE");
    (error as unknown as { status: number }).status = 503;
    throw error;
  }
  if (!res.ok) {
    if (res.status === 503 || res.status === 429 || res.status >= 500) {
      const err = new Error("AUTH_PROVIDER_UNAVAILABLE");
      (err as unknown as { status: number }).status =
        res.status === 429 ? 429 : 503;
      throw err;
    }
    const err = new Error(`Backend session check failed: ${res.status}`);
    (err as unknown as { status: number }).status = res.status;
    throw err;
  }
  const data = (await res.json()) as {
    capabilities: string[];
    session_id?: string | null;
  };
  return {
    capabilities: data.capabilities || [],
    sessionId: data.session_id || null,
  };
}

export async function signInWithPassword(
  email: string,
  password: string,
): Promise<KnoraSession> {
  const config = getSupabaseConfig();
  const endpoint = `${config.url}/auth/v1/token?grant_type=password`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      apikey: config.publishableKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
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
        "Invalid login credentials",
    );
  }

  const tokens = (await response.json()) as SupabaseTokens;
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
    expiresAt: now + (tokens.expires_in || 3600),
    sessionExpiresAt: now + 8 * 3600,
    sessionId: randomUUID(),
    capabilities: backend.capabilities,
    workspaceIds: [],
  };
}

export async function registerWithPassword(
  email: string,
  password: string,
  displayName?: string,
): Promise<KnoraSession> {
  const config = getSupabaseConfig();
  const endpoint = `${config.url}/auth/v1/signup`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      apikey: config.publishableKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password,
      data: displayName ? { name: displayName } : undefined,
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
      errorBody.error_description || errorBody.msg || "Registration failed",
    );
  }

  const data = (await response.json()) as {
    session?: SupabaseTokens;
    access_token?: string;
  };
  const tokens = (data.session || data) as SupabaseTokens;
  if (!tokens.access_token) {
    throw new Error(
      "Registration succeeded but no session returned. Check confirmation settings.",
    );
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
    expiresAt: now + (tokens.expires_in || 3600),
    sessionExpiresAt: now + 8 * 3600,
    sessionId: randomUUID(),
    capabilities: backend.capabilities,
    workspaceIds: [],
  };
}

export async function refreshSupabaseSession(
  session: KnoraSession,
): Promise<KnoraSession | null> {
  if (!session.refreshToken) return null;
  const config = getSupabaseConfig();
  const endpoint = `${config.url}/auth/v1/token?grant_type=refresh_token`;

  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: {
        apikey: config.publishableKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ refresh_token: session.refreshToken }),
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });
  } catch (_err) {
    const error = new Error("AUTH_PROVIDER_UNAVAILABLE");
    (error as unknown as { status: number }).status = 503;
    throw error;
  }

  if (!response.ok) {
    if (response.status === 429 || response.status >= 500) {
      const error = new Error("AUTH_PROVIDER_UNAVAILABLE");
      (error as unknown as { status: number }).status =
        response.status === 429 ? 429 : 503;
      throw error;
    }
    return null;
  }

  let tokens: SupabaseTokens;
  try {
    tokens = (await response.json()) as SupabaseTokens;
  } catch {
    const error = new Error("AUTH_PROVIDER_UNAVAILABLE");
    (error as unknown as { status: number }).status = 503;
    throw error;
  }

  let verified: { sub: string; sessionId: string; issuer: string };
  try {
    verified = await verifySupabaseJwt(tokens.access_token);
  } catch (err: unknown) {
    if (
      (err as { status?: number })?.status === 503 ||
      (err as { status?: number })?.status === 429 ||
      (err as Error)?.message?.includes("Failed to fetch Supabase JWKS")
    ) {
      const error = new Error("AUTH_PROVIDER_UNAVAILABLE");
      (error as unknown as { status: number }).status = 503;
      throw error;
    }
    return null;
  }

  // Subject and provider session ID must match
  if (verified.sub !== session.subject) return null;
  if (
    session.providerSessionId &&
    verified.sessionId !== session.providerSessionId
  ) {
    return null;
  }

  // Check backend state
  const backend = await fetchBackendSession(tokens.access_token);

  const now = Math.floor(Date.now() / 1000);
  return {
    provider: "supabase",
    providerSessionId: verified.sessionId,
    issuer: verified.issuer,
    subject: verified.sub,
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    expiresAt: now + (tokens.expires_in || 3600),
    sessionExpiresAt: session.sessionExpiresAt ?? now + 8 * 3600,
    sessionId: session.sessionId ?? randomUUID(),
    capabilities: backend.capabilities,
    workspaceIds: session.workspaceIds || [],
  };
}

export async function signOutSupabaseSession(
  session: KnoraSession,
  scope: "local" | "global" = "local",
): Promise<void> {
  const config = getSupabaseConfig();
  const endpoint = `${config.url}/auth/v1/logout?scope=${scope}`;

  let tokenToUse = session.accessToken;
  const now = Math.floor(Date.now() / 1000);

  // If access token is expired or expiring soon, but refresh token exists, refresh first
  if (session.refreshToken && session.expiresAt <= now) {
    try {
      const refreshed = await refreshSupabaseSession(session);
      if (refreshed?.accessToken) {
        tokenToUse = refreshed.accessToken;
      }
    } catch {
      // Continue with current access token
    }
  }

  let response = await fetch(endpoint, {
    method: "POST",
    headers: {
      apikey: config.publishableKey,
      Authorization: `Bearer ${tokenToUse}`,
      "Content-Type": "application/json",
    },
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
  });

  // If 401 received and we have a refresh token that wasn't refreshed yet, try refreshing once
  if (
    response.status === 401 &&
    session.refreshToken &&
    tokenToUse === session.accessToken
  ) {
    try {
      const refreshed = await refreshSupabaseSession(session);
      if (refreshed?.accessToken) {
        tokenToUse = refreshed.accessToken;
        response = await fetch(endpoint, {
          method: "POST",
          headers: {
            apikey: config.publishableKey,
            Authorization: `Bearer ${tokenToUse}`,
            "Content-Type": "application/json",
          },
          cache: "no-store",
          signal: AbortSignal.timeout(5000),
        });
      }
    } catch {
      // Keep existing response
    }
  }

  if (!response.ok) {
    throw new Error(`Supabase sign-out failed with status ${response.status}`);
  }
}
