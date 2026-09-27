import { createHmac, timingSafeEqual } from "node:crypto";

export const WORKSPACE_PREFERENCE_COOKIE = "knora_workspace_preference";
const DAYS_30_SECONDS = 30 * 24 * 60 * 60;

export type PreferenceIdentity = { issuer: string; subject: string };

function signingKey(): string {
  const value = process.env.SESSION_SECRET;
  if (!value && process.env.NODE_ENV === "production")
    throw new Error("SESSION_SECRET is required");
  return value ?? "development-only-session-secret-change-me";
}

function signature(payload: string): Buffer {
  return createHmac("sha256", signingKey()).update(payload).digest();
}

export async function encodePreference(
  workspaceId: string,
  identity: PreferenceIdentity,
  now = Date.now(),
): Promise<string> {
  if (!workspaceId || !identity.issuer || !identity.subject)
    throw new Error("Preference identity is incomplete");
  const payload = Buffer.from(
    JSON.stringify({
      version: 1,
      issuer: identity.issuer,
      subject: identity.subject,
      workspaceId,
      expiresAt: Math.floor(now / 1000) + DAYS_30_SECONDS,
    }),
  ).toString("base64url");
  return `${payload}.${signature(payload).toString("base64url")}`;
}

export async function decodePreference(
  value: string | undefined,
  identity: PreferenceIdentity,
  now = Date.now(),
): Promise<string | null> {
  if (!value || !identity.issuer || !identity.subject) return null;
  const parts = value.split(".");
  if (parts.length !== 2 || !parts[0] || !parts[1]) return null;
  const expected = signature(parts[0]);
  const provided = Buffer.from(parts[1], "base64url");
  if (
    parts[1] !== provided.toString("base64url") ||
    provided.length !== expected.length ||
    !timingSafeEqual(provided, expected)
  )
    return null;
  try {
    const payload = JSON.parse(
      Buffer.from(parts[0], "base64url").toString("utf8"),
    ) as Record<string, unknown>;
    if (
      payload.version !== 1 ||
      payload.issuer !== identity.issuer ||
      payload.subject !== identity.subject ||
      typeof payload.workspaceId !== "string" ||
      !payload.workspaceId ||
      typeof payload.expiresAt !== "number" ||
      payload.expiresAt <= Math.floor(now / 1000)
    )
      return null;
    return payload.workspaceId;
  } catch {
    return null;
  }
}

export function preferenceCookie(value: string) {
  return {
    name: WORKSPACE_PREFERENCE_COOKIE,
    value,
    options: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax" as const,
      path: "/",
      maxAge: DAYS_30_SECONDS,
    },
  };
}

export function clearPreferenceCookie() {
  return {
    ...preferenceCookie(""),
    options: { ...preferenceCookie("").options, maxAge: 0 },
  };
}
