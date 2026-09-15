import { cookies } from "next/headers";
import { jwtVerify, SignJWT, decodeJwt } from "jose";

export type KnoraSession = { subject: string; accessToken: string; workspaceIds: string[]; capabilities: string[]; expiresAt: number };
const COOKIE = "knora_session";
const secret = () => new TextEncoder().encode(process.env.SESSION_SECRET ?? "development-only-session-secret-change-me");

export async function encodeSession(session: Omit<KnoraSession, "expiresAt"> & { expiresAt?: number }): Promise<string> {
  const expiresAt = session.expiresAt ?? Math.floor(Date.now() / 1000) + 3600;
  return new SignJWT({ workspaceIds: session.workspaceIds, capabilities: session.capabilities, accessToken: session.accessToken, expiresAt })
    .setProtectedHeader({ alg: "HS256" }).setSubject(session.subject).setExpirationTime(expiresAt).sign(secret());
}
export async function decodeSession(value: string | undefined): Promise<KnoraSession | null> {
  if (!value) return null;
  try {
    const verified = await jwtVerify(value, secret());
    const p = verified.payload;
    if (typeof p.sub !== "string" || typeof p.accessToken !== "string" || !Array.isArray(p.workspaceIds) || !Array.isArray(p.capabilities)) return null;
    return { subject: p.sub, accessToken: p.accessToken, workspaceIds: p.workspaceIds.filter((x): x is string => typeof x === "string"), capabilities: p.capabilities.filter((x): x is string => typeof x === "string"), expiresAt: typeof p.expiresAt === "number" ? p.expiresAt : Number(p.exp ?? 0) };
  } catch { return null; }
}
export async function getSession(): Promise<KnoraSession | null> { return decodeSession((await cookies()).get(COOKIE)?.value); }
export function sessionCookie(value: string): { name: string; value: string; options: Record<string, unknown> } { return { name: COOKIE, value, options: { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 3600 } }; }
export function clearSessionCookie() { return { name: COOKIE, value: "", options: { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0 } }; }

export async function exchangeCode(code: string, redirectUri: string): Promise<KnoraSession> {
  const endpoint = process.env.KEYCLOAK_TOKEN_URL;
  if (!endpoint) throw new Error("KEYCLOAK_TOKEN_URL is not configured");
  const body = new URLSearchParams({ grant_type: "authorization_code", code, redirect_uri: redirectUri, client_id: process.env.KEYCLOAK_CLIENT_ID ?? "knora-web" });
  if (process.env.KEYCLOAK_CLIENT_SECRET) body.set("client_secret", process.env.KEYCLOAK_CLIENT_SECRET);
  const response = await fetch(endpoint, { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" }, body });
  if (!response.ok) throw new Error("OIDC token exchange failed");
  const token = await response.json() as { access_token?: string; expires_in?: number; id_token?: string };
  if (!token.access_token) throw new Error("OIDC response did not contain an access token");
  const claims = token.id_token ? decodeJwt(token.id_token) : decodeJwt(token.access_token);
  return { subject: typeof claims.sub === "string" ? claims.sub : "unknown", accessToken: token.access_token, workspaceIds: claimStrings(claims.workspace_ids), capabilities: claimStrings(claims.capabilities), expiresAt: Math.floor(Date.now() / 1000) + (token.expires_in ?? 3600) };
}
function claimStrings(value: unknown): string[] { return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []; }
export const SESSION_COOKIE_NAME = COOKIE;
